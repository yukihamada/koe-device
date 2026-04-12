/// E2E integration tests for Koe Hub.
///
/// Tests the full pipeline: UDP packet ingestion -> mixer processing -> output.
/// Run with: cargo test --test e2e
///
/// These tests do NOT require network access or running servers.
/// They exercise the library API directly to simulate real device interactions.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use koe_hub::mixer::{MixerEngine, BUFFER_FRAMES, MAX_CHANNELS, EqBandType};
use koe_hub::effects::{AudioEffect, Reverb, Compressor, Delay, Gate, DeEsser, StereoWidener};
use koe_hub::receiver::{
    new_device_registry, new_crowd_aggregator, assign_device_to_channel,
};

// ---- Helper: build a Soluna UDP packet ----

fn build_soluna_packet(device_id: u32, seq: u32, adpcm_payload: &[u8]) -> Vec<u8> {
    let mut pkt = Vec::with_capacity(19 + adpcm_payload.len());
    pkt.extend_from_slice(&[0x53, 0x4C]); // Magic "SL"
    pkt.extend_from_slice(&device_id.to_le_bytes());
    pkt.extend_from_slice(&seq.to_le_bytes());
    pkt.extend_from_slice(&0u32.to_le_bytes()); // channel
    pkt.extend_from_slice(&0u32.to_le_bytes()); // ntp_ms
    pkt.push(0x00); // flags (no heartbeat, no crowd)
    pkt.extend_from_slice(adpcm_payload);
    pkt
}

// ---- Helper: build a Pro UDP packet (PCM16) ----

fn build_pro_packet(device_hash: u32, seq: u32, samples: &[i16]) -> Vec<u8> {
    let mut pkt = Vec::with_capacity(20 + samples.len() * 2);
    pkt.extend_from_slice(&[0x4B, 0x50]); // Magic "KP"
    pkt.extend_from_slice(&device_hash.to_le_bytes());
    pkt.extend_from_slice(&seq.to_le_bytes());
    pkt.extend_from_slice(&0u64.to_le_bytes()); // uwb_timestamp
    pkt.push(0x00); // codec = PCM16
    pkt.push(0x01); // channel_count = 1 (mono)
    for &s in samples {
        pkt.extend_from_slice(&s.to_le_bytes());
    }
    pkt
}

// ---- E2E Tests ----

#[test]
fn e2e_mixer_full_pipeline() {
    // Create a 32-channel mixer
    let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
    let registry = new_device_registry();

    // Assign 4 devices to channels
    assign_device_to_channel(&registry, &mixer, 0, 0x0001, "Kick".into()).unwrap();
    assign_device_to_channel(&registry, &mixer, 1, 0x0002, "Snare".into()).unwrap();
    assign_device_to_channel(&registry, &mixer, 2, 0x0003, "Guitar L".into()).unwrap();
    assign_device_to_channel(&registry, &mixer, 3, 0x0004, "Guitar R".into()).unwrap();

    // Guitar L/R should be auto-linked
    {
        let engine = mixer.lock().unwrap();
        assert_eq!(engine.channels[2].linked_pair, Some(3));
        assert_eq!(engine.channels[3].linked_pair, Some(2));
    }

    // Feed audio to all 4 channels
    let signal: Vec<i16> = vec![8192; BUFFER_FRAMES];
    {
        let mut engine = mixer.lock().unwrap();
        engine.add_samples(0, &signal);
        engine.add_samples(1, &signal);
        engine.add_samples(2, &signal);
        engine.add_samples(3, &signal);
    }

    // Process and verify output
    let output = {
        let mut engine = mixer.lock().unwrap();
        engine.process()
    };

    assert_eq!(output.len(), BUFFER_FRAMES * 2);
    assert!(output.iter().all(|s| s.is_finite()));
    assert!(output.iter().any(|&s| s > 0.0), "mixed output should have signal");
}

#[test]
fn e2e_gain_mute_via_api_simulation() {
    let mixer = Arc::new(Mutex::new(MixerEngine::new(8)));
    let registry = new_device_registry();

    assign_device_to_channel(&registry, &mixer, 0, 0x10, "Vocal".into()).unwrap();

    let signal: Vec<i16> = vec![16384; BUFFER_FRAMES];

    // Test 1: Normal gain
    {
        let mut engine = mixer.lock().unwrap();
        engine.add_samples(0, &signal);
        let out = engine.process();
        assert!(out.iter().any(|&s| s > 0.1), "should have signal at gain=1.0");
    }

    // Test 2: Set gain to 0 (simulating API call)
    {
        let mut engine = mixer.lock().unwrap();
        engine.channels[0].gain = 0.0;
        engine.add_samples(0, &signal);
        let out = engine.process();
        assert!(out.iter().all(|&s| s.abs() < f32::EPSILON), "gain=0 should silence");
    }

    // Test 3: Mute
    {
        let mut engine = mixer.lock().unwrap();
        engine.channels[0].gain = 1.0;
        engine.channels[0].mute = true;
        engine.add_samples(0, &signal);
        let out = engine.process();
        assert!(out.iter().all(|&s| s == 0.0), "muted channel should be silent");
    }

    // Test 4: Unmute
    {
        let mut engine = mixer.lock().unwrap();
        engine.channels[0].mute = false;
        engine.add_samples(0, &signal);
        let out = engine.process();
        assert!(out.iter().any(|&s| s > 0.0), "unmuted channel should have signal");
    }
}

