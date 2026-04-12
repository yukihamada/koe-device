/*
 * ble_audio.h — Auracast BAP Broadcast Source API
 *
 * Koe Stone uses BLE Audio LE (Bluetooth 5.4 LE Audio / Auracast).
 * One broadcast source advertises two BIS (stereo) encoded with LC3.
 * Any compatible earphone can tune in without pairing.
 *
 * Thread safety: all public functions are called from a single Zephyr
 * thread (audio task).  ble_audio_send_frame() may be called from an
 * I2S DMA callback; internal ISO TX uses a kernel FIFO to decouple.
 */

#ifndef KOE_STONE_BLE_AUDIO_H
#define KOE_STONE_BLE_AUDIO_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Number of BIS (Broadcast ISO Streams): 2 = stereo. */
#define BLE_AUDIO_BIS_COUNT   2

/** LC3 sampling frequency: 48 kHz. */
#define BLE_AUDIO_SAMPLE_RATE 48000

/** LC3 frame duration: 10 ms → 480 samples per frame per channel. */
#define BLE_AUDIO_FRAME_SAMPLES 480

/** LC3 target bitrate per channel (bits/s). */
#define BLE_AUDIO_BITRATE_BPS 96000

/**
 * @brief Initialise BLE stack and configure the BAP broadcast source.
 *
 * Must be called once before ble_audio_start().
 * Blocks until the BLE stack is ready.
 *
 * @return 0 on success, negative errno on failure.
 */
int ble_audio_init(void);

/**
 * @brief Start the Auracast ISO broadcast.
 *
 * Begins Extended Advertising + Periodic Advertising + ISO broadcast.
 * After this call the broadcast is visible to Auracast scanner apps as
 * "Koe".
 *
 * @return 0 on success, negative errno on failure.
 */
int ble_audio_start(void);

/**
 * @brief Stop the Auracast ISO broadcast.
 *
 * Stops ISO transmission, periodic advertising, and extended advertising.
 *
 * @return 0 on success, negative errno on failure.
 */
int ble_audio_stop(void);

/**
 * @brief Encode one stereo PCM frame to LC3 and enqueue for ISO TX.
 *
 * @param pcm     Interleaved stereo PCM samples (L0,R0,L1,R1,...).
 *                Must contain exactly BLE_AUDIO_FRAME_SAMPLES*2 samples.
 * @param samples Total sample count (= BLE_AUDIO_FRAME_SAMPLES * 2).
 *
 * @return 0 on success, -ENOMEM if ISO TX queue is full.
 */
int ble_audio_send_frame(const int16_t *pcm, size_t samples);

/**
 * @brief Query whether the broadcast is currently active.
 *
 * @return true if broadcasting, false otherwise.
 */
bool ble_audio_is_broadcasting(void);

#ifdef __cplusplus
}
#endif

#endif /* KOE_STONE_BLE_AUDIO_H */
