// VisionXR Command Dashboard Orchestrator
let currentLayout = 'grid-2x2';
let focusedCam = 'cam_01';
let telemetryData = null;
let currentProfile = null; // Unauthenticated by default
let currentUserRole = null;
let currentSession = null;
let isEditMode = false;
let activeDrawType = 'red'; // 'green', 'amber', 'red'
let currentDrawingPoints = [];
let audioContext = null;

let CAM_CHANNELS = ['cam_01', 'cam_02', 'cam_03', 'cam_04'];
let cameraRegistry = [];

let authToken = localStorage.getItem('vxr_session_token');

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
    await loadBranding();
    const isAuthed = await checkAuthSession();
    if (!isAuthed) {
        // Portal remains locked behind full-screen auth overlay
        const userInp = document.getElementById('auth-username');
        if (userInp) userInp.focus();
        return;
    }
    // Only initialize layout, media, websockets if session is verified
    await bootstrapDashboard();
});

async function bootstrapDashboard() {
    initLayout();
    initAudio();
    setupEventListeners();
    initAntiPiracyShield();
    await loadCameraChannels();
    initWebSocket();
    refreshProfiles();
    checkEngineStatus();
}

async function loadBranding() {
    try {
        const res = await fetch('/api/governance/branding');
        if (res.ok) {
            const data = await res.json();
            const el = document.getElementById('login-company-name');
            if (el && data.company_name) {
                el.textContent = data.company_name.toUpperCase();
            }
            if (data.company_name) {
                document.title = `${data.company_name} • VisionXR Command Center`;
            }
        }
    } catch (e) {
        console.debug("Branding note:", e);
    }
}

async function checkAuthSession() {
    authToken = localStorage.getItem('vxr_session_token');
    const lockOverlay = document.getElementById('auth-lock-overlay');
    if (!authToken) {
        if (lockOverlay) lockOverlay.style.display = 'flex';
        return false;
    }

    try {
        const res = await fetch(`/api/auth/session?token=${encodeURIComponent(authToken)}`);
        if (!res.ok) {
            localStorage.removeItem('vxr_session_token');
            authToken = null;
            currentProfile = null;
            currentUserRole = null;
            currentSession = null;
            if (lockOverlay) lockOverlay.style.display = 'flex';
            return false;
        }
        const data = await res.json();
        if (lockOverlay) lockOverlay.style.display = 'none';
        applyAuthenticatedUser(data.session);
        return true;
    } catch (e) {
        if (lockOverlay) lockOverlay.style.display = 'flex';
        return false;
    }
}

async function submitLogin() {
    const userEl = document.getElementById('auth-username');
    const secEl = document.getElementById('auth-secret');
    const errBanner = document.getElementById('auth-error-banner');

    const user = userEl ? userEl.value.trim() : '';
    const sec = secEl ? secEl.value.trim() : '';

    if (!user || !sec) {
        if (errBanner) {
            errBanner.innerText = "Please provide your authorized username and secret password.";
            errBanner.style.display = 'block';
        }
        return;
    }

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, secret: sec })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            if (errBanner) {
                errBanner.innerText = `Authentication Failed: ${err.detail || 'Invalid Credentials'}`;
                errBanner.style.display = 'block';
            }
            return;
        }

        const data = await res.json();
        authToken = data.session.session_token;
        localStorage.setItem('vxr_session_token', authToken);

        const lockOverlay = document.getElementById('auth-lock-overlay');
        if (lockOverlay) lockOverlay.style.display = 'none';

        applyAuthenticatedUser(data.session);
        await bootstrapDashboard();
    } catch (e) {
        if (errBanner) {
            errBanner.innerText = `Network error during authentication: ${e}`;
            errBanner.style.display = 'block';
        }
    }
}

function applyAuthenticatedUser(session) {
    currentSession = session;
    currentProfile = session.user_id;
    currentUserRole = session.role;
    const adminBtn = document.getElementById('btn-admin-login');
    if (adminBtn) {
        const shortName = session.display_name.split(' ').pop() || session.username;
        adminBtn.innerText = `${session.avatar} ${shortName} (L${session.clearance})`;
        adminBtn.title = `${session.display_name} (${session.role} Level ${session.clearance}) • Click to view Admin Identity`;
        adminBtn.className = session.role === 'SUPER_ADMIN' ? 'btn btn-compact btn-cyan' : 'btn btn-compact btn-warning';
    }
    const infoEl = document.getElementById('modal-session-info');
    if (infoEl) {
        infoEl.innerHTML = `
            <div><b>Operator:</b> ${session.display_name} (@${session.username})</div>
            <div><b>Role:</b> <span style="color: ${session.role === 'SUPER_ADMIN' ? 'var(--color-cyan)' : 'var(--color-warning)'}; font-weight: bold;">${session.role}</span> (Clearance L${session.clearance})</div>
            <div><b>ID:</b> ${session.user_id}</div>
            <div><b>Terminal IP:</b> ${session.ip_address || 'Connected'}</div>
            <div style="font-size: 0.68rem; color: var(--text-muted); margin-top: 0.25rem;">Session: ${session.session_token.substring(0, 18)}...</div>
        `;
    }
}

async function handleLogout() {
    if (authToken) {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_token: authToken })
            });
        } catch (e) {}
    }
    localStorage.removeItem('vxr_session_token');
    authToken = null;
    currentUserRole = null;
    document.body.classList.remove('superadmin-unlocked');
    location.reload();
}

let isAudioMuted = true; // DEFAULT: MUTED
let isAlarmsSilenced = true; // Synced with mute state
let lastBeepTime = 0;

function initAudio() {
    updateSilenceButtonUI();
    updateAudioButtonUI();
}

function updateSilenceButtonUI() {
    const silenceBtn = document.getElementById('btn-silence');
    if (!silenceBtn) return;
    if (isAlarmsSilenced) {
        silenceBtn.className = 'btn btn-compact btn-warning';
        silenceBtn.innerHTML = '<span class="btn-icon">🔕</span> SILENCED';
        silenceBtn.title = 'Alarms are Silenced - Click to Arm Sound';
    } else {
        silenceBtn.className = 'btn btn-compact btn-green';
        silenceBtn.innerHTML = '<span class="btn-icon">🔔</span> ARMED';
        silenceBtn.title = 'Sound Alarms Armed & Active - Click to Silence';
    }
}

function updateAudioButtonUI() {
    const btn = document.getElementById('btn-audio-mute');
    if (btn) {
        if (isAudioMuted) {
            btn.className = 'btn btn-compact btn-danger';
            btn.innerHTML = '<span class="btn-icon">🔇</span> MUTED';
            btn.title = 'Audio Sound Muted - Click to Enable Sounds';
        } else {
            btn.className = 'btn btn-compact btn-green';
            btn.innerHTML = '<span class="btn-icon">🔊</span> AUDIO ON';
            btn.title = 'Audio Sound Active - Click to Mute';
        }
    }
}

function playArmedChime() {
    try {
        if (!audioContext || audioContext.state !== 'running') return;
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, audioContext.currentTime);
        gain.gain.setValueAtTime(0.04, audioContext.currentTime);
        gain.gain.linearRampToValueAtTime(0.001, audioContext.currentTime + 0.15);
        osc.connect(gain);
        gain.connect(audioContext.destination);
        osc.start();
        osc.stop(audioContext.currentTime + 0.15);
    } catch (e) {}
}

async function toggleSilence() {
    isAlarmsSilenced = !isAlarmsSilenced;
    isAudioMuted = isAlarmsSilenced;

    if (isAlarmsSilenced) {
        // Silencing
        try {
            await fetch('/api/alerts/silence', { method: 'POST' });
        } catch (e) {}
        if (audioContext && audioContext.state === 'running') {
            try { audioContext.suspend(); } catch (e) {}
        }
        if ('speechSynthesis' in window) {
            try { window.speechSynthesis.cancel(); } catch (e) {}
        }
        const sirenBtn = document.getElementById('btn-siren');
        if (sirenBtn) {
            sirenBtn.classList.remove('active');
            sirenBtn.innerHTML = '<span class="btn-icon">🔔</span> SIREN';
        }
        const list = document.getElementById('alerts-feed');
        if (list) {
            list.innerHTML = '<div style="padding: 10px; color: #f59e0b; font-size: 11px;">🔕 All alarms silenced. Sound output paused.</div>';
        }
    } else {
        // Un-silencing / Arming
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioContext && audioContext.state === 'suspended') {
            try { await audioContext.resume(); } catch (e) {}
        }
        playArmedChime();
        const list = document.getElementById('alerts-feed');
        if (list) {
            list.innerHTML = '<div style="padding: 10px; color: #10b981; font-size: 11px;">🔔 Sound alarms ARMED. Audio active for Red Zone breaches.</div>';
        }
    }

    updateSilenceButtonUI();
    updateAudioButtonUI();
}

// Alias for backwards-compatibility
async function silenceAllAlarms() {
    return toggleSilence();
}

function toggleAudioMute() {
    return toggleSilence();
}

function playSirenBeep() {
    // If audio is muted or context not active, play ZERO sound
    if (isAudioMuted || !audioContext || audioContext.state !== 'running') return;
    const now = Date.now();
    // Throttle: Never play sound more than once per 8 seconds
    if (now - lastBeepTime < 8000) return;
    lastBeepTime = now;
    try {
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, audioContext.currentTime);
        osc.frequency.setValueAtTime(660, audioContext.currentTime + 0.15);
        gain.gain.setValueAtTime(0.08, audioContext.currentTime);
        gain.gain.linearRampToValueAtTime(0.001, audioContext.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(audioContext.destination);
        osc.start();
        osc.stop(audioContext.currentTime + 0.35);

        if ('speechSynthesis' in window && !window.speechSynthesis.speaking) {
            const utter = new SpeechSynthesisUtterance("Warning: Red Zone Intrusion");
            utter.volume = 0.8;
            utter.rate = 1.1;
            window.speechSynthesis.speak(utter);
        }
    } catch (e) {
        console.warn("Audio alert error:", e);
    }
}

