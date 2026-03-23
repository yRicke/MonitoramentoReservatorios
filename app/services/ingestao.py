import json

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio
from app.services.regras import calcular_status, combinar_status


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

    LeituraQualidade.objects.create(
        ponto=ponto,
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
    )

    _recalcular_status_reservatorio(reservatorio)

    return reservatorio


def _recalcular_status_reservatorio(reservatorio):
    statuses = []

    for ponto in reservatorio.pontos_monitoramento.all():
        leitura = ponto.leituras_qualidade.first()
        if leitura is None:
            continue

        status_ponto = calcular_status(
            temperatura=leitura.temperatura,
            tds=leitura.tds,
            turbidez=leitura.turbidez,
        )
        statuses.append(status_ponto)

    reservatorio.atualizar_reservatorio(status=combinar_status(statuses))


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
        return float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc
