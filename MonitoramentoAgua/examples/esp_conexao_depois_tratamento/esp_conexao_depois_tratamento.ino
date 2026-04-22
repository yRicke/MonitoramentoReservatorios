#include <MonitoramentoAgua.h>

MonitoramentoAgua monitoramento;

void setup() {
  MonitoramentoAguaConfig config;
  config.modoRede = MONITORAMENTO_REDE_STA;

  config.redeSsid = "MONITOR-ESP32";
  config.redePassword = "12345678";
  config.localIP = IPAddress(192, 168, 50, 3);
  config.gateway = IPAddress(192, 168, 50, 1);
  config.subnet = IPAddress(255, 255, 255, 0);
  config.dns = IPAddress(192, 168, 50, 1);

  config.djangoHost = "192.168.50.2";
  config.apiToken = "Oqc9zeW5fZjRFvxXZhaJtdVAD3sRrhy2G0a7IWegMR3ZOR3dsAxQ142qRut3fWtA";
  config.reservatorioId = 8;

  config.pontoTipo = "depois_tratamento";
  config.deviceId = "esp_depois_tratamento";

  monitoramento.begin(config);
}

void loop() {
  monitoramento.loop();
}
