"""HTML-карта «конус обзора» по результату spike_window.py.

python pipeline/render_cone.py data/derived/spike_way_123.json mockups/spike-cone.html
"""
import json
import math
import sys

R = 6_371_000.0


def dest(lat, lon, az, d):
    a = math.radians(az)
    return (lat + d * math.cos(a) / R * 180 / math.pi,
            lon + d * math.sin(a) / (R * math.cos(math.radians(lat))) * 180 / math.pi)


def main(src, out):
    d = json.load(open(src))
    rays = {}
    for side, f in d["facades"].items():
        for fl, v in f["floors"].items():
            lines = []
            for az, p in v["profile"].items():
                az = int(az)
                if p["sea"]:
                    L, kind = 2500, "sea"
                elif p["kind"] == "building":
                    L, kind = max(p["dist"], 8), "building"
                else:
                    L, kind = min(p["dist"], 2500), "terrain"
                lines.append({"to": dest(f["eye_lat"], f["eye_lon"], az, L), "k": kind, "az": az,
                              "dist": p["dist"], "angle": p["angle"]})
            rays[f"{side}|{fl}"] = {"eye": [f["eye_lat"], f["eye_lon"]], "lines": lines,
                                     "sea": v["sea_share"], "sun": v["sun"], "eye_m": v["eye_m"]}
    html = TEMPLATE.replace("__DATA__", json.dumps({"hotel": d["hotel"], "rays": rays,
                                                     "nearby": d["buildings_nearby"]},
                                                    ensure_ascii=False))
    open(out, "w").write(html)
    print("→", out)


TEMPLATE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Конус обзора — проверка на реальных данных</title>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--brand:#0E41D2;--sec:#E3EBFD;--ink:#2D3137;--muted:#868686;--line:#E5E5E5}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Manrope,system-ui,sans-serif;color:var(--ink);display:grid;grid-template-columns:360px 1fr;height:100vh}
@media(max-width:800px){body{grid-template-columns:1fr;grid-template-rows:auto 60vh}}
aside{padding:18px;overflow:auto;border-right:1px solid var(--line)}
h1{font-size:20px;font-weight:800;margin:0 0 4px}.m{color:var(--muted);font-size:12px}
.seg{display:flex;gap:4px;flex-wrap:wrap;margin:6px 0 12px}.seg button{border:1px solid var(--line);background:#fff;border-radius:8px;padding:5px 10px;font:600 13px Manrope;cursor:pointer}
.seg button.on{background:var(--brand);border-color:var(--brand);color:#fff}
.big{font-size:28px;font-weight:800;color:var(--brand)}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:4px;border-bottom:1px solid var(--line);text-align:left}
.lg span{display:inline-flex;align-items:center;gap:6px;margin-right:12px;font-size:12px}.lg b{width:14px;height:4px;border-radius:2px;display:inline-block}
#map{height:100%}
</style></head><body>
<aside>
<h1 id="name"></h1><div class="m" id="meta"></div>
<div style="margin-top:14px;font-weight:600">Сторона окон</div><div class="seg" id="sides"></div>
<div style="font-weight:600">Этаж</div><div class="seg" id="floors"></div>
<div class="m">Видно моря в секторе обзора окна (±80°)</div><div class="big" id="sea"></div>
<div class="lg" style="margin:10px 0"><span><b style="background:#3D8BFD"></b>луч видит море</span><span><b style="background:#CE2121"></b>упёрся в дом</span><span><b style="background:#A08C6A"></b>рельеф</span></div>
<div style="font-weight:600;margin-top:12px">Закат из этого окна (15-е число)</div>
<table id="sun"></table>
<p class="m" id="note"></p>
</aside>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D=__DATA__;const M=['','янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];
const H=D.hotel;document.getElementById('name').textContent=H.name||'Отель';
document.getElementById('meta').textContent=`${H.osm} · земля ${H.ground_m} м над морем · ${H.levels} эт. (${H.levels_src})`;
const N=D.nearby;document.getElementById('note').textContent=`Зданий в радиусе 700 м: ${N.count}. Высота из тега height: ${N.height}, из этажности: ${N.levels}, оценка по типу: ${N.default}.`;
const keys=Object.keys(D.rays);const sides=[...new Set(keys.map(k=>k.split('|')[0]))];
const SN={N:'север',E:'восток',S:'юг',W:'запад'};
let side=sides.includes('W')?'W':sides[0], floor=null;
const map=L.map('map').setView([H.lat,H.lon],15);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
let layer=L.layerGroup().addTo(map);
function floorsOf(s){return keys.filter(k=>k.startsWith(s+'|')).map(k=>+k.split('|')[1]).sort((a,b)=>a-b)}
function draw(){
 const fl=floorsOf(side);if(!fl.includes(floor))floor=fl[fl.length-1];
 document.getElementById('sides').innerHTML=sides.map(s=>`<button class="${s===side?'on':''}" data-s="${s}">${SN[s]}</button>`).join('');
 document.getElementById('floors').innerHTML=fl.map(f=>`<button class="${f===floor?'on':''}" data-f="${f}">${f}</button>`).join('');
 document.querySelectorAll('#sides button').forEach(b=>b.onclick=()=>{side=b.dataset.s;draw()});
 document.querySelectorAll('#floors button').forEach(b=>b.onclick=()=>{floor=+b.dataset.f;draw()});
 const R=D.rays[side+'|'+floor];layer.clearLayers();
 const col={sea:'#3D8BFD',building:'#CE2121',terrain:'#A08C6A'};
 for(const l of R.lines){L.polyline([R.eye,l.to],{color:col[l.k],weight:l.k==='building'?2.5:1.5,opacity:.75}).bindTooltip(`${l.az}° · ${l.k==='sea'?'море':l.k==='building'?'дом в '+l.dist+' м':'рельеф, '+l.dist+' м'} · угол ${l.angle}°`).addTo(layer)}
 L.circleMarker(R.eye,{radius:6,color:'#0E41D2',fillColor:'#fff',fillOpacity:1,weight:3}).bindTooltip(`окно, глаза на ${R.eye_m} м над морем`).addTo(layer);
 document.getElementById('sea').textContent=Math.round(R.sea*100)+'%';
 document.getElementById('sun').innerHTML='<tr><th>месяц</th><th>закат</th><th>скроется</th><th>за чем</th></tr>'+R.sun.map(s=>`<tr><td>${M[s.month]}</td><td>${s.sunset_astro}</td><td>${s.sun_hidden_at||'—'}</td><td>${s.hidden_by==='sea'?'🌊 садится в море':s.hidden_by==='building'?'дом, −'+s.minutes_earlier+' мин':s.hidden_by==='terrain'?'горы, −'+s.minutes_earlier+' мин':s.hidden_by||'—'}</td></tr>`).join('');
}
draw();
</script></body></html>"""

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
