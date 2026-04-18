"""V10 Live Signal Provider — fast alpha evaluation for live trading.

Loads top alphas from factor zoo per (symbol, regime) and provides
sub-100μs signal evaluation per bar.
"""
import os, time, logging
from typing import Dict, Optional
import numpy as np

log = logging.getLogger(__name__)


class LiveSignalProvider:
    """Per-symbol alpha signal cache + live evaluator."""
    
    def __init__(self, zoo, ensemble_method: str = 'ic_weighted'):
        self.zoo = zoo
        self.ensemble_method = ensemble_method
        self._ensemble_cache: Dict[tuple, 'AlphaEnsemble'] = {}
        self._last_refresh = 0
        self.refresh_interval_sec = 3600  # refresh hourly
    
    async def get_ensemble(self, symbol: str, regime: str, top_k: int = 20):
        """Get or build ensemble for this symbol/regime."""
        from zangetsu.services.alpha_ensemble import AlphaEnsemble
        
        key = (symbol, regime)
        now = time.time()
        
        if key not in self._ensemble_cache or (now - self._last_refresh) > self.refresh_interval_sec:
            ens = AlphaEnsemble(self.zoo, method=self.ensemble_method, regime=regime)
            await ens.build(top_k=top_k)
            self._ensemble_cache[key] = ens
            self._last_refresh = now
        
        return self._ensemble_cache[key]
    
    async def compute_signal(self, symbol: str, regime: str, 
                              close, high, low, open_arr, volume,
                              indicator_cache: Optional[dict] = None) -> np.ndarray:
        """Return ensemble signal array for live trading."""
        ens = await self.get_ensemble(symbol, regime)
        if not ens.members:
            return np.zeros_like(close, dtype=np.float32)
        return ens.evaluate(close, high, low, open_arr, volume, indicator_cache)
    
    def clear_cache(self):
        self._ensemble_cache.clear()
    
    def stats(self) -> dict:
        return {
            'cached_ensembles': len(self._ensemble_cache),
            'keys': list(self._ensemble_cache.keys()),
            'last_refresh_age_sec': int(time.time() - self._last_refresh) if self._last_refresh else -1,
        }


if __name__ == "__main__":
    import asyncio
    async def _test():
        from zangetsu.services.factor_zoo import FactorZoo
        zoo = FactorZoo()
        provider = LiveSignalProvider(zoo)
        stats_before = await zoo.stats()
        print(f"Zoo stats: {stats_before}")
        print(f"Provider stats: {provider.stats()}")
    asyncio.run(_test())