#[test]
fn e2e_crowd_enable_disable() {
    let crowd = new_crowd_aggregator();

    // Initially disabled
    {
        let agg = crowd.lock().unwrap();
        assert!(!agg.is_enabled());
    }

    // Enable
    {
        let agg = crowd.lock().unwrap();
        agg.set_enabled(true);
        assert!(agg.is_enabled());
    }

    // Ingest while enabled
    {
        let mut agg = crowd.lock().unwrap();
        agg.ingest(1, vec![10000; 32]);
        agg.ingest(2, vec![10000; 32]);
        assert_eq!(agg.get_crowd_count(), 2);
    }

    // Mix
    {
        let mut agg = crowd.lock().unwrap();
        let mixed = agg.mix();
        assert!(!mixed.is_empty());
    }

    // Disable — new ingests should be ignored
    {
        let agg = crowd.lock().unwrap();
        agg.set_enabled(false);
    }
    {
        let mut agg = crowd.lock().unwrap();
        agg.ingest(3, vec![10000; 32]);
        // Count should still be 2 from before (not 3), since disabled
        assert_eq!(agg.get_crowd_count(), 2);
    }
}

#[test]
fn e2e_effect_chain_processing() {
    let mut mixer = MixerEngine::new(1);
    let signal: Vec<i16> = vec![8192; BUFFER_FRAMES];
    mixer.add_samples(0, &signal);
    let mut output = mixer.process();

    // Apply a chain of effects to the mixed output
    let mut reverb = Reverb::new(0.5, 0.5, 0.3);
    let mut comp = Compressor::new(-20.0, 4.0, 5.0, 100.0);
    let mut widener = StereoWidener::new(1.2);

    reverb.process(&mut output);
    comp.process(&mut output);
    widener.process(&mut output);

    assert!(output.iter().all(|s| s.is_finite()), "effect chain should produce finite output");
    assert!(output.iter().any(|&s| s.abs() > 0.0), "effect chain should preserve some signal");
}

#[test]
fn e2e_effect_parameter_changes() {
    let mut reverb = Reverb::new(0.3, 0.3, 0.2);
    let mut buf: Vec<f32> = vec![0.5; 256];

    // Process with initial params
    reverb.process(&mut buf);
    assert!(buf.iter().all(|s| s.is_finite()));

    // Change parameters mid-stream (simulating API call)
    reverb.set_params(0.9, 0.8, 0.8);

    let mut buf2: Vec<f32> = vec![0.5; 256];
    reverb.process(&mut buf2);
    assert!(buf2.iter().all(|s| s.is_finite()), "params change should not break processing");
}

#[test]
fn e2e_channel_levels_reporting() {
    let mut mixer = MixerEngine::new(4);

    // Ch0 gets a loud signal, Ch1 gets quiet, Ch2-3 get nothing
    let loud: Vec<i16> = vec![32000; BUFFER_FRAMES];
    let quiet: Vec<i16> = vec![100; BUFFER_FRAMES];
    mixer.add_samples(0, &loud);
    mixer.add_samples(1, &quiet);

    let _ = mixer.process();

    let levels = mixer.get_peak_levels();
    assert_eq!(levels.len(), 4);

    // Ch0 should have high level, Ch1 low, Ch2-3 zero
    assert!(levels[0].1 > 0.5, "ch0 should have high level");
    assert!(levels[1].1 < 0.1, "ch1 should have low level");
    assert!(levels[2].1 == 0.0, "ch2 should have zero level");
    assert!(levels[3].1 == 0.0, "ch3 should have zero level");
}

#[test]
fn e2e_eq_parameter_adjustment() {
    let mut mixer = MixerEngine::new(1);

    // Set up aggressive EQ
    mixer.channels[0].eq_bands[0] = koe_hub::mixer::EqBand {
        band_type: EqBandType::HighPass,
        frequency: 300.0,
        gain_db: 0.0,
        q: 1.0,
    };
    mixer.channels[0].eq_bands[3] = koe_hub::mixer::EqBand {
        band_type: EqBandType::LowPass,
        frequency: 8000.0,
        gain_db: 0.0,
        q: 1.0,
    };
    mixer.channels[0].eq_bands[1].gain_db = 10.0; // Boost mids

    let signal: Vec<i16> = vec![16384; BUFFER_FRAMES];
    mixer.add_samples(0, &signal);
    let out = mixer.process();

    assert!(out.iter().all(|s| s.is_finite()), "EQ with aggressive params should be finite");
}

