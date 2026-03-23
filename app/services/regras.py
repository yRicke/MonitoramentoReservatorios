TEMPO_ATUALIZACAO_MIN = 5


def calcular_status(temperatura, tds, turbidez):
    if tds >= 900 or turbidez >= 2.5:
        return "perigo"
    if tds >= 600 or turbidez >= 1.5:
        return "atencao"
    return "bom"


def combinar_status(statuses):
    prioridade = {
        "bom": 0,
        "atencao": 1,
        "perigo": 2,
    }
    if not statuses:
        return "bom"

    return max(statuses, key=lambda status: prioridade.get(status, -1))
