"""
Dashboard Interactivo - Vigilancia Epidemiológica SIVIGILA Tolima
=================================================================
Dashboard con cross-filtering (multifiltro) tipo Power BI / Looker Studio.
Clic en cualquier gráfica filtra todas las demás del mismo evento.

Uso:   python dashboard.py
URL:   http://localhost:8050

Autor: Wilson Andrés Gómez Gutiérrez
"""

import os, json, re, glob
import pandas as pd
import numpy as np
from http.server import HTTPServer, SimpleHTTPRequestHandler

PUERTO = 8050
RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")

CATEGORIAS = {
    "Materno-Perinatal":          {"color": "#E91E63", "c": ["110","113","215","549","551","560","591","740","750"]},
    "Cancer":                     {"color": "#9C27B0", "c": ["115","155"]},
    "ETV y Zoonosis":             {"color": "#FF5722", "c": ["205","210_220","217","228","300","310","330","355","420_430_440","455","580","895"]},
    "Hepatitis e ITS":            {"color": "#FF9800", "c": ["340","850"]},
    "Salud Mental y Violencia":   {"color": "#3F51B5", "c": ["356","453","452","452vi","875"]},
    "Tuberculosis y Respiratorio":{"color": "#607D8B", "c": ["813","345","348","995"]},
    "Inmunoprevenibles":          {"color": "#009688", "c": ["610","620","720","730_710","800","831"]},
    "Otras Enfermedades":         {"color": "#795548", "c": ["298","342","365","450","535","998"]},
}

def cod_num(t):
    m = re.search(r"(\d+)", t); return int(m.group(1)) if m else 9999

def get_cat(nombre):
    k = nombre.replace("evento_","")
    for cat,v in CATEGORIAS.items():
        if k in v["c"]: return cat
    return "Otras Enfermedades"

def get_color(nombre):
    return CATEGORIAS.get(get_cat(nombre),{}).get("color","#607D8B")

def cargar_datos():
    """Carga CSVs y devuelve dict {nombre: {rows:[], nom_eve:str, total:int}}"""
    COLS = ["semana","año","edad_","sexo_","area_","tip_cas_","con_fin_",
            "nmun_resi","nmun_proce","nmun_notif","nom_eve"]
    resultado = {}
    for f in sorted(glob.glob(os.path.join(RUTA,"evento_*.csv"))):
        nombre = os.path.basename(f).replace(".csv","")
        try:
            df = pd.read_csv(f, low_memory=False)
            if len(df) == 0: continue
            cols_ok = [c for c in COLS if c in df.columns]
            sub = df[cols_ok].copy()

            # Normalizar municipio
            for mc in ["nmun_resi","nmun_proce","nmun_notif"]:
                if mc in sub.columns:
                    sub[mc] = sub[mc].astype(str).str.strip().str.title()
                    sub[mc] = sub[mc].replace({"Nan":"","None":"","Nat":""})

            # Sexo legible
            if "sexo_" in sub.columns:
                sub["sexo_"] = pd.to_numeric(sub["sexo_"], errors="coerce")
                sub["sexo_"] = sub["sexo_"].map({1:"Masculino",2:"Femenino",3:"Indeterminado"})

            # Área legible
            if "area_" in sub.columns:
                sub["area_"] = pd.to_numeric(sub["area_"], errors="coerce")
                sub["area_"] = sub["area_"].map({1:"Cabecera",2:"Centro Poblado",3:"Rural"})

            # Tipo de caso legible
            if "tip_cas_" in sub.columns:
                sub["tip_cas_"] = pd.to_numeric(sub["tip_cas_"], errors="coerce")
                sub["tip_cas_"] = sub["tip_cas_"].map({
                    1:"Sospechoso",2:"Probable",3:"Lab.",4:"Clínico",5:"Nexo Epi"})

            # Condición final legible
            if "con_fin_" in sub.columns:
                sub["con_fin_"] = pd.to_numeric(sub["con_fin_"], errors="coerce")
                sub["con_fin_"] = sub["con_fin_"].map({1:"Vivo",2:"Muerto",3:"No sabe"})

            # Grupos de edad
            if "edad_" in sub.columns:
                e = pd.to_numeric(sub["edad_"], errors="coerce")
                sub["edad_g"] = pd.cut(e,
                    bins=[0,5,10,18,30,45,60,200],
                    labels=["0-4","5-9","10-17","18-29","30-44","45-59","60+"],
                    right=False).astype(str).replace("nan","")
            else:
                sub["edad_g"] = ""

            # Nombre evento
            nom_eve = ""
            if "nom_eve" in sub.columns and sub["nom_eve"].notna().any():
                nom_eve = str(sub["nom_eve"].dropna().iloc[0]).strip()

            # Municipio principal
            mun_col = next((c for c in ["nmun_resi","nmun_proce","nmun_notif"] if c in sub.columns and sub[c].replace("","nan").notna().any()), None)
            sub["municipio"] = sub[mun_col].fillna("") if mun_col else ""

            # Semana como int
            if "semana" in sub.columns:
                sub["semana"] = pd.to_numeric(sub["semana"], errors="coerce").fillna(0).astype(int)

            # Año como int
            if "año" in sub.columns:
                sub["año"] = pd.to_numeric(sub["año"], errors="coerce").fillna(0).astype(int)

            # Construir filas compactas — asegurar todas las columnas existen
            for col_req in ["semana","año","edad_g","sexo_","area_","tip_cas_","con_fin_","municipio"]:
                if col_req not in sub.columns:
                    sub[col_req] = None
            final = sub[["semana","año","edad_g","sexo_","area_","tip_cas_","con_fin_","municipio"]].copy()
            final = final.replace([np.nan, None, "nan","None",""], None)
            rows = final.where(pd.notnull(final), None).values.tolist()

            resultado[nombre] = {
                "rows": rows,
                "nom_eve": nom_eve,
                "total": len(rows),
                "cols": ["semana","año","edad_g","sexo_","area_","tip_cas_","con_fin_","municipio"]
            }
        except Exception as e:
            print(f"  Error {nombre}: {e}")
    return resultado


