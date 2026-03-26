package com.enabler.soluna

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Soluna audio sync protocol.
 *
 * 19-byte header:
 *   [0-1]   Magic: 0x53 0x4C ("SL")
 *   [2-5]   Device hash (u32 LE, FNV-1a of device ID)
 *   [6-9]   Sequence (u32 LE)
 *   [10-13] Channel hash (u32 LE, FNV-1a of channel name)
 *   [14-17] NTP timestamp ms (u32 LE)
 *   [18]    Flags: 0x01=ADPCM, 0x04=heartbeat
 */
object SolunaProtocol {

    const val HEADER_SIZE = 19
    const val MAGIC_0: Byte = 0x53  // 'S'
    const val MAGIC_1: Byte = 0x4C  // 'L'

    const val FLAG_ADPCM: Byte = 0x01
    const val FLAG_HEARTBEAT: Byte = 0x04

    const val MULTICAST_GROUP = "239.42.42.1"
    const val MULTICAST_PORT = 4242

    const val SAMPLE_RATE = 16000
    const val HEARTBEAT_INTERVAL_MS = 5000L

    // FNV-1a 32-bit
    fun fnv1a(data: ByteArray): Int {
        var hash = 0x811c9dc5.toInt()
        for (b in data) {
            hash = hash xor (b.toInt() and 0xFF)
            hash = (hash.toLong() * 0x01000193 and 0xFFFFFFFFL).toInt()
        }
        return hash
    }

    fun fnv1a(s: String): Int = fnv1a(s.toByteArray(Charsets.UTF_8))

    fun buildPacket(
        deviceHash: Int,
        sequence: Int,
        channelHash: Int,
        timestampMs: Long,
        flags: Byte,
        payload: ByteArray? = null
    ): ByteArray {
        val payloadSize = payload?.size ?: 0
        val buf = ByteBuffer.allocate(HEADER_SIZE + payloadSize)
            .order(ByteOrder.LITTLE_ENDIAN)

        buf.put(MAGIC_0)
        buf.put(MAGIC_1)
        buf.putInt(deviceHash)
        buf.putInt(sequence)
        buf.putInt(channelHash)
        buf.putInt((timestampMs and 0xFFFFFFFFL).toInt())
        buf.put(flags)

        if (payload != null) {
            buf.put(payload)
        }

        return buf.array()
    }

    data class ParsedPacket(
        val deviceHash: Int,
        val sequence: Int,
        val channelHash: Int,
        val timestampMs: Long,
        val flags: Byte,
        val payload: ByteArray
    )

    fun parsePacket(data: ByteArray, length: Int): ParsedPacket? {
        if (length < HEADER_SIZE) return null
        if (data[0] != MAGIC_0 || data[1] != MAGIC_1) return null

        val buf = ByteBuffer.wrap(data, 0, length).order(ByteOrder.LITTLE_ENDIAN)
        buf.position(2)

        val deviceHash = buf.getInt()
        val sequence = buf.getInt()
        val channelHash = buf.getInt()
        val timestampMs = buf.getInt().toLong() and 0xFFFFFFFFL
        val flags = buf.get()

        val payloadSize = length - HEADER_SIZE
        val payload = ByteArray(payloadSize)
        if (payloadSize > 0) {
            buf.get(payload)
        }

        return ParsedPacket(deviceHash, sequence, channelHash, timestampMs, flags, payload)
    }

    fun isHeartbeat(flags: Byte): Boolean = (flags.toInt() and FLAG_HEARTBEAT.toInt()) != 0
    fun isAdpcm(flags: Byte): Boolean = (flags.toInt() and FLAG_ADPCM.toInt()) != 0

    // IMA-ADPCM codec

    private val indexTable = intArrayOf(
        -1, -1, -1, -1, 2, 4, 6, 8,
        -1, -1, -1, -1, 2, 4, 6, 8
    )

    private val stepTable = intArrayOf(
        7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
        19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
        50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
        130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
        337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
        876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
        2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
        5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
        15289, 18217, 16818, 20000, 22000, 24200, 26620, 29282, 32210
    )

    class AdpcmState {
        var predictedSample: Int = 0
        var stepIndex: Int = 0
    }

    /** Encode 16-bit PCM samples to IMA-ADPCM (4:1 compression). */
    fun adpcmEncode(pcm: ShortArray, state: AdpcmState): ByteArray {
        val adpcm = ByteArray((pcm.size + 1) / 2)
        var outIdx = 0
        var nibbleBuf = 0
        var nibbleCount = 0

        for (sample in pcm) {
            val step = stepTable[state.stepIndex]
            var diff = sample.toInt() - state.predictedSample
            var code = 0

            if (diff < 0) {
                code = 8
                diff = -diff
            }
            if (diff >= step) { code = code or 4; diff -= step }
            if (diff >= step / 2) { code = code or 2; diff -= step / 2 }
            if (diff >= step / 4) { code = code or 1 }

            // Decode to update predictor
            var decodedDiff = step shr 3
            if (code and 4 != 0) decodedDiff += step
            if (code and 2 != 0) decodedDiff += step shr 1
            if (code and 1 != 0) decodedDiff += step shr 2

            state.predictedSample = if (code and 8 != 0) {
                (state.predictedSample - decodedDiff).coerceIn(-32768, 32767)
            } else {
                (state.predictedSample + decodedDiff).coerceIn(-32768, 32767)
            }

            state.stepIndex = (state.stepIndex + indexTable[code]).coerceIn(0, stepTable.size - 1)

            // Pack nibbles: low nibble first, then high
            if (nibbleCount == 0) {
                nibbleBuf = code and 0x0F
                nibbleCount = 1
            } else {
                nibbleBuf = nibbleBuf or ((code and 0x0F) shl 4)
                adpcm[outIdx++] = nibbleBuf.toByte()
                nibbleCount = 0
            }
        }

        // Flush remaining nibble
        if (nibbleCount == 1 && outIdx < adpcm.size) {
            adpcm[outIdx] = nibbleBuf.toByte()
        }

        return adpcm
    }

    /** Decode IMA-ADPCM to 16-bit PCM samples. */
    fun adpcmDecode(adpcm: ByteArray, sampleCount: Int, state: AdpcmState): ShortArray {
        val pcm = ShortArray(sampleCount)
        var inIdx = 0
        var nibbleHigh = false

        for (i in 0 until sampleCount) {
            val code: Int
            if (!nibbleHigh) {
                code = adpcm[inIdx].toInt() and 0x0F
                nibbleHigh = true
            } else {
                code = (adpcm[inIdx].toInt() shr 4) and 0x0F
                inIdx++
                nibbleHigh = false
            }

            val step = stepTable[state.stepIndex]
            var diff = step shr 3
            if (code and 4 != 0) diff += step
            if (code and 2 != 0) diff += step shr 1
            if (code and 1 != 0) diff += step shr 2

            state.predictedSample = if (code and 8 != 0) {
                (state.predictedSample - diff).coerceIn(-32768, 32767)
            } else {
                (state.predictedSample + diff).coerceIn(-32768, 32767)
            }

            state.stepIndex = (state.stepIndex + indexTable[code]).coerceIn(0, stepTable.size - 1)

            pcm[i] = state.predictedSample.toShort()
        }

        return pcm
    }
}
