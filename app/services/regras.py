FATOR_PERIGO_TDS = 1.5
FATOR_PERIGO_TURBIDEZ = 5.0 / 3.0
DESVIO_TEMPERATURA_ATENCAO = 5.0
DESVIO_TEMPERATURA_PERIGO = 8.0


def calcular_status(
    temperatura,
    tds,
    turbidez,
    *,
    meta_ppm_tds=600.0,
    meta_ntu_turbidez=1.5,
    meta_celsius_temperatura=25.0,
):
    desvio_temperatura = abs(temperatura - meta_celsius_temperatura)

    if (
        tds >= meta_ppm_tds * FATOR_PERIGO_TDS
        or turbidez >= meta_ntu_turbidez * FATOR_PERIGO_TURBIDEZ
        or desvio_temperatura >= DESVIO_TEMPERATURA_PERIGO
    ):
        return "perigo"

    if (
        tds >= meta_ppm_tds
        or turbidez >= meta_ntu_turbidez
        or desvio_temperatura >= DESVIO_TEMPERATURA_ATENCAO
    ):
        return "atencao"

    return "bom"
