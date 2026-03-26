/// ウェイクワード検出 — ダブル拍手 (600ms以内に2回)
///
/// 使い方:
///   拍手検出時に `on_clap(now_ms)` を呼ぶ。
///   true が返ったらウェイクワード発動。
use std::sync::atomic::{AtomicU32, Ordering};

static LAST_CLAP_MS: AtomicU32 = AtomicU32::new(0);

/// 最短拍手間隔 (ms) — これ未満は同一拍手の連続フレームとして無視
const MIN_GAP_MS: u32 = 80;
/// ダブル拍手の最大間隔 (ms)
const DOUBLE_WINDOW_MS: u32 = 600;

/// 拍手1回を記録。ダブル拍手なら true を返す。
pub fn on_clap(now_ms: u32) -> bool {
    let last = LAST_CLAP_MS.load(Ordering::Relaxed);
    let gap = now_ms.wrapping_sub(last);

    // 同一拍手の連続フレームは無視
    if gap < MIN_GAP_MS {
        return false;
    }

    LAST_CLAP_MS.store(now_ms, Ordering::Relaxed);

    // 前回の拍手から DOUBLE_WINDOW_MS 以内 → ダブル拍手!
    last != 0 && gap <= DOUBLE_WINDOW_MS
}

/// タイマーリセット (誤検出後などに呼ぶ)
pub fn reset() {
    LAST_CLAP_MS.store(0, Ordering::Relaxed);
}
