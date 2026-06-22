import json
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import (
    AmostraCalibracao,
    LeituraQualidade,
    PontoMonitoramento,
    Reservatorio,
    SessaoCalibracao,
)
from app.services.regras import calcular_status
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

    def criar_sessao(self, ponto, sensor, *, intervalo_envio_ms=None):
        return SessaoCalibracao.iniciar(
            ponto=ponto,
            sensor=sensor,
            iniciada_por=self.usuario,
            intervalo_envio_ms=intervalo_envio_ms,
            duracao_segundos=30 * 60,
        )

    def aware_datetime(self, year, month, day, hour, minute=0, second=0):
        return timezone.make_aware(
            datetime(year, month, day, hour, minute, second),
            timezone.get_current_timezone(),
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


class RegrasStatusTests(TestCase):
    def test_tds_usa_perigo_com_25_porcento_da_faixa(self):
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=530.0,
                turbidez=1.0,
                ph=7.0,
                faixa_ppm_tds_min=100.0,
                faixa_ppm_tds_max=500.0,
            ),
            Reservatorio.STATUS_ATENCAO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=626.0,
                turbidez=1.0,
                ph=7.0,
                faixa_ppm_tds_min=100.0,
                faixa_ppm_tds_max=500.0,
            ),
            Reservatorio.STATUS_PERIGO,
        )

    def test_turbidez_temperatura_e_ph_usam_novas_margens_de_perigo(self):
        self.assertEqual(
            calcular_status(
                temperatura=35.0,
                tds=120.0,
                turbidez=3.0,
                ph=7.0,
                faixa_celsius_temperatura_min=10.0,
                faixa_celsius_temperatura_max=30.0,
            ),
            Reservatorio.STATUS_ATENCAO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=41.0,
                tds=120.0,
                turbidez=3.0,
                ph=7.0,
                faixa_celsius_temperatura_min=10.0,
                faixa_celsius_temperatura_max=30.0,
            ),
            Reservatorio.STATUS_PERIGO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=120.0,
                turbidez=40.0,
                ph=7.0,
                faixa_ntu_turbidez_min=0.0,
                faixa_ntu_turbidez_max=5.0,
            ),
            Reservatorio.STATUS_ATENCAO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=120.0,
                turbidez=56.0,
                ph=7.0,
                faixa_ntu_turbidez_min=0.0,
                faixa_ntu_turbidez_max=5.0,
            ),
            Reservatorio.STATUS_PERIGO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=120.0,
                turbidez=1.0,
                ph=8.8,
                faixa_ph_min=6.0,
                faixa_ph_max=8.0,
            ),
            Reservatorio.STATUS_ATENCAO,
        )
        self.assertEqual(
            calcular_status(
                temperatura=25.0,
                tds=120.0,
                turbidez=1.0,
                ph=9.6,
                faixa_ph_min=6.0,
                faixa_ph_max=8.0,
            ),
            Reservatorio.STATUS_PERIGO,
        )


