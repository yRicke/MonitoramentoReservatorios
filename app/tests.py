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
            {"nome": "Reservatorio atualizado", "status": Reservatorio.STATUS_PERIGO},
        )

        self.assertEqual(response.status_code, 302)
        reservatorio.refresh_from_db()
        self.assertEqual(reservatorio.nome, "Reservatorio atualizado")
        self.assertEqual(reservatorio.status, Reservatorio.STATUS_PERIGO)

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
        Reservatorio.objects.create(usuario=self.usuario, nome="R1", status=Reservatorio.STATUS_BOM)
        Reservatorio.objects.create(usuario=self.usuario, nome="R2", status=Reservatorio.STATUS_PERIGO)

        response = self.client.get(reverse("index"), {"busca": "perigo"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R2")
        self.assertNotContains(response, "R1")


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

        filtrados = Reservatorio.listar("perigo")

        self.assertEqual(filtrados.count(), 1)
        self.assertEqual(filtrados.first().nome, "Leste")

    def test_update_atualiza_nome_e_status(self):
        reservatorio = Reservatorio.criar_reservatorio(
            usuario=self.usuario,
            nome="Velho",
            status=Reservatorio.STATUS_BOM,
        )

        atualizado = reservatorio.atualizar_reservatorio(
            nome="Novo",
            status=Reservatorio.STATUS_ATENCAO,
        )

        self.assertEqual(atualizado.nome, "Novo")
        self.assertEqual(atualizado.status, Reservatorio.STATUS_ATENCAO)

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
        self.assertAlmostEqual(leitura.tds, 920.5, places=2)
        self.assertAlmostEqual(leitura.temperatura, 28.75, places=2)
        self.assertAlmostEqual(leitura.turbidez, 2.8, places=2)

        self.reservatorio.refresh_from_db()
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_PERIGO)

    def test_status_do_reservatorio_considera_pior_entre_os_dois_pontos(self):
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
        self.assertEqual(self.reservatorio.status, Reservatorio.STATUS_PERIGO)
