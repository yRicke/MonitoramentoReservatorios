#include "MonitoramentoAgua.h"

#include <HTTPClient.h>
#include <math.h>

namespace {
const char* SENSOR_TEMPERATURA = "temperatura";
const char* SENSOR_TDS = "tds";
const char* SENSOR_TURBIDEZ = "turbidez";
const char* SENSOR_PH = "ph";

const unsigned long INTERVALO_FLUSH_FILA_MS = 2000;

const char* NVS_NAMESPACE_CONFIG = "mon_cfg";
const char* NVS_NAMESPACE_QUEUE = "mon_queue";

const char* NVS_KEY_SSID = "ssid";
const char* NVS_KEY_PASSWORD = "pwd";
const char* NVS_KEY_AP_IP = "ap_ip";
const char* NVS_KEY_DJANGO_IP = "dj_ip";
const char* NVS_KEY_TOKEN = "token";
const char* NVS_KEY_DEVICE = "device";
const char* NVS_KEY_RESERVATORIO = "res_id";
const char* NVS_KEY_CACHE_NORMAL = "itv_norm";
const char* NVS_KEY_CACHE_CAL = "itv_cal";

const char* NVS_KEY_META_INI = "meta_ini";
const char* NVS_KEY_META_FIM = "meta_fim";
const char* NVS_KEY_META_QTD = "meta_qtd";
const char* NVS_KEY_DADOS_A = "dados_a";
const char* NVS_KEY_DADOS_B = "dados_b";
}

MonitoramentoAguaConfig::MonitoramentoAguaConfig()
  : apSsid("MONITOR-ESP32"),
    apPassword("12345678"),
    apIP(192, 168, 50, 1),
    gateway(192, 168, 50, 1),
    subnet(255, 255, 255, 0),
    djangoHost("192.168.50.2"),
    djangoPort(8000),
    djangoLeiturasPath("/api/esp32/leituras/"),
    djangoConfiguracaoPath("/api/esp32/config/"),
    djangoCalibrationSamplesPath("/api/esp32/calibracao/amostras/"),
    reservatorioId(0),
    apiToken(""),
    deviceId(""),
    intervaloEnvioNormalPadraoMs(60UL * 1000UL),
    intervaloEnvioCalibracaoPadraoMs(5UL * 1000UL),
    intervaloPollConfiguracaoMs(2UL * 1000UL),
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
    prefsConfig_(),
    prefsQueue_(),
    server_(80),
    apSsid_(""),
    apPassword_(""),
    djangoHost_(""),
    apiToken_(""),
    deviceId_(""),
    apIP_(192, 168, 50, 1),
    reservatorioId_(0),
    intervaloEnvioNormalMs_(0),
    intervaloEnvioCalibracaoMs_(0),
    intervaloPollConfiguracaoMs_(0),
    ultimoEnvio_(0),
    ultimoFlushFila_(0),
    ultimoPollConfiguracao_(0),
    ultimoEnvioCalibracao_(0),
    calibracaoAtiva_(false),
    iniciado_(false),
    prefsConfigDisponivel_(false),
    prefsQueueDisponivel_(false),
    sensorCalibracaoAtivo_(""),
    qtdAmostrasCalibracao_(0),
    atrasoAmostraCalibracaoMs_(0),
    sessaoCalibracaoId_(0),
    filaInicio_(0),
    filaFim_(0),
    filaQuantidade_(0) {
}

