def calcular_status(temperatura, tds, turbidez):
    if tds >= 900 or turbidez >= 2.5:
        return "perigo"
    if tds >= 600 or turbidez >= 1.5:
        return "atencao"
    return "bom"
