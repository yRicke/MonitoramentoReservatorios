# Guia de Calibração do Sistema Integrado

## 1. Objetivo
Padronizar o processo de calibração dos sensores do sistema:
- temperatura;
- TDS;
- turbidez;
- pH (2 pontos).

Este guia cobre o fluxo completo entre:
- módulo edge (ESP32 com sensores);
- módulo plataforma (backend + interface web).

## 2. Conceitos Operacionais
### 2.1 Sessão de calibração
Uma sessão é um modo temporário no qual:
1. o operador inicia calibragem na interface;
2. o backend publica comando de calibração;
3. o ESP32 envia amostras dedicadas;
4. a UI avalia estabilidade em tempo real;
5. somente após estabilidade os botões de confirmação são habilitados.

### 2.2 Janela e limites de estabilidade
Parâmetros usados pelo sistema:
- TTL da sessão: 10 minutos.
- Amostras avaliadas: últimas 30.
- Limite de desvio de temperatura: 0.2.
- Limite de desvio TDS (ADC): 20.0.
- Limite de desvio turbidez (ADC): 20.0.
- Limite de desvio pH (ADC): 12.0.

### 2.3 Vencimento de calibração
Alertas de vencimento:
- pH: vencida a partir de 15 dias;
- água (temperatura/TDS/turbidez): vencida a partir de 15 dias.

## 3. Pré-requisitos para Calibrar
Checklist:
1. dispositivo vinculado ao `reservatorio_id` e `ponto_tipo` corretos;
2. conectividade ativa entre ESP32 e backend;
3. token IoT válido (`X-API-Token`);
4. sensores limpos e estabilizados no meio de referência;
5. acesso de usuário autenticado na plataforma.

## 4. Navegação do Fluxo de Calibração
Na interface web:
1. abrir detalhe do reservatório;
2. clicar `Calibrar`;
3. selecionar ponto (`antes_tratamento` ou `depois_tratamento`);
4. selecionar sensor;
5. iniciar sessão;
6. acompanhar cards de estabilidade;
7. confirmar calibração quando habilitado.

## 5. API de Suporte à Calibração
Endpoints envolvidos:
- `GET /api/esp32/calibracao/comando/`
- `POST /api/esp32/calibracao/amostras/`
- `GET /reservatorios/<id>/calibracao/<ponto>/<sensor>/sessao/status/` (UI polling)

Comportamento:
- sem sessão ativa: backend retorna `modo: normal`;
- com sessão ativa: retorna `modo: calibracao`, `sensor`, `sessao_id` e parâmetros de amostragem.

## 6. Calibração de Temperatura
## 6.1 Objetivo
Ajustar leitura calibrada de temperatura usando:
- temperatura bruta média estável da sessão;
- referência informada pelo operador;
- inclinação (ganho) opcional.

## 6.2 Entrada do operador
Campos:
- `temperatura_referencia_c` (obrigatório);
- `temperatura_inclinacao` (avançado, opcional na lógica de negócio e exposto no formulário).

## 6.3 Cálculo aplicado
Offset calculado:
- `offset = temperatura_referencia - (temperatura_bruta * inclinacao)`

Aplicação nas próximas leituras:
- `temperatura_corrigida = (temperatura_bruta * inclinacao) + offset`

## 6.4 Critérios de aceite
Calibração só é aceita quando:
1. sessão ativa do sensor temperatura;
2. estabilidade do sensor aprovada;
3. dados válidos de temperatura média.

## 7. Calibração de TDS
## 7.1 Objetivo
Ajustar TDS final (ppm) com base em:
- ADC médio estável;
- temperatura calibrada;
- alvo de referência;
- inclinação do sensor.

## 7.2 Entrada do operador
Campos:
- `tds_alvo_ppm` (0 a < 50);
- `tds_inclinacao` (> 0).

## 7.3 Cálculo base
Conversão de ADC para TDS no backend:
1. `tensao = adc * 3.3 / 4095`
2. compensação térmica em relação a 25 °C
3. polinômio de TDS aplicado à tensão compensada

Depois, na calibração:
- `offset_tds = alvo_tds - (tds_base * inclinacao_tds)`

Aplicação nas próximas leituras:
- `tds_final = (tds_calculado * inclinacao_tds) + offset_tds`

## 7.4 Critérios de aceite
Exigências:
1. sessão ativa de TDS;
2. estabilidade do sensor aprovada;
3. estabilidade de temperatura aprovada;
4. presença de `adc_tds` e temperatura na referência da sessão.

## 8. Calibração de Turbidez
## 8.1 Objetivo
Ajustar turbidez (NTU) com base em:
- ADC médio estável;
- alvo de referência;
- inclinação do sensor.

## 8.2 Entrada do operador
Campos:
- `turbidez_alvo_ntu` (0 a < 0.5);
- `turbidez_inclinacao` (> 0).

## 8.3 Cálculo aplicado
Base atual do sistema:
- turbidez é derivada da tensão/ADC (modelo vigente).

Offset de calibração:
- `offset_turbidez = alvo_turbidez - (turbidez_base * inclinacao_turbidez)`

Aplicação em leituras futuras:
- `turbidez_final = (turbidez_calculada * inclinacao_turbidez) + offset_turbidez`

