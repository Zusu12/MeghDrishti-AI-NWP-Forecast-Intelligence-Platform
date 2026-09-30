/**
 * app.js — WeatherGPT Frontend
 * All API calls go through FastAPI backend — no keys in frontend.
 * Voice output via ElevenLabs (backend /voice endpoint) with browser fallback.
 * Voice input via browser SpeechRecognition.
 * Interactive Leaflet map with click-to-weather & GPS location.
 */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────────
const state = {
  language: 'en',
  location: 'Visakhapatnam',
  lat: null,
  lon: null,
  sessionId: crypto.randomUUID(),
  isLoading: false,
  map: null,
  mapMarker: null,
  forecastChart: null,
  rainChart: null,
  climateTempChart: null,
  climateRainChart: null,
  climateHumChart: null,
  recognition: null,
  isListening: false,
  currentAudio: null,
  wsAlerts: null,
  demoMode: false,
};

// ── Language labels & translations ─────────────────────────────────────────────
const LANG_LABELS = {
  en: { placeholder: 'Ask WeatherGPT… (e.g. Will it rain tomorrow?)', welcome: 'Ask anything about weather!' },
  hi: { placeholder: 'WeatherGPT से पूछें… (उदा. क्या कल बारिश होगी?)', welcome: 'मौसम के बारे में कुछ भी पूछें!' },
  te: { placeholder: 'WeatherGPT ని అడగండి… (ఉదా. రేపు వర్షం పడుతుందా?)', welcome: 'వాతావరణం గురించి ఏదైనా అడగండి!' },
};

const QUICK_QUESTIONS = {
  en: [
    { icon: '☔', text: 'Will it rain tomorrow?' },
    { icon: '🌡️', text: 'What is the temperature today?' },
    { icon: '🚨', text: 'Is there any severe weather risk?' },
    { icon: '🌾', text: 'Is it suitable for farming tomorrow?' },
    { icon: '✈️', text: 'Give me an aviation weather briefing' },
    { icon: '🌊', text: 'Is it safe for marine activities?' },
    { icon: '📊', text: 'Show the climate trend' },
    { icon: '📍', text: 'Weather near me' },
  ],
  hi: [
    { icon: '☔', text: 'क्या कल बारिश होगी?' },
    { icon: '🌡️', text: 'आज का तापमान क्या है?' },
    { icon: '🚨', text: 'कोई मौसम चेतावनी है?' },
    { icon: '🌾', text: 'क्या कल खेती के लिए अच्छा है?' },
    { icon: '✈️', text: 'विमानन मौसम जानकारी दें' },
    { icon: '🌊', text: 'समुद्री यात्रा के लिए मौसम?' },
    { icon: '📍', text: 'मेरे पास का मौसम' },
  ],
  te: [
    { icon: '☔', text: 'రేపు వర్షం పడుతుందా?' },
    { icon: '🌡️', text: 'నేడు ఉష్ణోగ్రత ఎంత?' },
    { icon: '🚨', text: 'తీవ్రమైన వాతావరణ హెచ్చరికలు ఉన్నాయా?' },
    { icon: '🌾', text: 'రేపు వ్యవసాయానికి అనుకూలంగా ఉంటుందా?' },
    { icon: '✈️', text: 'విమానయాన వాతావరణ సారాంశం ఇవ్వండి' },
    { icon: '🌊', text: 'సముద్ర యాత్రకు వాతావరణం అనుకూలంగా ఉందా?' },
    { icon: '📍', text: 'నా సమీపంలో వాతావరణం' },
  ],
};

// ── Weather icon mapper ────────────────────────────────────────────────────────
function weatherIcon(conditionId, icon) {
  const id = conditionId || 800;
  if (id >= 200 && id < 300) return '⛈️';
  if (id >= 300 && id < 400) return '🌦️';
  if (id >= 500 && id < 510) return '🌧️';
  if (id === 511) return '🌨️';
  if (id >= 512 && id < 600) return '🌧️';
  if (id >= 600 && id < 700) return '❄️';
  if (id >= 700 && id < 800) return '🌫️';
  if (id === 800) return '☀️';
  if (id === 801) return '🌤️';
  if (id === 802) return '⛅';
  if (id >= 803) return '☁️';
  return '🌤️';
}

// ── Tab switching ──────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const panel = document.getElementById(`tab-${tabId}`);
  if (panel) panel.classList.add('active');

  const btn = document.querySelector(`[data-tab="${tabId}"]`);
  if (btn) btn.classList.add('active');

  // Lazy-load tab data
  if (tabId === 'forecast') loadForecast();
  if (tabId === 'alerts') loadAlerts();
  if (tabId === 'map') {
    initMap();
    setTimeout(() => { if (state.map) state.map.invalidateSize(); }, 250);
  }
  if (tabId === 'climate') loadClimate();
}

