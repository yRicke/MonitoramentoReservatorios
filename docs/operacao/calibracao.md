# Guia de Calibracao

## Sensores suportados

- temperatura
- TDS
- turbidez
- pH

## Fluxo geral

1. Abrir o detalhe do reservatorio.
2. Clicar em `Calibrar`.
3. Escolher o sensor.
4. Iniciar a sessao.
5. Acompanhar as amostras e a estabilidade.
6. Salvar a calibracao.
7. Encerrar a sessao quando concluir.

## Sessao de calibracao

No fluxo atual da UI:

- TTL da sessao: `10 minutos`
- janela de estabilidade: `30 amostras`
- `poll` de configuracao do ESP32: `2 segundos`
- a quantidade de amostras do firmware na sessao escala proporcionalmente ao intervalo configurado de calibracao, usando `80 amostras` como base para `5 segundos`
- atraso padrao entre amostras de calibracao analogica: `50 ms`
- envio padrao em calibracao: `5 segundos`

## Regras por sensor

### Temperatura

- usa a media estavel da sessao;
- o operador informa a temperatura de referencia;
- a calibracao ajusta inclinacao e offset.

### TDS

- usa temperatura calibrada atual;
- usa ADC bruto estavel da sessao;
- o operador informa o alvo em ppm;
- a calibracao ajusta inclinacao e offset do TDS.

### Turbidez

- a sessao serve para observar estabilidade da tensao;
- a gravacao final e manual em dois pontos;
- o operador informa dois pares `NTU/tensao`;
- o backend recalcula a reta `NTU = m * tensao + b`.

### pH

- a sessao serve para observar estabilidade da tensao;
- a gravacao final e manual em dois pontos;
- o operador informa dois pares `pH/tensao`;
- o backend recalcula `ph_inclinacao` e a referencia equivalente de `pH 7`.

## Endpoints usados

- `GET /api/esp32/config/`
- `POST /api/esp32/calibracao/amostras/`
- `GET /reservatorios/<id>/calibracao/<sensor>/sessao/status/`
- `POST /reservatorios/<id>/calibracao-<sensor>/auto/`

## Pos-calibracao

1. retornar ao detalhe do reservatorio;
2. verificar convergencia para a referencia;
3. observar historico por alguns minutos;
4. resetar a calibracao do sensor apenas quando realmente necessario.
