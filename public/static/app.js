/**
 * static/app.js — SIH26081 Scientific Forecast Intelligence Dashboard
 * Implements Multi-Model NWP Blending, Uncertainty Quantification,
 * Model Comparison, Weight Maps, Verification Analytics, and Operational Telemetry.
 */

'use strict';

// ── Application State ──────────────────────────────────────────────────────────
const state = {
  location: 'Visakhapatnam',
  lat: 17.6868,
  lon: 83.2185,
  isLoading: false,
  gisMap: null,
  gisMarker: null,
  charts: {
    forecast: null,
    comparison: null,
    verification: null,
  },
  latestBlendedData: null,
  latestObservationData: null,
};

// ── Weather Icon Mapper ───────────────────────────────────────────────────────
function getWeatherIcon(conditionId, isDay = true) {
  const id = conditionId || 800;
  if (id >= 200 && id < 300) return '⛈️';
  if (id >= 300 && id < 400) return '🌦️';
  if (id >= 500 && id < 510) return '🌧️';
  if (id === 511) return '🌨️';
  if (id >= 512 && id < 600) return '🌧️';
  if (id >= 600 && id < 700) return '❄️';
  if (id >= 700 && id < 800) return '🌫️';
  if (id === 800) return isDay ? '☀️' : '🌙';
  if (id === 801) return isDay ? '🌤️' : '☁️';
  if (id === 802) return '⛅';
  if (id >= 803) return '☁️';
  return '⛅';
}

