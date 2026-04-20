"""V10 Seed Batch 2: 101 Formulaic Alphas (Kakushadze 2016) — crypto-adapted.

Second batch of canonical alpha expressions ported from the paper.
Excludes those requiring cross-sectional rank or industry neutralization
(which do not translate to single-asset crypto).

Run: python -m zangetsu.services.seed_101_alphas_batch2
"""
# ============================================================
# DEPRECATED in v0.7.1 (2026-04-20 governance)
# ------------------------------------------------------------
# This module wrote directly to `champion_pipeline` before the
# physical split. Under v0.7.1:
#   - Writes must go through champion_pipeline_staging +
#     admission_validator(); direct INSERT to fresh is blocked
#     by DB trigger.
#   - Any use of this module as an entry point must pass the
#     explicit flag --i-know-deprecated-v071.
# ============================================================
import sys as _sys  # noqa: E402
if __name__ == "__main__" and "--i-know-deprecated-v071" not in _sys.argv:
    print("REFUSED: this module is DEPRECATED in v0.7.1.")
    print("Legacy seeding / discovery paths are frozen per governance rule #1.")
    print("Pass --i-know-deprecated-v071 only if you have an explicit ADR.")
    _sys.exit(2)

import os, sys, json, hashlib, logging, asyncio
from typing import Dict, Callable
from pathlib import Path
sys.path.insert(0, '/home/j13/j13-ops')

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from zangetsu.engine.components import alpha_primitives as prims

log = logging.getLogger(__name__)

DATA_DIR = Path('/home/j13/j13-ops/zangetsu/data/ohlcv')
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
           'DOGEUSDT', 'LINKUSDT', 'AAVEUSDT', 'AVAXUSDT', 'DOTUSDT',
           'FILUSDT', '1000PEPEUSDT', '1000SHIBUSDT', 'GALAUSDT']
DSN = f"postgresql://zangetsu:{os.environ['ZV5_DB_PASSWORD']}@127.0.0.1:5432/zangetsu"


# ============================================================
# Helpers
# ============================================================

def _f32(x):
    return np.ascontiguousarray(x, dtype=np.float32)


def _vwap_proxy(close, high, low):
    return _f32((close + high + low) / 3.0)


def _returns(close):
    c = _f32(close)
    r = np.zeros_like(c)
    r[1:] = (c[1:] - c[:-1]) / np.maximum(c[:-1], 1e-10)
    return r


def _rank(x):
    """Approx rank() using rolling 500-bar percentile."""
    return prims.ts_rank(_f32(x), 500)


def _delay(x, d):
    """delay(x, d) = x shifted by d bars (value from d bars ago)."""
    x = _f32(x)
    out = np.empty_like(x)
    if d <= 0:
        return x.copy()
    out[:d] = x[0]
    out[d:] = x[:-d]
    return out


# ============================================================
# Ported alphas
# ============================================================

def alpha_005(close, high, low, open_, volume):
    """Alpha#5 = (open - mean(vwap,10)) * abs(close - vwap) * -1"""
    vwap = _vwap_proxy(close, high, low)
    mean_vwap_10 = prims.ts_mean(vwap, 10)
    diff1 = prims.sub(_f32(open_), mean_vwap_10)
    diff2 = prims.abs_x(prims.sub(_f32(close), vwap))
    return prims.neg(prims.mul(diff1, diff2))


def alpha_007(close, high, low, open_, volume):
    """Alpha#7 = volume > adv20 ? -1*ts_rank(abs(delta(close,7)),60)*sign(delta(close,7)) : -1"""
    adv20 = prims.ts_mean(_f32(volume), 20)
    d7 = prims.delta(_f32(close), 7)
    ts_r = prims.ts_rank(prims.abs_x(d7), 60)
    branch_true = prims.neg(prims.mul(ts_r, prims.sign_x(d7)))
    branch_false = np.full_like(_f32(close), -1.0)
    return np.where(_f32(volume) > adv20, branch_true, branch_false).astype(np.float32)


def alpha_008(close, high, low, open_, volume):
    """Alpha#8 = -1 * rank(sum(open,5)*sum(returns,5) - delay(sum(open,5)*sum(returns,5),10))"""
    ret = _returns(close)
    sum_o = prims.ts_sum(_f32(open_), 5)
    sum_r = prims.ts_sum(ret, 5)
    prod = prims.mul(sum_o, sum_r)
    delayed = _delay(prod, 10)
    return prims.neg(_rank(prims.sub(prod, delayed)))


def alpha_009(close, high, low, open_, volume):
    """Alpha#9 = (0<ts_min(delta(close,1),5)) ? delta(close,1) :
                ((ts_max(delta(close,1),5)<0) ? delta(close,1) : -delta(close,1))"""
    d1 = prims.delta(_f32(close), 1)
    tmin = prims.ts_min(d1, 5)
    tmax = prims.ts_max(d1, 5)
    neg_d1 = prims.neg(d1)
    inner = np.where(tmax < 0, d1, neg_d1)
    return np.where(tmin > 0, d1, inner).astype(np.float32)


def alpha_010(close, high, low, open_, volume):
    """Alpha#10 = rank(Alpha#9-like with window 4)"""
    d1 = prims.delta(_f32(close), 1)
    tmin = prims.ts_min(d1, 4)
    tmax = prims.ts_max(d1, 4)
    neg_d1 = prims.neg(d1)
    inner = np.where(tmax < 0, d1, neg_d1)
    raw = np.where(tmin > 0, d1, inner).astype(np.float32)
    return _rank(raw)


