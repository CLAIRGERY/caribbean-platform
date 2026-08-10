/**
 * SaKgaZé — Prévision des échouages de sargasses Caraïbes
 * Esri Satellite basemap, neon-lime sargassum, drift vectors
 */
const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000/api/v1'
  : 'https://sakgaze-api.onrender.com/api/v1';
const CENTER = [-61.5, 15.5];
const ZOOM = 7;

/* ==========================================================================
   Carte — Esri World Imagery satellite raster (self-contained inline style)
   ========================================================================== */
const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      'esri-satellite': {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        attribution: 'Esri, Maxar, Earthstar Geographics',
      },
    },
    layers: [{
      id: 'satellite-basemap',
      type: 'raster',
      source: 'esri-satellite',
      minzoom: 0,
      maxzoom: 19,
    }],
  },
  center: CENTER,
  zoom: ZOOM,
  attributionControl: false,
});
window.__saKgaZeMap = map;

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-right');
map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

/* ==========================================================================
   État
   ========================================================================== */
let sargassumData = null;
let driftData    = null;
let weatherData  = null;
let timelineDay  = 0;
let isPlaying    = false;
let playInterval = null;

// Click-only popup (mutual exclusion)
let activePopup = null;
function openPopup(lngLat, html) {
  if (activePopup) activePopup.remove();
  activePopup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, maxWidth: '280px' })
    .setLngLat(lngLat).setHTML(html).addTo(map);
  activePopup.on('close', () => { activePopup = null; });
}

/* ==========================================================================
   Helpers
   ========================================================================== */
function s(val) { return (val != null && val !== '') ? val : '—'; }
function n(val, dec) { return val != null ? Number(val).toFixed(dec||1) : '—'; }

/* ==========================================================================
   API
   ========================================================================== */
