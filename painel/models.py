import re
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    acesso_total = models.BooleanField(
        "acesso total",
        default=False,
        help_text="Vê e administra os registros de todas as equipes.",
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def nome_curto(self):
        return self.get_full_name() or self.username


class Equipe(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "equipe"
        verbose_name_plural = "equipes"

    def __str__(self):
        return self.nome


class MembroEquipe(models.Model):
    class Papel(models.TextChoices):
        MEMBRO = "membro", "Membro"
        GERENTE = "gerente", "Gerente"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="vinculos")
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name="membros")
    papel = models.CharField(max_length=12, choices=Papel.choices, default=Papel.MEMBRO)

    class Meta:
        verbose_name = "membro da equipe"
        verbose_name_plural = "membros das equipes"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "equipe"], name="membro_unico_por_equipe")
        ]

    def __str__(self):
        return f"{self.usuario} · {self.equipe} ({self.get_papel_display()})"


class StatusOcorrencia(models.Model):
    nome = models.CharField(max_length=40)
    slug = models.SlugField(max_length=40, unique=True)
    cor = models.CharField(
        "cor",
        max_length=7,
        default="#E8E0D4",
        help_text="Clique no campo para escolher qualquer cor.",
    )
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(
        "status inicial",
        default=False,
        help_text="Usado automaticamente ao lançar uma ocorrência.",
    )
    encerra = models.BooleanField(
        "encerra a ocorrência",
        default=False,
        help_text="Com este status, a nota deixa de contar como ocorrência em aberto.",
    )

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "status"
        verbose_name_plural = "status"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.nome)[:40] or "status"
        super().save(*args, **kwargs)
        if self.padrao:
            StatusOcorrencia.objects.exclude(pk=self.pk).update(padrao=False)

    def cor_fundo(self):
        valor = (self.cor or "").strip()
        antigas = {
            "cobre": "#F8E7CF",
            "oliva": "#E3F3EA",
            "azul": "#E3EEF9",
            "vermelho": "#F8E0DC",
            "cinza": "#E8E0D4",
        }
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", valor):
            return valor.upper()
        return antigas.get(valor, "#E8E0D4")

    def cor_texto(self):
        hex_cor = self.cor_fundo().lstrip("#")
        vermelho, verde, azul = (int(hex_cor[i : i + 2], 16) for i in (0, 2, 4))
        claro = (0.2126 * vermelho) + (0.7152 * verde) + (0.0722 * azul) > 155
        return "#1C1914" if claro else "#FFFDF8"

    def cor_destaque(self):
        return self.cor_fundo()


class SetorOcorrencia(models.Model):
    nome = models.CharField(max_length=40)
    slug = models.SlugField(max_length=40, unique=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "setor responsável"
        verbose_name_plural = "setores responsáveis"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.nome)[:40] or "setor"
        super().save(*args, **kwargs)


class MotivoOcorrencia(models.Model):
    nome = models.CharField(max_length=40)
    slug = models.SlugField(max_length=40, unique=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "motivo"
        verbose_name_plural = "motivos"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.nome)[:40] or "motivo"
        super().save(*args, **kwargs)


class NotaFiscal(models.Model):
    numero = models.CharField("número", max_length=20, unique=True)
    cliente = models.CharField(max_length=160)
    peso = models.DecimalField("peso (kg)", max_digits=10, decimal_places=3)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    placa = models.CharField(max_length=8, blank=True)

    class Meta:
        verbose_name = "nota fiscal"
        verbose_name_plural = "notas fiscais"
        ordering = ["numero"]

    def __str__(self):
        return f"{self.numero} · {self.cliente}"


