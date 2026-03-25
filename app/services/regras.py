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
    faixa_ppm_tds_min=0.0,
    faixa_ppm_tds_max=500.0,
    faixa_ntu_turbidez_min=0.0,
    faixa_ntu_turbidez_max=5.0,
    faixa_celsius_temperatura_min=5.0,
    faixa_celsius_temperatura_max=30.0,
    faixa_ph_min=6.0,
    faixa_ph_max=9.5,
):
    status_tds = classificar_status_por_faixa(
        tds,
        minimo=faixa_ppm_tds_min,
        maximo=faixa_ppm_tds_max,
        margem_atencao=0.0,
        margem_perigo=faixa_ppm_tds_max * (FATOR_PERIGO_TDS - 1.0),
    )
    status_turbidez = classificar_status_por_faixa(
        turbidez,
        minimo=faixa_ntu_turbidez_min,
        maximo=faixa_ntu_turbidez_max,
        margem_atencao=0.0,
        margem_perigo=faixa_ntu_turbidez_max * (FATOR_PERIGO_TURBIDEZ - 1.0),
    )
    status_temperatura = classificar_status_por_faixa(
        temperatura,
        minimo=faixa_celsius_temperatura_min,
        maximo=faixa_celsius_temperatura_max,
        margem_atencao=DESVIO_TEMPERATURA_ATENCAO,
        margem_perigo=DESVIO_TEMPERATURA_PERIGO,
    )
    status_ph = "bom"
    if ph is not None:
        status_ph = classificar_status_por_faixa(
            ph,
            minimo=faixa_ph_min,
            maximo=faixa_ph_max,
            margem_atencao=DESVIO_PH_ATENCAO,
            margem_perigo=DESVIO_PH_PERIGO,
        )

    status_metricas = (status_tds, status_turbidez, status_temperatura, status_ph)
    if "perigo" in status_metricas:
        return "perigo"
    if "atencao" in status_metricas:
        return "atencao"
    return "bom"


def classificar_status_por_faixa(valor, *, minimo, maximo, margem_atencao, margem_perigo):
    if valor < (minimo - margem_perigo) or valor > (maximo + margem_perigo):
        return "perigo"
    if valor < (minimo - margem_atencao) or valor > (maximo + margem_atencao):
        return "atencao"
    return "bom"
