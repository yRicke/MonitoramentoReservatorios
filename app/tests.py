import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
        self.assertIsNone(ponto_antes.ph_calibrado_em)
        self.assertEqual(
            ponto_depois.ph_voltagem_referencia_7,
            PontoMonitoramento.PH_VOLTAGEM_REFERENCIA_7_PADRAO,
        )
        self.assertEqual(
            ponto_depois.ph_inclinacao,
            PontoMonitoramento.PH_INCLINACAO_PADRAO,
        )
        self.assertIsNone(ponto_depois.ph_calibrado_em)

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

    def test_calibracao_ph_view_atualiza_parametros_por_ponto(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao",
            status=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_atualizar", args=[reservatorio.id]),
            {
                "ph7_antes": "2.420",
                "inclinacao_antes": "0.225",
                "ph7_depois": "2.390",
                "inclinacao_depois": "0.230",
            },
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        self.assertAlmostEqual(ponto_antes.ph_voltagem_referencia_7, 2.42, places=3)
        self.assertAlmostEqual(ponto_antes.ph_inclinacao, 0.225, places=3)
        self.assertIsNotNone(ponto_antes.ph_calibrado_em)
        self.assertAlmostEqual(ponto_depois.ph_voltagem_referencia_7, 2.39, places=3)
        self.assertAlmostEqual(ponto_depois.ph_inclinacao, 0.23, places=3)
        self.assertIsNotNone(ponto_depois.ph_calibrado_em)

        detalhe = self.client.get(reverse("reservatorio_detalhe", args=[reservatorio.id]))
        self.assertContains(detalhe, 'id="ph7_antes"')
        self.assertContains(detalhe, 'value="2.42"')
        self.assertContains(detalhe, 'id="inclinacao_antes"')
        self.assertContains(detalhe, 'value="0.225"')

    def test_calibracao_ph_auto_define_ph7_pela_ultima_tensao_e_mantem_inclinacao(self):
        self._logar()
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Reservatorio calibracao auto",
            status=Reservatorio.STATUS_BOM,
        )
        ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
        ponto_antes.atualizar_calibracao_ph(
            ph_voltagem_referencia_7=2.30,
            ph_inclinacao=0.215,
        )

        ponto_antes.registrar_leitura(
            temperatura=24.0,
            tds=200.0,
            turbidez=0.6,
            ph=6.8,
            sinais_brutos={"adc_ph": 3051},
            status_leitura=Reservatorio.STATUS_BOM,
        )

        response = self.client.post(
            reverse("reservatorio_calibracao_ph_auto", args=[reservatorio.id]),
            {"ponto_tipo": PontoMonitoramento.TIPO_ANTES},
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertAlmostEqual(ponto_antes.ph_voltagem_referencia_7, 2.46, places=2)
        self.assertAlmostEqual(ponto_antes.ph_inclinacao, 0.215, places=3)
        self.assertIsNotNone(ponto_antes.ph_calibrado_em)

    def test_calibracao_ph_auto_nao_altera_quando_nao_tem_tensao(self):
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
            {"ponto_tipo": PontoMonitoramento.TIPO_ANTES},
        )

        self.assertEqual(response.status_code, 302)
        ponto_antes.refresh_from_db()
        self.assertEqual(ponto_antes.ph_voltagem_referencia_7, voltagem_original)
        self.assertEqual(ponto_antes.ph_inclinacao, inclinacao_original)

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
        self.assertEqual(response.context["periodo_dias"], 5)

        cards = response.context["dashboard_cards"]
        card = next(item for item in cards if item["reservatorio"].id == reservatorio.id)

        self.assertAlmostEqual(card["antes"]["temperatura"], 21.0, places=2)
        self.assertAlmostEqual(card["antes"]["tds"], 210.0, places=2)
        self.assertAlmostEqual(card["antes"]["turbidez"], 1.5, places=2)
        self.assertAlmostEqual(card["antes"]["ph"], 6.8, places=2)
        self.assertEqual(card["status_antes"]["temperatura"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_antes"]["tds"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_antes"]["turbidez"], Reservatorio.STATUS_ATENCAO)
        self.assertEqual(card["status_antes"]["ph"], Reservatorio.STATUS_BOM)

        self.assertAlmostEqual(card["depois"]["temperatura"], 18.0, places=2)
        self.assertAlmostEqual(card["depois"]["tds"], 120.0, places=2)
        self.assertAlmostEqual(card["depois"]["turbidez"], 0.6, places=2)
        self.assertAlmostEqual(card["depois"]["ph"], 6.4, places=2)
        self.assertEqual(card["status_depois"]["temperatura"], Reservatorio.STATUS_ATENCAO)
        self.assertEqual(card["status_depois"]["tds"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_depois"]["turbidez"], Reservatorio.STATUS_BOM)
        self.assertEqual(card["status_depois"]["ph"], Reservatorio.STATUS_ATENCAO)


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
            },
        )

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
