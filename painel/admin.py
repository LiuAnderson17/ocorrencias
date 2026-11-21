from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from rest_framework.authtoken.models import Token

from painel.models import (
    Auditoria,
    Equipe,
    ItemNota,
    MembroEquipe,
    NotaFiscal,
    ComplementoOcorrencia,
    MotivoOcorrencia,
    SetorOcorrencia,
    Ocorrencia,
    ProdutoDevolvido,
    StatusOcorrencia,
    Usuario,
    AnexoOcorrencia,
)

admin.site.site_header = "Ocorrências · Administração"
admin.site.site_title = "Ocorrências"
admin.site.index_title = "Usuários, equipes, motivos, setores, notas e API"


class MembroNaEquipeInline(admin.TabularInline):
    model = MembroEquipe
    extra = 1
    autocomplete_fields = ("usuario",)


class MembroNoUsuarioInline(admin.TabularInline):
    model = MembroEquipe
    extra = 1
    autocomplete_fields = ("equipe",)


class TokenInline(admin.StackedInline):
    model = Token
    extra = 0
    max_num = 1
    can_delete = False
    readonly_fields = ("key", "created")
    verbose_name = "token da API"
    verbose_name_plural = "token da API"


class ItemNotaInline(admin.TabularInline):
    model = ItemNota
    extra = 1


class ProdutoDevolvidoInline(admin.TabularInline):
    model = ProdutoDevolvido
    extra = 0


class AnexoOcorrenciaInline(admin.TabularInline):
    model = AnexoOcorrencia
    extra = 0
    readonly_fields = ("enviado_em", "enviado_por", "nome", "tipo")


class ComplementoOcorrenciaInline(admin.TabularInline):
    model = ComplementoOcorrencia
    extra = 0
    readonly_fields = ("autor", "texto", "reabriu", "criado_em")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SetorOcorrencia)
class SetorOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ordem", "ativo")
    list_editable = ("ordem", "ativo")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(MotivoOcorrencia)
class MotivoOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ordem", "ativo")
    list_editable = ("ordem", "ativo")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Acesso no painel",
            {
                "fields": ("acesso_total",),
                "description": (
                    "Marque acesso total para ver todas as equipes. "
                    "Marque equipe de staff para entrar neste admin e gerenciar usuários."
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Acesso no painel", {"fields": ("acesso_total",)}),)
    list_display = (
        "username",
        "first_name",
        "last_name",
        "equipes_resumo",
        "acesso_total",
        "is_staff",
        "is_active",
    )
    list_filter = ("acesso_total", "is_staff", "is_active", "vinculos__equipe")
    search_fields = ("username", "first_name", "last_name", "email")
    inlines = [MembroNoUsuarioInline, TokenInline]

    @admin.display(description="equipes")
    def equipes_resumo(self, obj):
        nomes = [f"{v.equipe.nome} ({v.get_papel_display()})" for v in obj.vinculos.select_related("equipe")]
        return ", ".join(nomes) if nomes else "—"


class StatusOcorrenciaForm(forms.ModelForm):
    class Meta:
        model = StatusOcorrencia
        fields = "__all__"
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}


@admin.register(StatusOcorrencia)
class StatusOcorrenciaAdmin(admin.ModelAdmin):
    form = StatusOcorrenciaForm
    list_display = ("nome", "amostra_cor", "ordem", "ativo", "padrao", "encerra")
    list_editable = ("ordem", "ativo", "padrao", "encerra")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}

    @admin.display(description="cor")
    def amostra_cor(self, obj):
        fundo = obj.cor_fundo()
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:.45rem">'
            '<span style="width:1.15rem;height:1.15rem;border-radius:999px;'
            "background:{};border:1px solid #d0c6b8\"></span>{}</span>",
            fundo,
            fundo,
        )


@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ("nome", "total_membros")
    search_fields = ["nome"]
    inlines = [MembroNaEquipeInline]

    @admin.display(description="membros")
    def total_membros(self, obj):
        return obj.membros.count()


@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "valor", "peso", "placa")
    search_fields = ("numero", "cliente", "placa")
    inlines = [ItemNotaInline]


@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("numero_nota", "cliente", "equipe", "motivo", "setor", "status", "criado_por", "data_hora")
    list_filter = ("status", "motivo", "setor", "equipe", "tipo_devolucao")
    search_fields = ("numero_nota", "cliente", "placa")
    autocomplete_fields = ("equipe", "criado_por", "nota", "status", "motivo", "setor")
    inlines = [ProdutoDevolvidoInline, AnexoOcorrenciaInline, ComplementoOcorrenciaInline]
    readonly_fields = ("data_hora", "atualizado_em")


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "usuario", "equipe", "acao", "resumo")
    list_filter = ("acao", "equipe")
    search_fields = ("resumo", "usuario__username")
    readonly_fields = (
        "criado_em",
        "usuario",
        "equipe",
        "ocorrencia",
        "referencia",
        "acao",
        "resumo",
        "detalhes",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


