use pyo3::prelude::*;
use pyo3::types::PyDict;
use numpy::{PyArray1, PyArray2, PyReadonlyArray1};
use std::collections::HashMap;

mod types;
mod moving_average;
mod momentum;
mod trend;
mod volatility;
mod volume;
mod price_action;
mod statistical;
mod cross_asset;
mod funding;
mod multi_timeframe;

use types::{OhlcvData, IndicatorResult};

/// All supported indicators with their canonical names and category
fn all_indicators() -> Vec<(&'static str, &'static str)> {
    vec![
        // Moving Averages (14)
        ("SMA", "moving_average"), ("EMA", "moving_average"), ("WMA", "moving_average"),
        ("DEMA", "moving_average"), ("TEMA", "moving_average"), ("KAMA", "moving_average"),
        ("T3", "moving_average"), ("VIDYA", "moving_average"), ("FRAMA", "moving_average"),
        ("HMA", "moving_average"), ("ALMA", "moving_average"), ("ZLEMA", "moving_average"),
        ("SWMA", "moving_average"), ("TRIMA", "moving_average"),
        // Momentum (22)
        ("RSI", "momentum"), ("MACD", "momentum"), ("STOCH_K", "momentum"),
        ("STOCH_D", "momentum"), ("CCI", "momentum"), ("ROC", "momentum"),
        ("WILLIAMS_R", "momentum"), ("MFI", "momentum"), ("TSI", "momentum"),
        ("ULTIMATE", "momentum"), ("AO", "momentum"), ("PPO", "momentum"),
        ("PMO", "momentum"), ("CMO", "momentum"), ("DPO", "momentum"),
        ("KST", "momentum"), ("RVI", "momentum"), ("STOCH_RSI", "momentum"),
        ("ELDER_BULL", "momentum"), ("ELDER_BEAR", "momentum"),
        ("MASS_INDEX", "momentum"), ("CHANDE_FORECAST", "momentum"),
        // Trend (30)
        ("adx", "trend"), ("aroon_up", "trend"), ("aroon_down", "trend"),
        ("aroon_oscillator", "trend"), ("supertrend", "trend"),
        ("ichimoku_tenkan", "trend"), ("ichimoku_kijun", "trend"),
        ("ichimoku_senkou_a", "trend"), ("ichimoku_senkou_b", "trend"),
        ("psar", "trend"), ("linreg_slope", "trend"), ("linreg_intercept", "trend"),
        ("linreg_angle", "trend"), ("trix", "trend"),
        ("vortex_positive", "trend"), ("vortex_negative", "trend"),
        ("dmi_plus", "trend"), ("dmi_minus", "trend"), ("adxr", "trend"),
        ("apo", "trend"), ("fisher_transform", "trend"), ("detrended_price", "trend"),
        ("choppiness_index", "trend"), ("rainbow_ma_1", "trend"),
        ("rainbow_ma_2", "trend"), ("rainbow_ma_3", "trend"),
        ("schaff_trend_cycle", "trend"), ("mcginley_dynamic", "trend"),
        ("qstick", "trend"), ("hurst_exponent", "trend"),
        // Volatility (21)
        ("atr", "volatility"), ("bollinger_upper", "volatility"),
        ("bollinger_lower", "volatility"), ("bollinger_mid", "volatility"),
        ("bollinger_width", "volatility"), ("keltner_upper", "volatility"),
        ("keltner_lower", "volatility"), ("keltner_mid", "volatility"),
        ("donchian_upper", "volatility"), ("donchian_lower", "volatility"),
        ("donchian_width", "volatility"), ("natr", "volatility"),
        ("true_range", "volatility"), ("ulcer_index", "volatility"),
        ("chaikin_volatility", "volatility"), ("historical_volatility", "volatility"),
        ("garman_klass", "volatility"), ("parkinson", "volatility"),
        ("rogers_satchell", "volatility"), ("yang_zhang", "volatility"),
        ("standard_deviation", "volatility"),
        // Volume (32)
        ("obv", "volume"), ("vwap", "volume"), ("vol_mfi", "volume"),
        ("ad", "volume"), ("cmf", "volume"), ("eom", "volume"),
        ("force_index", "volume"), ("pvt", "volume"), ("nvi", "volume"),
        ("pvi", "volume"), ("vpt", "volume"), ("klinger", "volume"),
        ("volume_roc", "volume"), ("volume_sma", "volume"), ("volume_ema", "volume"),
        ("taker_buy_ratio", "volume"), ("relative_volume", "volume"),
        ("volume_profile_poc", "volume"), ("amihud_illiq", "volume"),
        ("roll_spread", "volume"), ("tick_volume", "volume"),
        ("trade_intensity", "volume"), ("buy_sell_ratio", "volume"),
        ("large_trade_pct", "volume"), ("volume_imbalance", "volume"),
        ("micro_price", "volume"), ("trade_flow", "volume"),
        ("volume_clock", "volume"), ("bar_speed", "volume"),
        ("tick_speed", "volume"), ("aggressor_ratio", "volume"),
        ("kyle_lambda", "volume"),
        // Price Action (16)
        ("pin_bar", "price_action"), ("engulfing", "price_action"),
        ("doji", "price_action"), ("hammer", "price_action"),
        ("shooting_star", "price_action"), ("morning_star", "price_action"),
        ("evening_star", "price_action"), ("three_white_soldiers", "price_action"),
        ("three_black_crows", "price_action"), ("harami", "price_action"),
        ("piercing", "price_action"), ("dark_cloud", "price_action"),
        ("tweezer_top", "price_action"), ("tweezer_bottom", "price_action"),
        ("marubozu", "price_action"), ("spinning_top", "price_action"),
        // Statistical (7)
        ("zscore", "statistical"), ("skewness", "statistical"),
        ("kurtosis", "statistical"), ("hurst", "statistical"),
        ("entropy", "statistical"), ("autocorrelation", "statistical"),
        ("variance_ratio", "statistical"),
        // Cross-Asset (11)
        ("btc_dominance", "cross_asset"), ("eth_correlation", "cross_asset"),
        ("btc_correlation", "cross_asset"), ("sector_momentum", "cross_asset"),
        ("alt_rotation", "cross_asset"), ("stable_flow", "cross_asset"),
        ("defi_tvl_change", "cross_asset"), ("gas_price_norm", "cross_asset"),
        ("hashrate_change", "cross_asset"), ("difficulty_roc", "cross_asset"),
        ("mempool_size", "cross_asset"),
        // Funding (11)
        ("funding_rate", "funding"), ("oi_total", "funding"),
        ("oi_delta", "funding"), ("long_short_ratio", "funding"),
        ("liquidation_volume", "funding"), ("basis_spread", "funding"),
        ("funding_predicted", "funding"), ("oi_weighted_price", "funding"),
        ("perp_premium", "funding"), ("funding_velocity", "funding"),
        ("oi_concentration", "funding"),
        // Multi-Timeframe (6)
        ("mtf_rsi", "multi_timeframe"), ("mtf_macd", "multi_timeframe"),
        ("mtf_adx", "multi_timeframe"), ("mtf_bb_width", "multi_timeframe"),
        ("mtf_volume", "multi_timeframe"), ("mtf_atr", "multi_timeframe"),
    ]
}

