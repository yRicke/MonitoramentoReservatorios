# Protocolo de Operacao

## Protocolo sintetico de campo

1. Configurar o reservatorio no Django.
2. Registrar `reservatorio_id` no ESP32.
3. Confirmar recebimento inicial de leituras.
4. Calibrar sensores quando necessario.
5. Coletar historico e relatorios pelo dashboard.
6. Comparar os periodos de interesse com base nas leituras registradas.

## Uso academico sugerido

Para estudos comparativos, o protocolo pode separar momentos de coleta:

- antes da intervencao;
- durante a observacao;
- depois da intervencao.

Essa comparacao e metodologica. No software atual, os registros continuam centralizados no `ponto_unico`.
