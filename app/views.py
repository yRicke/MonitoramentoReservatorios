from datetime import timedelta
import math

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio
from app.services.ingestao import (
    ADC_TENSAO_REFERENCIA,
    ADC_VALOR_MAXIMO,
    IngestaoLeituraErro,
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
        messages.error(request, "Ja existe reservatorio com este nome.")
        return redirect("index")

    messages.success(request, "Reservatorio adicionado.")
    return redirect("index")


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def reservatorio_detalhe(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    reservatorio.garantir_pontos_monitoramento()

    ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
    ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

    series_antes = _series_leituras_por_ponto(ponto_antes)
    series_depois = _series_leituras_por_ponto(ponto_depois)

    return render(
        request,
        "reservatorio/detalhe.html",
        {
            "reservatorio": reservatorio,
            "ponto_antes": ponto_antes,
            "ponto_depois": ponto_depois,
            "ph_calibracao_antes": _resumo_calibracao_ph(ponto_antes),
            "ph_calibracao_depois": _resumo_calibracao_ph(ponto_depois),
            "agua_calibracao_antes": _resumo_calibracao_agua(ponto_antes),
            "agua_calibracao_depois": _resumo_calibracao_agua(ponto_depois),
            "tds_series_antes": series_antes["tds"],
            "tds_series_depois": series_depois["tds"],
            "temperatura_series_antes": series_antes["temperatura"],
            "temperatura_series_depois": series_depois["temperatura"],
            "turbidez_series_antes": series_antes["turbidez"],
            "turbidez_series_depois": series_depois["turbidez"],
            "ph_series_antes": series_antes["ph"],
            "ph_series_depois": series_depois["ph"],
        },
    )


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_atualizar(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
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
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)
    except IntegrityError:
        messages.error(request, "Ja existe reservatorio com este nome.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    messages.success(request, "Reservatorio atualizado.")
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_ph_atualizar(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    reservatorio.garantir_pontos_monitoramento()
    ponto_antes = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_ANTES)
    ponto_depois = reservatorio.obter_ponto_monitoramento(PontoMonitoramento.TIPO_DEPOIS)

    ph7_antes = request.POST.get("ph7_antes")
    ph7_depois = request.POST.get("ph7_depois")
    inclinacao_antes = request.POST.get("inclinacao_antes")
    inclinacao_depois = request.POST.get("inclinacao_depois")

    if not all([ph7_antes, ph7_depois, inclinacao_antes, inclinacao_depois]):
        messages.error(request, "Preencha todos os campos de calibracao de pH.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    try:
        if ponto_antes is not None:
            ponto_antes.atualizar_calibracao_ph(
                ph_voltagem_referencia_7=ph7_antes,
                ph_inclinacao=inclinacao_antes,
            )

        if ponto_depois is not None:
            ponto_depois.atualizar_calibracao_ph(
                ph_voltagem_referencia_7=ph7_depois,
                ph_inclinacao=inclinacao_depois,
            )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    messages.success(request, "Calibracao de pH atualizada por ponto.")
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_ph_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    ponto_tipo = request.POST.get("ponto_tipo")
    ph_solucao_raw = request.POST.get("ph_solucao", "7")
    try:
        ponto_tipo_normalizado = PontoMonitoramento.normalizar_tipo(ponto_tipo)
    except ValueError:
        messages.error(request, "Ponto de calibracao invalido.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    try:
        ph_solucao = float(ph_solucao_raw)
    except (TypeError, ValueError):
        messages.error(request, "pH da solucao invalido.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    if not math.isfinite(ph_solucao) or ph_solucao < 0 or ph_solucao > 14:
        messages.error(request, "pH da solucao deve estar entre 0 e 14.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    reservatorio.garantir_pontos_monitoramento()
    ponto = reservatorio.obter_ponto_monitoramento(ponto_tipo_normalizado)
    if ponto is None:
        messages.error(request, "Ponto de calibracao nao encontrado.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    ultima_tensao = _ultima_tensao_ph_por_ponto(ponto)
    if ultima_tensao is None:
        messages.error(request, "Nao ha voltagem de pH na ultima leitura deste ponto.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    ph7_equivalente = ultima_tensao + (ponto.ph_inclinacao * (ph_solucao - 7.0))
    try:
        ponto.atualizar_calibracao_ph(ph_voltagem_referencia_7=ph7_equivalente)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    nome_ponto = "antes" if ponto.tipo == PontoMonitoramento.TIPO_ANTES else "depois"
    messages.success(
        request,
        (
            f"Calibracao automatica aplicada no ponto {nome_ponto}: "
            f"solucao pH {ph_solucao:.2f}, leitura {ultima_tensao:.3f}V, "
            f"Vref pH7 ajustada para {ph7_equivalente:.3f}V."
        ),
    )
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_calibracao_agua_auto(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    ponto_tipo = request.POST.get("ponto_tipo")
    try:
        ponto_tipo_normalizado = PontoMonitoramento.normalizar_tipo(ponto_tipo)
    except ValueError:
        messages.error(request, "Ponto de calibracao invalido.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    reservatorio.garantir_pontos_monitoramento()
    ponto = reservatorio.obter_ponto_monitoramento(ponto_tipo_normalizado)
    if ponto is None:
        messages.error(request, "Ponto de calibracao nao encontrado.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    tds_alvo_raw = request.POST.get("tds_alvo_ppm")
    turbidez_alvo_raw = request.POST.get("turbidez_alvo_ntu")
    try:
        tds_alvo = (
            float(tds_alvo_raw)
            if tds_alvo_raw not in (None, "")
            else ponto.tds_alvo_calibracao_ppm
        )
        turbidez_alvo = (
            float(turbidez_alvo_raw)
            if turbidez_alvo_raw not in (None, "")
            else ponto.turbidez_alvo_calibracao_ntu
        )
    except (TypeError, ValueError):
        messages.error(request, "Informe alvos validos para TDS e turbidez.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    if not math.isfinite(tds_alvo) or not math.isfinite(turbidez_alvo):
        messages.error(request, "Informe alvos validos para TDS e turbidez.")
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    dados_agua = _ultimos_dados_agua_por_ponto(ponto)
    adc_tds = dados_agua["adc_tds"]
    adc_turb = dados_agua["adc_turb"]
    temperatura = dados_agua["temperatura"]
    if adc_tds is None or adc_turb is None or temperatura is None:
        messages.error(
            request,
            "Nao ha leitura bruta completa (adc_tds/adc_turb/temperatura) para este ponto.",
        )
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    try:
        tds_base_ppm = calcular_tds_por_adc(adc_tds=adc_tds, temperatura=temperatura)
        turbidez_base_ntu = calcular_turbidez_por_adc(adc_turb=adc_turb)
        ponto.atualizar_calibracao_agua_limpa(
            tds_base_ppm=tds_base_ppm,
            turbidez_base_ntu=turbidez_base_ntu,
            tds_alvo_ppm=tds_alvo,
            turbidez_alvo_ntu=turbidez_alvo,
            tds_adc=adc_tds,
            turbidez_adc=adc_turb,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)

    nome_ponto = "antes" if ponto.tipo == PontoMonitoramento.TIPO_ANTES else "depois"
    messages.success(
        request,
        (
            f"Calibracao de agua aplicada no ponto {nome_ponto}: "
            f"ADC TDS {adc_tds}, ADC turbidez {adc_turb}, "
            f"base {tds_base_ppm:.2f} ppm/{turbidez_base_ntu:.3f} NTU "
            f"-> alvo {tds_alvo:.2f} ppm/{turbidez_alvo:.3f} NTU."
        ),
    )
    return redirect("reservatorio_detalhe", reservatorio_id=reservatorio.id)


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def reservatorio_excluir(request, reservatorio_id):
    reservatorio = Reservatorio.obter_por_id(reservatorio_id, usuario=request.user)
    if reservatorio is None:
        messages.error(request, "Reservatorio nao encontrado.")
        return redirect("index")

    reservatorio.excluir_reservatorio()
    messages.success(request, "Reservatorio removido.")
    return redirect("index")


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
        messages.error(request, "Credenciais invalidas.")
        return render(request, "auth/entrar.html", {"nome": nome})

    login(request, usuario)
    return redirect("index")


@login_required(login_url="entrar")
@require_http_methods(["POST"])
def sair(request):
    logout(request)
    messages.success(request, "Voce saiu da sessao.")
    return redirect("entrar")


@csrf_exempt
@require_http_methods(["POST"])
def esp32_leitura(request):
    token = request.headers.get("X-API-Token", "")
    if token != settings.ESP32_API_TOKEN:
        return JsonResponse({"erro": "nao autorizado"}, status=401)

    try:
        processar_leitura_esp32(request.body)
    except IngestaoLeituraErro as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    return JsonResponse({"ok": True}, status=201)


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


def _medias_vazias():
    return {
        "temperatura": None,
        "tds": None,
        "turbidez": None,
        "ph": None,
    }


def _montar_dashboard_cards(reservatorios, periodo_delta):
    if not reservatorios:
        return []

    reservatorio_ids = [item.id for item in reservatorios]
    inicio_periodo = timezone.now() - periodo_delta
    medias_por_chave = {}

    agregados = (
        LeituraQualidade.objects.filter(
            ponto__reservatorio_id__in=reservatorio_ids,
            data_hora__gte=inicio_periodo,
        )
        .values("ponto__reservatorio_id", "ponto__tipo")
        .annotate(
            media_temperatura=Avg("temperatura"),
            media_tds=Avg("tds"),
            media_turbidez=Avg("turbidez"),
            media_ph=Avg("ph"),
        )
    )

    for item in agregados:
        medias_por_chave[
            (
                item["ponto__reservatorio_id"],
                item["ponto__tipo"],
            )
        ] = {
            "temperatura": item["media_temperatura"],
            "tds": item["media_tds"],
            "turbidez": item["media_turbidez"],
            "ph": item["media_ph"],
        }

    cards = []
    for reservatorio in reservatorios:
        medias_antes = medias_por_chave.get(
            (reservatorio.id, PontoMonitoramento.TIPO_ANTES),
            _medias_vazias(),
        )
        medias_depois = medias_por_chave.get(
            (reservatorio.id, PontoMonitoramento.TIPO_DEPOIS),
            _medias_vazias(),
        )

        cards.append(
            {
                "reservatorio": reservatorio,
                "antes": medias_antes,
                "depois": medias_depois,
                "status_antes": _status_metricas_por_faixa(
                    medias_antes,
                    reservatorio=reservatorio,
                ),
                "status_depois": _status_metricas_por_faixa(
                    medias_depois,
                    reservatorio=reservatorio,
                ),
            }
        )

    return cards


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

    # Limita a janela para evitar payload/render excessivo no frontend.
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
        x_label = data_hora_local.strftime("%d/%m %H:%M:%S")
        tds.append({"x": x_label, "y": leitura.tds})
        temperatura.append({"x": x_label, "y": leitura.temperatura})
        turbidez.append({"x": x_label, "y": leitura.turbidez})
        ph.append({"x": x_label, "y": leitura.ph})

    return {
        "tds": tds,
        "temperatura": temperatura,
        "turbidez": turbidez,
        "ph": ph,
    }


def _resumo_calibracao_ph(ponto):
    ultima_tensao = _ultima_tensao_ph_por_ponto(ponto)

    if ponto is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_tensao": ultima_tensao,
        }

    calibrado_em = ponto.ph_calibrado_em
    if calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            "ultima_tensao": ultima_tensao,
        }

    agora = timezone.now()
    delta = agora - calibrado_em
    dias = max(0, delta.days)
    return {
        "calibrado_em": calibrado_em,
        "dias": dias,
        "vencida": dias >= DIAS_ALERTA_CALIBRACAO_PH,
        "ultima_tensao": ultima_tensao,
    }


def _resumo_calibracao_agua(ponto):
    dados_agua = _ultimos_dados_agua_por_ponto(ponto)

    if ponto is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            **dados_agua,
        }

    calibrado_em = ponto.agua_calibrado_em
    if calibrado_em is None:
        return {
            "calibrado_em": None,
            "dias": None,
            "vencida": True,
            **dados_agua,
        }

    agora = timezone.now()
    delta = agora - calibrado_em
    dias = max(0, delta.days)
    return {
        "calibrado_em": calibrado_em,
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
