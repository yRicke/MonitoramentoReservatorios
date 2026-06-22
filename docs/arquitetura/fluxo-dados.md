# Fluxo de Dados

## 1. Ciclo normal de leitura

1. O ESP32 sobe em modo AP e disponibiliza o painel local.
2. O operador configura `reservatorio_id` e IP do Django.
3. O firmware consulta `GET /api/esp32/config/`.
4. Em modo normal, o firmware le temperatura, ADC de TDS, ADC de turbidez e ADC de pH.
5. A leitura e enviada para `POST /api/esp32/leituras/`.
6. O backend valida o `reservatorio_id`, normaliza o payload e resolve o `ponto_unico`.
7. As calibracoes salvas do ponto sao aplicadas.
8. O status e calculado pelas regras de faixa.
9. A leitura e persistida em `LeituraQualidade`.
10. O status do ponto e do reservatorio e sincronizado.

## 2. Tratamento de sinais brutos

O backend aceita preferencialmente sinais em `raw`:

- `adc_tds`
- `adc_turb`
- `adc_ph`
- `firmware_ts_ms`
- `firmware_now_ms`
- `device_id`

Se o payload trouxer tensoes ou valores finais, a service tenta resolver a melhor fonte disponivel, mas o contrato atual do firmware envia ADCs.

## 3. Fluxo de configuracao remota

O endpoint `GET /api/esp32/config/` devolve:

- horario do servidor em epoch ms;
- intervalo de poll da configuracao;
- intervalo normal;
- intervalo de calibracao;
- estado do alerta sonoro;
- modo de operacao normal ou calibracao.

Quando existe sessao ativa, a mesma resposta inclui:

- `sessao_id`
- `sensor`
- `qtd_amostras`
- `atraso_amostra_ms`
- `expira_em`

## 4. Fluxo de calibracao

1. O operador entra na tela de calibracao de um sensor.
2. O Django inicia uma `SessaoCalibracao` para o `ponto_unico`.
3. O endpoint de configuracao passa a responder `modo=calibracao`.
4. O ESP32 muda o tipo de coleta e envia amostras dedicadas para `POST /api/esp32/calibracao/amostras/`.
5. A UI consulta o status da sessao e acompanha estabilidade.
6. O operador salva a calibracao automatica ou manual, dependendo do sensor.

## 5. Fluxo do alerta sonoro

1. O backend recalcula o status do reservatorio.
2. Quando o estado exige buzzer, `alerta_sonoro_ativo` passa a ser verdadeiro na configuracao remota.
3. O ESP32 aplica o ciclo ligado/desligado informado.
4. A UI permite silenciar, silenciar permanentemente ou testar o buzzer por 5 segundos.

## 6. Resiliencia local

- O firmware mantem fila offline de leituras.
- A fila e persistida em NVS.
- Os ultimos intervalos validos tambem ficam em NVS.
- Se o Django ficar indisponivel, o ESP32 continua com os ultimos valores aceitos.
