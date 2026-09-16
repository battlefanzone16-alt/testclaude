"""Backtest final : une regle FIXE, issue de l'enseignement sur l'open interest.

Pourquoi une regle fixe et non la selection glissante. Le walk-forward re-choisit
sa regle chaque mois et en change 5 fois sur 17 : cette instabilite est le signe
qu'il suit le bruit. Ce qui a resiste, en revanche, c'est l'apport de l'OI - il
ameliore les 5 politiques de selection sans exception. On fige donc UNE regle
simple portant cet enseignement, et on la juge sur 24 mois avec le moteur
complet : stop, trailing, time stop, 3 positions, couts taker, convention
intra-barre conservatrice.
"""
import itertools
import numpy as np, pandas as pd
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net
from evaluate2 import episodes
pd.set_option("display.width", 240)

ev = pd.read_parquet("events_tail24.parquet"); ev["entry_time"]=pd.to_datetime(ev["entry_time"])
z = np.load("paths24.npz")
O,H,L,ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]
risk = np.clip(ev["sigma_ref"].to_numpy()*np.sqrt(5.)*4.0, 0.003, 0.15)
oi = ev.oi_chg_5m.to_numpy(); zb = ev.z_burst.to_numpy()

REGLES = {
    "A. reference : r_burst>3% seul":            ok,
    "B. + z>3":                                  ok & (zb > 3),
    "C. + OI > +0,5% / 5min":                    ok & (zb > 3) & (oi > 0.005),
    "D. + OI > +1% / 5min":                      ok & (zb > 3) & (oi > 0.01),
    "E. + OI > +2% / 5min":                      ok & (zb > 3) & (oi > 0.02),
    "F. controle : OI <= 0 (l'inverse)":         ok & (zb > 3) & (oi <= 0),
}

def bt(mask, rules, sizing=0.05):
    idx = np.flatnonzero(mask & np.isfinite(oi))
    if len(idx) < 60: return None
    r_, eb, why = simulate_batch(O[idx],H[idx],L[idx],risk[idx],rules)
    t = pd.DataFrame({"symbol":ev.symbol.to_numpy()[idx],"entry_time":ev.entry_time.to_numpy()[idx],
                      "hold":eb,"brut":r_,"net":net(r_,rules),"z":zb[idx]}).dropna(subset=["brut"])
    t["exit_time"]=t.entry_time+pd.to_timedelta(t.hold,unit="m")
    t=t.sort_values(["entry_time","z"],ascending=[True,False]).reset_index(drop=True)
    t=t[portfolio(t,max_concurrent=3)]
    if len(t)<60: return None
    r=t.net.to_numpy()
    t["_ep"]=episodes(t.entry_time)
    ep=t.groupby("_ep").agg(r=("net","mean"), t0=("entry_time","first"))
    er=ep.r.to_numpy(); m=ep.groupby(ep.t0.dt.to_period("M")).r.mean()*1e4
    eq=np.cumprod(1+r*sizing); pk=np.maximum.accumulate(eq)
    srt=np.sort(m.to_numpy())[::-1]
    return {"n":len(r),"n_ep":len(er),"n/j":round(len(r)/730,2),
            "brut_bps":round(t.brut.mean()*1e4,1),"net_bps":round(r.mean()*1e4,1),
            "net_EP":round(er.mean()*1e4,1),
            "t_EP":round(er.mean()/(er.std(ddof=1)/np.sqrt(len(er))),2),
            "med_mois":round(float(m.median()),1),
            "mois_pos":f"{int((m>0).sum())}/{len(m)}",
            "sans_3_meilleurs_mois":round(srt[3:].mean(),1),
            "eq_5pct":round(float(eq[-1]),3),"maxDD%":round(float(-(eq/pk-1).min())*100,1)}

print("\n=== Regles fixes, moteur complet, 24 mois, sortie hold=240 trail=2.5 ===")
rows=[]
for lab,m in REGLES.items():
    r=bt(m, ExitRules(max_hold=240, stop_k=1.0, trail_k=2.5, arm_at=0.5))
    if r: r["regle"]=lab; rows.append(r)
d=pd.DataFrame(rows); d=d[["regle"]+[c for c in d.columns if c!="regle"]]
print(d.to_string(index=False))

print("\n=== La meilleure regle OI, sur toute la grille de sorties ===")
best = REGLES["D. + OI > +1% / 5min"]
rows=[]
for hold,trail,arm in itertools.product([60,120,240,360],[1.5,2.5],[0.5,1.5]):
    r=bt(best, ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm))
    if r: r["sortie"]=f"hold{hold} trail{trail} arm{arm}"; rows.append(r)
d2=pd.DataFrame(rows).sort_values("net_EP",ascending=False)
d2=d2[["sortie"]+[c for c in d2.columns if c!="sortie"]]
print(d2.to_string(index=False))
print(f"\n{(d2.net_EP>0).sum()}/{len(d2)} sorties positives en net par episode")
print(f"{(d2.sans_3_meilleurs_mois>0).sum()}/{len(d2)} le restent sans les 3 meilleurs mois")
d2.to_csv("bt_final.csv", index=False)