// WebSocket Telemetry Client
function initWebSocket() {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${loc.host}/ws/telemetry`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            telemetryData = data;
            renderTelemetryHUD(data);
            renderCanvasOverlays(data);
            renderAlertsList(data.recent_alerts);
            updateGlobalStates(data);
        } catch (err) {
            console.error("Telemetry parse error:", err);
        }
    };

    ws.onopen = () => {
        // Auto-heal: re-sync channels and refresh image streams when backend connection is restored
        loadCameraChannels();
        const t = Date.now();
        CAM_CHANNELS.forEach(cid => {
            const cell = document.getElementById(`cell-${cid}`);
            if (cell) {
                const img = cell.querySelector('.cam-video');
                if (img) img.src = `/api/stream/${cid}/mjpeg?t=${t}`;
            }
        });
    };

    ws.onclose = () => {
        setTimeout(initWebSocket, 2000); // Auto reconnect
    };
}

function handleStreamError(img, camId) {
    if (!img || img._retryTimer) return;
    img._retryTimer = setTimeout(() => {
        img._retryTimer = null;
        img.src = `/api/stream/${camId}/mjpeg?t=${Date.now()}`;
    }, 2000);
}

function renderTelemetryHUD(data) {
    if (!data.cameras) return;
    
    // Total stats across cameras
    let totalWorkers = 0;
    let totalViolations = 0;
    let avgPPE = 0;
    let count = 0;

    for (const [cid, t] of Object.entries(data.cameras)) {
        totalWorkers += (t.total_workers || 0);
        totalViolations += (t.violations_count || 0);
        if (t.total_workers > 0 && t.ppe_compliance_pct !== null && t.ppe_compliance_pct !== undefined) {
            avgPPE += t.ppe_compliance_pct;
            count++;
        }
    }

    const workersEl = document.getElementById('hud-workers');
    if (workersEl) {
        workersEl.innerText = totalWorkers;
        workersEl.style.color = totalWorkers > 0 ? 'var(--color-cyan)' : 'var(--text-muted)';
    }

    const ppeEl = document.getElementById('hud-ppe');
    if (ppeEl) {
        if (count > 0) {
            const ppeVal = (avgPPE / count).toFixed(1);
            ppeEl.innerText = `${ppeVal}%`;
            ppeEl.style.color = ppeVal >= 85 ? 'var(--color-green)' : 'var(--color-red)';
        } else {
            ppeEl.innerText = totalWorkers > 0 ? 'OFF' : 'N/A';
            ppeEl.style.color = 'var(--text-muted)';
        }
    }

    const violEl = document.getElementById('hud-violations');
    if (violEl) {
        violEl.innerText = totalViolations;
        violEl.style.color = totalViolations > 0 ? 'var(--color-red)' : 'var(--color-green)';
    }
    const db = data.acoustic?.ambient_db ?? 0.0;
    const acEl = document.getElementById('hud-acoustic');
    if (acEl) {
        acEl.innerText = db > 0 ? `${db} dB` : '0.0 dB';
        acEl.style.color = db > 85 ? 'var(--color-red)' : (db > 0 ? 'var(--color-amber)' : 'var(--text-muted)');
    }

    if (data.offloader) {
        document.getElementById('hud-offload').innerText = `${data.offloader.bandwidth_saved_pct}%`;
    }
}

function updateGlobalStates(data) {
    const sirenBtn = document.getElementById('btn-siren');
    const silenceBtn = document.getElementById('btn-silence');
    if (sirenBtn) {
        if (data.siren_active) {
            sirenBtn.classList.add('active');
            sirenBtn.innerHTML = '<span class="btn-icon">🚨</span> SIREN ACTIVE';
            if (silenceBtn && !isAlarmsSilenced) {
                silenceBtn.className = 'btn btn-compact btn-danger';
                silenceBtn.innerHTML = '<span class="btn-icon">🚨</span> SILENCE ALARM!';
                silenceBtn.title = 'ALARM ACTIVE! Click to Silence Immediately';
            }
            playSirenBeep();
        } else {
            sirenBtn.classList.remove('active');
            sirenBtn.innerHTML = '<span class="btn-icon">🔔</span> SIREN';
            updateSilenceButtonUI();
        }
    }

    const lockdownBtn = document.getElementById('btn-lockdown');
    if (lockdownBtn) {
        if (data.lockdown_active) {
            lockdownBtn.classList.add('active');
            lockdownBtn.innerText = '🔒 LOCKDOWN ACTIVE';
        } else {
            lockdownBtn.classList.remove('active');
            lockdownBtn.innerText = '🛡️ LOCKDOWN';
        }
    }

    const curfewBadge = document.getElementById('curfew-indicator');
    if (curfewBadge) {
        curfewBadge.style.display = data.curfew_active ? 'inline-block' : 'none';
    }
}

// Canvas Overlay Rendering Engine
function renderCanvasOverlays(data) {
    CAM_CHANNELS.forEach(cid => {
        const canvas = document.getElementById(`canvas-${cid}`);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const camData = data.cameras ? data.cameras[cid] : null;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. Draw Tri-Zone Polygons
        if (camData && camData.zones) {
            camData.zones.forEach(zone => {
                drawPolygonZone(ctx, canvas, zone);
            });
        }

        // Draw in-progress polygon if editing this camera
        if (isEditMode && focusedCam === cid && currentDrawingPoints.length > 0) {
            drawCurrentDrawingPolygon(ctx, canvas);
        }

        // 2. Draw Tracked Entities (Bounding boxes, velocity vectors, PPE)
        if (camData && camData.entities) {
            camData.entities.forEach(ent => {
                drawEntity(ctx, canvas, ent);
            });
        }
    });
}

function drawPolygonZone(ctx, canvas, zone) {
    const pts = zone.polygon;
    if (!pts || pts.length < 3) return;

    ctx.save();
    ctx.beginPath();
    
    // Scale points to canvas dimensions (base: 854x480)
    const scaleX = canvas.width / 854.0;
    const scaleY = canvas.height / 480.0;

    ctx.moveTo(pts[0][0] * scaleX, pts[0][1] * scaleY);
    for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i][0] * scaleX, pts[i][1] * scaleY);
    }
    ctx.closePath();

    if (zone.type === 'green') {
        ctx.fillStyle = 'rgba(16, 185, 129, 0.12)';
        ctx.strokeStyle = '#10b981';
    } else if (zone.type === 'amber') {
        ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
        ctx.strokeStyle = '#f59e0b';
    } else {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.28)';
        ctx.strokeStyle = '#ef4444';
    }

    ctx.lineWidth = 2;
    ctx.setLineDash([6, 3]);
    ctx.fill();
    ctx.stroke();

    // Zone Label
    ctx.font = '10px monospace';
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fillText(`${zone.name.toUpperCase()} [${zone.type.toUpperCase()}]`, pts[0][0] * scaleX + 6, pts[0][1] * scaleY + 14);

    ctx.restore();
}

function drawEntity(ctx, canvas, ent) {
    const scaleX = canvas.width / 854.0;
    const scaleY = canvas.height / 480.0;
    const [x1, y1, x2, y2] = ent.bbox;

    const sx1 = x1 * scaleX;
    const sy1 = y1 * scaleY;
    const sw = (x2 - x1) * scaleX;
    const sh = (y2 - y1) * scaleY;

    ctx.save();

    // Box Color according to intent
    let boxColor = '#06b6d4';
    if (ent.intent === 'MAN_DOWN') {
        boxColor = '#ef4444';
    } else if (ent.intent === 'RUSHING') {
        boxColor = '#f59e0b';
    }

    // Bounding Box
    ctx.strokeStyle = boxColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(sx1, sy1, sw, sh);

    // Entity Badge
    ctx.fillStyle = 'rgba(13, 18, 29, 0.85)';
    ctx.fillRect(sx1, sy1 - 20, Math.max(sw, 90), 18);

    ctx.font = '10px monospace';
    ctx.fillStyle = boxColor;
    ctx.fillText(`#${ent.id} ${ent.label} ${ent.intent}`, sx1 + 4, sy1 - 7);

    // PPE Verification Badges for Persons
    if (ent.label === 'person') {
        const vestIcon = ent.ppe_vest ? '🦺' : '❌';
        const helmetIcon = ent.ppe_helmet ? '⛑️' : '❌';
        ctx.fillText(`${vestIcon} ${helmetIcon}`, sx1 + sw - 28, sy1 - 7);
    }

    // Velocity Vector (Ground point to movement projection)
    const footX = sx1 + sw / 2;
    const footY = sy1 + sh;
    const speed = ent.speed || 0;
    
    if (speed > 5) {
        ctx.beginPath();
        ctx.moveTo(footX, footY);
        const vecLen = Math.min(speed * 0.4, 40);
        ctx.lineTo(footX + vecLen, footY);
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    ctx.restore();
}

function drawCurrentDrawingPolygon(ctx, canvas) {
    if (currentDrawingPoints.length === 0) return;
    const scaleX = canvas.width / 854.0;
    const scaleY = canvas.height / 480.0;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(currentDrawingPoints[0][0] * scaleX, currentDrawingPoints[0][1] * scaleY);
    for (let i = 1; i < currentDrawingPoints.length; i++) {
        ctx.lineTo(currentDrawingPoints[i][0] * scaleX, currentDrawingPoints[i][1] * scaleY);
    }
    ctx.strokeStyle = activeDrawType === 'green' ? '#10b981' : (activeDrawType === 'amber' ? '#f59e0b' : '#ef4444');
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw vertices
    currentDrawingPoints.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt[0] * scaleX, pt[1] * scaleY, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
    });
    ctx.restore();
}

// Alerts List & Forensic Evidence
window._currentAlerts = [];
window._selectedEvidenceAlert = null;

function renderAlertsList(alerts) {
    window._currentAlerts = alerts || [];
    const list = document.getElementById('alerts-feed');
    if (!list || !alerts) return;

    list.innerHTML = alerts.map(alt => `
        <div class="alert-item severity-${alt.severity}">
            <div class="alert-header">
                <span>${alt.severity === 'CRITICAL' ? '🚨' : (alt.severity === 'WARNING' ? '⚠️' : 'ℹ️')} ${alt.title}</span>
                <span class="badge ${alt.severity === 'CRITICAL' ? 'badge-red' : 'badge-amber'}">${alt.camera_id}</span>
            </div>
            <div class="alert-desc">${alt.description}</div>
            <div class="alert-footer" style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.35rem; gap: 0.25rem;">
                <span style="font-size: 0.68rem; color: var(--text-muted);">${alt.formatted_time}</span>
                <div style="display: flex; gap: 0.25rem; align-items: center;">
                    ${alt.snapshot_url ? `<button class="btn btn-compact btn-cyan" style="font-size: 0.62rem; padding: 0.15rem 0.35rem;" onclick="viewAlertEvidence('${alt.id}', 'img')" title="View Forensic Evidence Snapshot">📸 IMAGE</button>` : ''}
                    ${alt.video_url ? `<button class="btn btn-compact btn-warning" style="font-size: 0.62rem; padding: 0.15rem 0.35rem;" onclick="viewAlertEvidence('${alt.id}', 'vid')" title="Play Forensic Intruder Discrepancy Video Clip">🎬 VIDEO</button>` : ''}
                    <button class="btn btn-cyan" style="padding: 0.15rem 0.45rem; font-size: 0.65rem;" onclick="ackAlert('${alt.id}')">
                        ${alt.status === 'ACKNOWLEDGED' ? '✓ ACKED' : 'ACK'}
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function viewAlertEvidence(alertId, preferredTab = 'img') {
    const alt = (window._currentAlerts || []).find(a => a.id === alertId);
    if (!alt) return;
    window._selectedEvidenceAlert = alt;

    const detailsEl = document.getElementById('evidence-alert-details');
    if (detailsEl) {
        detailsEl.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                <b style="color: ${alt.severity === 'CRITICAL' ? '#f87171' : '#fbbf24'};">${alt.title}</b>
                <span class="badge ${alt.severity === 'CRITICAL' ? 'badge-red' : 'badge-amber'}">${alt.camera_id}</span>
            </div>
            <div style="color: #cbd5e1; margin-bottom: 0.25rem;">${alt.description}</div>
            <div style="color: #94a3b8; font-size: 0.7rem;">TIMESTAMP: ${alt.formatted_time} • STATUS: ${alt.status}</div>
        `;
    }

    const imgEl = document.getElementById('evidence-img');
    const vidEl = document.getElementById('evidence-video');
    const vidSrcEl = document.getElementById('evidence-video-source');
    const btnVid = document.getElementById('evidence-tab-vid');

    if (imgEl) imgEl.src = alt.snapshot_url || '';
    if (vidEl && vidSrcEl) {
        if (alt.video_url) {
            vidSrcEl.src = alt.video_url;
            vidEl.load();
            if (btnVid) btnVid.style.display = 'inline-flex';
        } else {
            if (btnVid) btnVid.style.display = 'none';
        }
    }

    switchEvidenceTab(alt.video_url && preferredTab === 'vid' ? 'vid' : 'img');
    const modal = document.getElementById('modal-evidence');
    if (modal) modal.style.display = 'flex';
}

function switchEvidenceTab(type) {
    const imgCont = document.getElementById('evidence-img-container');
    const vidCont = document.getElementById('evidence-vid-container');
    const btnImg = document.getElementById('evidence-tab-img');
    const btnVid = document.getElementById('evidence-tab-vid');
    const vidEl = document.getElementById('evidence-video');
    const shaEl = document.getElementById('evidence-sha256');
    const alt = window._selectedEvidenceAlert;

    if (type === 'img') {
        if (imgCont) imgCont.style.display = 'flex';
        if (vidCont) {
            vidCont.style.display = 'none';
            if (vidEl) vidEl.pause();
        }
        if (btnImg) btnImg.className = 'btn btn-compact btn-cyan';
        if (btnVid) btnVid.className = 'btn btn-compact';
        if (shaEl && alt) shaEl.textContent = alt.snapshot_sha256 || 'N/A';
    } else {
        if (imgCont) imgCont.style.display = 'none';
        if (vidCont) {
            vidCont.style.display = 'block';
            if (vidEl) vidEl.play().catch(() => {});
        }
        if (btnVid) btnVid.className = 'btn btn-compact btn-warning';
        if (btnImg) btnImg.className = 'btn btn-compact';
        if (shaEl && alt) shaEl.textContent = alt.video_sha256 || alt.snapshot_sha256 || 'N/A';
    }
}

async function ackAlert(alertId) {
    try {
        await fetch(`/api/alerts/${alertId}/ack`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator_name: "SecOps Controller" })
        });
    } catch (e) {
        console.error("ACK failed:", e);
    }
}

