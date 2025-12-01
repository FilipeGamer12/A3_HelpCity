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
    
    @patch('main.messagebox.showerror')
    @patch('main.obter_gps_via_webview')
    @patch('main.obter_localizacao_usuario_ip')
    def test_gps_e_ip_falharam(self, mock_ip, mock_gps, mock_error):
        """Testa quando GPS e IP falham"""
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
    
    @patch('main.messagebox.showerror')
    @patch('main.geocode_endereco')
    def test_origem_manual_invalida(self, mock_geocode, mock_error):
        """Testa origem manual que não pode ser geocodificada"""
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
    
    @patch('main.messagebox.showerror')
    @patch('main.obter_localizacao_usuario_ip')
    @patch('main.geocode_endereco')
    def test_destino_invalido(self, mock_geocode, mock_ip, mock_error):
        """Testa destino que não pode ser geocodificado"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "DestinoInvalido123"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = None
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        assert mock_geocode.call_count == 1
        mock_error.assert_called_once()
    
    @patch('main.messagebox.showerror')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    def test_erro_ao_gerar_mapa(self, mock_ip, mock_geocode, mock_gerar_mapa, mock_error):
        """Testa erro ao gerar mapa"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_perfil.get.return_value = "car"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_gerar_mapa.return_value = None
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_error.assert_called_once()
    
    @patch('os.path.isfile')
    @patch('main.messagebox.showerror')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_gps_via_webview')
    def test_fluxo_completo_com_gps(self, mock_gps, mock_geocode, mock_gerar_mapa, mock_process, mock_error, mock_isfile):
        """Testa fluxo completo usando GPS"""
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
    
    @patch('os.path.isfile')
    @patch('main.messagebox.showerror')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    def test_fluxo_completo_origem_manual(self, mock_geocode, mock_gerar_mapa, mock_process, mock_error, mock_isfile):
        """Testa fluxo completo com origem manual"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = "Curitiba Centro"
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital São Vicente"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_perfil.get.return_value = "foot"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_geocode.side_effect = [
            (-25.4284, -49.2733),  # origem
            (-25.4300, -49.2800)   # destino
        ]
        mock_gerar_mapa.return_value = {
            "file": "/tmp/map.html",
            "distance_km": 2.5,
            "duration_min": 30.0
        }
        mock_isfile.return_value = True
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        assert mock_geocode.call_count == 2
        mock_process.assert_called_once()
    
    @patch('main.messagebox.showerror')
    @patch('main.obter_localizacao_usuario_ip')
    def test_sem_origem_sem_gps_ip_falha(self, mock_ip, mock_error):
        """Testa quando não há origem e IP falha"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_ip.return_value = None
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_error.assert_called_once()
    
    @patch('os.remove')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    def test_remove_map_file_antigo(self, mock_ip, mock_geocode, mock_gerar_mapa, mock_process, mock_isfile, mock_exists, mock_remove):
        """Testa remoção de arquivo de mapa antigo"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_perfil.get.return_value = "bike"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_exists.return_value = True
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_gerar_mapa.return_value = {
            "file": "/tmp/map.html",
            "distance_km": 3.0,
            "duration_min": 15.0
        }
        mock_isfile.return_value = True
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_remove.assert_called()
    
    @patch('main.ENDERECOS_PREDEFINIDOS', {'Hospital Teste': 'Rua Teste, 123'})
    @patch('os.path.isfile')
    @patch('multiprocessing.Process')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    def test_conversao_nome_para_endereco(self, mock_ip, mock_geocode, mock_gerar_mapa, mock_process, mock_isfile):
        """Testa conversão de nome predefinido para endereço"""
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
    
    @patch('os.path.isfile')
    @patch('main.messagebox.showerror')
    @patch('main.gerar_mapa_com_rota')
    @patch('main.geocode_endereco')
    @patch('main.obter_localizacao_usuario_ip')
    def test_arquivo_mapa_nao_encontrado(self, mock_ip, mock_geocode, mock_gerar_mapa, mock_error, mock_isfile):
        """Testa quando arquivo do mapa não é encontrado"""
        mock_entry_origin = Mock()
        mock_entry_origin.get.return_value = ""
        mock_combo_dest = Mock()
        mock_combo_dest.get.return_value = "Hospital"
        mock_use_gps = Mock()
        mock_use_gps.get.return_value = 0
        mock_perfil = Mock()
        mock_perfil.get.return_value = "car"
        mock_exibir_nomes = Mock()
        mock_exibir_nomes.get.return_value = 0
        
        mock_ip.return_value = (-25.4284, -49.2733)
        mock_geocode.return_value = (-25.4300, -49.2800)
        mock_gerar_mapa.return_value = {
            "file": "/tmp/map.html",
            "distance_km": 5.0,
            "duration_min": 10.0
        }
        mock_isfile.return_value = False
        
        main.buscar_e_mostrar(mock_entry_origin, mock_combo_dest, mock_use_gps, mock_perfil, mock_exibir_nomes)
        
        mock_error.assert_called_once()


class TestWebViewProcessos:
    """Testes para processos WebView"""
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('multiprocessing.Process')
    def test_obter_gps_remove_arquivo_antigo(self, mock_process, mock_remove, mock_exists):
        """Testa remoção de arquivo temporário antigo"""
        mock_exists.return_value = True
        
        with patch('time.sleep'):
            main.obter_gps_via_webview(timeout=0.1)
        
        mock_remove.assert_called_once()
    
    @patch('os.path.exists')
    @patch('multiprocessing.Process')
    def test_obter_gps_arquivo_nao_existe(self, mock_process, mock_exists):
        """Testa quando arquivo temp não existe"""
        mock_exists.return_value = True
        
        with patch('builtins.open', side_effect=Exception("File error")):
            resultado = main.obter_gps_via_webview(timeout=0.1)
        
        assert resultado is None
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('multiprocessing.Process')
    def test_obter_gps_arquivo_com_erro(self, mock_process, mock_file, mock_exists):
        """Testa arquivo criado mas com erro"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps({
            "error": "permission_denied",
            "ts": 1234567890
        })
        
        with patch('time.sleep'):
            resultado = main.obter_gps_via_webview(timeout=0.1)
        
        assert resultado is None
    
    @patch('multiprocessing.Process')
    def test_obter_gps_processo_iniciado(self, mock_process):
        """Testa que processo é iniciado corretamente"""
        mock_proc_instance = Mock()
        mock_process.return_value = mock_proc_instance
        
        with patch('time.sleep'), patch('os.path.exists', return_value=False):
            main.obter_gps_via_webview(timeout=0.1)
        
        mock_proc_instance.start.assert_called_once()


