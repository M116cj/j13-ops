use crate::types::*;

// ─── Helper: True Range ───
fn true_range(high: &[f64], low: &[f64], close: &[f64]) -> Vec<f64> {
    let n = high.len();
    let mut tr = vec![0.0; n];
    tr[0] = high[0] - low[0];
    for i in 1..n {
        let hl = high[i] - low[i];
        let hc = (high[i] - close[i - 1]).abs();
        let lc = (low[i] - close[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);
    }
    tr
}

fn highest(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    let mut out = vec![f64::NAN; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mx = f64::NEG_INFINITY;
        for j in start..=i {
            if data[j] > mx { mx = data[j]; }
        }
        out[i] = mx;
    }
    out
}

fn lowest(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    let mut out = vec![f64::NAN; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mn = f64::INFINITY;
        for j in start..=i {
            if data[j] < mn { mn = data[j]; }
        }
        out[i] = mn;
    }
    out
}

fn bars_since_highest(data: &[f64], period: usize) -> Vec<usize> {
    let n = data.len();
    let mut out = vec![0usize; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mx = f64::NEG_INFINITY;
        let mut idx = i;
        for j in start..=i {
            if data[j] >= mx { mx = data[j]; idx = j; }
        }
        out[i] = i - idx;
    }
    out
}

fn bars_since_lowest(data: &[f64], period: usize) -> Vec<usize> {
    let n = data.len();
    let mut out = vec![0usize; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mn = f64::INFINITY;
        let mut idx = i;
        for j in start..=i {
            if data[j] <= mn { mn = data[j]; idx = j; }
        }
        out[i] = i - idx;
    }
    out
}

// ─── 1. ADX ───
pub fn adx(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }

    let mut plus_dm = vec![0.0; n];
    let mut minus_dm = vec![0.0; n];
    let tr = true_range(&data.high, &data.low, &data.close);

    for i in 1..n {
        let up = data.high[i] - data.high[i - 1];
        let down = data.low[i - 1] - data.low[i];
        plus_dm[i] = if up > down && up > 0.0 { up } else { 0.0 };
        minus_dm[i] = if down > up && down > 0.0 { down } else { 0.0 };
    }

    let smooth_tr = wilder_smooth(&tr, period);
    let smooth_pdm = wilder_smooth(&plus_dm, period);
    let smooth_mdm = wilder_smooth(&minus_dm, period);

    let mut dx = vec![0.0; n];
    for i in 0..n {
        if smooth_tr[i] > 0.0 {
            let pdi = 100.0 * smooth_pdm[i] / smooth_tr[i];
            let mdi = 100.0 * smooth_mdm[i] / smooth_tr[i];
            let sum = pdi + mdi;
            dx[i] = if sum > 0.0 { 100.0 * (pdi - mdi).abs() / sum } else { 0.0 };
        }
    }

    let adx_vals = wilder_smooth(&dx, period);
    for i in 0..n { result[i] = adx_vals[i]; }
    IndicatorResult { values: result }
}

// ─── 2. Aroon Up ───
pub fn aroon_up(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    let bsh = bars_since_highest(&data.high, period);
    for i in 0..n {
        result[i] = 100.0 * (period as f64 - bsh[i] as f64) / period as f64;
    }
    IndicatorResult { values: result }
}

// ─── 3. Aroon Down ───
pub fn aroon_down(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    let bsl = bars_since_lowest(&data.low, period);
    for i in 0..n {
        result[i] = 100.0 * (period as f64 - bsl[i] as f64) / period as f64;
    }
    IndicatorResult { values: result }
}

// ─── 4. Aroon Oscillator ───
pub fn aroon_oscillator(data: &OhlcvData, period: usize) -> IndicatorResult {
    let up = aroon_up(data, period);
    let down = aroon_down(data, period);
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = up.values[i] - down.values[i]; }
    IndicatorResult { values: result }
}

