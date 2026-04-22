#include "MonitoramentoAgua.h"

#include <HTTPClient.h>
#include <math.h>

namespace {
const char* SENSOR_TEMPERATURA = "temperatura";
const char* SENSOR_TDS = "tds";
const char* SENSOR_TURBIDEZ = "turbidez";
const char* SENSOR_PH = "ph";

const unsigned long INTERVALO_FLUSH_FILA_MS = 2000;
const unsigned long INTERVALO_RECONEXAO_STA_MS = 10000;

const char* NVS_NAMESPACE = "fila_esp32";
const char* NVS_KEY_META_INI = "meta_ini";
const char* NVS_KEY_META_FIM = "meta_fim";
const char* NVS_KEY_META_QTD = "meta_qtd";
const char* NVS_KEY_DADOS_A = "dados_a";
const char* NVS_KEY_DADOS_B = "dados_b";
}

MonitoramentoAguaConfig::MonitoramentoAguaConfig()
  : modoRede(MONITORAMENTO_REDE_AP),
    redeSsid("MONITOR-ESP32"),
    redePassword("12345678"),
    localIP(192, 168, 50, 1),
    gateway(192, 168, 50, 1),
    subnet(255, 255, 255, 0),
    dns(192, 168, 50, 1),
    djangoHost("192.168.50.2"),
    djangoPort(8000),
    djangoPath("/api/esp32/leituras/"),
    djangoSyncPath("/api/esp32/sync/"),
    djangoCalibrationCommandPath("/api/esp32/calibracao/comando/"),
    djangoCalibrationSamplesPath("/api/esp32/calibracao/amostras/"),
    apiToken(""),
    reservatorioId(8),
    pontoTipo("antes_tratamento"),
    deviceId("esp_antes_tratamento"),
    intervaloEnvioMs(1UL * 1000UL * 60UL),
    intervaloSyncRelogioMs(30UL * 1000UL),
    intervaloPollCalibracaoMs(2000),
    intervaloEnvioCalibracaoPadraoMs(5000),
    delayLoopMs(50),
    tdsPin(34),
    turbidityPin(35),
    phPin(32),
    qtdAmostrasPh(60),
    qtdAmostrasTds(60),
    qtdAmostrasTurbidez(60),
    qtdAmostrasCalibracaoPadrao(80),
    atrasoAmostraCalibracaoPadraoMs(50),
    maxAmostrasFiltro(80),
    serialBaud(115200) {
}

MonitoramentoAgua::MonitoramentoAgua(uint8_t ds18b20Pin)
  : config_(),
    oneWire_(ds18b20Pin),
    sensors_(&oneWire_),
    ultimoEnvio_(0),
    ultimoFlushFila_(0),
    ultimaSincronizacaoRelogio_(0),
    proximaLeituraSincronizada_(0),
    ultimoPollCalibracao_(0),
    ultimoEnvioCalibracao_(0),
    ultimaTentativaReconexao_(0),
    relogioSincronizado_(false),
    calibracaoAtiva_(false),
    nvsDisponivel_(false),
    iniciado_(false),
    sensorCalibracaoAtivo_(""),
    intervaloEnvioCalibracaoMs_(0),
    qtdAmostrasCalibracao_(0),
    atrasoAmostraCalibracaoMs_(0),
    sessaoCalibracaoId_(0),
    filaInicio_(0),
    filaFim_(0),
    filaQuantidade_(0) {
}

void MonitoramentoAgua::begin(const MonitoramentoAguaConfig& config) {
  config_ = config;
  intervaloEnvioCalibracaoMs_ = config_.intervaloEnvioCalibracaoPadraoMs;
  qtdAmostrasCalibracao_ = config_.qtdAmostrasCalibracaoPadrao;
  atrasoAmostraCalibracaoMs_ = config_.atrasoAmostraCalibracaoPadraoMs;

  Serial.begin(config_.serialBaud);
  analogSetAttenuation(ADC_11db);
  sensors_.begin();

  nvsDisponivel_ = prefs_.begin(NVS_NAMESPACE, false);
  if (!nvsDisponivel_) {
    Serial.println("Falha ao iniciar NVS para fila offline.");
  } else {
    carregarFilaDaFlash();
  }

  iniciarRede();
  ultimoEnvio_ = millis() - config_.intervaloEnvioMs;
  atualizarSincronizacaoLeitura(true);
  ultimoPollCalibracao_ = millis() - config_.intervaloPollCalibracaoMs;
  iniciado_ = true;
}

