/*
 * led.h — WS2812B single-LED control for Koe Stone (nRF5340, GPIO2)
 *
 * The Stone has one WS2812B RGB LED on the top face.
 * Colour palette: Violet (R:80, G:0, B:140) matches Koe brand.
 *
 * States:
 *   Ready       — slow violet sine-wave pulse (2 s period)
 *   Broadcasting — solid violet
 *   Tap flash   — 200 ms white burst
 */

#ifndef KOE_STONE_LED_H
#define KOE_STONE_LED_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialise WS2812B GPIO and start the LED background thread.
 *
 * Spawns a low-priority Zephyr thread that drives the LED state machine.
 * Call once from main before ble_audio_init().
 *
 * @return 0 on success, negative errno on failure.
 */
int led_init(void);

/**
 * @brief Switch to "Ready" state: slow violet pulse (2 s period).
 *
 * Safe to call from any thread.
 */
void led_set_ready(void);

/**
 * @brief Switch to "Broadcasting" state: solid violet.
 *
 * Safe to call from any thread.
 */
void led_set_broadcasting(void);

/**
 * @brief Trigger a 200 ms white flash ("Tap" feedback).
 *
 * After 200 ms the LED automatically returns to the previous state.
 * Safe to call from any thread.
 */
void led_set_tap_flash(void);

#ifdef __cplusplus
}
#endif

#endif /* KOE_STONE_LED_H */
