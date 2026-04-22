#ifndef MONITORAMENTO_AGUA_H
#define MONITORAMENTO_AGUA_H

#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Preferences.h>
#include <WiFi.h>

enum MonitoramentoModoRede {
  MONITORAMENTO_REDE_AP,
  MONITORAMENTO_REDE_STA
};

struct MonitoramentoAguaConfig {
  MonitoramentoAguaConfig();

  MonitoramentoModoRede modoRede;
  const char* redeSsid;
  const char* redePassword;
  IPAddress localIP;
  IPAddress gateway;
  IPAddress subnet;
  IPAddress dns;

  const char* djangoHost;
  int djangoPort;
  const char* djangoPath;
  const char* djangoSyncPath;
  const char* djangoCalibrationCommandPath;
  const char* djangoCalibrationSamplesPath;
  const char* apiToken;

  int reservatorioId;
  const char* pontoTipo;
  const char* deviceId;

  unsigned long intervaloEnvioMs;
  unsigned long intervaloSyncRelogioMs;
  unsigned long intervaloPollCalibracaoMs;
  unsigned long intervaloEnvioCalibracaoPadraoMs;
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
  Preferences prefs_;

  unsigned long ultimoEnvio_;
  unsigned long ultimoFlushFila_;
  unsigned long ultimaSincronizacaoRelogio_;
  unsigned long proximaLeituraSincronizada_;
  unsigned long ultimoPollCalibracao_;
  unsigned long ultimoEnvioCalibracao_;
  unsigned long ultimaTentativaReconexao_;

  bool relogioSincronizado_;
  bool calibracaoAtiva_;
  bool nvsDisponivel_;
  bool iniciado_;

  String sensorCalibracaoAtivo_;
  unsigned long intervaloEnvioCalibracaoMs_;
  int qtdAmostrasCalibracao_;
  int atrasoAmostraCalibracaoMs_;
  long sessaoCalibracaoId_;

  LeituraPendente filaLeituras_[FILA_MAX_LEITURAS];
  int filaInicio_;
  int filaFim_;
  int filaQuantidade_;

  String montarUrlDjangoLeituras();
  String montarUrlDjangoSync();
  String montarUrlDjangoComandoCalibracao();
  String montarUrlDjangoAmostrasCalibracao();

  void iniciarRede();
  void iniciarRedePropria();
  void conectarNaRedePrincipal();
  bool redeDisponivel();

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

  String extrairCampoJsonString(const String& json, const String& chave);
  long extrairCampoJsonLong(const String& json, const String& chave, long padrao);

  bool atualizarSincronizacaoLeitura(bool forcar = false);
  void desativarModoCalibracao();
  void aplicarModoCalibracao(const String& sensor, long sessaoId, unsigned long intervaloEnvioMs, int qtdAmostras, int atrasoAmostraMs);
  void atualizarModoCalibracao();

  void executarCicloLeituraNormal();
  void executarCicloCalibracao();
};

#endif