void MonitoramentoAgua::loop() {
  if (!iniciado_) return;

  unsigned long agora = millis();

  if (agora - ultimoFlushFila_ >= INTERVALO_FLUSH_FILA_MS) {
    ultimoFlushFila_ = agora;
    tentarEnviarFila(3);
  }

  if (agora - ultimoPollCalibracao_ >= config_.intervaloPollCalibracaoMs) {
    ultimoPollCalibracao_ = agora;
    atualizarModoCalibracao();
  }

  if (calibracaoAtiva_) {
    if (agora - ultimoEnvioCalibracao_ >= intervaloEnvioCalibracaoMs_) {
      ultimoEnvioCalibracao_ = agora;
      executarCicloCalibracao();
    }
  } else if (relogioSincronizado_) {
    if ((long)(agora - proximaLeituraSincronizada_) >= 0) {
      executarCicloLeituraNormal();
      unsigned long depoisLeitura = millis();
      do {
        proximaLeituraSincronizada_ += config_.intervaloEnvioMs;
      } while ((long)(depoisLeitura - proximaLeituraSincronizada_) >= 0);
    }
  } else if (agora - ultimoEnvio_ >= config_.intervaloEnvioMs) {
    ultimoEnvio_ = agora;
    executarCicloLeituraNormal();
  }

  if (!calibracaoAtiva_ && agora - ultimaSincronizacaoRelogio_ >= config_.intervaloSyncRelogioMs) {
    atualizarSincronizacaoLeitura();
  }

  delay(config_.delayLoopMs);
}

String MonitoramentoAgua::montarUrlDjangoLeituras() {
  return String("http://") + config_.djangoHost + ":" + String(config_.djangoPort) + config_.djangoPath;
}

String MonitoramentoAgua::montarUrlDjangoSync() {
  return String("http://") + config_.djangoHost + ":" + String(config_.djangoPort) + config_.djangoSyncPath;
}

String MonitoramentoAgua::montarUrlDjangoComandoCalibracao() {
  String url = String("http://") + config_.djangoHost + ":" + String(config_.djangoPort) + config_.djangoCalibrationCommandPath;
  url += "?reservatorio_id=" + String(config_.reservatorioId);
  url += "&ponto_tipo=" + String(config_.pontoTipo);
  return url;
}

String MonitoramentoAgua::montarUrlDjangoAmostrasCalibracao() {
  return String("http://") + config_.djangoHost + ":" + String(config_.djangoPort) + config_.djangoCalibrationSamplesPath;
}

void MonitoramentoAgua::iniciarRede() {
  if (config_.modoRede == MONITORAMENTO_REDE_AP) {
    iniciarRedePropria();
  } else {
    conectarNaRedePrincipal();
  }
}

void MonitoramentoAgua::iniciarRedePropria() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(config_.localIP, config_.gateway, config_.subnet);

  bool ok = WiFi.softAP(config_.redeSsid, config_.redePassword);
  if (!ok) {
    Serial.println("Falha ao subir AP do ESP32.");
    return;
  }

  Serial.println("AP iniciado.");
  Serial.print("SSID: ");
  Serial.println(config_.redeSsid);
  Serial.print("IP AP: ");
  Serial.println(WiFi.softAPIP());
}

void MonitoramentoAgua::conectarNaRedePrincipal() {
  WiFi.mode(WIFI_STA);
  WiFi.config(config_.localIP, config_.gateway, config_.subnet, config_.dns);
  WiFi.begin(config_.redeSsid, config_.redePassword);

  Serial.print("Conectando na rede principal ");
  Serial.print(config_.redeSsid);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Falha ao conectar na rede principal. Nova tentativa sera feita no loop.");
    return;
  }

  Serial.println("Conectado na rede principal.");
  Serial.print("IP STA: ");
  Serial.println(WiFi.localIP());
}

bool MonitoramentoAgua::redeDisponivel() {
  if (config_.modoRede == MONITORAMENTO_REDE_AP) {
    return WiFi.softAPgetStationNum() > 0;
  }

  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  unsigned long agora = millis();
  if (agora - ultimaTentativaReconexao_ >= INTERVALO_RECONEXAO_STA_MS) {
    ultimaTentativaReconexao_ = agora;
    Serial.println("WiFi desconectado. Tentando reconectar na rede principal...");
    WiFi.disconnect();
    WiFi.begin(config_.redeSsid, config_.redePassword);
  }

  return false;
}

