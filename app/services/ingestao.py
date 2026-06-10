import json
import math
from datetime import timedelta

from django.utils import timezone

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio
from app.services.regras import calcular_status

ADC_TENSAO_REFERENCIA = 3.3
ADC_VALOR_MAXIMO = 4095
PH_VOLTAGEM_REFERENCIA_7 = 2.39
PH_INCLINACAO = 0.23


class IngestaoLeituraErro(ValueError):
    pass


def processar_leitura_esp32(request_body):
    payload = _carregar_payload(request_body)

    reservatorio_id = payload.get("reservatorio_id")
    _validar_payload_ponto_unico(payload)
    temperatura_bruta = _extrair_float(payload, "temperatura")
    sinais_brutos = _extrair_sinais_brutos(payload)
    sinais_brutos["temperatura_bruta"] = temperatura_bruta
    data_hora_leitura = _resolver_data_hora_leitura(sinais_brutos)

    reservatorio = Reservatorio.obter_por_id(reservatorio_id)
    if reservatorio is None:
        raise IngestaoLeituraErro("reservatório inválido")

    reservatorio.garantir_pontos_monitoramento()
    ponto = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
    if ponto is None:
        raise IngestaoLeituraErro("ponto de monitoramento inválido")

    temperatura = ponto.aplicar_calibracao_temperatura(temperatura_bruta)
    tds = _resolver_tds(payload, sinais_brutos, temperatura)
    turbidez = _resolver_turbidez(payload, sinais_brutos)
    ph = _resolver_ph(
        payload,
        sinais_brutos,
        temperatura=temperatura,
        ph_voltagem_referencia_7=ponto.ph_voltagem_referencia_7,
        ph_inclinacao=ponto.ph_inclinacao,
        ph_temperatura_calibracao_c=ponto.ph_temperatura_calibracao_c,
    )
    tds, turbidez = ponto.aplicar_calibracao_agua(tds=tds, turbidez=turbidez)

    status_leitura = calcular_status(
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
        ph=ph,
        faixa_ppm_tds_min=reservatorio.faixa_ppm_tds_min,
        faixa_ppm_tds_max=reservatorio.faixa_ppm_tds_max,
        faixa_ntu_turbidez_min=reservatorio.faixa_ntu_turbidez_min,
        faixa_ntu_turbidez_max=reservatorio.faixa_ntu_turbidez_max,
        faixa_celsius_temperatura_min=reservatorio.faixa_celsius_temperatura_min,
        faixa_celsius_temperatura_max=reservatorio.faixa_celsius_temperatura_max,
        faixa_ph_min=reservatorio.faixa_ph_min,
        faixa_ph_max=reservatorio.faixa_ph_max,
    )

    ponto.registrar_leitura(
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
        ph=ph,
        sinais_brutos=sinais_brutos,
        status_leitura=status_leitura,
        status_origem=LeituraQualidade.ORIGEM_REGRAS,
        confianca=None,
        modelo_versao="",
        data_hora=data_hora_leitura,
    )

    reservatorio.sincronizar_status_pelo_ponto()

    return reservatorio


