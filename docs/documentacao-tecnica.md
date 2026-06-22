# Documentacao Tecnica do Sistema

## 1. Objetivo

Consolidar em um unico ponto o funcionamento do sistema de monitoramento de qualidade da agua, cobrindo backend Django, firmware ESP32 e operacao web.

## 2. Escopo implementado

Hoje o repositorio implementa:

- autenticacao web com Django;
- cadastro, edicao, exclusao e reset de leituras por reservatorio;
- um ponto canonico de monitoramento por reservatorio;
- ingestao HTTP de leituras do ESP32;
- configuracao remota do ESP32 via endpoint unico;
- painel local do ESP32 em modo AP;
- calibracao de temperatura, TDS, turbidez e pH;
- alerta sonoro remoto com silenciamento temporario, permanente e teste;
- relatorio imprimivel/exportavel via navegador.

## 3. Decisoes arquiteturais vigentes

- `1 ESP32 = 1 reservatorio`.
- O fluxo ativo trabalha com `ponto_unico`.
- Alias historicos como `antes_tratamento` e `depois_tratamento` ainda existem apenas para compatibilidade.
- O payload novo nao deve enviar `ponto_tipo`.

## 4. Componentes principais

- Backend: Django 6 com ORM, rotas web e APIs para o ESP32.
- Dados: `Reservatorio`, `PontoMonitoramento`, `LeituraQualidade`, `SessaoCalibracao` e `AmostraCalibracao`.
- Firmware: biblioteca `MonitoramentoAgua` com leitura de sensores, fila offline, painel AP e cache em NVS.
- UI: dashboard, detalhe do reservatorio, tela de edicao, tela de calibracao e relatorio.

## 5. Fluxo resumido

Fluxo operacional principal:

`ESP32 -> GET /api/esp32/config/ -> POST /api/esp32/leituras/ -> processar_leitura_esp32 -> LeituraQualidade -> status do ponto -> status do reservatorio`

Fluxo de calibracao:

`UI -> inicia SessaoCalibracao -> /api/esp32/config/ responde modo=calibracao -> ESP32 envia /api/esp32/calibracao/amostras/ -> UI acompanha estabilidade -> operador salva calibracao`

## 6. Leituras complementares

- [Visao geral](arquitetura/visao-geral.md)
- [Fluxo de dados](arquitetura/fluxo-dados.md)
- [API do ESP32](arquitetura/api-esp32.md)
- [Modelo de dados](arquitetura/modelo-dados.md)