#[test]
fn e2e_multiple_process_cycles() {
    let mut mixer = MixerEngine::new(2);
    let signal: Vec<i16> = vec![8192; BUFFER_FRAMES];

    // Run 100 process cycles to verify no state corruption
    for cycle in 0..100 {
        mixer.add_samples(0, &signal);
        if cycle % 3 == 0 {
            mixer.add_samples(1, &signal);
        }
        let out = mixer.process();
        assert!(out.iter().all(|s| s.is_finite()),
            "cycle {} produced non-finite output", cycle);
    }
}

#[test]
fn e2e_device_assignment_out_of_range() {
    let mixer = Arc::new(Mutex::new(MixerEngine::new(4)));
    let registry = new_device_registry();

    // Assign to channel 10 (out of range for 4-channel mixer)
    let result = assign_device_to_channel(&registry, &mixer, 10, 0x01, "Bad".into());
    assert!(result.is_err(), "out-of-range channel should return error");
}

#[test]
fn e2e_soluna_packet_structure() {
    // Verify our helper builds valid Soluna packets
    let pkt = build_soluna_packet(0xDEADBEEF, 42, &[0x12, 0x34, 0x56]);
    assert_eq!(pkt.len(), 19 + 3);
    assert_eq!(&pkt[0..2], &[0x53, 0x4C]); // Magic
    let device_id = u32::from_le_bytes([pkt[2], pkt[3], pkt[4], pkt[5]]);
    assert_eq!(device_id, 0xDEADBEEF);
    let seq = u32::from_le_bytes([pkt[6], pkt[7], pkt[8], pkt[9]]);
    assert_eq!(seq, 42);
}

#[test]
fn e2e_pro_packet_structure() {
    let samples: Vec<i16> = vec![1000, -1000];
    let pkt = build_pro_packet(0x42, 7, &samples);
    assert_eq!(pkt.len(), 20 + 4); // 20 header + 2 samples * 2 bytes
    assert_eq!(&pkt[0..2], &[0x4B, 0x50]); // Magic
    let codec = pkt[18];
    assert_eq!(codec, 0x00); // PCM16
    let ch_count = pkt[19];
    assert_eq!(ch_count, 1); // mono
}

#[test]
fn e2e_master_gain() {
    let mut mixer = MixerEngine::new(1);
    let signal: Vec<i16> = vec![8192; BUFFER_FRAMES];

    // Process with master_gain=1.0
    mixer.add_samples(0, &signal);
    let out_normal = mixer.process();
    let energy_normal: f32 = out_normal.iter().map(|s| s * s).sum();

    // Process with master_gain=0.5
    mixer.master_gain = 0.5;
    mixer.add_samples(0, &signal);
    let out_half = mixer.process();
    let energy_half: f32 = out_half.iter().map(|s| s * s).sum();

    assert!(energy_half < energy_normal, "master_gain=0.5 should reduce energy");
    // Energy should be roughly 1/4 (gain^2)
    let ratio = energy_half / energy_normal;
    assert!(ratio > 0.2 && ratio < 0.35, "energy ratio should be ~0.25, got {ratio}");
}

#[test]
fn e2e_aux_bus_full_workflow() {
    let mut mixer = MixerEngine::new(4);
    let signal: Vec<i16> = vec![16384; BUFFER_FRAMES];

    // Set up aux sends: ch0 -> aux0 at 100%, ch1 -> aux1 at 50%
    mixer.channels[0].aux_sends[0] = 1.0;
    mixer.channels[1].aux_sends[1] = 0.5;

    mixer.add_samples(0, &signal);
    mixer.add_samples(1, &signal);
    let _ = mixer.process();

    // Verify aux outputs
    let aux0_energy: f32 = mixer.aux_outputs[0].iter().map(|s| s * s).sum();
    let aux1_energy: f32 = mixer.aux_outputs[1].iter().map(|s| s * s).sum();
    let aux2_energy: f32 = mixer.aux_outputs[2].iter().map(|s| s * s).sum();

    assert!(aux0_energy > 0.0, "aux0 should have signal from ch0");
    assert!(aux1_energy > 0.0, "aux1 should have signal from ch1");
    assert!(aux2_energy == 0.0, "aux2 should be silent");

    // Aux1 at 50% should have less energy than aux0 at 100%
    assert!(aux1_energy < aux0_energy, "50% send should have less energy than 100%");
}