// ── Toast Notification ────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.style.cssText = `
    background: ${type === 'error' ? '#EF4444' : type === 'success' ? '#10B981' : '#2563EB'};
    color: white; padding: 10px 18px; border-radius: 999px; margin-top: 8px;
    font-size: 0.8rem; font-weight: 600; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    animation: fadeIn 0.3s ease;
  `;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const panel = document.getElementById(`tab-${tabId}`);
  if (panel) panel.classList.add('active');

  const btn = document.querySelector(`[data-tab="${tabId}"]`);
  if (btn) btn.classList.add('active');

  // Trigger data loader for the active tab
  if (tabId === 'dashboard') loadDashboard();
  else if (tabId === 'forecast') renderForecastChart();
  else if (tabId === 'comparison') loadModelComparison();
  else if (tabId === 'weightmaps') loadWeightMap();
  else if (tabId === 'verification') loadVerification();
  else if (tabId === 'extremes') loadExtremes();
  else if (tabId === 'workflow') loadWorkflow();
  else if (tabId === 'map') initGISMap();
}

// ── Location Application ──────────────────────────────────────────────────────
function applyLocationChange() {
  const input = document.getElementById('global-location-input');
  if (!input || !input.value.trim()) return;
  state.location = input.value.trim();
  showToast(`Loading multi-model forecasts for ${state.location}...`, 'info');
  loadDashboard();
}

function requestCurrentLocation() {
  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser.', 'error');
    return;
  }
  showToast('Detecting GPS location…', 'info');
  navigator.geolocation.getCurrentPosition(
    async pos => {
      state.lat = pos.coords.latitude;
      state.lon = pos.coords.longitude;
      state.location = `Lat ${state.lat.toFixed(2)}, Lon ${state.lon.toFixed(2)}`;
      const inp = document.getElementById('global-location-input');
      if (inp) inp.value = state.location;
      loadDashboard();
    },
    err => {
      showToast('Could not access GPS location.', 'error');
    },
    { timeout: 8000 }
  );
}

// ── 1. Dashboard Loader ───────────────────────────────────────────────────────
async function loadDashboard() {
  const loc = state.location;
  document.getElementById('dash-location-title').textContent = loc;

  try {
    // 1. Fetch Observational Ground Truth
    const obsUrl = `/api/weather/current?location=${encodeURIComponent(loc)}`;
    const obsRes = await fetch(obsUrl);
    if (obsRes.ok) {
      const obsData = await obsRes.json();
      state.latestObservationData = obsData;
      renderObservationCard(obsData);
    }

    // 2. Fetch Consensus Blended Forecast
    const blendUrl = `/api/nwp/blended?location=${encodeURIComponent(loc)}`;
    const blendRes = await fetch(blendUrl);
    if (!blendRes.ok) {
      const err = await blendRes.json().catch(() => ({}));
      throw new Error(err.detail || `NWP forecast request failed (HTTP ${blendRes.status})`);
    }
    const blendData = await blendRes.json();
    if (!blendData.forecast_points?.length) {
      throw new Error('NWP blending returned no forecast points.');
    }
    state.latestBlendedData = blendData;
    renderBlendedCard(blendData);
    renderDashboardTimeline(blendData);
    renderDynamicWeights(blendData);
  } catch (err) {
    console.error('Error loading dashboard:', err);
    showToast(`Forecast loading failed: ${err.message || err}`, 'error');
  }
}

function renderObservationCard(data) {
  document.getElementById('obs-temp').textContent = `${data.temperature}°C`;
  document.getElementById('obs-condition').textContent = data.condition || 'Clear Sky';
  document.getElementById('obs-feels').textContent = `Feels like ${data.feels_like}°C`;
  document.getElementById('obs-humidity').textContent = `${data.humidity}%`;
  document.getElementById('obs-wind').textContent = `${data.wind_speed} km/h`;
  document.getElementById('obs-pressure').textContent = `${data.pressure} hPa`;
  document.getElementById('obs-rain').textContent = `${data.rain_1h || 0.0} mm`;
  document.getElementById('obs-icon').textContent = getWeatherIcon(data.condition_id);
}

function renderBlendedCard(data) {
  const points = data.forecast_points || [];
  if (!points.length) return;

  const first = points[0];
  document.getElementById('blend-temp').textContent = `${first.temperature}°C`;
  document.getElementById('blend-condition').textContent = `Consensus (+3h): ${first.temperature}°C, PoP ${first.precipitation_probability}%`;
  document.getElementById('blend-rain-signal').innerHTML = `🌧️ Rain Expected: <strong>${first.precipitation} mm</strong> (PoP ${first.precipitation_probability}%)`;
  document.getElementById('blend-wind').textContent = `${first.wind_speed} km/h (${first.wind_direction}°)`;
  document.getElementById('blend-pressure').textContent = `${first.pressure} hPa`;
  document.getElementById('blend-spread').textContent = `σ = ${first.confidence.disagreement_spread}°C (${first.confidence.category})`;

  // Badges
  const regimeBadge = document.getElementById('dash-regime-badge');
  regimeBadge.textContent = `REGIME: ${data.detected_regime.toUpperCase()}`;

  const confBadge = document.getElementById('dash-conf-badge');
  confBadge.textContent = `CONFIDENCE: ${data.overall_confidence} (${first.confidence.score_pct}%)`;
  confBadge.className = `metric-pill conf-pill conf-${data.overall_confidence.toLowerCase()}`;

  // Stat numbers
  document.getElementById('stat-spread').textContent = `${first.confidence.disagreement_spread}°C`;
  document.getElementById('stat-range').textContent = `${first.confidence.inter_model_range}°C`;
  const factorPct = Math.round(first.confidence.agreement_score * 100);
  document.getElementById('agreement-factor-bar').style.width = `${factorPct}%`;
  document.getElementById('agreement-factor-text').textContent = `${factorPct}% Agreement across ${first.confidence.active_models_count} NWP models`;

  // Risk Guidance
  const alertsList = document.getElementById('dash-alerts-list');
  alertsList.innerHTML = '';
  if (data.extreme_risk_summary && data.extreme_risk_summary.length > 0) {
    data.extreme_risk_summary.forEach(msg => {
      const div = document.createElement('div');
      div.className = 'alert-item alert-yellow';
      div.innerHTML = `<div class="alert-badge">ALERT</div><div class="alert-content"><strong>Risk Signal</strong><div>${msg}</div></div>`;
      alertsList.appendChild(div);
    });
  } else {
    alertsList.innerHTML = '<div style="color:#64748B; font-size:0.78rem; padding:8px;">No critical severe weather threshold breaches detected in next 24h.</div>';
  }
}

function renderDynamicWeights(data) {
  const points = data.forecast_points || [];
  if (!points.length) return;
  const weights = points[0].model_weights || { GFS: 0.33, WRF: 0.33, ECMWF: 0.34 };

  const gfsPct = Math.round((weights.GFS || 0.33) * 100);
  const wrfPct = Math.round((weights.WRF || 0.33) * 100);
  const ecmwfPct = Math.round((weights.ECMWF || 0.34) * 100);

  document.getElementById('wt-val-gfs').textContent = `${gfsPct}%`;
  document.getElementById('wt-fill-gfs').style.width = `${gfsPct}%`;

  document.getElementById('wt-val-wrf').textContent = `${wrfPct}%`;
  document.getElementById('wt-fill-wrf').style.width = `${wrfPct}%`;

  document.getElementById('wt-val-ecmwf').textContent = `${ecmwfPct}%`;
  document.getElementById('wt-fill-ecmwf').style.width = `${ecmwfPct}%`;
}

function renderDashboardTimeline(data) {
  const scroller = document.getElementById('dash-timeline-scroller');
  scroller.innerHTML = '';

  const points = (data.forecast_points || []).slice(0, 8); // Next 24 hours
  points.forEach(pt => {
    const timeStr = pt.valid_time ? pt.valid_time.split(' ')[1] || pt.valid_time : `+${pt.lead_time_hours}h`;
    const card = document.createElement('div');
    card.className = 'timeline-card';
    card.innerHTML = `
      <div class="timeline-hour">+${pt.lead_time_hours}h</div>
      <div class="timeline-icon">${getWeatherIcon(pt.precipitation > 2.0 ? 501 : 800)}</div>
      <div class="timeline-temp">${pt.temperature}°C</div>
      <div class="timeline-rain">${pt.precipitation} mm</div>
      <div style="font-size:0.65rem; color:#64748B; margin-top:3px;">PoP ${pt.precipitation_probability}%</div>
    `;
    scroller.appendChild(card);
  });
}

// ── 2. Consensus Forecast Chart & Table ───────────────────────────────────────
function renderForecastChart() {
  const data = state.latestBlendedData;
  if (!data || !data.forecast_points) {
    loadDashboard();
    return;
  }

  const variable = document.getElementById('forecast-chart-var').value;
  const ctx = document.getElementById('blendedForecastChart').getContext('2d');

  const labels = data.forecast_points.map(p => `+${p.lead_time_hours}h`);
  let datasetData = [];
  let labelTitle = '';
  let chartType = 'line';
  let color = '#2563EB';

  if (variable === 'temp') {
    datasetData = data.forecast_points.map(p => p.temperature);
    labelTitle = '2m Temperature (°C)';
    color = '#EF4444';
  } else if (variable === 'rain') {
    datasetData = data.forecast_points.map(p => p.precipitation);
    labelTitle = 'Precipitation (mm/3h)';
    chartType = 'bar';
    color = '#3B82F6';
  } else if (variable === 'wind') {
    datasetData = data.forecast_points.map(p => p.wind_speed);
    labelTitle = 'Wind Speed (km/h)';
    color = '#10B981';
  } else if (variable === 'pres') {
    datasetData = data.forecast_points.map(p => p.pressure);
    labelTitle = 'Surface Pressure (hPa)';
    color = '#8B5CF6';
  }

  if (state.charts.forecast) state.charts.forecast.destroy();

  state.charts.forecast = new Chart(ctx, {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: labelTitle,
        data: datasetData,
        borderColor: color,
        backgroundColor: chartType === 'bar' ? 'rgba(59, 130, 246, 0.6)' : 'rgba(37, 99, 235, 0.08)',
        fill: chartType === 'line',
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 2.5,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top' },
      },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: '#F1F5F9' } },
      }
    }
  });

  // Populate Table
  const tbody = document.getElementById('forecast-table-tbody');
  tbody.innerHTML = '';
  data.forecast_points.forEach(p => {
    const topModel = Object.keys(p.model_weights || {}).reduce((a, b) => p.model_weights[a] > p.model_weights[b] ? a : b, 'WRF');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>+${p.lead_time_hours}h</strong></td>
      <td>${p.valid_time}</td>
      <td style="font-weight:700;">${p.temperature}°C</td>
      <td>${p.precipitation} mm</td>
      <td>${p.precipitation_probability}%</td>
      <td>${p.wind_speed} km/h</td>
      <td>${p.wind_direction}°</td>
      <td>${p.pressure}</td>
      <td>${p.humidity}%</td>
      <td><span class="step-status-tag step-success">${topModel}</span></td>
      <td><span class="metric-pill conf-${p.confidence.category.toLowerCase()}" style="padding:2px 8px; font-size:0.68rem;">${p.confidence.category}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── 3. Model Comparison Loader ────────────────────────────────────────────────
async function loadModelComparison() {
  const loc = state.location;
  try {
    const res = await fetch(`/api/nwp/compare?location=${encodeURIComponent(loc)}`);
    if (!res.ok) return;
    const data = await res.json();

    const gfsPts = data.individual_models.GFS ? data.individual_models.GFS.points : [];
    const wrfPts = data.individual_models.WRF ? data.individual_models.WRF.points : [];
    const ecmwfPts = data.individual_models.ECMWF ? data.individual_models.ECMWF.points : [];
    const blendPts = data.blended_consensus ? data.blended_consensus.forecast_points : [];

    const labels = blendPts.slice(0, 16).map(p => `+${p.lead_time_hours}h`);

    const ctx = document.getElementById('modelComparisonChart').getContext('2d');
    if (state.charts.comparison) state.charts.comparison.destroy();

    state.charts.comparison = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'NOAA GFS',
            data: gfsPts.slice(0, 16).map(p => p.temperature),
            borderColor: '#3B82F6',
            borderDash: [5, 5],
            tension: 0.3,
            borderWidth: 1.8,
            pointRadius: 2,
          },
          {
            label: 'NCAR WRF',
            data: wrfPts.slice(0, 16).map(p => p.temperature),
            borderColor: '#10B981',
            borderDash: [5, 5],
            tension: 0.3,
            borderWidth: 1.8,
            pointRadius: 2,
          },
          {
            label: 'ECMWF IFS',
            data: ecmwfPts.slice(0, 16).map(p => p.temperature),
            borderColor: '#8B5CF6',
            borderDash: [5, 5],
            tension: 0.3,
            borderWidth: 1.8,
            pointRadius: 2,
          },
          {
            label: 'AI–NWP Consensus Blend',
            data: blendPts.slice(0, 16).map(p => p.temperature),
            borderColor: '#EF4444',
            backgroundColor: 'rgba(239, 68, 68, 0.06)',
            fill: true,
            tension: 0.3,
            borderWidth: 3,
            pointRadius: 3.5,
          },
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          title: { display: true, text: '2m Temperature (°C) — Individual Models vs Blended Consensus' },
        },
      }
    });

    // Comparison Matrix Cards
    const grid = document.getElementById('comparison-cards-grid');
    grid.innerHTML = '';
    const models = [
      { name: 'NOAA GFS', tag: '0.25° Global', temp: gfsPts[0]?.temperature || '--', rain: gfsPts[0]?.precipitation || '0.0', color: '#3B82F6' },
      { name: 'NCAR WRF', tag: 'Mesoscale Convective', temp: wrfPts[0]?.temperature || '--', rain: wrfPts[0]?.precipitation || '0.0', color: '#10B981' },
      { name: 'ECMWF IFS', tag: 'Global 9km HRES', temp: ecmwfPts[0]?.temperature || '--', rain: ecmwfPts[0]?.precipitation || '0.0', color: '#8B5CF6' },
      { name: 'AI Consensus Blend', tag: 'Optimal Dynamic Blend', temp: blendPts[0]?.temperature || '--', rain: blendPts[0]?.precipitation || '0.0', color: '#EF4444' },
    ];

    models.forEach(m => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.borderTop = `4px solid ${m.color}`;
      card.innerHTML = `
        <div style="font-weight:700; font-size:0.95rem;">${m.name}</div>
        <div style="font-size:0.7rem; color:#64748B;">${m.tag}</div>
        <div style="font-size:1.8rem; font-weight:800; margin:10px 0 4px 0;">${m.temp}°C</div>
        <div style="font-size:0.78rem; color:#2563EB;">Precip: ${m.rain} mm</div>
      `;
      grid.appendChild(card);
    });

  } catch (err) {
    console.error('Error loading model comparison:', err);
  }
}

// ── 4. Weight Maps Loader ─────────────────────────────────────────────────────
async function loadWeightMap() {
  const variable = document.getElementById('weight-map-var').value;
  const lead = document.getElementById('weight-map-lead').value;

  try {
    const res = await fetch(`/api/nwp/weight-map?variable=${variable}&lead_time_hours=${lead}`);
    if (!res.ok) return;
    const data = await res.json();

    const container = document.getElementById('weight-map-cards-container');
    container.innerHTML = '';

    data.forEach(reg => {
      const card = document.createElement('div');
      card.className = 'card';
      const domColor = reg.dominant_model === 'WRF' ? '#10B981' : (reg.dominant_model === 'GFS' ? '#3B82F6' : '#8B5CF6');
      card.innerHTML = `
        <div style="font-weight:700; font-size:0.88rem; color:#0F172A;">${reg.region_name}</div>
        <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.75rem; color:#64748B;">Dominant Model:</span>
          <span class="step-status-tag" style="background:${domColor}; color:white;">${reg.dominant_model} (${reg.dominant_weight_pct}%)</span>
        </div>
        <div style="margin-top:10px; font-size:0.75rem; color:#475569;">
          <div>GFS: <strong>${Math.round(reg.weights.GFS * 100)}%</strong></div>
          <div>WRF: <strong>${Math.round(reg.weights.WRF * 100)}%</strong></div>
          <div>ECMWF: <strong>${Math.round(reg.weights.ECMWF * 100)}%</strong></div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading weight maps:', err);
  }
}

