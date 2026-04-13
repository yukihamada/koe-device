/*
 * koe-amp.c — Koe Amp hub daemon (C / PortAudio / libcurl)
 *
 * Onset detection + session management + live audio level streaming.
 * C rewrite of koe-amp.py for zero-dependency, crash-stable operation on Pi.
 *
 * Algorithms match audio.rs and koe-amp.py exactly:
 *   EMA floor:  fast attack (α=0.95), slow release (α=0.9995)
 *   Onset gate: RMS > floor × 10^(8dB/20) ≈ 2.512×, 1.5s refractory
 *   Session end: 5s of continuous silence
 *
 * Thread model:
 *   [PA callback]  — real-time, no I/O; writes level + onset flag atomically
 *   [session_thr]  — 50ms poll; handles HTTP session start/end
 *   [heartbeat_thr]— 5s loop; POSTs device heartbeat
 *   [level_thr]    — 100ms loop; POSTs audio level for live /room display
 *
 * Build:
 *   make
 *
 * Auto-install (compiles, copies binary, enables + starts systemd service):
 *   sudo make install
 *
 * Deps:
 *   libportaudio2 portaudio19-dev libcurl4-openssl-dev
 *
 * Config files (auto-created by setup-pi.sh):
 *   /etc/koe/device_id   e.g. koe-amp-hawaii-01
 *   /etc/koe/room        e.g. main
 *   /etc/koe/server      e.g. https://koe.live
 */

#define _GNU_SOURCE
#include <portaudio.h>
#include <curl/curl.h>
#include <pthread.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <stdatomic.h>
#include <unistd.h>
#include <fcntl.h>

/* ── Constants (must match audio.rs and koe-amp.py) ─────────────── */
#define SAMPLE_RATE        16000
#define FRAME_SAMPLES      512          /* ~32 ms per frame */
#define FLOOR_ATTACK       0.95f
#define FLOOR_RELEASE      0.9995f
#define ONSET_LINEAR       2.512f       /* 10^(8dB/20) */
#define REFRACTORY_SECS    1.5
#define SILENCE_END_SECS   5.0
#define HEARTBEAT_SECS     5.0
#define LEVEL_SECS         0.1          /* 100 ms */
#define UUID_LEN           37

/* ── Config ──────────────────────────────────────────────────────── */
typedef struct {
    char server[256];
    char room[64];
    char device_id[64];
    char pa_device[128];   /* PortAudio device name substring; "" = default */
} Config;

static void cfg_read(char *dst, size_t cap, const char *path, const char *def) {
    FILE *f = fopen(path, "r");
    if (!f) { strncpy(dst, def, cap - 1); dst[cap - 1] = '\0'; return; }
    if (fgets(dst, (int)cap, f)) {
        size_t n = strlen(dst);
        while (n && (dst[n-1] == '\n' || dst[n-1] == '\r')) dst[--n] = '\0';
    } else {
        strncpy(dst, def, cap - 1); dst[cap - 1] = '\0';
    }
    fclose(f);
}

static void config_init(Config *c) {
    cfg_read(c->server,    sizeof c->server,    "/etc/koe/server",    "https://koe.live");
    cfg_read(c->room,      sizeof c->room,      "/etc/koe/room",      "main");
    cfg_read(c->device_id, sizeof c->device_id, "/etc/koe/device_id", "koe-amp-001");
    c->pa_device[0] = '\0';
}

/* ── Utilities ───────────────────────────────────────────────────── */
static double mono_secs(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec * 1e-9;
}

static float rms_f32(const float *buf, int n) {
    float s = 0.0f;
    for (int i = 0; i < n; i++) s += buf[i] * buf[i];
    return sqrtf(s / (float)n);
}

static void uuid4(char *out) {
    uint8_t b[16];
    int fd = open("/dev/urandom", O_RDONLY | O_CLOEXEC);
    if (fd >= 0) { read(fd, b, 16); close(fd); }
    else { srand((unsigned)time(NULL)); for (int i = 0; i < 16; i++) b[i] = (uint8_t)rand(); }
    b[6] = (uint8_t)((b[6] & 0x0f) | 0x40);
    b[8] = (uint8_t)((b[8] & 0x3f) | 0x80);
    snprintf(out, UUID_LEN,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],
        b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]);
}

