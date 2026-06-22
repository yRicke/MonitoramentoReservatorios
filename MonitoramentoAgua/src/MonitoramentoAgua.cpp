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
const char* NVS_KEY_DEVICE = "device";
const char* NVS_KEY_RESERVATORIO = "res_id";
const char* NVS_KEY_CACHE_NORMAL = "itv_norm";
const char* NVS_KEY_CACHE_CAL = "itv_cal";
const char* NVS_KEY_NORM_TDS_QTD = "n_tds_q";
const char* NVS_KEY_NORM_TDS_DLY = "n_tds_d";
const char* NVS_KEY_NORM_TRB_QTD = "n_trb_q";
const char* NVS_KEY_NORM_TRB_DLY = "n_trb_d";
const char* NVS_KEY_NORM_PH_QTD = "n_ph_q";
const char* NVS_KEY_NORM_PH_DLY = "n_ph_d";

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
    deviceId(""),
    intervaloEnvioNormalPadraoMs(60UL * 1000UL),
    intervaloEnvioCalibracaoPadraoMs(5UL * 1000UL),
    intervaloPollConfiguracaoMs(2UL * 1000UL),
    alertaSonoroLigadoPadraoMs(500UL),
    alertaSonoroDesligadoPadraoMs(500UL),
    delayLoopMs(50),
    tdsPin(34),
    turbidityPin(35),
    phPin(32),
    buzzerPin(25),
    qtdAmostrasPh(60),
    qtdAmostrasTds(60),
    qtdAmostrasTurbidez(60),
    atrasoAmostraPhPadraoMs(5),
    atrasoAmostraTdsPadraoMs(5),
    atrasoAmostraTurbidezPadraoMs(10),
    qtdAmostrasCalibracaoPadrao(80),
    atrasoAmostraCalibracaoPadraoMs(50),
    maxAmostrasFiltro(240),
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
    ultimoToggleBuzzer_(0),
    calibracaoAtiva_(false),
    alertaSonoroAtivo_(false),
    buzzerLigado_(false),
    iniciado_(false),
    prefsConfigDisponivel_(false),
    prefsQueueDisponivel_(false),
    sensorCalibracaoAtivo_(""),
    qtdAmostrasCalibracao_(0),
    atrasoAmostraCalibracaoMs_(0),
    qtdAmostrasNormalTds_(0),
    qtdAmostrasNormalTurbidez_(0),
    qtdAmostrasNormalPh_(0),
    atrasoAmostraNormalTdsMs_(0),
    atrasoAmostraNormalTurbidezMs_(0),
    atrasoAmostraNormalPhMs_(0),
    buzzerPin_(-1),
    sessaoCalibracaoId_(0),
    alertaSonoroLigadoMs_(0),
    alertaSonoroDesligadoMs_(0),
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
  deviceId_ = config_.deviceId ? String(config_.deviceId) : String("");
  apIP_ = config_.apIP;
  reservatorioId_ = config_.reservatorioId;
  intervaloEnvioNormalMs_ = config_.intervaloEnvioNormalPadraoMs;
  intervaloEnvioCalibracaoMs_ = config_.intervaloEnvioCalibracaoPadraoMs;
  intervaloPollConfiguracaoMs_ = config_.intervaloPollConfiguracaoMs;
  alertaSonoroLigadoMs_ = config_.alertaSonoroLigadoPadraoMs;
  alertaSonoroDesligadoMs_ = config_.alertaSonoroDesligadoPadraoMs;
  qtdAmostrasCalibracao_ = config_.qtdAmostrasCalibracaoPadrao;
  atrasoAmostraCalibracaoMs_ = config_.atrasoAmostraCalibracaoPadraoMs;
  qtdAmostrasNormalTds_ = config_.qtdAmostrasTds;
  qtdAmostrasNormalTurbidez_ = config_.qtdAmostrasTurbidez;
  qtdAmostrasNormalPh_ = config_.qtdAmostrasPh;
  atrasoAmostraNormalTdsMs_ = config_.atrasoAmostraTdsPadraoMs;
  atrasoAmostraNormalTurbidezMs_ = config_.atrasoAmostraTurbidezPadraoMs;
  atrasoAmostraNormalPhMs_ = config_.atrasoAmostraPhPadraoMs;
  buzzerPin_ = config_.buzzerPin;

  prefsConfigDisponivel_ = prefsConfig_.begin(NVS_NAMESPACE_CONFIG, false);
  if (!prefsConfigDisponivel_) {
    Serial.println("Falha ao abrir NVS de configuracao.");
  } else {
    carregarConfiguracaoSalva();
    carregarCacheOperacao();
  }

  prefsQueueDisponivel_ = prefsQueue_.begin(NVS_NAMESPACE_QUEUE, false);
  if (!prefsQueueDisponivel_) {
    Serial.println("Falha ao abrir NVS da fila.");
  } else {
    carregarFilaDaFlash();
  }

  garantirDeviceId();
  configurarBuzzer();
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

  atualizarBuzzer(agora);

  delay(config_.delayLoopMs);
}

