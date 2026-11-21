import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from painel.html_seguro import sanitizar, texto_puro
from painel.models import (
    AnexoOcorrencia,
    Auditoria,
    ComplementoOcorrencia,
    Equipe,
    ItemNota,
    MembroEquipe,
    MotivoOcorrencia,
    SetorOcorrencia,
    Ocorrencia,
    ProdutoDevolvido,
    StatusOcorrencia,
)

PESO_MAX = Decimal("9999999.999")
VALOR_MAX = Decimal("9999999999.99")

ROTULOS = {
    "numero_nota": "Nota fiscal",
    "cliente": "Cliente",
    "peso": "Peso",
    "valor": "Valor",
    "tipo_devolucao": "Tipo de devolução",
    "placa": "Placa",
    "setor": "Setor responsável",
    "motivo": "Motivo",
    "descricao": "Descrição",
}

ANEXO_MAX_BYTES = 8 * 1024 * 1024
ANEXO_MAX_QTD = 10
ANEXO_TIPOS = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}
ANEXO_EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


def erros_para_dict(exc):
    if hasattr(exc, "message_dict"):
        return {campo: [str(m) for m in msgs] for campo, msgs in exc.message_dict.items()}
    return {"detail": [str(m) for m in exc.messages]}


def normalizar_nota(numero):
    digitos = re.sub(r"\D", "", numero or "")
    if not digitos:
        raise ValidationError({"numero_nota": "Informe o número da nota fiscal."})
    if len(digitos) > 20:
        raise ValidationError({"numero_nota": "O número da nota é longo demais."})
    return digitos


def normalizar_placa(placa):
    placa = re.sub(r"[^A-Za-z0-9]", "", placa or "").upper()
    if not placa:
        return ""
    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        raise ValidationError(
            {"placa": "Placa inválida. Use o padrão Mercosul (ABC1D23) ou o antigo (ABC1234)."}
        )
    return placa


def decimal_flex(valor):
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        raise InvalidOperation
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    return Decimal(texto)


def equipes_do_usuario(usuario):
    if usuario.acesso_total:
        return Equipe.objects.all()
    ids = MembroEquipe.objects.filter(usuario=usuario).values("equipe_id")
    return Equipe.objects.filter(id__in=ids)


def equipes_de_auditoria(usuario):
    if usuario.acesso_total:
        return Equipe.objects.all()
    ids = MembroEquipe.objects.filter(
        usuario=usuario, papel=MembroEquipe.Papel.GERENTE
    ).values("equipe_id")
    return Equipe.objects.filter(id__in=ids)


def pode_ver_auditoria(usuario):
    return usuario.acesso_total or equipes_de_auditoria(usuario).exists()


def status_ativos():
    return StatusOcorrencia.objects.filter(ativo=True)


def motivos_ativos():
    return MotivoOcorrencia.objects.filter(ativo=True)


def setores_ativos():
    return SetorOcorrencia.objects.filter(ativo=True)


def status_padrao():
    atual = StatusOcorrencia.objects.filter(padrao=True, ativo=True).first()
    if atual:
        return atual
    atual = status_ativos().first()
    if atual:
        return atual
    return StatusOcorrencia.objects.create(
        nome="Pendente", slug="pendente", cor="#F8E7CF", ordem=1, padrao=True
    )


def resolver_status(valor):
    if valor in (None, ""):
        raise ValidationError({"status": "Escolha o status."})
    if isinstance(valor, StatusOcorrencia):
        escolhido = valor
    elif str(valor).isdigit():
        escolhido = StatusOcorrencia.objects.filter(pk=int(valor)).first()
    else:
        escolhido = StatusOcorrencia.objects.filter(slug=str(valor)).first()
    if escolhido is None or not escolhido.ativo:
        raise ValidationError({"status": "Status inválido."})
    return escolhido


def ocorrencias_visiveis(usuario):
    qs = Ocorrencia.objects.select_related(
        "equipe", "criado_por", "nota", "status", "motivo", "setor"
    ).prefetch_related("produtos", "anexos", "complementos__autor")
    if usuario.acesso_total:
        return qs
    ids = MembroEquipe.objects.filter(usuario=usuario).values("equipe_id")
    return qs.filter(equipe_id__in=ids)