void MonitoramentoAgua::begin(const MonitoramentoAguaConfig& config) {
  config_ = config;

  Serial.begin(config_.serialBaud);
  analogSetAttenuation(ADC_11db);
  sensors_.begin();

  apSsid_ = config_.apSsid ? String(config_.apSsid) : String("MONITOR-ESP32");
  apPassword_ = config_.apPassword ? String(config_.apPassword) : String("12345678");
  djangoHost_ = config_.djangoHost ? String(config_.djangoHost) : String("192.168.50.2");
  apiToken_ = config_.apiToken ? String(config_.apiToken) : String("");
  deviceId_ = config_.deviceId ? String(config_.deviceId) : String("");
  apIP_ = config_.apIP;
  reservatorioId_ = config_.reservatorioId;
  intervaloEnvioNormalMs_ = config_.intervaloEnvioNormalPadraoMs;
  intervaloEnvioCalibracaoMs_ = config_.intervaloEnvioCalibracaoPadraoMs;
  intervaloPollConfiguracaoMs_ = config_.intervaloPollConfiguracaoMs;
  qtdAmostrasCalibracao_ = config_.qtdAmostrasCalibracaoPadrao;
  atrasoAmostraCalibracaoMs_ = config_.atrasoAmostraCalibracaoPadraoMs;

  prefsConfigDisponivel_ = prefsConfig_.begin(NVS_NAMESPACE_CONFIG, false);
  if (!prefsConfigDisponivel_) {
    Serial.println("Falha ao abrir NVS de configuracao.");
  } else {
    carregarConfiguracaoSalva();
    carregarCacheIntervalos();
  }

  prefsQueueDisponivel_ = prefsQueue_.begin(NVS_NAMESPACE_QUEUE, false);
  if (!prefsQueueDisponivel_) {
    Serial.println("Falha ao abrir NVS da fila.");
  } else {
    carregarFilaDaFlash();
  }

  garantirDeviceId();
  iniciarRedePropria();
  iniciarPainelConfiguracao();

  ultimoEnvio_ = millis() - intervaloEnvioNormalMs_;
  ultimoPollConfiguracao_ = millis() - intervaloPollConfiguracaoMs_;
  iniciado_ = true;
}

void MonitoramentoAgua::loop() {
  if (!iniciado_) return;

  server_.handleClient();

  unsigned long agora = millis();

  if (agora - ultimoFlushFila_ >= INTERVALO_FLUSH_FILA_MS) {
    ultimoFlushFila_ = agora;
    tentarEnviarFila(3);
  }

  if (agora - ultimoPollConfiguracao_ >= intervaloPollConfiguracaoMs_) {
    ultimoPollConfiguracao_ = agora;
    atualizarConfiguracaoRemota();
  }

  if (calibracaoAtiva_) {
    if (agora - ultimoEnvioCalibracao_ >= intervaloEnvioCalibracaoMs_) {
      ultimoEnvioCalibracao_ = agora;
      executarCicloCalibracao();
    }
  } else if (agora - ultimoEnvio_ >= intervaloEnvioNormalMs_) {
    ultimoEnvio_ = agora;
    executarCicloLeituraNormal();
  }

  delay(config_.delayLoopMs);
}

void MonitoramentoAgua::carregarConfiguracaoSalva() {
  String ssidSalvo = prefsConfig_.getString(NVS_KEY_SSID, "");
  String senhaSalva = prefsConfig_.getString(NVS_KEY_PASSWORD, "");
  String ipSalvo = prefsConfig_.getString(NVS_KEY_AP_IP, "");
  String djangoSalvo = prefsConfig_.getString(NVS_KEY_DJANGO_IP, "");
  String tokenSalvo = prefsConfig_.getString(NVS_KEY_TOKEN, "");
  String deviceSalvo = prefsConfig_.getString(NVS_KEY_DEVICE, "");
  int reservatorioSalvo = prefsConfig_.getInt(NVS_KEY_RESERVATORIO, 0);

  if (ssidSalvo.length() > 0) apSsid_ = ssidSalvo;
  if (senhaSalva.length() >= 8) apPassword_ = senhaSalva;
  if (djangoSalvo.length() > 0) djangoHost_ = djangoSalvo;
  if (tokenSalvo.length() > 0) apiToken_ = tokenSalvo;
  if (deviceSalvo.length() > 0) deviceId_ = deviceSalvo;
  if (reservatorioSalvo > 0) reservatorioId_ = reservatorioSalvo;

  IPAddress ipConvertido;
  if (ipSalvo.length() > 0 && converterIp(ipSalvo, ipConvertido)) {
    apIP_ = ipConvertido;
  }
}

void MonitoramentoAgua::salvarConfiguracaoSalva() {
  if (!prefsConfigDisponivel_) return;

  prefsConfig_.putString(NVS_KEY_SSID, apSsid_);
  prefsConfig_.putString(NVS_KEY_PASSWORD, apPassword_);
  prefsConfig_.putString(NVS_KEY_AP_IP, apIP_.toString());
  prefsConfig_.putString(NVS_KEY_DJANGO_IP, djangoHost_);
  prefsConfig_.putString(NVS_KEY_TOKEN, apiToken_);
  prefsConfig_.putString(NVS_KEY_DEVICE, deviceId_);
  prefsConfig_.putInt(NVS_KEY_RESERVATORIO, reservatorioId_);
}