// Dynamic Multi-Camera Grid & Feed Architecture
async function loadCameraChannels() {
    try {
        const res = await fetch('/api/stream/cameras');
        if (res.ok) {
            cameraRegistry = await res.json();
            if (cameraRegistry && cameraRegistry.length > 0) {
                CAM_CHANNELS = cameraRegistry.map(c => c.id);
                renderSidebarChannels();
                renderGridViewport();
                setupCanvasClickListeners();
            }
        }
    } catch (e) {
        console.warn("Error loading dynamic camera feeds:", e);
    }
}

function renderSidebarChannels() {
    const container = document.getElementById('camera-channels-list');
    if (!container || !cameraRegistry || cameraRegistry.length === 0) return;

    const countBadge = document.getElementById('channels-count-badge');
    if (countBadge) {
        const maxQ = (cachedLicenseData && cachedLicenseData.max_cameras) ? cachedLicenseData.max_cameras : 32;
        countBadge.innerText = `${cameraRegistry.length} / ${maxQ} ACTIVE`;
    }

    container.innerHTML = cameraRegistry.map(cam => {
        const isLiveOptical = cam.type === 'usb_v4l2' || (cam.source && cam.source.startsWith('/dev/video')) || cam.source === '0' || cam.source === '2';
        const badgeClass = isLiveOptical ? 'badge-green' : 'badge-amber';
        const badgeText = isLiveOptical ? 'LIVE OPTICAL' : 'STANDBY';
        const isActive = cam.id === focusedCam ? 'active' : '';

        return `
        <div id="card-${cam.id}" class="camera-card ${isActive}" onclick="focusCamera('${cam.id}')">
          <div class="cam-meta">
            <span>${cam.id.toUpperCase()}: ${cam.name}</span>
            <span class="badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="cam-loc">${cam.location || cam.source} • ${cam.fps || 25} FPS</div>
        </div>
        `;
    }).join('');
}

function renderGridViewport() {
    const viewport = document.getElementById('grid-viewport');
    if (!viewport || !cameraRegistry || cameraRegistry.length === 0) return;

    let html = cameraRegistry.map(cam => {
        const isFocus = cam.id === focusedCam ? 'focus-active' : '';
        const isLive = cam.type === 'usb_v4l2' || (cam.source && cam.source.startsWith('/dev/video')) || cam.source === '0' || cam.source === '2';
        const tagText = isLive ? `${cam.id.toUpperCase()} • ${cam.name.toUpperCase()}` : `${cam.id.toUpperCase()} • PHYSICAL STANDBY`;
        const fpsText = isLive ? `${cam.fps || 30} FPS • REAL-TIME` : 'AWAITING RTSP';

        return `
        <div id="cell-${cam.id}" class="cam-cell ${isFocus}">
          <img class="cam-video" src="/api/stream/${cam.id}/mjpeg" alt="${cam.name}" onerror="handleStreamError(this, '${cam.id}')" />
          <canvas id="canvas-${cam.id}" class="cam-canvas" width="854" height="480"></canvas>
          <div class="osd-overlay">
            <div class="osd-live-tag"><div class="live-dot" style="${isLive ? '' : 'background: var(--color-amber);'}"></div> ${tagText}</div>
            <span>${fpsText}</span>
          </div>
        </div>
        `;
    }).join('');

    // Interactive "+ Provision Additional Camera Feed" Card directly in the grid
    html += `
    <div class="cam-cell add-camera-cell" onclick="openProvisionModal()" title="Click to Provision Another Camera Feed">
      <div style="text-align: center; padding: 1.5rem;">
        <div style="font-size: 2.2rem; color: var(--color-cyan); margin-bottom: 0.4rem;">➕</div>
        <div style="font-size: 0.95rem; font-weight: bold; color: var(--color-cyan); margin-bottom: 0.2rem;">ADD CAMERA FEED</div>
        <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.6rem;">Connect RTSP, ONVIF, USB V4L2 or Web Stream</div>
        <span class="btn btn-compact btn-cyan" style="font-size: 0.74rem;">📹 Provision New Feed</span>
      </div>
    </div>
    `;

    viewport.innerHTML = html;

    // Auto-select grid layout based on camera count
    if (cameraRegistry.length > 4 && currentLayout === 'grid-2x2') {
        currentLayout = 'grid-3x3';
    }
    viewport.className = `grid-viewport ${currentLayout}`;
}

function setupCanvasClickListeners() {
    CAM_CHANNELS.forEach(cid => {
        const canvas = document.getElementById(`canvas-${cid}`);
        if (canvas) {
            canvas.onclick = (e) => handleCanvasClick(e, cid);
        }
    });
}

function applyProvisionPreset(type) {
    const nextNum = (cameraRegistry ? cameraRegistry.length + 1 : 5);
    const idInput = document.getElementById('prov-id');
    const nameInput = document.getElementById('prov-name');
    const srcInput = document.getElementById('prov-source');
    const typeSelect = document.getElementById('prov-type');
    const locInput = document.getElementById('prov-location');

    if (type === 'usb') {
        idInput.value = `cam_${nextNum.toString().padStart(2, '0')}`;
        nameInput.value = `USB Optical Sensor #${nextNum}`;
        srcInput.value = `/dev/video${nextNum - 1}`;
        typeSelect.value = 'usb_v4l2';
        locInput.value = 'Local Workstation USB';
    } else if (type === 'rtsp') {
        idInput.value = `cam_${nextNum.toString().padStart(2, '0')}`;
        nameInput.value = `Industrial IP Dome #${nextNum}`;
        srcInput.value = `rtsp://192.168.1.${100 + nextNum}:554/live`;
        typeSelect.value = 'rtsp';
        locInput.value = 'Plant Perimeter Avenue';
    } else if (type === 'phone') {
        idInput.value = `cam_${nextNum.toString().padStart(2, '0')}`;
        nameInput.value = `Mobile Dashcam Feed #${nextNum}`;
        srcInput.value = `http://192.168.1.50:8080/video`;
        typeSelect.value = 'http';
        locInput.value = 'Vehicle Dashcam Stream';
    }
}

// Layout Switching
function initLayout() {
    setLayout('grid-2x2');
}

function setLayout(layout) {
    currentLayout = layout;
    const viewport = document.getElementById('grid-viewport');
    if (viewport) {
        viewport.className = `grid-viewport ${layout}`;
    }
    
    // Setup canvas resolution
    CAM_CHANNELS.forEach(cid => {
        const canvas = document.getElementById(`canvas-${cid}`);
        if (canvas) {
            canvas.width = 854;
            canvas.height = 480;
        }
    });
}

function focusCamera(camId) {
    focusedCam = camId;
    document.querySelectorAll('.camera-card').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.cam-cell').forEach(c => c.classList.remove('focus-active'));
    
    const card = document.getElementById(`card-${camId}`);
    const cell = document.getElementById(`cell-${camId}`);
    if (card) card.classList.add('active');
    if (cell) cell.classList.add('focus-active');

    const targetEl = document.getElementById('editor-target-cam');
    if (targetEl) targetEl.innerText = camId.toUpperCase();
}

// Interactive Polygon Zone Editor Controls
function toggleZoneEditor() {
    isEditMode = !isEditMode;
    const palette = document.getElementById('editor-palette');
    const tbControls = document.getElementById('zone-editor-controls');
    const btn = document.getElementById('btn-toggle-editor');
    if (tbControls) tbControls.style.display = 'inline-flex';
    if (isEditMode) {
        if (palette) palette.style.display = 'flex';
        btn.classList.add('active');
        btn.innerText = '📐 DRAWING: ON';
    } else {
        if (palette) palette.style.display = 'none';
        btn.classList.remove('active');
        btn.innerText = '📐 TRI-ZONES';
        currentDrawingPoints = [];
        document.querySelectorAll('.zone-draw-btn, #btn-toolbar-green, #btn-toolbar-amber, #btn-toolbar-red').forEach(b => b.classList.remove('active'));
    }
}

function setDrawType(type) {
    activeDrawType = type;
    if (!isEditMode) {
        toggleZoneEditor();
    }
    document.querySelectorAll('.zone-draw-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#btn-toolbar-green, #btn-toolbar-amber, #btn-toolbar-red').forEach(b => b.classList.remove('active'));
    
    const target = document.getElementById(`btn-draw-${type}`);
    if (target) target.classList.add('active');
    const tbTarget = document.getElementById(`btn-toolbar-${type}`);
    if (tbTarget) tbTarget.classList.add('active');
}

function handleCanvasClick(event, camId) {
    if (!isEditMode || camId !== focusedCam) return;
    const canvas = document.getElementById(`canvas-${camId}`);
    const rect = canvas.getBoundingClientRect();
    
    const clickX = (event.clientX - rect.left) * (854.0 / rect.width);
    const clickY = (event.clientY - rect.top) * (480.0 / rect.height);

    currentDrawingPoints.push([Math.round(clickX), Math.round(clickY)]);
}

async function saveCurrentZone() {
    if (currentDrawingPoints.length < 3) {
        alert("Please click at least 3 points on the video to define a polygon zone.");
        return;
    }

    try {
        // Fetch existing zones
        const res = await fetch(`/api/zones/${focusedCam}`);
        const existing = await res.json();

        const zoneName = prompt("Enter Zone Name:", `${activeDrawType.toUpperCase()} Perimeter Zone`);
        if (!zoneName) return;

        const newZone = {
            id: `zone_${focusedCam}_${Date.now()}`,
            name: zoneName,
            type: activeDrawType,
            polygon: currentDrawingPoints,
            max_dwell_sec: activeDrawType === 'amber' ? 5 : (activeDrawType === 'red' ? 0 : 60),
            description: "Custom user-defined spatial zone."
        };

        existing.push(newZone);

        await fetch(`/api/zones/${focusedCam}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ zones: existing })
        });

        currentDrawingPoints = [];
        alert(`✓ Zone '${zoneName}' successfully persisted!`);
    } catch (e) {
        console.error("Save zone error:", e);
    }
}

async function resetZones() {
    if (confirm(`Reset all zones for ${focusedCam} to presets?`)) {
        await fetch(`/api/zones/${focusedCam}/reset`, { method: 'POST' });
        currentDrawingPoints = [];
    }
}

async function clearAllZones() {
    if (confirm(`Clear all spatial zones from ${focusedCam.toUpperCase()}? This eliminates all zone breach alarms on this camera.`)) {
        await fetch(`/api/zones/${focusedCam}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ zones: [] })
        });
        currentDrawingPoints = [];
        alert(`✓ All zones cleared from ${focusedCam.toUpperCase()}. Camera is now in clean workspace mode.`);
    }
}

// SecOps Controls
async function toggleSiren() {
    const isAct = telemetryData?.siren_active || false;
    await fetch('/api/alerts/siren', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: !isAct, actor: "SecOps Controller" })
    });
}

async function toggleLockdown() {
    const isAct = telemetryData?.lockdown_active || false;
    await fetch('/api/alerts/lockdown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: !isAct, actor: "Sovereign Commander" })
    });
}

async function togglePrivacy() {
    const res = await fetch('/api/stream/privacy-toggle', { method: 'POST' });
    const data = await res.json();
    alert(`Privacy DPDP/GDPR Obfuscation: ${data.privacy_blur_enabled ? 'ENABLED' : 'DISABLED'}`);
}

async function testWhatsApp() {
    const res = await fetch('/api/alerts/test-whatsapp', { method: 'POST' });
    const data = await res.json();
    alert(`✓ WhatsApp Emergency Alert Dispatched to ${data.target}`);
}

async function triggerAcousticTest(type) {
    await fetch('/api/alerts/test-acoustic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_id: focusedCam, event_type: type })
    });
}

// Governance & Profiles
async function refreshProfiles() {
    const res = await fetch('/api/auth/profiles');
    const profiles = await res.json();
    const select = document.getElementById('profile-switcher');
    if (select) {
        select.innerHTML = profiles.map(p => `
            <option value="${p.user_id}" ${p.user_id === currentProfile ? 'selected' : ''}>
                ${p.avatar} ${p.username} (${p.role} L${p.clearance})
            </option>
        `).join('');
    }
}

function handleProfileChange(userId) {
    currentProfile = userId;
    alert(`Switched active security profile context to: ${userId}`);
}