// ── Language switching ─────────────────────────────────────────────────────────
document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const lang = btn.dataset.lang;
    state.language = lang;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const input = document.getElementById('chat-input');
    const labels = LANG_LABELS[lang];
    if (input) input.placeholder = labels.placeholder;

    updateQuickActions(lang);
    showToast(`Language: ${btn.textContent.trim()}`, 'info');
  });
});

function updateQuickActions(lang) {
  const container = document.getElementById('quick-actions');
  if (!container) return;
  const questions = QUICK_QUESTIONS[lang] || QUICK_QUESTIONS['en'];
  container.innerHTML = questions.map(q =>
    `<button class="quick-btn" onclick="sendQuick('${q.text.replace(/'/g, "\\'")}')">${q.icon} ${q.text}</button>`
  ).join('');
}

// ── Geolocation ("Weather Near Me") ────────────────────────────────────────────
async function requestCurrentLocation() {
  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser.', 'error');
    return;
  }
  showToast('Detecting location via GPS…', 'info');
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords;
      try {
        const res = await fetch(`/weather/current?lat=${latitude}&lon=${longitude}`);
        if (!res.ok) throw new Error('Could not fetch location weather');
        const w = await res.json();
        state.location = w.location;
        state.lat = latitude;
        state.lon = longitude;
        updateHeroWeather(w);
        updateNavLocation(w.location);
        if (state.map) {
          addMapMarker(latitude, longitude, w.location, `${w.temperature}°C`, w.condition);
        }
        showToast(`📍 Located: ${w.location}`, 'success');
      } catch (err) {
        showToast('Failed to retrieve weather for your coordinates.', 'error');
      }
    },
    (err) => {
      showToast('Location access denied or unavailable.', 'warning');
    },
    { timeout: 10000 }
  );
}

// ── Chat ───────────────────────────────────────────────────────────────────────
function sendQuick(text) {
  const input = document.getElementById('chat-input');
  if (input) {
    input.value = text;
    switchTab('chat');
  }
  if (text.includes('near me') || text.includes('पास') || text.includes('సమీపంలో')) {
    if (!state.lat && navigator.geolocation) {
      requestCurrentLocation();
    }
  }
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const message = input ? input.value.trim() : '';
  if (!message || state.isLoading) return;

  input.value = '';
  autoResize(input);
  appendMessage('user', message);
  showTyping();
  state.isLoading = true;
  setSendLoading(true);

  try {
    const payload = {
      message,
      language: state.language,
      session_id: state.sessionId,
      location: state.location,
    };
    if (state.lat && state.lon) {
      payload.lat = state.lat;
      payload.lon = state.lon;
    }

    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    removeTyping();

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Request failed' }));
      appendMessage('assistant', `⚠️ ${err.detail || 'Could not get a response. Please try again.'}`, null, true);
      return;
    }

    const data = await res.json();

    // Update hero weather
    if (data.weather) {
      updateHeroWeather(data.weather);
      state.location = data.location || state.location;
      updateNavLocation(state.location);
    }

    // Show alert in hero
    if (data.alerts && data.alerts.alert) {
      showHeroAlert(data.alerts);
    }

    // Render response
    appendMessage('assistant', data.response, data);

    // Update demo mode
    if (data.demo_mode) {
      const banner = document.getElementById('demo-banner');
      if (banner) banner.style.display = 'block';
    }

    // Log latency
    const lat = data.latency || {};
    console.log(`⏱️ Total: ${lat.total_ms}ms | Weather: ${lat.weather_ms}ms | Gemini: ${lat.gemini_response_ms}ms`);

  } catch (e) {
    removeTyping();
    appendMessage('assistant', '⚠️ Network error. Please check your connection and try again.', null, true);
    console.error('Chat error:', e);
  } finally {
    state.isLoading = false;
    setSendLoading(false);
  }
}

function formatMarkdown(str) {
  if (!str) return '';
  let safe = str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // Bold
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic
  safe = safe.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Line breaks
  safe = safe.replace(/\n/g, '<br>');
  return safe;
}

