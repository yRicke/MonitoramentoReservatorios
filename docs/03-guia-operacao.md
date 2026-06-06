# Guia de Operacao do Sistema

## 1. Objetivo
Este guia descreve como operar o ambiente completo de monitoramento:
- modulo fisico embarcado (ESP32 + sensores);
- modulo de plataforma web/backend (Django).

## 2. Pre-requisitos Operacionais
Backend:
- Python compativel com o projeto;
- banco local inicializado;
- timezone `America/Sao_Paulo`.

Edge:
- firmware compilado com `reservatorio_id`, `ponto_tipo` e `device_id` corretos;
- endpoint do backend acessivel na rede;
- token igual ao configurado no servidor.

## 3. Fluxo Basico na UI
1. Acessar `/entrar/`.
2. Ir para dashboard (`/`) e verificar os cards dos reservatorios.
3. Selecionar o periodo de analise.
4. Abrir o detalhe do reservatorio para investigar historico e calibracao.

## 4. Rotina Diaria
1. Verificar se ha reservatorios sem dados recentes.
2. Conferir status geral (`bom`, `atencao`, `perigo`) por card.
3. Abrir detalhes de casos em alerta.
4. Acompanhar a tendencia historica do ponto unico.
5. Registrar acoes tomadas (operacao, limpeza, recalibracao).

## 5. Interpretacao de Status
Convencao:
- `bom`: valores dentro da faixa esperada;
- `atencao`: desvio moderado de uma ou mais metricas;
- `perigo`: desvio critico de uma ou mais metricas.

Regra do reservatorio:
- status geral reflete exclusivamente o ponto unico.

## 6. Dashboard e Detalhe
### Dashboard
- visao consolidada de todos os reservatorios;
- medias do ponto unico por periodo;
- filtro por nome ou status.

### Detalhe do Reservatorio
- status do ponto unico;
- ultimas medicoes por metrica;
- graficos historicos de temperatura, TDS, turbidez e pH;
- edicao das faixas de referencia.

## 7. Operacao de Calibracao
Fluxo resumido:
1. abrir `Calibrar` no detalhe;
2. entrar no ponto unico;
3. selecionar sensor;
4. iniciar sessao;
5. aguardar estabilidade;
6. confirmar calibracao;
7. encerrar sessao quando concluido.

## 8. Incidentes Comuns
### Sem dados no dashboard
1. confirmar backend online;
2. validar rota `/api/esp32/leituras/`;
3. validar token;
4. verificar conectividade Wi-Fi do ESP32.

### Oscilacao alta
1. inspecionar sensores;
2. verificar estabilidade eletrica;
3. conferir necessidade de recalibracao;
4. revisar parametros de amostragem do firmware.

### Erro 400 na API
1. validar payload JSON;
2. conferir `reservatorio_id` e `ponto_tipo`;
3. conferir presenca de campos obrigatorios;
4. validar formato do bloco `raw`.

## 9. Observacao Importante desta Fase
- A operacao funcional do sistema foi consolidada em ponto unico.
- A API continua aceitando aliases legados de `ponto_tipo`.
- A biblioteca Arduino permanece inalterada nesta etapa.
