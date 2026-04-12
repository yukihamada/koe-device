/*
 * main.c — Koe Stone firmware entry point (nRF5340 / Zephyr RTOS)
 *
 * The Stone is a $1995 premium CNC aluminium wireless speaker.
 * It broadcasts music to the room over Auracast (BLE Audio LE) so guests'
 * earphones can tune in without pairing.
 *
 * Task layout:
 *   led_task   — background thread (spawned by led_init)
 *   i2s_task   — reads I2S RX from line-in DAC, feeds ble_audio_send_frame()
 *   main thread — initialises everything, then becomes i2s_task
 *
 * NVS layout (namespace "koe"):
 *   "serial"   — device serial string, e.g. "KOE-001" (default)
 *
 * GPIO assignments:
 *   I2S_BCLK  : GPIO26  (P0.26)
 *   I2S_LRCLK : GPIO27  (P0.27)
 *   I2S_DOUT  : GPIO25  (P0.25)  — audio amplifier input (TX)
 *   TAP       : GPIO5   (P0.05)  — capacitive top-face touch
 *   LED       : GPIO2   (P0.02)  — WS2812B single pixel
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2s.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/fs/nvs.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/reboot.h>
#include <string.h>
#include <stdio.h>

#include "ble_audio.h"
#include "led.h"
#include "tap.h"

LOG_MODULE_REGISTER(koe_stone, LOG_LEVEL_INF);

/* -------------------------------------------------------------------------
 * Firmware version — keep in sync with CMakeLists.txt project VERSION
 * -------------------------------------------------------------------------
 */
#define FIRMWARE_VERSION "0.3.1"

/* -------------------------------------------------------------------------
 * NVS configuration
 *
 * The NVS partition is typically the last sector(s) of internal flash.
 * FIXED_PARTITION_ID(storage_partition) resolves to the partition labelled
 * "storage" in the board devicetree (nrf5340dk has one by default).
 * -------------------------------------------------------------------------
 */
#define NVS_PARTITION          storage_partition
#define NVS_PARTITION_DEVICE   FIXED_PARTITION_DEVICE(NVS_PARTITION)
#define NVS_PARTITION_OFFSET   FIXED_PARTITION_OFFSET(NVS_PARTITION)

/* NVS key IDs — must be non-zero, unique within the namespace */
#define NVS_KEY_SERIAL  1u

#define SERIAL_MAX_LEN  32
#define DEFAULT_SERIAL  "KOE-001"

/* -------------------------------------------------------------------------
 * I2S configuration
 *
 * We receive stereo audio from the on-board audio CODEC / ADC over I2S
 * (Stone uses a CS4344 or similar DAC; the nRF5340 drives I2S as master).
 *
 *   Sample rate : 48 kHz  (matches LC3 encoder input)
 *   Bit depth   : 16-bit
 *   Channels    : 2 (stereo interleaved)
 *   Frame size  : BLE_AUDIO_FRAME_SAMPLES * 2 channels * 2 bytes = 1920 bytes
 *
 * The I2S driver in Zephyr operates as a TX master for speaker output.
 * We write PCM to the TX queue; the DMA feeds the amplifier.
 *
 * Note: on the Stone PCB the nRF5340 drives the I2S bus as master and the
 * source audio arrives from a separate Bluetooth LE sink (e.g. phone) or
 * from a USB audio bridge.  For this firmware we use a sine-wave test tone
 * generator to demonstrate the full pipeline; swap in real audio input when
 * the PCB delivers I2S RX from the CODEC.
 * -------------------------------------------------------------------------
 */