def pode_ver_ocorrencia(usuario, ocorrencia):
    if usuario.acesso_total:
        return True
    return MembroEquipe.objects.filter(usuario=usuario, equipe_id=ocorrencia.equipe_id).exists()


def pode_editar_ocorrencia(usuario, ocorrencia):
    return ocorrencia.criado_por_id == usuario.id


def pode_excluir_ocorrencia(usuario, ocorrencia):
    return usuario.acesso_total


def pode_alterar_status(usuario, ocorrencia):
    return pode_ver_ocorrencia(usuario, ocorrencia)


FILTRO_DE = "filtro_de"
FILTRO_ATE = "filtro_ate"


def periodo_padrao(params, session=None):
    hoje = timezone.localdate().isoformat()
    dados = params.copy()
    if "de" in params or "ate" in params:
        de = str(dados.get("de") or "").strip() or hoje
        ate = str(dados.get("ate") or "").strip() or hoje
    elif session is not None:
        de = str(session.get(FILTRO_DE) or "").strip() or hoje
        ate = str(session.get(FILTRO_ATE) or "").strip() or hoje
    else:
        de, ate = hoje, hoje
    dados["de"] = de
    dados["ate"] = ate
    if session is not None:
        session[FILTRO_DE] = de
        session[FILTRO_ATE] = ate
    return dados


def _unidade_massa(unidade):
    limpa = re.sub(r"[^A-Z]", "", (unidade or "").upper())
    return limpa in {"KG", "KGM", "KGS", "KILO", "KILOS", "QUILO", "QUILOS"} or limpa.startswith("KG")


def peso_valor_devolvido(ocorrencia):
    if ocorrencia.tipo_devolucao == Ocorrencia.TipoDevolucao.TOTAL:
        return ocorrencia.peso or Decimal("0"), ocorrencia.valor or Decimal("0")
    produtos = list(ocorrencia.produtos.all())
    peso = Decimal("0")
    valor = Decimal("0")
    for produto in produtos:
        item = produto.item_nota
        if item is None or not item.quantidade:
            if _unidade_massa(produto.unidade):
                peso += produto.quantidade or Decimal("0")
            continue
        frac = produto.quantidade / item.quantidade
        valor += (item.valor or Decimal("0")) * frac
        peso += item.peso_efetivo() * frac
    if peso <= 0 and (ocorrencia.peso or Decimal("0")) > 0:
        base_valor = ocorrencia.valor or Decimal("0")
        nota = ocorrencia.nota
        if nota is not None:
            soma_nota = sum((item.valor or Decimal("0") for item in nota.itens.all()), Decimal("0"))
            if soma_nota > 0:
                base_valor = soma_nota
        if valor > 0 and base_valor > 0:
            peso = (ocorrencia.peso * valor) / base_valor
        else:
            soma_qtd_nota = Decimal("0")
            if nota is not None:
                soma_qtd_nota = sum(
                    (item.quantidade or Decimal("0") for item in nota.itens.all()),
                    Decimal("0"),
                )
            soma_qtd_dev = sum((produto.quantidade or Decimal("0") for produto in produtos), Decimal("0"))
            if soma_qtd_nota > 0 and soma_qtd_dev > 0:
                peso = (ocorrencia.peso * soma_qtd_dev) / soma_qtd_nota
    if valor <= 0 and (ocorrencia.valor or Decimal("0")) > 0:
        nota = ocorrencia.nota
        soma_qtd_nota = Decimal("0")
        if nota is not None:
            soma_qtd_nota = sum(
                (item.quantidade or Decimal("0") for item in nota.itens.all()),
                Decimal("0"),
            )
        soma_qtd_dev = sum((produto.quantidade or Decimal("0") for produto in produtos), Decimal("0"))
        if soma_qtd_nota > 0 and soma_qtd_dev > 0:
            valor = (ocorrencia.valor * soma_qtd_dev) / soma_qtd_nota
    return peso.quantize(Decimal("0.001")), valor.quantize(Decimal("0.01"))