def generar_html(datos):
    nombres = sorted(datos.keys(), key=cod_num)
    primer = nombres[0] if nombres else ""

    # ── SIDEBAR ──────────────────────────────────────────────────
    grupos = {}
    for n in nombres:
        grupos.setdefault(get_cat(n), []).append(n)

    sidebar = ""
    for cat in sorted(grupos):
        color = CATEGORIAS.get(cat,{}).get("color","#607D8B")
        sidebar += f'<div class="nav-group"><div class="nav-group-title" style="color:{color}">{cat}</div>'
        for n in grupos[cat]:
            d = datos[n]
            nom = d["nom_eve"] or n
            corto = (nom[:27]+"…") if len(nom)>27 else nom
            active = "active" if n==primer else ""
            sidebar += (f'<button class="nav-btn {active}" data-tab="{n}" '
                        f'title="{nom}" style="--c:{color}">'
                        f'{corto}<span class="badge">{d["total"]:,}</span></button>')
        sidebar += '</div>'

    # ── CONTENIDO (esqueleto, datos van en JS) ────────────────────
    contenido = ""
    for n in nombres:
        d = datos[n]
        nom = d["nom_eve"] or n
        color = get_color(n)
        display = "flex" if n==primer else "none"
        contenido += f'''
<div id="tab_{n}" class="tab-pane" style="display:{display}">
  <div class="pane-header" style="border-left:4px solid {color}">
    <div>
      <h2>{nom}</h2>
      <p>Tabla: <code>{n}</code></p>
    </div>
    <div class="kpis" id="kpis_{n}"></div>
    <button class="btn-reset" onclick="resetFiltros('{n}')">✕ Limpiar filtros</button>
  </div>
  <div class="filters-bar" id="filters_{n}"></div>
  <div class="charts-grid">
    <div class="chart-card wide"><div class="chart-title">📅 Semana Epidemiológica</div>
      <canvas id="c_semana_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">📍 Top Municipios</div>
      <canvas id="c_mun_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">👤 Grupo de Edad</div>
      <canvas id="c_edad_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">⚥ Sexo</div>
      <canvas id="c_sexo_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">🏘️ Área</div>
      <canvas id="c_area_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">🔬 Tipo de Caso</div>
      <canvas id="c_tipo_{n}"></canvas></div>
    <div class="chart-card"><div class="chart-title">🏥 Condición Final</div>
      <canvas id="c_cond_{n}"></canvas></div>
  </div>
</div>'''

    total_global = sum(d["total"] for d in datos.values())

    # ── DATOS COMPACTOS para JS ───────────────────────────────────
    datos_js = json.dumps(
        {n: {"rows": d["rows"], "cols": d["cols"], "nom_eve": d["nom_eve"], "total": d["total"]}
         for n,d in datos.items()},
        ensure_ascii=False, separators=(",",":")
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Dashboard SIVIGILA Tolima</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;height:100vh;display:flex;flex-direction:column}}
/* HEADER */
.header{{background:linear-gradient(135deg,#1a1a2e,#0f3460);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:30px;flex-shrink:0}}
.header h1{{font-size:1.3em}}
.header p{{font-size:.78em;opacity:.7;margin-top:2px}}
.kpi-global{{display:flex;gap:20px;margin-left:auto}}
.kpi-g{{text-align:center}}.kpi-g .n{{font-size:1.6em;font-weight:700;color:#e94560}}.kpi-g .l{{font-size:.65em;opacity:.65;text-transform:uppercase}}
/* LAYOUT */
.body{{display:flex;flex:1;overflow:hidden}}
/* SIDEBAR */
.sidebar{{width:230px;background:#fff;border-right:1px solid #e0e0e0;overflow-y:auto;flex-shrink:0;padding:8px 0}}
.nav-group{{margin-bottom:2px}}
.nav-group-title{{padding:8px 12px 3px;font-size:.65em;font-weight:800;text-transform:uppercase;letter-spacing:.6px}}
.nav-btn{{display:block;width:100%;padding:6px 12px 6px 16px;border:none;background:0;cursor:pointer;
  font-size:.76em;color:#555;text-align:left;border-left:3px solid transparent;transition:.15s;line-height:1.35}}
.nav-btn:hover{{background:#f5f5f5;color:#111}}
.nav-btn.active{{background:#f0f4ff;color:#0f3460;font-weight:700;border-left-color:var(--c,#2196F3)}}
.badge{{float:right;background:#e8e8e8;color:#666;padding:1px 5px;border-radius:9px;font-size:.8em}}
.nav-btn.active .badge{{background:var(--c,#2196F3);color:#fff}}
/* CONTENT */
.content{{flex:1;overflow-y:auto;padding:20px 24px}}
.tab-pane{{flex-direction:column;gap:16px}}
.pane-header{{display:flex;align-items:flex-start;gap:16px;padding:0 0 14px 14px;border-bottom:1px solid #e8e8e8;margin-bottom:4px;flex-wrap:wrap}}
.pane-header h2{{font-size:1.2em;color:#1a1a2e}}
.pane-header p{{font-size:.8em;color:#777;margin-top:3px}}
.pane-header code{{background:#e8eaf6;padding:2px 6px;border-radius:4px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap}}
.kpi{{background:#fff;border-radius:8px;padding:10px 16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
.kpi .n{{font-size:1.5em;font-weight:700}}.kpi .l{{font-size:.68em;color:#888;text-transform:uppercase}}
.btn-reset{{margin-left:auto;padding:7px 14px;background:#fff;border:1px solid #ddd;border-radius:6px;
  cursor:pointer;font-size:.78em;color:#666;transition:.15s;white-space:nowrap}}
.btn-reset:hover{{background:#ffebee;color:#c62828;border-color:#ef9a9a}}
/* FILTROS ACTIVOS */
.filters-bar{{display:flex;flex-wrap:wrap;gap:6px;padding:6px 0;min-height:28px}}
.filter-chip{{background:#e3f2fd;color:#1565c0;padding:3px 10px 3px 12px;border-radius:20px;
  font-size:.75em;display:flex;align-items:center;gap:6px;cursor:pointer}}
.filter-chip:hover{{background:#ffcdd2;color:#b71c1c}}
.filter-chip span{{opacity:.6;font-size:1.1em}}
/* CHARTS */
.charts-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.chart-card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 6px rgba(0,0,0,.07)}}
.chart-card.wide{{grid-column:1/-1}}
.chart-title{{font-size:.82em;font-weight:600;color:#555;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #f0f0f0}}
canvas{{max-height:240px;cursor:pointer}}
.wide canvas{{max-height:180px}}
@media(max-width:1100px){{.charts-grid{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body>
<div class="header">
  <div><h1>Dashboard de Vigilancia Epidemiológica</h1>
    <p>SIVIGILA — Departamento del Tolima (DANE 73)</p></div>
  <div class="kpi-global">
    <div class="kpi-g"><div class="n">{total_global:,}</div><div class="l">Registros</div></div>
    <div class="kpi-g"><div class="n">{len(datos)}</div><div class="l">Eventos</div></div>
  </div>
</div>
<div class="body">
  <nav class="sidebar">{sidebar}</nav>
  <div class="content" id="content">{contenido}</div>
</div>

<script>
// ── DATOS ────────────────────────────────────────────────────────
const DB = {datos_js};

// Índices de columnas
const CI = {{semana:0,año:1,edad_g:2,sexo_:3,area_:4,tip_cas_:5,con_fin_:6,municipio:7}};

// Estado de filtros por evento: {{evento: {{campo: Set(valores)}}}}
const FILTROS = {{}};
// Instancias de Chart.js activas: {{canvasId: chart}}
const CHARTS = {{}};
// Tabs renderizados
const RENDERED = new Set();

const PALETA = ['#2196F3','#4CAF50','#FF9800','#E91E63','#9C27B0',
                '#00BCD4','#FF5722','#607D8B','#795548','#3F51B5',
                '#8BC34A','#FFC107','#F44336','#009688'];

// ── NAVEGACIÓN ───────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display='none');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab_'+tab).style.display='flex';
    btn.classList.add('active');
    if (!RENDERED.has(tab)) renderEvento(tab);
  }});
}});

// ── FILTRADO ─────────────────────────────────────────────────────
function getFilas(evento) {{
  const rows = DB[evento].rows;
  const f = FILTROS[evento] || {{}};
  if (Object.keys(f).length === 0) return rows;
  return rows.filter(row => {{
    for (const [campo, vals] of Object.entries(f)) {{
      const idx = CI[campo];
      const v = row[idx];
      if (!vals.has(v == null ? null : String(v))) return false;
    }}
    return true;
  }});
}}

function toggleFiltro(evento, campo, valor) {{
  if (!FILTROS[evento]) FILTROS[evento] = {{}};
  if (!FILTROS[evento][campo]) FILTROS[evento][campo] = new Set();
  const s = FILTROS[evento][campo];
  const key = valor == null ? null : String(valor);
  if (s.has(key)) {{ s.delete(key); if (s.size===0) delete FILTROS[evento][campo]; }}
  else s.add(key);
  actualizarTodo(evento);
}}

function resetFiltros(evento) {{
  FILTROS[evento] = {{}};
  actualizarTodo(evento);
}}

// ── RENDER COMPLETO ───────────────────────────────────────────────
function actualizarTodo(evento) {{
  const filas = getFilas(evento);
  renderKPIs(evento, filas);
  renderChips(evento);
  renderSemana(evento, filas);
  renderMunicipios(evento, filas);
  renderEdad(evento, filas);
  renderSexo(evento, filas);
  renderArea(evento, filas);
  renderTipo(evento, filas);
  renderCondicion(evento, filas);
}}

function renderEvento(evento) {{
  RENDERED.add(evento);
  actualizarTodo(evento);
}}

// ── KPIs ─────────────────────────────────────────────────────────
function renderKPIs(evento, filas) {{
  const total = DB[evento].total;
  const filt = filas.length;
  const pct = total>0 ? ((filt/total)*100).toFixed(1) : 100;
  const muertes = filas.filter(r => r[CI.con_fin_]==='Muerto').length;
  document.getElementById('kpis_'+evento).innerHTML = `
    <div class="kpi"><div class="n" style="color:#2196F3">${{filt.toLocaleString()}}</div><div class="l">Registros${{filt<total?' (filtrados)':''}}</div></div>
    <div class="kpi"><div class="n" style="color:#FF9800">${{pct}}%</div><div class="l">Del total</div></div>
    <div class="kpi"><div class="n" style="color:#e94560">${{muertes.toLocaleString()}}</div><div class="l">Fallecidos</div></div>`;
}}

// ── CHIPS DE FILTROS ACTIVOS ──────────────────────────────────────
const LABELS = {{semana:'Semana',año:'Año',edad_g:'Edad',sexo_:'Sexo',
                 area_:'Área',tip_cas_:'Tipo caso',con_fin_:'Cond. final',municipio:'Municipio'}};
function renderChips(evento) {{
  const f = FILTROS[evento] || {{}};
  const bar = document.getElementById('filters_'+evento);
  if (Object.keys(f).length===0) {{ bar.innerHTML='<span style="font-size:.75em;color:#aaa">Haz clic en cualquier gráfica para filtrar</span>'; return; }}
  let html='';
  for (const [campo,vals] of Object.entries(f)) {{
    for (const v of vals) {{
      html+=`<div class="filter-chip" onclick="toggleFiltro('${{evento}}','${{campo}}','${{v}}')">`+
            `${{LABELS[campo]||campo}}: <b>${{v??'(vacío)'}}</b><span>✕</span></div>`;
    }}
  }}
  bar.innerHTML=html;
}}

// ── HELPERS CHART ─────────────────────────────────────────────────
function contarPor(filas, col) {{
  const m={{}};
  filas.forEach(r=>{{const v=r[CI[col]]; if(v==null||v===''||v==='null') return; m[v]=(m[v]||0)+1;}});
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}}

function actualizarOCrear(id, config) {{
  if (CHARTS[id]) {{ CHARTS[id].destroy(); }}
  const ctx = document.getElementById(id);
  if (!ctx) return;
  CHARTS[id] = new Chart(ctx, config);
}}

function colorBarra(campo, valor, evento) {{
  const f = FILTROS[evento]||{{}};
  const activos = f[campo];
  if (!activos||activos.size===0) return '#2196F3';
  return activos.has(String(valor)) ? '#e94560' : '#b0bec5';
}}

function colorDona(campo, labels, evento) {{
  const f = FILTROS[evento]||{{}};
  const activos = f[campo];
  return labels.map((l,i)=>{{
    if (!activos||activos.size===0) return PALETA[i%PALETA.length];
    return activos.has(String(l)) ? PALETA[i%PALETA.length] : PALETA[i%PALETA.length]+'55';
  }});
}}

// ── GRÁFICAS INDIVIDUALES ─────────────────────────────────────────
function renderSemana(ev, filas) {{
  const m={{}};
  filas.forEach(r=>{{ const v=r[CI.semana]; if(v&&v!==0) m[v]=(m[v]||0)+1; }});
  const ks=Object.keys(m).map(Number).sort((a,b)=>a-b);
  const vs=ks.map(k=>m[k]);
  const f=FILTROS[ev]||{{}};
  const act=f.semana;
  const bg=ks.map(k=>(!act||act.size===0)?'#2196F3': act.has(String(k))?'#e94560':'#b0bec5');
  actualizarOCrear('c_semana_'+ev, {{type:'bar',data:{{labels:ks.map(k=>'SE '+k),datasets:[{{data:vs,backgroundColor:bg,borderRadius:3}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
      scales:{{x:{{grid:{{display:false}}}},y:{{beginAtZero:true}}}},
      onClick:(_,els)=>{{ if(els[0]) toggleFiltro(ev,'semana',ks[els[0].index]); }}
    }}}});
}}

function renderMunicipios(ev, filas) {{
  const pares = contarPor(filas,'municipio').slice(0,12);
  const ls=pares.map(p=>p[0]), vs=pares.map(p=>p[1]);
  const f=FILTROS[ev]||{{}};const act=f.municipio;
  const bg=ls.map(l=>(!act||act.size===0)?'#4CAF50':act.has(String(l))?'#e94560':'#b0bec5');
  actualizarOCrear('c_mun_'+ev, {{type:'bar',data:{{labels:ls,datasets:[{{data:vs,backgroundColor:bg,borderRadius:3}}]}},
    options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
      scales:{{x:{{beginAtZero:true}},y:{{grid:{{display:false}}}}}},
      onClick:(_,els)=>{{ if(els[0]) toggleFiltro(ev,'municipio',ls[els[0].index]); }}
    }}}});
}}

function renderEdad(ev, filas) {{
  const orden=["0-4","5-9","10-17","18-29","30-44","45-59","60+"];
  const m={{}};filas.forEach(r=>{{const v=r[CI.edad_g];if(v&&v!=='')m[v]=(m[v]||0)+1;}});
  const ls=orden.filter(k=>m[k]>0), vs=ls.map(k=>m[k]);
  const f=FILTROS[ev]||{{}};const act=f.edad_g;
  const bg=ls.map(l=>(!act||act.size===0)?'#FF9800':act.has(l)?'#e94560':'#b0bec5');
  actualizarOCrear('c_edad_'+ev, {{type:'bar',data:{{labels:ls,datasets:[{{data:vs,backgroundColor:bg,borderRadius:3}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
      scales:{{x:{{grid:{{display:false}}}},y:{{beginAtZero:true}}}},
      onClick:(_,els)=>{{ if(els[0]) toggleFiltro(ev,'edad_g',ls[els[0].index]); }}
    }}}});
}}

function renderDona(ev, campo, canvasId, titulo) {{
  const pares = contarPor(getFilas(ev), campo);
  if (pares.length===0) return;
  const ls=pares.map(p=>p[0]), vs=pares.map(p=>p[1]);
  const bg=colorDona(campo,ls,ev);
  actualizarOCrear(canvasId, {{type:'doughnut',data:{{labels:ls,datasets:[{{data:vs,backgroundColor:bg,borderWidth:2,borderColor:'#fff'}}]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{position:'bottom',labels:{{boxWidth:11,padding:8,font:{{size:11}}}}}}}},
      onClick:(_,els)=>{{ if(els[0]) toggleFiltro(ev,campo,ls[els[0].index]); }}
    }}}});
}}

function renderSexo(ev, filas)     {{ renderDona(ev,'sexo_',    'c_sexo_'+ev);   }}
function renderArea(ev, filas)     {{ renderDona(ev,'area_',    'c_area_'+ev);   }}
function renderTipo(ev, filas)     {{ renderDona(ev,'tip_cas_', 'c_tipo_'+ev);   }}
function renderCondicion(ev,filas) {{ renderDona(ev,'con_fin_', 'c_cond_'+ev);   }}

// ── ARRANCAR PRIMER TAB ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', ()=>{{
  const primero = document.querySelector('.nav-btn.active')?.dataset.tab;
  if (primero) renderEvento(primero);
}});
</script>
</body>
</html>"""


class Handler(SimpleHTTPRequestHandler):
    html = ""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type","text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(Handler.html.encode("utf-8"))
    def log_message(self, *a): pass


def main():
    print("="*55)
    print("  DASHBOARD INTERACTIVO SIVIGILA - TOLIMA")
    print("="*55)
    print("\n  Cargando datos...")
    datos = cargar_datos()
    total = sum(d["total"] for d in datos.values())
    print(f"  -> {len(datos)} eventos | {total:,} registros")
    print("  Generando dashboard...")
    html = generar_html(datos)
    Handler.html = html

    # Guardar HTML estático también
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(html_path,"w",encoding="utf-8") as f: f.write(html)

    print(f"\n  ✓ Dashboard listo en: http://localhost:{PUERTO}")
    print("  Presiona Ctrl+C para detener\n")
    srv = HTTPServer(("0.0.0.0", PUERTO), Handler)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n  Servidor detenido."); srv.server_close()

if __name__ == "__main__":
    main()
