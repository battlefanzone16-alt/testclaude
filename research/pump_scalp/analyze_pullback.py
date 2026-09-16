import sys
import numpy as np, pandas as pd
from evaluate import screen
pd.set_option("display.width", 250)

# entree en LIMITE : maker 2 bps ; sortie au marche : taker 4.5 + 5 de slippage
COST_PB = (2.0 + 4.5 + 5.0) / 1e4

pb = pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "pb_38.parquet")
pb["entry_time"] = pd.to_datetime(pb["fill_time"])
print(f"{len(pb)} remplissages | attente mediane {pb.attente_min.median():.0f} min "
      f"| amplitude mediane de la rafale {pb.amplitude.median()*100:.1f}%")

conds = {
    "tous les replis": pb.index == pb.index,
    "rafale > 5%": pb.amplitude > 0.05,
    "rafale > 8%": pb.amplitude > 0.08,
    "repli rapide (<15min)": pb.attente_min < 15,
    "repli lent (>=15min)": pb.attente_min >= 15,
    "flux taker acheteur (>0.6)": pb.taker_ratio > 0.60,
    "pas deja etendu (r_60m<5%)": pb.r_60m < 0.05,
    "liquide (>10k$/min)": pb.qv_ref_1d > 10000,
    "rafale>5% + repli rapide": (pb.amplitude > 0.05) & (pb.attente_min < 15),
}
for h in (15, 30, 60, 120):
    print(f"\n-- horizon {h} min (cout {COST_PB*1e4:.1f} bps) --")
    print(screen(pb, conds, f"fwd_{h}", cost=COST_PB).to_string(index=False))

print("\n### Forme du chemin depuis le remplissage (tous replis)")
rows = []
for h in (15, 30, 60, 120):
    rows.append({"h": h, "MFE_moy": pb[f"mfe_{h}"].mean()*1e4,
                 "MAE_moy": pb[f"mae_{h}"].mean()*1e4,
                 "MFE_med": pb[f"mfe_{h}"].median()*1e4,
                 "MAE_med": pb[f"mae_{h}"].median()*1e4})
print(pd.DataFrame(rows).round(0).to_string(index=False))
