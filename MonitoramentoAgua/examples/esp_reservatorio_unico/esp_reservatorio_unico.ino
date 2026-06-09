#include <MonitoramentoAgua.h>

MonitoramentoAgua monitoramento;

void setup() {
  MonitoramentoAguaConfig config;

  config.apSsid = "MONITOR-ESP32";
  config.apPassword = "12345678";
  config.apIP = IPAddress(192, 168, 50, 1);
  config.gateway = IPAddress(192, 168, 50, 1);
  config.subnet = IPAddress(255, 255, 255, 0);

  config.djangoHost = "192.168.50.2";
  config.djangoPort = 8000;

  monitoramento.begin(config);
}

void loop() {
  monitoramento.loop();
}
