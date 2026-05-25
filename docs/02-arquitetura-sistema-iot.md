# Arquitetura do Sistema IoT

## 1. Objetivo
Este documento descreve a arquitetura tÃ©cnica integrada do produto:
- módulo físico embarcado (`ESP32 + sensores`).
- módulo de plataforma de monitoramento (`Django + banco + interface web`).

## 2. VisÃ£o de Alto NÃ­vel
Arquitetura em camadas:
1. **Borda (Edge)**: aquisiÃ§Ã£o local e envio HTTP (ESP32).
2. **IngestÃ£o**: API Django para leituras, sync e calibraÃ§Ã£o.
3. **DomÃ­nio**: regras de negÃ³cio, calibraÃ§Ã£o e status.
4. **PersistÃªncia**: SQLite (modelo relacional Django ORM).
5. **ApresentaÃ§Ã£o**: dashboard, detalhe e mÃ³dulos de calibraÃ§Ã£o.

Fluxo principal:
`Sensores -> ESP32 -> /api/esp32/leituras/ -> services/ingestao.py -> models.py -> views/templates`

## 3. Módulo Edge na Arquitetura
Responsabilidades do edge:
- ler sensores fÃ­sicos;
- filtrar ruÃ­do localmente;
- manter fila offline em NVS;
- sincronizar janela de leitura com servidor;
- operar modo de calibraÃ§Ã£o sob comando remoto.

CaracterÃ­sticas relevantes:
- biblioteca `MonitoramentoAgua` (C++);
- modos de rede AP e STA;
- envio por token via cabeÃ§alho `X-API-Token`.

## 4. Módulo Plataforma na Arquitetura
Responsabilidades da plataforma:
- autenticar requisiÃ§Ãµes IoT por token;
- validar payload e normalizar sinais;
- converter ADC/tensÃ£o para grandezas;
- aplicar calibraÃ§Ãµes do ponto;
- classificar status por regras;
- persistir histÃ³rico e fornecer visualizaÃ§Ã£o.

Stack principal:
- Python + Django 6;
- banco SQLite;
- templates Django + JS (ApexCharts no detalhe).

## 5. Endpoints de IntegraÃ§Ã£o IoT
Endpoints disponÃ­veis:
- `POST /api/esp32/leituras/`
- `GET /api/esp32/sync/`
- `GET /api/esp32/calibracao/comando/`
- `POST /api/esp32/calibracao/amostras/`

Todos validam `X-API-Token`. Falha de token retorna `401`.

## 6. Pipeline de IngestÃ£o de Leitura
SequÃªncia no backend (`processar_leitura_esp32`):
1. parse do JSON e validaÃ§Ã£o do payload;
2. identificaÃ§Ã£o de `reservatorio` e `ponto_tipo`;
3. extraÃ§Ã£o de temperatura e sinais brutos (`raw`);
4. aplicaÃ§Ã£o de calibraÃ§Ã£o de temperatura do ponto;
5. resoluÃ§Ã£o de TDS/turbidez/pH (raw > fallback por valor direto);
6. aplicaÃ§Ã£o de calibraÃ§Ã£o de Ã¡gua (offset/inclinaÃ§Ã£o);
7. classificaÃ§Ã£o de status (`bom/atencao/perigo`);
8. gravaÃ§Ã£o em `LeituraQualidade`;
9. atualizaÃ§Ã£o de status do ponto;
10. sincronizaÃ§Ã£o do status do reservatÃ³rio pelo ponto `depois_tratamento`.

## 7. Regras de ClassificaÃ§Ã£o de Status
A classificaÃ§Ã£o Ã© baseada em faixas por reservatÃ³rio e margens:
- **TDS**: fator de perigo `1.5` sobre faixa mÃ¡xima.
- **Turbidez**: fator de perigo `5/3` sobre faixa mÃ¡xima.
- **Temperatura**:
  - atenÃ§Ã£o: desvio de `5.0` Â°C fora da faixa.
  - perigo: desvio de `8.0` Â°C fora da faixa.
- **pH**:
  - atenÃ§Ã£o: desvio de `0.5`.
  - perigo: desvio de `1.0`.

ComposiÃ§Ã£o final:
- se qualquer mÃ©trica em `perigo` -> status `perigo`;
- senÃ£o, se qualquer mÃ©trica em `atencao` -> status `atencao`;
- caso contrÃ¡rio -> `bom`.

## 8. Modelo de Dados (DomÃ­nio)
### 8.1 `Reservatorio`
Campos centrais:
- proprietÃ¡rio (`usuario`);
- nome;
- status geral;
- faixas de referÃªncia (TDS, turbidez, temperatura, pH);
- metas auxiliares.

Regra de estado:
- status geral reflete o estado do ponto `depois_tratamento`.

### 8.2 `PontoMonitoramento`
Tipos:
- `antes_tratamento`
- `depois_tratamento`

