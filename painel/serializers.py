from rest_framework import serializers

from painel.models import (
    AnexoOcorrencia,
    Auditoria,
    ComplementoOcorrencia,
    Equipe,
    MotivoOcorrencia,
    SetorOcorrencia,
    NotaFiscal,
    Ocorrencia,
    ProdutoDevolvido,
    StatusOcorrencia,
)
from painel.services import (
    alterar_status,
    criar_complemento,
    criar_ocorrencia,
    editar_ocorrencia,
    reabrir_ocorrencia,
    erros_para_dict,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
)
from rest_framework.reverse import reverse
from django.core.exceptions import PermissionDenied, ValidationError


class StatusOcorrenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusOcorrencia
        fields = ["id", "nome", "slug", "cor", "ordem", "padrao", "encerra"]


class MotivoOcorrenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MotivoOcorrencia
        fields = ["id", "nome", "slug", "ordem"]


class SetorOcorrenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SetorOcorrencia
        fields = ["id", "nome", "slug", "ordem"]


class AnexoOcorrenciaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = AnexoOcorrencia
        fields = ["id", "nome", "tipo", "enviado_em", "url", "imagem"]

    def get_url(self, obj) -> str:
        request = self.context.get("request")
        return reverse("anexo_arquivo", kwargs={"pk": obj.pk}, request=request)

    def get_imagem(self, obj) -> bool:
        return obj.eh_imagem()


class OcorrenciaAbertaSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    equipe_nome = serializers.CharField(source="equipe.nome", read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Ocorrencia
        fields = ["id", "numero_nota", "cliente", "equipe_nome", "status_label", "data_hora", "url"]

    def get_url(self, obj) -> str:
        request = self.context.get("request")
        return reverse("ocorrencia_detalhe", kwargs={"pk": obj.pk}, request=request)


class EquipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipe
        fields = ["id", "nome", "descricao"]


class ItemNotaSerializer(serializers.ModelSerializer):
    class Meta:
        from painel.models import ItemNota

        model = ItemNota
        fields = ["id", "codigo", "descricao", "quantidade", "unidade", "peso", "valor"]


class NotaFiscalSerializer(serializers.ModelSerializer):
    itens = ItemNotaSerializer(many=True, read_only=True)

    class Meta:
        model = NotaFiscal
        fields = ["numero", "cliente", "peso", "valor", "placa", "itens"]


class XmlNotaSerializer(serializers.Serializer):
    arquivo = serializers.FileField()


class EquipeVinculoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    papel = serializers.CharField()


class EuSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    nome = serializers.CharField()
    acesso_total = serializers.BooleanField()
    equipes = EquipeVinculoSerializer(many=True)


class ComplementoOcorrenciaSerializer(serializers.ModelSerializer):
    autor_nome = serializers.SerializerMethodField()

    class Meta:
        model = ComplementoOcorrencia
        fields = ["id", "autor", "autor_nome", "texto", "reabriu", "criado_em"]

    def get_autor_nome(self, obj) -> str:
        return obj.autor.nome_curto()


class ComplementoEntradaSerializer(serializers.Serializer):
    texto = serializers.CharField(min_length=3, max_length=4000)

    def save(self, **kwargs):
        ocorrencia = self.context["ocorrencia"]
        usuario = self.context["request"].user
        try:
            return criar_complemento(usuario, ocorrencia, self.validated_data["texto"])
        except ValidationError as exc:
            raise serializers.ValidationError(erros_para_dict(exc)) from exc


class ProdutoDevolvidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdutoDevolvido
        fields = ["id", "item_nota", "codigo", "descricao", "quantidade", "unidade"]


class ProdutoEntradaSerializer(serializers.Serializer):
    item_nota = serializers.IntegerField(required=False, allow_null=True)
    codigo = serializers.CharField(required=False, allow_blank=True)
    descricao = serializers.CharField(required=False, allow_blank=True)
    quantidade = serializers.CharField()
    unidade = serializers.CharField(required=False, allow_blank=True)
    selecionado = serializers.BooleanField(required=False, default=True)


class OcorrenciaSerializer(serializers.ModelSerializer):
    produtos = ProdutoDevolvidoSerializer(many=True, read_only=True)
    anexos = AnexoOcorrenciaSerializer(many=True, read_only=True)
    complementos = ComplementoOcorrenciaSerializer(many=True, read_only=True)
    encerrada = serializers.BooleanField(source="status.encerra", read_only=True)
    equipe_nome = serializers.CharField(source="equipe.nome", read_only=True)
    motivo_nome = serializers.CharField(source="motivo.nome", read_only=True)
    criado_por_nome = serializers.SerializerMethodField()
    status_id = serializers.IntegerField(source="status.id", read_only=True)
    status_slug = serializers.CharField(source="status.slug", read_only=True)
    status_cor = serializers.CharField(source="status.cor", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    tipo_label = serializers.CharField(source="get_tipo_devolucao_display", read_only=True)
    setor_label = serializers.CharField(source="setor.nome", read_only=True)
    pode_editar = serializers.SerializerMethodField()
    pode_excluir = serializers.SerializerMethodField()

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "equipe",
            "equipe_nome",
            "criado_por",
            "criado_por_nome",
            "nota",
            "numero_nota",
            "cliente",
            "peso",
            "valor",
            "tipo_devolucao",
            "tipo_label",
            "data_hora",
            "placa",
            "setor",
            "setor_label",
            "motivo",
            "motivo_nome",
            "descricao",
            "status",
            "status_id",
            "status_slug",
            "status_cor",
            "status_label",
            "atualizado_em",
            "encerrada",
            "produtos",
            "anexos",
            "complementos",
            "pode_editar",
            "pode_excluir",
        ]

    def get_criado_por_nome(self, obj) -> str:
        return obj.criado_por.nome_curto()

    def get_pode_editar(self, obj) -> bool:
        usuario = self.context["request"].user
        return pode_editar_ocorrencia(usuario, obj)

    def get_pode_excluir(self, obj) -> bool:
        return pode_excluir_ocorrencia(self.context["request"].user, obj)


class OcorrenciaWriteSerializer(serializers.Serializer):
    equipe = serializers.PrimaryKeyRelatedField(
        queryset=Equipe.objects.all(), required=False, allow_null=True
    )
    numero_nota = serializers.CharField()
    cliente = serializers.CharField()
    peso = serializers.CharField()
    valor = serializers.CharField()
    tipo_devolucao = serializers.ChoiceField(choices=Ocorrencia.TipoDevolucao.choices)
    placa = serializers.CharField(required=False, allow_blank=True)
    setor = serializers.PrimaryKeyRelatedField(queryset=SetorOcorrencia.objects.filter(ativo=True))
    motivo = serializers.PrimaryKeyRelatedField(queryset=MotivoOcorrencia.objects.filter(ativo=True))
    descricao = serializers.CharField()
    produtos = ProdutoEntradaSerializer(many=True)

    def create(self, validated_data):
        produtos = validated_data.pop("produtos")
        try:
            return criar_ocorrencia(self.context["request"].user, validated_data, produtos)
        except ValidationError as exc:
            raise serializers.ValidationError(erros_para_dict(exc)) from exc

    def update(self, instance, validated_data):
        produtos = validated_data.pop("produtos")
        validated_data.pop("equipe", None)
        try:
            return editar_ocorrencia(self.context["request"].user, instance, validated_data, produtos)
        except ValidationError as exc:
            raise serializers.ValidationError(erros_para_dict(exc)) from exc
        except PermissionDenied as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class AuditoriaSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()
    equipe_nome = serializers.CharField(source="equipe.nome", read_only=True)
    acao_label = serializers.CharField(source="get_acao_display", read_only=True)

    class Meta:
        model = Auditoria
        fields = [
            "id",
            "criado_em",
            "usuario",
            "usuario_nome",
            "equipe",
            "equipe_nome",
            "ocorrencia",
            "referencia",
            "acao",
            "acao_label",
            "resumo",
            "detalhes",
        ]

    def get_usuario_nome(self, obj) -> str:
        return obj.usuario.nome_curto()


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()

    def save(self, **kwargs):
        ocorrencia = self.context["ocorrencia"]
        usuario = self.context["request"].user
        try:
            return alterar_status(usuario, ocorrencia, self.validated_data["status"])
        except ValidationError as exc:
            raise serializers.ValidationError(erros_para_dict(exc)) from exc