/* ── Onset Detector ──────────────────────────────────────────────── */
typedef struct {
    float  floor_rms;
    double last_onset_t;
} OnsetDetector;

static void onset_init(OnsetDetector *od) {
    od->floor_rms    = 1e-6f;
    od->last_onset_t = -9999.0;
}

/* Returns 1 on onset, updates EMA floor. Audio thread only. */
static int onset_process(OnsetDetector *od, const float *samples, int n, double t) {
    float rms   = rms_f32(samples, n);
    float alpha = (rms < od->floor_rms) ? FLOOR_ATTACK : FLOOR_RELEASE;
    od->floor_rms = alpha * od->floor_rms + (1.0f - alpha) * rms;

    if (t - od->last_onset_t < REFRACTORY_SECS) return 0;
    if (rms > od->floor_rms * ONSET_LINEAR) { od->last_onset_t = t; return 1; }
    return 0;
}

/* ── Shared state ────────────────────────────────────────────────── */
typedef struct {
    pthread_mutex_t  mu;
    float            level;        /* normalised 0–1, protected by mu */
    int              is_recording; /* protected by mu */

    /* Audio-callback-only fields (no locking) */
    OnsetDetector    detector;
    atomic_int       onset_pending;
    volatile double  last_sound_t;

    /* Session — owned by session thread */
    char             session_id[UUID_LEN];
    double           session_start_t;
    float            rms_acc;
    int              frame_count;

    volatile int     shutdown;
    const Config    *cfg;
} State;

/* ── HTTP (each call is self-contained — safe across threads) ────── */
static size_t curl_sink(void *p, size_t s, size_t n, void *u)
    { (void)p; (void)u; return s * n; }

/* timeout_ms: use 300 for level (fire-and-forget), 2000 for session/heartbeat */
static void http_post_t(const char *url, const char *json, long timeout_ms) {
    CURL *c = curl_easy_init();
    if (!c) return;
    struct curl_slist *h = curl_slist_append(NULL, "Content-Type: application/json");
    curl_easy_setopt(c, CURLOPT_URL,             url);
    curl_easy_setopt(c, CURLOPT_POSTFIELDS,      json);
    curl_easy_setopt(c, CURLOPT_HTTPHEADER,      h);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION,   curl_sink);
    curl_easy_setopt(c, CURLOPT_TIMEOUT_MS,      (long)timeout_ms);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL,        1L);
    curl_easy_perform(c);
    curl_slist_free_all(h);
    curl_easy_cleanup(c);
}
static void http_post(const char *url, const char *json)
    { http_post_t(url, json, 2000); }

/* ── Session management (session thread only) ────────────────────── */
static void session_start(State *st) {
    uuid4(st->session_id);
    st->session_start_t = mono_secs();
    st->rms_acc  = 0.0f;
    st->frame_count = 0;

    pthread_mutex_lock(&st->mu);
    st->is_recording = 1;
    pthread_mutex_unlock(&st->mu);

    char url[384], body[256];
    snprintf(url,  sizeof url,
        "%s/api/v1/sessions/%s/start", st->cfg->server, st->session_id);
    snprintf(body, sizeof body,
        "{\"device_id\":\"%s\",\"room\":\"%s\"}", st->cfg->device_id, st->cfg->room);
    http_post(url, body);

    fprintf(stderr, "[koe-amp] ▶  session %s\n", st->session_id);
}

static void session_end(State *st) {
    double dur = mono_secs() - st->session_start_t;
    float  avg = st->frame_count ? st->rms_acc / (float)st->frame_count : 0.0f;

    pthread_mutex_lock(&st->mu);
    st->is_recording = 0;
    pthread_mutex_unlock(&st->mu);

    char url[384], body[256];
    snprintf(url,  sizeof url,
        "%s/api/v1/sessions/%s/end", st->cfg->server, st->session_id);
    snprintf(body, sizeof body,
        "{\"device_id\":\"%s\",\"room\":\"%s\",\"duration_secs\":%.1f,\"avg_rms\":%.4f}",
        st->cfg->device_id, st->cfg->room, dur, avg);
    http_post(url, body);

    fprintf(stderr, "[koe-amp] ■  session %s  %.0fs\n", st->session_id, dur);
    st->session_id[0] = '\0';
}

