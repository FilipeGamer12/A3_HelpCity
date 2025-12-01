'''
Testes para o arquivo main.py, com foco em aumentar a cobertura de testes.
'''
import os
import json
import socket
import tempfile
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock, mock_open
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Adicionar o diretório do projeto ao sys.path para permitir a importação do main
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mockar o módulo pywebview ANTES de importar o main
# Isso garante que qualquer 'import webview' dentro de main.py use nosso mock
mock_pywebview = MagicMock()
sys.modules['webview'] = mock_pywebview

import main

# Mock para as classes e funções do Tkinter
@pytest.fixture
def mock_tkinter(monkeypatch):
    '''Mock para as classes e funções do Tkinter.'''
    mock_tk = MagicMock()
    monkeypatch.setattr("main.tk.Tk", mock_tk)
    monkeypatch.setattr("main.tk.Frame", MagicMock())
    monkeypatch.setattr("main.tk.Label", MagicMock())
    monkeypatch.setattr("main.tk.Entry", MagicMock())
    monkeypatch.setattr("main.tk.Button", MagicMock())
    monkeypatch.setattr("main.tk.Checkbutton", MagicMock())
    monkeypatch.setattr("main.tk.Radiobutton", MagicMock())
    monkeypatch.setattr("main.tk.StringVar", MagicMock())
    monkeypatch.setattr("main.tk.IntVar", MagicMock())
    monkeypatch.setattr("main.ttk.Combobox", MagicMock())
    monkeypatch.setattr("main.messagebox.showerror", MagicMock())
    monkeypatch.setattr("main.messagebox.showwarning", MagicMock())
    return mock_tk

class TestVerificarConexao:
    '''Testes para a função de verificação de conexão com a internet.'''

    def test_conexao_disponivel(self):
        '''Testa o cenário em que a conexão com a internet está disponível.'''
        with patch('socket.create_connection') as mock_socket:
            mock_socket.return_value = Mock()
            assert main.verificar_conexao() is True

    def test_conexao_indisponivel(self):
        '''Testa o cenário em que a conexão com a internet está indisponível.'''
        with patch('socket.create_connection', side_effect=OSError("Network error")):
            assert main.verificar_conexao() is False

class TestObterLocalizacaoIP:
    '''Testes para a função de obtenção de localização por IP.'''

    @patch('main.verificar_conexao', return_value=True)
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_sucesso(self, mock_urlopen, mock_conexao):
        '''Testa a obtenção bem-sucedida de localização por IP.'''
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "success",
            "lat": -25.4284,
            "lon": -49.2733
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        assert main.obter_localizacao_usuario_ip() == (-25.4284, -49.2733)

    @patch('main.verificar_conexao', return_value=False)
    def test_localizacao_ip_sem_conexao(self, mock_conexao):
        '''Testa o comportamento quando não há conexão com a internet.'''
        assert main.obter_localizacao_usuario_ip() is None

    @patch('main.verificar_conexao', return_value=True)
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_api_falha(self, mock_urlopen, mock_conexao):
        '''Testa o comportamento quando a API de geolocalização por IP falha.'''
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "fail"}).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        assert main.obter_localizacao_usuario_ip() is None

    @patch('main.verificar_conexao', return_value=True)
    @patch('urllib.request.urlopen', side_effect=Exception("Erro de conexão"))
    def test_localizacao_ip_excecao(self, mock_urlopen, mock_conexao):
        '''Testa o tratamento de exceções durante a chamada da API.'''
        assert main.obter_localizacao_usuario_ip() is None

class TestGeocodeEndereco:
    '''Testes para a função de geocodificação de endereços.'''

    @patch('main.Nominatim')
    def test_geocode_sucesso(self, mock_nominatim):
        '''Testa a geocodificação bem-sucedida de um endereço.'''
        mock_geolocator = Mock()
        mock_location = Mock(latitude=-25.4284, longitude=-49.2733)
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator
        assert main.geocode_endereco("Curitiba, PR") == (-25.4284, -49.2733)

    @patch('main.Nominatim')
    def test_geocode_falha(self, mock_nominatim):
        '''Testa o comportamento quando a geocodificação falha.'''
        mock_geolocator = Mock()
        mock_geolocator.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator
        assert main.geocode_endereco("Endereço Inválido") is None

    @patch('main.Nominatim')
    def test_geocode_timeout(self, mock_nominatim):
        '''Testa o tratamento de timeout durante a geocodificação.'''
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = GeocoderTimedOut
        mock_nominatim.return_value = mock_geolocator
        assert main.geocode_endereco("Curitiba, PR") is None

    @patch('main.Nominatim')
    def test_geocode_servico_indisponivel(self, mock_nominatim):
        '''Testa o tratamento de indisponibilidade do serviço de geocodificação.'''
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = GeocoderUnavailable
        mock_nominatim.return_value = mock_geolocator
        assert main.geocode_endereco("Curitiba, PR") is None

    def test_geocode_endereco_vazio(self):
        '''Testa o comportamento com endereço vazio.'''
        assert main.geocode_endereco("") is None