void MonitoramentoAgua::carregarConfiguracaoSalva() {
  String ssidSalvo = prefsConfig_.getString(NVS_KEY_SSID, "");
  String senhaSalva = prefsConfig_.getString(NVS_KEY_PASSWORD, "");
  String ipSalvo = prefsConfig_.getString(NVS_KEY_AP_IP, "");
  String djangoSalvo = prefsConfig_.getString(NVS_KEY_DJANGO_IP, "");
  String deviceSalvo = prefsConfig_.getString(NVS_KEY_DEVICE, "");
  int reservatorioSalvo = prefsConfig_.getInt(NVS_KEY_RESERVATORIO, 0);

  if (ssidSalvo.length() > 0) apSsid_ = ssidSalvo;
  if (senhaSalva.length() >= 8) apPassword_ = senhaSalva;
  if (djangoSalvo.length() > 0) djangoHost_ = djangoSalvo;
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
  prefsConfig_.putString(NVS_KEY_DEVICE, deviceId_);
  prefsConfig_.putInt(NVS_KEY_RESERVATORIO, reservatorioId_);
}

void MonitoramentoAgua::carregarCacheOperacao() {
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

  qtdAmostrasNormalTds_ = prefsConfig_.getInt(
    NVS_KEY_NORM_TDS_QTD,
    config_.qtdAmostrasTds
  );
  qtdAmostrasNormalTurbidez_ = prefsConfig_.getInt(
    NVS_KEY_NORM_TRB_QTD,
    config_.qtdAmostrasTurbidez
  );
  qtdAmostrasNormalPh_ = prefsConfig_.getInt(
    NVS_KEY_NORM_PH_QTD,
    config_.qtdAmostrasPh
  );
  atrasoAmostraNormalTdsMs_ = prefsConfig_.getInt(
    NVS_KEY_NORM_TDS_DLY,
    config_.atrasoAmostraTdsPadraoMs
  );
  atrasoAmostraNormalTurbidezMs_ = prefsConfig_.getInt(
    NVS_KEY_NORM_TRB_DLY,
    config_.atrasoAmostraTurbidezPadraoMs
  );
  atrasoAmostraNormalPhMs_ = prefsConfig_.getInt(
    NVS_KEY_NORM_PH_DLY,
    config_.atrasoAmostraPhPadraoMs
  );

  if (qtdAmostrasNormalTds_ <= 0) qtdAmostrasNormalTds_ = config_.qtdAmostrasTds;
  if (qtdAmostrasNormalTurbidez_ <= 0) qtdAmostrasNormalTurbidez_ = config_.qtdAmostrasTurbidez;
  if (qtdAmostrasNormalPh_ <= 0) qtdAmostrasNormalPh_ = config_.qtdAmostrasPh;
  if (atrasoAmostraNormalTdsMs_ <= 0) atrasoAmostraNormalTdsMs_ = config_.atrasoAmostraTdsPadraoMs;
  if (atrasoAmostraNormalTurbidezMs_ <= 0) atrasoAmostraNormalTurbidezMs_ = config_.atrasoAmostraTurbidezPadraoMs;
  if (atrasoAmostraNormalPhMs_ <= 0) atrasoAmostraNormalPhMs_ = config_.atrasoAmostraPhPadraoMs;
}

