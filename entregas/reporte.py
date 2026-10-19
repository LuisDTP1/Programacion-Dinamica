"""
Mapa interactivo de las entregas en Ibagué (Leaflet + OpenStreetMap).

- Traza la ruta de cada vehículo y numera sus paradas.
- Al hacer clic en una parada muestra los paquetes que se entregan allí.
- Panel lateral con distancia, tiempo, paradas y paquetes de cada vehículo.
- Botón para animar el recorrido y vista 3D de la carga (three.js).
- Si se usó la red simplificada, la línea se ajusta a las calles reales
  con el servicio público OSRM (solo para dibujar; los km y minutos del
  reporte son los que calculó nuestro Dijkstra).
Se abre en cualquier navegador; necesita internet para el mapa base.
"""

from __future__ import annotations

import json

COLORES = {"Camión 1": "#1f6feb", "Camión 2": "#d1242f", "Moto 1": "#1a7f37", "Moto 2": "#8250df"}


def _datos(vehiculos, grafo, deposito, criterio, osm, matriz, puntos, salida_min) -> dict:
    factor_moto = next((v.perfil["factor_velocidad"] for v in vehiculos if v.tipo == "Moto"), 1.0)
    datos = {"criterio": criterio, "osm": osm, "salida": salida_min, "factor_moto": factor_moto,
             "deposito": {"nombre": grafo.nombre[deposito], "pos": grafo.pos[deposito]},
             "puntos": [{"id": n, "nombre": grafo.nombre[n], "comuna": grafo.comuna[n]} for n in puntos],
             "matriz": {f"{a}|{b}": {"km": round(d["km"], 2), "min": round(d["min"], 1),
                                     "vias": d["vias"], "linea": [grafo.pos[n] for n in d["nodos"]]}
                        for (a, b), d in (matriz or {}).items()},
             "vehiculos": []}
    for v in vehiculos:
        f = v.carga.furgon
        nodos = [v.ruta[0]] + [b for _, b, _ in v.recorrido]
        paradas = []
        for i, n in enumerate(v.ruta[1:-1], start=1):
            pq = [c for c in v.carga.colocados if c.paquete.destino == n]
            paradas.append({
                "orden": i, "nombre": grafo.nombre[n], "comuna": grafo.comuna[n],
                "pos": grafo.pos[n], "kg": round(sum(c.paquete.peso for c in pq), 1),
                "paquetes": [{"id": c.paquete.id, "emp": c.paquete.empaque,
                              "el": c.paquete.elemento, "alto": c.paquete.alto,
                              "ancho": c.paquete.ancho, "prof": c.paquete.profundidad,
                              "peso": c.paquete.peso, "fragil": c.paquete.fragil,
                              "vertical": c.paquete.vertical, "piso": c.paquete.solo_piso}
                             for c in pq]})
        cajas = [{"id": c.paquete.id, "emp": c.paquete.empaque, "el": c.paquete.elemento,
                  "alto": c.paquete.alto, "ancho": c.paquete.ancho, "prof": c.paquete.profundidad,
                  "peso": c.paquete.peso, "cli": grafo.nombre[c.paquete.destino],
                  "ent": c.orden_entrega, "color": c.paquete.color,
                  "x": c.x, "y": c.y, "z": c.z, "dx": c.dx, "dy": c.dy, "dz": c.dz}
                 for c in v.carga.colocados]
        vias = []
        for _, _, a in v.recorrido:
            if vias and vias[-1][0] == a.via:
                vias[-1][1] += a.km
            else:
                vias.append([a.via, a.km])
        datos["vehiculos"].append({
            "nombre": v.nombre, "tipo": v.tipo, "color": COLORES.get(v.nombre, "#555"),
            "metodo": v.metodo, "km": round(v.km, 2), "min_cond": round(v.min_conduccion, 1),
            "min_total": round(v.min_total, 1), "peso": round(v.carga.peso_total, 1),
            "vol": round(v.carga.volumen_total, 3), "n": len(v.paquetes),
            "espacio": {"nombre": f.nombre, "L": f.largo, "W": f.ancho, "H": f.alto,
                        "kg": f.capacidad_kg, "m3": round(f.volumen_m3, 3)},
            "linea": [grafo.pos[n] for n in nodos],
            "vias": [[n, round(k, 1)] for n, k in vias],
            "paradas": paradas, "cajas": cajas,
            "tramos": [{"n": t["n"], "de": t["de"], "a": t["a"], "deN": grafo.nombre[t["de"]],
                        "aN": grafo.nombre[t["a"]], "km": round(t["km"], 2), "min": round(t["min"], 1),
                        "llega": t["llega"], "entrega": round(t["entrega"], 1)}
                       for t in v.itinerario(salida_min)]})
    return datos