def alpha_011(close, high, low, open_, volume):
    """Alpha#11 = (rank(ts_max(vwap-close,3)) + rank(ts_min(vwap-close,3))) * rank(delta(volume,3))"""
    vwap = _vwap_proxy(close, high, low)
    vc = prims.sub(vwap, _f32(close))
    r_max = _rank(prims.ts_max(vc, 3))
    r_min = _rank(prims.ts_min(vc, 3))
    r_dv = _rank(prims.delta(_f32(volume), 3))
    return prims.mul(prims.add(r_max, r_min), r_dv)


def alpha_013(close, high, low, open_, volume):
    """Alpha#13 = -1 * rank(covariance(rank(close), rank(volume), 5))"""
    rc = _rank(_f32(close))
    rv = _rank(_f32(volume))
    return prims.neg(_rank(prims.covariance(rc, rv, 5)))


def alpha_014(close, high, low, open_, volume):
    """Alpha#14 = (-rank(delta(returns,3))) * correlation(open, volume, 10)"""
    ret = _returns(close)
    r_dr = _rank(prims.delta(ret, 3))
    corr = prims.correlation(_f32(open_), _f32(volume), 10)
    return prims.mul(prims.neg(r_dr), corr)


def alpha_015(close, high, low, open_, volume):
    """Alpha#15 = -1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3)"""
    rh = _rank(_f32(high))
    rv = _rank(_f32(volume))
    c3 = prims.correlation(rh, rv, 3)
    return prims.neg(prims.ts_sum(_rank(c3), 3))


def alpha_016(close, high, low, open_, volume):
    """Alpha#16 = -1 * rank(covariance(rank(high), rank(volume), 5))"""
    rh = _rank(_f32(high))
    rv = _rank(_f32(volume))
    return prims.neg(_rank(prims.covariance(rh, rv, 5)))


def alpha_017(close, high, low, open_, volume):
    """Alpha#17 = -rank(ts_rank(close,10)) * rank(delta(delta(close,1),1)) * rank(ts_rank(volume/adv20,5))"""
    c = _f32(close)
    v = _f32(volume)
    adv20 = prims.ts_mean(v, 20)
    r1 = _rank(prims.ts_rank(c, 10))
    r2 = _rank(prims.delta(prims.delta(c, 1), 1))
    r3 = _rank(prims.ts_rank(prims.protected_div(v, adv20), 5))
    return prims.neg(prims.mul(prims.mul(r1, r2), r3))


def alpha_018(close, high, low, open_, volume):
    """Alpha#18 = -rank(ts_std(abs(close-open),5) + (close-open) + correlation(close,open,10))"""
    c = _f32(close); o = _f32(open_)
    co = prims.sub(c, o)
    std_abs = prims.ts_std(prims.abs_x(co), 5)
    corr = prims.correlation(c, o, 10)
    return prims.neg(_rank(prims.add(prims.add(std_abs, co), corr)))


def alpha_019(close, high, low, open_, volume):
    """Alpha#19 = -sign((close-delay(close,7)) + delta(close,7)) * (1+rank(1+sum(returns,100)))"""
    c = _f32(close)
    ret = _returns(close)
    d7 = prims.delta(c, 7)
    # (close - delay(close,7)) == delta(close,7); so sum is 2*delta
    term = prims.add(prims.sub(c, _delay(c, 7)), d7)
    sum_r = prims.ts_sum(ret, 100)
    one = np.ones_like(c)
    factor = prims.add(one, _rank(prims.add(one, sum_r)))
    return prims.mul(prims.neg(prims.sign_x(term)), factor)


def alpha_020(close, high, low, open_, volume):
    """Alpha#20 = -rank(open - delay(high,1)) * rank(open - delay(close,1)) * rank(open - delay(low,1))"""
    o = _f32(open_)
    r1 = _rank(prims.sub(o, _delay(_f32(high), 1)))
    r2 = _rank(prims.sub(o, _delay(_f32(close), 1)))
    r3 = _rank(prims.sub(o, _delay(_f32(low), 1)))
    return prims.neg(prims.mul(prims.mul(r1, r2), r3))


def alpha_021(close, high, low, open_, volume):
    """Alpha#21 = conditional mean-crossing indicator"""
    c = _f32(close); v = _f32(volume)
    mean8 = prims.ts_mean(c, 8)
    std8 = prims.ts_std(c, 8)
    mean2 = prims.ts_mean(c, 2)
    adv20 = prims.ts_mean(v, 20)
    vr = prims.protected_div(v, adv20)
    upper = prims.add(mean8, std8)
    lower = prims.sub(mean8, std8)
    out = np.where(upper < mean2, -1.0,
                   np.where(mean2 < lower, 1.0,
                            np.where(vr >= 1.0, 1.0, -1.0)))
    return out.astype(np.float32)


def alpha_022(close, high, low, open_, volume):
    """Alpha#22 = -(delta(correlation(high,volume,5),5) * rank(ts_std(close,20)))"""
    corr = prims.correlation(_f32(high), _f32(volume), 5)
    d_corr = prims.delta(corr, 5)
    r_std = _rank(prims.ts_std(_f32(close), 20))
    return prims.neg(prims.mul(d_corr, r_std))


def alpha_024(close, high, low, open_, volume):
    """Alpha#24 = if delta(mean(close,100),100)/delay(close,100) <= 0.05 then -(close-ts_min(close,100)) else -delta(close,3)"""
    c = _f32(close)
    mean100 = prims.ts_mean(c, 100)
    d_mean = prims.delta(mean100, 100)
    delayed = _delay(c, 100)
    ratio = prims.protected_div(d_mean, delayed)
    branch_true = prims.neg(prims.sub(c, prims.ts_min(c, 100)))
    branch_false = prims.neg(prims.delta(c, 3))
    return np.where(ratio <= 0.05, branch_true, branch_false).astype(np.float32)