def marcar_peso_valor_relatorio(ocorrencias):
    for ocorrencia in ocorrencias:
        ocorrencia.peso_relatorio, ocorrencia.valor_relatorio = peso_valor_devolvido(ocorrencia)
    return ocorrencias


def relatorio_agrupado(qs, agrupamento):
    qs = qs.select_related("motivo", "setor", "nota").prefetch_related("produtos__item_nota", "nota__itens")
    if agrupamento == "setor":
        qs = qs.order_by("setor__ordem", "setor__nome", "data_hora", "id")
    elif agrupamento == "placa":
        qs = qs.order_by("placa", "data_hora", "id")
    else:
        qs = qs.order_by("motivo__ordem", "motivo__nome", "data_hora", "id")

    buckets = {}
    for ocorrencia in qs:
        ocorrencia.peso_relatorio, ocorrencia.valor_relatorio = peso_valor_devolvido(ocorrencia)
        if agrupamento == "setor":
            chave = ocorrencia.setor_id
            titulo = ocorrencia.setor.nome if ocorrencia.setor_id else "Sem setor"
        elif agrupamento == "placa":
            chave = ocorrencia.placa or ""
            titulo = ocorrencia.placa or "Sem placa"
        else:
            chave = ocorrencia.motivo_id
            titulo = ocorrencia.motivo.nome if ocorrencia.motivo_id else "Sem motivo"
        if chave not in buckets:
            buckets[chave] = {"titulo": titulo, "ocorrencias": []}
        buckets[chave]["ocorrencias"].append(ocorrencia)

    if agrupamento == "setor":
        chaves = sorted(
            buckets,
            key=lambda item: (
                buckets[item]["ocorrencias"][0].setor.ordem if item else 999,
                buckets[item]["titulo"],
            ),
        )
    elif agrupamento == "placa":
        chaves = sorted(buckets, key=lambda item: (item == "", item))
    else:
        chaves = sorted(
            buckets,
            key=lambda item: (
                buckets[item]["ocorrencias"][0].motivo.ordem if item else 999,
                buckets[item]["titulo"],
            ),
        )

    grupos = []
    total_peso = Decimal("0")
    total_valor = Decimal("0")
    for chave in chaves:
        itens = buckets[chave]["ocorrencias"]
        peso = sum((item.peso_relatorio for item in itens), Decimal("0"))
        valor_soma = sum((item.valor_relatorio for item in itens), Decimal("0"))
        total_peso += peso
        total_valor += valor_soma
        grupos.append(
            {
                "titulo": buckets[chave]["titulo"],
                "ocorrencias": itens,
                "quantidade": len(itens),
                "total_peso": peso,
                "total_valor": valor_soma,
            }
        )
    return grupos, total_peso, total_valor


def contagem_por_status(usuario, qs=None):
    base = qs if qs is not None else ocorrencias_visiveis(usuario)
    linhas = {
        linha["status_id"]: linha["total"]
        for linha in base.values("status_id").annotate(total=Count("id"))
    }
    itens = []
    for status in status_ativos():
        itens.append(
            {
                "id": status.id,
                "slug": status.slug,
                "nome": status.nome,
                "cor": status.cor,
                "total": linhas.get(status.id, 0),
            }
        )
    return {"todas": sum(item["total"] for item in itens), "itens": itens}


def aplicar_filtros(qs, params, campo_data="data_hora"):
    status = params.get("status") or ""
    if str(status).isdigit():
        qs = qs.filter(status_id=int(status))
    elif status:
        qs = qs.filter(status__slug=status)
    texto = (params.get("q") or "").strip()
    if texto:
        qs = qs.filter(_busca_livre(texto)).distinct()
    inicio = _data_param(params.get("de"))
    fim = _data_param(params.get("ate"))
    data = "atualizado_em" if campo_data == "atualizado_em" else "data_hora"
    if inicio:
        qs = qs.filter(**{f"{data}__date__gte": inicio})
    if fim:
        qs = qs.filter(**{f"{data}__date__lte": fim})
    return qs


