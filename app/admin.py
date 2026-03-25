from django.contrib import admin

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio


@admin.register(Reservatorio)
class ReservatorioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "status",
        "faixa_ppm_tds_min",
        "faixa_ppm_tds_max",
        "faixa_ntu_turbidez_min",
        "faixa_ntu_turbidez_max",
        "faixa_celsius_temperatura_min",
        "faixa_celsius_temperatura_max",
        "faixa_ph_min",
        "faixa_ph_max",
        "created_at",
    )
    search_fields = ("nome",)
    list_filter = ("status",)


@admin.register(PontoMonitoramento)
class PontoMonitoramentoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reservatorio",
        "tipo",
        "status_atual",
        "ph_voltagem_referencia_7",
        "ph_inclinacao",
        "ph_calibrado_em",
        "updated_at",
    )
    search_fields = ("reservatorio__nome",)
    list_filter = ("tipo",)


@admin.register(LeituraQualidade)
class LeituraQualidadeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ponto",
        "status_leitura",
        "status_origem",
        "tds",
        "temperatura",
        "turbidez",
        "ph",
        "data_hora",
    )
    search_fields = ("ponto__reservatorio__nome",)
    list_filter = ("ponto__tipo",)