def alpha_025(close, high, low, open_, volume):
    """Alpha#25 = rank(-returns * adv20 * vwap * (high-close))"""
    c = _f32(close); h = _f32(high); v = _f32(volume)
    ret = _returns(close)
    adv20 = prims.ts_mean(v, 20)
    vwap = _vwap_proxy(close, high, low)
    hc = prims.sub(h, c)
    prod = prims.mul(prims.mul(prims.mul(prims.neg(ret), adv20), vwap), hc)
    return _rank(prod)


def alpha_026(close, high, low, open_, volume):
    """Alpha#26 = -ts_max(correlation(ts_rank(volume,5), ts_rank(high,5), 5), 3)"""
    tv = prims.ts_rank(_f32(volume), 5)
    th = prims.ts_rank(_f32(high), 5)
    corr = prims.correlation(tv, th, 5)
    return prims.neg(prims.ts_max(corr, 3))


def alpha_028(close, high, low, open_, volume):
    """Alpha#28 = scale(correlation(adv20, low, 5) + (high+low)/2 - close)"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    adv20 = prims.ts_mean(v, 20)
    corr = prims.correlation(adv20, l, 5)
    mid = _f32((h + l) / 2.0)
    return prims.scale(prims.sub(prims.add(corr, mid), c))


def alpha_030(close, high, low, open_, volume):
    """Alpha#30 = (1 - rank(sum of sign(close-delay(close,1..3)))) * sum(volume,5) / sum(volume,20)"""
    c = _f32(close); v = _f32(volume)
    s1 = prims.sign_x(prims.sub(c, _delay(c, 1)))
    s2 = prims.sign_x(prims.sub(_delay(c, 1), _delay(c, 2)))
    s3 = prims.sign_x(prims.sub(_delay(c, 2), _delay(c, 3)))
    sum_sign = prims.add(prims.add(s1, s2), s3)
    ratio = prims.protected_div(prims.ts_sum(v, 5), prims.ts_sum(v, 20))
    return prims.mul(prims.sub(np.ones_like(c), _rank(sum_sign)), ratio)


def alpha_033(close, high, low, open_, volume):
    """Alpha#33 = rank(-(1 - open/close))"""
    return _rank(prims.neg(prims.sub(np.ones_like(_f32(close)),
                                      prims.protected_div(_f32(open_), _f32(close)))))


def alpha_034(close, high, low, open_, volume):
    """Alpha#34 = rank((1-rank(ts_std(ret,2)/ts_std(ret,5))) + (1-rank(delta(close,1))))"""
    ret = _returns(close)
    c = _f32(close)
    ratio = prims.protected_div(prims.ts_std(ret, 2), prims.ts_std(ret, 5))
    t1 = prims.sub(np.ones_like(c), _rank(ratio))
    t2 = prims.sub(np.ones_like(c), _rank(prims.delta(c, 1)))
    return _rank(prims.add(t1, t2))


def alpha_035(close, high, low, open_, volume):
    """Alpha#35 = ts_rank(volume,32) * (1-ts_rank(close+high-low,16)) * (1-ts_rank(returns,32))"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    ret = _returns(close)
    t1 = prims.ts_rank(v, 32)
    chl = _f32(c + h - l)
    t2 = prims.sub(np.ones_like(c), prims.ts_rank(chl, 16))
    t3 = prims.sub(np.ones_like(c), prims.ts_rank(ret, 32))
    return prims.mul(prims.mul(t1, t2), t3)


def alpha_036(close, high, low, open_, volume):
    """Alpha#36 = weighted combo of 5 rank terms"""
    c = _f32(close); o = _f32(open_); v = _f32(volume)
    ret = _returns(close)
    vwap = _vwap_proxy(close, high, low)
    adv20 = prims.ts_mean(v, 20)

    t1 = prims.mul(np.full_like(c, 2.21, dtype=np.float32),
                   _rank(prims.correlation(prims.sub(c, o), _delay(v, 1), 15)))
    t2 = prims.mul(np.full_like(c, 0.7, dtype=np.float32), _rank(prims.sub(o, c)))
    t3 = prims.mul(np.full_like(c, 0.73, dtype=np.float32),
                   _rank(prims.ts_rank(_delay(prims.neg(ret), 6), 5)))
    t4 = _rank(prims.abs_x(prims.correlation(vwap, adv20, 6)))
    mean200 = prims.ts_mean(c, 200)
    t5 = prims.mul(np.full_like(c, 0.6, dtype=np.float32),
                   _rank(prims.mul(prims.sub(mean200, o), prims.sub(c, o))))
    return prims.add(prims.add(prims.add(prims.add(t1, t2), t3), t4), t5)


def alpha_037(close, high, low, open_, volume):
    """Alpha#37 = rank(correlation(delay(open-close,1), close, 200)) + rank(open-close)"""
    c = _f32(close); o = _f32(open_)
    oc = prims.sub(o, c)
    t1 = _rank(prims.correlation(_delay(oc, 1), c, 200))
    t2 = _rank(oc)
    return prims.add(t1, t2)


def alpha_038(close, high, low, open_, volume):
    """Alpha#38 = -rank(ts_rank(close,10)) * rank(close/open)"""
    c = _f32(close); o = _f32(open_)
    return prims.neg(prims.mul(_rank(prims.ts_rank(c, 10)),
                                _rank(prims.protected_div(c, o))))


