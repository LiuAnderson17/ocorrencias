from rest_framework.permissions import SAFE_METHODS, BasePermission

from painel.services import (
    pode_alterar_status,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
    pode_ver_auditoria,
    pode_ver_ocorrencia,
)


class OcorrenciaAPIPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not pode_ver_ocorrencia(request.user, obj):
            self.message = "Esta ocorrência não está nas suas equipes."
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) == "status":
            return pode_alterar_status(request.user, obj)
        if request.method == "DELETE":
            if not pode_excluir_ocorrencia(request.user, obj):
                self.message = "Você não pode excluir ocorrências."
                return False
            return True
        if request.method in ("PUT", "PATCH"):
            if not pode_editar_ocorrencia(request.user, obj):
                self.message = "Você só pode editar as ocorrências que você registrou."
                return False
            return True
        return True


class AuditoriaAPIPermission(BasePermission):
    message = "A auditoria é visível para o gerente da equipe."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and pode_ver_auditoria(request.user))
