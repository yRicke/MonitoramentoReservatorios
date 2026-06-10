# Manual Tecnico do Sistema Fisico

## 1. Objetivo
Este documento descreve o modulo fisico do sistema de monitoramento de agua baseado em:
- ESP32;
- sensores analogicos;
- painel local em AP;
- integracao HTTP com o backend Django.

## 2. Escopo do Modulo Fisico
O modulo fisico cobre:
- hardware embarcado;
- firmware da biblioteca `MonitoramentoAgua`;
- conectividade em modo AP;
- painel web local de configuracao;
- envio de leituras e amostras de calibracao;
- cache local dos ultimos intervalos recebidos do servidor.

## 3. Fluxo Fisico Resumido
1. O ESP32 sobe a rede AP local.
2. O operador acessa `http://<ip_atual>/<senha_wifi>`.
3. O painel salva `reservatorio_id`, IP do Django e token.
4. O firmware consulta `GET /api/esp32/config/` a cada 2 segundos.
5. Em modo normal, envia leitura em `/api/esp32/leituras/`.
6. Em modo de calibracao, envia amostras em `/api/esp32/calibracao/amostras/`.

## 4. Componentes de Hardware
- Microcontrolador: ESP32
- Sensor de temperatura: DS18B20
- Sensor TDS: saida analogica
- Sensor de turbidez: saida analogica
- Sensor de pH: saida analogica
- Buzzer ativo continuo: ligado entre `3V3` e `GPIO 25` em modo ativo em nivel baixo

Dependencias:
- `OneWire`
- `DallasTemperature`

## 5. Pinagem Padrao
Definida em `MonitoramentoAguaConfig`:
- `ds18b20Pin`: 4
- `tdsPin`: 34
- `turbidityPin`: 35
- `phPin`: 32
- `buzzerPin`: 25

## 6. Endpoints do Backend
- `GET /api/esp32/config/`
- `POST /api/esp32/leituras/`
- `POST /api/esp32/calibracao/amostras/`

Autenticacao:
- `X-API-Token: <token_do_reservatorio>`

## 7. Estrutura de Leitura Enviada
Payload tipico:
- `reservatorio_id`
- `device_id`
- `temperatura`
- `raw.adc_tds`
- `raw.adc_turb`
- `raw.adc_ph`
- `raw.firmware_ts_ms`
- `raw.firmware_now_ms`

Observacao:
- o fluxo ativo nao usa `ponto_tipo`.

## 8. Cache e Persistencia
Persistido em NVS:
- configuracao estrutural do painel;
- `device_id`;
- ultimo `intervalo_normal_ms` valido;
- ultimo `intervalo_calibracao_ms` valido.

Com Django offline:
- o ESP32 continua usando o ultimo cache valido;
- apos reboot, sobe com os ultimos intervalos persistidos.

## 9. Comissionamento de Campo
1. Gravar o firmware generico.
2. Conectar no AP do ESP32.
3. Abrir o painel local.
4. Informar `reservatorio_id`, `ip_django` e token.
5. Salvar e aguardar reinicio.
6. Confirmar recebimento no painel web do reservatorio.
