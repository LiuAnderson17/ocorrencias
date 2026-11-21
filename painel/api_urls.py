from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from painel.api import (
    AnexoAPIView,
    AuditoriaViewSet,
    EquipeViewSet,
    EuView,
    MotivoViewSet,
    SetorViewSet,
    NotaAbertasView,
    NotaFiscalView,
    NotaXmlView,
    OcorrenciaViewSet,
    StatusViewSet,
    TokenAcessoView,
)

router = DefaultRouter()
router.register("ocorrencias", OcorrenciaViewSet, basename="api-ocorrencias")
router.register("equipes", EquipeViewSet, basename="api-equipes")
router.register("auditoria", AuditoriaViewSet, basename="api-auditoria")
router.register("status", StatusViewSet, basename="api-status")
router.register("motivos", MotivoViewSet, basename="api-motivos")
router.register("setores", SetorViewSet, basename="api-setores")

urlpatterns = [
    path("auth/token/", TokenAcessoView.as_view(), name="api-token"),
    path("auth/eu/", EuView.as_view(), name="api-eu"),
    path("notas/xml/", NotaXmlView.as_view(), name="api-nota-xml"),
    path("notas/<str:numero>/abertas/", NotaAbertasView.as_view(), name="api-nota-abertas"),
    path("notas/<str:numero>/", NotaFiscalView.as_view(), name="api-nota"),
    path("anexos/<int:pk>/", AnexoAPIView.as_view(), name="api-anexo"),
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("", include(router.urls)),
]
