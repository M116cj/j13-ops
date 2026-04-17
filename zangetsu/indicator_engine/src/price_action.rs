use crate::types::*;

// ============================================================
// Price Action Pattern Detectors — 16 patterns
// All return values in [-1.0, 1.0]: 1.0=bullish, -1.0=bearish, 0.0=none
// ============================================================

#[inline]
fn body(open: f64, close: f64) -> f64 { (close - open).abs() }
#[inline]
fn range(high: f64, low: f64) -> f64 { high - low }
#[inline]
fn upper_wick(open: f64, close: f64, high: f64) -> f64 { high - open.max(close) }
#[inline]
fn lower_wick(open: f64, close: f64, low: f64) -> f64 { open.min(close) - low }
#[inline]
fn is_bullish(open: f64, close: f64) -> bool { close > open }
#[inline]
fn is_bearish(open: f64, close: f64) -> bool { close < open }

/// We derive open from close[i-1] for OHLCV without explicit open.
/// In practice the caller should provide open; here we approximate.
#[inline]
fn open_at(data: &OhlcvData, i: usize) -> f64 {
    if i == 0 { data.close[0] } else { data.close[i - 1] }
}

/// 1. Pin Bar — long wick (>60% of range) with small body
fn pin_bar(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 0..data.len {
        let o = open_at(data, i);
        let r = range(data.high[i], data.low[i]);
        if r <= 0.0 { continue; }
        let lw = lower_wick(o, data.close[i], data.low[i]);
        let uw = upper_wick(o, data.close[i], data.high[i]);
        let b = body(o, data.close[i]);
        if lw / r > 0.6 && b / r < 0.25 {
            values[i] = 1.0; // bullish pin
        } else if uw / r > 0.6 && b / r < 0.25 {
            values[i] = -1.0; // bearish pin
        }
    }
    IndicatorResult { values }
}

/// 2. Engulfing
fn engulfing(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let c = data.close[i];
        let pc = data.close[i - 1];
        // Bullish engulfing: prev bearish, current bullish, body engulfs
        if is_bearish(po, pc) && is_bullish(o, c) && o <= pc && c >= po {
            values[i] = 1.0;
        }
        // Bearish engulfing
        else if is_bullish(po, pc) && is_bearish(o, c) && o >= pc && c <= po {
            values[i] = -1.0;
        }
    }
    IndicatorResult { values }
}

/// 3. Doji — body < 10% of range
fn doji(data: &OhlcvData) -> IndicatorResult {
    let values: Vec<f64> = (0..data.len)
        .map(|i| {
            let o = open_at(data, i);
            let r = range(data.high[i], data.low[i]);
            if r > 0.0 && body(o, data.close[i]) / r < 0.1 { 1.0 } else { 0.0 }
        })
        .collect();
    IndicatorResult { values }
}

/// 4. Hammer — small body at top, lower wick >2x body
fn hammer(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 0..data.len {
        let o = open_at(data, i);
        let b = body(o, data.close[i]);
        let lw = lower_wick(o, data.close[i], data.low[i]);
        let uw = upper_wick(o, data.close[i], data.high[i]);
        let r = range(data.high[i], data.low[i]);
        if r > 0.0 && b > 0.0 && lw > 2.0 * b && uw < b {
            values[i] = 1.0;
        }
    }
    IndicatorResult { values }
}

/// 5. Shooting Star — small body at bottom, upper wick >2x body
fn shooting_star(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 0..data.len {
        let o = open_at(data, i);
        let b = body(o, data.close[i]);
        let uw = upper_wick(o, data.close[i], data.high[i]);
        let lw = lower_wick(o, data.close[i], data.low[i]);
        let r = range(data.high[i], data.low[i]);
        if r > 0.0 && b > 0.0 && uw > 2.0 * b && lw < b {
            values[i] = -1.0;
        }
    }
    IndicatorResult { values }
}

/// 6. Morning Star (3-bar bullish reversal)
fn morning_star(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 2..data.len {
        let o0 = open_at(data, i - 2);
        let o1 = open_at(data, i - 1);
        let o2 = open_at(data, i);
        let r1 = range(data.high[i - 1], data.low[i - 1]);
        let b1 = body(o1, data.close[i - 1]);
        if is_bearish(o0, data.close[i - 2])
            && r1 > 0.0
            && b1 / r1 < 0.3
            && is_bullish(o2, data.close[i])
        {
            values[i] = 1.0;
        }
    }
    IndicatorResult { values }
}

/// 7. Evening Star (3-bar bearish reversal)
fn evening_star(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 2..data.len {
        let o0 = open_at(data, i - 2);
        let o1 = open_at(data, i - 1);
        let o2 = open_at(data, i);
        let r1 = range(data.high[i - 1], data.low[i - 1]);
        let b1 = body(o1, data.close[i - 1]);
        if is_bullish(o0, data.close[i - 2])
            && r1 > 0.0
            && b1 / r1 < 0.3
            && is_bearish(o2, data.close[i])
        {
            values[i] = -1.0;
        }
    }
    IndicatorResult { values }
}

/// 8. Three White Soldiers
fn three_white_soldiers(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 2..data.len {
        let o0 = open_at(data, i - 2);
        let o1 = open_at(data, i - 1);
        let o2 = open_at(data, i);
        if is_bullish(o0, data.close[i - 2])
            && is_bullish(o1, data.close[i - 1])
            && is_bullish(o2, data.close[i])
            && data.close[i] > data.close[i - 1]
            && data.close[i - 1] > data.close[i - 2]
        {
            values[i] = 1.0;
        }
    }
    IndicatorResult { values }
}