fn dispatch_indicator(name: &str, period: usize, data: &OhlcvData) -> IndicatorResult {
    // Handle vol_mfi -> mfi mapping for volume module
    let vol_name = if name == "vol_mfi" { "mfi" } else { name };

    // Try uppercase modules first (momentum, moving_average)
    let upper = name.to_uppercase();
    if let Some(r) = moving_average::dispatch(&upper, period, data) { return r; }
    if let Some(r) = momentum::dispatch(&upper, period, data) { return r; }

    // Try lowercase modules
    if let Some(r) = trend::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = volatility::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = volume::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = price_action::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = statistical::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = cross_asset::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = funding::dispatch(vol_name, period, data) { return r; }
    if let Some(r) = multi_timeframe::dispatch(vol_name, period, data) { return r; }

    // Fallback: zeros
    IndicatorResult { values: vec![0.0; data.len] }
}

/// Simple RNG (xorshift64) for deterministic config generation
struct Rng64 {
    state: u64,
}

impl Rng64 {
    fn new(seed: u64) -> Self { Self { state: seed.max(1) } }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }

    fn next_usize(&mut self, lo: usize, hi: usize) -> usize {
        if lo >= hi { return lo; }
        lo + (self.next_u64() as usize % (hi - lo))
    }
}

#[pyclass]
struct IndicatorEngine {
    seed: u64,
    indicators: Vec<(&'static str, &'static str)>,
}

#[pymethods]
impl IndicatorEngine {
    #[new]
    #[pyo3(signature = (seed=42))]
    fn new(seed: u64) -> Self {
        Self { seed, indicators: all_indicators() }
    }

    fn indicator_count(&self) -> usize {
        self.indicators.len()
    }

    fn engine_hash(&self) -> String {
        // Deterministic hash of all indicator names
        let mut h: u64 = 0xcbf29ce484222325; // FNV offset basis
        for (name, _) in &self.indicators {
            for b in name.bytes() {
                h ^= b as u64;
                h = h.wrapping_mul(0x100000001b3); // FNV prime
            }
        }
        format!("{:016x}", h)
    }

    fn list_indicators(&self) -> HashMap<String, Vec<String>> {
        let mut map: HashMap<String, Vec<String>> = HashMap::new();
        for (name, cat) in &self.indicators {
            map.entry(cat.to_string()).or_default().push(name.to_string());
        }
        map
    }

