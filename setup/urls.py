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
    path('reservatorios/<int:reservatorio_id>/atualizar/', views.reservatorio_atualizar, name="reservatorio_atualizar"),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-ph/',
        views.reservatorio_calibracao_ph_atualizar,
        name="reservatorio_calibracao_ph_atualizar",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-ph/auto/',
        views.reservatorio_calibracao_ph_auto,
        name="reservatorio_calibracao_ph_auto",
    ),
    path(
        'reservatorios/<int:reservatorio_id>/calibracao-agua/auto/',
        views.reservatorio_calibracao_agua_auto,
        name="reservatorio_calibracao_agua_auto",
    ),
    path('reservatorios/<int:reservatorio_id>/excluir/', views.reservatorio_excluir, name="reservatorio_excluir"),
    path('entrar/', views.entrar, name="entrar"),
    path('sair/', views.sair, name="sair"),

    path("api/esp32/leituras/", views.esp32_leitura, name="esp32_leitura"),
]