def alpha_039(close, high, low, open_, volume):
    """Alpha#39 = -rank(delta(close,7)*(1-rank(decay_linear(volume/adv20,9)))) * (1+rank(sum(returns,100)))"""
    c = _f32(close); v = _f32(volume)
    ret = _returns(close)
    adv20 = prims.ts_mean(v, 20)
    dl = prims.decay_linear(prims.protected_div(v, adv20), 9)
    inner = prims.mul(prims.delta(c, 7), prims.sub(np.ones_like(c), _rank(dl)))
    t1 = prims.neg(_rank(inner))
    t2 = prims.add(np.ones_like(c), _rank(prims.ts_sum(ret, 100)))
    return prims.mul(t1, t2)


def alpha_040(close, high, low, open_, volume):
    """Alpha#40 = -rank(ts_std(high,10)) * correlation(high, volume, 10)"""
    h = _f32(high); v = _f32(volume)
    return prims.neg(prims.mul(_rank(prims.ts_std(h, 10)),
                                prims.correlation(h, v, 10)))


def alpha_042(close, high, low, open_, volume):
    """Alpha#42 = rank(vwap-close) / rank(vwap+close)"""
    vwap = _vwap_proxy(close, high, low)
    c = _f32(close)
    num = _rank(prims.sub(vwap, c))
    den = _rank(prims.add(vwap, c))
    return prims.protected_div(num, den)


def alpha_043(close, high, low, open_, volume):
    """Alpha#43 = ts_rank(volume/adv20, 20) * ts_rank(-delta(close,7), 8)"""
    v = _f32(volume); c = _f32(close)
    adv20 = prims.ts_mean(v, 20)
    t1 = prims.ts_rank(prims.protected_div(v, adv20), 20)
    t2 = prims.ts_rank(prims.neg(prims.delta(c, 7)), 8)
    return prims.mul(t1, t2)


def alpha_044(close, high, low, open_, volume):
    """Alpha#44 = -correlation(high, rank(volume), 5)"""
    return prims.neg(prims.correlation(_f32(high), _rank(_f32(volume)), 5))


def alpha_045(close, high, low, open_, volume):
    """Alpha#45 = -(rank(mean(delay(close,5),20)) * correlation(close,volume,2) * rank(correlation(sum(close,5),sum(close,20),2)))"""
    c = _f32(close); v = _f32(volume)
    t1 = _rank(prims.ts_mean(_delay(c, 5), 20))
    t2 = prims.correlation(c, v, 2)
    t3 = _rank(prims.correlation(prims.ts_sum(c, 5), prims.ts_sum(c, 20), 2))
    return prims.neg(prims.mul(prims.mul(t1, t2), t3))


def alpha_046(close, high, low, open_, volume):
    """Alpha#46 = if (delay(close,20)-delay(close,10))/10 - (delay(close,10)-close)/10 > 0.25 then -1
                 elif < 0 then 1 else -(close-delay(close,1))"""
    c = _f32(close)
    term = prims.sub(prims.protected_div(prims.sub(_delay(c, 20), _delay(c, 10)), np.full_like(c, 10.0)),
                     prims.protected_div(prims.sub(_delay(c, 10), c), np.full_like(c, 10.0)))
    diff1 = prims.neg(prims.sub(c, _delay(c, 1)))
    out = np.where(term > 0.25, -1.0, np.where(term < 0, 1.0, diff1))
    return out.astype(np.float32)


def alpha_049(close, high, low, open_, volume):
    """Alpha#49 = if term < -0.1 then 1 else -(close-delay(close,1))"""
    c = _f32(close)
    term = prims.sub(prims.protected_div(prims.sub(_delay(c, 20), _delay(c, 10)), np.full_like(c, 10.0)),
                     prims.protected_div(prims.sub(_delay(c, 10), c), np.full_like(c, 10.0)))
    diff1 = prims.neg(prims.sub(c, _delay(c, 1)))
    return np.where(term < -0.1, np.ones_like(c), diff1).astype(np.float32)


def alpha_051(close, high, low, open_, volume):
    """Alpha#51 = if term < -0.05 then 1 else -(close-delay(close,1))"""
    c = _f32(close)
    term = prims.sub(prims.protected_div(prims.sub(_delay(c, 20), _delay(c, 10)), np.full_like(c, 10.0)),
                     prims.protected_div(prims.sub(_delay(c, 10), c), np.full_like(c, 10.0)))
    diff1 = prims.neg(prims.sub(c, _delay(c, 1)))
    return np.where(term < -0.05, np.ones_like(c), diff1).astype(np.float32)


def alpha_052(close, high, low, open_, volume):
    """Alpha#52 = (-ts_min(low,5) + delay(ts_min(low,5),5)) * rank((sum(returns,240)-sum(returns,20))/220) * ts_rank(volume,5)"""
    l = _f32(low); v = _f32(volume)
    ret = _returns(close)
    tmin5 = prims.ts_min(l, 5)
    t1 = prims.add(prims.neg(tmin5), _delay(tmin5, 5))
    diff_sum = prims.sub(prims.ts_sum(ret, 240), prims.ts_sum(ret, 20))
    t2 = _rank(prims.protected_div(diff_sum, np.full_like(l, 220.0)))
    t3 = prims.ts_rank(v, 5)
    return prims.mul(prims.mul(t1, t2), t3)


