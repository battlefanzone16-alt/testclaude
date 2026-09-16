"""Le signal 'grappe' est-il reel, ou trois pieges deguises ?

Piege 1 : octobre 2025 / le 10 octobre.
Piege 2 : la taille d'echantillon effective. 1709 evenements qui arrivent tous
          dans les memes 40 minutes ne sont pas 1709 observations independantes.
          C'est UN pari repete, et le t-stat est alors une fiction.
Piege 3 : la capacite. Si 60 signaux tombent la meme minute, un portefeuille a
          3 slots n'en prend que 3 - et ils sont parfaitement correles.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)
COST = 0.0019

ev = pd.read_parquet("events_breadth.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
g = ev[(ev.r_burst > 0.03) & (ev.breadth_z2 > 0.15)].copy()
g["jour"] = g.entry_time.dt.normalize()
g["mois"] = g.entry_time.dt.to_period("M")

print(f"=== PIEGE 1 : concentration temporelle ===")
print(f"{len(g)} evenements sur {g.jour.nunique()} jours distincts")
for h in (60, 120):
    for lab, d in [("tout", g), ("sans le 10 oct", g[g.jour != "2025-10-10"]),
                   ("sans octobre 2025", g[g.mois != "2025-10"])]:
        r = d[f"fwd_{h}"]
        print(f"  fwd{h} {lab:<20} n={len(r):>4}  {r.mean()*1e4:>7.1f} bps  "
              f"net {(r.mean()-COST)*1e4:>7.1f}  "
              f"IS {d[d.entry_time<'2026-03-01'][f'fwd_{h}'].mean()*1e4:>7.1f}  "
              f"OOS {d[d.entry_time>='2026-03-01'][f'fwd_{h}'].mean()*1e4:>7.1f}")

print(f"\n=== PIEGE 2 : taille d'echantillon effective ===")
# on regroupe en 'episodes' : evenements separes de moins de 60 min
g = g.sort_values("entry_time")
gap = g.entry_time.diff().dt.total_seconds().fillna(1e9) / 60
g["episode"] = (gap > 60).cumsum()
print(f"  {len(g)} evenements se regroupent en {g.episode.nunique()} episodes distincts")
ep = g.groupby("episode").agg(n=("fwd_60", "size"), date=("entry_time", "first"),
                              r60=("fwd_60", "mean"), r120=("fwd_120", "mean"))
print(f"  taille mediane d'un episode : {ep.n.median():.0f} evenements")
for h, col in ((60, "r60"), (120, "r120")):
    r = ep[col]
    print(f"  fwd{h} par EPISODE : n={len(r)}  moyenne {r.mean()*1e4:>7.1f} bps  "
          f"t={r.mean()/(r.std(ddof=1)/np.sqrt(len(r))):>5.2f}  "
          f"episodes positifs {(r>0).sum()}/{len(r)}")
print("\n  les 8 plus gros episodes :")
print(ep.nlargest(8, "n").assign(r60=lambda d: (d.r60*1e4).round(0),
                                 r120=lambda d: (d.r120*1e4).round(0)).to_string())
