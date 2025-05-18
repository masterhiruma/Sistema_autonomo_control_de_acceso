#include <SPI.h>
#include <MFRC522.h>
// #include <Servo.h> // Comentado para deshabilitar el servo temporalmente

// === DEFINICIÓN DE PINES ===
// RFID RC522
#define PIN_RST_RFID 9
#define PIN_SS_RFID  10

// Sensores HC-SR04
const int PIN_TRIG_SP1 = 2; // SP1 - Exterior
const int PIN_ECHO_SP1 = 3;
const int PIN_TRIG_SP2 = 4; // SP2 - Interior
const int PIN_ECHO_SP2 = 5;

// Interruptores (INPUT_PULLUP, activo en LOW)
const int PIN_INTERRUPTOR_S1 = 6;
const int PIN_INTERRUPTOR_S2 = 7;
const int PIN_INTERRUPTOR_EMERGENCIA = 8;

// Servo Puerta (Pin cambiado a A3, pero funcionalidad comentada)
// const int PIN_SERVO_PUERTA = A3; // D17 

// LEDs
const int PIN_LED_VERDE = A0; // D14 (Cambiado de A1 a A0)
const int PIN_LED_ROJO  = A2; // D16 (Se mantiene en A2)

// === CONSTANTES SERVO (Mantenidas por si se reactiva, pero no usadas ahora) ===
// const int POSICION_PUERTA_CERRADA = 0;
// const int POSICION_PUERTA_ABIERTA = 90;

// === CONSTANTES GENERALES ===
const unsigned long INTERVALO_ENVIO_DATOS_MS = 100; // Enviar datos a Python cada 100ms
const unsigned long DEBOUNCE_DELAY_MS = 50;
const unsigned long INTERVALO_PARPADEO_LED_ROJO_MS = 250; // Para comando de parpadeo

// === OBJETOS GLOBALES ===
MFRC522 rfid(PIN_SS_RFID, PIN_RST_RFID);
// Servo servoPuerta; // Comentado

// === VARIABLES GLOBALES ===
// Estados de los interruptores (debounced)
bool estadoInterruptorS1 = true;
bool estadoInterruptorS2 = true;
bool estadoInterruptorEmergencia = true;

// Variables para debounce de interruptores
bool ultimoEstadoPinS1 = HIGH;
bool ultimoEstadoPinS2 = HIGH;
bool ultimoEstadoPinEmergencia = HIGH;
unsigned long tiempoUltimoDebounceS1 = 0;
unsigned long tiempoUltimoDebounceS2 = 0;
unsigned long tiempoUltimoDebounceEmergencia = 0;

// Para envío periódico de datos
unsigned long tiempoUltimoEnvioDatos = 0;

// Para control de lectura RFID por Python
bool solicitarLecturaRfidActiva = false;
bool uidEnviadoDesdeUltimaSolicitud = false;

// Para parpadeo de LED Rojo comandado por Python
bool ledRojoParpadeando = false;
int contadorParpadeosLedRojo = 0;
const int MAX_PARPADEOS_ALERTA = 6; // 3 ON, 3 OFF
bool estadoActualLedRojoParpadeo = LOW;
unsigned long tiempoUltimoParpadeoLedRojo = 0;


void setup() {
  Serial.begin(115200); // Velocidad de comunicación con Python

  // Configuración pines sensores ultrasonido
  pinMode(PIN_TRIG_SP1, OUTPUT);
  pinMode(PIN_ECHO_SP1, INPUT);
  pinMode(PIN_TRIG_SP2, OUTPUT);
  pinMode(PIN_ECHO_SP2, INPUT);

  // Configuración pines interruptores
  pinMode(PIN_INTERRUPTOR_S1, INPUT_PULLUP);
  pinMode(PIN_INTERRUPTOR_S2, INPUT_PULLUP);
  pinMode(PIN_INTERRUPTOR_EMERGENCIA, INPUT_PULLUP);

  // Configuración pines LEDs
  pinMode(PIN_LED_VERDE, OUTPUT); // PIN_LED_VERDE ahora es A0
  pinMode(PIN_LED_ROJO, OUTPUT);
  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_ROJO, LOW);

  // Configuración Servo (Comentada)
  // servoPuerta.attach(PIN_SERVO_PUERTA);
  // servoPuerta.write(POSICION_PUERTA_CERRADA); 

  // Iniciar RFID
  SPI.begin();
  rfid.PCD_Init();

  leerInterruptores(); // Leer estado inicial

  Serial.println("ARDUINO_LISTO"); // Señal para Python
}