def _carregar_payload(request_body):
    if not request_body:
        raise IngestaoLeituraErro("payload vazio")

    try:
        payload = json.loads(request_body.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise IngestaoLeituraErro("payload invalido") from exc
    except json.JSONDecodeError as exc:
        raise IngestaoLeituraErro("payload invalido") from exc

    if not isinstance(payload, dict):
        raise IngestaoLeituraErro("payload invalido")

    return payload


def _validar_payload_ponto_unico(payload):
    if "ponto_tipo" in payload:
        raise IngestaoLeituraErro("campo nao suportado: ponto_tipo")


def _extrair_float(payload, campo):
    valor = payload.get(campo)
    if valor is None:
        raise IngestaoLeituraErro(f"campo obrigatorio: {campo}")

    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc

    if not math.isfinite(numero):
        raise IngestaoLeituraErro(f"campo invalido: {campo}")

    return numero


def _extrair_float_opcional(payload, campo):
    valor = payload.get(campo)
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc

    if not math.isfinite(numero):
        raise IngestaoLeituraErro(f"campo invalido: {campo}")

    return numero


def _extrair_int_opcional(payload, campo):
    valor = payload.get(campo)
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc

    if not math.isfinite(numero):
        raise IngestaoLeituraErro(f"campo invalido: {campo}")
    if not numero.is_integer():
        raise IngestaoLeituraErro(f"campo invalido: {campo}")

    inteiro = int(numero)
    if inteiro < 0:
        raise IngestaoLeituraErro(f"campo invalido: {campo}")

    return inteiro


def _extrair_int_opcional_alias(payload, aliases, campo_erro):
    for alias in aliases:
        valor = payload.get(alias)
        if valor is None:
            continue
        return _extrair_int_opcional({campo_erro: valor}, campo_erro)
    return None


def _extrair_float_opcional_alias(payload, aliases, campo_erro):
    for alias in aliases:
        valor = payload.get(alias)
        if valor is None:
            continue
        return _extrair_float_opcional({campo_erro: valor}, campo_erro)
    return None


def _extrair_sinais_brutos(payload):
    sinais_payload = payload.get("raw")
    if sinais_payload is None:
        sinais_payload = payload.get("sinais_brutos")
    if sinais_payload is None:
        return {}

    if not isinstance(sinais_payload, dict):
        raise IngestaoLeituraErro("campo invalido: raw")

    sinais_brutos = {}
    adc_tds = _extrair_int_opcional_alias(
        sinais_payload,
        ["adc_tds", "tds_adc"],
        "adc_tds",
    )
    if adc_tds is not None:
        sinais_brutos["adc_tds"] = adc_tds

    tds_tensao = _extrair_float_opcional_alias(
        sinais_payload,
        ["tds_tensao"],
        "tds_tensao",
    )
    if tds_tensao is not None:
        sinais_brutos["tds_tensao"] = tds_tensao

    adc_turb = _extrair_int_opcional_alias(
        sinais_payload,
        ["adc_turb", "adc_turbidez", "turbidez_adc"],
        "adc_turb",
    )
    if adc_turb is not None:
        sinais_brutos["adc_turb"] = adc_turb

    turbidez_tensao = _extrair_float_opcional_alias(
        sinais_payload,
        ["turbidez_tensao"],
        "turbidez_tensao",
    )
    if turbidez_tensao is not None:
        sinais_brutos["turbidez_tensao"] = turbidez_tensao

    adc_ph = _extrair_int_opcional_alias(
        sinais_payload,
        ["adc_ph", "ph_adc"],
        "adc_ph",
    )
    if adc_ph is not None:
        sinais_brutos["adc_ph"] = adc_ph

    ph_tensao = _extrair_float_opcional_alias(
        sinais_payload,
        ["ph_tensao"],
        "ph_tensao",
    )
    if ph_tensao is not None:
        sinais_brutos["ph_tensao"] = ph_tensao

    firmware_ts_ms = _extrair_int_opcional(sinais_payload, "firmware_ts_ms")
    if firmware_ts_ms is not None:
        sinais_brutos["firmware_ts_ms"] = firmware_ts_ms

    firmware_now_ms = _extrair_int_opcional(sinais_payload, "firmware_now_ms")
    if firmware_now_ms is not None:
        sinais_brutos["firmware_now_ms"] = firmware_now_ms

    device_id = sinais_payload.get("device_id") or payload.get("device_id")
    if isinstance(device_id, str) and device_id.strip():
        sinais_brutos["device_id"] = device_id.strip()[:80]

    return sinais_brutos


def _resolver_data_hora_leitura(sinais_brutos):
    firmware_ts_ms = sinais_brutos.get("firmware_ts_ms")
    firmware_now_ms = sinais_brutos.get("firmware_now_ms")

    if firmware_ts_ms is None or firmware_now_ms is None:
        return None

    atraso_ms = firmware_now_ms - firmware_ts_ms
    if atraso_ms < 0:
        return None

    # Protege contra leituras antigas demais apos reboot/NVS corrompida.
    if atraso_ms > 7 * 24 * 60 * 60 * 1000:
        return None

    return timezone.now() - timedelta(milliseconds=atraso_ms)


def _resolver_tds(payload, sinais_brutos, temperatura):
    tds_tensao = sinais_brutos.get("tds_tensao")
    if tds_tensao is not None:
        return _calcular_tds_por_tensao(tds_tensao=tds_tensao, temperatura=temperatura)

    adc_tds = sinais_brutos.get("adc_tds")
    if adc_tds is not None:
        return calcular_tds_por_adc(adc_tds=adc_tds, temperatura=temperatura)

    return _extrair_float(payload, "tds")


def _resolver_turbidez(payload, sinais_brutos):
    turbidez_tensao = sinais_brutos.get("turbidez_tensao")
    if turbidez_tensao is not None:
        return _calcular_turbidez_por_tensao(turbidez_tensao=turbidez_tensao)

    adc_turb = sinais_brutos.get("adc_turb")
    if adc_turb is not None:
        return calcular_turbidez_por_adc(adc_turb=adc_turb)

    return _extrair_float(payload, "turbidez")


def _resolver_ph(
    payload,
    sinais_brutos,
    *,
    temperatura,
    ph_voltagem_referencia_7,
    ph_inclinacao,
    ph_temperatura_calibracao_c,
):
    ph_tensao = sinais_brutos.get("ph_tensao")
    if ph_tensao is not None:
        return _calcular_ph_por_tensao(
            ph_tensao=ph_tensao,
            temperatura=temperatura,
            ph_voltagem_referencia_7=ph_voltagem_referencia_7,
            ph_inclinacao=ph_inclinacao,
            ph_temperatura_calibracao_c=ph_temperatura_calibracao_c,
        )

    adc_ph = sinais_brutos.get("adc_ph")
    if adc_ph is not None:
        ph_tensao = _adc_para_tensao(adc_ph, campo="adc_ph")
        return _calcular_ph_por_tensao(
            ph_tensao=ph_tensao,
            temperatura=temperatura,
            ph_voltagem_referencia_7=ph_voltagem_referencia_7,
            ph_inclinacao=ph_inclinacao,
            ph_temperatura_calibracao_c=ph_temperatura_calibracao_c,
        )

    ph = _extrair_float_opcional(payload, "ph")
    if ph is not None:
        return _normalizar_ph(ph)

    return None


def _calcular_tds_por_tensao(*, tds_tensao, temperatura):
    coeficiente_compensacao = 1.0 + 0.02 * (temperatura - 25.0)
    if coeficiente_compensacao == 0:
        raise IngestaoLeituraErro("campo invalido: temperatura")

    tensao_compensada = tds_tensao / coeficiente_compensacao
    tds = (
        133.42 * (tensao_compensada ** 3)
        - 255.86 * (tensao_compensada ** 2)
        + 857.39 * tensao_compensada
    ) * 0.5

    if not math.isfinite(tds):
        raise IngestaoLeituraErro("campo invalido: tds")

    return max(tds, 0.0)


def _calcular_turbidez_por_tensao(*, turbidez_tensao):
    if turbidez_tensao < 0:
        raise IngestaoLeituraErro("campo invalido: turbidez")
    return turbidez_tensao


def calcular_tds_por_adc(*, adc_tds, temperatura):
    tds_tensao = _adc_para_tensao(adc_tds, campo="adc_tds")
    return _calcular_tds_por_tensao(tds_tensao=tds_tensao, temperatura=temperatura)


def calcular_turbidez_por_adc(*, adc_turb):
    turbidez_tensao = _adc_para_tensao(adc_turb, campo="adc_turb")
    return _calcular_turbidez_por_tensao(turbidez_tensao=turbidez_tensao)


def calcular_ph_por_adc(
    *,
    adc_ph,
    temperatura,
    ph_voltagem_referencia_7=PH_VOLTAGEM_REFERENCIA_7,
    ph_inclinacao=PH_INCLINACAO,
    ph_temperatura_calibracao_c=25.0,
):
    ph_tensao = _adc_para_tensao(adc_ph, campo="adc_ph")
    return _calcular_ph_por_tensao(
        ph_tensao=ph_tensao,
        temperatura=temperatura,
        ph_voltagem_referencia_7=ph_voltagem_referencia_7,
        ph_inclinacao=ph_inclinacao,
        ph_temperatura_calibracao_c=ph_temperatura_calibracao_c,
    )

def _calcular_ph_por_tensao(
    *,
    ph_tensao,
    temperatura,
    ph_voltagem_referencia_7=PH_VOLTAGEM_REFERENCIA_7,
    ph_inclinacao=PH_INCLINACAO,
    ph_temperatura_calibracao_c=25.0,
):
    if not math.isfinite(ph_voltagem_referencia_7) or ph_voltagem_referencia_7 <= 0:
        raise IngestaoLeituraErro("calibração inválida: ph_voltagem_referencia_7")
    if not math.isfinite(ph_inclinacao) or ph_inclinacao <= 0:
        raise IngestaoLeituraErro("calibração inválida: ph_inclinacao")
    if not math.isfinite(temperatura) or temperatura <= -273.15:
        raise IngestaoLeituraErro("campo invalido: temperatura")
    if (
        not math.isfinite(ph_temperatura_calibracao_c)
        or ph_temperatura_calibracao_c <= -273.15
    ):
        raise IngestaoLeituraErro("calibração inválida: ph_temperatura_calibracao_c")

    inclinacao_ajustada = ph_inclinacao * (
        (temperatura + 273.15) / (ph_temperatura_calibracao_c + 273.15)
    )
    if not math.isfinite(inclinacao_ajustada) or inclinacao_ajustada <= 0:
        raise IngestaoLeituraErro("calibração inválida: ph_inclinacao")

    ph = 7.0 + (ph_voltagem_referencia_7 - ph_tensao) / inclinacao_ajustada
    return _normalizar_ph(ph)

def _normalizar_ph(ph):
    if not math.isfinite(ph):
        raise IngestaoLeituraErro("campo invalido: ph")

    if ph < 0:
        return 0.0
    if ph > 14:
        return 14.0
    return ph

def _adc_para_tensao(adc, *, campo):
    if adc < 0 or adc > ADC_VALOR_MAXIMO:
        raise IngestaoLeituraErro(f"campo invalido: {campo}")
    return (adc * ADC_TENSAO_REFERENCIA) / ADC_VALOR_MAXIMO
