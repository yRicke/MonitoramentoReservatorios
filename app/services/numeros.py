import math
from decimal import Decimal, InvalidOperation

ERRO_DECIMAL_INVALIDO = "valor decimal invalido"
ERRO_INTEIRO_INVALIDO = "valor inteiro invalido"


def normalizar_decimal_localizado(valor):
    if isinstance(valor, bool):
        raise ValueError(ERRO_DECIMAL_INVALIDO)

    if isinstance(valor, (int, float)):
        numero = float(valor)
        if not math.isfinite(numero):
            raise ValueError(ERRO_DECIMAL_INVALIDO)
        return numero

    if not isinstance(valor, str):
        raise TypeError(ERRO_DECIMAL_INVALIDO)

    texto = valor.strip().replace("\xa0", "").replace(" ", "")
    if not texto:
        raise ValueError(ERRO_DECIMAL_INVALIDO)

    possui_virgula = "," in texto
    possui_ponto = "." in texto

    if possui_virgula and possui_ponto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif possui_virgula:
        texto = texto.replace(",", ".")

    try:
        numero = float(Decimal(texto))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(ERRO_DECIMAL_INVALIDO) from exc

    if not math.isfinite(numero):
        raise ValueError(ERRO_DECIMAL_INVALIDO)
    return numero


def normalizar_inteiro_localizado(valor):
    if isinstance(valor, bool):
        raise ValueError(ERRO_INTEIRO_INVALIDO)

    if isinstance(valor, int):
        return valor

    numero = normalizar_decimal_localizado(valor)
    if not float(numero).is_integer():
        raise ValueError(ERRO_INTEIRO_INVALIDO)
    return int(numero)


def formatar_decimal_br(valor, casas=2):
    if valor is None:
        return ""

    numero = float(valor)
    if not math.isfinite(numero):
        return ""

    casas_final = max(0, int(casas))
    return f"{numero:.{casas_final}f}".replace(".", ",")