def alpha_055(close, high, low, open_, volume):
    """Alpha#55 = -correlation(rank((close - ts_min(low,12)) / (ts_max(high,12) - ts_min(low,12))), rank(volume), 6)"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    tmin = prims.ts_min(l, 12)
    tmax = prims.ts_max(h, 12)
    num = prims.sub(c, tmin)
    den = prims.sub(tmax, tmin)
    ratio = prims.protected_div(num, den)
    return prims.neg(prims.correlation(_rank(ratio), _rank(v), 6))


def alpha_057(close, high, low, open_, volume):
    """Alpha#57 = -(close-vwap) / decay_linear(rank(ts_argmax(close,30)), 2)"""
    c = _f32(close)
    vwap = _vwap_proxy(close, high, low)
    num = prims.sub(c, vwap)
    den = prims.decay_linear(_rank(prims.ts_argmax(c, 30).astype(np.float32)), 2)
    return prims.neg(prims.protected_div(num, den))


def alpha_060(close, high, low, open_, volume):
    """Alpha#60 = -((2*scale(rank(((close-low)-(high-close))/(high-low)*volume))) - scale(rank(ts_argmax(close,10))))"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    num = prims.sub(prims.sub(c, l), prims.sub(h, c))
    den = prims.sub(h, l)
    ratio = prims.mul(prims.protected_div(num, den), v)
    t1 = prims.mul(np.full_like(c, 2.0), prims.scale(_rank(ratio)))
    t2 = prims.scale(_rank(prims.ts_argmax(c, 10).astype(np.float32)))
    return prims.neg(prims.sub(t1, t2))


def alpha_061(close, high, low, open_, volume):
    """Alpha#61 = rank(vwap - ts_min(vwap, 16)) < rank(correlation(vwap, adv20, 18)) cast to {-1,1}"""
    v = _f32(volume)
    vwap = _vwap_proxy(close, high, low)
    adv20 = prims.ts_mean(v, 20)
    t1 = _rank(prims.sub(vwap, prims.ts_min(vwap, 16)))
    t2 = _rank(prims.correlation(vwap, adv20, 18))
    return (t1 < t2).astype(np.float32) * 2.0 - 1.0


def alpha_062(close, high, low, open_, volume):
    """Alpha#62 = -1 if rank(correlation(vwap, sum(adv20,22), 10)) < rank((rank(open) + rank(open)) < (rank((high+low)/2) + rank(high))) else 0"""
    v = _f32(volume); o = _f32(open_); h = _f32(high); l = _f32(low)
    vwap = _vwap_proxy(close, high, low)
    adv20 = prims.ts_mean(v, 20)
    t1 = _rank(prims.correlation(vwap, prims.ts_sum(adv20, 22), 10))
    t2 = prims.add(_rank(o), _rank(o))
    mid = _f32((h + l) / 2.0)
    t3 = prims.add(_rank(mid), _rank(h))
    t4 = (t2 < t3).astype(np.float32)
    t5 = _rank(t4)
    return ((t1 < t5).astype(np.float32) * -1.0).astype(np.float32)


def alpha_064(close, high, low, open_, volume):
    """Alpha#64 = -(rank(correlation(sum(open*0.18+low*0.82,13), sum(adv20,13), 17)) < rank(delta((high+low)/2*0.18 + vwap*0.82, 4)))"""
    v = _f32(volume); o = _f32(open_); h = _f32(high); l = _f32(low)
    vwap = _vwap_proxy(close, high, low)
    adv20 = prims.ts_mean(v, 20)
    comb1 = prims.add(prims.mul(o, np.full_like(o, 0.18)), prims.mul(l, np.full_like(l, 0.82)))
    t1 = _rank(prims.correlation(prims.ts_sum(comb1, 13), prims.ts_sum(adv20, 13), 17))
    mid = _f32((h + l) / 2.0)
    comb2 = prims.add(prims.mul(mid, np.full_like(mid, 0.18)), prims.mul(vwap, np.full_like(vwap, 0.82)))
    t2 = _rank(prims.delta(comb2, 4))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_065(close, high, low, open_, volume):
    """Alpha#65 = -(rank(correlation(open*0.00817+vwap*0.99183, sum(adv20,9), 6)) < rank(open - ts_min(open,14)))"""
    v = _f32(volume); o = _f32(open_)
    vwap = _vwap_proxy(close, high, low)
    adv20 = prims.ts_mean(v, 20)
    comb = prims.add(prims.mul(o, np.full_like(o, 0.00817)),
                     prims.mul(vwap, np.full_like(vwap, 0.99183)))
    t1 = _rank(prims.correlation(comb, prims.ts_sum(adv20, 9), 6))
    t2 = _rank(prims.sub(o, prims.ts_min(o, 14)))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_068(close, high, low, open_, volume):
    """Alpha#68 = -(ts_rank(correlation(rank(high), rank(adv15), 9), 14) < rank(delta(close*0.518+low*0.482, 1)))"""
    v = _f32(volume); c = _f32(close); h = _f32(high); l = _f32(low)
    adv15 = prims.ts_mean(v, 15)
    t1 = prims.ts_rank(prims.correlation(_rank(h), _rank(adv15), 9), 14)
    comb = prims.add(prims.mul(c, np.full_like(c, 0.518)),
                     prims.mul(l, np.full_like(l, 0.482)))
    t2 = _rank(prims.delta(comb, 1))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_071(close, high, low, open_, volume):
    """Alpha#71 = max(ts_rank(decay_linear(correlation(ts_rank(close,3), ts_rank(adv180,12), 18), 4), 16),
                     ts_rank(decay_linear(rank((low+open)-(vwap+vwap))^2, 16), 4))"""
    v = _f32(volume); c = _f32(close); o = _f32(open_); l = _f32(low)
    vwap = _vwap_proxy(close, high, low)
    adv180 = prims.ts_mean(v, 180)
    corr = prims.correlation(prims.ts_rank(c, 3), prims.ts_rank(adv180, 12), 18)
    t1 = prims.ts_rank(prims.decay_linear(corr, 4), 16)
    inner = prims.sub(prims.add(l, o), prims.add(vwap, vwap))
    sq = prims.power(_rank(inner), 2)
    t2 = prims.ts_rank(prims.decay_linear(sq, 16), 4)
    return np.maximum(t1, t2).astype(np.float32)


