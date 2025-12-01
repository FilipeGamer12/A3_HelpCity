"""
test_main.py
Testes unitários para o módulo main.py
Execute com: pytest test_main.py -v --cov=main --cov-report=term --cov-report=html
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch, mock_open
import main


class TestVerificarConexao:
    """Testes para verificação de conexão"""
    
    @patch('socket.create_connection')
    def test_conexao_sucesso(self, mock_socket):
        """Testa conexão bem-sucedida"""
        mock_socket.return_value = Mock()
        resultado = main.verificar_conexao()
        assert resultado is True
    
    @patch('socket.create_connection')
    def test_conexao_falha(self, mock_socket):
        """Testa falha na conexão"""
        mock_socket.side_effect = OSError("Connection failed")
        resultado = main.verificar_conexao()
        assert resultado is False


class TestObterLocalizacaoUsuarioIP:
    """Testes para obtenção de localização por IP"""
    
    @patch('main.verificar_conexao')
    def test_sem_conexao(self, mock_conexao):
        """Testa quando não há conexão"""
        mock_conexao.return_value = False
        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None
    
    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_sucesso(self, mock_urlopen, mock_conexao):
        """Testa obtenção bem-sucedida"""
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
        assert resultado == (-25.4284, -49.2733)
    
    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_status_falha(self, mock_urlopen, mock_conexao):
        """Testa quando API retorna status de falha"""
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
    def test_excecao(self, mock_urlopen, mock_conexao):
        """Testa tratamento de exceção"""
        mock_conexao.return_value = True
        mock_urlopen.side_effect = Exception("Network error")
        
        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None


class TestGeocodeEndereco:
    """Testes para geocodificação de endereços"""
    
    @patch('main.Nominatim')
    def test_sucesso(self, mock_nominatim):
        """Testa geocodificação bem-sucedida"""
        mock_geolocator = Mock()
        mock_location = Mock()
        mock_location.latitude = -25.4284
        mock_location.longitude = -49.2733
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba, PR")
        assert resultado == (-25.4284, -49.2733)
    
    @patch('main.Nominatim')
    def test_endereco_nao_encontrado(self, mock_nominatim):
        """Testa quando endereço não é encontrado"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("EnderecoInvalido123")
        assert resultado is None
    
    @patch('main.Nominatim')
    @patch('time.sleep')
    def test_timeout_com_retry(self, mock_sleep, mock_nominatim):
        """Testa timeout com tentativas"""
        from geopy.exc import GeocoderTimedOut
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = [
            GeocoderTimedOut("timeout"),
            GeocoderTimedOut("timeout"),
            GeocoderTimedOut("timeout")
        ]
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba", tentativas=3)
        assert resultado is None
        assert mock_sleep.call_count == 2
    
    @patch('main.Nominatim')
    @patch('time.sleep')
    def test_unavailable_com_retry(self, mock_sleep, mock_nominatim):
        """Testa serviço indisponível com retry"""
        from geopy.exc import GeocoderUnavailable
        mock_geolocator = Mock()
        mock_location = Mock()
        mock_location.latitude = -25.4284
        mock_location.longitude = -49.2733
        mock_geolocator.geocode.side_effect = [
            GeocoderUnavailable("unavailable"),
            mock_location
        ]
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba", tentativas=3)
        assert resultado == (-25.4284, -49.2733)
    
    @patch('main.Nominatim')
    def test_excecao_generica(self, mock_nominatim):
        """Testa exceção genérica"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = Exception("Generic error")
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba")
        assert resultado is None


class TestPerfilOSRM:
    """Testes para conversão de perfil OSRM"""
    
    def test_perfil_car(self):
        """Testa perfil carro"""
        assert main.perfil_osrm_para_query("car") == "driving"
    
    def test_perfil_foot(self):
        """Testa perfil a pé"""
        assert main.perfil_osrm_para_query("foot") == "walking"
    
    def test_perfil_bike(self):
        """Testa perfil bicicleta"""
        assert main.perfil_osrm_para_query("bike") == "cycling"
    
    def test_perfil_desconhecido(self):
        """Testa perfil desconhecido (fallback)"""
        assert main.perfil_osrm_para_query("unknown") == "driving"


class TestObterRotaOSRM:
    """Testes para obtenção de rota OSRM"""
    
    @patch('urllib.request.urlopen')
    def test_rota_sucesso(self, mock_urlopen):
        """Testa obtenção de rota bem-sucedida"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": [{
                "geometry": {
                    "coordinates": [
                        [-49.2733, -25.4284],
                        [-49.2800, -25.4300]
                    ]
                },
                "distance": 5000.0,
                "duration": 600.0
            }]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800, "car")
        
        assert resultado is not None
        assert resultado["distance_m"] == 5000.0
        assert resultado["duration_s"] == 600.0
        assert len(resultado["poly"]) == 2
    
    @patch('urllib.request.urlopen')
    def test_rota_sem_routes(self, mock_urlopen):
        """Testa quando não há rotas"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": []
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800)
        assert resultado is None
    
    @patch('urllib.request.urlopen')
    def test_rota_excecao(self, mock_urlopen):
        """Testa exceção ao obter rota"""
        mock_urlopen.side_effect = Exception("OSRM error")
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800)
        assert resultado is None


class TestGerarMapaComRota:
    """Testes para geração de mapa com rota"""
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_mapa_com_rota_sucesso(self, mock_map, mock_rota):
        """Testa geração de mapa com rota bem-sucedida"""
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000,
            "duration_s": 600
        }
        
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        
        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital Teste",
            "car"
        )
        
        assert resultado is not None
        assert resultado["distance_km"] == 5.0
        assert resultado["duration_min"] == 10.0
        mock_map_instance.save.assert_called_once()
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_mapa_sem_rota(self, mock_map, mock_rota):
        """Testa geração de mapa quando rota não está disponível"""
        mock_rota.return_value = None
        
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        
        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital",
            "car"
        )
        
        assert resultado is not None
        assert resultado["distance_km"] is None
        assert resultado["duration_min"] is None
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_mapa_excecao(self, mock_map, mock_rota):
        """Testa exceção ao gerar mapa"""
        mock_map.side_effect = Exception("Map generation error")
        
        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital",
            "car"
        )
        
        assert resultado is None


class TestObterGPSViaWebview:
    """Testes para obtenção de GPS via WebView"""
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('multiprocessing.Process')
    @patch('builtins.open', new_callable=mock_open)
    @patch('time.sleep')
    def test_gps_sucesso(self, mock_sleep, mock_file, mock_process, mock_remove, mock_exists):
        """Testa obtenção de GPS bem-sucedida"""
        mock_exists.side_effect = [False, True]  # Primeira chamada False, segunda True
        mock_file.return_value.read.return_value = json.dumps({
            "lat": -25.4284,
            "lon": -49.2733,
            "ts": 1234567890
        })
        
        resultado = main.obter_gps_via_webview(timeout=1)
        
        assert resultado == (-25.4284, -49.2733)
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('multiprocessing.Process')
    @patch('time.sleep')
    def test_gps_timeout(self, mock_sleep, mock_process, mock_remove, mock_exists):
        """Testa timeout ao obter GPS"""
        mock_exists.return_value = False
        mock_proc = Mock()
        mock_proc.is_alive.return_value = True
        mock_process.return_value = mock_proc
        
        resultado = main.obter_gps_via_webview(timeout=0.5)
        
        assert resultado is None
        mock_proc.terminate.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('multiprocessing.Process')
    @patch('builtins.open', new_callable=mock_open)
    @patch('time.sleep')
    def test_gps_arquivo_com_erro(self, mock_sleep, mock_file, mock_process, mock_remove, mock_exists):
        """Testa arquivo com erro"""
        mock_exists.side_effect = [False, True]
        mock_file.return_value.read.return_value = json.dumps({
            "error": "permission_denied",
            "ts": 1234567890
        })
        
        resultado = main.obter_gps_via_webview(timeout=1)
        
        assert resultado is None


class TestBuscarEMostrar:
    """Testes para a função principal buscar_e_mostrar"""
    
    @patch('main.messagebox.showwarning')
    def test_destino_vazio(self, mock_warning):
        """Testa quando destino está vazio"""
        mock_entry_origin = Mock()
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "   "
        mock_use_gps = Mock()
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_warning.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('main.messagebox.showerror')
    @patch('main.obter_gps_via_webview')
    @patch('main.obter_localizacao_usuario_ip')
    def test_gps_e_ip_falharam(self, mock_ip, mock_gps, mock_error, mock_remove, mock_exists):
        """Testa quando GPS e IP falham"""
        mock_exists.return_value = False
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital Central"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 1
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_gps.return_value = None
        mock_ip.return_value = None
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_error.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('main.messagebox.showerror')
    @patch('main.geocode_endereco')
    def test_origem_manual_invalida(self, mock_geocode, mock_error, mock_remove, mock_exists):
        """Testa origem manual que não pode ser geocodificada"""
        mock_exists.return_value = False
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = "EnderecoInvalido123XYZ"
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital Central"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_geocode.return_value = None
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_error.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('main.messagebox.showerror')
    @patch('main.obter_localizacao_usuario_ip')
    @patch('main.geocode_endereco')
    def test_sem_origem_ip_fallback(self, mock_geocode, mock_ip, mock_error, mock_remove, mock_exists):
        """Testa fallback para IP quando não há origem"""
        mock_exists.return_value = False
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        
        with patch('main.gerar_mapa_com_rota') as mock_mapa:
            mock_mapa.return_value = None
            main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_ip.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.path.isfile')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    def test_fluxo_completo_com_gps(self, mock_gps, mock_geocode, mock_gerar_mapa, 
                                     mock_process, mock_isfile, mock_remove, mock_exists):
        """Testa fluxo completo usando GPS"""
        mock_exists.return_value = False
        mock_entry_origin = Mock()
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital Central"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 1
        mock_perfil = Mock()
        mock_perfil.get.return_value = "car"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_gps.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_gerar_mapa.return_value = {
            "file": "/tmp/map.html",
            "distance_km": 5.0,
            "duration_min": 10.0
        }
        mock_isfile.return_value = True
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_gps.assert_called_once()
        mock_process.assert_called_once()
    
    @patch('main.ENDERECOS_PREDEFINIDOS', {'Hospital Teste': 'Rua Teste, 123'})
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.path.isfile')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    def test_conversao_nome_para_endereco(self, mock_ip, mock_geocode, mock_gerar_mapa, 
                                          mock_process, mock_isfile, mock_remove, mock_exists):
        """Testa conversão de nome predefinido para endereço"""
        mock_exists.return_value = False
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital Teste"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_perfil.get.return_value = "car"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 1  # Exibindo nomes
        
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_gerar_mapa.return_value = {
            "file": "/tmp/map.html",
            "distance_km": 1.0,
            "duration_min": 5.0
        }
        mock_isfile.return_value = True
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        # Verifica que geocode foi chamado com o endereço completo
        mock_geocode.assert_called_with('Rua Teste, 123')


class TestCriarInterface:
    """Testes para criação da interface"""
    
    @patch('tkinter.Tk')
    def test_interface_criada(self, mock_tk):
        """Testa que a interface Tkinter é criada"""
        mock_janela = Mock()
        mock_tk.return_value = mock_janela
        
        with patch('tkinter.Frame'), patch('tkinter.Label'), \
             patch('tkinter.Entry'), patch('tkinter.Checkbutton'), \
             patch('tkinter.Button'), patch('tkinter.Radiobutton'), \
             patch('tkinter.ttk.Combobox'):
            resultado = main.criar_interface()
        
        mock_janela.title.assert_called_once()
        mock_janela.geometry.assert_called_once()
        assert resultado == mock_janela


class TestConstantes:
    """Testes para constantes e configurações"""
    
    def test_enderecos_predefinidos_existem(self):
        """Testa que endereços predefinidos existem"""
        assert len(main.ENDERECOS_PREDEFINIDOS) > 0
    
    def test_enderecos_nomes_correspondem(self):
        """Testa que listas de nomes correspondem"""
        assert len(main.ENDERECOS_NOMES) == len(main.ENDERECOS_PREDEFINIDOS)
    
    def test_enderecos_completos_correspondem(self):
        """Testa que endereços completos correspondem"""
        assert len(main.ENDERECOS_COMPLETOS) == len(main.ENDERECOS_PREDEFINIDOS)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=term", "--cov-report=html"])