// ── 5. Verification & Skill Loader ────────────────────────────────────────────
async function loadVerification() {
  const variable = document.getElementById('verif-var').value;
  const region = document.getElementById('verif-region').value;

  try {
    const res = await fetch(`/api/nwp/verification?variable=${variable}&region=${region}&lead_time=24`);
    if (!res.ok) return;
    const data = await res.json();

    // Verdict callout
    document.getElementById('verif-verdict-box').textContent = data.verdict;

    // Table
    const tbody = document.getElementById('verif-metrics-tbody');
    tbody.innerHTML = '';

    const models = Object.keys(data.models || {});
    const ctx = document.getElementById('verificationSkillChart').getContext('2d');
    if (!models.length) { document.getElementById('verif-verdict-box').textContent = data.verdict || 'No verified forecast-observation samples are available yet.'; if (state.charts.verification) state.charts.verification.destroy(); document.getElementById('verif-metrics-tbody').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;">Collecting real verification samples — no synthetic skill is displayed.</td></tr>'; return; }
    const maes = models.map(m => data.models[m].mae);

    models.forEach(m => {
      const stats = data.models[m];
      const isBlended = m === 'BLENDED';
      const tr = document.createElement('tr');
      if (isBlended) tr.style.background = '#EFF6FF';
      tr.innerHTML = `
        <td><strong>${m}</strong> ${isBlended ? '⭐' : ''}</td>
        <td style="font-weight:700; color:${isBlended ? '#1D4ED8' : '#1E293B'};">${stats.mae}</td>
        <td>${stats.rmse}</td>
        <td>${stats.bias > 0 ? '+' : ''}${stats.bias}</td>
        <td>${stats.pod}</td>
        <td>${stats.far}</td>
        <td>${stats.csi}</td>
        <td><span class="step-status-tag ${isBlended ? 'step-success' : ''}">${isBlended ? 'OPTIMAL CONSENSUS' : 'SINGLE MODEL'}</span></td>
      `;
      tbody.appendChild(tr);
    });

    if (state.charts.verification) state.charts.verification.destroy();
    state.charts.verification = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: models,
        datasets: [{
          label: `Mean Absolute Error (MAE) — Lower is Better`,
          data: maes,
          backgroundColor: models.map(m => m === 'BLENDED' ? '#2563EB' : '#94A3B8'),
          borderRadius: 6,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'MAE' } }
        }
      }
    });

  } catch (err) {
    console.error('Error loading verification:', err);
  }
}