## 8.4 Critérios de aceite
Exigências:
1. sessão ativa de turbidez;
2. estabilidade do sensor aprovada;
3. presença de `adc_turb` válido na referência da sessão.

## 9. Calibração de pH (papel e caneta)
## 9.1 Objetivo
Recalcular:
- inclinação do eletrodo (`ph_inclinacao`);
- tensão equivalente de referência para pH 7 (`ph_voltagem_referencia_7`);
- reta linear do sensor a partir de dois pontos anotados pelo operador.

## 9.2 Sequência obrigatória
1. iniciar sessão do sensor `ph`;
2. mergulhar o sensor na solução 1;
3. aguardar estabilização da tensão exibida;
4. anotar o par (`ph1`, `v1`);
5. encerrar a sessão, limpar o sensor e trocar a solução;
6. iniciar nova sessão;
7. aguardar nova estabilização da tensão;
8. anotar o par (`ph2`, `v2`);
9. preencher manualmente os 4 campos do formulário;
10. salvar a calibração.

Observação:
- nesta versão, a sessão de calibração do pH funciona como visor em tempo real para o operador anotar tensão, ADC e pH traduzido.

## 9.3 Cálculo de 2 pontos
Com:
- ponto 1: (`ph1`, `v1`)
- ponto 2: (`ph2`, `v2`)

Inclinação:
- `ph_inclinacao = (v2 - v1) / (ph1 - ph2)`

Referência equivalente pH 7:
- `v7 = v1 + ph_inclinacao * (ph1 - 7.0)`

Condição obrigatória:
- `ph1` e `ph2` devem ser diferentes.

Forma linear equivalente:
- `ph = a * tensao + b`
- `a = -1 / ph_inclinacao`
- `b = 7 + (v7 / ph_inclinacao)`

## 9.4 Recomendação de soluções
Prática indicada:
- usar soluções tampão com valores conhecidos e distintos;
- exemplos usuais: `7 e 4` ou `7 e 10`.

## 9.5 Critérios de aceite
Exigências:
1. dois pares (`pH`, `tensao`) preenchidos manualmente;
2. `ph1` e `ph2` diferentes;
3. tensões dentro da faixa do ADC (`0` a `3.3 V`);
4. inclinação calculada > 0 e finita.

## 10. Regras de Bloqueio na UI
O sistema desabilita ações de confirmação quando:
- não há sessão ativa;
- estabilidade mínima não foi atingida.

Exceção atual do pH:
- o botão de salvar não depende de sessão ativa;
- a sessão serve para o operador observar e anotar os valores antes do preenchimento manual.

Resultado:
- menor risco de calibrar com dado instável;
- maior repetibilidade entre operadores.

## 11. Checklist de Execução por Sensor
Checklist único (aplicar por sensor):
1. iniciar sessão;
2. aguardar aumento gradual de amostras;
3. confirmar status `Estavel`;
4. validar último valor e média;
5. preencher referência;
6. salvar calibração;
7. validar mensagem de sucesso;
8. repetir para próximo sensor.

## 12. Validação Pós-Calibração
Após salvar:
1. voltar ao detalhe do reservatório;
2. conferir se novas leituras convergem para referência;
3. acompanhar 10 a 20 minutos de dados;
4. verificar se status reduziu variação indevida;
5. registrar data/hora da intervenção.

## 13. Problemas Comuns e Correções
### 13.1 "Sessão inativa"
Correção:
1. iniciar sessão novamente;
2. confirmar que ESP está consultando comando de calibração.

### 13.2 "Aguardando estabilidade"
Correção:
1. manter sensor imerso sem perturbação;
2. reduzir vibração e ruído elétrico;
3. aguardar novas amostras até estabilizar.

### 13.3 "Sem leitura bruta completa"
Correção:
1. validar se `raw` está chegando com ADC necessário;
2. confirmar pinagem e leitura do sensor;
3. reiniciar sessão após corrigir.

### 13.4 Falha no pH em 2 pontos
Correção:
1. confirmar que os dois valores de pH são diferentes;
2. confirmar que as duas tensões anotadas estão corretas;
3. repetir a medição com soluções tampão válidas;
4. observar se a tensão realmente estabilizou antes de anotar.

## 14. Boas Práticas de Calibração
Recomendações:
- calibrar com soluções de referência confiáveis;
- evitar calibrar durante transientes de temperatura;
- executar limpeza dos sensores antes da sessão;
- não alterar inclinações avançadas sem justificativa técnica;
- manter histórico de parâmetros alterados.

## 15. Frequência Operacional Recomendada
Prática mínima:
- verificar vencimento de todos sensores semanalmente;
- recalibrar imediatamente após manutenção física;
- recalibrar quando houver drift persistente nas séries.

## 16. Registro e Rastreabilidade
Registrar para cada calibração:
1. reservatório e ponto;
2. sensor calibrado;
3. referência utilizada;
4. horário e usuário executor;
5. observações de campo.

Isso facilita:
- auditoria técnica;
- comparação de desempenho por período;
- investigação de desvios futuros.

## 17. Critério de Encerramento
Uma calibração é considerada concluída quando:
1. parâmetros foram salvos com sucesso;
2. sessão pode ser encerrada sem erros;
3. leituras subsequentes demonstram comportamento estável;
4. intervenção foi registrada no processo operacional.
