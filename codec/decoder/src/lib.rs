//! KoeCodec v2 — ESP32-native audio codec decoder
//!
//! Product VQ (sub-vector quantization) + MDCT
//! Memory: ~240KB codebooks + ~2KB state
//! CPU: <20% of ESP32-S3 @ 240MHz for 16kHz real-time

#![cfg_attr(not(feature = "std"), no_std)]

pub mod bitstream;
pub mod mdct;
pub mod rvq;

use mdct::InverseMDCT;
use rvq::CodebookSet;

// v2 constants
pub const SAMPLE_RATE: u32 = 16000;
pub const FRAME_MS: u32 = 20;
pub const FRAME_SIZE: usize = 320; // SAMPLE_RATE * FRAME_MS / 1000
pub const HOP_SIZE: usize = 160;   // FRAME_SIZE / 2
pub const N_STAGES: usize = 3;
pub const N_SUB: usize = 4;
pub const CODEBOOK_SIZE: usize = 256;
pub const SUB_DIM: usize = 40;     // HOP_SIZE / N_SUB
pub const BITS_PER_INDEX: usize = 8;

/// Bits per frame: 3 stages * 4 subs * 8 bits = 96 bits = 12 bytes
pub const FRAME_BITS: usize = N_STAGES * N_SUB * BITS_PER_INDEX;
pub const FRAME_BYTES: usize = FRAME_BITS / 8; // 12

/// Streaming decoder
pub struct Decoder<'a> {
    codebooks: &'a CodebookSet,
    imdct: InverseMDCT,
    overlap_buf: [f32; HOP_SIZE],
}

impl<'a> Decoder<'a> {
    pub fn new(codebooks: &'a CodebookSet) -> Self {
        Self {
            codebooks,
            imdct: InverseMDCT::new(),
            overlap_buf: [0.0; HOP_SIZE],
        }
    }

    /// Decode one frame (12 bytes in) → HOP_SIZE (160) PCM samples out.
    pub fn decode_frame(&mut self, frame_data: &[u8], output: &mut [i16]) -> usize {
        let mut reader = bitstream::Reader::new(frame_data);

        // Read indices: n_stages * n_sub * 8 bits
        let mut indices = [[0u16; N_SUB]; N_STAGES];
        for stage in 0..N_STAGES {
            for sub in 0..N_SUB {
                indices[stage][sub] = reader.read_bits(BITS_PER_INDEX as u8) as u16;
            }
        }

        // VQ decode → MDCT coefficients
        let mut coeffs = [0.0f32; HOP_SIZE];
        self.codebooks.decode_frame(&indices, &mut coeffs);

        // Inverse MDCT
        let mut frame_pcm = [0.0f32; FRAME_SIZE];
        self.imdct.process(&coeffs, &mut frame_pcm);

        // Overlap-add
        let n_out = HOP_SIZE.min(output.len());
        for i in 0..n_out {
            let sample = frame_pcm[i] + self.overlap_buf[i];
            output[i] = f32_to_i16(sample);
        }
        self.overlap_buf.copy_from_slice(&frame_pcm[HOP_SIZE..]);

        n_out
    }

    pub fn reset(&mut self) {
        self.overlap_buf = [0.0; HOP_SIZE];
    }
}

#[inline]
fn f32_to_i16(x: f32) -> i16 {
    let scaled = x * 32767.0;
    if scaled > 32767.0 {
        32767
    } else if scaled < -32768.0 {
        -32768
    } else {
        scaled as i16
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_f32_to_i16() {
        assert_eq!(f32_to_i16(0.0), 0);
        assert_eq!(f32_to_i16(1.0), 32767);
        assert_eq!(f32_to_i16(-1.0), -32767);
        assert_eq!(f32_to_i16(2.0), 32767);
    }

    #[test]
    fn test_frame_bytes() {
        // 3 * 4 * 8 = 96 bits = 12 bytes
        assert_eq!(FRAME_BYTES, 12);
    }

    #[test]
    fn test_theoretical_bitrate() {
        // 12 bytes * 50 fps * 8 = 4800 bps = 4.8 kbps
        let bitrate = FRAME_BYTES as f64 * (1000.0 / FRAME_MS as f64) * 8.0;
        assert!((bitrate - 4800.0).abs() < 1.0);
    }
}
