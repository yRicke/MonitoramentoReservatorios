# Troubleshooting do Firmware

## Nao aparecem leituras no dashboard

Verifique:

1. backend Django acessivel no IP configurado;
2. `reservatorio_id` salvo no painel local;
3. se o notebook esta realmente conectado ao AP do ESP32;
4. se o firmware conseguiu consultar `/api/esp32/config/`.

## `401 nao autorizado`

Possiveis causas:

- `reservatorio_id` apontando para outro reservatorio;
- `reservatorio_id` ausente ou invalido na requisicao.

## `400 campo nao suportado: ponto_tipo`

O payload novo nao deve enviar `ponto_tipo`. Se houver um firmware antigo ou script auxiliar enviando esse campo, ele precisa ser removido.

## Painel local nao abre

Verifique:

1. IP atual do AP;
2. se a senha usada na URL corresponde a senha salva da rede AP;
3. se a rede AP do ESP32 realmente subiu apos o boot.

## Intervalos nao atualizam

O ESP32 consulta configuracao a cada 2 segundos. Se o Django estiver indisponivel, o firmware continua usando o ultimo cache valido em NVS.

## Calibracao nao envia amostras

Verifique:

1. se a UI iniciou uma sessao de calibracao;
2. se o endpoint de configuracao esta retornando `modo=calibracao`;
3. se o `sensor` da sessao confere com o fluxo em andamento;
4. se a sessao nao expirou.
