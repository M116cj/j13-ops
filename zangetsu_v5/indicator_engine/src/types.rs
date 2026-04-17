pub struct OhlcvData {
    pub close: Vec<f64>,
    pub high: Vec<f64>,
    pub low: Vec<f64>,
    pub volume: Vec<f64>,
    pub len: usize,
}

pub struct IndicatorResult {
    pub values: Vec<f64>,
}

pub trait Indicator {
    fn compute(&self, data: &OhlcvData) -> IndicatorResult;
    fn name(&self) -> &str;
}

/// Simple Moving Average over a slice
pub fn sma(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n == 0 {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    if period > n {
        return result;
    }
    let mut sum: f64 = data[..period].iter().sum();
    result[period - 1] = sum / period as f64;
    for i in period..n {
        sum += data[i] - data[i - period];
        result[i] = sum / period as f64;
    }
    result
}

/// Exponential Moving Average over a slice
pub fn ema(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n == 0 {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    if period > n {
        return result;
    }
    // Seed with SMA of first `period` values
    let seed: f64 = data[..period].iter().sum::<f64>() / period as f64;
    result[period - 1] = seed;
    let alpha = 2.0 / (period as f64 + 1.0);
    for i in period..n {
        result[i] = alpha * data[i] + (1.0 - alpha) * result[i - 1];
    }
    result
}

/// Wilder's smoothing (used by RSI, ATR, etc.)
pub fn wilder_smooth(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n == 0 {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    if period > n {
        return result;
    }
    let seed: f64 = data[..period].iter().sum::<f64>() / period as f64;
    result[period - 1] = seed;
    for i in period..n {
        result[i] = (result[i - 1] * (period as f64 - 1.0) + data[i]) / period as f64;
    }
    result
}

/// Weighted Moving Average over a slice
pub fn wma(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n == 0 {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    if period > n {
        return result;
    }
    let denom = (period * (period + 1)) as f64 / 2.0;
    for i in (period - 1)..n {
        let mut sum = 0.0;
        for j in 0..period {
            sum += data[i - period + 1 + j] * (j + 1) as f64;
        }
        result[i] = sum / denom;
    }
    result
}