class TestPerfilOSRM:
    '''Testes para a função de conversão de perfil de transporte para o OSRM.'''

    def test_perfis_conhecidos(self):
        '''Testa a conversão de perfis de transporte conhecidos.'''
        assert main.perfil_osrm_para_query("car") == "driving"
        assert main.perfil_osrm_para_query("foot") == "walking"
        assert main.perfil_osrm_para_query("bike") == "cycling"

    def test_perfil_desconhecido(self):
        '''Testa o comportamento com um perfil de transporte desconhecido.'''
        assert main.perfil_osrm_para_query("unknown") == "driving"

class TestObterRotaOSRM:
    '''Testes para a função de obtenção de rota do OSRM.'''

    @patch('urllib.request.urlopen')
    def test_rota_sucesso(self, mock_urlopen):
        '''Testa a obtenção bem-sucedida de uma rota.'''
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": [{
                "geometry": {
                    "coordinates": [[-49.2733, -25.4284], [-49.2800, -25.4300]]
                },
                "distance": 5000.5,
                "duration": 600.0
            }]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800, "car")
        assert resultado is not None
        assert resultado["distance_m"] == 5000.5

    @patch('urllib.request.urlopen')
    def test_rota_sem_resultados(self, mock_urlopen):
        '''Testa o comportamento quando não há rotas disponíveis.'''
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"routes": []}).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        assert main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800) is None

    @patch('urllib.request.urlopen', side_effect=Exception("Erro de API"))
    def test_rota_erro_api(self, mock_urlopen):
        '''Testa o tratamento de erro na API do OSRM.'''
        assert main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800) is None

class TestGerarMapaComRota:
    '''Testes para a função de geração de mapa com rota.'''

    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_com_rota_sucesso(self, mock_map, mock_rota):
        '''Testa a geração bem-sucedida de um mapa com rota.'''
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000.5,
            "duration_s": 600.0,
            "raw": {}
        }
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        resultado = main.gerar_mapa_com_rota(-25.4284, -49.2733, -25.4300, -49.2800, "Destino", "car")
        assert resultado is not None
        assert "file" in resultado
        mock_map_instance.save.assert_called_once()

    @patch('main.obter_rota_osrm', return_value=None)
    @patch('folium.Map')
    def test_gerar_mapa_sem_rota(self, mock_map, mock_rota):
        '''Testa a geração de mapa quando a rota não está disponível.'''
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        resultado = main.gerar_mapa_com_rota(-25.4284, -49.2733, -25.4300, -49.2800, "Destino", "car")
        assert resultado is not None
        assert resultado["distance_km"] is None

    @patch('main.obter_rota_osrm', side_effect=Exception("Erro ao obter rota"))
    def test_gerar_mapa_excecao_rota(self, mock_rota):
        '''Testa o tratamento de exceção ao obter a rota.'''
        assert main.gerar_mapa_com_rota(0, 0, 1, 1, "Destino", "car") is None

