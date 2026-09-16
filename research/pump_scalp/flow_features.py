"""Features de flux d'ordres, depuis les trades tick par tick.

Pourquoi cette source et pas une autre. Les klines agregent la minute en cinq
nombres et detruisent ce qui decide a cette echelle. L'open interest aurait pu
combler le manque, mais son horodatage par tranches de 5 minutes s'est revele
decale de +5 min, ce qui a fabrique une fuite. Les aggTrades, eux, portent un
horodatage a la milliseconde : il n'y a rien a supposer.

Fenetres, strictement causales :
  rafale    [s-300s, s)     les 5 minutes qui declenchent le signal
  reference [s-3600s, s-300s)  le regime du token juste avant

Le flux est stream : telecharge, agrege, jete. Rien n'est conserve sur disque,
sinon les 3 798 jours de trades ne tiendraient pas dans l'espace disponible.

Convention Binance : is_buyer_maker=true signifie que l'ACHETEUR etait maker,
donc que le trade a ete initie par un VENDEUR. Le volume agressif a l'achat est
donc celui des lignes is_buyer_maker=false. Se tromper ici inverse tout le
signal, d'ou ce commentaire.
"""
from __future__ import annotations

import io, os, sys, time, zipfile, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np, pandas as pd
import pyarrow as pa
from pyarrow import csv as pacsv

BASE = "https://data.binance.vision/data/futures/um/daily/aggTrades"
BURST_S, REF_S = 300, 3600


def _get(url, timeout=120, retries=3):
    last = None
    for a in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:
            last = e
        time.sleep(2 ** a)
    raise RuntimeError(f"{url}: {last}")


def load_day(sym, day: pd.Timestamp):
    """Telecharge et parse un jour de trades. Rien n'est ecrit sur disque.

    Parsing par pyarrow et non pandas : sur ces fichiers (jusqu'a 2 millions de
    lignes) il est plusieurs fois plus rapide et alloue beaucoup moins, ce qui
    decide entre 2 heures et 30 minutes de traitement total.
    """
    url = f"{BASE}/{sym}/{sym}-aggTrades-{day:%Y-%m-%d}.zip"
    blob = _get(url)
    if blob is None:
        return None
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0])
    head = raw[:64].decode("utf-8", errors="replace")
    has_hdr = not head.split(",", 1)[0].strip().lstrip("-").isdigit()
    names = ["agg_id", "price", "qty", "first_id", "last_id", "t", "buyer_maker"]
    ro = pacsv.ReadOptions(column_names=None if has_hdr else names,
                           block_size=1 << 24)
    co = pacsv.ConvertOptions(include_columns=(
        ["price", "quantity", "transact_time", "is_buyer_maker"] if has_hdr
        else ["price", "qty", "t", "buyer_maker"]))
    try:
        tbl = pacsv.read_csv(io.BytesIO(raw), read_options=ro, convert_options=co)
    except Exception:
        return None
    del raw
    cols = tbl.column_names
    px = tbl.column(cols[0]).to_numpy(zero_copy_only=False).astype("float64")
    q = tbl.column(cols[1]).to_numpy(zero_copy_only=False).astype("float64")
    t = tbl.column(cols[2]).to_numpy(zero_copy_only=False).astype("float64")
    bm = tbl.column(cols[3])
    if pa.types.is_boolean(bm.type):
        sell = bm.to_numpy(zero_copy_only=False).astype(bool)
    else:
        sell = np.char.lower(bm.to_numpy(zero_copy_only=False).astype(str)) == "true"
    del tbl
    unit = 1e6 if np.nanmax(t) > 1e15 else 1e3
    return {"t": t / unit, "px": px, "q": q, "sell": sell}


def features(d, s_epoch):
    """Features causales pour un signal a s_epoch (secondes epoch)."""
    t, px, q, sell = d["t"], d["px"], d["q"], d["sell"]
    qv = px * q
    b0, b1 = s_epoch - BURST_S, s_epoch
    r0 = max(t[0], s_epoch - REF_S)
    ib = (t >= b0) & (t < b1)
    ir = (t >= r0) & (t < b0)
    nb, nr = int(ib.sum()), int(ir.sum())
    if nb < 20 or nr < 100 or (b0 - r0) < 600:
        return None

    qb, sb, tb, pb = qv[ib], sell[ib], t[ib], px[ib]
    qr, sr = qv[ir], sell[ir]
    vol_b, vol_r = qb.sum(), qr.sum()
    if vol_b <= 0 or vol_r <= 0:
        return None

    buy_b = qb[~sb].sum()
    f = {}
    f["ofi"] = (2 * buy_b - vol_b) / vol_b                       # -1 vendeur .. +1 acheteur
    f["ofi_ref"] = (2 * qr[~sr].sum() - vol_r) / vol_r
    f["ofi_ecart"] = f["ofi"] - f["ofi_ref"]

    # gros ordres : seuil = 95e centile des tailles du REGIME precedent
    big = np.percentile(qr, 95)
    m_big = qb >= big
    f["big_part"] = qb[m_big].sum() / vol_b
    f["big_ofi"] = ((2 * qb[m_big & ~sb].sum() - qb[m_big].sum()) / qb[m_big].sum()
                    if qb[m_big].sum() > 0 else np.nan)
    f["trade_max_part"] = qb.max() / vol_b                       # un seul print, ou du flux ?
    f["taille_moy_rel"] = (vol_b / nb) / (vol_r / nr)

    # acceleration de l'arrivee des ordres
    dur_r = max(b0 - r0, 1.0)
    f["taux_rel"] = (nb / BURST_S) / (nr / dur_r)
    last60 = tb >= (b1 - 60)
    f["taux_fin"] = ((last60.sum() / 60) / (nb / BURST_S)) if nb else np.nan
    f["vol_fin_part"] = qb[last60].sum() / vol_b

    # forme du mouvement a l'interieur de la rafale
    f["px_fin_part"] = ((pb[-1] / pb[last60][0] - 1) / (pb[-1] / pb[0] - 1)
                        if last60.any() and abs(pb[-1] / pb[0] - 1) > 1e-9 else np.nan)
    # impact : combien de mouvement par unite de volume anormal
    rel_vol = vol_b / (vol_r * BURST_S / dur_r)
    f["impact"] = (pb[-1] / pb[0] - 1) / rel_vol if rel_vol > 0 else np.nan
    f["vol_mult_tick"] = rel_vol
    f["secondes_actives"] = len(np.unique(np.floor(tb))) / BURST_S
    f["n_trades_rafale"] = nb
    return f