async function fetchGeoJSON(path) {
  const resp = await fetch(`${API_BASE_URL}${path}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  return data?.features ? data : { type:'FeatureCollection', features:[] };
}

async function chargerDonnees() {
  const [sak, drift, wx] = await Promise.allSettled([
    fetchGeoJSON('/sakgaze/detections/latest'),
    fetchGeoJSON('/sakgaze/drift-predictions/latest'),
    fetchGeoJSON('/weathernext/marine-alerts/latest'),
  ]);
  sargassumData = sak.status    === 'fulfilled' ? sak.value    : { type:'FeatureCollection', features:[] };
  driftData     = drift.status  === 'fulfilled' ? drift.value  : { type:'FeatureCollection', features:[] };
  weatherData   = wx.status     === 'fulfilled' ? wx.value     : { type:'FeatureCollection', features:[] };
}

/* ==========================================================================
   Timeline
   ========================================================================== */
function mettreAJourSources() {
  if (map.getSource('sargassum')) map.getSource('sargassum').setData(sargassumData);
  if (map.getSource('drift'))     map.getSource('drift').setData(driftData);
  if (map.getSource('weather'))   map.getSource('weather').setData(weatherData);
}

/* ==========================================================================
   Layer stacking: sargassum → drift → weather
   ========================================================================== */

/* ---- Sargassum: glowing terracotta fill under land ---- */
function ajouterCoucheSargasses() {
  if (!map.getSource('sargassum')) {
    map.addSource('sargassum', { type:'geojson', data: sargassumData });
  }
  if (!map.getLayer('sargassum-fill')) {
    map.addLayer({
      id:'sargassum-fill', type:'fill', source:'sargassum',
      paint:{
        'fill-color':          '#AB47BC',
        'fill-opacity':        0.10,
        'fill-outline-color':  '#E040FB',
      },
    });
    map.addLayer({
      id:'sargassum-outline', type:'line', source:'sargassum',
      paint:{ 'line-color':'#E040FB', 'line-width':1, 'line-opacity':0.5 },
    });
    map.on('click', 'sargassum-fill', e => {
      const p = e.features[0].properties;
      openPopup(e.lngLat, popupHTML('🌿 Détection Sargasses', [
        ['Surface', `${n(p.surface_km2)} km²`],
        ['Densité', `${n(p.density_score,2)} (${s(p.density_level)})`],
        ['Date d\'acquisition', s(p.acquisition_date)],
      ]));
    });
    map.on('mouseenter', 'sargassum-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'sargassum-fill', () => { map.getCanvas().style.cursor = ''; });
  }
}

/* ---- Drift: vibrant dashed lines + arrowheads, under land ---- */
function ajouterCoucheDerive() {
  if (!map.getSource('drift')) {
    map.addSource('drift', { type:'geojson', data: driftData });
  }
  // Impact cones
  if (!map.getLayer('drift-cones')) {
    map.addLayer({
      id:'drift-cones', type:'fill', source:'drift',
      filter:['==',['geometry-type'],'Polygon'],
      paint:{
        'fill-color':          '#FF6D00',
        'fill-opacity':        0.08,
        'fill-outline-color':  '#FF3D00',
      },
    });
  }
  // Trajectory lines — above sargassum, still under land
  if (!map.getLayer('drift-lines')) {
    map.addLayer({
      id:'drift-lines', type:'line', source:'drift',
      filter:['==',['geometry-type'],'LineString'],
      paint:{
        'line-color':     '#FF6D00',
        'line-width':     2.5,
        'line-dasharray': [2, 4],
        'line-opacity':   0.90,
      },
      layout:{ 'line-cap':'round' },
    });
    // Arrowheads
    map.addLayer({
      id:'drift-arrows', type:'symbol', source:'drift',
      filter:['==',['geometry-type'],'LineString'],
      layout:{
        'symbol-placement': 'line',
        'symbol-spacing':   80,
        'icon-image':       'arrow',
        'icon-size':        0.5,
        'icon-rotate':      90,
        'icon-rotation-alignment': 'map',
      },
      paint:{ 'icon-color':'#FF6D00' },
    });
  }
  map.on('click', 'drift-lines', e => {
    const p = e.features[0].properties;
    openPopup(e.lngLat, popupHTML('🌀 Trajectoire de Dérive', [
      ['Horizon', `${s(p.prediction_horizon_days)} jour(s)`],
      ['ETA d\'échouement', `${s(p.eta_hours)} h`],
      ['Secteur cible', s(p.target_sector)],
      ['Probabilité', `${n(p.landing_probability_pct)} %`],
    ]));
  });
  map.on('mouseenter', 'drift-lines', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'drift-lines', () => { map.getCanvas().style.cursor = ''; });
}

/* ---- Weather source + coastal alert shoreline strokes ---- */
function ajouterCoucheAlertes() {
  if (!map.getSource('weather')) {
    map.addSource('weather', { type:'geojson', data: weatherData });
  }
  // Coastal alert glow effect: stacked line layers along sector boundaries
  if (!map.getLayer('coastal-glow')) {
    // Outer glow layer
    map.addLayer({
      id:'coastal-glow', type:'line', source:'weather',
      filter:['all', ['==',['geometry-type'],'Polygon'], ['has','alert_level']],
      paint:{
        'line-color': ['match',['get','alert_level'],
                       'Green','#00E676','Yellow','#FFEA00','Orange','#FF9100',
                       'Red','#FF3D00','Purple','#9B59B6','#4A8296'],
        'line-width': 8,
        'line-blur': 4,
        'line-opacity': 0.6,
      },
    });
    // Inner core line
    map.addLayer({
      id:'coastal-core', type:'line', source:'weather',
      filter:['all', ['==',['geometry-type'],'Polygon'], ['has','alert_level']],
      paint:{
        'line-color': ['match',['get','alert_level'],
                       'Green','#00E676','Yellow','#FFEA00','Orange','#FF9100',
                       'Red','#FF3D00','Purple','#9B59B6','#4A8296'],
        'line-width': 3,
        'line-opacity': 1.0,
      },
    });
    map.on('click', 'coastal-core', e => afficherInspecteur(e.features[0].properties));
    map.on('mouseenter', 'coastal-core', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'coastal-core', () => { map.getCanvas().style.cursor = ''; });
  }
  // Cyclone tracks
  if (!map.getLayer('cyclone-tracks')) {
    map.addLayer({
      id:'cyclone-tracks', type:'line', source:'weather',
      filter:['all',['==',['geometry-type'],'LineString'],['==',['get','alert_type'],'cyclone_track']],
      paint:{ 'line-color':'#FF9100', 'line-width':2, 'line-opacity':0.9 },
    });
  }
  // Cyclone uncertainty cones
  if (!map.getLayer('cyclone-cones')) {
    map.addLayer({
      id:'cyclone-cones', type:'fill', source:'weather',
      filter:['all',['==',['geometry-type'],'Polygon'],['==',['get','alert_type'],'cyclone_cone']],
      paint:{ 'fill-color':'#FF3D00', 'fill-opacity':0.05, 'fill-outline-color':'#FF6D00' },
    });
  }
}

/* ==========================================================================
   Popup HTML builder
   ========================================================================== */
function popupHTML(title, rows) {
  let h = `<div class="popup-title">${title}</div>`;
  for (const [label, value] of rows) {
    h += `<div class="popup-row"><span class="popup-label">${label}</span><span class="popup-value">${value}</span></div>`;
  }
  return h;
}

/* ==========================================================================
   Inspecteur Côtier (panel-integrated)
   ========================================================================== */
function afficherInspecteur(props) {
  const empty = document.getElementById('panel-inspector-empty');
  const content = document.getElementById('panel-inspector-content');
  empty.classList.add('hidden');
  content.classList.remove('hidden');

  document.getElementById('panel-inspector-sector').textContent = s(props.sector || props.target_sector);

  const badge = document.getElementById('panel-inspector-badge');
  const lvl = s(props.alert_level);
  badge.textContent = `Niveau : ${lvl}`;
  badge.className = 'text-xs font-bold uppercase tracking-wide px-2 py-1 rounded-md inline-block';
  if (lvl === 'Purple')      { badge.style.background='rgba(155,89,182,0.25)'; badge.style.color='#CE93D8'; }
  else if (lvl === 'Red')    { badge.style.background='rgba(244,67,54,0.25)'; badge.style.color='#EF9A9A'; }
  else if (lvl === 'Orange') { badge.style.background='rgba(255,152,0,0.25)'; badge.style.color='#FFB74D'; }
  else if (lvl === 'Yellow') { badge.style.background='rgba(255,235,59,0.25)'; badge.style.color='#FFF176'; }
  else                       { badge.style.background='rgba(76,175,80,0.25)'; badge.style.color='#A5D6A7'; }

  document.getElementById('pi-surface').textContent = props.surface_km2 != null ? `${n(props.surface_km2)} km²` : '—';
  document.getElementById('pi-density').textContent = n(props.density_score, 2);
  document.getElementById('pi-wind').textContent    = props.wind_speed_knots != null ? `${n(props.wind_speed_knots,0)} kt` : '—';
  document.getElementById('pi-wave').textContent    = props.wave_height_m != null ? `${n(props.wave_height_m)} m` : '—';

  const secteur = props.sector || props.target_sector;
  let bestEta = null;
  driftData?.features?.forEach(f => {
    const p = f.properties || {};
    if (p.target_sector === secteur && p.eta_hours != null) {
      if (bestEta === null || p.eta_hours < bestEta) bestEta = p.eta_hours;
    }
  });
  document.getElementById('pi-eta').textContent = bestEta != null ? `${n(bestEta,0)} h` : '—';

  const h2sEl = document.getElementById('pi-h2s');
  const h2sRisk = (props.h2s_risk || '').toLowerCase();
  if (h2sRisk.includes('alerte')) {
    h2sEl.textContent = 'Alerte'; h2sEl.style.color = '#EF9A9A';
  } else if (h2sRisk.includes('attention')) {
    h2sEl.textContent = 'Modéré'; h2sEl.style.color = '#FFB74D';
  } else {
    h2sEl.textContent = 'Faible'; h2sEl.style.color = '#A5D6A7';
  }
}

/* ==========================================================================
   Panel Toggle
   ========================================================================== */
const panel = document.getElementById('sidebar-panel');
const toggleIcon = document.getElementById('panel-toggle-icon');
document.getElementById('panel-toggle').addEventListener('click', () => {
  const closed = panel.classList.toggle('panel-closed');
  toggleIcon.textContent = closed ? '▶' : '◀';
  panel.classList.toggle('panel-open', !closed);
});

/* ==========================================================================
   Timeline Slider
   ========================================================================== */
const slider = document.getElementById('timeline-slider');
const label  = document.getElementById('timeline-label');
slider.addEventListener('input', () => {
  timelineDay = parseInt(slider.value);
  if (timelineDay === 0) label.textContent = 'Maintenant';
  else if (timelineDay < 0) label.textContent = `T − ${Math.abs(timelineDay)} j`;
  else label.textContent = `T + ${timelineDay} j`;
  mettreAJourSources();
});
document.getElementById('timeline-play').addEventListener('click', () => {
  isPlaying ? arreterLecture() : demarrerLecture();
});
function demarrerLecture() {
  isPlaying = true;
  document.getElementById('timeline-play-icon').classList.add('hidden');
  document.getElementById('timeline-pause-icon').classList.remove('hidden');
  playInterval = setInterval(() => {
    let v = timelineDay + 1; if (v > 7) v = -7;
    slider.value = v; timelineDay = v;
    label.textContent = v === 0 ? 'Maintenant' : (v < 0 ? `T ${v} j` : `T +${v} j`);
    mettreAJourSources();
  }, 1800);
}
function arreterLecture() {
  isPlaying = false;
  document.getElementById('timeline-play-icon').classList.remove('hidden');
  document.getElementById('timeline-pause-icon').classList.add('hidden');
  if (playInterval) { clearInterval(playInterval); playInterval = null; }
}

/* ==========================================================================
   Layer pills
   ========================================================================== */
const GROUPES_COUCHES = {
  sargassum: ['sargassum-fill','sargassum-outline'],
  drift:     ['drift-cones','drift-lines','drift-arrows'],
  weather:   ['coastal-glow','coastal-core','cyclone-tracks','cyclone-cones'],
};
document.querySelectorAll('.layer-pill').forEach(btn => {
  btn.addEventListener('click', () => {
    const key = btn.dataset.layer;
    const on = btn.classList.contains('active');
    (GROUPES_COUCHES[key]||[]).forEach(id => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'none' : 'visible');
    });
    btn.classList.toggle('active', !on);
  });
});

/* ==========================================================================
   Boot
   ========================================================================== */
map.on('load', async () => {
  // Arrowhead image for drift lines
  if (!map.hasImage('arrow')) {
    const img = new Image();
    img.onload = () => map.addImage('arrow', img);
    img.src = 'data:image/svg+xml,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">' +
      '<polygon points="8,0 16,16 8,12" fill="white"/>' +
      '</svg>'
    );
  }
  try {
    await chargerDonnees();
    ajouterCoucheSargasses();
    ajouterCoucheDerive();
    ajouterCoucheAlertes();
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.add('opacity-0');
    setTimeout(() => overlay.remove(), 500);
  } catch (err) {
    console.error('Erreur de chargement:', err);
    document.getElementById('loading-overlay').innerHTML = `
      <div class="text-center text-[#E65100]">
        <p class="font-bold text-lg">Erreur de chargement</p>
        <p class="text-sm mt-1">${err.message}</p>
      </div>`;
  }
});
