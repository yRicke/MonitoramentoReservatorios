from datetime import timedelta
import json
import math
import secrets
import statistics
import time

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.models import (
    AmostraCalibracao,
    LeituraQualidade,
    PontoMonitoramento,
    Reservatorio,
    SessaoCalibracao,
)
from app.services.ingestao import (
    ADC_TENSAO_REFERENCIA,
    ADC_VALOR_MAXIMO,
    IngestaoLeituraErro,
    calcular_ph_por_adc,
    calcular_tds_por_adc,
    calcular_turbidez_por_adc,
    processar_leitura_esp32,
)
from app.services.regras import (
    DESVIO_PH_ATENCAO,
    DESVIO_PH_PERIGO,
    DESVIO_TEMPERATURA_ATENCAO,
    DESVIO_TEMPERATURA_PERIGO,
    FATOR_PERIGO_TDS,
    FATOR_PERIGO_TURBIDEZ,
    classificar_status_por_faixa,
)

MAX_PONTOS_GRAFICO = 1200
PERIODO_PADRAO_VALOR = "5d"
ESP32_CONFIG_POLL_INTERVALO_MS = 2 * 1000
PERIODOS_DISPONIVEIS = (
    ("15m", "15 min"),
    ("30m", "30 min"),
    ("1h", "1 hora"),
    ("3h", "3 horas"),
    ("6h", "6 horas"),
    ("12h", "12 horas"),
    ("1d", "1 dia"),
    ("3d", "3 dias"),
    ("5d", "5 dias"),
    ("7d", "7 dias"),
    ("10d", "10 dias"),
    ("15d", "15 dias"),
    ("30d", "30 dias"),
    ("60d", "60 dias"),
    ("90d", "90 dias"),
)
STATUS_SEM_DADO = "sem-dado"
DIAS_ALERTA_CALIBRACAO_PH = 15
DIAS_ALERTA_CALIBRACAO_AGUA = 15
TTL_SESSAO_CALIBRACAO_SEGUNDOS = 10 * 60
LIMITE_AMOSTRAS_STATUS_CALIBRACAO = 30
CALIBRACAO_STATUS_LONG_POLL_MAX_MS = 15 * 1000
CALIBRACAO_STATUS_LONG_POLL_SLEEP_MS = 0.2
DESVIO_MAXIMO_ESTAVEL_TEMPERATURA = 0.2
DESVIO_MAXIMO_ESTAVEL_TDS_ADC = 20.0
DESVIO_MAXIMO_ESTAVEL_TURBIDEZ_ADC = 20.0
DESVIO_MAXIMO_ESTAVEL_PH_ADC = 12.0
ALERTA_SONORO_INTERVALO_LIGADO_MS = 500
ALERTA_SONORO_INTERVALO_DESLIGADO_MS = 500
SENSORES_CALIBRACAO = (
    {
        "id": "temperatura",
        "nome": "Temperatura",
        "descricao": "Ajuste a referência em graus Celsius para este ponto.",
    },
    {
        "id": "tds",
        "nome": "TDS",
        "descricao": "Calibre ppm com temperatura compensada deste ponto.",
    },
    {
        "id": "turbidez",
        "nome": "Turbidez",
        "descricao": "Calibre NTU sem compensação de temperatura.",
    },
    {
        "id": "ph",
        "nome": "pH",
        "descricao": "Ajuste solução conhecida e inclinação do eletrodo.",
    },
)
METRICAS_DETALHE_RECENTES = (
    ("temperatura", "Temperatura", "celsius", 2),
    ("tds", "TDS", "ppm", 2),
    ("turbidez", "Turbidez", "ntu", 3),
    ("ph", "pH", "", 2),
)


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def index(request):
    busca = request.GET.get("busca", "").strip()
    periodo_valor = _normalizar_periodo_valor(request.GET.get("dias"))
    periodo_delta = _delta_por_periodo(periodo_valor)
    reservatorios = list(Reservatorio.listar(busca=busca, usuario=request.user))
    dashboard_cards = _montar_dashboard_cards(reservatorios, periodo_delta)

    return render(
        request,
        "index.html",
        {
            "reservatorios": reservatorios,
            "dashboard_cards": dashboard_cards,
            "busca": busca,
            "periodo_selecionado": periodo_valor,
            "periodo_rotulo": _rotulo_periodo(periodo_valor),
            "periodos_disponiveis": PERIODOS_DISPONIVEIS,
        },
    )


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_adicionar(request):
    nome = request.POST.get("nome")

    try:
        Reservatorio.criar_reservatorio(usuario=request.user, nome=nome)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("index")
    except IntegrityError:
        messages.error(request, "Já existe reservatório com este nome.")
        return redirect("index")

    messages.success(request, "Reservatório adicionado.")
    return redirect("index")


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_detalhe(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    return render(
        request,
        "reservatorio/detalhe.html",
        _contexto_detalhe_reservatorio(reservatorio),
    )


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_editar(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "ReservatÃ³rio nÃ£o encontrado.")
        return redirect("index")

    return render(
        request,
        "reservatorio/editar.html",
        _contexto_edicao_reservatorio(reservatorio),
    )


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_regenerar_token_esp32(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "ReservatÃ³rio nÃ£o encontrado.")
        return redirect("index")

    reservatorio.regenerar_token_integracao_esp32()
    messages.success(request, "Token de integraÃ§Ã£o do ESP32 regenerado.")
    return redirect("reservatorio_editar", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_alerta_sonoro_alternar(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "ReservatÃ³rio nÃ£o encontrado.")
        return redirect("index")

    reservatorio.sincronizar_status_pelo_ponto()
    if reservatorio.status != Reservatorio.STATUS_PERIGO:
        reservatorio.reativar_alerta_sonoro()
        messages.info(request, "O alerta sonoro permanece desligado porque o reservatÃ³rio nÃ£o estÃ¡ em perigo.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    if reservatorio.alerta_sonoro_deve_apitar:
        reservatorio.silenciar_alerta_sonoro()
        messages.success(request, "Alerta sonoro silenciado para este estado de perigo.")
    else:
        reservatorio.reativar_alerta_sonoro()
        messages.success(request, "Alerta sonoro reativado.")
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_relatorio(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    return render(
        request,
        "reservatorio/relatorio.html",
        {
            **_contexto_detalhe_reservatorio(reservatorio),
            "gerado_em": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
            "relatorio_periodos_cards": _montar_relatorio_periodos_reservatorio(reservatorio),
            "auto_imprimir_relatorio": request.GET.get("download") == "1",
        },
    )


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_atualizar(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    nome = request.POST.get("nome")
    faixa_ppm_tds_min = request.POST.get("faixa_ppm_tds_min")
    faixa_ppm_tds_max = request.POST.get("faixa_ppm_tds_max")
    faixa_ntu_turbidez_min = request.POST.get("faixa_ntu_turbidez_min")
    faixa_ntu_turbidez_max = request.POST.get("faixa_ntu_turbidez_max")
    faixa_celsius_temperatura_min = request.POST.get("faixa_celsius_temperatura_min")
    faixa_celsius_temperatura_max = request.POST.get("faixa_celsius_temperatura_max")
    faixa_ph_min = request.POST.get("faixa_ph_min")
    faixa_ph_max = request.POST.get("faixa_ph_max")
    esp32_intervalo_envio_normal_s = request.POST.get("esp32_intervalo_envio_normal_s")
    esp32_intervalo_envio_calibracao_s = request.POST.get("esp32_intervalo_envio_calibracao_s")

    # Compatibilidade com payload antigo.
    meta_ppm_tds = request.POST.get("meta_ppm_tds")
    meta_ntu_turbidez = request.POST.get("meta_ntu_turbidez")
    meta_celsius_temperatura = request.POST.get("meta_celsius_temperatura")
    meta_ph = request.POST.get("meta_ph")

    try:
        reservatorio.atualizar_reservatorio(
            nome=nome,
            faixa_ppm_tds_min=faixa_ppm_tds_min,
            faixa_ppm_tds_max=faixa_ppm_tds_max,
            faixa_ntu_turbidez_min=faixa_ntu_turbidez_min,
            faixa_ntu_turbidez_max=faixa_ntu_turbidez_max,
            faixa_celsius_temperatura_min=faixa_celsius_temperatura_min,
            faixa_celsius_temperatura_max=faixa_celsius_temperatura_max,
            faixa_ph_min=faixa_ph_min,
            faixa_ph_max=faixa_ph_max,
            meta_ppm_tds=meta_ppm_tds,
            meta_ntu_turbidez=meta_ntu_turbidez,
            meta_celsius_temperatura=meta_celsius_temperatura,
            meta_ph=meta_ph,
            esp32_intervalo_envio_normal_s=esp32_intervalo_envio_normal_s,
            esp32_intervalo_envio_calibracao_s=esp32_intervalo_envio_calibracao_s,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reservatorio_editar", reservatorio_id=reservatorio.id)
    except IntegrityError:
        messages.error(request, "Já existe reservatório com este nome.")
        return redirect("reservatorio_editar", reservatorio_id=reservatorio.id)

    messages.success(request, "Reservatório atualizado.")
    return redirect("reservatorio_editar", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_calibracao(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    reservatorio.garantir_pontos_monitoramento()
    ponto_unico = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)

    return render(
        request,
        "reservatorio/calibracao.html",
        {
            **_contexto_calibracao_reservatorio(
                reservatorio,
                ponto_unico=ponto_unico,
            ),
            "ponto_calibracao": ponto_unico,
            "ponto_selecionado": PontoMonitoramento.TIPO_UNICO,
            "sensores_calibracao": _sensores_calibracao(),
        },
    )


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_calibracao_sensor(request, reservatorio_id, sensor_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    reservatorio.garantir_pontos_monitoramento()
    ponto_unico = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
    sensor_selecionado = _normalizar_sensor_calibracao(
        sensor_id,
        padrao="temperatura",
    )
    ponto_calibracao = ponto_unico

    return render(
        request,
        "reservatorio/calibracao_sensor.html",
        {
            **_contexto_calibracao_reservatorio(
                reservatorio,
                ponto_unico=ponto_unico,
            ),
            "sensor_selecionado": sensor_selecionado,
            "sensor_selecionado_nome": _rotulo_sensor_calibracao(sensor_selecionado),
            "titulo_calibracao_ativa": _titulo_calibracao_ativa(
                ponto=ponto_calibracao,
                sensor=sensor_selecionado,
            ),
            "ponto_calibracao": ponto_calibracao,
            "temperatura_calibracao_ativa": _resumo_calibracao_temperatura(ponto_calibracao),
            "tds_calibracao_ativa": _resumo_calibracao_tds(ponto_calibracao),
            "turbidez_calibracao_ativa": _resumo_calibracao_turbidez(ponto_calibracao),
            "ph_calibracao_ativa": _resumo_calibracao_ph(ponto_calibracao),
            "sessao_calibracao_ativa": _resumo_sessao_calibracao(
                ponto=ponto_calibracao,
                sensor=sensor_selecionado,
            ),
            "calibracao_intervalo_poll_ms": int(reservatorio.esp32_intervalo_envio_calibracao_s) * 1000,
        },
    )


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_sessao_iniciar(request, reservatorio_id, sensor_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        return redirect(_url_calibracao_raiz(reservatorio))

    sensor = _normalizar_sensor_calibracao(sensor_id, padrao="temperatura")
    SessaoCalibracao.iniciar(
        ponto=ponto,
        sensor=sensor,
        iniciada_por=request.user,
        intervalo_envio_ms=reservatorio.esp32_intervalo_envio_calibracao_s * 1000,
        duracao_segundos=TTL_SESSAO_CALIBRACAO_SEGUNDOS,
    )
    messages.success(
        request,
        f"Sessao de calibração iniciada para {_rotulo_sensor_calibracao(sensor)} em {_nome_curto_ponto(ponto)}.",
    )
    return _redirect_calibracao_sensor(reservatorio, ponto, sensor)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_sessao_encerrar(request, reservatorio_id, sensor_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        return redirect(_url_calibracao_raiz(reservatorio))

    sensor = _normalizar_sensor_calibracao(sensor_id, padrao="temperatura")
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=sensor)
    if sessao is not None:
        sessao.encerrar()
        messages.success(
            request,
            f"Sessao de calibração encerrada para {_rotulo_sensor_calibracao(sensor)}.",
        )
    else:
        messages.info(request, "Nao havia sessao ativa para este sensor.")
    return _redirect_calibracao_sensor(reservatorio, ponto, sensor)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_sensor_resetar(request, reservatorio_id, sensor_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        return redirect(_url_calibracao_raiz(reservatorio))

    sensor = _normalizar_sensor_calibracao(sensor_id, padrao="")
    if not sensor:
        messages.error(request, "Sensor de calibração inválido.")
        return redirect(_url_calibracao_raiz(reservatorio))

    ponto.resetar_calibracao_sensor(sensor=sensor)
    messages.success(
        request,
        (
            f"Dados de calibração de {_rotulo_sensor_calibracao(sensor)} resetados "
            f"em {_nome_curto_ponto(ponto)}."
        ),
    )
    return _redirect_calibracao_sensor(reservatorio, ponto, sensor)


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_calibracao_sessao_status(request, reservatorio_id, sensor_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        return JsonResponse({"erro": "reservatório não encontrado"}, status=404)

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        return JsonResponse({"erro": "ponto inválido"}, status=404)

    sensor = _normalizar_sensor_calibracao(sensor_id, padrao="temperatura")
    intervalo_padrao_ms = int(reservatorio.esp32_intervalo_envio_calibracao_s) * 1000
    cursor = str(request.GET.get("cursor") or "").strip()
    wait_ms = _normalizar_wait_status_calibracao_ms(
        request.GET.get("wait_ms"),
        intervalo_padrao_ms=intervalo_padrao_ms,
    )
    if cursor and wait_ms > 0:
        _aguardar_atualizacao_status_calibracao(
            ponto=ponto,
            sensor=sensor,
            cursor_atual=cursor,
            wait_ms=wait_ms,
        )

    resumo = _resumo_sessao_calibracao(ponto=ponto, sensor=sensor)
    if not resumo.get("intervalo_poll_ms"):
        resumo["intervalo_poll_ms"] = intervalo_padrao_ms
    return JsonResponse(resumo, status=200)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_temperatura_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    temperatura_referencia_raw = request.POST.get("temperatura_referencia_c")
    temperatura_inclinacao_raw = request.POST.get("temperatura_inclinacao")

    try:
        temperatura_referencia = float(temperatura_referencia_raw)
        temperatura_inclinacao = (
            float(temperatura_inclinacao_raw)
            if temperatura_inclinacao_raw not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        messages.error(request, "Informe temperatura de referencia e inclinacao validas.")
        return redirect(_url_calibracao_sensor(reservatorio, "temperatura"))

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        messages.error(request, "Ponto de calibracao nao encontrado.")
        return redirect(_url_calibracao_raiz(reservatorio))

    _, _, erro_sessao = _obter_sessao_calibracao_pronta(
        ponto=ponto,
        sensor=SessaoCalibracao.SENSOR_TEMPERATURA,
    )
    if erro_sessao:
        messages.error(request, erro_sessao)
        return redirect(_url_calibracao_sensor(reservatorio, "temperatura"))

    temperatura_bruta = _temperatura_bruta_para_calibracao(ponto)
    if temperatura_bruta is None:
        messages.error(request, "Nao ha temperatura media estavel na sessao deste ponto.")
        return redirect(_url_calibracao_sensor(reservatorio, "temperatura"))

    try:
        ponto.atualizar_calibracao_temperatura(
            temperatura_bruta_c=temperatura_bruta,
            temperatura_referencia_c=temperatura_referencia,
            temperatura_inclinacao=temperatura_inclinacao,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_url_calibracao_sensor(reservatorio, "temperatura"))

    messages.success(
        request,
        (
            f"Calibracao de temperatura aplicada no ponto {_nome_curto_ponto(ponto)}: "
            f"media {temperatura_bruta:.2f}C -> referencia {temperatura_referencia:.2f}C."
        ),
    )
    return redirect(_url_calibracao_sensor(reservatorio, "temperatura"))


@login_required(login_url="entrar")
@require_http_methods(["POST"])

@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_tds_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    ponto = _obter_ponto_calibracao_por_post(request, reservatorio)
    if ponto is None:
        return redirect(_url_calibracao_raiz(reservatorio))

    tds_alvo_raw = request.POST.get("tds_alvo_ppm")
    tds_inclinacao_raw = request.POST.get("tds_inclinacao")
    try:
        tds_alvo = float(tds_alvo_raw)
        tds_inclinacao = float(tds_inclinacao_raw)
    except (TypeError, ValueError):
        messages.error(request, "Informe TDS de referência e inclinação válidos.")
        return redirect(_url_calibracao_sensor(reservatorio, "tds"))

    _, _, erro_sessao = _obter_sessao_calibracao_pronta(
        ponto=ponto,
        sensor=SessaoCalibracao.SENSOR_TDS,
    )
    if erro_sessao:
        messages.error(request, erro_sessao)
        return redirect(_url_calibracao_sensor(reservatorio, "tds"))

    referencia_tds = _referencia_tds_para_calibracao(ponto)
    adc_tds = referencia_tds["adc_tds"]
    temperatura = referencia_tds["temperatura"]
    if adc_tds is None or temperatura is None:
        messages.error(request, "Nao ha leitura bruta completa (adc_tds/temperatura) para este ponto.")
        return redirect(_url_calibracao_sensor(reservatorio, "tds"))

    try:
        tds_base_ppm = calcular_tds_por_adc(adc_tds=adc_tds, temperatura=temperatura)
        ponto.atualizar_calibracao_tds(
            tds_base_ppm=tds_base_ppm,
            tds_alvo_ppm=tds_alvo,
            tds_adc=adc_tds,
            tds_inclinacao=tds_inclinacao,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_url_calibracao_sensor(reservatorio, "tds"))

    messages.success(
        request,
        (
            f"Calibração de TDS aplicada no ponto {_nome_curto_ponto(ponto)}: "
            f"média base {tds_base_ppm:.2f} ppm, alvo {tds_alvo:.2f} ppm."
        ),
    )
    return redirect(_url_calibracao_sensor(reservatorio, "tds"))


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_turbidez_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    ponto = _obter_ponto_calibracao_por_post(request, reservatorio)
    if ponto is None:
        return redirect(_url_calibracao_raiz(reservatorio))

    turbidez_alvo_raw = request.POST.get("turbidez_alvo_ntu")
    turbidez_inclinacao_raw = request.POST.get("turbidez_inclinacao")
    try:
        turbidez_alvo = float(turbidez_alvo_raw)
        turbidez_inclinacao = float(turbidez_inclinacao_raw)
    except (TypeError, ValueError):
        messages.error(request, "Informe turbidez de referência e inclinação válidas.")
        return redirect(_url_calibracao_sensor(reservatorio, "turbidez"))

    _, _, erro_sessao = _obter_sessao_calibracao_pronta(
        ponto=ponto,
        sensor=SessaoCalibracao.SENSOR_TURBIDEZ,
    )
    if erro_sessao:
        messages.error(request, erro_sessao)
        return redirect(_url_calibracao_sensor(reservatorio, "turbidez"))

    referencia_turbidez = _referencia_turbidez_para_calibracao(ponto)
    adc_turb = referencia_turbidez["adc_turb"]
    if adc_turb is None:
        messages.error(request, "Nao ha leitura bruta completa (adc_turb) para este ponto.")
        return redirect(_url_calibracao_sensor(reservatorio, "turbidez"))

    try:
        turbidez_base_ntu = calcular_turbidez_por_adc(adc_turb=adc_turb)
        ponto.atualizar_calibracao_turbidez(
            turbidez_base_ntu=turbidez_base_ntu,
            turbidez_alvo_ntu=turbidez_alvo,
            turbidez_adc=adc_turb,
            turbidez_inclinacao=turbidez_inclinacao,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_url_calibracao_sensor(reservatorio, "turbidez"))

    messages.success(
        request,
        (
            f"Calibração de turbidez aplicada no ponto {_nome_curto_ponto(ponto)}: "
            f"média base {turbidez_base_ntu:.3f} NTU, alvo {turbidez_alvo:.3f} NTU."
        ),
    )
    return redirect(_url_calibracao_sensor(reservatorio, "turbidez"))


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_ph_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    try:
        ph_solucao_ponto_1 = _normalizar_valor_referencia_generico(
            request.POST.get("ph_solucao_ponto_1"),
            campo="pH da solucao 1",
            minimo=0.0,
            maximo=14.0,
        )
        tensao_ponto_1 = _normalizar_valor_referencia_generico(
            request.POST.get("ph_tensao_ponto_1"),
            campo="tensao da solucao 1",
            minimo=0.0,
            maximo=ADC_TENSAO_REFERENCIA,
        )
        ph_solucao_ponto_2 = _normalizar_valor_referencia_generico(
            request.POST.get("ph_solucao_ponto_2"),
            campo="pH da solucao 2",
            minimo=0.0,
            maximo=14.0,
        )
        tensao_ponto_2 = _normalizar_valor_referencia_generico(
            request.POST.get("ph_tensao_ponto_2"),
            campo="tensao da solucao 2",
            minimo=0.0,
            maximo=ADC_TENSAO_REFERENCIA,
        )
    except (TypeError, ValueError):
        messages.error(request, "Preencha os dois pares de pH e tensao com valores validos.")
        return redirect(_url_calibracao_sensor(reservatorio, "ph"))

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        messages.error(request, "Ponto de calibracao nao encontrado.")
        return redirect(_url_calibracao_raiz(reservatorio))

    if math.isclose(ph_solucao_ponto_1, ph_solucao_ponto_2, rel_tol=0.0, abs_tol=1e-9):
        messages.error(request, "As solucoes de pH devem ter valores diferentes para recalcular a inclinacao.")
        return redirect(_url_calibracao_sensor(reservatorio, "ph"))

    ph_inclinacao = (tensao_ponto_2 - tensao_ponto_1) / (ph_solucao_ponto_1 - ph_solucao_ponto_2)
    if not math.isfinite(ph_inclinacao) or ph_inclinacao <= 0:
        messages.error(request, "Nao foi possivel calcular uma inclinacao valida com os dois pontos informados.")
        return redirect(_url_calibracao_sensor(reservatorio, "ph"))

    ph7_equivalente = tensao_ponto_1 + (ph_inclinacao * (ph_solucao_ponto_1 - 7.0))

    try:
        ponto.atualizar_calibracao_ph(
            ph_voltagem_referencia_7=ph7_equivalente,
            ph_inclinacao=ph_inclinacao,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_url_calibracao_sensor(reservatorio, "ph"))

    messages.success(
        request,
        (
            f"Calibracao de pH aplicada no ponto {_nome_curto_ponto(ponto)}: "
            f"ponto 1 {ph_solucao_ponto_1:.2f}/{tensao_ponto_1:.3f}V, "
            f"ponto 2 {ph_solucao_ponto_2:.2f}/{tensao_ponto_2:.3f}V."
        ),
    )
    return redirect(_url_calibracao_sensor(reservatorio, "ph"))


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_excluir(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    reservatorio.excluir_reservatorio()
    messages.success(request, "Reservatório removido.")
    return redirect("index")


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_resetar_leituras(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatório não encontrado.")
        return redirect("index")

    total_removido = reservatorio.resetar_leituras()
    messages.success(
        request,
        f"Leituras resetadas com sucesso. Registros removidos: {total_removido}.",
    )
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@require_http_methods(["GET", "POST"])
def entrar(request):
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "GET":
        return render(request, "auth/entrar.html")

    nome = request.POST.get("nome", "").strip()
    senha = request.POST.get("senha", "")
    if not nome or not senha:
        messages.error(request, "Preencha nome e senha.")
        return render(request, "auth/entrar.html", {"nome": nome})

    usuario = authenticate(request, username=nome, password=senha)
    if usuario is None:
        messages.error(request, "Credenciais inválidas.")
        return render(request, "auth/entrar.html", {"nome": nome})

    login(request, usuario)
    return redirect("index")


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def sair(request):
    logout(request)
    messages.success(request, "Você saiu da sessão.")
    return redirect("entrar")


@csrf_exempt
@require_http_methods(["POST"])
def esp32_leitura(request):
    try:
        payload = _carregar_payload_json(request.body)
    except IngestaoLeituraErro as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    reservatorio = _autenticar_esp32_reservatorio(
        reservatorio_id=payload.get("reservatorio_id"),
        token=request.headers.get("X-API-Token", ""),
    )
    if reservatorio is None:
        return JsonResponse({"erro": "nao autorizado"}, status=401)

    try:
        processar_leitura_esp32(request.body)
    except IngestaoLeituraErro as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    return JsonResponse({"ok": True}, status=201)


@csrf_exempt
@require_http_methods(["GET"])
def esp32_configuracao(request):
    reservatorio = _autenticar_esp32_reservatorio(
        reservatorio_id=request.GET.get("reservatorio_id"),
        token=request.headers.get("X-API-Token", ""),
    )
    if reservatorio is None:
        return JsonResponse({"erro": "nao autorizado"}, status=401)

    return JsonResponse(_montar_configuracao_esp32(reservatorio), status=200)


@csrf_exempt
@require_http_methods(["POST"])
def esp32_calibracao_amostra(request):
    try:
        payload = _carregar_payload_json(request.body)
    except IngestaoLeituraErro as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    reservatorio = _autenticar_esp32_reservatorio(
        reservatorio_id=payload.get("reservatorio_id"),
        token=request.headers.get("X-API-Token", ""),
    )
    if reservatorio is None:
        return JsonResponse({"erro": "nao autorizado"}, status=401)

    if "ponto_tipo" in payload:
        return JsonResponse({"erro": "campo nao suportado: ponto_tipo"}, status=400)

    try:
        sensor = SessaoCalibracao.normalizar_sensor(payload.get("sensor"))
    except ValueError:
        return JsonResponse({"erro": "campo invalido: sensor"}, status=400)

    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        return JsonResponse({"erro": "ponto de monitoramento invalido"}, status=400)

    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=sensor)
    if sessao is None:
        return JsonResponse({"erro": "sessao de calibracao inativa"}, status=409)

    sinais_brutos = payload.get("raw")
    if sinais_brutos is None:
        sinais_brutos = payload.get("sinais_brutos")
    if sinais_brutos is None:
        sinais_brutos = {}
    if not isinstance(sinais_brutos, dict):
        return JsonResponse({"erro": "campo invalido: raw"}, status=400)

    device_id = payload.get("device_id")
    if isinstance(device_id, str) and device_id.strip():
        sinais_brutos = {**sinais_brutos, "device_id": device_id.strip()[:80]}

    try:
        amostra = _registrar_amostra_calibracao(
            sessao=sessao,
            sensor=sensor,
            payload=payload,
            sinais_brutos=sinais_brutos,
        )
    except IngestaoLeituraErro as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    return JsonResponse({"ok": True, "amostra_id": amostra.id}, status=201)


def _autenticar_esp32_reservatorio(*, reservatorio_id, token):
    if reservatorio_id in (None, ""):
        return None

    reservatorio = Reservatorio.obter_por_id(reservatorio_id)
    if reservatorio is None:
        return None

    token_recebido = str(token or "")
    token_esperado = str(reservatorio.esp32_token_integracao or "")
    if not token_recebido or not token_esperado:
        return None
    if not secrets.compare_digest(token_recebido, token_esperado):
        return None
    return reservatorio


def _montar_configuracao_esp32(reservatorio):
    reservatorio.sincronizar_status_pelo_ponto()
    ponto = _obter_ponto_unico_calibracao(reservatorio)
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto) if ponto is not None else None
    alerta_sonoro = _resumo_alerta_sonoro_reservatorio(reservatorio)

    payload = {
        "server_epoch_ms": int(timezone.now().timestamp() * 1000),
        "poll_configuracao_ms": ESP32_CONFIG_POLL_INTERVALO_MS,
        "intervalo_normal_ms": int(reservatorio.esp32_intervalo_envio_normal_s) * 1000,
        "intervalo_calibracao_ms": int(reservatorio.esp32_intervalo_envio_calibracao_s) * 1000,
        "alerta_sonoro_ativo": alerta_sonoro["ativo"],
        "alerta_sonoro_intervalo_ligado_ms": ALERTA_SONORO_INTERVALO_LIGADO_MS,
        "alerta_sonoro_intervalo_desligado_ms": ALERTA_SONORO_INTERVALO_DESLIGADO_MS,
        "modo": "normal",
    }

    if sessao is None:
        return payload

    payload.update(
        {
            "modo": "calibracao",
            "sessao_id": sessao.id,
            "sensor": sessao.sensor,
            "qtd_amostras": sessao.qtd_amostras,
            "atraso_amostra_ms": sessao.atraso_amostra_ms,
            "expira_em": timezone.localtime(sessao.expira_em).isoformat(),
        }
    )
    return payload


def _normalizar_periodo_valor(valor):
    valor_normalizado = (valor or "").strip().lower()
    valores_validos = {item[0] for item in PERIODOS_DISPONIVEIS}
    if valor_normalizado in valores_validos:
        return valor_normalizado

    # Compatibilidade com links antigos (?dias=5, ?dias=30...)
    try:
        dias_legado = int(valor_normalizado)
    except (TypeError, ValueError):
        return PERIODO_PADRAO_VALOR

    valor_legado = f"{dias_legado}d"
    if valor_legado in valores_validos:
        return valor_legado
    return PERIODO_PADRAO_VALOR


def _delta_por_periodo(periodo_valor):
    unidade = periodo_valor[-1]
    quantidade = int(periodo_valor[:-1])

    if unidade == "m":
        return timedelta(minutes=quantidade)
    if unidade == "h":
        return timedelta(hours=quantidade)
    return timedelta(days=quantidade)


def _rotulo_periodo(periodo_valor):
    for valor, rotulo in PERIODOS_DISPONIVEIS:
        if valor == periodo_valor:
            return rotulo
    return "5 dias"


def _carregar_payload_json(request_body):
    if not request_body:
        raise IngestaoLeituraErro("payload vazio")

    try:
        payload = json.loads(request_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IngestaoLeituraErro("payload inválido") from exc

    if not isinstance(payload, dict):
        raise IngestaoLeituraErro("payload inválido")
    return payload


def _normalizar_sensor_calibracao(valor, *, padrao):
    sensor_normalizado = (valor or padrao or "").strip().lower()
    validos = {item["id"] for item in SENSORES_CALIBRACAO}
    if sensor_normalizado in validos:
        return sensor_normalizado
    return padrao


def _rotulo_sensor_calibracao(sensor):
    for item in SENSORES_CALIBRACAO:
        if item["id"] == sensor:
            return item["nome"]
    return "Sensor"


def _titulo_calibracao_ativa(*, ponto, sensor):
    return f"Calibrar {_rotulo_sensor_calibracao(sensor)}"


def _sensores_calibracao():
    return list(SENSORES_CALIBRACAO)


def _nome_curto_ponto(ponto):
    if ponto is None:
        return "desconhecido"
    return "ponto único"


def _obter_ponto_calibracao_por_post(request, reservatorio):
    ponto = _obter_ponto_unico_calibracao(reservatorio)
    if ponto is None:
        messages.error(request, "Ponto de calibracao nao encontrado.")
        return None
    return ponto


def _obter_ponto_unico_calibracao(reservatorio):
    reservatorio.garantir_pontos_monitoramento()
    return reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)


def _url_calibracao_raiz(reservatorio):
    return reverse("reservatorio_calibracao", args=[reservatorio.id])


def _url_calibracao_sensor(reservatorio, sensor, sensor_legado=None):
    sensor_final = sensor_legado or sensor
    return reverse(
        "reservatorio_calibracao_sensor",
        args=[reservatorio.id, sensor_final],
    )


def _redirect_calibracao_sensor(reservatorio, ponto, sensor):
    return redirect(_url_calibracao_sensor(reservatorio, sensor))


def _coletar_amostras_sessao(sessao, *, limite=LIMITE_AMOSTRAS_STATUS_CALIBRACAO):
    amostras = list(sessao.amostras.order_by("-coletada_em")[:limite])
    amostras.reverse()
    return amostras


def _mediana_valores(valores):
    valores_filtrados = [valor for valor in valores if valor is not None]
    if not valores_filtrados:
        return None
    return statistics.median(valores_filtrados)


def _media_valores(valores):
    valores_filtrados = [valor for valor in valores if valor is not None]
    if not valores_filtrados:
        return None
    return statistics.fmean(valores_filtrados)


def _desvio_valores(valores):
    valores_filtrados = [valor for valor in valores if valor is not None]
    if len(valores_filtrados) < 2:
        return None
    return statistics.pstdev(valores_filtrados)


def _limite_estabilidade_sensor(sensor):
    limites = {
        SessaoCalibracao.SENSOR_TEMPERATURA: DESVIO_MAXIMO_ESTAVEL_TEMPERATURA,
        SessaoCalibracao.SENSOR_TDS: DESVIO_MAXIMO_ESTAVEL_TDS_ADC,
        SessaoCalibracao.SENSOR_TURBIDEZ: DESVIO_MAXIMO_ESTAVEL_TURBIDEZ_ADC,
        SessaoCalibracao.SENSOR_PH: DESVIO_MAXIMO_ESTAVEL_PH_ADC,
    }
    return limites.get(sensor)


def _unidade_sensor(sensor):
    unidades = {
        SessaoCalibracao.SENSOR_TEMPERATURA: "C",
        SessaoCalibracao.SENSOR_TDS: "ppm",
        SessaoCalibracao.SENSOR_TURBIDEZ: "NTU",
        SessaoCalibracao.SENSOR_PH: "pH",
    }
    return unidades.get(sensor, "")


def _extrair_adc_da_amostra(amostra, sensor):
    if sensor == SessaoCalibracao.SENSOR_TDS:
        return amostra.adc_tds
    if sensor == SessaoCalibracao.SENSOR_TURBIDEZ:
        return amostra.adc_turb
    if sensor == SessaoCalibracao.SENSOR_PH:
        return amostra.adc_ph
    return None


def _valor_calibrado_amostra(*, ponto, sensor, amostra):
    temperatura_bruta = amostra.temperatura
    temperatura_calibrada = (
        ponto.aplicar_calibracao_temperatura(temperatura_bruta)
        if temperatura_bruta is not None
        else None
    )

    if sensor == SessaoCalibracao.SENSOR_TEMPERATURA:
        return temperatura_calibrada

    if sensor == SessaoCalibracao.SENSOR_TDS and amostra.adc_tds is not None and temperatura_calibrada is not None:
        base = calcular_tds_por_adc(adc_tds=amostra.adc_tds, temperatura=temperatura_calibrada)
        return max(0.0, (base * float(ponto.tds_inclinacao)) + float(ponto.tds_offset_ppm))

    if sensor == SessaoCalibracao.SENSOR_TURBIDEZ and amostra.adc_turb is not None:
        base = calcular_turbidez_por_adc(adc_turb=amostra.adc_turb)
        return max(0.0, (base * float(ponto.turbidez_inclinacao)) + float(ponto.turbidez_offset_ntu))

    if sensor == SessaoCalibracao.SENSOR_PH and amostra.adc_ph is not None and temperatura_calibrada is not None:
        return calcular_ph_por_adc(
            adc_ph=amostra.adc_ph,
            temperatura=temperatura_calibrada,
            ph_voltagem_referencia_7=ponto.ph_voltagem_referencia_7,
            ph_inclinacao=ponto.ph_inclinacao,
            ph_temperatura_calibracao_c=ponto.ph_temperatura_calibracao_c,
        )

    return None


def _snapshot_amostra_calibracao(*, ponto, sensor, amostra):
    adc = _extrair_adc_da_amostra(amostra, sensor)
    tensao = (adc * ADC_TENSAO_REFERENCIA / ADC_VALOR_MAXIMO) if adc is not None else None
    temperatura_bruta = amostra.temperatura
    temperatura_calibrada = (
        ponto.aplicar_calibracao_temperatura(temperatura_bruta)
        if temperatura_bruta is not None
        else None
    )
    valor_calibrado = _valor_calibrado_amostra(ponto=ponto, sensor=sensor, amostra=amostra)
    return {
        "coletada_em": timezone.localtime(amostra.coletada_em).isoformat(),
        "adc": adc,
        "tensao": tensao,
        "temperatura_bruta": temperatura_bruta,
        "temperatura_calibrada": temperatura_calibrada,
        "valor_calibrado": valor_calibrado,
    }


def _resumo_sessao_calibracao(*, ponto, sensor):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=sensor)
    if sessao is None:
        return {
            "ativa": False,
            "sensor": sensor,
            "sensor_nome": _rotulo_sensor_calibracao(sensor),
            "amostras": 0,
            "sessao_id": None,
            "status": "inativa",
            "dados_fluxo": {},
            "ultima_amostra": None,
            "medias": {},
            "medianas": {},
            "serie": [],
            "cursor": _cursor_sessao_calibracao_inativa(sensor),
            "intervalo_poll_ms": None,
            "estabilidade_sensor": {"disponivel": False, "estavel": False, "desvio": None},
            "estabilidade_temperatura": {"disponivel": False, "estavel": False, "desvio": None},
        }

    amostras = _coletar_amostras_sessao(sessao)
    snapshots = [_snapshot_amostra_calibracao(ponto=ponto, sensor=sensor, amostra=amostra) for amostra in amostras]
    adcs = [item["adc"] for item in snapshots]
    temperaturas_brutas = [item["temperatura_bruta"] for item in snapshots]
    temperaturas_calibradas = [item["temperatura_calibrada"] for item in snapshots]
    valores_calibrados = [item["valor_calibrado"] for item in snapshots]
    tensãoes = [item["tensao"] for item in snapshots]

    desvio_sensor = _desvio_valores(adcs if sensor != SessaoCalibracao.SENSOR_TEMPERATURA else temperaturas_brutas)
    limite_sensor = _limite_estabilidade_sensor(sensor)
    desvio_temperatura = _desvio_valores(temperaturas_brutas)
    temperatura_disponivel = sensor in {SessaoCalibracao.SENSOR_TEMPERATURA, SessaoCalibracao.SENSOR_TDS, SessaoCalibracao.SENSOR_PH}
    desvio_sensor_exibicao = _desvio_valores(
        temperaturas_calibradas if sensor == SessaoCalibracao.SENSOR_TEMPERATURA else valores_calibrados
    )

    return {
        "ativa": True,
        "sensor": sensor,
        "sensor_nome": _rotulo_sensor_calibracao(sensor),
        "amostras": len(amostras),
        "sessao_id": sessao.id,
        "status": sessao.status,
        "dados_fluxo": sessao.dados_fluxo if isinstance(sessao.dados_fluxo, dict) else {},
        "cursor": _cursor_sessao_calibracao_ativa(sessao),
        "intervalo_poll_ms": sessao.intervalo_envio_ms,
        "iniciada_em": timezone.localtime(sessao.iniciada_em).isoformat(),
        "expira_em": timezone.localtime(sessao.expira_em).isoformat(),
        "ultima_amostra_em": timezone.localtime(sessao.ultima_amostra_em).isoformat() if sessao.ultima_amostra_em else None,
        "ultima_amostra": snapshots[-1] if snapshots else None,
        "medias": {
            "adc": _media_valores(adcs),
            "tensao": _media_valores(tensãoes),
            "temperatura_bruta": _media_valores(temperaturas_brutas),
            "temperatura_calibrada": _media_valores(temperaturas_calibradas),
            "valor_calibrado": _media_valores(valores_calibrados),
        },
        "medianas": {
            "adc": _mediana_valores(adcs),
            "tensao": _mediana_valores(tensãoes),
            "temperatura_bruta": _mediana_valores(temperaturas_brutas),
            "temperatura_calibrada": _mediana_valores(temperaturas_calibradas),
            "valor_calibrado": _mediana_valores(valores_calibrados),
        },
        "serie": snapshots,
        "parametros": {
            "temperatura_inclinacao": ponto.temperatura_inclinacao,
            "temperatura_offset_c": ponto.temperatura_offset_c,
            "ph_inclinacao": ponto.ph_inclinacao,
            "ph_voltagem_referencia_7": ponto.ph_voltagem_referencia_7,
            "ph_temperatura_calibracao_c": ponto.ph_temperatura_calibracao_c,
            "tds_inclinacao": ponto.tds_inclinacao,
            "tds_offset_ppm": ponto.tds_offset_ppm,
            "turbidez_inclinacao": ponto.turbidez_inclinacao,
            "turbidez_offset_ntu": ponto.turbidez_offset_ntu,
        },
        "estabilidade_sensor": {
            "disponivel": desvio_sensor is not None,
            "estavel": (desvio_sensor is not None and limite_sensor is not None and desvio_sensor <= limite_sensor),
            "desvio": desvio_sensor,
            "desvio_exibicao": desvio_sensor_exibicao,
            "limite": limite_sensor,
            "unidade": _unidade_sensor(sensor),
        },
        "estabilidade_temperatura": {
            "disponivel": temperatura_disponivel and desvio_temperatura is not None,
            "estavel": temperatura_disponivel and desvio_temperatura is not None and desvio_temperatura <= DESVIO_MAXIMO_ESTAVEL_TEMPERATURA,
            "desvio": desvio_temperatura if temperatura_disponivel else None,
            "limite": DESVIO_MAXIMO_ESTAVEL_TEMPERATURA if temperatura_disponivel else None,
        },
    }


def _cursor_sessao_calibracao_inativa(sensor):
    return f"inativa:{sensor}"


def _cursor_sessao_calibracao_ativa(sessao):
    atualizado_em = timezone.localtime(sessao.updated_at).isoformat() if sessao.updated_at else ""
    ultima_amostra_em = timezone.localtime(sessao.ultima_amostra_em).isoformat() if sessao.ultima_amostra_em else ""
    return f"ativa:{sessao.id}:{atualizado_em}:{ultima_amostra_em}"


def _cursor_sessao_calibracao_atual(*, ponto, sensor):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=sensor)
    if sessao is None:
        return _cursor_sessao_calibracao_inativa(sensor)
    return _cursor_sessao_calibracao_ativa(sessao)


def _normalizar_wait_status_calibracao_ms(valor, *, intervalo_padrao_ms):
    try:
        wait_ms = int(valor)
    except (TypeError, ValueError):
        wait_ms = int(intervalo_padrao_ms or 0)

    wait_ms = max(0, wait_ms)
    return min(wait_ms, CALIBRACAO_STATUS_LONG_POLL_MAX_MS)


def _aguardar_atualizacao_status_calibracao(*, ponto, sensor, cursor_atual, wait_ms):
    prazo_final = time.monotonic() + (wait_ms / 1000.0)
    while time.monotonic() < prazo_final:
        if _cursor_sessao_calibracao_atual(ponto=ponto, sensor=sensor) != cursor_atual:
            return
        time.sleep(CALIBRACAO_STATUS_LONG_POLL_SLEEP_MS)


def _temperatura_bruta_para_calibracao(ponto):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=SessaoCalibracao.SENSOR_TEMPERATURA)
    if sessao is None:
        return _ultima_temperatura_bruta_por_ponto(ponto)
    return _mediana_valores([amostra.temperatura for amostra in _coletar_amostras_sessao(sessao)])


def _referencia_tds_para_calibracao(ponto):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=SessaoCalibracao.SENSOR_TDS)
    if sessao is None:
        return _ultimos_dados_agua_por_ponto(ponto)
    amostras = _coletar_amostras_sessao(sessao)
    return {
        "adc_tds": _mediana_valores([amostra.adc_tds for amostra in amostras]),
        "temperatura": _mediana_valores([
            ponto.aplicar_calibracao_temperatura(amostra.temperatura)
            for amostra in amostras
            if amostra.temperatura is not None
        ]),
        "resumo": _resumo_sessao_calibracao(ponto=ponto, sensor=SessaoCalibracao.SENSOR_TDS),
    }


def _referencia_turbidez_para_calibracao(ponto):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=SessaoCalibracao.SENSOR_TURBIDEZ)
    if sessao is None:
        return _ultimos_dados_agua_por_ponto(ponto)
    amostras = _coletar_amostras_sessao(sessao)
    return {
        "adc_turb": _mediana_valores([amostra.adc_turb for amostra in amostras]),
        "resumo": _resumo_sessao_calibracao(ponto=ponto, sensor=SessaoCalibracao.SENSOR_TURBIDEZ),
    }


def _tensao_ph_para_calibracao(ponto):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=SessaoCalibracao.SENSOR_PH)
    if sessao is None:
        return _ultima_tensao_ph_por_ponto(ponto)
    amostras = _coletar_amostras_sessao(sessao)
    adc_mediano = _mediana_valores([amostra.adc_ph for amostra in amostras])
    if adc_mediano is None:
        return None
    return (adc_mediano * ADC_TENSAO_REFERENCIA) / ADC_VALOR_MAXIMO


def _sensor_exige_estabilidade_temperatura(sensor):
    return sensor in {
        SessaoCalibracao.SENSOR_TDS,
        SessaoCalibracao.SENSOR_PH,
    }


def _obter_sessao_calibracao_pronta(*, ponto, sensor):
    sessao = SessaoCalibracao.obter_ativa(ponto=ponto, sensor=sensor)
    if sessao is None:
        return None, None, "Inicie a sessão de calibração e aguarde amostras suficientes."

    resumo = _resumo_sessao_calibracao(ponto=ponto, sensor=sensor)
    if not resumo["estabilidade_sensor"]["estavel"]:
        return sessao, resumo, "A estabilidade do sensor ainda nao esta pronta para confirmar a calibracao."

    if _sensor_exige_estabilidade_temperatura(sensor) and not resumo["estabilidade_temperatura"]["estavel"]:
        return sessao, resumo, "A temperatura ainda nao esta estavel para confirmar a calibracao."

    return sessao, resumo, None


def _normalizar_valor_referencia_generico(valor, *, campo, minimo=None, maximo=None):
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{campo} inválido.") from exc

    if not math.isfinite(numero):
        raise ValueError(f"{campo} inválido.")
    if minimo is not None and numero < minimo:
        raise ValueError(f"{campo} deve ser maior ou igual a {minimo}.")
    if maximo is not None and numero > maximo:
        raise ValueError(f"{campo} deve ser menor ou igual a {maximo}.")
    return numero


def _extrair_float_json(payload, campo, *, obrigatorio=False):
    valor = payload.get(campo)
    if valor is None:
        if obrigatorio:
            raise IngestaoLeituraErro(f"campo obrigatorio: {campo}")
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc
    if not math.isfinite(numero):
        raise IngestaoLeituraErro(f"campo invalido: {campo}")
    return numero


def _extrair_int_json(payload, campo, *, obrigatorio=False):
    valor = payload.get(campo)
    if valor is None:
        if obrigatorio:
            raise IngestaoLeituraErro(f"campo obrigatorio: {campo}")
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise IngestaoLeituraErro(f"campo invalido: {campo}") from exc
    if not math.isfinite(numero) or not numero.is_integer():
        raise IngestaoLeituraErro(f"campo invalido: {campo}")
    return int(numero)


def _registrar_amostra_calibracao(*, sessao, sensor, payload, sinais_brutos):
    temperatura = _extrair_float_json(payload, "temperatura", obrigatorio=sensor != SessaoCalibracao.SENSOR_TURBIDEZ)
    raw = sinais_brutos
    if sensor == SessaoCalibracao.SENSOR_TEMPERATURA:
        adc_tds = None
        adc_turb = None
        adc_ph = None
    elif sensor == SessaoCalibracao.SENSOR_TDS:
        adc_tds = _extrair_int_json(raw, "adc_tds", obrigatorio=True)
        adc_turb = None
        adc_ph = None
    elif sensor == SessaoCalibracao.SENSOR_TURBIDEZ:
        adc_turb = _extrair_int_json(raw, "adc_turb", obrigatorio=True)
        adc_tds = None
        adc_ph = None
    else:
        adc_ph = _extrair_int_json(raw, "adc_ph", obrigatorio=True)
        adc_tds = None
        adc_turb = None

    amostra = AmostraCalibracao.objects.create(
        sessao=sessao,
        temperatura=temperatura,
        adc_tds=adc_tds,
        adc_turb=adc_turb,
        adc_ph=adc_ph,
        firmware_ts_ms=_extrair_int_json(raw, "firmware_ts_ms", obrigatorio=False),
        sinais_brutos=raw,
    )
    sessao.ultima_amostra_em = amostra.coletada_em
    sessao.save(update_fields=["ultima_amostra_em", "updated_at"])
    return amostra


def _medias_vazias():
    return {
        "temperatura": None,
        "tds": None,
        "turbidez": None,
        "ph": None,
    }


def _contexto_calibracao_reservatorio(reservatorio, *, ponto_unico):
    return {
        "reservatorio": reservatorio,
        "ponto_unico": ponto_unico,
        "temperatura_calibracao": _resumo_calibracao_temperatura(ponto_unico),
        "tds_calibracao": _resumo_calibracao_tds(ponto_unico),
        "turbidez_calibracao": _resumo_calibracao_turbidez(ponto_unico),
        "ph_calibracao": _resumo_calibracao_ph(ponto_unico),
    }


def _resumo_alerta_sonoro_reservatorio(reservatorio):
    ativo = reservatorio.alerta_sonoro_deve_apitar
    em_perigo = reservatorio.status == Reservatorio.STATUS_PERIGO
    silenciado = em_perigo and reservatorio.alerta_sonoro_silenciado

    if ativo:
        rotulo = "Apitando"
        classe_status = "status-perigo"
    elif silenciado:
        rotulo = "Silenciado"
        classe_status = "status-atencao"
    else:
        rotulo = "Desligado"
        classe_status = "status-sem-dado"

    return {
        "ativo": ativo,
        "em_perigo": em_perigo,
        "silenciado": silenciado,
        "rotulo": rotulo,
        "classe_status": classe_status,
        "texto_acao": "Silenciar alerta" if ativo else "Reativar alerta",
    }


def _contexto_detalhe_reservatorio(reservatorio):
    reservatorio.garantir_pontos_monitoramento()
    reservatorio.sincronizar_status_pelo_ponto()

    ponto_unico = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_UNICO)
    series = _series_leituras_por_ponto(ponto_unico)

    return {
        **_contexto_calibracao_reservatorio(
            reservatorio,
            ponto_unico=ponto_unico,
        ),
        "tds_series": series["tds"],
        "temperatura_series": series["temperatura"],
        "turbidez_series": series["turbidez"],
        "ph_series": series["ph"],
        "metricas_recentes": _metricas_recentes_reservatorio(
            reservatorio,
            ponto_unico=ponto_unico,
        ),
        "alerta_sonoro": _resumo_alerta_sonoro_reservatorio(reservatorio),
    }


def _contexto_edicao_reservatorio(reservatorio):
    reservatorio.garantir_pontos_monitoramento()
    return {"reservatorio": reservatorio}


def _montar_dashboard_cards(reservatorios, periodo_delta):
    if not reservatorios:
        return []

    medias_por_chave = _mapear_medias_por_reservatorio(
        reservatorio_ids=[item.id for item in reservatorios],
        inicio_periodo=timezone.now() - periodo_delta,
    )
    return [
        _montar_dashboard_card_reservatorio(
            reservatorio,
            medias_por_chave=medias_por_chave,
        )
        for reservatorio in reservatorios
    ]


def _montar_relatorio_periodos_reservatorio(reservatorio):
    cards = []
    for periodo_valor, periodo_rotulo in PERIODOS_DISPONIVEIS:
        medias_por_chave = _mapear_medias_por_reservatorio(
            reservatorio_ids=[reservatorio.id],
            inicio_periodo=timezone.now() - _delta_por_periodo(periodo_valor),
        )
        cards.append(
            {
                **_montar_dashboard_card_reservatorio(
                    reservatorio,
                    medias_por_chave=medias_por_chave,
                ),
                "periodo_valor": periodo_valor,
                "periodo_rotulo": periodo_rotulo,
            }
        )
    return cards


def _mapear_medias_por_reservatorio(*, reservatorio_ids, inicio_periodo):
    medias_por_chave = {}
    agregados = (
        LeituraQualidade.objects.filter(
            ponto__reservatorio_id__in=reservatorio_ids,
            data_hora__gte=inicio_periodo,
        )
        .values("ponto__reservatorio_id")
        .annotate(
            media_temperatura=Avg("temperatura"),
            media_tds=Avg("tds"),
            media_turbidez=Avg("turbidez"),
            media_ph=Avg("ph"),
        )
    )

    for item in agregados:
        medias_por_chave[item["ponto__reservatorio_id"]] = {
            "temperatura": item["media_temperatura"],
            "tds": item["media_tds"],
            "turbidez": item["media_turbidez"],
            "ph": item["media_ph"],
        }

    return medias_por_chave


def _montar_dashboard_card_reservatorio(reservatorio, *, medias_por_chave):
    medias_ponto = medias_por_chave.get(reservatorio.id, _medias_vazias())

    return {
        "reservatorio": reservatorio,
        "ponto_unico": medias_ponto,
        "status_ponto_unico": _status_metricas_por_faixa(
            medias_ponto,
            reservatorio=reservatorio,
        ),
    }


def _status_metricas_por_faixa(medias, *, reservatorio):
    return {
        "temperatura": _status_media_temperatura(
            medias.get("temperatura"),
            minimo=reservatorio.faixa_celsius_temperatura_min,
            maximo=reservatorio.faixa_celsius_temperatura_max,
        ),
        "tds": _status_media_tds(
            medias.get("tds"),
            minimo=reservatorio.faixa_ppm_tds_min,
            maximo=reservatorio.faixa_ppm_tds_max,
        ),
        "turbidez": _status_media_turbidez(
            medias.get("turbidez"),
            minimo=reservatorio.faixa_ntu_turbidez_min,
            maximo=reservatorio.faixa_ntu_turbidez_max,
        ),
        "ph": _status_media_ph(
            medias.get("ph"),
            minimo=reservatorio.faixa_ph_min,
            maximo=reservatorio.faixa_ph_max,
        ),
    }


def _status_media_temperatura(valor, *, minimo, maximo):
    if valor is None:
        return STATUS_SEM_DADO

    return classificar_status_por_faixa(
        valor,
        minimo=minimo,
        maximo=maximo,
        margem_atencao=DESVIO_TEMPERATURA_ATENCAO,
        margem_perigo=DESVIO_TEMPERATURA_PERIGO,
    )


def _status_media_tds(valor, *, minimo, maximo):
    if valor is None:
        return STATUS_SEM_DADO

    return classificar_status_por_faixa(
        valor,
        minimo=minimo,
        maximo=maximo,
        margem_atencao=0.0,
        margem_perigo=maximo * (FATOR_PERIGO_TDS - 1.0),
    )


def _status_media_turbidez(valor, *, minimo, maximo):
    if valor is None:
        return STATUS_SEM_DADO

    return classificar_status_por_faixa(
        valor,
        minimo=minimo,
        maximo=maximo,
        margem_atencao=0.0,
        margem_perigo=maximo * (FATOR_PERIGO_TURBIDEZ - 1.0),
    )


def _status_media_ph(valor, *, minimo, maximo):
    if valor is None:
        return STATUS_SEM_DADO

    return classificar_status_por_faixa(
        valor,
        minimo=minimo,
        maximo=maximo,
        margem_atencao=DESVIO_PH_ATENCAO,
        margem_perigo=DESVIO_PH_PERIGO,
    )


def _series_leituras_por_ponto(ponto):
    if ponto is None:
        return {"tds": [], "temperatura": [], "turbidez": [], "ph": []}

    # Limita a janela para evitar payload/render excessivo não frontend.
    leituras = list(
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")[:MAX_PONTOS_GRAFICO]
    )
    leituras.reverse()

    tds = []
    temperatura = []
    turbidez = []
    ph = []
    for leitura in leituras:
        data_hora_local = timezone.localtime(leitura.data_hora)
        x_timestamp_ms = int(data_hora_local.timestamp() * 1000)
        x_label = data_hora_local.strftime("%d/%m/%Y %H:%M:%S")
        tds.append({"x": x_timestamp_ms, "y": leitura.tds, "label": x_label})
        temperatura.append({"x": x_timestamp_ms, "y": leitura.temperatura, "label": x_label})
        turbidez.append({"x": x_timestamp_ms, "y": leitura.turbidez, "label": x_label})
        ph.append({"x": x_timestamp_ms, "y": leitura.ph, "label": x_label})

    return {
        "tds": tds,
        "temperatura": temperatura,
        "turbidez": turbidez,
        "ph": ph,
    }


def _metricas_recentes_reservatorio(reservatorio, *, ponto_unico):
    ultima_leitura = _ultima_leitura_qualidade_por_ponto(ponto_unico)

    return [
        {
            "id": metrica_id,
            "nome": nome,
            "unidade": unidade,
            "casas": casas,
            "ponto_unico": _snapshot_metrica_recente(
                ultima_leitura,
                metrica_id=metrica_id,
                reservatorio=reservatorio,
            ),
        }
        for metrica_id, nome, unidade, casas in METRICAS_DETALHE_RECENTES
    ]


def _ultima_leitura_qualidade_por_ponto(ponto):
    if ponto is None:
        return None

    return (
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora", "-id")
        .first()
    )


def _snapshot_metrica_recente(leitura, *, metrica_id, reservatorio):
    if leitura is None:
        return _snapshot_metrica_sem_dado()

    valor = getattr(leitura, metrica_id, None)
    if valor is None:
        return _snapshot_metrica_sem_dado(leitura=leitura)

    status = _status_metricas_por_faixa(
        {metrica_id: valor},
        reservatorio=reservatorio,
    )[metrica_id]

    data_hora_local = timezone.localtime(leitura.data_hora)
    return {
        "valor": float(valor),
        "status": status,
        "status_label": _rotulo_status_metrica(status),
        "data_hora": data_hora_local.strftime("%d/%m/%Y %H:%M:%S"),
    }


def _snapshot_metrica_sem_dado(leitura=None):
    data_hora = None
    if leitura is not None:
        data_hora = timezone.localtime(leitura.data_hora).strftime("%d/%m/%Y %H:%M:%S")

    return {
        "valor": None,
        "status": STATUS_SEM_DADO,
        "status_label": _rotulo_status_metrica(STATUS_SEM_DADO),
        "data_hora": data_hora,
    }


def _rotulo_status_metrica(status):
    if status == STATUS_SEM_DADO:
        return "Sem dado"

    return dict(Reservatorio.STATUS_CHOICES).get(status, "Sem dado")


def _resumo_calibracao_ph(ponto):
    ultima_tensao = _ultima_tensao_ph_por_ponto(ponto)
    ultima_temperatura = _ultima_temperatura_calibrada_por_ponto(ponto)

    if ponto is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_tensao": ultima_tensao,
            "ultima_temperatura": ultima_temperatura,
        }

    calibrado_em = ponto.ph_calibrado_em
    if calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_tensao": ultima_tensao,
            "ultima_temperatura": ultima_temperatura,
        }

    agora = timezone.now()
    delta = agora - calibrado_em
    dias = max(0, delta.days)
    return {
        "calibrado_em": calibrado_em,
        "dias": dias,
        "vencida": dias >= DIAS_ALERTA_CALIBRACAO_PH,
        "ultima_tensao": ultima_tensao,
        "ultima_temperatura": ultima_temperatura,
    }


def _resumo_calibracao_tds(ponto):
    dados_agua = _ultimos_dados_agua_por_ponto(ponto)
    if ponto is None or ponto.tds_calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            **dados_agua,
        }

    dias = max(0, (timezone.now() - ponto.tds_calibrado_em).days)
    return {
        "calibrado_em": ponto.tds_calibrado_em,
        "dias": dias,
        "vencida": dias >= DIAS_ALERTA_CALIBRACAO_AGUA,
        **dados_agua,
    }


def _resumo_calibracao_turbidez(ponto):
    dados_agua = _ultimos_dados_agua_por_ponto(ponto)
    if ponto is None or ponto.turbidez_calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            **dados_agua,
        }

    dias = max(0, (timezone.now() - ponto.turbidez_calibrado_em).days)
    return {
        "calibrado_em": ponto.turbidez_calibrado_em,
        "dias": dias,
        "vencida": dias >= DIAS_ALERTA_CALIBRACAO_AGUA,
        **dados_agua,
    }


def _ultima_tensao_ph_por_ponto(ponto):
    if ponto is None:
        return None

    ultima_leitura = (
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")
        .only("sinais_brutos")
        .first()
    )
    if ultima_leitura is None:
        return None

    sinais = ultima_leitura.sinais_brutos if isinstance(ultima_leitura.sinais_brutos, dict) else {}
    return _resolver_tensao_em_sinais_brutos(sinais)


def _ultimos_dados_agua_por_ponto(ponto):
    vazio = {
        "temperatura": None,
        "adc_tds": None,
        "adc_turb": None,
        "tds_estimado_ppm": None,
        "turbidez_estimada_ntu": None,
    }
    if ponto is None:
        return vazio

    ultima_leitura = (
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")
        .only("temperatura", "sinais_brutos")
        .first()
    )
    if ultima_leitura is None:
        return vazio

    sinais = ultima_leitura.sinais_brutos if isinstance(ultima_leitura.sinais_brutos, dict) else {}
    adc_tds = _resolver_adc_em_sinais_brutos(sinais, aliases=("adc_tds", "tds_adc"))
    adc_turb = _resolver_adc_em_sinais_brutos(
        sinais,
        aliases=("adc_turb", "adc_turbidez", "turbidez_adc"),
    )
    temperatura = float(ultima_leitura.temperatura)
    tds_estimado_ppm = None
    turbidez_estimada_ntu = None

    if adc_tds is not None:
        try:
            tds_estimado_ppm = calcular_tds_por_adc(adc_tds=adc_tds, temperatura=temperatura)
        except ValueError:
            tds_estimado_ppm = None
    if adc_turb is not None:
        try:
            turbidez_estimada_ntu = calcular_turbidez_por_adc(adc_turb=adc_turb)
        except ValueError:
            turbidez_estimada_ntu = None

    return {
        "temperatura": temperatura,
        "adc_tds": adc_tds,
        "adc_turb": adc_turb,
        "tds_estimado_ppm": tds_estimado_ppm,
        "turbidez_estimada_ntu": turbidez_estimada_ntu,
    }


def _resumo_calibracao_temperatura(ponto):
    ultima_temperatura_bruta = _ultima_temperatura_bruta_por_ponto(ponto)
    ultima_temperatura_calibrada = _ultima_temperatura_calibrada_por_ponto(ponto)

    if ponto is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_temperatura_bruta": ultima_temperatura_bruta,
            "ultima_temperatura_calibrada": ultima_temperatura_calibrada,
        }

    calibrado_em = ponto.temperatura_calibrado_em
    if calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_temperatura_bruta": ultima_temperatura_bruta,
            "ultima_temperatura_calibrada": ultima_temperatura_calibrada,
        }

    agora = timezone.now()
    delta = agora - calibrado_em
    dias = max(0, delta.days)
    return {
        "calibrado_em": calibrado_em,
        "dias": dias,
        "vencida": dias >= DIAS_ALERTA_CALIBRACAO_AGUA,
        "ultima_temperatura_bruta": ultima_temperatura_bruta,
        "ultima_temperatura_calibrada": ultima_temperatura_calibrada,
    }


