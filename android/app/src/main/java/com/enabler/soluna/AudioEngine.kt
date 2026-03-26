package com.enabler.soluna

import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Audio engine: mic capture (16kHz mono 16-bit) -> ADPCM encode -> send,
 * receive -> ADPCM decode -> playback.
 */
class AudioEngine(
    private val onAudioCaptured: (ByteArray) -> Unit,
    private val onAudioLevel: (Int) -> Unit  // 0-100
) {
    companion object {
        private const val SAMPLE_RATE = SolunaProtocol.SAMPLE_RATE
        private const val CHANNEL_IN = AudioFormat.CHANNEL_IN_MONO
        private const val CHANNEL_OUT = AudioFormat.CHANNEL_OUT_MONO
        private const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
        private const val FRAME_SIZE = 320  // 20ms at 16kHz
    }

    private val recording = AtomicBoolean(false)
    private val playing = AtomicBoolean(false)

    private var audioRecord: AudioRecord? = null
    private var audioTrack: AudioTrack? = null
    private var captureThread: Thread? = null

    private val encodeState = SolunaProtocol.AdpcmState()
    private val decodeState = SolunaProtocol.AdpcmState()

    @Volatile
    var volume: Float = 0.8f

    fun startPlayback() {
        if (playing.getAndSet(true)) return

        val minBuf = AudioTrack.getMinBufferSize(SAMPLE_RATE, CHANNEL_OUT, ENCODING)
        val bufSize = maxOf(minBuf, FRAME_SIZE * 4)

        audioTrack = AudioTrack(
            AudioManager.STREAM_MUSIC,
            SAMPLE_RATE,
            CHANNEL_OUT,
            ENCODING,
            bufSize,
            AudioTrack.MODE_STREAM
        ).apply {
            setStereoVolume(volume, volume)
            play()
        }
    }

    fun stopPlayback() {
        if (!playing.getAndSet(false)) return
        try {
            audioTrack?.stop()
            audioTrack?.release()
        } catch (_: Exception) {}
        audioTrack = null
        decodeState.predictedSample = 0
        decodeState.stepIndex = 0
    }

    fun startCapture() {
        if (recording.getAndSet(true)) return

        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_IN, ENCODING)
        val bufSize = maxOf(minBuf, FRAME_SIZE * 4)

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            CHANNEL_IN,
            ENCODING,
            bufSize
        ).apply {
            startRecording()
        }

        encodeState.predictedSample = 0
        encodeState.stepIndex = 0

        captureThread = Thread({
            val buffer = ShortArray(FRAME_SIZE)
            while (recording.get()) {
                val read = audioRecord?.read(buffer, 0, FRAME_SIZE) ?: break
                if (read > 0) {
                    // Compute RMS for level meter
                    var sum = 0L
                    for (i in 0 until read) {
                        sum += buffer[i].toLong() * buffer[i].toLong()
                    }
                    val rms = Math.sqrt(sum.toDouble() / read)
                    val level = ((rms / 32768.0) * 300).toInt().coerceIn(0, 100)
                    onAudioLevel(level)

                    // ADPCM encode and send
                    val samples = if (read == FRAME_SIZE) buffer else buffer.copyOf(read)
                    val adpcm = SolunaProtocol.adpcmEncode(samples, encodeState)
                    onAudioCaptured(adpcm)
                }
            }
        }, "soluna-capture").apply {
            isDaemon = true
            start()
        }
    }

    fun stopCapture() {
        if (!recording.getAndSet(false)) return
        captureThread?.interrupt()
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    fun playAdpcmPacket(adpcmData: ByteArray) {
        if (!playing.get() || audioTrack == null) return

        // Each ADPCM byte = 2 samples
        val sampleCount = adpcmData.size * 2
        val pcm = SolunaProtocol.adpcmDecode(adpcmData, sampleCount, decodeState)

        // Apply volume
        if (volume < 1.0f) {
            for (i in pcm.indices) {
                pcm[i] = (pcm[i] * volume).toInt().toShort()
            }
        }

        audioTrack?.write(pcm, 0, pcm.size)
    }

    fun setPlaybackVolume(vol: Float) {
        volume = vol.coerceIn(0f, 1f)
        audioTrack?.setStereoVolume(volume, volume)
    }

    fun release() {
        stopCapture()
        stopPlayback()
    }
}
