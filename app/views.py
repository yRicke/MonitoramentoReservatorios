from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio
from app.services.ingestao import IngestaoLeituraErro, processar_leitura_esp32

MAX_PONTOS_GRAFICO = 1200


@login_required(login_url="entrar")
@require_http_methods(["GET"])
def index(request):
    busca = request.GET.get("busca", "").strip()
    reservatorios = Reservatorio.listar(busca=busca, usuario=request.user)

    return render(
        request,
        "index.html",
        {
            "reservatorios": reservatorios,
            "busca": busca,
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
