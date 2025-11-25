"""
main.py
Requisitos:
pip install folium geopy pywebview
Execute com: py -3.12 main.py  (Windows) ou python main.py

O script:
- Permite digitar origem e destino (origem opcional).
- Possui checkbox "Usar minha localização (GPS)". Se marcado:
    1) tenta obter GPS via WebView (permite solicitar permissão no navegador embedado)
    2) se falhar ou timeout, usa geolocalização por IP (ip-api.com)
- Calcula rota via OSRM (driving/walking/cycling)
- Exibe distância (km) e tempo (min) no popup do destino
- Abre mapa interativo em janela WebView separada (para não quebrar Tkinter)
"""

import os
import socket
import json
import logging
import urllib.request
import tempfile
import time
import multiprocessing
import tkinter as tk
from tkinter import messagebox
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

logging.basicConfig(
    filename="map_app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAP_FILE = os.path.abspath("map.html")
TEMP_LOC_FILE = os.path.join(tempfile.gettempdir(), "map_app_user_loc.json")


# ---------------------------
# Utilitários de rede / IO
# ---------------------------
def verificar_conexao(timeout: float = 2.0) -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except OSError:
        return False


# ---------------------------
# GPS via WebView (child process)
# ---------------------------
def webview_get_location_process(out_file: str, timeout_s: int = 10):
    """
    Função executada no processo filho:
    - cria uma pequena janela webview com HTML/JS que solicita geolocalização (navigator.geolocation)
    - quando obtém coords, chama a API Python exposta (reportLocation) para gravar JSON em out_file e fecha a janela
    Observação: esta função roda apenas no processo filho (spawn).
    """
    try:
        import webview
        import threading

        class Api:
            def __init__(self, out_file_path):
                self.out_file = out_file_path

            def reportLocation(self, lat, lon):
                try:
                    payload = {"lat": float(lat), "lon": float(lon), "ts": time.time()}
                    with open(self.out_file, "w", encoding="utf-8") as f:
                        json.dump(payload, f)
                    # fecha a janela (chamada do JS)
                    # A chamada abaixo funciona quando chamada pelo JS exposto; mas para garantir,
                    # também definimos timeout que fecha a janela mais tarde.
                    try:
                        webview.windows[0].destroy()
                    except Exception:
                        pass
                    return True
                except Exception as e:
                    logging.exception("Falha ao gravar localização no arquivo: %s", e)
                    return False

            def reportError(self, msg):
                try:
                    payload = {"error": str(msg), "ts": time.time()}
                    with open(self.out_file, "w", encoding="utf-8") as f:
                        json.dump(payload, f)
                except Exception:
                    logging.exception("Erro ao gravar erro de localização")
                try:
                    webview.windows[0].destroy()
                except Exception:
                    pass
                return True

        api = Api(out_file)

        # HTML que solicita permissão de geolocalização e envia para a API Python
        html = """
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Obter localização</title></head>
        <body>
        <p>Solicitando localização...</p>
        <script>
        function success(pos) {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            try {
                // reportLocation é a função exposta pela API Python
                window.pywebview.api.reportLocation(lat, lon);
            } catch (e) {
                try { window.pywebview.api.reportError('Exposed API missing: ' + e.toString()); } catch(e) {}
            }
        }
        function error(err) {
            try {
                window.pywebview.api.reportError(err.message || 'permission_denied');
            } catch(e) {}
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(success, error, {timeout: 8000, maximumAge: 60000});
        } else {
            try { window.pywebview.api.reportError('geolocation_not_supported'); } catch(e) {}
        }
        // Safety: close after timeout if nothing happens
        setTimeout(() => {
            try { window.pywebview.api.reportError('timeout'); } catch(e) {}
        }, 10000);
        </script>
        </body>
        </html>
        """

        # cria janela - pequena e sem borda é possível, mas mantemos simples
        window = webview.create_window("Obter localização (GPS) — permita quando solicitado", html=html, js_api=api, width=400, height=150)
        webview.start(http_server=True)  # http_server True facilita a execução do HTML inline

    except Exception:
        logging.exception("Erro no processo WebView de geolocalização")
        # tentar escrever um erro para que o pai saiba
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump({"error": "webview_failed"}, f)
        except Exception:
            pass


def obter_gps_via_webview(timeout: int = 10) -> tuple | None:
    """
    Inicia processo filho que pede permissão de localização via webview.
    Espera o arquivo TEMP_LOC_FILE ser criado (ou atualizado) com coords.
    Retorna (lat, lon) ou None.
    """
    # remove arquivo antigo se existir
    try:
        if os.path.exists(TEMP_LOC_FILE):
            os.remove(TEMP_LOC_FILE)
    except Exception:
        pass

    p = multiprocessing.Process(target=webview_get_location_process, args=(TEMP_LOC_FILE,), daemon=True)
    p.start()
    logging.info("Processo GPS (WebView) iniciado (PID %s)", p.pid)

    # espera pelo arquivo (timeout)
    waited = 0.0
    poll_interval = 0.25
    while waited < timeout:
        if os.path.exists(TEMP_LOC_FILE):
            try:
                with open(TEMP_LOC_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "lat" in data and "lon" in data:
                    return float(data["lat"]), float(data["lon"])
                else:
                    # arquivo criado mas tem erro - treat as fail
                    logging.info("Arquivo temp com erro/sem coords: %s", data)
                    return None
            except Exception:
                logging.exception("Falha ao ler arquivo temp de localização")
                return None
        time.sleep(poll_interval)
        waited += poll_interval

    # timeout - tentar terminar processo e retornar None
    try:
        if p.is_alive():
            p.terminate()
    except Exception:
        pass
    logging.info("Timeout ao aguardar localização via WebView")
    return None


# ---------------------------
# Geolocação via IP (fallback)
# ---------------------------
def obter_localizacao_usuario_ip() -> tuple | None:
    if not verificar_conexao():
        return None
    try:
        url = "http://ip-api.com/json/"
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("status") == "success":
            return float(data["lat"]), float(data["lon"])
        else:
            logging.error("ip-api error: %s", data)
            return None
    except Exception:
        logging.exception("Erro ao obter localização via IP")
        return None


# ---------------------------
# Geocoding para endereços
# ---------------------------
def geocode_endereco(endereco: str):
    geolocator = Nominatim(user_agent="map_app", timeout=6)
    try:
        loc = geolocator.geocode(endereco)
        if loc:
            return float(loc.latitude), float(loc.longitude)
        else:
            return None
    except Exception:
        logging.exception("Erro no geocoder para: %s", endereco)
        return None


# ---------------------------
# OSRM routing
# ---------------------------
def perfil_osrm_para_query(perfil: str) -> str:
    """
    Mapear perfil UI -> OSRM profile
    UI: 'car', 'foot', 'bike', 'bus' (bus mapeado para walking como fallback)
    OSRM profiles: driving, walking, cycling
    """
    if perfil == "car":
        return "driving"
    if perfil == "foot":
        return "walking"
    if perfil == "bike":
        return "cycling"
    # fallback
    return "driving"


def obter_rota_osrm(lat1, lon1, lat2, lon2, perfil_ui="car"):
    profile = perfil_osrm_para_query(perfil_ui)
    url = (
        f"https://router.project-osrm.org/route/v1/{profile}/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&annotations=duration,distance"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.load(response)
        if "routes" not in data or not data["routes"]:
            logging.error("OSRM sem rotas: %s", data)
            return None
        route = data["routes"][0]
        # geometry coordinates: list [lon, lat]
        coords = route["geometry"]["coordinates"]
        # convert to (lat, lon)
        poly = [(float(lat), float(lon)) for lon, lat in coords]
        distance_m = float(route.get("distance", 0.0))
        duration_s = float(route.get("duration", 0.0))
        return {"poly": poly, "distance_m": distance_m, "duration_s": duration_s, "raw": route}
    except Exception:
        logging.exception("Erro ao consultar OSRM")
        return None


# ---------------------------
# Gera mapa com rota + popups
# ---------------------------
def gerar_mapa_com_rota(orig_lat, orig_lon, dest_lat, dest_lon, dest_label, perfil_ui="car"):
    try:
        mapa = folium.Map(location=[(orig_lat + dest_lat) / 2, (orig_lon + dest_lon) / 2], zoom_start=13)

        folium.Marker(
            [orig_lat, orig_lon],
            popup="Origem",
            tooltip="Origem",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(mapa)

        folium.Marker(
            [dest_lat, dest_lon],
            popup=dest_label,
            tooltip="Destino",
            icon=folium.Icon(color="red", icon="flag")
        ).add_to(mapa)

        # obter rota
        rota = obter_rota_osrm(orig_lat, orig_lon, dest_lat, dest_lon, perfil_ui=perfil_ui)
        if not rota:
            # salva mapa sem rota, mas avisa
            folium.map.Marker(
                [dest_lat, dest_lon],
                popup=f"{dest_label} (rota indisponível)",
            ).add_to(mapa)
            mapa.save(MAP_FILE)
            return {"file": MAP_FILE, "distance_km": None, "duration_min": None}

        # desenha polyline
        folium.PolyLine(rota["poly"], color="green", weight=5, opacity=0.85).add_to(mapa)

        # distancia e tempo
        dist_km = rota["distance_m"] / 1000.0
        dur_min = rota["duration_s"] / 60.0

        # popup com detalhes (formatado)
        popup_html = f"""
        <b>{dest_label}</b><br>
        Distância: {dist_km:.2f} km<br>
        Tempo estimado: {dur_min:.1f} min<br>
        Modo: {perfil_ui}
        """
        folium.Marker(
            [dest_lat, dest_lon],
            popup=popup_html,
            icon=folium.Icon(color="red")
        ).add_to(mapa)

        mapa.save(MAP_FILE)
        return {"file": MAP_FILE, "distance_km": dist_km, "duration_min": dur_min}

    except Exception:
        logging.exception("Erro ao gerar mapa com rota")
        return None


# ---------------------------
# AÇÃO do botão — lógica principal
# ---------------------------
def buscar_e_mostrar(entry_origin: tk.Entry, entry_dest: tk.Entry, use_gps_var: tk.IntVar, perfil_var: tk.StringVar):
    destino_text = entry_dest.get().strip()
    if not destino_text:
        messagebox.showwarning("Aviso", "Digite o destino.")
        return

    # determinar origem
    orig_coords = None
    # se usuário marcou usar GPS
    if use_gps_var.get() == 1:
        # tentar GPS via WebView
        gps = obter_gps_via_webview(timeout=10)
        if gps:
            orig_coords = gps  # (lat, lon)
            logging.info("Localização obtida via GPS WebView: %s", str(orig_coords))
        else:
            # fallback para IP
            ip_loc = obter_localizacao_usuario_ip()
            if ip_loc:
                orig_coords = ip_loc
                logging.info("GPS falhou; localização por IP usada: %s", str(orig_coords))
            else:
                messagebox.showerror("Erro", "Não foi possível obter sua localização (GPS/IP).")
                return
    else:
        # usuário forneceu origem manualmente?
        origin_text = entry_origin.get().strip()
        if origin_text:
            geoc = geocode_endereco(origin_text)
            if not geoc:
                messagebox.showerror("Erro", "Não foi possível geocodificar a origem.")
                return
            orig_coords = geoc
            logging.info("Origem manual geocodificada: %s -> %s", origin_text, str(orig_coords))
        else:
            # sem origem manual e sem GPS marcado: tentar IP automaticamente
            ip_loc = obter_localizacao_usuario_ip()
            if ip_loc:
                orig_coords = ip_loc
                logging.info("Nenhuma origem fornecida; usando localização por IP: %s", str(orig_coords))
            else:
                messagebox.showerror("Erro", "Forneça uma origem ou ative 'Usar minha localização'.")
                return

    # geocodifica destino
    dest_gc = geocode_endereco(destino_text)
    if not dest_gc:
        messagebox.showerror("Erro", "Não foi possível geocodificar o destino.")
        return
    dest_lat, dest_lon = dest_gc
    orig_lat, orig_lon = orig_coords

    perfil_ui = perfil_var.get()  # 'car', 'foot', 'bike', 'bus'

    # se usuário escolheu 'bus', avisar que usamos walking como fallback
    perfil_for_osrm = perfil_ui
    if perfil_ui == "bus":
        # OSRM não tem transporte público; avisar
        perfil_for_osrm = "foot"
        messagebox.showinfo("Observação", "Perfil 'Ônibus' não é suportado pelo OSRM. Usaremos 'a pé' como aproximação.")

    result = gerar_mapa_com_rota(orig_lat, orig_lon, dest_lat, dest_lon, destino_text, perfil_ui=perfil_for_osrm)
    if not result or "file" not in result:
        messagebox.showerror("Erro", "Erro ao gerar o mapa/rota.")
        return

    # abrir o mapa em webview separado (processo filho)
    html_path = result["file"]
    if not os.path.isfile(html_path):
        messagebox.showerror("Erro", "Arquivo do mapa não encontrado.")
        return

    # iniciar processo que abre o webview com o mapa
    p = multiprocessing.Process(target=abrir_mapa_processo, args=(html_path,), daemon=True)
    p.start()
    logging.info("WebView de mapa iniciado (PID %s). Distância: %s km, Tempo: %s min",
                 p.pid, str(result.get("distance_km")), str(result.get("duration_min")))


# ---------------------------
# Processo que abre mapa em WebView (reutilizado)
# ---------------------------
def abrir_mapa_processo(caminho_html: str):
    try:
        import webview
        if not os.path.isfile(caminho_html):
            logging.error("Arquivo HTML não encontrado: %s", caminho_html)
            return
        webview.create_window("Mapa com Rota", caminho_html, width=900, height=700)
        webview.start()
    except Exception:
        logging.exception("Erro no processo do WebView (mapa)")


# ---------------------------
# Interface Tkinter
# ---------------------------
def criar_interface():
    janela = tk.Tk()
    janela.title("Roteador — Folium + OSRM")
    janela.geometry("620x280")
    janela.resizable(False, False)

    pad = 10
    frame = tk.Frame(janela)
    frame.pack(padx=pad, pady=pad, fill="x")

    tk.Label(frame, text="Origem (deixe em branco para usar GPS/IP e marque 'Usar minha localização')").pack(fill="x")
    entry_origin = tk.Entry(frame, font=("Arial", 12))
    entry_origin.pack(fill="x", pady=(4, 8))

    # checkbox usar GPS
    use_gps_var = tk.IntVar(value=0)
    chk = tk.Checkbutton(frame, text="Usar minha localização (GPS ou IP - Instável)", variable=use_gps_var)
    chk.pack(anchor="w", pady=(0, 8))

    tk.Label(frame, text="Destino (endereço) *", anchor="w").pack(fill="x")
    entry_dest = tk.Entry(frame, font=("Arial", 12))
    entry_dest.pack(fill="x", pady=(4, 6))

    # modo de transporte
    mode_frame = tk.Frame(frame)
    mode_frame.pack(fill="x", pady=(6, 6))
    tk.Label(mode_frame, text="Modo:").pack(side="left")
    perfil_var = tk.StringVar(value="car")
    tk.Radiobutton(mode_frame, text="Carro", variable=perfil_var, value="car").pack(side="left", padx=6)
    tk.Radiobutton(mode_frame, text="A pé", variable=perfil_var, value="foot").pack(side="left", padx=6)
    tk.Radiobutton(mode_frame, text="Bicicleta", variable=perfil_var, value="bike").pack(side="left", padx=6)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(fill="x", pady=(10, 0))
    btn = tk.Button(btn_frame, text="Gerar rota e abrir mapa", width=24,
                    command=lambda: buscar_e_mostrar(entry_origin, entry_dest, use_gps_var, perfil_var))
    btn.pack(side="left", padx=(0, 8))

    info_label = tk.Label(frame, text="O mapa com rota abrirá em uma janela separada.\nCaso o GPS não funcione, será usado IP para localizar você.", fg="gray")
    info_label.pack(fill="x", pady=(12, 0))

    return janela


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    app = criar_interface()
    app.mainloop()