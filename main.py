import os
import socket
import logging
import tkinter as tk
from tkinter import messagebox
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import multiprocessing

# Observação: `webview` é importado dentro do processo filho para evitar
# conflitos/efeitos colaterais com o loop Tkinter no processo principal.
logging.basicConfig(
    filename="map_app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAP_FILE = os.path.abspath("map.html")  # caminho absoluto para local previsível do arquivo


def verificar_conexao(timeout: float = 2.0) -> bool:
    """Verifica se há conexão com a internet.

    Usa uma tentativa de conexão rápida ao DNS público do Google.
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except OSError:
        return False


def gerar_mapa(endereco: str) -> str | None:
    """Geocodifica o endereço e cria um arquivo HTML com o mapa.

    Retorna o caminho do arquivo salvo ou None em caso de falha.
    """
    if not verificar_conexao():
        messagebox.showerror("Erro", "Sem conexão com a internet.")
        return None

    geolocator = Nominatim(user_agent="map_app", timeout=5)

    try:
        location = geolocator.geocode(endereco)
    except GeocoderTimedOut:
        messagebox.showerror("Erro", "O geocodificador demorou demais. Tente novamente.")
        return None
    except GeocoderUnavailable:
        messagebox.showerror("Erro", "Serviço de geocodificação indisponível.")
        return None
    except Exception as e:
        logging.exception("Erro inesperado no geocoder")
        messagebox.showerror("Erro", f"Erro ao localizar o endereço: {e}")
        return None

    if location is None:
        messagebox.showwarning("Aviso", "Endereço não encontrado.")
        return None

    try:
        mapa = folium.Map(location=[location.latitude, location.longitude], zoom_start=16)
        folium.Marker([location.latitude, location.longitude], popup=endereco).add_to(mapa)
        mapa.save(MAP_FILE)
        logging.info("Mapa salvo em %s", MAP_FILE)
        return MAP_FILE
    except Exception:
        logging.exception("Erro ao gerar/salvar o mapa")
        messagebox.showerror("Erro", "Não foi possível gerar o mapa.")
        return None


def abrir_mapa_processo(caminho_html: str):
    """Abre o arquivo HTML em uma janela WebView (executado no processo filho).

    Mantemos essa função livre de qualquer código Tkinter para evitar conflitos
    entre loops de evento de GUI diferentes.
    """
    try:
        # Import local para evitar import-time side-effects no processo principal
        import webview

        if not os.path.isfile(caminho_html):
            logging.error("Arquivo HTML não encontrado no processo filho: %s", caminho_html)
            return

        webview.create_window("Mapa (Folium)", caminho_html)
        webview.start()
    except Exception:
        logging.exception("Erro no processo do WebView")


def buscar_command(entry_widget: tk.Entry):
    """Lê o endereço da entrada, gera o mapa e abre no WebView em processo filho."""
    endereco = entry_widget.get().strip()
    if not endereco:
        messagebox.showwarning("Aviso", "Digite um endereço.")
        return

    # Gera o mapa no processo principal (Tkinter roda aqui)
    html = gerar_mapa(endereco)
    if not html:
        return

    # Verifica que o arquivo foi criado
    if not os.path.isfile(html):
        messagebox.showerror("Erro", "Arquivo do mapa não foi criado corretamente.")
        logging.error("Arquivo do mapa não existe após salvar: %s", html)
        return

    # Inicia processo filho para o WebView (mantém Tk e WebView separados).
    # Note: target deve ser função de nível superior.
    p = multiprocessing.Process(target=abrir_mapa_processo, args=(html,), daemon=True)
    p.start()
    logging.info("Processo WebView iniciado (PID: %s)", p.pid)


def criar_interface():
    janela = tk.Tk()
    janela.title("Mapa com Folium")
    janela.geometry("460x170")
    janela.resizable(False, False)

    frame = tk.Frame(janela)
    frame.pack(pady=12, padx=12, fill="x")

    lbl = tk.Label(frame, text="Digite um endereço (ex.: 'São Paulo' ou 'Avenida Paulista 1000')", anchor="w")
    lbl.pack(fill="x")

    entrada = tk.Entry(frame, font=("Arial", 12))
    entrada.pack(fill="x", pady=8)

    btn = tk.Button(frame, text="Gerar mapa", width=20, command=lambda: buscar_command(entrada))
    btn.pack(pady=4)

    info = tk.Label(frame, text="O mapa abrirá em uma janela separada (WebView).", fg="gray")
    info.pack(fill="x", pady=(8, 0))

    return janela


if __name__ == "__main__":
    # No Windows, forçar 'spawn' para evitar problemas com múltiplos processos.
    multiprocessing.set_start_method("spawn", force=True)

    # Executa a interface Tkinter no processo principal.
    app = criar_interface()
    app.mainloop()