def generar_html(vehiculos, grafo, deposito, criterio, osm=False, matriz=None, puntos=None,
                 salida_min=480, archivo="mapa_entregas.html"):
    """Escribe el mapa HTML y devuelve su ruta (Path)."""
    from pathlib import Path
    archivo = Path(archivo)
    datos = json.dumps(_datos(vehiculos, grafo, deposito, criterio, osm, matriz,
                              puntos or [deposito], salida_min), ensure_ascii=False)
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(PLANTILLA.replace("__DATOS__", datos))
    return archivo


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entregas Ibagué</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<style>
:root{--tx:#1d2330;--mut:#667085;--bd:#e3e6eb;--bg:#f6f7f9;--osc:#14213d}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{font:14px/1.45 system-ui,"Segoe UI",Roboto,sans-serif;color:var(--tx);display:flex;flex-direction:column}
header{background:var(--osc);color:#fff;padding:10px 16px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
header h1{font-size:18px;margin:0}header .s{opacity:.8;font-size:13px}
#app{flex:1;display:flex;min-height:0}
#mapa{flex:1;min-height:300px}
aside{width:400px;max-width:100%;overflow:auto;background:var(--bg);border-left:1px solid var(--bd);padding:12px}
@media(max-width:820px){#app{flex-direction:column}#mapa{height:55vh;flex:none}aside{width:auto;border-left:0}}
.veh{background:#fff;border:1px solid var(--bd);border-left:6px solid;border-radius:10px;padding:8px 10px;margin-bottom:8px;cursor:pointer}
.veh.on{box-shadow:0 0 0 2px var(--osc)}
.veh .t{font-weight:600;display:flex;justify-content:space-between}.veh .d{color:var(--mut);font-size:12px}
.btns{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
button{border:1px solid var(--bd);background:#fff;border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit}
button.p{background:var(--osc);color:#fff;border-color:var(--osc)}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}
.kpi{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:6px 8px}.kpi b{display:block}.kpi span{font-size:11px;color:var(--mut)}
details{background:#fff;border:1px solid var(--bd);border-radius:8px;margin-bottom:6px}
summary{padding:6px 8px;cursor:pointer;display:flex;gap:6px;align-items:center}
.num{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;color:#fff;font-size:12px;font-weight:700;flex:none}
table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:3px 5px;border-top:1px solid var(--bd);text-align:left;white-space:nowrap}
td.n{text-align:right}.tag{font-size:10px;padding:1px 5px;border-radius:8px;background:#fde2e1;color:#a4161a}
.vias{font-size:12px;color:var(--mut)}.nota{font-size:11px;color:var(--mut);margin-top:8px}
.pin{display:flex;align-items:center;justify-content:center;border-radius:50%;color:#fff;font-weight:700;font-size:12px;border:2px solid #fff;box-shadow:0 1px 3px #0006}
.mov{font-size:26px;line-height:1;filter:drop-shadow(0 1px 2px #0008)}
.leaflet-popup-content{margin:10px 12px;max-height:260px;overflow:auto}
#modal{position:fixed;inset:0;background:#0008;display:none;align-items:center;justify-content:center;z-index:2000}
#modal>div{background:#fff;border-radius:12px;width:min(900px,95vw);padding:12px}
#v3d{height:min(520px,70vh);position:relative;background:#eef1f5;border-radius:8px}
#tip{position:absolute;pointer-events:none;background:#14213dee;color:#fff;padding:6px 8px;border-radius:6px;font-size:12px;display:none}
.ab{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:10px;margin-bottom:10px}
.ab h3{margin:0 0 8px;font-size:15px}.ab select{width:100%;padding:6px;border:1px solid var(--bd);border-radius:8px;font:inherit;margin-bottom:6px}
.ab .fila{display:flex;gap:6px;align-items:center}.ab .fila select{flex:1;margin:0}
.res{margin-top:8px;font-size:13px}.res .g{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:6px 0}
tr.tr{cursor:pointer}tr.tr:hover{background:#eef3ff}
#mmat .scroll{max-height:70vh;overflow:auto}#mmat td,#mmat th{font-size:11px;text-align:center;padding:3px 4px}
#mmat th.r{text-align:left;position:sticky;left:0;background:#f0f2f5}#mmat thead th{position:sticky;top:0;background:#f0f2f5;writing-mode:vertical-rl;transform:rotate(180deg);height:150px}
#mmat td.c{cursor:pointer}#mmat td.c:hover{outline:2px solid var(--osc)}
.ley{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;margin-top:6px}.ley i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:3px}
</style></head><body>
<header><h1>Entregas en Ibagué</h1><span class="s" id="sub"></span></header>
<div id="app"><div id="mapa"></div><aside>
  <div class="ab"><h3>⏱️ ¿Cuánto se tarda de A a B?</h3>
    <div class="fila"><select id="selA"></select><button title="Invertir" onclick="invertir()">⇅</button></div>
    <select id="selB" style="margin-top:6px"></select>
    <div class="res" id="resAB"></div>
    <div class="btns" style="margin:6px 0 0"><button onclick="abrirMatriz()">Ver tiempos entre todos los puntos</button></div>
  </div>
  <div id="lista"></div>
  <div id="detalle"></div>
  <div class="nota" id="nota"></div>
</aside></div>
<div id="mmat" style="position:fixed;inset:0;background:#0008;display:none;align-items:center;justify-content:center;z-index:2000"><div style="background:#fff;border-radius:12px;width:min(1200px,96vw);padding:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"><b>Tiempo entre todos los puntos (Dijkstra)</b>
    <span><label><input type="radio" name="vm" value="c" checked onchange="pintarMatriz()"> 🚚 Camión</label>
    <label><input type="radio" name="vm" value="m" onchange="pintarMatriz()"> 🏍️ Moto</label>
    <label><input type="radio" name="vm" value="k" onchange="pintarMatriz()"> km</label>
    <button onclick="document.getElementById('mmat').style.display='none'">Cerrar</button></span></div>
  <div class="nota">Fila = desde, columna = hasta. Haga clic en una celda para ver ese recorrido en el mapa.</div>
  <div class="scroll"><table id="tmat"></table></div>
</div></div>
<div id="modal"><div>
  <div style="display:flex;justify-content:space-between;align-items:center"><b id="mt"></b><button onclick="cerrar3d()">Cerrar</button></div>
  <div class="nota">Arrastre para girar y use la rueda para acercar. La salida de la carga está a la derecha.</div>
  <div id="v3d"><div id="tip"></div></div><div class="ley" id="ley"></div>
</div></div>
<script>
const D = __DATOS__;
const hhmm = m => `${Math.floor(m/60)} h ${String(Math.round(m%60)).padStart(2,'0')} min`;
const ico = t => t === 'Moto' ? '🏍️' : '🚚';
const reglas = p => [p.fragil?'FRÁGIL':'', p.vertical?'Este lado arriba':'', p.piso?'Solo piso':''].filter(Boolean).join(', ');
const tabla = ps => '<table><tr><th>ID</th><th>Empaque</th><th>Elemento</th><th>Alto</th><th>Ancho</th><th>Prof.</th><th>Peso</th><th></th></tr>' +
  ps.map(p => `<tr><td>${p.id}</td><td>${p.emp}</td><td>${p.el}</td><td class="n">${p.alto}</td><td class="n">${p.ancho}</td>
  <td class="n">${p.prof}</td><td class="n">${p.peso}</td><td>${reglas(p) ? '<span class="tag">'+reglas(p)+'</span>' : ''}</td></tr>`).join('') + '</table>';
const tot = k => D.vehiculos.reduce((s,v)=>s+v[k],0);
const reloj = m => { m = Math.round(m) % 1440; const h = Math.floor(m/60), mm = String(m%60).padStart(2,'0');
  return `${(h+11)%12+1}:${mm} ${h<12?'a. m.':'p. m.'}`; };
const mins = m => m >= 60 ? hhmm(m) : `${Math.round(m)} min`;
document.getElementById('sub').textContent = `Salida: ${D.deposito.nombre} · 2 camiones y 2 motos · `+
  `${tot('n')} paquetes · ${tot('km').toFixed(1)} km · ruta más eficiente por ${D.criterio}`;

// ---------------- Mapa ----------------
const mapa = L.map('mapa', {zoomControl:true});
// Mapa base: tile.openstreetmap.org bloquea páginas abiertas como archivo
// local (file://) y CARTO exige clave; Esri se puede usar sin clave.
const bases = {
  'Calles': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
            {maxZoom:19, attribution:'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap'}),
  'Gris claro': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
            {maxZoom:16, attribution:'Tiles &copy; Esri'}),
  'Satélite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {maxZoom:19, attribution:'Tiles &copy; Esri, Maxar, Earthstar Geographics'}),
};
bases['Calles'].addTo(mapa);
L.control.layers(bases, null, {position:'topleft'}).addTo(mapa);
L.marker(D.deposito.pos, {icon:L.divIcon({className:'', html:'<div class="pin" style="width:34px;height:34px;background:#14213d;font-size:18px">🏭</div>', iconSize:[34,34], iconAnchor:[17,17]})})
  .addTo(mapa).bindPopup(`<b>${D.deposito.nombre}</b><br>Punto de salida y regreso`);
const capas = D.vehiculos.map(v => {
  const g = L.layerGroup().addTo(mapa);
  v.poly = L.polyline(v.linea, {color:v.color, weight:5, opacity:.85}).addTo(g).bindTooltip(`${ico(v.tipo)} ${v.nombre}: ${v.km} km`);
  v.marcas = v.paradas.map(p => L.marker(p.pos, {icon:L.divIcon({className:'',
      html:`<div class="pin" style="width:26px;height:26px;background:${v.color}">${p.orden}</div>`, iconSize:[26,26], iconAnchor:[13,13]})})
    .addTo(g).bindPopup(`<b>${p.nombre}</b> · comuna ${p.comuna}<br>${ico(v.tipo)} ${v.nombre}, parada ${p.orden}<br>
      ${p.paquetes.length} paquetes · ${p.kg} kg${tabla(p.paquetes)}`, {maxWidth:520}));
  return g;
});
mapa.fitBounds(D.vehiculos.flatMap(v => v.linea).concat([D.deposito.pos]), {padding:[30,30]});

// Ajuste del trazado a las calles reales (solo visual)
const nota = document.getElementById('nota');
if (!D.osm) {
  let ok = 0;
  Promise.all(D.vehiculos.map(v => {
    const pts = v.linea.map(([la,lo]) => `${lo},${la}`).join(';');
    return fetch(`https://router.project-osrm.org/route/v1/driving/${pts}?overview=full&geometries=geojson`)
      .then(r => r.json()).then(j => {
        if (j.code !== 'Ok') throw 0;
        v.poly.setLatLngs(j.routes[0].geometry.coordinates.map(([lo,la]) => [la,lo])); ok++;
      }).catch(() => {});
  })).then(() => nota.textContent = ok ? 'El trazado se dibuja sobre las calles reales de Ibagué (OSRM). La distancia y el tiempo son los que calculó Dijkstra sobre el grafo del proyecto.'
                                       : 'Trazado aproximado entre barrios: no se pudo consultar el servicio de calles (OSRM).');
} else nota.textContent = 'Rutas calculadas sobre todas las calles de OpenStreetMap.';

// ---------------- Panel lateral ----------------
let sel = null;
function lista(){
  document.getElementById('lista').innerHTML =
    `<div class="veh ${sel===null?'on':''}" style="border-left-color:#14213d" onclick="elegir(null)">
      <div class="t"><span>Toda la flota</span><span>${tot('km').toFixed(1)} km</span></div>
      <div class="d">${tot('n')} paquetes · ${hhmm(tot('min_total'))} de trabajo</div></div>` +
    D.vehiculos.map((v,i) => `<div class="veh ${sel===i?'on':''}" style="border-left-color:${v.color}" onclick="elegir(${i})">
      <div class="t"><span>${ico(v.tipo)} ${v.nombre}</span><span>${v.km} km</span></div>
      <div class="d">${v.n} paquetes · ${v.paradas.length} paradas · ${hhmm(v.min_total)}</div></div>`).join('');
}
function elegir(i){
  sel = i; lista(); parar();
  D.vehiculos.forEach((v,j) => { v.poly.setStyle({opacity: i===null||i===j ? .85 : .15, weight: i===j ? 7 : 5});
    v.marcas.forEach(m => m.setOpacity(i===null||i===j ? 1 : .25)); });
  const det = document.getElementById('detalle');
  if (i === null){ det.innerHTML = ''; mapa.fitBounds(D.vehiculos.flatMap(v=>v.linea),{padding:[30,30]}); return; }
  const v = D.vehiculos[i];
  mapa.fitBounds(v.poly.getBounds(), {padding:[40,40]});
  det.innerHTML = `<div class="btns"><button class="p" onclick="recorrer(${i})">▶ Recorrer ruta</button>
      <button onclick="abrir3d(${i})">Ver carga en 3D</button></div>
    <div class="kpis">
      <div class="kpi"><b>${v.km} km</b><span>Distancia (Dijkstra)</span></div>
      <div class="kpi"><b>${hhmm(v.min_cond)}</b><span>Conducción</span></div>
      <div class="kpi"><b>${hhmm(v.min_total)}</b><span>Total con entregas</span></div>
      <div class="kpi"><b>${v.peso} / ${v.espacio.kg} kg</b><span>Peso (${(100*v.peso/v.espacio.kg).toFixed(0)} %)</span></div>
      <div class="kpi"><b>${v.vol} / ${v.espacio.m3} m³</b><span>Volumen (${(100*v.vol/v.espacio.m3).toFixed(0)} %)</span></div>
      <div class="kpi"><b>${v.metodo.split(' (')[0]}</b><span>Algoritmo de ruta</span></div></div>
    <h4 style="margin:10px 0 6px">⏱️ Tiempo de cada tramo <small style="color:var(--mut)">(salida ${reloj(D.salida)})</small></h4>
    <div style="background:#fff;border:1px solid var(--bd);border-radius:8px;overflow:auto"><table>
      <tr><th>#</th><th>De → A</th><th>km</th><th>Tiempo</th><th>Llega</th></tr>
      ${v.tramos.map((t,k) => `<tr class="tr" onclick="verTramo(${i},${k})"><td>${t.n}</td><td>${t.deN}<br>→ <b>${t.aN}</b></td>
        <td class="n">${t.km}</td><td class="n"><b>${mins(t.min)}</b></td><td>${reloj(t.llega)}${t.entrega ? `<br><small style="color:var(--mut)">entrega ${Math.round(t.entrega)} min</small>` : ''}</td></tr>`).join('')}
      <tr><td></td><td><b>Total conducción</b></td><td class="n"><b>${v.km}</b></td><td class="n"><b>${mins(v.min_cond)}</b></td><td></td></tr>
    </table></div>
    <div class="nota">Haga clic en un tramo para resaltarlo en el mapa.</div>
    <div class="vias" style="margin-top:8px"><b>Vías:</b> ${v.vias.map(([n,k]) => `${n} (${k} km)`).join(' → ')}</div>
    <h4 style="margin:10px 0 6px">Paradas y paquetes</h4>` +
    v.paradas.map((p,k) => `<details><summary onclick="verParada(${i},${k})"><span class="num" style="background:${v.color}">${p.orden}</span>
      <span><b>${p.nombre}</b><br><small>${p.paquetes.length} paquetes · ${p.kg} kg</small></span></summary>${tabla(p.paquetes)}</details>`).join('');
}
function verParada(i,k){ const m = D.vehiculos[i].marcas[k]; mapa.setView(m.getLatLng(), 15); m.openPopup(); }

// ---------------- Animación del recorrido ----------------
let anim = null, movil = null;
function parar(){ if (anim) cancelAnimationFrame(anim); anim = null; if (movil) mapa.removeLayer(movil); movil = null; }
function recorrer(i){
  parar();
  const v = D.vehiculos[i], pts = v.poly.getLatLngs();
  const acum = [0]; for (let k=1;k<pts.length;k++) acum.push(acum[k-1] + pts[k-1].distanceTo(pts[k]));
  const total = acum[acum.length-1], dur = 14000, t0 = performance.now();
  movil = L.marker(pts[0], {icon:L.divIcon({className:'', html:`<div class="mov">${ico(v.tipo)}</div>`, iconSize:[30,30], iconAnchor:[15,15]}), zIndexOffset:1000}).addTo(mapa);
  const paso = now => {
    const d = Math.min(1,(now-t0)/dur) * total;
    let k = 1; while (k < acum.length-1 && acum[k] < d) k++;
    const f = (d-acum[k-1]) / ((acum[k]-acum[k-1]) || 1);
    movil.setLatLng([pts[k-1].lat + (pts[k].lat-pts[k-1].lat)*f, pts[k-1].lng + (pts[k].lng-pts[k-1].lng)*f]);
    anim = d < total ? requestAnimationFrame(paso) : null;
  };
  anim = requestAnimationFrame(paso);
}

// ---------------- Vista 3D de la carga ----------------
let r3 = null;
function iniciar3d(){
  const c = document.getElementById('v3d'), tip = document.getElementById('tip');
  const ren = new THREE.WebGLRenderer({antialias:true}); ren.setPixelRatio(devicePixelRatio); c.appendChild(ren.domElement);
  const esc = new THREE.Scene(); esc.background = new THREE.Color(0xeef1f5);
  const cam = new THREE.PerspectiveCamera(45,1,1,5000), ctl = new THREE.OrbitControls(cam, ren.domElement);
  esc.add(new THREE.AmbientLight(0xffffff,.65)); const l = new THREE.DirectionalLight(0xffffff,.55); l.position.set(300,500,400); esc.add(l);
  const ray = new THREE.Raycaster(), ms = new THREE.Vector2();
  r3 = {c, ren, esc, cam, ctl, grupo:null, mallas:[]};
  ren.domElement.addEventListener('mousemove', ev => {
    const b = ren.domElement.getBoundingClientRect();
    ms.x = ((ev.clientX-b.left)/b.width)*2-1; ms.y = -((ev.clientY-b.top)/b.height)*2+1; ray.setFromCamera(ms, cam);
    const h = ray.intersectObjects(r3.mallas,false)[0]; if (!h){ tip.style.display='none'; return; }
    const p = h.object.userData;
    tip.innerHTML = `<b>#${p.id} ${p.emp} · ${p.el}</b><br>Alto ${p.alto} · Ancho ${p.ancho} · Prof. ${p.prof} cm<br>${p.peso} kg · para ${p.cli} (parada ${p.ent})`;
    tip.style.left = (ev.clientX-b.left+12)+'px'; tip.style.top = (ev.clientY-b.top+12)+'px'; tip.style.display = 'block';
  });
  (function loop(){ requestAnimationFrame(loop); ren.render(esc,cam); })();
}
function abrir3d(i){
  const v = D.vehiculos[i], E = v.espacio;
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('mt').textContent = `${ico(v.tipo)} ${v.nombre} · ${E.nombre} (${E.L} × ${E.W} × ${E.H} cm)`;
  if (!r3) iniciar3d();
  const {c, ren, esc, cam, ctl} = r3; ren.setSize(c.clientWidth, c.clientHeight); cam.aspect = c.clientWidth/c.clientHeight; cam.updateProjectionMatrix();
  if (r3.grupo) esc.remove(r3.grupo);
  const g = new THREE.Group(); r3.mallas = [];
  const caja = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(E.L,E.H,E.W)), new THREE.LineBasicMaterial({color:0x333333}));
  caja.position.set(E.L/2,E.H/2,E.W/2); g.add(caja);
  const piso = new THREE.Mesh(new THREE.PlaneGeometry(E.L,E.W), new THREE.MeshLambertMaterial({color:0xcfd4dc}));
  piso.rotation.x = -Math.PI/2; piso.position.set(E.L/2,0,E.W/2); g.add(piso);
  v.cajas.forEach(b => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(b.dx,b.dz,b.dy), new THREE.MeshLambertMaterial({color:b.color}));
    m.position.set(b.x+b.dx/2, b.z+b.dz/2, b.y+b.dy/2); m.userData = b;
    m.add(new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), new THREE.LineBasicMaterial({color:0x222222})));
    g.add(m); r3.mallas.push(m);
  });
  esc.add(g); r3.grupo = g;
  cam.position.set(E.L*1.25, E.H*1.6, E.W*2.6); ctl.target.set(E.L/2, E.H/3, E.W/2); ctl.update();
  const t = {}; v.cajas.forEach(b => t[b.el] = b.color);
  document.getElementById('ley').innerHTML = Object.entries(t).map(([k,col]) => `<span><i style="background:${col}"></i>${k}</span>`).join('');
}
function cerrar3d(){ document.getElementById('modal').style.display = 'none'; }

// ---------------- Tiempo de A a B ----------------
let resaltado = null;
function dibujarCamino(linea, color){
  if (resaltado) mapa.removeLayer(resaltado);
  resaltado = L.polyline(linea, {color: color || '#111', weight:8, opacity:.9, dashArray:'10 8'}).addTo(mapa);
  mapa.fitBounds(resaltado.getBounds(), {padding:[60,60]});
}
const selA = document.getElementById('selA'), selB = document.getElementById('selB');
const opciones = D.puntos.map(p => `<option value="${p.id}">${p.nombre}</option>`).join('');
selA.innerHTML = opciones; selB.innerHTML = opciones;
if (D.puntos.length > 1) selB.value = D.puntos[1].id;
selA.onchange = selB.onchange = calcularAB;
function invertir(){ const t = selA.value; selA.value = selB.value; selB.value = t; calcularAB(); }
function calcularAB(){
  const a = selA.value, b = selB.value, r = document.getElementById('resAB');
  if (a === b){ r.innerHTML = '<span style="color:var(--mut)">Elija dos puntos distintos.</span>'; if (resaltado) mapa.removeLayer(resaltado); return; }
  const d = D.matriz[a+'|'+b];
  if (!d){ r.textContent = 'Sin datos para ese par.'; return; }
  r.innerHTML = `<div class="g"><div class="kpi"><b>${mins(d.min)}</b><span>🚚 Camión</span></div>
    <div class="kpi"><b>${mins(d.min / D.factor_moto)}</b><span>🏍️ Moto</span></div>
    <div class="kpi"><b>${d.km} km</b><span>Distancia</span></div></div>
    <div class="vias"><b>Por:</b> ${d.vias.join(' → ')}</div>`;
  dibujarCamino(d.linea);
}
function verTramo(i,k){
  const t = D.vehiculos[i].tramos[k], d = D.matriz[t.de+'|'+t.a];
  if (d) dibujarCamino(d.linea, D.vehiculos[i].color);
  selA.value = t.de; selB.value = t.a; calcularAB(); if (d) dibujarCamino(d.linea, D.vehiculos[i].color);
}
function abrirMatriz(){ document.getElementById('mmat').style.display = 'flex'; pintarMatriz(); }
function pintarMatriz(){
  const modo = document.querySelector('input[name=vm]:checked').value;
  const val = d => modo === 'k' ? d.km : modo === 'm' ? d.min / D.factor_moto : d.min;
  const todos = Object.values(D.matriz).map(val), max = Math.max(...todos), min = Math.min(...todos);
  const P = D.puntos;
  document.getElementById('tmat').innerHTML = '<thead><tr><th class="r" style="writing-mode:horizontal-tb;transform:none;height:auto">Desde ↓ · Hasta →</th>' +
    P.map(p => `<th>${p.nombre}</th>`).join('') + '</tr></thead><tbody>' +
    P.map(a => `<tr><th class="r">${a.nombre}</th>` + P.map(b => {
      if (a.id === b.id) return '<td style="background:#f0f2f5">—</td>';
      const d = D.matriz[a.id+'|'+b.id]; if (!d) return '<td></td>';
      const x = val(d), f = (x - min) / ((max - min) || 1);
      const fondo = `hsl(${140 - 140*f},70%,${88 - 20*f}%)`;
      return `<td class="c" style="background:${fondo}" title="${a.nombre} → ${b.nombre}"
        onclick="elegirPar(${a.id},${b.id})">${modo === 'k' ? x.toFixed(1) : Math.round(x)}</td>`;
    }).join('') + '</tr>').join('') + '</tbody>';
}
function elegirPar(a,b){ document.getElementById('mmat').style.display = 'none'; selA.value = a; selB.value = b; calcularAB(); }

lista();
calcularAB();
</script></body></html>
"""
