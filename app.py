"""
Allsvenskan Analytics — Streamlit
pip install streamlit plotly pandas
streamlit run app.py
"""
import json, math, io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

st.set_page_config(
    page_title="Allsvenskan Analytics", page_icon="⚽",
    layout="wide", initial_sidebar_state="expanded",
)

st.markdown("""<style>
[data-testid="stSidebar"]          { background:#0a0f1a; }
[data-testid="stAppViewContainer"] { background:#0d1829; }
[data-testid="stHeader"]           { background:transparent; }
.main .block-container             { padding-top:1rem; padding-bottom:2rem; }
h1,h2,h3                           { color:#e2e8f0 !important; }
div[data-testid="metric-container"] {
    background:#111d30; border:1px solid #1a2f50; border-radius:8px; padding:10px 14px;
}
div[data-testid="metric-container"] > label { color:#4a6080 !important; font-size:11px; }
div[data-testid="metric-container"] > div   { color:#e2e8f0 !important; }
.stSelectbox label,.stMultiSelect label,.stRadio label { color:#7090b0 !important; font-size:11px; }
div[role="radiogroup"] label { color:#a0c0e0 !important; }
.badge {
    display:inline-block; font-size:9px; font-weight:700;
    letter-spacing:0.08em; padding:3px 9px; border-radius:4px;
    text-transform:uppercase; margin-right:5px;
}
.sl-section   { margin-bottom:20px; }
.sl-sec-hdr   { display:flex; align-items:center; gap:8px; margin-bottom:10px;
                 padding-bottom:4px; border-bottom:2px solid #1a2f50; }
.sl-sec-title { font-size:11px; font-weight:800; letter-spacing:0.14em; text-transform:uppercase; }
.sl-sec-badge { font-size:10px; font-weight:800; padding:2px 7px; border-radius:3px; }
.sl-row {
    display:grid; grid-template-columns:1fr 64px 1fr 36px;
    align-items:center; gap:8px; padding:4px 0;
    border-bottom:1px solid #0f1829;
}
.sl-row:last-child { border-bottom:none; }
.sl-lbl       { font-size:11px; color:#7090b0; }
.sl-val       { font-size:12px; font-weight:700; color:#c0d8f0; text-align:right; }
.sl-bar-wrap  { background:#1a2f50; border-radius:3px; height:6px; overflow:hidden; }
.sl-bar-fill  { height:6px; border-radius:3px; }
.sl-pct       { font-size:10px; font-weight:800; text-align:center;
                 padding:1px 4px; border-radius:3px; min-width:30px; }
.player-hdr   { background:#0a1525; border:1px solid #1a3050;
                 border-radius:12px; padding:18px 22px; margin-bottom:20px; }
</style>""", unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────────────────────
def load_data():
    try:
        with open("data.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("⚠️  Kör python process_data.py för att generera data.json")
        st.stop()

DB = load_data()
# Seasons with player data OR match log files
import os as _os
SEASONS_AVAIL = sorted(
    [y for y in DB["seasons"] if DB["seasons"][y].get("players")] +
    [y for y in ["2024","2023","2022","2001"] 
     if y not in DB["seasons"] and _os.path.exists(f"match_data_{y}.json")],
    reverse=True
)

def f(v): return v if isinstance(v,(int,float)) and not math.isnan(v) else 0

def pos_group(pos):
    if not pos: return "U"
    p = str(pos).split(",")[0].strip()
    return {"GK":"GK","DF":"DF","MF":"MF","FW":"FW"}.get(p,"U")

def players_df(season):
    ps = DB["seasons"].get(season,{}).get("players",[])
    df = pd.DataFrame(ps)
    if df.empty: return df
    df["pos_group"] = df["pos"].apply(pos_group)
    df["squad"]     = df["squad"].fillna("")
    return df

def squads_df(season):
    sq = DB["seasons"].get(season,{}).get("squads",[])
    return pd.DataFrame(sq) if sq else pd.DataFrame()

def nats_data(season):
    return DB["seasons"].get(season,{}).get("nationalities",[])

def domare_data(season):
    return DB["seasons"].get(season,{}).get("domare",[])


def league_avg(season, pos_group_key="ALL"):
    return DB["seasons"].get(season,{}).get("league_averages",{}).get(pos_group_key,{})

# ── Alla radarmått ─────────────────────────────────────────────────────────────
ALL_RADAR = {
    "Mål/90":          ("glsPer90",  1.5,  False),
    "Assist/90":       ("astPer90",  0.6,  False),
    "Skott/90":        ("shPer90",   6.0,  False),
    "SoT%":            ("sotPct",    70,   False),
    "Mål/Skott":       ("gPerSh",    0.3,  False),
    "xG/90":           ("xGpx",      1.5,  False),
    "xA/90":           ("xApx",      0.5,  False),
    "xG vs Mål":       ("gMinusXG",  5.0,  False),
    "xP/90":           ("xPpx",      15,   False),
    "Brytningar/90":   ("intPer90",  4.0,  False),
    "Tacklingar/90":   ("tklWPer90", 4.0,  False),
    "Inlägg":     ("crs",       80,   False),
    "Frisparkar/90":   ("fldPer90",  4.0,  False),
    "Felspel/90":      ("flsPer90",  3.0,  True ),
    "SoT/90":          ("sotPer90",  3.0,  False),
    "Offside":         ("off",       20,   True ),
    # Passningar (från extra-fil)
    "Passn.%":         ("pass_pct",        100,  False),
    "Prog.pass/90":    ("prog_pass_p90",   20,   False),
    "Framåtpass%":     ("fwd_pass_pct",    100,  False),
    "Långa pass":      ("long_pass",       200,  False),
    "Genomskärare":    ("through_balls",   30,   False),
    "Nyckelpass/90":   ("key_passes_p90",  5,    False),
    # Löpningar & dueljer
    "Återerövr./90":   ("recoveries_p90", 15,   False),
    "Prog.löpn./90":   ("prog_carries_p90",10,  False),
    "Luftduell%":      ("headers_pct",     100,  False),
    "Närkamp%":        ("np_duels_pct",    100,  False),
    # Målchanser (2026)
    "Målchanser/90":   ("chances_p90",     10,   False),
    "Hockeyast./90":   ("second_ast_p90",  2,    False),
    "Räddn%  (MV)":    ("gkSavePct", 100,  False),
    "IM/90  (MV)":     ("gkGA90",    3.0,  True ),
    "Nollor%  (MV)":   ("gkCSPct",   100,  False),
    "Räddningar (MV)": ("gkSaves",   200,  False),
    "Vinster (MV)":    ("gkW",       30,   False),
}

DEFAULT_RADAR = {
    "GK": ["Räddn%  (MV)","IM/90  (MV)","Nollor%  (MV)","Räddningar (MV)","Vinster (MV)"],
    "DF": ["Brytningar/90","Tacklingar/90","Passn.%","Återerövr./90","Luftduell%","Mål/90"],
    "MF": ["Mål/90","Assist/90","xG/90","xA/90","Passn.%","Prog.pass/90","Återerövr./90"],
    "FW": ["Mål/90","Assist/90","xG/90","xA/90","Skott/90","SoT%","Mål/Skott"],
    "U":  ["Mål/90","Assist/90","Skott/90","Brytningar/90","Tacklingar/90"],
}

# ── Percentilhjälpare ──────────────────────────────────────────────────────────
def pct_val(v, mx, inv=False, pct_dict=None, key=None):
    fv = f(v)
    if pct_dict and key and key in pct_dict:
        stored = int(pct_dict[key])
        # Use stored percentile if it's non-zero OR if actual value is also 0
        if stored > 0 or fv == 0:
            return stored
    # Fall back to direct calculation
    p = min(round((fv / max(mx, 0.001)) * 100), 100)
    return max(0, 100 - p if inv else p)

def pct_color(p):
    if p>=85: return "#00e8c8"
    if p>=65: return "#30c060"
    if p>=40: return "#f0a030"
    return "#e03030"

def pct_bg(p):
    if p>=85: return "#0a2a28"
    if p>=65: return "#0a2a1a"
    if p>=40: return "#2a1e00"
    return "#2a0e0e"

def bar_css(p):
    if p>=85: return "linear-gradient(90deg,#009070,#00e8c8)"
    if p>=65: return "linear-gradient(90deg,#1a7a40,#30c060)"
    if p>=40: return "linear-gradient(90deg,#a06010,#f0a030)"
    return "linear-gradient(90deg,#8a1a1a,#e03030)"

def pos_badge_html(pos):
    g = pos_group(pos)
    s = {"GK":("15153a","7080ff"),"DF":("0e2a1a","40d080"),
         "MF":("1a1800","d0a040"),"FW":("2a0e0e","ff6060"),"U":("1a2540","8090a0")}
    bg,co = s.get(g,("1a2540","8090a0"))
    return f'<span class="badge" style="background:#{bg};color:#{co}">{g}</span>'

def fmt_val(v, key=""):
    if v == 0: return "—"
    if key in ("sotPct","gkSavePct","gkCSPct"): return f"{v:.1f}%"
    if key in ("glsPer90","astPer90","shPer90","sotPer90","intPer90",
               "tklWPer90","flsPer90","fldPer90","crsPer90","xGpx","xApx",
               "gPerSh","gPerSoT","gkGA90","gMinusXG"): return f"{v:.2f}"
    if key in ("min",): return f"{int(v):,}".replace(",",".")
    return str(int(v)) if v == int(v) else f"{v:.2f}"

# ── Radar chart med ligasnitt ─────────────────────────────────────────────────
def radar_chart(players_data, chosen_metrics, season, show_avg=True):
    """players_data = [(name, p_dict, color_override), ...]"""
    if not players_data or not chosen_metrics: return None

    colors = ["#3a80ff","#00e8c8","#f0a030","#e05050","#a050e0","#ff8c00"]
    fig = go.Figure()
    labels = chosen_metrics + [chosen_metrics[0]]

    for i, item in enumerate(players_data):
        name, p, *rest = item
        col = rest[0] if rest else colors[i % len(colors)]
        r,g,b = int(col[1:3],16), int(col[3:5],16), int(col[5:7],16)
        pcts = []
        for m in chosen_metrics:
            key, mx, inv = ALL_RADAR[m]
            pcts.append(pct_val(p.get(key,0), mx, inv, p.get("pct"), key))

        fig.add_trace(go.Scatterpolar(
            r=pcts+[pcts[0]], theta=labels, fill="toself",
            fillcolor=f"rgba({r},{g},{b},0.12)",
            line=dict(color=col, width=2.5),
            name=name,
            hovertemplate="%{theta}<br>Percentil: %{r:.0f}<extra>"+name+"</extra>",
        ))

    # ── Ligasnitt som referens
    if show_avg and season:
        pg_first = pos_group(players_data[0][1].get("pos",""))
        avg_d    = league_avg(season, pg_first)
        if avg_d:
            avg_pcts = []
            for m in chosen_metrics:
                key, mx, inv = ALL_RADAR[m]
                v = avg_d.get(key, 0)
                avg_pcts.append(pct_val(v, mx, inv))
            fig.add_trace(go.Scatterpolar(
                r=avg_pcts+[avg_pcts[0]], theta=labels, fill="toself",
                fillcolor="rgba(150,150,150,0.06)",
                line=dict(color="#3a4a60", width=1.5, dash="dot"),
                name=f"Liigasnitt ({pg_first})",
                hovertemplate="%{theta}<br>Snitt: %{r:.0f}<extra>Ligasnitt</extra>",
            ))

    fig.update_layout(
        polar=dict(
            bgcolor="#080e1c",
            radialaxis=dict(visible=False, range=[0,100]),
            angularaxis=dict(
                linecolor="#1a2540", gridcolor="#1a2540",
                tickfont=dict(color="#5070a0", size=11),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#7090b0"),
        legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)",
                    orientation="h", yanchor="bottom", y=-0.15, x=0.5, xanchor="center"),
        margin=dict(l=40,r=40,t=30,b=50),
        height=380,
    )
    return fig

# ── Scout Lab spelarpanel ──────────────────────────────────────────────────────
def sl_row_html(label, value, pct_v, avg_val=None):
    pc  = pct_color(pct_v)
    pbg = pct_bg(pct_v)
    bc  = bar_css(pct_v)
    avg_str = f'<span style="font-size:9px;color:#3a5070;margin-left:4px">⌀{avg_val}</span>' if avg_val else ""
    return f"""<div class="sl-row">
  <span class="sl-lbl">{label}</span>
  <span class="sl-val">{value}{avg_str}</span>
  <div class="sl-bar-wrap"><div class="sl-bar-fill" style="width:{pct_v}%;background:{bc}"></div></div>
  <span class="sl-pct" style="color:{pc};background:{pbg}">{pct_v}</span>
</div>"""

def sec_html(title, color, rows, avg_pct):
    pc=pct_color(avg_pct); pbg=pct_bg(avg_pct)
    return f"""<div class="sl-section">
  <div class="sl-sec-hdr">
    <span class="sl-sec-title" style="color:{color}">{title}</span>
    <span class="sl-sec-badge" style="color:{pc};background:{pbg}">{avg_pct}</span>
  </div>{"".join(rows)}</div>"""

def sec_avg(rows_pcts): 
    v = [p for p in rows_pcts if p > 0]
    return round(sum(v)/len(v)) if v else 0

def scout_panel(p, season, show_avg_vals=True):
    name=p.get("name",""); squad=p.get("squad",""); pos=p.get("pos","")
    nation=p.get("nation",""); age=p.get("age",""); mn=int(p.get("min",0))
    pg=pos_group(pos); is_ifk=squad=="IFK Göteborg"; pd_=p.get("pct",{})
    has_xg = f(p.get("xG",0)) > 0 or f(p.get("xGpx",0)) > 0
    has_xp = f(p.get("xP",0)) > 0 or f(p.get("xPpx",0)) > 0

    # Avg vals for display
    avg_d = league_avg(season, pg) if show_avg_vals else {}
    def av(key, decimals=2, pct=False):
        v = avg_d.get(key,0)
        if not v: return None
        if pct: return f"{v:.1f}%"
        return f"{v:.{decimals}f}" if decimals else str(int(v))

    squad_badge = (
        '<span class="badge" style="background:#0d2050;color:#60a0ff">IFK Göteborg</span>'
        if is_ifk else
        f'<span class="badge" style="background:#0e1f35;color:#5090d0">{squad}</span>'
    )
    xg_badge = (
        '<span class="badge" style="background:#0a2518;color:#20c060">xG</span>'
        if has_xg else ""
    )
    xp_badge = (
        '<span class="badge" style="background:#0a1830;color:#4090e0">xP</span>'
        if has_xp else ""
    )
    cup_badge = (
        '<span class="badge" style="background:#1a1000;color:#c09020">CUPEN</span>'
        if p.get("cup") else ""
    )
    st.markdown(f"""<div class="player-hdr">
    <div style="font-size:26px;font-weight:900;color:#e2e8f0;letter-spacing:-0.03em;margin-bottom:10px;">{name}</div>
    <div>{pos_badge_html(pos)}{squad_badge}
    <span class="badge" style="background:#0f1829;color:#4a6080">{pos}</span>
    <span class="badge" style="background:#0f1829;color:#4a6080">{nation}</span>
    <span class="badge" style="background:#0f1829;color:#4a6080">{mn:,} MIN</span>
    <span class="badge" style="background:#0f1829;color:#4a6080">{age} ÅR</span>
    {xg_badge}{xp_badge}{cup_badge}</div>
    </div>""".replace(",","."), unsafe_allow_html=True)

    is_gk = pg == "GK"

    def row(lbl, key, mx, inv=False, fmt_key=None):
        v   = f(p.get(key,0))
        pv  = pct_val(v, mx, inv, pd_, key)
        val = fmt_val(v, fmt_key or key)
        avg = av(key, 2) if show_avg_vals else None
        return sl_row_html(lbl, val, pv, avg), pv

    if is_gk:
        gk_def = [
            row("Räddningar %",  "gkSavePct", 100, False),
            row("Insläppta/90",  "gkGA90",    3,   True),
            row("Räddningar",    "gkSaves",   200, False),
            row("SoT emot",      "gkSoTA",    200, True),
            row("Nollor",        "gkCS",      20,  False),
            row("Nollor %",      "gkCSPct",   100, False),
        ]
        wl_def = [
            row("Vinster",   "gkW",  30, False),
            row("Oavgjort",  "gkD",  15, False),
            row("Förluster", "gkL",  30, True),
        ]
        disc_def = [
            row("Gula kort", "crdY", 12, True),
            row("Röda kort", "crdR",  3, True),
        ]
        html = sec_html("Målvakt","#00e8c8", [r[0] for r in gk_def], sec_avg([r[1] for r in gk_def]))
        html+= sec_html("Resultat","#7080ff", [r[0] for r in wl_def], sec_avg([r[1] for r in wl_def]))
        html+= sec_html("Disciplin","#e05050",[r[0] for r in disc_def],sec_avg([r[1] for r in disc_def]))
        st.markdown(html, unsafe_allow_html=True)
    else:
        atk = [
            row("Mål",          "gls",     20,  False),
            row("Mål/90",       "glsPer90",1.5, False),
            row("Assist",       "ast",     15,  False),
            row("Assist/90",    "astPer90",0.6, False),
            row("Skott",        "sh",      100, False),
            row("SoT",          "sot",     50,  False),
            row("SoT %",        "sotPct",  70,  False),
            row("Skott/90",     "shPer90", 6,   False),
            row("Mål/Skott",    "gPerSh",  0.3, False),
        ]
        xg_rows = []
        has_xp = f(p.get("xP",0)) > 0 or f(p.get("xPpx",0)) > 0
        if has_xg or has_xp:
            xg_rows = [
                row("xG",             "xG",       20,   False),
                row("xG/90",          "xGpx",     1.5,  False),
                row("xA",             "xA",       15,   False),
                row("xA/90",          "xApx",     0.5,  False),
                row("xP",             "xP",        20,  False),
                row("xP/90",          "xPpx",     15,   False),
                row("Mål vs xG",      "gMinusXG", 5,    False),
                row("Assist vs xA",   "aMinusXA", 5,    False),
            ]
        def_ = [
            row("Brytningar",   "int",      60,  False),
            row("Bryt./90",     "intPer90", 4,   False),
            row("Tacklingar",   "tklW",     80,  False),
            row("Tackl./90",    "tklWPer90",4,   False),
            row("Inlägg",  "crs",      80,  False),
        ]
        duo = [
            row("Frisparkar vunna","fld",    100, False),
            row("Frispark./90",   "fldPer90",5,  False),
            row("Felspel/90",     "flsPer90",3,  True),
            row("Offside",        "off",     20,  True),
        ]
        # Extra passningsstatistik
        pass_rows = []
        if f(p.get("pass_total",0)) > 0:
            pass_rows = [
                row("Passningar",     "pass_total",  2000, False),
                row("Passningsprocent","pass_pct",    100, False),
                row("Framåtpassn.",   "fwd_pass",    500,  False),
                row("Framåt%",        "fwd_pass_pct",100,  False),
                row("Prog. pass",     "prog_pass",   500,  False),
                row("Prog. pass/90",  "prog_pass_p90",20,  False),
                row("Långa pass",     "long_pass",   200,  False),
                row("Genomskärare",   "through_balls",30,  False),
            ]
        # Löpningar & återerövringar
        run_rows = []
        if f(p.get("recoveries",0)) > 0 or f(p.get("prog_carries",0)) > 0:
            run_rows = [
                row("Återerövringar",  "recoveries",    200, False),
                row("Åter./90",        "recoveries_p90", 15, False),
                row("Prog. löpningar", "prog_carries",  200, False),
                row("Prog. löpn./90",  "prog_carries_p90",10,False),
                row("Acc. löpningar",  "acc_carries",   100, False),
            ]
        # Luftdueller
        head_rows = []
        if f(p.get("headers_won",0)) > 0:
            head_rows = [
                row("Luftdueller vunna","headers_won", 200, False),
                row("Luftduell%",       "headers_pct", 100, False),
                row("Närkamp vunna",    "np_duels",    200, False),
                row("Närkamp%",         "np_duels_pct",100, False),
            ]
        disc = [
            row("Gula kort","crdY",12,True),
            row("Röda kort","crdR", 3,True),
        ]
        col1,col2 = st.columns(2)
        with col1:
            html = sec_html("Anfall","#f0a030",[r[0] for r in atk],sec_avg([r[1] for r in atk]))
            if xg_rows and (has_xg or has_xp):
                html+=sec_html("Expected Goals","#20c060",[r[0] for r in xg_rows],sec_avg([r[1] for r in xg_rows]))
            html+=sec_html("Disciplin","#e05050",[r[0] for r in disc],sec_avg([r[1] for r in disc]))
            st.markdown(html, unsafe_allow_html=True)
        with col2:
            html = sec_html("Försvar","#00e8c8",[r[0] for r in def_],sec_avg([r[1] for r in def_]))
            html+=sec_html("Dueller & Övrigt","#a050e0",[r[0] for r in duo],sec_avg([r[1] for r in duo]))
            if pass_rows:
                html+=sec_html("Passningar","#3a80ff",[r[0] for r in pass_rows],sec_avg([r[1] for r in pass_rows]))
            if run_rows:
                html+=sec_html("Löpningar & Återerövringar","#00c8a0",[r[0] for r in run_rows],sec_avg([r[1] for r in run_rows]))
            if head_rows:
                html+=sec_html("Luftdueller","#8060d0",[r[0] for r in head_rows],sec_avg([r[1] for r in head_rows]))
            st.markdown(html, unsafe_allow_html=True)

    # Cup stats om de finns
    if p.get("cup"):
        with st.expander("📋 Svenska Cupen — statistik"):
            cup = p["cup"]
            cup_cols = st.columns(5)
            for col_el, (lbl,key) in zip(cup_cols, [
                ("Matcher","mp"),("Mål","gls"),("Assist","ast"),
                ("Skott","sh"),("Min","min")
            ]):
                col_el.metric(lbl, int(cup.get(key,0)))

# ── Radar-konfigurator ─────────────────────────────────────────────────────────
def radar_config(key, pg="MF"):
    default = [m for m in DEFAULT_RADAR.get(pg, DEFAULT_RADAR["U"]) if m in ALL_RADAR]
    show_avg = st.checkbox("Visa ligasnitt i radar", value=True, key=key+"_avg")
    chosen = st.multiselect(
        "Välj statistikaxlar (3–8)",
        list(ALL_RADAR.keys()),
        default=default,
        key=key,
    )
    return chosen, show_avg

# SCOUTING REPORT GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

SECTION_METRICS = {
    "GK": {
        "Räddning":   [("Räddn. %",  "gkSavePct",  100, False),
                       ("Nollor %",  "gkCSPct",    100, False),
                       ("Räddningar","gkSaves",    200, False)],
        "Mål emot":   [("IM/90",     "gkGA90",      3,  True ),
                       ("SoT emot",  "gkSoTA",     200, True )],
        "Spelartid":  [("Minuter",   "min",       2700, False),
                       ("Matcher",   "mp",           30, False)],
    },
    "DF": {
        "Försvar":    [("Bryt./90",  "intPer90",    4, False),
                       ("Tackl./90", "tklWPer90",   4, False),
                       ("Krossn.",   "crs",         80, False)],
        "Anfall":     [("Mål/90",    "glsPer90",  0.5, False),
                       ("Assist/90", "astPer90",  0.4, False),
                       ("xA/90",     "xApx",      0.4, False)],
        "Disciplin":  [("Gula kort", "crdY",       12, True ),
                       ("Felspel/90","flsPer90",    3, True )],
    },
    "MF": {
        "Anfall":     [("Mål/90",    "glsPer90",  1.0, False),
                       ("Assist/90", "astPer90",  0.6, False),
                       ("xG/90",     "xGpx",      1.0, False),
                       ("xA/90",     "xApx",      0.5, False)],
        "Passning":   [("Skott/90",  "shPer90",   4.0, False),
                       ("SoT%",      "sotPct",     70, False),
                       ("xP/90",     "xPpx",       15, False)],
        "Försvar":    [("Bryt./90",  "intPer90",   4, False),
                       ("Tackl./90", "tklWPer90",  4, False),
                       ("Frispk/90", "fldPer90",   4, False)],
        "Disciplin":  [("Gula kort", "crdY",       12, True ),
                       ("Felspel/90","flsPer90",    3, True )],
    },
    "FW": {
        "Målscoring": [("Mål/90",    "glsPer90",  1.5, False),
                       ("xG/90",     "xGpx",      1.5, False),
                       ("Mål vs xG", "gMinusXG",   5, False),
                       ("Skott/90",  "shPer90",    6, False)],
        "Kvalitet":   [("SoT%",      "sotPct",     70, False),
                       ("Mål/Skott", "gPerSh",    0.3, False),
                       ("xA/90",     "xApx",      0.5, False)],
        "Rörelse":    [("Assist/90", "astPer90",  0.6, False),
                       ("Frispk/90", "fldPer90",   4, False),
                       ("Offside",   "off",        20, True )],
        "Disciplin":  [("Gula kort", "crdY",       12, True ),
                       ("Felspel/90","flsPer90",    3, True )],
    },
}

SECTION_COLORS = {
    "Målscoring": "#e05050", "Anfall":  "#e05050",
    "Försvar":    "#30c060", "Räddning":"#3a80ff",
    "Passning":   "#f0a030", "Mål emot":"#a050e0",
    "Kvalitet":   "#00e8c8", "Rörelse": "#f0a030",
    "Spelartid":  "#7090b0", "Disciplin":"#d09030",
    "Resultat":   "#7080ff",
}

def _pv(v, mx, inv=False, pct_d=None, key=None):
    if pct_d and key and key in pct_d: return int(pct_d[key])
    p = min(round((f(v) / max(mx, 0.001)) * 100), 100)
    return max(0, 100 - p if inv else p)

def _grade(score):
    if score >= 80: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"

def _grade_color(grade):
    return {"A":"#00e8c8","B":"#30c060","C":"#f0a030","D":"#d04040","F":"#a02020"}.get(grade,"#888")

def _radar_labels_for_pos(pg):
    """Get radar labels and pct values for a player and its avg."""
    return DEFAULT_RADAR.get(pg, DEFAULT_RADAR["U"])

def generate_scouting_report(p, season):
    """Generate a scouting report image. Returns BytesIO PNG."""
    pg    = pos_group(p.get("pos",""))
    pct_d = p.get("pct", {})
    avg_d = league_avg(season, pg)
    secs  = SECTION_METRICS.get(pg, SECTION_METRICS["MF"])

    # ── Calculate section scores
    section_scores = {}
    for sec_name, metrics in secs.items():
        vals = [_pv(p.get(k,0), mx, inv, pct_d, k) for _,k,mx,inv in metrics]
        section_scores[sec_name] = round(sum(vals)/len(vals)) if vals else 0
    overall = round(sum(section_scores.values()) / len(section_scores))
    grade   = _grade(overall)

    # ── Radar data
    radar_mets  = _radar_labels_for_pos(pg)
    radar_lbls  = radar_mets
    n_ax        = len(radar_lbls)
    angles      = np.linspace(0, 2*np.pi, n_ax, endpoint=False).tolist()
    angles_closed = angles + [angles[0]]

    def get_pcts(src_dict, is_avg=False):
        vals = []
        for m in radar_lbls:
            key, mx, inv = ALL_RADAR[m]
            v = f(src_dict.get(key, 0))
            vals.append(_pv(v, mx, inv) if is_avg else _pv(v, mx, inv, pct_d, key))
        return vals + [vals[0]]

    player_pcts = get_pcts(p)
    avg_pcts    = get_pcts(avg_d, is_avg=True) if avg_d else [0]*(n_ax+1)

    # ──────────────────────────────────────────────────────────────────────────
    # FIGURE
    # ──────────────────────────────────────────────────────────────────────────
    BG   = "#0d0d0d"
    CARD = "#161616"
    matplotlib.rcParams['font.family'] = 'DejaVu Sans'
    fig  = plt.figure(figsize=(20, 10), facecolor=BG)
    fig.patch.set_facecolor(BG)

    # Title
    title_name = p.get("name","")
    fig.text(0.5, 0.96, f"SCOUTING REPORT: {title_name.upper()}",
             ha="center", va="top", color="white",
             fontsize=24, fontweight="bold")
    fig.text(0.5, 0.91,
             f"{p.get('squad','')}  ·  {p.get('pos','')}  ·  {p.get('age','')} ÅR  ·  Allsvenskan {season}",
             ha="center", va="top", color="#8090a0", fontsize=12)

    # ── LEFT panel: Horizontal bar chart (section scores)
    ax_bar = fig.add_axes([0.03, 0.10, 0.28, 0.76])
    ax_bar.set_facecolor(CARD)
    for spine in ax_bar.spines.values(): spine.set_visible(False)

    sec_names  = list(section_scores.keys())
    sec_vals   = [section_scores[s] for s in sec_names]
    sec_colors = [SECTION_COLORS.get(s,"#4a6080") for s in sec_names]
    y_pos      = np.arange(len(sec_names))

    bars = ax_bar.barh(y_pos, sec_vals, color=sec_colors, height=0.55,
                       edgecolor="none", zorder=3)
    ax_bar.set_xlim(0, 110)
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(sec_names, color="white", fontsize=13, fontweight="bold")
    ax_bar.set_xticks([0, 25, 50, 75, 100])
    ax_bar.tick_params(colors="#4a6080", labelsize=10)
    ax_bar.xaxis.tick_bottom()
    ax_bar.set_xlim(0, 115)
    ax_bar.grid(axis="x", color="#2a2a2a", linewidth=0.8, zorder=0)

    # Value labels
    for bar, val in zip(bars, sec_vals):
        ax_bar.text(val + 2, bar.get_y() + bar.get_height()/2,
                    f"{val}", va="center", ha="left",
                    color="white", fontsize=13, fontweight="bold")

    ax_bar.set_title("Sektionspoäng", color="white", fontsize=13,
                     fontweight="bold", pad=10)

    # ── MIDDLE panel: Player info + grade
    ax_mid = fig.add_axes([0.34, 0.10, 0.28, 0.76])
    ax_mid.set_facecolor(CARD)
    ax_mid.axis("off")

    info_lines = [
        ("Namn:",    p.get("name","")),
        ("Lag:",     p.get("squad","")),
        ("Position:",p.get("pos","")),
        ("Ålder:",   f"{p.get('age','')} år"),
        ("Nation:",  p.get("nation","")),
        ("Säsong:",  season),
        ("Minuter:", f"{int(p.get('min',0)):,}".replace(",",".")),
    ]
    # Add xG if available
    if f(p.get("xGpx",0)) > 0:
        info_lines.append(("xG/90:", f"{f(p.get('xGpx',0)):.2f}"))
    if f(p.get("xApx",0)) > 0:
        info_lines.append(("xA/90:", f"{f(p.get('xApx',0)):.2f}"))
    if f(p.get("xPpx",0)) > 0:
        info_lines.append(("xP/90:", f"{f(p.get('xPpx',0)):.2f}"))

    y_start = 0.88
    ax_mid.text(0.5, 0.96, "Spelarinformation",
                ha="center", va="top", transform=ax_mid.transAxes,
                color="white", fontsize=13, fontweight="bold")
    for label, value in info_lines:
        ax_mid.text(0.1, y_start, label, transform=ax_mid.transAxes,
                    color="#8090a0", fontsize=12, va="top")
        ax_mid.text(0.52, y_start, value, transform=ax_mid.transAxes,
                    color="white", fontsize=12, va="top", fontweight="bold")
        y_start -= 0.09

    # Grade badge
    gc = _grade_color(grade)
    grade_box = FancyBboxPatch((0.15, 0.04), 0.70, 0.20,
                                boxstyle="round,pad=0.02",
                                facecolor=gc+"22", edgecolor=gc,
                                linewidth=2, transform=ax_mid.transAxes)
    ax_mid.add_patch(grade_box)
    ax_mid.text(0.5, 0.14, f"Betyg:  {grade}",
                ha="center", va="center", transform=ax_mid.transAxes,
                color=gc, fontsize=22, fontweight="bold")
    ax_mid.text(0.5, 0.07, f"Overall: {overall}/100",
                ha="center", va="center", transform=ax_mid.transAxes,
                color="#8090a0", fontsize=11)

    # ── RIGHT panel: Radar
    ax_rad = fig.add_axes([0.64, 0.07, 0.34, 0.82], polar=True)
    ax_rad.set_facecolor("#0a0f1a")

    # Gridlines
    for level in [25, 50, 75, 100]:
        ax_rad.plot(angles_closed, [level]*(n_ax+1),
                    color="#1a2540", lw=0.7, zorder=1)

    # Avg fill
    ax_rad.fill(angles, avg_pcts[:-1], color="#606060", alpha=0.15, zorder=2)
    ax_rad.plot(angles_closed, avg_pcts, color="#e05050", lw=1.5,
                linestyle="--", zorder=3, label="Ligasnitt")

    # Player fill
    ax_rad.fill(angles, player_pcts[:-1], color="#30a060", alpha=0.30, zorder=4)
    ax_rad.plot(angles_closed, player_pcts, color="#30ff80", lw=2.5,
                zorder=5, label=title_name)

    # Dots
    ax_rad.scatter(angles, player_pcts[:-1], color="#30ff80", s=40, zorder=6)

    ax_rad.set_xticks(angles)
    ax_rad.set_xticklabels(radar_lbls, color="white", fontsize=10.5,
                            fontweight="bold")
    ax_rad.set_ylim(0, 100)
    ax_rad.set_yticks([25, 50, 75, 100])
    ax_rad.set_yticklabels(["25","50","75","100"], color="#4a5568", fontsize=8)
    ax_rad.tick_params(colors="#4a5568")
    ax_rad.spines["polar"].set_color("#1a2540")
    ax_rad.grid(color="#1a2540", lw=0.5)
    ax_rad.set_title("Spelare vs Ligasnitt (percentil)",
                     color="white", fontsize=12, fontweight="bold", pad=18)

    # Legend
    handles = [
        mpatches.Patch(facecolor="#30ff80", alpha=0.6, label=title_name),
        mpatches.Patch(facecolor="#e05050", alpha=0.5, label="Ligasnitt"),
    ]
    ax_rad.legend(handles=handles, loc="lower center",
                  bbox_to_anchor=(0.5, -0.12), ncol=2,
                  facecolor="#161616", edgecolor="#1a2540",
                  labelcolor="white", fontsize=10)

    # Footer
    fig.text(0.98, 0.01, "Allsvenskan Analytics ",
             ha="right", va="bottom", color="#2a3a50", fontsize=9)

    plt.tight_layout(rect=[0, 0.02, 1, 0.90])

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf




# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style='display:flex;align-items:center;gap:10px;
         padding:0 0 16px;border-bottom:1px solid #1a2540;margin-bottom:16px;'>
        <div style='width:36px;height:36px;border-radius:8px;
             background:linear-gradient(135deg,#003399,#1a5fcc);
             display:flex;align-items:center;justify-content:center;'>
            <span style='color:white;font-size:18px;'>⚽</span></div>
        <div><div style='color:#e2e8f0;font-weight:700;font-size:14px;'>Allsvenskan</div>
             <div style='color:#4a6080;font-size:10px;'>Analytics</div></div></div>
    """, unsafe_allow_html=True)

    view = st.radio("", ["⊞ IFK Göteborg","☰ Alla spelare","⇄ Jämför spelare","◫ Lagöversikt","🌍 Nationaliteter","🔍 Transferscout","📈 Spelarutveckling","📅 Säsongsöversikt","⭐ Nästa Steg","📋 Formtabell","👨‍⚖️ Domare"],
                    label_visibility="collapsed", key="main_view")
    st.divider()
    st.markdown("**Säsong**")
    season = st.selectbox("Säsong", SEASONS_AVAIL, label_visibility="collapsed")
    df_all = players_df(season)

    st.markdown("**Position**")
    pos_filter = st.selectbox("Position",
        ["Alla","GK – Målvakter","DF – Försvarare","MF – Mittfältare","FW – Anfallare"],
        label_visibility="collapsed")
    pos_sel = {"Alla":"ALL","GK – Målvakter":"GK","DF – Försvarare":"DF",
               "MF – Mittfältare":"MF","FW – Anfallare":"FW"}[pos_filter]

    st.markdown("**Lag**")
    all_teams = sorted(df_all["squad"].unique().tolist()) if not df_all.empty else []
    team_opts = ["Alla lag"] + (["IFK Göteborg"] if "IFK Göteborg" in all_teams else [])
    team_opts += [t for t in all_teams if t not in ("IFK Göteborg","Alla lag")]
    team_filter = st.selectbox("Lag", team_opts, label_visibility="collapsed")
    team_sel = None if team_filter == "Alla lag" else team_filter

    st.markdown("**Sök**")
    search = st.text_input("", placeholder="Spelarnamn…", label_visibility="collapsed")

    st.divider()
    if not df_all.empty:
        st.caption(f"📊 {len(df_all)} spelare · {season}")
        ifk_n = len(df_all[df_all.squad=="IFK Göteborg"])
        st.caption(f"🔵 {ifk_n} IFK Göteborg")
        xg_n = int(df_all["xGpx"].apply(f).gt(0).sum()) if "xGpx" in df_all.columns else 0
        st.caption(f"📈 {xg_n} med xG-data" if xg_n > 0 else "⚠️ Ingen xG-data laddad")

def filt(df):
    out = df.copy()
    if pos_sel != "ALL":   out = out[out.pos_group == pos_sel]
    if team_sel:           out = out[out.squad == team_sel]
    if search:             out = out[out.name.str.contains(search, case=False, na=False)]
    return out

df_filt = filt(df_all) if not df_all.empty else pd.DataFrame()

if "IFK Göteborg" in view:
    st.markdown(f"# 🔵 IFK Göteborg — {season}")
    ifk = df_all[df_all.squad=="IFK Göteborg"].copy() if not df_all.empty else pd.DataFrame()
    sq_df = squads_df(season)
    ifk_sq = sq_df[sq_df.squad=="IFK Göteborg"].iloc[0].to_dict() \
             if not sq_df.empty and "IFK Göteborg" in sq_df.squad.values else {}

    if ifk.empty:
        st.warning("Ingen data för IFK Göteborg denna säsong.")
        st.stop()

    c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
    c1.metric("⚽ Mål",         int(ifk.gls.sum())   if "gls"  in ifk else 0)
    c2.metric("🎯 Assist",      int(ifk.ast.sum())   if "ast"  in ifk else 0)
    c3.metric("👟 Skott",       int(ifk.sh.sum())    if "sh"   in ifk else 0)
    c4.metric("🎳 SoT",         int(ifk.sot.sum())   if "sot"  in ifk else 0)
    c5.metric("📊 SoT%",        f"{ifk_sq.get('sotPct',0):.1f}%" if ifk_sq else "—")
    c6.metric("🔵 Bollinneh.",  f"{ifk_sq.get('poss',0):.0f}%"  if ifk_sq else "—")
    c7.metric("🛡 Brytningar",  int(ifk["int"].sum()) if "int" in ifk else 0)
    c8.metric("🟨 Gula kort",   int(ifk.crdY.sum())  if "crdY" in ifk else 0)
    st.divider()

    ta,tb,tc,td = st.columns(4)
    def top5(col, icon, unit, df=None, custom=None):
        src = df if df is not None else ifk
        if custom:
            for row in custom: st.markdown(row)
            return
        sub = src[src[col]>0].sort_values(col,ascending=False).head(5) if col in src else pd.DataFrame()
        for _,r in sub.iterrows():
            v = int(r[col]) if f(r[col])==int(f(r[col])) else round(f(r[col]),2)
            st.markdown(f"{icon} **{r['name'].split()[-1]}** — {v} {unit}")

    with ta:
        st.markdown("**Mål**")
        top5("gls","⚽","mål")
    with tb:
        st.markdown("**Assist**")
        top5("ast","🎯","ast")
    with tc:
        st.markdown("**Spelade minuter**")
        sub = ifk.sort_values("min",ascending=False).head(5) if "min" in ifk else pd.DataFrame()
        for _,r in sub.iterrows():
            st.markdown(f"⏱ **{r['name'].split()[-1]}** — {int(r['min']):,}".replace(",",".")+" min")
    with td:
        st.markdown("**Flest skott**")
        top5("sh","👟","skott")

    st.divider()
    st.markdown("### Spelarprofil")
    pos_local = st.radio("", ["Alla","GK","DF","MF","FW"],
                          horizontal=True, label_visibility="collapsed", key="ifk_pos_main")
    ifk_show = ifk.sort_values("min",ascending=False)
    if pos_local != "Alla":
        ifk_show = ifk_show[ifk_show.pos_group==pos_local]

    sel = st.selectbox("Välj spelare", ifk_show["name"].tolist(),
                        label_visibility="collapsed", key="ifk_sel")
    if sel:
        p_dict = ifk_show[ifk_show.name==sel].iloc[0].to_dict()
        pg = pos_group(p_dict.get("pos",""))

        chosen, show_avg = radar_config("ifk_radar", pg)
        if len(chosen) >= 3:
            fig = radar_chart([(sel, p_dict)], chosen, season, show_avg)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
        else:
            st.info("Välj minst 3 axlar för radarn.")
        st.divider()
        scout_panel(p_dict, season)

# ══ VIEW: ALLA SPELARE ════════════════════════════════════════════════════════
elif "Alla spelare" in view:
    st.markdown(f"# ☰ Alla spelare — {season}")
    st.caption(f"{len(df_filt)} spelare")
    if df_filt.empty:
        st.info("Inga spelare matchade filtret.")
    else:
        sort_col = st.selectbox("Sortera",
            ["gls","ast","min","sh","sot","sotPct","int","tklW","xGpx","xApx"],
            format_func=lambda x:{"gls":"Mål","ast":"Assist","min":"Minuter","sh":"Skott",
                "sot":"SoT","sotPct":"SoT%","int":"Brytningar","tklW":"Tacklingar",
                "xGpx":"xG/90","xApx":"xA/90"}.get(x,x),
            label_visibility="collapsed")
        df_s = df_filt.sort_values(sort_col,ascending=False) if sort_col in df_filt else df_filt

        cols_show=["name","squad","pos","age","mp","min","gls","ast","sh","sot","sotPct","int","tklW","crdY","xGpx","xApx","xPpx"]
        avail=[c for c in cols_show if c in df_s.columns]
        ren={"name":"Spelare","squad":"Lag","pos":"Pos","age":"Ålder","mp":"M","min":"Min",
             "gls":"Mål","ast":"Ass","sh":"Skott","sot":"SoT","sotPct":"SoT%",
             "int":"Bryt","tklW":"Tackl","crdY":"GK","xGpx":"xG/90","xApx":"xA/90","xPpx":"xP/90"}
        tbl=df_s[avail].rename(columns=ren).reset_index(drop=True)
        if "Min"   in tbl: tbl["Min"]   = tbl["Min"].apply(lambda v:f"{int(v):,}".replace(",",".") if v else "—")
        if "SoT%"  in tbl: tbl["SoT%"]  = tbl["SoT%"].apply(lambda v:f"{v:.1f}%" if v else "—")
        if "xG/90" in tbl: tbl["xG/90"] = tbl["xG/90"].apply(lambda v:f"{v:.2f}" if v else "—")
        if "xA/90" in tbl: tbl["xA/90"] = tbl["xA/90"].apply(lambda v:f"{v:.2f}" if v else "—")
        if "xP/90" in tbl: tbl["xP/90"] = tbl["xP/90"].apply(lambda v:f"{v:.2f}" if v else "—")
        st.dataframe(tbl, use_container_width=True, height=440, hide_index=True)

        st.divider()
        sel = st.selectbox("Spelarprofil", df_s["name"].tolist(),
                            label_visibility="collapsed", key="league_sel")
        if sel:
            p_dict = df_s[df_s.name==sel].iloc[0].to_dict()
            pg = pos_group(p_dict.get("pos",""))
            chosen, show_avg = radar_config("league_radar", pg)
            if len(chosen) >= 3:
                fig = radar_chart([(sel, p_dict)], chosen, season, show_avg)
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            else:
                st.info("Välj minst 3 axlar.")
            st.divider()
            scout_panel(p_dict, season)

# ══ VIEW: JÄMFÖR ═════════════════════════════════════════════════════════════
elif "Jämför" in view:
    st.markdown(f"# ⇄ Jämför spelare — {season}")
    all_names = sorted(df_all["name"].tolist()) if not df_all.empty else []

    # IFK-spelare sorted first
    ifk_names = sorted(df_all[df_all.squad=="IFK Göteborg"]["name"].tolist()) if not df_all.empty else []
    other_names = [n for n in all_names if n not in ifk_names]
    grouped_names = ifk_names + ["──────────"] + other_names

    ca,cb = st.columns(2)
    with ca:
        p1 = st.selectbox("Spelare 1", ["—"]+all_names, key="c1")
        p3 = st.selectbox("Spelare 3 (valfri)", ["—"]+all_names, key="c3")
    with cb:
        p2 = st.selectbox("Spelare 2", ["—"]+all_names, key="c2")
        p4 = st.selectbox("Spelare 4 (valfri)", ["—"]+all_names, key="c4")

    selected = [p for p in [p1,p2,p3,p4] if p and p!="—"]
    pdata = []
    colors_cmp = ["#3a80ff","#00e8c8","#f0a030","#e05050"]
    for i,name in enumerate(selected):
        row = df_all[df_all.name==name]
        if not row.empty:
            pdata.append((name, row.iloc[0].to_dict(), colors_cmp[i%4]))

    if len(pdata) < 2:
        st.markdown("<div style='text-align:center;padding:60px;color:#2a4060;font-size:14px;'>"
                    "<div style='font-size:36px'>⇄</div>Välj minst 2 spelare.</div>",
                    unsafe_allow_html=True)
    else:
        pg_first = pos_group(pdata[0][1].get("pos",""))

        # ── Radar med snitt
        st.markdown("### 📡 Radardiagram")
        chosen, show_avg = radar_config("cmp_radar", pg_first)

        if len(chosen) >= 3:
            fig = radar_chart(pdata, chosen, season, show_avg)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
        else:
            st.info("Välj minst 3 axlar.")

        # ── Direktjämförelsetabell
        st.markdown("### 📊 Direktjämförelse")

        ALL_CMP_STATS = [
            ("Minuter",         "min",       lambda v:f"{int(v):,}".replace(",",".")),
            ("Matcher",         "mp",        lambda v:str(int(v))),
            ("Mål",             "gls",       lambda v:str(int(v))),
            ("Assist",          "ast",       lambda v:str(int(v))),
            ("Mål+Assist",      "gPluA",     lambda v:str(int(v))),
            ("Mål/90",          "glsPer90",  lambda v:f"{v:.2f}"),
            ("Assist/90",       "astPer90",  lambda v:f"{v:.2f}"),
            ("xG",              "xG",        lambda v:f"{v:.2f}"),
            ("xG/90",           "xGpx",      lambda v:f"{v:.2f}"),
            ("xA",              "xA",        lambda v:f"{v:.2f}"),
            ("xA/90",           "xApx",      lambda v:f"{v:.2f}"),
            ("Mål vs xG",       "gMinusXG",  lambda v:f"{v:+.2f}"),
            ("xP",              "xP",        lambda v:f"{v:.0f}"),
            ("xP/90",           "xPpx",      lambda v:f"{v:.2f}"),
            ("Assist vs xA",    "aMinusXA",  lambda v:f"{v:+.2f}"),
            ("Skott",           "sh",        lambda v:str(int(v))),
            ("SoT",             "sot",       lambda v:str(int(v))),
            ("SoT %",           "sotPct",    lambda v:f"{v:.1f}%"),
            ("Skott/90",        "shPer90",   lambda v:f"{v:.2f}"),
            ("Mål/Skott",       "gPerSh",    lambda v:f"{v:.2f}"),
            ("Brytningar",      "int",       lambda v:str(int(v))),
            ("Bryt./90",        "intPer90",  lambda v:f"{v:.2f}"),
            ("Tacklingar",      "tklW",      lambda v:str(int(v))),
            ("Tackl./90",       "tklWPer90", lambda v:f"{v:.2f}"),
            ("Inlägg",     "crs",       lambda v:str(int(v))),
            ("Frisparkar vunna","fld",       lambda v:str(int(v))),
            ("Felspel/90",      "flsPer90",  lambda v:f"{v:.2f}"),
            ("Offside",         "off",       lambda v:str(int(v))),
            ("Gula kort",       "crdY",      lambda v:str(int(v))),
        ]
        LOW_GOOD = {"crdY","crdR","fls","flsPer90","off","gkGA90","gkSoTA"}

        avg_d = league_avg(season, pg_first)

        # Bygg tabell
        rows_tbl = {"Statistik":[r[0] for r in ALL_CMP_STATS]}
        if avg_d:
            rows_tbl["⌀ Liga"] = []
            for lbl,key,fn in ALL_CMP_STATS:
                v = avg_d.get(key,0)
                rows_tbl["⌀ Liga"].append(fn(v) if v else "—")

        for name,p,col in pdata:
            vals = []
            for lbl,key,fn in ALL_CMP_STATS:
                v = f(p.get(key,0))
                vals.append(fn(v) if v else "—")
            rows_tbl[name.split()[-1]] = vals

        cmp_df = pd.DataFrame(rows_tbl)

        # Highlight best (non-avg columns)
        player_cols = [name.split()[-1] for name,_,_ in pdata]
        def highlight_best(df):
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            for i,(lbl,key,fn) in enumerate(ALL_CMP_STATS):
                row_vals = []
                for col_n in player_cols:
                    try:
                        v = f(pdata[player_cols.index(col_n)][1].get(key,0))
                        row_vals.append(v)
                    except: row_vals.append(0)
                if all(v==0 for v in row_vals): continue
                best_idx = row_vals.index(min(row_vals) if key in LOW_GOOD else max(row_vals))
                best_col = player_cols[best_idx]
                styles.at[i, best_col] = "color: #00e8c8; font-weight: bold"
            return styles

        st.dataframe(
            cmp_df.style.apply(highlight_best, axis=None),
            use_container_width=True, hide_index=True, height=580
        )

        # ── Individuella profiler
        st.markdown("### 📋 Individuella profiler")
        for i,(name,p_dict,col) in enumerate(pdata):
            with st.expander(f"{'🔵' if p_dict.get('squad')=='IFK Göteborg' else '⚪'} {name} — {p_dict.get('squad','')} · {p_dict.get('pos','')}", expanded=(i<2)):
                scout_panel(p_dict, season)

# ══ VIEW: LAGÖVERSIKT ════════════════════════════════════════════════════════
elif "Lagöversikt" in view:
    st.markdown(f"# ◫ Lagöversikt — {season}")

    sq_df = squads_df(season)
    if sq_df.empty:
        st.warning("Ingen lagdata.")
    else:
        sq_df = sq_df.sort_values("gls", ascending=False).reset_index(drop=True)
        disp  = ["squad","mp","gls","ast","sh","sot","sotPct","poss","crdY","crdR"]
        avail = [c for c in disp if c in sq_df.columns]
        ren   = {"squad":"Lag","mp":"M","gls":"Mål","ast":"Ass","sh":"Skott",
                 "sot":"SoT","sotPct":"SoT%","poss":"Boll%","crdY":"GK","crdR":"RK"}
        tbl   = sq_df[avail].rename(columns=ren)
        if "SoT%" in tbl: tbl["SoT%"] = tbl["SoT%"].apply(lambda v: f"{f(v):.1f}%")
        if "Boll%" in tbl: tbl["Boll%"] = tbl["Boll%"].apply(lambda v: f"{f(v):.0f}%")
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Detaljerad laganalys")

    all_squads_list = sq_df["squad"].tolist() if not sq_df.empty else (
        sorted(df_all["squad"].unique().tolist()) if not df_all.empty else []
    )
    if not all_squads_list:
        st.stop()

    ifk_first = ["IFK Göteborg"] + [t for t in all_squads_list if t != "IFK Göteborg"]
    col_sel, col_pos = st.columns([2, 1])
    with col_sel:
        chosen_team = st.selectbox("", ifk_first,
            label_visibility="collapsed", key="lo_team")
    with col_pos:
        pos_lo = st.radio("", ["Alla","GK","DF","MF","FW"],
            horizontal=True, label_visibility="collapsed", key="lo_pos")

    is_ifk     = chosen_team == "IFK Göteborg"
    team_color = "#3a80ff" if is_ifk else "#a0c0e0"
    st.markdown(f"## {'🔵 ' if is_ifk else ''}{chosen_team} — {season}")

    team_ps = df_all[df_all.squad == chosen_team].copy() if not df_all.empty else pd.DataFrame()
    team_sq = sq_df[sq_df.squad == chosen_team].iloc[0].to_dict() \
              if not sq_df.empty and chosen_team in sq_df.squad.values else {}

    if team_ps.empty:
        st.info("Ingen spelardata för detta lag.")
    else:
        c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
        c1.metric("⚽ Mål",        int(team_ps.gls.sum())    if "gls"  in team_ps else 0)
        c2.metric("🎯 Assist",     int(team_ps.ast.sum())    if "ast"  in team_ps else 0)
        c3.metric("👟 Skott",      int(team_ps.sh.sum())     if "sh"   in team_ps else 0)
        c4.metric("🎳 SoT",        int(team_ps.sot.sum())    if "sot"  in team_ps else 0)
        c5.metric("📊 SoT%",       f"{team_sq.get('sotPct',0):.1f}%" if team_sq else "—")
        c6.metric("🔵 Bollinneh.", f"{team_sq.get('poss',0):.0f}%"   if team_sq else "—")
        c7.metric("🛡 Brytningar", int(team_ps["int"].sum()) if "int"  in team_ps else 0)
        c8.metric("🟨 Gula kort",  int(team_ps.crdY.sum())   if "crdY" in team_ps else 0)
        st.divider()

        st.markdown("### Topplistor")
        ta,tb,tc,td = st.columns(4)
        def top5_lo(col, icon, unit):
            sub = team_ps[team_ps[col]>0].sort_values(col,ascending=False).head(5) \
                  if col in team_ps else pd.DataFrame()
            for _,r in sub.iterrows():
                v = int(r[col]) if f(r[col])==int(f(r[col])) else round(f(r[col]),2)
                st.markdown(f"{icon} **{r['name'].split()[-1]}** — {v} {unit}")
        with ta:
            st.markdown("**Mål**"); top5_lo("gls","⚽","mål")
        with tb:
            st.markdown("**Assist**"); top5_lo("ast","🎯","ast")
        with tc:
            st.markdown("**Spelade minuter**")
            sub = team_ps.sort_values("min",ascending=False).head(5) if "min" in team_ps else pd.DataFrame()
            for _,r in sub.iterrows():
                st.markdown(f"⏱ **{r['name'].split()[-1]}** — {int(r['min']):,}".replace(",",".")+" min")
        with td:
            st.markdown("**Flest skott**"); top5_lo("sh","👟","skott")

        st.divider()
        st.markdown("### Spelarbidrag")
        has_xg_lo   = team_ps["xGpx"].apply(f).gt(0).any()      if "xGpx"      in team_ps.columns else False
        has_pass_lo = team_ps["pass_total"].apply(f).gt(0).any() if "pass_total" in team_ps.columns else False
        has_rec_lo  = team_ps["recoveries"].apply(f).gt(0).any() if "recoveries" in team_ps.columns else False

        def hbar_lo(df_b, traces, barmode="stack", height=None):
            fig_h = go.Figure()
            for nm, col, color in traces:
                if col in df_b.columns:
                    fig_h.add_trace(go.Bar(name=nm, y=df_b.name,
                        x=df_b[col].apply(f), orientation="h",
                        marker_color=color, marker_line_width=0))
            fig_h.update_layout(barmode=barmode,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#7090b0",size=11),
                xaxis=dict(gridcolor="#1a2540"),
                yaxis=dict(tickfont=dict(color="#c0d8f0",size=11)),
                legend=dict(font=dict(color="#a0c0e0"),bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=20,t=10,b=20),
                height=height or max(320,len(df_b)*30))
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar":False})

        tab_names_lo = ["⚽ Mål & Assist","👟 Skott & SoT","🛡 Försvar"]
        if has_xg_lo:   tab_names_lo.append("📈 Expected Goals")
        if has_pass_lo: tab_names_lo.append("🎯 Passningar")
        if has_rec_lo:  tab_names_lo.append("🏃 Löpningar")
        tabs_lo = st.tabs(tab_names_lo)
        ti = 0

        with tabs_lo[ti]:
            ti += 1
            top_c = team_ps[team_ps.gPluA>0].sort_values("gPluA",ascending=True).tail(16) \
                    if "gPluA" in team_ps.columns else pd.DataFrame()
            if not top_c.empty:
                hbar_lo(top_c,[("Mål","gls",team_color),("Assist","ast","#00e8c8")])
        with tabs_lo[ti]:
            ti += 1
            top_sh = team_ps[team_ps.sh>0].sort_values("sh",ascending=True).tail(16) \
                     if "sh" in team_ps.columns else pd.DataFrame()
            if not top_sh.empty:
                hbar_lo(top_sh,[("Skott","sh","#f0a030"),("SoT","sot","#30c060")],barmode="group")
        with tabs_lo[ti]:
            ti += 1
            if "int" in team_ps.columns:
                td2 = team_ps.copy()
                td2["def_total"] = td2["int"].apply(f)+td2["tklW"].apply(f)
                td2 = td2[td2.def_total>0].sort_values("def_total",ascending=True).tail(16)
                if not td2.empty:
                    hbar_lo(td2,[("Brytningar","int","#30c060"),("Tacklingar","tklW","#a050e0")])
        if has_xg_lo:
            with tabs_lo[ti]:
                ti += 1
                top_xg = team_ps[team_ps["xGpx"].apply(f)>0].sort_values(
                    "xGpx",ascending=True,key=lambda x:x.apply(f)).tail(16)
                if not top_xg.empty:
                    hbar_lo(top_xg,[("xG","xG","#20c060"),("xA","xA","#3a80ff"),("xP","xP","#a050e0")],barmode="group")
                st.markdown("#### xG vs faktiska mål")
                top_cmp = team_ps[team_ps["xG"].apply(f)>0].sort_values("xG",ascending=True,key=lambda x:x.apply(f)).tail(16)
                if not top_cmp.empty:
                    fig_cmp = go.Figure()
                    fig_cmp.add_trace(go.Bar(name="xG",y=top_cmp.name,x=top_cmp["xG"].apply(f),
                        orientation="h",marker_color="#20c06099",marker_line_width=0))
                    fig_cmp.add_trace(go.Bar(name="Faktiska mål",y=top_cmp.name,x=top_cmp["gls"].apply(f),
                        orientation="h",marker_color=team_color,marker_line_width=0))
                    fig_cmp.update_layout(barmode="overlay",paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#7090b0",size=11),
                        xaxis=dict(gridcolor="#1a2540"),yaxis=dict(tickfont=dict(color="#c0d8f0",size=11)),
                        legend=dict(font=dict(color="#a0c0e0"),bgcolor="rgba(0,0,0,0)"),
                        margin=dict(l=0,r=20,t=10,b=20),height=max(320,len(top_cmp)*30))
                    st.plotly_chart(fig_cmp,use_container_width=True,config={"displayModeBar":False})
        if has_pass_lo:
            with tabs_lo[ti]:
                ti += 1
                cp1,cp2 = st.columns(2)
                with cp1:
                    st.markdown("**Passningsprocent**")
                    tp = team_ps[team_ps["pass_pct"].apply(f)>0].sort_values("pass_pct",ascending=True,key=lambda x:x.apply(f)).tail(16)
                    if not tp.empty: hbar_lo(tp,[("P%","pass_pct","#3a80ff")])
                with cp2:
                    st.markdown("**Progressiva pass/90**")
                    tp2 = team_ps[team_ps["prog_pass_p90"].apply(f)>0].sort_values("prog_pass_p90",ascending=True,key=lambda x:x.apply(f)).tail(16)
                    if not tp2.empty: hbar_lo(tp2,[("PP/90","prog_pass_p90","#a050e0")])
        if has_rec_lo:
            with tabs_lo[ti]:
                ti += 1
                cr1,cr2 = st.columns(2)
                with cr1:
                    st.markdown("**Återerövringar/90**")
                    tr = team_ps[team_ps["recoveries_p90"].apply(f)>0].sort_values("recoveries_p90",ascending=True,key=lambda x:x.apply(f)).tail(16)
                    if not tr.empty: hbar_lo(tr,[("Åter./90","recoveries_p90","#00e8c8")])
                with cr2:
                    st.markdown("**Prog. löpningar/90**")
                    tr2 = team_ps[team_ps["prog_carries_p90"].apply(f)>0].sort_values("prog_carries_p90",ascending=True,key=lambda x:x.apply(f)).tail(16)
                    if not tr2.empty: hbar_lo(tr2,[("PL/90","prog_carries_p90","#f0a030")])

        st.divider()
        st.markdown("### Spelartabell")
        base_c = ["name","pos","age","mp","min","gls","ast","sh","sot","sotPct","int","tklW","crdY"]
        xg_c   = ["xG","xGpx","xA","xApx","xP","xPpx"] if has_xg_lo else []
        pa_c   = ["pass_pct","prog_pass_p90","recoveries_p90"] if has_pass_lo else []
        sc_cols = [c for c in base_c+xg_c+pa_c if c in team_ps.columns]
        rn_map  = {"name":"Spelare","pos":"Pos","age":"Ålder","mp":"M","min":"Min",
                   "gls":"Mål","ast":"Ast","sh":"Skott","sot":"SoT","sotPct":"SoT%",
                   "int":"Bryt","tklW":"Tackl","crdY":"GK",
                   "xG":"xG","xGpx":"xG/90","xA":"xA","xApx":"xA/90","xP":"xP","xPpx":"xP/90",
                   "pass_pct":"P%","prog_pass_p90":"PP/90","recoveries_p90":"Åter/90"}
        tbl_lo = team_ps.sort_values("min",ascending=False)[sc_cols].rename(columns=rn_map).reset_index(drop=True)
        if "Min"  in tbl_lo.columns: tbl_lo["Min"]  = tbl_lo["Min"].apply(lambda v: str(int(f(v))) if v else "—")
        if "SoT%" in tbl_lo.columns: tbl_lo["SoT%"] = tbl_lo["SoT%"].apply(lambda v: f"{f(v):.1f}%" if v else "—")
        for xc in ["xG/90","xA/90","xP/90","P%","PP/90","Åter/90"]:
            if xc in tbl_lo.columns:
                tbl_lo[xc] = tbl_lo[xc].apply(lambda v: f"{f(v):.2f}" if v else "—")
        st.dataframe(tbl_lo, use_container_width=True, hide_index=True, height=460)

        st.divider()
        st.markdown("### Spelarprofil")
        team_show = team_ps.sort_values("min",ascending=False)
        if pos_lo != "Alla":
            team_show = team_show[team_show.pos_group == pos_lo]
        sel_lo = st.selectbox("Välj spelare", team_show["name"].tolist(),
                               label_visibility="collapsed", key="lo_player")
        if sel_lo:
            p_dict = team_show[team_show.name==sel_lo].iloc[0].to_dict()
            pg = pos_group(p_dict.get("pos",""))
            chosen_lo, show_avg_lo = radar_config("lo_radar", pg)
            if len(chosen_lo) >= 3:
                fig_lo = radar_chart([(sel_lo,p_dict)],chosen_lo,season,show_avg_lo)
                if fig_lo: st.plotly_chart(fig_lo,use_container_width=True,config={"displayModeBar":False})
            else:
                st.info("Välj minst 3 axlar.")
            st.divider()
            scout_panel(p_dict, season)


elif "Transferscout" in view:
    st.markdown(f"# 🔍 Transferscout — Liknande spelare")
    st.caption("Hitta statistiskt liknande spelare i Allsvenskan baserat på percentilprofil")

    if df_all.empty:
        st.warning("Ingen data tillgänglig.")
        st.stop()

    SCOUT_KEYS_FIELD = [
        "glsPer90","astPer90","shPer90","sotPct","gPerSh",
        "intPer90","tklWPer90","flsPer90","fldPer90","crsPer90",
        "xGpx","xApx",
    ]
    SCOUT_KEYS_GK = [
        "gkSavePct","gkGA90","gkCSPct","gkSaves","gkW",
        "intPer90","tklWPer90",
    ]

    def player_vec(p_dict):
        pct = p_dict.get("pct", {})
        pg  = pos_group(p_dict.get("pos",""))
        keys = SCOUT_KEYS_GK if pg == "GK" else SCOUT_KEYS_FIELD
        return np.array([float(pct.get(k, 0)) for k in keys])

    def cosine_sim(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0: return 0.0
        return float(np.dot(a, b) / (na * nb))

    # ── Controls
    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        # IFK first
        ifk_names   = sorted(df_all[df_all.squad=="IFK Göteborg"]["name"].tolist())
        other_names = [n for n in sorted(df_all["name"].tolist()) if n not in ifk_names]
        scout_all   = ifk_names + other_names
        scout_sel   = st.selectbox("Välj spelare att hitta liknande för",
                                    scout_all, label_visibility="collapsed",
                                    key="scout_player")
    with col_b:
        top_n = st.slider("Antal liknande", 3, 15, 8, key="scout_n")
    with col_c:
        same_pos = st.checkbox("Samma position", value=True, key="scout_pos")
        excl_own = st.checkbox("Exkludera eget lag", value=False, key="scout_excl")

    if scout_sel:
        ref_row = df_all[df_all.name == scout_sel].iloc[0].to_dict()
        ref_pg  = pos_group(ref_row.get("pos",""))
        ref_vec = player_vec(ref_row)

        # Filter candidates
        candidates = df_all[df_all.name != scout_sel].copy()
        if same_pos:
            candidates = candidates[candidates.pos_group == ref_pg]
        if excl_own:
            candidates = candidates[candidates.squad != ref_row.get("squad","")]

        # Compute similarities
        sims = []
        for _, row in candidates.iterrows():
            pdict = row.to_dict()
            sim   = cosine_sim(ref_vec, player_vec(pdict))
            sims.append((sim, pdict))
        sims.sort(key=lambda x: x[0], reverse=True)
        top = sims[:top_n]

        st.divider()

        # ── Reference player header
        is_ifk = ref_row.get("squad") == "IFK Göteborg"
        st.markdown(f"""<div style='background:#0a1525;border:1px solid {"#1a4090" if is_ifk else "#1a2540"};
            border-radius:10px;padding:14px 18px;margin-bottom:16px;'>
            <span style='font-size:18px;font-weight:800;color:#e2e8f0'>{scout_sel}</span>
            &nbsp;
            {pos_badge_html(ref_row.get("pos",""))}
            <span class="badge" style='background:#0e1f35;color:#5090d0'>{ref_row.get("squad","")}</span>
            <span class="badge" style='background:#0f1829;color:#4a6080'>{ref_row.get("pos","")} · {ref_row.get("nation","")} · {ref_row.get("age","")} år</span>
        </div>""", unsafe_allow_html=True)

        # ── Similarity cards
        st.markdown(f"### {top_n} mest liknande spelare")
        cols_per_row = 3
        for row_i in range(0, len(top), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_i, (sim, p) in enumerate(top[row_i:row_i+cols_per_row]):
                with cols[col_i]:
                    is_ifk_p  = p.get("squad") == "IFK Göteborg"
                    pg_c      = pos_group(p.get("pos",""))
                    pill      = POS_PILL.get(pg_c, POS_PILL["U"]) if hasattr(globals().get("POS_PILL",None), "get") else {}

                    pct_ring_color = ("#00e8c8" if sim >= 0.95 else
                                      "#30c060" if sim >= 0.90 else
                                      "#f0a030" if sim >= 0.80 else "#e05050")
                    sim_pct = round(sim * 100)

                    st.markdown(f"""
                    <div style='background:{"#0a1525" if is_ifk_p else "#0d1829"};
                         border:1px solid {"#1a4090" if is_ifk_p else "#1a2540"};
                         border-radius:10px;padding:14px;margin-bottom:4px;'>
                        <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                            <div>
                                <div style='font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:6px;'>{p.get("name","")}</div>
                                <div style='font-size:11px;color:#4a6080;'>{p.get("squad","")} · {p.get("pos","")} · {p.get("age","")} år</div>
                            </div>
                            <div style='text-align:center;'>
                                <div style='font-size:22px;font-weight:900;color:{pct_ring_color};'>{sim_pct}%</div>
                                <div style='font-size:9px;color:#3a5070;'>likhet</div>
                            </div>
                        </div>
                        <div style='display:flex;gap:12px;margin-top:10px;border-top:1px solid #1a2540;padding-top:10px;'>
                            <div style='text-align:center;'>
                                <div style='font-size:16px;font-weight:700;color:#e2e8f0;'>{p.get("gls",0)}</div>
                                <div style='font-size:9px;color:#3a5070;'>MÅL</div>
                            </div>
                            <div style='text-align:center;'>
                                <div style='font-size:16px;font-weight:700;color:#e2e8f0;'>{p.get("ast",0)}</div>
                                <div style='font-size:9px;color:#3a5070;'>ASSIST</div>
                            </div>
                            <div style='text-align:center;'>
                                <div style='font-size:16px;font-weight:700;color:#e2e8f0;'>{str(int(p.get("min",0))).replace(",",".")}</div>
                                <div style='font-size:9px;color:#3a5070;'>MIN</div>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

        # ── Radar overlay — reference + top 2 most similar
        st.divider()
        st.markdown("### 📡 Radarjämförelse — referens vs topp 2 liknande")
        top2_data = [(scout_sel, ref_row)] + [(p["name"], p) for _, p in top[:2]]
        pg_first  = ref_pg
        def_mets  = [m for m in DEFAULT_RADAR.get(pg_first, DEFAULT_RADAR["U"]) if m in ALL_RADAR]
        chosen_sc = st.multiselect("Radaraxlar", list(ALL_RADAR.keys()),
                                    default=def_mets, key="scout_radar")
        if len(chosen_sc) >= 3:
            fig = radar_chart(
                [(n, pd_) for n, pd_ in top2_data],
                chosen_sc, season, show_avg=True
            )
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})


# ══ VIEW: SPELARUTVECKLING ════════════════════════════════════════════════════
elif "Spelarutveckling" in view:
    st.markdown("# 📈 Spelarutveckling")
    st.caption("Följ en spelares statistiska resa över säsonger")

    import unicodedata as _ud2
    def _norm2(name):
        s = _ud2.normalize("NFKD", str(name or "").strip())
        s = "".join(c for c in s if not _ud2.combining(c))
        for o2, n2 in [("Þ","th"),("þ","th"),("ð","d"),("ø","o"),("æ","ae"),("ß","ss")]:
            s = s.replace(o2, n2)
        return s.lower().strip()

    # Collect all unique player names across all seasons
    all_player_names = {}
    for yr, sdata in DB["seasons"].items():
        for p in sdata.get("players", []):
            nm = p.get("name","")
            if nm:
                key = _norm2(nm)
                if key not in all_player_names:
                    all_player_names[key] = nm
    sorted_dev_names = sorted(all_player_names.values(), key=lambda x: x.split()[-1])

    # IFK first
    ifk_dev_names = []
    for yr in SEASONS_AVAIL:
        for p in DB["seasons"].get(yr,{}).get("players",[]):
            if p.get("squad") == "IFK Göteborg" and p.get("name") not in ifk_dev_names:
                ifk_dev_names.append(p["name"])
    other_dev = [n for n in sorted_dev_names if n not in ifk_dev_names]
    dev_all_names = ifk_dev_names + other_dev

    dev_sel = st.selectbox("Välj spelare", dev_all_names,
                            label_visibility="collapsed", key="dev_player")

    if dev_sel:
        dev_norm = _norm2(dev_sel)

        # Collect data across seasons
        dev_data = {}
        for yr in sorted(DB["seasons"].keys()):
            for p in DB["seasons"][yr].get("players",[]):
                if _norm2(p.get("name","")) == dev_norm:
                    dev_data[yr] = p
                    break

        if len(dev_data) < 1:
            st.info("Ingen data hittades för denna spelare.")
        else:
            p_any  = list(dev_data.values())[0]
            pg_dev = pos_group(p_any.get("pos",""))
            is_ifk_dev = any(p.get("squad")=="IFK Göteborg" for p in dev_data.values())

            # Header
            yrs_found = sorted(dev_data.keys())
            squads_found = [dev_data[y].get("squad","") for y in yrs_found]
            st.markdown(f"""<div class="player-hdr">
            <div style='font-size:22px;font-weight:900;color:#e2e8f0;margin-bottom:8px;'>{dev_sel}</div>
            <div>{'  ·  '.join(f"<span style='color:#5090d0'>{y}</span> {s}" for y,s in zip(yrs_found,squads_found))}</div>
            </div>""", unsafe_allow_html=True)

            # Choose metrics to show
            DEV_METRICS = {
                "Mål":            "gls",
                "Assist":         "ast",
                "Mål/90":         "glsPer90",
                "Assist/90":      "astPer90",
                "Minuter":        "min",
                "Skott":          "sh",
                "SoT%":           "sotPct",
                "xG/90":          "xGpx",
                "xA/90":          "xApx",
                "Brytningar":     "int",
                "Tacklingar":     "tklW",
                "Gula kort":      "crdY",
                "Räddningar% (MV)": "gkSavePct",
                "IM/90 (MV)":     "gkGA90",
                "Nollor% (MV)":   "gkCSPct",
            }
            default_mets_dev = {
                "GK": ["Räddningar% (MV)","IM/90 (MV)","Nollor% (MV)","Minuter"],
                "DF": ["Minuter","Mål","Assist","Brytningar","Tacklingar"],
                "MF": ["Mål","Assist","Mål/90","Assist/90","xG/90","Minuter"],
                "FW": ["Mål","Assist","Mål/90","Assist/90","xG/90","Skott"],
                "U":  ["Mål","Assist","Minuter","Skott"],
            }
            chosen_dev = st.multiselect(
                "Välj statistik att följa",
                list(DEV_METRICS.keys()),
                default=[m for m in default_mets_dev.get(pg_dev,default_mets_dev["U"])
                         if m in DEV_METRICS],
                key="dev_metrics",
            )

            if chosen_dev and yrs_found:
                # Build chart
                seasons_x = yrs_found
                colors_dev = ["#3a80ff","#00e8c8","#f0a030","#e05050",
                               "#a050e0","#30c060","#ff8c00"]

                fig_dev = go.Figure()
                for ci, met_lbl in enumerate(chosen_dev):
                    key_dev = DEV_METRICS[met_lbl]
                    y_vals  = [f(dev_data[yr].get(key_dev, 0)) for yr in seasons_x]
                    col_dev = colors_dev[ci % len(colors_dev)]
                    r,g_c,b = int(col_dev[1:3],16),int(col_dev[3:5],16),int(col_dev[5:7],16)

                    fig_dev.add_trace(go.Scatter(
                        x=seasons_x, y=y_vals,
                        name=met_lbl,
                        mode="lines+markers",
                        line=dict(color=col_dev, width=2.5),
                        marker=dict(size=9, color=col_dev,
                                    line=dict(color="white", width=1.5)),
                        fill="tozeroy",
                        fillcolor=f"rgba({r},{g_c},{b},0.07)",
                        hovertemplate=f"<b>{met_lbl}</b><br>%{{x}}: %{{y}}<extra></extra>",
                    ))

                fig_dev.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#7090b0", size=12),
                    xaxis=dict(gridcolor="#1a2540", tickfont=dict(color="#a0c0e0", size=12),
                               tickmode="array", tickvals=seasons_x),
                    yaxis=dict(gridcolor="#1a2540", tickfont=dict(color="#5070a0")),
                    legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)",
                                orientation="h", yanchor="bottom", y=-0.2, x=0.5, xanchor="center"),
                    margin=dict(l=20, r=20, t=30, b=60),
                    height=360,
                    hovermode="x unified",
                )
                st.plotly_chart(fig_dev, use_container_width=True, config={"displayModeBar":False})

                # ── Comparison table
                st.markdown("### Säsongsjämförelse")
                tbl_dev = {"Statistik": list(DEV_METRICS.keys())}
                for yr in seasons_x:
                    p_yr = dev_data[yr]
                    col_vals = []
                    for lbl, key in DEV_METRICS.items():
                        v = f(p_yr.get(key, 0))
                        if key == "min":
                            col_vals.append(f"{int(v):,}".replace(",",".") if v else "—")
                        elif key in ("sotPct","gkSavePct","gkCSPct"):
                            col_vals.append(f"{v:.1f}%" if v else "—")
                        elif key in ("glsPer90","astPer90","xGpx","xApx","gkGA90"):
                            col_vals.append(f"{v:.2f}" if v else "—")
                        else:
                            col_vals.append(str(int(v)) if v else "—")
                    tbl_dev[f"{yr} ({dev_data[yr].get('squad','')[:12]})"] = col_vals

                st.dataframe(pd.DataFrame(tbl_dev), use_container_width=True,
                             hide_index=True, height=500)

                # ── Radar overlay across seasons
                if len(yrs_found) >= 2:
                    st.divider()
                    st.markdown("### 📡 Radaröverlay — säsonger")
                    rad_mets_dev = [m for m in DEFAULT_RADAR.get(pg_dev, DEFAULT_RADAR["U"]) if m in ALL_RADAR]
                    chosen_rad_dev = st.multiselect("Radaraxlar", list(ALL_RADAR.keys()),
                                                     default=rad_mets_dev, key="dev_radar")
                    if len(chosen_rad_dev) >= 3:
                        season_player_data = [(f"{dev_sel} ({yr})", dev_data[yr]) for yr in yrs_found]
                        fig_rad = radar_chart(season_player_data, chosen_rad_dev, yrs_found[-1], show_avg=True)
                        if fig_rad:
                            st.plotly_chart(fig_rad, use_container_width=True, config={"displayModeBar":False})


