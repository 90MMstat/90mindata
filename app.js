// ─────────────────────────────────────────────────────────────────────────────
// ALLSVENSKAN ANALYTICS  —  app.js
// ─────────────────────────────────────────────────────────────────────────────

// ── State ────────────────────────────────────────────────────────────────────
let DB           = null;   // full data.json
let activeSeason = '2025';
let activeView   = 'squad';
let activePos    = 'ALL';
let activeTeam   = 'ALL';
let sortKey      = 'gls';
let searchQ      = '';
let teamSearch   = '';
let selectedPlayer = null;
let compareList  = [];     // max 3
let chartInst    = {};     // Chart.js instances keyed by id

// ── Spider metric config per position ────────────────────────────────────────
const SPIDER = {
  GK: [
    { key:'gkSavePct', lbl:'Räddn. %',  bar:'bar-blue',   inv:false, max:100 },
    { key:'gkGA90',    lbl:'IM/90',      bar:'bar-red',    inv:true,  max:3   },
    { key:'gkCSPct',   lbl:'Nollor %',  bar:'bar-green',  inv:false, max:100 },
    { key:'gkSoTA',    lbl:'SoT emot',  bar:'bar-purple', inv:true,  max:200 },
    { key:'gkW',       lbl:'Vinster',   bar:'bar-teal',   inv:false, max:30  },
  ],
  DF: [
    { key:'intPer90',  lbl:'Bryt./90',  bar:'bar-green',  inv:false, max:4   },
    { key:'tklWPer90', lbl:'Tackl./90', bar:'bar-blue',   inv:false, max:4   },
    { key:'crs',       lbl:'Krossn.',   bar:'bar-teal',   inv:false, max:80  },
    { key:'glsPer90',  lbl:'Mål/90',    bar:'bar-amber',  inv:false, max:0.5 },
    { key:'astPer90',  lbl:'Ass./90',   bar:'bar-purple', inv:false, max:0.4 },
    { key:'flsPer90',  lbl:'Fel/90',    bar:'bar-red',    inv:true,  max:3   },
  ],
  MF: [
    { key:'glsPer90',  lbl:'Mål/90',    bar:'bar-blue',   inv:false, max:1   },
    { key:'astPer90',  lbl:'Ass./90',   bar:'bar-purple', inv:false, max:0.6 },
    { key:'shPer90',   lbl:'Skott/90',  bar:'bar-amber',  inv:false, max:4   },
    { key:'sotPct',    lbl:'SoT%',      bar:'bar-teal',   inv:false, max:70  },
    { key:'intPer90',  lbl:'Bryt./90',  bar:'bar-green',  inv:false, max:4   },
    { key:'tklWPer90', lbl:'Tackl./90', bar:'bar-blue',   inv:false, max:4   },
    { key:'fldPer90',  lbl:'Frisparkar/90', bar:'bar-red',inv:false, max:3   },
  ],
  FW: [
    { key:'glsPer90',  lbl:'Mål/90',    bar:'bar-blue',   inv:false, max:1.5 },
    { key:'astPer90',  lbl:'Ass./90',   bar:'bar-purple', inv:false, max:0.6 },
    { key:'shPer90',   lbl:'Skott/90',  bar:'bar-amber',  inv:false, max:6   },
    { key:'sotPct',    lbl:'SoT%',      bar:'bar-teal',   inv:false, max:70  },
    { key:'gPerSh',    lbl:'Mål/Skott', bar:'bar-green',  inv:false, max:0.3 },
    { key:'fldPer90',  lbl:'Frispark./90',bar:'bar-red',  inv:false, max:4   },
  ],
};