def _busca_livre(texto):
    placa = re.sub(r"[^A-Za-z0-9]", "", texto)
    nota = re.sub(r"\D", "", texto)
    consulta = (
        Q(cliente__icontains=texto)
        | Q(numero_nota__icontains=nota or texto)
        | Q(placa__icontains=placa or texto)
        | Q(equipe__nome__icontains=texto)
        | Q(criado_por__first_name__icontains=texto)
        | Q(criado_por__last_name__icontains=texto)
        | Q(criado_por__username__icontains=texto)
        | Q(status__nome__icontains=texto)
        | Q(motivo__nome__icontains=texto)
        | Q(setor__nome__icontains=texto)
        | Q(descricao__icontains=texto)
        | Q(complementos__texto__icontains=texto)
        | Q(complementos__autor__first_name__icontains=texto)
    )
    tipos = [
        valor for valor, rotulo in Ocorrencia.TipoDevolucao.choices if texto.casefold() in rotulo.casefold()
    ]
    if tipos:
        consulta |= Q(tipo_devolucao__in=tipos)
    return consulta


def _data_param(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        return None


def buscar_nota(numero):
    from painel.origens import resolver_nota

    try:
        normalizado = normalizar_nota(numero)
    except ValidationError:
        return None
    return resolver_nota(normalizado)


def resolver_setor(valor):
    if valor in (None, ""):
        raise ValidationError({"setor": "Escolha o setor responsável."})
    if isinstance(valor, SetorOcorrencia):
        escolhido = valor
    elif str(valor).isdigit():
        escolhido = SetorOcorrencia.objects.filter(pk=int(valor)).first()
    else:
        escolhido = SetorOcorrencia.objects.filter(slug=str(valor)).first()
    if escolhido is None or not escolhido.ativo:
        raise ValidationError({"setor": "Setor inválido."})
    return escolhido


def resolver_motivo(valor):
    if valor in (None, ""):
        raise ValidationError({"motivo": "Escolha o motivo da ocorrência."})
    if isinstance(valor, MotivoOcorrencia):
        escolhido = valor
    elif str(valor).isdigit():
        escolhido = MotivoOcorrencia.objects.filter(pk=int(valor)).first()
    else:
        escolhido = MotivoOcorrencia.objects.filter(slug=str(valor)).first()
    if escolhido is None or not escolhido.ativo:
        raise ValidationError({"motivo": "Motivo inválido."})
    return escolhido


def ocorrencias_abertas_da_nota(usuario, numero, ignorar_id=None):
    try:
        normalizado = normalizar_nota(numero)
    except ValidationError:
        return Ocorrencia.objects.none()
    qs = ocorrencias_visiveis(usuario).filter(numero_nota=normalizado, status__encerra=False)
    if ignorar_id:
        qs = qs.exclude(pk=ignorar_id)
    return qs.order_by("-data_hora")


def resolver_equipe(usuario, equipe):
    vinculos = list(usuario.vinculos.select_related("equipe"))
    if usuario.acesso_total:
        if equipe is None:
            raise ValidationError({"equipe": "Escolha a equipe."})
        return equipe
    if not vinculos:
        raise ValidationError({"equipe": "Você ainda não participa de nenhuma equipe."})
    if len(vinculos) == 1:
        return vinculos[0].equipe
    if equipe is None or not any(v.equipe_id == equipe.id for v in vinculos):
        raise ValidationError({"equipe": "Escolha uma equipe da qual você participa."})
    return equipe


def _apresentar(campo, valor):
    if valor in (None, ""):
        return "—"
    if campo == "motivo":
        return valor.nome if hasattr(valor, "nome") else str(valor)
    if campo == "tipo_devolucao":
        return Ocorrencia.TipoDevolucao(valor).label
    if campo == "setor":
        return valor.nome if hasattr(valor, "nome") else str(valor)
    if campo == "peso":
        return f"{valor} kg"
    if campo == "valor":
        return f"R$ {valor}"
    return str(valor)


def _linhas_produtos(ocorrencia):
    return [
        f"{p.descricao} × {p.quantidade} {p.unidade}"
        for p in ocorrencia.produtos.all().order_by("id")
    ]


def _snapshot(ocorrencia):
    return {
        "nota": ocorrencia.numero_nota,
        "cliente": ocorrencia.cliente,
        "peso": str(ocorrencia.peso),
        "valor": str(ocorrencia.valor),
        "tipo": ocorrencia.get_tipo_devolucao_display(),
        "placa": ocorrencia.placa or "—",
        "setor": ocorrencia.setor.nome if ocorrencia.setor_id else "—",
        "motivo": ocorrencia.motivo.nome if ocorrencia.motivo_id else "—",
        "descricao": ocorrencia.descricao,
        "status": ocorrencia.get_status_display(),
        "produtos": _linhas_produtos(ocorrencia),
    }


def registrar_auditoria(*, usuario, acao, resumo, equipe, ocorrencia=None, referencia=None, detalhes=None):
    Auditoria.objects.create(
        usuario=usuario,
        acao=acao,
        resumo=resumo[:280],
        equipe=equipe,
        ocorrencia=ocorrencia,
        referencia=referencia if referencia is not None else ocorrencia.pk,
        detalhes=detalhes or {},
    )


def auditoria_visivel(usuario):
    qs = Auditoria.objects.select_related("usuario", "equipe")
    if usuario.acesso_total:
        return qs
    ids = equipes_de_auditoria(usuario).values("id")
    return qs.filter(equipe_id__in=ids)


def _decimal_campo(dados, campo, casas, limite, rotulo):
    try:
        valor = decimal_flex(dados[campo])
    except (InvalidOperation, KeyError, TypeError):
        raise ValidationError({campo: f"Informe {rotulo} com um número válido."}) from None
    quantizado = valor.quantize(Decimal("1").scaleb(-casas))
    if quantizado < 0:
        raise ValidationError({campo: f"{rotulo.capitalize()} não pode ser negativo."})
    if quantizado > limite:
        raise ValidationError({campo: f"{rotulo.capitalize()} acima do limite."})
    return quantizado


def validar_produtos(produtos, nota, tipo):
    if nota and tipo == Ocorrencia.TipoDevolucao.TOTAL:
        itens = list(nota.itens.all())
        if not itens:
            raise ValidationError({"produtos": "Esta nota não tem produtos cadastrados."})
        return [_de_item(item, item.quantidade) for item in itens]

    if not isinstance(produtos, list) or not produtos:
        raise ValidationError({"produtos": "Informe ao menos um produto devolvido."})

    itens_por_id = {}
    if nota:
        itens_por_id = {item.id: item for item in nota.itens.all()}

    limpos = []
    for bruto in produtos:
        if not isinstance(bruto, dict):
            raise ValidationError({"produtos": "Não foi possível ler os produtos devolvidos."})
        if bruto.get("selecionado", True) is False:
            continue
        item = None
        item_id = bruto.get("item_nota") or None
        if item_id:
            try:
                item = itens_por_id.get(int(item_id))
            except (TypeError, ValueError):
                item = None
            if nota and item is None:
                raise ValidationError({"produtos": "Há um produto que não pertence a esta nota."})
        descricao = (bruto.get("descricao") or (item.descricao if item else "")).strip()
        if not descricao:
            raise ValidationError({"produtos": "Todo produto precisa de uma descrição."})
        try:
            quantidade = decimal_flex(bruto.get("quantidade")).quantize(Decimal("0.001"))
        except (InvalidOperation, TypeError):
            raise ValidationError({"produtos": f"Quantidade inválida em {descricao}."}) from None
        if quantidade <= 0:
            raise ValidationError({"produtos": f"A quantidade de {descricao} precisa ser maior que zero."})
        if item and quantidade > item.quantidade:
            raise ValidationError(
                {"produtos": f"A quantidade de {descricao} passa do que consta na nota."}
            )
        unidade = (bruto.get("unidade") or (item.unidade if item else "UN")).strip().upper()[:12]
        limpos.append(
            {
                "item_nota": item,
                "codigo": (item.codigo if item else str(bruto.get("codigo") or ""))[:40],
                "descricao": descricao[:180],
                "quantidade": quantidade,
                "unidade": unidade or "UN",
            }
        )
    if not limpos:
        raise ValidationError({"produtos": "Selecione ao menos um produto devolvido."})
    return limpos


def _de_item(item: ItemNota, quantidade: Decimal):
    return {
        "item_nota": item,
        "codigo": item.codigo,
        "descricao": item.descricao,
        "quantidade": quantidade,
        "unidade": item.unidade,
    }


def _gravar_produtos(ocorrencia, limpos):
    ocorrencia.produtos.all().delete()
    ProdutoDevolvido.objects.bulk_create(
        [
            ProdutoDevolvido(
                ocorrencia=ocorrencia,
                item_nota=item["item_nota"],
                codigo=item["codigo"],
                descricao=item["descricao"],
                quantidade=item["quantidade"],
                unidade=item["unidade"],
            )
            for item in limpos
        ]
    )


def _dados_limpos(dados):
    numero = normalizar_nota(dados.get("numero_nota"))
    cliente = str(dados.get("cliente") or "").strip()
    if not cliente:
        raise ValidationError({"cliente": "Informe o nome do cliente."})
    descricao = sanitizar(str(dados.get("descricao") or ""))
    if len(texto_puro(descricao)) < 10:
        raise ValidationError({"descricao": "Descreva a ocorrência com pelo menos 10 caracteres."})
    tipo = dados.get("tipo_devolucao")
    if tipo not in Ocorrencia.TipoDevolucao.values:
        raise ValidationError({"tipo_devolucao": "Escolha se a devolução é total ou parcial."})
    return {
        "numero_nota": numero,
        "cliente": cliente[:160],
        "peso": _decimal_campo(dados, "peso", 3, PESO_MAX, "o peso"),
        "valor": _decimal_campo(dados, "valor", 2, VALOR_MAX, "o valor"),
        "tipo_devolucao": tipo,
        "placa": normalizar_placa(dados.get("placa")),
        "setor": resolver_setor(dados.get("setor")),
        "motivo": resolver_motivo(dados.get("motivo")),
        "descricao": descricao,
    }


def _extensao(nome):
    return os.path.splitext(nome or "")[1].lower()


def _arquivos_enviados(arquivos):
    if not arquivos:
        return []
    if hasattr(arquivos, "getlist"):
        return [item for item in arquivos.getlist("anexos") if item]
    if isinstance(arquivos, (list, tuple)):
        return [item for item in arquivos if item]
    return [arquivos]


def gravar_anexos(usuario, ocorrencia, arquivos, remover_ids=None):
    if remover_ids:
        ocorrencia.anexos.filter(id__in=remover_ids).delete()
    enviados = _arquivos_enviados(arquivos)
    if not enviados:
        return
    existentes = ocorrencia.anexos.count()
    if existentes + len(enviados) > ANEXO_MAX_QTD:
        raise ValidationError({"anexos": f"No máximo {ANEXO_MAX_QTD} anexos por ocorrência."})
    for arquivo in enviados:
        nome = os.path.basename(getattr(arquivo, "name", "") or "arquivo")[:180]
        tipo = (getattr(arquivo, "content_type", "") or "").lower()
        if _extensao(nome) not in ANEXO_EXTENSOES and tipo not in ANEXO_TIPOS:
            raise ValidationError({"anexos": f"{nome} não é foto nem PDF."})
        tamanho = getattr(arquivo, "size", 0) or 0
        if tamanho > ANEXO_MAX_BYTES:
            raise ValidationError({"anexos": f"{nome} passa de 8 MB."})
        AnexoOcorrencia.objects.create(
            ocorrencia=ocorrencia,
            arquivo=arquivo,
            nome=nome,
            tipo=tipo,
            enviado_por=usuario,
        )


@transaction.atomic
def criar_ocorrencia(usuario, dados, produtos, arquivos=None):
    equipe = resolver_equipe(usuario, dados.get("equipe"))
    limpos = _dados_limpos(dados)
    nota = buscar_nota(limpos["numero_nota"])
    itens = validar_produtos(produtos, nota, limpos["tipo_devolucao"])
    ocorrencia = Ocorrencia.objects.create(
        equipe=equipe,
        criado_por=usuario,
        nota=nota,
        status=status_padrao(),
        **limpos,
    )
    _gravar_produtos(ocorrencia, itens)
    gravar_anexos(usuario, ocorrencia, arquivos)
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.CRIOU,
        resumo=f"Registrou a ocorrência da nota {ocorrencia.numero_nota} ({ocorrencia.cliente}).",
        equipe=equipe,
        ocorrencia=ocorrencia,
        detalhes={"snapshot": _snapshot(ocorrencia)},
    )
    return ocorrencia


