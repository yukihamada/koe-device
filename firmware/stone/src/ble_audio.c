/*
 * ble_audio.c — Auracast BAP Broadcast Source (nRF5340 / Zephyr BLE Audio)
 *
 * This module implements a BLE Audio LE Auracast transmitter using the
 * Zephyr BAP (Basic Audio Profile) Broadcast Source API.
 *
 * Broadcast parameters:
 *   BIS count  : 2  (stereo left + right)
 *   Codec      : LC3
 *   Sample rate: 48 kHz
 *   Frame dur  : 10 ms  (480 samples / channel / frame)
 *   Bitrate    : 96 kbps per channel
 *   Broadcast name: "Koe"  (visible in Auracast scanner apps)
 *
 * Architecture:
 *   ble_audio_send_frame() → LC3-encode L/R channels separately →
 *   enqueue encoded frames to iso_tx_fifo → ISO TX callback dequeues
 *   and calls bt_bap_broadcast_source_send_synchronize().
 *
 * Thread model:
 *   Audio task thread calls ble_audio_send_frame() at 100 Hz (10 ms frames).
 *   The BT stack calls iso_sent_cb() from a BT cooperative thread.
 *   A k_fifo decouples the two without dynamic allocation:
 *   ISO frames are drawn from a fixed pool (iso_tx_pool).
 *
 * LC3 integration:
 *   Requires CONFIG_LC3=y.  The Zephyr LC3 shim exposes lc3_encode().
 *   Include <bluetooth/audio/lc3.h> (Zephyr ≥ 3.4).
 */

#include "ble_audio.h"

#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gap.h>
#include <zephyr/bluetooth/audio/audio.h>
#include <zephyr/bluetooth/audio/bap.h>
#include <zephyr/bluetooth/audio/bap_lc3_preset.h>
#include <zephyr/bluetooth/audio/lc3.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/net/buf.h>
#include <string.h>

LOG_MODULE_REGISTER(koe_ble_audio, LOG_LEVEL_INF);

/* -------------------------------------------------------------------------
 * LC3 preset: 48 kHz / 10 ms / 96 kbps (Zephyr built-in presets)
 * BT_BAP_LC3_BROADCAST_PRESET_48_4_1:
 *   48 kHz, 10 ms frame, 120 bytes/frame = 96 kbps
 * -------------------------------------------------------------------------
 */
static struct bt_bap_lc3_preset g_preset =
    BT_BAP_LC3_BROADCAST_PRESET_48_4_1(BT_AUDIO_LOCATION_FRONT_LEFT |
                                        BT_AUDIO_LOCATION_FRONT_RIGHT,
                                        BT_AUDIO_CONTEXT_TYPE_MEDIA);

/* -------------------------------------------------------------------------
 * Broadcast source handles
 * -------------------------------------------------------------------------
 */

/* Two subgroups — one per BIS (left, right).
 * In the simplest Auracast layout all BIS share one subgroup; we use
 * one subgroup with two streams here (stereo L+R). */
#define SUBGROUP_COUNT  1
#define BIS_PER_SUBGROUP 2

static struct bt_bap_broadcast_source         *g_source;
static struct bt_bap_broadcast_source_stream   g_streams[BIS_PER_SUBGROUP];
static struct bt_bap_broadcast_source_subgroup g_subgroups[SUBGROUP_COUNT];
static struct bt_bap_broadcast_source_param    g_source_param;
static struct bt_le_ext_adv                   *g_ext_adv;

static bool g_broadcasting;

/* -------------------------------------------------------------------------
 * ISO TX frame pool and FIFO
 *
 * Each frame pool entry holds one encoded LC3 frame for one BIS.
 * We need enough buffers to cover one full 10 ms period for both BIS
 * plus one extra to absorb jitter.
 * -------------------------------------------------------------------------
 */

