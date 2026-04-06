#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Preferences.h>
#include <math.h>

// ===== REDE PROPRIA DO ESP (AP) =====
const char* apSsid = "MONITOR-ESP32";
const char* apPassword = "12345678"; // minimo 8 chars

IPAddress apIP(192, 168, 50, 1);
IPAddress apGateway(192, 168, 50, 1);
IPAddress apSubnet(255, 255, 255, 0);

// ===== SERVIDOR DJANGO (MAQUINA CONECTADA AO AP DO ESP) =====
const char* djangoHost = "192.168.50.2"; // IP da sua maquina nessa rede
const int djangoPort = 8000;
const char* djangoPath = "/api/esp32/leituras/";
const char* djangoCalibrationCommandPath = "/api/esp32/calibracao/comando/";
const char* djangoCalibrationSamplesPath = "/api/esp32/calibracao/amostras/";
const char* apiToken = "Oqc9zeW5fZjRFvxXZhaJtdVAD3sRrhy2G0a7IWegMR3ZOR3dsAxQ142qRut3fWtA";
const int reservatorioId = 8;

// ===== PONTO =====
const char* pontoTipo = "depois_tratamento"; // "antes_tratamento" ou "depois_tratamento"

// ===== INTERVALO =====
const unsigned long INTERVALO_ENVIO_MS = 1UL * 1000UL * 60UL;
const unsigned long INTERVALO_POLL_CALIBRACAO_MS = 2000;
const unsigned long INTERVALO_ENVIO_CALIBRACAO_PADRAO_MS = 5000;
const unsigned long DELAY_LOOP_MS = 50;

// ===== PINOS =====
#define DS18B20_PIN 4
#define TDS_PIN 34
#define TURBIDITY_PIN 35
#define PH_PIN 32

// ===== AMOSTRAGEM =====
const int QTD_AMOSTRAS_PH = 60;
const int QTD_AMOSTRAS_TDS = 60;
const int QTD_AMOSTRAS_TURBIDEZ = 60;
const int QTD_AMOSTRAS_CALIBRACAO_PADRAO = 80;
const int ATRASO_AMOSTRA_CALIBRACAO_PADRAO_MS = 50;
const int MAX_AMOSTRAS_FILTRO = 80;

const char* SENSOR_TEMPERATURA = "temperatura";
const char* SENSOR_TDS = "tds";
const char* SENSOR_TURBIDEZ = "turbidez";
const char* SENSOR_PH = "ph";

OneWire oneWire(DS18B20_PIN);
DallasTemperature sensors(&oneWire);

unsigned long ultimoEnvio = 0;
unsigned long ultimoFlushFila = 0;
unsigned long ultimoPollCalibracao = 0;
unsigned long ultimoEnvioCalibracao = 0;

const unsigned long INTERVALO_FLUSH_FILA_MS = 2000;
const int FILA_MAX_LEITURAS = 180;

bool calibracaoAtiva = false;
String sensorCalibracaoAtivo = "";
unsigned long intervaloEnvioCalibracaoMs = INTERVALO_ENVIO_CALIBRACAO_PADRAO_MS;
int qtdAmostrasCalibracao = QTD_AMOSTRAS_CALIBRACAO_PADRAO;
int atrasoAmostraCalibracaoMs = ATRASO_AMOSTRA_CALIBRACAO_PADRAO_MS;
long sessaoCalibracaoId = 0;

struct LeituraPendente {
  float temperatura;
  int adcTds;
  int adcTurb;
  int adcPh;
  unsigned long firmwareTsMs;
};

LeituraPendente filaLeituras[FILA_MAX_LEITURAS];
int filaInicio = 0;
int filaFim = 0;
int filaQuantidade = 0;
Preferences prefs;

const char* NVS_NAMESPACE = "fila_esp32";
const char* NVS_KEY_META_INI = "meta_ini";
const char* NVS_KEY_META_FIM = "meta_fim";
const char* NVS_KEY_META_QTD = "meta_qtd";
const char* NVS_KEY_DADOS_A = "dados_a";
const char* NVS_KEY_DADOS_B = "dados_b";

bool nvsDisponivel = false;

String montarUrlDjangoLeituras() {
  return String("http://") + djangoHost + ":" + String(djangoPort) + djangoPath;
}

String montarUrlDjangoComandoCalibracao() {
  String url = String("http://") + djangoHost + ":" + String(djangoPort) + djangoCalibrationCommandPath;
  url += "?reservatorio_id=" + String(reservatorioId);
  url += "&ponto_tipo=" + String(pontoTipo);
  return url;
}

String montarUrlDjangoAmostrasCalibracao() {
  return String("http://") + djangoHost + ":" + String(djangoPort) + djangoCalibrationSamplesPath;
}