# ══ VIEW: SÄSONGSÖVERSIKT ════════════════════════════════════════════════════
elif "Säsongsöversikt" in view:
    st.markdown(f"# 📅 IFK Göteborg Säsongsöversikt — {season}")

    # ── Load match data
    import os
    match_file = f"match_data_{season}.json"
    has_matches = os.path.exists(match_file)
    matches = []
    if has_matches:
        with open(match_file, encoding='utf-8') as mf:
            matches = json.load(mf)

    # df_all may be empty for seasons with only match data (e.g. 2024 before player files added)
    ifk_all = df_all[df_all.squad == "IFK Göteborg"].copy() if not df_all.empty else pd.DataFrame()
    sq_df   = squads_df(season)
    ifk_sq  = sq_df[sq_df.squad == "IFK Göteborg"].iloc[0].to_dict()               if not sq_df.empty and "IFK Göteborg" in sq_df.squad.values else {}

    # ── Season top metrics
    if matches:
        w = sum(1 for m in matches if m['result']=='W')
        d_ = sum(1 for m in matches if m['result']=='D')
        l = sum(1 for m in matches if m['result']=='L')
        pts = w*3+d_
        gf_tot = sum(m['gf'] for m in matches)
        ga_tot = sum(m['ga'] for m in matches)
        cs_tot = sum(m.get('cs',0) for m in matches)
        avg_poss = round(sum(m['poss'] for m in matches if m.get('poss'))/
                         max(1,sum(1 for m in matches if m.get('poss'))),1)
        avg_sh   = round(sum(m['sh'] for m in matches if m.get('sh'))/
                         max(1,sum(1 for m in matches if m.get('sh'))),1)
        avg_sot  = round(sum(m['sot'] for m in matches if m.get('sot'))/
                         max(1,sum(1 for m in matches if m.get('sot'))),1)

        c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
        c1.metric("⚽ Mål",         gf_tot)
        c2.metric("🛡 Insl. mål",   ga_tot)
        c3.metric("✅ Vinster",      w)
        c4.metric("🟡 Oavgjort",     d_)
        c5.metric("❌ Förluster",    l)
        c6.metric("📊 Poäng",        pts)
        c7.metric("🔒 Nollor",       cs_tot)
        c8.metric("🔵 Boll snitt",  f"{avg_poss}%")
        st.divider()

    # ── Match timeline
    if matches:
        st.markdown("### 📈 Säsongstidslinje")

        cum_gf, cum_ga, cum_pts = 0, 0, 0
        cum_gf_list, cum_ga_list, cum_pts_list = [], [], []
        cum_sh_list, cum_sot_list = [], []
        match_labels, result_colors = [], []
        cum_sh, cum_sot = 0, 0

        for m in matches:
            cum_gf  += m['gf']
            cum_ga  += m['ga']
            cum_pts += 3 if m['result']=='W' else (1 if m['result']=='D' else 0)
            cum_sh  += m.get('sh') or 0
            cum_sot += m.get('sot') or 0
            cum_gf_list.append(cum_gf)
            cum_ga_list.append(cum_ga)
            cum_pts_list.append(cum_pts)
            cum_sh_list.append(cum_sh)
            cum_sot_list.append(cum_sot)
            opp = m['opponent'][:12]
            match_labels.append(f"O{m['round']} {opp}")
            result_colors.append(
                "#30c060" if m['result']=='W' else
                "#f0a030" if m['result']=='D' else "#e05050"
            )

        tab_tl1, tab_tl2, tab_tl3 = st.tabs(["Mål & Poäng", "Skott", "Resultat per match"])

        with tab_tl1:
            fig_tl = go.Figure()
            fig_tl.add_trace(go.Scatter(
                x=match_labels, y=cum_pts_list, name="Poäng",
                mode="lines+markers", line=dict(color="#3a80ff", width=2.5),
                marker=dict(size=8, color=result_colors,
                            line=dict(color="white",width=1.5)),
                hovertemplate="<b>%{x}</b><br>Poäng: %{y}<extra></extra>",
            ))
            fig_tl.add_trace(go.Scatter(
                x=match_labels, y=cum_gf_list, name="Mål gjorda",
                mode="lines", line=dict(color="#30c060", width=2, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Mål: %{y}<extra></extra>",
            ))
            fig_tl.add_trace(go.Scatter(
                x=match_labels, y=cum_ga_list, name="Mål insläppta",
                mode="lines", line=dict(color="#e05050", width=2, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Insläppt: %{y}<extra></extra>",
            ))
            fig_tl.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#7090b0", size=11),
                xaxis=dict(gridcolor="#1a2540", tickangle=-45,
                           tickfont=dict(color="#5070a0",size=9)),
                yaxis=dict(gridcolor="#1a2540"),
                legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)",
                            orientation="h", y=-0.25, x=0.5, xanchor="center"),
                margin=dict(l=0,r=0,t=10,b=80), height=320, hovermode="x unified",
            )
            st.plotly_chart(fig_tl, use_container_width=True, config={"displayModeBar":False})

        with tab_tl2:
            fig_sh = go.Figure()
            sh_per_match   = [m.get('sh') or 0  for m in matches]
            sot_per_match  = [m.get('sot') or 0 for m in matches]
            sota_per_match = [m.get('sota') or 0 for m in matches]
            fig_sh.add_trace(go.Bar(
                x=match_labels, y=sh_per_match, name="Skott",
                marker_color="#f0a030", marker_line_width=0,
            ))
            fig_sh.add_trace(go.Bar(
                x=match_labels, y=sot_per_match, name="SoT",
                marker_color="#30c060", marker_line_width=0,
            ))
            fig_sh.add_trace(go.Bar(
                x=match_labels, y=sota_per_match, name="SoT emot",
                marker_color="#e05050", marker_line_width=0,
            ))
            fig_sh.update_layout(
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#7090b0",size=11),
                xaxis=dict(gridcolor="#1a2540", tickangle=-45,
                           tickfont=dict(color="#5070a0",size=9)),
                yaxis=dict(gridcolor="#1a2540"),
                legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)",
                            orientation="h", y=-0.25, x=0.5, xanchor="center"),
                margin=dict(l=0,r=0,t=10,b=80), height=320,
            )
            st.plotly_chart(fig_sh, use_container_width=True, config={"displayModeBar":False})

        with tab_tl3:
            # Matchlogg som tabell
            log_rows = []
            for m in matches:
                log_rows.append({
                    "Omgång": m['round'],
                    "Datum":  m['date'],
                    "Hemma/Borta": "🏠 Hem" if m['venue']=='Home' else "✈️ Borta",
                    "Motståndare": m['opponent'],
                    "Resultat": f"{m['gf']}–{m['ga']}",
                    "V/O/F":   {"W":"✅ V","D":"🟡 O","L":"❌ F"}.get(m['result'],''),
                    "Skott":   int(m['sh']) if m.get('sh') else '—',
                    "SoT":     int(m['sot']) if m.get('sot') else '—',
                    "SoT%":    f"{m['sot_pct']:.0f}%" if m.get('sot_pct') else '—',
                    "SoT emot":int(m['sota']) if m.get('sota') else '—',
                    "Räddningar":int(m['gk_saves']) if m.get('gk_saves') else '—',
                    "Räddn%":  f"{m['gk_save_pct']:.0f}%" if m.get('gk_save_pct') else '—',
                    "Nolla":   "✓" if m.get('cs') else '',
                    "Boll%":   f"{m['poss']:.0f}%" if m.get('poss') else '—',
                    "Åskådare":f"{int(m['attendance']):,}".replace(',','.') if m.get('attendance') else '—',
                    "Kapten":  m.get('captain',''),
                })
            log_df = pd.DataFrame(log_rows)
            st.dataframe(log_df, use_container_width=True, hide_index=True, height=500)

    st.divider()

    # ── Player contribution charts (always show)
    if not ifk_all.empty:
        st.markdown("### Spelarbidrag")
        tab1, tab2, tab3 = st.tabs(["⚽ Mål & Assist", "👟 Skott & SoT", "🛡 Försvar"])

        with tab1:
            top_c = ifk_all[ifk_all.gPluA > 0].sort_values("gPluA", ascending=True).tail(14)
            if not top_c.empty:
                fig_c = go.Figure()
                fig_c.add_trace(go.Bar(name="Mål", y=top_c.name,
                    x=top_c.gls, orientation="h",
                    marker_color="#3a80ff", marker_line_width=0))
                fig_c.add_trace(go.Bar(name="Assist", y=top_c.name,
                    x=top_c.ast, orientation="h",
                    marker_color="#00e8c8", marker_line_width=0))
                fig_c.update_layout(barmode="stack",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#7090b0",size=11),
                    xaxis=dict(gridcolor="#1a2540"),
                    yaxis=dict(tickfont=dict(color="#c0d8f0",size=11)),
                    legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0,r=20,t=10,b=20),
                    height=max(320,len(top_c)*32))
                st.plotly_chart(fig_c, use_container_width=True, config={"displayModeBar":False})

        with tab2:
            top_sh = ifk_all[ifk_all.sh > 0].sort_values("sh", ascending=True).tail(14)
            if not top_sh.empty:
                fig_sh2 = go.Figure()
                fig_sh2.add_trace(go.Bar(name="Skott", y=top_sh.name,
                    x=top_sh.sh, orientation="h",
                    marker_color="#f0a030", marker_line_width=0))
                fig_sh2.add_trace(go.Bar(name="SoT", y=top_sh.name,
                    x=top_sh.sot, orientation="h",
                    marker_color="#30c060", marker_line_width=0))
                fig_sh2.update_layout(barmode="group",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#7090b0",size=11),
                    xaxis=dict(gridcolor="#1a2540"),
                    yaxis=dict(tickfont=dict(color="#c0d8f0",size=11)),
                    legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0,r=20,t=10,b=20),
                    height=max(320,len(top_sh)*32))
                st.plotly_chart(fig_sh2, use_container_width=True, config={"displayModeBar":False})

        with tab3:
            if "int" in ifk_all.columns:
                top_def = ifk_all.copy()
                top_def["def_total"] = top_def["int"].apply(f) + top_def["tklW"].apply(f)
                top_def = top_def[top_def.def_total > 0].sort_values("def_total",ascending=True).tail(14)
                if not top_def.empty:
                    fig_def = go.Figure()
                    fig_def.add_trace(go.Bar(name="Brytningar", y=top_def.name,
                        x=top_def["int"], orientation="h",
                        marker_color="#30c060", marker_line_width=0))
                    fig_def.add_trace(go.Bar(name="Tacklingar", y=top_def.name,
                        x=top_def.tklW, orientation="h",
                        marker_color="#a050e0", marker_line_width=0))
                    fig_def.update_layout(barmode="stack",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#7090b0",size=11),
                        xaxis=dict(gridcolor="#1a2540"),
                        yaxis=dict(tickfont=dict(color="#c0d8f0",size=11)),
                        legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)"),
                        margin=dict(l=0,r=20,t=10,b=20),
                        height=max(320,len(top_def)*32))
                    st.plotly_chart(fig_def, use_container_width=True, config={"displayModeBar":False})


