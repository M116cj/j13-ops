use crate::types::*;

/// Cross-asset indicators (11 total)
/// Most require external data not available in backtesting.
/// Implemented as stubs returning zeros.

pub fn btc_dominance(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn eth_correlation(_period: usize, data: &OhlcvData) -> IndicatorResult {
    // Requires multi-symbol data; return 0.0 for single-symbol
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn btc_correlation(_period: usize, data: &OhlcvData) -> IndicatorResult {
    // Requires multi-symbol data; return 0.0 for single-symbol
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn sector_momentum(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn alt_rotation(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn stable_flow(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn defi_tvl_change(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn gas_price_norm(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn hashrate_change(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn difficulty_roc(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn mempool_size(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "btc_dominance" => Some(btc_dominance(period, data)),
        "eth_correlation" => Some(eth_correlation(period, data)),
        "btc_correlation" => Some(btc_correlation(period, data)),
        "sector_momentum" => Some(sector_momentum(period, data)),
        "alt_rotation" => Some(alt_rotation(period, data)),
        "stable_flow" => Some(stable_flow(period, data)),
        "defi_tvl_change" => Some(defi_tvl_change(period, data)),
        "gas_price_norm" => Some(gas_price_norm(period, data)),
        "hashrate_change" => Some(hashrate_change(period, data)),
        "difficulty_roc" => Some(difficulty_roc(period, data)),
        "mempool_size" => Some(mempool_size(period, data)),
        _ => None,
    }
}