/* LC3 @ 48 kHz / 10 ms / 96 kbps = 120 bytes per channel */
#define LC3_FRAME_BYTES  120
/* BT_ISO_SDU_BUF_SIZE includes the ISO header overhead */
#define ISO_BUF_SIZE     BT_ISO_SDU_BUF_SIZE(LC3_FRAME_BYTES)

/* Pool: 2 BIS × 3 buffers = 6 (handles one pending + one queued + one spare) */
NET_BUF_POOL_FIXED_DEFINE(iso_tx_pool, 6, ISO_BUF_SIZE, 8, NULL);

/* Per-BIS TX FIFO (one net_buf per 10 ms frame) */
static struct k_fifo iso_tx_fifo[BIS_PER_SUBGROUP];

/* -------------------------------------------------------------------------
 * LC3 encoder state (one encoder per channel)
 * -------------------------------------------------------------------------
 */

static lc3_encoder_t g_enc[BIS_PER_SUBGROUP];
static uint8_t       g_enc_mem[BIS_PER_SUBGROUP][LC3_ENCODER_SIZE(BLE_AUDIO_SAMPLE_RATE, 10000)];

/* -------------------------------------------------------------------------
 * Auracast broadcast name AD data
 * -------------------------------------------------------------------------
 */

/* BT_DATA helper for broadcast name (type 0x30 per Bluetooth SIG spec) */
#define BT_DATA_BROADCAST_NAME  0x30

static const uint8_t broadcast_name[] = "Koe";

static const struct bt_data ext_adv_data[] = {
    BT_DATA(BT_DATA_BROADCAST_NAME,
            broadcast_name, sizeof(broadcast_name) - 1),
};

/* -------------------------------------------------------------------------
 * BT stack ready callback
 * -------------------------------------------------------------------------
 */

static K_SEM_DEFINE(bt_ready_sem, 0, 1);

static void bt_ready_cb(int err)
{
    if (err) {
        LOG_ERR("bt_enable failed: %d", err);
    } else {
        LOG_INF("BT stack ready");
        k_sem_give(&bt_ready_sem);
    }
}

/* -------------------------------------------------------------------------
 * ISO TX sent callback
 *
 * The BT stack calls this from a cooperative BT thread each time it has
 * consumed an ISO SDU.  We use it to drain the per-BIS FIFOs and feed
 * the next frame.
 * -------------------------------------------------------------------------
 */

static void iso_sent_cb(struct bt_bap_stream *stream,
                        struct bt_iso_tx_info *info)
{
    /* Identify which BIS this is */
    int bis_idx = -1;
    for (int i = 0; i < BIS_PER_SUBGROUP; i++) {
        if (&g_streams[i].stream == stream) {
            bis_idx = i;
            break;
        }
    }
    if (bis_idx < 0) {
        return;
    }

    /* Dequeue the next encoded frame for this BIS */
    struct net_buf *buf = k_fifo_get(&iso_tx_fifo[bis_idx], K_NO_WAIT);
    if (!buf) {
        /* No frame ready — underrun; skip this interval */
        LOG_DBG("BIS%d: TX underrun", bis_idx);
        return;
    }

    int err = bt_bap_stream_send(stream, buf, info->seq_num + 1);
    if (err) {
        LOG_WRN("BIS%d: bt_bap_stream_send err %d", bis_idx, err);
        net_buf_unref(buf);
    }
}

static void stream_started_cb(struct bt_bap_stream *stream)
{
    LOG_INF("BIS stream started");
}

static void stream_stopped_cb(struct bt_bap_stream *stream,
                              uint8_t reason)
{
    LOG_INF("BIS stream stopped, reason 0x%02x", reason);
}

static const struct bt_bap_stream_ops g_stream_ops = {
    .sent    = iso_sent_cb,
    .started = stream_started_cb,
    .stopped = stream_stopped_cb,
};

/* -------------------------------------------------------------------------
 * ble_audio_init
 * -------------------------------------------------------------------------
 */