void MonitoramentoAgua::resetarFilaEmMemoria() {
  filaInicio_ = 0;
  filaFim_ = 0;
  filaQuantidade_ = 0;
}

void MonitoramentoAgua::salvarFilaEmFlash() {
  if (!nvsDisponivel_) return;

  const uint8_t* base = reinterpret_cast<const uint8_t*>(filaLeituras_);
  const size_t bytesTotais = sizeof(filaLeituras_);
  const size_t bytesA = bytesTotais / 2;
  const size_t bytesB = bytesTotais - bytesA;

  prefs_.putInt(NVS_KEY_META_INI, filaInicio_);
  prefs_.putInt(NVS_KEY_META_FIM, filaFim_);
  prefs_.putInt(NVS_KEY_META_QTD, filaQuantidade_);
  prefs_.putBytes(NVS_KEY_DADOS_A, base, bytesA);
  prefs_.putBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);
}

void MonitoramentoAgua::carregarFilaDaFlash() {
  if (!nvsDisponivel_) return;

  int inicio = prefs_.getInt(NVS_KEY_META_INI, 0);
  int fim = prefs_.getInt(NVS_KEY_META_FIM, 0);
  int quantidade = prefs_.getInt(NVS_KEY_META_QTD, 0);

  if (
    inicio < 0 || inicio >= FILA_MAX_LEITURAS ||
    fim < 0 || fim >= FILA_MAX_LEITURAS ||
    quantidade < 0 || quantidade > FILA_MAX_LEITURAS
  ) {
    resetarFilaEmMemoria();
    salvarFilaEmFlash();
    return;
  }

  const size_t bytesTotais = sizeof(filaLeituras_);
  const size_t bytesA = bytesTotais / 2;
  const size_t bytesB = bytesTotais - bytesA;

  uint8_t* base = reinterpret_cast<uint8_t*>(filaLeituras_);
  size_t lidosA = prefs_.getBytes(NVS_KEY_DADOS_A, base, bytesA);
  size_t lidosB = prefs_.getBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);

  if (lidosA != bytesA || lidosB != bytesB) {
    resetarFilaEmMemoria();
    salvarFilaEmFlash();
    return;
  }

  filaInicio_ = inicio;
  filaFim_ = fim;
  filaQuantidade_ = quantidade;

  if (filaQuantidade_ > 0) {
    Serial.print("Fila restaurada da flash. Pendentes: ");
    Serial.println(filaQuantidade_);
  }
}

void MonitoramentoAgua::enfileirarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs) {
  if (filaQuantidade_ >= FILA_MAX_LEITURAS) {
    filaInicio_ = (filaInicio_ + 1) % FILA_MAX_LEITURAS;
    filaQuantidade_--;
    Serial.println("Fila cheia: leitura mais antiga descartada.");
  }

  filaLeituras_[filaFim_].temperatura = temperatura;
  filaLeituras_[filaFim_].adcTds = adcTds;
  filaLeituras_[filaFim_].adcTurb = adcTurb;
  filaLeituras_[filaFim_].adcPh = adcPh;
  filaLeituras_[filaFim_].firmwareTsMs = firmwareTsMs;

  filaFim_ = (filaFim_ + 1) % FILA_MAX_LEITURAS;
  filaQuantidade_++;
  salvarFilaEmFlash();

  Serial.print("Fila pendente: ");
  Serial.println(filaQuantidade_);
}

bool MonitoramentoAgua::obterPrimeiraLeituraFila(LeituraPendente& leitura) {
  if (filaQuantidade_ <= 0) return false;
  leitura = filaLeituras_[filaInicio_];
  return true;
}

void MonitoramentoAgua::removerPrimeiraLeituraFila() {
  if (filaQuantidade_ <= 0) return;
  filaInicio_ = (filaInicio_ + 1) % FILA_MAX_LEITURAS;
  filaQuantidade_--;
}

