"""Batterie complete, open interest ALIGNEE correctement.

Le test du prix implicite (oi_value/oi compare aux klines) date l'instantane a
T+5 : la ligne etiquetee 21:45 decrit l'etat a 21:50. Lire cette ligne au moment
d'un signal a 21:47, c'est donc lire 3 minutes de futur. Mon resultat precedent
etait une fuite.

Version causale : au signal s, on n'utilise que les lignes etiquetees <= s-5
(snapshot publie), soit un retard de 5 minutes sur la serie etiquetee. On ajoute
le retard 6 par prudence, pour couvrir le delai de publication.
"""
import itertools
import numpy as np, pandas as pd
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net
from evaluate2 import episodes
pd.set_option("display.width", 240)

a = pd.read_parquet("events_tail24_lag.parquet")
b = pd.read_parquet("events_tail24_lag2.parquet")
ev = a.copy()
for c in b.columns:
    if c.startswith("oi_lag"): ev[c] = b[c].to_numpy()
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
z = np.load("paths24.npz")
O,H,L,ok = z["o"].astype("float64"),z["h"].astype("float64"),z["l"].astype("float64"),z["ok"]
risk = np.clip(ev["sigma_ref"].to_numpy()*np.sqrt(5.)*4.0,0.003,0.15)
zb = ev.z_burst.to_numpy()

def bt(mask, rules):
    idx=np.flatnonzero(mask)
    if len(idx)<60: return None
    rr,eb,_=simulate_batch(O[idx],H[idx],L[idx],risk[idx],rules)
    t=pd.DataFrame({"symbol":ev.symbol.to_numpy()[idx],"entry_time":ev.entry_time.to_numpy()[idx],
                    "hold":eb,"brut":rr,"net":net(rr,rules),"z":zb[idx]}).dropna(subset=["brut"])
    t["exit_time"]=t.entry_time+pd.to_timedelta(t.hold,unit="m")
    t=t.sort_values(["entry_time","z"],ascending=[True,False]).reset_index(drop=True)
    t=t[portfolio(t,max_concurrent=3)]
    if len(t)<60: return None
    r=t.net.to_numpy(); t["_ep"]=episodes(t.entry_time)
    ep=t.groupby("_ep").agg(r=("net","mean"),t0=("entry_time","first"))
    er=ep.r.to_numpy(); m=ep.groupby(ep.t0.dt.to_period("M")).r.mean()*1e4
    srt=np.sort(m.to_numpy())[::-1]; eq=np.cumprod(1+r*0.05)
    return {"n":len(r),"n_ep":len(er),"net_EP":round(er.mean()*1e4,1),
            "t_EP":round(er.mean()/(er.std(ddof=1)/np.sqrt(len(er))),2),
            "mois_pos":f"{int((m>0).sum())}/{len(m)}","sans_top3":round(srt[3:].mean(),1),
            "2024-25":round(ep[ep.t0<'2025-09-01'].r.mean()*1e4,1),
            "2025-26":round(ep[ep.t0>='2025-09-01'].r.mean()*1e4,1),
            "eq":round(float(eq[-1]),3)}

R = ExitRules(max_hold=240, stop_k=1.0, trail_k=2.5, arm_at=0.5)
print("=== 1. La regle et son controle, aux trois alignements ===")
rows=[]
for lag, note in [(0,"FUITE de 3-5 min"), (5,"causal"), (6,"causal + marge")]:
    c = ev[f"oi_lag{lag}"].to_numpy()
    for lab, m in [("OI > +1%", c>0.01), ("CONTROLE OI<=0", c<=0)]:
        r = bt(ok & (zb>3) & m & np.isfinite(c), R)
        if r: r["alignement"]=f"retard {lag} min ({note})"; r["regle"]=lab; rows.append(r)
d=pd.DataFrame(rows)
print(d[["alignement","regle","n","net_EP","t_EP","mois_pos","sans_top3","2024-25","2025-26","eq"]].to_string(index=False))

print("\n=== 2. Dose-reponse, alignement causal (retard 5 min) ===")
c5 = ev["oi_lag5"].to_numpy(); rows=[]
for lab, m in [("sans filtre OI", np.isfinite(c5)), ("OI > +0,5%", c5>0.005),
               ("OI > +1%", c5>0.01), ("OI > +2%", c5>0.02), ("OI > +3%", c5>0.03)]:
    r=bt(ok & (zb>3) & m & np.isfinite(c5), R)
    if r: r["seuil"]=lab; rows.append(r)
d2=pd.DataFrame(rows)
print(d2[["seuil","n","net_EP","t_EP","mois_pos","sans_top3","2024-25","2025-26"]].to_string(index=False))

print("\n=== 3. Grille de sorties, regle OI>+1% causale ===")
sel = ok & (zb>3) & (c5>0.01) & np.isfinite(c5); rows=[]
for hold,trail,arm in itertools.product([60,120,240,360],[1.5,2.5],[0.5,1.5]):
    r=bt(sel, ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm))
    if r: r["sortie"]=f"h{hold} tr{trail} arm{arm}"; rows.append(r)
d3=pd.DataFrame(rows).sort_values("net_EP",ascending=False)
print(d3[["sortie","n","net_EP","t_EP","mois_pos","sans_top3","2024-25","2025-26"]].to_string(index=False))
print(f"\n{(d3.net_EP>0).sum()}/{len(d3)} positives ; "
      f"{(d3.sans_top3>0).sum()}/{len(d3)} sans les 3 meilleurs mois ; "
      f"{((d3['2024-25']>0)&(d3['2025-26']>0)).sum()}/{len(d3)} sur les DEUX periodes")