#define I2S_SAMPLE_RATE     BLE_AUDIO_SAMPLE_RATE          /* 48000 Hz */
#define I2S_CHANNELS        2                              /* stereo */
#define I2S_WORD_SIZE       16                             /* bits */
#define I2S_FRAME_SAMPLES   BLE_AUDIO_FRAME_SAMPLES        /* 480 samples/ch */
/* Bytes per I2S TX buffer: samples × channels × bytes/sample */
#define I2S_BUF_BYTES       (I2S_FRAME_SAMPLES * I2S_CHANNELS * (I2S_WORD_SIZE / 8))
/* Number of I2S TX buffers to keep in the queue (double-buffer) */
#define I2S_NUM_BUFS        2

/* I2S device — devicetree node "i2s0" or board alias "i2s-out" */
#if DT_NODE_EXISTS(DT_ALIAS(i2s_out))
#define I2S_NODE DT_ALIAS(i2s_out)
#else
#define I2S_NODE DT_NODELABEL(i2s0)
#endif

/* -------------------------------------------------------------------------
 * Broadcast toggle state
 * -------------------------------------------------------------------------
 */
static volatile bool g_broadcast_active;

/* -------------------------------------------------------------------------
 * Tap callback — called from the tap work queue thread
 * -------------------------------------------------------------------------
 */
static void on_tap(void)
{
    LOG_INF("tap: toggling broadcast");
    led_set_tap_flash();

    if (g_broadcast_active) {
        int err = ble_audio_stop();
        if (err) {
            LOG_WRN("ble_audio_stop: %d", err);
        } else {
            g_broadcast_active = false;
            LOG_INF("Auracast stopped");
        }
        led_set_ready();
    } else {
        int err = ble_audio_start();
        if (err) {
            LOG_WRN("ble_audio_start: %d", err);
        } else {
            g_broadcast_active = true;
            LOG_INF("Auracast started");
        }
        led_set_broadcasting();
    }
}

/* -------------------------------------------------------------------------
 * NVS helpers
 * -------------------------------------------------------------------------
 */

static struct nvs_fs g_nvs;

static int nvs_init_fs(void)
{
    int err;
    const struct device *flash_dev = NVS_PARTITION_DEVICE;

    if (!device_is_ready(flash_dev)) {
        LOG_ERR("NVS flash device not ready");
        return -ENODEV;
    }

    g_nvs.flash_device = flash_dev;
    g_nvs.offset       = NVS_PARTITION_OFFSET;
    g_nvs.sector_size  = 4096; /* nRF5340 internal flash page size */
    g_nvs.sector_count = CONFIG_NVS_SECTOR_COUNT;

    err = nvs_mount(&g_nvs);
    if (err) {
        LOG_ERR("nvs_mount: %d", err);
        return err;
    }

    return 0;
}

/*
 * nvs_read_serial — read device serial from NVS.
 *
 * Writes a NUL-terminated string into buf (max len-1 chars + NUL).
 * Falls back to DEFAULT_SERIAL if the key is absent or truncated.
 */
static void nvs_read_serial(char *buf, size_t len)
{
    ssize_t rc = nvs_read(&g_nvs, NVS_KEY_SERIAL, buf, len - 1);
    if (rc <= 0) {
        /* Key not found or read error — use default */
        strncpy(buf, DEFAULT_SERIAL, len - 1);
        buf[len - 1] = '\0';
        return;
    }
    buf[rc] = '\0'; /* ensure NUL termination */
}

/* -------------------------------------------------------------------------
 * Test-tone generator (48 kHz, 440 Hz, -20 dBFS)
 *
 * Used to verify the I2S → LC3 → BLE pipeline end-to-end.
 * Replace with real audio capture when hardware delivers I2S RX audio.
 * -------------------------------------------------------------------------
 */
#include <math.h>

#define TONE_FREQ_HZ    440.0f
#define TONE_AMPLITUDE  (32767 * 0.1f) /* -20 dBFS ≈ 10% of full scale */

/* Phase accumulator — persists across successive 10 ms frames */
static float g_tone_phase;

/*
 * generate_test_tone — fill buf with one stereo 10 ms frame of 440 Hz sine.
 *
 * buf must point to I2S_FRAME_SAMPLES * 2 int16_t elements.
 */
