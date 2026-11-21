from django.db import migrations, models
import django.db.models.deletion


SETORES = [
    ("separacao", "Separação", 1),
    ("expedicao", "Expedição", 2),
    ("transporte", "Transporte", 3),
    ("conferencia", "Conferência", 4),
    ("recebimento", "Recebimento", 5),
    ("outro", "Outro", 6),
]


def popular(apps, schema_editor):
    SetorOcorrencia = apps.get_model("painel", "SetorOcorrencia")
    Ocorrencia = apps.get_model("painel", "Ocorrencia")
    mapa = {}
    for slug, nome, ordem in SETORES:
        mapa[slug] = SetorOcorrencia.objects.create(
            nome=nome, slug=slug, ordem=ordem, ativo=True
        )
    padrao = mapa["outro"]
    for ocorrencia in Ocorrencia.objects.all():
        ocorrencia.setor = mapa.get(ocorrencia.setor_codigo, padrao)
        ocorrencia.save(update_fields=["setor"])


def reverter(apps, schema_editor):
    SetorOcorrencia = apps.get_model("painel", "SetorOcorrencia")
    SetorOcorrencia.objects.filter(slug__in=[slug for slug, _nome, _ordem in SETORES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0005_complemento_reabertura"),
    ]

    operations = [
        migrations.CreateModel(
            name="SetorOcorrencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=40)),
                ("slug", models.SlugField(max_length=40, unique=True)),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "setor responsável",
                "verbose_name_plural": "setores responsáveis",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.RenameField(
            model_name="ocorrencia",
            old_name="setor",
            new_name="setor_codigo",
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="setor",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.setorocorrencia",
                verbose_name="setor responsável",
            ),
        ),
        migrations.RunPython(popular, reverter),
        migrations.AlterField(
            model_name="ocorrencia",
            name="setor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias",
                to="painel.setorocorrencia",
                verbose_name="setor responsável",
            ),
        ),
        migrations.RemoveField(
            model_name="ocorrencia",
            name="setor_codigo",
        ),
    ]