/* ── Threads ─────────────────────────────────────────────────────── */

static void *thr_session(void *arg) {
    State *st       = (State *)arg;
    int    active   = 0;

    while (!st->shutdown) {
        usleep(50000); /* 50ms poll */

        if (!active) {
            if (atomic_exchange(&st->onset_pending, 0)) {
                session_start(st);
                active = 1;
            }
        } else {
            double silence = mono_secs() - st->last_sound_t;
            if (silence > SILENCE_END_SECS) {
                session_end(st);
                active = 0;
            }
        }
    }
    if (active) session_end(st);
    return NULL;
}

static void *thr_heartbeat(void *arg) {
    State *st = (State *)arg;
    char   url[384];
    snprintf(url, sizeof url, "%s/api/v1/device/heartbeat", st->cfg->server);

    while (!st->shutdown) {
        pthread_mutex_lock(&st->mu);
        float lv = st->level;
        int   rc = st->is_recording;
        pthread_mutex_unlock(&st->mu);

        char body[256];
        snprintf(body, sizeof body,
            "{\"device_id\":\"%s\",\"room\":\"%s\",\"audio_level\":%.3f,\"is_recording\":%s}",
            st->cfg->device_id, st->cfg->room, lv, rc ? "true" : "false");
        http_post(url, body);

        for (int i = 0; i < (int)(HEARTBEAT_SECS / 0.5) && !st->shutdown; i++)
            usleep(500000);
    }
    return NULL;
}

static void *thr_level(void *arg) {
    State *st = (State *)arg;
    char   url[384];
    snprintf(url, sizeof url, "%s/api/v1/room/audio-level", st->cfg->server);

    while (!st->shutdown) {
        double tick = mono_secs();

        pthread_mutex_lock(&st->mu);
        float lv = st->level;
        int   rc = st->is_recording;
        pthread_mutex_unlock(&st->mu);

        char body[256];
        snprintf(body, sizeof body,
            "{\"device_id\":\"%s\",\"room\":\"%s\",\"level\":%.3f,\"is_recording\":%s}",
            st->cfg->device_id, st->cfg->room, lv, rc ? "true" : "false");

        /* Short timeout: waveform is cosmetic; a dropped frame is fine */
        http_post_t(url, body, 300);

        /* Sleep for the remainder of the 100ms window (never negative) */
        double elapsed = mono_secs() - tick;
        double remaining = LEVEL_SECS - elapsed;
        if (remaining > 0.005) usleep((useconds_t)(remaining * 1e6));
    }
    return NULL;
}

/* ── PortAudio callback (real-time — NO blocking I/O) ───────────── */
static int pa_cb(
    const void *in, void *out,
    unsigned long frames,
    const PaStreamCallbackTimeInfo *ti,
    PaStreamCallbackFlags flags,
    void *udata)
{
    (void)out; (void)ti; (void)flags;
    State       *st      = (State *)udata;
    const float *samples = (const float *)in;
    if (!samples) return paContinue;

    double t   = mono_secs();
    float  rms = rms_f32(samples, (int)frames);

    /* Scale to perceptual 0–1 (PortAudio float32 is already -1..+1) */
    float lv = fminf(1.0f, rms * 8.0f);

    /* Try-lock: skip if contested rather than stall the audio thread */
    if (pthread_mutex_trylock(&st->mu) == 0) {
        st->level = lv;
        pthread_mutex_unlock(&st->mu);
    }

    /* Onset detection (pure math — safe in RT context) */
    if (onset_process(&st->detector, samples, (int)frames, t))
        atomic_store(&st->onset_pending, 1);

    /* Feed silence timer + session RMS accumulator */
    if (rms > st->detector.floor_rms * 0.5f) st->last_sound_t = t;
    if (st->is_recording) { st->rms_acc += rms; st->frame_count++; }

    return paContinue;
}

/* ── Signal handler ──────────────────────────────────────────────── */
static volatile State *g_st;
static void on_signal(int s) { (void)s; if (g_st) ((State *)g_st)->shutdown = 1; }

