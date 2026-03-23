from django.contrib import admin

from app.models import LeituraQualidade, PontoMonitoramento, Reservatorio


@admin.register(Reservatorio)
class ReservatorioAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "status", "created_at")
    search_fields = ("nome",)
    list_filter = ("status",)


@admin.register(PontoMonitoramento)
class PontoMonitoramentoAdmin(admin.ModelAdmin):
    list_display = ("id", "reservatorio", "tipo", "created_at")
    search_fields = ("reservatorio__nome",)
    list_filter = ("tipo",)


@admin.register(LeituraQualidade)
class LeituraQualidadeAdmin(admin.ModelAdmin):
    list_display = ("id", "ponto", "tds", "temperatura", "turbidez", "data_hora")
    search_fields = ("ponto__reservatorio__nome",)
    list_filter = ("ponto__tipo",)
