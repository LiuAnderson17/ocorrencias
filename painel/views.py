import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from painel.forms import ComplementoForm, EntrarForm, OcorrenciaForm
from painel.models import AnexoOcorrencia, Equipe
from painel.services import (
    alterar_status,
    aplicar_filtros,
    auditoria_visivel,
    contagem_por_status,
    criar_complemento,
    criar_ocorrencia,
    editar_ocorrencia,
    reabrir_ocorrencia,
    equipes_de_auditoria,
    equipes_do_usuario,
    erros_para_dict,
    excluir_ocorrencia,
    ocorrencias_visiveis,
    pode_ver_ocorrencia,
    periodo_padrao,
    relatorio_agrupado,
    marcar_peso_valor_relatorio,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
    pode_ver_auditoria,
    status_ativos,
)


def sem_acesso(request, mensagem):
    return render(request, "painel/sem_acesso.html", {"mensagem": mensagem}, status=403)


def destino_seguro(request, candidato, padrao="painel"):
    if candidato and url_has_allowed_host_and_scheme(
        candidato,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidato
    return reverse(padrao)


def adicionar_erros(form, exc):
    for campo, msgs in erros_para_dict(exc).items():
        destino = campo if campo in form.fields else None
        if campo == "produtos" and "produtos_json" in form.fields:
            destino = "produtos_json"
        if campo == "anexos":
            destino = None
        for msg in msgs:
            form.add_error(destino, msg)


def json_solto(raw):
    try:
        dados = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return dados if isinstance(dados, list) else []


def produtos_iniciais_da_ocorrencia(ocorrencia):
    linhas = []
    for produto in ocorrencia.produtos.select_related("item_nota"):
        item = produto.item_nota
        linhas.append(
            {
                "item_nota": produto.item_nota_id,
                "codigo": produto.codigo,
                "descricao": produto.descricao,
                "quantidade": format(produto.quantidade, "f"),
                "unidade": produto.unidade,
                "selecionado": True,
                "valor_linha": format(item.valor, "f") if item else "",
                "peso_linha": format(item.peso, "f") if item else "",
                "quantidade_nota": format(item.quantidade, "f") if item else "",
            }
        )
    return linhas


def entrar(request):
    if request.user.is_authenticated:
        return redirect("painel")
    form = EntrarForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(destino_seguro(request, request.POST.get("next") or request.GET.get("next")))
    return render(request, "painel/entrar.html", {"form": form})


def sair(request):
    logout(request)
    return redirect("entrar")


POR_PAGINA = 20


def _filtros(request):
    params = periodo_padrao(request.GET, request.session)
    return params, params.get("de"), params.get("ate")


@login_required
def painel(request):
    params, filtro_de, filtro_ate = _filtros(request)
    visiveis = ocorrencias_visiveis(request.user)
    params_contagem = params.copy()
    params_contagem.pop("status", None)
    qs = aplicar_filtros(visiveis, params, campo_data="atualizado_em").order_by(
        "-atualizado_em", "-id"
    )
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("page"))
    return render(
        request,
        "painel/painel.html",
        {
            "pagina": pagina,
            "totais": contagem_por_status(
                request.user, aplicar_filtros(visiveis, params_contagem, campo_data="atualizado_em")
            ),
            "equipes": equipes_do_usuario(request.user),
            "status_choices": status_ativos(),
            "filtro_de": filtro_de,
            "filtro_ate": filtro_ate,
        },
    )


@login_required
def ocorrencia_nova(request):
    usuario = request.user
    equipes = list(equipes_do_usuario(usuario))
    if not equipes:
        mensagem = (
            "Cadastre uma equipe antes de lançar ocorrências."
            if usuario.acesso_total
            else "Peça ao responsável da empresa para incluir você em uma equipe."
        )
        return sem_acesso(request, mensagem)
    fixar = (not usuario.acesso_total) and usuario.vinculos.count() == 1
    produtos = []
    queryset = Equipe.objects.filter(id__in=[equipe.id for equipe in equipes])
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES, equipes=queryset, fixar_equipe=fixar)
        produtos = json_solto(request.POST.get("produtos_json"))
        if form.is_valid():
            dados = dict(form.cleaned_data)
            dados.pop("produtos_json", None)
            if fixar:
                dados["equipe"] = None
            try:
                ocorrencia = criar_ocorrencia(usuario, dados, produtos, request.FILES)
            except ValidationError as exc:
                adicionar_erros(form, exc)
            except PermissionDenied as exc:
                return sem_acesso(request, str(exc))
            else:
                messages.success(request, "Ocorrência registrada. A equipe já pode vê-la.")
                return redirect("ocorrencia_detalhe", pk=ocorrencia.pk)
    else:
        form = OcorrenciaForm(equipes=queryset, fixar_equipe=fixar)
    return render(
        request,
        "painel/ocorrencia_form.html",
        {"form": form, "produtos_iniciais": produtos, "editando": False},
    )


