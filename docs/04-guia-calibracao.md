# Guia de Calibração do Sistema Integrado

## 1. Objetivo
Padronizar o processo de calibraÃ§Ã£o dos sensores do sistema:
- temperatura;
- TDS;
- turbidez;
- pH (2 pontos).

Este guia cobre o fluxo completo entre:
- módulo edge (ESP32 com sensores);
- módulo plataforma (backend + interface web).

## 2. Conceitos Operacionais
### 2.1 SessÃ£o de calibraÃ§Ã£o
Uma sessÃ£o Ã© um modo temporÃ¡rio no qual:
1. o operador inicia calibragem na interface;
2. o backend publica comando de calibraÃ§Ã£o;
3. o ESP32 envia amostras dedicadas;
4. a UI avalia estabilidade em tempo real;
5. somente apÃ³s estabilidade os botÃµes de confirmaÃ§Ã£o sÃ£o habilitados.

### 2.2 Janela e limites de estabilidade
ParÃ¢metros usados pelo sistema:
- TTL da sessÃ£o: 10 minutos.
- Amostras avaliadas: Ãºltimas 30.
- Limite de desvio de temperatura: 0.2.
- Limite de desvio TDS (ADC): 20.0.
- Limite de desvio turbidez (ADC): 20.0.
- Limite de desvio pH (ADC): 12.0.

### 2.3 Vencimento de calibraÃ§Ã£o
Alertas de vencimento:
- pH: vencida a partir de 15 dias;
- Ã¡gua (temperatura/TDS/turbidez): vencida a partir de 15 dias.

## 3. PrÃ©-requisitos para Calibrar
Checklist:
1. dispositivo vinculado ao `reservatorio_id` e `ponto_tipo` corretos;
2. conectividade ativa entre ESP32 e backend;
3. token IoT vÃ¡lido (`X-API-Token`);
4. sensores limpos e estabilizados no meio de referÃªncia;
5. acesso de usuÃ¡rio autenticado na plataforma.

## 4. NavegaÃ§Ã£o do Fluxo de CalibraÃ§Ã£o
Na interface web:
1. abrir detalhe do reservatÃ³rio;
2. clicar `Calibrar`;
3. selecionar ponto (`antes_tratamento` ou `depois_tratamento`);
4. selecionar sensor;
5. iniciar sessÃ£o;
6. acompanhar cards de estabilidade;
7. confirmar calibraÃ§Ã£o quando habilitado.

## 5. API de Suporte Ã  CalibraÃ§Ã£o
Endpoints envolvidos:
- `GET /api/esp32/calibracao/comando/`
- `POST /api/esp32/calibracao/amostras/`
- `GET /reservatorios/<id>/calibracao/<ponto>/<sensor>/sessao/status/` (UI polling)

Comportamento:
- sem sessÃ£o ativa: backend retorna `modo: normal`;
- com sessÃ£o ativa: retorna `modo: calibracao`, `sensor`, `sessao_id` e parÃ¢metros de amostragem.

## 6. CalibraÃ§Ã£o de Temperatura
## 6.1 Objetivo
Ajustar leitura calibrada de temperatura usando:
- temperatura bruta mÃ©dia estÃ¡vel da sessÃ£o;
- referÃªncia informada pelo operador;
- inclinaÃ§Ã£o (ganho) opcional.

## 6.2 Entrada do operador
Campos:
- `temperatura_referencia_c` (obrigatÃ³rio);
- `temperatura_inclinacao` (avanÃ§ado, opcional na lÃ³gica de negÃ³cio e exposto no formulÃ¡rio).

## 6.3 CÃ¡lculo aplicado
Offset calculado:
- `offset = temperatura_referencia - (temperatura_bruta * inclinacao)`

AplicaÃ§Ã£o nas prÃ³ximas leituras:
- `temperatura_corrigida = (temperatura_bruta * inclinacao) + offset`

## 6.4 CritÃ©rios de aceite
CalibraÃ§Ã£o sÃ³ Ã© aceita quando:
1. sessÃ£o ativa do sensor temperatura;
2. estabilidade do sensor aprovada;
3. dados vÃ¡lidos de temperatura mÃ©dia.