void MonitoramentoAgua::tentarEnviarFila(int limitePorCiclo) {
  if (filaQuantidade_ <= 0) return;
  if (!redeDisponivel()) return;

  int enviados = 0;
  while (filaQuantidade_ > 0 && enviados < limitePorCiclo) {
    LeituraPendente leitura;
    if (!obterPrimeiraLeituraFila(leitura)) return;

    if (!enviarLeitura(
      leitura.temperatura,
      leitura.adcTds,
      leitura.adcTurb,
      leitura.adcPh,
      leitura.firmwareTsMs
    )) {
      Serial.println("Falha no envio da fila. Mantendo pendencias.");
      break;
    }

    removerPrimeiraLeituraFila();
    enviados++;
  }

  if (enviados > 0) {
    salvarFilaEmFlash();
    Serial.print("Fila enviada: ");
    Serial.print(enviados);
    Serial.print(" | Restantes: ");
    Serial.println(filaQuantidade_);
  }
}

float MonitoramentoAgua::lerTemperatura() {
  sensors_.requestTemperatures();
  float temp = sensors_.getTempCByIndex(0);
  if (temp == DEVICE_DISCONNECTED_C) return NAN;
  return temp;
}

void MonitoramentoAgua::ordenarLeituras(int* leituras, int total) {
  for (int i = 0; i < total - 1; i++) {
    for (int j = i + 1; j < total; j++) {
      if (leituras[i] > leituras[j]) {
        int tmp = leituras[i];
        leituras[i] = leituras[j];
        leituras[j] = tmp;
      }
    }
  }
}

int MonitoramentoAgua::mediaMioloEstavel(int* leiturasOrdenadas, int total) {
  if (total <= 0) return 0;

  int inicioFaixa = total / 3;
  int fimFaixa = total - inicioFaixa;
  int quantidadeFaixa = fimFaixa - inicioFaixa;

  if (quantidadeFaixa <= 0) {
    inicioFaixa = 0;
    fimFaixa = total;
    quantidadeFaixa = total;
  }

  long somaCentral = 0;
  for (int i = inicioFaixa; i < fimFaixa; i++) {
    somaCentral += leiturasOrdenadas[i];
  }

  return (quantidadeFaixa > 0)
    ? (int)(somaCentral / quantidadeFaixa)
    : 0;
}

int MonitoramentoAgua::lerAdcFiltradoRobusto(int pino, int totalAmostras, int atrasoPorAmostraMs, bool ignorarZeros) {
  if (totalAmostras <= 0) return 0;

  int alvoAmostras = totalAmostras;
  if (alvoAmostras > config_.maxAmostrasFiltro) {
    alvoAmostras = config_.maxAmostrasFiltro;
  }
  if (alvoAmostras > MAX_AMOSTRAS_FILTRO_ABSOLUTO) {
    alvoAmostras = MAX_AMOSTRAS_FILTRO_ABSOLUTO;
  }

  int leituras[MAX_AMOSTRAS_FILTRO_ABSOLUTO];
  int validas = 0;
  for (int i = 0; i < alvoAmostras; i++) {
    int leitura = analogRead(pino);
    if (!ignorarZeros || leitura > 0) {
      leituras[validas] = leitura;
      validas += 1;
    }
    delay(atrasoPorAmostraMs);
  }

  if (validas <= 0) {
    return 0;
  }

  ordenarLeituras(leituras, validas);
  return mediaMioloEstavel(leituras, validas);
}

int MonitoramentoAgua::lerAdcPhFiltradoRobusto(int quantidadeAmostras, int atrasoAmostraMs) {
  return lerAdcFiltradoRobusto(config_.phPin, quantidadeAmostras, atrasoAmostraMs, false);
}

bool MonitoramentoAgua::enviarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs) {
  if (!redeDisponivel()) {
    if (config_.modoRede == MONITORAMENTO_REDE_AP) {
      Serial.println("Sem cliente conectado no AP. Nao enviando.");
    } else {
      Serial.println("Sem conexao Wi-Fi. Nao enviando.");
    }
    return false;
  }

  HTTPClient http;
  http.setTimeout(10000);

  String url = montarUrlDjangoLeituras();
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", config_.apiToken);

  String body = "{";
  body += "\"reservatorio_id\":" + String(config_.reservatorioId) + ",";
  body += "\"ponto_tipo\":\"" + String(config_.pontoTipo) + "\",";
  body += "\"device_id\":\"" + String(config_.deviceId) + "\",";
  body += "\"temperatura\":" + String(temperatura, 2) + ",";
  body += "\"raw\":{";
  body += "\"adc_tds\":" + String(adcTds) + ",";
  body += "\"adc_turb\":" + String(adcTurb) + ",";
  body += "\"adc_ph\":" + String(adcPh) + ",";
  body += "\"firmware_ts_ms\":" + String(firmwareTsMs) + ",";
  body += "\"firmware_now_ms\":" + String(millis());
  body += "}";
  body += "}";

  int code = http.POST(body);
  String resposta = http.getString();
  http.end();

  Serial.print("URL: ");
  Serial.println(url);
  Serial.print("POST code: ");
  Serial.println(code);
  Serial.print("Resposta: ");
  Serial.println(resposta);

  return (code >= 200 && code < 300);
}

