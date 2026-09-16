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

# --- Le declenchement le plus fort de la journee ---------------------------
top = sub.z_burst[ok[j]].idxmax()
print(f"\n{'='*80}\nDeclenchement le PLUS FORT de la journee : {top:%H:%M} UTC")
w2 = sub.loc[top - pd.Timedelta(minutes=6): top + pd.Timedelta(minutes=8)]
t2 = pd.DataFrame({
    "close": df.close.reindex(w2.index).round(6),
    "r_5m_%": (w2.r_burst*100).round(2), "z": w2.z_burst.round(1),
    "vol_x": w2.vol_mult.round(1), "taker_%": (w2.taker_ratio*100).round(0),
    "r_btc_%": (w2.r_btc*100).round(2),
    "declenche": ["  <<<< OUI" if ok.get(i, False) else "" for i in w2.index]})
t2.index = t2.index.strftime("%H:%M")
print(t2.to_string())
o = df.open.to_numpy(); pos = df.index.get_indexer([top])[0]
for h in (60, 120, 180):
    e = min(pos+1+h, len(o)-1)
    print(f"  si on entre a l'ouverture de {df.index[pos+1]:%H:%M} : "
          f"+{h//60}h -> {(o[e]/o[pos+1]-1)*100:+.2f} %")
print(f"\nSur la journee : {int(ok[j].sum())} minutes declenchent, "
      f"dont {int((sub.z_burst[ok[j]]>6).sum())} avec z>6 et "
      f"{int((sub.z_burst[ok[j]]>9).sum())} avec z>9.")