class TestGerarMapaComRotaDetalhado:
    """Testes adicionais para geração de mapa"""
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    @patch('folium.Marker')
    def test_marcadores_criados(self, mock_marker, mock_map, mock_rota):
        """Testa que marcadores de origem e destino são criados"""
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000,
            "duration_s": 600
        }
        
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        
        main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital",
            "car"
        )
        
        # Verifica que Marker foi chamado (origem e destino)
        assert mock_marker.call_count >= 2
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    @patch('folium.PolyLine')
    def test_polyline_criada(self, mock_polyline, mock_map, mock_rota):
        """Testa que polyline da rota é criada"""
        mock_rota.return_value = {
            "poly": [(-25.4284, -49.2733), (-25.4300, -49.2800)],
            "distance_m": 5000,
            "duration_s": 600
        }
        
        mock_map_instance = MagicMock()
        mock_map.return_value = mock_map_instance
        
        main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital",
            "car"
        )
        
        mock_polyline.assert_called_once()
    
    @patch('main.obter_rota_osrm')
    @patch('folium.Map')
    def test_gerar_mapa_exception_tratada(self, mock_map, mock_rota):
        """Testa tratamento de exceção ao gerar mapa"""
        mock_map.side_effect = Exception("Map error")
        
        resultado = main.gerar_mapa_com_rota(
            -25.4284, -49.2733,
            -25.4300, -49.2800,
            "Hospital",
            "car"
        )
        
        assert resultado is None


class TestCriarInterface:
    """Testes para criação da interface"""
    
    @patch('tkinter.Tk')
    def test_interface_criada(self, mock_tk):
        """Testa que a interface Tkinter é criada"""
        mock_janela = Mock()
        mock_tk.return_value = mock_janela
        
        resultado = main.criar_interface()
        
        mock_janela.title.assert_called_once()
        mock_janela.geometry.assert_called_once()
        assert resultado == mock_janela
    
    @patch('tkinter.Tk')
    def test_widgets_criados(self, mock_tk):
        """Testa que widgets são criados"""
        mock_janela = Mock()
        mock_tk.return_value = mock_janela
        
        with patch('tkinter.Label'), patch('tkinter.Entry'), patch('tkinter.Checkbutton'):
            resultado = main.criar_interface()
        
        assert resultado is not None


class TestCasosBorda:
    """Testes para casos de borda e edge cases"""
    
    @patch('urllib.request.urlopen')
    def test_rota_distancia_zero(self, mock_urlopen):
        """Testa rota com distância zero"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "routes": [{
                "geometry": {"coordinates": [[-49.2733, -25.4284]]},
                "distance": 0,
                "duration": 0
            }]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        resultado = main.obter_rota_osrm(-25.4284, -49.2733, -25.4284, -49.2733)
        
        assert resultado is not None
        assert resultado["distance_m"] == 0
        assert resultado["duration_s"] == 0
    
    @patch('main.verificar_conexao')
    @patch('urllib.request.urlopen')
    def test_localizacao_ip_json_invalido(self, mock_urlopen, mock_conexao):
        """Testa resposta com JSON inválido"""
        mock_conexao.return_value = True
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json {{"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        resultado = main.obter_localizacao_usuario_ip()
        assert resultado is None
    
    def test_perfil_string_vazia(self):
        """Testa perfil com string vazia"""
        resultado = main.perfil_osrm_para_query("")
        assert resultado == "driving"
    
    @patch('main.Nominatim')
    def test_geocode_espacos_extras(self, mock_nominatim):
        """Testa geocodificação com espaços extras"""
        mock_geolocator = Mock()
        mock_location = Mock()
        mock_location.latitude = -25.4284
        mock_location.longitude = -49.2733
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator
        
        resultado = main.geocode_endereco("  Curitiba  ")
        
        assert resultado is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=term", "--cov-report=html"])