bool MonitoramentoAgua::enviarAmostraCalibracao(
  const String& sensor,
  float temperatura,
  int adcTds,
  int adcTurb,
  int adcPh,
  unsigned long firmwareTsMs
) {
  if (!redeDisponivel()) {
    if (config_.modoRede == MONITORAMENTO_REDE_AP) {
      Serial.println("Sem cliente conectado no AP. Nao enviando amostra de calibracao.");
    } else {
      Serial.println("Sem conexao Wi-Fi. Nao enviando amostra de calibracao.");
    }
    return false;
  }

  HTTPClient http;
  http.setTimeout(10000);

  String url = montarUrlDjangoAmostrasCalibracao();
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", config_.apiToken);

  String body = "{";
  body += "\"reservatorio_id\":" + String(config_.reservatorioId) + ",";
  body += "\"ponto_tipo\":\"" + String(config_.pontoTipo) + "\",";
  body += "\"device_id\":\"" + String(config_.deviceId) + "\",";
  body += "\"sensor\":\"" + sensor + "\"";
  if (!isnan(temperatura)) {
    body += ",\"temperatura\":" + String(temperatura, 2);
  }
  body += ",\"raw\":{";

  bool precisaVirgula = false;
  if (adcTds >= 0) {
    body += "\"adc_tds\":" + String(adcTds);
    precisaVirgula = true;
  }
  if (adcTurb >= 0) {
    if (precisaVirgula) body += ",";
    body += "\"adc_turb\":" + String(adcTurb);
    precisaVirgula = true;
  }
  if (adcPh >= 0) {
    if (precisaVirgula) body += ",";
    body += "\"adc_ph\":" + String(adcPh);
    precisaVirgula = true;
  }
  if (precisaVirgula) body += ",";
  body += "\"firmware_ts_ms\":" + String(firmwareTsMs) + ",";
  body += "\"firmware_now_ms\":" + String(millis());
  body += "}}";

  int code = http.POST(body);
  String resposta = http.getString();
  http.end();

  Serial.print("Calibracao POST code: ");
  Serial.println(code);
  Serial.print("Resposta calibracao: ");
  Serial.println(resposta);

  return (code >= 200 && code < 300);
}

String MonitoramentoAgua::extrairCampoJsonString(const String& json, const String& chave) {
  String marcador = "\"" + chave + "\":";
  int inicio = json.indexOf(marcador);
  if (inicio < 0) return "";

  inicio += marcador.length();
  while (inicio < (int)json.length() && (json[inicio] == ' ' || json[inicio] == '\n' || json[inicio] == '\r' || json[inicio] == '\t')) {
    inicio++;
  }

  if (inicio >= (int)json.length() || json[inicio] != '"') return "";
  inicio += 1;
  int fim = json.indexOf('"', inicio);
  if (fim < 0) return "";
  return json.substring(inicio, fim);
}

long MonitoramentoAgua::extrairCampoJsonLong(const String& json, const String& chave, long padrao) {
  String marcador = "\"" + chave + "\":";
  int inicio = json.indexOf(marcador);
  if (inicio < 0) return padrao;

  inicio += marcador.length();
  while (inicio < (int)json.length() && (json[inicio] == ' ' || json[inicio] == '\n' || json[inicio] == '\r' || json[inicio] == '\t')) {
    inicio++;
  }

  int fim = inicio;
  while (
    fim < (int)json.length() &&
    json[fim] != ',' &&
    json[fim] != '}' &&
    json[fim] != '\n' &&
    json[fim] != '\r'
  ) {
    fim++;
  }

  String valor = json.substring(inicio, fim);
  valor.trim();
  if (valor.length() <= 0) return padrao;
  return valor.toInt();
}

