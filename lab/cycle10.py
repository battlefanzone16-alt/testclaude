import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL, protocole4 as P4

def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan

def derive_autorisee(h1, semaines=P4.DERIVE_SEMAINES):
    """Sens autorise pour chaque barre, connu des l'ouverture de la semaine.

    La derive est mesuree sur les `semaines` semaines PRECEDENTES, closes.
    """
    hebdo = h1["close"].resample("W-SUN").last()
    hebdo.index = hebdo.index.to_period("W-SUN")
    # la derive de la semaine W-1 gouverne la semaine W
    sens = np.sign(hebdo / hebdo.shift(semaines) - 1.0).shift(1)
    par_barre = sens.reindex(h1.index.to_period("W-SUN")).to_numpy()
    return pd.Series(par_barre, index=h1.index)

def mesure(sym, ancrage=P4.ANCRAGE, filtre=True):
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    fr=data.load_funding(sym,"2021-10","2026-08")
    heb = VH.profils_hebdo(m5) if ancrage=="semaine" else VH.profils_hebdo_jambe(m5, mode=ancrage)
    niv=VH.niveaux(h1.index, heb)
    a,b=P4.FENETRE
    s=h1.loc[a:b]; nv=niv.loc[a:b]; f5=m5.loc[a:b]
    if len(s)<3000: return None
    sa = derive_autorisee(h1).loc[a:b] if filtre else None
    r=EL.simuler(s,nv,fr,entree="limite",attente=P4.ATTENTE,max_barres=P4.MAX_BARRES,
                 fin=f5,slippage_stop=P4.SLIPPAGE_STOP,sens_autorise=sa)
    t=r.trades.copy(); t["sym"]=sym
    return t

print(f"=== CYCLE 10 — dix actifs vierges, filtre de derive {P4.DERIVE_SEMAINES} semaines ===")
print(f"    ancrage : {P4.ANCRAGE}   fenetre : {P4.FENETRE[0]} -> {P4.FENETRE[1]}\n", flush=True)
print(f"{'actif':>10} {'n filtre':>9} {'PF filtre':>10} {'n brut':>7} {'PF non filtre':>14} {'net filtre':>11}", flush=True)
F=[]; N=[]
for sym in P4.ACTIFS:
    try:
        tf=mesure(sym, filtre=True); tn=mesure(sym, filtre=False)
    except Exception as e:
        print(f"{sym:>10}  indisponible ({type(e).__name__}: {e})", flush=True); continue
    if tf is None or len(tf)<30:
        print(f"{sym:>10}  historique insuffisant", flush=True); continue
    F.append(tf); N.append(tn)
    eq=(1+tf.net.to_numpy()).cumprod()
    print(f"{sym:>10} {len(tf):>9} {pf(tf.net):>10.3f} {len(tn):>7} {pf(tn.net):>14.3f} "
          f"{(eq[-1]-1)*100:>+10.1f}%", flush=True)

TF=pd.concat(F, ignore_index=True); TN=pd.concat(N, ignore_index=True)
print(f"\n  AVEC filtre    : {len(TF):>5} trades, PF {pf(TF.net):.3f}")
print(f"  SANS filtre    : {len(TN):>5} trades, PF {pf(TN.net):.3f}")
rng=np.random.default_rng(0); syms=TF.sym.unique()
bs=np.array([pf(pd.concat([TF[TF.sym==s] for s in rng.choice(syms,len(syms),replace=True)],
             ignore_index=True).net) for _ in range(3000)])
bs=bs[np.isfinite(bs)]
ic_bas=np.percentile(bs,5)
print(f"  IC 90 % grappes : [{ic_bas:.3f} ; {np.percentile(bs,95):.3f}]  "
      f"tirages > 1 : {(bs>1).mean()*100:.1f}%")

print("\n=== VERDICT contre les criteres ecrits d'avance ===")
c1 = pf(TF.net) >= P4.PF_MINIMUM
c2 = ic_bas > P4.IC_BAS_MINIMUM
c3 = pf(TF.net) > pf(TN.net)
for nom, ok, detail in ((f"PF >= {P4.PF_MINIMUM}", c1, f"{pf(TF.net):.3f}"),
                        (f"IC bas > {P4.IC_BAS_MINIMUM}", c2, f"{ic_bas:.3f}"),
                        ("le filtre ameliore", c3, f"{pf(TF.net):.3f} vs {pf(TN.net):.3f}")):
    print(f"  {nom:<22} {detail:>18}  -> {'PASSE' if ok else 'ECHOUE'}")

print("\n=== secondaire, robustesse seulement (jamais des candidats) ===")
for anc in ("depuis","jambe"):
    try:
        T=pd.concat([x for x in (mesure(s,ancrage=anc,filtre=True) for s in P4.ACTIFS)
                     if x is not None and len(x)>30], ignore_index=True)
        print(f"  ancrage {anc:>8} avec filtre : {len(T):>5} trades, PF {pf(T.net):.3f}", flush=True)
    except Exception as e:
        print(f"  ancrage {anc}: {e}")
