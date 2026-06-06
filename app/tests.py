import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.models import (
    AmostraCalibracao,
    LeituraQualidade,
    PontoMonitoramento,
    Reservatorio,
    SessaoCalibracao,
)
from app.views import PERIODOS_DISPONIVEIS


class BaseAppTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="monitor",
            password="monitor123",
        )

    def login(self):
        self.client.force_login(self.usuario)

    def criar_reservatorio(self, nome="Reservatorio teste"):
        return Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome=nome,
        )

    def criar_sessao(self, ponto, sensor):
        return SessaoCalibracao.iniciar(
            ponto=ponto,
            sensor=sensor,
            iniciada_por=self.usuario,
            duracao_segundos=30 * 60,
        )

    def adicionar_amostras_estaveis(
        self,
        sessao,
        *,
        temperatura=25.0,
        adc_tds=None,
        adc_turb=None,
        adc_ph=None,
        qtd=5,
    ):
        amostras = []
        for _ in range(qtd):
            amostras.append(
                AmostraCalibracao.objects.create(
                    sessao=sessao,
                    temperatura=temperatura,
                    adc_tds=adc_tds,
                    adc_turb=adc_turb,
                    adc_ph=adc_ph,
                    sinais_brutos={},
                )
            )
        sessao.ultima_amostra_em = amostras[-1].coletada_em
        sessao.save(update_fields=["ultima_amostra_em", "updated_at"])
        return amostras