bool MonitoramentoAgua::atualizarSincronizacaoLeitura(bool forcar) {
  unsigned long agora = millis();
  if (!forcar && relogioSincronizado_ && agora - ultimaSincronizacaoRelogio_ < config_.intervaloSyncRelogioMs) {
    return true;
  }

  ultimaSincronizacaoRelogio_ = agora;

  if (!redeDisponivel()) {
    return false;
  }

  HTTPClient http;
  http.setTimeout(5000);

  String url = montarUrlDjangoSync();
  http.begin(url);
  http.addHeader("X-API-Token", config_.apiToken);

  int code = http.GET();
  String resposta = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.print("Falha ao sincronizar leitura. Code: ");
    Serial.println(code);
    return false;
  }

  long aguardarMs = extrairCampoJsonLong(resposta, "aguardar_ms", -1);
  long intervaloMs = extrairCampoJsonLong(resposta, "intervalo_ms", config_.intervaloEnvioMs);
  if (aguardarMs < 0 || intervaloMs <= 0) {
    Serial.println("Resposta de sincronizacao invalida.");
    return false;
  }

  if (aguardarMs < 500) {
    aguardarMs += intervaloMs;
  }

  proximaLeituraSincronizada_ = millis() + (unsigned long)aguardarMs;
  relogioSincronizado_ = true;

  Serial.print("Leitura sincronizada em ");
  Serial.print(aguardarMs);
  Serial.println(" ms.");
  return true;
}

void MonitoramentoAgua::desativarModoCalibracao() {
  if (calibracaoAtiva_) {
    Serial.println("Modo calibracao encerrado. Voltando para o fluxo normal.");
  }
  calibracaoAtiva_ = false;
  sensorCalibracaoAtivo_ = "";
  intervaloEnvioCalibracaoMs_ = config_.intervaloEnvioCalibracaoPadraoMs;
  qtdAmostrasCalibracao_ = config_.qtdAmostrasCalibracaoPadrao;
  atrasoAmostraCalibracaoMs_ = config_.atrasoAmostraCalibracaoPadraoMs;
  sessaoCalibracaoId_ = 0;
}

void MonitoramentoAgua::aplicarModoCalibracao(
  const String& sensor,
  long sessaoId,
  unsigned long intervaloEnvioMs,
  int qtdAmostras,
  int atrasoAmostraMs
) {
  bool mudou = (!calibracaoAtiva_) || sensorCalibracaoAtivo_ != sensor || sessaoCalibracaoId_ != sessaoId;

  calibracaoAtiva_ = true;
  sensorCalibracaoAtivo_ = sensor;
  sessaoCalibracaoId_ = sessaoId;
  intervaloEnvioCalibracaoMs_ = intervaloEnvioMs;
  qtdAmostrasCalibracao_ = qtdAmostras;
  atrasoAmostraCalibracaoMs_ = atrasoAmostraMs;

  if (mudou) {
    ultimoEnvioCalibracao_ = millis() - intervaloEnvioCalibracaoMs_;
    Serial.print("Modo calibracao ativo. Sensor: ");
    Serial.print(sensorCalibracaoAtivo_);
    Serial.print(" | sessao ");
    Serial.println(sessaoCalibracaoId_);
  }
}

