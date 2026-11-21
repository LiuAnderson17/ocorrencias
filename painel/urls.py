from django.urls import path

from painel import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("entrar/", views.entrar, name="entrar"),
    path("sair/", views.sair, name="sair"),
    path("ocorrencias/nova/", views.ocorrencia_nova, name="ocorrencia_nova"),
    path("ocorrencias/<int:pk>/", views.ocorrencia_detalhe, name="ocorrencia_detalhe"),
    path("ocorrencias/<int:pk>/imprimir/", views.ocorrencia_imprimir, name="ocorrencia_imprimir"),
    path("ocorrencias/<int:pk>/editar/", views.ocorrencia_editar, name="ocorrencia_editar"),
    path("ocorrencias/<int:pk>/status/", views.ocorrencia_status, name="ocorrencia_status"),
    path("ocorrencias/<int:pk>/complemento/", views.ocorrencia_complemento, name="ocorrencia_complemento"),
    path("ocorrencias/<int:pk>/reabrir/", views.ocorrencia_reabrir, name="ocorrencia_reabrir"),
    path("ocorrencias/<int:pk>/excluir/", views.ocorrencia_excluir, name="ocorrencia_excluir"),
    path("relatorios/", views.relatorios, name="relatorios"),
    path("relatorios/setores/", views.relatorio_setores, name="relatorio_setores"),
    path("relatorios/placas/", views.relatorio_placas, name="relatorio_placas"),
    path("relatorios/motivos/", views.relatorio_motivos, name="relatorio_motivos"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("anexos/<int:pk>/", views.anexo_arquivo, name="anexo_arquivo"),
]