def alpha_072(close, high, low, open_, volume):
    """Alpha#72 = rank(decay_linear(correlation((high+low)/2, adv40, 9), 10)) / rank(decay_linear(correlation(ts_rank(vwap,4), ts_rank(volume,19), 7), 3))"""
    v = _f32(volume); h = _f32(high); l = _f32(low)
    adv40 = prims.ts_mean(v, 40)
    vwap = _vwap_proxy(close, high, low)
    mid = _f32((h + l) / 2.0)
    t1 = _rank(prims.decay_linear(prims.correlation(mid, adv40, 9), 10))
    t2 = _rank(prims.decay_linear(prims.correlation(prims.ts_rank(vwap, 4), prims.ts_rank(v, 19), 7), 3))
    return prims.protected_div(t1, t2)


def alpha_074(close, high, low, open_, volume):
    """Alpha#74 = -(rank(correlation(close, sum(adv30,37), 15)) < rank(correlation(rank(high*0.026+vwap*0.974), rank(volume), 11)))"""
    v = _f32(volume); c = _f32(close); h = _f32(high)
    adv30 = prims.ts_mean(v, 30)
    vwap = _vwap_proxy(close, high, low)
    t1 = _rank(prims.correlation(c, prims.ts_sum(adv30, 37), 15))
    comb = prims.add(prims.mul(h, np.full_like(h, 0.026)),
                     prims.mul(vwap, np.full_like(vwap, 0.974)))
    t2 = _rank(prims.correlation(_rank(comb), _rank(v), 11))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_078(close, high, low, open_, volume):
    """Alpha#78 = rank(correlation(sum(low*0.352+vwap*0.648,20), sum(adv40,20), 7))^rank(correlation(rank(vwap), rank(volume), 6))"""
    v = _f32(volume); l = _f32(low)
    adv40 = prims.ts_mean(v, 40)
    vwap = _vwap_proxy(close, high, low)
    comb = prims.add(prims.mul(l, np.full_like(l, 0.352)),
                     prims.mul(vwap, np.full_like(vwap, 0.648)))
    base = _rank(prims.correlation(prims.ts_sum(comb, 20), prims.ts_sum(adv40, 20), 7))
    exp_r = _rank(prims.correlation(_rank(vwap), _rank(v), 6))
    # x^y approximated via power (y as scalar doesn't apply; use multiplicative)
    return prims.mul(base, exp_r)


def alpha_083(close, high, low, open_, volume):
    """Alpha#83 = rank(delay((high-low)/mean(close,5), 2)) * rank(rank(volume)) / ((high-low)/mean(close,5) / (vwap-close))"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    vwap = _vwap_proxy(close, high, low)
    mean5 = prims.ts_mean(c, 5)
    hl = prims.sub(h, l)
    ratio = prims.protected_div(hl, mean5)
    t1 = _rank(_delay(ratio, 2))
    t2 = _rank(_rank(v))
    num = prims.mul(t1, t2)
    den = prims.protected_div(ratio, prims.sub(vwap, c))
    return prims.protected_div(num, den)


def alpha_084(close, high, low, open_, volume):
    """Alpha#84 = signed_power(ts_rank(vwap - ts_max(vwap,15), 21), delta(close, 5))
       simplified: signed_power with scalar power 2"""
    c = _f32(close)
    vwap = _vwap_proxy(close, high, low)
    base = prims.ts_rank(prims.sub(vwap, prims.ts_max(vwap, 15)), 21)
    # Use delta(close, 5) as a modulating signal via sign
    delta_sign = prims.sign_x(prims.delta(c, 5))
    return prims.mul(prims.signed_power(base, 2), delta_sign)


def alpha_085(close, high, low, open_, volume):
    """Alpha#85 = rank(correlation(high*0.877+close*0.123, adv30, 10)) * rank(correlation(ts_rank((high+low)/2,4), ts_rank(volume,10), 7))"""
    v = _f32(volume); c = _f32(close); h = _f32(high); l = _f32(low)
    adv30 = prims.ts_mean(v, 30)
    comb = prims.add(prims.mul(h, np.full_like(h, 0.877)),
                     prims.mul(c, np.full_like(c, 0.123)))
    t1 = _rank(prims.correlation(comb, adv30, 10))
    mid = _f32((h + l) / 2.0)
    t2 = _rank(prims.correlation(prims.ts_rank(mid, 4), prims.ts_rank(v, 10), 7))
    return prims.mul(t1, t2)


def alpha_086(close, high, low, open_, volume):
    """Alpha#86 = -(ts_rank(correlation(close, sum(adv20,15), 6), 20) < rank((open+close)-(vwap+open)))"""
    v = _f32(volume); c = _f32(close); o = _f32(open_)
    adv20 = prims.ts_mean(v, 20)
    vwap = _vwap_proxy(close, high, low)
    t1 = prims.ts_rank(prims.correlation(c, prims.ts_sum(adv20, 15), 6), 20)
    t2 = _rank(prims.sub(prims.add(o, c), prims.add(vwap, o)))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_088(close, high, low, open_, volume):
    """Alpha#88 = min(rank(decay_linear(rank(open)+rank(low)-rank(high)-rank(close), 8)),
                     ts_rank(decay_linear(correlation(ts_rank(close,8), ts_rank(adv60,21), 8), 7), 3))"""
    v = _f32(volume); c = _f32(close); o = _f32(open_); h = _f32(high); l = _f32(low)
    adv60 = prims.ts_mean(v, 60)
    t1 = _rank(prims.decay_linear(
        prims.sub(prims.sub(prims.add(_rank(o), _rank(l)), _rank(h)), _rank(c)), 8))
    corr = prims.correlation(prims.ts_rank(c, 8), prims.ts_rank(adv60, 21), 8)
    t2 = prims.ts_rank(prims.decay_linear(corr, 7), 3)
    return np.minimum(t1, t2).astype(np.float32)


