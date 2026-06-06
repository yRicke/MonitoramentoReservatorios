# Guia de Calibracao do Sistema Integrado

## 1. Objetivo
Padronizar o processo de calibracao dos sensores do sistema:
- temperatura;
- TDS;
- turbidez;
- pH (2 pontos).

## 2. Conceitos Operacionais
### Sessao de calibracao
1. o operador inicia a calibragem na interface;
2. o backend publica o comando de calibracao;
3. o ESP32 envia amostras dedicadas;
4. a UI avalia estabilidade em tempo real;
5. somente apos estabilidade os botoes de confirmacao sao habilitados.

### Limites atuais
- TTL da sessao: 10 minutos
- Amostras avaliadas: ultimas 30
- Limite de desvio de temperatura: 0.2
- Limite de desvio TDS (ADC): 20.0
- Limite de desvio turbidez (ADC): 20.0
- Limite de desvio pH (ADC): 12.0

## 3. Pre-requisitos
1. dispositivo vinculado ao `reservatorio_id` e `ponto_tipo` corretos;
2. conectividade ativa entre ESP32 e backend;
3. token IoT valido;
4. sensores limpos e estabilizados;
5. usuario autenticado na plataforma.

## 4. Navegacao na Interface
1. abrir detalhe do reservatorio;
2. clicar `Calibrar`;
3. entrar no ponto unico;
4. selecionar sensor;
5. iniciar sessao;
6. acompanhar os cards de estabilidade;
7. confirmar calibracao quando habilitado.

## 5. API de Suporte
Endpoints envolvidos:
- `GET /api/esp32/calibracao/comando/`
- `POST /api/esp32/calibracao/amostras/`
- `GET /reservatorios/<id>/calibracao/<ponto>/<sensor>/sessao/status/`

Comportamento:
- sem sessao ativa: `modo=normal`;
- com sessao ativa: `modo=calibracao`, `sensor`, `sessao_id` e parametros de amostragem.

## 6. Calibracao por Sensor
### Temperatura
- usa temperatura bruta media estavel da sessao;
- aplica referencia informada pelo operador;
- aceita inclinacao avancada opcional.

### TDS
- usa ADC medio estavel;
- depende de temperatura calibrada;
- calcula offset e inclinacao final do ponto.

### Turbidez
- usa ADC medio estavel;
- aplica alvo informado pelo operador;
- calcula offset e inclinacao final do ponto.

### pH
- fluxo manual em 2 pontos;
- o operador observa a tensao estabilizada na sessao;
- depois informa dois pares `pH/tensao`;
- o backend recalcula `ph_inclinacao` e `ph_voltagem_referencia_7`.

## 7. Regras de Bloqueio
O sistema desabilita confirmacoes quando:
- nao ha sessao ativa;
- estabilidade minima nao foi atingida.

Excecao atual do pH:
- o botao de salvar nao depende de sessao ativa;
- a sessao serve como visor para anotacao.

## 8. Validacao Pos-Calibracao
1. voltar ao detalhe do reservatorio;
2. conferir se novas leituras convergem para a referencia;
3. acompanhar 10 a 20 minutos de dados;
4. verificar se o status reduziu variacao indevida.

## 9. Compatibilidade Legada
- A UI opera apenas com ponto unico.
- O backend continua aceitando `antes_tratamento` e `depois_tratamento`.
- Isso foi mantido para nao alterar a biblioteca Arduino nesta fase.
