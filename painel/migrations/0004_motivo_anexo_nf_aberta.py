from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import painel.models


def popular(apps, schema_editor):
    StatusOcorrencia = apps.get_model("painel", "StatusOcorrencia")
    MotivoOcorrencia = apps.get_model("painel", "MotivoOcorrencia")
    Ocorrencia = apps.get_model("painel", "Ocorrencia")
    StatusOcorrencia.objects.filter(slug="feito").update(encerra=True)
    mapa = {}
    for slug, nome, ordem in [
        ("avaria", "Avaria", 1),
        ("falta", "Falta", 2),
        ("recusa", "Recusa", 3),
        ("prazo", "Prazo / janela", 4),
        ("temperatura", "Temperatura", 5),
        ("outro", "Outro", 6),
    ]:
        mapa[slug] = MotivoOcorrencia.objects.create(
            nome=nome, slug=slug, ordem=ordem, ativo=True
        )
    Ocorrencia.objects.filter(motivo_id__isnull=True).update(motivo=mapa["outro"])


def reverter(apps, schema_editor):
    MotivoOcorrencia = apps.get_model("painel", "MotivoOcorrencia")
    MotivoOcorrencia.objects.filter(
        slug__in=["avaria", "falta", "recusa", "prazo", "temperatura", "outro"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0003_status_cor_livre"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="statusocorrencia",
            name="encerra",
            field=models.BooleanField(
                default=False,
                help_text="Com este status, a nota deixa de contar como ocorrência em aberto.",
                verbose_name="encerra a ocorrência",
            ),
        ),
        migrations.CreateModel(
            name="MotivoOcorrencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=40)),
                ("slug", models.SlugField(max_length=40, unique=True)),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "motivo",
                "verbose_name_plural": "motivos",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="motivo",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.motivoocorrencia",
                verbose_name="motivo",
            ),
        ),
        migrations.CreateModel(
            name="AnexoOcorrencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("arquivo", models.FileField(upload_to=painel.models._caminho_anexo)),
                ("nome", models.CharField(max_length=180)),
                ("tipo", models.CharField(blank=True, max_length=80)),
                ("enviado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "enviado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="anexos_enviados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ocorrencia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anexos",
                        to="painel.ocorrencia",
                    ),
                ),
            ],
            options={
                "verbose_name": "anexo",
                "verbose_name_plural": "anexos",
                "ordering": ["id"],
            },
        ),
        migrations.RunPython(popular, reverter),
        migrations.AlterField(
            model_name="ocorrencia",
            name="motivo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.motivoocorrencia",
                verbose_name="motivo",
            ),
        ),
    ]