@transaction.atomic
def editar_ocorrencia(usuario, ocorrencia, dados, produtos, arquivos=None, remover_anexos=None):
    if not pode_editar_ocorrencia(usuario, ocorrencia):
        raise PermissionDenied("Você só pode editar as ocorrências que você registrou.")
    limpos = _dados_limpos(dados)
    nota = buscar_nota(limpos["numero_nota"])
    itens = validar_produtos(produtos, nota, limpos["tipo_devolucao"])
    antes = {campo: getattr(ocorrencia, campo) for campo in ROTULOS}
    produtos_antes = _linhas_produtos(ocorrencia)
    for campo, valor in limpos.items():
        setattr(ocorrencia, campo, valor)
    ocorrencia.nota = nota
    ocorrencia.save()
    _gravar_produtos(ocorrencia, itens)
    gravar_anexos(usuario, ocorrencia, arquivos, remover_anexos)
    alteracoes = []
    for campo, rotulo in ROTULOS.items():
        if antes[campo] != getattr(ocorrencia, campo):
            alteracoes.append(
                {
                    "campo": rotulo,
                    "de": _apresentar(campo, antes[campo]),
                    "para": _apresentar(campo, getattr(ocorrencia, campo)),
                }
            )
    produtos_depois = _linhas_produtos(ocorrencia)
    mudou_anexo = bool(_arquivos_enviados(arquivos) or remover_anexos)
    if not alteracoes and produtos_antes == produtos_depois and not mudou_anexo:
        return ocorrencia
    detalhes = {"alteracoes": alteracoes}
    if produtos_antes != produtos_depois:
        detalhes["produtos_antes"] = produtos_antes
        detalhes["produtos_depois"] = produtos_depois
    campos = ", ".join(item["campo"].lower() for item in alteracoes)
    if produtos_antes != produtos_depois:
        campos = f"{campos} e produtos" if campos else "produtos"
    if mudou_anexo:
        campos = f"{campos} e anexos" if campos else "anexos"
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.EDITOU,
        resumo=f"Alterou {campos} da nota {ocorrencia.numero_nota}.",
        equipe=ocorrencia.equipe,
        ocorrencia=ocorrencia,
        detalhes=detalhes,
    )
    return ocorrencia


