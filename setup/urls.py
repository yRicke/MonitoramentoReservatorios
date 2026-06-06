"""
URL configuration for setup project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name="index"),
    path('reservatorios/adicionar/', views.reservatorio_adicionar, name="reservatorio_adicionar"),
    path('reservatorios/<int:reservatorio_id>/', views.reservatorio_detalhe, name="reservatorio_detalhe"),
    path('reservatorios/<int:reservatorio_id>/editar/', views.reservatorio_editar, name="reservatorio_editar"),
    path(
        'reservatorios/<int:reservatorio_id>/relatorio/',
        views.reservatorio_relatorio,
        name="reservatorio_relatorio",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/',
        views.reservatorio_calibracao,
        name="reservatorio_calibracao",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/',
        views.reservatorio_calibracao_ponto,
        name="reservatorio_calibracao_ponto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/<str:sensor_id>/',
        views.reservatorio_calibracao_sensor,
        name="reservatorio_calibracao_sensor",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/<str:sensor_id>/sessao/iniciar/',
        views.reservatorio_calibracao_sessao_iniciar,
        name="reservatorio_calibracao_sessao_iniciar",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/<str:sensor_id>/sessao/encerrar/',
        views.reservatorio_calibracao_sessao_encerrar,
        name="reservatorio_calibracao_sessao_encerrar",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/<str:sensor_id>/resetar/',
        views.reservatorio_calibracao_sensor_resetar,
        name="reservatorio_calibracao_sensor_resetar",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao/<str:ponto_tipo>/<str:sensor_id>/sessao/status/',
        views.reservatorio_calibracao_sessao_status,
        name="reservatorio_calibracao_sessao_status",
    ),
    path('reservatorios/<int:reservatorio_id>/atualizar/', views.reservatorio_atualizar, name="reservatorio_atualizar"),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-temperatura/auto/',
        views.reservatorio_calibracao_temperatura_auto,
        name="reservatorio_calibracao_temperatura_auto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-tds/auto/',
        views.reservatorio_calibracao_tds_auto,
        name="reservatorio_calibracao_tds_auto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-turbidez/auto/',
        views.reservatorio_calibracao_turbidez_auto,
        name="reservatorio_calibracao_turbidez_auto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-ph/auto/',
        views.reservatorio_calibracao_ph_auto,
        name="reservatorio_calibracao_ph_auto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/resetar-leituras/',
        views.reservatorio_resetar_leituras,
        name="reservatorio_resetar_leituras",
    ),
    path('reservatorios/<int:reservatorio_id>/excluir/', views.reservatorio_excluir, name="reservatorio_excluir"),
    path('entrar/', views.entrar, name="entrar"),
    path('sair/', views.sair, name="sair"),

    path("api/esp32/leituras/", views.esp32_leitura, name="esp32_leitura"),
    path("api/esp32/sync/", views.esp32_sync, name="esp32_sync"),
    path("api/esp32/calibracao/comando/", views.esp32_calibracao_comando, name="esp32_calibracao_comando"),
    path("api/esp32/calibracao/amostras/", views.esp32_calibracao_amostra, name="esp32_calibracao_amostra"),
]
