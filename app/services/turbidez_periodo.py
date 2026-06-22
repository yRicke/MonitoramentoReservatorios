from datetime import time

from django.utils import timezone

STATUS_IGNORADO_NOTURNO = "ignorado-noturno"
ROTULO_IGNORADO_NOTURNO = "Ignorado a noite"
INICIO_NOITE_TURBIDEZ = time(hour=18, minute=30)
FIM_NOITE_TURBIDEZ = time(hour=6, minute=30)


def is_leitura_turbidez_noturna(data_hora):
    if data_hora is None:
        return False

    data_hora_local = _localtime_seguro(data_hora)
    horario = data_hora_local.timetz().replace(tzinfo=None)
    return horario >= INICIO_NOITE_TURBIDEZ or horario <= FIM_NOITE_TURBIDEZ


def _localtime_seguro(data_hora):
    if timezone.is_naive(data_hora):
        return timezone.make_aware(data_hora, timezone.get_current_timezone())
    return timezone.localtime(data_hora)