/// 9. Three Black Crows
fn three_black_crows(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 2..data.len {
        let o0 = open_at(data, i - 2);
        let o1 = open_at(data, i - 1);
        let o2 = open_at(data, i);
        if is_bearish(o0, data.close[i - 2])
            && is_bearish(o1, data.close[i - 1])
            && is_bearish(o2, data.close[i])
            && data.close[i] < data.close[i - 1]
            && data.close[i - 1] < data.close[i - 2]
        {
            values[i] = -1.0;
        }
    }
    IndicatorResult { values }
}

/// 10. Harami — current body within previous body
fn harami(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let c = data.close[i];
        let pc = data.close[i - 1];
        let prev_hi = po.max(pc);
        let prev_lo = po.min(pc);
        let cur_hi = o.max(c);
        let cur_lo = o.min(c);
        if cur_hi <= prev_hi && cur_lo >= prev_lo {
            if is_bearish(po, pc) && is_bullish(o, c) {
                values[i] = 1.0;
            } else if is_bullish(po, pc) && is_bearish(o, c) {
                values[i] = -1.0;
            }
        }
    }
    IndicatorResult { values }
}

/// 11. Piercing — bullish bar closes above 50% of previous bearish bar
fn piercing(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let c = data.close[i];
        let pc = data.close[i - 1];
        if is_bearish(po, pc) && is_bullish(o, c) {
            let mid = (po + pc) / 2.0;
            if o < pc && c > mid && c < po {
                values[i] = 1.0;
            }
        }
    }
    IndicatorResult { values }
}

/// 12. Dark Cloud Cover
fn dark_cloud(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let c = data.close[i];
        let pc = data.close[i - 1];
        if is_bullish(po, pc) && is_bearish(o, c) {
            let mid = (po + pc) / 2.0;
            if o > pc && c < mid && c > po {
                values[i] = -1.0;
            }
        }
    }
    IndicatorResult { values }
}

/// 13. Tweezer Top
fn tweezer_top(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let tol = 0.001; // 0.1% tolerance
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let hi_diff = (data.high[i] - data.high[i - 1]).abs();
        let avg_hi = (data.high[i] + data.high[i - 1]) / 2.0;
        if avg_hi > 0.0 && hi_diff / avg_hi < tol
            && is_bullish(po, data.close[i - 1])
            && is_bearish(o, data.close[i])
        {
            values[i] = -1.0;
        }
    }
    IndicatorResult { values }
}

/// 14. Tweezer Bottom
fn tweezer_bottom(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let tol = 0.001;
    for i in 1..data.len {
        let o = open_at(data, i);
        let po = open_at(data, i - 1);
        let lo_diff = (data.low[i] - data.low[i - 1]).abs();
        let avg_lo = (data.low[i] + data.low[i - 1]) / 2.0;
        if avg_lo > 0.0 && lo_diff / avg_lo < tol
            && is_bearish(po, data.close[i - 1])
            && is_bullish(o, data.close[i])
        {
            values[i] = 1.0;
        }
    }
    IndicatorResult { values }
}

/// 15. Marubozu — body > 95% of range
fn marubozu(data: &OhlcvData) -> IndicatorResult {
    let values: Vec<f64> = (0..data.len)
        .map(|i| {
            let o = open_at(data, i);
            let r = range(data.high[i], data.low[i]);
            if r > 0.0 && body(o, data.close[i]) / r > 0.95 {
                if is_bullish(o, data.close[i]) { 1.0 } else { -1.0 }
            } else {
                0.0
            }
        })
        .collect();
    IndicatorResult { values }
}

/// 16. Spinning Top — small body, roughly equal upper and lower wicks
fn spinning_top(data: &OhlcvData) -> IndicatorResult {
    let values: Vec<f64> = (0..data.len)
        .map(|i| {
            let o = open_at(data, i);
            let r = range(data.high[i], data.low[i]);
            if r <= 0.0 { return 0.0; }
            let b = body(o, data.close[i]);
            let uw = upper_wick(o, data.close[i], data.high[i]);
            let lw = lower_wick(o, data.close[i], data.low[i]);
            if b / r < 0.3 && uw > 0.0 && lw > 0.0 {
                let ratio = if uw > lw { lw / uw } else { uw / lw };
                if ratio > 0.5 { 1.0 } else { 0.0 } // neutral signal
            } else {
                0.0
            }
        })
        .collect();
    IndicatorResult { values }
}

// ============================================================
// Dispatch
// ============================================================

pub fn dispatch(name: &str, _period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "pin_bar" => Some(pin_bar(data)),
        "engulfing" => Some(engulfing(data)),
        "doji" => Some(doji(data)),
        "hammer" => Some(hammer(data)),
        "shooting_star" => Some(shooting_star(data)),
        "morning_star" => Some(morning_star(data)),
        "evening_star" => Some(evening_star(data)),
        "three_white_soldiers" => Some(three_white_soldiers(data)),
        "three_black_crows" => Some(three_black_crows(data)),
        "harami" => Some(harami(data)),
        "piercing" => Some(piercing(data)),
        "dark_cloud" => Some(dark_cloud(data)),
        "tweezer_top" => Some(tweezer_top(data)),
        "tweezer_bottom" => Some(tweezer_bottom(data)),
        "marubozu" => Some(marubozu(data)),
        "spinning_top" => Some(spinning_top(data)),
        _ => None,
    }
}
