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
- Possui enderecos pre-definidos de unidades de saude para pontos de coleta
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
from tkinter import ttk

logging.basicConfig(
    filename="map_app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAP_FILE = os.path.abspath("map.html")
TEMP_LOC_FILE = os.path.join(tempfile.gettempdir(), "map_app_user_loc.json")


# ==========================================
# Enderecos de unidades de saude pre-definidos.
# ==========================================
# Adicionado nomes mais simples de se entender
# inves de ficar apenas no endereco,
# para melhor compreensao do usuario.
# ==========================================
ENDERECOS_PREDEFINIDOS = {

    "Unidade de Saúde Acesso Saúde - Barão do Serro Azul": "Rua Barão do Serro Azul, 198 - Centro, Curitiba - PR", # okay
    "Unidade de Saúde Bairro Alto - Alceu Chichorro": "Rua Alceu Chichorro, 314 - Bairro Alto, Curitiba - PR", # okay
    "Unidade de Saúde Ouvidor Pardinho": "Rua 24 de Maio, 807 - Centro, Curitiba", # okay
    "Unidade de Saúde Iracema": "Rua Prof. Nivaldo Braga, 1571 - Capão da Imbuia, Curitiba - PR", # okay
    "Unidade de Saúde Capanema": "Rua Manoel Martins de Abreu, 830 - Prado Velho, Curitiba - PR", # okay
    "Unidade de Saúde Guaíra - R. São Paulo": "Rua São Paulo, 1495 - Guaíra, Curitiba - PR", # okay
    "Unidade de Saúde Parolin - R. Sergipe": "Rua Sergipe, 59 - Guaíra, Curitiba - PR", # okay
    "Unidade de Saúde Fanny Lindóia": "Rua Conde dos Arcos, 295 - Lindoia, Curitiba - PR", # okay
    "Unidade de Saúde Vila Hauer": "Rua Waldemar Kost, 650 - Hauer, Curitiba - PR", # okay
    "Unidade de Saúde Tapajós": "Rua André Ferreira Camargo, 188 - Boqueirão, Curitiba - PR", # okay
    "UPA 24h Boqueirão": "Rua Professora Maria de Assumpção, 2590 - Boqueirão, Curitiba - PR", # okay
    "Unidade de Saúde São Paulo - Canal Belém": "Rua Canal Belém - 6427 - Uberaba, Curitiba - PR", # okay
    "Unidade de Saúde Uberaba de Cima": "Rua Cap. Leônidas Marques, 1392 - Uberaba, Curitiba - PR", # okay
    "Unidade de Saúde São Domingos - Ladislau Mikosz": "Rua Ladislau Mikosz, 133 - PR", # okay
    "Unidade de Saúde Trindade II": "Rua Sebastião Marcos Luiz, 1197 - Cajuru, Curitiba - PR", # okay
    "Unidade de Saúde Atuba - Colombo": "Rua Roger Bacon, 150 - Atuba, Colombo - PR", # okay

}



ENDERECOS_NOMES = list(ENDERECOS_PREDEFINIDOS.keys())
ENDERECOS_COMPLETOS = list(ENDERECOS_PREDEFINIDOS.values())

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
        <body style="background-color: white; padding: 20px; font-family: Arial;">
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
        window = webview.create_window("Obter localização (GPS) — permita quando solicitado", 
                                       html=html, js_api=api, width=500, height=250)
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


# Foi feita alteracoes na funcao geocode_endereco, pois com a implementacao de
# enderecos pre-definidos, a funcao dava timeout antes de comecar a procurar
# o local.

def geocode_endereco(endereco: str, tentativas=3):
    geolocator = Nominatim(user_agent="map_app", timeout=15)
    
    for tentativa in range(tentativas):
        try:
            loc = geolocator.geocode(endereco)
            if loc:
                return float(loc.latitude), float(loc.longitude)
            else:
                return None
                
        except GeocoderTimedOut:
            if tentativa < tentativas - 1:
                time.sleep(2)
            else:
                logging.exception("Erro no geocoder para: %s", endereco)
                return None
                
        except GeocoderUnavailable:
            if tentativa < tentativas - 1:
                time.sleep(2)
            else:
                logging.exception("Erro no geocoder para: %s", endereco)
                return None
                
        except Exception:
            logging.exception("Erro no geocoder para: %s", endereco)
            return None
    
    return None

# ---------------------------
# OSRM routing
# ---------------------------
def perfil_osrm_para_query(perfil: str) -> str:
    """
    Mapear perfil UI -> OSRM profile
    UI: 'car', 'foot', 'bike'
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

        rota = obter_rota_osrm(orig_lat, orig_lon, dest_lat, dest_lon, perfil_ui=perfil_ui)
        if not rota:
            folium.map.Marker(
                [dest_lat, dest_lon],
                popup=f"{dest_label} (rota indisponível)",
            ).add_to(mapa)
            mapa.save(MAP_FILE)
            return {"file": MAP_FILE, "distance_km": None, "duration_min": None}

        folium.PolyLine(rota["poly"], color="green", weight=5, opacity=0.85).add_to(mapa)

        dist_km = rota["distance_m"] / 1000.0
        dur_min = rota["duration_s"] / 60.0

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

        # popup no canto inferior esquerdo do html pra mostrar origem e destino do usuario
        info_html = f"""
        <div style="position: fixed; 
                    bottom: 10px; 
                    left: 10px; 
                    width: 300px; 
                    background-color: white; 
                    border: 2px solid grey; 
                    border-radius: 5px;
                    padding: 10px;
                    font-family: Arial;
                    font-size: 12px;
                    z-index: 9999;
                    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
            <b>📍 Origem:</b><br>Sua localização<br><br>
            <b>🎯 Destino:</b><br>{dest_label}
        </div>
        """
        # adiciona o html
        mapa.get_root().html.add_child(folium.Element(info_html))

        mapa.save(MAP_FILE)
        return {"file": MAP_FILE, "distance_km": dist_km, "duration_min": dur_min}

    except Exception:
        logging.exception("Erro ao gerar mapa com rota")
        return None

# ---------------------------
# AÇÃO do botão — lógica principal
# ---------------------------
def buscar_e_mostrar(entry_origin: tk.Entry, combo_dest: tk.Entry, use_gps_var: tk.IntVar, perfil_var: tk.StringVar, exibir_nomes: tk.IntVar):
    destino_selecionado = combo_dest.get().strip()
    if not destino_selecionado:
        messagebox.showwarning("Aviso", "Digite o destino.")
        return
    

     # Se estiver exibindo nomes, converte o nome para o endereco completo do local
    if exibir_nomes.get() == 1:
        destino_text = ENDERECOS_PREDEFINIDOS.get(destino_selecionado, destino_selecionado)
    # Se estiver exibindo endereços, usa direto
    else:
        destino_text = destino_selecionado

    # Remove o arquivo gerado html antigo para forcar novo calculo
    try:
        if os.path.exists(MAP_FILE):
            os.remove(MAP_FILE)
    except Exception:
        pass


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

    perfil_ui = perfil_var.get()  # 'car', 'foot', 'bike'

    result = gerar_mapa_com_rota(orig_lat, orig_lon, dest_lat, dest_lon, destino_text, perfil_ui=perfil_ui)
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
    janela.geometry("620x300")
    janela.resizable(False, False)


    # Label com o intuito da aplicacao

    tk.Label(
        janela,
        text="Aplicação para localização de unidades de saúde para coleta de recursos.",
        font=("Arial", 13, "bold"),
        ).pack(pady=(10, 0))

    pad = 10
    frame = tk.Frame(janela)
    frame.pack(padx=pad, pady=pad, fill="x")

    tk.Label(frame, text="Origem (deixe em branco para usar GPS/IP e marque 'Usar minha localização')").pack(fill="x")
    entry_origin = tk.Entry(frame, font=("Arial", 12))
    entry_origin.pack(fill="x", pady=(4, 8))

    use_gps_var = tk.IntVar(value=0)
    chk = tk.Checkbutton(frame, text="Usar minha localização (GPS ou IP - Instável)", variable=use_gps_var)
    chk.pack(anchor="w", pady=(0, 8))

    # Frame para o label e botao de toggle ficarem na mesma reta

    dest_frame = tk.Frame(frame)
    dest_frame.pack(fill="x", pady=(0, 6))
    tk.Label(dest_frame, text="Destino (selecione ou digite) *", anchor="w").pack(side="left")
    
    # variavel que controla se exibe nomes (1) ou enderecos completos (0)
    # e combobox inicia mostrando nomes das unidades
    exibir_nomes = tk.IntVar(value=1)
    combo_dest = ttk.Combobox(frame, values=ENDERECOS_NOMES, font=("Arial", 12))
    combo_dest.pack(fill="x", pady=(4, 6))

    # funcao que alterna entre mostrar nomes e enderecos completos
    def alternar_exibicao():
        if exibir_nomes.get() == 1:
            exibir_nomes.set(0)
            combo_dest['values'] = ENDERECOS_COMPLETOS
            btn_toggle.config(text="Exibir: Endereços ✓")
        else:
            exibir_nomes.set(1)
            combo_dest['values'] = ENDERECOS_NOMES
            btn_toggle.config(text="Exibir: Nomes ✓")
        combo_dest.set('')
    
    # botao pra alternar o modo da exibicao la
    btn_toggle = tk.Button(dest_frame, text="Exibir: Nomes ✓", command=alternar_exibicao)
    btn_toggle.pack(side="right", padx=(5, 0))

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
                command=lambda: buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes))
    btn.pack(side="left", padx=(0, 8))

    info_label = tk.Label(frame, text="O mapa com rota abrirá em uma janela separada.\nCaso o GPS não funcione, será usado IP para localizar você.", fg="gray")
    info_label.pack(fill="x", pady=(12, 0))

    return janela


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    app = criar_interface()
    app.mainloop()