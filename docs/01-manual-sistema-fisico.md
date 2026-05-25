# Manual TÃ©cnico do Sistema FÃ­sico

## 1. Objetivo
Este documento descreve o módulo físico do sistema de monitoramento de água, baseado em ESP32, sensores analógicos e integração com a plataforma web.

O objetivo do sistema fÃ­sico Ã©:
- coletar mediÃ§Ãµes de qualidade da Ã¡gua em campo;
- manter coleta contÃ­nua mesmo com instabilidade de rede;
- enviar leituras estruturadas para o backend Django;
- suportar rotinas de calibraÃ§Ã£o assistida em operaÃ§Ã£o.

## 2. Escopo do Módulo Físico
O produto fÃ­sico cobre:
- hardware embarcado (ESP32 + sensores);
- firmware da biblioteca `MonitoramentoAgua`;
- conectividade Wi-Fi em modo AP ou STA;
- envio de leitura para endpoints HTTP do backend;
- fila offline persistente em NVS.

NÃ£o cobre:
- decisÃ£o final de status de qualidade (executada no backend);
- gestÃ£o de usuÃ¡rios e dashboards da plataforma de software.

## 3. Arquitetura FÃ­sica Resumida
Fluxo resumido:
1. Sensores coletam grandezas fÃ­sicas e elÃ©tricas.
2. ESP32 realiza amostragem e filtragem robusta.
3. Leitura Ã© enfileirada localmente (memÃ³ria + NVS).
4. Quando rede disponÃ­vel, o firmware envia para a API Django.
5. Backend processa, classifica e persiste.

## 4. Componentes de Hardware
Componentes usados na implementaÃ§Ã£o atual:
- Microcontrolador: ESP32.
- Sensor de temperatura: DS18B20 (OneWire).
- Sensor TDS: saÃ­da analÃ³gica (ADC).
- Sensor de turbidez: saÃ­da analÃ³gica (ADC).
- Sensor de pH: saÃ­da analÃ³gica (ADC).
- AlimentaÃ§Ã£o estÃ¡vel para ESP32 e sensores.
- Infraestrutura Wi-Fi para comunicaÃ§Ã£o com o servidor Django.

DependÃªncias de firmware declaradas:
- `OneWire`
- `DallasTemperature`

## 5. Pinagem PadrÃ£o do Firmware
Pinagem padrÃ£o definida em `MonitoramentoAguaConfig`:
- `ds18b20Pin`: 4 (no construtor da classe `MonitoramentoAgua`)
- `tdsPin`: 34
- `turbidityPin`: 35
- `phPin`: 32

ObservaÃ§Ãµes:
- alteraÃ§Ãµes de pinagem devem ser refletidas no firmware do dispositivo;
- sensores analÃ³gicos devem respeitar faixa de entrada do ADC do ESP32;
- o firmware usa `analogSetAttenuation(ADC_11db)` para ampliar faixa de leitura.

## 6. Modos de Rede Suportados
### 6.1 Modo AP (`MONITORAMENTO_REDE_AP`)
Uso tÃ­pico:
- o ESP32 cria uma rede prÃ³pria;
- o servidor se conecta Ã  rede do ESP32.

ParÃ¢metros comuns:
- SSID padrÃ£o de exemplo: `MONITOR-ESP32`
- senha padrÃ£o de exemplo: `12345678`
- IP AP padrÃ£o de exemplo: `192.168.50.1`

### 6.2 Modo STA (`MONITORAMENTO_REDE_STA`)
Uso tÃ­pico:
- o ESP32 entra na rede existente;
- servidor e ESP compartilham a mesma LAN.

Comportamento:
- reconexÃ£o automÃ¡tica quando cai Wi-Fi;
- retentativa de conexÃ£o periÃ³dica no loop.

## 7. Canais de ComunicaÃ§Ã£o com Backend
URLs usadas pelo firmware (configurÃ¡veis):
- `/api/esp32/leituras/`
- `/api/esp32/sync/`
- `/api/esp32/calibracao/comando/`
- `/api/esp32/calibracao/amostras/`

CabeÃ§alho de autenticaÃ§Ã£o:
- `X-API-Token: <token>`

## 8. Estrutura de Leitura Enviada
Payload tÃ­pico de leitura:
- `reservatorio_id`
- `ponto_tipo` (`antes_tratamento` ou `depois_tratamento`)
- `device_id`
- `temperatura`
- `raw.adc_tds`
- `raw.adc_turb`
- `raw.adc_ph`
- `raw.firmware_ts_ms`
- `raw.firmware_now_ms`

## 9. Filtragem e EstabilizaÃ§Ã£o no Edge
TÃ©cnicas aplicadas no firmware:
- mÃºltiplas amostras por sensor;
- ordenaÃ§Ã£o das leituras;
- uso de mÃ©dia do miolo estÃ¡vel (descarta extremos);
- parÃ¢metros configurÃ¡veis de quantidade de amostras e atraso entre amostras.

Objetivo:
- reduzir ruÃ­do instantÃ¢neo e oscilaÃ§Ã£o elÃ©trica;
- melhorar robustez para o backend classificar com menor variabilidade.