const STAT_TABLE_COLS = [
  { key:'mp',       lbl:'M',       title:'Matcher' },
  { key:'min',      lbl:'Min',     fmt:v => v > 0 ? v.toLocaleString('sv-SE') : '—' },
  { key:'gls',      lbl:'Mål' },
  { key:'ast',      lbl:'Ast' },
  { key:'sh',       lbl:'Skott' },
  { key:'sot',      lbl:'SoT' },
  { key:'sotPct',   lbl:'SoT%',   fmt:v => v > 0 ? v.toFixed(1)+'%' : '—' },
  { key:'int',      lbl:'Bryt.' },
  { key:'tklW',     lbl:'Tackl.' },
  { key:'crdY',     lbl:'GK' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const f = v => typeof v === 'number' ? v : 0;
const pct = (v, max, inv=false) => {
  const p = Math.min(Math.round((f(v) / Math.max(max, 0.001)) * 100), 100);
  return inv ? 100 - p : p;
};

function posGroup(pos) {
  if (!pos) return 'U';
  if (pos.startsWith('GK') || pos === 'GK') return 'GK';
  if (pos.includes('GK')) return 'GK';
  const p = pos.split(',')[0];
  if (p === 'GK') return 'GK';
  if (p === 'DF') return 'DF';
  if (p === 'MF') return 'MF';
  if (p === 'FW') return 'FW';
  return 'U';
}

function posPill(pos) {
  const g = posGroup(pos);
  const map = { GK:'G', DF:'D', MF:'M', FW:'F', U:'?' };
  return `<span class="pc-pos-pill pill-${map[g]||'U'}">${map[g]||pos}</span>`;
}

function spiderKey(pos) {
  const g = posGroup(pos);
  return SPIDER[g] || SPIDER.MF;
}

function getColor(idx) {
  return ['#3a80ff','#30c060','#f0a030','#e05050','#a050e0'][idx % 5];
}

function pctBadge(p) {
  if (p >= 90) return `<span class="pp-pct-badge pct-elite">${p}</span>`;
  if (p >= 65) return `<span class="pp-pct-badge pct-good">${p}</span>`;
  if (p >= 35) return `<span class="pp-pct-badge pct-mid">${p}</span>`;
  return `<span class="pp-pct-badge pct-low">${p}</span>`;
}

function pctFillClass(pos) {
  const g = posGroup(pos);
  return { GK:'fill-G', DF:'fill-D', MF:'fill-M', FW:'fill-F', U:'fill-U' }[g] || 'fill-U';
}

function destroyChart(id) {
  if (chartInst[id]) { chartInst[id].destroy(); delete chartInst[id]; }
}

function currentPlayers() {
  const s = DB?.seasons?.[activeSeason];
  return s?.players || [];
}

function currentSquads() {
  const s = DB?.seasons?.[activeSeason];
  return s?.squads || [];
}

function filteredPlayers() {
  let ps = currentPlayers();
  if (activeTeam !== 'ALL') ps = ps.filter(p => p.squad === activeTeam);
  if (activePos  !== 'ALL') ps = ps.filter(p => posGroup(p.pos) === activePos);
  if (searchQ) ps = ps.filter(p => p.name.toLowerCase().includes(searchQ));
  if (sortKey === 'name_asc') ps.sort((a,b) => a.name.localeCompare(b.name,'sv'));
  else ps.sort((a,b) => f(b[sortKey]) - f(a[sortKey]));
  return ps;
}

function ifkPlayers() {
  return currentPlayers().filter(p => p.squad === 'IFK Göteborg');
}

// ── Load data ─────────────────────────────────────────────────────────────────
async function loadData() {
  setStatus('Laddar data…');
  try {
    const r = await fetch('/api/data');
    if (!r.ok) throw new Error('data.json inte hittad');
    DB = await r.json();
    const seasons = Object.keys(DB.seasons).filter(y => DB.seasons[y].players?.length > 0);
    if (seasons.includes('2025')) activeSeason = '2025';
    else activeSeason = seasons[0];
    setStatus(`${seasons.join(', ')} · ${currentPlayers().length} spelare`);
    init();
  } catch(e) {
    setStatus('Kör python process_data.py för att generera data!');
    $('view-squad').innerHTML = `<div class="no-data">⚠ ${e.message}<br><br>Kör <code>python process_data.py</code> och starta om servern.</div>`;
  }
}

function setStatus(t) { $('sb-status').textContent = t; }

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  renderSeasons();
  renderPosBtns();
  renderTeamBtns();
  renderView();
  setupEvents();
}

// ── Seasons ───────────────────────────────────────────────────────────────────
function renderSeasons() {
  const seasons = Object.keys(DB.seasons)
    .filter(y => DB.seasons[y].players?.length > 0 || DB.seasons[y].squads?.length > 0)
    .sort((a,b) => b - a);
  $('season-btns').innerHTML = seasons.map(y =>
    `<button class="season-btn ${y === activeSeason ? 'active' : ''}" data-season="${y}">${y}</button>`
  ).join('');
}

function renderPosBtns() {
  const filters = [
    { key:'ALL', lbl:'Alla' },
    { key:'GK',  lbl:'MV'  },
    { key:'DF',  lbl:'DEF' },
    { key:'MF',  lbl:'MID' },
    { key:'FW',  lbl:'FWD' },
  ];
  $('pos-btns').innerHTML = filters.map(f =>
    `<button class="pos-btn ${f.key === activePos ? 'active' : ''}" data-pos="${f.key}">${f.lbl}</button>`
  ).join('');
}

function renderTeamBtns() {
  const teams = [...new Set(currentPlayers().map(p => p.squad))].sort((a,b) => {
    if (a === 'IFK Göteborg') return -1;
    if (b === 'IFK Göteborg') return 1;
    return a.localeCompare(b,'sv');
  });
  const q = teamSearch.toLowerCase();
  const filtered = ['ALL', ...teams].filter(t =>
    t === 'ALL' || q === '' || t.toLowerCase().includes(q)
  );
  $('team-btns').innerHTML = filtered.map(t => {
    const isIfk = t === 'IFK Göteborg';
    const isAll = t === 'ALL';
    const cls   = `team-btn${isIfk ? ' ifk' : ''}${t === activeTeam ? ' active' : ''}`;
    return `<button class="${cls}" data-team="${t}">${isAll ? 'Alla lag' : t}</button>`;
  }).join('');
}

// ── Views ─────────────────────────────────────────────────────────────────────
function renderView() {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  $(`view-${activeView}`)?.classList.add('active');
  document.querySelector(`[data-view="${activeView}"]`)?.classList.add('active');

  const titles = {
    squad:'IFK Göteborg', league:'Alla spelare',
    compare:'Jämför spelare', teams:'Lagöversikt'
  };
  $('view-title').textContent = titles[activeView] || '';

  switch(activeView) {
    case 'squad':   renderSquad();   break;
    case 'league':  renderLeague();  break;
    case 'compare': renderCompare(); break;
    case 'teams':   renderTeams();   break;
  }
}

// ── Squad view ────────────────────────────────────────────────────────────────
function renderSquad() {
  const ps = ifkPlayers();
  const sq = currentSquads().find(s => s.squad === 'IFK Göteborg');

  $('view-sub').textContent = `Allsvenskan ${activeSeason} · ${ps.length} spelare`;

  // Hero stats
  const heroStats = [
    { val: sq?.mp || 0,      lbl:'Matcher',     sub:'spelade' },
    { val: sq?.gls || ps.reduce((s,p)=>s+f(p.gls),0), lbl:'Mål',    sub:'säsong', hi:true },
    { val: sq?.ast || ps.reduce((s,p)=>s+f(p.ast),0), lbl:'Assist',  sub:'säsong' },
    { val: sq?.sh  || ps.reduce((s,p)=>s+f(p.sh),0),  lbl:'Skott',   sub:'säsong' },
    { val: sq?.sotPct ? sq.sotPct.toFixed(1)+'%' : '—', lbl:'SoT%', sub:'skott på mål' },
    { val: sq?.poss ? sq.poss.toFixed(1)+'%' : '—', lbl:'Bollinnehav', sub:'snitt' },
    { val: ps.reduce((s,p)=>s+f(p.int),0), lbl:'Brytningar', sub:'säsong' },
    { val: ps.reduce((s,p)=>s+f(p.crdY),0), lbl:'Gula kort', sub:'säsong' },
  ];

  $('squad-hero').innerHTML = heroStats.map(s =>
    `<div class="hero-stat${s.hi?' highlight':''}">
       <div class="hero-val${s.hi?' blue':''}">${s.val}</div>
       <div class="hero-lbl">${s.lbl}</div>
       <div class="hero-sub">${s.sub}</div>
     </div>`
  ).join('');

  // Player cards sorted by minutes
  let filtered = ps;
  if (searchQ) filtered = ps.filter(p => p.name.toLowerCase().includes(searchQ));
  if (activePos !== 'ALL') filtered = filtered.filter(p => posGroup(p.pos) === activePos);
  if (sortKey === 'name_asc') filtered.sort((a,b) => a.name.localeCompare(b.name,'sv'));
  else filtered.sort((a,b) => f(b[sortKey]) - f(a[sortKey]));

  // Get percentile for main stat vs all players in same position
  const allPs = currentPlayers();

  $('squad-grid').innerHTML = filtered.map(p => {
    const g      = posGroup(p.pos);
    const spdr   = spiderKey(p.pos);
    const pctVal = p.pct?.[spdr[0]?.key] || 0;
    const fillCls = pctFillClass(p.pos);

    const isGK  = g === 'GK';
    const s1Key = isGK ? 'gkSavePct' : 'gls';
    const s1Lbl = isGK ? 'Save%' : 'Mål';
    const s1Val = isGK ? (f(p.gkSavePct).toFixed(1)+'%') : f(p.gls);
    const s2Key = isGK ? 'gkCS' : 'ast';
    const s2Lbl = isGK ? 'Nollor' : 'Ass.';
    const s2Val = isGK ? f(p.gkCS) : f(p.ast);
    const s3Key = 'min';
    const s3Val = p.min > 0 ? (p.min/1000*1000).toLocaleString('sv-SE') : '—';

    const hi1 = f(p[s1Key]) > 0;

    return `
      <div class="player-card${selectedPlayer?.name === p.name ? ' active':''}" data-name="${p.name}">
        ${posPill(p.pos)}
        <div class="pc-name">${p.name}</div>
        <div class="pc-squad">${p.pos} · ${p.nation}</div>
        <div class="pc-stats">
          <div class="pc-stat">
            <div class="pc-stat-val${hi1?' highlight':''}">${s1Val}</div>
            <div class="pc-stat-lbl">${s1Lbl}</div>
          </div>
          <div class="pc-stat">
            <div class="pc-stat-val">${s2Val}</div>
            <div class="pc-stat-lbl">${s2Lbl}</div>
          </div>
          <div class="pc-stat">
            <div class="pc-stat-val">${s3Val}</div>
            <div class="pc-stat-lbl">Min</div>
          </div>
        </div>
        <div class="pc-pct-bar">
          <div class="pc-pct-fill ${fillCls}" style="width:${pctVal}%"></div>
        </div>
      </div>`;
  }).join('') || '<div class="no-data">Inga spelare matchar filtret.</div>';
}

// ── League table ──────────────────────────────────────────────────────────────
function renderLeague() {
  const ps = filteredPlayers();
  $('view-sub').textContent = `${ps.length} spelare · Allsvenskan ${activeSeason}`;

  const thead = `
    <th>Spelare</th>
    <th title="Position">Pos</th>
    ${STAT_TABLE_COLS.map(c => `<th title="${c.title||c.lbl}">${c.lbl}</th>`).join('')}
  `;
  $('league-table') && ($('league-table').querySelector('thead tr').innerHTML = thead);

  // Find top values for coloring
  const tops = {};
  for (const col of STAT_TABLE_COLS) {
    const vals = ps.map(p => f(p[col.key])).filter(v => v > 0);
    tops[col.key] = vals.length ? Math.max(...vals) : 0;
  }

  const tbody = ps.map(p => {
    const isIfk = p.squad === 'IFK Göteborg';
    const g = posGroup(p.pos);
    const pill = `<span class="td-pos pill-${({GK:'G',DF:'D',MF:'M',FW:'F'}[g]||'U')}">${g}</span>`;
    const initials = p.name.split(' ').map(w=>w[0]).slice(0,2).join('');

    const cells = STAT_TABLE_COLS.map(col => {
      const v   = f(p[col.key]);
      const raw = col.fmt ? col.fmt(v) : (v > 0 ? v : '');
      const top = tops[col.key] > 0 && v === tops[col.key] ? 'val-top' : v > 0 ? 'val-high' : 'val-zero';
      return `<td class="${top}">${raw || '—'}</td>`;
    }).join('');

    return `
      <tr class="${isIfk?'ifk-row':''} ${selectedPlayer?.name===p.name?'active':''}" data-name="${p.name}">
        <td>
          <div class="td-player">
            <div class="td-avatar">${initials}</div>
            <div>
              <div class="td-name">${p.name}</div>
              <div class="td-squad">${p.squad}</div>
            </div>
          </div>
        </td>
        <td>${pill}</td>
        ${cells}
      </tr>`;
  }).join('');

  $('league-table') && ($('league-table').querySelector('tbody').innerHTML = tbody ||
    '<tr><td colspan="15" class="no-data">Inga spelare.</td></tr>');
}

// ── Teams view ────────────────────────────────────────────────────────────────
function renderTeams() {
  const squads = currentSquads();
  const players = currentPlayers();
  $('view-sub').textContent = `${squads.length} lag · Allsvenskan ${activeSeason}`;

  const maxGls  = Math.max(...squads.map(s=>f(s.gls)), 1);
  const maxSh   = Math.max(...squads.map(s=>f(s.sh)),  1);
  const maxSoT  = Math.max(...squads.map(s=>f(s.sot)), 1);
  const maxInt  = Math.max(...squads.map(s => {
    const sp = players.filter(p => p.squad === s.squad);
    return sp.reduce((a,p)=>a+f(p.int),0);
  }), 1);

  $('view-teams').innerHTML = squads
    .sort((a,b) => f(b.gls) - f(a.gls))
    .map(sq => {
      const isIfk = sq.squad === 'IFK Göteborg';
      const sp = players.filter(p => p.squad === sq.squad);
      const ints = sp.reduce((a,p)=>a+f(p.int),0);

      const bars = [
        { lbl:'Mål',    val:sq.gls,       max:maxGls,  cls:'bar-blue',  fmt:v=>v },
        { lbl:'Skott',  val:sq.sh,        max:maxSh,   cls:'bar-amber', fmt:v=>v },
        { lbl:'SoT',    val:sq.sot,       max:maxSoT,  cls:'bar-teal',  fmt:v=>v },
        { lbl:'Bryt.',  val:ints,         max:maxInt,  cls:'bar-green', fmt:v=>v },
      ];

      return `
        <div class="team-card${isIfk?' ifk':''}" data-team="${sq.squad}">
          <div class="tc-name${isIfk?' ifk':''}">${sq.squad}</div>
          <div class="tc-stats">
            <div class="tc-stat"><div class="tc-val">${sq.gls||0}</div><div class="tc-lbl">Mål</div></div>
            <div class="tc-stat"><div class="tc-val">${sq.ast||0}</div><div class="tc-lbl">Ast</div></div>
            <div class="tc-stat"><div class="tc-val">${sq.sh||0}</div><div class="tc-lbl">Skott</div></div>
            <div class="tc-stat"><div class="tc-val">${sq.poss?sq.poss.toFixed(0)+'%':'—'}</div><div class="tc-lbl">Boll</div></div>
          </div>
          ${bars.map(b => {
            const w = Math.round((f(b.val)/b.max)*100);
            return `
              <div class="tc-bar-row">
                <div class="tc-bar-label">${b.lbl}</div>
                <div class="tc-bar-wrap"><div class="tc-bar-fill ${b.cls}" style="width:${w}%"></div></div>
                <div class="tc-bar-val">${b.fmt(f(b.val))}</div>
              </div>`;
          }).join('')}
        </div>`;
    }).join('') || '<div class="no-data">Ingen lagdata tillgänglig.</div>';
}

// ── Compare view ──────────────────────────────────────────────────────────────
function renderCompare() {
  $('view-sub').textContent = 'Välj upp till 3 spelare att jämföra';
  const container = $('view-compare');

  if (!compareList.length) {
    container.innerHTML = `
      <div class="compare-empty">
        <span>⇄</span>
        Lägg till spelare via spelarpanelen eller sökresultaten.
      </div>`;
    return;
  }

  // Slots
  const slots = [0,1,2].map(i => {
    const p = compareList[i];
    if (!p) return `
      <div class="cmp-slot" data-slot="${i}">
        <div class="cmp-slot-ph"><span class="plus">+</span>Lägg till spelare</div>
      </div>`;
    const g = posGroup(p.pos);
    return `
      <div class="cmp-slot filled" data-slot="${i}">
        <div class="cmp-slot-name">${p.name}</div>
        <div class="cmp-slot-sub">${p.squad} · ${p.pos}</div>
        <button class="cmp-slot-rm" data-rm="${i}">✕</button>
      </div>`;
  });

  // Spider data
  const metrics = spiderKey(compareList[0].pos);
  const radarLabels = metrics.map(m => m.lbl);
  const radarDatasets = compareList.map((p, i) => ({
    label: p.name,
    data:  metrics.map(m => p.pct?.[m.key] ?? pct(p[m.key], m.max, m.inv)),
    borderColor:     getColor(i),
    backgroundColor: getColor(i) + '22',
    borderWidth: 2,
    pointRadius: 3,
  }));

  // Stat comparison table rows
  const statRows = [
    { lbl:'Mål',          key:'gls' },
    { lbl:'Assist',       key:'ast' },
    { lbl:'Minuter',      key:'min',      fmt:v=>v.toLocaleString('sv-SE') },
    { lbl:'Skott',        key:'sh' },
    { lbl:'SoT',          key:'sot' },
    { lbl:'SoT%',         key:'sotPct',  fmt:v=>v.toFixed(1)+'%' },
    { lbl:'Mål/90',       key:'glsPer90',fmt:v=>v.toFixed(2) },
    { lbl:'Ass./90',      key:'astPer90',fmt:v=>v.toFixed(2) },
    { lbl:'Skott/90',     key:'shPer90', fmt:v=>v.toFixed(2) },
    { lbl:'Brytningar',   key:'int' },
    { lbl:'Tacklingar',   key:'tklW' },
    { lbl:'Felspel',      key:'fls' },
    { lbl:'Gula kort',    key:'crdY' },
  ];

  container.innerHTML = `
    <div class="cmp-slots">${slots.join('')}</div>
    <div class="cmp-chart-row">
      <div class="cmp-chart-box">
        <div class="cmp-chart-title">Prestationsprofil (percentil vs liga)</div>
        <div class="cmp-radar-wrap"><canvas id="cmp-radar"></canvas></div>
      </div>
      <div class="cmp-chart-box">
        <div class="cmp-chart-title">Nyckeltal jämförelse</div>
        <div class="cmp-bar-wrap"><canvas id="cmp-bar" height="280"></canvas></div>
      </div>
    </div>
    <div class="cmp-table">
      <table>
        <thead>
          <tr>
            <th>Statistik</th>
            ${compareList.map(p=>`<th>${p.name.split(' ').slice(-1)[0]}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${statRows.map(row => {
            const vals  = compareList.map(p => f(p[row.key]));
            const maxV  = Math.max(...vals);
            return `
              <tr>
                <td class="td-metric">${row.lbl}</td>
                ${compareList.map((p,i) => {
                  const v    = f(p[row.key]);
                  const disp = row.fmt ? row.fmt(v) : v || '—';
                  const best = v > 0 && v === maxV && !['crdY','fls','crdR'].includes(row.key);
                  return `<td class="${best?'td-best':''}">${disp}</td>`;
                }).join('')}
              </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;

  // Render charts
  requestAnimationFrame(() => {
    destroyChart('cmp-radar');
    const rc = document.getElementById('cmp-radar');
    if (rc) {
      chartInst['cmp-radar'] = new Chart(rc, {
        type: 'radar',
        data: { labels: radarLabels, datasets: radarDatasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            r: {
              min:0, max:100,
              grid:        { color:'#1a2540', lineWidth:0.8 },
              angleLines:  { color:'#1a2540', lineWidth:0.8 },
              ticks:       { display:false },
              pointLabels: { color:'#5070a0', font:{ size:11 } },
            }
          },
          plugins: {
            legend: { labels:{ color:'#7090b0', font:{ size:11 } } }
          }
        }
      });
    }

    destroyChart('cmp-bar');
    const bc = document.getElementById('cmp-bar');
    if (bc) {
      const barMetrics = statRows.slice(0,6);
      chartInst['cmp-bar'] = new Chart(bc, {
        type: 'bar',
        data: {
          labels: barMetrics.map(m=>m.lbl),
          datasets: compareList.map((p,i) => ({
            label: p.name.split(' ').slice(-1)[0],
            data:  barMetrics.map(m => f(p[m.key])),
            backgroundColor: getColor(i) + 'aa',
            borderColor:     getColor(i),
            borderWidth: 1, borderRadius: 2,
          }))
        },
        options: {
          responsive:true, maintainAspectRatio:false,
          scales: {
            x: { ticks:{ color:'#5070a0', font:{size:10} }, grid:{ color:'#1a2540' } },
            y: { ticks:{ color:'#5070a0', font:{size:10} }, grid:{ color:'#1a2540' } }
          },
          plugins: {
            legend: { labels:{ color:'#7090b0', font:{size:11} } }
          }
        }
      });
    }
  });
}

// ── Player panel ──────────────────────────────────────────────────────────────
function openPanel(player) {
  selectedPlayer = player;
  $('player-panel').classList.remove('hidden');
  renderPanelHeader(player);
  renderPanelBody(player);
  // Refresh active state in table/grid
  if (activeView === 'league') {
    document.querySelectorAll('#league-table tbody tr').forEach(r => {
      r.classList.toggle('active', r.dataset.name === player.name);
    });
  }
  if (activeView === 'squad') {
    document.querySelectorAll('.player-card').forEach(c => {
      c.classList.toggle('active', c.dataset.name === player.name);
    });
  }
}

function closePanel() {
  selectedPlayer = null;
  $('player-panel').classList.add('hidden');
  destroyChart('pp-radar');
  document.querySelectorAll('.player-card, #league-table tbody tr').forEach(el => {
    el.classList.remove('active');
  });
}

function renderPanelHeader(p) {
  const isIfk = p.squad === 'IFK Göteborg';
  $('pp-identity').innerHTML = `
    <div class="pp-name">${p.name}</div>
    <div class="pp-tags">
      <span class="pp-tag tag-pos-${posGroup(p.pos)[0]}">${p.pos}</span>
      ${p.nation ? `<span class="pp-tag tag-nat">${p.nation}</span>` : ''}
      <span class="pp-tag ${isIfk?'tag-ifk':'tag-squad'}">${p.squad}</span>
      ${p.age  ? `<span class="pp-tag tag-age">${p.age} år</span>` : ''}
      ${p.min  ? `<span class="pp-tag tag-min">${p.min.toLocaleString('sv-SE')} min</span>` : ''}
    </div>`;
}

function renderPanelBody(p) {
  const body  = $('pp-body');
  const g     = posGroup(p.pos);
  const isGK  = g === 'GK';
  const metrics = spiderKey(p.pos);

  // Section builder
  const section = (title, rows) => `
    <div class="pp-section">
      <div class="pp-section-title">${title}</div>
      ${rows}
    </div>`;

  const row = (lbl, val, barPct, barCls, valClass='', warn=false, top=false) => {
    const v = val ?? 0;
    const display = v === 0 ? '—' : String(v);
    const cls = top ? 'pp-stat-val top' : warn ? 'pp-stat-val warn' : 'pp-stat-val';
    const isZero = v === 0;
    return `
      <div class="pp-stat-row${isZero?' zero':''}">
        <span class="pp-stat-lbl">${lbl}</span>
        <div class="pp-stat-bar">
          <div class="pp-stat-fill ${barCls}" style="width:${Math.min(barPct,100)}%"></div>
        </div>
        <span class="${cls}">${display}</span>
      </div>`;
  };

  const pctRow = (lbl, key, barCls, max, inv=false, fmt=null) => {
    const v     = f(p[key]);
    const pctV  = p.pct?.[key] ?? pct(v, max, inv);
    const disp  = fmt ? fmt(v) : (v > 0 ? v : 0);
    const top   = pctV >= 90;
    const warn  = inv && v > 0;
    return `
      <div class="pp-stat-row${v===0?' zero':''}">
        <span class="pp-stat-lbl">${lbl}</span>
        <div class="pp-stat-bar"><div class="pp-stat-fill ${barCls}" style="width:${pctV}%"></div></div>
        <span class="pp-stat-val${top?' top':warn?' warn':''}">${fmt ? fmt(v) : (v || '—')}</span>
      </div>`;
  };

  let sections = '';

  if (isGK) {
    sections += section('Målvakt', [
      pctRow('Räddningar %','gkSavePct','bar-blue',  100,  false, v=>v.toFixed(1)+'%'),
      pctRow('IM / 90',     'gkGA90',   'bar-red',   3,    true,  v=>v.toFixed(2)),
      pctRow('Nollor',      'gkCS',     'bar-green', 20),
      pctRow('Nollor %',    'gkCSPct',  'bar-teal',  100,  false, v=>v.toFixed(1)+'%'),
      pctRow('SoT emot',    'gkSoTA',   'bar-purple',200,  true),
      pctRow('Räddningar',  'gkSaves',  'bar-blue',  200),
    ].join(''));
    sections += section('Disciplin', [
      pctRow('Gula kort','crdY','bar-amber',10,true),
      pctRow('Röda kort','crdR','bar-red',  3, true),
    ].join(''));
  } else {
    sections += section('Anfall', [
      pctRow('Mål',           'gls',     'bar-blue',  20),
      pctRow('Mål / 90',      'glsPer90','bar-blue',  1.5, false, v=>v.toFixed(2)),
      pctRow('Assist',        'ast',     'bar-purple',15),
      pctRow('Assist / 90',   'astPer90','bar-purple',0.6, false, v=>v.toFixed(2)),
      pctRow('Skott',         'sh',      'bar-amber', 100),
      pctRow('SoT',           'sot',     'bar-teal',  50),
      pctRow('SoT %',         'sotPct',  'bar-teal',  70,  false, v=>v.toFixed(1)+'%'),
      pctRow('Mål / skott',   'gPerSh',  'bar-green', 0.3, false, v=>v.toFixed(2)),
      pctRow('Straff',        'pk',      'bar-amber', 5),
    ].join(''));
    sections += section('Försvar', [
      pctRow('Brytningar',    'int',      'bar-green', 60),
      pctRow('Brit./90',      'intPer90', 'bar-green', 4,  false, v=>v.toFixed(2)),
      pctRow('Tacklingar',    'tklW',     'bar-blue',  80),
      pctRow('Tackl./90',     'tklWPer90','bar-blue',  4,  false, v=>v.toFixed(2)),
      pctRow('Krossningar',   'crs',      'bar-teal',  80),
    ].join(''));
    sections += section('Dueller & Övrigt', [
      pctRow('Felspel mot',   'fld',    'bar-green',100),
      pctRow('Felspel mot/90','fldPer90','bar-green',5,  false, v=>v.toFixed(2)),
      pctRow('Felspel gjort', 'fls',    'bar-red',  80, true),
      pctRow('Offside',       'off',    'bar-amber',20, true),
      pctRow('Straffvunna',   'pkWon',  'bar-teal', 5),
    ].join(''));
    sections += section('Disciplin', [
      pctRow('Gula kort','crdY','bar-amber',12,true),
      pctRow('Röda kort','crdR','bar-red',  3, true),
    ].join(''));
  }

  body.innerHTML = `
    <div class="pp-section">
      <div class="pp-section-title">Prestationsprofil (percentil)</div>
      <div class="pp-radar-box">
        <canvas id="pp-radar" height="175"></canvas>
      </div>
    </div>
    ${sections}`;

  // Draw radar
  requestAnimationFrame(() => {
    destroyChart('pp-radar');
    const cv = document.getElementById('pp-radar');
    if (!cv) return;
    const fillCls = { GK:'#5060e0',DF:'#20a050',MF:'#c09030',FW:'#e03030',U:'#4a6080' };
    const col = fillCls[g] || '#3a80ff';
    chartInst['pp-radar'] = new Chart(cv, {
      type: 'radar',
      data: {
        labels: metrics.map(m=>m.lbl),
        datasets: [{
          data: metrics.map(m => p.pct?.[m.key] ?? pct(p[m.key],m.max,m.inv)),
          borderColor: col, borderWidth:2,
          backgroundColor: col+'30',
          pointRadius:3, pointBackgroundColor: col,
          pointHoverRadius:4,
        }]
      },
      options: {
        responsive:true, maintainAspectRatio:false,
        scales: {
          r: {
            min:0, max:100,
            grid:        { color:'#1a2540', lineWidth:0.7 },
            angleLines:  { color:'#1a2540', lineWidth:0.7 },
            ticks:       { display:false },
            pointLabels: { color:'#5070a0', font:{size:10} },
          }
        },
        plugins: { legend:{ display:false } }
      }
    });
  });
}

// ── Events ────────────────────────────────────────────────────────────────────
function setupEvents() {

  // Nav
  document.querySelectorAll('.nav-item').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      activeView = a.dataset.view;
      renderView();
    });
  });

  // Season (delegated)
  $('season-btns').addEventListener('click', e => {
    const b = e.target.closest('.season-btn');
    if (!b) return;
    activeSeason = b.dataset.season;
    document.querySelectorAll('.season-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    closePanel();
    renderTeamBtns();
    renderView();
  });

  // Position
  $('pos-btns').addEventListener('click', e => {
    const b = e.target.closest('.pos-btn');
    if (!b) return;
    activePos = b.dataset.pos;
    document.querySelectorAll('.pos-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    renderView();
  });

  // Team filter
  $('team-search').addEventListener('input', e => {
    teamSearch = e.target.value;
    renderTeamBtns();
  });

  $('team-btns').addEventListener('click', e => {
    const b = e.target.closest('.team-btn');
    if (!b) return;
    activeTeam = b.dataset.team;
    document.querySelectorAll('.team-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    if (activeTeam !== 'ALL' && activeView === 'squad') {
      activeView = 'league';
      renderView();
    } else renderView();
  });

  // Player search
  $('player-search').addEventListener('input', e => {
    searchQ = e.target.value.toLowerCase();
    renderView();
  });

  // Sort
  $('sort-sel').addEventListener('change', e => {
    sortKey = e.target.value;
    renderView();
  });

  // Player card clicks (squad)
  $('view-squad').addEventListener('click', e => {
    const card = e.target.closest('.player-card');
    if (!card) return;
    const p = currentPlayers().find(p => p.name === card.dataset.name);
    if (!p) return;
    if (selectedPlayer?.name === p.name) closePanel();
    else openPanel(p);
  });

  // League table row clicks
  $('view-league').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-name]');
    if (!tr) return;
    const p = currentPlayers().find(p => p.name === tr.dataset.name);
    if (!p) return;
    if (selectedPlayer?.name === p.name) closePanel();
    else openPanel(p);
  });

  // Teams view - click team → league filtered
  $('view-teams').addEventListener('click', e => {
    const card = e.target.closest('[data-team]');
    if (!card) return;
    activeTeam = card.dataset.team;
    activeView = 'league';
    renderTeamBtns();
    renderView();
  });

  // Compare slot clicks
  $('view-compare').addEventListener('click', e => {
    const rm = e.target.closest('[data-rm]');
    if (rm) {
      compareList.splice(+rm.dataset.rm, 1);
      renderCompare(); return;
    }
    const slot = e.target.closest('.cmp-slot:not(.filled)');
    if (slot) { showPickerForCompare(); }
  });

  // Panel close
  $('pp-close').addEventListener('click', closePanel);

  // Add to compare
  $('pp-compare-btn').addEventListener('click', () => {
    if (!selectedPlayer) return;
    if (compareList.length >= 3) compareList.shift();
    if (!compareList.find(p=>p.name===selectedPlayer.name)) {
      compareList.push(selectedPlayer);
    }
    activeView = 'compare';
    renderView();
  });
}

// ── Picker (for compare) ──────────────────────────────────────────────────────
function showPickerForCompare() {
  // Simple: show a quick overlay with player list
  const ps = currentPlayers().sort((a,b)=>a.name.localeCompare(b.name,'sv'));
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:100;
    display:flex;align-items:center;justify-content:center;`;

  const modal = document.createElement('div');
  modal.style.cssText = `
    background:#060c18;border:1px solid #1a2540;border-radius:12px;
    width:480px;max-height:70vh;display:flex;flex-direction:column;overflow:hidden;`;

  modal.innerHTML = `
    <div style="padding:14px 16px;border-bottom:1px solid #1a2540;display:flex;align-items:center;justify-content:space-between;">
      <span style="color:#c0d8f0;font-weight:600;font-size:13px">Välj spelare</span>
      <button id="pk-close" style="background:none;border:none;color:#4a6080;font-size:16px;cursor:pointer;font-family:inherit">✕</button>
    </div>
    <input id="pk-search" type="text" placeholder="Sök spelare…" style="
      margin:10px 12px;padding:7px 12px;border-radius:6px;
      border:1px solid #1a2540;background:#080e1c;color:#a0c0e0;
      font-size:12px;font-family:inherit;outline:none;">
    <div id="pk-list" style="overflow-y:auto;padding:4px 8px 12px;flex:1;"></div>`;

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const renderList = q => {
    const filtered = ps.filter(p => !q || p.name.toLowerCase().includes(q.toLowerCase()));
    document.getElementById('pk-list').innerHTML = filtered.map(p => `
      <div data-name="${p.name}" style="
        padding:7px 10px;border-radius:6px;cursor:pointer;
        display:flex;align-items:center;gap:10px;
        transition:background 0.1s;" 
        onmouseover="this.style.background='#0d1829'"
        onmouseout="this.style.background='transparent'">
        <span style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;
          background:#0d2050;color:#3a80ff;flex-shrink:0">${posGroup(p.pos)[0]||'?'}</span>
        <div>
          <div style="font-size:12px;color:#c0d8f0;font-weight:500">${p.name}</div>
          <div style="font-size:10px;color:#4a6080">${p.squad} · ${activeSeason}</div>
        </div>
        <span style="margin-left:auto;font-size:12px;color:#3a5070;font-weight:600">${p.gls||0}g ${p.ast||0}a</span>
      </div>`).join('');
  };

  renderList('');

  document.getElementById('pk-search').addEventListener('input', e => renderList(e.target.value));

  document.getElementById('pk-list').addEventListener('click', e => {
    const el = e.target.closest('[data-name]');
    if (!el) return;
    const p = currentPlayers().find(x=>x.name===el.dataset.name);
    if (p && !compareList.find(x=>x.name===p.name)) {
      if (compareList.length >= 3) compareList.shift();
      compareList.push(p);
    }
    document.body.removeChild(overlay);
    renderCompare();
  });

  document.getElementById('pk-close').addEventListener('click', () => document.body.removeChild(overlay));
  overlay.addEventListener('click', e => { if (e.target===overlay) document.body.removeChild(overlay); });
}

// ── Start ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadData);