// ─── 5. SuperTrend ───
pub fn supertrend(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let multiplier = 3.0;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }

    let tr = true_range(&data.high, &data.low, &data.close);
    let atr = wilder_smooth(&tr, period);

    let mut upper_band = vec![0.0; n];
    let mut lower_band = vec![0.0; n];
    let mut supertrend = vec![0.0; n];
    let mut direction = vec![1i32; n]; // 1 = up (bullish), -1 = down (bearish)

    for i in 0..n {
        let mid = (data.high[i] + data.low[i]) / 2.0;
        upper_band[i] = mid + multiplier * atr[i];
        lower_band[i] = mid - multiplier * atr[i];
    }

    for i in 1..n {
        if lower_band[i] < lower_band[i - 1] && data.close[i - 1] > lower_band[i - 1] {
            // keep previous lower band if close was above it
        } else if data.close[i - 1] > lower_band[i - 1] {
            lower_band[i] = lower_band[i].max(lower_band[i - 1]);
        }

        if upper_band[i] > upper_band[i - 1] && data.close[i - 1] < upper_band[i - 1] {
            // keep previous upper band if close was below it
        } else if data.close[i - 1] < upper_band[i - 1] {
            upper_band[i] = upper_band[i].min(upper_band[i - 1]);
        }

        if direction[i - 1] == 1 {
            direction[i] = if data.close[i] < lower_band[i] { -1 } else { 1 };
        } else {
            direction[i] = if data.close[i] > upper_band[i] { 1 } else { -1 };
        }
    }

    for i in 0..n {
        supertrend[i] = if direction[i] == 1 { lower_band[i] } else { upper_band[i] };
        result[i] = supertrend[i];
    }
    IndicatorResult { values: result }
}

// ─── 6. Ichimoku Tenkan ───
pub fn ichimoku_tenkan(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let period = 9;
    let n = data.len;
    let hh = highest(&data.high, period);
    let ll = lowest(&data.low, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = (hh[i] + ll[i]) / 2.0; }
    IndicatorResult { values: result }
}

// ─── 7. Ichimoku Kijun ───
pub fn ichimoku_kijun(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let period = 26;
    let n = data.len;
    let hh = highest(&data.high, period);
    let ll = lowest(&data.low, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = (hh[i] + ll[i]) / 2.0; }
    IndicatorResult { values: result }
}

// ─── 8. Ichimoku Senkou A ───
pub fn ichimoku_senkou_a(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let tenkan = ichimoku_tenkan(data, 0);
    let kijun = ichimoku_kijun(data, 0);
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = (tenkan.values[i] + kijun.values[i]) / 2.0; }
    IndicatorResult { values: result }
}

// ─── 9. Ichimoku Senkou B ───
pub fn ichimoku_senkou_b(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let period = 52;
    let n = data.len;
    let hh = highest(&data.high, period);
    let ll = lowest(&data.low, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = (hh[i] + ll[i]) / 2.0; }
    IndicatorResult { values: result }
}

// ─── 10. PSAR ───
pub fn psar(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 { return IndicatorResult { values: result }; }

    let af_start = 0.02;
    let af_inc = 0.02;
    let af_max = 0.20;

    let mut is_long = true;
    let mut sar = data.low[0];
    let mut ep = data.high[0];
    let mut af = af_start;
    result[0] = sar;

    for i in 1..n {
        sar = sar + af * (ep - sar);

        if is_long {
            sar = sar.min(data.low[i - 1]);
            if i >= 2 { sar = sar.min(data.low[i - 2]); }
            if data.low[i] < sar {
                is_long = false;
                sar = ep;
                ep = data.low[i];
                af = af_start;
            } else {
                if data.high[i] > ep {
                    ep = data.high[i];
                    af = (af + af_inc).min(af_max);
                }
            }
        } else {
            sar = sar.max(data.high[i - 1]);
            if i >= 2 { sar = sar.max(data.high[i - 2]); }
            if data.high[i] > sar {
                is_long = true;
                sar = ep;
                ep = data.high[i];
                af = af_start;
            } else {
                if data.low[i] < ep {
                    ep = data.low[i];
                    af = (af + af_inc).min(af_max);
                }
            }
        }
        result[i] = sar;
    }
    IndicatorResult { values: result }
}

