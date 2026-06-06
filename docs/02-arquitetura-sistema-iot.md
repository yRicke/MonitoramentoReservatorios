# Arquitetura do Sistema IoT

## 1. Objetivo
Este documento descreve a arquitetura tecnica integrada do produto:
- modulo fisico embarcado (`ESP32 + sensores`);
- modulo de plataforma de monitoramento (`Django + banco + interface web`).

## 2. Visao de Alto Nivel
Arquitetura em camadas:
1. Borda (Edge): aquisicao local e envio HTTP.
2. Ingestao: API Django para leituras, sync e calibracao.
3. Dominio: regras de negocio, calibracao e status.
4. Persistencia: SQLite via Django ORM.
5. Apresentacao: dashboard, detalhe e modulos de calibracao.

Fluxo principal:
`Sensores -> ESP32 -> /api/esp32/leituras/ -> services/ingestao.py -> models.py -> views/templates`

## 3. Pipeline de Ingestao
Sequencia no backend (`processar_leitura_esp32`):
1. parse do JSON e validacao do payload;
2. identificacao de `reservatorio` e `ponto_tipo`;
3. extracao de temperatura e sinais brutos (`raw`);
4. aplicacao de calibracao de temperatura do ponto;
5. resolucao de TDS, turbidez e pH;
6. aplicacao de calibracao de agua;
7. classificacao de status;
8. gravacao em `LeituraQualidade`;
9. atualizacao de status do ponto;
10. sincronizacao do status do reservatorio pelo ponto unico.

## 4. Modelo de Dominio
### `Reservatorio`
- proprietario (`usuario`);
- nome;
- status geral;
- faixas de referencia (TDS, turbidez, temperatura, pH);
- metas auxiliares.

Regra de estado:
- status geral reflete o estado do ponto unico.

### `PontoMonitoramento`
Tipo canonico:
- `ponto_unico`

Compatibilidade de entrada:
- `antes_tratamento`
- `depois_tratamento`
- `pre`
- `pos`

Funcoes:
- manter status atual do ponto;
- armazenar parametros de calibracao por sensor;
- registrar leituras calculadas.

### `LeituraQualidade`
Armazena:
- medicoes finais (`temperatura`, `tds`, `turbidez`, `ph`);
- sinais brutos (`JSONField`);
- status da leitura e origem;
- metadados de modelo e confianca.

### `SessaoCalibracao`
Representa sessao ativa de calibracao:
- sensor alvo;
- janela de validade;
- parametros de coleta;
- dados de fluxo em tempo real.

## 5. Fluxo de Calibracao Assistida
1. Operador inicia sessao na UI.
2. ESP32 consulta `/api/esp32/calibracao/comando/`.
3. Backend responde `modo=calibracao` quando ha sessao ativa.
4. ESP envia amostras dedicadas para `/api/esp32/calibracao/amostras/`.
5. UI calcula estabilidade das ultimas amostras.
6. Confirmacao e habilitada apenas quando a sessao estiver estavel.
7. Backend grava novos parametros de calibracao no ponto unico.

## 6. Observabilidade
No painel web:
- dashboard com medias por periodo do ponto unico;
- detalhe com series historicas por metrica;
- status do ponto unico;
- indicadores de ultima calibracao e vencimento.

Na camada IoT:
- respostas HTTP para diagnostico;
- persistencia de sinais brutos para auditoria tecnica.

## 7. Compatibilidade Legada
- A plataforma web foi simplificada para um unico ponto.
- A API ainda aceita `antes_tratamento` e `depois_tratamento`.
- Isso evita quebra imediata da biblioteca `MonitoramentoAgua`, que permaneceu sem alteracoes nesta fase.