function appendMessage(role, text, data = null, isError = false) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = formatMarkdown(text);
  if (isError) bubble.style.background = '#FEF2F2';
  div.appendChild(bubble);

  if (role === 'assistant' && !isError) {
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    meta.innerHTML = `<span>WeatherGPT · ${state.language.toUpperCase()}</span>`;

    // Listen button
    const listenBtn = document.createElement('button');
    listenBtn.className = 'listen-btn';
    listenBtn.innerHTML = '🔊 Listen';
    listenBtn.addEventListener('click', () => playTTS(text, listenBtn));
    meta.appendChild(listenBtn);

    div.appendChild(meta);
  }

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showTyping() {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.id = 'typing-indicator';
  div.className = 'message assistant';
  div.innerHTML = `<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing-indicator');
  if (t) t.remove();
}

function setSendLoading(loading) {
  const btn = document.getElementById('send-btn');
  if (!btn) return;
  btn.innerHTML = loading
    ? '<div class="spinner" style="width:16px;height:16px;border-width:2px;"></div>'
    : '<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13" /><path d="M22 2L15 22l-4-9-9-4 20-7z" /></svg>';
}

function handleInputKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── Hero weather update ────────────────────────────────────────────────────────
function updateHeroWeather(w) {
  setText('hero-temp', `${w.temperature}°`);
  setText('hero-condition', w.condition);
  setText('hero-location', `${w.location}, ${w.country || 'IN'}`);
  setText('hero-feels', `Feels like ${w.feels_like}°C`);
  setText('hero-humidity', `${w.humidity}%`);
  setText('hero-wind', `${w.wind_speed} km/h`);
  setText('hero-vis', `${(w.visibility / 1000).toFixed(1)} km`);
  setText('hero-cloud', `${w.cloud_cover}%`);
  setText('hero-icon', weatherIcon(w.condition_id, w.icon));
}

function showHeroAlert(alerts) {
  const el = document.getElementById('hero-alert');
  const textEl = document.getElementById('hero-alert-text');
  if (el && textEl && alerts.alerts && alerts.alerts.length > 0) {
    textEl.textContent = alerts.alerts[0].message;
    el.classList.remove('hidden');
    el.style.display = 'inline-flex';
    const colors = { HIGH: '#EF4444', WARNING: '#F59E0B', WATCH: '#3B82F6', INFO: '#22C55E' };
    el.style.background = (colors[alerts.severity] || '#EF4444') + '33';
    el.style.borderColor = (colors[alerts.severity] || '#EF4444') + '66';
  }
}

function updateNavLocation(loc) {
  setText('nav-location', loc);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ── Voice Output — ElevenLabs & Browser Fallback ───────────────────────────────
async function playTTS(text, btn) {
  // If already playing, stop and reset
  if (state.currentAudio) {
    state.currentAudio.pause();
    state.currentAudio = null;
    if (btn) {
      btn.classList.remove('playing');
      btn.innerHTML = '🔊 Listen';
    }
    return;
  }

  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    if (btn) {
      btn.classList.remove('playing');
      btn.innerHTML = '🔊 Listen';
    }
    return;
  }

  if (btn) {
    btn.classList.add('playing');
    btn.textContent = '⏸ Stop';
  }

  try {
    const cleanText = text.replace(/<[^>]*>/g, '').replace(/\*/g, '');
    const res = await fetch('/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: cleanText, language: state.language }),
    });

    if (!res.ok) {
      // Gracefully fall back to browser SpeechSynthesis
      fallbackTTS(cleanText, btn);
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    state.currentAudio = audio;

    audio.onended = () => {
      if (btn) { btn.classList.remove('playing'); btn.innerHTML = '🔊 Listen'; }
      URL.revokeObjectURL(url);
      state.currentAudio = null;
    };

    audio.onerror = () => {
      fallbackTTS(cleanText, btn);
    };

    await audio.play();

  } catch (e) {
    console.warn('ElevenLabs error, using browser speech synthesis fallback:', e);
    const cleanText = text.replace(/<[^>]*>/g, '').replace(/\*/g, '');
    fallbackTTS(cleanText, btn);
  }
}

function fallbackTTS(text, btn = null) {
  if (!window.speechSynthesis) {
    if (btn) { btn.classList.remove('playing'); btn.innerHTML = '🔊 Listen'; }
    showToast('Voice synthesis is not supported in this browser.', 'warning');
    return;
  }
  window.speechSynthesis.cancel();

  // Clean and expand abbreviations for smooth speech
  let clean = text
    .replace(/<[^>]*>/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/#{1,6}\s*/g, '')
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '')
    .trim();

  if (state.language === 'te') {
    clean = clean
      .replace(/(\d+(?:\.\d+)?)\s*°\s*C/g, '$1 డిగ్రీల సెల్సియస్')
      .replace(/(\d+(?:\.\d+)?)\s*°/g, '$1 డిగ్రీలు')
      .replace(/(\d+(?:\.\d+)?)\s*km\/h/g, '$1 కిలోమీటర్లు ప్రతి గంటకు')
      .replace(/(\d+(?:\.\d+)?)\s*%/g, '$1 శాతం');
  } else if (state.language === 'hi') {
    clean = clean
      .replace(/(\d+(?:\.\d+)?)\s*°\s*C/g, '$1 डिग्री सेल्सियस')
      .replace(/(\d+(?:\.\d+)?)\s*°/g, '$1 डिग्री')
      .replace(/(\d+(?:\.\d+)?)\s*km\/h/g, '$1 किलोमीटर प्रति घंटा')
      .replace(/(\d+(?:\.\d+)?)\s*%/g, '$1 प्रतिशत');
  } else {
    clean = clean
      .replace(/(\d+(?:\.\d+)?)\s*°\s*C/g, '$1 degrees Celsius')
      .replace(/(\d+(?:\.\d+)?)\s*km\/h/g, '$1 kilometers per hour')
      .replace(/(\d+(?:\.\d+)?)\s*%/g, '$1 percent');
  }

  const utt = new SpeechSynthesisUtterance(clean);
  const langCodes = { en: 'en-IN', hi: 'hi-IN', te: 'te-IN' };
  utt.lang = langCodes[state.language] || 'en-IN';
  utt.rate = 0.92;
  utt.pitch = 1.0;

  // Try to find matching voice
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find(v => v.lang.startsWith(state.language) || v.lang.includes(langCodes[state.language]));
  if (match) utt.voice = match;

  utt.onend = () => {
    if (btn) { btn.classList.remove('playing'); btn.innerHTML = '🔊 Listen'; }
  };
  utt.onerror = () => {
    if (btn) { btn.classList.remove('playing'); btn.innerHTML = '🔊 Listen'; }
  };

  window.speechSynthesis.speak(utt);
}

// ── Voice Input — SpeechRecognition ───────────────────────────────────────────
function toggleVoice() {
  if (state.isListening) {
    stopListening();
  } else {
    startListening();
  }
}

function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast('Voice recognition not supported in this browser. Please use Chrome.', 'error');
    return;
  }

  const langCodes = { en: 'en-IN', hi: 'hi-IN', te: 'te-IN' };
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = langCodes[state.language] || 'en-IN';
  state.recognition = recognition;

  recognition.onstart = () => {
    state.isListening = true;
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) micBtn.classList.add('listening');
    const voiceStatus = document.getElementById('voice-status');
    if (voiceStatus) voiceStatus.classList.remove('hidden');
  };

  recognition.onresult = (e) => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
    const input = document.getElementById('chat-input');
    if (input) { input.value = transcript; autoResize(input); }
  };

  recognition.onend = () => {
    state.isListening = false;
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) micBtn.classList.remove('listening');
    const voiceStatus = document.getElementById('voice-status');
    if (voiceStatus) voiceStatus.classList.add('hidden');
    state.recognition = null;
    const input = document.getElementById('chat-input');
    if (input && input.value.trim()) sendChat();
  };

  recognition.onerror = (e) => {
    state.isListening = false;
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) micBtn.classList.remove('listening');
    const voiceStatus = document.getElementById('voice-status');
    if (voiceStatus) voiceStatus.classList.add('hidden');
    showToast(`Voice error: ${e.error}`, 'error');
  };

  recognition.start();
}

function stopListening() {
  if (state.recognition) {
    state.recognition.stop();
  }
}

// ── Forecast Tab ──────────────────────────────────────────────────────────────
async function loadForecast() {
  const location = document.getElementById('fc-location')?.value.trim() || state.location;
  state.location = location;
  updateNavLocation(location);

  try {
    const res = await fetch(`/weather/forecast?location=${encodeURIComponent(location)}`);
    if (!res.ok) { showToast('Could not load forecast', 'error'); return; }
    const forecast = await res.json();
    renderForecastScroll(forecast);
    renderForecastCharts(forecast);
  } catch (e) {
    showToast('Network error loading forecast', 'error');
  }
}

function renderForecastScroll(forecast) {
  const container = document.getElementById('forecast-scroll');
  if (!container) return;
  container.innerHTML = forecast.slice(0, 10).map(slot => {
    const d = new Date(slot.dt * 1000);
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    const day = d.toLocaleDateString([], { weekday: 'short' });
    return `
      <div class="forecast-card">
        <div class="time">${day}<br>${time}</div>
        <div class="icon">${weatherIcon(slot.condition_id, slot.icon)}</div>
        <div class="temp">${slot.temperature}°C</div>
        <div class="pop">💧 ${Math.round((slot.pop || 0) * 100)}%</div>
        <div class="cond">${slot.condition}</div>
      </div>`;
  }).join('');
}

function renderForecastCharts(forecast) {
  const labels = forecast.slice(0, 14).map(s => {
    const d = new Date(s.dt * 1000);
    return d.toLocaleDateString([], { weekday: 'short' }) + ' ' +
           d.toLocaleTimeString([], { hour: '2-digit', hour12: true });
  });
  const temps = forecast.slice(0, 14).map(s => s.temperature);
  const pops = forecast.slice(0, 14).map(s => Math.round((s.pop || 0) * 100));

  destroyChart('forecastChart');
  destroyChart('rainChart');

  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { font: { size: 10 }, maxRotation: 45 }, grid: { display: false } },
      y: { ticks: { font: { size: 10 } }, grid: { color: '#F1F5F9' } },
    },
  };

  const fcEl = document.getElementById('forecast-chart');
  if (fcEl) {
    state.forecastChart = new Chart(fcEl, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: temps,
          borderColor: '#2563EB',
          backgroundColor: 'rgba(37,99,235,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#2563EB',
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, title: { display: true, text: '°C', font: { size: 10 } } } } },
    });
  }

  const rcEl = document.getElementById('rain-chart');
  if (rcEl) {
    state.rainChart = new Chart(rcEl, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: pops,
          backgroundColor: pops.map(p => p >= 70 ? 'rgba(37,99,235,0.8)' : p >= 40 ? 'rgba(14,165,233,0.6)' : 'rgba(148,163,184,0.4)'),
          borderRadius: 4,
        }],
      },
      options: chartDefaults,
    });
  }
}

// ── Alerts Tab ─────────────────────────────────────────────────────────────────
async function loadAlerts() {
  const location = document.getElementById('alert-location')?.value.trim() || state.location;
  const container = document.getElementById('alert-results');
  if (!container) return;
  container.innerHTML = `<div class="empty-state"><div class="spinner" style="border-color:rgba(37,99,235,0.3);border-top-color:#2563EB;"></div><div class="empty-text">Checking weather risks…</div></div>`;

  try {
    const res = await fetch(`/alerts?location=${encodeURIComponent(location)}`);
    if (!res.ok) { container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-text">Could not load alerts</div></div>`; return; }
    const data = await res.json();
    renderAlerts(container, data, location);
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">🔌</div><div class="empty-text">Network error</div></div>`;
  }
}

