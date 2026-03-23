from django.conf import settings
from django.db import models
from django.db.models import Q


class Reservatorio(models.Model):
    STATUS_BOM = "bom"
    STATUS_ATENCAO = "atencao"
    STATUS_PERIGO = "perigo"
    STATUS_CHOICES = (
        (STATUS_BOM, "Bom"),
        (STATUS_ATENCAO, "Atencao"),
        (STATUS_PERIGO, "Perigo"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservatorios",
    )
    nome = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BOM)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @classmethod
    def listar(cls, busca="", usuario=None):
        queryset = cls.objects.all()
        if usuario is not None:
            queryset = queryset.filter(usuario=usuario)

        termo = (busca or "").strip()
        if not termo:
            return queryset

        return queryset.filter(Q(nome__icontains=termo) | Q(status__icontains=termo))

    @classmethod
    def obter_por_id(cls, reservatorio_id, usuario=None):
        reservatorio_id = cls._normalizar_id(reservatorio_id)
        if reservatorio_id is None:
            return None

        queryset = cls.objects.filter(id=reservatorio_id)
        if usuario is not None:
            queryset = queryset.filter(usuario=usuario)
        return queryset.first()

    @classmethod
    def criar_reservatorio(cls, *, usuario, nome=None, status=None):
        if usuario is None:
            raise ValueError("Usuario obrigatorio para criar reservatorio.")

        nome_final = cls._normalizar_nome(nome) if nome is not None else cls._proximo_nome()
        status_final = cls._normalizar_status(status)
        reservatorio = cls.objects.create(nome=nome_final, status=status_final, usuario=usuario)
        reservatorio.garantir_pontos_monitoramento()
        return reservatorio

    def atualizar_reservatorio(self, *, nome=None, status=None):
        if status is not None:
            raise ValueError("Status do reservatorio e automatico e nao pode ser editado manualmente.")

        if nome is None:
            return self

        self.nome = self._normalizar_nome(nome)
        self.save(update_fields=["nome", "updated_at"])
        return self

    def excluir_reservatorio(self):
        self.delete()
        return True

    def garantir_pontos_monitoramento(self):
        for tipo in PontoMonitoramento.TIPOS:
            PontoMonitoramento.objects.get_or_create(
                reservatorio=self,
                tipo=tipo,
            )

    def obter_ponto_monitoramento(self, tipo):
        tipo_normalizado = PontoMonitoramento.normalizar_tipo(tipo)
        return self.pontos_monitoramento.filter(tipo=tipo_normalizado).first()

    def sincronizar_status_pelo_ponto_depois(self):
        ponto_depois = self.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)
        status_final = self.STATUS_BOM
        if ponto_depois is not None and ponto_depois.status_atual:
            status_final = ponto_depois.status_atual

        if self.status != status_final:
            self.status = status_final
            self.save(update_fields=["status", "updated_at"])

        return self

    @classmethod
    def _proximo_nome(cls):
        indice = 1
        while cls.objects.filter(nome=f"Reservatorio {indice}").exists():
            indice += 1
        return f"Reservatorio {indice}"

    @classmethod
    def _normalizar_status(cls, status):
        status_final = (status or cls.STATUS_BOM).strip().lower()
        validos = {opcao[0] for opcao in cls.STATUS_CHOICES}
        if status_final not in validos:
            raise ValueError("Status invalido para reservatorio.")
        return status_final

    @staticmethod
    def _normalizar_nome(nome):
        if not isinstance(nome, str):
            raise ValueError("Nome invalido para reservatorio.")

        nome_final = nome.strip()
        if not nome_final:
            raise ValueError("Nome do reservatorio e obrigatorio.")

        return nome_final

    @staticmethod
    def _normalizar_id(reservatorio_id):
        if isinstance(reservatorio_id, int):
            return reservatorio_id if reservatorio_id > 0 else None

        if isinstance(reservatorio_id, str) and reservatorio_id.isdigit():
            return int(reservatorio_id)

        return None


class PontoMonitoramento(models.Model):
    TIPO_ANTES = "antes_tratamento"
    TIPO_DEPOIS = "depois_tratamento"
    TIPOS = (
        TIPO_ANTES,
        TIPO_DEPOIS,
    )
    TIPO_CHOICES = (
        (TIPO_ANTES, "Antes do tratamento"),
        (TIPO_DEPOIS, "Depois do tratamento"),
    )

    reservatorio = models.ForeignKey(
        Reservatorio,
        on_delete=models.CASCADE,
        related_name="pontos_monitoramento",
    )
    tipo = models.CharField(max_length=32, choices=TIPO_CHOICES)
    status_atual = models.CharField(
        max_length=20,
        choices=Reservatorio.STATUS_CHOICES,
        default=Reservatorio.STATUS_BOM,
    )
    confianca_status = models.FloatField(null=True, blank=True)
    modelo_versao = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["reservatorio_id", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["reservatorio", "tipo"],
                name="uq_ponto_monitoramento_reservatorio_tipo",
            ),
        ]

    def __str__(self):
        return f"{self.reservatorio.nome} - {self.get_tipo_display()}"

    @classmethod
    def normalizar_tipo(cls, tipo):
        if not isinstance(tipo, str):
            raise ValueError("ponto_tipo invalido")

        tipo_normalizado = tipo.strip().lower()
        validos = {item[0] for item in cls.TIPO_CHOICES}
        if tipo_normalizado not in validos:
            raise ValueError("ponto_tipo invalido")
        return tipo_normalizado

    def atualizar_status(self, *, status, confianca=None, modelo_versao=""):
        self.status_atual = status
        self.confianca_status = confianca
        self.modelo_versao = (modelo_versao or "").strip()
        self.save(update_fields=["status_atual", "confianca_status", "modelo_versao", "updated_at"])
        return self

    def registrar_leitura(
        self,
        *,
        temperatura,
        tds,
        turbidez,
        status_leitura,
        status_origem="regras",
        confianca=None,
        modelo_versao="",
    ):
        status_final = Reservatorio._normalizar_status(status_leitura)
        leitura = LeituraQualidade.objects.create(
            ponto=self,
            temperatura=temperatura,
            tds=tds,
            turbidez=turbidez,
            status_leitura=status_final,
            status_origem=status_origem,
            confianca=confianca,
            modelo_versao=(modelo_versao or "").strip(),
        )
        self.atualizar_status(
            status=status_final,
            confianca=confianca,
            modelo_versao=modelo_versao,
        )
        return leitura


class LeituraQualidade(models.Model):
    ORIGEM_REGRAS = "regras"
    ORIGEM_TINYML = "tinyml"
    ORIGEM_CHOICES = (
        (ORIGEM_REGRAS, "Regras"),
        (ORIGEM_TINYML, "TinyML"),
    )

    ponto = models.ForeignKey(
        PontoMonitoramento,
        on_delete=models.CASCADE,
        related_name="leituras_qualidade",
    )
    tds = models.FloatField()
    temperatura = models.FloatField()
    turbidez = models.FloatField()
    status_leitura = models.CharField(
        max_length=20,
        choices=Reservatorio.STATUS_CHOICES,
        default=Reservatorio.STATUS_BOM,
    )
    status_origem = models.CharField(
        max_length=16,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_REGRAS,
    )
    confianca = models.FloatField(null=True, blank=True)
    modelo_versao = models.CharField(max_length=64, blank=True, default="")
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_hora"]
        indexes = [
            models.Index(fields=["ponto", "data_hora"]),
        ]
