/*
 * tap.h — Capacitive top-face tap detection for Koe Stone (GPIO5)
 *
 * The Stone has a capacitive touch pad on its top face wired to GPIO5.
 * A GPIO interrupt fires on the falling edge; a 50 ms software debounce
 * suppresses bounces before invoking the registered callback.
 */

#ifndef KOE_STONE_TAP_H
#define KOE_STONE_TAP_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Callback type invoked on a confirmed tap event.
 *
 * Called from the tap worker thread (not ISR context), so it is safe to
 * call Zephyr APIs that may sleep or yield.
 */
typedef void (*tap_callback_t)(void);

/**
 * @brief Initialise the tap detector and register a callback.
 *
 * Configures GPIO5 as input with interrupt-on-falling-edge and starts
 * the debounce work queue.  Only one callback is supported; a second
 * call to tap_init() replaces the previous callback.
 *
 * @param cb  Function to call on each confirmed tap.  Must not be NULL.
 *
 * @return 0 on success, negative errno on failure.
 */
int tap_init(tap_callback_t cb);

#ifdef __cplusplus
}
#endif

#endif /* KOE_STONE_TAP_H */