def alpha_092(close, high, low, open_, volume):
    """Alpha#92 = min(ts_rank(decay_linear(((high+low)/2 + close < low+open), 15), 19),
                     ts_rank(decay_linear(correlation(rank(low), rank(adv30), 8), 7), 7))"""
    v = _f32(volume); c = _f32(close); o = _f32(open_); h = _f32(high); l = _f32(low)
    adv30 = prims.ts_mean(v, 30)
    mid = _f32((h + l) / 2.0)
    cond = (prims.add(mid, c) < prims.add(l, o)).astype(np.float32)
    t1 = prims.ts_rank(prims.decay_linear(cond, 15), 19)
    corr = prims.correlation(_rank(l), _rank(adv30), 8)
    t2 = prims.ts_rank(prims.decay_linear(corr, 7), 7)
    return np.minimum(t1, t2).astype(np.float32)


def alpha_094(close, high, low, open_, volume):
    """Alpha#94 = -(rank(vwap - ts_min(vwap,12))^ts_rank(correlation(ts_rank(vwap,20), ts_rank(adv60,4), 18), 3))"""
    v = _f32(volume)
    vwap = _vwap_proxy(close, high, low)
    adv60 = prims.ts_mean(v, 60)
    base = _rank(prims.sub(vwap, prims.ts_min(vwap, 12)))
    exp_r = prims.ts_rank(prims.correlation(prims.ts_rank(vwap, 20), prims.ts_rank(adv60, 4), 18), 3)
    return prims.neg(prims.mul(base, exp_r))


def alpha_095(close, high, low, open_, volume):
    """Alpha#95 = (rank(open - ts_min(open,12)) < ts_rank(rank(correlation(sum((high+low)/2,19), sum(adv40,19), 13))^5, 12)) cast"""
    v = _f32(volume); o = _f32(open_); h = _f32(high); l = _f32(low)
    adv40 = prims.ts_mean(v, 40)
    t1 = _rank(prims.sub(o, prims.ts_min(o, 12)))
    mid = _f32((h + l) / 2.0)
    corr = prims.correlation(prims.ts_sum(mid, 19), prims.ts_sum(adv40, 19), 13)
    t2 = prims.ts_rank(prims.power(_rank(corr), 5), 12)
    return ((t1 < t2).astype(np.float32) * 2.0 - 1.0).astype(np.float32)


def alpha_099(close, high, low, open_, volume):
    """Alpha#99 = -(rank(correlation(sum((high+low)/2,20), sum(adv60,20), 9)) < rank(correlation(low, volume, 6)))"""
    v = _f32(volume); h = _f32(high); l = _f32(low)
    adv60 = prims.ts_mean(v, 60)
    mid = _f32((h + l) / 2.0)
    t1 = _rank(prims.correlation(prims.ts_sum(mid, 20), prims.ts_sum(adv60, 20), 9))
    t2 = _rank(prims.correlation(l, v, 6))
    return ((t1 < t2).astype(np.float32) * -1.0).astype(np.float32)


def alpha_100(close, high, low, open_, volume):
    """Alpha#100 = simplified: -scale(correlation(close,volume,5)) - scale(rank((close-low)-(high-close))/(high-low)*volume)"""
    c = _f32(close); h = _f32(high); l = _f32(low); v = _f32(volume)
    t1 = prims.scale(prims.correlation(c, v, 5))
    num = prims.sub(prims.sub(c, l), prims.sub(h, c))
    den = prims.sub(h, l)
    ratio = prims.mul(prims.protected_div(num, den), v)
    t2 = prims.scale(_rank(ratio))
    return prims.neg(prims.add(t1, t2))


# ============================================================
# Registry
# ============================================================

BATCH2_REGISTRY: Dict[str, Callable] = {
    'Alpha#5': alpha_005,
    'Alpha#7': alpha_007,
    'Alpha#8': alpha_008,
    'Alpha#9': alpha_009,
    'Alpha#10': alpha_010,
    'Alpha#11': alpha_011,
    'Alpha#13': alpha_013,
    'Alpha#14': alpha_014,
    'Alpha#15': alpha_015,
    'Alpha#16': alpha_016,
    'Alpha#17': alpha_017,
    'Alpha#18': alpha_018,
    'Alpha#19': alpha_019,
    'Alpha#20': alpha_020,
    'Alpha#21': alpha_021,
    'Alpha#22': alpha_022,
    'Alpha#24': alpha_024,
    'Alpha#25': alpha_025,
    'Alpha#26': alpha_026,
    'Alpha#28': alpha_028,
    'Alpha#30': alpha_030,
    'Alpha#33': alpha_033,
    'Alpha#34': alpha_034,
    'Alpha#35': alpha_035,
    'Alpha#36': alpha_036,
    'Alpha#37': alpha_037,
    'Alpha#38': alpha_038,
    'Alpha#39': alpha_039,
    'Alpha#40': alpha_040,
    'Alpha#42': alpha_042,
    'Alpha#43': alpha_043,
    'Alpha#44': alpha_044,
    'Alpha#45': alpha_045,
    'Alpha#46': alpha_046,
    'Alpha#49': alpha_049,
    'Alpha#51': alpha_051,
    'Alpha#52': alpha_052,
    'Alpha#55': alpha_055,
    'Alpha#57': alpha_057,
    'Alpha#60': alpha_060,
    'Alpha#61': alpha_061,
    'Alpha#62': alpha_062,
    'Alpha#64': alpha_064,
    'Alpha#65': alpha_065,
    'Alpha#68': alpha_068,
    'Alpha#71': alpha_071,
    'Alpha#72': alpha_072,
    'Alpha#74': alpha_074,
    'Alpha#78': alpha_078,
    'Alpha#83': alpha_083,
    'Alpha#84': alpha_084,
    'Alpha#85': alpha_085,
    'Alpha#86': alpha_086,
    'Alpha#88': alpha_088,
    'Alpha#92': alpha_092,
    'Alpha#94': alpha_094,
    'Alpha#95': alpha_095,
    'Alpha#99': alpha_099,
    'Alpha#100': alpha_100,
}