function showModal(id) {
    closeModals();
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('open');
        modal.style.display = 'flex';
    }
}

function openBreakGlassModal() {
    showModal('modal-breakglass');
}

async function submitBreakGlass() {
    const reason = document.getElementById('bg-reason').value;
    if (!reason) {
        alert("Please enter a critical operational reason.");
        return;
    }

    const res = await fetch('/api/auth/break-glass/elevate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentProfile, reason, duration_sec: 900 })
    });
    const data = await res.json();
    closeModals();
    alert(`🚨 BREAK-GLASS EMERGENCY ELEVATION GRANTED (Clearance L4 Sovereign)`);
}

// IP Management Modal
async function openIPModal() {
    showModal('modal-ip');
    try {
        const res = await fetch('/api/security/ip/rules');
        const stats = await res.json();
        document.getElementById('ip-whitelist-list').innerText = stats.whitelist.join(', ');
        document.getElementById('ip-blacklist-list').innerText = stats.blacklist.length ? stats.blacklist.join(', ') : 'None';
        document.getElementById('ip-threats').innerText = stats.threats_blocked;
    } catch (e) {
        console.error("IP Modal fetch error:", e);
    }
}

async function addWhitelistIP() {
    const ip = prompt("Enter IP or CIDR to whitelist:");
    if (ip) {
        await fetch('/api/security/ip/whitelist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_or_cidr: ip })
        });
        openIPModal();
    }
}

// Sniffer Discovery Modal
async function openSnifferModal() {
    showModal('modal-sniffer');
    const body = document.getElementById('sniffer-results');
    body.innerHTML = '<em>Probing Sector 22 CCTV topology and RTSP/ONVIF streams...</em>';

    try {
        const res = await fetch('/api/sniffer/scan');
        const data = await res.json();
        body.innerHTML = data.discovered_devices.map(d => `
            <div style="padding: 0.5rem; background: var(--bg-card); border-radius: 4px; margin-bottom: 0.5rem; border: 1px solid var(--border-subtle);">
                <strong>${d.hostname}</strong> (${d.ip}) - <span class="badge badge-green">${d.status}</span><br>
                <small style="color: var(--color-cyan);">${d.vendor}</small><br>
                <small style="font-family: monospace; color: var(--text-muted);">${d.rtsp_url}</small>
            </div>
        `).join('');
    } catch (e) {
        body.innerHTML = '<span style="color: var(--color-red);">Failed to run hardware scan.</span>';
    }
}

// Cryptographic Audit Ledger Modal
async function openAuditModal() {
    showModal('modal-audit');
    refreshAuditEntries();
}

async function refreshAuditEntries() {
    const res = await fetch('/api/security/audit/ledger?limit=25');
    const data = await res.json();
    const container = document.getElementById('audit-entries');
    container.innerHTML = data.entries.map(e => `
        <div style="font-size: 0.75rem; padding: 0.4rem; border-bottom: 1px solid var(--border-subtle); font-family: monospace;">
            <span style="color: var(--color-cyan);">${e.formatted_time}</span> | 
            <strong>${e.actor}</strong> [${e.role}] &rarr; 
            <span style="color: var(--color-amber);">${e.action}</span> (${e.resource})
            <div style="color: var(--text-muted); font-size: 0.68rem;">Hash: ${e.entry_hash.slice(0, 24)}...</div>
        </div>
    `).join('');
}

async function verifyAuditChain() {
    const res = await fetch('/api/security/audit/verify');
    const result = await res.json();
    if (result.valid) {
        alert(`✓ AUDIT INTEGRITY VERIFIED:\n${result.message}\nTotal Entries: ${result.total_entries}`);
    } else {
        alert(`❌ INTEGRITY BREACH DETECTED:\n${result.message}`);
    }
}

function closeModals() {
    const vidEl = document.getElementById('evidence-video');
    if (vidEl) vidEl.pause();
    document.querySelectorAll('.modal-backdrop, .modal-overlay').forEach(m => {
        m.classList.remove('open');
        m.style.display = 'none';
    });
}

function setupEventListeners() {
    // Enable horizontal scroll on mouse wheel over the top header ribbon
    const headerEl = document.querySelector('header');
    if (headerEl) {
        headerEl.addEventListener('wheel', (e) => {
            if (e.deltaY !== 0) {
                e.preventDefault();
                headerEl.scrollLeft += e.deltaY;
            }
        }, { passive: false });
    }

    // Add canvas click listeners
    CAM_CHANNELS.forEach(cid => {
        const canvas = document.getElementById(`canvas-${cid}`);
        if (canvas) {
            canvas.addEventListener('click', (e) => handleCanvasClick(e, cid));
        }
    });
}

// Super Admin Camera Feed Provisioning & Deprovisioning
async function openProvisionModal() {
    showModal('modal-provision');
    try {
        const res = await fetch('/api/governance/license');
        if (res.ok) {
            const data = await res.json();
            const actCount = data.active_cameras || 0;
            const maxQuota = data.max_cameras || 4;
            
            const activeEl = document.getElementById('prov-active-count');
            const quotaEl = document.getElementById('prov-max-quota');
            const btnElevate = document.getElementById('btn-quick-elevate');
            
            if (activeEl) activeEl.innerText = actCount;
            if (quotaEl) quotaEl.innerText = maxQuota;
            
            if (btnElevate) {
                // If capacity is at or exceeds limit, highlight quick elevate
                btnElevate.style.display = (actCount >= maxQuota) ? 'inline-flex' : 'none';
            }
        }
    } catch (e) {
        console.warn("Could not fetch license quota for provision modal:", e);
    }
}

async function quickElevateQuota() {
    try {
        const licRes = await fetch('/api/governance/license');
        const licData = await licRes.json();
        const newQuota = Math.max(8, (licData.max_cameras || 4) + 4);
        
        const res = await fetch('/api/governance/license/quota', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                max_cameras: newQuota,
                tier: 'COMMERCIAL_ENTERPRISE'
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            alert(`Quota Elevation Error: ${err.detail}`);
            return;
        }
        
        const updated = await res.json();
        alert(`✓ Super Admin Camera Quota Successfully Elevated to ${updated.max_cameras} Channels!`);
        openProvisionModal();
    } catch (e) {
        alert(`Error elevating camera quota: ${e}`);
    }
}


async function submitProvisionCamera() {
    const camId = document.getElementById('prov-id').value.trim();
    const name = document.getElementById('prov-name').value.trim();
    const source = document.getElementById('prov-source').value.trim();
    const location = document.getElementById('prov-location').value.trim();
    const type = document.getElementById('prov-type').value;

    if (!camId || !name || !source) {
        alert("Please fill in Camera ID, Name, and Source URL.");
        return;
    }

    try {
        const res = await fetch('/api/governance/cameras/provision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                id: camId,
                name: name,
                source: source,
                location: location || "Sector 22 Perimeter",
                type: type,
                fps: 25,
                width: 854,
                height: 480
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Provisioning Failed: ${err.detail || 'Access Denied'}`);
            return;
        }

        const data = await res.json();
        closeModals();
        alert(`✓ Camera Feed '${data.camera.name}' (${data.camera.id}) successfully provisioned under Super Admin Governance!`);
        location.reload();
    } catch (e) {
        alert(`Error provisioning feed: ${e}`);
    }
}

function openDeprovisionModal() {
    showModal('modal-deprovision');
    const select = document.getElementById('deprov-cam-select');
    if (select) {
        select.innerHTML = CAM_CHANNELS.map(cid => `<option value="${cid}">${cid.toUpperCase()}</option>`).join('');
    }
}

async function submitDeprovisionCamera() {
    const camId = document.getElementById('deprov-cam-select').value;
    const reason = document.getElementById('deprov-reason').value.trim();

    if (!reason) {
        alert("Please provide a mandatory Super Admin governance justification.");
        return;
    }

    try {
        const res = await fetch(`/api/governance/cameras/${camId}/deprovision`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                reason: reason
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Deprovisioning Failed: ${err.detail || 'Access Denied'}`);
            return;
        }

        closeModals();
        alert(`✓ Camera feed '${camId}' safely deprovisioned and archived.`);
        await loadCameraChannels();
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

// Storage Governance & Quota Control
async function openStorageModal() {
    showModal('modal-storage');
    try {
        const res = await fetch('/api/governance/storage');
        const data = await res.json();
        
        if (document.getElementById('storage-used-mb')) document.getElementById('storage-used-mb').innerText = `${data.total_used_mb} MB`;
        if (document.getElementById('storage-quota-label')) document.getElementById('storage-quota-label').innerText = `Quota Limit: ${data.max_quota_mb} MB`;
        if (document.getElementById('storage-used-pct')) document.getElementById('storage-used-pct').innerText = `${data.usage_pct}%`;
        if (document.getElementById('storage-snapshot-count')) document.getElementById('storage-snapshot-count').innerText = `Snapshots: ${data.snapshot_count} files (${data.snapshot_used_mb} MB)`;
        if (document.getElementById('input-quota-mb')) document.getElementById('input-quota-mb').value = data.max_quota_mb;
        
        const bar = document.getElementById('storage-progress-bar');
        if (bar) {
            bar.style.width = `${Math.min(data.usage_pct, 100)}%`;
            bar.style.background = data.usage_pct > 80 ? 'var(--color-red)' : 'var(--color-cyan)';
        }
    } catch (e) {
        console.error("Storage query error:", e);
    }
}

async function updateStorageQuota() {
    const quota = parseFloat(document.getElementById('input-quota-mb').value);
    if (isNaN(quota) || quota < 10) {
        alert("Please specify a valid quota >= 10 MB.");
        return;
    }

    try {
        const res = await fetch('/api/governance/storage/quota', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                max_storage_mb: quota
            })
        });
        const data = await res.json();
        alert(`✓ Storage Quota updated to ${quota} MB on NVMe Boot Partition!`);
        openStorageModal();
    } catch (e) {
        alert(`Error updating quota: ${e}`);
    }
}

async function triggerManualPrune() {
    try {
        const res = await fetch('/api/governance/storage/prune', { method: 'POST' });
        const data = await res.json();
        alert(`🧹 Storage Pruned Successfully!\nFreed: ${data.freed_mb} MB\nSnapshots deleted: ${data.pruned_snapshots_count}`);
        openStorageModal();
    } catch (e) {
        alert(`Error pruning storage: ${e}`);
    }
}

// Super Admin Safety & Alarm Rules Governance
async function openSafetyRulesModal() {
    showModal('modal-safety-rules');
    try {
        const res = await fetch('/api/governance/safety-rules');
        if (res.ok) {
            const data = await res.json();
            const sub = data.rules?.subject || {};
            const obj = data.rules?.object || {};
            const esc = data.rules?.escalation || {};

            const setVal = (id, val) => {
                const el = document.getElementById(id);
                if (el && val !== undefined) el.value = val;
            };
            const setChk = (id, val) => {
                const el = document.getElementById(id);
                if (el && val !== undefined) el.checked = Boolean(val);
            };

            // Populate Subject Fields
            setVal('rule-amber-dwell', sub.amber_max_dwell_sec);
            setVal('rule-red-grace', sub.red_grace_period_sec);
            setVal('rule-mandown-sec', sub.man_down_motionless_sec);
            setVal('rule-run-speed', sub.running_speed_kmh);
            setVal('rule-sleep-sec', sub.sleeping_inactivity_sec);
            setVal('rule-glance-deg', sub.cheating_glance_deg);
            setChk('rule-req-vest', sub.require_ppe_vest);
            setChk('rule-req-helmet', sub.require_ppe_helmet);
            setChk('rule-curfew-enable', sub.curfew_enabled);

            // Populate Object Fields
            setVal('rule-forklift-speed', obj.forklift_speed_limit_kmh);
            setVal('rule-tilt-deg', obj.cargo_tilt_max_deg);
            setVal('rule-spill-m2', obj.chemical_spill_max_m2);
            setVal('rule-temp-c', obj.thermal_hotspot_threshold_c);
            setVal('rule-turb-score', obj.turbulence_chaos_threshold);
            setVal('rule-sound-db', obj.acoustic_decibel_threshold_db);

            // Populate Escalation Fields
            setChk('rule-auto-siren', esc.auto_trigger_siren_on_red);
            setChk('rule-auto-wa', esc.auto_dispatch_whatsapp);
            setChk('rule-auto-esd', esc.auto_trip_scada_esd);
        }
    } catch (e) {
        console.error("Failed to load safety rules:", e);
    }
}

