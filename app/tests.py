import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio


class LoginFlowTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="henri",
            password="senha12345",
        )

    def test_index_redireciona_quando_nao_autenticado(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('entrar')}?next={reverse('index')}")

    def test_entrar_post_com_credenciais_validas(self):
        response = self.client.post(
            reverse("entrar"),
            {"nome": "henri", "senha": "senha12345"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))


class IndexReservatorioTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="monitor",
            password="monitor123",
        )

    def _logar(self):
        self.client.force_login(self.usuario)

    def test_adicionar_cria_reservatorio_com_status_bom(self):
        self._logar()

        response = self.client.post(
            reverse("reservatorio_adicionar"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))
        self.assertEqual(Reservatorio.objects.count(), 1)

        reservatorio = Reservatorio.objects.first()
        self.assertEqual(reservatorio.nome, "Reservatorio 1")
        self.assertEqual(reservatorio.status, Reservatorio.STATUS_BOM)
        self.assertEqual(reservatorio.meta_ppm_tds, Reservatorio.META_PADRAO_PPM_TDS)
        self.assertEqual(reservatorio.meta_ntu_turbidez, Reservatorio.META_PADRAO_NTU_TURBIDEZ)
        self.assertEqual(
            reservatorio.meta_celsius_temperatura,
            Reservatorio.META_PADRAO_CELSIUS_TEMPERATURA,
        )
        self.assertEqual(reservatorio.pontos_monitoramento.count(), 2)

    def test_excluir_remove_reservatorio(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio 99",
            status=Reservatorio.STATUS_ATENCAO,
        )

        response = self.client.post(
            reverse("reservatorio_excluir", args=[reservatorio.id]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservatorio.objects.count(), 0)

    def test_detalhe_retorna_200(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio detalhe",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salvar alteracoes")

    def test_atualizar_view_altera_objeto(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio original",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse("reservatorio_atualizar", args=[reservatorio.id]),
            {
                "nome": "Reservatorio atualizado",
                "meta_ppm_tds": "700.0",
                "meta_ntu_turbidez": "1.9",
                "meta_celsius_temperatura": "27.5",
            },
        )

        self.assertEqual(response.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.nome, "Reservatorio atualizado")
        self.assertEqual(reservatorio.status, Reservatorio.STATUS_BOM)
        self.assertEqual(reservatorio.meta_ppm_tds, 700.0)
        self.assertEqual(reservatorio.meta_ntu_turbidez, 1.9)
        self.assertEqual(reservatorio.meta_celsius_temperatura, 27.5)

    def test_detalhe_nao_permite_acesso_a_reservatorio_de_outro_usuario(self):
        self._logar()
        outro_usuario = User.objects.create_user(username="outro", password="outro123")
        reservatorio = Reservatorio.objects.create(
            usuario=outro_usuario,
            nome="Reservatorio Privado",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))

    def test_busca_filtra_por_nome(self):
        self._logar()
        Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio Norte",
            status=Reservatorio.STATUS_BOM,
        )
        Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Tanque Sul",
            status=Reservatorio.STATUS_PERIGO,
        )

        response = self.client.get(reverse("index"), {"busca": "norte"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RESERVATORIO NORTE")
        self.assertNotContains(response, "TANQUE SUL")

    def test_busca_filtra_por_status(self):
        self._logar()
        Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Tanque Status Bom",
            status=Reservatorio.STATUS_BOM,
        )
        Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Tanque Status Perigo",
            status=Reservatorio.STATUS_PERIGO,
        )

        response = self.client.get(reverse("index"), {"busca": "perigo"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TANQUE STATUS PERIGO")
        self.assertNotContains(response, "TANQUE STATUS BOM")


class ReservatorioModelCrudTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="model_user",
            password="model12345",
        )

    def test_create_gera_nome_se_nao_informado(self):
        primeiro = Reservatorio.criar_reservatorio(usuario=self.usuario)
        segundo = Reservatorio.criar_reservatorio(usuario=self.usuario)

        self.assertEqual(primeiro.nome, "Reservatorio 1")
        self.assertEqual(segundo.nome, "Reservatorio 2")
        self.assertEqual(primeiro.status, Reservatorio.STATUS_BOM)
        self.assertEqual(primeiro.meta_ppm_tds, Reservatorio.META_PADRAO_PPM_TDS)
        self.assertEqual(primeiro.meta_ntu_turbidez, Reservatorio.META_PADRAO_NTU_TURBIDEZ)
        self.assertEqual(
            primeiro.meta_celsius_temperatura,
            Reservatorio.META_PADRAO_CELSIUS_TEMPERATURA,
        )

    def test_read_listar_com_busca(self):
        Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Central",
            status=Reservatorio.STATUS_BOM,
        )
        Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Leste",
            status=Reservatorio.STATUS_PERIGO,
        )

        filtrados = Reservatorio.listar("perigo", usuario=self.usuario)

        self.assertEqual(filtrados.count(), 1)
        self.assertEqual(filtrados.first().nome, "Leste")

    def test_update_atualiza_somente_nome(self):
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Velho",
            status=Reservatorio.STATUS_BOM,
        )

        atualizado = reservatorio.atualizar_reservatorio(
            nome="Novo",
        )

        self.assertEqual(atualizado.nome, "Novo")
        self.assertEqual(atualizado.status, Reservatorio.STATUS_BOM)

    def test_update_rejeita_status_manual(self):
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Sem Status Manual",
            status=Reservatorio.STATUS_BOM,
        )

        with self.assertRaisesMessage(ValueError, "Status do reservatorio e automatico"):
            reservatorio.atualizar_reservatorio(status=Reservatorio.STATUS_PERIGO)

    def test_update_atualiza_metas(self):
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Com Metas",
            status=Reservatorio.STATUS_BOM,
        )

        reservatorio.atualizar_reservatorio(
            meta_ppm_tds=450.5,
            meta_ntu_turbidez=1.2,
            meta_celsius_temperatura=24.0,
        )

        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.meta_ppm_tds, 450.5)
        self.assertEqual(reservatorio.meta_ntu_turbidez, 1.2)
        self.assertEqual(reservatorio.meta_celsius_temperatura, 24.0)

    def test_delete_exclui_por_id(self):
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Excluir",
            status=Reservatorio.STATUS_BOM,
        )

        resultado = reservatorio.excluir_reservatorio()

        self.assertTrue(resultado)
        self.assertEqual(Reservatorio.objects.count(), 0)