// ─── 11. Linear Regression Slope ───
pub fn linreg_slope(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period < 2 { return IndicatorResult { values: result }; }
    for i in (period - 1)..n {
        let start = i - period + 1;
        let mut sum_x = 0.0;
        let mut sum_y = 0.0;
        let mut sum_xy = 0.0;
        let mut sum_x2 = 0.0;
        for j in 0..period {
            let x = j as f64;
            let y = data.close[start + j];
            sum_x += x;
            sum_y += y;
            sum_xy += x * y;
            sum_x2 += x * x;
        }
        let pf = period as f64;
        let denom = pf * sum_x2 - sum_x * sum_x;
        if denom.abs() > 1e-15 {
            result[i] = (pf * sum_xy - sum_x * sum_y) / denom;
        }
    }
    IndicatorResult { values: result }
}

// ─── 12. Linear Regression Intercept ───
pub fn linreg_intercept(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period < 2 { return IndicatorResult { values: result }; }
    for i in (period - 1)..n {
        let start = i - period + 1;
        let mut sum_x = 0.0;
        let mut sum_y = 0.0;
        let mut sum_xy = 0.0;
        let mut sum_x2 = 0.0;
        for j in 0..period {
            let x = j as f64;
            let y = data.close[start + j];
            sum_x += x;
            sum_y += y;
            sum_xy += x * y;
            sum_x2 += x * x;
        }
        let pf = period as f64;
        let denom = pf * sum_x2 - sum_x * sum_x;
        if denom.abs() > 1e-15 {
            let slope = (pf * sum_xy - sum_x * sum_y) / denom;
            result[i] = (sum_y - slope * sum_x) / pf;
        }
    }
    IndicatorResult { values: result }
}

// ─── 13. Linear Regression Angle ───
pub fn linreg_angle(data: &OhlcvData, period: usize) -> IndicatorResult {
    let slope = linreg_slope(data, period);
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in 0..n {
        result[i] = slope.values[i].atan().to_degrees();
    }
    IndicatorResult { values: result }
}

// ─── 14. TRIX ───
pub fn trix(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let ema1 = ema(&data.close, period);
    let ema2 = ema(&ema1, period);
    let ema3 = ema(&ema2, period);
    let mut result = vec![0.0; n];
    for i in 1..n {
        if ema3[i - 1].abs() > 1e-15 {
            result[i] = (ema3[i] - ema3[i - 1]) / ema3[i - 1] * 100.0;
        }
    }
    IndicatorResult { values: result }
}

// ─── 15. Vortex Positive ───
pub fn vortex_positive(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }
    let tr = true_range(&data.high, &data.low, &data.close);
    let mut vm_plus = vec![0.0; n];
    for i in 1..n {
        vm_plus[i] = (data.high[i] - data.low[i - 1]).abs();
    }
    for i in period..n {
        let start = i - period + 1;
        let sum_vm: f64 = vm_plus[start..=i].iter().sum();
        let sum_tr: f64 = tr[start..=i].iter().sum();
        if sum_tr > 0.0 { result[i] = sum_vm / sum_tr; }
    }
    IndicatorResult { values: result }
}

// ─── 16. Vortex Negative ───
pub fn vortex_negative(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }
    let tr = true_range(&data.high, &data.low, &data.close);
    let mut vm_minus = vec![0.0; n];
    for i in 1..n {
        vm_minus[i] = (data.low[i] - data.high[i - 1]).abs();
    }
    for i in period..n {
        let start = i - period + 1;
        let sum_vm: f64 = vm_minus[start..=i].iter().sum();
        let sum_tr: f64 = tr[start..=i].iter().sum();
        if sum_tr > 0.0 { result[i] = sum_vm / sum_tr; }
    }
    IndicatorResult { values: result }
}

// ─── 17. DMI Plus ───
pub fn dmi_plus(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }
    let mut plus_dm = vec![0.0; n];
    let tr = true_range(&data.high, &data.low, &data.close);
    for i in 1..n {
        let up = data.high[i] - data.high[i - 1];
        let down = data.low[i - 1] - data.low[i];
        plus_dm[i] = if up > down && up > 0.0 { up } else { 0.0 };
    }
    let smooth_tr = wilder_smooth(&tr, period);
    let smooth_pdm = wilder_smooth(&plus_dm, period);
    for i in 0..n {
        if smooth_tr[i] > 0.0 { result[i] = 100.0 * smooth_pdm[i] / smooth_tr[i]; }
    }
    IndicatorResult { values: result }
}

