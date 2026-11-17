# Proyecto final sistemas embebidos
# Jorge TR - 220823

from microdot.wsgi import Microdot
import os
import time

app = Microdot()

# el token se pone en el archivo wsgi
API_TOKEN = os.environ.get("IOT_API_TOKEN", "")

MAX_MUESTRAS = 20

# se guardan en RAM, si se reinicia la pagina se pierden
datos = {
    "tiempo": [],
    "adc1": [],
    "boton": [],
    "temperatura": [],
    "humedad": []
}

# ultima orden para el esp32
control = {"led": False, "pwm": 0, "version": 0}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Proyecto Final - Jorge TR 220823</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body bgcolor="#f2f2f2">
<center>

<h1>Proyecto Final - Sistemas Embebidos</h1>
<p>Jorge TR - Matricula: 220823</p>
<hr>

<h2>Lecturas del ESP32</h2>
<table border="1" cellspacing="0" cellpadding="10" width="90%" bgcolor="white">
    <tr bgcolor="#dddddd">
        <th width="25%">Voltaje ADC</th>
        <th width="25%">Boton</th>
        <th width="25%">Temperatura</th>
        <th width="25%">Humedad</th>
    </tr>
    <tr align="center">
        <td><h1 id="adc">---</h1></td>
        <td><h1 id="boton">---</h1></td>
        <td><h1 id="temperatura">---</h1></td>
        <td><h1 id="humedad">---</h1></td>
    </tr>
</table>
<p>Ultima muestra: <b id="hora">---</b></p>

<br>

<table cellpadding="15">
    <tr valign="top">
        <td align="center">
            <h2>Grafica de temperatura y humedad</h2>
            <div style="width: 650px; background-color: white;">
                <canvas id="grafica"></canvas>
            </div>
        </td>
        <td align="center">
            <h2>Controles</h2>
            <table border="1" cellspacing="0" cellpadding="20" width="320" bgcolor="white">
                <tr align="center">
                    <td>
                        <h2>LED</h2>
                        <input id="led" type="checkbox" style="width: 40px; height: 40px;">
                    </td>
                </tr>
                <tr align="center">
                    <td>
                        <h2>PWM</h2>
                        <input id="pwm" type="range" min="0" max="100" value="0" style="width: 250px;">
                        <h1 id="porcentaje">0%</h1>
                    </td>
                </tr>
            </table>
            <p id="mensaje"></p>
        </td>
    </tr>
</table>

</center>

<script>
// la grafica se crea una sola ves
var grafica = new Chart(document.getElementById('grafica'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            {label: 'Temperatura (°C)', data: [], borderColor: 'red', yAxisID: 'y'},
            {label: 'Humedad (%HR)', data: [], borderColor: 'blue', yAxisID: 'y1'}
        ]
    },
    options: {
        scales: {
            y: {position: 'left', title: {display: true, text: 'Temperatura (°C)'}},
            y1: {position: 'right', title: {display: true, text: 'Humedad (%HR)'},
                 grid: {drawOnChartArea: false}}
        }
    }
});

async function actualizar() {
    try {
        const res = await fetch('/refresh');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        var n = data.tiempo.length;
        if (n > 0) {
            document.getElementById('adc').innerText = data.adc1[n - 1] + ' V';
            // 0 es precionado
            document.getElementById('boton').innerText =
                data.boton[n - 1] == 0 ? 'Presionado' : 'Suelto';
            document.getElementById('temperatura').innerText = data.temperatura[n - 1] + ' °C';
            document.getElementById('humedad').innerText = data.humedad[n - 1] + ' %HR';
            document.getElementById('hora').innerText =
                new Date(data.tiempo[n - 1] * 1000).toLocaleTimeString();
        }

        grafica.data.labels = data.tiempo.map(t => new Date(t * 1000).toLocaleTimeString());
        grafica.data.datasets[0].data = data.temperatura;
        grafica.data.datasets[1].data = data.humedad;
        grafica.update();
    } catch (error) {
        console.error(error);
    }
}