int ble_audio_init(void)
{
    int err;

    /* Enable BT stack */
    err = bt_enable(bt_ready_cb);
    if (err) {
        LOG_ERR("bt_enable: %d", err);
        return err;
    }

    /* Block until BT is ready (bt_ready_cb fires) */
    err = k_sem_take(&bt_ready_sem, K_SECONDS(5));
    if (err) {
        LOG_ERR("BT ready timeout");
        return -ETIMEDOUT;
    }

    /* Initialise TX FIFOs */
    for (int i = 0; i < BIS_PER_SUBGROUP; i++) {
        k_fifo_init(&iso_tx_fifo[i]);
    }

    /* Initialise LC3 encoders (48 kHz, 10 ms frame, one per channel) */
    for (int i = 0; i < BIS_PER_SUBGROUP; i++) {
        g_enc[i] = lc3_setup_encoder(10000,          /* frame duration µs */
                                     BLE_AUDIO_SAMPLE_RATE,
                                     0,              /* hrmode off */
                                     g_enc_mem[i]);
        if (g_enc[i] == NULL) {
            LOG_ERR("lc3_setup_encoder[%d] failed", i);
            return -ENOMEM;
        }
    }

    /* Configure streams */
    for (int i = 0; i < BIS_PER_SUBGROUP; i++) {
        bt_bap_stream_cb_register(&g_streams[i].stream, &g_stream_ops);
    }

    /* Configure subgroup: one subgroup, two streams (L+R) */
    g_subgroups[0].params_count = BIS_PER_SUBGROUP;
    g_subgroups[0].params       = (struct bt_bap_broadcast_source_stream_param[BIS_PER_SUBGROUP]) {
        [0] = { .stream = &g_streams[0], .data_count = 0 },
        [1] = { .stream = &g_streams[1], .data_count = 0 },
    };
    g_subgroups[0].codec_cfg    = &g_preset.codec_cfg;

    /* Configure broadcast source */
    g_source_param.params_count  = SUBGROUP_COUNT;
    g_source_param.params        = g_subgroups;
    g_source_param.qos           = &g_preset.qos;
    g_source_param.packing       = BT_ISO_PACKING_SEQUENTIAL;
    g_source_param.encryption    = false;

    err = bt_bap_broadcast_source_create(&g_source_param, &g_source);
    if (err) {
        LOG_ERR("bt_bap_broadcast_source_create: %d", err);
        return err;
    }

    LOG_INF("ble_audio_init OK (LC3 48kHz/10ms/96kbps, 2×BIS)");
    return 0;
}

/* -------------------------------------------------------------------------
 * ble_audio_start
 * -------------------------------------------------------------------------
 */

int ble_audio_start(void)
{
    int err;

    if (g_broadcasting) {
        return 0;
    }

    /* Create extended advertiser */
    struct bt_le_adv_param adv_param =
        BT_LE_ADV_PARAM_INIT(BT_LE_ADV_OPT_EXT_ADV,
                             BT_GAP_ADV_FAST_INT_MIN_2,
                             BT_GAP_ADV_FAST_INT_MAX_2,
                             NULL);

    err = bt_le_ext_adv_create(&adv_param, NULL, &g_ext_adv);
    if (err) {
        LOG_ERR("bt_le_ext_adv_create: %d", err);
        return err;
    }

    /* Set broadcast name in extended advertising data */
    err = bt_le_ext_adv_set_data(g_ext_adv,
                                 ext_adv_data, ARRAY_SIZE(ext_adv_data),
                                 NULL, 0);
    if (err) {
        LOG_ERR("bt_le_ext_adv_set_data: %d", err);
        return err;
    }

    /* Attach broadcast source to the extended advertiser */
    err = bt_bap_broadcast_source_start(g_source, g_ext_adv);
    if (err) {
        LOG_ERR("bt_bap_broadcast_source_start: %d", err);
        return err;
    }

    /* Begin advertising */
    err = bt_le_ext_adv_start(g_ext_adv, BT_LE_EXT_ADV_START_DEFAULT);
    if (err) {
        LOG_ERR("bt_le_ext_adv_start: %d", err);
        return err;
    }

    g_broadcasting = true;
    LOG_INF("Auracast broadcast started — name=\"Koe\"");
    return 0;
}

