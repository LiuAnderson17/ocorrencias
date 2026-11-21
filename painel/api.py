from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from painel.models import AnexoOcorrencia, Auditoria, Equipe, MotivoOcorrencia, Ocorrencia, SetorOcorrencia, StatusOcorrencia
from painel.nfe import importar_xml
from painel.permissions import AuditoriaAPIPermission, OcorrenciaAPIPermission
from painel.serializers import (
    AnexoOcorrenciaSerializer,
    AuditoriaSerializer,
    ComplementoEntradaSerializer,
    EquipeSerializer,
    EuSerializer,
    MotivoOcorrenciaSerializer,
    SetorOcorrenciaSerializer,
    NotaFiscalSerializer,
    OcorrenciaAbertaSerializer,
    OcorrenciaSerializer,
    OcorrenciaWriteSerializer,
    StatusOcorrenciaSerializer,
    StatusSerializer,
    XmlNotaSerializer,
)
from painel.services import (
    aplicar_filtros,
    auditoria_visivel,
    buscar_nota,
    equipes_do_usuario,
    erros_para_dict,
    excluir_ocorrencia,
    gravar_anexos,
    motivos_ativos,
    setores_ativos,
    reabrir_ocorrencia,
    ocorrencias_abertas_da_nota,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
    pode_ver_auditoria,
    status_ativos,
)


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class TokenAcessoView(ObtainAuthToken):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.validated_data["user"]
        token, _criado = Token.objects.get_or_create(user=usuario)
        return Response(
            {
                "token": token.key,
                "usuario": {
                    "id": usuario.id,
                    "username": usuario.username,
                    "nome": usuario.nome_curto(),
                    "acesso_total": usuario.acesso_total,
                },
            }
        )


class EuView(APIView):
    serializer_class = EuSerializer

    def get(self, request):
        usuario = request.user
        vinculos = usuario.vinculos.select_related("equipe")
        return Response(
            {
                "id": usuario.id,
                "username": usuario.username,
                "nome": usuario.nome_curto(),
                "acesso_total": usuario.acesso_total,
                "equipes": [
                    {"id": v.equipe_id, "nome": v.equipe.nome, "papel": v.papel} for v in vinculos
                ],
            }
        )


