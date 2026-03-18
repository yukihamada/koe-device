use std::thread;
use std::time::Duration;

use super::{get_state, DeviceState};

pub fn run_led_task() {
    let mut brightness: u8 = 0;
    let mut rising = true;
    let mut blink_on = true;

    loop {
        let current = get_state();

        if rising {
            brightness = brightness.saturating_add(8);
            if brightness >= 248 { rising = false; }
        } else {
            brightness = brightness.saturating_sub(8);
            if brightness <= 8 { rising = true; }
        }

        let _color: [u8; 3] = match current {
            DeviceState::Booting => [brightness, brightness, brightness], // white pulse
            DeviceState::Connecting => [0, 0, brightness],               // blue pulse
            DeviceState::Listening => [30, 0, 0],                        // dim green
            DeviceState::Processing => [0, brightness / 2, brightness],  // purple pulse
            DeviceState::Speaking => [128, 128, 0],                      // cyan solid
            DeviceState::Error => {
                blink_on = !blink_on;
                if blink_on { [0, 255, 0] } else { [0, 0, 0] }          // red blink
            }
            DeviceState::Syncing => {
                // Soluna: オレンジパルス (ピア同期中)
                [brightness, brightness / 3, 0]
            }
        };

        // TODO: RMT write _color to WS2812B GPIO16

        thread::sleep(Duration::from_millis(50));
    }
}
