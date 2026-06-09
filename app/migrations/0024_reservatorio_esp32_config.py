import secrets

import app.models
from django.db import migrations, models


def _gerar_token():
    return secrets.token_urlsafe(32)


def _preencher_tokens_esp32(apps, schema_editor):
    Reservatorio = apps.get_model("app", "Reservatorio")

    for reservatorio in Reservatorio.objects.filter(esp32_token_integracao__isnull=True):
        reservatorio.esp32_token_integracao = _gerar_token()
        reservatorio.save(update_fields=["esp32_token_integracao"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0023_pontomonitoramento_ponto_unico"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservatorio",
            name="esp32_intervalo_envio_calibracao_s",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="reservatorio",
            name="esp32_intervalo_envio_normal_s",
            field=models.PositiveIntegerField(default=60),
        ),
        migrations.AddField(
            model_name="reservatorio",
            name="esp32_token_integracao",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.RunPython(_preencher_tokens_esp32, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="reservatorio",
            name="esp32_token_integracao",
            field=models.CharField(
                default=app.models.gerar_token_integracao_esp32,
                max_length=128,
                unique=True,
            ),
        ),
    ]