void resetarFilaEmMemoria() {
  filaInicio = 0;
  filaFim = 0;
  filaQuantidade = 0;
}

void salvarFilaEmFlash() {
  if (!nvsDisponivel) return;

  const uint8_t* base = reinterpret_cast<const uint8_t*>(filaLeituras);
  const size_t bytesTotais = sizeof(filaLeituras);
  const size_t bytesA = bytesTotais / 2;
  const size_t bytesB = bytesTotais - bytesA;

  prefs.putInt(NVS_KEY_META_INI, filaInicio);
  prefs.putInt(NVS_KEY_META_FIM, filaFim);
  prefs.putInt(NVS_KEY_META_QTD, filaQuantidade);
  prefs.putBytes(NVS_KEY_DADOS_A, base, bytesA);
  prefs.putBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);
}

void carregarFilaDaFlash() {
  if (!nvsDisponivel) return;

  int inicio = prefs.getInt(NVS_KEY_META_INI, 0);
  int fim = prefs.getInt(NVS_KEY_META_FIM, 0);
  int quantidade = prefs.getInt(NVS_KEY_META_QTD, 0);

  if (
    inicio < 0 || inicio >= FILA_MAX_LEITURAS ||
    fim < 0 || fim >= FILA_MAX_LEITURAS ||
    quantidade < 0 || quantidade > FILA_MAX_LEITURAS
  ) {
    resetarFilaEmMemoria();
    salvarFilaEmFlash();
    return;
  }

  const size_t bytesTotais = sizeof(filaLeituras);
  const size_t bytesA = bytesTotais / 2;
  const size_t bytesB = bytesTotais - bytesA;

  uint8_t* base = reinterpret_cast<uint8_t*>(filaLeituras);
  size_t lidosA = prefs.getBytes(NVS_KEY_DADOS_A, base, bytesA);
  size_t lidosB = prefs.getBytes(NVS_KEY_DADOS_B, base + bytesA, bytesB);

  if (lidosA != bytesA || lidosB != bytesB) {
    resetarFilaEmMemoria();
    salvarFilaEmFlash();
    return;
  }

  filaInicio = inicio;
  filaFim = fim;
  filaQuantidade = quantidade;

  if (filaQuantidade > 0) {
    Serial.print("Fila restaurada da flash. Pendentes: ");
    Serial.println(filaQuantidade);
  }
}

void iniciarRedePropria() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apGateway, apSubnet);

  bool ok = WiFi.softAP(apSsid, apPassword);
  if (!ok) {
    Serial.println("Falha ao subir AP do ESP32.");
    return;
  }

  Serial.println("AP iniciado.");
  Serial.print("SSID: ");
  Serial.println(apSsid);
  Serial.print("IP AP: ");
  Serial.println(WiFi.softAPIP());
}

float lerTemperatura() {
  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);
  if (temp == DEVICE_DISCONNECTED_C) return NAN;
  return temp;
}

