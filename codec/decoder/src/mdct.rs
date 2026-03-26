//! Inverse MDCT for KoeCodec.
//! Fixed-size (320 samples, 160 coefficients), zero-allocation.
//!
//! Uses direct computation (not FFT-based) since N=320 is small enough
//! and we want to avoid pulling in an FFT library for no_std.

use crate::{FRAME_SIZE, HOP_SIZE};
use core::f32::consts::PI;

/// Inverse MDCT processor with pre-computed window.
pub struct InverseMDCT {
    /// Synthesis window (sine window)
    window: [f32; FRAME_SIZE],
}

impl InverseMDCT {
    pub fn new() -> Self {
        let mut window = [0.0f32; FRAME_SIZE];
        for (n, w) in window.iter_mut().enumerate() {
            *w = sin_approx(PI * (n as f32 + 0.5) / FRAME_SIZE as f32);
        }
        Self { window }
    }

    /// Transform HOP_SIZE frequency coefficients to FRAME_SIZE time samples.
    /// Output is windowed and ready for overlap-add.
    pub fn process(&self, coeffs: &[f32; HOP_SIZE], output: &mut [f32; FRAME_SIZE]) {
        let n_half = HOP_SIZE as f32; // N in standard MDCT notation

        // Standard IMDCT: y[n] = (1/N) * sum_k X[k] * cos(pi/N * (n+0.5+N/2) * (k+0.5))
        let scale = 2.0 / n_half;

        for n in 0..FRAME_SIZE {
            let mut sum = 0.0f32;
            let n_term = (n as f32 + 0.5 + n_half / 2.0) * PI / n_half;

            for k in 0..HOP_SIZE {
                let angle = n_term * (k as f32 + 0.5);
                sum += coeffs[k] * cos_approx(angle);
            }

            output[n] = sum * scale * self.window[n];
        }
    }
}

/// Fast sine approximation using Bhaskara I's formula.
/// Accurate to ~0.2% over full range. Good enough for window computation.
#[inline]
fn sin_approx(x: f32) -> f32 {
    // Normalize to [0, 2*PI]
    let x = x % (2.0 * PI);
    let x = if x < 0.0 { x + 2.0 * PI } else { x };

    // Use symmetry to map to [0, PI]
    let (x, sign) = if x > PI { (x - PI, -1.0f32) } else { (x, 1.0) };

    // Bhaskara I's approximation: sin(x) ≈ 16x(π-x) / (5π²-4x(π-x))
    let numerator = 16.0 * x * (PI - x);
    let denominator = 5.0 * PI * PI - 4.0 * x * (PI - x);

    sign * numerator / denominator
}

/// Fast cosine via sin(x + π/2)
#[inline]
fn cos_approx(x: f32) -> f32 {
    sin_approx(x + PI / 2.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sin_approx() {
        // Check accuracy at key points
        assert!((sin_approx(0.0) - 0.0).abs() < 0.01);
        assert!((sin_approx(PI / 2.0) - 1.0).abs() < 0.01);
        assert!((sin_approx(PI) - 0.0).abs() < 0.01);
        assert!((sin_approx(3.0 * PI / 2.0) - (-1.0)).abs() < 0.01);
    }

    #[test]
    fn test_cos_approx() {
        assert!((cos_approx(0.0) - 1.0).abs() < 0.01);
        assert!((cos_approx(PI / 2.0) - 0.0).abs() < 0.02);
        assert!((cos_approx(PI) - (-1.0)).abs() < 0.01);
    }

    #[test]
    fn test_imdct_zeros() {
        let imdct = InverseMDCT::new();
        let coeffs = [0.0f32; HOP_SIZE];
        let mut output = [0.0f32; FRAME_SIZE];
        imdct.process(&coeffs, &mut output);

        for &s in output.iter() {
            assert_eq!(s, 0.0);
        }
    }

    #[test]
    fn test_imdct_dc() {
        let imdct = InverseMDCT::new();
        let mut coeffs = [0.0f32; HOP_SIZE];
        coeffs[0] = 1.0; // DC-like component
        let mut output = [0.0f32; FRAME_SIZE];
        imdct.process(&coeffs, &mut output);

        // Should produce a windowed cosine-like pattern
        let energy: f32 = output.iter().map(|x| x * x).sum();
        assert!(energy > 0.0);
    }
}