async function enviarControl() {
    var mensaje = document.getElementById('mensaje');
    document.getElementById('porcentaje').innerText = document.getElementById('pwm').value + '%';
    const orden = {
        led: document.getElementById('led').checked,
        pwm: Number(document.getElementById('pwm').value)
    };
    try {
        const r = await fetch('/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(orden)
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        mensaje.innerText = 'Orden enviada';
    } catch (error) {
        mensaje.innerText = 'Error al enviar la orden: ' + error.message;
    }
}

// pone los controles como estavan al abrir la pagina
async function cargarControl() {
    try {
        const res = await fetch('/control');
        const c = await res.json();
        document.getElementById('led').checked = c.led;
        document.getElementById('pwm').value = c.pwm;
        document.getElementById('porcentaje').innerText = c.pwm + '%';
    } catch (error) {
        console.error(error);
    }
}

document.getElementById('led').addEventListener('change', enviarControl);
document.getElementById('pwm').addEventListener('change', enviarControl);
document.getElementById('pwm').addEventListener('input', function () {
    document.getElementById('porcentaje').innerText = this.value + '%';
});

cargarControl();
actualizar();
setInterval(actualizar, 2000);
</script>

</body>
</html>
"""


def leer_json(request):
    try:
        recibido = request.json
    except ValueError:
        return None
    if not isinstance(recibido, dict):
        return None
    return recibido


@app.get('/')
def index(request):
    return HTML, 200, {'Content-Type': 'text/html'}


@app.get('/refresh')
def consultar_datos(request):
    return datos


# aqui manda los datos el esp32
@app.post('/refresh')
def recibir_datos(request):

    if not API_TOKEN or request.headers.get('X-API-Key') != API_TOKEN:
        return {'error': 'No autorizado'}, 401

    recibido = leer_json(request)
    if recibido is None:
        return {'error': 'JSON invalido'}, 400

    # primero se validan todos y despues se guardan para que no se desalinien
    try:
        voltaje = float(recibido['adc1'])
        boton = int(recibido['boton'])
        T = float(recibido['temperatura'])
        H = float(recibido['humedad'])
    except (KeyError, TypeError, ValueError):
        return {'error': 'Faltan datos o no son numericos'}, 400

    if not 0 <= voltaje <= 3.3:
        return {'error': 'Voltaje fuera de rango'}, 400
    if boton not in (0, 1):
        return {'error': 'Boton invalido'}, 400
    if not -40 <= T <= 80:
        return {'error': 'Temperatura fuera de rango'}, 400
    if not 0 <= H <= 100:
        return {'error': 'Humedad fuera de rango'}, 400

    datos['tiempo'].append(time.time())
    datos['adc1'].append(round(voltaje, 3))
    datos['boton'].append(boton)
    datos['temperatura'].append(T)
    datos['humedad'].append(H)

    if len(datos['tiempo']) > MAX_MUESTRAS:
        for clave in datos:
            datos[clave].pop(0)

    return {'status': 'OK'}


@app.get('/control')
def consultar_control(request):
    return control


# aqui manda las ordenes la pagina
@app.post('/control')
def recibir_control(request):

    recibido = leer_json(request)
    if recibido is None:
        return {'error': 'JSON invalido'}, 400

    try:
        led = recibido['led']
        pwm = int(recibido['pwm'])
    except (KeyError, TypeError, ValueError, OverflowError):
        return {'error': 'Faltan datos o pwm no es numerico'}, 400

    if not isinstance(led, bool):
        return {'error': 'led debe ser true o false'}, 400

    # si se pasa del rango se deja entre 0 y 100
    pwm = max(0, min(100, pwm))

    control['led'] = led
    control['pwm'] = pwm
    control['version'] += 1

    return control