class NotaFiscalView(APIView):
    serializer_class = NotaFiscalSerializer

    @extend_schema(
        summary="Buscar nota pelo número",
        description=(
            "Caminho principal de integração. Consulta a origem configurada "
            "(cadastro local ou banco da empresa) e devolve cliente, peso, valor, placa e itens."
        ),
        responses={200: NotaFiscalSerializer},
        tags=["notas"],
    )
    def get(self, request, numero):
        nota = buscar_nota(numero)
        if nota is None:
            return Response(
                {
                    "detail": (
                        "Nota não encontrada na origem configurada. "
                        "Preencha os campos e os produtos manualmente."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(NotaFiscalSerializer(nota).data)


class NotaAbertasView(APIView):
    serializer_class = OcorrenciaAbertaSerializer

    @extend_schema(
        summary="Ocorrências em aberto desta nota",
        description=(
            "Avisa se já existe ocorrência não encerrada com o mesmo número, "
            "mesmo quando a nota ainda não está no cadastro local."
        ),
        tags=["notas"],
    )
    def get(self, request, numero):
        ignorar = request.query_params.get("ignorar")
        ignorar_id = int(ignorar) if ignorar and str(ignorar).isdigit() else None
        qs = ocorrencias_abertas_da_nota(request.user, numero, ignorar_id)
        return Response(
            {
                "abertas": OcorrenciaAbertaSerializer(
                    qs, many=True, context={"request": request}
                ).data
            }
        )


@extend_schema(
    summary="Importar XML de NF-e ou CT-e",
    description="Atalho opcional. Grava a nota no cadastro local para o preenchimento automático.",
    request=XmlNotaSerializer,
    responses={200: NotaFiscalSerializer},
    tags=["notas"],
)
class NotaXmlView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = NotaFiscalSerializer

    def post(self, request):
        try:
            nota = importar_xml(request.FILES.get("arquivo"))
        except ValidationError as exc:
            erros = erros_para_dict(exc)
            detalhe = next(iter(erros.values()))[0]
            return Response({"detail": detalhe}, status=status.HTTP_400_BAD_REQUEST)
        return Response(NotaFiscalSerializer(nota).data)


class StatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StatusOcorrencia.objects.all()
    serializer_class = StatusOcorrenciaSerializer

    def get_queryset(self):
        return status_ativos()


class MotivoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MotivoOcorrencia.objects.all()
    serializer_class = MotivoOcorrenciaSerializer

    def get_queryset(self):
        return motivos_ativos()


class SetorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SetorOcorrencia.objects.all()
    serializer_class = SetorOcorrenciaSerializer

    def get_queryset(self):
        return setores_ativos()


class EquipeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Equipe.objects.all()
    serializer_class = EquipeSerializer

    def get_queryset(self):
        return equipes_do_usuario(self.request.user)


class OcorrenciaViewSet(viewsets.ModelViewSet):
    queryset = Ocorrencia.objects.all()
    permission_classes = [IsAuthenticated, OcorrenciaAPIPermission]
    http_method_names = ["get", "post", "put", "delete", "head", "options"]

    def get_queryset(self):
        campo = (
            "atualizado_em"
            if self.request.query_params.get("por") == "movimentacao"
            else "data_hora"
        )
        return aplicar_filtros(
            ocorrencias_do_request(self.request), self.request.query_params, campo_data=campo
        )

    def get_serializer_class(self):
        if self.action in {"create", "update"}:
            return OcorrenciaWriteSerializer
        return OcorrenciaSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ocorrencia = serializer.save()
        return Response(
            OcorrenciaSerializer(ocorrencia, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        ocorrencia = self.get_object()
        if not pode_editar_ocorrencia(request.user, ocorrencia):
            return Response(
                {"detail": "Você só pode editar as ocorrências que você registrou."},
                status=status.HTTP_403_FORBIDDEN,
            )
        resposta = super().update(request, *args, **kwargs)
        if resposta.status_code == status.HTTP_200_OK:
            ocorrencia.refresh_from_db()
            return Response(OcorrenciaSerializer(ocorrencia, context={"request": request}).data)
        return resposta

    def destroy(self, request, *args, **kwargs):
        ocorrencia = self.get_object()
        if not pode_excluir_ocorrencia(request.user, ocorrencia):
            return Response(
                {"detail": "Você não pode excluir ocorrências."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            excluir_ocorrencia(request.user, ocorrencia)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        ocorrencia = self.get_object()
        serializer = StatusSerializer(
            data=request.data,
            context={"request": request, "ocorrencia": ocorrencia},
        )
        serializer.is_valid(raise_exception=True)
        try:
            atualizada = serializer.save()
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(OcorrenciaSerializer(atualizada, context={"request": request}).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def anexos(self, request, pk=None):
        ocorrencia = self.get_object()
        if not pode_editar_ocorrencia(request.user, ocorrencia):
            return Response(
                {"detail": "Você só pode anexar arquivos nas ocorrências que você registrou."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            gravar_anexos(request.user, ocorrencia, request.FILES)
        except ValidationError as exc:
            erros = erros_para_dict(exc)
            detalhe = next(iter(erros.values()))[0]
            return Response({"detail": detalhe}, status=status.HTTP_400_BAD_REQUEST)
        ocorrencia.refresh_from_db()
        return Response(OcorrenciaSerializer(ocorrencia, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def complemento(self, request, pk=None):
        ocorrencia = self.get_object()
        serializer = ComplementoEntradaSerializer(
            data=request.data, context={"request": request, "ocorrencia": ocorrencia}
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        ocorrencia.refresh_from_db()
        return Response(OcorrenciaSerializer(ocorrencia, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        ocorrencia = self.get_object()
        try:
            atualizada = reabrir_ocorrencia(request.user, ocorrencia, request.data.get("texto") or "")
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            erros = erros_para_dict(exc)
            detalhe = next(iter(erros.values()))[0]
            return Response({"detail": detalhe}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OcorrenciaSerializer(atualizada, context={"request": request}).data)


class AnexoAPIView(APIView):
    serializer_class = AnexoOcorrenciaSerializer

    def delete(self, request, pk):
        from django.shortcuts import get_object_or_404

        anexo = get_object_or_404(AnexoOcorrencia.objects.select_related("ocorrencia"), pk=pk)
        if not pode_editar_ocorrencia(request.user, anexo.ocorrencia):
            return Response(
                {"detail": "Você só pode remover anexos das ocorrências que você registrou."},
                status=status.HTTP_403_FORBIDDEN,
            )
        anexo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def ocorrencias_do_request(request):
    from painel.services import ocorrencias_visiveis

    return ocorrencias_visiveis(request.user)


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Auditoria.objects.all()
    permission_classes = [IsAuthenticated, AuditoriaAPIPermission]
    serializer_class = AuditoriaSerializer

    def get_queryset(self):
        if not pode_ver_auditoria(self.request.user):
            return Auditoria.objects.none()
        qs = auditoria_visivel(self.request.user)
        equipe = self.request.query_params.get("equipe")
        if equipe and str(equipe).isdigit():
            qs = qs.filter(equipe_id=int(equipe))
        return qs

    def list(self, request, *args, **kwargs):
        if not pode_ver_auditoria(request.user):
            return Response(
                {"detail": "A auditoria é visível para o gerente da equipe."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not pode_ver_auditoria(request.user):
            return Response(
                {"detail": "A auditoria é visível para o gerente da equipe."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)