void MonitoramentoAgua::carregarCacheIntervalos() {
  if (!prefsConfigDisponivel_) return;

  unsigned long normalSalvo = prefsConfig_.getULong(
    NVS_KEY_CACHE_NORMAL,
    config_.intervaloEnvioNormalPadraoMs
  );
  unsigned long calibracaoSalva = prefsConfig_.getULong(
    NVS_KEY_CACHE_CAL,
    config_.intervaloEnvioCalibracaoPadraoMs
  );

  if (normalSalvo >= 1000UL) {
    intervaloEnvioNormalMs_ = normalSalvo;
  }
  if (calibracaoSalva >= 1000UL) {
    intervaloEnvioCalibracaoMs_ = calibracaoSalva;
  }
}

void MonitoramentoAgua::salvarCacheIntervalos() {
  if (!prefsConfigDisponivel_) return;
  prefsConfig_.putULong(NVS_KEY_CACHE_NORMAL, intervaloEnvioNormalMs_);
  prefsConfig_.putULong(NVS_KEY_CACHE_CAL, intervaloEnvioCalibracaoMs_);
}

bool MonitoramentoAgua::configuracaoProntaParaEnvio() const {
  return reservatorioId_ > 0 && djangoHost_.length() > 0 && apiToken_.length() > 0;
}

void MonitoramentoAgua::garantirDeviceId() {
  if (deviceId_.length() > 0) {
    if (prefsConfigDisponivel_) {
      prefsConfig_.putString(NVS_KEY_DEVICE, deviceId_);
    }
    return;
  }

  uint64_t chipId = ESP.getEfuseMac();
  char buffer[24];
  snprintf(buffer, sizeof(buffer), "esp32-%04X%08X", (uint16_t)(chipId >> 32), (uint32_t)chipId);
  deviceId_ = String(buffer);

  if (prefsConfigDisponivel_) {
    prefsConfig_.putString(NVS_KEY_DEVICE, deviceId_);
  }
}

void MonitoramentoAgua::iniciarRedePropria() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP_, apIP_, config_.subnet);

  bool ok = WiFi.softAP(apSsid_.c_str(), apPassword_.c_str());
  if (!ok) {
    Serial.println("Falha ao subir AP do ESP32.");
    return;
  }

  Serial.println("AP iniciado.");
  Serial.print("SSID: ");
  Serial.println(apSsid_);
  Serial.print("IP AP: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("Painel: http://");
  Serial.print(WiFi.softAPIP());
  Serial.print("/");
  Serial.println(apPassword_);
}

bool MonitoramentoAgua::redeDisponivel() const {
  return WiFi.softAPgetStationNum() > 0;
}

void MonitoramentoAgua::iniciarPainelConfiguracao() {
  server_.on("/", HTTP_GET, [this]() {
    server_.send(200, "text/plain", "Acesse /" + apPassword_ + " para abrir o painel.");
  });

  String rotaPainel = "/" + apPassword_;
  server_.on(rotaPainel.c_str(), HTTP_GET, [this]() {
    responderPainelConfiguracao();
  });
  server_.on(rotaPainel.c_str(), HTTP_POST, [this]() {
    salvarPainelConfiguracao();
  });
  server_.onNotFound([this]() {
    server_.send(404, "text/plain", "Rota nao encontrada.");
  });
  server_.begin();
}

void MonitoramentoAgua::responderPainelConfiguracao() {
  server_.send(200, "text/html", montarHtmlPainel());
}