@override_settings(ESP32_API_TOKEN="token-teste-esp32")
class Esp32IngestaoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="iot_user",
            password="iot12345",
        )
        self.reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio IoT",
            status=Reservatorio.STATUS_BOM,
        )
        self.url = reverse("esp32_leitura")

    def _post_json(self, payload, token="token-teste-esp32"):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_TOKEN=token,
        )

    def test_esp32_leitura_retorna_401_sem_token_valido(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 25.4,
                "tds": 350.2,
                "turbidez": 0.8,
            },
            token="token-invalido",
        )

        self.assertEqual(response.status_code, 401)

    def test_esp32_leitura_retorna_400_payload_invalido(self):
        response = self.client.post(
            self.url,
            data="{temperatura: 20",
            content_type="application/json",
            HTTP_X_API_TOKEN="token-teste-esp32",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "payload invalido")

    def test_esp32_leitura_retorna_400_reservatorio_invalido(self):
        response = self._post_json(
            {
                "reservatorio_id": 999999,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 26.3,
                "tds": 420.0,
                "turbidez": 1.0,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "reservatorio invalido")

    def test_esp32_leitura_retorna_400_quando_falta_campo(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 27.0,
                "turbidez": 1.0,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "campo obrigatorio: tds")

    def test_esp32_leitura_retorna_400_com_ponto_tipo_invalido(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": "inexistente",
                "temperatura": 27.0,
                "tds": 500.0,
                "turbidez": 1.2,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "campo invalido: ponto_tipo")

    def test_esp32_leitura_ignora_status_enviado_e_aplica_regras(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 25.0,
                "tds": 300.0,
                "turbidez": 0.5,
                "status_leitura": "perigo",
                "confianca": 0.99,
                "modelo_versao": "qualquer-coisa",
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertEqual(leitura.status_origem, LeituraQualidade.ORIGEM_REGRAS)
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_BOM)
        self.assertIsNone(leitura.confianca)
        self.assertEqual(leitura.modelo_versao, "")

    def test_esp32_leitura_salva_leitura_qualidade_e_atualiza_status(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 28.75,
                "tds": 920.5,
                "turbidez": 2.8,
            }
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LeituraQualidade.objects.count(), 1)
        leitura = LeituraQualidade.objects.first()
        self.assertEqual(leitura.ponto.tipo, PontoMonitoramento.TIPO_ANTES)
        self.assertEqual(leitura.status_origem, LeituraQualidade.ORIGEM_REGRAS)
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_PERIGO)
        self.assertAlmostEqual(leitura.tds, 920.5, places=2)
        self.assertAlmostEqual(leitura.temperatura, 28.75, places=2)
        self.assertAlmostEqual(leitura.turbidez, 2.8, places=2)
        self.assertEqual(leitura.sinais_brutos, {})

        ponto_antes = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        self.assertEqual(ponto_antes.status_atual, Reservatorio.STATUS_PERIGO)

        self.reservatorio.refresh_from_db()
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_BOM)

    def test_esp32_leitura_salva_status_no_ponto_com_base_em_regras(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 20.0,
                "tds": 650.0,
                "turbidez": 0.3,
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertEqual(leitura.status_origem, LeituraQualidade.ORIGEM_REGRAS)
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_ATENCAO)
        self.assertIsNone(leitura.confianca)
        self.assertEqual(leitura.modelo_versao, "")

        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        self.assertEqual(ponto_depois.status_atual, Reservatorio.STATUS_ATENCAO)
        self.assertIsNone(ponto_depois.confianca_status)
        self.assertEqual(ponto_depois.modelo_versao, "")
        self.reservatorio.refresh_from_db()
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_ATENCAO)

    def test_status_do_reservatorio_reflete_status_do_ponto_depois(self):
        response_antes = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 28.0,
                "tds": 950.0,
                "turbidez": 2.6,
            }
        )
        self.assertEqual(response_antes.status_code, 201)

        response_depois = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 24.0,
                "tds": 300.0,
                "turbidez": 0.5,
            }
        )
        self.assertEqual(response_depois.status_code, 201)

        self.reservatorio.refresh_from_db()
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_BOM)

    def test_esp32_leitura_considera_meta_personalizada_do_reservatorio(self):
        self.reservatorio.atualizar_reservatorio(
            meta_ppm_tds=300.0,
            meta_ntu_turbidez=1.0,
            meta_celsius_temperatura=25.0,
        )

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "tds": 320.0,
                "turbidez": 0.5,
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_ATENCAO)

    def test_esp32_leitura_aceita_raw_e_calcula_tds_turbidez_no_backend(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "raw": {
                    "adc_tds": 1861,
                    "adc_turb": 980,
                    "firmware_ts_ms": 93000,
                },
            }
        )

        self.assertEqual(response.status_code, 201)

        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.temperatura, 25.0, places=2)
        self.assertAlmostEqual(leitura.turbidez, 0.79, places=2)
        self.assertAlmostEqual(leitura.tds, 580.20, places=2)
        self.assertEqual(
            leitura.sinais_brutos,
            {
                "adc_tds": 1861,
                "adc_turb": 980,
                "firmware_ts_ms": 93000,
            },
        )

    def test_esp32_leitura_retorna_400_quando_raw_tem_formato_invalido(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 26.0,
                "raw": "invalido",
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "campo invalido: raw")
