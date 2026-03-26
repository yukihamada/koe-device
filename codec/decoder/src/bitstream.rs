//! Bitstream reader for KoeCodec frame decoding.
//! Zero-allocation, no_std compatible.

/// Bitstream reader that reads bits from a byte slice.
pub struct Reader<'a> {
    data: &'a [u8],
    byte_pos: usize,
    bit_pos: u8, // 0-7, MSB first
}

impl<'a> Reader<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            byte_pos: 0,
            bit_pos: 0,
        }
    }

    /// Read up to 16 bits, MSB first.
    #[inline]
    pub fn read_bits(&mut self, n_bits: u8) -> u32 {
        let mut value: u32 = 0;
        for _ in 0..n_bits {
            if self.byte_pos >= self.data.len() {
                return value;
            }
            let bit = (self.data[self.byte_pos] >> (7 - self.bit_pos)) & 1;
            value = (value << 1) | bit as u32;
            self.bit_pos += 1;
            if self.bit_pos == 8 {
                self.bit_pos = 0;
                self.byte_pos += 1;
            }
        }
        value
    }

    /// Number of bits remaining
    pub fn bits_remaining(&self) -> usize {
        if self.byte_pos >= self.data.len() {
            return 0;
        }
        (self.data.len() - self.byte_pos) * 8 - self.bit_pos as usize
    }
}

/// Bitstream writer for encoding (used in tests / host-side encoder)
#[cfg(feature = "std")]
pub struct Writer {
    buffer: Vec<u8>,
    current_byte: u8,
    bit_pos: u8,
}

#[cfg(feature = "std")]
impl Writer {
    pub fn new() -> Self {
        Self {
            buffer: Vec::new(),
            current_byte: 0,
            bit_pos: 0,
        }
    }

    pub fn write_bits(&mut self, value: u32, n_bits: u8) {
        for i in (0..n_bits).rev() {
            let bit = ((value >> i) & 1) as u8;
            self.current_byte = (self.current_byte << 1) | bit;
            self.bit_pos += 1;
            if self.bit_pos == 8 {
                self.buffer.push(self.current_byte);
                self.current_byte = 0;
                self.bit_pos = 0;
            }
        }
    }

    pub fn flush(&mut self) {
        if self.bit_pos > 0 {
            self.current_byte <<= 8 - self.bit_pos;
            self.buffer.push(self.current_byte);
            self.current_byte = 0;
            self.bit_pos = 0;
        }
    }

    pub fn into_bytes(mut self) -> Vec<u8> {
        self.flush();
        self.buffer
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_roundtrip() {
        let mut writer = Writer::new();
        writer.write_bits(0b1010101010, 10); // 682
        writer.write_bits(0xFF, 8); // 255
        writer.write_bits(0b110, 3); // 6
        let bytes = writer.into_bytes();

        let mut reader = Reader::new(&bytes);
        assert_eq!(reader.read_bits(10), 682);
        assert_eq!(reader.read_bits(8), 255);
        assert_eq!(reader.read_bits(3), 6);
    }

    #[test]
    fn test_frame_sized() {
        // Simulate a full KoeCodec frame: 20*8 + 4*10 = 200 bits = 25 bytes
        let mut writer = Writer::new();

        // Envelope: 20 bands * 8 bits
        for i in 0..20u32 {
            writer.write_bits(128 + i, 8);
        }

        // VQ indices: 4 stages * 10 bits
        for i in 0..4u32 {
            writer.write_bits(i * 100, 10);
        }

        let bytes = writer.into_bytes();
        assert_eq!(bytes.len(), 25);

        // Read back
        let mut reader = Reader::new(&bytes);
        for i in 0..20u32 {
            assert_eq!(reader.read_bits(8), 128 + i);
        }
        for i in 0..4u32 {
            assert_eq!(reader.read_bits(10), i * 100);
        }
    }
}
