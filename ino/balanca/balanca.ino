#include "HX711.h"
#include <Wire.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

#define DT 4
#define SCK 5
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
HX711 escala;
WebSocketsClient wsClient;

const char* ssid = "";
const char* password = "";
const char* host = "...";
const int port = 8000;
const char* path = "/carrinho/123";

float pesoAnterior = 0.0;
const float TOLERANCIA = 0.05;
bool envioSolicitado = false;

void mostrarMensagem(String msg) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println(msg);
  display.display();
}

void enviarPeso(float pesoAtual) {
  StaticJsonDocument<128> json;
  json["peso"] = pesoAtual;
  String mensagem;
  serializeJson(json, mensagem);

  wsClient.sendTXT(mensagem);
  Serial.println("Peso enviado via WebSocket: " + mensagem);
  mostrarMensagem("Peso: " + String(pesoAtual, 3) + " kg");
}

void setup() {
  Serial.begin(115200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Falha ao iniciar o SSD1306"));
    for (;;);
  }
  mostrarMensagem("Iniciando...");

  escala.begin(DT, SCK);
  escala.set_scale(-94375);
  delay(2000);
  escala.tare();
  mostrarMensagem("Balanca zerada!");
  delay(2000);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi conectado");
  mostrarMensagem("Wi-Fi conectado!");

  wsClient.begin(host, port, path);
  wsClient.onEvent(onWsEvent);
  wsClient.setReconnectInterval(5000);
  wsClient.enableHeartbeat(15000, 3000, 2);
}

unsigned long ultimoEnvio = 0;
const unsigned long intervalo = 5000;

void loop() {
  wsClient.loop();

  unsigned long agora = millis();

  if (agora - ultimoEnvio > intervalo) {
    ultimoEnvio = agora;
    float pesoAtual = max(0.0f, escala.get_units(20));
    float diferenca = pesoAtual - pesoAnterior;

    // Envia automaticamente apenas em caso de retirada (queda significativa)
    if (diferenca < -TOLERANCIA) {
      Serial.printf("Remocao detectada: %.3f\n", diferenca);
      enviarPeso(pesoAtual);
      pesoAnterior = pesoAtual;
      envioSolicitado = false;
    }

    // Envio sob demanda
    if (envioSolicitado) {
      Serial.println("Enviando peso sob demanda...");
      enviarPeso(pesoAtual);
      pesoAnterior = pesoAtual;
      envioSolicitado = false;
    }

  }

}

void onWsEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("Conectado ao WebSocket do backend.");
      break;

    case WStype_DISCONNECTED:
      Serial.println("Desconectado do WebSocket.");
      break;

    case WStype_TEXT: {
      Serial.printf("Mensagem recebida do backend: %s\n", payload);

      StaticJsonDocument<128> doc;
      DeserializationError err = deserializeJson(doc, payload);
      if (!err && doc["acao"] == "enviar_peso") {
        Serial.println("Solicitação de envio de peso recebida do backend.");
        envioSolicitado = true;  // Ativa o envio no próximo loop
      }
      break;
    }

    default:
      break;
  }
}
