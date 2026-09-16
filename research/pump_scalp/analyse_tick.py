"""La vitesse change-t-elle quelque chose ?

Memes garde-fous que pour tout le reste : ponderation par episode, deux
periodes, retrait des meilleurs mois. Plus une question propre a ce test :
combien de declenchements sont des faux positifs, et le P&L survit-il quand on
les compte tous.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 240)
LAT = [0.2, 2.0, 10.0, 60.0]
COST_NOTE = "frais taker 4,5 bps par cote inclus ; slippage reel par balayage du flux"

d = pd.read_parquet("tick_events.parquet")
d["t"] = pd.to_datetime(d["ts"], unit="s")
d["mois"] = d.t.dt.to_period("M")
print(f"{len(d)} declenchements, {d.symbol.nunique()} symboles, "
      f"{d.t.min():%Y-%m} -> {d.t.max():%Y-%m}")
print(f"mouvement median sur 30 s au declenchement : {d.r_30s.median()*100:.2f} %\n")

def episodes(ts, gap=3600):
    s = ts.sort_values()
    return (s.diff().dt.total_seconds().fillna(1e18) > gap).cumsum().reindex(ts.index)

d["_ep"] = episodes(d.t)
print(f"{d._ep.nunique()} episodes independants ({len(d)/d._ep.nunique():.1f} par episode)\n")

print("=== 1. Rendement forward brut selon la latence (par episode) ===")
rows=[]
for lat in LAT:
    for hz,lab in ((60,"1min"),(300,"5min"),(900,"15min"),(3600,"1h")):
        c=f"fwd_{lat}_{hz}"
        if c not in d.columns: continue
        x=d.dropna(subset=[c])
        ep=x.groupby("_ep")[c].mean()
        rows.append({"latence_s":lat,"horizon":lab,"n_ep":len(ep),
                     "moy_bps":round(ep.mean()*1e4,1),
                     "med_bps":round(ep.median()*1e4,1),
                     "t":round(ep.mean()/(ep.std(ddof=1)/np.sqrt(len(ep))),2)})
print(pd.DataFrame(rows).pivot(index="horizon",columns="latence_s",
                               values=["moy_bps","t"]).to_string())

print("\n=== 2. P&L complet, sortie en temps-tick (stop 1,5%, trail 2%, max 1h) ===")
print(f"    {COST_NOTE}")
rows=[]
for lat in LAT:
    c=f"pnl_{lat}"
    if c not in d.columns: continue
    x=d.dropna(subset=[c]).copy()
    ep=x.groupby("_ep").agg(r=(c,"mean"), t0=("t","first"))
    r=ep.r.to_numpy(); m=ep.groupby(ep.t0.dt.to_period("M")).r.mean()*1e4
    srt=np.sort(m.to_numpy())[::-1]
    rows.append({"latence_s":lat,"n":len(x),"n_ep":len(r),
                 "moy_bps":round(r.mean()*1e4,1),
                 "med_bps":round(np.median(r)*1e4,1),
                 "t":round(r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),2),
                 "gagnants_%":round((x[c]>0).mean()*100,1),
                 "duree_med_s":round(x[f"duree_{lat}"].median()),
                 "mois_pos":f"{int((m>0).sum())}/{len(m)}",
                 "sans_top3":round(srt[3:].mean(),1),
                 "2024-25":round(ep[ep.t0<'2025-09-01'].r.mean()*1e4,1),
                 "2025-26":round(ep[ep.t0>='2025-09-01'].r.mean()*1e4,1)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== 3. Cout de la latence sur le PRIX D'ENTREE ===")
base=d[f"px_in_0.2"]
rows=[]
for lat in LAT[1:]:
    x=(d[f"px_in_{lat}"]/base-1.0).dropna()
    rows.append({"latence_s":lat,"surcout_median_bps":round(x.median()*1e4,2),
                 "surcout_moyen_bps":round(x.mean()*1e4,2),
                 "p90_bps":round(x.quantile(.9)*1e4,1)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== 4. Repartition des issues (latence 2 s) ===")
c="pnl_2.0"
if c in d.columns:
    x=d.dropna(subset=[c])
    q=x[c].quantile([.05,.25,.5,.75,.95])*100
    print("quantiles du P&L (%) :", {f"p{int(k*100)}":round(v,2) for k,v in q.items()})
    print("raisons de sortie :", x["why_2.0"].value_counts().to_dict())
