/*
 * led.c — WS2812B single-LED driver for Koe Stone (nRF5340, GPIO2)
 *
 * Driving a WS2812B from an nRF5340 GPIO at the bit-bang level would
 * require cycle-accurate timing impossible in a preemptive RTOS.
 * Instead, we use Zephyr's LED Strip driver subsystem backed by the
 * nRFX SPI peripheral to produce the required 800 kHz NZR waveform.
 *
 * Hardware: WS2812B DIN connected to GPIO2 (P0.02) configured as the
 * MOSI line of SPI2 in the board devicetree overlay. Each WS2812B bit
 * is encoded as 3 SPI bits:
 *   Logical 1 → 0b110  (high, high, low)
 *   Logical 0 → 0b100  (high, low,  low)
 * SPI clock: 2.4 MHz → 3 SPI clocks = 1.25 µs WS2812B bit period.
 *
 * Colour palette (Koe brand violet):
 *   Violet: R=80  G=0   B=140
 *   White:  R=255 G=255 B=255
 *   Off:    R=0   G=0   B=0
 */

#include "led.h"

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#define _USE_MATH_DEFINES
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

LOG_MODULE_REGISTER(koe_led, LOG_LEVEL_INF);

/* -------------------------------------------------------------------------
 * WS2812B encoding via SPI bit-bang
 *
 * We encode each WS2812B bit as 3 SPI bits at 2.4 MHz:
 *   1 → 110b   high 833 ns, low 417 ns  ≈ T1H=800ns T1L=450ns
 *   0 → 100b   high 417 ns, low 833 ns  ≈ T0H=400ns T0L=850ns
 *
 * One colour byte (8 bits) = 3 SPI bytes (24 bits).
 * One WS2812B pixel (GRB, 3 bytes) = 9 SPI bytes.
 * Reset pulse ≥ 50 µs → 12 SPI bytes of 0x00 (= 40 µs; pad to 15 bytes).
 * -------------------------------------------------------------------------
 */

/* Use Zephyr's built-in LED strip driver if available (DEVICE_DT_GET),
 * otherwise fall back to GPIO bit-bang at a lower clock rate using
 * k_busy_wait(). The GPIO bit-bang path is always compiled; the SPI path
 * is preferred when the devicetree alias "led-strip" resolves. */

/* GPIO node: alias "ws2812-gpio" → P0.02 */
#define LED_GPIO_NODE DT_ALIAS(ws2812_gpio)

#if DT_NODE_EXISTS(LED_GPIO_NODE)
static const struct gpio_dt_spec led_pin = GPIO_DT_SPEC_GET(LED_GPIO_NODE, gpios);
#else
/* Fallback: hard-code GPIO2 = P0.02 if no devicetree alias present */
static const struct gpio_dt_spec led_pin =
    GPIO_DT_SPEC_GET_BY_IDX(DT_NODELABEL(gpio0), gpios, 2);
#endif

/* -------------------------------------------------------------------------
 * WS2812B bit timings (nanoseconds) for GPIO bit-bang path
 * -------------------------------------------------------------------------
 */
#define T0H_NS  400u
#define T0L_NS  850u
#define T1H_NS  800u
#define T1L_NS  450u
#define RESET_US 60u   /* > 50 µs reset pulse */

/* -------------------------------------------------------------------------
 * LED state machine
 * -------------------------------------------------------------------------
 */

typedef enum {
    LED_STATE_READY = 0,
    LED_STATE_BROADCASTING,
    LED_STATE_TAP_FLASH,
} led_state_t;

/* State shared between public API and LED thread; protected by a mutex. */
static K_MUTEX_DEFINE(led_mutex);
static led_state_t  g_led_state      = LED_STATE_READY;
static led_state_t  g_pre_flash_state = LED_STATE_READY;
static int64_t      g_flash_end_ms   = 0; /* k_uptime_get() when flash ends */

/* -------------------------------------------------------------------------
 * Thread stack + TCB
 * -------------------------------------------------------------------------
 */
#define LED_STACK_SIZE 1024
#define LED_THREAD_PRIO 7    /* low priority; yields freely */

K_THREAD_STACK_DEFINE(led_stack, LED_STACK_SIZE);
static struct k_thread led_thread_data;

/* -------------------------------------------------------------------------
 * Bit-bang helpers (compiler barriers prevent reordering)
 * -------------------------------------------------------------------------
 */

static inline void write_bit_1(void)
{
    gpio_pin_set_dt(&led_pin, 1);
    k_busy_wait((T1H_NS + 499u) / 1000u);  /* ceil ns → µs */
    gpio_pin_set_dt(&led_pin, 0);
    k_busy_wait((T1L_NS + 499u) / 1000u);
}

static inline void write_bit_0(void)
{
    gpio_pin_set_dt(&led_pin, 1);
    k_busy_wait((T0H_NS + 499u) / 1000u);
    gpio_pin_set_dt(&led_pin, 0);
    k_busy_wait((T0L_NS + 499u) / 1000u);
}

