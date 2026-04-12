# Hub v2 — Functional Test Specification

## Test Equipment
- 12V USB-C PD adapter
- Multimeter
- 3.5mm and 6.35mm audio cables
- Headphones
- Ethernet cable
- Laptop with nRF Connect

## Tests (all must PASS)

### TEST 1: Power Supply
1. Connect 12V via USB-C PD (J3)
2. U9 output: **PASS if 4.8V - 5.2V**
3. U10 output: **PASS if 3.2V - 3.4V**
4. All 6 LEDs show power-on sequence

### TEST 2: Raspberry Pi CM5 Boot
1. With microSD inserted, apply power
2. Pi CM5 boots (green LED on CM5 module blinks)
3. Ethernet (J4): connect cable, link LED lights up
4. **PASS if CM5 boots and network link established**

### TEST 3: Audio Input (TRS)
1. Connect audio source to J10 (6.35mm TRS)
2. Play 1kHz test tone
3. PCM1808 ADC captures signal
4. **PASS if signal detected on ADC**

### TEST 4: Audio Output (Headphone)
1. Connect headphones to J18 (6.35mm TRS)
2. Play audio through DAC → TPA6120A2
3. **PASS if audio clear in headphones**

### TEST 5: Speaker Output
1. Connect test speaker to J16 (Speakon)
2. Play audio through TPA3116D2
3. **PASS if audio audible from speaker**

### TEST 6: XLR Input
1. Connect XLR mic or line source to J14
2. Verify signal capture
3. **PASS if audio signal received**

### TEST 7: Digital Audio (Toslink)
1. Connect Toslink source to J6
2. Verify digital audio received
3. **PASS if signal detected**

### TEST 8: BLE Radio
1. Scan BLE with nRF Connect app
2. **PASS if "Koe-Hub-XXXX" appears**

### TEST 9: Enclosure
1. All connectors accessible through cutouts
2. Lid secure with 4 screws
3. Ventilation slots unobstructed
4. Rubber feet attached
5. **PASS if mechanical integrity OK**

## Reject Criteria
- Power test fail → check U9/U10 solder joints
- CM5 no boot → check J1/J2 connector seating
- Audio distortion → check ES9038Q2M/TPA3116 solder