void MonitoramentoAgua::salvarCacheOperacao() {
  if (!prefsConfigDisponivel_) return;
  prefsConfig_.putULong(NVS_KEY_CACHE_NORMAL, intervaloEnvioNormalMs_);
  prefsConfig_.putULong(NVS_KEY_CACHE_CAL, intervaloEnvioCalibracaoMs_);
  prefsConfig_.putInt(NVS_KEY_NORM_TDS_QTD, qtdAmostrasNormalTds_);
  prefsConfig_.putInt(NVS_KEY_NORM_TRB_QTD, qtdAmostrasNormalTurbidez_);
  prefsConfig_.putInt(NVS_KEY_NORM_PH_QTD, qtdAmostrasNormalPh_);
  prefsConfig_.putInt(NVS_KEY_NORM_TDS_DLY, atrasoAmostraNormalTdsMs_);
  prefsConfig_.putInt(NVS_KEY_NORM_TRB_DLY, atrasoAmostraNormalTurbidezMs_);
  prefsConfig_.putInt(NVS_KEY_NORM_PH_DLY, atrasoAmostraNormalPhMs_);
}

bool MonitoramentoAgua::configuracaoProntaParaEnvio() const {
  return reservatorioId_ > 0 && djangoHost_.length() > 0;
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

void MonitoramentoAgua::configurarBuzzer() {
  if (buzzerPin_ < 0) {
    return;
  }

  pinMode(buzzerPin_, OUTPUT_OPEN_DRAIN);
  digitalWrite(buzzerPin_, HIGH);
  buzzerLigado_ = false;
}

void MonitoramentoAgua::aplicarEstadoBuzzer(bool ligado) {
  if (buzzerPin_ < 0) {
    buzzerLigado_ = false;
    return;
  }

  pinMode(buzzerPin_, OUTPUT_OPEN_DRAIN);
  digitalWrite(buzzerPin_, ligado ? LOW : HIGH);
  buzzerLigado_ = ligado;
}

void MonitoramentoAgua::atualizarBuzzer(unsigned long agora) {
  if (!alertaSonoroAtivo_) {
    if (buzzerLigado_) {
      aplicarEstadoBuzzer(false);
    }
    return;
  }

  unsigned long duracaoAtualMs = buzzerLigado_ ? alertaSonoroLigadoMs_ : alertaSonoroDesligadoMs_;
  if (duracaoAtualMs < 50UL) {
    duracaoAtualMs = 50UL;
  }

  if (agora - ultimoToggleBuzzer_ < duracaoAtualMs) {
    return;
  }

  ultimoToggleBuzzer_ = agora;
  aplicarEstadoBuzzer(!buzzerLigado_);
}

void MonitoramentoAgua::atualizarAlertaSonoroRemoto(
  bool ativo,
  unsigned long ligadoMs,
  unsigned long desligadoMs
) {
  if (ligadoMs >= 50UL) {
    alertaSonoroLigadoMs_ = ligadoMs;
  }
  if (desligadoMs >= 50UL) {
    alertaSonoroDesligadoMs_ = desligadoMs;
  }

  if (!ativo) {
    alertaSonoroAtivo_ = false;
    aplicarEstadoBuzzer(false);
    return;
  }

  bool reiniciarCiclo = !alertaSonoroAtivo_;
  alertaSonoroAtivo_ = true;
  if (!reiniciarCiclo) {
    return;
  }

  ultimoToggleBuzzer_ = millis();
  aplicarEstadoBuzzer(true);
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
  String acao = server_.arg("painel_acao");
  acao.trim();

  if (acao == "reiniciar") {
    reiniciarPeloPainel();
    return;
  }

  if (acao == "restaurar_padrao") {
    restaurarPadraoPeloPainel();
    return;
  }

  String reservatorioTexto = server_.arg("reservatorio_id");
  String ssid = server_.arg("ssid");
  String senha = server_.arg("senha");
  String ipEspTexto = server_.arg("ip_esp");
  String ipDjango = server_.arg("ip_django");

  reservatorioTexto.trim();
  ssid.trim();
  senha.trim();
  ipEspTexto.trim();
  ipDjango.trim();

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

  salvarConfiguracaoSalva();
  server_.send(200, "text/html", montarHtmlPainel("Configuracao salva. Reiniciando o ESP32..."));
  delay(1200);
  ESP.restart();
}

void MonitoramentoAgua::reiniciarPeloPainel() {
  server_.send(200, "text/html", montarHtmlPainel("Reinicio solicitado. O ESP32 sera reiniciado em instantes."));
  delay(1200);
  ESP.restart();
}

void MonitoramentoAgua::restaurarPadraoPeloPainel() {
  if (prefsConfigDisponivel_) {
    prefsConfig_.clear();
  }
  if (prefsQueueDisponivel_) {
    prefsQueue_.clear();
  }

  resetarFilaEmMemoria();
  server_.send(
    200,
    "text/html",
    montarHtmlPainel("Configuracao local apagada. O ESP32 vai voltar ao padrao de fabrica e reiniciar.")
  );
  delay(1200);
  ESP.restart();
}

String MonitoramentoAgua::montarHtmlPainel(const String& alerta) const {
  String html;
  html += "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Painel ESP32</title>";
  html += "<style>";
  html += "body{font-family:Arial,sans-serif;background:linear-gradient(180deg,#eff6ff 0%,#f8fafc 100%);color:#17324d;max-width:900px;margin:0 auto;padding:24px;}";
  html += "main{background:#fff;border:1px solid #d7e0ea;border-radius:20px;padding:28px;box-shadow:0 18px 50px rgba(15,76,129,.08);}";
  html += "h1{margin:0 0 8px;font-size:30px;line-height:1.1;}p{line-height:1.6;margin:0;}";
  html += ".intro{display:grid;gap:10px;margin-bottom:22px;}";
  html += ".meta{font-size:14px;color:#4f657d;}";
  html += ".alerta{margin:16px 0;padding:14px 16px;border-radius:14px;background:#eaf3ff;border:1px solid #bdd6f2;color:#163554;font-weight:600;}";
  html += ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;}";
  html += ".card{border:1px solid #d9e2ec;border-radius:16px;padding:18px;background:#fbfdff;display:grid;gap:14px;}";
  html += ".card h2{margin:0;font-size:18px;}";
  html += ".field{display:grid;gap:8px;}";
  html += ".field-head{display:flex;justify-content:space-between;gap:12px;align-items:center;}";
  html += "label{font-weight:700;color:#294662;}";
  html += ".pill{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}";
  html += ".pill-editavel{background:#e9f7ef;color:#1d6b45;border:1px solid #bfe0cb;}";
  html += ".pill-info{background:#eef2f7;color:#4a6076;border:1px solid #d4dde7;}";
  html += "input{width:100%;padding:12px 14px;border:1px solid #b8c6d8;border-radius:12px;box-sizing:border-box;background:#fff;color:#17324d;font-size:15px;}";
  html += "input:focus{outline:none;border-color:#0f4c81;box-shadow:0 0 0 4px rgba(15,76,129,.12);}";
  html += "input[readonly]{background:linear-gradient(180deg,#f8fafc 0%,#eef4f8 100%);border-style:dashed;border-color:#c5d2df;color:#53687d;font-weight:700;box-shadow:inset 0 1px 0 rgba(255,255,255,.8);}";
  html += ".hint{font-size:12px;color:#5e748b;}";
  html += ".actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;}";
  html += "button{padding:13px 16px;border:0;border-radius:12px;color:#fff;font-weight:700;font-size:14px;cursor:pointer;transition:transform .15s ease,box-shadow .15s ease;}";
  html += "button:hover{transform:translateY(-1px);box-shadow:0 10px 18px rgba(15,76,129,.12);}";
  html += ".btn-primary{background:#0f4c81;}";
  html += ".btn-secondary{background:#3d5f7a;}";
  html += ".btn-danger{background:#a33a3a;}";
  html += ".action-note{font-size:13px;color:#5e748b;}";
  html += "@media (max-width:640px){body{padding:16px;}main{padding:20px;}h1{font-size:26px;}}";
  html += "</style></head><body><main>";
  html += "<section class='intro'>";
  html += "<h1>Painel de configuracao do ESP32</h1>";
  html += "<p class='meta'>Acesse este painel sempre por <strong>http://";
  html += WiFi.softAPIP().toString();
  html += "/";
  html += escaparHtml(apPassword_);
  html += "</strong>.</p>";
  html += "<p class='meta'>Os campos com selo <strong>somente leitura</strong> exibem o estado atual do modulo e nao podem ser editados aqui.</p>";
  html += "</section>";
  if (alerta.length() > 0) {
    html += "<div class='alerta'>" + escaparHtml(alerta) + "</div>";
  }
  html += "<div class='grid'>";
  html += "<section class='card'>";
  html += "<h2>Configuracoes editaveis</h2>";
  html += "<form method='post'>";
  html += "<div class='field'><div class='field-head'><label for='reservatorio_id'>Reservatorio ID</label><span class='pill pill-editavel'>Editavel</span></div>";
  html += "<input id='reservatorio_id' name='reservatorio_id' value='" + String(reservatorioId_) + "' required></div>";
  html += "<div class='field'><div class='field-head'><label for='ssid'>Nome da rede AP</label><span class='pill pill-editavel'>Editavel</span></div>";
  html += "<input id='ssid' name='ssid' value='" + escaparHtml(apSsid_) + "' required></div>";
  html += "<div class='field'><div class='field-head'><label for='senha'>Senha da rede AP e rota do painel</label><span class='pill pill-editavel'>Editavel</span></div>";
  html += "<input id='senha' name='senha' value='" + escaparHtml(apPassword_) + "' minlength='8' required></div>";
  html += "<div class='field'><div class='field-head'><label for='ip_esp'>IP local do ESP32</label><span class='pill pill-editavel'>Editavel</span></div>";
  html += "<input id='ip_esp' name='ip_esp' value='" + apIP_.toString() + "' required></div>";
  html += "<div class='field'><div class='field-head'><label for='ip_django'>IP do servidor Django</label><span class='pill pill-editavel'>Editavel</span></div>";
  html += "<input id='ip_django' name='ip_django' value='" + escaparHtml(djangoHost_) + "' required></div>";
  html += "<button class='btn-primary' type='submit' name='painel_acao' value='salvar'>Salvar no ESP32</button>";
  html += "</form>";
  html += "</section>";
  html += "<section class='card'>";
  html += "<h2>Informacoes do modulo</h2>";
  html += "<div class='field'><div class='field-head'><label for='device_id'>Device ID</label><span class='pill pill-info'>Somente leitura</span></div>";
  html += "<input id='device_id' value='" + escaparHtml(deviceId_) + "' readonly><p class='hint'>Identificador fixo do hardware usado nas integracoes.</p></div>";
  html += "<div class='field'><div class='field-head'><label for='cache_normal'>Ultimo intervalo normal recebido (ms)</label><span class='pill pill-info'>Somente leitura</span></div>";
  html += "<input id='cache_normal' value='" + String(intervaloEnvioNormalMs_) + "' readonly><p class='hint'>Valor enviado pelo servidor para o ciclo normal de leituras.</p></div>";
  html += "<div class='field'><div class='field-head'><label for='cache_cal'>Ultimo intervalo de calibracao recebido (ms)</label><span class='pill pill-info'>Somente leitura</span></div>";
  html += "<input id='cache_cal' value='" + String(intervaloEnvioCalibracaoMs_) + "' readonly><p class='hint'>Usado quando uma sessao de calibracao esta ativa.</p></div>";
  html += "<div class='field'><div class='field-head'><label for='buzzer_pin'>GPIO do buzzer</label><span class='pill pill-info'>Somente leitura</span></div>";
  html += "<input id='buzzer_pin' value='" + String(buzzerPin_) + "' readonly></div>";
  html += "<div class='field'><div class='field-head'><label for='buzzer_cadencia'>Cadencia do alerta sonoro (ms)</label><span class='pill pill-info'>Somente leitura</span></div>";
  html += "<input id='buzzer_cadencia' value='" + String(alertaSonoroLigadoMs_) + " ligado / " + String(alertaSonoroDesligadoMs_) + " desligado' readonly></div>";
  html += "</section>";
  html += "</div>";
  html += "<section class='card' style='margin-top:16px;'>";
  html += "<h2>Acoes rapidas</h2>";
  html += "<p class='action-note'>Use reinicio para aplicar o estado atual do modulo. Restaurar padrao apaga a configuracao local e volta ao estado inicial do firmware.</p>";
  html += "<div class='actions'>";
  html += "<form method='post'><button class='btn-secondary' type='submit' name='painel_acao' value='reiniciar'>Reiniciar ESP32</button></form>";
  html += "<form method='post' onsubmit=\"return confirm('Restaurar o ESP32 ao padrao? Esta acao apaga a configuracao local salva.');\">";
  html += "<button class='btn-danger' type='submit' name='painel_acao' value='restaurar_padrao'>Restaurar padrao</button></form>";
  html += "</div>";
  html += "</section>";
  html += "</main></body></html>";
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

bool MonitoramentoAgua::extrairCampoJsonBool(const String& json, const String& chave, bool padrao) const {
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
  valor.toLowerCase();

  if (valor == "true" || valor == "1") return true;
  if (valor == "false" || valor == "0") return false;
  return padrao;
}

bool MonitoramentoAgua::atualizarConfiguracaoRemota() {
  if (!configuracaoProntaParaEnvio()) return false;
  if (!redeDisponivel()) return false;

  HTTPClient http;
  http.setTimeout(5000);
  http.begin(montarUrlDjangoConfiguracao());

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
  long normalQtdTds = extrairCampoJsonLong(
    resposta,
    "normal_qtd_amostras_tds",
    (long)qtdAmostrasNormalTds_
  );
  long normalAtrasoTdsMs = extrairCampoJsonLong(
    resposta,
    "normal_atraso_amostra_tds_ms",
    (long)atrasoAmostraNormalTdsMs_
  );
  long normalQtdTurbidez = extrairCampoJsonLong(
    resposta,
    "normal_qtd_amostras_turbidez",
    (long)qtdAmostrasNormalTurbidez_
  );
  long normalAtrasoTurbidezMs = extrairCampoJsonLong(
    resposta,
    "normal_atraso_amostra_turbidez_ms",
    (long)atrasoAmostraNormalTurbidezMs_
  );
  long normalQtdPh = extrairCampoJsonLong(
    resposta,
    "normal_qtd_amostras_ph",
    (long)qtdAmostrasNormalPh_
  );
  long normalAtrasoPhMs = extrairCampoJsonLong(
    resposta,
    "normal_atraso_amostra_ph_ms",
    (long)atrasoAmostraNormalPhMs_
  );
  bool alertaSonoroAtivo = extrairCampoJsonBool(resposta, "alerta_sonoro_ativo", false);
  long alertaSonoroLigadoMs = extrairCampoJsonLong(
    resposta,
    "alerta_sonoro_intervalo_ligado_ms",
    (long)alertaSonoroLigadoMs_
  );
  long alertaSonoroDesligadoMs = extrairCampoJsonLong(
    resposta,
    "alerta_sonoro_intervalo_desligado_ms",
    (long)alertaSonoroDesligadoMs_
  );

  if (intervaloNormal >= 1000L) intervaloEnvioNormalMs_ = (unsigned long)intervaloNormal;
  if (intervaloCalibracao >= 1000L) intervaloEnvioCalibracaoMs_ = (unsigned long)intervaloCalibracao;
  if (pollConfiguracao >= 1000L) intervaloPollConfiguracaoMs_ = (unsigned long)pollConfiguracao;
  if (normalQtdTds > 0L) qtdAmostrasNormalTds_ = (int)normalQtdTds;
  if (normalAtrasoTdsMs > 0L) atrasoAmostraNormalTdsMs_ = (int)normalAtrasoTdsMs;
  if (normalQtdTurbidez > 0L) qtdAmostrasNormalTurbidez_ = (int)normalQtdTurbidez;
  if (normalAtrasoTurbidezMs > 0L) atrasoAmostraNormalTurbidezMs_ = (int)normalAtrasoTurbidezMs;
  if (normalQtdPh > 0L) qtdAmostrasNormalPh_ = (int)normalQtdPh;
  if (normalAtrasoPhMs > 0L) atrasoAmostraNormalPhMs_ = (int)normalAtrasoPhMs;
  atualizarAlertaSonoroRemoto(
    alertaSonoroAtivo,
    alertaSonoroLigadoMs >= 50L ? (unsigned long)alertaSonoroLigadoMs : alertaSonoroLigadoMs_,
    alertaSonoroDesligadoMs >= 50L ? (unsigned long)alertaSonoroDesligadoMs : alertaSonoroDesligadoMs_
  );
  salvarCacheOperacao();

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
    qtdAmostrasNormalTurbidez_,
    atrasoAmostraNormalTurbidezMs_,
    false
  );
  int adcTDS = lerAdcFiltradoRobusto(
    config_.tdsPin,
    qtdAmostrasNormalTds_,
    atrasoAmostraNormalTdsMs_,
    true
  );
  int adcPh = lerAdcPhFiltradoRobusto(qtdAmostrasNormalPh_, atrasoAmostraNormalPhMs_);

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