@transaction.atomic
def alterar_status(usuario, ocorrencia, status):
    if not pode_alterar_status(usuario, ocorrencia):
        raise PermissionDenied("Você não pode alterar o status desta ocorrência.")
    escolhido = resolver_status(status)
    if ocorrencia.status_id == escolhido.id:
        return ocorrencia
    anterior = ocorrencia.get_status_display()
    ocorrencia.status = escolhido
    ocorrencia.save(update_fields=["status", "atualizado_em"])
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.STATUS,
        resumo=(
            f"Mudou o status de {anterior} para {ocorrencia.get_status_display()} "
            f"na nota {ocorrencia.numero_nota}."
        ),
        equipe=ocorrencia.equipe,
        ocorrencia=ocorrencia,
        detalhes={"de": anterior, "para": ocorrencia.get_status_display()},
    )
    return ocorrencia


def status_reabertura():
    padrao = status_padrao()
    if not padrao.encerra:
        return padrao
    aberto = status_ativos().filter(encerra=False).order_by("ordem", "nome").first()
    if aberto is None:
        raise ValidationError(
            {"status": "Cadastre um status que não encerre a ocorrência para poder reabrir."}
        )
    return aberto


def _tocar(ocorrencia):
    ocorrencia.save(update_fields=["atualizado_em"])


