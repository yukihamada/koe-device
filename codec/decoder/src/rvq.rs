//! Product Vector Quantizer — sub-vector codebook lookup.
//!
//! Stores codebooks as Q15 (i16) for memory efficiency.
//! Layout: [stage][sub][entry][sub_dim]
//!
//! v2 format: 3 stages × 4 subs × 256 entries × 40 dims = 240 KB

use crate::{HOP_SIZE, N_STAGES, N_SUB, CODEBOOK_SIZE, SUB_DIM};

/// Product VQ codebook set, loaded from flash.
pub struct CodebookSet {
    /// Raw Q15 codebook data
    data: &'static [i16],
    /// Scale factors: [stage * N_SUB + sub]
    scales: [f32; N_STAGES * N_SUB],
}

impl CodebookSet {
    /// Parse from binary exported by Python trainer.
    ///
    /// Format v2 (magic "KOE2"):
    /// - 4 bytes: magic
    /// - 4 bytes: n_stages(u8), n_sub(u8), codebook_size(u8), sub_dim(u8)
    /// - N_STAGES * N_SUB * 4 bytes: scale factors (f32)
    /// - N_STAGES * N_SUB * CODEBOOK_SIZE * SUB_DIM * 2 bytes: Q15 data
    pub fn from_binary(data: &'static [u8]) -> Option<Self> {
        if data.len() < 8 {
            return None;
        }
        if &data[0..4] != b"KOE2" {
            return None;
        }

        let n_stages = data[4] as usize;
        let n_sub = data[5] as usize;
        let cb_size_byte = data[6];
        let sub_dim = data[7] as usize;

        // codebook_size: 256 wraps to 0 in u8
        let codebook_size = if cb_size_byte == 0 { 256 } else { cb_size_byte as usize };

        if n_stages != N_STAGES || n_sub != N_SUB
            || codebook_size != CODEBOOK_SIZE || sub_dim != SUB_DIM
        {
            return None;
        }

        // Read scales
        let mut scales = [0.0f32; N_STAGES * N_SUB];
        let scale_offset = 8;
        for (i, scale) in scales.iter_mut().enumerate() {
            let off = scale_offset + i * 4;
            *scale = f32::from_le_bytes([
                data[off], data[off + 1], data[off + 2], data[off + 3],
            ]);
        }

        // Codebook data
        let cb_offset = scale_offset + N_STAGES * N_SUB * 4;
        let cb_len = N_STAGES * N_SUB * CODEBOOK_SIZE * SUB_DIM;
        let cb_bytes = &data[cb_offset..cb_offset + cb_len * 2];

        let cb_data = unsafe {
            core::slice::from_raw_parts(cb_bytes.as_ptr() as *const i16, cb_len)
        };

        Some(Self {
            data: cb_data,
            scales,
        })
    }

    /// Create from pre-initialized data (testing).
    pub fn from_parts(data: &'static [i16], scales: [f32; N_STAGES * N_SUB]) -> Self {
        Self { data, scales }
    }

    /// Look up one sub-vector entry and accumulate into target buffer.
    ///
    /// `target` is a full HOP_SIZE buffer; this writes to the sub-vector's slice.
    #[inline]
    pub fn lookup_add(
        &self,
        stage: usize,
        sub: usize,
        index: usize,
        target: &mut [f32; HOP_SIZE],
    ) {
        let scale_idx = stage * N_SUB + sub;
        let scale = self.scales[scale_idx] / 32767.0;

        // Offset into flat data: (stage * N_SUB + sub) * CODEBOOK_SIZE * SUB_DIM + index * SUB_DIM
        let base = ((stage * N_SUB + sub) * CODEBOOK_SIZE + index) * SUB_DIM;
        let dst_start = sub * SUB_DIM;

        for i in 0..SUB_DIM {
            target[dst_start + i] += self.data[base + i] as f32 * scale;
        }
    }

    /// Decode a full frame from indices: (n_stages, n_sub) → HOP_SIZE floats
    pub fn decode_frame(
        &self,
        indices: &[[u16; N_SUB]; N_STAGES],
        output: &mut [f32; HOP_SIZE],
    ) {
        // Zero output
        for v in output.iter_mut() {
            *v = 0.0;
        }

        for stage in 0..N_STAGES {
            for sub in 0..N_SUB {
                self.lookup_add(stage, sub, indices[stage][sub] as usize, output);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_zeros() {
        static DATA: [i16; 122880] = [0; N_STAGES * N_SUB * CODEBOOK_SIZE * SUB_DIM];
        let scales = [1.0f32; N_STAGES * N_SUB];
        let cb = CodebookSet::from_parts(&DATA, scales);

        let indices = [[0u16; N_SUB]; N_STAGES];
        let mut output = [0.0f32; HOP_SIZE];
        cb.decode_frame(&indices, &mut output);

        for &v in output.iter() {
            assert_eq!(v, 0.0);
        }
    }
}
