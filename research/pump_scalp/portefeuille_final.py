"""Ce que la strategie donne en portefeuille, palier par palier.

On passe du "bps par trade" au compte reel : contrainte de positions
simultanees, frequence effective sur l'univers, capital immobilise.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)

N_JOURS_ECHANT, N_UNIVERS = 2500, 525
d = pd.read_parquet("tick_mixte.parquet")
d["t"] = pd.to_datetime(d["ts"], unit="s")
T, tp, h = 10000, 40, 900
c, w = f"pnl_{T}_{tp}_{h}", f"why_{T}_{tp}_{h}"
x = d.dropna(subset=[c]).copy().sort_values("t")
orig = np.where(x[w] == "tp_passif", (4.5+2.0)/1e4, (4.5+4.5)/1e4)
x["brut"] = x[c] + orig

# frequence : l'echantillon couvre 2500 jours-symboles tires sur 730 jours
jours_calendaires = 730
decl_par_jour_univers = len(x) / N_JOURS_ECHANT * N_UNIVERS
print(f"{len(x)} trades sur {N_JOURS_ECHANT} jours-symboles tires")
print(f"-> {len(x)/N_JOURS_ECHANT:.2f} declenchement par symbole et par jour")
print(f"-> sur un univers de {N_UNIVERS} symboles : "
      f"{decl_par_jour_univers:.0f} declenchements par jour\n")

# contrainte de portefeuille : N positions simultanees, duree mediane observee
duree_med = 900  # borne haute de la configuration
print(f"Avec {duree_med//60} min de detention maximale et 5 positions simultanees,")
cap_jour = 5 * 24*3600 / duree_med
print(f"le systeme peut prendre au plus {cap_jour:.0f} trades par jour ; "
      f"la contrainte vient donc du flux de signaux, pas des slots.\n")

PALIERS = [("VIP 0 (base)",4.50,2.00), ("VIP 0 + BNB",4.05,1.80), ("VIP 2",3.50,1.60),
           ("VIP 4",3.00,1.20), ("VIP 6",2.50,1.00), ("VIP 9",1.70,1.00),
           ("teneur de marche",1.70,-0.50)]
rows=[]
for lab, tk, mk in PALIERS:
    fees = np.where(x[w]=="tp_passif", (tk+mk)/1e4, (tk+tk)/1e4)
    net = (x["brut"] - fees).to_numpy()
    n_an = decl_par_jour_univers * 365
    pnl_par_trade = net.mean() * T
    capital = 5 * T * 2          # 5 positions + marge de securite
    rows.append({"palier": lab,
                 "net_bps": round(net.mean()*1e4, 2),
                 "$ par trade": round(pnl_par_trade, 2),
                 "trades/an": int(n_an),
                 "$ par an": int(pnl_par_trade * n_an),
                 "volume/an M$": round(n_an*T/1e6, 0),
                 "rendement sur 100k$": f"{pnl_par_trade*n_an/100_000*100:.0f} %",
                 "ecart-type/trade %": round(net.std()*100, 2)})
r=pd.DataFrame(rows)
print(r.to_string(index=False))
print("\nVolume annuel genere par la strategie elle-meme : "
      f"{rows[0]['volume/an M$']:.0f} M$, soit {rows[0]['volume/an M$']/12:.0f} M$ sur 30 jours.")
print("C'est le point decisif : les paliers VIP 6 a 9 exigent des volumes")
print("mensuels de l'ordre du milliard de dollars. Cette strategie ne peut PAS")
print("financer son propre palier de frais - il doit venir d'ailleurs.")