void loop() {
  unsigned long tiempoActual = millis();

  leerInterruptores(); 
  manejarComandosPython(); 

  if (tiempoActual - tiempoUltimoEnvioDatos >= INTERVALO_ENVIO_DATOS_MS) {
    enviarDatosAPython();
    tiempoUltimoEnvioDatos = tiempoActual;
  }
  
  if (ledRojoParpadeando) {
    parpadearLedRojoComandado(tiempoActual);
  }
}

// --- FUNCIONES DE LECTURA DE SENSORES E INTERRUPTORES ---
float leerUltrasonico(int pinTrig, int pinEcho) {
  digitalWrite(pinTrig, LOW);
  delayMicroseconds(2);
  digitalWrite(pinTrig, HIGH);
  delayMicroseconds(10);
  digitalWrite(pinTrig, LOW);
  long duracion = pulseIn(pinEcho, HIGH, 25000); 
  if (duracion == 0) return 999.0; 
  return duracion * 0.0343 / 2.0;
}

void leerInterruptores() {
  unsigned long tiempoActual = millis();

  // Interruptor S1
  bool lecturaPinS1 = digitalRead(PIN_INTERRUPTOR_S1);
  if (lecturaPinS1 != ultimoEstadoPinS1) {
    tiempoUltimoDebounceS1 = tiempoActual;
  }
  if ((tiempoActual - tiempoUltimoDebounceS1) > DEBOUNCE_DELAY_MS) {
    if (lecturaPinS1 != estadoInterruptorS1) { 
         estadoInterruptorS1 = lecturaPinS1; 
    }
  }
  ultimoEstadoPinS1 = lecturaPinS1;

  // Interruptor S2
  bool lecturaPinS2 = digitalRead(PIN_INTERRUPTOR_S2);
  if (lecturaPinS2 != ultimoEstadoPinS2) {
    tiempoUltimoDebounceS2 = tiempoActual;
  }
  if ((tiempoActual - tiempoUltimoDebounceS2) > DEBOUNCE_DELAY_MS) {
    if (lecturaPinS2 != estadoInterruptorS2) {
        estadoInterruptorS2 = lecturaPinS2;
    }
  }
  ultimoEstadoPinS2 = lecturaPinS2;

  // Interruptor Emergencia
  bool lecturaPinEmergencia = digitalRead(PIN_INTERRUPTOR_EMERGENCIA);
  if (lecturaPinEmergencia != ultimoEstadoPinEmergencia) {
    tiempoUltimoDebounceEmergencia = tiempoActual;
  }
  if ((tiempoActual - tiempoUltimoDebounceEmergencia) > DEBOUNCE_DELAY_MS) {
     if (lecturaPinEmergencia != estadoInterruptorEmergencia) {
        estadoInterruptorEmergencia = lecturaPinEmergencia;
     }
  }
  ultimoEstadoPinEmergencia = lecturaPinEmergencia;
}

String leerUidRfid() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return "NADA";
  }

  String uidStr = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uidStr += "0";
    }
    uidStr += String(rfid.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();

  rfid.PICC_HaltA();      
  rfid.PCD_StopCrypto1(); 
  return uidStr;
}

