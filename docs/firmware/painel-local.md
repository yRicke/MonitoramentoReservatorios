# Painel Local do ESP32

## Modo de operacao

O ESP32 opera em modo AP e disponibiliza um painel web local.

Padroes atuais:

- IP padrao: `192.168.50.1`
- rota raiz: orienta o operador a abrir `/<senha_wifi>`
- rota do painel: `http://<ip_atual>/<senha_wifi>`

## Campos exibidos no painel

Campos editaveis:

- `reservatorio_id`
- `token`
- `ssid`
- `senha`
- `ip_esp`
- `ip_django`

Campos somente leitura:

- `device_id`
- ultimo intervalo normal recebido
- ultimo intervalo de calibracao recebido
- GPIO do buzzer
- cadencia do alerta sonoro

## Persistencia em NVS

Configuracoes persistidas:

- `reservatorio_id`
- `ssid`
- `senha`
- `ip_esp`
- `ip_django`
- `token`
- `device_id`
- cache dos intervalos normal e calibracao

## Validacoes do painel

Ao salvar, o firmware exige:

- `reservatorio_id` maior que zero;
- SSID preenchido;
- senha com pelo menos 8 caracteres;
- IP do Django preenchido;
- token preenchido;
- IP local do ESP32 valido.

Quando a validacao passa, o ESP32 salva a configuracao e reinicia.
