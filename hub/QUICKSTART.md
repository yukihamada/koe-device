# Koe Hub Quick Start

## On your Mac (development)
```bash
cargo run --release
# Open http://localhost:3000
```

## On Raspberry Pi CM5
```bash
curl -sSL https://koe.live/setup-pi.sh | bash
# Open http://pi-ip:3000
```

## API Endpoints
- `GET  /api/status` — system status (channels, uptime, sample rate)
- `GET  /api/channels` — mixer channels with gain/pan/mute/EQ
- `POST /api/channels/:id/gain` — set channel gain
- `POST /api/crowd/enable` — toggle crowd mode
- `GET  /ws/mixer` — WebSocket for real-time mixer control

## Architecture
- **32-channel mixer** with 4-band EQ, pan, mute, solo, aux sends
- **UDP receivers**: Soluna (port 4242), Pro (port 4244), Crowd (port 4246)
- **Effects**: reverb, compressor, delay, gate, de-esser, stereo widener
- **Dashboard**: built-in web UI at port 3000

## Systemd Management
```bash
sudo systemctl status koe-hub    # check status
sudo systemctl restart koe-hub   # restart
sudo journalctl -u koe-hub -f    # follow logs
```
