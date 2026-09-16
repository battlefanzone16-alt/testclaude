"""Combien d'hypotheses ai-je testees, et qu'attendre du hasard seul ?

C'est la question qu'on doit se poser apres une recherche aussi large. Si on
essaie N filtres independants sur du bruit pur, le meilleur d'entre eux affiche
un t-stat d'environ sqrt(2 ln N) - sans qu'aucun edge n'existe. Ce chiffre est
l'etalon auquel comparer mes "trouvailles".
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 180)

tests = [
    ("event study, buckets x horizons",            6*5*4),
    ("queue : conditionnement x horizons",         7*3),
    ("fade de la meche",                           5*7),
    ("repli en limite : profondeur x attente x marge x horizon", 4*2*4*2),
    ("regime vs meche (k=30)",                     8*3),
    ("recherche systematique (gradient boosting)", 2*2),
    ("largeur de marche",                          7*3),
    ("population idiosyncratique",                 14*2),
    ("microstructure OI / prime / spot",           10*2),
    ("flux d'ordres tick",                         10*2),
    ("grilles de sortie",                          64+16+16+16),
    ("alignements d'open interest",                9*2),
    ("sessions horaires",                          24+4*2),
]
d = pd.DataFrame(tests, columns=["famille", "n_tests"])
N = int(d.n_tests.sum())
print(d.to_string(index=False))
print(f"\nTotal approximatif : {N} tests distincts")
tmax = np.sqrt(2*np.log(N))
print(f"\nSous l'hypothese nulle (aucun edge nulle part), le meilleur de {N} tests")
print(f"independants affiche un t-stat attendu de {tmax:.2f}.")
print("\nA comparer avec mes 'trouvailles' successives :")
for lab, t in [("queue r_burst>8% (avant controle octobre)", 2.3),
               ("fade vol_mult 25-60x", 7.7),
               ("repli 90% (avant correction du biais)", 6.0),
               ("grappe >15% (avant ponderation par episode)", 6.0),
               ("open interest (avant correction d'horodatage)", 2.44),
               ("flux d'ordres, meilleur filtre", 1.1)]:
    verdict = "sous le seuil du hasard" if t < tmax else "au-dessus — mais explique par un biais identifie"
    print(f"  t = {t:<5} {lab:<48} {verdict}")
print(f"\nLes deux qui depassaient {tmax:.2f} ont ete expliques, non par un edge,")
print("mais par un biais precis : ordre des tests intra-barre pour le repli,")
print("ponderation par evenement au lieu d'episode pour la grappe.")
print("Aucun resultat de cette etude ne survit conjointement au seuil du hasard")
print("et aux controles de biais.")
