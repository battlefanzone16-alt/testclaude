"""Portefeuille simule sur la chronologie reelle, avec contrainte de slots.

Les deux corrections par rapport a la premiere version :
  - on ne pondere plus par trade ni par episode, on SIMULE : les trades sont
    rejoues dans l'ordre et refuses quand les slots sont pris. C'est exact et ca
    evite le debat sur la ponderation.
  - on ne pretend pas extrapoler a l'univers entier. L'echantillon couvre 2 500
    jours-symboles tires au hasard sur 525 symboles x 730 jours, soit 0,65 % du
    total. Multiplier le P&L par 153 supposerait que les signaux ne se
    chevauchent jamais, ce qui est faux. On rapporte donc ce que l'echantillon
    montre, et la contrainte de capacite separement.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 230)

T, tp, h = 10000, 40, 900
d = pd.read_parquet("tick_mixte.parquet")
d["t"] = pd.to_datetime(d["ts"], unit="s")
c, w = f"pnl_{T}_{tp}_{h}", f"why_{T}_{tp}_{h}"
x = d.dropna(subset=[c]).copy().sort_values("t").reset_index(drop=True)
orig = np.where(x[w] == "tp_passif", (4.5+2.0)/1e4, (4.5+4.5)/1e4)
x["brut"] = x[c] + orig
x["fin"] = x.t + pd.Timedelta(seconds=h)

def simule(net, slots=5):
    pris, ouverts = [], []
    for i in range(len(x)):
        now = x.t.iloc[i]
        ouverts = [e for e in ouverts if e > now]
        if len(ouverts) >= slots:
            continue
        pris.append(i); ouverts.append(x.fin.iloc[i])
    r = net[pris]
    return r, len(pris)

PALIERS=[("VIP 0 (base)",4.50,2.00),("VIP 0 + BNB",4.05,1.80),("VIP 2",3.50,1.60),
         ("VIP 4",3.00,1.20),("VIP 6",2.50,1.00),("VIP 9",1.70,1.00),
         ("teneur de marche",1.70,-0.50)]
rows=[]
for lab, tk, mk in PALIERS:
    fees = np.where(x[w]=="tp_passif",(tk+mk)/1e4,(tk+tk)/1e4)
    net = (x["brut"]-fees).to_numpy()
    r, n = simule(net, slots=5)
    ts = x.t.iloc[:len(x)][np.isin(np.arange(len(x)), np.arange(len(x)))]
    idx = np.array([i for i in range(len(x))])
    # mois par mois sur les trades reellement pris
    pris_mask = np.zeros(len(x), bool)
    rr, pris_idx = [], []
    ouverts=[]
    for i in range(len(x)):
        now=x.t.iloc[i]; ouverts=[e for e in ouverts if e>now]
        if len(ouverts)>=5: continue
        pris_idx.append(i); ouverts.append(x.fin.iloc[i])
    sub = x.iloc[pris_idx].copy(); sub["net"]=net[pris_idx]
    m = sub.groupby(sub.t.dt.to_period("M")).net.mean()*1e4
    srt=np.sort(m.to_numpy())[::-1]
    eq = np.cumprod(1+sub.net.to_numpy()*0.20)      # 20% du capital par position
    pk = np.maximum.accumulate(eq)
    rows.append({"palier":lab,"trades_pris":len(sub),
                 "net_bps":round(sub.net.mean()*1e4,2),
                 "t":round(sub.net.mean()/(sub.net.std(ddof=1)/np.sqrt(len(sub))),2),
                 "gagnants_%":round((sub.net>0).mean()*100,1),
                 "mois_pos":f"{int((m>0).sum())}/{len(m)}",
                 "sans_top3":round(srt[3:].mean(),2),
                 "2024-25":round(sub[sub.t<'2025-09-01'].net.mean()*1e4,2),
                 "2025-26":round(sub[sub.t>='2025-09-01'].net.mean()*1e4,2),
                 "equity_2ans":round(float(eq[-1]),3),
                 "maxDD_%":round(float(-(eq/pk-1).min())*100,1)})
r=pd.DataFrame(rows)
print(f"{len(x)} trades candidats ; simulation a 5 positions simultanees\n")
print(r.to_string(index=False))
print(f"\nTrades refuses faute de slot : {len(x)-rows[0]['trades_pris']} "
      f"({(1-rows[0]['trades_pris']/len(x))*100:.0f} %) -> la contrainte mord peu")
print(f"\nFrequence observee : {len(x)/2500:.2f} trade par symbole-jour.")
print(f"Sur un univers de 525 symboles, cela ferait ~{len(x)/2500*525:.0f} signaux/jour,")
print("bien au-dela de ce que 5 slots absorbent : en reel il faudrait selectionner")
print("les meilleurs signaux, ce que cette simulation ne fait pas (elle prend le")
print("premier arrive). Le chiffre par trade est donc representatif, le total non.")