FunÃ§Ãµes:
- manter status atual do ponto;
- armazenar parÃ¢metros de calibraÃ§Ã£o por sensor;
- registrar leituras calculadas.

### 8.3 `LeituraQualidade`
Armazena:
- mediÃ§Ãµes finais (`temperatura`, `tds`, `turbidez`, `ph`);
- sinais brutos (`JSONField`);
- status da leitura e origem;
- metadados de modelo/confianÃ§a (estrutura pronta para TinyML).

### 8.4 `SessaoCalibracao`
Representa sessÃ£o ativa de calibraÃ§Ã£o:
- sensor alvo;
- janela de validade;
- parÃ¢metros de coleta;
- dados de fluxo em tempo real.

### 8.5 `AmostraCalibracao`
Armazena amostras coletadas durante sessÃ£o:
- ADC por sensor;
- temperatura;
- timestamp firmware;
- sinais brutos.

## 9. Fluxo de SincronizaÃ§Ã£o Temporal
Endpoint `GET /api/esp32/sync/` retorna:
- `intervalo_ms` (atual: 60.000 ms);
- epoch atual do servidor;
- epoch da prÃ³xima janela;
- `aguardar_ms`.

Uso:
- sincronizar momento de coleta dos dispositivos;
- reduzir desalinhamento entre leituras prÃ©/pÃ³s tratamento.

## 10. Fluxo de CalibraÃ§Ã£o Assistida
1. Operador inicia sessÃ£o na UI.
2. ESP32 consulta `/api/esp32/calibracao/comando/`.
3. Backend responde `modo=calibracao` quando hÃ¡ sessÃ£o ativa.
4. ESP envia amostras dedicadas para `/api/esp32/calibracao/amostras/`.
5. UI calcula estabilidade (Ãºltimas 30 amostras).
6. BotÃµes de confirmaÃ§Ã£o habilitam somente quando estÃ¡vel.
7. Backend grava novos parÃ¢metros de calibraÃ§Ã£o no `PontoMonitoramento`.

## 11. Estabilidade e Qualidade de CalibraÃ§Ã£o
Limites atuais:
- desvio mÃ¡x temperatura: `0.2`
- desvio mÃ¡x TDS ADC: `20.0`
- desvio mÃ¡x turbidez ADC: `20.0`
- desvio mÃ¡x pH ADC: `12.0`
- amostragem para status de sessÃ£o: Ãºltimas `30` amostras

TTL da sessÃ£o:
- `10` minutos (`TTL_SESSAO_CALIBRACAO_SEGUNDOS`).

## 12. SeguranÃ§a
Controles implementados:
- autenticaÃ§Ã£o de API IoT por token.
- separaÃ§Ã£o entre rotas autenticadas web e rotas IoT.
- validaÃ§Ã£o forte de payload e normalizaÃ§Ã£o numÃ©rica.

Pontos de atenÃ§Ã£o para produÃ§Ã£o:
- remover tokens default e usar variÃ¡veis de ambiente seguras;
- ativar HTTPS e segmentaÃ§Ã£o de rede;
- endurecer `ALLOWED_HOSTS`, `DEBUG` e controles de acesso fÃ­sico.

## 13. Observabilidade Funcional
No painel web:
- dashboard com mÃ©dias prÃ©/pÃ³s por perÃ­odo;
- detalhe com sÃ©ries histÃ³ricas por mÃ©trica;
- status por ponto antes/depois;
- indicadores de Ãºltima calibraÃ§Ã£o e vencimento.

Na camada IoT:
- respostas HTTP e mensagens seriais para diagnÃ³stico;
- persistÃªncia de sinais brutos para auditoria tÃ©cnica.

## 14. Escalabilidade e EvoluÃ§Ã£o
A arquitetura atual permite evoluÃ§Ã£o incremental:
- substituir SQLite por banco gerenciado;
- separar app/API em serviÃ§os independentes;
- adicionar mensageria para ingestÃ£o em lote;
- reintroduzir TinyML usando `status_origem=TinyML` sem perder trilha de sinais brutos;
- incluir gestÃ£o de mÃºltiplos sites com telemetria agregada.

## 15. LimitaÃ§Ãµes Atuais
LimitaÃ§Ãµes observadas:
- acoplamento da ingestÃ£o ao processo web Django;
- autenticaÃ§Ã£o IoT por token estÃ¡tico;
- ausÃªncia de fila externa no backend;
- armazenamento local padrÃ£o (SQLite).

## 16. Resumo Arquitetural
O sistema foi desenhado para operar com alta robustez prÃ¡tica em ambiente de campo:
- resiliÃªncia no edge com fila offline;
- regras de negÃ³cio explÃ­citas e auditÃ¡veis;
- calibraÃ§Ã£o guiada com critÃ©rios de estabilidade;
- visÃ£o operacional completa no painel web.