void MonitoramentoAgua::salvarPainelConfiguracao() {
  String reservatorioTexto = server_.arg("reservatorio_id");
  String ssid = server_.arg("ssid");
  String senha = server_.arg("senha");
  String ipEspTexto = server_.arg("ip_esp");
  String ipDjango = server_.arg("ip_django");
  String token = server_.arg("token");

  reservatorioTexto.trim();
  ssid.trim();
  senha.trim();
  ipEspTexto.trim();
  ipDjango.trim();
  token.trim();

  if (reservatorioTexto.length() == 0 || reservatorioTexto.toInt() <= 0) {
    server_.send(400, "text/html", montarHtmlPainel("Informe um reservatorio ID valido."));
    return;
  }
  if (ssid.length() == 0) {
    server_.send(400, "text/html", montarHtmlPainel("Informe o nome da rede AP."));
    return;
  }
  if (senha.length() < 8) {
    server_.send(400, "text/html", montarHtmlPainel("A senha da rede precisa ter ao menos 8 caracteres."));
    return;
  }
  if (ipDjango.length() == 0) {
    server_.send(400, "text/html", montarHtmlPainel("Informe o IP do servidor Django."));
    return;
  }
  if (token.length() == 0) {
    server_.send(400, "text/html", montarHtmlPainel("Informe o token de integracao do ESP."));
    return;
  }

  IPAddress novoIp;
  if (!converterIp(ipEspTexto, novoIp)) {
    server_.send(400, "text/html", montarHtmlPainel("Informe um IP valido para o ESP32."));
    return;
  }

  reservatorioId_ = reservatorioTexto.toInt();
  apSsid_ = ssid;
  apPassword_ = senha;
  apIP_ = novoIp;
  djangoHost_ = ipDjango;
  apiToken_ = token;

  salvarConfiguracaoSalva();
  server_.send(200, "text/html", montarHtmlPainel("Configuracao salva. Reiniciando o ESP32..."));
  delay(1200);
  ESP.restart();
}

String MonitoramentoAgua::montarHtmlPainel(const String& alerta) const {
  String html;
  html += "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Painel ESP32</title>";
  html += "<style>";
  html += "body{font-family:Arial,sans-serif;background:#f3f6fa;color:#123;max-width:760px;margin:0 auto;padding:24px;}";
  html += "main{background:#fff;border:1px solid #d7e0ea;border-radius:10px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.05);}";
  html += "h1{margin:0 0 8px;font-size:24px;}p{line-height:1.5;}label{display:block;margin-top:14px;font-weight:600;}";
  html += "input{width:100%;padding:10px 12px;margin-top:6px;border:1px solid #b8c6d8;border-radius:8px;box-sizing:border-box;}";
  html += "button{margin-top:20px;padding:12px 16px;border:0;border-radius:8px;background:#0f4c81;color:#fff;font-weight:700;}";
  html += ".alerta{margin:12px 0;padding:12px;border-radius:8px;background:#eaf3ff;border:1px solid #bdd6f2;}";
  html += ".meta{font-size:14px;color:#456;}";
  html += "</style></head><body><main>";
  html += "<h1>Painel de configuracao do ESP32</h1>";
  html += "<p class='meta'>Acesse este painel sempre por <strong>http://";
  html += WiFi.softAPIP().toString();
  html += "/";
  html += escaparHtml(apPassword_);
  html += "</strong>.</p>";
  if (alerta.length() > 0) {
    html += "<div class='alerta'>" + escaparHtml(alerta) + "</div>";
  }
  html += "<form method='post'>";
  html += "<label for='reservatorio_id'>Reservatorio ID</label>";
  html += "<input id='reservatorio_id' name='reservatorio_id' value='" + String(reservatorioId_) + "' required>";
  html += "<label for='token'>Token de integracao</label>";
  html += "<input id='token' name='token' value='" + escaparHtml(apiToken_) + "' required>";
  html += "<label for='ssid'>Nome da rede AP</label>";
  html += "<input id='ssid' name='ssid' value='" + escaparHtml(apSsid_) + "' required>";
  html += "<label for='senha'>Senha da rede AP e rota do painel</label>";
  html += "<input id='senha' name='senha' value='" + escaparHtml(apPassword_) + "' minlength='8' required>";
  html += "<label for='ip_esp'>IP local do ESP32</label>";
  html += "<input id='ip_esp' name='ip_esp' value='" + apIP_.toString() + "' required>";
  html += "<label for='ip_django'>IP do servidor Django</label>";
  html += "<input id='ip_django' name='ip_django' value='" + escaparHtml(djangoHost_) + "' required>";
  html += "<label for='device_id'>Device ID</label>";
  html += "<input id='device_id' value='" + escaparHtml(deviceId_) + "' readonly>";
  html += "<label for='cache_normal'>Ultimo intervalo normal recebido (ms)</label>";
  html += "<input id='cache_normal' value='" + String(intervaloEnvioNormalMs_) + "' readonly>";
  html += "<label for='cache_cal'>Ultimo intervalo de calibracao recebido (ms)</label>";
  html += "<input id='cache_cal' value='" + String(intervaloEnvioCalibracaoMs_) + "' readonly>";
  html += "<button type='submit'>Salvar no ESP32</button>";
  html += "</form></main></body></html>";
  return html;
}

