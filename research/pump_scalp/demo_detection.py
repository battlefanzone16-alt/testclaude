"""Ce que le detecteur voit, minute par minute, sur un vrai pump."""
import sys
import numpy as np, pandas as pd
import bvision, features
pd.set_option("display.width", 200)

sym, jour = sys.argv[1], sys.argv[2]
d0 = pd.Timestamp(jour)
# on charge large : sigma_ref et vol_ref ont besoin d'un jour de recul
df = bvision.fetch(sym, "1m", (d0 - pd.Timedelta(days=4)).strftime("%Y-%m-%d"),
                   (d0 + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
btc = bvision.fetch("BTCUSDT", "1m", (d0 - pd.Timedelta(days=4)).strftime("%Y-%m-%d"),
                    (d0 + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))["close"]
f = features.add_features(df, k=5, btc_close=btc)

Z_MIN, VOL_MIN, QV_MIN = 2.5, 2.0, 2000.0
ok = ((f.z_burst >= Z_MIN) & (f.vol_mult >= VOL_MIN)
      & (f.qv_ref_1d >= QV_MIN) & (f.r_burst > 0))

j = f.index.normalize() == d0
sub = f[j]
first = ok[j].idxmax() if ok[j].any() else None
print(f"{sym} le {jour} : {int(ok[j].sum())} minutes remplissent les 4 conditions")
if first is None:
    sys.exit()
print(f"Premier declenchement : {first:%H:%M} UTC\n")

w = sub.loc[first - pd.Timedelta(minutes=8): first + pd.Timedelta(minutes=6)]
t = pd.DataFrame({
    "close": df.close.reindex(w.index).round(6),
    "r_5m_%": (w.r_burst * 100).round(2),
    "z": w.z_burst.round(1),
    "vol_x": w.vol_mult.round(1),
    "taker_%": (w.taker_ratio * 100).round(0),
    "r_btc_%": (w.r_btc * 100).round(2),
    "declenche": ["  <<<< OUI" if ok.get(i, False) else "" for i in w.index],
})
t.index = t.index.strftime("%H:%M")
print(t.to_string())

sr = float(f.sigma_ref.loc[first])
print(f"\nRegime normal de {sym} juste avant : sigma 1-min = {sr*100:.3f} %")
print(f"  -> un mouvement 5-min 'typique' vaut {sr*np.sqrt(5)*100:.2f} %")
print(f"  -> le mouvement observe vaut {f.r_burst.loc[first]*100:.2f} %, "
      f"soit {f.z_burst.loc[first]:.1f} ecarts-types")
print(f"  -> volume des 5 min : {f.qv_burst.loc[first]/1e6:.2f} M$ contre "
      f"{f.qv_ref_1d.loc[first]*5/1e6:.3f} M$ en temps normal ({f.vol_mult.loc[first]:.0f}x)")

# --- Ce que le systeme prend REELLEMENT -------------------------------------
# Piege a eviter : afficher la minute de z maximal donne une fausse image. Le
# systeme n'attend pas le pic, il entre au PREMIER declenchement puis se met en
# sourdine 60 minutes. Le z maximal arrive en general au climax du mouvement,
# bien apres l'entree reelle.
print(f"\n{'='*84}")
print("Entrees reellement generees (premier declenchement, puis cooldown 60 min)")
keep, last = [], -10**9
idx = np.flatnonzero(ok.to_numpy())
for i in idx:
    if i - last >= 60:
        keep.append(i); last = i
o = df.open.to_numpy()
rows = []
for i in keep:
    if f.index[i].normalize() != d0 or i + 1 >= len(o):
        continue
    e = i + 1
    r = {"signal_UTC": f"{f.index[i]:%H:%M}", "entree_Paris": f"{f.index[e]+pd.Timedelta(hours=2):%H:%M}",
         "prix": round(float(o[e]), 6), "z": round(float(f.z_burst.iloc[i]), 1),
         "vol_x": round(float(f.vol_mult.iloc[i]), 0)}
    for h in (60, 120, 240):
        j2 = min(e + h, len(o) - 1)
        r[f"+{h//60}h_%"] = round((o[j2] / o[e] - 1) * 100, 2)
    rows.append(r)
print(pd.DataFrame(rows).to_string(index=False))
print(f"\nSur la journee : {int(ok[j].sum())} minutes remplissent les conditions,")
print(f"regroupees par le cooldown en {len(rows)} entrees effectives.")
