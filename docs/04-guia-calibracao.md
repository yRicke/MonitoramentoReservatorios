# Guia de Calibracao do Sistema Integrado

## 1. Objetivo
Padronizar a calibracao de:
- temperatura;
- TDS;
- turbidez;
- pH em 2 pontos.

## 2. Conceito de Sessao
1. O operador inicia a sessao na interface.
2. O Django publica `modo=calibracao` no endpoint de configuracao.
3. O ESP32 passa a enviar amostras dedicadas.
4. A UI acompanha estabilidade em tempo real.
5. O backend salva a calibracao no ponto unico.

## 3. Pre-requisitos
1. reservatorio configurado no sistema;
2. token correto salvo no painel do ESP32;
3. conectividade entre notebook e AP do ESP32;
4. sensores limpos e estabilizados;
5. usuario autenticado na plataforma.

## 4. Navegacao
1. abrir detalhe do reservatorio;
2. clicar em `Calibrar`;
3. selecionar o sensor;
4. iniciar sessao;
5. acompanhar estabilidade;
6. salvar calibracao;
7. encerrar a sessao quando concluir.

## 5. Endpoints Envolvidos
- `GET /api/esp32/config/`
- `POST /api/esp32/calibracao/amostras/`
- `GET /reservatorios/<id>/calibracao/<sensor>/sessao/status/`

Comportamento:
- sem sessao ativa: `modo=normal`
- com sessao ativa: `modo=calibracao`, `sensor`, `sessao_id`, `qtd_amostras`, `atraso_amostra_ms`

## 6. Regras Atuais
- TTL da sessao: 10 minutos
- janela de estabilidade: ultimas 30 amostras
- `poll` de configuracao do ESP32: 2 segundos
- intervalo padrao de envio em calibracao: 5 segundos

## 7. Validacao Pos-Calibracao
1. voltar ao detalhe do reservatorio;
2. conferir se as novas leituras convergem para a referencia;
3. acompanhar alguns minutos de historico;
4. confirmar reducao de oscilacao indevida.