class ItemNota(models.Model):
    nota = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name="itens")
    codigo = models.CharField(max_length=40, blank=True)
    descricao = models.CharField(max_length=180)
    quantidade = models.DecimalField(max_digits=10, decimal_places=3)
    unidade = models.CharField(max_length=12, default="UN")
    peso = models.DecimalField("peso da linha (kg)", max_digits=10, decimal_places=3, default=0)
    valor = models.DecimalField("valor da linha", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "item da nota"
        verbose_name_plural = "itens da nota"
        ordering = ["id"]

    def __str__(self):
        return self.descricao

    def peso_efetivo(self):
        if self.peso:
            return self.peso
        unidade = re.sub(r"[^A-Z]", "", (self.unidade or "").upper())
        if unidade in {"KG", "KGM", "KGS", "KILO", "KILOS", "QUILO", "QUILOS"} or unidade.startswith("KG"):
            return self.quantidade or Decimal("0")
        return Decimal("0")


class Ocorrencia(models.Model):
    class TipoDevolucao(models.TextChoices):
        TOTAL = "total", "Total"
        PARCIAL = "parcial", "Parcial"

    equipe = models.ForeignKey(Equipe, on_delete=models.PROTECT, related_name="ocorrencias")
    criado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="ocorrencias_criadas"
    )
    nota = models.ForeignKey(
        NotaFiscal, null=True, blank=True, on_delete=models.SET_NULL, related_name="ocorrencias"
    )
    numero_nota = models.CharField("nota fiscal", max_length=20)
    cliente = models.CharField(max_length=160)
    peso = models.DecimalField("peso (kg)", max_digits=10, decimal_places=3)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_devolucao = models.CharField(
        "tipo de devolução", max_length=10, choices=TipoDevolucao.choices
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)
    placa = models.CharField(max_length=8, blank=True)
    setor = models.ForeignKey(
        SetorOcorrencia,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="setor responsável",
    )
    motivo = models.ForeignKey(
        MotivoOcorrencia,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="motivo",
    )
    descricao = models.TextField()
    status = models.ForeignKey(
        StatusOcorrencia,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ocorrência"
        verbose_name_plural = "ocorrências"
        ordering = ["-data_hora", "-id"]
        indexes = [
            models.Index(fields=["numero_nota"]),
            models.Index(fields=["-atualizado_em"]),
        ]

    def __str__(self):
        return f"{self.numero_nota} · {self.cliente}"

    def get_status_display(self):
        return self.status.nome if self.status_id else "—"

    def get_setor_display(self):
        return self.setor.nome if self.setor_id else "—"


class ProdutoDevolvido(models.Model):
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="produtos")
    item_nota = models.ForeignKey(
        ItemNota, null=True, blank=True, on_delete=models.SET_NULL, related_name="devolucoes"
    )
    codigo = models.CharField(max_length=40, blank=True)
    descricao = models.CharField(max_length=180)
    quantidade = models.DecimalField(max_digits=10, decimal_places=3)
    unidade = models.CharField(max_length=12, default="UN")

    class Meta:
        verbose_name = "produto devolvido"
        verbose_name_plural = "produtos devolvidos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.descricao} × {self.quantidade} {self.unidade}"


def _caminho_anexo(instance, filename):
    nome = (filename or "arquivo").replace("\\", "/").split("/")[-1]
    return f"anexos/{instance.ocorrencia_id}/{nome}"


class AnexoOcorrencia(models.Model):
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="anexos")
    arquivo = models.FileField(upload_to=_caminho_anexo)
    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=80, blank=True)
    enviado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="anexos_enviados"
    )
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "anexo"
        verbose_name_plural = "anexos"
        ordering = ["id"]

    def __str__(self):
        return self.nome

    def eh_imagem(self):
        tipo = (self.tipo or "").lower()
        nome = (self.nome or "").lower()
        return tipo.startswith("image/") or nome.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))


class ComplementoOcorrencia(models.Model):
    ocorrencia = models.ForeignKey(
        Ocorrencia, on_delete=models.CASCADE, related_name="complementos"
    )
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="complementos")
    texto = models.TextField()
    reabriu = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "complemento"
        verbose_name_plural = "complementos"
        ordering = ["criado_em", "id"]

    def __str__(self):
        return f"Complemento de {self.autor} em {self.ocorrencia_id}"


class Auditoria(models.Model):
    class Acao(models.TextChoices):
        CRIOU = "criou", "Registrou"
        EDITOU = "editou", "Editou"
        STATUS = "status", "Alterou status"
        COMENTOU = "comentou", "Complementou"
        REABRIU = "reabriu", "Reabriu"
        EXCLUIU = "excluiu", "Excluiu"

    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="auditorias")
    equipe = models.ForeignKey(
        Equipe, null=True, on_delete=models.PROTECT, related_name="auditorias"
    )
    ocorrencia = models.ForeignKey(
        Ocorrencia, null=True, blank=True, on_delete=models.SET_NULL, related_name="auditorias"
    )
    referencia = models.PositiveIntegerField("id da ocorrência")
    acao = models.CharField(max_length=12, choices=Acao.choices)
    resumo = models.CharField(max_length=280)
    detalhes = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "auditoria"
        verbose_name_plural = "auditorias"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["equipe", "-criado_em"])]

    def __str__(self):
        return self.resumo
