from datetime import timedelta

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
from app.services.ingestao import IngestaoLeituraErro, processar_leitura_esp32
from app.services.regras import (
    DESVIO_TEMPERATURA_ATENCAO,
    DESVIO_TEMPERATURA_PERIGO,
    FATOR_PERIGO_TDS,
    FATOR_PERIGO_TURBIDEZ,
)

MAX_PONTOS_GRAFICO = 1200
PERIODO_PADRAO_DIAS = 5
PERIODOS_DIAS_DISPONIVEIS = (1, 3, 5, 7, 10, 15, 30)
STATUS_SEM_DADO = "sem-dado"


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def index(request):
    busca = request.GET.get("busca", "").strip()
    periodo_dias = _normalizar_periodo_dias(request.GET.get("dias"))
    reservatorios = list(Reservatorio.listar(busca=busca, usuario=request.user))
    dashboard_cards = _montar_dashboard_cards(reservatorios, periodo_dias)

    return render(
        request,
        "index.html",
        {
            "reservatorios": reservatorios,
            "dashboard_cards": dashboard_cards,
            "busca": busca,
            "periodo_dias": periodo_dias,
            "periodos_dias_disponiveis": PERIODOS_DIAS_DISPONIVEIS,
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
            "tds_series_antes": series_antes["tds"],
            "tds_series_depois": series_depois["tds"],
            "temperatura_series_antes": series_antes["temperatura"],
            "temperatura_series_depois": series_depois["temperatura"],
            "turbidez_series_antes": series_antes["turbidez"],
            "turbidez_series_depois": series_depois["turbidez"],
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
    meta_ppm_tds = request.POST.get("meta_ppm_tds")
    meta_ntu_turbidez = request.POST.get("meta_ntu_turbidez")
    meta_celsius_temperatura = request.POST.get("meta_celsius_temperatura")

    try:
        reservatorio.atualizar_reservatorio(
            nome=nome,
            meta_ppm_tds=meta_ppm_tds,
            meta_ntu_turbidez=meta_ntu_turbidez,
            meta_celsius_temperatura=meta_celsius_temperatura,
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


def _normalizar_periodo_dias(valor):
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return PERIODO_PADRAO_DIAS

    if dias not in PERIODOS_DIAS_DISPONIVEIS:
        return PERIODO_PADRAO_DIAS
    return dias


def _medias_vazias():
    return {
        "temperatura": None,
        "tds": None,
        "turbidez": None,
    }


def _montar_dashboard_cards(reservatorios, periodo_dias):
    if not reservatorios:
        return []

    reservatorio_ids = [item.id for item in reservatorios]
    inicio_periodo = timezone.now() - timedelta(days=periodo_dias)
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
                "status_antes": _status_metricas_por_meta(
                    medias_antes,
                    reservatorio=reservatorio,
                ),
                "status_depois": _status_metricas_por_meta(
                    medias_depois,
                    reservatorio=reservatorio,
                ),
            }
        )

    return cards


def _status_metricas_por_meta(medias, *, reservatorio):
    return {
        "temperatura": _status_media_temperatura(
            medias.get("temperatura"),
            meta=reservatorio.meta_celsius_temperatura,
        ),
        "tds": _status_media_tds(
            medias.get("tds"),
            meta=reservatorio.meta_ppm_tds,
        ),
        "turbidez": _status_media_turbidez(
            medias.get("turbidez"),
            meta=reservatorio.meta_ntu_turbidez,
        ),
    }


def _status_media_temperatura(valor, *, meta):
    if valor is None:
        return STATUS_SEM_DADO

    desvio = abs(valor - meta)
    if desvio >= DESVIO_TEMPERATURA_PERIGO:
        return Reservatorio.STATUS_PERIGO
    if desvio >= DESVIO_TEMPERATURA_ATENCAO:
        return Reservatorio.STATUS_ATENCAO
    return Reservatorio.STATUS_BOM


def _status_media_tds(valor, *, meta):
    if valor is None:
        return STATUS_SEM_DADO

    if valor >= meta * FATOR_PERIGO_TDS:
        return Reservatorio.STATUS_PERIGO
    if valor >= meta:
        return Reservatorio.STATUS_ATENCAO
    return Reservatorio.STATUS_BOM


def _status_media_turbidez(valor, *, meta):
    if valor is None:
        return STATUS_SEM_DADO

    if valor >= meta * FATOR_PERIGO_TURBIDEZ:
        return Reservatorio.STATUS_PERIGO
    if valor >= meta:
        return Reservatorio.STATUS_ATENCAO
    return Reservatorio.STATUS_BOM


def _series_leituras_por_ponto(ponto):
    if ponto is None:
        return {"tds": [], "temperatura": [], "turbidez": []}

    # Limita a janela para evitar payload/render excessivo no frontend.
    leituras = list(
        LeituraQualidade.objects.filter(ponto=ponto)
        .order_by("-data_hora")[:MAX_PONTOS_GRAFICO]
    )
    leituras.reverse()

    tds = []
    temperatura = []
    turbidez = []
    for leitura in leituras:
        data_hora_local = timezone.localtime(leitura.data_hora)
        x_label = data_hora_local.strftime("%d/%m %H:%M:%S")
        tds.append({"x": x_label, "y": leitura.tds})
        temperatura.append({"x": x_label, "y": leitura.temperatura})
        turbidez.append({"x": x_label, "y": leitura.turbidez})

    return {
        "tds": tds,
        "temperatura": temperatura,
        "turbidez": turbidez,
    }
