/*
 * tap.c — Capacitive top-face tap detection (GPIO5, P0.05)
 *
 * The Stone's top face has a capacitive pad wired to GPIO5 through a
 * touch controller IC (e.g. AT42QT1010) that outputs a logic-high when
 * touched.  A falling-edge interrupt fires when the finger lifts (end of
 * touch), which triggers this driver.
 *
 * Debounce: a k_work_delayable item is (re-)scheduled for 50 ms on every
 * interrupt edge.  The actual callback fires only once the 50 ms window
 * elapses without another edge — identical to the classic switch-debounce
 * pattern.
 *
 * GPIO assignment: GPIO5 = P0.05
 * Pull configuration: internal pull-down; touch IC drives high when active.
 */

#include "tap.h"

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(koe_tap, LOG_LEVEL_INF);

/* GPIO node: alias "tap-gpio" → P0.05 */
#define TAP_GPIO_NODE DT_ALIAS(tap_gpio)

#if DT_NODE_EXISTS(TAP_GPIO_NODE)
static const struct gpio_dt_spec tap_pin = GPIO_DT_SPEC_GET(TAP_GPIO_NODE, gpios);
#else
/* Fallback: use GPIO0 pin 5 directly */
static const struct gpio_dt_spec tap_pin =
    GPIO_DT_SPEC_GET_BY_IDX(DT_NODELABEL(gpio0), gpios, 5);
#endif

/* Debounce interval in milliseconds */
#define TAP_DEBOUNCE_MS 50

/* -------------------------------------------------------------------------
 * Module state
 * -------------------------------------------------------------------------
 */

static struct gpio_callback tap_gpio_cb;
static struct k_work_delayable tap_work;
static tap_callback_t g_tap_cb = NULL;

/* -------------------------------------------------------------------------
 * Work handler — runs in system work queue after debounce period
 * -------------------------------------------------------------------------
 */

static void tap_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    /* Read pin state: we expect it to be low (tap released) for a real tap.
     * If the pin is still high the touch is still ongoing — ignore. */
    int val = gpio_pin_get_dt(&tap_pin);
    if (val < 0) {
        LOG_WRN("tap: gpio_pin_get error %d", val);
        return;
    }

    /* Only fire callback on confirmed touch-end (pin low = released) */
    if (val == 0) {
        LOG_DBG("tap: confirmed");
        if (g_tap_cb != NULL) {
            g_tap_cb();
        }
    }
}

/* -------------------------------------------------------------------------
 * GPIO interrupt handler — fires on every edge, reschedules debounce work
 * -------------------------------------------------------------------------
 */

static void tap_gpio_isr(const struct device *dev, struct gpio_callback *cb,
                         uint32_t pins)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);

    /* (Re-)schedule the debounce handler.  k_work_reschedule cancels any
     * pending execution and restarts the timer. */
    k_work_reschedule(&tap_work, K_MSEC(TAP_DEBOUNCE_MS));
}

/* -------------------------------------------------------------------------
 * Public API
 * -------------------------------------------------------------------------
 */

int tap_init(tap_callback_t cb)
{
    int ret;

    if (cb == NULL) {
        LOG_ERR("tap_init: callback is NULL");
        return -EINVAL;
    }

    g_tap_cb = cb;

    if (!device_is_ready(tap_pin.port)) {
        LOG_ERR("tap: GPIO port not ready");
        return -ENODEV;
    }

    /* Configure as input with pull-down; touch IC drives high when touched. */
    ret = gpio_pin_configure_dt(&tap_pin, GPIO_INPUT | GPIO_PULL_DOWN);
    if (ret < 0) {
        LOG_ERR("tap: gpio_pin_configure failed: %d", ret);
        return ret;
    }

    /* Detect both edges so we can debounce on the falling edge (release). */
    ret = gpio_pin_interrupt_configure_dt(&tap_pin, GPIO_INT_EDGE_BOTH);
    if (ret < 0) {
        LOG_ERR("tap: gpio_pin_interrupt_configure failed: %d", ret);
        return ret;
    }

    /* Initialise the delayable work item */
    k_work_init_delayable(&tap_work, tap_work_handler);

    /* Register the ISR */
    gpio_init_callback(&tap_gpio_cb, tap_gpio_isr, BIT(tap_pin.pin));
    ret = gpio_add_callback(tap_pin.port, &tap_gpio_cb);
    if (ret < 0) {
        LOG_ERR("tap: gpio_add_callback failed: %d", ret);
        return ret;
    }

    LOG_INF("tap init OK (GPIO P0.%02d, debounce %d ms)",
            tap_pin.pin, TAP_DEBOUNCE_MS);
    return 0;
}
