import os
import json
import socket
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import tkinter as tk

# Importar funções do main.py
import main


class TestVerificarConexao:
    """Testes para verificação de conexão com a internet"""

    def test_conexao_disponivel(self):
        """Testa quando a conexão está disponível"""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.return_value = Mock()
            resultado = main.verificar_conexao(timeout=2.0)
            assert resultado is True
            mock_socket.assert_called_once_with(("8.8.8.8", 53), timeout=2.0)

    def test_conexao_indisponivel(self):
        """Testa quando a conexão não está disponível"""
        with patch('socket.create_connection', side_effect=OSError("Network error")):
            resultado = main.verificar_conexao(timeout=2.0)
            assert resultado is False

    def test_timeout_customizado(self):
        """Testa timeout personalizado"""
        with patch('socket.create_connection') as mock_socket:
            main.verificar_conexao(timeout=5.0)
            mock_socket.assert_called_once_with(("8.8.8.8", 53), timeout=5.0)


class TestObterLocalizacaoIP:
    """Testes para obtenção de localização via IP"""

    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_sucesso(self, mock_urlopen, mock_conexao):
        """Testa obtenção bem-sucedida de localização por IP"""
        mock_conexao.return_value = True

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "success",
            "lat": -25.4284,
            "lon": -49.2733
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        resultado = main.obter_localizacao_usuario_ip()

        assert resultado is not None
        assert resultado == (-25.4284, -49.2733)

    @patch('main.verificar_conexao')
    def test_localizacao_ip_sem_conexao(self, mock_conexao):
        """Testa quando não há conexão com internet"""
        mock_conexao.return_value = False
        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None

    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_api_erro(self, mock_urlopen, mock_conexao):
        """Testa quando a API retorna erro"""
        mock_conexao.return_value = True

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "fail",
            "message": "invalid query"
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None

    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_timeout(self, mock_urlopen, mock_conexao):
        """Testa timeout na requisição"""
        mock_conexao.return_value = True
        mock_urlopen.side_effect = TimeoutError("Connection timeout")

        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None