// ─── 18. DMI Minus ───
pub fn dmi_minus(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period == 0 { return IndicatorResult { values: result }; }
    let mut minus_dm = vec![0.0; n];
    let tr = true_range(&data.high, &data.low, &data.close);
    for i in 1..n {
        let up = data.high[i] - data.high[i - 1];
        let down = data.low[i - 1] - data.low[i];
        minus_dm[i] = if down > up && down > 0.0 { down } else { 0.0 };
    }
    let smooth_tr = wilder_smooth(&tr, period);
    let smooth_mdm = wilder_smooth(&minus_dm, period);
    for i in 0..n {
        if smooth_tr[i] > 0.0 { result[i] = 100.0 * smooth_mdm[i] / smooth_tr[i]; }
    }
    IndicatorResult { values: result }
}

// ─── 19. ADXR ───
pub fn adxr(data: &OhlcvData, period: usize) -> IndicatorResult {
    let adx_vals = adx(data, period);
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in period..n {
        result[i] = (adx_vals.values[i] + adx_vals.values[i - period]) / 2.0;
    }
    IndicatorResult { values: result }
}

// ─── 20. APO ───
pub fn apo(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let fast_period = period;
    let slow_period = period * 2;
    let fast_ema = ema(&data.close, fast_period);
    let slow_ema = ema(&data.close, slow_period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = fast_ema[i] - slow_ema[i]; }
    IndicatorResult { values: result }
}

// ─── 21. Fisher Transform ───
pub fn fisher_transform(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    let hh = highest(&data.high, period);
    let ll = lowest(&data.low, period);
    let mut val = 0.0;
    let mut fish = 0.0;
    for i in 0..n {
        let range = hh[i] - ll[i];
        let mid = (data.high[i] + data.low[i]) / 2.0;
        let raw = if range > 1e-15 { 2.0 * (mid - ll[i]) / range - 1.0 } else { 0.0 };
        // clamp to avoid infinity
        let clamped = raw.max(-0.999).min(0.999);
        // smooth
        val = 0.5 * clamped + 0.5 * val;
        let v = val.max(-0.999).min(0.999);
        let prev_fish = fish;
        fish = 0.5 * ((1.0 + v) / (1.0 - v)).ln() + 0.5 * prev_fish;
        result[i] = fish;
    }
    IndicatorResult { values: result }
}

// ─── 22. Detrended Price ───
pub fn detrended_price(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    let shift = period / 2 + 1;
    let sma_vals = sma(&data.close, shift);
    for i in shift..n {
        result[i] = data.close[i] - sma_vals[i - shift + shift - 1];
    }
    // simpler: detrended[i] = close[i] - sma[i] with lookback offset
    // standard implementation: close - sma shifted back
    let sma_full = sma(&data.close, period);
    for i in 0..n {
        if i >= shift {
            result[i] = data.close[i] - sma_full[i.saturating_sub(shift)];
        } else {
            result[i] = 0.0;
        }
    }
    IndicatorResult { values: result }
}

// ─── 23. Choppiness Index ───
pub fn choppiness_index(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period < 2 { return IndicatorResult { values: result }; }
    let tr = true_range(&data.high, &data.low, &data.close);
    for i in period..n {
        let start = i - period + 1;
        let sum_atr: f64 = tr[start..=i].iter().sum();
        let mut hi = f64::NEG_INFINITY;
        let mut lo = f64::INFINITY;
        for j in start..=i {
            if data.high[j] > hi { hi = data.high[j]; }
            if data.low[j] < lo { lo = data.low[j]; }
        }
        let range = hi - lo;
        if range > 1e-15 {
            result[i] = 100.0 * (sum_atr / range).log10() / (period as f64).log10();
        }
    }
    IndicatorResult { values: result }
}

