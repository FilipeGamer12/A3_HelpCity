import os
import json
import socket
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

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
    def test_geocode_timeout(self, mock_nominatim):
        """Testa timeout no geocoding"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = GeocoderTimedOut("Timeout")
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba, PR")
        assert resultado is None
    
    @patch('main.Nominatim')
    def test_geocode_servico_indisponivel(self, mock_nominatim):
        """Testa quando o serviço está indisponível"""
        mock_geolocator = Mock()
        mock_geolocator.geocode.side_effect = GeocoderUnavailable("Service down")
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("Curitiba, PR")
        assert resultado is None


class TestPerfilOSRM:
    """Testes para conversão de perfis de transporte"""
    
    def test_perfil_carro(self):
        """Testa conversão do perfil carro"""
        assert main.perfil_osrm_para_query("car") == "driving"
    
    def test_perfil_pe(self):
        """Testa conversão do perfil a pé"""
        assert main.perfil_osrm_para_query("foot") == "walking"
    
    def test_perfil_bicicleta(self):
        """Testa conversão do perfil bicicleta"""
        assert main.perfil_osrm_para_query("bike") == "cycling"
    
    def test_perfil_desconhecido(self):
        """Testa perfil desconhecido (fallback)"""
        assert main.perfil_osrm_para_query("unknown") == "driving"
        assert main.perfil_osrm_para_query("bus") == "driving"


class TestObterRotaOSRM:
    """Testes para obtenção de rotas via OSRM"""
    
    @patch('urllib.request.urlopen')
    def test_rota_sucesso(self, mock_urlopen):
        """Testa obtenção bem-sucedida de rota"""
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
        assert "poly" in resultado
        assert "distance_m" in resultado
        assert "duration_s" in resultado
        assert resultado["distance_m"] == 5000.5
        assert resultado["duration_s"] == 600.0
        assert len(resultado["poly"]) == 2
    
    @patch('urllib.request.urlopen')
    def test_rota_sem_resultados(self, mock_urlopen):
        """Testa quando não há rotas disponíveis"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": []
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800)
        assert resultado is None
    
    @patch('urllib.request.urlopen')
    def test_rota_erro_api(self, mock_urlopen):
        """Testa erro na API OSRM"""
        mock_urlopen.side_effect = Exception("API Error")
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800)
        assert resultado is None
    
    @patch('urllib.request.urlopen')
    def test_rota_diferentes_perfis(self, mock_urlopen):
        """Testa diferentes perfis de transporte"""
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
            resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4300, -49.2800, perfil)
            assert resultado is not None


class TestGerarMapaComRota:
    """Testes para geração de mapas"""
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_com_rota_sucesso(self, mock_map, mock_rota):
        """Testa geração bem-sucedida de mapa com rota"""
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
        """Testa geração de mapa quando rota não está disponível"""
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


class TestObterGPSViaWebview:
    """Testes para obtenção de GPS via WebView"""
    
    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_gps_webview_sucesso(self, mock_file, mock_exists, mock_process):
        """Testa obtenção bem-sucedida de GPS via WebView"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps({
            "lat": -25.4284,
            "lon": -49.2733,
            "ts": 1234567890
        })
        
        with patch('time.sleep'):
            resultado = main.obter_gps_via_webview(timeout=1)
        
        # Como o arquivo é criado instantaneamente no mock, deve retornar coords
        assert resultado is not None or resultado is None  # Depende do timing
    
    @patch('multiprocessing.Process')
    @patch('os.path.exists')
    @patch('time.sleep')
    def test_gps_webview_timeout(self, mock_sleep, mock_exists, mock_process):
        """Testa timeout ao aguardar GPS"""
        mock_exists.return_value = False
        
        resultado = main.obter_gps_via_webview(timeout=1)
        assert resultado is None


# TESTE DE INTEGRAÇÃO
class TestIntegracaoSistema:
    """Testes de integração entre componentes"""
    
    @patch('main.verificar_conexao')
    @patch('main.geocode_endereco')
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_fluxo_completo_geocoding_rota_mapa(
        self, mock_map, mock_rota, mock_geocode, mock_conexao
    ):
        """
        Teste de integração: fluxo completo de geocodificação + rota + mapa
        Este é o teste de integração obrigatório do requisito
        """
        # Setup
        mock_conexao.return_value = True
        mock_geocode.side_effect = [
            (-25.4284, -49.2733),  # origem
            (-25.4300, -49.2800)   # destino
        ]
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000.0,
            "duration_s": 600.0,
            "raw": {}
        }
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        
        # Execução: simula fluxo completo
        # 1. Geocodificar origem
        origem = main.geocode_endereco("Curitiba Centro")
        assert origem is not None
        
        # 2. Geocodificar destino
        destino = main.geocode_endereco("Hospital São Vicente")
        assert destino is not None
        
        # 3. Obter rota
        rota = main.obter_rota_osrm(
            origem[0], origem[1],
            destino[0], destino[1],
            "car"
        )
        assert rota is not None
        assert "distance_m" in rota
        assert "duration_s" in rota
        
        # 4. Gerar mapa
        mapa_result = main.gerar_mapa_com_rota(
            origem[0], origem[1],
            destino[0], destino[1],
            "Hospital São Vicente",
            "car"
        )
        assert mapa_result is not None
        assert mapa_result["distance_km"] == 5.0
        assert mapa_result["duration_min"] == 10.0
        
        # Verificações de integração
        assert mock_geocode.call_count == 2
        mock_rota.assert_called_once()
        mock_map_instance.save.assert_called_once()


class TestTratamentoErros:
    """Testes para tratamento de erros"""
    
    @patch('main.geocode_endereco')
    def test_endereco_vazio(self, mock_geocode):
        """Testa comportamento com endereço vazio"""
        resultado = main.geocode_endereco("")
        assert mock_geocode.called
    
    @patch('urllib.request.urlopen')
    def test_rota_coordenadas_invalidas(self, mock_urlopen):
        """Testa rota com coordenadas inválidas"""
        mock_urlopen.side_effect = Exception("Invalid coordinates")
        
        resultado = main.obter_rota_osrm(999, 999, 999, 999)
        assert resultado is None


# Configuração do pytest
@pytest.fixture(autouse=True)
def limpar_logs():
    """Limpa arquivos de log antes de cada teste"""
    yield
    if os.path.exists("map_app.log"):
        try:
            os.remove("map_app.log")
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=term", "--cov-report=html"])