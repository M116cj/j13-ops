"""Champion passport — progressive JSONB enrichment per arena."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ChampionPassport:
    def __init__(self, indicator_hash: str, regime: str, engine_hash: str):
        self._data = {
            "indicator_hash": indicator_hash,
            "regime": regime,
            "engine_hash": engine_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "5.0",
        }

    def stamp_arena1(self, indicator_configs, n_indicators, base_wr, base_pnl,
                     base_weighted_pnl, base_score, base_n_trades, round_number,
                     symbol, parent_hash=None, generation=0, evolution_operator="random"):
        self._data["arena1"] = {
            "indicator_configs": indicator_configs,
            "n_indicators": n_indicators,
            "base_win_rate": base_wr,
            "base_pnl": base_pnl,
            "base_weighted_pnl": base_weighted_pnl,
            "base_score": base_score,
            "base_n_trades": base_n_trades,
            "base_agreement_threshold": 0.80,
            "arena1_round": round_number,
            "arena1_regime": self._data["regime"],
            "arena1_symbol": symbol,
            "parent_hash": parent_hash,
            "generation": generation,
            "evolution_operator": evolution_operator,
        }

    def stamp_arena2(self, entry_thr, exit_thr, signal_strength_min,
                     signal_strength_grade, optimized_wr, optimized_pnl,
                     optimized_n_trades, champion_type):
        self._data["arena2"] = {
            "optimized_entry_threshold": entry_thr,
            "optimized_exit_threshold": exit_thr,
            "signal_strength_min": signal_strength_min,
            "signal_strength_grade": signal_strength_grade,
            "optimized_win_rate": optimized_wr,
            "optimized_pnl": optimized_pnl,
            "optimized_n_trades": optimized_n_trades,
            "champion_type": champion_type,
        }

    def stamp_arena3(self, atr_multiplier, tp_trailing_pct, tp_fixed_target_pct,
                     tp_no_tp, half_kelly, sharpe, expectancy, cumulative_pnl,
                     n_trades, win_rate, avg_win, avg_loss, profit_factor, max_drawdown):
        self._data["arena3"] = {
            "atr_multiplier": atr_multiplier,
            "voting_decay_exit_threshold": 0.80,
            "exit_mode": "binary",
            "tp_trailing_pct": tp_trailing_pct,
            "tp_fixed_target_pct": tp_fixed_target_pct,
            "tp_no_tp": tp_no_tp,
            "half_kelly": half_kelly,
            "sharpe_ratio": sharpe,
            "expectancy": expectancy,
            "cumulative_pnl": cumulative_pnl,
            "n_trades": n_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
        }

    def stamp_arena4(self, signal_grade_profile, recommended_min_grade,
                     walk_forward_win_rates, walk_forward_pnls, variability,
                     hell_win_rate, hell_pnl, hell_n_trades, quant_class):
        self._data["arena4"] = {
            "signal_grade_profile": signal_grade_profile,
            "recommended_min_grade": recommended_min_grade,
            "walk_forward_win_rates": walk_forward_win_rates,
            "walk_forward_pnls": walk_forward_pnls,
            "variability": variability,
            "hell_win_rate": hell_win_rate,
            "hell_pnl": hell_pnl,
            "hell_n_trades": hell_n_trades,
            "quant_class": quant_class,
        }

    def stamp_alpha_expression(self, alpha_result: dict):
        """Stamp a GP-discovered alpha expression into the passport (V9 X7).

        `alpha_result` may be either an `AlphaResult.to_passport_dict()`
        payload (keys: formula/ast/ic/sharpe/stability/complexity/hash/
        generation) or an `AlphaResult.to_dict()` payload (keys use `ast_json`
        instead of `ast`). We normalize to a canonical shape so downstream
        live-trade loaders can rely on a stable schema.
        """
        if not isinstance(alpha_result, dict):
            raise TypeError(
                f"stamp_alpha_expression: expected dict, got {type(alpha_result).__name__}"
            )
        if "formula" not in alpha_result:
            raise ValueError("stamp_alpha_expression: missing 'formula'")

        ast_payload = alpha_result.get("ast")
        if ast_payload is None:
            ast_payload = alpha_result.get("ast_json")
        if ast_payload is None:
            raise ValueError("stamp_alpha_expression: missing 'ast' / 'ast_json'")

        self._data["alpha_expression"] = {
            "formula": str(alpha_result["formula"]),
            "ast": ast_payload,
            "metrics": {
                "ic": float(alpha_result.get("ic", 0.0) or 0.0),
                "sharpe": float(alpha_result.get("sharpe", 0.0) or 0.0),
                "stability": float(alpha_result.get("stability", 0.0) or 0.0),
                "complexity": int(alpha_result.get("complexity", 0) or 0),
            },
            "hash": str(alpha_result.get("hash", "") or ""),
            "generation": int(alpha_result.get("generation", 0) or 0),
            "stamped_at": datetime.now(timezone.utc).isoformat(),
            "schema": "alpha_expression.v1",
        }

    def stamp_arena5(self, elo_rating, rounds_played, wins, losses, draws, rank, is_active):
        self._data["arena5"] = {
            "elo_rating": elo_rating,
            "elo_rounds_played": rounds_played,
            "elo_wins": wins,
            "elo_losses": losses,
            "elo_draws": draws,
            "elo_last_reset": datetime.now(timezone.utc).isoformat(),
            "elo_rank_in_regime": rank,
            "is_active_card": is_active,
        }

    def to_jsonb(self) -> dict:
        return self._data

    def validate(self) -> list:
        errors = []
        if "arena1" not in self._data:
            errors.append("missing arena1 stamp")
        if "arena2" in self._data and "arena1" not in self._data:
            errors.append("arena2 without arena1")
        if "arena3" in self._data and "arena2" not in self._data:
            errors.append("arena3 without arena2")
        if "arena4" in self._data and "arena3" not in self._data:
            errors.append("arena4 without arena3")
        return errors

    @classmethod
    def from_jsonb(cls, data: dict) -> "ChampionPassport":
        p = cls.__new__(cls)
        p._data = data
        return p
