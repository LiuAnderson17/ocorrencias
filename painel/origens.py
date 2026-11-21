"""Origem dos dados da nota fiscal.

O painel e a API pedem a nota só pelo número. Hoje a origem padrão é o
cadastro local (digitado ou XML). Quando a empresa ligar o banco dela,
basta configurar NOTAS_ORIGEM e as variáveis NOTAS_DB_* / NOTAS_SQL.
"""

from decimal import Decimal, InvalidOperation
import logging

from django.conf import settings
from django.db import connections
from django.db.utils import ConnectionDoesNotExist

from painel.models import ItemNota, NotaFiscal

logger = logging.getLogger(__name__)


def salvar_nota_local(dados):
    nota, _criada = NotaFiscal.objects.update_or_create(
        numero=dados["numero"],
        defaults={
            "cliente": dados["cliente"],
            "peso": dados.get("peso"),
            "valor": dados.get("valor"),
            "placa": dados.get("placa") or "",
        },
    )
    nota.itens.all().delete()
    itens = dados.get("itens") or []
    ItemNota.objects.bulk_create(
        [
            ItemNota(
                nota=nota,
                codigo=item.get("codigo") or "",
                descricao=item["descricao"],
                quantidade=item["quantidade"],
                unidade=item.get("unidade") or "UN",
                peso=item.get("peso") or Decimal("0"),
                valor=item.get("valor") or Decimal("0"),
            )
            for item in itens
        ]
    )
    return NotaFiscal.objects.prefetch_related("itens").get(pk=nota.pk)


def buscar_local(numero):
    return (
        NotaFiscal.objects.filter(numero=numero)
        .prefetch_related("itens")
        .first()
    )


def _decimal(valor):
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _linha(cursor):
    colunas = [item[0].lower() for item in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(colunas, row))


def _linhas(cursor):
    colunas = [item[0].lower() for item in cursor.description]
    return [dict(zip(colunas, row)) for row in cursor.fetchall()]


def buscar_externa(numero):
    if "notas" not in settings.DATABASES:
        return None
    sql = (getattr(settings, "NOTAS_SQL", "") or "").strip()
    if not sql:
        return None
    try:
        with connections["notas"].cursor() as cursor:
            cursor.execute(sql, [numero])
            cabecalho = _linha(cursor)
            if cabecalho is None:
                return None
            itens = []
            sql_itens = (getattr(settings, "NOTAS_ITENS_SQL", "") or "").strip()
            if sql_itens:
                cursor.execute(sql_itens, [numero])
                itens = [
                    {
                        "codigo": str(item.get("codigo") or ""),
                        "descricao": str(item.get("descricao") or "Item"),
                        "quantidade": _decimal(item.get("quantidade")) or Decimal("1"),
                        "unidade": str(item.get("unidade") or "UN"),
                        "peso": _decimal(item.get("peso")),
                        "valor": _decimal(item.get("valor")),
                    }
                    for item in _linhas(cursor)
                ]
    except ConnectionDoesNotExist:
        return None
    except Exception:
        logger.exception("Falha ao consultar a nota %s na origem externa.", numero)
        return None

    dados = {
        "numero": str(cabecalho.get("numero") or numero),
        "cliente": str(cabecalho.get("cliente") or "")[:160],
        "peso": _decimal(cabecalho.get("peso")),
        "valor": _decimal(cabecalho.get("valor")),
        "placa": str(cabecalho.get("placa") or ""),
        "itens": itens,
    }
    if not dados["cliente"]:
        logger.warning("A nota %s veio da origem externa sem cliente.", numero)
        return None
    return salvar_nota_local(dados)


def resolver_nota(numero):
    origem = (getattr(settings, "NOTAS_ORIGEM", "local") or "local").strip().lower()
    if origem == "externa":
        return buscar_externa(numero)
    if origem == "auto":
        return buscar_externa(numero) or buscar_local(numero)
    return buscar_local(numero)
