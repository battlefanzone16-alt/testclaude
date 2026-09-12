"""Agrégation portefeuille.

Le Sharpe est une statistique de PORTEFEUILLE. Le système v5 mesurait des
médianes par token, ce qui jette toute la diversification — c'est précisément
ce qui manquait pour parler de Sharpe.

Trois transformations de risque sont appliquées, toutes causales :
  1. Cap d'exposition brute (scaling pro-rata quand la somme des |leviers| déborde)
  2. Cap du nombre de positions simultanées (les plus anciennes gardées)
  3. Vol targeting sur vol réalisée glissante (fenêtre passée uniquement)

Le coût de la variation du multiplicateur de vol targeting est facturé
(turnover de rééquilibrage), pour ne pas s'offrir un Sharpe gratuit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from . import metrics


def build_matrices(results: list[dict]) -> dict:
    """Aligne les sorties par token sur un index commun."""
    results = [r for r in results if r is not None and len(r["index"]) > 0]
    if not results:
        raise ValueError("Aucun résultat de token à agréger.")
    idx = results[0]["index"]
    for r in results[1:]:
        idx = idx.union(r["index"])
    idx = pd.DatetimeIndex(sorted(idx))

    tokens = [r["token"] for r in results]
    L = pd.DataFrame(0.0, index=idx, columns=tokens)
    C = pd.DataFrame(0.0, index=idx, columns=tokens)
    P = pd.DataFrame(0.0, index=idx, columns=tokens)
    for r in results:
        L.loc[r["index"], r["token"]] = r["lev_signed"]
        C.loc[r["index"], r["token"]] = r["cost_frac"]
        P.loc[r["index"], r["token"]] = r["px_ret"]
    return {"index": idx, "tokens": tokens, "L": L, "C": C, "P": P}


def _cap_positions(L: np.ndarray, max_positions: int | None) -> np.ndarray:
    """Limite le nombre de positions simultanées, priorité aux plus anciennes."""
    if max_positions is None:
        return L
    out = L.copy()
    n, m = L.shape
    age = np.zeros(m)
    for t in range(n):
        active = np.nonzero(L[t] != 0)[0]
        age[L[t] == 0] = 0
        age[L[t] != 0] += 1
        if active.size > max_positions:
            # On garde celles ouvertes depuis le plus longtemps.
            keep = active[np.argsort(-age[active])[:max_positions]]
            mask = np.zeros(m, dtype=bool)
            mask[keep] = True
            out[t, ~mask] = 0.0
    return out


def _cap_net(L: np.ndarray, max_net: float | None) -> np.ndarray:
    """Borne l'exposition NETTE en dégonflant le côté dominant.

    Un système de tendance gagne en étant net long en bull et net short en bear :
    on ne neutralise donc PAS le book. On borne seulement le bêta marché pour
    éviter qu'une cassure synchronisée sur 40 alts ne devienne un pari
    directionnel géant sur BTC.
    """
    if max_net is None:
        return L
    out = L.copy()
    net = out.sum(axis=1)
    over = np.abs(net) > max_net
    if not over.any():
        return out
    for t in np.nonzero(over)[0]:
        row = out[t]
        dom = row > 0 if net[t] > 0 else row < 0
        dom_sum = row[dom].sum()
        excess = net[t] - np.sign(net[t]) * max_net
        if abs(dom_sum) > 1e-12:
            row[dom] *= max(0.0, 1.0 - excess / dom_sum)
        out[t] = row
    return out


def run_portfolio(results: list[dict], cfg: Config) -> dict:
    """Construit la courbe d'équité portefeuille et ses statistiques."""
    M = build_matrices(results)
    idx = M["index"]
    L = M["L"].to_numpy(float)
    C = M["C"].to_numpy(float)
    P = M["P"].to_numpy(float)

    L = _cap_positions(L, cfg.max_positions)
    # Les coûts ne doivent porter que sur les positions effectivement retenues.
    C = np.where(L != 0, C, np.where(np.roll(L, 1, axis=0) != 0, C, 0.0))

    L = _cap_net(L, cfg.max_net)
    gross = np.abs(L).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cap_scale = np.where(gross > cfg.max_gross, cfg.max_gross / np.maximum(gross, 1e-12), 1.0)

    raw = (L * P).sum(axis=1) - C.sum(axis=1)
    raw_scaled = raw * cap_scale

    # --- vol targeting causal ---
    if cfg.vol_target_annual is None:
        vol_mult = np.ones_like(raw_scaled)
    else:
        s = pd.Series(raw_scaled)
        # shift(1) : la vol du jour t n'est connue qu'après t, on n'utilise que t-1.
        rv = s.rolling(cfg.vol_lookback_bars, min_periods=max(20, cfg.vol_lookback_bars // 4)) \
              .std(ddof=1).shift(1).to_numpy()
        ann = rv * np.sqrt(cfg.bars_per_year)
        with np.errstate(divide="ignore", invalid="ignore"):
            vol_mult = np.where(np.isfinite(ann) & (ann > 1e-9),
                                cfg.vol_target_annual / ann, 1.0)
        vol_mult = np.clip(np.nan_to_num(vol_mult, nan=1.0), 0.0, cfg.vol_scale_cap)

    total_scale = cap_scale * vol_mult
    # Coût du rééquilibrage induit par la variation du multiplicateur.
    d_scale = np.abs(np.diff(total_scale, prepend=total_scale[0]))
    rebal_cost = d_scale * gross * cfg.cost_per_side_frac()

    port_ret = raw * total_scale - rebal_cost

    eq = metrics.equity_curve(port_ret)
    stats = metrics.summary(port_ret, periods_per_year=cfg.bars_per_year)
    stats["max_gross_observed"] = float(gross.max()) if gross.size else 0.0
    stats["avg_gross"] = float(gross.mean()) if gross.size else 0.0
    stats["avg_n_positions"] = float((L != 0).sum(axis=1).mean())
    stats["exposure"] = float((gross > 0).mean())
    net_abs = np.abs(L.sum(axis=1))
    stats["avg_net"] = float(net_abs.mean())
    stats["max_net_observed"] = float(net_abs.max()) if net_abs.size else 0.0

    all_trades = [r["trades"] for r in results if len(r["trades"])]
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    stats["n_trades"] = int(len(trades))

    return {"returns": pd.Series(port_ret, index=idx), "equity": pd.Series(eq, index=idx),
            "stats": stats, "trades": trades, "gross": pd.Series(gross, index=idx),
            "scale": pd.Series(total_scale, index=idx), "matrices": M}


def run_universe(universe: dict, cfg: Config, tokens: list[str] | None = None) -> dict:
    """Backtest tout l'univers puis agrège."""
    from .engine import backtest_token
    names = tokens if tokens is not None else list(universe.keys())
    names = [t for t in names if t not in cfg.exclude_tokens]
    results = []
    for t in names:
        df = universe[t]
        if len(df) < 250:
            continue
        results.append(backtest_token(df, cfg, t))
    return run_portfolio(results, cfg)