## 7. CalibraÃ§Ã£o de TDS
## 7.1 Objetivo
Ajustar TDS final (ppm) com base em:
- ADC mÃ©dio estÃ¡vel;
- temperatura calibrada;
- alvo de referÃªncia;
- inclinaÃ§Ã£o do sensor.

## 7.2 Entrada do operador
Campos:
- `tds_alvo_ppm` (0 a < 50);
- `tds_inclinacao` (> 0).

## 7.3 CÃ¡lculo base
ConversÃ£o de ADC para TDS no backend:
1. `tensao = adc * 3.3 / 4095`
2. compensaÃ§Ã£o tÃ©rmica em relaÃ§Ã£o a 25 Â°C
3. polinÃ´mio de TDS aplicado Ã  tensÃ£o compensada

Depois, na calibraÃ§Ã£o:
- `offset_tds = alvo_tds - (tds_base * inclinacao_tds)`

AplicaÃ§Ã£o nas prÃ³ximas leituras:
- `tds_final = (tds_calculado * inclinacao_tds) + offset_tds`

## 7.4 CritÃ©rios de aceite
ExigÃªncias:
1. sessÃ£o ativa de TDS;
2. estabilidade do sensor aprovada;
3. estabilidade de temperatura aprovada;
4. presenÃ§a de `adc_tds` e temperatura na referÃªncia da sessÃ£o.

## 8. CalibraÃ§Ã£o de Turbidez
## 8.1 Objetivo
Ajustar turbidez (NTU) com base em:
- ADC mÃ©dio estÃ¡vel;
- alvo de referÃªncia;
- inclinaÃ§Ã£o do sensor.

## 8.2 Entrada do operador
Campos:
- `turbidez_alvo_ntu` (0 a < 0.5);
- `turbidez_inclinacao` (> 0).

## 8.3 CÃ¡lculo aplicado
Base atual do sistema:
- turbidez Ã© derivada da tensÃ£o/ADC (modelo vigente).

Offset de calibraÃ§Ã£o:
- `offset_turbidez = alvo_turbidez - (turbidez_base * inclinacao_turbidez)`

AplicaÃ§Ã£o em leituras futuras:
- `turbidez_final = (turbidez_calculada * inclinacao_turbidez) + offset_turbidez`

## 8.4 CritÃ©rios de aceite
ExigÃªncias:
1. sessÃ£o ativa de turbidez;
2. estabilidade do sensor aprovada;
3. presenÃ§a de `adc_turb` vÃ¡lido na referÃªncia da sessÃ£o.

## 9. CalibraÃ§Ã£o de pH (2 pontos)
## 9.1 Objetivo
Recalcular:
- inclinaÃ§Ã£o do eletrodo (`ph_inclinacao`);
- tensÃ£o equivalente de referÃªncia para pH 7 (`ph_voltagem_referencia_7`);
- temperatura de calibraÃ§Ã£o mÃ©dia.

## 9.2 SequÃªncia obrigatÃ³ria
1. iniciar sessÃ£o do sensor `ph`;
2. aguardar estabilidade do sensor e da temperatura;
3. informar pH da soluÃ§Ã£o 1 e capturar ponto 1;
4. trocar soluÃ§Ã£o fÃ­sica;
5. aguardar nova estabilidade;
6. informar pH da soluÃ§Ã£o 2;
7. confirmar calibraÃ§Ã£o final.

## 9.3 CÃ¡lculo de 2 pontos
Com:
- ponto 1: (`ph1`, `v1`)
- ponto 2: (`ph2`, `v2`)

InclinaÃ§Ã£o:
- `ph_inclinacao = (v2 - v1) / (ph1 - ph2)`

ReferÃªncia equivalente pH 7:
- `v7 = v1 + ph_inclinacao * (ph1 - 7.0)`

CondiÃ§Ã£o obrigatÃ³ria:
- `ph1` e `ph2` devem ser diferentes.

## 9.4 RecomendaÃ§Ã£o de soluÃ§Ãµes
PrÃ¡tica indicada:
- usar soluÃ§Ãµes tampÃ£o com valores conhecidos e distintos;
- exemplos usuais: `7 e 4` ou `7 e 10`.

## 9.5 CritÃ©rios de aceite
ExigÃªncias:
1. sessÃ£o ativa de pH;
2. estabilidade de sensor aprovada;
3. estabilidade de temperatura aprovada;
4. ponto 1 capturado;
5. inclinaÃ§Ã£o calculada > 0 e finita.

