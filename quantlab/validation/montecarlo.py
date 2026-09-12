"""Suite Monte Carlo.

Quatre tests indépendants, qui ne répondent PAS à la même question :

  A. Bootstrap par blocs des rendements   -> "le Sharpe est-il significatif
     (stationnaire)"                          compte tenu de la taille d'échantillon ?"
  B. Permutation de l'ordre des trades    -> "le drawdown observé est-il de la
                                              chance de séquencement ?"
  C. Entrées aléatoires à exposition égale-> "l'ENTREE a-t-elle un edge, ou est-ce
                                              juste de l'exposition au marché ?"
  D. Re-run sur chemins de prix rééchantillonnés -> "les REGLES tiennent-elles sur
                                              un marché qui aurait pu se produire ?"

C et D sont les deux qui coûtent cher et qui tuent les stratégies overfittées.
Un système qui ne passe que A et B n'est pas validé.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..core import metrics


def stationary_bootstrap_indices(n: int, rng, mean_block: float):
    """Indices d'un bootstrap stationnaire (Politis & Romano) — blocs de longueur
    géométrique, ce qui préserve l'autocorrélation sans fixer une taille de bloc."""
    p = 1.0 / max(2.0, mean_block)
    idx = np.empty(n, dtype=np.int64)
    i = rng.integers(0, n)
    for t in range(n):
        idx[t] = i
        if rng.random() < p:
            i = rng.integers(0, n)
        else:
            i = (i + 1) % n
    return idx


def test_a_block_bootstrap(returns, periods_per_year, n_iter=2000, mean_block=30, seed=0):
    """Distribution du Sharpe sous rééchantillonnage par blocs."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    rng = np.random.default_rng(seed)
    obs = metrics.sharpe(r, periods_per_year)
    sims = np.empty(n_iter)
    for k in range(n_iter):
        sims[k] = metrics.sharpe(r[stationary_bootstrap_indices(r.size, rng, mean_block)],
                                 periods_per_year)
    return {
        "test": "A_block_bootstrap",
        "observed_sharpe": float(obs),
        "mean": float(sims.mean()),
        "p05": float(np.percentile(sims, 5)),
        "p50": float(np.percentile(sims, 50)),
        "p95": float(np.percentile(sims, 95)),
        # Probabilité que le vrai Sharpe soit <= 0.
        "p_value_le_zero": float((sims <= 0).mean()),
        "prob_sharpe_gt_1_5": float((sims > 1.5).mean()),
        "distribution": sims,
    }


def test_b_trade_shuffle(trades: pd.DataFrame, n_iter=2000, seed=0, col="pnl_frac"):
    """Permutation de l'ordre des trades : distribution du MDD et du PF.

    Le P&L total est invariant par permutation ; ce qui bouge, c'est le CHEMIN.
    Un MDD observé dans la queue haute de la distribution = on a eu de la chance
    sur l'ordre, le vrai risque est pire.
    """
    if trades is None or len(trades) == 0 or col not in trades:
        return {"test": "B_trade_shuffle", "error": "pas de trades"}
    p = trades[col].to_numpy(float)
    p = p[np.isfinite(p)]
    if p.size < 10:
        return {"test": "B_trade_shuffle", "error": "trop peu de trades"}

    rng = np.random.default_rng(seed)
    obs_mdd = metrics.max_drawdown(p)
    mdds = np.empty(n_iter)
    ruin = 0
    for k in range(n_iter):
        s = rng.permutation(p)
        mdds[k] = metrics.max_drawdown(s)
        if float(np.prod(1.0 + s)) <= 0.5:      # -50% de capital
            ruin += 1
    return {
        "test": "B_trade_shuffle",
        "observed_mdd": float(obs_mdd),
        "mdd_p50": float(np.percentile(mdds, 50)),
        "mdd_p95": float(np.percentile(mdds, 95)),
        "mdd_p99": float(np.percentile(mdds, 99)),
        # Percentile du MDD observé : bas = on a été chanceux sur la séquence.
        "observed_mdd_percentile": float((mdds < obs_mdd).mean()),
        "prob_drawdown_gt_50pct": float(ruin / n_iter),
        "distribution": mdds,
    }


def test_c_random_entries(universe, cfg, observed_trades: pd.DataFrame,
                          n_iter=200, seed=0):
    """Entrées aléatoires, MEME logique de sortie, MEME nombre de trades par token.

    Si le Sharpe réel n'est pas nettement au-dessus de cette distribution,
    l'entrée Kalman n'apporte rien : on est payé pour de l'exposition, pas pour
    du signal.
    """
    from ..core.engine import compute_signals
    from ..core.portfolio import run_portfolio

    rng = np.random.default_rng(seed)
    counts = (observed_trades.groupby("token").size().to_dict()
              if len(observed_trades) else {})
    sims = np.empty(n_iter)

    for k in range(n_iter):
        results = []
        for token, df in universe.items():
            n_tr = counts.get(token, 0)
            if n_tr == 0:
                continue
            results.append(_random_entry_token(df, cfg, token, n_tr, rng, compute_signals))
        if not results:
            sims[k] = 0.0
            continue
        sims[k] = run_portfolio(results, cfg)["stats"]["sharpe"]

    return {"test": "C_random_entries", "n_iter": n_iter,
            "mean": float(sims.mean()), "p50": float(np.percentile(sims, 50)),
            "p95": float(np.percentile(sims, 95)), "p99": float(np.percentile(sims, 99)),
            "distribution": sims}


def _random_entry_token(df, cfg, token, n_trades, rng, compute_signals):
    """Rejoue le token avec des dates d'entrée tirées au hasard."""
    s = compute_signals(df, cfg)
    n = len(df)
    close, high, low, med = s["close"], s["high"], s["low"], s["median"]
    cost = cfg.cost_per_side_frac()
    lev_signed = np.zeros(n)
    cost_frac = np.zeros(n)
    trades = []

    start = max(cfg.dc_length + cfg.pvt_right + 5, 60)
    if n - start < 50 or n_trades == 0:
        px = np.zeros(n); px[1:] = close[1:] / close[:-1] - 1.0
        return {"token": token, "trades": pd.DataFrame(), "index": df.index,
                "lev_signed": lev_signed, "cost_frac": cost_frac,
                "px_ret": np.nan_to_num(px), "bar_ret": np.zeros(n), "signals": s}

    cand = np.sort(rng.choice(np.arange(start, n - 2), size=min(n_trades, n - start - 2),
                              replace=False))
    last_exit = -1
    for i in cand:
        if i <= last_exit or not np.isfinite(med[i]):
            continue
        side = 1 if rng.random() < 0.5 else -1
        if side > 0 and not cfg.enable_long:
            continue
        if side < 0 and not cfg.enable_short:
            continue
        entry = close[i]
        sl = low[i] if side > 0 else high[i]
        if not np.isfinite(sl) or entry <= 0:
            continue
        sl_dist = side * (entry - sl) / entry
        if not (sl_dist > 0):
            continue
        if cfg.max_sl_dist is not None and sl_dist > cfg.max_sl_dist:
            continue
        lev = min(cfg.risk_pct / sl_dist, cfg.max_lev)

        exit_idx, exit_px = None, None
        for j in range(i + 1, n):
            if (low[j] <= sl) if side > 0 else (high[j] >= sl):
                exit_idx, exit_px = j, sl
                break
            if cfg.exit_on_median and np.isfinite(med[j]):
                if (side > 0 and close[j] < med[j]) or (side < 0 and close[j] > med[j]):
                    exit_idx, exit_px = j, close[j]
                    break
        if exit_idx is None:
            exit_idx, exit_px = n - 1, close[n - 1]

        lev_signed[i + 1: exit_idx + 1] = side * lev
        cost_frac[i] += lev * cost
        cost_frac[exit_idx] += lev * cost
        net = side * (exit_px - entry) / entry - 2.0 * cost
        trades.append({"token": token, "pnl_frac": net * lev, "R": net / sl_dist})
        last_exit = exit_idx

    px = np.zeros(n); px[1:] = close[1:] / close[:-1] - 1.0
    px = np.nan_to_num(px)
    return {"token": token, "trades": pd.DataFrame(trades), "index": df.index,
            "lev_signed": lev_signed, "cost_frac": cost_frac,
            "px_ret": px, "bar_ret": lev_signed * px - cost_frac, "signals": s}


