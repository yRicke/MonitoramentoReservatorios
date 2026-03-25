from django.contrib import admin

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio


@admin.register(Reservatorio)
class ReservatorioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "status",
        "meta_ppm_tds",
        "meta_ntu_turbidez",
        "meta_celsius_temperatura",
        "meta_ph",
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
