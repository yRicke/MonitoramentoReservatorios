from django import template

from app.services.numeros import formatar_decimal_br

register = template.Library()


@register.filter
def decimal_br(valor, casas=2):
    return formatar_decimal_br(valor, casas)
