// Soluna Player — WebAudio + WebSocket client
(function() {
  'use strict';

  const S = window.Soluna;
  const SAMPLE_RATE = 16000;
  const FRAME_SIZE = 1024; // samples per packet
  const SEND_INTERVAL_MS = 64; // 1024 samples / 16kHz = 64ms

  let ws = null;
  let audioCtx = null;
  let micStream = null;
  let micSource = null;
  let scriptNode = null;
  let isPlaying = false;
  let deviceHash = 0;
  let seq = 0;
  let currentChannel = 'soluna';
  let channelHash = 0;
  let encodeState = null;
  let decodeState = null;
  let volume = 0.8;
  let gainNode = null;
  let peerCount = 0;
  let analyserNode = null;
  let visualizerCanvas = null;
  let visualizerCtx = null;
  let animFrameId = null;

  // --- Init ---
  function init() {
    deviceHash = (Math.random() * 0xFFFFFFFF) >>> 0;
    channelHash = S.fnv1aStr(currentChannel);
    encodeState = new S.AdpcmState();
    decodeState = new S.AdpcmState();

    // Bind UI
    document.querySelectorAll('.channel-btn').forEach(btn => {
      btn.addEventListener('click', () => selectChannel(btn.dataset.channel));
    });

    const playBtn = document.getElementById('play-btn');
    if (playBtn) playBtn.addEventListener('click', togglePlay);

    const volSlider = document.getElementById('volume-slider');
    if (volSlider) {
      volSlider.addEventListener('input', (e) => {
        volume = parseFloat(e.target.value);
        if (gainNode) gainNode.gain.value = volume;
      });
    }

    visualizerCanvas = document.getElementById('visualizer');
    if (visualizerCanvas) {
      visualizerCtx = visualizerCanvas.getContext('2d');
    }

    // Set initial active channel
    selectChannel(currentChannel);
    updateStatus('disconnected');
  }

  function selectChannel(ch) {
    currentChannel = ch;
    channelHash = S.fnv1aStr(ch);
    encodeState.reset();
    decodeState.reset();
    seq = 0;

    document.querySelectorAll('.channel-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.channel === ch);
    });

    const chDisplay = document.getElementById('channel-display');
    if (chDisplay) chDisplay.textContent = ch;

    // Reconnect WS with new channel
    if (isPlaying) {
      disconnectWS();
      connectWS();
    }
  }

  async function togglePlay() {
    if (isPlaying) {
      stop();
    } else {
      await start();
    }
  }

  async function start() {
    try {
      // Create AudioContext
      audioCtx = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: SAMPLE_RATE,
      });

      // Resume context (required by autoplay policy)
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      // Gain node for volume control
      gainNode = audioCtx.createGain();
      gainNode.gain.value = volume;
      gainNode.connect(audioCtx.destination);

      // Analyser for visualization
      analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 256;
      analyserNode.connect(gainNode);

      // Get microphone
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      micSource = audioCtx.createMediaStreamSource(micStream);

      // ScriptProcessor for mic capture (AudioWorklet would be better but has broader compat issues)
      scriptNode = audioCtx.createScriptProcessor(FRAME_SIZE, 1, 1);
      scriptNode.onaudioprocess = onAudioProcess;
      micSource.connect(scriptNode);
      scriptNode.connect(audioCtx.createMediaStreamDestination()); // dummy output to keep it alive

      // Connect WebSocket
      connectWS();

      isPlaying = true;
      const playBtn = document.getElementById('play-btn');
      if (playBtn) playBtn.classList.add('active');
      updateStatus('connecting');

      // Start visualizer
      drawVisualizer();

    } catch (err) {
      console.error('Failed to start:', err);
      updateStatus('error: ' + err.message);
    }
  }

  function stop() {
    isPlaying = false;

    if (scriptNode) {
      scriptNode.disconnect();
      scriptNode = null;
    }
    if (micSource) {
      micSource.disconnect();
      micSource = null;
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
      micStream = null;
    }
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }

    disconnectWS();

    const playBtn = document.getElementById('play-btn');
    if (playBtn) playBtn.classList.remove('active');
    updateStatus('disconnected');
    peerCount = 0;
    updatePeerCount();
  }

  // --- Mic capture → encode → send ---
  function onAudioProcess(e) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const input = e.inputBuffer.getChannelData(0);
    const int16 = S.float32ToInt16(input);
    const adpcm = S.adpcmEncode(int16, encodeState);

    const packet = S.buildPacket(deviceHash, seq, channelHash, S.FLAG_ADPCM, adpcm);
    ws.send(packet.buffer);
    seq = (seq + 1) >>> 0;
  }

  // --- Receive → decode → play ---
  function onWSMessage(event) {
    if (typeof event.data === 'string') {
      // JSON control message
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'connected') {
          updateStatus('connected');
        }
      } catch {}
      return;
    }

    // Binary: Soluna packet
    const data = new Uint8Array(event.data);
    const pkt = S.parsePacket(data);
    if (!pkt || !pkt.audio) return;

    if (pkt.isHeartbeat || pkt.isChirp) return;

    if (pkt.isADPCM) {
      const pcm = S.adpcmDecode(pkt.audio, decodeState);
      const float32 = S.int16ToFloat32(pcm);
      playPCM(float32);
    }
  }

  function playPCM(float32Data) {
    if (!audioCtx || audioCtx.state === 'closed') return;

    const buffer = audioCtx.createBuffer(1, float32Data.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(float32Data);

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyserNode);
    source.start();
  }

  // --- WebSocket ---
  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws?channel=${encodeURIComponent(currentChannel)}`;

    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      updateStatus('connected');
      // Start heartbeat ping
      startPing();
    };

    ws.onmessage = onWSMessage;

    ws.onclose = () => {
      updateStatus('disconnected');
      if (isPlaying) {
        // Auto-reconnect
        setTimeout(connectWS, 2000);
      }
    };

    ws.onerror = (err) => {
      console.error('WS error:', err);
    };
  }

  function disconnectWS() {
    if (ws) {
      ws.onclose = null; // prevent auto-reconnect
      ws.close();
      ws = null;
    }
  }

  let pingInterval = null;
  function startPing() {
    if (pingInterval) clearInterval(pingInterval);
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 5000);
  }

  // --- UI updates ---
  function updateStatus(status) {
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('status-label');
    if (dot) {
      dot.classList.toggle('connected', status === 'connected');
    }
    if (label) {
      label.textContent = status;
    }
  }

  function updatePeerCount() {
    const el = document.getElementById('peer-count');
    if (el) el.textContent = peerCount;
  }

  // --- Visualizer ---
  function drawVisualizer() {
    if (!visualizerCanvas || !visualizerCtx || !analyserNode) return;

    const canvas = visualizerCanvas;
    const ctx = visualizerCtx;
    const w = canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
    const h = canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);

    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
      animFrameId = requestAnimationFrame(draw);
      analyserNode.getByteFrequencyData(dataArray);

      ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
      ctx.fillRect(0, 0, w, h);

      const barWidth = (w / bufferLength) * 2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 255;
        const barHeight = v * h;

        const r = Math.floor(0 + v * 0);
        const g = Math.floor(212 * v);
        const b = Math.floor(170 + v * 85);
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.fillRect(x, h - barHeight, barWidth - 1, barHeight);

        x += barWidth;
      }
    }

    draw();
  }

  // --- Boot ---
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for embed
  window.SolunaPlayer = { start, stop, selectChannel, togglePlay };
})();
