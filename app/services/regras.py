FATOR_PERIGO_TDS = 0.25
DESVIO_TURBIDEZ_PERIGO = 50.0
DESVIO_TEMPERATURA_PERIGO = 10.0
DESVIO_PH_PERIGO = 1.5


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
        margem_perigo=0.0,
        margem_perigo_inferior=abs(faixa_ppm_tds_min) * FATOR_PERIGO_TDS,
        margem_perigo_superior=abs(faixa_ppm_tds_max) * FATOR_PERIGO_TDS,
    )
    status_turbidez = classificar_status_por_faixa(
        turbidez,
        minimo=faixa_ntu_turbidez_min,
        maximo=faixa_ntu_turbidez_max,
        margem_atencao=0.0,
        margem_perigo=DESVIO_TURBIDEZ_PERIGO,
    )
    status_temperatura = classificar_status_por_faixa(
        temperatura,
        minimo=faixa_celsius_temperatura_min,
        maximo=faixa_celsius_temperatura_max,
        margem_atencao=0.0,
        margem_perigo=DESVIO_TEMPERATURA_PERIGO,
    )
    status_ph = "bom"
    if ph is not None:
        status_ph = classificar_status_por_faixa(
            ph,
            minimo=faixa_ph_min,
            maximo=faixa_ph_max,
            margem_atencao=0.0,
            margem_perigo=DESVIO_PH_PERIGO,
        )

    status_metricas = (status_tds, status_turbidez, status_temperatura, status_ph)
    if "perigo" in status_metricas:
        return "perigo"
    if "atencao" in status_metricas:
        return "atencao"
    return "bom"


def calcular_status_reservatorio(
    *,
    reservatorio,
    temperatura,
    tds,
    turbidez,
    ph=None,
):
    return calcular_status(
        temperatura=temperatura,
        tds=tds,
        turbidez=turbidez,
        ph=ph,
        faixa_ppm_tds_min=reservatorio.faixa_ppm_tds_min,
        faixa_ppm_tds_max=reservatorio.faixa_ppm_tds_max,
        faixa_ntu_turbidez_min=reservatorio.faixa_ntu_turbidez_min,
        faixa_ntu_turbidez_max=reservatorio.faixa_ntu_turbidez_max,
        faixa_celsius_temperatura_min=reservatorio.faixa_celsius_temperatura_min,
        faixa_celsius_temperatura_max=reservatorio.faixa_celsius_temperatura_max,
        faixa_ph_min=reservatorio.faixa_ph_min,
        faixa_ph_max=reservatorio.faixa_ph_max,
    )


def classificar_status_por_faixa(
    valor,
    *,
    minimo,
    maximo,
    margem_atencao,
    margem_perigo,
    margem_atencao_inferior=None,
    margem_atencao_superior=None,
    margem_perigo_inferior=None,
    margem_perigo_superior=None,
):
    margem_atencao_inferior = (
        margem_atencao if margem_atencao_inferior is None else margem_atencao_inferior
    )
    margem_atencao_superior = (
        margem_atencao if margem_atencao_superior is None else margem_atencao_superior
    )
    margem_perigo_inferior = (
        margem_perigo if margem_perigo_inferior is None else margem_perigo_inferior
    )
    margem_perigo_superior = (
        margem_perigo if margem_perigo_superior is None else margem_perigo_superior
    )

    if valor < (minimo - margem_perigo_inferior) or valor > (
        maximo + margem_perigo_superior
    ):
        return "perigo"
    if valor < (minimo - margem_atencao_inferior) or valor > (
        maximo + margem_atencao_superior
    ):
        return "atencao"
    return "bom"