class TestBuscarEMostrar:
    '''Testes para a função principal de busca e exibição de rota.'''

    @patch('main.messagebox')
    @patch('main.geocode_endereco')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.multiprocessing.Process')
    def test_buscar_e_mostrar_sucesso(self, mock_process, mock_gerar_mapa, mock_geocode, mock_messagebox):
        '''Testa o fluxo de sucesso da função buscar_e_mostrar.'''
        entry_origin = Mock(get=Mock(return_value="Origem"))
        combo_dest = Mock(get=Mock(return_value="Destino"))
        use_gps_var = Mock(get=Mock(return_value=0))
        perfil_var = Mock(get=Mock(return_value="car"))
        exibir_nomes = Mock(get=Mock(return_value=0))

        mock_geocode.side_effect = [(-25.0, -49.0), (-25.5, -49.5)]
        mock_gerar_mapa.return_value = {"file": "map.html"}
        mock_process_instance = MagicMock()
        mock_process.return_value = mock_process_instance

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        mock_gerar_mapa.assert_called_once()
        mock_process.assert_called_once()
        mock_process_instance.start.assert_called_once()

    @patch('main.messagebox')
    def test_buscar_e_mostrar_sem_destino(self, mock_messagebox):
        '''Testa o comportamento quando o destino não é fornecido.'''
        combo_dest = Mock(get=Mock(return_value=""))
        main.buscar_e_mostrar(Mock(), combo_dest, Mock(), Mock(), Mock())
        mock_messagebox.showwarning.assert_called_once()

    @patch('main.messagebox')
    @patch('main.obter_localizacao_usuario_ip', return_value=None)
    def test_buscar_e_mostrar_sem_origem_e_sem_ip(self, mock_ip, mock_messagebox):
        '''Testa o comportamento quando não há origem nem localização por IP.'''
        entry_origin = Mock(get=Mock(return_value=""))
        use_gps_var = Mock(get=Mock(return_value=0))
        main.buscar_e_mostrar(entry_origin, Mock(get=Mock(return_value="Destino")), use_gps_var, Mock(), Mock())
        mock_messagebox.showerror.assert_called_once()

    @patch('main.messagebox')
    @patch('main.geocode_endereco', return_value=None)
    def test_buscar_e_mostrar_geocode_falha(self, mock_geocode, mock_messagebox):
        '''Testa o comportamento quando a geocodificação do destino falha.'''
        entry_origin = Mock(get=Mock(return_value="Origem"))
        main.buscar_e_mostrar(entry_origin, Mock(get=Mock(return_value="Destino")), Mock(get=Mock(return_value=0)), Mock(), Mock())
        mock_messagebox.showerror.assert_called_once()

    @patch('main.messagebox')
    @patch('main.geocode_endereco', side_effect=[(-25.0, -49.0), (-25.5, -49.5)])
    @patch('main.gerar_mapa_com_rota', return_value=None)
    def test_buscar_e_mostrar_gerar_mapa_falha(self, mock_gerar_mapa, mock_geocode, mock_messagebox):
        '''Testa o comportamento quando a geração do mapa falha.'''
        main.buscar_e_mostrar(Mock(get=Mock(return_value="Origem")), Mock(get=Mock(return_value="Destino")), Mock(get=Mock(return_value=0)), Mock(), Mock())
        mock_messagebox.showerror.assert_called_once()

class TestInterfaceTkinter:
    '''Testes para a interface gráfica Tkinter.'''

    def test_criar_interface(self, mock_tkinter):
        '''Testa a criação da interface gráfica.'''
        janela = main.criar_interface()
        assert janela is not None
        mock_tkinter.assert_called_once()

@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    '''Remove a necessidade de requisições de rede para os testes.'''
    monkeypatch.delattr("requests.sessions.Session.request", raising=False)

@pytest.fixture(autouse=True)
def mock_os_path(monkeypatch):
    '''Mock para as funções de os.path.'''
    monkeypatch.setattr("os.path.exists", lambda path: True)
    monkeypatch.setattr("os.path.isfile", lambda path: True)
    monkeypatch.setattr("os.remove", lambda path: None)

class TestAbrirMapaProcesso:
    '''Testes para a função que abre o mapa em um processo separado.'''

    def test_abrir_mapa_sucesso(self):
        '''Testa a abertura bem-sucedida do mapa.'''
        mock_pywebview.reset_mock()
        main.abrir_mapa_processo("map.html")
        mock_pywebview.create_window.assert_called_once()
        mock_pywebview.start.assert_called_once()

    @patch('os.path.isfile', return_value=False)
    @patch('main.logging')
    def test_abrir_mapa_arquivo_nao_encontrado(self, mock_logging, mock_isfile):
        '''Testa o comportamento quando o arquivo HTML do mapa não é encontrado.'''
        mock_pywebview.reset_mock()
        main.abrir_mapa_processo("map.html")
        mock_logging.error.assert_called_once()
        mock_pywebview.create_window.assert_not_called()

    @patch('os.path.isfile', return_value=True)
    @patch('main.logging')
    def test_abrir_mapa_excecao(self, mock_logging, mock_isfile):
        '''Testa o tratamento de exceção ao abrir o mapa.'''
        mock_pywebview.reset_mock()
        mock_pywebview.start.side_effect = Exception("Erro no webview")
        main.abrir_mapa_processo("map.html")
        mock_logging.exception.assert_called_once()
        mock_pywebview.start.side_effect = None # Resetar para não afetar outros testes