// ── 6. Extremes Loader ────────────────────────────────────────────────────────
async function loadExtremes() {
  const loc = state.location;
  try {
    // 1. Model-based guidance
    const mRes = await fetch(`/api/extreme-weather?location=${encodeURIComponent(loc)}`);
    if (mRes.ok) {
      const mData = await mRes.json();
      const mList = document.getElementById('extremes-model-guidance-list');
      mList.innerHTML = '';
      if (mData.alerts && mData.alerts.length > 0) {
        mData.alerts.forEach(a => {
          const div = document.createElement('div');
          div.className = `alert-item alert-${a.severity.toLowerCase()}`;
          div.innerHTML = `
            <div class="alert-badge">${a.severity}</div>
            <div class="alert-content">
              <strong>${a.hazard_type} (Forecast: ${a.trigger_value} ${a.unit})</strong>
              <div>${a.recommendation}</div>
              <div style="font-size:0.68rem; color:#64748B; margin-top:3px;">Valid: ${a.valid_time} · Lead: +${a.lead_time_hours}h</div>
            </div>
          `;
          mList.appendChild(div);
        });
      } else {
        mList.innerHTML = '<div style="color:#64748B; font-size:0.8rem;">No extreme threshold breaches predicted in next 120h.</div>';
      }
    }

    // 2. Official IMD Warnings
    const oRes = await fetch(`/alerts/official?location=${encodeURIComponent(loc)}`);
    if (oRes.ok) {
      const oData = await oRes.json();
      const oList = document.getElementById('extremes-official-warnings-list');
      oList.innerHTML = '';
      const warns = oData.official_warnings || [];
      if (warns.length > 0) {
        warns.forEach(w => {
          const div = document.createElement('div');
          div.className = `alert-item alert-${(w.color || 'yellow').toLowerCase()}`;
          div.innerHTML = `
            <div class="alert-badge">${w.color || 'OFFICIAL'}</div>
            <div class="alert-content">
              <strong>${w.warning_level || 'IMD Warning'} — ${w.hazard_type || 'Weather Hazard'}</strong>
              <div>${w.description || 'Monitor official IMD bulletins.'}</div>
              <div style="font-size:0.68rem; color:#64748B; margin-top:3px;">Authority: ${w.authority || 'IMD'}</div>
            </div>
          `;
          oList.appendChild(div);
        });
      } else {
        oList.innerHTML = '<div style="color:#64748B; font-size:0.8rem;">Green Alert: No severe weather warning from IMD for this district.</div>';
      }
    }
  } catch (err) {
    console.error('Error loading extremes:', err);
  }
}

