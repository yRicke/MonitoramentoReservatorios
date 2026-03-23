import json
import math

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio
from app.services.regras import calcular_status


class IngestaoLeituraErro(ValueError):
    pass


def processar_leitura_esp32(request_body):
    payload = _carregar_payload(request_body)

    reservatorio_id = payload.get("reservatorio_id")
    ponto_tipo = _extrair_ponto_tipo(payload)
    temperatura = _extrair_float(payload, "temperatura")
    tds = _extrair_float(payload, "tds")
    turbidez = _extrair_float(payload, "turbidez")

    reservatorio = Reservatorio.obter_por_id(reservatorio_id)
    if reservatorio is None:
        raise IngestaoLeituraErro("reservatorio invalido")

    reservatorio.garantir_pontos_monitoramento()
    ponto = reservatorio.obter_ponto_monitoramento(ponto_tipo)
    if ponto is None:
        raise IngestaoLeituraErro("ponto_tipo invalido")

    status_leitura = calcular_status(
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
        meta_ppm_tds=reservatorio.meta_ppm_tds,
        meta_ntu_turbidez=reservatorio.meta_ntu_turbidez,
        meta_celsius_temperatura=reservatorio.meta_celsius_temperatura,
    )

    ponto.registrar_leitura(
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
        status_leitura=status_leitura,
        status_origem=LeituraQualidade.ORIGEM_REGRAS,
        confianca=None,
        modelo_versao="",
    )

    reservatorio.sincronizar_status_pelo_ponto_depois()

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


def _extrair_ponto_tipo(payload):
    ponto_tipo = payload.get("ponto_tipo")
    if ponto_tipo is None:
        raise IngestaoLeituraErro("campo obrigatorio: ponto_tipo")

    try:
        return PontoMonitoramento.normalizar_tipo(ponto_tipo)
    except ValueError as exc:
        raise IngestaoLeituraErro("campo invalido: ponto_tipo") from exc


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
