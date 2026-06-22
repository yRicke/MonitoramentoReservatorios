# Instalacao do ESP32

## Visao geral

O firmware do projeto esta centralizado na biblioteca `MonitoramentoAgua` e no exemplo `MonitoramentoAgua/examples/esp_reservatorio_unico/`.

## Dependencias identificadas

- `OneWire`
- `DallasTemperature`
- bibliotecas base do ecossistema ESP32: `WiFi`, `WebServer`, `HTTPClient` e `Preferences`

## Parametros padrao da biblioteca

O `MonitoramentoAguaConfig` define, por padrao:

- AP `MONITOR-ESP32`
- senha `12345678`
- IP local `192.168.50.1`
- host Django `192.168.50.2`
- porta Django `8000`
- intervalo normal `60000 ms`
- intervalo em calibracao `5000 ms`
- poll de configuracao `2000 ms`
- buzzer `500 ms` ligado / `500 ms` desligado

## Comissionamento sugerido

1. Gravar o exemplo `esp_reservatorio_unico`.
2. Ligar o ESP32 e confirmar a rede AP.
3. Abrir o painel local no navegador.
4. Informar `reservatorio_id` e IP do Django.
5. Salvar e aguardar reinicio do dispositivo.
6. Confirmar o recebimento das leituras no dashboard web.

## Comportamento importante

- A configuracao estrutural fica em NVS.
- O device id e persistido em NVS.
- Leituras nao enviadas entram em fila offline persistida.
