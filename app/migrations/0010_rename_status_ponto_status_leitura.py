from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0009_remove_temperatura_reservatorio_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="leituraqualidade",
            old_name="status_ponto",
            new_name="status_leitura",
        ),
    ]