def _contexto_ficha(request, ocorrencia):
    return {
        "ocorrencia": ocorrencia,
        "pode_editar": pode_editar_ocorrencia(request.user, ocorrencia),
        "pode_excluir": pode_excluir_ocorrencia(request.user, ocorrencia),
        "status_choices": status_ativos(),
        "form_complemento": ComplementoForm(),
        "encerrada": ocorrencia.status.encerra,
    }


@login_required
def ocorrencia_detalhe(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    return render(request, "painel/ocorrencia_detalhe.html", _contexto_ficha(request, ocorrencia))


@login_required
def ocorrencia_imprimir(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    return render(request, "painel/relatorio_ficha.html", {"ocorrencia": ocorrencia})


@login_required
def ocorrencia_editar(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    if not pode_editar_ocorrencia(request.user, ocorrencia):
        return sem_acesso(request, "Você só pode editar as ocorrências que você registrou.")
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES, fixar_equipe=True)
        produtos = json_solto(request.POST.get("produtos_json"))
        remover = [int(pk) for pk in request.POST.getlist("remover_anexo") if str(pk).isdigit()]
        if form.is_valid():
            dados = dict(form.cleaned_data)
            dados.pop("produtos_json", None)
            try:
                editar_ocorrencia(
                    request.user, ocorrencia, dados, produtos, request.FILES, remover
                )
            except ValidationError as exc:
                adicionar_erros(form, exc)
            except PermissionDenied as exc:
                return sem_acesso(request, str(exc))
            else:
                messages.success(request, "Ocorrência atualizada.")
                return redirect("ocorrencia_detalhe", pk=ocorrencia.pk)
    else:
        form = OcorrenciaForm(
            fixar_equipe=True,
            initial={
                "numero_nota": ocorrencia.numero_nota,
                "cliente": ocorrencia.cliente,
                "peso": str(ocorrencia.peso).replace(".", ","),
                "valor": str(ocorrencia.valor).replace(".", ","),
                "tipo_devolucao": ocorrencia.tipo_devolucao,
                "placa": ocorrencia.placa,
                "setor": ocorrencia.setor_id,
                "motivo": ocorrencia.motivo_id,
                "descricao": ocorrencia.descricao,
            },
        )
        produtos = produtos_iniciais_da_ocorrencia(ocorrencia)
    return render(
        request,
        "painel/ocorrencia_form.html",
        {
            "form": form,
            "produtos_iniciais": produtos,
            "editando": True,
            "ocorrencia": ocorrencia,
        },
    )


def _pedido_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@login_required
@require_POST
def ocorrencia_status(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    try:
        alterar_status(request.user, ocorrencia, request.POST.get("status"))
    except ValidationError as exc:
        mensagens = erros_para_dict(exc)
        detalhe = mensagens.get("status", mensagens.get("detail", ["Status inválido."]))[0]
        if _pedido_ajax(request):
            return JsonResponse({"ok": False, "detail": detalhe}, status=400)
        messages.error(request, detalhe)
    except PermissionDenied as exc:
        if _pedido_ajax(request):
            return JsonResponse({"ok": False, "detail": str(exc)}, status=403)
        return sem_acesso(request, str(exc))
    else:
        if _pedido_ajax(request):
            return JsonResponse(
                {
                    "ok": True,
                    "status": ocorrencia.status_id,
                    "status_label": ocorrencia.get_status_display(),
                    "status_cor": ocorrencia.status.cor_destaque(),
                }
            )
        messages.success(request, f"Status atualizado para {ocorrencia.get_status_display()}.")
    return redirect(destino_seguro(request, request.POST.get("next")))


@login_required
@require_POST
def ocorrencia_complemento(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    form = ComplementoForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.get("texto", ["Escreva o complemento."])[0])
        return redirect("ocorrencia_detalhe", pk=ocorrencia.pk)
    estava_encerrada = ocorrencia.status.encerra
    try:
        criar_complemento(request.user, ocorrencia, form.cleaned_data["texto"])
    except ValidationError as exc:
        mensagens = erros_para_dict(exc)
        messages.error(request, next(iter(mensagens.values()))[0])
    except PermissionDenied as exc:
        return sem_acesso(request, str(exc))
    else:
        if estava_encerrada:
            messages.success(
                request,
                "Complemento registrado e ocorrência reaberta. O lançamento original permanece.",
            )
        else:
            messages.success(request, "Complemento registrado.")
    return redirect("ocorrencia_detalhe", pk=ocorrencia.pk)


@login_required
@require_POST
def ocorrencia_reabrir(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    try:
        reabrir_ocorrencia(request.user, ocorrencia, request.POST.get("texto") or "")
    except ValidationError as exc:
        mensagens = erros_para_dict(exc)
        messages.error(request, next(iter(mensagens.values()))[0])
    except PermissionDenied as exc:
        return sem_acesso(request, str(exc))
    else:
        messages.success(
            request,
            "Ocorrência reaberta. A data de origem permanece a mesma; ela voltou ao painel pela movimentação de hoje.",
        )
    return redirect("ocorrencia_detalhe", pk=ocorrencia.pk)


@login_required
@require_POST
def ocorrencia_excluir(request, pk):
    ocorrencia = get_object_or_404(ocorrencias_visiveis(request.user), pk=pk)
    if not pode_excluir_ocorrencia(request.user, ocorrencia):
        return sem_acesso(request, "Você não pode excluir ocorrências.")
    excluir_ocorrencia(request.user, ocorrencia)
    messages.success(request, "Ocorrência excluída. A auditoria guardou o registro.")
    return redirect("painel")


@login_required
def relatorios(request):
    params, filtro_de, filtro_ate = _filtros(request)
    qs = (
        aplicar_filtros(ocorrencias_visiveis(request.user), params)
        .select_related("nota")
        .prefetch_related("produtos__item_nota", "nota__itens")
    )
    imprimir = request.GET.get("print") == "1"
    pagina = None if imprimir else Paginator(qs, POR_PAGINA).get_page(request.GET.get("page"))
    ocorrencias = list(qs) if imprimir else pagina
    marcar_peso_valor_relatorio(ocorrencias if imprimir else pagina.object_list)
    return render(
        request,
        "painel/relatorios.html",
        {
            "ocorrencias": ocorrencias,
            "pagina": pagina,
            "equipes": equipes_do_usuario(request.user),
            "status_choices": status_ativos(),
            "resumo_filtros": _resumo_filtros(params),
            "filtro_de": filtro_de,
            "filtro_ate": filtro_ate,
            "relatorio_atual": "lista",
        },
    )


def _relatorio_agrupado(request, agrupamento, titulo, atual):
    params, filtro_de, filtro_ate = _filtros(request)
    qs = aplicar_filtros(ocorrencias_visiveis(request.user), params)
    grupos, total_peso, total_valor = relatorio_agrupado(qs, agrupamento)
    return render(
        request,
        "painel/relatorio_agrupado.html",
        {
            "titulo": titulo,
            "grupos": grupos,
            "total_peso": total_peso,
            "total_valor": total_valor,
            "total_ocorrencias": sum(grupo["quantidade"] for grupo in grupos),
            "resumo_filtros": _resumo_filtros(params),
            "filtro_de": filtro_de,
            "filtro_ate": filtro_ate,
            "relatorio_atual": atual,
        },
    )


@login_required
def relatorio_setores(request):
    return _relatorio_agrupado(request, "setor", "Por setor responsável", "setores")


@login_required
def relatorio_placas(request):
    return _relatorio_agrupado(request, "placa", "Por placa", "placas")


@login_required
def relatorio_motivos(request):
    return _relatorio_agrupado(request, "motivo", "Por motivo", "motivos")


def _resumo_filtros(params):
    partes = []
    if params.get("q"):
        partes.append(f"“{params.get('q')}”")
    if params.get("de"):
        partes.append(f"de {params.get('de')}")
    if params.get("ate"):
        partes.append(f"até {params.get('ate')}")
    return " · ".join(partes) if partes else "Todas as ocorrências que você pode ver"


@login_required
def auditoria(request):
    if not pode_ver_auditoria(request.user):
        return sem_acesso(request, "A auditoria fica com o gerente de cada equipe.")
    qs = auditoria_visivel(request.user)
    equipe_id = request.GET.get("equipe")
    if equipe_id and str(equipe_id).isdigit():
        qs = qs.filter(equipe_id=int(equipe_id))
    texto = (request.GET.get("q") or "").strip()
    if texto:
        qs = qs.filter(resumo__icontains=texto)
    pagina = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "painel/auditoria.html",
        {"pagina": pagina, "equipes": equipes_de_auditoria(request.user)},
    )


@login_required
def anexo_arquivo(request, pk):
    anexo = get_object_or_404(AnexoOcorrencia.objects.select_related("ocorrencia"), pk=pk)
    if not pode_ver_ocorrencia(request.user, anexo.ocorrencia):
        return sem_acesso(request, "Você não pode ver este anexo.")
    if not anexo.arquivo:
        raise Http404()
    return FileResponse(
        anexo.arquivo.open("rb"),
        as_attachment=not anexo.eh_imagem(),
        filename=anexo.nome,
    )