// ─── 24. Rainbow MA 1 ───
pub fn rainbow_ma_1(data: &OhlcvData, period: usize) -> IndicatorResult {
    let vals = sma(&data.close, period);
    IndicatorResult { values: vals }
}

// ─── 25. Rainbow MA 2 ───
pub fn rainbow_ma_2(data: &OhlcvData, period: usize) -> IndicatorResult {
    let r1 = sma(&data.close, period);
    let vals = sma(&r1, period);
    IndicatorResult { values: vals }
}

// ─── 26. Rainbow MA 3 ───
pub fn rainbow_ma_3(data: &OhlcvData, period: usize) -> IndicatorResult {
    let r1 = sma(&data.close, period);
    let r2 = sma(&r1, period);
    let vals = sma(&r2, period);
    IndicatorResult { values: vals }
}

// ─── 27. Schaff Trend Cycle ───
pub fn schaff_trend_cycle(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period < 2 { return IndicatorResult { values: result }; }

    // MACD line
    let fast = ema(&data.close, period);
    let slow = ema(&data.close, period * 2);
    let mut macd = vec![0.0; n];
    for i in 0..n { macd[i] = fast[i] - slow[i]; }

    let stoch_period = period;

    // First stochastic of MACD
    let mut pf = vec![0.0; n];
    let mut f1 = 0.0;
    for i in 0..n {
        let start = if i >= stoch_period { i - stoch_period + 1 } else { 0 };
        let mut hi = f64::NEG_INFINITY;
        let mut lo = f64::INFINITY;
        for j in start..=i {
            if macd[j] > hi { hi = macd[j]; }
            if macd[j] < lo { lo = macd[j]; }
        }
        let range = hi - lo;
        let stoch = if range > 1e-15 { (macd[i] - lo) / range * 100.0 } else { f1 };
        f1 = f1 + 0.5 * (stoch - f1);
        pf[i] = f1;
    }

    // Second stochastic
    let mut f2 = 0.0;
    for i in 0..n {
        let start = if i >= stoch_period { i - stoch_period + 1 } else { 0 };
        let mut hi = f64::NEG_INFINITY;
        let mut lo = f64::INFINITY;
        for j in start..=i {
            if pf[j] > hi { hi = pf[j]; }
            if pf[j] < lo { lo = pf[j]; }
        }
        let range = hi - lo;
        let stoch = if range > 1e-15 { (pf[i] - lo) / range * 100.0 } else { f2 };
        f2 = f2 + 0.5 * (stoch - f2);
        result[i] = f2;
    }

    IndicatorResult { values: result }
}

// ─── 28. McGinley Dynamic ───
pub fn mcginley_dynamic(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n == 0 || period == 0 { return IndicatorResult { values: result }; }
    let k = period as f64;
    result[0] = data.close[0];
    for i in 1..n {
        let md = result[i - 1];
        let c = data.close[i];
        let ratio = c / md;
        let denom = k * ratio.powi(4);
        if denom.abs() > 1e-15 {
            result[i] = md + (c - md) / denom;
        } else {
            result[i] = md;
        }
    }
    IndicatorResult { values: result }
}

// ─── 29. Qstick ───
pub fn qstick(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    // Qstick needs open prices — use close[i-1] as proxy if open not available
    // But OhlcvData doesn't have open, so we approximate: close[i] - close[i] = 0
    // Actually, we should use high/low midpoint as proxy for open
    // Standard Qstick = SMA(close - open). Without open, use (high+low)/2 as open proxy.
    let mut co = vec![0.0; n];
    for i in 0..n {
        let open_proxy = (data.high[i] + data.low[i]) / 2.0;
        co[i] = data.close[i] - open_proxy;
    }
    let vals = sma(&co, period);
    IndicatorResult { values: vals }
}

