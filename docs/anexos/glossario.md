# Glossario

- `Reservatorio`: unidade principal monitorada no sistema.
- `PontoMonitoramento`: ponto logico associado ao reservatorio. No fluxo atual, `ponto_unico`.
- `LeituraQualidade`: registro historico de uma medicao processada.
- `SessaoCalibracao`: janela ativa de coleta dedicada para calibracao.
- `AmostraCalibracao`: amostra recebida do firmware durante a sessao.
- `AP`: Access Point criado pelo ESP32 para configuracao local.
- `NVS`: memoria nao volatil usada pelo ESP32 para salvar configuracao e cache.
- `raw`: bloco JSON com sinais brutos de ADC, timestamp do firmware e `device_id`.
- `ponto_tipo`: campo legado, nao aceito no fluxo novo.
