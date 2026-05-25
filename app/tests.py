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
        self.assertEqual(reservatorio.faixa_ppm_tds_min, Reservatorio.FAIXA_PADRAO_PPM_TDS_MIN)
        self.assertEqual(reservatorio.faixa_ppm_tds_max, Reservatorio.FAIXA_PADRAO_PPM_TDS_MAX)
        self.assertEqual(
            reservatorio.faixa_ntu_turbidez_min,
            Reservatorio.FAIXA_PADRAO_NTU_TURBIDEZ_MIN,
        )
        self.assertEqual(
            reservatorio.faixa_ntu_turbidez_max,
            Reservatorio.FAIXA_PADRAO_NTU_TURBIDEZ_MAX,
        )
        self.assertEqual(
            reservatorio.faixa_celsius_temperatura_min,
            Reservatorio.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN,
        )
        self.assertEqual(
            reservatorio.faixa_celsius_temperatura_max,
            Reservatorio.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX,
        )
        self.assertEqual(reservatorio.faixa_ph_min, Reservatorio.FAIXA_PADRAO_PH_MIN)
        self.assertEqual(reservatorio.faixa_ph_max, Reservatorio.FAIXA_PADRAO_PH_MAX)
        self.assertEqual(reservatorio.meta_ppm_tds, Reservatorio.META_PADRAO_PPM_TDS)
        self.assertEqual(reservatorio.meta_ntu_turbidez, Reservatorio.META_PADRAO_NTU_TURBIDEZ)
        self.assertEqual(
            reservatorio.meta_celsius_temperatura,
            Reservatorio.META_PADRAO_CELSIUS_TEMPERATURA,
        )
        self.assertEqual(reservatorio.meta_ph, Reservatorio.META_PADRAO_PH)
        self.assertEqual(reservatorio.pontos_monitoramento.count(), 2)
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        self.assertEqual(
            ponto_antes.ph_voltagem_referencia_7,
            PontoMonitoramento.PH_VOLTAGEM_REFERENCIA_7_PADRAO,
        )
        self.assertEqual(
            ponto_antes.ph_inclinacao,
            PontoMonitoramento.PH_INCLINACAO_PADRAO,
        )
        self.assertEqual(
            ponto_antes.temperatura_inclinacao,
            PontoMonitoramento.TEMPERATURA_INCLINACAO_PADRAO,
        )
        self.assertEqual(ponto_antes.temperatura_offset_c, 0.0)
        self.assertIsNone(ponto_antes.temperatura_calibrado_em)
        self.assertIsNone(ponto_antes.ph_calibrado_em)
        self.assertEqual(
            ponto_depois.ph_voltagem_referencia_7,
            PontoMonitoramento.PH_VOLTAGEM_REFERENCIA_7_PADRAO,
        )
        self.assertEqual(
            ponto_depois.ph_inclinacao,
            PontoMonitoramento.PH_INCLINACAO_PADRAO,
        )
        self.assertEqual(
            ponto_depois.temperatura_inclinacao,
            PontoMonitoramento.TEMPERATURA_INCLINACAO_PADRAO,
        )
        self.assertEqual(ponto_depois.temperatura_offset_c, 0.0)
        self.assertIsNone(ponto_depois.temperatura_calibrado_em)
        self.assertIsNone(ponto_depois.ph_calibrado_em)
        self.assertEqual(ponto_antes.tds_offset_ppm, 0.0)
        self.assertEqual(ponto_antes.tds_inclinacao, PontoMonitoramento.TDS_INCLINACAO_PADRAO)
        self.assertEqual(ponto_antes.turbidez_offset_ntu, 0.0)
        self.assertEqual(
            ponto_antes.turbidez_inclinacao,
            PontoMonitoramento.TURBIDEZ_INCLINACAO_PADRAO,
        )
        self.assertEqual(
            ponto_antes.tds_alvo_calibracao_ppm,
            PontoMonitoramento.TDS_ALVO_CALIBRACAO_PADRAO,
        )
        self.assertEqual(
            ponto_antes.turbidez_alvo_calibracao_ntu,
            PontoMonitoramento.TURBIDEZ_ALVO_CALIBRACAO_PADRAO,
        )
        self.assertIsNone(ponto_antes.tds_calibrado_em)
        self.assertIsNone(ponto_antes.turbidez_calibrado_em)
        self.assertIsNone(ponto_antes.agua_calibrado_em)

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
        self.assertContains(response, reverse("reservatorio_calibracao", args=[reservatorio.id]))
        self.assertContains(response, "Calibrar")
        self.assertContains(response, "Resetar leitura")

    def test_resetar_leituras_remove_apenas_registros_do_reservatorio(self):
        self._logar()
        reservatorio_alvo = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio reset alvo",
            status=Reservatorio.STATUS_BOM,
        )
        reservatorio_controle = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio reset controle",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_alvo_antes = reservatorio_alvo.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_alvo_depois = reservatorio_alvo.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        ponto_controle_antes = reservatorio_controle.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)

        ponto_alvo_antes.registrar_leitura(
            temperatura=25.0,
            tds=300.0,
            turbidez=0.7,
            ph=7.1,
            status_leitura=Reservatorio.STATUS_BOM,
        )
        ponto_alvo_depois.registrar_leitura(
            temperatura=24.0,
            tds=250.0,
            turbidez=0.6,
            ph=7.0,
            status_leitura=Reservatorio.STATUS_BOM,
        )
        ponto_controle_antes.registrar_leitura(
            temperatura=28.0,
            tds=500.0,
            turbidez=1.2,
            ph=7.8,
            status_leitura=Reservatorio.STATUS_ATENCAO,
        )

        response = self.client.post(
            reverse("reservatorio_resetar_leituras", args=[reservatorio_alvo.id]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("reservatorio_detalhe", args=[reservatorio_alvo.id]),
        )
        self.assertEqual(
            LeituraQualidade.objects.filter(ponto__reservatorio=reservatorio_alvo).count(),
            0,
        )
        self.assertEqual(
            LeituraQualidade.objects.filter(ponto__reservatorio=reservatorio_controle).count(),
            1,
        )

    def test_detalhe_expoe_metricas_recentes_dos_dois_pontos(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio metricas recentes",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        ponto_antes.registrar_leitura(
            temperatura=36.0,
            tds=760.0,
            turbidez=5.5,
            ph=9.8,
            status_leitura=Reservatorio.STATUS_PERIGO,
        )
        ponto_depois.registrar_leitura(
            temperatura=24.0,
            tds=120.0,
            turbidez=0.4,
            ph=7.2,
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        metricas = response.context["metricas_recentes"]
        self.assertEqual([metrica["id"] for metrica in metricas], ["temperatura", "tds", "turbidez", "ph"])

        temperatura = metricas[0]
        self.assertAlmostEqual(temperatura["antes"]["valor"], 36.0, places=2)
        self.assertEqual(temperatura["antes"]["status"], Reservatorio.STATUS_ATENCAO)
        self.assertAlmostEqual(temperatura["depois"]["valor"], 24.0, places=2)
        self.assertEqual(temperatura["depois"]["status"], Reservatorio.STATUS_BOM)

        tds = metricas[1]
        self.assertAlmostEqual(tds["antes"]["valor"], 760.0, places=2)
        self.assertEqual(tds["antes"]["status"], Reservatorio.STATUS_PERIGO)
        self.assertAlmostEqual(tds["depois"]["valor"], 120.0, places=2)
        self.assertEqual(tds["depois"]["status"], Reservatorio.STATUS_BOM)

        self.assertContains(response, "Ultima medicao")
        self.assertContains(response, "Antes")
        self.assertContains(response, "Depois")

    def test_calibracao_retorna_200(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio calibracao pagina",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_calibracao", args=[reservatorio.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CALIBRACAO")
        self.assertContains(response, "Escolha o ponto")
        self.assertContains(response, "Antes do tratamento")
        self.assertContains(response, "Depois do tratamento")

    def test_calibracao_ponto_retorna_sensores(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio calibracao sensores",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(
            reverse(
                "reservatorio_calibracao_ponto",
                args=[reservatorio.id, PontoMonitoramento.TIPO_ANTES],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha o sensor")
        self.assertContains(response, "Temperatura")
        self.assertContains(response, "TDS")
        self.assertContains(response, "Turbidez")
        self.assertContains(response, "pH")

    def test_calibracao_sensor_retorna_formulario_do_sensor(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio calibracao sensor",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(
            reverse(
                "reservatorio_calibracao_sensor",
                args=[reservatorio.id, PontoMonitoramento.TIPO_ANTES, "temperatura"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passo 3")
        self.assertContains(response, "A media da temperatura deveria estar em")
        self.assertContains(response, "Salvar calibracao")
        self.assertContains(response, "Iniciar calibracao")
        self.assertContains(response, "Resetar dados de calibracao do sensor")

    def test_resetar_calibracao_sensor_limpa_apenas_sensor_selecionado(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio reset calibracao sensor",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_antes.atualizar_calibracao_temperatura(
            temperatura_bruta_c=20.0,
            temperatura_referencia_c=25.0,
            temperatura_inclinacao=1.100,
        )
        ponto_antes.atualizar_calibracao_ph(
            ph_voltagem_referencia_7=2.50,
            ph_inclinacao=0.20,
            temperatura_calibracao_c=24.0,
        )

        response = self.client.post(
            reverse(
                "reservatorio_calibracao_sensor_resetar",
                args=[reservatorio.id, ponto_antes.tipo, "temperatura"],
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse(
                "reservatorio_calibracao_sensor",
                args=[reservatorio.id, ponto_antes.tipo, "temperatura"],
            ),
        )
        ponto_antes.refresh_from_db()
        self.assertEqual(
            ponto_antes.temperatura_inclinacao,
            PontoMonitoramento.TEMPERATURA_INCLINACAO_PADRAO,
        )
        self.assertEqual(ponto_antes.temperatura_offset_c, 0.0)
        self.assertIsNone(ponto_antes.temperatura_valor_referencia_c)
        self.assertIsNone(ponto_antes.temperatura_bruta_referencia_c)
        self.assertIsNone(ponto_antes.temperatura_calibrado_em)
        self.assertAlmostEqual(ponto_antes.ph_voltagem_referencia_7, 2.50, places=2)
        self.assertAlmostEqual(ponto_antes.ph_inclinacao, 0.20, places=2)
        self.assertAlmostEqual(ponto_antes.ph_temperatura_calibracao_c, 24.0, places=2)
        self.assertIsNotNone(ponto_antes.ph_calibrado_em)

    def test_calibracao_sessao_iniciar_cria_sessao_ativa(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio sessao calibracao",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse(
                "reservatorio_calibracao_sessao_iniciar",
                args=[reservatorio.id, PontoMonitoramento.TIPO_ANTES, "tds"],
            )
        )

        self.assertEqual(response.status_code, 302)
        sessao = SessaoCalibracao.objects.get()
        self.assertEqual(sessao.ponto.tipo, PontoMonitoramento.TIPO_ANTES)
        self.assertEqual(sessao.sensor, SessaoCalibracao.SENSOR_TDS)
        self.assertEqual(sessao.status, SessaoCalibracao.STATUS_ATIVA)

    def test_calibracao_sessao_status_retorna_json(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio sessao status",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_antes,
            sensor=SessaoCalibracao.SENSOR_PH,
            iniciada_por=self.usuario,
        )
        AmostraCalibracao.objects.create(
            sessao=sessao,
            temperatura=24.0,
            adc_ph=3051,
            sinais_brutos={"adc_ph": 3051},
        )

        response = self.client.get(
            reverse(
                "reservatorio_calibracao_sessao_status",
                args=[reservatorio.id, ponto_antes.tipo, "ph"],
            )
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ativa"])
        self.assertEqual(data["sensor"], "ph")
        self.assertEqual(data["amostras"], 1)
        self.assertIsNotNone(data["ultima_amostra"])
        self.assertIsNotNone(data["ultima_amostra"]["tensao"])
        self.assertIsNotNone(data["ultima_amostra"]["valor_calibrado"])
        self.assertIsNotNone(data["medias"]["tensao"])

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
                "meta_ph": "6.80",
            },
        )

        self.assertEqual(response.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.nome, "Reservatorio atualizado")
        self.assertEqual(reservatorio.status, Reservatorio.STATUS_BOM)
        self.assertEqual(reservatorio.meta_ppm_tds, 700.0)
        self.assertEqual(reservatorio.meta_ntu_turbidez, 1.9)
        self.assertEqual(reservatorio.meta_celsius_temperatura, 27.5)
        self.assertEqual(reservatorio.meta_ph, 6.8)

    def test_calibracao_temperatura_auto_define_offset_por_ponto(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao temperatura",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_antes,
            sensor=SessaoCalibracao.SENSOR_TEMPERATURA,
            iniciada_por=self.usuario,
        )
        for temperatura in (22.0, 22.02, 21.98, 22.01):
            AmostraCalibracao.objects.create(
                sessao=sessao,
                temperatura=temperatura,
                sinais_brutos={"temperatura_bruta": temperatura},
            )

        response = self.client.post(
            reverse("reservatorio_calibracao_temperatura_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "temperatura_referencia_c": "25.0",
                "temperatura_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(ponto_antes.temperatura_offset_c, 3.0, places=1)
        self.assertAlmostEqual(ponto_antes.temperatura_inclinacao, 1.0, places=3)
        self.assertAlmostEqual(ponto_antes.temperatura_valor_referencia_c, 25.0, places=2)
        self.assertAlmostEqual(ponto_antes.temperatura_bruta_referencia_c, 22.0, places=1)
        self.assertIsNotNone(ponto_antes.temperatura_calibrado_em)

    def test_calibracao_ph_auto_define_ph7_e_inclinacao_por_dois_pontos(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao auto",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "ph_solucao_ponto_1": "6.00",
                "ph_tensao_ponto_1": "2.100",
                "ph_solucao_ponto_2": "8.00",
                "ph_tensao_ponto_2": "1.400",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(ponto_antes.ph_voltagem_referencia_7, 1.75, places=2)
        self.assertAlmostEqual(ponto_antes.ph_inclinacao, 0.35, places=2)
        self.assertAlmostEqual(
            ponto_antes.ph_temperatura_calibracao_c,
            PontoMonitoramento.PH_TEMPERATURA_CALIBRACAO_PADRAO,
            places=2,
        )
        self.assertIsNotNone(ponto_antes.ph_calibrado_em)

    def test_calibracao_ph_auto_nao_altera_com_campos_incompletos(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao auto sem leitura",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        voltagem_original = ponto_antes.ph_voltagem_referencia_7
        inclinacao_original = ponto_antes.ph_inclinacao

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "ph_solucao_ponto_1": "7.00",
                "ph_tensao_ponto_1": "",
                "ph_solucao_ponto_2": "4.00",
                "ph_tensao_ponto_2": "2.100",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertEqual(ponto_antes.ph_voltagem_referencia_7, voltagem_original)
        self.assertEqual(ponto_antes.ph_inclinacao, inclinacao_original)

    def test_calibracao_ph_auto_exige_duas_solucoes_diferentes(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao auto ph conhecido",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "ph_solucao_ponto_1": "7.00",
                "ph_tensao_ponto_1": "2.390",
                "ph_solucao_ponto_2": "7.00",
                "ph_tensao_ponto_2": "2.100",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(
            ponto_antes.ph_voltagem_referencia_7,
            PontoMonitoramento.PH_VOLTAGEM_REFERENCIA_7_PADRAO,
            places=2,
        )

    def test_calibracao_sensor_ph_exibe_formulario_papel_e_caneta(self):
        self._logar()
        reservatorio = Reservatorio.objects.create(
            usuario=self.usuario,
            nome="Reservatorio calibracao ph manual",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(
            reverse(
                "reservatorio_calibracao_sensor",
                args=[reservatorio.id, PontoMonitoramento.TIPO_ANTES, "ph"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "papel e caneta")
        self.assertContains(response, "Tensao da solucao 1 (V)")
        self.assertContains(response, "Tensao da solucao 2 (V)")

    def test_calibracao_tds_auto_define_offset_e_inclinacao_por_ponto(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao tds auto",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_antes,
            sensor=SessaoCalibracao.SENSOR_TDS,
            iniciada_por=self.usuario,
        )

        for adc in (1860, 1861, 1862, 1861):
            AmostraCalibracao.objects.create(
                sessao=sessao,
                temperatura=25.0,
                adc_tds=adc,
                sinais_brutos={"adc_tds": adc},
            )

        response = self.client.post(
            reverse("reservatorio_calibracao_tds_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "tds_alvo_ppm": "40.0",
                "tds_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(ponto_antes.tds_offset_ppm, -540.20, places=2)
        self.assertAlmostEqual(ponto_antes.tds_inclinacao, 1.0, places=3)
        self.assertEqual(ponto_antes.tds_adc_calibracao, 1861)
        self.assertIsNotNone(ponto_antes.tds_calibrado_em)

    def test_calibracao_turbidez_auto_define_offset_e_inclinacao_por_ponto(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao turbidez auto",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_antes,
            sensor=SessaoCalibracao.SENSOR_TURBIDEZ,
            iniciada_por=self.usuario,
        )

        for adc in (979, 980, 981, 980):
            AmostraCalibracao.objects.create(
                sessao=sessao,
                adc_turb=adc,
                sinais_brutos={"adc_turb": adc},
            )

        response = self.client.post(
            reverse("reservatorio_calibracao_turbidez_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "turbidez_alvo_ntu": "0.4",
                "turbidez_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(ponto_antes.turbidez_offset_ntu, -0.39, places=2)
        self.assertAlmostEqual(ponto_antes.turbidez_inclinacao, 1.0, places=3)
        self.assertEqual(ponto_antes.turbidez_adc_calibracao, 980)
        self.assertIsNotNone(ponto_antes.turbidez_calibrado_em)

    def test_calibracao_tds_auto_nao_altera_sem_adc_completo(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao tds incompleta",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        offset_tds_original = ponto_antes.tds_offset_ppm

        ponto_antes.registrar_leitura(
            temperatura=25.0,
            tds=999.0,
            turbidez=9.0,
            ph=7.0,
            sinais_brutos={"adc_turb": 980},
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse("reservatorio_calibracao_tds_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "tds_alvo_ppm": "40.0",
                "tds_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertEqual(ponto_antes.tds_offset_ppm, offset_tds_original)
        self.assertIsNone(ponto_antes.tds_calibrado_em)

    def test_calibracao_turbidez_auto_nao_altera_sem_adc(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao turbidez incompleta",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        offset_turbidez_original = ponto_antes.turbidez_offset_ntu

        ponto_antes.registrar_leitura(
            temperatura=25.0,
            tds=999.0,
            turbidez=9.0,
            ph=7.0,
            sinais_brutos={"adc_tds": 1861},
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse("reservatorio_calibracao_turbidez_auto", args=[reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_ANTES,
                "turbidez_alvo_ntu": "0.4",
                "turbidez_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertEqual(ponto_antes.turbidez_offset_ntu, offset_turbidez_original)
        self.assertIsNone(ponto_antes.turbidez_calibrado_em)

    def test_detalhe_mostra_alerta_calibracao_ph_vencida_e_ok(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao alerta",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        ponto_antes.ph_calibrado_em = timezone.now() - timedelta(days=20)
        ponto_antes.save(update_fields=["ph_calibrado_em", "updated_at"])
        ponto_depois.ph_calibrado_em = timezone.now() - timedelta(days=3)
        ponto_depois.save(update_fields=["ph_calibrado_em", "updated_at"])

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["ph_calibracao_antes"]["vencida"])
        self.assertEqual(response.context["ph_calibracao_antes"]["dias"], 20)
        self.assertFalse(response.context["ph_calibracao_depois"]["vencida"])
        self.assertEqual(response.context["ph_calibracao_depois"]["dias"], 3)
        self.assertIsNone(response.context["ph_calibracao_antes"]["ultima_tensao"])
        self.assertIsNone(response.context["ph_calibracao_depois"]["ultima_tensao"])

    def test_detalhe_expoe_ultima_voltagem_ph_por_ponto(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio voltagem ph",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        ponto_antes.registrar_leitura(
            temperatura=24.0,
            tds=200.0,
            turbidez=0.6,
            ph=6.8,
            sinais_brutos={"adc_ph": 3051},
            status_leitura=Reservatorio.STATUS_BOM,
        )
        ponto_depois.registrar_leitura(
            temperatura=24.0,
            tds=200.0,
            turbidez=0.6,
            ph=7.0,
            sinais_brutos={"ph_tensao": 2.410},
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.context["ph_calibracao_antes"]["ultima_tensao"], 2.46, places=2)
        self.assertAlmostEqual(response.context["ph_calibracao_depois"]["ultima_tensao"], 2.41, places=2)

    def test_detalhe_expoe_ultima_voltagem_ph_com_formato_legado(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio voltagem ph legado",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)

        ponto_antes.registrar_leitura(
            temperatura=24.0,
            tds=200.0,
            turbidez=0.6,
            ph=6.8,
            sinais_brutos={"raw": {"ph_adc": 3051}},
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.context["ph_calibracao_antes"]["ultima_tensao"], 2.46, places=2)

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

    def test_dashboard_calcula_medias_pre_pos_no_periodo(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio Media",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

        leitura_antes_antiga = ponto_antes.registrar_leitura(
            temperatura=99.0,
            tds=999.0,
            turbidez=9.9,
            ph=5.2,
            status_leitura=Reservatorio.STATUS_PERIGO,
        )
        ponto_antes.registrar_leitura(
            temperatura=21.0,
            tds=210.0,
            turbidez=1.5,
            ph=6.8,
            status_leitura=Reservatorio.STATUS_ATENCAO,
        )
        ponto_depois.registrar_leitura(
            temperatura=18.0,
            tds=120.0,
            turbidez=0.6,
            ph=6.4,
            status_leitura=Reservatorio.STATUS_BOM,
        )

        LeituraQualidade.objects.filter(id=leitura_antes_antiga.id).update(
            data_hora=timezone.now() - timedelta(days=15)
        )

        response = self.client.get(reverse("index"), {"dias": "5"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periodo_selecionado"], "5d")
        self.assertEqual(response.context["periodo_rotulo"], "5 dias")

        cards = response.context["dashboard_cards"]
        card = next(item for item in cards if item["reservatorio"].id == reservatorio.id)

        self.assertAlmostEqual(card["antes"]["temperatura"], 21.0, places=2)
        self.assertAlmostEqual(card["antes"]["tds"], 210.0, places=2)
        self.assertAlmostEqual(card["antes"]["turbidez"], 1.5, places=2)
        self.assertAlmostEqual(card["antes"]["ph"], 6.8, places=2)
        self.assertEqual(card["status_antes"]["temperatura"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_antes"]["tds"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_antes"]["turbidez"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_antes"]["ph"], Reservatorio.STATUS_BOM)

        self.assertAlmostEqual(card["depois"]["temperatura"], 18.0, places=2)
        self.assertAlmostEqual(card["depois"]["tds"], 120.0, places=2)
        self.assertAlmostEqual(card["depois"]["turbidez"], 0.6, places=2)
        self.assertAlmostEqual(card["depois"]["ph"], 6.4, places=2)
        self.assertEqual(card["status_depois"]["temperatura"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_depois"]["tds"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_depois"]["turbidez"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_depois"]["ph"], Reservatorio.STATUS_BOM)

    def test_dashboard_aceita_periodos_em_horas_e_minutos(self):
        self._logar()
        response_hora = self.client.get(reverse("index"), {"dias": "1h"})
        self.assertEqual(response_hora.status_code, 200)
        self.assertEqual(response_hora.context["periodo_selecionado"], "1h")
        self.assertEqual(response_hora.context["periodo_rotulo"], "1 hora")

        response_min = self.client.get(reverse("index"), {"dias": "15m"})
        self.assertEqual(response_min.status_code, 200)
        self.assertEqual(response_min.context["periodo_selecionado"], "15m")
        self.assertEqual(response_min.context["periodo_rotulo"], "15 min")


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
        self.assertEqual(primeiro.faixa_ppm_tds_min, Reservatorio.FAIXA_PADRAO_PPM_TDS_MIN)
        self.assertEqual(primeiro.faixa_ppm_tds_max, Reservatorio.FAIXA_PADRAO_PPM_TDS_MAX)
        self.assertEqual(
            primeiro.faixa_ntu_turbidez_min,
            Reservatorio.FAIXA_PADRAO_NTU_TURBIDEZ_MIN,
        )
        self.assertEqual(
            primeiro.faixa_ntu_turbidez_max,
            Reservatorio.FAIXA_PADRAO_NTU_TURBIDEZ_MAX,
        )
        self.assertEqual(
            primeiro.faixa_celsius_temperatura_min,
            Reservatorio.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN,
        )
        self.assertEqual(
            primeiro.faixa_celsius_temperatura_max,
            Reservatorio.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX,
        )
        self.assertEqual(primeiro.faixa_ph_min, Reservatorio.FAIXA_PADRAO_PH_MIN)
        self.assertEqual(primeiro.faixa_ph_max, Reservatorio.FAIXA_PADRAO_PH_MAX)
        self.assertEqual(primeiro.meta_ppm_tds, Reservatorio.META_PADRAO_PPM_TDS)
        self.assertEqual(primeiro.meta_ntu_turbidez, Reservatorio.META_PADRAO_NTU_TURBIDEZ)
        self.assertEqual(
            primeiro.meta_celsius_temperatura,
            Reservatorio.META_PADRAO_CELSIUS_TEMPERATURA,
        )
        self.assertEqual(primeiro.meta_ph, Reservatorio.META_PADRAO_PH)
        ponto_antes = primeiro.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        self.assertEqual(
            ponto_antes.ph_voltagem_referencia_7,
            PontoMonitoramento.PH_VOLTAGEM_REFERENCIA_7_PADRAO,
        )
        self.assertEqual(
            ponto_antes.ph_inclinacao,
            PontoMonitoramento.PH_INCLINACAO_PADRAO,
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
            meta_ph=6.9,
        )

        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.meta_ppm_tds, 450.5)
        self.assertEqual(reservatorio.meta_ntu_turbidez, 1.2)
        self.assertEqual(reservatorio.meta_celsius_temperatura, 24.0)
        self.assertEqual(reservatorio.meta_ph, 6.9)

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
        self.sync_url = reverse("esp32_sync")
        self.command_url = reverse("esp32_calibracao_comando")
        self.sample_url = reverse("esp32_calibracao_amostra")

    def _post_json(self, payload, token="token-teste-esp32"):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_TOKEN=token,
        )

    def _post_json_calibracao(self, payload, token="token-teste-esp32"):
        return self.client.post(
            self.sample_url,
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

    def test_esp32_sync_retorna_proxima_janela_de_leitura(self):
        response = self.client.get(
            self.sync_url,
            HTTP_X_API_TOKEN="token-teste-esp32",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["intervalo_ms"], 60000)
        self.assertGreater(data["server_epoch_ms"], 0)
        self.assertGreater(data["proxima_leitura_epoch_ms"], data["server_epoch_ms"])
        self.assertGreater(data["aguardar_ms"], 0)
        self.assertLessEqual(data["aguardar_ms"], 60000)
        self.assertEqual(
            data["proxima_leitura_epoch_ms"] - data["server_epoch_ms"],
            data["aguardar_ms"],
        )

    def test_esp32_sync_retorna_401_sem_token_valido(self):
        response = self.client.get(
            self.sync_url,
            HTTP_X_API_TOKEN="token-invalido",
        )

        self.assertEqual(response.status_code, 401)

    def test_esp32_calibracao_comando_retorna_calibracao_quando_sessao_ativa(self):
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_depois,
            sensor=SessaoCalibracao.SENSOR_TDS,
        )

        response = self.client.get(
            self.command_url,
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
            },
            HTTP_X_API_TOKEN="token-teste-esp32",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["modo"], "calibracao")
        self.assertEqual(data["sensor"], "tds")
        self.assertEqual(data["sessao_id"], sessao.id)

    def test_esp32_calibracao_amostra_registra_amostra_em_sessao_ativa(self):
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_depois,
            sensor=SessaoCalibracao.SENSOR_PH,
        )

        response = self._post_json_calibracao(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "sensor": "ph",
                "temperatura": 24.5,
                "raw": {
                    "adc_ph": 3051,
                    "firmware_ts_ms": 12000,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        amostra = AmostraCalibracao.objects.get(sessao=sessao)
        self.assertEqual(amostra.adc_ph, 3051)
        self.assertAlmostEqual(amostra.temperatura, 24.5, places=2)

    def test_calibracao_tds_auto_usa_mediana_da_sessao_ativa(self):
        self.client.force_login(self.usuario)
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        sessao = SessaoCalibracao.iniciar(
            ponto=ponto_depois,
            sensor=SessaoCalibracao.SENSOR_TDS,
            iniciada_por=self.usuario,
        )
        AmostraCalibracao.objects.create(
            sessao=sessao,
            temperatura=25.0,
            adc_tds=1861,
            sinais_brutos={"adc_tds": 1861},
        )
        AmostraCalibracao.objects.create(
            sessao=sessao,
            temperatura=25.0,
            adc_tds=1861,
            sinais_brutos={"adc_tds": 1861},
        )

        response = self.client.post(
            reverse("reservatorio_calibracao_tds_auto", args=[self.reservatorio.id]),
            {
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "tds_alvo_ppm": "40.0",
                "tds_inclinacao": "1.000",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_depois.refresh_from_db()
        self.assertAlmostEqual(ponto_depois.tds_offset_ppm, -540.20, places=2)

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
        self.assertEqual(leitura.sinais_brutos, {"temperatura_bruta": 28.75})

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
            meta_ph=7.0,
        )

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "tds": 320.0,
                "turbidez": 0.5,
                "ph": 7.0,
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertEqual(leitura.status_leitura, Reservatorio.STATUS_ATENCAO)
        self.assertAlmostEqual(leitura.ph, 7.0, places=2)

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
        self.assertIsNone(leitura.ph)
        self.assertEqual(
            leitura.sinais_brutos,
            {
                "adc_tds": 1861,
                "adc_turb": 980,
                "firmware_ts_ms": 93000,
                "temperatura_bruta": 25.0,
            },
        )

    def test_esp32_leitura_preserva_horario_de_coleta_quando_fila_atrasar(self):
        antes_post = timezone.now()

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "device_id": "esp_depois_tratamento",
                "temperatura": 25.0,
                "raw": {
                    "adc_tds": 1861,
                    "adc_turb": 980,
                    "firmware_ts_ms": 1000,
                    "firmware_now_ms": 61000,
                },
            }
        )

        depois_post = timezone.now()

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertGreaterEqual(leitura.data_hora, antes_post - timedelta(seconds=60))
        self.assertLessEqual(leitura.data_hora, depois_post - timedelta(seconds=60))
        self.assertEqual(leitura.sinais_brutos["device_id"], "esp_depois_tratamento")
        self.assertEqual(leitura.sinais_brutos["firmware_now_ms"], 61000)

    def test_esp32_leitura_aplica_calibracao_de_temperatura_ao_tds(self):
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        ponto_depois.atualizar_calibracao_temperatura(
            temperatura_bruta_c=20.0,
            temperatura_referencia_c=25.0,
            temperatura_inclinacao=1.0,
        )

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 20.0,
                "raw": {
                    "adc_tds": 1861,
                    "adc_turb": 980,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.temperatura, 25.0, places=2)
        self.assertAlmostEqual(leitura.tds, 580.20, places=2)

    def test_esp32_leitura_salva_ph_quando_enviado(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.5,
                "tds": 280.0,
                "turbidez": 0.6,
                "ph": 6.7,
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.ph, 6.7, places=2)

    def test_esp32_leitura_calcula_ph_por_adc_raw(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "tds": 300.0,
                "turbidez": 0.5,
                "raw": {
                    "adc_ph": 3051,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.ph, 6.70, places=2)

    def test_esp32_leitura_prioriza_ph_raw_quando_recebe_ph_e_adc(self):
        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "tds": 300.0,
                "turbidez": 0.5,
                "ph": 1.2,
                "raw": {
                    "adc_ph": 3051,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.ph, 6.70, places=2)

    def test_esp32_leitura_usa_calibracao_ph_do_ponto(self):
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        ponto_depois.atualizar_calibracao_ph(
            ph_voltagem_referencia_7=2.50,
            ph_inclinacao=0.20,
        )

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "tds": 300.0,
                "turbidez": 0.5,
                "raw": {
                    "adc_ph": 3051,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.ph, 7.21, places=2)

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

    def test_esp32_leitura_aplica_offset_calibracao_agua(self):
        ponto_depois = self.reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        ponto_depois.atualizar_calibracao_agua_limpa(
            tds_base_ppm=580.20,
            turbidez_base_ntu=0.79,
            tds_alvo_ppm=40.0,
            turbidez_alvo_ntu=0.4,
            tds_adc=1861,
            turbidez_adc=980,
        )

        response = self._post_json(
            {
                "reservatorio_id": self.reservatorio.id,
                "ponto_tipo": PontoMonitoramento.TIPO_DEPOIS,
                "temperatura": 25.0,
                "raw": {
                    "adc_tds": 1861,
                    "adc_turb": 980,
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        leitura = LeituraQualidade.objects.latest("id")
        self.assertAlmostEqual(leitura.tds, 40.0, places=1)
        self.assertAlmostEqual(leitura.turbidez, 0.4, places=2)
