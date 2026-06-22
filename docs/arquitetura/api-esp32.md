# API do ESP32

## Identificacao

Todos os endpoints do ESP32 usam:

- `reservatorio_id` valido

O backend identifica o reservatorio diretamente pelo `reservatorio_id` enviado no payload ou na query string.

## `GET /api/esp32/config/`

Consulta a configuracao remota do reservatorio.

### Requisicao

- metodo: `GET`
- query obrigatoria: `reservatorio_id`

### Resposta base

```json
{
  "server_epoch_ms": 1760000000000,
  "poll_configuracao_ms": 2000,
  "intervalo_normal_ms": 60000,
  "intervalo_calibracao_ms": 5000,
  "alerta_sonoro_ativo": false,
  "alerta_sonoro_intervalo_ligado_ms": 500,
  "alerta_sonoro_intervalo_desligado_ms": 500,
  "modo": "normal"
}
```

### Resposta em calibracao

```json
{
  "server_epoch_ms": 1760000000000,
  "poll_configuracao_ms": 2000,
  "intervalo_normal_ms": 60000,
  "intervalo_calibracao_ms": 5000,
  "alerta_sonoro_ativo": true,
  "alerta_sonoro_intervalo_ligado_ms": 500,
  "alerta_sonoro_intervalo_desligado_ms": 500,
  "modo": "calibracao",
  "sessao_id": 12,
  "sensor": "tds",
  "qtd_amostras": 80,
  "atraso_amostra_ms": 50,
  "expira_em": "2026-06-20T12:00:00-03:00"
}
```

## `POST /api/esp32/leituras/`

Recebe leituras operacionais do firmware.

### Payload esperado

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

### Regras do contrato

- `ponto_tipo` nao e aceito.
- `raw` pode ser enviado como `raw` ou `sinais_brutos`, mas o fluxo canonico usa `raw`.
- `temperatura` e obrigatoria.
- o backend aceita `ph` final se nao houver `adc_ph`, mas o firmware atual envia ADC.

### Respostas

- `201 {"ok": true}`
- `400 {"erro": "..."}`
- `401 {"erro": "nao autorizado"}`

## `POST /api/esp32/calibracao/amostras/`

Recebe amostras dedicadas de uma sessao de calibracao ativa.

### Payload esperado

```json
{
  "reservatorio_id": 1,
  "device_id": "esp32-ABCD12345678",
  "sensor": "ph",
  "temperatura": 24.91,
  "raw": {
    "adc_ph": 2084,
    "firmware_ts_ms": 223456789,
    "firmware_now_ms": 223456999,
    "device_id": "esp32-ABCD12345678"
  }
}
```

### Regras do contrato

- exige sessao ativa para o sensor informado;
- `sensor` deve ser um de `temperatura`, `tds`, `turbidez` ou `ph`;
- `ponto_tipo` nao e aceito;
- `raw` deve ser objeto JSON.

### Respostas

- `201 {"ok": true, "amostra_id": 123}`
- `400 {"erro": "..."}`
- `401 {"erro": "nao autorizado"}`
- `409 {"erro": "sessao de calibracao inativa"}`
