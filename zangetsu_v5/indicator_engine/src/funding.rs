use crate::types::*;

/// Funding/derivatives indicators (11 total)
/// All require exchange API data. Stub implementations returning zeros.

pub fn funding_rate(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn oi_total(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn oi_delta(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn long_short_ratio(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn liquidation_volume(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn basis_spread(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn funding_predicted(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn oi_weighted_price(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn perp_premium(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn funding_velocity(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn oi_concentration(_period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.0; data.len] }
}

pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "funding_rate" => Some(funding_rate(period, data)),
        "oi_total" => Some(oi_total(period, data)),
        "oi_delta" => Some(oi_delta(period, data)),
        "long_short_ratio" => Some(long_short_ratio(period, data)),
        "liquidation_volume" => Some(liquidation_volume(period, data)),
        "basis_spread" => Some(basis_spread(period, data)),
        "funding_predicted" => Some(funding_predicted(period, data)),
        "oi_weighted_price" => Some(oi_weighted_price(period, data)),
        "perp_premium" => Some(perp_premium(period, data)),
        "funding_velocity" => Some(funding_velocity(period, data)),
        "oi_concentration" => Some(oi_concentration(period, data)),
        _ => None,
    }
}