String MonitoramentoAgua::escaparHtml(const String& valor) {
  String resultado = valor;
  resultado.replace("&", "&amp;");
  resultado.replace("<", "&lt;");
  resultado.replace(">", "&gt;");
  resultado.replace("\"", "&quot;");
  return resultado;
}

bool MonitoramentoAgua::converterIp(const String& texto, IPAddress& ip) {
  return ip.fromString(texto);
}

String MonitoramentoAgua::montarUrlDjangoLeituras() const {
  return String("http://") + djangoHost_ + ":" + String(config_.djangoPort) + config_.djangoLeiturasPath;
}

String MonitoramentoAgua::montarUrlDjangoConfiguracao() const {
  String url = String("http://") + djangoHost_ + ":" + String(config_.djangoPort) + config_.djangoConfiguracaoPath;
  url += "?reservatorio_id=" + String(reservatorioId_);
  return url;
}

String MonitoramentoAgua::montarUrlDjangoAmostrasCalibracao() const {
  return String("http://") + djangoHost_ + ":" + String(config_.djangoPort) + config_.djangoCalibrationSamplesPath;
}

void MonitoramentoAgua::resetarFilaEmMemoria() {
  filaInicio_ = 0;
  filaFim_ = 0;
  filaQuantidade_ = 0;
}

void MonitoramentoAgua::salvarFilaEmFlash() {
  if (!prefsQueueDisponivel_) return;

  const uint8_t* base = reinterpret_cast<const uint8_t*>(filaLeituras_);
  const size_t bytesTotais = sizeof(filaLeituras_);
  const size_t bytesA = bytesTotais / 2;
  const size_t bytesB = bytesTotais - bytesA;

  prefsQueue_.putInt(NVS_KEY_META_INI, filaInicio_);
  prefsQueue_.putInt(NVS_KEY_META_FIM, filaFim_);
  prefsQueue_.putInt(NVS_KEY_META_QTD, filaQuantidade_);
  prefsQueue_.putBytes(NVS_KEY_DADOS_A, base, bytesA);
  prefsQueue_.putBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);
}

void MonitoramentoAgua::carregarFilaDaFlash() {
  if (!prefsQueueDisponivel_) return;

  int inicio = prefsQueue_.getInt(NVS_KEY_META_INI, 0);
  int fim = prefsQueue_.getInt(NVS_KEY_META_FIM, 0);
  int quantidade = prefsQueue_.getInt(NVS_KEY_META_QTD, 0);

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
  size_t lidosA = prefsQueue_.getBytes(NVS_KEY_DADOS_A, base, bytesA);
  size_t lidosB = prefsQueue_.getBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);

  if (lidosA != bytesA || lidosB != bytesB) {
    resetarFilaEmMemoria();
    salvarFilaEmFlash();
    return;
  }

  filaInicio_ = inicio;
  filaFim_ = fim;
  filaQuantidade_ = quantidade;
}

void MonitoramentoAgua::enfileirarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs) {
  if (filaQuantidade_ >= FILA_MAX_LEITURAS) {
    filaInicio_ = (filaInicio_ + 1) % FILA_MAX_LEITURAS;
    filaQuantidade_--;
  }

  filaLeituras_[filaFim_].temperatura = temperatura;
  filaLeituras_[filaFim_].adcTds = adcTds;
  filaLeituras_[filaFim_].adcTurb = adcTurb;
  filaLeituras_[filaFim_].adcPh = adcPh;
  filaLeituras_[filaFim_].firmwareTsMs = firmwareTsMs;

  filaFim_ = (filaFim_ + 1) % FILA_MAX_LEITURAS;
  filaQuantidade_++;
  salvarFilaEmFlash();
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
  if (!configuracaoProntaParaEnvio()) return;
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
      break;
    }

    removerPrimeiraLeituraFila();
    enviados++;
  }

  if (enviados > 0) {
    salvarFilaEmFlash();
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

  return (quantidadeFaixa > 0) ? (int)(somaCentral / quantidadeFaixa) : 0;
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

  if (validas <= 0) return 0;
  ordenarLeituras(leituras, validas);
  return mediaMioloEstavel(leituras, validas);
}