    /// Generate n random indicator configs as JSON string
    fn generate_random_set(&self, n: usize) -> String {
        let mut rng = Rng64::new(self.seed);
        let periods = [5, 7, 9, 10, 12, 14, 20, 21, 25, 30, 50, 55, 89, 100, 144, 200];
        let count = self.indicators.len();

        let mut configs = Vec::with_capacity(n);
        for _ in 0..n {
            let idx = rng.next_usize(0, count);
            let (name, _cat) = self.indicators[idx];
            let pidx = rng.next_usize(0, periods.len());
            let period = periods[pidx];
            configs.push(format!("{{\"name\":\"{}\",\"period\":{}}}", name, period));
        }
        format!("[{}]", configs.join(","))
    }

    /// Compute indicator set: returns (2D numpy array [n_bars x n_indicators], list of names)
    #[pyo3(signature = (open, high, low, close, volume, config_json))]
    fn compute_indicator_set<'py>(
        &self,
        py: Python<'py>,
        open: PyReadonlyArray1<'py, f64>,
        high: PyReadonlyArray1<'py, f64>,
        low: PyReadonlyArray1<'py, f64>,
        close: PyReadonlyArray1<'py, f64>,
        volume: PyReadonlyArray1<'py, f64>,
        config_json: &str,
    ) -> PyResult<(Bound<'py, PyArray2<f64>>, Vec<String>)> {
        let close_slice = close.as_slice()?;
        let high_slice = high.as_slice()?;
        let low_slice = low.as_slice()?;
        let vol_slice = volume.as_slice()?;
        let _open_slice = open.as_slice()?; // not used by most indicators yet

        let n = close_slice.len();
        let data = OhlcvData {
            len: n,
            close: close_slice.to_vec(),
            high: high_slice.to_vec(),
            low: low_slice.to_vec(),
            volume: vol_slice.to_vec(),
        };

        // Parse config JSON manually (avoid serde dependency)
        let configs = parse_configs(config_json)?;
        let n_ind = configs.len();
        let mut names = Vec::with_capacity(n_ind);
        let mut matrix = vec![0.0f64; n * n_ind];

        for (col, (name, period)) in configs.iter().enumerate() {
            let result = dispatch_indicator(name, *period, &data);
            names.push(format!("{}_{}", name, period));
            for row in 0..n {
                matrix[row * n_ind + col] = if row < result.values.len() {
                    let v = result.values[row];
                    if v.is_finite() { v } else { 0.0 }
                } else { 0.0 };
            }
        }

        let array = ndarray::Array2::from_shape_vec((n, n_ind), matrix)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("shape error: {}", e)))?;
        let py_array = PyArray2::from_owned_array_bound(py, array);
        Ok((py_array, names))
    }
}

/// Parse configs from JSON string like [{"name":"SMA","period":14}, ...]
fn parse_configs(json: &str) -> PyResult<Vec<(String, usize)>> {
    let mut result = Vec::new();
    let trimmed = json.trim();
    if trimmed.is_empty() || trimmed == "[]" {
        return Ok(result);
    }

    // Simple JSON array parser - split by }, {
    let inner = trimmed.trim_start_matches('[').trim_end_matches(']');
    for item in inner.split("},") {
        let item = item.trim().trim_matches('{').trim_matches('}').trim();
        let mut name = String::new();
        let mut period: usize = 14;

        for part in item.split(',') {
            let part = part.trim();
            if let Some(val) = part.strip_prefix("\"name\":")
                .or_else(|| part.strip_prefix("\"name\" :")) {
                name = val.trim().trim_matches('"').to_string();
            } else if let Some(val) = part.strip_prefix("\"period\":")
                .or_else(|| part.strip_prefix("\"period\" :")) {
                period = val.trim().parse::<usize>().unwrap_or(14);
            }
        }

        if !name.is_empty() {
            result.push((name, period));
        }
    }
    Ok(result)
}

// Keep the original compute function for backward compatibility
#[pyfunction]
#[pyo3(signature = (name, params, close, high, low, volume))]
fn compute<'py>(
    py: Python<'py>,
    name: &str,
    params: &Bound<'py, PyDict>,
    close: PyReadonlyArray1<'py, f64>,
    high: PyReadonlyArray1<'py, f64>,
    low: PyReadonlyArray1<'py, f64>,
    volume: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let close_slice = close.as_slice()?;
    let high_slice = high.as_slice()?;
    let low_slice = low.as_slice()?;
    let vol_slice = volume.as_slice()?;
    let data = OhlcvData {
        len: close_slice.len(),
        close: close_slice.to_vec(),
        high: high_slice.to_vec(),
        low: low_slice.to_vec(),
        volume: vol_slice.to_vec(),
    };
    let period = params
        .get_item("period")?
        .map(|v| v.extract::<usize>())
        .transpose()?
        .unwrap_or(14);

    let result = dispatch_indicator(name, period, &data);
    Ok(PyArray1::from_slice_bound(py, &result.values))
}

#[pymodule]
fn zangetsu_indicators(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute, m)?)?;
    m.add_class::<IndicatorEngine>()?;
    Ok(())
}
