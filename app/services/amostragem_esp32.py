NORMAL_INTERVALO_BASE_MS = 60 * 1000
CALIBRACAO_INTERVALO_BASE_MS = 5 * 1000
QTD_AMOSTRAS_MINIMA = 8
QTD_AMOSTRAS_MAXIMA = 240
SENSOR_TEMPERATURA = "temperatura"
SENSOR_TDS = "tds"
SENSOR_TURBIDEZ = "turbidez"
SENSOR_PH = "ph"

PLANOS_BASE_NORMAL = {
    SENSOR_TDS: {
        "qtd_amostras_base": 60,
        "atraso_amostra_ms": 5,
    },
    SENSOR_TURBIDEZ: {
        "qtd_amostras_base": 60,
        "atraso_amostra_ms": 10,
    },
    SENSOR_PH: {
        "qtd_amostras_base": 60,
        "atraso_amostra_ms": 5,
    },
}

PLANOS_BASE_CALIBRACAO = {
    SENSOR_TEMPERATURA: {
        "qtd_amostras_base": 1,
        "atraso_amostra_ms": 0,
    },
    SENSOR_TDS: {
        "qtd_amostras_base": 80,
        "atraso_amostra_ms": 50,
    },
    SENSOR_TURBIDEZ: {
        "qtd_amostras_base": 80,
        "atraso_amostra_ms": 50,
    },
    SENSOR_PH: {
        "qtd_amostras_base": 80,
        "atraso_amostra_ms": 50,
    },
}


def _limitar_quantidade(qtd):
    return max(QTD_AMOSTRAS_MINIMA, min(QTD_AMOSTRAS_MAXIMA, int(qtd)))


def _normalizar_intervalo_ms(intervalo_ms, *, padrao):
    try:
        numero = int(intervalo_ms)
    except (TypeError, ValueError):
        return int(padrao)

    if numero <= 0:
        return int(padrao)
    return numero


def _escalar_quantidade(*, qtd_base, intervalo_ms, intervalo_base_ms):
    if qtd_base <= 1:
        return int(qtd_base)

    qtd_escalada = round((int(qtd_base) * int(intervalo_ms)) / int(intervalo_base_ms))
    return _limitar_quantidade(qtd_escalada)


def construir_plano_amostragem_normal(*, intervalo_envio_ms):
    intervalo_final_ms = _normalizar_intervalo_ms(
        intervalo_envio_ms,
        padrao=NORMAL_INTERVALO_BASE_MS,
    )
    plano = {}

    for sensor, definicao in PLANOS_BASE_NORMAL.items():
        plano[sensor] = {
            "qtd_amostras": _escalar_quantidade(
                qtd_base=definicao["qtd_amostras_base"],
                intervalo_ms=intervalo_final_ms,
                intervalo_base_ms=NORMAL_INTERVALO_BASE_MS,
            ),
            "atraso_amostra_ms": int(definicao["atraso_amostra_ms"]),
        }

    return plano


def construir_plano_amostragem_calibracao(*, sensor, intervalo_envio_ms):
    definicao = PLANOS_BASE_CALIBRACAO.get(sensor) or PLANOS_BASE_CALIBRACAO[SENSOR_TEMPERATURA]
    intervalo_final_ms = _normalizar_intervalo_ms(
        intervalo_envio_ms,
        padrao=CALIBRACAO_INTERVALO_BASE_MS,
    )

    return {
        "qtd_amostras": _escalar_quantidade(
            qtd_base=definicao["qtd_amostras_base"],
            intervalo_ms=intervalo_final_ms,
            intervalo_base_ms=CALIBRACAO_INTERVALO_BASE_MS,
        ),
        "atraso_amostra_ms": int(definicao["atraso_amostra_ms"]),
    }