async def validate_and_seed_batch2():
    """Evaluate each batch-2 alpha on all symbols; insert passing alphas to factor_zoo."""
    import asyncpg

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    log.info(f"Batch2 seed: {len(BATCH2_REGISTRY)} alphas x {len(SYMBOLS)} symbols "
             f"= {len(BATCH2_REGISTRY) * len(SYMBOLS)} evaluations")

    conn = await asyncpg.connect(DSN)
    inserted = 0
    evaluated = 0
    top_ics = []

    try:
        for alpha_name, alpha_fn in BATCH2_REGISTRY.items():
            for sym in SYMBOLS:
                path = DATA_DIR / f"{sym}.parquet"
                if not path.exists():
                    continue

                df = pl.read_parquet(str(path))
                n = min(100000, len(df))
                close = df['close'].to_numpy()[-n:].astype(np.float32)
                high = df['high'].to_numpy()[-n:].astype(np.float32)
                low = df['low'].to_numpy()[-n:].astype(np.float32)
                vol = df['volume'].to_numpy()[-n:].astype(np.float32)
                if 'open' in df.columns:
                    open_ = df['open'].to_numpy()[-n:].astype(np.float32)
                else:
                    open_ = close - (close - low) * 0.5

                evaluated += 1
                try:
                    alpha_vals = alpha_fn(close, high, low, open_, vol)
                    if not isinstance(alpha_vals, np.ndarray):
                        continue
                    alpha_vals = np.nan_to_num(alpha_vals, nan=0.0, posinf=0.0, neginf=0.0)
                    if np.std(alpha_vals) < 1e-10:
                        continue

                    fwd = np.zeros(n)
                    fwd[:-1] = (close[1:] - close[:-1]) / np.maximum(close[:-1], 1e-10)

                    valid = np.isfinite(alpha_vals) & np.isfinite(fwd)
                    if valid.sum() < 1000:
                        continue
                    corr, pval = spearmanr(alpha_vals[valid], fwd[valid])
                    if np.isnan(corr):
                        continue
                    ic = float(corr)

                    if abs(ic) < 0.005:
                        continue

                    alpha_hash = hashlib.md5(f"{alpha_name}_{sym}_b2".encode()).hexdigest()[:16]
                    passport = {
                        'arena1': {
                            'alpha_expression': {
                                'formula': f'{alpha_name}({sym})',
                                'source': 'kakushadze_2016_batch2',
                                'alpha_hash': alpha_hash,
                                'ic': ic,
                                'ic_pvalue': float(pval) if not np.isnan(pval) else 1.0,
                                'depth': 4,
                                'used_indicators': [],
                                'used_operators': ['sub', 'mul', 'delta', 'correlation'],
                            },
                            'symbol': sym,
                            'regime': 'MULTI',
                        },
                        'seed_101_b2': {
                            'source': alpha_name,
                            'paper': 'Kakushadze 2016 101 Formulaic Alphas (batch 2)',
                        }
                    }

                    await conn.execute("""
                        INSERT INTO champion_pipeline (
                            regime, indicator_hash, alpha_hash, status, n_indicators,
                            arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                            passport, engine_hash, card_status, evolution_operator,
                            created_at, updated_at
                        ) VALUES (
                            'MULTI', $1, $2, 'DEPLOYABLE', 1,
                            $3, 0.5, 0.0, 0,
                            $4::jsonb, 'zv5_v10_alpha', 'SEED', 'kakushadze_2016_b2',
                            NOW(), NOW()
                        )
                    """, f"alpha_{alpha_hash}_{sym}", alpha_hash, abs(ic), json.dumps(passport, default=str))
                    inserted += 1
                    top_ics.append((abs(ic), ic, alpha_name, sym))
                    log.info(f"  {alpha_name} / {sym}: IC={ic:+.4f} p={pval:.4f} — INSERTED")
                except Exception as e:
                    log.debug(f"  {alpha_name} / {sym}: failed ({e})")
    finally:
        await conn.close()

    top_ics.sort(reverse=True)
    log.info(f"Batch2 complete: evaluated={evaluated}, inserted={inserted}")
    log.info("Top 5 IC results:")
    for abs_ic, ic, name, sym in top_ics[:5]:
        log.info(f"  {name} / {sym}: IC={ic:+.4f}")

    return {"evaluated": evaluated, "inserted": inserted, "top_ics": top_ics[:5]}


if __name__ == "__main__":
    result = asyncio.run(validate_and_seed_batch2())
    print(json.dumps({"evaluated": result["evaluated"], "inserted": result["inserted"],
                      "top_ics": [(float(t[1]), t[2], t[3]) for t in result["top_ics"]]}, indent=2))