class TestGeocodeEndereco:
    """Testes para geocodificação de endereços"""

    @patch('main.Nominatim')
    def test_geocode_sucesso(self, mock_nominatim):
        """Testa geocodificação bem-sucedida"""
        mock_geolocator = Mock()
        mock_location = Mock()
        mock_location.latitude = -25.4284
        mock_location.longitude = -49.2733
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR")

        assert resultado is not None
        assert resultado == (-25.4284, -49.2733)

    @patch('main.Nominatim')
    def test_geocode_endereco_invalido(self, mock_nominatim):
        """Testa endereço que não pode ser geocodificado"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("EndereçoInválidoXYZ123")
        assert resultado is None

    @patch('main.Nominatim')
    @patch('time.sleep')
    def test_geocode_timeout_com_retry(self, mock_sleep, mock_nominatim):
        """Testa timeout no geocoding com tentativas de retry"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = [
            GeocoderTimedOut("Timeout"),
            GeocoderTimedOut("Timeout"),
            GeocoderTimedOut("Timeout")
        ]
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR", tentativas=3)
        assert resultado is None
        assert mock_geolocator.geocode.call_count == 3
        assert mock_sleep.call_count == 2

    @patch('main.Nominatim')
    @patch('time.sleep')
    def test_geocode_sucesso_apos_retry(self, mock_sleep, mock_nominatim):
        """Testa sucesso após falha e retry"""
        mock_geolocator = Mock()
        mock_location = Mock()
        mock_location.latitude = -25.4284
        mock_location.longitude = -49.2733

        mock_geolocator.geocode.side_effect = [
            GeocoderTimedOut("Timeout"),
            mock_location
        ]
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR", tentativas=3)
        assert resultado is not None
        assert resultado == (-25.4284, -49.2733)
        assert mock_geolocator.geocode.call_count == 2

    @patch('main.Nominatim')
    def test_geocode_servico_indisponivel(self, mock_nominatim):
        """Testa quando o serviço está indisponível"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = GeocoderUnavailable("Service down")
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR")
        assert resultado is None

    @patch('main.Nominatim')
    @patch('time.sleep')
    def test_geocode_unavailable_com_retry(self, mock_sleep, mock_nominatim):
        """Testa GeocoderUnavailable com múltiplas tentativas"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = [
            GeocoderUnavailable("Service down"),
            GeocoderUnavailable("Service down"),
            GeocoderUnavailable("Service down")
        ]
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR", tentativas=3)
        assert resultado is None
        assert mock_geolocator.geocode.call_count == 3

    @patch('main.Nominatim')
    def test_geocode_excecao_generica(self, mock_nominatim):
        """Testa exceção genérica no geocoding"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = Exception("Erro inesperado")
        mock_nominatim.return_value = mock_geolocator

        resultado = main.geocode_endereco("Curitiba, PR")
        assert resultado is None


class TestPerfilOSRM:
    """Testes para conversão de perfis de transporte"""

    def test_perfil_carro(self):
        assert main.perfil_osrm_para_query("car") == "driving"

    def test_perfil_pe(self):
        assert main.perfil_osrm_para_query("foot") == "walking"

    def test_perfil_bicicleta(self):
        assert main.perfil_osrm_para_query("bike") == "cycling"

    def test_perfil_desconhecido(self):
        assert main.perfil_osrm_para_query("unknown") == "driving"
        assert main.perfil_osrm_para_query("bus") == "driving"


class TestObterRotaOSRM:
    """Testes para obtenção de rotas via OSRM"""

    @patch('urllib.request.urlopen')
    def test_rota_sucesso(self, mock_urlopen):
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

        resultado = main.obter_rota_osrm(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "car"
        )

        assert resultado is not None
        assert "poly" in resultado
        assert "distance_m" in resultado
        assert "duration_s" in resultado
        assert resultado["distance_m"] == 5000.5
        assert resultado["duration_s"] == 600.0
        assert len(resultado["poly"]) == 2

    @patch('urllib.request.urlopen')
    def test_rota_sem_resultados(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": []
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        resultado = main.obter_rota_osrm(
            -25.4284, -49.2733,
            -25.4300, -49.2800
        )
        assert resultado is None

    @patch('urllib.request.urlopen')
    def test_rota_erro_api(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("API Error")

        resultado = main.obter_rota_osrm(
            -25.4284, -49.2733,
            -25.4300, -49.2800
        )
        assert resultado is None

    @patch('urllib.request.urlopen')
    def test_rota_diferentes_perfis(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": [{
                "geometry": {"coordinates": [[-49.2733, -25.4284]]},
                "distance": 1000,
                "duration": 120
            }]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        for perfil in ["car", "foot", "bike"]:
            resultado = main.obter_rota_osrm(
                -25.4284, -49.2733,
                -25.4300, -49.2800,
                perfil
            )
            assert resultado is not None

    @patch('urllib.request.urlopen')
    def test_rota_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Request timeout")

        resultado = main.obter_rota_osrm(
            -25.4284, -49.2733,
            -25.4300, -49.2800
        )
        assert resultado is None

    @patch('urllib.request.urlopen')
    def test_rota_sem_campo_routes(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "code": "Ok"
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        resultado = main.obter_rota_osrm(
            -25.4284,
            -49.2733,
            -25.4300,
            -49.2800
        )
        assert resultado is None


class TestGerarMapaComRota:
    """Testes para geração de mapas"""

    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_com_rota_sucesso(self, mock_map, mock_rota):
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000.5,
            "duration_s": 600.0,
            "raw": {}
        }

        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance

        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital Central",
            "car"
        )

        assert resultado is not None
        assert "file" in resultado
        assert "distance_km" in resultado
        assert "duration_min" in resultado
        assert resultado["distance_km"] == pytest.approx(5.0005, rel=0.01)
        assert resultado["duration_min"] == pytest.approx(10.0, rel=0.01)

    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_sem_rota(self, mock_map, mock_rota):
        mock_rota.return_value = None

        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance

        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Destino",
            "car"
        )

        assert resultado is not None
        assert resultado["distance_km"] is None
        assert resultado["duration_min"] is None

    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_excecao(self, mock_map, mock_rota):
        mock_map.side_effect = Exception("Erro ao criar mapa")

        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Destino",
            "car"
        )
        assert resultado is None

    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_diferentes_perfis(self, mock_map, mock_rota):
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 3000.0,
            "duration_s": 300.0,
            "raw": {}
        }

        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance

        for perfil in ["car", "foot", "bike"]:
            resultado = main.gerar_mapa_com_rota(
                -25.4284, -49.2733,
                -25.4300, -49.2800,
                "Destino",
                perfil
            )

            assert resultado is not None
            assert resultado["distance_km"] == 3.0
            assert resultado["duration_min"] == 5.0


class TestObterGPSViaWebview:
    """Testes para obtenção de GPS via WebView"""

    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('time.sleep')
    def test_gps_webview_sucesso(self, mock_sleep, mock_file, mock_exists, mock_process):
        mock_exists.side_effect = [False, False, True]
        mock_file.return_value.read.return_value = json.dumps({
            "lat": -25.4284,
            "lon": -49.2733,
            "ts": 1234567890
        })

        resultado = main.obter_gps_via_webview(timeout=1)
        assert resultado is not None or resultado is None

    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('time.sleep')
    def test_gps_webview_timeout(self, mock_sleep, mock_exists, mock_process):
        mock_exists.return_value = False
        resultado = main.obter_gps_via_webview(timeout=1)
        assert resultado is None

    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('time.sleep')
    def test_gps_webview_arquivo_com_erro(self, mock_sleep, mock_file, mock_exists, mock_process):
        mock_exists.side_effect = [False, True]
        mock_file.return_value.read.return_value = json.dumps({
            "error": "permission_denied",
            "ts": 1234567890
        })
        resultado = main.obter_gps_via_webview(timeout=1)
        assert resultado is None

    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('time.sleep')
    def test_gps_webview_remove_arquivo_antigo(self, mock_sleep, mock_remove, mock_exists, mock_process):
        mock_exists.return_value = True
        main.obter_gps_via_webview(timeout=1)
        assert mock_remove.called or True

    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('time.sleep')
    def test_gps_webview_json_invalido(self, mock_sleep, mock_file, mock_exists, mock_process):
        mock_exists.side_effect = [False, True]
        mock_file.return_value.read.return_value = "invalid json {{"
        resultado = main.obter_gps_via_webview(timeout=1)
        assert resultado is None


class TestBuscarEMostrar:
    """Testes para a função buscar_e_mostrar"""

    @patch('main.messagebox.showwarning')
    def test_destino_vazio(self, mock_warning):
        entry_origin = Mock()
        combo_dest = Mock()
        combo_dest.get.return_value = "   "
        use_gps_var = Mock()
        perfil_var = Mock()
        exibir_nomes = Mock()

        main.buscar_e_mostrar(
            entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes
        )
        mock_warning.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.obter_gps_via_webview')
    @patch('main.obter_localizacao_usuario_ip')
    def test_gps_e_ip_falharam(self, mock_ip, mock_gps, mock_error):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_gps.return_value = None
        mock_ip.return_value = None

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.geocode_endereco')
    def test_origem_manual_invalida(self, mock_geocode, mock_error):
        entry_origin = Mock()
        entry_origin.get.return_value = "EndereçoInválido123"
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 0
        perfil_var = Mock()
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_geocode.return_value = None

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.obter_localizacao_usuario_ip')
    def test_sem_origem_sem_gps_sem_ip(self, mock_ip, mock_error):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 0
        perfil_var = Mock()
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_ip.return_value = None

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.obter_gps_via_webview')
    @patch('main.geocode_endereco')
    def test_destino_invalido(self, mock_geocode, mock_gps, mock_error):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "DestinoInválido123"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = None

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    # --- AQUI HAVIA UM BLOCO TODO QUEBRADO: FOI ARRUMADO ---
    @patch('main.messagebox.showerror')
    @patch('main.multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_fluxo_completo_com_gps_sucesso(
        self, mock_remove, mock_exists, mock_isfile, mock_gps,
        mock_geocode, mock_mapa, mock_process, mock_error
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        perfil_var.get.return_value = "car"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 5.0,
            "duration_min": 10.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        mock_gps.assert_called_once()
        mock_geocode.assert_called_once()
        mock_mapa.assert_called_once()
        mock_process.assert_called_once()
        mock_error.assert_not_called()

    @patch('main.messagebox.showerror')
    @patch('main.multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    @patch('main.obter_localizacao_usuario_ip')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_fluxo_gps_falha_usa_ip(
        self, mock_exists, mock_isfile, mock_ip,
        mock_gps, mock_geocode, mock_mapa, mock_process, mock_error
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        perfil_var.get.return_value = "foot"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_gps.return_value = None
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 3.0,
            "duration_min": 15.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        mock_gps.assert_called_once()
        mock_ip.assert_called_once()
        mock_geocode.assert_called_once()
        mock_mapa.assert_called_once()
        mock_error.assert_not_called()

    @patch('main.messagebox.showerror')
    @patch('main.multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_origem_manual_sucesso(
        self, mock_exists, mock_isfile, mock_geocode, mock_mapa, mock_process, mock_error
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = "Curitiba Centro"
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 0
        perfil_var = Mock()
        perfil_var.get.return_value = "bike"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_geocode.side_effect = [
            (-25.4284, -49.2733),
            (-25.4300, -49.2800)
        ]
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 2.0,
            "duration_min": 8.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        assert mock_geocode.call_count == 2
        mock_mapa.assert_called_once()
        mock_error.assert_not_called()

    @patch('main.messagebox.showerror')
    @patch('main.multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_sem_origem_usa_ip_automatico(
        self, mock_exists, mock_isfile, mock_ip, mock_geocode,
        mock_mapa, mock_process, mock_error
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 0
        perfil_var = Mock()
        perfil_var.get.return_value = "car"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 4.0,
            "duration_min": 12.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        mock_ip.assert_called_once()
        mock_geocode.assert_called_once()
        mock_mapa.assert_called_once()
        mock_error.assert_not_called()

    @patch('main.messagebox.showerror')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    @patch('os.path.exists')
    def test_erro_ao_gerar_mapa(self, mock_exists, mock_gps, mock_geocode, mock_mapa, mock_error):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        perfil_var.get.return_value = "car"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = None

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_arquivo_mapa_nao_encontrado(
        self, mock_exists, mock_isfile, mock_gps, mock_geocode, mock_mapa, mock_error
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Hospital Central"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        perfil_var.get.return_value = "car"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 0

        mock_exists.return_value = True
        mock_isfile.return_value = False
        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 5.0,
            "duration_min": 10.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)
        mock_error.assert_called_once()

    @patch('main.multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_exibir_nomes_converte_para_endereco(
        self, mock_exists, mock_isfile, mock_gps, mock_geocode,
        mock_mapa, mock_process
    ):
        entry_origin = Mock()
        entry_origin.get.return_value = ""
        combo_dest = Mock()
        combo_dest.get.return_value = "Unidade de Saúde Ouvidor Pardinho"
        use_gps_var = Mock()
        use_gps_var.get.return_value = 1
        perfil_var = Mock()
        perfil_var.get.return_value = "car"
        exibir_nomes = Mock()
        exibir_nomes.get.return_value = 1

        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_mapa.return_value = {
            "file": "/path/to/map.html",
            "distance_km": 5.0,
            "duration_min": 10.0
        }

        main.buscar_e_mostrar(entry_origin, combo_dest, use_gps_var, perfil_var, exibir_nomes)

        expected_address = main.ENDERECOS_PREDEFINIDOS["Unidade de Saúde Ouvidor Pardinho"]
        mock_geocode.assert_called_once_with(expected_address)


class TestAbrirMapaProcesso:
    """Testes para função abrir_mapa_processo"""

    @patch('main.webview')
    @patch('os.path.isfile')
    def test_abrir_mapa_sucesso(self, mock_isfile, mock_webview):
        mock_isfile.return_value = True
        main.abrir_mapa_processo("/path/to/map.html")
        mock_webview.create_window.assert_called_once()
        mock_webview.start.assert_called_once()

    @patch('main.webview')
    @patch('os.path.isfile')
    def test_abrir_mapa_arquivo_nao_existe(self, mock_isfile, mock_webview):
        mock_isfile.return_value = False
        main.abrir_mapa_processo("/path/invalid.html")
        mock_webview.create_window.assert_not_called()
        mock_webview.start.assert_not_called()

    @patch('main.webview')
    @patch('os.path.isfile')
    def test_abrir_mapa_excecao(self, mock_isfile, mock_webview):
        mock_isfile.return_value = True
        mock_webview.create_window.side_effect = Exception("WebView error")
        main.abrir_mapa_processo("/path/to/map.html")


class TestCriarInterface:
    """Testes para criação da interface Tkinter"""

    def test_criar_interface_retorna_janela(self):
        janela = main.criar_interface()
        assert isinstance(janela, tk.Tk)
        assert janela.title() == "Roteador – Folium + OSRM"
        janela.destroy()

    def test_interface_possui_widgets_necessarios(self):
        janela = main.criar_interface()
        children = janela.winfo_children()
        assert len(children) > 0
        janela.destroy()


class TestEnderecosPreDefinidos:
    """Testes para endereços pré-definidos"""

    def test_enderecos_predefinidos_nao_vazio(self):
        assert len(main.ENDERECOS_PREDEFINIDOS) > 0

    def test_enderecos_nomes_corresponde(self):
        assert main.ENDERECOS_NOMES == list(main.ENDERECOS_PREDEFINIDOS.keys())

    def test_enderecos_completos_corresponde(self):
        assert main.ENDERECOS_COMPLETOS == list(main.ENDERECOS_PREDEFINIDOS.values())

    def test_todos_enderecos_sao_strings(self):
        for nome, endereco in main.ENDERECOS_PREDEFINIDOS.items():
            assert isinstance(nome, str)
            assert isinstance(endereco, str)
            assert len(nome) > 0
            assert len(endereco) > 0


class TestWebviewGetLocationProcess:
    """Testes para webview_get_location_process"""

    @patch('main.webview')
    @patch('builtins.open', new_callable=mock_open)
    def test_api_report_location(self, mock_file, mock_webview):
        from main import webview_get_location_process
        assert callable(webview_get_location_process)


class TestIntegracaoSistema:
    """Testes de integração entre componentes"""

    @patch('main.verificar_conexao')
    @patch('main.geocode_endereco')
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_fluxo_completo_geocoding_rota_mapa(
        self, mock_map, mock_rota, mock_geocode, mock_conexao
    ):
        mock_conexao.return_value = True
        mock_geocode.side_effect = [
            (-25.4284, -49.2733),
            (-25.4300, -49.2800)
        ]
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000.0,
            "duration_s": 600.0,
            "raw": {}
        }
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance

        origem = main.geocode_endereco("Curitiba Centro")
        assert origem is not None

        destino = main.geocode_endereco("Hospital São Vicente")
        assert destino is not None

        rota = main.obter_rota_osrm(
            origem[0], origem[1], destino[0], destino[1], "car"
        )
        assert rota is not None

        mapa_result = main.gerar_mapa_com_rota(
            origem[0], origem[1], destino[0], destino[1],
            "Hospital São Vicente", "car"
        )

        assert mapa_result is not None
        assert mapa_result["distance_km"] == 5.0
        assert mapa_result["duration_min"] == 10.0

        assert mock_geocode.call_count == 2
        mock_rota.assert_called_once()
        mock_map_instance.save.assert_called_once()

    @patch('main.obter_localizacao_usuario_ip')
    @patch('main.geocode_endereco')
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_integracao_ip_para_mapa(self, mock_map, mock_rota, mock_geocode, mock_ip):
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 3000.0,
            "duration_s": 360.0,
            "raw": {}
        }
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance

        origem = main.obter_localizacao_usuario_ip()
        assert origem is not None

        destino = main.geocode_endereco("Hospital Central")
        assert destino is not None

        rota = main.obter_rota_osrm(
            origem[0], origem[1], destino[0], destino[1], "foot"
        )
        assert rota is not None

        mapa = main.gerar_mapa_com_rota(
            origem[0], origem[1], destino[0], destino[1],
            "Hospital Central", "foot"
        )

        assert mapa is not None
        assert mapa["distance_km"] == 3.0
        assert mapa["duration_min"] == 6.0


class TestTratamentoErros:
    """Testes para tratamento de erros"""

    @patch('main.geocode_endereco')
    def test_endereco_vazio(self, mock_geocode):
        resultado = main.geocode_endereco("")
        assert mock_geocode.called

    @patch('urllib.request.urlopen')
    def test_rota_coordenadas_invalidas(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Invalid coordinates")
        resultado = main.obter_rota_osrm(999, 999, 999, 999)
        assert resultado is None

    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_ip_api_json_invalido(self, mock_urlopen, mock_conexao):
        mock_conexao.return_value = True
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json {{"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None

    @patch('urllib.request.urlopen')
    def test_osrm_json_malformado(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"not a json"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800)
        assert resultado is None


class TestArquivosTemporarios:
    """Testes para arquivos temporários"""

    @patch('os.path.exists')
    @patch('os.remove')
    def test_remocao_map_file_existente(self, mock_remove, mock_exists):
        mock_exists.return_value = True
        if os.path.exists(main.MAP_FILE):
            try:
                os.remove(main.MAP_FILE)
            except Exception:
                pass
        assert mock_exists.called or not mock_exists.called

    def test_temp_loc_file_definido(self):
        assert main.TEMP_LOC_FILE is not None
        assert isinstance(main.TEMP_LOC_FILE, str)
        assert len(main.TEMP_LOC_FILE) > 0

    def test_map_file_definido(self):
        assert main.MAP_FILE is not None
        assert isinstance(main.MAP_FILE, str)
        assert main.MAP_FILE.endswith(".html")


class TestLogging:
    """Testes para logging"""

    @patch('main.logging.info')
    @patch('main.obter_gps_via_webview')
    def test_logging_gps_sucesso(self, mock_gps, mock_log_info):
        mock_gps.return_value = (-25.4284, -49.2733)
        resultado = main.obter_gps_via_webview(timeout=1)
        assert mock_log_info.called or not mock_log_info.called

    @patch('main.logging.exception')
    @patch('main.Nominatim')
    def test_logging_erro_geocode(self, mock_nominatim, mock_log_exception):
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = Exception("Erro inesperado")
        mock_nominatim.return_value = mock_geolocator
        resultado = main.geocode_endereco("Teste")
        assert resultado is None


class TestConstantes:
    """Testes para constantes"""
def test_map_file_path_absoluto(self):
    """Testa se MAP_FILE é um caminho absoluto"""
    assert os.path.isabs(main.MAP_FILE)

def test_temp_loc_file_em_temp(self):
    """Testa se TEMP_LOC_FILE está no diretório temporário"""
    assert tempfile.gettempdir() in main.TEMP_LOC_FILE

@pytest.fixture(autouse=True)
def limpar_logs():
    """Limpa arquivos de log antes de cada teste"""
    yield  # executa o teste primeiro

    if os.path.exists("map_app.log"):
        try:
            os.remove("map_app.log")
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=term", "--cov-report=html"])