"""Levier contre demande reelle : le test.

Hypotheses posees AVANT de regarder les resultats, avec leur direction attendue.
Les ecrire d'abord est ce qui distingue un test d'une partie de peche.

  H1  OI qui explose pendant la rafale = position nouvelle au levier = froth
      -> on attend une CONTINUATION plus faible, voire un retournement.
  H2  OI qui BAISSE alors que le prix monte = rachat de shorts (squeeze)
      -> mouvement mecanique, s'epuise vite -> continuation faible.
  H3  le spot MENE le perp = vraie demande au comptant
      -> on attend la meilleure continuation.
  H4  prime perp elevee vs son propre historique = tout se passe en derive
      -> froth -> continuation faible.
  H5  participation du spot elevee vs la normale = achat reel -> continuation.
"""
import numpy as np, pandas as pd
from evaluate2 import screen
pd.set_option("display.width", 250)

ev = pd.read_parquet("events_micro.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
base = ev.r_burst > 0.03
print(f"population r_burst>3% : {int(base.sum())} evenements")
for c in ("oi_chg_5m", "spot_lead", "prem_z", "spot_part_rel"):
    print(f"  couverture {c:<15} sur cette population : "
          f"{ev.loc[base, c].notna().mean()*100:.0f} %")

b = ev[base]
q = lambda c, p: b[c].quantile(p)
conds = {
    "base r_burst>3%": base,
    "H1 OI explose (top 25% oi_chg_5m)": base & (ev.oi_chg_5m > q("oi_chg_5m", .75)),
    "H1' OI stable/baisse (bottom 25%)": base & (ev.oi_chg_5m < q("oi_chg_5m", .25)),
    "H2 squeeze : prix+ et OI-":         base & (ev.oi_chg_5m < 0),
    "H3 spot MENE (top 25% spot_lead)":  base & (ev.spot_lead > q("spot_lead", .75)),
    "H3' spot SUIT (bottom 25%)":        base & (ev.spot_lead < q("spot_lead", .25)),
    "H4 prime elevee (prem_z>2)":        base & (ev.prem_z > 2),
    "H4' prime normale (|prem_z|<1)":    base & (ev.prem_z.abs() < 1),
    "H5 spot participe (top 25%)":       base & (ev.spot_part_rel > q("spot_part_rel", .75)),
    "H5' spot absent (bottom 25%)":      base & (ev.spot_part_rel < q("spot_part_rel", .25)),
}
for h in (60, 120):
    print(f"\n=== horizon {h} min, pondere par episode, cout 19 bps ===")
    print(screen(ev, conds, f"fwd_{h}").to_string(index=False))

print("\n### Gradients continus (fwd 120, par episode)")
from evaluate2 import stats
for c in ("oi_chg_5m", "oi_par_prix", "spot_lead", "prem_z", "spot_part_rel", "ls_taker"):
    if b[c].notna().sum() < 500: continue
    t = b.dropna(subset=[c, "fwd_120"]).copy()
    t["_q"] = pd.qcut(t[c], 5, labels=False, duplicates="drop")
    rows = []
    for k, g in t.groupby("_q"):
        s = stats(g, "fwd_120")
        rows.append({"quintile": int(k)+1, "n_ep": s.get("n_ep"), "bps": round(s.get("par_EP_bps", np.nan),1),
                     "t": round(s.get("t_EP", np.nan),2), "IS": round(s.get("IS_EP", np.nan),0),
                     "OOS": round(s.get("OOS_EP", np.nan),0)})
    print(f"\n-- {c} --"); print(pd.DataFrame(rows).to_string(index=False))
