"""Telechargement parallele des klines Binance Vision, avec cache parquet.

Choix structurels :
  - on garde quote_volume, trades et taker_buy_quote en plus de l'OHLCV : la
    pression acheteuse et le nombre de trades sont des features de premier ordre
    pour detecter une ignition de momentum. Les jeter maintenant couterait un
    retelechargement complet plus tard.
  - stockage float32 + parquet zstd : ~4x plus compact que le CSV, et le disque
    de la session est une allocation fixe.
  - un 404 = mois inexistant (token pas encore liste). Ce n'est pas une erreur.
"""
from __future__ import annotations

import io, os, sys, time, zipfile, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

BASE = "https://data.binance.vision/data"
CACHE = os.environ.get("BV_CACHE", "/home/user/testclaude/research/pump_scalp/cache")

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
KEEP = ["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_quote"]


def url(symbol, interval, year, month, market="futures"):
    seg = {"futures": "futures/um", "spot": "spot"}[market]
    return (f"{BASE}/{seg}/monthly/klines/{symbol}/{interval}/"
            f"{symbol}-{interval}-{year}-{month:02d}.zip")


def _get(u, timeout=120, retries=4):
    last = None
    for a in range(retries):
        try:
            with urllib.request.urlopen(u, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:
            last = e
        time.sleep(2 ** a)
    raise RuntimeError(f"echec {u}: {last}")


def parse(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8", errors="replace")
    first = text.split(",", 1)[0].strip().lstrip("-")
    df = pd.read_csv(io.StringIO(text), header=None if first.isdigit() else 0)
    df.columns = KLINE_COLS[:len(df.columns)]

    ot = pd.to_numeric(df["open_time"], errors="coerce")
    nn = ot.dropna()
    if nn.empty:
        return pd.DataFrame()
    unit = "us" if float(nn.iloc[0]) > 1e14 else "ms"
    idx = pd.DatetimeIndex(pd.to_datetime(ot, unit=unit, utc=True).dt.tz_localize(None))

    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce").astype("float32")
                        for c in KEEP})
    out.index = idx
    out.index.name = "timestamp"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(subset=["open", "high", "low", "close"])


def months(start: str, end: str):
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    y, m = t0.year, t0.month
    while (y, m) <= (t1.year, t1.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def fetch_month(symbol, interval, y, m, market="futures"):
    """Renvoie un DataFrame (eventuellement vide) pour un couple symbole/mois."""
    path = os.path.join(CACHE, interval, symbol, f"{y}-{m:02d}.parquet")
    if os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            os.remove(path)
    blob = _get(url(symbol, interval, y, m, market))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if blob is None:
        df = pd.DataFrame(columns=KEEP, index=pd.DatetimeIndex([], name="timestamp"))
    else:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            df = parse(z.read(z.namelist()[0]))
    df.to_parquet(path, compression="zstd")
    return df


def fetch(symbol, interval, start, end, market="futures") -> pd.DataFrame:
    frames = [fetch_month(symbol, interval, y, m, market) for y, m in months(start, end)]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame(columns=KEEP, index=pd.DatetimeIndex([], name="timestamp"))
    full = pd.concat(frames).sort_index()
    full = full[~full.index.duplicated(keep="last")]
    return full[(full.index >= pd.Timestamp(start)) & (full.index < pd.Timestamp(end))]


def fetch_many(symbols, interval, start, end, workers=16, market="futures",
               quiet=False, collect=True):
    """Telecharge en parallele au niveau (symbole, mois) : c'est la granularite
    ou le parallelisme paie, un symbole seul etant une chaine de mois sequentiels."""
    jobs = [(s, y, m) for s in symbols for y, m in months(start, end)]
    done = {}
    t0, n = time.time(), 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_month, s, interval, y, m, market): (s, y, m) for s, y, m in jobs}
        for f in as_completed(futs):
            s, y, m = futs[f]
            n += 1
            try:
                f.result()
            except Exception as e:
                print(f"  ECHEC {s} {y}-{m:02d}: {e}", file=sys.stderr)
            if not quiet and n % 200 == 0:
                print(f"  {n}/{len(jobs)} ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)
    # On ne reassemble QUE si l'appelant veut les donnees. Charger 400 symboles
    # x 1 an de 1-min pour les jeter aussitot, c'est 7 Go de RAM pour rien - et
    # c'est ce que faisait la version precedente.
    if not collect:
        return {}
    for s in symbols:
        df = fetch(s, interval, start, end, market)
        if len(df):
            done[s] = df
    return done
