from datetime import timedelta
import math
import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from app.services.amostragem_esp32 import construir_plano_amostragem_calibracao
from app.services.regras import calcular_status_reservatorio


def gerar_token_integracao_esp32():
    # Mantido por compatibilidade com migrações históricas que ainda referenciam esta função.
    return secrets.token_urlsafe(32)


class Reservatorio(models.Model):
    STATUS_BOM = "bom"
    STATUS_ATENCAO = "atencao"
    STATUS_PERIGO = "perigo"
    FAIXA_PADRAO_PPM_TDS_MIN = 0.0
    FAIXA_PADRAO_PPM_TDS_MAX = 500.0
    FAIXA_PADRAO_NTU_TURBIDEZ_MIN = 0.0
    FAIXA_PADRAO_NTU_TURBIDEZ_MAX = 5.0
    FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN = 5.0
    FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX = 30.0
    FAIXA_PADRAO_PH_MIN = 6.0
    FAIXA_PADRAO_PH_MAX = 9.5
    META_PADRAO_PPM_TDS = 600.0
    META_PADRAO_NTU_TURBIDEZ = 1.5
    META_PADRAO_CELSIUS_TEMPERATURA = 25.0
    META_PADRAO_PH = 7.0
    ESP32_INTERVALO_ENVIO_NORMAL_PADRAO_S = 60
    ESP32_INTERVALO_ENVIO_CALIBRACAO_PADRAO_S = 5
    STATUS_CHOICES = (
        (STATUS_BOM, "Bom"),
        (STATUS_ATENCAO, "Atenção"),
        (STATUS_PERIGO, "Perigo"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservatorios",
    )
    nome = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BOM)
    faixa_ppm_tds_min = models.FloatField(default=FAIXA_PADRAO_PPM_TDS_MIN)
    faixa_ppm_tds_max = models.FloatField(default=FAIXA_PADRAO_PPM_TDS_MAX)
    faixa_ntu_turbidez_min = models.FloatField(default=FAIXA_PADRAO_NTU_TURBIDEZ_MIN)
    faixa_ntu_turbidez_max = models.FloatField(default=FAIXA_PADRAO_NTU_TURBIDEZ_MAX)
    faixa_celsius_temperatura_min = models.FloatField(default=FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN)
    faixa_celsius_temperatura_max = models.FloatField(default=FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX)
    faixa_ph_min = models.FloatField(default=FAIXA_PADRAO_PH_MIN)
    faixa_ph_max = models.FloatField(default=FAIXA_PADRAO_PH_MAX)
    meta_ppm_tds = models.FloatField(default=META_PADRAO_PPM_TDS)
    meta_ntu_turbidez = models.FloatField(default=META_PADRAO_NTU_TURBIDEZ)
    meta_celsius_temperatura = models.FloatField(default=META_PADRAO_CELSIUS_TEMPERATURA)
    meta_ph = models.FloatField(default=META_PADRAO_PH)
    esp32_intervalo_envio_normal_s = models.PositiveIntegerField(
        default=ESP32_INTERVALO_ENVIO_NORMAL_PADRAO_S,
    )
    esp32_intervalo_envio_calibracao_s = models.PositiveIntegerField(
        default=ESP32_INTERVALO_ENVIO_CALIBRACAO_PADRAO_S,
    )
    alerta_sonoro_silenciado = models.BooleanField(default=False)
    alerta_sonoro_silenciado_permanente = models.BooleanField(default=False)
    alerta_sonoro_teste_ate = models.DateTimeField(null=True, blank=True)
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
    def criar_reservatorio(
        cls,
        *,
        usuario,
        nome=None,
        status=None,
        meta_ppm_tds=None,
        meta_ntu_turbidez=None,
        meta_celsius_temperatura=None,
        meta_ph=None,
        faixa_ppm_tds_min=None,
        faixa_ppm_tds_max=None,
        faixa_ntu_turbidez_min=None,
        faixa_ntu_turbidez_max=None,
        faixa_celsius_temperatura_min=None,
        faixa_celsius_temperatura_max=None,
        faixa_ph_min=None,
        faixa_ph_max=None,
        esp32_intervalo_envio_normal_s=None,
        esp32_intervalo_envio_calibracao_s=None,
    ):
        if usuario is None:
            raise ValueError("Usuário obrigatório para criar reservatório.")

        nome_final = cls._normalizar_nome(nome) if nome is not None else cls._proximo_nome()
        status_final = cls._normalizar_status(status)

        # Compatibilidade com metas antigas: converte meta -> faixa quando necessario.
        if meta_ppm_tds is not None and faixa_ppm_tds_max is None:
            faixa_ppm_tds_max = meta_ppm_tds
        if meta_ntu_turbidez is not None and faixa_ntu_turbidez_max is None:
            faixa_ntu_turbidez_max = meta_ntu_turbidez
        if meta_celsius_temperatura is not None:
            if faixa_celsius_temperatura_min is None:
                faixa_celsius_temperatura_min = meta_celsius_temperatura
            if faixa_celsius_temperatura_max is None:
                faixa_celsius_temperatura_max = meta_celsius_temperatura
        if meta_ph is not None:
            if faixa_ph_min is None:
                faixa_ph_min = meta_ph
            if faixa_ph_max is None:
                faixa_ph_max = meta_ph

        faixa_ppm_tds_min_final, faixa_ppm_tds_max_final = cls._normalizar_faixa(
            faixa_ppm_tds_min,
            faixa_ppm_tds_max,
            campo="faixa_ppm_tds",
            padrao_min=cls.FAIXA_PADRAO_PPM_TDS_MIN,
            padrao_max=cls.FAIXA_PADRAO_PPM_TDS_MAX,
            permitir_zero=True,
        )
        faixa_ntu_turbidez_min_final, faixa_ntu_turbidez_max_final = cls._normalizar_faixa(
            faixa_ntu_turbidez_min,
            faixa_ntu_turbidez_max,
            campo="faixa_ntu_turbidez",
            padrao_min=cls.FAIXA_PADRAO_NTU_TURBIDEZ_MIN,
            padrao_max=cls.FAIXA_PADRAO_NTU_TURBIDEZ_MAX,
            permitir_zero=True,
        )
        (
            faixa_celsius_temperatura_min_final,
            faixa_celsius_temperatura_max_final,
        ) = cls._normalizar_faixa(
            faixa_celsius_temperatura_min,
            faixa_celsius_temperatura_max,
            campo="faixa_celsius_temperatura",
            padrao_min=cls.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN,
            padrao_max=cls.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX,
            permitir_zero=False,
        )
        faixa_ph_min_final, faixa_ph_max_final = cls._normalizar_faixa_ph(
            faixa_ph_min,
            faixa_ph_max,
            padrao_min=cls.FAIXA_PADRAO_PH_MIN,
            padrao_max=cls.FAIXA_PADRAO_PH_MAX,
        )
        meta_ppm_tds_final = cls._normalizar_meta(
            meta_ppm_tds,
            campo="meta_ppm_tds",
            padrao=cls.META_PADRAO_PPM_TDS,
        )
        meta_ntu_turbidez_final = cls._normalizar_meta(
            meta_ntu_turbidez,
            campo="meta_ntu_turbidez",
            padrao=cls.META_PADRAO_NTU_TURBIDEZ,
        )
        meta_celsius_temperatura_final = cls._normalizar_meta(
            meta_celsius_temperatura,
            campo="meta_celsius_temperatura",
            padrao=cls.META_PADRAO_CELSIUS_TEMPERATURA,
        )
        meta_ph_final = cls._normalizar_meta_ph(meta_ph, padrao=cls.META_PADRAO_PH)

        reservatorio = cls.objects.create(
            nome=nome_final,
            status=status_final,
            usuario=usuario,
            faixa_ppm_tds_min=faixa_ppm_tds_min_final,
            faixa_ppm_tds_max=faixa_ppm_tds_max_final,
            faixa_ntu_turbidez_min=faixa_ntu_turbidez_min_final,
            faixa_ntu_turbidez_max=faixa_ntu_turbidez_max_final,
            faixa_celsius_temperatura_min=faixa_celsius_temperatura_min_final,
            faixa_celsius_temperatura_max=faixa_celsius_temperatura_max_final,
            faixa_ph_min=faixa_ph_min_final,
            faixa_ph_max=faixa_ph_max_final,
            meta_ppm_tds=meta_ppm_tds_final,
            meta_ntu_turbidez=meta_ntu_turbidez_final,
            meta_celsius_temperatura=meta_celsius_temperatura_final,
            meta_ph=meta_ph_final,
            esp32_intervalo_envio_normal_s=cls._normalizar_intervalo_esp32(
                esp32_intervalo_envio_normal_s,
                campo="esp32_intervalo_envio_normal_s",
                padrao=cls.ESP32_INTERVALO_ENVIO_NORMAL_PADRAO_S,
            ),
            esp32_intervalo_envio_calibracao_s=cls._normalizar_intervalo_esp32(
                esp32_intervalo_envio_calibracao_s,
                campo="esp32_intervalo_envio_calibracao_s",
                padrao=cls.ESP32_INTERVALO_ENVIO_CALIBRACAO_PADRAO_S,
            ),
        )
        reservatorio.garantir_pontos_monitoramento()
        return reservatorio

    def atualizar_reservatorio(
        self,
        *,
        nome=None,
        status=None,
        meta_ppm_tds=None,
        meta_ntu_turbidez=None,
        meta_celsius_temperatura=None,
        meta_ph=None,
        faixa_ppm_tds_min=None,
        faixa_ppm_tds_max=None,
        faixa_ntu_turbidez_min=None,
        faixa_ntu_turbidez_max=None,
        faixa_celsius_temperatura_min=None,
        faixa_celsius_temperatura_max=None,
        faixa_ph_min=None,
        faixa_ph_max=None,
        esp32_intervalo_envio_normal_s=None,
        esp32_intervalo_envio_calibracao_s=None,
    ):
        if status is not None:
            raise ValueError("O status do reservatório é automático e não pode ser editado manualmente.")

        campos_para_salvar = []
        if nome is not None:
            self.nome = self._normalizar_nome(nome)
            campos_para_salvar.append("nome")

        # Compatibilidade com metas antigas: converte meta -> faixa quando necessario.
        if meta_ppm_tds is not None and faixa_ppm_tds_max is None:
            faixa_ppm_tds_max = meta_ppm_tds
        if meta_ntu_turbidez is not None and faixa_ntu_turbidez_max is None:
            faixa_ntu_turbidez_max = meta_ntu_turbidez
        if meta_celsius_temperatura is not None:
            if faixa_celsius_temperatura_min is None:
                faixa_celsius_temperatura_min = meta_celsius_temperatura
            if faixa_celsius_temperatura_max is None:
                faixa_celsius_temperatura_max = meta_celsius_temperatura
        if meta_ph is not None:
            if faixa_ph_min is None:
                faixa_ph_min = meta_ph
            if faixa_ph_max is None:
                faixa_ph_max = meta_ph

        if faixa_ppm_tds_min is not None or faixa_ppm_tds_max is not None:
            minimo, maximo = self._normalizar_faixa(
                faixa_ppm_tds_min if faixa_ppm_tds_min is not None else self.faixa_ppm_tds_min,
                faixa_ppm_tds_max if faixa_ppm_tds_max is not None else self.faixa_ppm_tds_max,
                campo="faixa_ppm_tds",
                padrao_min=self.FAIXA_PADRAO_PPM_TDS_MIN,
                padrao_max=self.FAIXA_PADRAO_PPM_TDS_MAX,
                permitir_zero=True,
            )
            self.faixa_ppm_tds_min = minimo
            self.faixa_ppm_tds_max = maximo
            campos_para_salvar.extend(["faixa_ppm_tds_min", "faixa_ppm_tds_max"])

        if faixa_ntu_turbidez_min is not None or faixa_ntu_turbidez_max is not None:
            minimo, maximo = self._normalizar_faixa(
                faixa_ntu_turbidez_min if faixa_ntu_turbidez_min is not None else self.faixa_ntu_turbidez_min,
                faixa_ntu_turbidez_max if faixa_ntu_turbidez_max is not None else self.faixa_ntu_turbidez_max,
                campo="faixa_ntu_turbidez",
                padrao_min=self.FAIXA_PADRAO_NTU_TURBIDEZ_MIN,
                padrao_max=self.FAIXA_PADRAO_NTU_TURBIDEZ_MAX,
                permitir_zero=True,
            )
            self.faixa_ntu_turbidez_min = minimo
            self.faixa_ntu_turbidez_max = maximo
            campos_para_salvar.extend(["faixa_ntu_turbidez_min", "faixa_ntu_turbidez_max"])

        if faixa_celsius_temperatura_min is not None or faixa_celsius_temperatura_max is not None:
            minimo, maximo = self._normalizar_faixa(
                (
                    faixa_celsius_temperatura_min
                    if faixa_celsius_temperatura_min is not None
                    else self.faixa_celsius_temperatura_min
                ),
                (
                    faixa_celsius_temperatura_max
                    if faixa_celsius_temperatura_max is not None
                    else self.faixa_celsius_temperatura_max
                ),
                campo="faixa_celsius_temperatura",
                padrao_min=self.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MIN,
                padrao_max=self.FAIXA_PADRAO_CELSIUS_TEMPERATURA_MAX,
                permitir_zero=False,
            )
            self.faixa_celsius_temperatura_min = minimo
            self.faixa_celsius_temperatura_max = maximo
            campos_para_salvar.extend(
                [
                    "faixa_celsius_temperatura_min",
                    "faixa_celsius_temperatura_max",
                ]
            )

        if faixa_ph_min is not None or faixa_ph_max is not None:
            minimo, maximo = self._normalizar_faixa_ph(
                faixa_ph_min if faixa_ph_min is not None else self.faixa_ph_min,
                faixa_ph_max if faixa_ph_max is not None else self.faixa_ph_max,
                padrao_min=self.FAIXA_PADRAO_PH_MIN,
                padrao_max=self.FAIXA_PADRAO_PH_MAX,
            )
            self.faixa_ph_min = minimo
            self.faixa_ph_max = maximo
            campos_para_salvar.extend(["faixa_ph_min", "faixa_ph_max"])

        if meta_ppm_tds is not None:
            self.meta_ppm_tds = self._normalizar_meta(
                meta_ppm_tds,
                campo="meta_ppm_tds",
                padrao=self.META_PADRAO_PPM_TDS,
            )
            campos_para_salvar.append("meta_ppm_tds")

        if meta_ntu_turbidez is not None:
            self.meta_ntu_turbidez = self._normalizar_meta(
                meta_ntu_turbidez,
                campo="meta_ntu_turbidez",
                padrao=self.META_PADRAO_NTU_TURBIDEZ,
            )
            campos_para_salvar.append("meta_ntu_turbidez")

        if meta_celsius_temperatura is not None:
            self.meta_celsius_temperatura = self._normalizar_meta(
                meta_celsius_temperatura,
                campo="meta_celsius_temperatura",
                padrao=self.META_PADRAO_CELSIUS_TEMPERATURA,
            )
            campos_para_salvar.append("meta_celsius_temperatura")

        if meta_ph is not None:
            self.meta_ph = self._normalizar_meta_ph(
                meta_ph,
                padrao=self.META_PADRAO_PH,
            )
            campos_para_salvar.append("meta_ph")

        if esp32_intervalo_envio_normal_s is not None:
            self.esp32_intervalo_envio_normal_s = self._normalizar_intervalo_esp32(
                esp32_intervalo_envio_normal_s,
                campo="esp32_intervalo_envio_normal_s",
                padrao=self.ESP32_INTERVALO_ENVIO_NORMAL_PADRAO_S,
            )
            campos_para_salvar.append("esp32_intervalo_envio_normal_s")

        if esp32_intervalo_envio_calibracao_s is not None:
            self.esp32_intervalo_envio_calibracao_s = self._normalizar_intervalo_esp32(
                esp32_intervalo_envio_calibracao_s,
                campo="esp32_intervalo_envio_calibracao_s",
                padrao=self.ESP32_INTERVALO_ENVIO_CALIBRACAO_PADRAO_S,
            )
            campos_para_salvar.append("esp32_intervalo_envio_calibracao_s")

        if not campos_para_salvar:
            return self

        campos_unicos = list(dict.fromkeys(campos_para_salvar))
        self.save(update_fields=[*campos_unicos, "updated_at"])
        return self

    def excluir_reservatorio(self):
        self.delete()
        return True

    def resetar_leituras(self):
        total_removido, _ = LeituraQualidade.objects.filter(
            ponto__reservatorio=self,
        ).delete()
        return total_removido

    def garantir_pontos_monitoramento(self):
        possui_ponto = self.pontos_monitoramento.filter(
            tipo__in=PontoMonitoramento.TIPOS_COMPATIVEIS,
        ).exists()
        if possui_ponto:
            return

        PontoMonitoramento.objects.get_or_create(
            reservatorio=self,
            tipo=PontoMonitoramento.TIPO_UNICO,
        )

    def obter_ponto_monitoramento(self, tipo):
        tipo_normalizado = PontoMonitoramento.normalizar_tipo(tipo)
        queryset = self.pontos_monitoramento.all()
        if tipo_normalizado == PontoMonitoramento.TIPO_UNICO:
            for tipo_compativel in PontoMonitoramento.TIPOS_COMPATIVEIS:
                ponto = queryset.filter(tipo=tipo_compativel).first()
                if ponto is not None:
                    return ponto
        return queryset.filter(tipo=tipo_normalizado).first()

    def sincronizar_status_pelo_ponto(self):
        ponto = self.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
        status_final = self.STATUS_BOM
        if ponto is not None and ponto.status_atual:
            status_final = ponto.status_atual

        campos_para_salvar = []
        if self.status != status_final:
            self.status = status_final
            campos_para_salvar.append("status")

        if status_final != self.STATUS_PERIGO and self.alerta_sonoro_silenciado:
            self.alerta_sonoro_silenciado = False
            campos_para_salvar.append("alerta_sonoro_silenciado")

        if campos_para_salvar:
            self.save(update_fields=[*campos_para_salvar, "updated_at"])

        return self

    def sincronizar_status_pelo_ponto_depois(self):
        return self.sincronizar_status_pelo_ponto()

    def silenciar_alerta_sonoro(self):
        if self.alerta_sonoro_silenciado:
            return self
        self.alerta_sonoro_silenciado = True
        self.save(update_fields=["alerta_sonoro_silenciado", "updated_at"])
        return self

    def reativar_alerta_sonoro(self):
        if not self.alerta_sonoro_silenciado:
            return self
        self.alerta_sonoro_silenciado = False
        self.save(update_fields=["alerta_sonoro_silenciado", "updated_at"])
        return self

    def silenciar_alerta_sonoro_permanentemente(self):
        if self.alerta_sonoro_silenciado_permanente and not self.alerta_sonoro_silenciado:
            return self
        self.alerta_sonoro_silenciado_permanente = True
        self.alerta_sonoro_silenciado = False
        self.save(
            update_fields=[
                "alerta_sonoro_silenciado_permanente",
                "alerta_sonoro_silenciado",
                "updated_at",
            ]
        )
        return self

    def reativar_alerta_sonoro_permanente(self):
        if not self.alerta_sonoro_silenciado_permanente:
            return self
        self.alerta_sonoro_silenciado_permanente = False
        self.save(update_fields=["alerta_sonoro_silenciado_permanente", "updated_at"])
        return self

    def iniciar_teste_alerta_sonoro(self, *, duracao_segundos=5):
        agora = timezone.now()
        self.alerta_sonoro_teste_ate = agora + timedelta(seconds=duracao_segundos)
        self.save(update_fields=["alerta_sonoro_teste_ate", "updated_at"])
        return self

    @property
    def alerta_sonoro_teste_ativo(self):
        return self.alerta_sonoro_teste_ate is not None and self.alerta_sonoro_teste_ate > timezone.now()

    @property
    def alerta_sonoro_deve_apitar(self):
        return (
            self.alerta_sonoro_teste_ativo
            or (
                self.status == self.STATUS_PERIGO
                and not self.alerta_sonoro_silenciado
                and not self.alerta_sonoro_silenciado_permanente
            )
        )

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
            raise ValueError("Status inválido para reservatório.")
        return status_final

    @staticmethod
    def _normalizar_meta(meta, *, campo, padrao):
        if meta is None:
            return float(padrao)

        try:
            numero = float(meta)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} inválida para reservatório.") from exc

        if not math.isfinite(numero) or numero <= 0:
            raise ValueError(f"{campo} deve ser maior que zero.")

        return numero

    @classmethod
    def _normalizar_meta_ph(cls, meta, *, padrao):
        numero = cls._normalizar_meta(meta, campo="meta_ph", padrao=padrao)
        if numero > 14:
            raise ValueError("meta_ph deve ser menor ou igual a 14.")
        return numero

    @staticmethod
    def _normalizar_intervalo_esp32(valor, *, campo, padrao):
        if valor is None:
            return int(padrao)

        try:
            numero = int(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} invalido para reservatorio.") from exc

        if numero <= 0:
            raise ValueError(f"{campo} deve ser maior que zero.")
        return numero

    @classmethod
    def _normalizar_faixa(
        cls,
        minimo,
        maximo,
        *,
        campo,
        padrao_min,
        padrao_max,
        permitir_zero,
    ):
        min_final = cls._normalizar_numero_faixa(
            minimo,
            campo=f"{campo}_min",
            padrao=padrao_min,
            permitir_zero=permitir_zero,
        )
        max_final = cls._normalizar_numero_faixa(
            maximo,
            campo=f"{campo}_max",
            padrao=padrao_max,
            permitir_zero=False,
        )

        if max_final < min_final:
            raise ValueError(f"{campo}_max deve ser maior ou igual a {campo}_min.")

        return min_final, max_final

    @classmethod
    def _normalizar_faixa_ph(cls, minimo, maximo, *, padrao_min, padrao_max):
        min_final, max_final = cls._normalizar_faixa(
            minimo,
            maximo,
            campo="faixa_ph",
            padrao_min=padrao_min,
            padrao_max=padrao_max,
            permitir_zero=False,
        )
        if min_final < 0 or max_final > 14:
            raise ValueError("faixa_ph deve estar entre 0 e 14.")
        return min_final, max_final

    @staticmethod
    def _normalizar_numero_faixa(valor, *, campo, padrao, permitir_zero):
        if valor is None:
            numero = float(padrao)
        else:
            try:
                numero = float(valor)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{campo} inválida para reservatório.") from exc

        if not math.isfinite(numero):
            raise ValueError(f"{campo} inválida para reservatório.")
        if permitir_zero and numero == 0:
            return numero
        if numero <= 0:
            raise ValueError(f"{campo} deve ser maior que zero.")
        return numero

    @staticmethod
    def _normalizar_nome(nome):
        if not isinstance(nome, str):
            raise ValueError("Nome inválido para reservatório.")

        nome_final = nome.strip()
        if not nome_final:
            raise ValueError("O nome do reservatório é obrigatório.")

        return nome_final

    @staticmethod
    def _normalizar_id(reservatorio_id):
        if isinstance(reservatorio_id, int):
            return reservatorio_id if reservatorio_id > 0 else None

        if isinstance(reservatorio_id, str) and reservatorio_id.isdigit():
            return int(reservatorio_id)

        return None