class TestObterGPSViaWebview:
    '''Testes para a função de obtenção de GPS via webview.'''

    @patch('main.multiprocessing.Process')
    @patch('os.path.exists', side_effect=[False, True])
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({'lat': 1.0, 'lon': 2.0}))
    def test_obter_gps_sucesso(self, mock_open, mock_exists, mock_process):
        '''Testa a obtenção bem-sucedida de coordenadas GPS.'''
        with patch('time.sleep'):
            coords = main.obter_gps_via_webview()
            assert coords == (1.0, 2.0)

    @patch('main.multiprocessing.Process')
    @patch('os.path.exists', return_value=False)
    def test_obter_gps_timeout(self, mock_exists, mock_process):
        '''Testa o comportamento de timeout na obtenção de GPS.'''
        with patch('time.sleep'):
            assert main.obter_gps_via_webview(timeout=0.1) is None

    @patch('main.multiprocessing.Process')
    @patch('os.path.exists', side_effect=[False, True])
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({'error': 'denied'}))
    def test_obter_gps_com_erro(self, mock_open, mock_exists, mock_process):
        '''Testa o comportamento quando o arquivo de localização contém um erro.'''
        with patch('time.sleep'):
            assert main.obter_gps_via_webview() is None

    @patch('main.multiprocessing.Process')
    @patch('os.path.exists', side_effect=[False, True])
    @patch('builtins.open', side_effect=Exception("Erro de leitura"))
    def test_obter_gps_excecao_leitura(self, mock_open, mock_exists, mock_process):
        '''Testa o tratamento de exceção ao ler o arquivo de localização.'''
        with patch('time.sleep'):
            assert main.obter_gps_via_webview() is None

    @patch('main.multiprocessing.Process')
    def test_obter_gps_processo_morto(self, mock_process):
        '''Testa o comportamento quando o processo filho morre inesperadamente.'''
        mock_p = MagicMock()
        mock_p.is_alive.return_value = False
        mock_process.return_value = mock_p
        with patch('time.sleep'):
            assert main.obter_gps_via_webview(timeout=0.1) is None
            mock_p.terminate.assert_not_called()

class TestWebviewGetLocationProcess:
    '''Testes para a função executada no processo filho do webview.'''

    def test_processo_sucesso(self):
        '''Testa a execução bem-sucedida do processo.'''
        mock_pywebview.reset_mock()
        main.webview_get_location_process("test.json")
        mock_pywebview.create_window.assert_called_once()
        mock_pywebview.start.assert_called_once()

    @patch('builtins.open', new_callable=mock_open)
    @patch('main.logging')
    def test_processo_sem_webview(self, mock_logging, mock_open):
        '''Testa o comportamento quando a biblioteca webview não está instalada (simulando ImportError).'''
        mock_pywebview.reset_mock()
        with patch.dict('sys.modules', {'webview': None}):
            main.webview_get_location_process("test.json")
            mock_open.assert_called_with("test.json", "w", encoding="utf-8")
            mock_logging.exception.assert_called_once()

class TestApi:
    '''Testes para a classe Api usada pelo webview.'''

    @patch('builtins.open', new_callable=mock_open)
    def test_report_location(self, mock_open):
        '''Testa o método reportLocation.'''
        mock_pywebview.reset_mock()
        mock_window = MagicMock()
        mock_pywebview.windows = [mock_window]
        api = main.Api("test.json")
        api.reportLocation(1.0, 2.0)
        mock_open.assert_called_with("test.json", "w", encoding="utf-8")
        mock_window.destroy.assert_called_once()

    @patch('builtins.open', side_effect=Exception("Erro de escrita"))
    @patch('logging.exception')
    def test_report_location_excecao(self, mock_log_exception, mock_open):
        '''Testa o tratamento de exceção em reportLocation.'''
        mock_pywebview.reset_mock()
        api = main.Api("test.json")
        assert not api.reportLocation(1.0, 2.0)
        mock_log_exception.assert_called_once()

    @patch('builtins.open', new_callable=mock_open)
    def test_report_error(self, mock_open):
        '''Testa o método reportError.'''
        mock_pywebview.reset_mock()
        mock_window = MagicMock()
        mock_pywebview.windows = [mock_window]
        api = main.Api("test.json")
        api.reportError("denied")
        mock_open.assert_called_with("test.json", "w", encoding="utf-8")
        mock_window.destroy.assert_called_once()

    @patch('builtins.open', side_effect=Exception("Erro de escrita"))
    @patch('logging.exception')
    def test_report_error_excecao(self, mock_log_exception, mock_open):
        '''Testa o tratamento de exceção em reportError.'''
        mock_pywebview.reset_mock()
        api = main.Api("test.json")
        assert api.reportError("denied")
        mock_log_exception.assert_called_once()

    def test_destroy_window_excecao(self):
        '''Testa o tratamento de exceção ao destruir a janela.'''
        mock_pywebview.reset_mock()
        mock_window = MagicMock()
        mock_window.destroy.side_effect = Exception("Erro ao fechar")
        mock_pywebview.windows = [mock_window]
        api = main.Api("test.json")
        with patch('builtins.open', new_callable=mock_open):
            api.reportLocation(1.0, 2.0)
            mock_window.destroy.assert_called_once()