void ordenarLeituras(int* leituras, int total) {
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

int mediaMioloEstavel(int* leiturasOrdenadas, int total) {
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

int lerAdcFiltradoRobusto(
  int pino,
  int totalAmostras,
  int atrasoPorAmostraMs,
  bool ignorarZeros = false
) {
  if (totalAmostras <= 0) return 0;

  int alvoAmostras = totalAmostras;
  if (alvoAmostras > MAX_AMOSTRAS_FILTRO) {
    alvoAmostras = MAX_AMOSTRAS_FILTRO;
  }

  int leituras[MAX_AMOSTRAS_FILTRO];
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

int lerAdcPhFiltradoRobusto(int quantidadeAmostras, int atrasoAmostraMs) {
  return lerAdcFiltradoRobusto(PH_PIN, quantidadeAmostras, atrasoAmostraMs, false);
}

bool enviarLeitura(
  float temperatura,
  int adcTds,
  int adcTurb,
  int adcPh,
  unsigned long firmwareTsMs
) {
  if (WiFi.softAPgetStationNum() <= 0) {
    Serial.println("Sem cliente conectado no AP. Nao enviando.");
    return false;
  }

  HTTPClient http;
  http.setTimeout(10000);

  String url = montarUrlDjangoLeituras();
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", apiToken);

  String body = "{";
  body += "\"reservatorio_id\":" + String(reservatorioId) + ",";
  body += "\"ponto_tipo\":\"" + String(pontoTipo) + "\",";
  body += "\"temperatura\":" + String(temperatura, 2) + ",";
  body += "\"raw\":{";
  body += "\"adc_tds\":" + String(adcTds) + ",";
  body += "\"adc_turb\":" + String(adcTurb) + ",";
  body += "\"adc_ph\":" + String(adcPh) + ",";
  body += "\"firmware_ts_ms\":" + String(firmwareTsMs);
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

void enfileirarLeitura(
  float temperatura,
  int adcTds,
  int adcTurb,
  int adcPh,
  unsigned long firmwareTsMs
) {
  if (filaQuantidade >= FILA_MAX_LEITURAS) {
    filaInicio = (filaInicio + 1) % FILA_MAX_LEITURAS;
    filaQuantidade--;
    Serial.println("Fila cheia: leitura mais antiga descartada.");
  }

  filaLeituras[filaFim].temperatura = temperatura;
  filaLeituras[filaFim].adcTds = adcTds;
  filaLeituras[filaFim].adcTurb = adcTurb;
  filaLeituras[filaFim].adcPh = adcPh;
  filaLeituras[filaFim].firmwareTsMs = firmwareTsMs;

  filaFim = (filaFim + 1) % FILA_MAX_LEITURAS;
  filaQuantidade++;
  salvarFilaEmFlash();

  Serial.print("Fila pendente: ");
  Serial.println(filaQuantidade);
}

bool obterPrimeiraLeituraFila(LeituraPendente &leitura) {
  if (filaQuantidade <= 0) return false;
  leitura = filaLeituras[filaInicio];
  return true;
}

void removerPrimeiraLeituraFila() {
  if (filaQuantidade <= 0) return;
  filaInicio = (filaInicio + 1) % FILA_MAX_LEITURAS;
  filaQuantidade--;
}

void tentarEnviarFila(int limitePorCiclo) {
  if (filaQuantidade <= 0) return;
  if (WiFi.softAPgetStationNum() <= 0) return;

  int enviados = 0;
  while (filaQuantidade > 0 && enviados < limitePorCiclo) {
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
    Serial.println(filaQuantidade);
  }
}

String extrairCampoJsonString(const String& json, const String& chave) {
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

long extrairCampoJsonLong(const String& json, const String& chave, long padrao) {
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

void desativarModoCalibracao() {
  if (calibracaoAtiva) {
    Serial.println("Modo calibracao encerrado. Voltando para o fluxo normal.");
  }
  calibracaoAtiva = false;
  sensorCalibracaoAtivo = "";
  intervaloEnvioCalibracaoMs = INTERVALO_ENVIO_CALIBRACAO_PADRAO_MS;
  qtdAmostrasCalibracao = QTD_AMOSTRAS_CALIBRACAO_PADRAO;
  atrasoAmostraCalibracaoMs = ATRASO_AMOSTRA_CALIBRACAO_PADRAO_MS;
  sessaoCalibracaoId = 0;
}

void aplicarModoCalibracao(
  const String& sensor,
  long sessaoId,
  unsigned long intervaloEnvioMs,
  int qtdAmostras,
  int atrasoAmostraMs
) {
  bool mudou = (!calibracaoAtiva) || sensorCalibracaoAtivo != sensor || sessaoCalibracaoId != sessaoId;

  calibracaoAtiva = true;
  sensorCalibracaoAtivo = sensor;
  sessaoCalibracaoId = sessaoId;
  intervaloEnvioCalibracaoMs = intervaloEnvioMs;
  qtdAmostrasCalibracao = qtdAmostras;
  atrasoAmostraCalibracaoMs = atrasoAmostraMs;

  if (mudou) {
    ultimoEnvioCalibracao = millis() - intervaloEnvioCalibracaoMs;
    Serial.print("Modo calibracao ativo. Sensor: ");
    Serial.print(sensorCalibracaoAtivo);
    Serial.print(" | sessao ");
    Serial.println(sessaoCalibracaoId);
  }
}

void atualizarModoCalibracao() {
  if (WiFi.softAPgetStationNum() <= 0) {
    return;
  }

  HTTPClient http;
  http.setTimeout(5000);
  String url = montarUrlDjangoComandoCalibracao();
  http.begin(url);
  http.addHeader("X-API-Token", apiToken);

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
    INTERVALO_ENVIO_CALIBRACAO_PADRAO_MS
  );
  int qtdAmostras = (int)extrairCampoJsonLong(
    resposta,
    "qtd_amostras",
    QTD_AMOSTRAS_CALIBRACAO_PADRAO
  );
  int atrasoAmostraMs = (int)extrairCampoJsonLong(
    resposta,
    "atraso_amostra_ms",
    ATRASO_AMOSTRA_CALIBRACAO_PADRAO_MS
  );

  if (intervaloEnvioMs < 1000) {
    intervaloEnvioMs = INTERVALO_ENVIO_CALIBRACAO_PADRAO_MS;
  }
  if (qtdAmostras <= 0) {
    qtdAmostras = QTD_AMOSTRAS_CALIBRACAO_PADRAO;
  }
  if (atrasoAmostraMs <= 0) {
    atrasoAmostraMs = ATRASO_AMOSTRA_CALIBRACAO_PADRAO_MS;
  }

  aplicarModoCalibracao(
    sensor,
    sessaoId,
    intervaloEnvioMs,
    qtdAmostras,
    atrasoAmostraMs
  );
}

bool enviarAmostraCalibracao(
  const String& sensor,
  float temperatura,
  int adcTds,
  int adcTurb,
  int adcPh,
  unsigned long firmwareTsMs
) {
  if (WiFi.softAPgetStationNum() <= 0) {
    Serial.println("Sem cliente conectado no AP. Nao enviando amostra de calibracao.");
    return false;
  }

  HTTPClient http;
  http.setTimeout(10000);

  String url = montarUrlDjangoAmostrasCalibracao();
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Token", apiToken);

  String body = "{";
  body += "\"reservatorio_id\":" + String(reservatorioId) + ",";
  body += "\"ponto_tipo\":\"" + String(pontoTipo) + "\",";
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
  body += "\"firmware_ts_ms\":" + String(firmwareTsMs);
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

void executarCicloLeituraNormal() {
  float temp = lerTemperatura();
  if (isnan(temp)) {
    Serial.println("Falha ao ler temperatura.");
    return;
  }

  int adcTurbidez = lerAdcFiltradoRobusto(
    TURBIDITY_PIN,
    QTD_AMOSTRAS_TURBIDEZ,
    10,
    false
  );
  int adcTDS = lerAdcFiltradoRobusto(
    TDS_PIN,
    QTD_AMOSTRAS_TDS,
    5,
    true
  );
  int adcPh = lerAdcPhFiltradoRobusto(QTD_AMOSTRAS_PH, 5);

  unsigned long firmwareTsMs = millis();

  Serial.print("Ponto: ");
  Serial.print(pontoTipo);
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

void executarCicloCalibracao() {
  float temperatura = NAN;
  int adcTds = -1;
  int adcTurb = -1;
  int adcPh = -1;

  if (sensorCalibracaoAtivo == SENSOR_TEMPERATURA) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao.");
      return;
    }
  } else if (sensorCalibracaoAtivo == SENSOR_TDS) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao de TDS.");
      return;
    }
    adcTds = lerAdcFiltradoRobusto(
      TDS_PIN,
      qtdAmostrasCalibracao,
      atrasoAmostraCalibracaoMs,
      true
    );
  } else if (sensorCalibracaoAtivo == SENSOR_TURBIDEZ) {
    adcTurb = lerAdcFiltradoRobusto(
      TURBIDITY_PIN,
      qtdAmostrasCalibracao,
      atrasoAmostraCalibracaoMs,
      false
    );
  } else if (sensorCalibracaoAtivo == SENSOR_PH) {
    temperatura = lerTemperatura();
    if (isnan(temperatura)) {
      Serial.println("Falha ao ler temperatura para calibracao de pH.");
      return;
    }
    adcPh = lerAdcPhFiltradoRobusto(
      qtdAmostrasCalibracao,
      atrasoAmostraCalibracaoMs
    );
  } else {
    return;
  }

  unsigned long firmwareTsMs = millis();
  Serial.print("Calibracao | sensor: ");
  Serial.print(sensorCalibracaoAtivo);
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
    sensorCalibracaoAtivo,
    temperatura,
    adcTds,
    adcTurb,
    adcPh,
    firmwareTsMs
  );
}

void setup() {
  Serial.begin(115200);
  analogSetAttenuation(ADC_11db);
  sensors.begin();

  nvsDisponivel = prefs.begin(NVS_NAMESPACE, false);
  if (!nvsDisponivel) {
    Serial.println("Falha ao iniciar NVS para fila offline.");
  } else {
    carregarFilaDaFlash();
  }

  iniciarRedePropria();
  ultimoEnvio = millis() - INTERVALO_ENVIO_MS;
  ultimoPollCalibracao = millis() - INTERVALO_POLL_CALIBRACAO_MS;
}

void loop() {
  unsigned long agora = millis();

  if (agora - ultimoFlushFila >= INTERVALO_FLUSH_FILA_MS) {
    ultimoFlushFila = agora;
    tentarEnviarFila(3);
  }

  if (agora - ultimoPollCalibracao >= INTERVALO_POLL_CALIBRACAO_MS) {
    ultimoPollCalibracao = agora;
    atualizarModoCalibracao();
  }

  if (calibracaoAtiva) {
    if (agora - ultimoEnvioCalibracao >= intervaloEnvioCalibracaoMs) {
      ultimoEnvioCalibracao = agora;
      executarCicloCalibracao();
    }
  } else if (agora - ultimoEnvio >= INTERVALO_ENVIO_MS) {
    ultimoEnvio = agora;
    executarCicloLeituraNormal();
  }

  delay(DELAY_LOOP_MS);
}