function renderAlerts(container, data, location) {
  const severityColors = { HIGH: '#EF4444', WARNING: '#F59E0B', WATCH: '#3B82F6', INFO: '#22C55E' };
  const color = severityColors[data.severity] || '#22C55E';

  let html = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <div>
        <div style="font-weight:700;font-size:1rem;">${location}</div>
        <div style="font-size:0.72rem;color:#64748B;">Multi-Hazard Threat Evaluation & Official CAP Feed</div>
      </div>
      <div style="background:${color};color:white;border-radius:999px;padding:4px 14px;font-size:0.72rem;font-weight:700;">${data.severity}</div>
    </div>`;

  // Official IMD 4-Color Warning & NDMA CAP Bulletin Card
  if (data.imd_warning) {
    const imd = data.imd_warning;
    html += `
      <div style="background:${imd.bg_hex};border:2px solid ${imd.color_hex};border-radius:12px;padding:14px 16px;margin-bottom:14px;box-shadow:0 2px 6px rgba(0,0,0,0.04);">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:1.2rem;">🏛️</span>
            <div>
              <span style="font-size:0.75rem;font-weight:800;color:${imd.color_hex};letter-spacing:0.04em;">OFFICIAL IMD / NDMA CAP WARNING</span>
              <div style="font-size:0.68rem;color:#475569;">${imd.sender} · ${imd.area}</div>
            </div>
          </div>
          <div style="background:${imd.color_hex};color:white;font-weight:800;font-size:0.75rem;padding:4px 12px;border-radius:20px;letter-spacing:0.03em;">
            ${imd.color_code} ALERT (${imd.action.toUpperCase()})
          </div>
        </div>
        <div style="font-size:0.88rem;font-weight:700;color:#1E293B;margin-bottom:6px;line-height:1.4;">
          ${imd.headline}
        </div>
        <div style="font-size:0.78rem;color:#334155;line-height:1.5;margin-bottom:8px;">
          ${imd.instruction}
        </div>
        <div style="font-size:0.68rem;color:#64748B;display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;border-top:1px solid rgba(0,0,0,0.06);padding-top:6px;">
          <span>CAP ID: <code>${imd.bulletin_id || '--'}</code></span>
          <span>Emergency Helpline: <strong>112</strong> · NDMA: <strong>1078</strong></span>
        </div>
      </div>`;
  }

  if (!data.alert && (!data.alerts || data.alerts.length === 0) && (!data.imd_warning || data.imd_warning.color_code === 'GREEN')) {
    html += `
      <div class="alert-card INFO">
        <div style="font-size:1.4rem;">✅</div>
        <div>
          <div style="font-weight:600;font-size:0.88rem;">No significant weather risks detected</div>
          <div style="font-size:0.78rem;color:#64748B;margin-top:4px;">Meteorological variables appear within safe parameters.</div>
        </div>
      </div>`;
  } else {
    data.alerts.forEach(alert => {
      html += `
        <div class="alert-card ${alert.severity}">
          <div style="font-size:1.4rem;">${alert.icon}</div>
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
              <span style="font-weight:600;font-size:0.88rem;">${alert.type.replace(/_/g,' ').toUpperCase()}</span>
              <span class="alert-badge ${alert.severity}">${alert.severity}</span>
            </div>
            <div style="font-size:0.8rem;color:#475569;line-height:1.5;">${alert.message}</div>
          </div>
        </div>`;
    });
  }

  if (data.demo) {
    html += `<div style="text-align:center;font-size:0.68rem;color:#94A3B8;margin-top:8px;">⚠️ Demo data</div>`;
  }

  container.innerHTML = html;
}

// ── Climate Tab ────────────────────────────────────────────────────────────────
async function loadClimate() {
  const location = document.getElementById('climate-location')?.value.trim() || state.location;
  const days = parseInt(document.getElementById('climate-days')?.value || '30');

  // Trigger NWP model run in parallel
  loadNWP();

  try {
    const res = await fetch(`/climate?location=${encodeURIComponent(location)}&days=${days}`);
    if (!res.ok) { showToast('Could not load climate data', 'error'); return; }
    const data = await res.json();
    renderClimateCharts(data);
  } catch (e) {
    showToast('Network error loading climate data', 'error');
  }
}

function renderClimateCharts(data) {
  const { dates, temperature, rainfall, humidity, stats } = data;

  // Stats
  const statsEl = document.getElementById('climate-stats');
  if (statsEl) {
    statsEl.style.display = 'grid';
    setText('cs-temp', `${stats.avg_temp}°C`);
    setText('cs-rain', `${stats.total_rainfall} mm`);
    setText('cs-hum', `${stats.avg_humidity}%`);
  }

  // Compact labels (every 5th)
  const labels = dates.map((d, i) => i % 5 === 0 ? new Date(d).toLocaleDateString([], { month:'short', day:'numeric' }) : '');

  destroyChart('climateTempChart');
  destroyChart('climateRainChart');
  destroyChart('climateHumChart');

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { font: { size: 9 }, maxRotation: 0 }, grid: { display: false } },
      y: { ticks: { font: { size: 9 } }, grid: { color: '#F1F5F9' } },
    },
  };

  const ctc = document.getElementById('climate-temp-chart');
  if (ctc) {
    state.climateTempChart = new Chart(ctc, {
      type: 'line',
      data: { labels, datasets: [{ data: temperature, borderColor: '#2563EB', backgroundColor: 'rgba(37,99,235,0.07)', fill: true, tension: 0.4, pointRadius: 1 }] },
      options: baseOpts,
    });
  }

  const crc = document.getElementById('climate-rain-chart');
  if (crc) {
    state.climateRainChart = new Chart(crc, {
      type: 'bar',
      data: { labels, datasets: [{ data: rainfall, backgroundColor: 'rgba(14,165,233,0.6)', borderRadius: 2 }] },
      options: baseOpts,
    });
  }

  const chc = document.getElementById('climate-hum-chart');
  if (chc) {
    state.climateHumChart = new Chart(chc, {
      type: 'line',
      data: { labels, datasets: [{ data: humidity, borderColor: '#06B6D4', backgroundColor: 'rgba(6,182,212,0.07)', fill: true, tension: 0.4, pointRadius: 1 }] },
      options: baseOpts,
    });
  }
}

// ── NWP Model Integration ──────────────────────────────────────────────────────
async function loadNWP() {
  const location = document.getElementById('climate-location')?.value.trim() || state.location;
  const provider = document.getElementById('nwp-provider-select')?.value || 'owm';
  const tbody = document.getElementById('nwp-tbody');
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:#2563EB;">
      <div class="spinner" style="border-color:rgba(37,99,235,0.3);border-top-color:#2563EB;width:18px;height:18px;display:inline-block;vertical-align:middle;margin-right:8px;"></div>
      Running numerical model assimilation via OpenWeatherMap…
    </td></tr>`;
  }

  try {
    let url = `/nwp?location=${encodeURIComponent(location)}&provider=${encodeURIComponent(provider)}`;
    if (state.lat && state.lon && !document.getElementById('climate-location')?.value) {
      url = `/nwp?lat=${state.lat}&lon=${state.lon}&provider=${encodeURIComponent(provider)}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:#EF4444;">Failed to fetch NWP data.</td></tr>`;
      return;
    }
    const data = await res.json();
    renderNWP(data);
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:#EF4444;">Network error fetching NWP model run.</td></tr>`;
  }
}