async function saveSafetyRules() {
    const payload = {
        user_id: currentProfile,
        subject: {
            amber_max_dwell_sec: parseFloat(document.getElementById('rule-amber-dwell').value),
            red_grace_period_sec: parseFloat(document.getElementById('rule-red-grace').value),
            man_down_motionless_sec: parseFloat(document.getElementById('rule-mandown-sec').value),
            running_speed_kmh: parseFloat(document.getElementById('rule-run-speed').value),
            sleeping_inactivity_sec: parseFloat(document.getElementById('rule-sleep-sec').value),
            cheating_glance_deg: parseFloat(document.getElementById('rule-glance-deg').value),
            require_ppe_vest: document.getElementById('rule-req-vest').checked,
            require_ppe_helmet: document.getElementById('rule-req-helmet').checked,
            curfew_enabled: document.getElementById('rule-curfew-enable').checked
        },
        object: {
            forklift_speed_limit_kmh: parseFloat(document.getElementById('rule-forklift-speed').value),
            cargo_tilt_max_deg: parseFloat(document.getElementById('rule-tilt-deg').value),
            chemical_spill_max_m2: parseFloat(document.getElementById('rule-spill-m2').value),
            thermal_hotspot_threshold_c: parseFloat(document.getElementById('rule-temp-c').value),
            turbulence_chaos_threshold: parseFloat(document.getElementById('rule-turb-score').value),
            acoustic_decibel_threshold_db: parseFloat(document.getElementById('rule-sound-db').value)
        },
        escalation: {
            auto_trigger_siren_on_red: document.getElementById('rule-auto-siren').checked,
            auto_dispatch_whatsapp: document.getElementById('rule-auto-wa').checked,
            auto_trip_scada_esd: document.getElementById('rule-auto-esd').checked
        }
    };

    try {
        const res = await fetch('/api/governance/safety-rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Governance Permission Error: ${err.detail}`);
            return;
        }

        const data = await res.json();
        closeModals();
        alert("✓ Super Admin Safety & Alarm Parameters Successfully Deployed & Sealed in Audit Ledger!");
    } catch (e) {
        alert(`Error saving rules: ${e}`);
    }
}

async function resetSafetyRulesToDefault() {
    if (confirm("Reset all safety and alarm parameters to factory sovereign defaults?")) {
        try {
            const res = await fetch('/api/governance/safety-rules/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentProfile })
            });
            const data = await res.json();
            alert("✓ Reset to factory sovereign baseline!");
            openSafetyRulesModal();
        } catch (e) {
            alert(`Error resetting: ${e}`);
        }
    }
}

// Master Engine Start / Stop Switch
async function toggleEngineState() {
    try {
        const res = await fetch('/api/governance/engine/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentProfile, action: 'TOGGLE' })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Governance Permission Error: ${err.detail}`);
            return;
        }
        const data = await res.json();
        updateEngineUI(data.is_active);
    } catch (e) {
        alert(`Error toggling engine: ${e}`);
    }
}

function updateEngineUI(isActive) {
    const btn = document.getElementById('btn-engine-toggle');
    const stageBtn = document.getElementById('btn-stage-engine');
    const modalBtn = document.getElementById('modal-btn-engine-toggle');
    const statusText = document.getElementById('modal-engine-status-text');

    if (isActive) {
        if (btn) {
            btn.className = 'btn btn-compact btn-danger';
            btn.innerHTML = '<span class="btn-icon">⏹️</span> STOP SURVEILLANCE';
            btn.title = 'Surveillance Running - Click to STOP Engine & All Alarms';
        }
        if (stageBtn) {
            stageBtn.className = 'btn btn-danger';
            stageBtn.innerHTML = '⏹️ STOP SURVEILLANCE';
            stageBtn.title = 'Surveillance Running - Click to STOP Engine & All Alarms';
        }
        if (modalBtn) {
            modalBtn.className = 'btn btn-danger';
            modalBtn.innerText = '⏹️ STOP SURVEILLANCE ENGINE';
        }
        if (statusText) {
            statusText.style.color = 'var(--color-green)';
            statusText.innerText = 'STATUS: ACTIVE (SURVEILLANCE RUNNING)';
        }
    } else {
        if (btn) {
            btn.className = 'btn btn-compact btn-green active';
            btn.innerHTML = '<span class="btn-icon">▶️</span> START SURVEILLANCE';
            btn.title = 'Surveillance Stopped - Click to START Engine';
        }
        if (stageBtn) {
            stageBtn.className = 'btn btn-green active';
            stageBtn.innerHTML = '▶️ START SURVEILLANCE';
            stageBtn.title = 'Surveillance Stopped - Click to START Engine';
        }
        if (modalBtn) {
            modalBtn.className = 'btn btn-green active';
            modalBtn.innerText = '▶️ START SURVEILLANCE ENGINE';
        }
        if (statusText) {
            statusText.style.color = 'var(--color-red)';
            statusText.innerText = 'STATUS: PAUSED / STOPPED (NO ALARMS)';
        }
    }
}

async function checkEngineStatus() {
    try {
        const res = await fetch('/api/governance/engine/status');
        if (res.ok) {
            const data = await res.json();
            updateEngineUI(data.is_active);
        }
    } catch (e) {}
}

function openAdminLoginModal() {
    showModal('modal-admin-login');
    if (currentSession) {
        applyAuthenticatedUser(currentSession);
    }
    checkEngineStatus();
}

// License & Camera Task Matrix Engine Handlers
let cachedLicenseData = null;

async function openLicenseModal() {
    showModal('modal-license');

    try {
        const res = await fetch('/api/governance/license');
        if (res.ok) {
            const data = await res.json();
            cachedLicenseData = data;

            const tierEl = document.getElementById('lic-tier-name');
            if (tierEl) tierEl.innerText = data.tier_name || data.tier || 'Enterprise';
            const machEl = document.getElementById('lic-machine-id');
            if (machEl) machEl.innerText = data.machine_id || '--';
            const quotaEl = document.getElementById('lic-cam-quota');
            if (quotaEl) quotaEl.innerText = `${data.active_cameras || 4} / ${data.max_cameras || 16} Max`;

            const numInput = document.getElementById('lic-quota-number');
            if (numInput && data.max_cameras) numInput.value = data.max_cameras;

            const quotaSelect = document.getElementById('lic-quota-select');
            if (quotaSelect && data.max_cameras) {
                quotaSelect.value = data.max_cameras.toString();
            }

            const badge = document.getElementById('lic-dev-badge');
            if (badge) {
                if (data.is_developer_machine) {
                    badge.className = 'badge badge-amber';
                    badge.innerText = 'DEVELOPER MACHINE';
                } else {
                    badge.className = 'badge badge-green';
                    badge.innerText = 'COMMERCIAL LICENSED';
                }
            }

            const sel = document.getElementById('lic-task-cam-select');
            if (sel) loadTasksForSelectedCamera(sel.value || 'cam_01');
        }
    } catch (e) {
        console.warn("License fetch warning:", e);
    }
}