/* -------------------------------------------------------------------------
 * ble_audio_stop
 * -------------------------------------------------------------------------
 */

int ble_audio_stop(void)
{
    int err;

    if (!g_broadcasting) {
        return 0;
    }

    err = bt_bap_broadcast_source_stop(g_source);
    if (err) {
        LOG_WRN("bt_bap_broadcast_source_stop: %d", err);
    }

    err = bt_le_ext_adv_stop(g_ext_adv);
    if (err) {
        LOG_WRN("bt_le_ext_adv_stop: %d", err);
    }

    err = bt_le_ext_adv_delete(g_ext_adv);
    if (err) {
        LOG_WRN("bt_le_ext_adv_delete: %d", err);
    }

    g_ext_adv      = NULL;
    g_broadcasting = false;

    /* Drain any pending frames from TX FIFOs */
    for (int i = 0; i < BIS_PER_SUBGROUP; i++) {
        struct net_buf *buf;
        while ((buf = k_fifo_get(&iso_tx_fifo[i], K_NO_WAIT)) != NULL) {
            net_buf_unref(buf);
        }
    }

    LOG_INF("Auracast broadcast stopped");
    return 0;
}

/* -------------------------------------------------------------------------
 * ble_audio_send_frame
 * -------------------------------------------------------------------------
 */

int ble_audio_send_frame(const int16_t *pcm, size_t samples)
{
    if (!g_broadcasting) {
        return -EAGAIN;
    }

    /* Expect exactly BLE_AUDIO_FRAME_SAMPLES * 2 samples (stereo interleaved) */
    if (samples != (size_t)(BLE_AUDIO_FRAME_SAMPLES * 2)) {
        LOG_WRN("send_frame: unexpected sample count %zu", samples);
        return -EINVAL;
    }

    /* De-interleave stereo PCM into per-channel buffers on the stack.
     * Stack usage: 480 × 2 × 2 = 1920 bytes — acceptable on 8 kB stack. */
    int16_t pcm_ch[BIS_PER_SUBGROUP][BLE_AUDIO_FRAME_SAMPLES];
    for (int s = 0; s < BLE_AUDIO_FRAME_SAMPLES; s++) {
        pcm_ch[0][s] = pcm[s * 2 + 0]; /* Left */
        pcm_ch[1][s] = pcm[s * 2 + 1]; /* Right */
    }

    /* Encode each channel and enqueue */
    for (int ch = 0; ch < BIS_PER_SUBGROUP; ch++) {
        struct net_buf *buf = net_buf_alloc(&iso_tx_pool, K_NO_WAIT);
        if (!buf) {
            LOG_WRN("ISO TX pool exhausted (ch %d)", ch);
            return -ENOMEM;
        }

        /* Reserve ISO header space */
        net_buf_reserve(buf, BT_ISO_CHAN_SEND_RESERVE);

        /* Encode LC3 directly into the buffer tail area */
        uint8_t *frame_data = net_buf_add(buf, LC3_FRAME_BYTES);
        int lc3_err = lc3_encode(g_enc[ch],
                                 LC3_PCM_FORMAT_S16,
                                 pcm_ch[ch],
                                 1,               /* stride = 1 (mono channel) */
                                 LC3_FRAME_BYTES,
                                 frame_data);
        if (lc3_err) {
            LOG_WRN("lc3_encode ch%d err %d", ch, lc3_err);
            net_buf_unref(buf);
            continue;
        }

        k_fifo_put(&iso_tx_fifo[ch], buf);
    }

    return 0;
}

/* -------------------------------------------------------------------------
 * ble_audio_is_broadcasting
 * -------------------------------------------------------------------------
 */

bool ble_audio_is_broadcasting(void)
{
    return g_broadcasting;
}