static void generate_test_tone(int16_t *buf)
{
    const float phase_inc = 2.0f * M_PI * TONE_FREQ_HZ / (float)I2S_SAMPLE_RATE;
    for (int i = 0; i < I2S_FRAME_SAMPLES; i++) {
        int16_t sample = (int16_t)(sinf(g_tone_phase) * TONE_AMPLITUDE);
        buf[i * 2 + 0] = sample; /* Left */
        buf[i * 2 + 1] = sample; /* Right */
        g_tone_phase += phase_inc;
        if (g_tone_phase >= 2.0f * M_PI) {
            g_tone_phase -= 2.0f * M_PI;
        }
    }
}

/* -------------------------------------------------------------------------
 * I2S TX task
 *
 * Runs as the main thread after initialisation.
 * Feeds the I2S TX FIFO from a test-tone generator (or future audio source)
 * and simultaneously calls ble_audio_send_frame() to encode & broadcast.
 * -------------------------------------------------------------------------
 */

/* Static PCM scratch buffer — one stereo frame */
static int16_t g_pcm_buf[I2S_FRAME_SAMPLES * I2S_CHANNELS];

/*
 * Static I2S TX memory blocks.
 * Zephyr I2S uses a memory-slab for zero-copy TX; we define two blocks.
 */
static char __aligned(4) i2s_tx_mem[I2S_NUM_BUFS][I2S_BUF_BYTES];
K_MEM_SLAB_DEFINE(i2s_tx_slab, I2S_BUF_BYTES, I2S_NUM_BUFS, 4);

static void run_audio_loop(const struct device *i2s_dev)
{
    int err;

    /* Configure I2S TX */
    struct i2s_config cfg = {
        .word_size   = I2S_WORD_SIZE,
        .channels    = I2S_CHANNELS,
        .format      = I2S_FMT_DATA_FORMAT_I2S,
        .options     = I2S_OPT_BIT_CLK_MASTER | I2S_OPT_FRAME_CLK_MASTER,
        .frame_clk_freq = I2S_SAMPLE_RATE,
        .mem_slab    = &i2s_tx_slab,
        .block_size  = I2S_BUF_BYTES,
        .timeout     = SYS_FOREVER_MS,
    };

    err = i2s_configure(i2s_dev, I2S_DIR_TX, &cfg);
    if (err) {
        LOG_ERR("i2s_configure TX: %d", err);
        return;
    }

    /* Pre-fill the I2S TX queue with two silent frames to prime the DMA */
    for (int b = 0; b < I2S_NUM_BUFS; b++) {
        void *buf_ptr = i2s_tx_mem[b];
        memset(buf_ptr, 0, I2S_BUF_BYTES);
        err = i2s_write(i2s_dev, buf_ptr, I2S_BUF_BYTES);
        if (err) {
            LOG_ERR("i2s_write prime: %d", err);
            return;
        }
    }

    err = i2s_trigger(i2s_dev, I2S_DIR_TX, I2S_TRIGGER_START);
    if (err) {
        LOG_ERR("i2s_trigger START: %d", err);
        return;
    }

    LOG_INF("I2S TX running at %d Hz, %d-bit stereo", I2S_SAMPLE_RATE, I2S_WORD_SIZE);

    /* ---- Main audio loop: one iteration = one 10 ms frame ---- */
    while (true) {
        /* Generate (or capture) one stereo PCM frame */
        generate_test_tone(g_pcm_buf);

        /* Feed the Auracast encoder regardless of broadcast state;
         * ble_audio_send_frame() returns -EAGAIN when not broadcasting. */
        if (g_broadcast_active) {
            err = ble_audio_send_frame(g_pcm_buf, I2S_FRAME_SAMPLES * I2S_CHANNELS);
            if (err && err != -EAGAIN) {
                LOG_WRN("ble_audio_send_frame: %d", err);
            }
        }

        /* Write the same frame to I2S TX (drives the physical amp output) */
        void *tx_buf = NULL;
        err = k_mem_slab_alloc(&i2s_tx_slab, &tx_buf, K_NO_WAIT);
        if (err) {
            LOG_WRN("i2s slab alloc failed: %d", err);
            /* Keep the I2S pipeline alive with a silent frame */
            tx_buf = i2s_tx_mem[0];
            memset(tx_buf, 0, I2S_BUF_BYTES);
        } else {
            memcpy(tx_buf, g_pcm_buf, I2S_BUF_BYTES);
        }

        err = i2s_write(i2s_dev, tx_buf, I2S_BUF_BYTES);
        if (err == -EIO) {
            /* FIFO overrun — restart the I2S TX */
            LOG_WRN("I2S TX EIO — restarting");
            i2s_trigger(i2s_dev, I2S_DIR_TX, I2S_TRIGGER_DROP);
            k_msleep(10);
            i2s_trigger(i2s_dev, I2S_DIR_TX, I2S_TRIGGER_PREPARE);
            /* Re-fill the queue */
            for (int b = 0; b < I2S_NUM_BUFS; b++) {
                void *p = i2s_tx_mem[b];
                memset(p, 0, I2S_BUF_BYTES);
                i2s_write(i2s_dev, p, I2S_BUF_BYTES);
            }
            i2s_trigger(i2s_dev, I2S_DIR_TX, I2S_TRIGGER_START);
        } else if (err) {
            LOG_WRN("i2s_write: %d", err);
        }

        /* 10 ms pacing — the I2S DMA interrupt will have consumed one frame
         * by the time we loop around */
        k_msleep(10);
    }
}