class AuthTests(BaseAppTestCase):
    def test_index_redireciona_quando_nao_autenticado(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('entrar')}?next={reverse('index')}")

    def test_entrar_post_com_credenciais_validas(self):
        response = self.client.post(
            reverse("entrar"),
            {"nome": "monitor", "senha": "monitor123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("index"))


class ReservatorioPontoUnicoTests(BaseAppTestCase):
    def test_criar_reservatorio_garante_um_ponto_unico_e_aliases_compativeis(self):
        reservatorio = self.criar_reservatorio()

        self.assertEqual(reservatorio.pontos_monitoramento.count(), 1)

        ponto_unico = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto_pre = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_pos = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        self.assertIsNotNone(ponto_unico)
        self.assertEqual(ponto_unico.id, ponto_pre.id)
        self.assertEqual(ponto_unico.id, ponto_pos.id)
        self.assertEqual(ponto_unico.tipo, PontoMonitoramento.TIPO_UNICO)
        self.assertEqual(ponto_unico.nome_exibicao, "Ponto único")

    def test_detalhe_calibracao_e_relatorio_exibem_ponto_unico(self):
        self.login()
        reservatorio = self.criar_reservatorio()

        detalhe = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))
        calibracao = self.client.get(reverse("reservatorio_calibracao", args=[reservatorio.id]))
        relatorio = self.client.get(reverse("reservatorio_relatorio", args=[reservatorio.id]))

        self.assertEqual(detalhe.status_code, 200)
        self.assertEqual(calibracao.status_code, 200)
        self.assertEqual(relatorio.status_code, 200)
        self.assertContains(calibracao, "Ponto único")

    def test_relatorio_retorna_todos_os_periodos_disponiveis(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio relatorio")
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        leitura = ponto.registrar_leitura(
            temperatura=20.0,
            tds=100.0,
            turbidez=0.4,
            ph=7.0,
            status_leitura=Reservatorio.STATUS_BOM,
        )
        LeituraQualidade.objects.filter(id=leitura.id).update(
            data_hora=timezone.now() - timedelta(minutes=10),
        )

        response = self.client.get(reverse("reservatorio_relatorio", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["relatorio_periodos_cards"]),
            len(PERIODOS_DISPONIVEIS),
        )
        self.assertIn("ponto_unico", response.context["relatorio_periodos_cards"][0])

    def test_resetar_leituras_remove_todas_do_reservatorio(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.registrar_leitura(
            temperatura=22.0,
            tds=90.0,
            turbidez=0.2,
            ph=7.1,
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(reverse("reservatorio_resetar_leituras", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LeituraQualidade.objects.count(), 0)

    def test_dashboard_contexto_usa_medias_do_ponto_unico(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.registrar_leitura(
            temperatura=24.0,
            tds=110.0,
            turbidez=0.3,
            ph=7.2,
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("index"))

        card = response.context["dashboard_cards"][0]
        self.assertAlmostEqual(card["ponto_unico"]["temperatura"], 24.0, places=2)
        self.assertEqual(card["status_ponto_unico"]["temperatura"], Reservatorio.STATUS_BOM)


class CalibrationFlowTests(BaseAppTestCase):
    def test_calibracao_sessao_iniciar_e_status_funcionam_com_rota_canonica(self):
        self.login()
        reservatorio = self.criar_reservatorio()

        iniciar = self.client.post(
            reverse(
                "reservatorio_calibracao_sessao_iniciar",
                args=[reservatorio.id, PontoMonitoramento.TIPO_UNICO, "temperatura"],
            )
        )
        self.assertEqual(iniciar.status_code, 302)

        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        sessao = SessaoCalibracao.obter_ativa(
            ponto=ponto,
            sensor=SessaoCalibracao.SENSOR_TEMPERATURA,
        )
        self.assertIsNotNone(sessao)

        self.adicionar_amostras_estaveis(sessao, temperatura=24.5)
        status = self.client.get(
            reverse(
                "reservatorio_calibracao_sessao_status",
                args=[reservatorio.id, PontoMonitoramento.TIPO_UNICO, "temperatura"],
            )
        )

        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertTrue(payload["ativa"])
        self.assertEqual(payload["sensor"], "temperatura")
        self.assertGreaterEqual(payload["amostras"], 5)

    def test_calibracao_temperatura_auto_aceita_alias_legado(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        sessao = self.criar_sessao(ponto, SessaoCalibracao.SENSOR_TEMPERATURA)
        self.adicionar_amostras_estaveis(sessao, temperatura=22.0)

        response = self.client.post(
            reverse("reservatorio_calibracao_temperatura_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura_referencia_c": "25",
                "temperatura_inclinacao": "1.0",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertAlmostEqual(ponto.temperatura_offset_c, 3.0, places=2)
        self.assertIsNotNone(ponto.temperatura_calibrado_em)

    def test_calibracao_tds_auto_aplica_ajuste_no_ponto_unico(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        sessao = self.criar_sessao(ponto, SessaoCalibracao.SENSOR_TDS)
        self.adicionar_amostras_estaveis(sessao, temperatura=25.0, adc_tds=1861)

        response = self.client.post(
            reverse("reservatorio_calibracao_tds_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "tds_alvo_ppm": "40.0",
                "tds_inclinacao": "1.0",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertIsNotNone(ponto.tds_calibrado_em)
        self.assertEqual(ponto.tds_adc_calibracao, 1861)

    def test_calibracao_ph_auto_aplica_dois_pontos_no_ponto_unico(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "ph_solucao_ponto_1": "7.0",
                "ph_tensao_ponto_1": "1.75",
                "ph_solucao_ponto_2": "4.0",
                "ph_tensao_ponto_2": "2.80",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertAlmostEqual(ponto.ph_voltagem_referencia_7, 1.75, places=2)
        self.assertAlmostEqual(ponto.ph_inclinacao, 0.35, places=2)
        self.assertIsNotNone(ponto.ph_calibrado_em)

    def test_resetar_calibracao_sensor_limpa_apenas_sensor_escolhido(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.atualizar_calibracao_temperatura(
            temperatura_bruta_c=20.0,
            temperatura_referencia_c=25.0,
            temperatura_inclinacao=1.0,
        )
        ponto.atualizar_calibracao_ph(
            ph_voltagem_referencia_7=2.50,
            ph_inclinacao=0.20,
            temperatura_calibracao_c=24.0,
        )

        response = self.client.post(
            reverse(
                "reservatorio_calibracao_sensor_resetar",
                args=[reservatorio.id, PontoMonitoramento.TIPO_UNICO, "temperatura"],
            )
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertEqual(ponto.temperatura_offset_c, 0.0)
        self.assertAlmostEqual(ponto.ph_voltagem_referencia_7, 2.50, places=2)
        self.assertAlmostEqual(ponto.ph_inclinacao, 0.20, places=2)


@override_settings(ESP32_API_TOKEN="token-monitor")
class Esp32IngestaoTests(BaseAppTestCase):
    def setUp(self):
        super().setUp()
        self.reservatorio = self.criar_reservatorio("Reservatorio ESP32")
        self.ponto = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)

    def _post_json(self, url, payload, *, token=True):
        headers = {"content_type": "application/json"}
        if token:
            headers["HTTP_X_API_TOKEN"] = "token-monitor"
        return self.client.post(url, data=json.dumps(payload), **headers)

    def test_esp32_leitura_retorna_401_sem_token_valido(self):
        response = self._post_json(
            reverse("esp32_leitura"),
            {"reservatorio_id": self.reservatorio.id},
            token=False,
        )

        self.assertEqual(response.status_code, 401)

    def test_esp32_leitura_aceita_aliases_legados_e_sincroniza_no_ponto_unico(self):
        payload_pre = {
            "reservatorio_id": self.reservatorio.id,
            "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
            "temperatura": 24.0,
            "tds": 120.0,
            "turbidez": 0.4,
            "ph": 7.1,
        }
        payload_pos = {
            "reservatorio_id": self.reservatorio.id,
            "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
            "temperatura": 36.0,
            "tds": 780.0,
            "turbidez": 6.0,
            "ph": 10.0,
        }

        response_pre = self._post_json(reverse("esp32_leitura"), payload_pre)
        response_pos = self._post_json(reverse("esp32_leitura"), payload_pos)

        self.assertEqual(response_pre.status_code, 201)
        self.assertEqual(response_pos.status_code, 201)
        self.assertEqual(LeituraQualidade.objects.count(), 2)
        self.assertEqual(
            LeituraQualidade.objects.values_list("ponto_id", flat=True).distinct().get(),
            self.ponto.id,
        )

        self.reservatorio.refresh_from_db()
        self.ponto.refresh_from_db()
        self.assertEqual(self.reservatorio.status, self.ponto.status_atual)

    def test_esp32_leitura_raw_calcula_metricas_e_preserva_device_id(self):
        payload = {
            "reservatorio_id": self.reservatorio.id,
            "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
            "temperatura": 25.0,
            "raw": {
                "adc_tds": 1861,
                "adc_turb": 980,
                "adc_ph": 2048,
                "firmware_ts_ms": 1000,
                "firmware_now_ms": 2000,
                "device_id": "esp_unico_01",
            },
        }

        response = self._post_json(reverse("esp32_leitura"), payload)

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.get()
        self.assertGreaterEqual(leitura.tds, 0.0)
        self.assertGreaterEqual(leitura.turbidez, 0.0)
        self.assertIn("device_id", leitura.sinais_brutos)
        self.assertEqual(leitura.sinais_brutos["device_id"], "esp_unico_01")

    def test_esp32_calibracao_comando_aceita_alias_legado(self):
        sessao = self.criar_sessao(self.ponto, SessaoCalibracao.SENSOR_TDS)

        response = self.client.get(
            reverse("esp32_calibracao_comando"),
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
            },
            HTTP_X_API_TOKEN="token-monitor",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["modo"], "calibracao")
        self.assertEqual(payload["sessao_id"], sessao.id)
        self.assertEqual(payload["sensor"], SessaoCalibracao.SENSOR_TDS)

    def test_esp32_calibracao_amostra_registra_em_sessao_ativa_do_ponto_unico(self):
        sessao = self.criar_sessao(self.ponto, SessaoCalibracao.SENSOR_PH)

        response = self._post_json(
            reverse("esp32_calibracao_amostra"),
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "sensor": "ph",
                "temperatura": 24.0,
                "device_id": "esp_unico_02",
                "raw": {
                    "adc_ph": 2050,
                    "firmware_ts_ms": 10,
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(AmostraCalibracao.objects.count(), 1)
        amostra = AmostraCalibracao.objects.get()
        self.assertEqual(amostra.sessao_id, sessao.id)
        self.assertEqual(amostra.adc_ph, 2050)
