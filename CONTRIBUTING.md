# Contributing to Koe

Thanks for your interest in contributing to Koe.

## Ways to contribute

### Hardware
- Review schematic in `hardware/kicad/`
- Suggest BOM alternatives (cheaper, better availability)
- Design 3D printable enclosures
- Test prototypes and share measurements

### Firmware
- ESP32-S3 Rust development (`firmware/`)
- Audio DSP (VAD, AEC, AGC)
- Soluna P2P protocol improvements
- Bug fixes and testing

### Software
- Companion app (mobile)
- Cloud API (`/api/v1/device/audio` endpoint)
- Dashboard improvements (`docs/dashboard.html`)

### Documentation
- Translations
- Build guides with photos
- Tutorial videos

## Getting started

```bash
git clone https://github.com/yukihamada/koe-device.git
cd koe-device

# Firmware (requires ESP Rust toolchain)
cd firmware/demo
cargo install espup && espup install
WIFI_SSID="xxx" WIFI_PASS="yyy" cargo build

# Site (just open in browser)
open docs/index.html
```

## Pull requests

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-change`)
3. Make your changes
4. Test if possible
5. Submit a PR with a clear description

## Communication

- GitHub Issues for bugs and feature requests
- Email: info@enablerdao.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