async function elevateCameraQuota() {
    const numInput = document.getElementById('lic-quota-number');
    const quotaSelect = document.getElementById('lic-quota-select');
    const newQuota = parseInt(numInput && numInput.value ? numInput.value : (quotaSelect ? quotaSelect.value : '16'), 10);
    if (!newQuota || newQuota < 1) {
        alert("Please enter a valid positive camera quota.");
        return;
    }

    try {
        const res = await fetch('/api/governance/license/quota', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                max_cameras: newQuota,
                tier: newQuota > 4 ? 'COMMERCIAL_ENTERPRISE' : 'DEVELOPER_PILOT'
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Governance Permission Error: ${err.detail}`);
            return;
        }

        const updated = await res.json();
        alert(`✓ Camera Quota Successfully Set to ${updated.max_cameras} Channels (Tier: ${updated.tier_name})!`);
        openLicenseModal();
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

function loadTasksForSelectedCamera(camId) {
    if (!cachedLicenseData || !cachedLicenseData.available_tasks) return;
    const container = document.getElementById('lic-task-checkboxes');
    if (!container) return;
    const assigned = (cachedLicenseData.camera_tasks && cachedLicenseData.camera_tasks[camId]) || [];

    container.innerHTML = cachedLicenseData.available_tasks.map(t => `
        <label style="display: flex; align-items: flex-start; gap: 0.35rem; background: var(--bg-surface); padding: 0.4rem; border-radius: 4px; border: 1px solid var(--border-subtle); cursor: pointer;">
            <input type="checkbox" value="${t.id}" ${assigned.includes(t.id) ? 'checked' : ''} style="margin-top: 0.15rem;" />
            <div>
                <b style="color: var(--color-cyan); font-size: 0.72rem;">${t.name}</b>
                <div style="font-size: 0.65rem; color: var(--text-muted);">${t.desc}</div>
            </div>
        </label>
    `).join('');
}

async function saveSelectedCameraTasks() {
    const camId = document.getElementById('lic-task-cam-select').value;
    const checkboxes = document.querySelectorAll('#lic-task-checkboxes input[type="checkbox"]');
    const selected = [];
    checkboxes.forEach(cb => {
        if (cb.checked) selected.push(cb.value);
    });

    try {
        const res = await fetch(`/api/governance/cameras/${camId}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentProfile, task_ids: selected })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Governance Error: ${err.detail}`);
            return;
        }
        if (cachedLicenseData && cachedLicenseData.camera_tasks) {
            cachedLicenseData.camera_tasks[camId] = selected;
        }
        alert(`✓ AI Tasks successfully assigned and deployed for ${camId.toUpperCase()}!`);
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

async function submitCommercialLicense() {
    const key = document.getElementById('lic-input-token').value.trim();
    if (!key) {
        alert("Please enter a valid cryptographic license key.");
        return;
    }

    try {
        const res = await fetch('/api/governance/license/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                license_key: key,
                tier: 'COMMERCIAL_ENTERPRISE',
                max_cameras: 16
            })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`License Error: ${err.detail}`);
            return;
        }
        alert("🎉 Commercial Enterprise License Successfully Activated! Camera capacity elevated to 16 channels.");
        openLicenseModal();
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

// Industrial Disaster Simulation Trigger Handler
async function triggerDisaster(type) {
    try {
        const res = await fetch('/api/industrial/disaster/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_id: focusedCam || 'cam_02',
                disaster_type: type
            })
        });
        const data = await res.json();
        console.log("Industrial disaster triggered:", data);
    } catch (e) {
        console.error("Disaster trigger error:", e);
    }
}

// Password Reset with 6-Digit Code Handlers
function openResetPasswordModal() {
    showModal('modal-password-reset');
    const banner = document.getElementById('reset-status-banner');
    if (banner) {
        banner.style.display = 'none';
        banner.innerHTML = '';
    }
}

async function requestResetCode() {
    const username = document.getElementById('reset-input-username').value.trim();
    const banner = document.getElementById('reset-status-banner');
    if (!username) {
        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(239, 68, 68, 0.2)';
            banner.style.color = '#fca5a5';
            banner.innerText = 'Please enter your username.';
        }
        return;
    }

    try {
        const res = await fetch('/api/auth/reset-password/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (!res.ok) {
            if (banner) {
                banner.style.display = 'block';
                banner.style.background = 'rgba(239, 68, 68, 0.2)';
                banner.style.color = '#fca5a5';
                banner.innerText = `Error: ${data.detail || 'Could not generate reset code.'}`;
            }
            return;
        }

        // Auto-fill and display code for user convenience
        const codeInput = document.getElementById('reset-input-code');
        if (codeInput && data.reset_code) {
            codeInput.value = data.reset_code;
        }

        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(16, 185, 129, 0.2)';
            banner.style.color = '#6ee7b7';
            banner.innerHTML = `✓ <b>Verification Code Issued:</b> <span style="font-family: monospace; font-size: 1.1rem; color: #10b981; letter-spacing: 0.15em;">${data.reset_code}</span><br><small>Valid for 15 minutes. Code auto-filled below.</small>`;
        }
    } catch (e) {
        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(239, 68, 68, 0.2)';
            banner.style.color = '#fca5a5';
            banner.innerText = `Network error: ${e}`;
        }
    }
}

async function confirmResetPassword() {
    const username = document.getElementById('reset-input-username').value.trim();
    const code = document.getElementById('reset-input-code').value.trim();
    const newPassword = document.getElementById('reset-input-newpassword').value;
    const banner = document.getElementById('reset-status-banner');

    if (!username || !code || !newPassword) {
        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(239, 68, 68, 0.2)';
            banner.style.color = '#fca5a5';
            banner.innerText = 'Please provide username, 6-digit code, and new password.';
        }
        return;
    }

    try {
        const res = await fetch('/api/auth/reset-password/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                reset_code: code,
                new_password: newPassword
            })
        });
        const data = await res.json();
        if (!res.ok) {
            if (banner) {
                banner.style.display = 'block';
                banner.style.background = 'rgba(239, 68, 68, 0.2)';
                banner.style.color = '#fca5a5';
                banner.innerText = `Reset Failed: ${data.detail || 'Invalid or expired code.'}`;
            }
            return;
        }

        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(16, 185, 129, 0.2)';
            banner.style.color = '#6ee7b7';
            banner.innerHTML = `✓ <b>Password Updated Successfully!</b> You can now log in with your new password.`;
        }

        // Auto-update secret input if login screen is open
        const secretInput = document.getElementById('auth-secret');
        if (secretInput) secretInput.value = newPassword;

        setTimeout(() => {
            closeModals();
        }, 2000);
    } catch (e) {
        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(239, 68, 68, 0.2)';
            banner.style.color = '#fca5a5';
            banner.innerText = `Network error: ${e}`;
        }
    }
}

// ==========================================
// Super Admin User Governance & Credentials
// ==========================================
let cachedUsersList = [];

function openUserGovernanceModal() {
    showModal('modal-user-governance');
    switchUserGovTab('list');
    fetchAndRenderUserGovList();
}

function switchUserGovTab(tabName) {
    const tabs = ['list', 'provision', 'passwords', 'matrix'];
    tabs.forEach(t => {
        const el = document.getElementById(`usergov-tab-${t}`);
        if (el) el.style.display = (t === tabName) ? 'block' : 'none';
        const btn = document.getElementById(`tab-btn-${t === 'list' ? 'users' : t}`);
        if (btn) {
            if (t === tabName) {
                btn.classList.add('btn-cyan', 'active');
            } else {
                btn.classList.remove('btn-cyan', 'active');
            }
        }
    });

    if (tabName === 'passwords') {
        populateUserGovPasswordDropdown();
    }
}

async function fetchAndRenderUserGovList() {
    const container = document.getElementById('usergov-users-table-container');
    if (!container) return;
    container.innerHTML = '<em style="color: var(--text-muted); font-size: 0.8rem;">Loading user accounts...</em>';

    try {
        const res = await fetch('/api/auth/users');
        const data = await res.json();
        cachedUsersList = data.users || [];

        if (cachedUsersList.length === 0) {
            container.innerHTML = '<div style="color: var(--text-muted); padding: 0.5rem;">No user accounts found.</div>';
            return;
        }

        let html = `
        <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem; text-align: left;">
            <thead>
                <tr style="border-bottom: 1px solid var(--border-subtle); color: var(--text-muted);">
                    <th style="padding: 0.45rem;">USER</th>
                    <th style="padding: 0.45rem;">USERNAME</th>
                    <th style="padding: 0.45rem;">ROLE & CLEARANCE</th>
                    <th style="padding: 0.45rem;">DEPARTMENT</th>
                    <th style="padding: 0.45rem;">CONTACT</th>
                    <th style="padding: 0.45rem; text-align: right;">ACTIONS</th>
                </tr>
            </thead>
            <tbody>
        `;

        cachedUsersList.forEach(u => {
            const isSuper = u.role === 'SUPER_ADMIN';
            const badgeClass = isSuper ? 'badge-red' : (u.clearance >= 3 ? 'badge-amber' : 'badge-cyan');
            const isCurrent = u.user_id === currentProfile;

            html += `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04); ${isCurrent ? 'background: rgba(6, 182, 212, 0.05);' : ''}">
                <td style="padding: 0.5rem; font-weight: bold;">
                    <span>${u.avatar || '👤'}</span> ${u.display_name} ${isCurrent ? '<span class="badge badge-green" style="font-size:0.6rem;">ACTIVE</span>' : ''}
                </td>
                <td style="padding: 0.5rem; font-family: monospace; color: var(--color-cyan);">${u.username}</td>
                <td style="padding: 0.5rem;">
                    <span class="badge ${badgeClass}">${u.role} (L${u.clearance})</span>
                </td>
                <td style="padding: 0.5rem; color: var(--text-muted);">${u.department || '--'}</td>
                <td style="padding: 0.5rem; color: var(--text-muted);">${u.phone || '--'}</td>
                <td style="padding: 0.5rem; text-align: right; white-space: nowrap;">
                    <button class="btn btn-compact btn-warning" style="font-size: 0.7rem; padding: 0.2rem 0.4rem;" onclick="quickResetUserPassword('${u.user_id}', '${u.username}')" title="Reset Password for ${u.username}">🔑 Reset</button>
                    <button class="btn btn-compact btn-cyan" style="font-size: 0.7rem; padding: 0.2rem 0.4rem;" onclick="switchProfileFromUserGov('${u.user_id}')" title="Switch Session Context">👤 Switch</button>
                    ${!isSuper ? `<button class="btn btn-compact btn-danger" style="font-size: 0.7rem; padding: 0.2rem 0.4rem;" onclick="deleteUserAccount('${u.user_id}', '${u.username}')" title="Delete User">🗑️</button>` : ''}
                </td>
            </tr>
            `;
        });

        html += `</tbody></table>`;
        container.innerHTML = html;
        populateUserGovPasswordDropdown();
    } catch (e) {
        container.innerHTML = `<span style="color: var(--color-red);">Error loading users: ${e}</span>`;
    }
}

function populateUserGovPasswordDropdown() {
    const select = document.getElementById('admin-override-user-select');
    if (!select || cachedUsersList.length === 0) return;
    select.innerHTML = cachedUsersList.map(u => `
        <option value="${u.user_id}">
            ${u.avatar || '👤'} ${u.display_name} (${u.username} • ${u.role})
        </option>
    `).join('');
}

function switchProfileFromUserGov(userId) {
    handleProfileChange(userId);
    closeModals();
    alert(`Switched active operational profile context to: ${userId}`);
}

async function submitCreateUser() {
    const username = document.getElementById('new-user-username').value.trim();
    const displayName = document.getElementById('new-user-name').value.trim();
    const role = document.getElementById('new-user-role').value;
    const clearance = parseInt(document.getElementById('new-user-clearance').value);
    const department = document.getElementById('new-user-dept').value.trim();
    const phone = document.getElementById('new-user-phone').value.trim();
    const password = document.getElementById('new-user-password').value;

    if (!username || !displayName) {
        alert("Please enter both username and full display name.");
        return;
    }
    if (!password || password.length < 6) {
        alert("Initial password must be at least 6 characters.");
        return;
    }

    try {
        const res = await fetch('/api/auth/users/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                display_name: displayName,
                role,
                clearance,
                department,
                phone,
                password
            })
        });

        const data = await res.json();
        if (!res.ok) {
            alert(`Failed to create user: ${data.detail || 'Error'}`);
            return;
        }

        alert(`✓ User '${username}' successfully provisioned with ${role} clearance (L${clearance})!`);
        document.getElementById('new-user-username').value = '';
        document.getElementById('new-user-name').value = '';
        document.getElementById('new-user-password').value = '';
        switchUserGovTab('list');
        fetchAndRenderUserGovList();
    } catch (e) {
        alert(`Network error creating user: ${e}`);
    }
}

function quickResetUserPassword(userId, username) {
    switchUserGovTab('passwords');
    const select = document.getElementById('admin-override-user-select');
    if (select) select.value = userId;
    const input = document.getElementById('admin-override-new-password');
    if (input) {
        input.value = '';
        input.focus();
    }
}

async function submitAdminPasswordOverride() {
    const userId = document.getElementById('admin-override-user-select').value;
    const newPassword = document.getElementById('admin-override-new-password').value;

    if (!newPassword || newPassword.length < 6) {
        alert("Password must be at least 6 characters long.");
        return;
    }

    try {
        const res = await fetch('/api/auth/users/admin-reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                new_password: newPassword
            })
        });

        const data = await res.json();
        if (!res.ok) {
            alert(`Failed: ${data.detail || 'Could not update password.'}`);
            return;
        }

        alert(`✓ ${data.message || 'Password successfully updated!'}`);
        document.getElementById('admin-override-new-password').value = '';
        switchUserGovTab('list');
    } catch (e) {
        alert(`Error resetting password: ${e}`);
    }
}

async function requestUserGovCode() {
    const username = document.getElementById('usergov-code-username').value.trim();
    const banner = document.getElementById('usergov-reset-banner');
    if (!username) {
        alert("Please enter a username.");
        return;
    }

    try {
        const res = await fetch('/api/auth/reset-password/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (!res.ok) {
            if (banner) {
                banner.style.display = 'block';
                banner.style.background = 'rgba(239, 68, 68, 0.2)';
                banner.style.color = '#fca5a5';
                banner.innerText = data.detail || 'User not found.';
            }
            return;
        }

        if (banner) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(16, 185, 129, 0.2)';
            banner.style.color = '#6ee7b7';
            banner.innerHTML = `✓ Verification Code Issued: <b style="font-size:1.1rem; color:var(--color-green);">${data.reset_code}</b> (Valid 15m)`;
        }

        const input = document.getElementById('usergov-code-input');
        if (input) input.value = data.reset_code;
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

async function confirmUserGovCode() {
    const username = document.getElementById('usergov-code-username').value.trim();
    const code = document.getElementById('usergov-code-input').value.trim();
    const newPassword = document.getElementById('usergov-code-newpass').value;

    if (!code || code.length !== 6) {
        alert("Please enter the 6-digit verification code.");
        return;
    }
    if (!newPassword || newPassword.length < 6) {
        alert("New password must be at least 6 characters.");
        return;
    }

    try {
        const res = await fetch('/api/auth/reset-password/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                reset_code: code,
                new_password: newPassword
            })
        });
        const data = await res.json();
        if (!res.ok) {
            alert(`Failed: ${data.detail || 'Invalid or expired code.'}`);
            return;
        }

        alert(`✓ Password for ${username} updated successfully!`);
        document.getElementById('usergov-code-input').value = '';
        document.getElementById('usergov-code-newpass').value = '';
        switchUserGovTab('list');
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

async function deleteUserAccount(userId, username) {
    if (!confirm(`Are you sure you want to permanently delete user account '${username}'?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/auth/users/${userId}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) {
            alert(`Failed: ${data.detail || 'Could not delete user.'}`);
            return;
        }
        alert(`✓ User '${username}' removed.`);
        fetchAndRenderUserGovList();
    } catch (e) {
        alert(`Error: ${e}`);
    }
}

// =========================================================================
// SUPER ADMIN FULL SUBSYSTEM & CAMERA HARDWARE RESET
// =========================================================================
async function triggerSubsystemReset() {
    if (!confirm("Perform a full Camera Subsystem Reset?\n\nThis will re-initialize all video device handles and restart the ingestion pipeline.\n\nNote: All audit logs, event records, and memory will remain completely intact.")) {
        return;
    }

    const btn = document.getElementById('btn-subsystem-reset');
    const statusEl = document.getElementById('subsystem-reset-status');
    if (btn) {
        btn.disabled = true;
        btn.innerText = "⏳ RE-INITIALIZING CAMERA HARDWARE...";
    }
    if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.style.background = 'rgba(6, 182, 212, 0.15)';
        statusEl.style.color = 'var(--color-cyan)';
        statusEl.innerText = "Releasing V4L2 device locks and re-binding optical streams...";
    }

    try {
        const res = await fetch('/api/governance/subsystem/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentProfile })
        });
        const data = await res.json();
        if (res.ok) {
            if (statusEl) {
                statusEl.style.background = 'rgba(16, 185, 129, 0.15)';
                statusEl.style.color = 'var(--color-green)';
                statusEl.innerText = `✓ ${data.message || 'Subsystem successfully reset.'}`;
            }
            // 1. Immediately re-fetch and render all camera channels (restores CAM_02 tile if missing)
            await loadCameraChannels();

            // 2. Refresh channel images by forcing cache-bust timestamp
            const t = Date.now();
            CAM_CHANNELS.forEach(cid => {
                const cell = document.getElementById(`cell-${cid}`);
                if (cell) {
                    const img = cell.querySelector('.cam-video');
                    if (img) {
                        img.src = `/api/stream/${cid}/mjpeg?t=${t}`;
                    }
                }
            });
        } else {
            if (statusEl) {
                statusEl.style.background = 'rgba(239, 68, 68, 0.15)';
                statusEl.style.color = '#fca5a5';
                statusEl.innerText = `Error: ${data.detail || 'Reset failed.'}`;
            }
        }
    } catch (e) {
        if (statusEl) {
            statusEl.style.background = 'rgba(239, 68, 68, 0.15)';
            statusEl.style.color = '#fca5a5';
            statusEl.innerText = `Network error: ${e}`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "⚡ RE-INITIALIZE ALL CAMERAS & RESTART PIPELINE";
        }
    }
}