// --- FUNCIONES DE COMUNICACIÓN Y CONTROL ---
void enviarDatosAPython() {
  float distSp1 = leerUltrasonico(PIN_TRIG_SP1, PIN_ECHO_SP1);
  float distSp2 = leerUltrasonico(PIN_TRIG_SP2, PIN_ECHO_SP2);
  String rfidUid = "NADA";

  if (solicitarLecturaRfidActiva && !uidEnviadoDesdeUltimaSolicitud) {
    rfidUid = leerUidRfid();
    if (rfidUid != "NADA") {
      uidEnviadoDesdeUltimaSolicitud = true; 
    }
  }
  
  String paqueteDatos = "DATOS;";
  paqueteDatos += "SP1:" + String(distSp1, 1) + ";";
  paqueteDatos += "SP2:" + String(distSp2, 1) + ";";
  paqueteDatos += "S1:" + String(estadoInterruptorS1 ? 1 : 0) + ";";
  paqueteDatos += "S2:" + String(estadoInterruptorS2 ? 1 : 0) + ";";
  paqueteDatos += "E:" + String(estadoInterruptorEmergencia ? 1 : 0) + ";"; 
  paqueteDatos += "RFID:" + rfidUid;
  
  Serial.println(paqueteDatos);
}

void manejarComandosPython() {
  if (Serial.available() > 0) {
    String comandoCompleto = Serial.readStringUntil('\n');
    comandoCompleto.trim();

    if (comandoCompleto.startsWith("COMANDO:")) {
      String comando = comandoCompleto.substring(8); 

      if (comando == "ABRIR_PUERTA") {
        // servoPuerta.write(POSICION_PUERTA_ABIERTA); // Comentado
        Serial.println("INFO: Comando ABRIR_PUERTA recibido (servo deshabilitado)");
      } else if (comando == "CERRAR_PUERTA") {
        // servoPuerta.write(POSICION_PUERTA_CERRADA); // Comentado
        Serial.println("INFO: Comando CERRAR_PUERTA recibido (servo deshabilitado)");
      } else if (comando == "LED_VERDE_ON") {
        digitalWrite(PIN_LED_VERDE, HIGH);
      } else if (comando == "LED_VERDE_OFF") {
        digitalWrite(PIN_LED_VERDE, LOW);
      } else if (comando == "LED_ROJO_ON") {
        ledRojoParpadeando = false; 
        digitalWrite(PIN_LED_ROJO, HIGH);
      } else if (comando == "LED_ROJO_OFF") {
        ledRojoParpadeando = false; 
        digitalWrite(PIN_LED_ROJO, LOW);
      } else if (comando == "LED_ROJO_PARPADEAR_ALERTA") { 
        ledRojoParpadeando = true;
        contadorParpadeosLedRojo = 0; 
        estadoActualLedRojoParpadeo = LOW; 
        tiempoUltimoParpadeoLedRojo = 0; 
      } else if (comando == "LED_ROJO_PARPADEAR_EMERGENCIA_INICIAR") {
        ledRojoParpadeando = true;
        contadorParpadeosLedRojo = -1; 
        estadoActualLedRojoParpadeo = LOW;
        tiempoUltimoParpadeoLedRojo = 0;
      } else if (comando == "LED_ROJO_PARPADEAR_EMERGENCIA_DETENER") {
        ledRojoParpadeando = false;
        digitalWrite(PIN_LED_ROJO, LOW); 
      }
      else if (comando == "SOLICITAR_LECTURA_RFID") {
        solicitarLecturaRfidActiva = true;
        uidEnviadoDesdeUltimaSolicitud = false; 
      }
    }
  }
}

void parpadearLedRojoComandado(unsigned long tiempoActual) {
    if (!ledRojoParpadeando) return;

    if (tiempoActual - tiempoUltimoParpadeoLedRojo >= INTERVALO_PARPADEO_LED_ROJO_MS) {
        estadoActualLedRojoParpadeo = !estadoActualLedRojoParpadeo;
        digitalWrite(PIN_LED_ROJO, estadoActualLedRojoParpadeo);
        tiempoUltimoParpadeoLedRojo = tiempoActual;

        if (contadorParpadeosLedRojo >= 0) { 
            contadorParpadeosLedRojo++;
            if (contadorParpadeosLedRojo >= MAX_PARPADEOS_ALERTA) {
                ledRojoParpadeando = false;
                digitalWrite(PIN_LED_ROJO, LOW); 
            }
        }
    }
}
