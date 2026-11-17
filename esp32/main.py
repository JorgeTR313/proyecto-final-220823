# Proyecto final sistemas embebidos
# Jorge TR - 220823

import network
import time
import ujson
import dht
from machine import ADC, Pin, PWM
 
try:
    import requests
except ImportError:
    import urequests as requests

from config import SSID, PASSWORD, URL_BASE, API_TOKEN

headers = {
    "X-API-Key": API_TOKEN,
    "Content-Type": "application/json"
}

# pines del esp32
adc1 = ADC(Pin(4))                       # pot
adc1.atten(ADC.ATTN_11DB)
boton = Pin(42, Pin.IN, Pin.PULL_UP)     # 0 si esta precionado
sensor = dht.DHT11(Pin(18))
led = Pin(10, Pin.OUT, value=0)
pwm = PWM(Pin(9), freq=1000, duty_u16=0)

INTERVALO_CONTROL = 1000   # tiempo para checar ordenes
INTERVALO_DATOS = 3000     # tiempo para enviar datos
MAX_FALLOS = 5             # maximo de fayos seguidos

wifi = network.WLAN(network.STA_IF)
wifi.active(True)

ultima_version = -1


def salidas_seguras():
    # apaga las salidas si se pierde la conecsion
    led.value(0)
    pwm.duty_u16(0)


def conectar_wifi():
    print("Conectando a Wi-Fi...")
    try:
        wifi.disconnect()
        wifi.connect(SSID, PASSWORD)
    except OSError as e:
        print("Error Wi-Fi:", e)
    for i in range(20):
        if wifi.isconnected():
            print("Wi-Fi conectado, IP:", wifi.ifconfig()[0])
            return
        time.sleep(1)
    print("No se pudo conectar, se intentara de nuevo")


def leer_voltaje():
    try:
        return round(adc1.read_uv() / 1000000, 3)
    except AttributeError:
        return round(adc1.read_u16() * 3.3 / 65535, 3)


def consultar_control():
    global ultima_version
    respuesta = None
    try:
        respuesta = requests.get(URL_BASE + "/control", timeout=5)
        if respuesta.status_code != 200:
            print("Control HTTP:", respuesta.status_code)
            return False
        orden = respuesta.json()

        # si canbio la orden en la pagina se imprime
        if orden.get('version') != ultima_version:
            ultima_version = orden.get('version')
            estado_led = "ON" if orden['led'] else "OFF"
            print(">>> Orden web -> LED:", estado_led, "| PWM:", orden['pwm'], "%")

        led.value(1 if orden['led'] else 0)
        porcentaje = max(0, min(100, int(orden['pwm'])))
        pwm.duty_u16(round(porcentaje * 65535 / 100))
        return True
    except Exception as e:
        print("Error control:", e)
        return False
    finally:
        if respuesta is not None:
            respuesta.close()


def enviar_datos(datos):
    respuesta = None
    try:
        respuesta = requests.post(URL_BASE + "/refresh", data=ujson.dumps(datos),
                                  headers=headers, timeout=5)
        print("Datos:", datos)
        print("HTTP:", respuesta.status_code, respuesta.text)
    except Exception as e:
        print("Error envio:", e)
    finally:
        if respuesta is not None:
            respuesta.close()


# loop principal
temperatura = 25.0   # valor temporal si no esta el sensor
humedad = 50.0
fallos = 0
t_control = time.ticks_ms()
t_datos = time.ticks_ms()

conectar_wifi()

while True:

    if not wifi.isconnected():
        print("Sin Wi-Fi")
        salidas_seguras()
        conectar_wifi()
        continue

    ahora = time.ticks_ms()

    if time.ticks_diff(ahora, t_control) >= INTERVALO_CONTROL:
        t_control = ahora
        if consultar_control():
            fallos = 0
        else:
            fallos += 1
            if fallos >= MAX_FALLOS:
                print("La nube no responde, salidas apagadas")
                salidas_seguras()

    if time.ticks_diff(ahora, t_datos) >= INTERVALO_DATOS:
        t_datos = ahora

        # si falla el dht11 se usan los valores de antes
        try:
            sensor.measure()
            temperatura = sensor.temperature()
            humedad = sensor.humidity()
        except OSError:
            pass

        enviar_datos({
            "adc1": leer_voltaje(),
            "boton": boton.value(),
            "temperatura": temperatura,
            "humedad": humedad
        })

    time.sleep_ms(50)
