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
const char* apiToken = "Oqc9zeW5fZjRFvxXZhaJtdVAD3sRrhy2G0a7IWegMR3ZOR3dsAxQ142qRut3fWtA";
const int reservatorioId = 8;

// ===== PONTO =====
const char* pontoTipo = "depois_tratamento"; // "antes_tratamento" ou "depois_tratamento"

// ===== INTERVALO =====
const unsigned long INTERVALO_ENVIO_MS = 1 * 1000 * 60;

// ===== PINOS =====
#define DS18B20_PIN 4
#define TDS_PIN 34
#define TURBIDITY_PIN 35
#define PH_PIN 32

// ===== AMOSTRAGEM pH (RAW) =====
const int QTD_AMOSTRAS_PH = 60;

OneWire oneWire(DS18B20_PIN);
DallasTemperature sensors(&oneWire);

unsigned long ultimoEnvio = 0;
unsigned long ultimoFlushFila = 0;

const unsigned long INTERVALO_FLUSH_FILA_MS = 2000;
const int FILA_MAX_LEITURAS = 180;

struct SinalAnalogico {
  int adc;
};

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

String montarUrlDjango() {
  return String("http://") + djangoHost + ":" + String(djangoPort) + djangoPath;
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

SinalAnalogico lerSinalAnalogicoMedio(
  int pino,
  int totalAmostras,
  int atrasoPorAmostraMs,
  bool ignorarZeros = false
) {
  long soma = 0;
  int cont = 0;

  for (int i = 0; i < totalAmostras; i++) {
    int leitura = analogRead(pino);
    if (!ignorarZeros || leitura > 0) {
      soma += leitura;
      cont += 1;
    }
    delay(atrasoPorAmostraMs);
  }

  int adcMedio = (cont > 0) ? (soma / cont) : 0;
  return {adcMedio};
}

int lerAdcPhFiltradoRobusto() {
  int leituras[QTD_AMOSTRAS_PH];

  for (int i = 0; i < QTD_AMOSTRAS_PH; i++) {
    leituras[i] = analogRead(PH_PIN);
    delay(5);
  }

  for (int i = 0; i < QTD_AMOSTRAS_PH - 1; i++) {
    for (int j = i + 1; j < QTD_AMOSTRAS_PH; j++) {
      if (leituras[i] > leituras[j]) {
        int tmp = leituras[i];
        leituras[i] = leituras[j];
        leituras[j] = tmp;
      }
    }
  }

  const int inicioFaixa = QTD_AMOSTRAS_PH / 3;
  const int fimFaixa = QTD_AMOSTRAS_PH - inicioFaixa;
  const int quantidadeFaixa = fimFaixa - inicioFaixa;

  long somaCentral = 0;
  for (int i = inicioFaixa; i < fimFaixa; i++) {
    somaCentral += leituras[i];
  }

  int adcFiltrado = (quantidadeFaixa > 0)
    ? (int)(somaCentral / quantidadeFaixa)
    : 0;

  return adcFiltrado;
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

  String url = montarUrlDjango();
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
  // Se lotar, descarta a mais antiga para manter as mais recentes.
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
  }

  if (enviados > 0) {
    Serial.print("Fila enviada: ");
    Serial.print(enviados);
    Serial.print(" | Restantes: ");
    Serial.println(filaQuantidade);
  }
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
}

void loop() {
  if (millis() - ultimoFlushFila >= INTERVALO_FLUSH_FILA_MS) {
    ultimoFlushFila = millis();
    tentarEnviarFila(3);
  }

  if (millis() - ultimoEnvio >= INTERVALO_ENVIO_MS) {
    ultimoEnvio = millis();

    float temp = lerTemperatura();
    if (isnan(temp)) {
      Serial.println("Falha ao ler temperatura.");
      delay(500);
      return;
    }

    SinalAnalogico sinalTurbidez = lerSinalAnalogicoMedio(
      TURBIDITY_PIN,
      20,
      10,
      false
    );
    SinalAnalogico sinalTDS = lerSinalAnalogicoMedio(
      TDS_PIN,
      30,
      5,
      true
    );
    int adcPh = lerAdcPhFiltradoRobusto();

    unsigned long firmwareTsMs = millis();

    Serial.print("Ponto: ");
    Serial.print(pontoTipo);
    Serial.print(" | Temp: ");
    Serial.print(temp, 2);
    Serial.print(" C | ADC Turbidez: ");
    Serial.print(sinalTurbidez.adc);
    Serial.print(" | ADC TDS: ");
    Serial.print(sinalTDS.adc);
    Serial.print(" | ADC pH: ");
    Serial.print(adcPh);
    Serial.println();

    enfileirarLeitura(
      temp,
      sinalTDS.adc,
      sinalTurbidez.adc,
      adcPh,
      firmwareTsMs
    );
    tentarEnviarFila(10);
  }

  delay(1000);
}