/* -------------------------------------------------------------------------
 * main
 * -------------------------------------------------------------------------
 */

int main(void)
{
    int err;
    char serial[SERIAL_MAX_LEN];

    LOG_INF("Koe Stone v" FIRMWARE_VERSION " starting");

    /* --- LED --- */
    err = led_init();
    if (err) {
        /* Non-fatal: continue without LED feedback */
        LOG_WRN("led_init: %d", err);
    }
    led_set_ready();

    /* --- NVS --- */
    err = nvs_init_fs();
    if (err) {
        LOG_WRN("NVS init failed (%d), using default serial", err);
        strncpy(serial, DEFAULT_SERIAL, sizeof(serial) - 1);
        serial[sizeof(serial) - 1] = '\0';
    } else {
        nvs_read_serial(serial, sizeof(serial));
    }
    LOG_INF("device serial: %s", serial);

    /* --- BLE Audio (Auracast) --- */
    err = ble_audio_init();
    if (err) {
        LOG_ERR("ble_audio_init: %d — rebooting", err);
        k_msleep(1000);
        sys_reboot(SYS_REBOOT_WARM);
        return -1;
    }

    /* --- Tap detector --- */
    err = tap_init(on_tap);
    if (err) {
        LOG_WRN("tap_init: %d", err);
    }

    /* --- Auto-start Auracast on boot --- */
    err = ble_audio_start();
    if (err) {
        LOG_WRN("ble_audio_start: %d", err);
        led_set_ready();
        g_broadcast_active = false;
    } else {
        g_broadcast_active = true;
        led_set_broadcasting();
        LOG_INF("Auracast broadcast live — scan for \"Koe\"");
    }

    /* --- I2S audio output device --- */
    const struct device *i2s_dev = DEVICE_DT_GET(I2S_NODE);
    if (!device_is_ready(i2s_dev)) {
        LOG_ERR("I2S device not ready — audio output disabled");
        /* Park in idle; Auracast will still work with silence */
        while (true) {
            k_msleep(1000);
        }
    }

    LOG_INF("I2S device ready: %s", i2s_dev->name);

    /* Run the audio loop (never returns) */
    run_audio_loop(i2s_dev);

    /* Should never reach here */
    return 0;
}