@transaction.atomic
def reabrir_ocorrencia(usuario, ocorrencia, texto=""):
    if not pode_alterar_status(usuario, ocorrencia):
        raise PermissionDenied("Você não pode reabrir esta ocorrência.")
    if not ocorrencia.status.encerra:
        raise ValidationError({"status": "Esta ocorrência já está em aberto."})
    anterior = ocorrencia.get_status_display()
    ocorrencia.status = status_reabertura()
    ocorrencia.save(update_fields=["status", "atualizado_em"])
    texto = str(texto or "").strip()
    if texto:
        if len(texto) < 3:
            raise ValidationError({"texto": "Descreva o complemento com pelo menos 3 caracteres."})
        ComplementoOcorrencia.objects.create(
            ocorrencia=ocorrencia, autor=usuario, texto=texto[:4000], reabriu=True
        )
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.REABRIU,
        resumo=(
            f"Reabriu a ocorrência da nota {ocorrencia.numero_nota} "
            f"({anterior} → {ocorrencia.get_status_display()})."
        ),
        equipe=ocorrencia.equipe,
        ocorrencia=ocorrencia,
        detalhes={"de": anterior, "para": ocorrencia.get_status_display(), "texto": texto},
    )
    return ocorrencia


@transaction.atomic
def criar_complemento(usuario, ocorrencia, texto):
    if not pode_ver_ocorrencia(usuario, ocorrencia):
        raise PermissionDenied("Você não pode complementar esta ocorrência.")
    texto = str(texto or "").strip()
    if len(texto) < 3:
        raise ValidationError({"texto": "Descreva o complemento com pelo menos 3 caracteres."})
    if len(texto) > 4000:
        raise ValidationError({"texto": "O complemento é longo demais."})
    reabriu = bool(ocorrencia.status.encerra)
    if reabriu:
        anterior = ocorrencia.get_status_display()
        ocorrencia.status = status_reabertura()
        ocorrencia.save(update_fields=["status", "atualizado_em"])
        registrar_auditoria(
            usuario=usuario,
            acao=Auditoria.Acao.REABRIU,
            resumo=(
                f"Reabriu a ocorrência da nota {ocorrencia.numero_nota} "
                f"ao complementar ({anterior} → {ocorrencia.get_status_display()})."
            ),
            equipe=ocorrencia.equipe,
            ocorrencia=ocorrencia,
            detalhes={"de": anterior, "para": ocorrencia.get_status_display()},
        )
    complemento = ComplementoOcorrencia.objects.create(
        ocorrencia=ocorrencia, autor=usuario, texto=texto, reabriu=reabriu
    )
    if not reabriu:
        _tocar(ocorrencia)
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.COMENTOU,
        resumo=f"Complementou a ocorrência da nota {ocorrencia.numero_nota}.",
        equipe=ocorrencia.equipe,
        ocorrencia=ocorrencia,
        detalhes={"texto": texto, "reabriu": reabriu},
    )
    return complemento


@transaction.atomic
def excluir_ocorrencia(usuario, ocorrencia):
    if not pode_excluir_ocorrencia(usuario, ocorrencia):
        raise PermissionDenied("Você não pode excluir ocorrências.")
    snapshot = _snapshot(ocorrencia)
    referencia = ocorrencia.pk
    equipe = ocorrencia.equipe
    numero = ocorrencia.numero_nota
    cliente = ocorrencia.cliente
    ocorrencia.delete()
    registrar_auditoria(
        usuario=usuario,
        acao=Auditoria.Acao.EXCLUIU,
        resumo=f"Excluiu a ocorrência da nota {numero} ({cliente}).",
        equipe=equipe,
        ocorrencia=None,
        referencia=referencia,
        detalhes={"snapshot": snapshot},
    )
