# Pinagem do ESP32

## Pinagem padrao

Definida em `MonitoramentoAguaConfig`:

- `ds18b20Pin`: `4`
- `tdsPin`: `34`
- `turbidityPin`: `35`
- `phPin`: `32`
- `buzzerPin`: `25`

## Sensores esperados

- temperatura: DS18B20
- TDS: entrada analogica
- turbidez: entrada analogica
- pH: entrada analogica

## Alerta sonoro

O buzzer ativo continuo foi documentado no projeto como ligado entre `3V3` e `GPIO 25`, com acionamento em nivel baixo.

No firmware:

- o pino do buzzer usa `OUTPUT_OPEN_DRAIN`;
- `LOW` liga o buzzer;
- `HIGH` desliga o buzzer.

## Observacao

O diagrama eletrico final e a confirmacao do hardware de campo continuam como pendencias documentais para uma versao produtiva.
