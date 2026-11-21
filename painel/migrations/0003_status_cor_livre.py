from django.db import migrations, models

CORES = {
    "cobre": "#F8E7CF",
    "oliva": "#E3F3EA",
    "azul": "#E3EEF9",
    "vermelho": "#F8E0DC",
    "cinza": "#E8E0D4",
}


def converter_cores(apps, schema_editor):
    StatusOcorrencia = apps.get_model("painel", "StatusOcorrencia")
    for status in StatusOcorrencia.objects.all():
        if str(status.cor).startswith("#"):
            continue
        status.cor = CORES.get(status.cor, "#E8E0D4")
        status.save(update_fields=["cor"])


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0002_status_ocorrencia"),
    ]

    operations = [
        migrations.RunPython(converter_cores, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="statusocorrencia",
            name="cor",
            field=models.CharField(
                default="#E8E0D4",
                help_text="Clique no campo para escolher qualquer cor.",
                max_length=7,
                verbose_name="cor",
            ),
        ),
    ]