int MonitoramentoAgua::lerAdcPhFiltradoRobusto(int quantidadeAmostras, int atrasoAmostraMs) {
  return lerAdcFiltradoRobusto(config_.phPin, quantidadeAmostras, atrasoAmostraMs, false);
}

bool MonitoramentoAgua::enviarLeitura(float temperatura, int adcTds, int adcTurb, int adcPh, unsigned long firmwareTsMs) {
  if (!configuracaoProntaParaEnvio()) return false;
  if (!redeDisponivel()) return false;

  HTTPClient http;
  http.setTimeout(10000);
  http.begin(montarUrlDjangoLeituras());
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", apiToken_);

  String body = "{";
  body += "\"reservatorio_id\":" + String(reservatorioId_) + ",";
  body += "\"device_id\":\"" + deviceId_ + "\",";
  body += "\"temperatura\":" + String(temperatura, 2) + ",";
  body += "\"raw\":{";
  body += "\"adc_tds\":" + String(adcTds) + ",";
  body += "\"adc_turb\":" + String(adcTurb) + ",";
  body += "\"adc_ph\":" + String(adcPh) + ",";
  body += "\"firmware_ts_ms\":" + String(firmwareTsMs) + ",";
  body += "\"firmware_now_ms\":" + String(millis()) + ",";
  body += "\"device_id\":\"" + deviceId_ + "\"";
  body += "}}";

  int code = http.POST(body);
  String resposta = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.print("Falha envio leitura: ");
    Serial.print(code);
    Serial.print(" | ");
    Serial.println(resposta);
    return false;
  }

  return true;
}

bool MonitoramentoAgua::enviarAmostraCalibracao(
  const String& sensor,
  float temperatura,
  int adcTds,
  int adcTurb,
  int adcPh,
  unsigned long firmwareTsMs
) {
  if (!configuracaoProntaParaEnvio()) return false;
  if (!redeDisponivel()) return false;

  HTTPClient http;
  http.setTimeout(10000);
  http.begin(montarUrlDjangoAmostrasCalibracao());
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", apiToken_);

  String body = "{";
  body += "\"reservatorio_id\":" + String(reservatorioId_) + ",";
  body += "\"device_id\":\"" + deviceId_ + "\",";
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
  body += "\"firmware_now_ms\":" + String(millis()) + ",";
  body += "\"device_id\":\"" + deviceId_ + "\"";
  body += "}}";

  int code = http.POST(body);
  String resposta = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.print("Falha envio calibracao: ");
    Serial.print(code);
    Serial.print(" | ");
    Serial.println(resposta);
    return false;
  }

  return true;
}

String MonitoramentoAgua::extrairCampoJsonString(const String& json, const String& chave) const {
  String marcador = "\"" + chave + "\":";
  int inicio = json.indexOf(marcador);
  if (inicio < 0) return "";

  inicio += marcador.length();
  while (
    inicio < (int)json.length() &&
    (json[inicio] == ' ' || json[inicio] == '\n' || json[inicio] == '\r' || json[inicio] == '\t')
  ) {
    inicio++;
  }

  if (inicio >= (int)json.length() || json[inicio] != '"') return "";
  inicio += 1;
  int fim = json.indexOf('"', inicio);
  if (fim < 0) return "";
  return json.substring(inicio, fim);
}

