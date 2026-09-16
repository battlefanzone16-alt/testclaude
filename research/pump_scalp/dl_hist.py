"""Extension de l'echantillon : 2024-09 -> 2025-09.

Pourquoi c'est necessaire. Le walk-forward ne dispose que de 6 mois de test sur
12 mois de donnees, et ses politiques de selection ne sont pas d'accord entre
elles (-25 a +142 bps). Avec cet ecart, 6 mois ne tranchent rien. Doubler la
periode donne ~18 mois de test.

Le screen de liquidite est refait sur la periode ancienne : reutiliser tel quel
un univers selectionne sur 2025-2026 pour trader 2024-2025 serait un
look-ahead sur la composition meme de l'univers.
"""
import sys, pandas as pd, bvision
S, E = "2024-09-01", "2025-09-01"
syms = [s.strip() for s in open("symbols_all.txt") if s.strip() and s.strip().isascii()]
print(f"screen 1d sur {len(syms)} symboles, {S} -> {E}", file=sys.stderr)
uni = bvision.fetch_many(syms, "1d", S, E, workers=24, quiet=False)
rows=[]
for s, df in uni.items():
    if len(df) < 90: continue
    qv, dow = df["quote_volume"], df.index.dayofweek
    we, wd = qv[dow>=5], qv[dow<5]
    if len(we)<5 or len(wd)<10 or wd.median()<=0: continue
    rows.append({"symbol": s, "n_days": len(df),
                 "qv_median_musd": float(qv.median())/1e6,
                 "weekend_ratio": float(we.median()/wd.median())})
d = pd.DataFrame(rows)
keep = d[(d.weekend_ratio>=0.40) & (d.qv_median_musd>=3.0) & (d.n_days>=90)]
print(f"{len(keep)} symboles crypto liquides sur 2024-2025", file=sys.stderr)
keep.to_csv("universe_meta_hist.csv", index=False)
old = set(s.strip() for s in open("universe.txt") if s.strip())
union = sorted(set(keep.symbol) | old)
open("universe_hist.txt","w").write("\n".join(sorted(keep.symbol))+"\n")
open("universe_union.txt","w").write("\n".join(union)+"\n")
print(f"union des deux periodes : {len(union)} symboles", file=sys.stderr)
