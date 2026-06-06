from django.db import migrations, models


TIPO_UNICO = "ponto_unico"
TIPO_ANTES = "antes_tratamento"
TIPO_DEPOIS = "depois_tratamento"


def consolidar_pontos_monitoramento(apps, schema_editor):
    PontoMonitoramento = apps.get_model("app", "PontoMonitoramento")
    LeituraQualidade = apps.get_model("app", "LeituraQualidade")
    SessaoCalibracao = apps.get_model("app", "SessaoCalibracao")

    reservatorio_ids = (
        PontoMonitoramento.objects.order_by()
        .values_list("reservatorio_id", flat=True)
        .distinct()
    )

    for reservatorio_id in reservatorio_ids:
        pontos = list(
            PontoMonitoramento.objects.filter(reservatorio_id=reservatorio_id).order_by("id")
        )
        if not pontos:
            continue

        ponto_unico = next((p for p in pontos if p.tipo == TIPO_UNICO), None)
        ponto_antes = next((p for p in pontos if p.tipo == TIPO_ANTES), None)
        ponto_depois = next((p for p in pontos if p.tipo == TIPO_DEPOIS), None)

        canonico = ponto_unico or ponto_antes or ponto_depois or pontos[0]
        extras = [ponto for ponto in pontos if ponto.id != canonico.id]

        if canonico.tipo != TIPO_UNICO:
            canonico.tipo = TIPO_UNICO
            canonico.save(update_fields=["tipo"])

        for ponto in extras:
            LeituraQualidade.objects.filter(ponto_id=ponto.id).update(ponto_id=canonico.id)
            SessaoCalibracao.objects.filter(ponto_id=ponto.id).update(ponto_id=canonico.id)
            ponto.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0022_alter_leituraqualidade_status_leitura_and_more"),
    ]

    operations = [
        migrations.RunPython(consolidar_pontos_monitoramento, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pontomonitoramento",
            name="tipo",
            field=models.CharField(
                choices=[("ponto_unico", "Ponto unico")],
                max_length=32,
            ),
        ),
    ]
