"""Features de microstructure : levier, prime perp, participation du spot.

L'hypothese qu'on teste enfin. Un pump peut avoir deux moteurs radicalement
differents, indiscernables sur une kline perp :

  - de la DEMANDE REELLE : on achete le token au comptant, le spot mene, l'open
    interest suit mollement, la prime reste sage. Ca peut durer.
  - du LEVIER : personne n'achete au comptant, tout se passe en perp, l'open
    interest explose, la prime s'envole. C'est un squeeze, ca retombe.

Les klines perp seules ne separent pas les deux. Ces trois sources le font.
"""
from __future__ import annotations

import os, sys, time
import numpy as np, pandas as pd
import bvision
from bvision import CACHE

K = 5


def _load(kind, sym, start, end):
    base = os.path.join(CACHE, kind, sym)
    if not os.path.isdir(base):
        return None
    fr = []
    for f in sorted(os.listdir(base)):
        try:
            d = pd.read_parquet(os.path.join(base, f))
        except Exception:
            continue
        if len(d):
            fr.append(d)
    if not fr:
        return None
    out = pd.concat(fr).sort_index()
    return out[~out.index.duplicated(keep="last")]


def features_for_symbol(sym, ev_sym, start, end):
    perp = bvision.fetch(sym, "1m", start, end)
    if not len(perp):
        return None
    t = pd.DatetimeIndex(pd.to_datetime(ev_sym["signal_time"].to_numpy()))
    out = pd.DataFrame(index=ev_sym.index)

    # --- prime du perp sur l'index spot ------------------------------------
    pr = _load("premium", sym, start, end)
    if pr is not None and len(pr):
        p = pr["prem_close"].astype("float64").reindex(perp.index).ffill(limit=5)
        out["prem_now"] = p.reindex(t).to_numpy()
        out["prem_chg"] = (p - p.shift(K)).reindex(t).to_numpy()
        mu = p.rolling(1440, min_periods=360).mean()
        sd = p.rolling(1440, min_periods=360).std().replace(0, np.nan)
        out["prem_z"] = ((p - mu) / sd).reindex(t).to_numpy()

    # --- participation du marche spot --------------------------------------
    sp = _load("spot", sym, start, end)
    if sp is not None and len(sp):
        sq = sp["quote_volume"].astype("float64").reindex(perp.index).fillna(0)
        sc = sp["close"].astype("float64").reindex(perp.index).ffill(limit=5)
        st = sp["taker_quote"].astype("float64").reindex(perp.index).fillna(0)
        pq = perp["quote_volume"].astype("float64")
        sq_b, pq_b = sq.rolling(K).sum(), pq.rolling(K).sum()
        out["spot_part"] = (sq_b / (sq_b + pq_b).replace(0, np.nan)).reindex(t).to_numpy()
        base_part = (sq.rolling(1440, min_periods=360).sum()
                     / (sq.rolling(1440, min_periods=360).sum()
                        + pq.rolling(1440, min_periods=360).sum()).replace(0, np.nan))
        out["spot_part_rel"] = (out["spot_part"].to_numpy()
                                / base_part.shift(K).reindex(t).to_numpy())
        r_spot = sc / sc.shift(K) - 1.0
        r_perp = perp["close"].astype("float64") / perp["close"].astype("float64").shift(K) - 1.0
        out["spot_lead"] = (r_spot - r_perp).reindex(t).to_numpy()
        out["spot_taker"] = (st.rolling(K).sum() / sq_b.replace(0, np.nan)).reindex(t).to_numpy()

    # --- open interest et positionnement -----------------------------------
    oi = _load("metrics", sym, start, end)
    if oi is not None and len(oi):
        # granularite 5 min -> on reindexe sur la minute en propageant
        o = oi["oi"].astype("float64").reindex(perp.index).ffill(limit=10)
        ov = oi["oi_value"].astype("float64").reindex(perp.index).ffill(limit=10)
        out["oi_chg_5m"] = (o / o.shift(K) - 1.0).reindex(t).to_numpy()
        out["oi_chg_60m"] = (o / o.shift(60) - 1.0).reindex(t).to_numpy()
        out["oi_value"] = ov.reindex(t).to_numpy()
        # le coeur de l'hypothese : prix qui monte AVEC ou SANS nouvelles positions
        r5 = (perp["close"].astype("float64") / perp["close"].astype("float64").shift(K) - 1.0)
        out["oi_par_prix"] = (out["oi_chg_5m"].to_numpy() / r5.reindex(t).to_numpy())
        for c, n in (("cnt_ls", "ls_cnt"), ("sum_top_ls", "ls_top"), ("taker_ls", "ls_taker")):
            if c in oi.columns:
                s = oi[c].astype("float64").reindex(perp.index).ffill(limit=10)
                out[n] = s.reindex(t).to_numpy()
                out[n + "_chg"] = (s - s.shift(60)).reindex(t).to_numpy()
    return out


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2025-09-01")
    p.add_argument("--end", default="2026-09-01")
    p.add_argument("--events", default="events_breadth.parquet")
    p.add_argument("--out", default="events_micro.parquet")
    a = p.parse_args()
    start, end = a.start, a.end
    ev = pd.read_parquet(a.events).reset_index(drop=True)
    ev["signal_time"] = pd.to_datetime(ev["signal_time"])
    ev["entry_time"] = pd.to_datetime(ev["entry_time"])
    parts, t0 = [], time.time()
    for i, (sym, g) in enumerate(ev.groupby("symbol", sort=False), 1):
        try:
            f = features_for_symbol(sym, g, start, end)
        except Exception as e:
            print(f"  {sym}: {e}", file=sys.stderr); f = None
        if f is not None:
            parts.append(f)
        if i % 40 == 0:
            print(f"  {i} symboles ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)
    micro = pd.concat(parts).reindex(ev.index)
    out = pd.concat([ev, micro], axis=1)
    out.to_parquet(a.out, compression="zstd")
    print(f"\n{len(out)} evenements -> {a.out}", file=sys.stderr)
    cov = out[micro.columns].notna().mean().sort_values(ascending=False)
    print("couverture des nouvelles features :", file=sys.stderr)
    print((cov*100).round(1).to_string(), file=sys.stderr)


if __name__ == "__main__":
    main()
