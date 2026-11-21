from django.db import migrations, models
import django.db.models.deletion


def criar_status_e_migrar(apps, schema_editor):
    StatusOcorrencia = apps.get_model("painel", "StatusOcorrencia")
    Ocorrencia = apps.get_model("painel", "Ocorrencia")
    mapa = {}
    for slug, nome, cor, ordem, padrao in [
        ("pendente", "Pendente", "cobre", 1, True),
        ("em_andamento", "Em andamento", "azul", 2, False),
        ("feito", "Feito", "oliva", 3, False),
    ]:
        mapa[slug] = StatusOcorrencia.objects.create(
            nome=nome, slug=slug, cor=cor, ordem=ordem, ativo=True, padrao=padrao
        )
    for ocorrencia in Ocorrencia.objects.all():
        ocorrencia.status_novo = mapa.get(ocorrencia.status, mapa["pendente"])
        ocorrencia.save(update_fields=["status_novo"])


def reverter(apps, schema_editor):
    Ocorrencia = apps.get_model("painel", "Ocorrencia")
    for ocorrencia in Ocorrencia.objects.select_related("status_novo"):
        ocorrencia.status = ocorrencia.status_novo.slug if ocorrencia.status_novo_id else "pendente"
        ocorrencia.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StatusOcorrencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=40)),
                ("slug", models.SlugField(max_length=40, unique=True)),
                (
                    "cor",
                    models.CharField(
                        choices=[
                            ("cobre", "Cobre"),
                            ("oliva", "Verde"),
                            ("azul", "Azul"),
                            ("vermelho", "Vermelho"),
                            ("cinza", "Cinza"),
                        ],
                        default="cinza",
                        max_length=12,
                    ),
                ),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                ("ativo", models.BooleanField(default=True)),
                (
                    "padrao",
                    models.BooleanField(
                        default=False,
                        help_text="Usado automaticamente ao lançar uma ocorrência.",
                        verbose_name="status inicial",
                    ),
                ),
            ],
            options={
                "verbose_name": "status",
                "verbose_name_plural": "status",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="status_novo",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.statusocorrencia",
            ),
        ),
        migrations.RunPython(criar_status_e_migrar, reverter),
        migrations.RemoveIndex(
            model_name="ocorrencia",
            name="painel_ocor_status_3ebaab_idx",
        ),
        migrations.RemoveField(
            model_name="ocorrencia",
            name="status",
        ),
        migrations.RenameField(
            model_name="ocorrencia",
            old_name="status_novo",
            new_name="status",
        ),
        migrations.AlterField(
            model_name="ocorrencia",
            name="status",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.statusocorrencia",
            ),
        ),
    ]
