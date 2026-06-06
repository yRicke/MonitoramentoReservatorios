# Manual Tecnico do Sistema Fisico

## 1. Objetivo
Este documento descreve o modulo fisico do sistema de monitoramento de agua, baseado em ESP32, sensores analogicos e integracao com a plataforma web.

Objetivos principais:
- coletar medicoes de qualidade da agua em campo;
- manter coleta continua mesmo com instabilidade de rede;
- enviar leituras estruturadas para o backend Django;
- suportar rotinas de calibracao assistida em operacao.

## 2. Escopo do Modulo Fisico
O produto fisico cobre:
- hardware embarcado (ESP32 + sensores);
- firmware da biblioteca `MonitoramentoAgua`;
- conectividade Wi-Fi em modo AP ou STA;
- envio de leitura para endpoints HTTP do backend;
- fila offline persistente em NVS.

Nao cobre:
- decisao final de status de qualidade (executada no backend);
- gestao de usuarios e dashboards da plataforma.

## 3. Fluxo Fisico Resumido
1. Sensores coletam grandezas fisicas e eletricas.
2. ESP32 realiza amostragem e filtragem local.
3. Leitura e enfileirada localmente.
4. Quando a rede esta disponivel, o firmware envia para a API Django.
5. Backend processa, classifica e persiste no ponto unico do reservatorio.

## 4. Componentes de Hardware
- Microcontrolador: ESP32
- Sensor de temperatura: DS18B20
- Sensor TDS: saida analogica
- Sensor de turbidez: saida analogica
- Sensor de pH: saida analogica

Dependencias de firmware:
- `OneWire`
- `DallasTemperature`

## 5. Pinagem Padrao do Firmware
Definida em `MonitoramentoAguaConfig`:
- `ds18b20Pin`: 4
- `tdsPin`: 34
- `turbidityPin`: 35
- `phPin`: 32

## 6. Canais de Comunicacao com Backend
URLs usadas pelo firmware:
- `/api/esp32/leituras/`
- `/api/esp32/sync/`
- `/api/esp32/calibracao/comando/`
- `/api/esp32/calibracao/amostras/`

Cabecalho de autenticacao:
- `X-API-Token: <token>`

## 7. Estrutura de Leitura Enviada
Payload tipico:
- `reservatorio_id`
- `ponto_tipo`
- `device_id`
- `temperatura`
- `raw.adc_tds`
- `raw.adc_turb`
- `raw.adc_ph`
- `raw.firmware_ts_ms`
- `raw.firmware_now_ms`

Contrato atual do backend:
- o sistema opera com `ponto_unico`;
- por compatibilidade, a API ainda aceita `antes_tratamento` e `depois_tratamento`.

## 8. Resiliencia Offline
Mecanismo implementado:
- fila circular local;
- persistencia em NVS;
- reenvio automatico quando a rede volta;
- descarte da leitura mais antiga se a fila lotar.

## 9. Sincronizacao Temporal
O firmware consulta `/api/esp32/sync/` para:
- obter o intervalo oficial de leitura;
- alinhar a proxima coleta com o servidor;
- reduzir desalinhamento entre dispositivos.

## 10. Modo de Calibracao no Dispositivo
Durante calibracao:
1. firmware consulta o endpoint de comando;
2. backend informa modo e sensor ativo;
3. dispositivo envia amostras dedicadas;
4. ao encerrar a sessao, retorna ao ciclo normal.

## 11. Instalacao Fisica Recomendada
1. Definir o ponto fisico monitorado para cada reservatorio.
2. Instalar sensores com protecao mecanica e acesso para manutencao.
3. Garantir isolamento de respingos na eletronica.
4. Validar alimentacao estavel e aterramento.
5. Validar intensidade de sinal Wi-Fi no local.

## 12. Comissionamento de Campo
1. Gravar firmware com `reservatorio_id`, `ponto_tipo` e `device_id` corretos.
2. Configurar `djangoHost` e `apiToken` validos.
3. Verificar conexao Wi-Fi.
4. Confirmar retorno `201` em `/api/esp32/leituras/`.
5. Conferir leitura no painel web do reservatorio correto.
6. Executar calibracao inicial dos sensores.

## 13. Observacao Importante desta Fase
- O backend e a interface web ja usam ponto unico.
- A biblioteca Arduino nao foi refatorada nesta etapa.
- Por isso, aliases legados de `ponto_tipo` continuam aceitos pela API.
