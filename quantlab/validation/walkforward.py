"""Walk-forward et sélection de paramètres par PLATEAU.

Deux principes, tous deux issus de la méthodologie déjà écrite dans le contexte
v5 :

  - « plateau pas pic » : on ne retient jamais l'argmax d'une grille. On retient
    le point dont le VOISINAGE est bon. Un pic isolé dans un océan de médiocrité
    est du bruit ; un plateau large est un effet.

  - Chaque essai monte la barre du hasard. Le nombre de combinaisons testées est
    compté et transmis au Deflated Sharpe, qui déflate le résultat en
    conséquence.
"""
from __future__ import annotations

import itertools
import numpy as np
import pandas as pd

from ..core.config import Config
from ..core.portfolio import run_universe
from ..core import metrics


def slice_universe(universe: dict, start=None, end=None) -> dict:
    out = {}
    for t, df in universe.items():
        d = df
        if start is not None:
            d = d[d.index >= start]
        if end is not None:
            d = d[d.index < end]
        if len(d) > 250:
            out[t] = d
    return out


def expand_grid(grid: dict) -> list[dict]:
    keys = list(grid.keys())
    return [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]


def _neighbours(combo: dict, grid: dict) -> list[dict]:
    """Combinaisons à un cran de distance sur exactement un axe."""
    out = []
    for k, v in combo.items():
        vals = list(grid[k])
        try:
            i = vals.index(v)
        except ValueError:
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                c = dict(combo)
                c[k] = vals[j]
                out.append(c)
    return out


def evaluate_grid(universe: dict, base_cfg: Config, grid: dict,
                  objective=lambda s: s["sharpe"]) -> pd.DataFrame:
    """Evalue toute la grille sur l'échantillon fourni."""
    rows = []
    # On indexe les combinaisons plutôt que de stocker leurs valeurs brutes : un
    # DataFrame mélangeant None et int recasterait 20 en 20.0, ce qui casse
    # ensuite les paramètres attendus entiers (min_periods, longueurs de fenêtre).
    for cid, combo in enumerate(expand_grid(grid)):
        cfg = base_cfg.copy_with(**combo)
        try:
            st = run_universe(universe, cfg)["stats"]
        except Exception as e:                    # une combinaison peut ne produire aucun trade
            rows.append({"combo_id": cid, "sharpe": np.nan, "n_trades": 0,
                         "score": -np.inf, "error": str(e)})
            continue
        rows.append({"combo_id": cid, "sharpe": st["sharpe"], "cagr": st["cagr"],
                     "max_drawdown": st["max_drawdown"], "n_trades": st["n_trades"],
                     "score": objective(st)})
    df = pd.DataFrame(rows)
    df["params"] = [expand_grid(grid)[c] for c in df["combo_id"]]
    return df


def _key(combo: dict, keys) -> tuple:
    """Clé hashable et stable d'une combinaison (None inclus)."""
    return tuple(repr(combo[k]) for k in keys)


def select_plateau(df: pd.DataFrame, grid: dict, min_trades: int = 100) -> dict:
    """Retient le point dont le VOISINAGE est le meilleur, pas l'argmax.

    Le score d'un point est la moyenne de son voisinage pénalisée par sa
    dispersion : on cherche une zone à la fois haute ET plate. Un pic isolé,
    entouré de mauvais scores, est écarté — c'est du bruit, pas un effet.
    """
    keys = list(grid.keys())
    ok = df[(df["n_trades"].fillna(0) >= min_trades) & np.isfinite(df["score"])]
    if len(ok) == 0:
        ok = df[np.isfinite(df["score"])]
    if len(ok) == 0:
        return {k: grid[k][len(grid[k]) // 2] for k in keys}

    lookup = {_key(r["params"], keys): r["score"] for _, r in ok.iterrows()}
    best, best_val = None, -np.inf
    for _, row in ok.iterrows():
        combo = row["params"]
        vals = [row["score"]]
        for nb in _neighbours(combo, grid):
            k = _key(nb, keys)
            if k in lookup:
                vals.append(lookup[k])
        v = float(np.mean(vals)) - 0.25 * float(np.std(vals))
        if v > best_val:
            best_val, best = v, dict(combo)
    return best


def walk_forward(universe: dict, base_cfg: Config, grid: dict, n_folds: int = 4,
                 train_frac: float = 0.6, selector: str = "plateau",
                 min_trades: int = 100, verbose: bool = True) -> dict:
    """Walk-forward glissant. Seuls les segments OOS sont agrégés.

    Le Sharpe retourné dans `oos_stats` est le SEUL chiffre auquel accorder du
    crédit : chaque segment a été choisi sans voir son propre futur.
    """
    idx = None
    for df in universe.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = pd.DatetimeIndex(sorted(idx))
    n = len(idx)
    if n < 500:
        raise ValueError("Historique trop court pour un walk-forward.")

    n_combos = len(expand_grid(grid))
    fold_len = n // (n_folds + 1)
    oos_chunks, picks = [], []

    for f in range(n_folds):
        tr_start = idx[0]
        tr_end = idx[min(n - 1, fold_len * (f + 1))]
        te_end = idx[min(n - 1, fold_len * (f + 2))]

        train = slice_universe(universe, tr_start, tr_end)
        test = slice_universe(universe, tr_end, te_end)
        if not train or not test:
            continue

        gdf = evaluate_grid(train, base_cfg, grid)
        pick = (select_plateau(gdf, grid, min_trades) if selector == "plateau"
                else dict(gdf.loc[gdf["score"].idxmax(), "params"]))

        cfg = base_cfg.copy_with(**pick)
        oos = run_universe(test, cfg)
        oos_chunks.append(oos["returns"])
        picks.append({"fold": f, "train_end": tr_end, "test_end": te_end, **pick,
                      "oos_sharpe": oos["stats"]["sharpe"],
                      "oos_trades": oos["stats"]["n_trades"]})
        if verbose:
            print(f"  fold {f}: train<{tr_end:%Y-%m-%d}  pick={pick}  "
                  f"OOS Sharpe={oos['stats']['sharpe']:.2f} "
                  f"({oos['stats']['n_trades']} trades)", flush=True)

    if not oos_chunks:
        raise ValueError("Aucun fold exploitable.")
    oos_ret = pd.concat(oos_chunks).sort_index()
    oos_ret = oos_ret[~oos_ret.index.duplicated(keep="first")]

    st = metrics.summary(oos_ret.to_numpy(), periods_per_year=base_cfg.bars_per_year)
    sr_bar = st["sharpe"] / np.sqrt(base_cfg.bars_per_year)
    # Variance des Sharpe à travers les essais : l'intrant du Deflated Sharpe.
    all_sr = evaluate_grid(universe, base_cfg, grid)["sharpe"].dropna().to_numpy()
    var_tr = float(np.var(all_sr / np.sqrt(base_cfg.bars_per_year), ddof=1)) if all_sr.size > 1 else 0.0
    st["deflated_sharpe"] = metrics.deflated_sharpe(
        sr_bar, st["n_bars"], st["skew"], st["kurtosis"], max(2, n_combos), var_tr)
    st["n_trials"] = int(n_combos)

    return {"oos_returns": oos_ret, "oos_stats": st, "picks": pd.DataFrame(picks)}
