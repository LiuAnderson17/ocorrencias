from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0004_motivo_anexo_nf_aberta"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="ocorrencia",
            index=models.Index(fields=["-atualizado_em"], name="painel_ocor_atualiz_idx"),
        ),
        migrations.CreateModel(
            name="ComplementoOcorrencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("texto", models.TextField()),
                ("reabriu", models.BooleanField(default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "autor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="complementos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ocorrencia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="complementos",
                        to="painel.ocorrencia",
                    ),
                ),
            ],
            options={
                "verbose_name": "complemento",
                "verbose_name_plural": "complementos",
                "ordering": ["criado_em", "id"],
            },
        ),
    ]