/* ── PortAudio device selection ──────────────────────────────────── */
static PaDeviceIndex pick_device(const char *substr) {
    if (!substr || !*substr) return Pa_GetDefaultInputDevice();
    int n = Pa_GetDeviceCount();
    for (int i = 0; i < n; i++) {
        const PaDeviceInfo *d = Pa_GetDeviceInfo(i);
        if (d && d->maxInputChannels > 0 && strstr(d->name, substr)) {
            fprintf(stderr, "[koe-amp] device [%d] %s\n", i, d->name);
            return (PaDeviceIndex)i;
        }
    }
    fprintf(stderr, "[koe-amp] device '%s' not found — using default\n", substr);
    return Pa_GetDefaultInputDevice();
}

/* ── main ────────────────────────────────────────────────────────── */
int main(int argc, char **argv) {
    Config cfg;
    config_init(&cfg);

    for (int i = 1; i < argc - 1; i++) {
        if      (!strcmp(argv[i], "--server"))    { strncpy(cfg.server,    argv[++i], sizeof cfg.server    - 1); }
        else if (!strcmp(argv[i], "--room"))       { strncpy(cfg.room,      argv[++i], sizeof cfg.room      - 1); }
        else if (!strcmp(argv[i], "--device-id"))  { strncpy(cfg.device_id, argv[++i], sizeof cfg.device_id - 1); }
        else if (!strcmp(argv[i], "--device"))     { strncpy(cfg.pa_device, argv[++i], sizeof cfg.pa_device - 1); }
    }

    fprintf(stderr, "[koe-amp] server=%s  room=%s  id=%s\n",
            cfg.server, cfg.room, cfg.device_id);

    curl_global_init(CURL_GLOBAL_ALL); /* before any threads */

    State st = {0};
    pthread_mutex_init(&st.mu, NULL);
    atomic_init(&st.onset_pending, 0);
    onset_init(&st.detector);
    st.last_sound_t = mono_secs();
    st.cfg = &cfg;
    g_st   = &st;

    signal(SIGINT,  on_signal);
    signal(SIGTERM, on_signal);

    pthread_t t_ses, t_hb, t_lv;
    pthread_create(&t_ses, NULL, thr_session,   &st);
    pthread_create(&t_hb,  NULL, thr_heartbeat, &st);
    pthread_create(&t_lv,  NULL, thr_level,     &st);

    PaError pa = Pa_Initialize();
    if (pa != paNoError) {
        fprintf(stderr, "[koe-amp] Pa_Initialize: %s\n", Pa_GetErrorText(pa));
        return 1;
    }

    PaDeviceIndex dev = pick_device(cfg.pa_device);
    if (dev == paNoDevice) {
        fprintf(stderr, "[koe-amp] no input device\n");
        Pa_Terminate(); return 1;
    }

    PaStreamParameters inp = {
        .device                    = dev,
        .channelCount              = 1,
        .sampleFormat              = paFloat32,
        .suggestedLatency          = Pa_GetDeviceInfo(dev)->defaultLowInputLatency,
        .hostApiSpecificStreamInfo = NULL,
    };

    PaStream *stream;
    pa = Pa_OpenStream(&stream, &inp, NULL, SAMPLE_RATE, FRAME_SAMPLES,
                       paClipOff, pa_cb, &st);
    if (pa != paNoError) {
        fprintf(stderr, "[koe-amp] Pa_OpenStream: %s\n", Pa_GetErrorText(pa));
        Pa_Terminate(); return 1;
    }

    pa = Pa_StartStream(stream);
    if (pa != paNoError) {
        fprintf(stderr, "[koe-amp] Pa_StartStream: %s\n", Pa_GetErrorText(pa));
        Pa_CloseStream(stream); Pa_Terminate(); return 1;
    }

    const PaDeviceInfo *di = Pa_GetDeviceInfo(dev);
    fprintf(stderr, "[koe-amp] listening on \"%s\" @ %d Hz\n",
            di ? di->name : "?", SAMPLE_RATE);

    while (!st.shutdown) usleep(100000);

    fprintf(stderr, "[koe-amp] shutting down…\n");
    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();

    pthread_join(t_ses, NULL);
    pthread_join(t_hb,  NULL);
    pthread_join(t_lv,  NULL);

    pthread_mutex_destroy(&st.mu);
    curl_global_cleanup();
    fprintf(stderr, "[koe-amp] done\n");
    return 0;
}