## 10. ResiliÃªncia Offline
Mecanismo implementado:
- fila circular local com capacidade mÃ¡xima (`FILA_MAX_LEITURAS = 180`);
- persistÃªncia em NVS (`Preferences`) com metadados de fila;
- reenvio automÃ¡tico quando rede volta;
- descarte da leitura mais antiga se fila lotar.

BenefÃ­cios:
- continuidade operacional durante falha de link;
- menor perda de dados em campo;
- recuperaÃ§Ã£o automÃ¡tica sem intervenÃ§Ã£o manual em falhas curtas.

## 11. SincronizaÃ§Ã£o Temporal
O firmware consulta `/api/esp32/sync/` para:
- obter intervalo oficial de leitura (`intervalo_ms`);
- alinhar prÃ³xima coleta a uma janela comum;
- reduzir desalinhamento entre pontos antes/depois.

Se sincronizaÃ§Ã£o nÃ£o estiver disponÃ­vel:
- o sistema continua operando com intervalo local;
- volta a sincronizar quando rede normaliza.

## 12. Modo de CalibraÃ§Ã£o no Dispositivo
Durante calibraÃ§Ã£o:
1. firmware consulta endpoint de comando de calibraÃ§Ã£o;
2. backend informa modo e sensor ativo (`temperatura`, `tds`, `turbidez`, `ph`);
3. dispositivo passa a enviar amostras dedicadas para calibraÃ§Ã£o;
4. ao encerrar sessÃ£o, retorna ao ciclo normal de leitura.

## 13. InstalaÃ§Ã£o FÃ­sica Recomendada
Passos recomendados:
1. Definir pontos de coleta `antes_tratamento` e `depois_tratamento`.
2. Instalar sensores com proteÃ§Ã£o mecÃ¢nica e acesso para manutenÃ§Ã£o.
3. Garantir isolamento de respingos na eletrÃ´nica.
4. Validar alimentaÃ§Ã£o estÃ¡vel e aterramento conforme prÃ¡tica elÃ©trica local.
5. Validar intensidade de sinal Wi-Fi nos pontos de instalaÃ§Ã£o.

## 14. Comissionamento de Campo
Checklist de comissionamento:
1. Gravar firmware com `reservatorio_id`, `ponto_tipo` e `device_id` corretos.
2. Configurar `djangoHost` e `apiToken` vÃ¡lidos.
3. Verificar conexÃ£o Wi-Fi (AP ou STA).
4. Confirmar retorno `201` em `/api/esp32/leituras/`.
5. Conferir leitura no painel web do reservatÃ³rio correto.
6. Executar calibraÃ§Ã£o inicial dos sensores.

## 15. OperaÃ§Ã£o e ManutenÃ§Ã£o Preventiva
RecomendaÃ§Ãµes mÃ­nimas:
- inspeÃ§Ã£o visual semanal de cabos, conectores e caixa;
- limpeza dos sensores conforme especificaÃ§Ã£o do fabricante;
- conferÃªncia periÃ³dica da estabilidade de leitura;
- recalibraÃ§Ã£o por rotina operacional ou apÃ³s eventos de contaminaÃ§Ã£o;
- validaÃ§Ã£o de relÃ³gio/sincronizaÃ§Ã£o quando houver gaps de comunicaÃ§Ã£o.

## 16. SeguranÃ§a e Boas PrÃ¡ticas
Boas prÃ¡ticas obrigatÃ³rias:
- nÃ£o manter token padrÃ£o em produÃ§Ã£o;
- nÃ£o versionar credenciais reais em firmware;
- proteger fisicamente a eletrÃ´nica contra acesso indevido;
- manter firmware e backend alinhados por versÃ£o;
- registrar intervenÃ§Ãµes de manutenÃ§Ã£o para rastreabilidade.

## 17. Troubleshooting de Campo
### 17.1 ESP sem envio de leituras
Verificar:
1. energia e reboot do mÃ³dulo;
2. rede disponÃ­vel (cliente no AP ou STA conectado);
3. IP/porta do servidor Django;
4. token no cabeÃ§alho;
5. status HTTP de retorno.

### 17.2 Leituras errÃ¡ticas
Verificar:
1. integridade de cabos e conectores;
2. ruÃ­do elÃ©trico e aterramento;
3. limpeza do sensor;
4. parÃ¢metros de amostragem do firmware;
5. necessidade de recalibraÃ§Ã£o.

### 17.3 Fila offline crescendo continuamente
Verificar:
1. reachability do servidor (`djangoHost`);
2. firewall/roteamento local;
3. token invÃ¡lido (401);
4. erros 400 por payload inconsistente;
5. disponibilidade do endpoint no backend.

## 18. Limites e Premissas
Premissas atuais da implementaÃ§Ã£o:
- backend esperado em rede local HTTP;
- autenticaÃ§Ã£o por token estÃ¡tico;
- armazenamento local de fila com limite fixo;
- processamento analÃ­tico principal executado no backend.

## 19. Interface com a Plataforma de Software
IntegraÃ§Ãµes diretas com a plataforma de software:
- ingestÃ£o de leituras normais;
- sincronizaÃ§Ã£o de relÃ³gio de coleta;
- comando de sessÃ£o de calibraÃ§Ã£o;
- recebimento de amostras de calibraÃ§Ã£o.

Sem a plataforma de software ativa, o sistema físico mantém coleta local, mas não conclui o ciclo de monitoramento fim a fim.




