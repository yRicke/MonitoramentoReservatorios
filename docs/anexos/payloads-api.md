# Payloads de API

## Leitura operacional

```json
{
  "reservatorio_id": 1,
  "device_id": "esp32-ABCD12345678",
  "temperatura": 25.34,
  "raw": {
    "adc_tds": 812,
    "adc_turb": 1460,
    "adc_ph": 2048,
    "firmware_ts_ms": 123456789,
    "firmware_now_ms": 123456999,
    "device_id": "esp32-ABCD12345678"
  }
}
```

## Resposta de configuracao

```json
{
  "server_epoch_ms": 1760000000000,
  "poll_configuracao_ms": 2000,
  "intervalo_normal_ms": 60000,
  "intervalo_calibracao_ms": 5000,
  "normal_qtd_amostras_tds": 60,
  "normal_atraso_amostra_tds_ms": 5,
  "normal_qtd_amostras_turbidez": 60,
  "normal_atraso_amostra_turbidez_ms": 10,
  "normal_qtd_amostras_ph": 60,
  "normal_atraso_amostra_ph_ms": 5,
  "alerta_sonoro_ativo": false,
  "alerta_sonoro_intervalo_ligado_ms": 500,
  "alerta_sonoro_intervalo_desligado_ms": 500,
  "modo": "normal"
}
```

## Amostra de calibracao

```json
{
  "reservatorio_id": 1,
  "device_id": "esp32-ABCD12345678",
  "sensor": "tds",
  "temperatura": 24.95,
  "raw": {
    "adc_tds": 801,
    "firmware_ts_ms": 223456789,
    "firmware_now_ms": 223456999,
    "device_id": "esp32-ABCD12345678"
  }
}
```

## Erros comuns

```json
{"erro": "nao autorizado"}
```

```json
{"erro": "campo nao suportado: ponto_tipo"}
```

```json
{"erro": "sessao de calibracao inativa"}
```