## 10. Regras de Bloqueio na UI
O sistema desabilita aÃ§Ãµes de confirmaÃ§Ã£o quando:
- nÃ£o hÃ¡ sessÃ£o ativa;
- estabilidade mÃ­nima nÃ£o foi atingida;
- para pH, ponto 1 ainda nÃ£o foi capturado.

Resultado:
- menor risco de calibrar com dado instÃ¡vel;
- maior repetibilidade entre operadores.

## 11. Checklist de ExecuÃ§Ã£o por Sensor
Checklist Ãºnico (aplicar por sensor):
1. iniciar sessÃ£o;
2. aguardar aumento gradual de amostras;
3. confirmar status `Estavel`;
4. validar Ãºltimo valor e mÃ©dia;
5. preencher referÃªncia;
6. salvar calibraÃ§Ã£o;
7. validar mensagem de sucesso;
8. repetir para prÃ³ximo sensor.

## 12. ValidaÃ§Ã£o PÃ³s-CalibraÃ§Ã£o
ApÃ³s salvar:
1. voltar ao detalhe do reservatÃ³rio;
2. conferir se novas leituras convergem para referÃªncia;
3. acompanhar 10 a 20 minutos de dados;
4. verificar se status reduziu variaÃ§Ã£o indevida;
5. registrar data/hora da intervenÃ§Ã£o.

## 13. Problemas Comuns e CorreÃ§Ãµes
### 13.1 "SessÃ£o inativa"
CorreÃ§Ã£o:
1. iniciar sessÃ£o novamente;
2. confirmar que ESP estÃ¡ consultando comando de calibraÃ§Ã£o.

### 13.2 "Aguardando estabilidade"
CorreÃ§Ã£o:
1. manter sensor imerso sem perturbaÃ§Ã£o;
2. reduzir vibraÃ§Ã£o e ruÃ­do elÃ©trico;
3. aguardar novas amostras atÃ© estabilizar.

### 13.3 "Sem leitura bruta completa"
CorreÃ§Ã£o:
1. validar se `raw` estÃ¡ chegando com ADC necessÃ¡rio;
2. confirmar pinagem e leitura do sensor;
3. reiniciar sessÃ£o apÃ³s corrigir.

### 13.4 Falha no pH em 2 pontos
CorreÃ§Ã£o:
1. confirmar que os dois valores de pH sÃ£o diferentes;
2. recapturar ponto 1 se necessÃ¡rio;
3. repetir com soluÃ§Ãµes tampÃ£o vÃ¡lidas.

## 14. Boas PrÃ¡ticas de CalibraÃ§Ã£o
RecomendaÃ§Ãµes:
- calibrar com soluÃ§Ãµes de referÃªncia confiÃ¡veis;
- evitar calibrar durante transientes de temperatura;
- executar limpeza dos sensores antes da sessÃ£o;
- nÃ£o alterar inclinaÃ§Ãµes avanÃ§adas sem justificativa tÃ©cnica;
- manter histÃ³rico de parÃ¢metros alterados.

## 15. FrequÃªncia Operacional Recomendada
PrÃ¡tica mÃ­nima:
- verificar vencimento de todos sensores semanalmente;
- recalibrar imediatamente apÃ³s manutenÃ§Ã£o fÃ­sica;
- recalibrar quando houver drift persistente nas sÃ©ries.

## 16. Registro e Rastreabilidade
Registrar para cada calibraÃ§Ã£o:
1. reservatÃ³rio e ponto;
2. sensor calibrado;
3. referÃªncia utilizada;
4. horÃ¡rio e usuÃ¡rio executor;
5. observaÃ§Ãµes de campo.

Isso facilita:
- auditoria tÃ©cnica;
- comparaÃ§Ã£o de desempenho por perÃ­odo;
- investigaÃ§Ã£o de desvios futuros.

## 17. CritÃ©rio de Encerramento
Uma calibraÃ§Ã£o Ã© considerada concluÃ­da quando:
1. parÃ¢metros foram salvos com sucesso;
2. sessÃ£o pode ser encerrada sem erros;
3. leituras subsequentes demonstram comportamento estÃ¡vel;
4. intervenÃ§Ã£o foi registrada no processo operacional.




