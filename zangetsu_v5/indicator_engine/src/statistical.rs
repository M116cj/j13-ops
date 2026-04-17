use crate::types::*;

// ============================================================
// Statistical Indicators — 7 implementations
// ============================================================

/// 1. Z-Score: (close - mean) / std over rolling window
fn zscore(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < period || period < 2 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        let slice = &data.close[start..=i];
        let mean = slice.iter().sum::<f64>() / period as f64;
        let var = slice.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (period - 1) as f64;
        let std = var.sqrt();
        values[i] = if std > 0.0 { (data.close[i] - mean) / std } else { 0.0 };
    }
    IndicatorResult { values }
}

/// Helper: compute returns vector
fn returns(close: &[f64]) -> Vec<f64> {
    let mut ret = vec![0.0; close.len()];
    for i in 1..close.len() {
        if close[i - 1] != 0.0 {
            ret[i] = (close[i] - close[i - 1]) / close[i - 1];
        }
    }
    ret
}

/// 2. Rolling Skewness of returns
fn skewness(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let ret = returns(&data.close);
    if data.len < period || period < 3 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        let slice = &ret[start..=i];
        let n = period as f64;
        let mean = slice.iter().sum::<f64>() / n;
        let m2 = slice.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
        let m3 = slice.iter().map(|x| (x - mean).powi(3)).sum::<f64>() / n;
        let std = m2.sqrt();
        values[i] = if std > 0.0 {
            (n * n / ((n - 1.0) * (n - 2.0))) * (m3 / std.powi(3))
        } else {
            0.0
        };
    }
    IndicatorResult { values }
}

/// 3. Rolling Kurtosis of returns (excess kurtosis)
fn kurtosis(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let ret = returns(&data.close);
    if data.len < period || period < 4 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        let slice = &ret[start..=i];
        let n = period as f64;
        let mean = slice.iter().sum::<f64>() / n;
        let m2 = slice.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
        let m4 = slice.iter().map(|x| (x - mean).powi(4)).sum::<f64>() / n;
        values[i] = if m2 > 0.0 { m4 / m2.powi(2) - 3.0 } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 4. Hurst Exponent via simplified R/S analysis
fn hurst(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.5; data.len]; // default H=0.5 (random walk)
    let ret = returns(&data.close);
    if data.len < period || period < 8 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        let slice = &ret[start..=i];
        // Try multiple sub-period sizes for log-log regression
        let mut log_n = Vec::new();
        let mut log_rs = Vec::new();
        let sizes: Vec<usize> = vec![period / 4, period / 2, period]
            .into_iter()
            .filter(|&s| s >= 4)
            .collect();
        for &sz in &sizes {
            let n_chunks = (period / sz).max(1);
            let mut rs_sum = 0.0;
            let mut rs_count = 0;
            for c in 0..n_chunks {
                let cs = start + c * sz;
                let ce = (cs + sz).min(i + 1);
                if ce - cs < 4 { continue; }
                let chunk = &ret[cs..ce];
                let m = chunk.iter().sum::<f64>() / chunk.len() as f64;
                let std = (chunk.iter().map(|x| (x - m).powi(2)).sum::<f64>() / chunk.len() as f64).sqrt();
                if std <= 0.0 { continue; }
                // Cumulative deviation
                let mut cum = 0.0;
                let mut max_cum = f64::MIN;
                let mut min_cum = f64::MAX;
                for &v in chunk {
                    cum += v - m;
                    if cum > max_cum { max_cum = cum; }
                    if cum < min_cum { min_cum = cum; }
                }
                let r = max_cum - min_cum;
                rs_sum += r / std;
                rs_count += 1;
            }
            if rs_count > 0 {
                log_n.push((sz as f64).ln());
                log_rs.push((rs_sum / rs_count as f64).ln());
            }
        }
        // Linear regression on log-log
        if log_n.len() >= 2 {
            let n = log_n.len() as f64;
            let sx: f64 = log_n.iter().sum();
            let sy: f64 = log_rs.iter().sum();
            let sxx: f64 = log_n.iter().map(|x| x * x).sum();
            let sxy: f64 = log_n.iter().zip(log_rs.iter()).map(|(x, y)| x * y).sum();
            let denom = n * sxx - sx * sx;
            if denom.abs() > 1e-12 {
                let h = (n * sxy - sx * sy) / denom;
                values[i] = h.clamp(0.0, 1.0);
            }
        }
    }
    IndicatorResult { values }
}