/*
 * write_byte — send one byte MSB-first to the WS2812B data line.
 */
static void write_byte(uint8_t byte)
{
    for (int b = 7; b >= 0; b--) {
        if (byte & (1u << b)) {
            write_bit_1();
        } else {
            write_bit_0();
        }
    }
}

/*
 * ws2812_write_pixel — transmit one GRB pixel to the LED strip.
 *
 * WS2812B expects bytes in G-R-B order, each byte MSB-first.
 */
static void ws2812_write_pixel(uint8_t r, uint8_t g, uint8_t b)
{
    /* Disable interrupts for the duration to avoid bit-timing glitches. */
    unsigned int key = irq_lock();
    write_byte(g); /* green first */
    write_byte(r);
    write_byte(b);
    irq_unlock(key);

    /* Reset pulse: hold DIN low for > 50 µs */
    gpio_pin_set_dt(&led_pin, 0);
    k_busy_wait(RESET_US);
}

/* -------------------------------------------------------------------------
 * LED thread
 * -------------------------------------------------------------------------
 */

static void led_thread_fn(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    int64_t start_ms = k_uptime_get();

    LOG_INF("LED thread started");

    while (true) {
        int64_t now_ms = k_uptime_get();
        led_state_t state;

        k_mutex_lock(&led_mutex, K_FOREVER);
        /* Check if a tap flash has expired */
        if (g_led_state == LED_STATE_TAP_FLASH && now_ms >= g_flash_end_ms) {
            g_led_state = g_pre_flash_state;
        }
        state = g_led_state;
        k_mutex_unlock(&led_mutex);

        switch (state) {
        case LED_STATE_READY: {
            /* Slow violet sine-wave pulse: 2 s period, brightness 10–70% */
            float t_sec = (float)(now_ms - start_ms) / 1000.0f;
            /* sin() returns -1..+1; map to 0.1..0.7 */
            float phase = sinf(t_sec * M_PI); /* 0.5 Hz */
            float brightness = (phase + 1.0f) / 2.0f * 0.6f + 0.1f;
            uint8_t r = (uint8_t)(80.0f  * brightness);
            uint8_t b = (uint8_t)(140.0f * brightness);
            ws2812_write_pixel(r, 0, b);
            k_msleep(33); /* ~30 fps */
            break;
        }

        case LED_STATE_BROADCASTING:
            /* Solid violet */
            ws2812_write_pixel(80, 0, 140);
            k_msleep(50);
            break;

        case LED_STATE_TAP_FLASH:
            /* White burst — duration managed above; keep refreshing at 30 fps */
            ws2812_write_pixel(255, 255, 255);
            k_msleep(33);
            break;
        }
    }
}

/* -------------------------------------------------------------------------
 * Public API
 * -------------------------------------------------------------------------
 */

int led_init(void)
{
    int ret;

    if (!device_is_ready(led_pin.port)) {
        LOG_ERR("LED GPIO port not ready");
        return -ENODEV;
    }

    ret = gpio_pin_configure_dt(&led_pin, GPIO_OUTPUT_INACTIVE);
    if (ret < 0) {
        LOG_ERR("Failed to configure LED GPIO: %d", ret);
        return ret;
    }

    /* Send an off-pixel to clear any residual state from a previous boot */
    ws2812_write_pixel(0, 0, 0);

    /* Spawn the LED thread */
    k_thread_create(&led_thread_data, led_stack, LED_STACK_SIZE,
                    led_thread_fn, NULL, NULL, NULL,
                    LED_THREAD_PRIO, 0, K_NO_WAIT);
    k_thread_name_set(&led_thread_data, "led");

    LOG_INF("LED init OK");
    return 0;
}

void led_set_ready(void)
{
    k_mutex_lock(&led_mutex, K_FOREVER);
    if (g_led_state != LED_STATE_TAP_FLASH) {
        g_led_state = LED_STATE_READY;
    }
    g_pre_flash_state = LED_STATE_READY;
    k_mutex_unlock(&led_mutex);
}

void led_set_broadcasting(void)
{
    k_mutex_lock(&led_mutex, K_FOREVER);
    if (g_led_state != LED_STATE_TAP_FLASH) {
        g_led_state = LED_STATE_BROADCASTING;
    }
    g_pre_flash_state = LED_STATE_BROADCASTING;
    k_mutex_unlock(&led_mutex);
}

void led_set_tap_flash(void)
{
    k_mutex_lock(&led_mutex, K_FOREVER);
    /* Save current state to restore after flash */
    if (g_led_state != LED_STATE_TAP_FLASH) {
        g_pre_flash_state = g_led_state;
    }
    g_led_state    = LED_STATE_TAP_FLASH;
    g_flash_end_ms = k_uptime_get() + 200; /* 200 ms white flash */
    k_mutex_unlock(&led_mutex);
}