// =========================================================================
// SOVEREIGN ANTI-PIRACY & INTELLECTUAL PROPERTY PROTECTION SHIELD
// Only SuperAdmin has privilege to select, copy, inspect, or drag
// =========================================================================
function isSuperAdmin() {
    return currentUserRole === 'SUPER_ADMIN';
}

let lastToastTime = 0;
function showAntiPiracyWarning(msg) {
    const now = Date.now();
    if (now - lastToastTime < 2500) return; // Prevent toast spam
    lastToastTime = now;

    let toast = document.querySelector('.anti-piracy-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'anti-piracy-toast';
        document.body.appendChild(toast);
    }
    toast.innerHTML = `<span>🔒</span> <span><b>Sovereign IP Guard:</b> ${msg}</span>`;
    toast.style.display = 'flex';
    toast.style.opacity = '1';

    setTimeout(() => {
        if (toast) {
            toast.style.opacity = '0';
            setTimeout(() => { if (toast) toast.style.display = 'none'; }, 300);
        }
    }, 2500);
}

function initAntiPiracyShield() {
    function isFormField(el) {
        if (!el) return false;
        const tag = el.tagName ? el.tagName.toLowerCase() : '';
        return tag === 'input' || tag === 'textarea' || el.isContentEditable === true;
    }

    function clearUISelection() {
        try {
            const sel = window.getSelection ? window.getSelection() : null;
            if (sel && sel.removeAllRanges) {
                sel.removeAllRanges();
            }
        } catch (e) {}
    }

    // 1. Right Click Context Menu Block (Permitted only inside text inputs)
    document.addEventListener('contextmenu', (e) => {
        if (!isFormField(e.target)) {
            e.preventDefault();
            e.stopPropagation();
            showAntiPiracyWarning("Right-click context menu is locked by Sovereign IP Guard.");
            return false;
        }
    }, true);

    // 2. Drag & Drop on Images / Feeds / Elements
    document.addEventListener('dragstart', (e) => {
        if (!isFormField(e.target)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    }, true);

    // 3. Text & Media Selection Block (Strictly prevented outside form inputs)
    document.addEventListener('selectstart', (e) => {
        if (!isFormField(e.target)) {
            e.preventDefault();
            e.stopPropagation();
            clearUISelection();
            return false;
        }
    }, true);

    // 4. Continuous Selection Change Monitor - Purge any stray selection ranges
    document.addEventListener('selectionchange', () => {
        const active = document.activeElement;
        if (!isFormField(active)) {
            const sel = window.getSelection ? window.getSelection() : null;
            if (sel && sel.rangeCount > 0 && sel.toString().length > 0) {
                sel.removeAllRanges();
            }
        }
    }, true);

    // 5. Clipboard Copy & Cut Interception outside form fields
    document.addEventListener('copy', (e) => {
        if (!isFormField(e.target)) {
            e.preventDefault();
            e.stopPropagation();
            clearUISelection();
            showAntiPiracyWarning("Text & image copying is locked for intellectual property protection.");
            return false;
        }
    }, true);

    document.addEventListener('cut', (e) => {
        if (!isFormField(e.target)) {
            e.preventDefault();
            e.stopPropagation();
            clearUISelection();
            return false;
        }
    }, true);

    // 6. Print Subsystem Lockdown (window.print override + beforeprint listener)
    try {
        window.print = function() {
            showAntiPiracyWarning("Printing is blocked by Sovereign IP Guard.");
            return false;
        };
    } catch (e) {}

    window.addEventListener('beforeprint', (e) => {
        e.preventDefault();
        showAntiPiracyWarning("Printing is blocked by Sovereign IP Guard.");
        return false;
    }, true);

    // 7. Special Developer & Function Key Blocking (Ctrl+P, Ctrl+A, Ctrl+C, F12, DevTools)
    const interceptProtectedKeys = (e) => {
        const isCtrlOrMeta = e.ctrlKey || e.metaKey;
        const key = (e.key || '').toUpperCase();
        const code = e.code || '';
        const keyCode = e.keyCode || e.which;
        const isInput = isFormField(e.target);

        // Ctrl+P (Print Page) - Unconditionally blocked across whole window
        if (isCtrlOrMeta && (key === 'P' || code === 'KeyP' || keyCode === 80)) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            showAntiPiracyWarning("Page printing is blocked by Sovereign IP Guard.");
            return false;
        }

        // Ctrl+A (Select All), Ctrl+C (Copy), Ctrl+X (Cut) outside input fields
        if (isCtrlOrMeta && (key === 'A' || key === 'C' || key === 'X' || code === 'KeyA' || code === 'KeyC' || code === 'KeyX' || keyCode === 65 || keyCode === 67 || keyCode === 88)) {
            if (!isInput) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                clearUISelection();
                showAntiPiracyWarning("Text selection & copying is locked by Sovereign IP Guard.");
                return false;
            }
        }

        // F12 or Developer Inspect keys
        if (key === 'F12' || code === 'F12' || keyCode === 123) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            showAntiPiracyWarning("Developer Tools access disabled by Hardware IP Guard.");
            return false;
        }

        // Ctrl+Shift+I (DevTools), Ctrl+Shift+J (Console), Ctrl+Shift+C (Inspect), Ctrl+Shift+K (Console)
        if (isCtrlOrMeta && e.shiftKey && (key === 'I' || key === 'J' || key === 'C' || key === 'K' || code === 'KeyI' || code === 'KeyJ' || code === 'KeyC' || code === 'KeyK' || keyCode === 73 || keyCode === 74 || keyCode === 67 || keyCode === 75)) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            showAntiPiracyWarning("Source inspection shortcuts are locked.");
            return false;
        }

        // Ctrl+U (View Source), Ctrl+S (Save Page)
        if (isCtrlOrMeta && (key === 'U' || key === 'S' || code === 'KeyU' || code === 'KeyS' || keyCode === 85 || keyCode === 83)) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            showAntiPiracyWarning("Source code saving and viewing is disabled.");
            return false;
        }
    };

    window.addEventListener('keydown', interceptProtectedKeys, { capture: true, passive: false });
    document.addEventListener('keydown', interceptProtectedKeys, { capture: true, passive: false });
}

// ==========================================
// Super Admin PPE Enforcement Governance
// ==========================================
let ppeEnforcementActive = true;

async function syncPPEButtonState() {
    try {
        const res = await fetch('/api/governance/ppe-status');
        if (res.ok) {
            const data = await res.json();
            ppeEnforcementActive = !!data.ppe_enforced;
            renderPPEButtons(ppeEnforcementActive);
        }
    } catch (e) {
        console.warn('Failed to sync PPE status:', e);
    }
}

function renderPPEButtons(active) {
    const topBtn = document.getElementById('btn-toggle-ppe');
    const topText = document.getElementById('btn-toggle-ppe-text');
    const govBtn = document.getElementById('gov-ppe-master-btn');

    if (topBtn && topText) {
        if (active) {
            topBtn.className = 'btn btn-compact btn-cyan';
            topText.innerText = 'PPE: ON';
            topBtn.title = 'Super Admin PPE Compliance Master Switch: ACTIVE (Click to Turn OFF)';
        } else {
            topBtn.className = 'btn btn-compact';
            topBtn.style.color = 'var(--text-muted)';
            topText.innerText = 'PPE: OFF';
            topBtn.title = 'Super Admin PPE Compliance Master Switch: DISABLED (Click to Turn ON)';
        }
    }

    if (govBtn) {
        if (active) {
            govBtn.className = 'btn btn-compact btn-cyan';
            govBtn.innerHTML = '🦺 PPE: ACTIVE';
            govBtn.title = 'Click to Turn OFF PPE Warnings';
        } else {
            govBtn.className = 'btn btn-compact';
            govBtn.style.color = 'var(--text-muted)';
            govBtn.innerHTML = '🦺 PPE: DISABLED';
            govBtn.title = 'Click to Turn ON PPE Warnings';
        }
    }

    // Also sync the checkboxes in the Rules modal if open
    const vestCb = document.getElementById('rule-req-vest');
    const helmetCb = document.getElementById('rule-req-helmet');
    if (vestCb) vestCb.checked = active;
    if (helmetCb) helmetCb.checked = active;

    // Update HUD indicator if turning off
    if (!active) {
        const ppeEl = document.getElementById('hud-ppe');
        if (ppeEl) {
            ppeEl.innerText = 'OFF';
            ppeEl.style.color = 'var(--text-muted)';
        }
    }
}