/// 5. Shannon Entropy of discretized returns
fn entropy(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let ret = returns(&data.close);
    let bins = 10usize;
    if data.len < period || period < 2 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        let slice = &ret[start..=i];
        let mut lo = f64::MAX;
        let mut hi = f64::MIN;
        for &v in slice {
            if v < lo { lo = v; }
            if v > hi { hi = v; }
        }
        let range = hi - lo;
        if range <= 0.0 {
            values[i] = 0.0;
            continue;
        }
        let step = range / bins as f64;
        let mut counts = vec![0u32; bins];
        for &v in slice {
            let idx = ((v - lo) / step).min((bins - 1) as f64) as usize;
            counts[idx] += 1;
        }
        let n = slice.len() as f64;
        let mut h = 0.0;
        for &c in &counts {
            if c > 0 {
                let p = c as f64 / n;
                h -= p * p.ln();
            }
        }
        values[i] = h;
    }
    IndicatorResult { values }
}

/// 6. Lag-1 Autocorrelation of returns over window
fn autocorrelation(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let ret = returns(&data.close);
    if data.len < period || period < 3 {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let start = i + 1 - period;
        // x = ret[start..i], y = ret[start+1..=i]
        let n = (period - 1) as f64;
        if n < 2.0 { continue; }
        let x = &ret[start..i];
        let y = &ret[(start + 1)..=i];
        let mx = x.iter().sum::<f64>() / n;
        let my = y.iter().sum::<f64>() / n;
        let mut cov = 0.0;
        let mut vx = 0.0;
        let mut vy = 0.0;
        for j in 0..x.len() {
            let dx = x[j] - mx;
            let dy = y[j] - my;
            cov += dx * dy;
            vx += dx * dx;
            vy += dy * dy;
        }
        let denom = (vx * vy).sqrt();
        values[i] = if denom > 0.0 { cov / denom } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 7. Variance Ratio: var(k-period returns) / (k * var(1-period returns))
fn variance_ratio(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![1.0; data.len]; // VR=1 for random walk
    let ret = returns(&data.close);
    let k = period.max(2);
    if data.len < k * 2 {
        return IndicatorResult { values };
    }
    // k-period returns
    let mut kret = vec![0.0; data.len];
    for i in k..data.len {
        if data.close[i - k] != 0.0 {
            kret[i] = (data.close[i] - data.close[i - k]) / data.close[i - k];
        }
    }
    // Rolling calculation
    let window = k * 4; // use a reasonable window for estimation
    for i in window..data.len {
        let start = i + 1 - window;
        // Var of 1-period returns
        let r1 = &ret[start..=i];
        let m1 = r1.iter().sum::<f64>() / r1.len() as f64;
        let var1 = r1.iter().map(|x| (x - m1).powi(2)).sum::<f64>() / (r1.len() - 1) as f64;
        // Var of k-period returns
        let rk: Vec<f64> = kret[start..=i].iter().copied().collect();
        let mk = rk.iter().sum::<f64>() / rk.len() as f64;
        let vark = rk.iter().map(|x| (x - mk).powi(2)).sum::<f64>() / (rk.len() - 1).max(1) as f64;
        let denom = k as f64 * var1;
        values[i] = if denom > 0.0 { vark / denom } else { 1.0 };
    }
    IndicatorResult { values }
}

// ============================================================
// Dispatch
// ============================================================

pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "zscore" => Some(zscore(period, data)),
        "skewness" => Some(skewness(period, data)),
        "kurtosis" => Some(kurtosis(period, data)),
        "hurst" => Some(hurst(period, data)),
        "entropy" => Some(entropy(period, data)),
        "autocorrelation" => Some(autocorrelation(period, data)),
        "variance_ratio" => Some(variance_ratio(period, data)),
        _ => None,
    }
}
