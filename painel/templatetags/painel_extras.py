from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

from painel.html_seguro import descricao_html

register = template.Library()


def _decimal(valor):
    if valor in (None, ""):
        return None
    return Decimal(valor)


@register.filter
def moeda(valor):
    try:
        quant = _decimal(valor)
    except (InvalidOperation, TypeError):
        return "—"
    if quant is None:
        return "—"
    sinal = "-" if quant < 0 else ""
    quant = abs(quant).quantize(Decimal("0.01"))
    inteiro, frac = f"{quant:.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{frac}"


@register.filter
def peso_br(valor):
    try:
        quant = _decimal(valor)
    except (InvalidOperation, TypeError):
        return "—"
    if quant is None:
        return "—"
    quant = quant.quantize(Decimal("0.001"))
    inteiro, frac = f"{quant:.3f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{inteiro},{frac} kg"


@register.filter
def qtd_br(valor):
    try:
        quant = _decimal(valor).quantize(Decimal("0.001"))
    except (InvalidOperation, TypeError):
        return valor
    texto = f"{quant:.3f}".replace(".", ",")
    return texto.rstrip("0").rstrip(",")


@register.filter
def rico(html):
    return mark_safe(descricao_html(html))


@register.filter
def nota_br(numero):
    numero = str(numero or "")
    if len(numero) == 9 and numero.isdigit():
        return f"{numero[:3]}.{numero[3:6]}.{numero[6:]}"
    return numero


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    params = context["request"].GET.copy()
    for chave, valor in kwargs.items():
        if valor in (None, ""):
            params.pop(chave, None)
        else:
            params[chave] = valor
    return params.urlencode()
