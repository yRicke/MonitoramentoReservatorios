FATOR_PERIGO_TDS = 1.5
FATOR_PERIGO_TURBIDEZ = 5.0 / 3.0
DESVIO_TEMPERATURA_ATENCAO = 5.0
DESVIO_TEMPERATURA_PERIGO = 8.0
DESVIO_PH_ATENCAO = 0.5
DESVIO_PH_PERIGO = 1.0


def calcular_status(
    temperatura,
    tds,
    turbidez,
    ph=None,
    *,
    meta_ppm_tds=600.0,
    meta_ntu_turbidez=1.5,
    meta_celsius_temperatura=25.0,
    meta_ph=7.0,
):
    desvio_temperatura = abs(temperatura - meta_celsius_temperatura)
    desvio_ph = abs(ph - meta_ph) if ph is not None else None

    if (
        tds >= meta_ppm_tds * FATOR_PERIGO_TDS
        or turbidez >= meta_ntu_turbidez * FATOR_PERIGO_TURBIDEZ
        or desvio_temperatura >= DESVIO_TEMPERATURA_PERIGO
        or (desvio_ph is not None and desvio_ph >= DESVIO_PH_PERIGO)
    ):
        return "perigo"

    if (
        tds >= meta_ppm_tds
        or turbidez >= meta_ntu_turbidez
        or desvio_temperatura >= DESVIO_TEMPERATURA_ATENCAO
        or (desvio_ph is not None and desvio_ph >= DESVIO_PH_ATENCAO)
    ):
        return "atencao"

    return "bom"