function renderNWP(data) {
  setText('nwp-meta-model', data.model_name || data.provider);
  setText('nwp-meta-res', data.grid_resolution || '0.25° (~25 km)');
  setText('nwp-meta-horizon', data.forecast_horizon || '120 Hours (5 Days)');
  setText('nwp-meta-steps', `${data.timesteps_count || (data.data && data.data.length) || 0} steps (3h)`);

  const liveBadge = document.getElementById('nwp-live-badge');
  if (liveBadge) {
    if (data.demo) {
      liveBadge.textContent = '◐ Demo Model Mode';
      liveBadge.style.background = '#FEF3C7';
      liveBadge.style.color = '#B45309';
    } else {
      liveBadge.textContent = '● Operational OWM';
      liveBadge.style.background = '#DCFCE7';
      liveBadge.style.color = '#15803D';
    }
  }

  const resBadge = document.getElementById('nwp-res-badge');
  if (resBadge && data.grid_resolution) {
    resBadge.textContent = data.grid_resolution;
  }

  const tbody = document.getElementById('nwp-tbody');
  if (!tbody || !data.data) return;

  const rows = data.data.slice(0, 24); // Show up to 72 hours (24 timesteps)
  tbody.innerHTML = rows.map((s, idx) => {
    const validStr = s.valid_time ? s.valid_time.replace('T', ' ').slice(5, 16) : `+${s.step_hours}h`;
    const windStr = `${s.wind_speed_10m} km/h ${s.wind_direction_cardinal || ''}`;
    const precipVal = s.total_precipitation || 0;
    const precipStr = precipVal > 0 ? `${precipVal} mm (${s.precipitation_probability}%)` : `0 mm (${s.precipitation_probability}%)`;
    const bg = idx % 2 === 0 ? '#FFFFFF' : '#F8FAFC';
    return `<tr style="background:${bg};border-bottom:1px solid #F1F5F9;">
      <td style="padding:6px 10px;font-weight:600;color:#2563EB;">+${s.step_hours !== undefined ? s.step_hours : idx * 3}h</td>
      <td style="padding:6px 10px;color:#334155;">${validStr}</td>
      <td style="padding:6px 10px;font-weight:700;color:#0F172A;">${s.temperature_2m}°C</td>
      <td style="padding:6px 10px;color:#64748B;">${s.dew_point_2m !== undefined ? s.dew_point_2m + '°C' : '--'}</td>
      <td style="padding:6px 10px;color:#0284C7;font-weight:600;">${s.relative_humidity_2m}%</td>
      <td style="padding:6px 10px;color:#475569;">${s.surface_pressure} hPa</td>
      <td style="padding:6px 10px;color:#334155;">${windStr}</td>
      <td style="padding:6px 10px;color:${precipVal > 0 ? '#2563EB' : '#94A3B8'};font-weight:${precipVal > 0 ? '700' : '400'};">${precipStr}</td>
      <td style="padding:6px 10px;color:#64748B;">${s.cloud_cover}%</td>
      <td style="padding:6px 10px;color:#1E293B;">${weatherIcon(s.condition_id, s.icon)} ${s.condition || '--'}</td>
    </tr>`;
  }).join('');
}