class ReservatorioPontoUnicoTests(BaseAppTestCase):
    def test_criar_reservatorio_garante_ponto_unico_e_campos_esp32(self):
        reservatorio = self.criar_reservatorio()

        self.assertEqual(reservatorio.pontos_monitoramento.count(), 1)
        self.assertEqual(reservatorio.esp32_intervalo_envio_normal_s, 60)
        self.assertEqual(reservatorio.esp32_intervalo_envio_calibracao_s, 5)
        self.assertFalse(reservatorio.alerta_sonoro_silenciado)
        self.assertFalse(reservatorio.alerta_sonoro_silenciado_permanente)
        self.assertIsNone(reservatorio.alerta_sonoro_teste_ate)

        ponto_unico = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto_pre = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_pos = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        self.assertIsNotNone(ponto_unico)
        self.assertEqual(ponto_unico.id, ponto_pre.id)
        self.assertEqual(ponto_unico.id, ponto_pos.id)

    def test_edicao_exibe_campos_esp32_e_permte_atualizar(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio edicao")

        edicao = self.client.get(reverse("reservatorio_editar", args=[reservatorio.id]))

        self.assertEqual(edicao.status_code, 200)
        self.assertContains(edicao, "Reservatório ID")
        self.assertContains(edicao, "esp32_intervalo_envio_normal_s")
        self.assertContains(edicao, "esp32_intervalo_envio_calibracao_s")
        self.assertNotContains(edicao, "Token de integração")

        resposta = self.client.post(
            reverse("reservatorio_atualizar", args=[reservatorio.id]),
            {
                "nome": reservatorio.nome,
                "faixa_ppm_tds_min": "10",
                "faixa_ppm_tds_max": "200",
                "faixa_ntu_turbidez_min": "0",
                "faixa_ntu_turbidez_max": "1",
                "faixa_celsius_temperatura_min": "10",
                "faixa_celsius_temperatura_max": "30",
                "faixa_ph_min": "6",
                "faixa_ph_max": "8",
                "esp32_intervalo_envio_normal_s": "120",
                "esp32_intervalo_envio_calibracao_s": "2",
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta.url,
            reverse("reservatorio_editar", args=[reservatorio.id]),
        )
        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.esp32_intervalo_envio_normal_s, 120)
        self.assertEqual(reservatorio.esp32_intervalo_envio_calibracao_s, 2)

    def test_edicao_exibe_regras_de_status_em_cada_card_de_faixa(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio regras visuais")

        response = self.client.get(reverse("reservatorio_editar", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ultrapassou a faixa em mais de 25%")
        self.assertContains(response, "Ultrapassou a faixa em mais de 50 NTU")
        self.assertContains(response, "Ultrapassou a faixa em mais de 10 C")
        self.assertContains(response, "Ultrapassou a faixa em mais de 1.5 pH")

    def test_edicao_reclassifica_ultima_leitura_e_sincroniza_status_ao_salvar_faixas(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio reclassificacao imediata")
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        leitura = ponto.registrar_leitura(
            temperatura=24.0,
            tds=120.0,
            turbidez=60.0,
            ph=7.0,
            status_leitura=Reservatorio.STATUS_PERIGO,
        )
        reservatorio.sincronizar_status_pelo_ponto()

        response = self.client.post(
            reverse("reservatorio_atualizar", args=[reservatorio.id]),
            {
                "nome": reservatorio.nome,
                "faixa_ppm_tds_min": str(reservatorio.faixa_ppm_tds_min),
                "faixa_ppm_tds_max": str(reservatorio.faixa_ppm_tds_max),
                "faixa_ntu_turbidez_min": "0",
                "faixa_ntu_turbidez_max": "70",
                "faixa_celsius_temperatura_min": str(reservatorio.faixa_celsius_temperatura_min),
                "faixa_celsius_temperatura_max": str(reservatorio.faixa_celsius_temperatura_max),
                "faixa_ph_min": str(reservatorio.faixa_ph_min),
                "faixa_ph_max": str(reservatorio.faixa_ph_max),
                "esp32_intervalo_envio_normal_s": str(reservatorio.esp32_intervalo_envio_normal_s),
                "esp32_intervalo_envio_calibracao_s": str(reservatorio.esp32_intervalo_envio_calibracao_s),
            },
        )

        self.assertEqual(response.status_code, 302)
        leitura.refresh_from_db()
        ponto.refresh_from_db()
        reservatorio.refresh_from_db()
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_BOM)
        self.assertEqual(ponto.status_atual, Reservatorio.STATUS_BOM)
        self.assertEqual(reservatorio.status, Reservatorio.STATUS_BOM)

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

    def test_dashboard_ignora_turbidez_noturna_na_media_do_periodo(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio media turbidez")
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.registrar_leitura(
            temperatura=20.0,
            tds=100.0,
            turbidez=1.0,
            ph=7.0,
            status_leitura=Reservatorio.STATUS_BOM,
            data_hora=self.aware_datetime(2026, 6, 22, 14, 0),
        )
        ponto.registrar_leitura(
            temperatura=24.0,
            tds=300.0,
            turbidez=20.0,
            ph=7.4,
            status_leitura=Reservatorio.STATUS_PERIGO,
            data_hora=self.aware_datetime(2026, 6, 22, 20, 0),
        )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        card = response.context["dashboard_cards"][0]
        self.assertAlmostEqual(card["ponto_unico"]["turbidez"], 1.0, places=3)
        self.assertAlmostEqual(card["ponto_unico"]["tds"], 200.0, places=3)
        self.assertEqual(card["status_ponto_unico"]["turbidez"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_periodo"], Reservatorio.STATUS_BOM)

    def test_detalhe_mostra_turbidez_noturna_com_status_neutro_e_serie_marcada(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio turbidez noturna")
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.registrar_leitura(
            temperatura=21.0,
            tds=120.0,
            turbidez=1.5,
            ph=7.0,
            status_leitura=Reservatorio.STATUS_BOM,
            data_hora=self.aware_datetime(2026, 6, 22, 12, 0),
        )
        ponto.registrar_leitura(
            temperatura=22.0,
            tds=125.0,
            turbidez=18.0,
            ph=7.1,
            status_leitura=Reservatorio.STATUS_PERIGO,
            data_hora=self.aware_datetime(2026, 6, 22, 20, 0),
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        metrica_turbidez = next(
            item
            for item in response.context["metricas_recentes"]
            if item["id"] == "turbidez"
        )
        self.assertEqual(
            metrica_turbidez["ponto_unico"]["status"],
            "ignorado-noturno",
        )
        self.assertEqual(
            metrica_turbidez["ponto_unico"]["status_label"],
            "Ignorado a noite",
        )
        self.assertEqual(
            [item["night"] for item in response.context["turbidez_series"]],
            [False, True],
        )

    def test_calibracao_turbidez_orienta_mesma_luz_ambiente(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio calibracao luz")

        response = self.client.get(
            reverse(
                "reservatorio_calibracao_sensor",
                args=[reservatorio.id, "turbidez"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mesma luz ambiente")

    def test_alerta_sonoro_pode_ser_silenciado_e_reativado_no_detalhe(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio alarme")
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.atualizar_status(status=Reservatorio.STATUS_PERIGO)
        reservatorio.sincronizar_status_pelo_ponto()

        silenciar = self.client.post(
            reverse("reservatorio_alerta_sonoro_alternar", args=[reservatorio.id])
        )

        self.assertEqual(silenciar.status_code, 302)
        self.assertEqual(
            silenciar.url,
            reverse("reservatorio_detalhe", args=[reservatorio.id]),
        )
        reservatorio.refresh_from_db()
        self.assertTrue(reservatorio.alerta_sonoro_silenciado)

        reativar = self.client.post(
            reverse("reservatorio_alerta_sonoro_alternar", args=[reservatorio.id])
        )

        self.assertEqual(reativar.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertFalse(reservatorio.alerta_sonoro_silenciado)

    def test_alerta_sonoro_pode_ser_silenciado_permanentemente(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio alarme permanente")

        silenciar = self.client.post(
            reverse("reservatorio_alerta_sonoro_permanente_alternar", args=[reservatorio.id])
        )

        self.assertEqual(silenciar.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertTrue(reservatorio.alerta_sonoro_silenciado_permanente)

        reativar = self.client.post(
            reverse("reservatorio_alerta_sonoro_permanente_alternar", args=[reservatorio.id])
        )

        self.assertEqual(reativar.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertFalse(reservatorio.alerta_sonoro_silenciado_permanente)

    def test_alerta_sonoro_pode_ser_testado_por_cinco_segundos(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio teste sonoro")

        resposta = self.client.post(
            reverse("reservatorio_alerta_sonoro_testar", args=[reservatorio.id])
        )

        self.assertEqual(resposta.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertIsNotNone(reservatorio.alerta_sonoro_teste_ate)
        self.assertTrue(reservatorio.alerta_sonoro_teste_ativo)

    def test_pagina_opcoes_alerta_sonoro_exibe_controles(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio alerta opcoes")

        response = self.client.get(
            reverse("reservatorio_alerta_sonoro_opcoes", args=[reservatorio.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opções do alerta sonoro")
        self.assertContains(response, "Testar alerta sonoro")
        self.assertContains(response, "Voltar aos detalhes")

    def test_acoes_alerta_sonoro_retorna_para_pagina_de_opcoes_quando_solicitado(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio alerta redirect")

        resposta = self.client.post(
            reverse("reservatorio_alerta_sonoro_testar", args=[reservatorio.id]),
            {"destino": "opcoes"},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta.url,
            reverse("reservatorio_alerta_sonoro_opcoes", args=[reservatorio.id]),
        )


class CalibrationFlowTests(BaseAppTestCase):
    def test_calibracao_sessao_iniciar_ajusta_plano_ao_intervalo_configurado(self):
        self.login()
        reservatorio = self.criar_reservatorio("Reservatorio calibracao proporcional")
        reservatorio.esp32_intervalo_envio_calibracao_s = 1
        reservatorio.save(update_fields=["esp32_intervalo_envio_calibracao_s", "updated_at"])

        iniciar = self.client.post(
            reverse(
                "reservatorio_calibracao_sessao_iniciar",
                args=[reservatorio.id, "tds"],
            )
        )

        self.assertEqual(iniciar.status_code, 302)
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        sessao = SessaoCalibracao.obter_ativa(
            ponto=ponto,
            sensor=SessaoCalibracao.SENSOR_TDS,
        )
        self.assertIsNotNone(sessao)
        self.assertEqual(sessao.intervalo_envio_ms, 1000)
        self.assertEqual(sessao.qtd_amostras, 16)
        self.assertEqual(sessao.atraso_amostra_ms, 50)

    def test_calibracao_sessao_iniciar_e_status_funcionam_na_rota_nova(self):
        self.login()
        reservatorio = self.criar_reservatorio()

        iniciar = self.client.post(
            reverse(
                "reservatorio_calibracao_sessao_iniciar",
                args=[reservatorio.id, "temperatura"],
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
                args=[reservatorio.id, "temperatura"],
            )
        )

        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertTrue(payload["ativa"])
        self.assertEqual(payload["sensor"], "temperatura")
        self.assertGreaterEqual(payload["amostras"], 5)
        self.assertEqual(
            payload["intervalo_poll_ms"],
            reservatorio.esp32_intervalo_envio_calibracao_s * 1000,
        )
        self.assertTrue(payload["cursor"].startswith("ativa:"))

    def test_calibracao_temperatura_auto_funciona_sem_ponto_tipo(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        sessao = self.criar_sessao(ponto, SessaoCalibracao.SENSOR_TEMPERATURA)
        self.adicionar_amostras_estaveis(sessao, temperatura=22.0)

        response = self.client.post(
            reverse("reservatorio_calibracao_temperatura_auto", args=[reservatorio.id]),
            {
                "temperatura_referencia_c": "25,0",
                "temperatura_inclinacao": "1,0",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertAlmostEqual(ponto.temperatura_offset_c, 3.0, places=2)
        self.assertIsNotNone(ponto.temperatura_calibrado_em)

    def test_resetar_calibracao_sensor_usa_rota_sem_ponto(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        ponto.atualizar_calibracao_temperatura(
            temperatura_bruta_c=20.0,
            temperatura_referencia_c=25.0,
            temperatura_inclinacao=1.0,
        )

        response = self.client.post(
            reverse(
                "reservatorio_calibracao_sensor_resetar",
                args=[reservatorio.id, "temperatura"],
            )
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertEqual(ponto.temperatura_offset_c, 0.0)

    def test_calibracao_turbidez_aplica_reta_de_dois_pontos(self):
        self.login()
        reservatorio = self.criar_reservatorio()
        ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)

        response = self.client.post(
            reverse("reservatorio_calibracao_turbidez_auto", args=[reservatorio.id]),
            {
                "turbidez_referencia_ponto_1": "50,00",
                "turbidez_tensao_ponto_1": "0,8",
                "turbidez_referencia_ponto_2": "200,00",
                "turbidez_tensao_ponto_2": "0,2",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto.refresh_from_db()
        self.assertAlmostEqual(ponto.turbidez_alvo_calibracao_ntu, 50.0, places=3)
        self.assertAlmostEqual(ponto.turbidez_inclinacao, -250.0, places=6)
        self.assertAlmostEqual(ponto.turbidez_offset_ntu, 250.0, places=6)
        _, turbidez_ponto_1 = ponto.aplicar_calibracao_agua(tds=0.0, turbidez=0.8)
        _, turbidez_ponto_2 = ponto.aplicar_calibracao_agua(tds=0.0, turbidez=0.2)
        self.assertAlmostEqual(turbidez_ponto_1, 50.0, places=3)
        self.assertAlmostEqual(turbidez_ponto_2, 200.0, places=3)


class Esp32IngestaoTests(BaseAppTestCase):
    def setUp(self):
        super().setUp()
        self.reservatorio = self.criar_reservatorio("Reservatorio ESP32")
        self.ponto = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def _get_config(self):
        return self.client.get(
            reverse("esp32_configuracao"),
            {"reservatorio_id": self.reservatorio.id},
        )

    def test_esp32_configuracao_exige_reservatorio_id_valido(self):
        response = self.client.get(reverse("esp32_configuracao"))

        self.assertEqual(response.status_code, 401)

    def test_esp32_configuracao_retorna_intervalos_e_modo_normal(self):
        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["modo"], "normal")
        self.assertEqual(payload["poll_configuracao_ms"], 2000)
        self.assertEqual(payload["intervalo_normal_ms"], 60000)
        self.assertEqual(payload["intervalo_calibracao_ms"], 5000)
        self.assertEqual(payload["normal_qtd_amostras_tds"], 60)
        self.assertEqual(payload["normal_atraso_amostra_tds_ms"], 5)
        self.assertEqual(payload["normal_qtd_amostras_turbidez"], 60)
        self.assertEqual(payload["normal_atraso_amostra_turbidez_ms"], 10)
        self.assertEqual(payload["normal_qtd_amostras_ph"], 60)
        self.assertEqual(payload["normal_atraso_amostra_ph_ms"], 5)
        self.assertFalse(payload["alerta_sonoro_ativo"])
        self.assertEqual(payload["alerta_sonoro_intervalo_ligado_ms"], 500)
        self.assertEqual(payload["alerta_sonoro_intervalo_desligado_ms"], 500)
        self.assertIn("server_epoch_ms", payload)

    def test_esp32_configuracao_ajusta_plano_normal_ao_intervalo_configurado(self):
        self.reservatorio.esp32_intervalo_envio_normal_s = 120
        self.reservatorio.save(update_fields=["esp32_intervalo_envio_normal_s", "updated_at"])

        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intervalo_normal_ms"], 120000)
        self.assertEqual(payload["normal_qtd_amostras_tds"], 120)
        self.assertEqual(payload["normal_qtd_amostras_turbidez"], 120)
        self.assertEqual(payload["normal_qtd_amostras_ph"], 120)

    def test_esp32_configuracao_ativa_alerta_sonoro_em_status_perigo(self):
        self.ponto.atualizar_status(status=Reservatorio.STATUS_PERIGO)
        self.reservatorio.sincronizar_status_pelo_ponto()

        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["alerta_sonoro_ativo"])

    def test_esp32_configuracao_respeita_silencio_permanente(self):
        self.ponto.atualizar_status(status=Reservatorio.STATUS_PERIGO)
        self.reservatorio.sincronizar_status_pelo_ponto()
        self.reservatorio.silenciar_alerta_sonoro_permanentemente()

        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["alerta_sonoro_ativo"])

    def test_esp32_configuracao_ativa_alerta_sonoro_durante_teste(self):
        self.reservatorio.iniciar_teste_alerta_sonoro(duracao_segundos=5)

        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["alerta_sonoro_ativo"])

    def test_esp32_configuracao_retorna_sessao_ativa(self):
        sessao = self.criar_sessao(
            self.ponto,
            SessaoCalibracao.SENSOR_TDS,
            intervalo_envio_ms=self.reservatorio.esp32_intervalo_envio_calibracao_s * 1000,
        )

        response = self._get_config()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["modo"], "calibracao")
        self.assertEqual(payload["sessao_id"], sessao.id)
        self.assertEqual(payload["sensor"], SessaoCalibracao.SENSOR_TDS)
        self.assertIn("expira_em", payload)

    def test_esp32_leitura_aceita_payload_sem_ponto_tipo(self):
        response = self._post_json(
            reverse("esp32_leitura"),
            {
                "reservatorio_id": self.reservatorio.id,
                "temperatura": 24.0,
                "tds": 120.0,
                "turbidez": 0.4,
                "ph": 7.1,
            },
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.get()
        self.assertEqual(leitura.ponto_id, self.ponto.id)

    def test_esp32_leitura_rejeita_fluxo_antigo_com_ponto_tipo(self):
        response = self._post_json(
            reverse("esp32_leitura"),
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura": 24.0,
                "tds": 120.0,
                "turbidez": 0.4,
                "ph": 7.1,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "campo nao suportado: ponto_tipo")

    def test_esp32_leitura_raw_calcula_metricas_e_preserva_device_id(self):
        response = self._post_json(
            reverse("esp32_leitura"),
            {
                "reservatorio_id": self.reservatorio.id,
                "temperatura": 25.0,
                "raw": {
                    "adc_tds": 1861,
                    "adc_turb": 980,
                    "adc_ph": 2048,
                    "firmware_ts_ms": 1000,
                    "firmware_now_ms": 2000,
                    "device_id": "esp_unico_01",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.get()
        self.assertGreaterEqual(leitura.tds, 0.0)
        self.assertGreaterEqual(leitura.turbidez, 0.0)
        self.assertIn("device_id", leitura.sinais_brutos)
        self.assertEqual(leitura.sinais_brutos["device_id"], "esp_unico_01")

    def test_esp32_leitura_noturna_ignora_turbidez_no_status_atual(self):
        instante_noturno = self.aware_datetime(2026, 6, 22, 19, 0)

        with patch("app.services.ingestao.timezone.now", return_value=instante_noturno):
            response = self._post_json(
                reverse("esp32_leitura"),
                {
                    "reservatorio_id": self.reservatorio.id,
                    "temperatura": 24.0,
                    "tds": 120.0,
                    "turbidez": 60.0,
                    "ph": 7.1,
                    "raw": {
                        "firmware_ts_ms": 5000,
                        "firmware_now_ms": 5000,
                    },
                },
            )

        self.assertEqual(response.status_code, 201)
        self.ponto.refresh_from_db()
        self.reservatorio.refresh_from_db()
        self.assertEqual(self.ponto.status_atual, Reservatorio.STATUS_BOM)
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_BOM)
        self.assertEqual(LeituraQualidade.objects.count(), 1)

    def test_esp32_leitura_diurna_mantem_impacto_normal_da_turbidez(self):
        instante_diurno = self.aware_datetime(2026, 6, 22, 12, 0)

        with patch("app.services.ingestao.timezone.now", return_value=instante_diurno):
            response = self._post_json(
                reverse("esp32_leitura"),
                {
                    "reservatorio_id": self.reservatorio.id,
                    "temperatura": 24.0,
                    "tds": 120.0,
                    "turbidez": 60.0,
                    "ph": 7.1,
                    "raw": {
                        "firmware_ts_ms": 5000,
                        "firmware_now_ms": 5000,
                    },
                },
            )

        self.assertEqual(response.status_code, 201)
        self.ponto.refresh_from_db()
        self.reservatorio.refresh_from_db()
        self.assertEqual(self.ponto.status_atual, Reservatorio.STATUS_PERIGO)
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_PERIGO)

    def test_esp32_calibracao_amostra_registra_sem_ponto_tipo(self):
        sessao = self.criar_sessao(self.ponto, SessaoCalibracao.SENSOR_PH)

        response = self._post_json(
            reverse("esp32_calibracao_amostra"),
            {
                "reservatorio_id": self.reservatorio.id,
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

    def test_esp32_calibracao_amostra_rejeita_fluxo_antigo_com_ponto_tipo(self):
        self.criar_sessao(self.ponto, SessaoCalibracao.SENSOR_PH)

        response = self._post_json(
            reverse("esp32_calibracao_amostra"),
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "sensor": "ph",
                "temperatura": 24.0,
                "raw": {"adc_ph": 2050},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["erro"], "campo nao suportado: ponto_tipo")