void MonitoramentoAgua::atualizarModoCalibracao() {
  if (!redeDisponivel()) {
    return;
  }

  HTTPClient http;
  http.setTimeout(5000);
  String url = montarUrlDjangoComandoCalibracao();
  http.begin(url);
  http.addHeader("X-API-Token", config_.apiToken);

  int code = http.GET();
  String resposta = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.print("Falha ao consultar comando de calibracao. Code: ");
    Serial.println(code);
    return;
  }

  String modo = extrairCampoJsonString(resposta, "modo");
  if (modo != "calibracao") {
    desativarModoCalibracao();
    return;
  }

  String sensor = extrairCampoJsonString(resposta, "sensor");
  if (
    sensor != SENSOR_TEMPERATURA &&
    sensor != SENSOR_TDS &&
    sensor != SENSOR_TURBIDEZ &&
    sensor != SENSOR_PH
  ) {
    desativarModoCalibracao();
    return;
  }

  long sessaoId = extrairCampoJsonLong(resposta, "sessao_id", 0);
  unsigned long intervaloEnvioMs = (unsigned long)extrairCampoJsonLong(
    resposta,
    "intervalo_envio_ms",
    config_.intervaloEnvioCalibracaoPadraoMs
  );
  int qtdAmostras = (int)extrairCampoJsonLong(
    resposta,
    "qtd_amostras",
    config_.qtdAmostrasCalibracaoPadrao
  );
  int atrasoAmostraMs = (int)extrairCampoJsonLong(
    resposta,
    "atraso_amostra_ms",
    config_.atrasoAmostraCalibracaoPadraoMs
  );

  if (intervaloEnvioMs < 1000) {
    intervaloEnvioMs = config_.intervaloEnvioCalibracaoPadraoMs;
  }
  if (qtdAmostras <= 0) {
    qtdAmostras = config_.qtdAmostrasCalibracaoPadrao;
  }
  if (atrasoAmostraMs <= 0) {
    atrasoAmostraMs = config_.atrasoAmostraCalibracaoPadraoMs;
  }

  aplicarModoCalibracao(
    sensor,
    sessaoId,
    intervaloEnvioMs,
    qtdAmostras,
    atrasoAmostraMs
  );
}

void MonitoramentoAgua::executarCicloLeituraNormal() {
  float temp = lerTemperatura();
  if (isnan(temp)) {
    Serial.println("Falha ao ler temperatura.");
    return;
  }

  int adcTurbidez = lerAdcFiltradoRobusto(
    config_.turbidityPin,
    config_.qtdAmostrasTurbidez,
    10,
    false
  );
  int adcTDS = lerAdcFiltradoRobusto(
    config_.tdsPin,
    config_.qtdAmostrasTds,
    5,
    true
  );
  int adcPh = lerAdcPhFiltradoRobusto(config_.qtdAmostrasPh, 5);

  unsigned long firmwareTsMs = millis();

  Serial.print("Ponto: ");
  Serial.print(config_.pontoTipo);
  Serial.print(" | Temp: ");
  Serial.print(temp, 2);
  Serial.print(" C | ADC Turbidez: ");
  Serial.print(adcTurbidez);
  Serial.print(" | ADC TDS: ");
  Serial.print(adcTDS);
  Serial.print(" | ADC pH: ");
  Serial.println(adcPh);

  enfileirarLeitura(
    temp,
    adcTDS,
    adcTurbidez,
    adcPh,
    firmwareTsMs
  );
  tentarEnviarFila(10);
}

void MonitoramentoAgua::executarCicloCalibracao() {
  float temperatura = NAN;
  int adcTds = -1;
  int adcTurb = -1;
  int adcPh = -1;

  if (sensorCalibracaoAtivo_ == SENSOR_TEMPERATURA) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao.");
      return;
    }
  } else if (sensorCalibracaoAtivo_ == SENSOR_TDS) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao de TDS.");
      return;
    }
    adcTds = lerAdcFiltradoRobusto(
      config_.tdsPin,
      qtdAmostrasCalibracao_,
      atrasoAmostraCalibracaoMs_,
      true
    );
  } else if (sensorCalibracaoAtivo_ == SENSOR_TURBIDEZ) {
    adcTurb = lerAdcFiltradoRobusto(
      config_.turbidityPin,
      qtdAmostrasCalibracao_,
      atrasoAmostraCalibracaoMs_,
      false
    );
  } else if (sensorCalibracaoAtivo_ == SENSOR_PH) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao de pH.");
      return;
    }
    adcPh = lerAdcPhFiltradoRobusto(
      qtdAmostrasCalibracao_,
      atrasoAmostraCalibracaoMs_
    );
  } else {
    return;
  }

  unsigned long firmwareTsMs = millis();
  Serial.print("Calibracao | sensor: ");
  Serial.print(sensorCalibracaoAtivo_);
  Serial.print(" | temp: ");
  if (isnan(temperatura)) {
    Serial.print("--");
  } else {
    Serial.print(temperatura, 2);
  }
  Serial.print(" | adc_tds: ");
  Serial.print(adcTds);
  Serial.print(" | adc_turb: ");
  Serial.print(adcTurb);
  Serial.print(" | adc_ph: ");
  Serial.println(adcPh);

  enviarAmostraCalibracao(
    sensorCalibracaoAtivo_,
    temperatura,
    adcTds,
    adcTurb,
    adcPh,
    firmwareTsMs
  );
}