def _ultima_temperatura_bruta_por_ponto(ponto):
    if ponto is None:
        return None

    ultima_leitura = (
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")
        .only("temperatura", "sinais_brutos")
        .first()
    )
    if ultima_leitura is None:
        return None

    sinais = ultima_leitura.sinais_brutos if isinstance(ultima_leitura.sinais_brutos, dict) else {}
    temperatura_bruta = _resolver_valor_em_sinais_brutos(
        sinais,
        aliases=("temperatura_bruta",),
        normalizador=_normalizar_temperatura,
    )
    if temperatura_bruta is not None:
        return temperatura_bruta
    return float(ultima_leitura.temperatura)


def _ultima_temperatura_calibrada_por_ponto(ponto):
    if ponto is None:
        return None

    ultima_leitura = (
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")
        .only("temperatura")
        .first()
    )
    if ultima_leitura is None:
        return None
    return float(ultima_leitura.temperatura)


def _resolver_tensao_em_sinais_brutos(sinais):
    ph_tensao = _resolver_valor_em_sinais_brutos(
        sinais,
        aliases=("ph_tensao",),
        normalizador=_normalizar_tensao,
    )
    if ph_tensao is not None:
        return ph_tensao

    adc_ph = _resolver_adc_em_sinais_brutos(sinais, aliases=("adc_ph", "ph_adc"))
    if adc_ph is not None:
        return (adc_ph * ADC_TENSAO_REFERENCIA) / ADC_VALOR_MAXIMO

    return None


def _resolver_adc_em_sinais_brutos(sinais, *, aliases):
    return _resolver_valor_em_sinais_brutos(
        sinais,
        aliases=aliases,
        normalizador=_normalizar_adc,
    )


def _resolver_valor_em_sinais_brutos(sinais, *, aliases, normalizador):
    if not isinstance(sinais, dict):
        return None

    for alias in aliases:
        valor = normalizador(sinais.get(alias))
        if valor is not None:
            return valor

    bruto_aninhado = sinais.get("raw")
    if isinstance(bruto_aninhado, dict):
        return _resolver_valor_em_sinais_brutos(
            bruto_aninhado,
            aliases=aliases,
            normalizador=normalizador,
        )

    return None


def _normalizar_tensao(valor):
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero) or numero < 0:
        return None
    return numero


def _normalizar_temperatura(valor):
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero) or numero < -50 or numero > 150:
        return None
    return numero


def _normalizar_adc(valor):
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero) or not numero.is_integer():
        return None

    inteiro = int(numero)
    if inteiro < 0 or inteiro > ADC_VALOR_MAXIMO:
        return None
    return inteiro