async function togglePPEEnforcement() {
    const newState = !ppeEnforcementActive;
    try {
        const res = await fetch('/api/governance/toggle-ppe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentProfile,
                enabled: newState
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Governance Permission Error: ${err.detail || 'Access Denied'}`);
            return;
        }

        const data = await res.json();
        ppeEnforcementActive = !!data.ppe_enforced;
        renderPPEButtons(ppeEnforcementActive);

        if (!ppeEnforcementActive) {
            // Remove all PPE warning cards from DOM immediately
            const feed = document.getElementById('alerts-feed');
            if (feed) {
                const ppeCards = feed.querySelectorAll('.alert-card');
                ppeCards.forEach(c => {
                    if (c.innerText.includes('PPE')) c.remove();
                });
            }
            alert('✓ PPE Compliance Warnings & Sirens Successfully Switched OFF by Super Admin!');
        } else {
            alert('✓ PPE Compliance Monitoring Activated by Super Admin.');
        }
    } catch (e) {
        alert(`Error toggling PPE: ${e}`);
    }
}

async function clearAllAlertsBus() {
    try {
        const res = await fetch('/api/alerts/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ actor: currentProfile })
        });
        if (res.ok) {
            const feed = document.getElementById('alerts-feed');
            if (feed) feed.innerHTML = '';
            alert('✓ All warning alerts cleared from Event Bus.');
        }
    } catch (e) {
        alert(`Error clearing alerts: ${e}`);
    }
}

// Initial sync on load
setTimeout(syncPPEButtonState, 500);

// ==========================================
// PUBLIC ADDRESS (PA) & PUSH-TO-TALK (PTT)
// ==========================================

let pttMediaRecorder = null;
let pttAudioChunks = [];
let pttStream = null;
let isPTTRecording = false;
let pttAudioContext = null;
let pttAnalyser = null;
let pttVUMeterAnimFrame = null;
let pttRecordingStartTime = 0;
let pttTimerInterval = null;
let pttPointerDownTime = 0;
let isPttHolding = false;
let pttMimeType = '';

function openPAModal() {
    showModal('modal-pa-broadcast');
    initPTTListeners();
    // Pre-warm and verify microphone access
    checkOrRequestMic();
}

function setPAPreset(text) {
    const input = document.getElementById('pa-tts-input');
    if (input) {
        input.value = text;
        input.focus();
    }
}

async function checkOrRequestMic() {
    const statusEl = document.getElementById('ptt-mic-status');
    const feedback = document.getElementById('ptt-feedback-bar');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (statusEl) statusEl.innerHTML = '<span style="color: var(--color-red);">● MIC UNSUPPORTED</span>';
        if (feedback) feedback.innerHTML = '<span style="color: var(--color-red);">Browser does not support mediaDevices API or requires HTTPS.</span>';
        return null;
    }

    if (pttStream && pttStream.active) {
        if (statusEl) statusEl.innerHTML = '<span style="color: var(--color-green);">● MIC READY</span>';
        startVUMeter(pttStream);
        return pttStream;
    }

    if (statusEl) statusEl.innerHTML = '<span style="color: var(--color-amber);">● REQUESTING MIC...</span>';

    try {
        pttStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        if (statusEl) statusEl.innerHTML = '<span style="color: var(--color-green);">● MIC READY</span>';
        if (feedback && !isPTTRecording) {
            feedback.innerHTML = '<span style="color: var(--color-cyan);">Microphone connected. Click or hold button to broadcast.</span>';
        }

        // Detect supported mimeType
        const candidates = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4'
        ];
        pttMimeType = '';
        if (window.MediaRecorder) {
            for (const t of candidates) {
                if (MediaRecorder.isTypeSupported(t)) {
                    pttMimeType = t;
                    break;
                }
            }
        }

        startVUMeter(pttStream);
        return pttStream;
    } catch (err) {
        console.warn("Microphone access denied or error:", err);
        if (statusEl) statusEl.innerHTML = '<span style="color: var(--color-red);">● MIC BLOCKED</span>';
        if (feedback) {
            feedback.innerHTML = `<span style="color: var(--color-red);">Microphone blocked: ${err.message || 'Permission denied'}. Please allow mic in browser settings.</span>`;
        }
        return null;
    }
}

function startVUMeter(stream) {
    try {
        if (!pttAudioContext || pttAudioContext.state === 'closed') {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            pttAudioContext = new AudioCtx();
        }
        if (pttAudioContext.state === 'suspended') {
            pttAudioContext.resume();
        }

        if (pttAnalyser) return; // already connected

        const source = pttAudioContext.createMediaStreamSource(stream);
        pttAnalyser = pttAudioContext.createAnalyser();
        pttAnalyser.fftSize = 256;
        source.connect(pttAnalyser);

        const dataArray = new Uint8Array(pttAnalyser.frequencyBinCount);
        const vuBar = document.getElementById('ptt-vu-meter');

        function updateMeter() {
            if (!document.getElementById('modal-pa-broadcast') || document.getElementById('modal-pa-broadcast').style.display === 'none') {
                pttVUMeterAnimFrame = requestAnimationFrame(updateMeter);
                return;
            }

            pttAnalyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const avg = sum / dataArray.length;
            const pct = Math.min(100, Math.round((avg / 128) * 100));

            if (vuBar) {
                vuBar.style.width = Math.max(2, pct) + '%';
                if (pct > 60) {
                    vuBar.style.background = 'var(--color-red)';
                } else if (pct > 25) {
                    vuBar.style.background = 'var(--color-amber)';
                } else {
                    vuBar.style.background = 'var(--color-green)';
                }
            }

            pttVUMeterAnimFrame = requestAnimationFrame(updateMeter);
        }

        if (pttVUMeterAnimFrame) cancelAnimationFrame(pttVUMeterAnimFrame);
        pttVUMeterAnimFrame = requestAnimationFrame(updateMeter);
    } catch (e) {
        console.warn("VU Meter initialization error:", e);
    }
}

async function broadcastTTSAnnouncement() {
    const input = document.getElementById('pa-tts-input');
    const zoneSel = document.getElementById('pa-target-zone');
    const feedback = document.getElementById('tts-feedback-bar');
    if (!input || !input.value.trim()) {
        alert("Please enter a message to broadcast.");
        return;
    }

    const message = input.value.trim();
    const targetZone = zoneSel ? zoneSel.value : "FACILITY_WIDE";

    if (feedback) {
        feedback.innerHTML = '<span style="color: var(--color-amber);">🔊 Broadcasting announcement to facility speakers...</span>';
    }

    try {
        const res = await fetch('/api/audio/broadcast-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                target_zone: targetZone,
                priority: 'HIGH',
                chime: true,
                actor: (typeof currentProfile !== 'undefined' && currentProfile) ? currentProfile : 'Commander'
            })
        });

        if (res.ok) {
            const data = await res.json();
            if (feedback) {
                feedback.innerHTML = `<span style="color: var(--color-green);">✓ Broadcast Dispatched! Played on facility speakers (${data.target_zone}).</span>`;
            }
            if (!isAudioMuted && data.audio_url) {
                const aud = new Audio(data.audio_url);
                aud.play().catch(() => {});
            }
            setTimeout(() => {
                if (feedback) feedback.innerText = '';
            }, 6000);
        } else {
            const err = await res.json().catch(() => ({}));
            if (feedback) feedback.innerHTML = `<span style="color: var(--color-red);">Error: ${err.detail || 'Broadcast failed'}</span>`;
        }
    } catch (e) {
        if (feedback) feedback.innerHTML = `<span style="color: var(--color-red);">Network Error: ${e}</span>`;
    }
}

function initPTTListeners() {
    const pttBtn = document.getElementById('btn-ptt-mic');
    if (!pttBtn || pttBtn._pttBound) return;
    pttBtn._pttBound = true;

    // Unified pointer events for mouse, touch, and stylus
    pttBtn.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        pttPointerDownTime = Date.now();

        if (isPTTRecording) {
            // Already recording in toggle mode -> click stops & transmits
            isPttHolding = false;
            stopPTTRecording();
            return;
        }

        // Start recording
        isPttHolding = true;
        startPTTRecording();
    });

    window.addEventListener('pointerup', (e) => {
        if (!isPTTRecording) {
            isPttHolding = false;
            return;
        }

        if (isPttHolding) {
            const heldDuration = Date.now() - pttPointerDownTime;
            // Hold-to-Talk: if held >= 400ms, releasing stops and transmits
            if (heldDuration >= 400) {
                isPttHolding = false;
                stopPTTRecording();
            } else {
                // Short click: switch into Click-to-Talk (Toggle) mode!
                isPttHolding = false;
                const statusText = document.getElementById('ptt-status-text');
                if (statusText) {
                    statusText.innerText = '🔴 TRANSMITTING • CLICK TO SEND';
                }
            }
        }
    });

    window.addEventListener('pointercancel', () => {
        if (isPTTRecording && isPttHolding) {
            isPttHolding = false;
            stopPTTRecording();
        }
    });
}

async function startPTTRecording() {
    if (isPTTRecording) return;
    const btn = document.getElementById('btn-ptt-mic');
    const statusText = document.getElementById('ptt-status-text');
    const feedback = document.getElementById('ptt-feedback-bar');

    // Ensure microphone stream is active
    let stream = pttStream;
    if (!stream || !stream.active) {
        if (statusText) statusText.innerText = '⏳ ACQUIRING MIC...';
        stream = await checkOrRequestMic();
    }

    if (!stream || !stream.active) {
        if (feedback) {
            feedback.innerHTML = '<span style="color: var(--color-red);">Microphone unavailable. Please grant microphone access.</span>';
        }
        if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
        return;
    }

    if (pttAudioContext && pttAudioContext.state === 'suspended') {
        pttAudioContext.resume().catch(() => {});
    }

    pttAudioChunks = [];
    try {
        const options = pttMimeType ? { mimeType: pttMimeType } : {};
        pttMediaRecorder = new MediaRecorder(stream, options);
    } catch (e) {
        try {
            pttMediaRecorder = new MediaRecorder(stream);
        } catch (err) {
            console.error("MediaRecorder creation failed:", err);
            if (feedback) feedback.innerHTML = `<span style="color: var(--color-red);">Recorder error: ${err.message}</span>`;
            return;
        }
    }

    pttMediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
            pttAudioChunks.push(e.data);
        }
    };

    pttMediaRecorder.onstop = () => {
        uploadPTTVoice();
    };

    pttMediaRecorder.start(100);
    isPTTRecording = true;
    pttRecordingStartTime = Date.now();

    if (btn) {
        btn.style.background = 'linear-gradient(135deg, #ef4444, #b91c1c)';
        btn.style.boxShadow = '0 0 25px rgba(239, 68, 68, 0.85)';
        btn.style.transform = 'scale(0.98)';
    }

    if (statusText) {
        statusText.innerText = '🔴 LIVE TRANSMITTING (00:00) • SPEAK NOW';
    }

    if (feedback) {
        feedback.innerHTML = '<span style="color: var(--color-red); font-weight: bold;">● LIVE ON FACILITY SPEAKERS • Release or click again to send</span>';
    }

    if (pttTimerInterval) clearInterval(pttTimerInterval);
    pttTimerInterval = setInterval(() => {
        if (!isPTTRecording) {
            clearInterval(pttTimerInterval);
            return;
        }
        const secs = Math.floor((Date.now() - pttRecordingStartTime) / 1000);
        const mm = String(Math.floor(secs / 60)).padStart(2, '0');
        const ss = String(secs % 60).padStart(2, '0');
        if (statusText) {
            statusText.innerText = `🔴 LIVE TRANSMITTING (${mm}:${ss}) • SPEAK NOW`;
        }
    }, 500);
}

function stopPTTRecording() {
    if (!isPTTRecording) return;
    isPTTRecording = false;

    if (pttTimerInterval) {
        clearInterval(pttTimerInterval);
        pttTimerInterval = null;
    }

    const btn = document.getElementById('btn-ptt-mic');
    const statusText = document.getElementById('ptt-status-text');
    const feedback = document.getElementById('ptt-feedback-bar');

    if (btn) {
        btn.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
        btn.style.boxShadow = '0 4px 14px rgba(245, 158, 11, 0.4)';
        btn.style.transform = 'none';
    }
    if (statusText) {
        statusText.innerText = '🎙️ PROCESSING TRANSMISSION...';
    }
    if (feedback) {
        feedback.innerHTML = '<span style="color: var(--color-cyan);">Encoding and broadcasting voice to facility speakers...</span>';
    }

    const elapsed = Date.now() - pttRecordingStartTime;
    const delay = Math.max(0, 400 - elapsed);
    setTimeout(() => {
        if (pttMediaRecorder && pttMediaRecorder.state !== 'inactive') {
            try {
                pttMediaRecorder.stop();
            } catch (e) {
                console.warn("Error stopping MediaRecorder:", e);
                uploadPTTVoice();
            }
        } else {
            uploadPTTVoice();
        }
    }, delay);
}

async function uploadPTTVoice() {
    const statusText = document.getElementById('ptt-status-text');
    const feedback = document.getElementById('ptt-feedback-bar');
    const zoneSel = document.getElementById('pa-target-zone');
    const targetZone = zoneSel ? zoneSel.value : "FACILITY_WIDE";

    if (pttAudioChunks.length === 0) {
        if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
        if (feedback) feedback.innerHTML = '<span style="color: var(--color-amber);">Recording was too brief. Please hold or click and speak.</span>';
        return;
    }

    const mime = (pttMediaRecorder && pttMediaRecorder.mimeType) || pttMimeType || 'audio/webm';
    const ext = mime.includes('mp4') ? 'mp4' : (mime.includes('ogg') ? 'ogg' : 'webm');
    const audioBlob = new Blob(pttAudioChunks, { type: mime });
    pttAudioChunks = [];

    if (audioBlob.size < 300) {
        if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
        if (feedback) feedback.innerHTML = '<span style="color: var(--color-amber);">Recording too short (< 0.4s). Please hold or click to speak.</span>';
        return;
    }

    const formData = new FormData();
    formData.append('file', audioBlob, `voice.${ext}`);
    formData.append('target_zone', targetZone);
    formData.append('actor', (typeof currentProfile !== 'undefined' && currentProfile) ? currentProfile : 'Commander');

    try {
        const res = await fetch('/api/audio/broadcast-voice', {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
            if (feedback) {
                const kb = (audioBlob.size / 1024).toFixed(1);
                feedback.innerHTML = `<span style="color: var(--color-green); font-weight: bold;">✓ Voice broadcast successfully played on facility speakers (${data.target_zone})! [${kb} KB]</span>`;
            }
            setTimeout(() => {
                if (feedback && !isPTTRecording) {
                    feedback.innerText = 'Ready to broadcast. Click or hold button to talk.';
                }
            }, 5000);
        } else {
            const err = await res.json().catch(() => ({}));
            if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
            if (feedback) {
                feedback.innerHTML = `<span style="color: var(--color-red);">Voice upload failed: ${err.detail || res.statusText}</span>`;
            }
        }
    } catch (e) {
        if (statusText) statusText.innerText = '🎙️ HOLD OR CLICK TO TALK (PUSH-TO-TALK)';
        if (feedback) feedback.innerHTML = `<span style="color: var(--color-red);">Network Error: ${e}</span>`;
    }
}