// ─── 30. Hurst Exponent ───
pub fn hurst_exponent(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.5; n]; // default to 0.5 (random walk)
    if period < 4 || n < period { return IndicatorResult { values: result }; }

    for i in (period - 1)..n {
        let start = i - period + 1;
        let slice = &data.close[start..=i];
        let len = slice.len();

        // Compute R/S for different sub-period sizes
        let mut log_ns = Vec::new();
        let mut log_rs = Vec::new();

        let sizes = [len / 4, len / 2, len];
        for &sz in &sizes {
            if sz < 4 { continue; }
            let num_blocks = len / sz;
            if num_blocks == 0 { continue; }
            let mut rs_sum = 0.0;
            let mut valid_blocks = 0;
            for b in 0..num_blocks {
                let block = &slice[b * sz..(b + 1) * sz];
                let mean: f64 = block.iter().sum::<f64>() / sz as f64;
                let mut cum_dev = vec![0.0; sz];
                cum_dev[0] = block[0] - mean;
                for k in 1..sz {
                    cum_dev[k] = cum_dev[k - 1] + (block[k] - mean);
                }
                let r = cum_dev.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
                    - cum_dev.iter().cloned().fold(f64::INFINITY, f64::min);
                let var: f64 = block.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / sz as f64;
                let s = var.sqrt();
                if s > 1e-15 {
                    rs_sum += r / s;
                    valid_blocks += 1;
                }
            }
            if valid_blocks > 0 {
                let avg_rs = rs_sum / valid_blocks as f64;
                log_ns.push((sz as f64).ln());
                log_rs.push(avg_rs.ln());
            }
        }

        if log_ns.len() >= 2 {
            // Linear regression of log(R/S) on log(n) to get Hurst exponent
            let k = log_ns.len() as f64;
            let sx: f64 = log_ns.iter().sum();
            let sy: f64 = log_rs.iter().sum();
            let sxy: f64 = log_ns.iter().zip(log_rs.iter()).map(|(x, y)| x * y).sum();
            let sx2: f64 = log_ns.iter().map(|x| x * x).sum();
            let denom = k * sx2 - sx * sx;
            if denom.abs() > 1e-15 {
                let h = (k * sxy - sx * sy) / denom;
                result[i] = h.max(0.0).min(1.0);
            }
        }
    }
    IndicatorResult { values: result }
}

// ─── Dispatch ───
pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "adx" => Some(adx(data, period)),
        "aroon_up" => Some(aroon_up(data, period)),
        "aroon_down" => Some(aroon_down(data, period)),
        "aroon_oscillator" => Some(aroon_oscillator(data, period)),
        "supertrend" => Some(supertrend(data, period)),
        "ichimoku_tenkan" => Some(ichimoku_tenkan(data, period)),
        "ichimoku_kijun" => Some(ichimoku_kijun(data, period)),
        "ichimoku_senkou_a" => Some(ichimoku_senkou_a(data, period)),
        "ichimoku_senkou_b" => Some(ichimoku_senkou_b(data, period)),
        "psar" => Some(psar(data, period)),
        "linreg_slope" => Some(linreg_slope(data, period)),
        "linreg_intercept" => Some(linreg_intercept(data, period)),
        "linreg_angle" => Some(linreg_angle(data, period)),
        "trix" => Some(trix(data, period)),
        "vortex_positive" => Some(vortex_positive(data, period)),
        "vortex_negative" => Some(vortex_negative(data, period)),
        "dmi_plus" => Some(dmi_plus(data, period)),
        "dmi_minus" => Some(dmi_minus(data, period)),
        "adxr" => Some(adxr(data, period)),
        "apo" => Some(apo(data, period)),
        "fisher_transform" => Some(fisher_transform(data, period)),
        "detrended_price" => Some(detrended_price(data, period)),
        "choppiness_index" => Some(choppiness_index(data, period)),
        "rainbow_ma_1" => Some(rainbow_ma_1(data, period)),
        "rainbow_ma_2" => Some(rainbow_ma_2(data, period)),
        "rainbow_ma_3" => Some(rainbow_ma_3(data, period)),
        "schaff_trend_cycle" => Some(schaff_trend_cycle(data, period)),
        "mcginley_dynamic" => Some(mcginley_dynamic(data, period)),
        "qstick" => Some(qstick(data, period)),
        "hurst_exponent" => Some(hurst_exponent(data, period)),
        _ => None,
    }
}