// ── Map Tab ────────────────────────────────────────────────────────────────────
function initMap() {
  if (state.map) {
    state.map.invalidateSize();
    return;
  }

  state.map = L.map('map').setView([17.6868, 83.2185], 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(state.map);

  addMapMarker(17.6868, 83.2185, 'Visakhapatnam', '--°C', 'Loading…');
  loadMapWeather();
  loadIngestionStatus();

  // Map click interaction: fetch weather at clicked point
  state.map.on('click', async (e) => {
    const { lat, lng } = e.latlng;
    try {
      showToast('Fetching weather for selected coordinates…', 'info');
      const res = await fetch(`/weather/current?lat=${lat}&lon=${lng}`);
      if (res.ok) {
        const w = await res.json();
        state.location = w.location;
        state.lat = lat;
        state.lon = lng;
        updateHeroWeather(w);
        updateNavLocation(w.location);
        addMapMarker(lat, lng, w.location, `${w.temperature}°C`, w.condition);
        const infoEl = document.getElementById('map-info');
        if (infoEl) infoEl.classList.remove('hidden');
        setText('map-city', w.location);
        setText('map-coords', `${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E`);
        setText('map-temp', `${w.temperature}°C`);
        setText('map-cond', w.condition);
        showToast(`Selected: ${w.location} (${w.temperature}°C)`, 'success');
      }
    } catch (err) {
      console.error(err);
    }
  });
}

function addMapMarker(lat, lon, name, temp, cond) {
  if (state.mapMarker && state.map) state.map.removeLayer(state.mapMarker);

  const icon = L.divIcon({
    html: `<div style="background:#2563EB;color:white;border-radius:50% 50% 50% 0;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;transform:rotate(-45deg);box-shadow:0 3px 10px rgba(37,99,235,0.4);">
      <span style="transform:rotate(45deg);text-align:center;">${temp}</span>
    </div>`,
    className: '',
    iconSize: [40, 40],
    iconAnchor: [20, 40],
  });

  if (state.map) {
    state.mapMarker = L.marker([lat, lon], { icon })
      .addTo(state.map)
      .bindPopup(`<strong>${name}</strong><br>${temp}<br>${cond}`, { maxWidth: 200 })
      .openPopup();

    state.map.flyTo([lat, lon], 10, { duration: 1.2 });
  }
}

async function loadMapWeather() {
  const location = document.getElementById('map-location')?.value.trim() || state.location;

  try {
    let url = `/weather/current?location=${encodeURIComponent(location)}`;
    if (state.lat && state.lon && !document.getElementById('map-location')?.value) {
      url = `/weather/current?lat=${state.lat}&lon=${state.lon}`;
    }
    const res = await fetch(url);
    if (!res.ok) return;
    const w = await res.json();

    addMapMarker(w.lat, w.lon, w.location, `${w.temperature}°C`, w.condition);

    const infoEl = document.getElementById('map-info');
    if (infoEl) { infoEl.classList.remove('hidden'); }
    setText('map-city', w.location);
    setText('map-coords', `${w.lat.toFixed(4)}°N, ${w.lon.toFixed(4)}°E`);
    setText('map-temp', `${w.temperature}°C`);
    setText('map-cond', w.condition);

  } catch (e) {
    console.error('Map weather error:', e);
  }
}

function updateMap() {
  loadMapWeather();
}

async function loadIngestionStatus() {
  try {
    const res = await fetch('/health');
    if (!res.ok) return;
    const data = await res.json();
    const sources = data.ingestion || [];
    const statusEl = document.getElementById('ingestion-status');
    if (statusEl) {
      statusEl.innerHTML = sources.map(s => {
        const colors = { active: '#22C55E', integration_ready: '#F59E0B' };
        const labels = { active: '● Active', integration_ready: '◐ Integration-ready' };
        const proto = s.protocol ? `<span style="font-size:0.68rem;color:#94A3B8;margin-left:4px;">(${s.protocol})</span>` : '';
        return `<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 0;border-bottom:1px solid #F1F5F9;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="color:${colors[s.status]||'#94A3B8'};font-weight:700;font-size:0.75rem;">${labels[s.status]||s.status}</span>
            <span style="font-size:0.78rem;font-weight:600;color:#1E293B;">${s.name}</span>
          </div>
          ${proto}
        </div>`;
      }).join('');
    }
  } catch {}
}

// ── Advisory Tab ───────────────────────────────────────────────────────────────
async function getAdvisory(mode) {
  const location = document.getElementById('adv-location')?.value.trim() || state.location;
  const resultEl = document.getElementById('advisory-result');
  if (!resultEl) return;

  resultEl.classList.remove('hidden');
  resultEl.innerHTML = `<div class="empty-state"><div class="spinner" style="border-color:rgba(37,99,235,0.3);border-top-color:#2563EB;width:28px;height:28px;"></div><div class="empty-text">Generating ${mode} advisory…</div></div>`;

  try {
    const res = await fetch('/advisory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ location, mode, language: state.language }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed' }));
      resultEl.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-text">${err.detail}</div></div>`;
      return;
    }

    const data = await res.json();
    const modeIcons = { agriculture: '🌾', aviation: '✈️', marine: '🌊', travel: '🚗', outdoor: '🏕️', urban: '🏙️' };

    resultEl.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <span style="font-size:1.8rem;">${modeIcons[mode] || '📋'}</span>
        <div>
          <div style="font-weight:700;font-size:0.95rem;">${data.title}</div>
          <div style="font-size:0.75rem;color:#64748B;">${data.location}</div>
        </div>
      </div>
      <div class="grid-2" style="margin-bottom:12px;">
        <div class="stat-chip"><div class="stat-label">Temperature</div><div class="stat-value">${data.weather?.temperature}°C</div></div>
        <div class="stat-chip"><div class="stat-label">Condition</div><div class="stat-value" style="font-size:0.85rem;">${data.weather?.condition}</div></div>
        <div class="stat-chip"><div class="stat-label">Humidity</div><div class="stat-value">${data.weather?.humidity}%</div></div>
        <div class="stat-chip"><div class="stat-label">Wind</div><div class="stat-value">${data.weather?.wind_speed} km/h</div></div>
      </div>
      <div style="background:#F8FAFC;border-radius:10px;padding:12px;font-size:0.84rem;line-height:1.65;color:#334155;margin-bottom:10px;">
        ${formatMarkdown(data.advisory)}
      </div>
      <div style="font-size:0.7rem;color:#94A3B8;line-height:1.5;">⚠️ ${data.disclaimer}</div>
      ${data.demo ? '<div style="font-size:0.65rem;color:#F59E0B;margin-top:6px;text-align:center;">⚠️ Demo data</div>' : ''}
    `;

  } catch (e) {
    resultEl.innerHTML = `<div class="empty-state"><div class="empty-icon">🔌</div><div class="empty-text">Network error</div></div>`;
  }
}

// ── Toast Notifications ────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { info: 'ℹ️', error: '⚠️', warning: '⚡', success: '✅' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = '0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ── WebSocket Alerts ───────────────────────────────────────────────────────────
function connectWebSocket() {
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/alerts`);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'alert') {
        showToast(`⚠️ ${data.severity} alert for ${data.location}`, 'warning');
      }
    };

    ws.onerror = () => {};
    ws.onclose = () => { setTimeout(connectWebSocket, 5000); };
    state.wsAlerts = ws;
  } catch {}
}

// ── Chart helpers ──────────────────────────────────────────────────────────────
function destroyChart(key) {
  if (state[key]) { state[key].destroy(); state[key] = null; }
}

// ── Initialisation ─────────────────────────────────────────────────────────────
async function init() {
  // Check health
  try {
    const res = await fetch('/health');
    const data = await res.json();
    state.demoMode = data.apis.demo_mode;
    if (state.demoMode) {
      const banner = document.getElementById('demo-banner');
      if (banner) banner.style.display = 'block';
    }
  } catch {}

  // Load initial weather for hero
  try {
    const res = await fetch(`/weather/current?location=${encodeURIComponent(state.location)}`);
    if (res.ok) {
      const w = await res.json();
      updateHeroWeather(w);
    }
  } catch {}

  // Connect WebSocket
  connectWebSocket();
}

// Start
document.addEventListener('DOMContentLoaded', init);
