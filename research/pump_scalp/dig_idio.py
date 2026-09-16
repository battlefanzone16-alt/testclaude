"""La population idiosyncratique : peut-on l'ameliorer avec ce qu'on a deja ?

Seul le filtre 'le token pump SEUL' garde le meme signe en IS et en OOS une fois
pondere par episode (+22,4 / +16,5 bps a 60 min). C'est la premisse de depart de
l'utilisateur, et c'est la seule base sur laquelle il vaille la peine d'empiler
quelque chose. Le cout a battre reste 19 bps.
"""
import numpy as np, pandas as pd
from evaluate2 import screen
pd.set_option("display.width", 250)

ev = pd.read_parquet("events_breadth.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
idio = (ev.r_burst > 0.03) & (ev.breadth_z2 < 0.01)
print(f"population de base : {int(idio.sum())} evenements\n")

conds = {"idio (base)": idio}
for lab, m in [
    ("taker acheteur >0,6", ev.taker_ratio > 0.60),
    ("taker acheteur >0,7", ev.taker_ratio > 0.70),
    ("volume x>5", ev.vol_mult > 5),
    ("volume x>10", ev.vol_mult > 10),
    ("z>4", ev.z_burst > 4),
    ("z>6", ev.z_burst > 6),
    ("casse le haut 60m", ev.break60 > 0),
    ("pas etendu (r_60m<3%)", ev.r_60m < 0.03),
    ("deja etendu (r_60m>6%)", ev.r_60m > 0.06),
    ("liquide >20k$/min", ev.qv_ref_1d > 20000),
    ("peu liquide <10k$/min", ev.qv_ref_1d < 10000),
    ("BTC calme (|r_btc|<0,1%)", ev.r_btc.abs() < 0.001),
    ("marche en baisse (mkt_r5<0)", ev.mkt_r5 < 0),
]:
    conds[f"  + {lab}"] = idio & m
for h in (60, 120):
    print(f"\n--- horizon {h} min (pondere par episode, cout 19 bps) ---")
    d = screen(ev, conds, f"fwd_{h}")
    print(d.to_string(index=False))
    if h == 60:
        ok = d[(d.IS_EP > 0) & (d.OOS_EP > 0) & (d.n_ep > 150)]
        print(f"\n  -> filtres avec IS ET OOS positifs : {len(ok)}/{len(d)}")
        if len(ok): print(ok[["filtre","n_ep","net_EP_bps","t_EP","IS_EP","OOS_EP"]].to_string(index=False))
