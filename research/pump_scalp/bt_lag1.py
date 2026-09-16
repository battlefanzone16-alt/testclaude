"""Backtest final, open interest RETARDE d'une minute.

Choix conservateur assume. Je n'ai pas pu etablir avec certitude, depuis
l'archive seule, si l'horodatage Binance des tranches d'open interest est un
instantane ou la fin d'une fenetre. Le test d'alignement penche pour
l'instantane, mais penche n'est pas prouve. On publie donc les chiffres avec une
minute de retard : ils sont valides sous les deux lectures, au prix d'un peu de
performance.
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
zb = ev.z_burst.to_numpy(); oi1 = ev["oi_lag1"].to_numpy()

def bt(mask, rules, fee=4.5, slip=5.0, sizing=0.05):
    idx = np.flatnonzero(mask)
    if len(idx) < 60: return None
    r_ = ExitRules(max_hold=rules.max_hold, stop_k=rules.stop_k, trail_k=rules.trail_k,
                   arm_at=rules.arm_at, fee_bps=fee, slip_bps=slip)
    rr, eb, _ = simulate_batch(O[idx],H[idx],L[idx],risk[idx],r_)
    t = pd.DataFrame({"symbol":ev.symbol.to_numpy()[idx],"entry_time":ev.entry_time.to_numpy()[idx],
                      "hold":eb,"brut":rr,"net":net(rr,r_),"z":zb[idx]}).dropna(subset=["brut"])
    t["exit_time"]=t.entry_time+pd.to_timedelta(t.hold,unit="m")
    t=t.sort_values(["entry_time","z"],ascending=[True,False]).reset_index(drop=True)
    t=t[portfolio(t,max_concurrent=3)]
    if len(t)<60: return None
    r=t.net.to_numpy(); t["_ep"]=episodes(t.entry_time)
    ep=t.groupby("_ep").agg(r=("net","mean"),t0=("entry_time","first"))
    er=ep.r.to_numpy(); m=ep.groupby(ep.t0.dt.to_period("M")).r.mean()*1e4
    srt=np.sort(m.to_numpy())[::-1]; eq=np.cumprod(1+r*sizing); pk=np.maximum.accumulate(eq)
    return {"n":len(r),"n_ep":len(er),"n/j":round(len(r)/730,2),
            "brut":round(t.brut.mean()*1e4,1),"net":round(r.mean()*1e4,1),
            "net_EP":round(er.mean()*1e4,1),
            "t_EP":round(er.mean()/(er.std(ddof=1)/np.sqrt(len(er))),2),
            "win%":round((r>0).mean()*100,1),
            "mois_pos":f"{int((m>0).sum())}/{len(m)}","sans_top3":round(srt[3:].mean(),1),
            "2024-25":round(ep[ep.t0<'2025-09-01'].r.mean()*1e4,1),
            "2025-26":round(ep[ep.t0>='2025-09-01'].r.mean()*1e4,1),
            "eq":round(float(eq[-1]),3),"maxDD%":round(float(-(eq/pk-1).min())*100,1)}

R = ExitRules(max_hold=240, stop_k=1.0, trail_k=2.5, arm_at=0.5)
print("=== 1. La regle et son controle, OI retardee de 1 min ===")
rows=[]
for lab, m in [("reference sans OI", ok & (zb>3)),
               ("OI > +0,5%", ok & (zb>3) & (oi1>0.005)),
               ("OI > +1%",   ok & (zb>3) & (oi1>0.01)),
               ("OI > +2%",   ok & (zb>3) & (oi1>0.02)),
               ("CONTROLE : OI <= 0", ok & (zb>3) & (oi1<=0))]:
    r=bt(m & np.isfinite(oi1), R)
    if r: r["regle"]=lab; rows.append(r)
d=pd.DataFrame(rows); print(d[["regle"]+[c for c in d.columns if c!="regle"]].to_string(index=False))

print("\n=== 2. Grille de sorties, regle OI>+1% retardee ===")
sel = ok & (zb>3) & (oi1>0.01) & np.isfinite(oi1)
rows=[]
for hold,trail,arm in itertools.product([60,120,240,360],[1.5,2.5],[0.5,1.5]):
    r=bt(sel, ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm))
    if r: r["sortie"]=f"hold{hold} trail{trail} arm{arm}"; rows.append(r)
d2=pd.DataFrame(rows).sort_values("net_EP",ascending=False)
print(d2[["sortie"]+[c for c in d2.columns if c!="sortie"]].to_string(index=False))
print(f"\n{(d2.net_EP>0).sum()}/{len(d2)} sorties positives ; "
      f"{(d2.sans_top3>0).sum()}/{len(d2)} le restent sans les 3 meilleurs mois ; "
      f"{((d2['2024-25']>0)&(d2['2025-26']>0)).sum()}/{len(d2)} positives sur LES DEUX periodes")

print("\n=== 3. Sensibilite au cout (sortie hold360 trail1.5) ===")
rows=[]
for lab, fee, slip in [("maker/taker ideal",2.0,2.0),("taker, slippage 2bps",4.5,2.0),
                       ("taker, slippage 5bps (base)",4.5,5.0),
                       ("taker, slippage 10bps",4.5,10.0),("taker, slippage 15bps",4.5,15.0)]:
    r=bt(sel, ExitRules(max_hold=360, stop_k=1.0, trail_k=1.5, arm_at=1.5), fee=fee, slip=slip)
    if r: r["cout"]=f"{lab} ({(fee+slip)*2:.0f} bps AR)"; rows.append(r)
d3=pd.DataFrame(rows)
print(d3[["cout","net_EP","t_EP","mois_pos","sans_top3","eq","maxDD%"]].to_string(index=False))
d2.to_csv("bt_lag1.csv", index=False)