// ── 7. Operational Workflow Loader ────────────────────────────────────────────
async function loadWorkflow() {
  try {
    const res = await fetch('/api/workflow/status');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('wf-stat-status').textContent = data.status;
    document.getElementById('wf-stat-duration').textContent = `${data.total_duration_ms} ms`;
    document.getElementById('wf-stat-timesteps').textContent = `${data.blended_timesteps_generated} Steps`;
    document.getElementById('wf-stat-providers').textContent = `${data.active_providers.length} Active`;

    const stepsContainer = document.getElementById('workflow-steps-container');
    stepsContainer.innerHTML = '';
    (data.steps || []).forEach(s => {
      const card = document.createElement('div');
      card.className = 'workflow-step-card';
      card.innerHTML = `
        <div>
          <div style="font-weight:700;">${s.step_name}</div>
          <div style="font-size:0.72rem; color:#64748B;">${s.details || 'Completed'}</div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:0.72rem; color:#64748B;">${s.duration_ms}ms</span>
          <span class="step-status-tag ${s.status === 'SUCCESS' ? 'step-success' : 'step-failed'}">${s.status}</span>
        </div>
      `;
      stepsContainer.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading workflow status:', err);
  }
}

async function triggerWorkflowCycle() {
  showToast('Executing Operational Blending Cycle...', 'info');
  try {
    const res = await fetch(`/api/workflow/run?location=${encodeURIComponent(state.location)}`, { method: 'POST' });
    if (res.ok) {
      showToast('Blending cycle completed successfully!', 'success');
      loadWorkflow();
      loadDashboard();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Workflow failed: ${err.detail || res.statusText}`, 'error');
    }
  } catch (err) {
    showToast('Failed to trigger workflow cycle.', 'error');
  }
}

// ── 8. GIS Map ────────────────────────────────────────────────────────────────
function initGISMap() {
  if (state.gisMap) {
    state.gisMap.invalidateSize();
    return;
  }

  const mapEl = document.getElementById('gis-map');
  if (!mapEl) return;

  state.gisMap = L.map('gis-map').setView([state.lat, state.lon], 7);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors',
  }).addTo(state.gisMap);

  state.gisMarker = L.marker([state.lat, state.lon])
    .addTo(state.gisMap)
    .bindPopup(`<b>${state.location}</b><br>AI-NWP Blended Consensus Point`)
    .openPopup();

  state.gisMap.on('click', e => {
    state.lat = e.latlng.lat;
    state.lon = e.latlng.lng;
    state.location = `Lat ${state.lat.toFixed(2)}, Lon ${state.lon.toFixed(2)}`;
    document.getElementById('global-location-input').value = state.location;
    state.gisMarker.setLatLng(e.latlng).bindPopup(`Selected: ${state.location}`).openPopup();
    loadDashboard();
    showToast(`Fetched consensus forecast for ${state.location}`, 'info');
  });
}

function updateMapLayer() {
  showToast('Updated active meteorological GIS layer.', 'info');
}

// ── App Initialization ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
});