def resample_ohlcv_blocks(df: pd.DataFrame, rng, mean_block: float = 60) -> pd.DataFrame:
    """Reconstruit une série OHLCV en rééchantillonnant les rendements par blocs.

    On rééchantillonne les rendements log ET la géométrie de la bougie
    (mèches relatives), puis on recompose des prix cohérents. Le résultat est un
    marché « qui aurait pu arriver » avec les mêmes propriétés statistiques.
    """
    c = df["close"].to_numpy(float)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    n = len(df)
    if n < 20:
        return df.copy()

    logret = np.diff(np.log(c), prepend=np.log(c[0]))
    up_w = np.divide(h, np.maximum(o, c), out=np.ones(n), where=np.maximum(o, c) > 0)
    dn_w = np.divide(l, np.minimum(o, c), out=np.ones(n), where=np.minimum(o, c) > 0)

    idx = stationary_bootstrap_indices(n, rng, mean_block)
    r = logret[idx]
    new_c = c[0] * np.exp(np.cumsum(r))
    new_o = np.concatenate(([c[0]], new_c[:-1]))
    mx = np.maximum(new_o, new_c)
    mn = np.minimum(new_o, new_c)
    new_h = mx * np.maximum(1.0, up_w[idx])
    new_l = mn * np.minimum(1.0, dn_w[idx])
    return pd.DataFrame({"open": new_o, "high": new_h, "low": new_l, "close": new_c,
                         "volume": df["volume"].to_numpy()}, index=df.index)


def test_d_resampled_paths(universe, cfg, n_iter=200, seed=0, mean_block=60,
                           progress=False):
    """Rejoue TOUTE la stratégie (indicateurs compris) sur des marchés rééchantillonnés.

    C'est le test le plus dur : il casse les coïncidences de dates sur lesquelles
    un système overfitté s'appuie, tout en gardant vol clustering et queues.
    """
    from ..core.portfolio import run_universe
    rng = np.random.default_rng(seed)
    sims = np.empty(n_iter)
    for k in range(n_iter):
        synth = {t: resample_ohlcv_blocks(df, rng, mean_block) for t, df in universe.items()}
        sims[k] = run_universe(synth, cfg)["stats"]["sharpe"]
        if progress and (k + 1) % max(1, n_iter // 10) == 0:
            print(f"    [D] {k+1}/{n_iter}  Sharpe median courant "
                  f"{np.median(sims[:k+1]):.2f}", flush=True)
    return {"test": "D_resampled_paths", "n_iter": n_iter,
            "mean": float(sims.mean()), "p50": float(np.percentile(sims, 50)),
            "p05": float(np.percentile(sims, 5)), "p95": float(np.percentile(sims, 95)),
            "prob_positive": float((sims > 0).mean()),
            "distribution": sims}
