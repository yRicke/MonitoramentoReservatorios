# Arquitetura do Sistema IoT

## 1. Objetivo
Descrever a arquitetura integrada entre:
- modulo fisico embarcado;
- backend Django;
- interface web de operacao.

## 2. Visao de Alto Nivel
Camadas principais:
1. Edge: coleta local, painel AP e envio HTTP.
2. Ingestao: endpoints do Django para configuracao, leituras e calibracao.
3. Dominio: regras de negocio, calibracao e status.
4. Persistencia: banco via Django ORM.
5. Apresentacao: dashboard, detalhe, edicao e calibracao.

Fluxo principal:
`Sensores -> ESP32 -> /api/esp32/config/ -> /api/esp32/leituras/ -> services/ingestao.py -> models.py -> views/templates`

## 3. Pipeline de Ingestao
Sequencia no backend:
1. validacao do token do reservatorio;
2. parse do JSON;
3. localizacao do reservatorio;
4. uso do ponto canonico unico;
5. aplicacao de calibracoes;
6. classificacao de status;
7. gravacao em `LeituraQualidade`;
8. atualizacao do status do ponto;
9. sincronizacao do status do reservatorio.

## 4. Modelo de Dominio
### `Reservatorio`
- nome;
- status geral;
- faixas de referencia;
- token de integracao do ESP32;
- intervalo normal do ESP32;
- intervalo de calibracao do ESP32;
- estado de silenciamento do alerta sonoro.

### `PontoMonitoramento`
- tipo canonico: `ponto_unico`;
- parametros de calibracao por sensor;
- status atual.

### `LeituraQualidade`
- medicoes finais;
- sinais brutos;
- status da leitura;
- metadados tecnicos.

### `SessaoCalibracao`
- sensor alvo;
- validade;
- parametros de amostragem;
- dados de acompanhamento em tempo real.

## 5. Fluxo de Configuracao do ESP32
1. O Django gera o token do reservatorio.
2. O operador abre a tela de edicao do reservatorio.
3. O operador copia token e `reservatorio_id`.
4. O operador acessa o painel AP local do ESP32.
5. O ESP32 salva configuracao estrutural em NVS.
6. O dispositivo passa a consultar o endpoint unico de configuracao.
7. O mesmo endpoint informa quando o alerta sonoro deve ficar ativo.

## 6. Fluxo de Calibracao
1. Operador inicia a sessao na UI.
2. O Django passa a responder `modo=calibracao` em `/api/esp32/config/`.
3. O ESP32 troca o ciclo normal por amostras dedicadas.
4. A UI acompanha estabilidade das ultimas amostras.
5. O backend grava os novos parametros no ponto unico.

## 7. Regras de Contrato
- `1 ESP = 1 reservatorio`
- sem `ponto_tipo` no fluxo ativo
- sem token global em `.env`
- `poll` de configuracao fixo em 2 segundos
- intervalos operacionais definidos pelo reservatorio no Django
- alerta sonoro ativo somente quando o status do reservatorio estiver em `perigo` e nao houver silenciamento manual
