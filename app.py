from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Crear DB si no existe
if not os.path.exists('jornadas.db'):
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE jornadas (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 tecnico TEXT,
                 fecha TEXT,
                 hora_inicio TEXT,
                 hora_fin TEXT,
                 resumen TEXT
                 )''')
    c.execute('''CREATE TABLE bloques (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 jornada_id INTEGER,
                 descripcion TEXT,
                 inicio TEXT,
                 fin TEXT,
                 resolucion TEXT
                 )''')
    c.execute('''CREATE TABLE ubicaciones (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 bloque_id INTEGER,
                 lat REAL,
                 lon REAL,
                 timestamp TEXT
                 )''')
    conn.commit()
    conn.close()

# HTML
login_html = """
<h2>Login Técnico</h2>
<form method="POST">
  <input type="text" name="nombre" placeholder="Tu nombre">
  <button type="submit">Entrar</button>
</form>
"""

panel_html = """
<h2>Bienvenido, {{nombre}}</h2>
<div id="estado"></div>
<form id="descForm">
  <textarea id="descripcion" placeholder="Descripción del trabajo..." rows="3" cols="40"></textarea>
  <button type="button" onclick="iniciarJornada()">Iniciar Jornada</button>
  <button type="button" onclick="pausarJornada()">Pausar</button>
  <button type="button" onclick="reanudarJornada()">Reanudar</button>
  <button type="button" onclick="finalizarBloque()">Finalizar Trabajo</button>
  <button type="button" onclick="finalizarJornada()">Finalizar Jornada</button>
</form>

<h3>Mis jornadas</h3>
<ul>
{% for j in jornadas %}
  <li>{{j[2]}}: {{j[3]}} - {{j[4]}} | {{j[5]}}</li>
{% endfor %}
</ul>

<script>
let jornadaId = null;
let bloqueId = null;
let tracking = null;
let lastLat = null;
let lastLon = null;
let lastMoveTime = Date.now();

function iniciarJornada() {
  let desc = document.getElementById("descripcion").value;
  fetch("/iniciar", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ descripcion: desc })
  }).then(res => res.json()).then(data => {
    jornadaId = data.jornada_id;
    bloqueId = data.bloque_id;
    document.getElementById("estado").innerText = "Jornada iniciada";
    startTracking();
  });
}

function startTracking() {
  tracking = setInterval(() => {
    navigator.geolocation.getCurrentPosition(pos => {
      let lat = pos.coords.latitude;
      let lon = pos.coords.longitude;
      let moved = lastLat && getDistance(lastLat, lastLon, lat, lon) > 0.1;
      if (moved) lastMoveTime = Date.now();
      lastLat = lat;
      lastLon = lon;
      fetch("/ubicacion", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bloque_id: bloqueId, lat: lat, lon: lon })
      });

      if (moved) {
        if (confirm("¿Finalizaste el trabajo anterior?")) {
          let res = prompt("Ingresá la resolución del servicio");
          fetch("/finalizar_bloque", {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bloque_id: bloqueId, resolucion: res })
          });
        }
      } else {
        if (Date.now() - lastMoveTime > 10 * 60 * 1000) {
          if (confirm("¿Estás en un nuevo cliente?")) {
            let nueva = prompt("Describí el nuevo trabajo");
            fetch("/nuevo_bloque", {
              method: "POST",
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ jornada_id: jornadaId, descripcion: nueva })
            }).then(res => res.json()).then(data => bloqueId = data.bloque_id);
          }
        }
      }
    });
  }, 300000);
}

function getDistance(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

function pausarJornada() {
  clearInterval(tracking);
  document.getElementById("estado").innerText = "Pausada";
}

function reanudarJornada() {
  document.getElementById("estado").innerText = "Reanudada";
  startTracking();
}

function finalizarBloque() {
  let res = prompt("Ingresá la resolución del trabajo");
  fetch("/finalizar_bloque", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bloque_id: bloqueId, resolucion: res })
  });
}

function finalizarJornada() {
  let resumen = prompt("Resumen de jornada");
  fetch("/finalizar_jornada", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jornada_id: jornadaId, resumen: resumen })
  }).then(() => location.reload());
}
</script>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['nombre'] = request.form['nombre']
        return redirect(url_for('panel'))
    return render_template_string(login_html)

@app.route('/panel')
def panel():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jornadas WHERE tecnico = ? ORDER BY id DESC", (session['nombre'],))
    jornadas = c.fetchall()
    conn.close()
    return render_template_string(panel_html, nombre=session['nombre'], jornadas=jornadas)

@app.route('/iniciar', methods=['POST'])
def iniciar():
    data = request.get_json()
    nombre = session['nombre']
    fecha = datetime.now().strftime('%Y-%m-%d')
    hora = datetime.now().strftime('%H:%M:%S')
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("INSERT INTO jornadas (tecnico, fecha, hora_inicio) VALUES (?, ?, ?)", (nombre, fecha, hora))
    jornada_id = c.lastrowid
    c.execute("INSERT INTO bloques (jornada_id, descripcion, inicio) VALUES (?, ?, ?)", (jornada_id, data['descripcion'], hora))
    bloque_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"jornada_id": jornada_id, "bloque_id": bloque_id})

@app.route('/nuevo_bloque', methods=['POST'])
def nuevo_bloque():
    data = request.get_json()
    hora = datetime.now().strftime('%H:%M:%S')
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("INSERT INTO bloques (jornada_id, descripcion, inicio) VALUES (?, ?, ?)", (data['jornada_id'], data['descripcion'], hora))
    bloque_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"bloque_id": bloque_id})

@app.route('/ubicacion', methods=['POST'])
def ubicacion():
    data = request.get_json()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("INSERT INTO ubicaciones (bloque_id, lat, lon, timestamp) VALUES (?, ?, ?, ?)", (data['bloque_id'], data['lat'], data['lon'], ts))
    conn.commit()
    conn.close()
    return ('', 204)

@app.route('/finalizar_bloque', methods=['POST'])
def finalizar_bloque():
    data = request.get_json()
    hora = datetime.now().strftime('%H:%M:%S')
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("UPDATE bloques SET fin = ?, resolucion = ? WHERE id = ?", (hora, data['resolucion'], data['bloque_id']))
    conn.commit()
    conn.close()
    return ('', 204)

@app.route('/finalizar_jornada', methods=['POST'])
def finalizar_jornada():
    data = request.get_json()
    hora = datetime.now().strftime('%H:%M:%S')
    conn = sqlite3.connect('jornadas.db')
    c = conn.cursor()
    c.execute("UPDATE jornadas SET hora_fin = ?, resumen = ? WHERE id = ?", (hora, data['resumen'], data['jornada_id']))
    conn.commit()
    conn.close()
    return ('', 204)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
