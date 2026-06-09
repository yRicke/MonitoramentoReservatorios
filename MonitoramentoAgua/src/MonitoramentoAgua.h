#ifndef MONITORAMENTO_AGUA_H
#define MONITORAMENTO_AGUA_H

#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>

struct MonitoramentoAguaConfig {
  MonitoramentoAguaConfig();

  const char* apSsid;
  const char* apPassword;
  IPAddress apIP;
  IPAddress gateway;
  IPAddress subnet;

  const char* djangoHost;
  int djangoPort;
  const char* djangoLeiturasPath;
  const char* djangoConfiguracaoPath;
  const char* djangoCalibrationSamplesPath;

  int reservatorioId;
  const char* apiToken;
  const char* deviceId;

  unsigned long intervaloEnvioNormalPadraoMs;
  unsigned long intervaloEnvioCalibracaoPadraoMs;
  unsigned long intervaloPollConfiguracaoMs;
  unsigned long delayLoopMs;

  int tdsPin;
  int turbidityPin;
  int phPin;

  int qtdAmostrasPh;
  int qtdAmostrasTds;
  int qtdAmostrasTurbidez;
  int qtdAmostrasCalibracaoPadrao;
  int atrasoAmostraCalibracaoPadraoMs;
  int maxAmostrasFiltro;

  unsigned long serialBaud;
};

class MonitoramentoAgua {
public:
  explicit MonitoramentoAgua(uint8_t ds18b20Pin = 4);

  void begin(const MonitoramentoAguaConfig& config);
  void loop();

private:
  static const int FILA_MAX_LEITURAS = 180;
  static const int MAX_AMOSTRAS_FILTRO_ABSOLUTO = 80;

  struct LeituraPendente {
    float temperatura;
    int adcTds;
    int adcTurb;
    int adcPh;
    unsigned long firmwareTsMs;
  };

  MonitoramentoAguaConfig config_;
  OneWire oneWire_;
  DallasTemperature sensors_;
  Preferences prefsConfig_;
  Preferences prefsQueue_;
  WebServer server_;

  String apSsid_;
  String apPassword_;
  String djangoHost_;
  String apiToken_;
  String deviceId_;
  IPAddress apIP_;
  int reservatorioId_;
  unsigned long intervaloEnvioNormalMs_;
  unsigned long intervaloEnvioCalibracaoMs_;
  unsigned long intervaloPollConfiguracaoMs_;

  unsigned long ultimoEnvio_;
  unsigned long ultimoFlushFila_;
  unsigned long ultimoPollConfiguracao_;
  unsigned long ultimoEnvioCalibracao_;

  bool calibracaoAtiva_;
  bool iniciado_;
  bool prefsConfigDisponivel_;
  bool prefsQueueDisponivel_;

  String sensorCalibracaoAtivo_;
  int qtdAmostrasCalibracao_;
  int atrasoAmostraCalibracaoMs_;
  long sessaoCalibracaoId_;

  LeituraPendente filaLeituras_[FILA_MAX_LEITURAS];
  int filaInicio_;
  int filaFim_;
  int filaQuantidade_;

  void carregarConfiguracaoSalva();
  void salvarConfiguracaoSalva();
  void carregarCacheIntervalos();
  void salvarCacheIntervalos();
  bool configuracaoProntaParaEnvio() const;
  void garantirDeviceId();

  void iniciarRedePropria();
  bool redeDisponivel() const;

  void iniciarPainelConfiguracao();
  void responderPainelConfiguracao();
  void salvarPainelConfiguracao();
  String montarHtmlPainel(const String& alerta = "") const;
  static String escaparHtml(const String& valor);
  static bool converterIp(const String& texto, IPAddress& ip);

  String montarUrlDjangoLeituras() const;
  String montarUrlDjangoConfiguracao() const;
  String montarUrlDjangoAmostrasCalibracao() const;

  void resetarFilaEmMemoria();
  void salvarFilaEmFlash();
  void carregarFilaDaFlash();
  void enfileirarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs);
  bool obterPrimeiraLeituraFila(LeituraPendente& leitura);
  void removerPrimeiraLeituraFila();
  void tentarEnviarFila(int limitePorCiclo);

  float lerTemperatura();
  void ordenarLeituras(int* leituras, int total);
  int mediaMioloEstavel(int* leiturasOrdenadas, int total);
  int lerAdcFiltradoRobusto(int pino, int totalAmostras, int atrasoPorAmostraMs, bool ignorarZeros = false);
  int lerAdcPhFiltradoRobusto(int quantidadeAmostras, int atrasoAmostraMs);

  bool enviarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs);
  bool enviarAmostraCalibracao(const String& sensor, float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs);

  String extrairCampoJsonString(const String& json, const String& chave) const;
  long extrairCampoJsonLong(const String& json, const String& chave, long padrao) const;

  bool atualizarConfiguracaoRemota();
  void desativarModoCalibracao();
  void aplicarModoCalibracao(const String& sensor, long sessaoId, int qtdAmostras, int atrasoAmostraMs);

  void executarCicloLeituraNormal();
  void executarCicloCalibracao();
};

#endif