long MonitoramentoAgua::extrairCampoJsonLong(const String& json, const String& chave, long padrao) const {
  String marcador = "\"" + chave + "\":";
  int inicio = json.indexOf(marcador);
  if (inicio < 0) return padrao;

  inicio += marcador.length();
  while (
    inicio < (int)json.length() &&
    (json[inicio] == ' ' || json[inicio] == '\n' || json[inicio] == '\r' || json[inicio] == '\t')
  ) {
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

bool MonitoramentoAgua::atualizarConfiguracaoRemota() {
  if (!configuracaoProntaParaEnvio()) return false;
  if (!redeDisponivel()) return false;

  HTTPClient http;
  http.setTimeout(5000);
  http.begin(montarUrlDjangoConfiguracao());
  http.addHeader("X-API-Token", apiToken_);

  int code = http.GET();
  String resposta = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.print("Falha ao consultar configuracao remota: ");
    Serial.println(code);
    return false;
  }

  long intervaloNormal = extrairCampoJsonLong(resposta, "intervalo_normal_ms", (long)intervaloEnvioNormalMs_);
  long intervaloCalibracao = extrairCampoJsonLong(resposta, "intervalo_calibracao_ms", (long)intervaloEnvioCalibracaoMs_);
  long pollConfiguracao = extrairCampoJsonLong(resposta, "poll_configuracao_ms", (long)intervaloPollConfiguracaoMs_);

  if (intervaloNormal >= 1000L) intervaloEnvioNormalMs_ = (unsigned long)intervaloNormal;
  if (intervaloCalibracao >= 1000L) intervaloEnvioCalibracaoMs_ = (unsigned long)intervaloCalibracao;
  if (pollConfiguracao >= 1000L) intervaloPollConfiguracaoMs_ = (unsigned long)pollConfiguracao;
  salvarCacheIntervalos();

  String modo = extrairCampoJsonString(resposta, "modo");
  if (modo != "calibracao") {
    desativarModoCalibracao();
    return true;
  }

  String sensor = extrairCampoJsonString(resposta, "sensor");
  if (
    sensor != SENSOR_TEMPERATURA &&
    sensor != SENSOR_TDS &&
    sensor != SENSOR_TURBIDEZ &&
    sensor != SENSOR_PH
  ) {
    desativarModoCalibracao();
    return true;
  }

  long sessaoId = extrairCampoJsonLong(resposta, "sessao_id", 0);
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

  if (qtdAmostras <= 0) {
    qtdAmostras = config_.qtdAmostrasCalibracaoPadrao;
  }
  if (atrasoAmostraMs <= 0) {
    atrasoAmostraMs = config_.atrasoAmostraCalibracaoPadraoMs;
  }

  aplicarModoCalibracao(sensor, sessaoId, qtdAmostras, atrasoAmostraMs);
  return true;
}

void MonitoramentoAgua::desativarModoCalibracao() {
  calibracaoAtiva_ = false;
  sensorCalibracaoAtivo_ = "";
  qtdAmostrasCalibracao_ = config_.qtdAmostrasCalibracaoPadrao;
  atrasoAmostraCalibracaoMs_ = config_.atrasoAmostraCalibracaoPadraoMs;
  sessaoCalibracaoId_ = 0;
}

void MonitoramentoAgua::aplicarModoCalibracao(
  const String& sensor,
  long sessaoId,
  int qtdAmostras,
  int atrasoAmostraMs
) {
  bool mudou = (!calibracaoAtiva_) || sensorCalibracaoAtivo_ != sensor || sessaoCalibracaoId_ != sessaoId;

  calibracaoAtiva_ = true;
  sensorCalibracaoAtivo_ = sensor;
  sessaoCalibracaoId_ = sessaoId;
  qtdAmostrasCalibracao_ = qtdAmostras;
  atrasoAmostraCalibracaoMs_ = atrasoAmostraMs;

  if (mudou) {
    ultimoEnvioCalibracao_ = millis() - intervaloEnvioCalibracaoMs_;
  }
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
  enfileirarLeitura(temp, adcTDS, adcTurbidez, adcPh, firmwareTsMs);
  tentarEnviarFila(10);
}

void MonitoramentoAgua::executarCicloCalibracao() {
  float temperatura = NAN;
  int adcTds = -1;
  int adcTurb = -1;
  int adcPh = -1;

  if (sensorCalibracaoAtivo_ == SENSOR_TEMPERATURA) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) return;
  } else if (sensorCalibracaoAtivo_ == SENSOR_TDS) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) return;
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
    if (isnan(temperatura)) return;
    adcPh = lerAdcPhFiltradoRobusto(
      qtdAmostrasCalibracao_,
      atrasoAmostraCalibracaoMs_
    );
  } else {
    return;
  }

  enviarAmostraCalibracao(
    sensorCalibracaoAtivo_,
    temperatura,
    adcTds,
    adcTurb,
    adcPh,
    millis()
  );
}