# ══ VIEW: NÄSTA STEG — Auto-Scout ════════════════════════════════════════════
elif "Nästa Steg" in view:
    st.markdown(f"# ⭐ Nästa Steg — Allsvenskan {season}")
    st.caption("Unga spelare som statistiskt är redo för en högre nivå")

    if df_all.empty:
        st.warning("Ingen data.")
        st.stop()

    # ── Scout-parametrar
    st.markdown("### Scouting-filter")
    fa, fb, fc, fd, fe = st.columns(5)
    with fa:
        max_age = st.slider("Max ålder", 18, 26, 23, key="ns_age")
    with fb:
        min_min = st.slider("Min minuter", 100, 1800, 500, key="ns_min")
    with fc:
        min_pct = st.slider("Min percentil", 40, 90, 65, key="ns_pct")
    with fd:
        ns_pos = st.selectbox("Position", ["Alla","GK","DF","MF","FW"],
                               label_visibility="collapsed", key="ns_pos")
    with fe:
        ifk_only = st.checkbox("Endast IFK Göteborg", value=False, key="ns_ifk")

    # ── Scoring per position
    POS_SCORE_KEYS = {
        "GK": ["gkSavePct","gkGA90","gkCSPct","gkSaves","gkW"],
        "DF": ["intPer90","tklWPer90","astPer90","xApx","crsPer90"],
        "MF": ["glsPer90","astPer90","intPer90","sotPct","xGpx","xApx"],
        "FW": ["glsPer90","sotPct","gPerSh","xGpx","fldPer90"],
        "U":  ["glsPer90","astPer90","intPer90","sotPct"],
    }
    POTENTIAL_BONUS = {  # Bonus for certain traits
        "young":        (lambda p: 10 if p.get("age",99) <= 20 else 5 if p.get("age",99) <= 21 else 0),
        "goals":        (lambda p: min(p.get("gls",0) * 2, 15)),
        "minutes_high": (lambda p: 5 if p.get("min",0) >= 2000 else 0),
        "xg_over":      (lambda p: 5 if (p.get("gMinusXG",0) or 0) > 0.5 else 0),
    }
    GRADE_LABEL = {
        "A+": ("#00e8c8", "🌟 Klar för topp-liga"),
        "A":  ("#30c060", "✅ Klar för högre nivå"),
        "B+": ("#7fd080", "📈 Nära genombrott"),
        "B":  ("#f0a030", "🔍 Lovande talang"),
        "C":  ("#d09030", "👀 En att bevaka"),
    }

    def scout_score(p_dict):
        pg      = pos_group(p_dict.get("pos",""))
        pct_d   = p_dict.get("pct", {})
        keys    = POS_SCORE_KEYS.get(pg, POS_SCORE_KEYS["U"])
        vals    = [float(pct_d.get(k, 0)) for k in keys if pct_d.get(k,0) > 0]
        base    = round(sum(vals)/len(vals)) if vals else 0
        bonus   = sum(fn(p_dict) for fn in POTENTIAL_BONUS.values())
        return min(base + bonus, 100)

    def scout_grade(score):
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 72: return "B+"
        if score >= 60: return "B"
        return "C"

    # ── Filter players
    candidates = df_all.copy()
    candidates = candidates[candidates["age"].apply(f) <= max_age]
    candidates = candidates[candidates["min"].apply(f)  >= min_min]
    if ns_pos != "Alla":
        candidates = candidates[candidates.pos_group == ns_pos]
    if ifk_only:
        candidates = candidates[candidates.squad == "IFK Göteborg"]

    # Score
    records = []
    for _, row in candidates.iterrows():
        pd_ = row.to_dict()
        sc  = scout_score(pd_)
        pg_ = pos_group(pd_.get("pos",""))
        key_pcts = POS_SCORE_KEYS.get(pg_, POS_SCORE_KEYS["U"])
        avg_pct  = round(sum(float(pd_.get("pct",{}).get(k,0)) for k in key_pcts) /
                         max(len([k for k in key_pcts if pd_.get("pct",{}).get(k,0)>0]),1))
        if avg_pct < min_pct: continue
        records.append({**pd_, "_score": sc, "_avg_pct": avg_pct, "_grade": scout_grade(sc)})

    records.sort(key=lambda x: -x["_score"])

    st.divider()
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("Spelare som matchar", len(records))
    ifk_matches = sum(1 for r in records if r.get("squad") == "IFK Göteborg")
    col_info2.metric("🔵 IFK Göteborg-talanger", ifk_matches)
    top_grade = records[0]["_grade"] if records else "—"
    col_info3.metric("Bästa betyg", top_grade)

    if not records:
        st.info("Inga spelare matchade kriterierna. Testa bredare filter.")
        st.stop()

    # ── Grade tabs
    grades = ["A+", "A", "B+", "B", "C"]
    grade_tabs = st.tabs([f"{GRADE_LABEL[g][0]} {g} — {GRADE_LABEL[g][1]}" for g in grades
                          if any(r["_grade"] == g for r in records)])
    tab_grades = [g for g in grades if any(r["_grade"] == g for r in records)]

    for tab, grade in zip(grade_tabs, tab_grades):
        grade_records = [r for r in records if r["_grade"] == grade]
        grade_color, grade_label = GRADE_LABEL[grade]
        with tab:
            st.markdown(f"<div style='color:{grade_color};font-weight:700;font-size:13px;"
                        f"margin-bottom:12px;'>{grade_label} · {len(grade_records)} spelare</div>",
                        unsafe_allow_html=True)

            cols_per_row = 3
            for row_i in range(0, len(grade_records), cols_per_row):
                cols = st.columns(cols_per_row)
                for col_i, p in enumerate(grade_records[row_i:row_i+cols_per_row]):
                    with cols[col_i]:
                        is_ifk   = p.get("squad") == "IFK Göteborg"
                        pg_      = pos_group(p.get("pos",""))
                        pct_d_   = p.get("pct", {})
                        age_     = int(f(p.get("age",0)))
                        score_   = p["_score"]
                        avg_pct_ = p["_avg_pct"]
                        # Key stat per position
                        if pg_ == "GK":
                            key_stat = f"{f(p.get('gkSavePct',0)):.1f}% räddningar"
                        elif pg_ == "FW":
                            key_stat = f"{f(p.get('gls',0))} mål · {f(p.get('glsPer90',0)):.2f}/90"
                        elif pg_ == "MF":
                            key_stat = f"{f(p.get('gls',0))}g {f(p.get('ast',0))}a · {f(p.get('intPer90',0)):.2f} bryt/90"
                        else:
                            key_stat = f"{f(p.get('int',0))} bryt · {f(p.get('tklW',0))} tackl"

                        # Strength highlights
                        strengths = []
                        for k, lbl in [("glsPer90","Mål/90"),("astPer90","Assist/90"),
                                        ("intPer90","Brutna boll/90"),("xGpx","xG/90"),
                                        ("gkSavePct","Räddning%"),("tklWPer90","Tacklingar/90")]:
                            pv = float(pct_d_.get(k, 0))
                            if pv >= 80:
                                strengths.append(f"<span style='color:#00e8c8;font-size:10px;'>★ {lbl} top {100-int(pv)}%</span>")

                        bar_w  = score_
                        bar_col= grade_color

                        st.markdown(f"""
<div style='background:{"#0a1525" if is_ifk else "#0d1829"};
     border:1px solid {"#1a4090" if is_ifk else "#1a2540"};
     border-radius:10px; padding:14px; margin-bottom:4px;'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'>
    <div>
      <div style='font-size:14px;font-weight:800;color:#e2e8f0;'>{p.get("name","")}</div>
      <div style='font-size:10px;color:#4a6080;margin-top:2px;'>
        {p.get("squad","")} · {p.get("pos","")} · {age_} år · {p.get("nation","")}
      </div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:24px;font-weight:900;color:{grade_color};line-height:1;'>{grade}</div>
      <div style='font-size:9px;color:#3a5070;'>betyg</div>
    </div>
  </div>
  <div style='font-size:11px;color:#7090b0;margin-bottom:8px;'>{key_stat}</div>
  {"".join(f"<div>{s}</div>" for s in strengths[:3])}
  <div style='margin-top:10px;'>
    <div style='display:flex;justify-content:space-between;font-size:9px;color:#3a5070;margin-bottom:3px;'>
      <span>Scout-poäng</span><span>{score_}/100</span>
    </div>
    <div style='background:#1a2540;border-radius:3px;height:5px;overflow:hidden;'>
      <div style='width:{bar_w}%;height:5px;border-radius:3px;
                  background:linear-gradient(90deg,{grade_color}88,{grade_color});'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:9px;color:#3a5070;margin-top:4px;'>
      <span>{int(f(p.get("min",0))):,} min'.replace(",",".")</span>
      <span>Pctl: {avg_pct_}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Top-10 tabell
    st.divider()
    st.markdown("### 📊 Komplett tabell")
    tbl_cols = ["name","squad","pos","age","min","gls","ast","_score","_grade"]
    tbl_ren  = {"name":"Spelare","squad":"Lag","pos":"Pos","age":"Ålder",
                "min":"Min","gls":"Mål","ast":"Ast","_score":"Scout-poäng","_grade":"Betyg"}
    tbl_rec  = [{k: r.get(k,"") for k in tbl_cols} for r in records]
    tbl_df   = pd.DataFrame(tbl_rec).rename(columns=tbl_ren)
    tbl_df["Min"] = tbl_df["Min"].apply(lambda v: str(int(f(v))).replace(",",".") if v else "—")
    st.dataframe(tbl_df, use_container_width=True, hide_index=True, height=440)

    # ── Djupanalys på vald spelare
    st.divider()
    st.markdown("### 🔬 Djupanalys")
    ns_player = st.selectbox("Välj spelare för djupanalys",
                              [r.get("name","") for r in records],
                              label_visibility="collapsed", key="ns_deep")
    if ns_player:
        p_ns = next((r for r in records if r.get("name") == ns_player), None)
        if p_ns:
            pg_ns = pos_group(p_ns.get("pos",""))
            rad_mets = [m for m in DEFAULT_RADAR.get(pg_ns, DEFAULT_RADAR["U"]) if m in ALL_RADAR]
            chosen_ns = st.multiselect("Radaraxlar", list(ALL_RADAR.keys()),
                                        default=rad_mets, key="ns_radar")
            if len(chosen_ns) >= 3:
                fig_ns = radar_chart([(ns_player, p_ns)], chosen_ns, season, show_avg=True)
                if fig_ns:
                    st.plotly_chart(fig_ns, use_container_width=True, config={"displayModeBar":False})
            scout_panel(p_ns, season)
# ══ VIEW: FORMTABELL ═════════════════════════════════════════════════════════
elif "Formtabell" in view:
    st.markdown(f"# 📋 Formtabell — Allsvenskan {season}")
    st.caption("Baserat på matchloggar för IFK Göteborg")

    import os as _os2, glob as _glob2
    match_files = sorted(_glob2.glob("match_data_*.json"), reverse=True)
    if not match_files:
        st.warning("Inga matchloggfiler hittades. Lägg till match_data_YYYY.json i mappen.")
        st.stop()

    n_form = st.radio("Visa senaste", [5, 10, 15, "Alla"],
                      horizontal=True, label_visibility="collapsed", key="form_n")

    all_seasons_data = {}
    for mf in match_files:
        yr = mf.replace("match_data_","").replace(".json","")
        with open(mf, encoding="utf-8") as f_mf:
            matches = json.load(f_mf)
        if n_form != "Alla":
            matches = matches[-int(n_form):]
        all_seasons_data[yr] = matches

    # ── Form per season
    for yr in sorted(all_seasons_data.keys(), reverse=True):
        matches = all_seasons_data[yr]
        if not matches: continue

        w = sum(1 for m in matches if m["result"]=="W")
        d_ = sum(1 for m in matches if m["result"]=="D")
        l = sum(1 for m in matches if m["result"]=="L")
        pts = w*3+d_
        gf = sum(m["gf"] for m in matches)
        ga = sum(m["ga"] for m in matches)

        form_icons = {"W":"🟢","D":"🟡","L":"🔴"}
        form_str = " ".join(form_icons.get(m["result"],"⚪") for m in matches)

        st.markdown(f"### {yr}")
        st.markdown(f"""
<div style='background:#0a1525;border:1px solid #1a3050;border-radius:10px;
     padding:16px 20px;margin-bottom:16px;'>
  <div style='font-size:20px;letter-spacing:4px;margin-bottom:12px;'>{form_str}</div>
  <div style='display:flex;gap:24px;flex-wrap:wrap;'>
    <div><span style='color:#4a6080;font-size:11px;'>VINSTER</span>
         <div style='color:#30c060;font-size:22px;font-weight:800;'>{w}</div></div>
    <div><span style='color:#4a6080;font-size:11px;'>OAVGJORT</span>
         <div style='color:#f0a030;font-size:22px;font-weight:800;'>{d_}</div></div>
    <div><span style='color:#4a6080;font-size:11px;'>FÖRLUSTER</span>
         <div style='color:#e05050;font-size:22px;font-weight:800;'>{l}</div></div>
    <div><span style='color:#4a6080;font-size:11px;'>POÄNG</span>
         <div style='color:#3a80ff;font-size:22px;font-weight:800;'>{pts}</div></div>
    <div><span style='color:#4a6080;font-size:11px;'>MÅL</span>
         <div style='color:#e2e8f0;font-size:22px;font-weight:800;'>{gf}–{ga}</div></div>
    <div><span style='color:#4a6080;font-size:11px;'>POÄNG/MATCH</span>
         <div style='color:#e2e8f0;font-size:22px;font-weight:800;'>{pts/max(len(matches),1):.2f}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

        # Match-för-match rad
        cols = st.columns(len(matches))
        for col_el, m in zip(cols, matches):
            res_col = {"W":"#30c060","D":"#f0a030","L":"#e05050"}.get(m["result"],"#5070a0")
            score = f"{m['gf']}–{m['ga']}"
            opp = m["opponent"][:8]
            hb = "H" if m["venue"]=="Home" else "B"
            col_el.markdown(f"""
<div style='background:#0d1829;border-top:3px solid {res_col};border-radius:0 0 6px 6px;
     padding:6px 4px;text-align:center;'>
  <div style='font-size:10px;color:#3a5070;'>{hb}</div>
  <div style='font-size:9px;color:#7090b0;'>{opp}</div>
  <div style='font-size:13px;font-weight:800;color:#e2e8f0;'>{score}</div>
  <div style='font-size:9px;color:{res_col};font-weight:700;'>{m["result"]}</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Skott & possession chart
        with st.expander(f"📊 Detaljstatistik {yr}"):
            sh_data = [m.get("sh",0) or 0 for m in matches]
            sot_data = [m.get("sot",0) or 0 for m in matches]
            poss_data = [m.get("poss",0) or 0 for m in matches]
            labels_f = [f"O{m['round']} {m['opponent'][:8]}" for m in matches]
            res_colors_f = [{"W":"#30c060","D":"#f0a030","L":"#e05050"}.get(m["result"],"#5070a0")
                           for m in matches]

            fig_form = go.Figure()
            fig_form.add_trace(go.Bar(
                x=labels_f, y=sh_data, name="Skott",
                marker=dict(color=res_colors_f, line_width=0),
                hovertemplate="%{x}<br>Skott: %{y}<extra></extra>",
            ))
            fig_form.add_trace(go.Scatter(
                x=labels_f, y=poss_data, name="Bollinnehav %",
                mode="lines+markers", yaxis="y2",
                line=dict(color="#3a80ff", width=2),
                marker=dict(size=6),
                hovertemplate="%{x}<br>Boll: %{y:.0f}%<extra></extra>",
            ))
            fig_form.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#7090b0", size=10),
                xaxis=dict(gridcolor="#1a2540", tickangle=-45,
                           tickfont=dict(color="#5070a0",size=9)),
                yaxis=dict(gridcolor="#1a2540", title="Skott"),
                yaxis2=dict(overlaying="y", side="right",
                            title="Boll %", range=[20,80],
                            tickfont=dict(color="#3a80ff")),
                legend=dict(font=dict(color="#a0c0e0"), bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=40,t=10,b=60), height=280,
            )
            st.plotly_chart(fig_form, use_container_width=True, config={"displayModeBar":False})



# ══ VIEW: NATIONALITETER ══════════════════════════════════════════════════════
elif "Nationaliteter" in view:
    st.markdown(f"# 🌍 Nationaliteter — {season}")
    nats = nats_data(season)
    if not nats:
        st.info("Ingen nationalitetsdata för denna säsong.")
        st.stop()

    # Season comparison dropdown
    other_seasons = [s for s in SEASONS_AVAIL if s != season and nats_data(s)]
    compare_season = st.selectbox("Jämför med säsong",
        ["—"] + other_seasons, label_visibility="collapsed", key="nat_compare")

    # Top nations cards
    top_nats = sorted(nats, key=lambda x: -x.get("players",0))[:10]
    cols_nat = st.columns(5)
    for i, nat in enumerate(top_nats[:10]):
        with cols_nat[i % 5]:
            st.markdown(f"""
<div style='background:#0a1525;border:1px solid #1a3050;border-radius:8px;
     padding:10px;text-align:center;margin-bottom:8px;'>
  <div style='font-size:13px;font-weight:700;color:#e2e8f0;'>{nat.get("nation","")}</div>
  <div style='font-size:10px;color:#4a6080;'>{nat.get("code","")}</div>
  <div style='font-size:22px;font-weight:900;color:#3a80ff;'>{nat.get("players",0)}</div>
  <div style='font-size:9px;color:#3a5070;'>spelare</div>
</div>""", unsafe_allow_html=True)

    st.divider()

    # Bar chart — all nations
    nat_sorted = sorted(nats, key=lambda x: -x.get("players",0))[:25]
    fig_nat = go.Figure(go.Bar(
        x=[n.get("code","") or n.get("nation","")[:3].upper() for n in nat_sorted],
        y=[n.get("players",0) for n in nat_sorted],
        marker_color="#3a80ff",
        hovertemplate="%{x}: %{y} spelare<extra></extra>",
    ))
    fig_nat.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#7090b0",size=11),
        xaxis=dict(gridcolor="#1a2540",tickfont=dict(color="#a0c0e0",size=10)),
        yaxis=dict(gridcolor="#1a2540"),
        margin=dict(l=0,r=0,t=10,b=40), height=320,
    )
    st.plotly_chart(fig_nat, use_container_width=True, config={"displayModeBar":False})

    # Compare with another season
    if compare_season != "—":
        nats2 = nats_data(compare_season)
        nat2_idx = {n.get("code",""): n.get("players",0) for n in nats2}
        nat1_idx = {n.get("code",""): n.get("players",0) for n in nats}
        all_codes = sorted(set(nat1_idx)|set(nat2_idx), key=lambda c: -(nat1_idx.get(c,0)+nat2_idx.get(c,0)))[:20]

        fig_cmp = go.Figure()
        fig_cmp.add_trace(go.Bar(name=season,
            x=all_codes, y=[nat1_idx.get(c,0) for c in all_codes],
            marker_color="#3a80ff"))
        fig_cmp.add_trace(go.Bar(name=compare_season,
            x=all_codes, y=[nat2_idx.get(c,0) for c in all_codes],
            marker_color="#f0a030"))
        fig_cmp.update_layout(barmode="group",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#7090b0",size=11),
            xaxis=dict(gridcolor="#1a2540",tickfont=dict(color="#a0c0e0",size=10)),
            yaxis=dict(gridcolor="#1a2540"),
            legend=dict(font=dict(color="#a0c0e0"),bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=0,r=0,t=10,b=40), height=320,
        )
        st.markdown(f"### {season} vs {compare_season}")
        st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar":False})

    # Full list
    st.divider()
    nat_df = pd.DataFrame(sorted(nats, key=lambda x: -x.get("players",0)))
    if not nat_df.empty:
        ren_nat = {"nation":"Nation","code":"Kod","players":"Spelare","min":"Minuter"}
        nat_df = nat_df.rename(columns={k:v for k,v in ren_nat.items() if k in nat_df.columns})
        if "Minuter" in nat_df.columns:
            nat_df["Minuter"] = nat_df["Minuter"].apply(lambda v: f"{float(v)*90:.0f}" if v else "—")
        st.dataframe(nat_df[[c for c in ["Nation","Kod","Spelare","Minuter"] if c in nat_df.columns]],
                     use_container_width=True, hide_index=True, height=500)


# ══ VIEW: DOMARE ══════════════════════════════════════════════════════════════
elif "Domare" in view:
    st.markdown(f"# 👨‍⚖️ Domare — Allsvenskan {season}")
    st.caption("Domarbedömning baserat på matchstatistik")

    domare = domare_data(season)
    if not domare:
        # Försök med senaste tillgängliga säsong med domardata
        for fallback_yr in sorted(SEASONS_AVAIL, reverse=True):
            fb_dom = domare_data(fallback_yr)
            if fb_dom:
                domare = fb_dom
                st.info(f"Visar domardata från {fallback_yr} (ingen data för {season}).")
                break
    if not domare:
        st.info("Ingen domardata tillgänglig. Lägg till Passning_YYYY.xlsx eller Statistik_YYYY.xlsx i Player/YEAR/ och kör process_data.py.")
        st.stop()

    # Sort options
    sort_d = st.radio("Sortera efter",
        ["Flest matcher","Frisparkar/match","Gula kort/match","Röda kort/match","Straff/match"],
        horizontal=True, label_visibility="collapsed", key="dom_sort")
    sort_key = {
        "Flest matcher":     "matches",
        "Frisparkar/match":  "fouls_pm",
        "Gula kort/match":   "yk_pm",
        "Röda kort/match":   "rk_pm",
        "Straff/match":      "pen_pm",
    }[sort_d]

    domare_sorted = sorted(domare, key=lambda x: -(x.get(sort_key) or 0))

    # ── Overview metrics
    total_m = sum(d.get("matches",0) or 0 for d in domare)
    avg_fpm = round(sum(d.get("fouls_pm",0) or 0 for d in domare)/len(domare),2)
    avg_yk  = round(sum(d.get("yk_pm",0)   or 0 for d in domare)/len(domare),2)
    total_p = sum(d.get("pen",0) or 0 for d in domare)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("👨‍⚖️ Domare",       len(domare))
    c2.metric("⚽ Frisparkar/match", avg_fpm)
    c3.metric("🟨 Gula kort/match",  avg_yk)
    c4.metric("🎯 Totalt straff",    int(total_p))

    st.divider()

    # ── Domarekort (cards)
    cols_per_row = 3
    for row_i in range(0, len(domare_sorted), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_i, d_ref in enumerate(domare_sorted[row_i:row_i+cols_per_row]):
            with cols[col_i]:
                name      = d_ref.get("name","")
                matches   = int(d_ref.get("matches") or 0)
                fouls_pm  = d_ref.get("fouls_pm") or 0
                yk_pm     = d_ref.get("yk_pm")    or 0
                rk_pm     = d_ref.get("rk_pm")    or 0
                pen       = int(d_ref.get("pen")   or 0)
                pen_pm    = d_ref.get("pen_pm")    or 0

                # Color coding — strict vs lenient
                strictness = yk_pm
                border_col = ("#e05050" if strictness >= 5 else
                              "#f0a030" if strictness >= 4 else
                              "#30c060")
                st.markdown(f"""
<div style='background:#0a1525;border:1px solid {border_col};border-radius:10px;
     padding:14px;margin-bottom:8px;'>
  <div style='font-size:15px;font-weight:800;color:#e2e8f0;margin-bottom:4px;'>{name}</div>
  <div style='font-size:10px;color:#4a6080;margin-bottom:10px;'>{matches} matcher</div>
  <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;'>
    <div style='text-align:center;'>
      <div style='font-size:18px;font-weight:700;color:#f0a030;'>{fouls_pm:.1f}</div>
      <div style='font-size:9px;color:#3a5070;'>Frispk/M</div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:18px;font-weight:700;color:#e0c020;'>{yk_pm:.2f}</div>
      <div style='font-size:9px;color:#3a5070;'>GK/M</div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:18px;font-weight:700;color:#e05050;'>{rk_pm:.2f}</div>
      <div style='font-size:9px;color:#3a5070;'>RK/M</div>
    </div>
  </div>
  <div style='margin-top:8px;border-top:1px solid #1a2540;padding-top:8px;
       display:flex;justify-content:space-between;'>
    <span style='font-size:11px;color:#4a6080;'>Straff totalt: <b style="color:#c0d8f0">{pen}</b></span>
    <span style='font-size:11px;color:#4a6080;'>Straff/M: <b style="color:#c0d8f0">{pen_pm:.2f}</b></span>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Jämförelsetabell
    st.divider()
    st.markdown("### Detaljerad tabell")
    dom_df = pd.DataFrame(domare_sorted)
    dom_df = dom_df.rename(columns={
        "name":"Domare","matches":"Matcher","fouls_pm":"Frispk/M",
        "yk_pm":"GK/M","rk_pm":"RK/M","pen":"Straff","pen_pm":"Straff/M"
    })
    for col in ["Frispk/M","GK/M","RK/M","Straff/M"]:
        if col in dom_df:
            dom_df[col] = dom_df[col].apply(lambda v: f"{v:.2f}" if v else "—")
    st.dataframe(dom_df, use_container_width=True, hide_index=True)

    # ── Stapeldiagram
    st.divider()
    metric_d = st.selectbox("Visualisera", 
        ["yk_pm","fouls_pm","rk_pm","pen_pm"],
        format_func=lambda x: {"yk_pm":"Gula kort/match","fouls_pm":"Frisparkar/match",
                                "rk_pm":"Röda kort/match","pen_pm":"Straff/match"}.get(x,x),
        label_visibility="collapsed", key="dom_metric")
    dom_vals = [d_ref.get(metric_d,0) or 0 for d_ref in domare_sorted]
    dom_cols = ["#e05050" if v == max(dom_vals) else "#1a3050" for v in dom_vals]
    fig_dom = go.Figure(go.Bar(
        x=[d_ref["name"] for d_ref in domare_sorted],
        y=dom_vals,
        marker=dict(color=dom_cols, line_width=0),
    ))
    fig_dom.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#7090b0",size=11),
        xaxis=dict(gridcolor="#1a2540", tickangle=-35, tickfont=dict(color="#a0c0e0",size=10)),
        yaxis=dict(gridcolor="#1a2540"),
        margin=dict(l=0,r=0,t=10,b=80), height=340,
    )
    st.plotly_chart(fig_dom, use_container_width=True, config={"displayModeBar":False})

# ══ VIEW: DOMARE ══════════════════════════════════════════════════════════════