class PontoMonitoramento(models.Model):
    TIPO_UNICO = "ponto_unico"
    TIPO_ANTES = "antes_tratamento"
    TIPO_DEPOIS = "depois_tratamento"
    TEMPERATURA_INCLINACAO_PADRAO = 1.0
    PH_VOLTAGEM_REFERENCIA_7_PADRAO = 2.39
    PH_INCLINACAO_PADRAO = 0.23
    PH_TEMPERATURA_CALIBRACAO_PADRAO = 25.0
    TDS_INCLINACAO_PADRAO = 1.0
    TURBIDEZ_INCLINACAO_PADRAO = 1.0
    TDS_ALVO_CALIBRACAO_PADRAO = 40.0
    TURBIDEZ_ALVO_CALIBRACAO_PADRAO = 0.4
    TIPOS_LEGADOS = (
        TIPO_ANTES,
        TIPO_DEPOIS,
    )
    TIPOS = (TIPO_UNICO,)
    TIPOS_COMPATIVEIS = (
        TIPO_UNICO,
        TIPO_ANTES,
        TIPO_DEPOIS,
    )
    TIPO_CHOICES = (
        (TIPO_UNICO, "Ponto único"),
    )
    TIPO_ALIASES = {
        TIPO_UNICO: TIPO_UNICO,
        TIPO_ANTES: TIPO_UNICO,
        TIPO_DEPOIS: TIPO_UNICO,
        "pre": TIPO_UNICO,
        "pos": TIPO_UNICO,
        "ponto_unico": TIPO_UNICO,
        "ponto unico": TIPO_UNICO,
    }

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
    temperatura_inclinacao = models.FloatField(default=TEMPERATURA_INCLINACAO_PADRAO)
    temperatura_offset_c = models.FloatField(default=0.0)
    temperatura_valor_referencia_c = models.FloatField(null=True, blank=True)
    temperatura_bruta_referencia_c = models.FloatField(null=True, blank=True)
    temperatura_calibrado_em = models.DateTimeField(null=True, blank=True)
    ph_voltagem_referencia_7 = models.FloatField(default=PH_VOLTAGEM_REFERENCIA_7_PADRAO)
    ph_inclinacao = models.FloatField(default=PH_INCLINACAO_PADRAO)
    ph_temperatura_calibracao_c = models.FloatField(default=PH_TEMPERATURA_CALIBRACAO_PADRAO)
    ph_calibrado_em = models.DateTimeField(null=True, blank=True)
    tds_inclinacao = models.FloatField(default=TDS_INCLINACAO_PADRAO)
    tds_offset_ppm = models.FloatField(default=0.0)
    tds_calibrado_em = models.DateTimeField(null=True, blank=True)
    turbidez_inclinacao = models.FloatField(default=TURBIDEZ_INCLINACAO_PADRAO)
    turbidez_offset_ntu = models.FloatField(default=0.0)
    turbidez_calibrado_em = models.DateTimeField(null=True, blank=True)
    tds_alvo_calibracao_ppm = models.FloatField(default=TDS_ALVO_CALIBRACAO_PADRAO)
    turbidez_alvo_calibracao_ntu = models.FloatField(default=TURBIDEZ_ALVO_CALIBRACAO_PADRAO)
    tds_adc_calibracao = models.IntegerField(null=True, blank=True)
    turbidez_adc_calibracao = models.IntegerField(null=True, blank=True)
    agua_calibrado_em = models.DateTimeField(null=True, blank=True)
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
        return f"{self.reservatorio.nome} - {self.nome_exibicao}"

    @property
    def tipo_canonico(self):
        return self.TIPO_UNICO

    @property
    def nome_exibicao(self):
        return "Ponto único"

    @classmethod
    def normalizar_tipo(cls, tipo):
        if not isinstance(tipo, str):
            raise ValueError("ponto_tipo invalido")

        tipo_normalizado = tipo.strip().lower()
        tipo_resolvido = cls.TIPO_ALIASES.get(tipo_normalizado)
        if tipo_resolvido is None:
            raise ValueError("ponto_tipo invalido")
        return tipo_resolvido

    def atualizar_status(self, *, status, confianca=None, modelo_versao=""):
        self.status_atual = status
        self.confianca_status = confianca
        self.modelo_versao = (modelo_versao or "").strip()
        self.save(update_fields=["status_atual", "confianca_status", "modelo_versao", "updated_at"])
        return self

    def reclassificar_ultima_leitura(self):
        ultima_leitura = (
            LeituraQualidade.objects.filter(ponto=self)
            .order_by("-data_hora", "-id")
            .first()
        )
        if ultima_leitura is None:
            return None

        status_recalculado = calcular_status_reservatorio(
            reservatorio=self.reservatorio,
            temperatura=ultima_leitura.temperatura,
            tds=ultima_leitura.tds,
            turbidez=ultima_leitura.turbidez,
            ph=ultima_leitura.ph,
            data_hora=ultima_leitura.data_hora,
        )

        if ultima_leitura.status_leitura != status_recalculado:
            ultima_leitura.status_leitura = status_recalculado
            ultima_leitura.save(update_fields=["status_leitura"])

        self.atualizar_status(
            status=status_recalculado,
            confianca=ultima_leitura.confianca,
            modelo_versao=ultima_leitura.modelo_versao,
        )
        return ultima_leitura

    def atualizar_calibracao_temperatura(
        self,
        *,
        temperatura_bruta_c,
        temperatura_referencia_c,
        temperatura_inclinacao=None,
    ):
        temperatura_bruta_final = self._normalizar_temperatura_calibracao(
            temperatura_bruta_c,
            campo="temperatura_bruta_referencia_c",
        )
        temperatura_referencia_final = self._normalizar_temperatura_calibracao(
            temperatura_referencia_c,
            campo="temperatura_valor_referencia_c",
        )
        inclinacao_final = (
            self._normalizar_temperatura_inclinacao(temperatura_inclinacao)
            if temperatura_inclinacao is not None
            else self.temperatura_inclinacao
        )

        self.temperatura_inclinacao = inclinacao_final
        self.temperatura_offset_c = (
            temperatura_referencia_final - (temperatura_bruta_final * inclinacao_final)
        )
        self.temperatura_valor_referencia_c = temperatura_referencia_final
        self.temperatura_bruta_referencia_c = temperatura_bruta_final
        self.temperatura_calibrado_em = timezone.now()
        self.save(
            update_fields=[
                "temperatura_inclinacao",
                "temperatura_offset_c",
                "temperatura_valor_referencia_c",
                "temperatura_bruta_referencia_c",
                "temperatura_calibrado_em",
                "updated_at",
            ]
        )
        return self

    def atualizar_calibracao_ph(
        self,
        *,
        ph_voltagem_referencia_7=None,
        ph_inclinacao=None,
        temperatura_calibracao_c=None,
    ):
        campos_para_salvar = []

        if ph_voltagem_referencia_7 is not None:
            self.ph_voltagem_referencia_7 = self._normalizar_ph_voltagem_referencia_7(
                ph_voltagem_referencia_7
            )
            campos_para_salvar.append("ph_voltagem_referencia_7")

        if ph_inclinacao is not None:
            self.ph_inclinacao = self._normalizar_ph_inclinacao(ph_inclinacao)
            campos_para_salvar.append("ph_inclinacao")

        if temperatura_calibracao_c is not None:
            self.ph_temperatura_calibracao_c = self._normalizar_temperatura_calibracao(
                temperatura_calibracao_c,
                campo="ph_temperatura_calibracao_c",
            )
            campos_para_salvar.append("ph_temperatura_calibracao_c")

        if not campos_para_salvar:
            return self

        self.ph_calibrado_em = timezone.now()
        self.save(update_fields=[*campos_para_salvar, "ph_calibrado_em", "updated_at"])
        return self

    def atualizar_calibracao_agua_limpa(
        self,
        *,
        tds_base_ppm,
        turbidez_base_ntu,
        tds_alvo_ppm,
        turbidez_alvo_ntu,
        tds_adc=None,
        turbidez_adc=None,
    ):
        tds_alvo_final = self._normalizar_tds_alvo_calibracao(tds_alvo_ppm)
        turbidez_alvo_final = self._normalizar_turbidez_alvo_calibracao(turbidez_alvo_ntu)

        self.tds_offset_ppm = tds_alvo_final - float(tds_base_ppm)
        self.turbidez_offset_ntu = turbidez_alvo_final - float(turbidez_base_ntu)
        self.tds_alvo_calibracao_ppm = tds_alvo_final
        self.turbidez_alvo_calibracao_ntu = turbidez_alvo_final
        self.tds_adc_calibracao = self._normalizar_adc_calibracao(tds_adc, campo="tds_adc_calibracao")
        self.turbidez_adc_calibracao = self._normalizar_adc_calibracao(
            turbidez_adc,
            campo="turbidez_adc_calibracao",
        )
        self.agua_calibrado_em = timezone.now()

        self.save(
            update_fields=[
                "tds_offset_ppm",
                "turbidez_offset_ntu",
                "tds_alvo_calibracao_ppm",
                "turbidez_alvo_calibracao_ntu",
                "tds_adc_calibracao",
                "turbidez_adc_calibracao",
                "agua_calibrado_em",
                "updated_at",
            ]
        )
        return self

    def atualizar_calibracao_tds(
        self,
        *,
        tds_base_ppm,
        tds_alvo_ppm,
        tds_adc=None,
        tds_inclinacao=None,
    ):
        tds_alvo_final = self._normalizar_tds_alvo_calibracao(tds_alvo_ppm)
        tds_inclinacao_final = (
            self._normalizar_inclinacao_sensor(
                tds_inclinacao,
                campo="tds_inclinacao",
            )
            if tds_inclinacao is not None
            else self.tds_inclinacao
        )

        self.tds_inclinacao = tds_inclinacao_final
        self.tds_offset_ppm = tds_alvo_final - (float(tds_base_ppm) * tds_inclinacao_final)
        self.tds_alvo_calibracao_ppm = tds_alvo_final
        self.tds_adc_calibracao = self._normalizar_adc_calibracao(tds_adc, campo="tds_adc_calibracao")
        self.tds_calibrado_em = timezone.now()
        self.agua_calibrado_em = self.tds_calibrado_em
        self.save(
            update_fields=[
                "tds_inclinacao",
                "tds_offset_ppm",
                "tds_alvo_calibracao_ppm",
                "tds_adc_calibracao",
                "tds_calibrado_em",
                "agua_calibrado_em",
                "updated_at",
            ]
        )
        return self

    def atualizar_calibracao_turbidez(
        self,
        *,
        turbidez_base_ntu,
        turbidez_alvo_ntu,
        turbidez_adc=None,
        turbidez_inclinacao=None,
    ):
        turbidez_alvo_final = self._normalizar_turbidez_alvo_calibracao(turbidez_alvo_ntu)
        turbidez_inclinacao_final = (
            self._normalizar_inclinacao_sensor(
                turbidez_inclinacao,
                campo="turbidez_inclinacao",
            )
            if turbidez_inclinacao is not None
            else self.turbidez_inclinacao
        )

        self.turbidez_inclinacao = turbidez_inclinacao_final
        self.turbidez_offset_ntu = (
            turbidez_alvo_final - (float(turbidez_base_ntu) * turbidez_inclinacao_final)
        )
        self.turbidez_alvo_calibracao_ntu = turbidez_alvo_final
        self.turbidez_adc_calibracao = self._normalizar_adc_calibracao(
            turbidez_adc,
            campo="turbidez_adc_calibracao",
        )
        self.turbidez_calibrado_em = timezone.now()
        self.agua_calibrado_em = self.turbidez_calibrado_em
        self.save(
            update_fields=[
                "turbidez_inclinacao",
                "turbidez_offset_ntu",
                "turbidez_alvo_calibracao_ntu",
                "turbidez_adc_calibracao",
                "turbidez_calibrado_em",
                "agua_calibrado_em",
                "updated_at",
            ]
        )
        return self

    def atualizar_calibracao_turbidez_2_pontos(
        self,
        *,
        turbidez_ponto_1_ntu,
        turbidez_tensao_ponto_1,
        turbidez_ponto_2_ntu,
        turbidez_tensao_ponto_2,
    ):
        turbidez_ponto_1_final = self._normalizar_turbidez_alvo_calibracao(turbidez_ponto_1_ntu)
        turbidez_ponto_2_final = self._normalizar_turbidez_alvo_calibracao(turbidez_ponto_2_ntu)
        tensao_ponto_1_final = self._normalizar_tensao_calibracao_sensor(
            turbidez_tensao_ponto_1,
            campo="turbidez_tensao_ponto_1",
        )
        tensao_ponto_2_final = self._normalizar_tensao_calibracao_sensor(
            turbidez_tensao_ponto_2,
            campo="turbidez_tensao_ponto_2",
        )

        if math.isclose(
            tensao_ponto_1_final,
            tensao_ponto_2_final,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "As tensoes de turbidez devem ser diferentes para recalcular a inclinacao."
            )

        inclinacao_final = self._normalizar_turbidez_inclinacao(
            (turbidez_ponto_2_final - turbidez_ponto_1_final)
            / (tensao_ponto_2_final - tensao_ponto_1_final)
        )
        offset_final = turbidez_ponto_1_final - (tensao_ponto_1_final * inclinacao_final)
        if not math.isfinite(offset_final):
            raise ValueError("Nao foi possivel calcular um offset valido para a turbidez.")

        self.turbidez_inclinacao = inclinacao_final
        self.turbidez_offset_ntu = offset_final
        self.turbidez_alvo_calibracao_ntu = turbidez_ponto_1_final
        self.turbidez_adc_calibracao = None
        self.turbidez_calibrado_em = timezone.now()
        self.agua_calibrado_em = self.turbidez_calibrado_em
        self.save(
            update_fields=[
                "turbidez_inclinacao",
                "turbidez_offset_ntu",
                "turbidez_alvo_calibracao_ntu",
                "turbidez_adc_calibracao",
                "turbidez_calibrado_em",
                "agua_calibrado_em",
                "updated_at",
            ]
        )
        return self

    def aplicar_calibracao_agua(self, *, tds, turbidez):
        tds_ajustado = (float(tds) * float(self.tds_inclinacao)) + float(self.tds_offset_ppm)
        turbidez_ajustada = (
            float(turbidez) * float(self.turbidez_inclinacao)
        ) + float(self.turbidez_offset_ntu)
        return max(0.0, tds_ajustado), max(0.0, turbidez_ajustada)

    def aplicar_calibracao_temperatura(self, temperatura):
        temperatura_corrigida = (
            float(temperatura) * float(self.temperatura_inclinacao)
        ) + float(self.temperatura_offset_c)
        return self._normalizar_temperatura_calibracao(
            temperatura_corrigida,
            campo="temperatura",
        )

    def resetar_calibracao_sensor(self, *, sensor):
        sensor_final = (sensor or "").strip().lower()
        if sensor_final == "temperatura":
            self.temperatura_inclinacao = self.TEMPERATURA_INCLINACAO_PADRAO
            self.temperatura_offset_c = 0.0
            self.temperatura_valor_referencia_c = None
            self.temperatura_bruta_referencia_c = None
            self.temperatura_calibrado_em = None
            self.save(
                update_fields=[
                    "temperatura_inclinacao",
                    "temperatura_offset_c",
                    "temperatura_valor_referencia_c",
                    "temperatura_bruta_referencia_c",
                    "temperatura_calibrado_em",
                    "updated_at",
                ]
            )
            return self

        if sensor_final == "tds":
            self.tds_inclinacao = self.TDS_INCLINACAO_PADRAO
            self.tds_offset_ppm = 0.0
            self.tds_alvo_calibracao_ppm = self.TDS_ALVO_CALIBRACAO_PADRAO
            self.tds_adc_calibracao = None
            self.tds_calibrado_em = None
            self._sincronizar_data_calibracao_agua()
            self.save(
                update_fields=[
                    "tds_inclinacao",
                    "tds_offset_ppm",
                    "tds_alvo_calibracao_ppm",
                    "tds_adc_calibracao",
                    "tds_calibrado_em",
                    "agua_calibrado_em",
                    "updated_at",
                ]
            )
            return self

        if sensor_final == "turbidez":
            self.turbidez_inclinacao = self.TURBIDEZ_INCLINACAO_PADRAO
            self.turbidez_offset_ntu = 0.0
            self.turbidez_alvo_calibracao_ntu = self.TURBIDEZ_ALVO_CALIBRACAO_PADRAO
            self.turbidez_adc_calibracao = None
            self.turbidez_calibrado_em = None
            self._sincronizar_data_calibracao_agua()
            self.save(
                update_fields=[
                    "turbidez_inclinacao",
                    "turbidez_offset_ntu",
                    "turbidez_alvo_calibracao_ntu",
                    "turbidez_adc_calibracao",
                    "turbidez_calibrado_em",
                    "agua_calibrado_em",
                    "updated_at",
                ]
            )
            return self

        if sensor_final == "ph":
            self.ph_voltagem_referencia_7 = self.PH_VOLTAGEM_REFERENCIA_7_PADRAO
            self.ph_inclinacao = self.PH_INCLINACAO_PADRAO
            self.ph_temperatura_calibracao_c = self.PH_TEMPERATURA_CALIBRACAO_PADRAO
            self.ph_calibrado_em = None
            self.save(
                update_fields=[
                    "ph_voltagem_referencia_7",
                    "ph_inclinacao",
                    "ph_temperatura_calibracao_c",
                    "ph_calibrado_em",
                    "updated_at",
                ]
            )
            return self

        raise ValueError("sensor inválido")

    def _sincronizar_data_calibracao_agua(self):
        datas = [data for data in (self.tds_calibrado_em, self.turbidez_calibrado_em) if data is not None]
        self.agua_calibrado_em = max(datas) if datas else None

    def registrar_leitura(
        self,
        *,
        temperatura,
        tds,
        turbidez,
        ph=None,
        sinais_brutos=None,
        status_leitura,
        status_origem="regras",
        confianca=None,
        modelo_versao="",
        data_hora=None,
    ):
        status_final = Reservatorio._normalizar_status(status_leitura)
        sinais_brutos_final = sinais_brutos if isinstance(sinais_brutos, dict) else {}
        dados_leitura = {
            "ponto": self,
            "temperatura": temperatura,
            "tds": tds,
            "turbidez": turbidez,
            "ph": ph,
            "sinais_brutos": sinais_brutos_final,
            "status_leitura": status_final,
            "status_origem": status_origem,
            "confianca": confianca,
            "modelo_versao": (modelo_versao or "").strip(),
        }
        leitura = LeituraQualidade.objects.create(
            **dados_leitura,
        )
        if data_hora is not None:
            LeituraQualidade.objects.filter(id=leitura.id).update(data_hora=data_hora)
            leitura.data_hora = data_hora

        self.atualizar_status(
            status=status_final,
            confianca=confianca,
            modelo_versao=modelo_versao,
        )
        return leitura

    @staticmethod
    def _normalizar_ph_voltagem_referencia_7(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Calibração pH7 inválida para o ponto.") from exc

        if not math.isfinite(numero) or numero <= 0 or numero > 3.3:
            raise ValueError("A calibração pH7 deve estar entre 0 e 3.3V.")
        return numero

    @staticmethod
    def _normalizar_ph_inclinacao(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Inclinação de pH inválida para o ponto.") from exc

        if not math.isfinite(numero) or numero <= 0:
            raise ValueError("A inclinacao de pH deve ser maior que zero.")
        return numero

    @staticmethod
    def _normalizar_temperatura_inclinacao(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Inclinação de temperatura inválida para o ponto.") from exc

        if not math.isfinite(numero) or numero <= 0:
            raise ValueError("A inclinacao de temperatura deve ser maior que zero.")
        return numero

    @staticmethod
    def _normalizar_temperatura_calibracao(valor, *, campo):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} inválida para calibração.") from exc

        if not math.isfinite(numero) or numero < -50 or numero > 150:
            raise ValueError(f"{campo} deve estar entre -50C e 150C.")
        return numero

    @staticmethod
    def _normalizar_tds_alvo_calibracao(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Alvo de TDS inválido para calibração.") from exc

        if not math.isfinite(numero) or numero < 0 or numero >= 50:
            raise ValueError("O alvo de TDS da calibração deve estar entre 0 e ser menor que 50 ppm.")
        return numero

    @staticmethod
    def _normalizar_turbidez_alvo_calibracao(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Alvo de turbidez inválido para calibração.") from exc

        if not math.isfinite(numero) or numero < 0:
            raise ValueError("O alvo de turbidez da calibração deve ser maior ou igual a 0 NTU.")
        return numero

    @staticmethod
    def _normalizar_turbidez_inclinacao(valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("Inclinação de turbidez inválida para o ponto.") from exc

        if not math.isfinite(numero) or math.isclose(numero, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("A inclinacao de turbidez deve ser diferente de zero.")
        return numero

    @staticmethod
    def _normalizar_tensao_calibracao_sensor(valor, *, campo):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} inválida.") from exc

        if not math.isfinite(numero) or numero < 0 or numero > 3.3:
            raise ValueError(f"{campo} deve estar entre 0 e 3.3V.")
        return numero

    @staticmethod
    def _normalizar_inclinacao_sensor(valor, *, campo):
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} inválida.") from exc
        if not math.isfinite(numero) or numero <= 0:
            raise ValueError(f"{campo} deve ser maior que zero.")
        return numero

    @staticmethod
    def _normalizar_adc_calibracao(valor, *, campo):
        if valor is None:
            return None
        try:
            numero = int(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{campo} inválido.") from exc
        if numero < 0:
            raise ValueError(f"{campo} deve ser maior ou igual a zero.")
        return numero


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
    ph = models.FloatField(null=True, blank=True)
    sinais_brutos = models.JSONField(default=dict, blank=True)
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


class SessaoCalibracao(models.Model):
    STATUS_ATIVA = "ativa"
    STATUS_ENCERRADA = "encerrada"
    STATUS_EXPIRADA = "expirada"
    SENSOR_TEMPERATURA = "temperatura"
    SENSOR_TDS = "tds"
    SENSOR_TURBIDEZ = "turbidez"
    SENSOR_PH = "ph"
    STATUS_CHOICES = (
        (STATUS_ATIVA, "Ativa"),
        (STATUS_ENCERRADA, "Encerrada"),
        (STATUS_EXPIRADA, "Expirada"),
    )
    SENSOR_CHOICES = (
        (SENSOR_TEMPERATURA, "Temperatura"),
        (SENSOR_TDS, "TDS"),
        (SENSOR_TURBIDEZ, "Turbidez"),
        (SENSOR_PH, "pH"),
    )
    DURACAO_PADRAO_SEGUNDOS = 15 * 60
    INTERVALO_ENVIO_PADRAO_MS = 5000
    QTD_AMOSTRAS_PADRAO = 80
    ATRASO_AMOSTRA_PADRAO_MS = 50

    ponto = models.ForeignKey(
        PontoMonitoramento,
        on_delete=models.CASCADE,
        related_name="sessoes_calibracao",
    )
    sensor = models.CharField(max_length=20, choices=SENSOR_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ATIVA)
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessoes_calibracao_iniciadas",
    )
    intervalo_envio_ms = models.PositiveIntegerField(default=INTERVALO_ENVIO_PADRAO_MS)
    qtd_amostras = models.PositiveIntegerField(default=QTD_AMOSTRAS_PADRAO)
    atraso_amostra_ms = models.PositiveIntegerField(default=ATRASO_AMOSTRA_PADRAO_MS)
    dados_fluxo = models.JSONField(default=dict, blank=True)
    iniciada_em = models.DateTimeField(auto_now_add=True)
    ultima_amostra_em = models.DateTimeField(null=True, blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-iniciada_em"]
        indexes = [
            models.Index(fields=["ponto", "status", "expira_em"]),
            models.Index(fields=["ponto", "sensor", "status"]),
        ]

    def __str__(self):
        return f"{self.ponto} - {self.get_sensor_display()} ({self.status})"

    @classmethod
    def iniciar(
        cls,
        *,
        ponto,
        sensor,
        iniciada_por=None,
        intervalo_envio_ms=None,
        qtd_amostras=None,
        atraso_amostra_ms=None,
        duracao_segundos=None,
    ):
        sensor_final = cls.normalizar_sensor(sensor)
        cls.encerrar_ativas_do_ponto(ponto)
        agora = timezone.now()
        duracao_final = duracao_segundos or cls.DURACAO_PADRAO_SEGUNDOS
        intervalo_envio_final = intervalo_envio_ms or cls.INTERVALO_ENVIO_PADRAO_MS
        plano_amostragem = construir_plano_amostragem_calibracao(
            sensor=sensor_final,
            intervalo_envio_ms=intervalo_envio_final,
        )

        return cls.objects.create(
            ponto=ponto,
            sensor=sensor_final,
            status=cls.STATUS_ATIVA,
            iniciada_por=iniciada_por,
            intervalo_envio_ms=intervalo_envio_final,
            qtd_amostras=(
                int(qtd_amostras)
                if qtd_amostras is not None
                else plano_amostragem["qtd_amostras"]
            ),
            atraso_amostra_ms=(
                int(atraso_amostra_ms)
                if atraso_amostra_ms is not None
                else plano_amostragem["atraso_amostra_ms"]
            ),
            expira_em=agora + timedelta(seconds=duracao_final),
        )

    @classmethod
    def encerrar_ativas_do_ponto(cls, ponto):
        agora = timezone.now()
        cls.objects.filter(
            ponto=ponto,
            status=cls.STATUS_ATIVA,
        ).update(
            status=cls.STATUS_ENCERRADA,
            encerrada_em=agora,
            updated_at=agora,
        )

    @classmethod
    def obter_ativa(cls, *, ponto, sensor=None):
        agora = timezone.now()
        expiradas = cls.objects.filter(
            ponto=ponto,
            status=cls.STATUS_ATIVA,
            expira_em__lt=agora,
        )
        if expiradas.exists():
            expiradas.update(
                status=cls.STATUS_EXPIRADA,
                encerrada_em=agora,
                updated_at=agora,
            )

        filtros = {
            "ponto": ponto,
            "status": cls.STATUS_ATIVA,
            "expira_em__gte": agora,
        }
        if sensor is not None:
            filtros["sensor"] = cls.normalizar_sensor(sensor)
        return cls.objects.filter(**filtros).order_by("-iniciada_em").first()

    @classmethod
    def normalizar_sensor(cls, sensor):
        if not isinstance(sensor, str):
            raise ValueError("sensor inválido")
        sensor_normalizado = sensor.strip().lower()
        validos = {item[0] for item in cls.SENSOR_CHOICES}
        if sensor_normalizado not in validos:
            raise ValueError("sensor inválido")
        return sensor_normalizado

    def encerrar(self, *, status=STATUS_ENCERRADA):
        if self.status != self.STATUS_ATIVA:
            return self
        self.status = status
        self.encerrada_em = timezone.now()
        self.save(update_fields=["status", "encerrada_em", "updated_at"])
        return self

    @property
    def esta_ativa(self):
        return self.status == self.STATUS_ATIVA and self.expira_em >= timezone.now()


class AmostraCalibracao(models.Model):
    sessao = models.ForeignKey(
        SessaoCalibracao,
        on_delete=models.CASCADE,
        related_name="amostras",
    )
    temperatura = models.FloatField(null=True, blank=True)
    adc_tds = models.IntegerField(null=True, blank=True)
    adc_turb = models.IntegerField(null=True, blank=True)
    adc_ph = models.IntegerField(null=True, blank=True)
    firmware_ts_ms = models.BigIntegerField(null=True, blank=True)
    sinais_brutos = models.JSONField(default=dict, blank=True)
    coletada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-coletada_em"]
        indexes = [
            models.Index(fields=["sessao", "coletada_em"]),
        ]

    def __str__(self):
        return f"Sessao {self.sessao_id} - {self.coletada_em:%d/%m/%Y %H:%M:%S}"
