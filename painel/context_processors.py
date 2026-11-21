from django.utils import timezone

from painel.services import FILTRO_ATE, FILTRO_DE, pode_ver_auditoria


def painel_nav(request):
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {}
    hoje = timezone.localdate().isoformat()
    return {
        "vinculos_nav": list(usuario.vinculos.select_related("equipe")),
        "pode_auditar": pode_ver_auditoria(usuario),
        "filtro_de": request.session.get(FILTRO_DE) or hoje,
        "filtro_ate": request.session.get(FILTRO_ATE) or hoje,
    }
