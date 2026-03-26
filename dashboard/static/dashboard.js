// Soluna Dashboard — Device monitoring & visualization
(function() {
  'use strict';

  const S = window.Soluna;
  const POLL_INTERVAL = 1000;

  let topoCanvas, topoCtx;
  let distCanvas, distCtx;
  let devices = [];
  let totalPackets = 0;
  let uptimeSecs = 0;
  let ws = null;
  let packetRate = 0;
  let lastPacketCount = 0;
  let lastPollTime = Date.now();

  function init() {
    topoCanvas = document.getElementById('topo-canvas');
    distCanvas = document.getElementById('dist-canvas');

    if (topoCanvas) topoCtx = topoCanvas.getContext('2d');
    if (distCanvas) distCtx = distCanvas.getContext('2d');

    // Start polling
    poll();
    setInterval(poll, POLL_INTERVAL);

    // Connect dashboard WS for live updates
    connectDashboardWS();

    // Redraw on resize
    window.addEventListener('resize', () => {
      drawTopology();
      drawDistanceMap();
    });
  }

  async function poll() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      devices = data.devices || [];
      totalPackets = data.total_packets || 0;
      uptimeSecs = data.uptime_secs || 0;

      // Compute packet rate
      const now = Date.now();
      const elapsed = (now - lastPollTime) / 1000;
      if (elapsed > 0) {
        packetRate = Math.round((totalPackets - lastPacketCount) / elapsed);
      }
      lastPacketCount = totalPackets;
      lastPollTime = now;

      updateUI();
    } catch (err) {
      console.error('Poll error:', err);
    }
  }

  function connectDashboardWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws?channel=__dashboard__`;
    // Dashboard WS is optional — just for getting live packet flow
    // We mainly rely on REST polling for device list
  }

  function updateUI() {
    // Stats
    setText('stat-devices', devices.length);
    setText('stat-packets', formatNumber(totalPackets));
    setText('stat-rate', packetRate + '/s');
    setText('stat-uptime', formatUptime(uptimeSecs));

    // Unique channels
    const channels = new Set(devices.map(d => d.channel_name));
    setText('stat-channels', channels.size);

    // Status dot
    const dot = document.getElementById('status-dot');
    if (dot) dot.classList.toggle('connected', devices.length > 0 || uptimeSecs > 0);

    // Device list
    const list = document.getElementById('device-list');
    if (list) {
      if (devices.length === 0) {
        list.innerHTML = '<div class="no-devices">No devices connected. Start a Soluna device or open the Player to appear here.</div>';
      } else {
        list.innerHTML = devices.map(d => `
          <div class="device-row">
            <span class="hash">0x${d.hash.toString(16).padStart(8, '0')}</span>
            <span class="channel">${escapeHtml(d.channel_name)}</span>
            <span class="mode">${flagsToMode(d.flags)}</span>
            <span class="peers">${d.peer_count} peers</span>
            <span class="seq">#${d.last_seq}</span>
            <div class="level-meter">
              <div class="bar ${d.audio_level > 0.8 ? 'hot' : ''}" style="width: ${Math.round(d.audio_level * 100)}%"></div>
            </div>
          </div>
        `).join('');
      }
    }

    // Draw canvases
    drawTopology();
    drawDistanceMap();
  }

  function drawTopology() {
    if (!topoCanvas || !topoCtx) return;

    const canvas = topoCanvas;
    const ctx = topoCtx;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = (rect.width * 9 / 16) * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = (rect.width * 9 / 16) + 'px';
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.width * 9 / 16;

    // Clear
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.fillRect(0, 0, w, h);

    if (devices.length === 0) {
      ctx.fillStyle = '#888';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('No devices connected', w / 2, h / 2);
      return;
    }

    // Position devices in a circle
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(w, h) * 0.35;

    const positions = devices.map((d, i) => {
      const angle = (i / devices.length) * Math.PI * 2 - Math.PI / 2;
      return {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        device: d,
      };
    });

    // Draw connections (same channel)
    ctx.strokeStyle = 'rgba(0, 212, 170, 0.15)';
    ctx.lineWidth = 1;
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        if (positions[i].device.channel_hash === positions[j].device.channel_hash) {
          ctx.beginPath();
          ctx.moveTo(positions[i].x, positions[i].y);
          ctx.lineTo(positions[j].x, positions[j].y);
          ctx.stroke();
        }
      }
    }

    // Draw nodes
    for (const pos of positions) {
      const d = pos.device;

      // Glow based on audio level
      if (d.audio_level > 0.05) {
        const glowRadius = 20 + d.audio_level * 30;
        const grad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius);
        grad.addColorStop(0, `rgba(0, 212, 170, ${d.audio_level * 0.4})`);
        grad.addColorStop(1, 'rgba(0, 212, 170, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Node circle
      ctx.fillStyle = channelColor(d.channel_name);
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
      ctx.fill();

      // Border
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#e0e0e0';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('0x' + d.hash.toString(16).slice(-4), pos.x, pos.y + 24);
      ctx.fillStyle = '#888';
      ctx.font = '10px system-ui';
      ctx.fillText(d.channel_name, pos.x, pos.y + 38);
    }
  }

  function drawDistanceMap() {
    if (!distCanvas || !distCtx) return;

    const canvas = distCanvas;
    const ctx = distCtx;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = (rect.width * 9 / 16) * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = (rect.width * 9 / 16) + 'px';
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.width * 9 / 16;

    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.fillRect(0, 0, w, h);

    if (devices.length === 0) {
      ctx.fillStyle = '#888';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for acoustic ranging data...', w / 2, h / 2);
      return;
    }

    // Simple 2D scatter based on device hash (simulated positions when no real distance data)
    const cx = w / 2;
    const cy = h / 2;

    // Draw grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    // Scale rings
    ctx.strokeStyle = 'rgba(0, 212, 170, 0.1)';
    for (let r = 1; r <= 3; r++) {
      const ringR = r * Math.min(w, h) * 0.12;
      ctx.beginPath();
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = 'rgba(0, 212, 170, 0.3)';
      ctx.font = '9px system-ui';
      ctx.textAlign = 'left';
      ctx.fillText(`${r}m`, cx + ringR + 4, cy - 2);
    }

    // Place devices
    for (let i = 0; i < devices.length; i++) {
      const d = devices[i];
      // Use hash to deterministically position (since we don't have real coords)
      const angle = ((d.hash % 360) / 360) * Math.PI * 2;
      const dist = ((d.hash >> 8) % 100) / 100;
      const maxR = Math.min(w, h) * 0.4;
      const x = cx + Math.cos(angle) * dist * maxR;
      const y = cy + Math.sin(angle) * dist * maxR;

      // Pulse effect
      const pulseR = 6 + Math.sin(Date.now() / 500 + i) * 2;

      ctx.fillStyle = channelColor(d.channel_name);
      ctx.beginPath();
      ctx.arc(x, y, pulseR, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#ccc';
      ctx.font = '10px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('0x' + d.hash.toString(16).slice(-4), x, y + 20);
    }
  }

  // --- Helpers ---
  function channelColor(name) {
    switch (name) {
      case 'soluna': return '#00d4aa';
      case 'voice': return '#4488ff';
      case 'music': return '#ff6644';
      case 'ambient': return '#aa44ff';
      default: return '#888888';
    }
  }

  function flagsToMode(flags) {
    if (flags & S.FLAG_HEARTBEAT) return 'Heartbeat';
    if (flags & S.FLAG_CHIRP) return 'Ranging';
    if (flags & S.FLAG_ADPCM) return 'Audio';
    return 'Idle';
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function formatNumber(n) {
    if (n > 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n > 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
  }

  function formatUptime(secs) {
    if (secs < 60) return secs + 's';
    if (secs < 3600) return Math.floor(secs / 60) + 'm';
    return Math.floor(secs / 3600) + 'h ' + Math.floor((secs % 3600) / 60) + 'm';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // --- Boot ---
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
