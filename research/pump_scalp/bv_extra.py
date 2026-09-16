"""Telechargement des jeux de microstructure de Binance Vision.

Trois sources que l'etude n'avait pas utilisees, et qui portent precisement
l'information absente des klines :

  metrics/      open interest + ratios long/short, pas de 5 min, fichiers
                JOURNALIERS (pas de version mensuelle) -> beaucoup de petits
                fichiers, d'ou le parallelisme eleve.
  premiumIndex/ prime du perp sur l'index spot, pas de 1 min, mensuel.
  spot/klines/  le marche spot du meme token, mensuel. Tous les perps n'ont
                pas de paire spot : un 404 ici est une information, pas une
                erreur.
"""
from __future__ import annotations

import io, os, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np, pandas as pd
from bvision import _get, CACHE, months

BASE = "https://data.binance.vision/data"

METRIC_COLS = ["create_time", "symbol", "oi", "oi_value", "cnt_top_ls",
               "sum_top_ls", "cnt_ls", "taker_ls"]


def _store(path, df):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, compression="zstd")


def fetch_metrics_day(sym, day: pd.Timestamp):
    path = os.path.join(CACHE, "metrics", sym, f"{day:%Y-%m-%d}.parquet")
    if os.path.exists(path):
        return
    url = f"{BASE}/futures/um/daily/metrics/{sym}/{sym}-metrics-{day:%Y-%m-%d}.zip"
    blob = _get(url, timeout=60, retries=3)
    if blob is None:
        _store(path, pd.DataFrame(columns=METRIC_COLS[2:],
                                  index=pd.DatetimeIndex([], name="timestamp")))
        return
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = METRIC_COLS[:len(df.columns)]
    idx = pd.DatetimeIndex(pd.to_datetime(df["create_time"]), name="timestamp")
    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce").astype("float32")
                        for c in METRIC_COLS[2:] if c in df.columns})
    out.index = idx
    _store(path, out[~out.index.duplicated(keep="last")].sort_index())


def fetch_premium_month(sym, y, m):
    path = os.path.join(CACHE, "premium", sym, f"{y}-{m:02d}.parquet")
    if os.path.exists(path):
        return
    url = f"{BASE}/futures/um/monthly/premiumIndexKlines/{sym}/1m/{sym}-1m-{y}-{m:02d}.zip"
    blob = _get(url, timeout=120, retries=3)
    if blob is None:
        _store(path, pd.DataFrame(columns=["prem_close", "prem_high"],
                                  index=pd.DatetimeIndex([], name="timestamp")))
        return
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0])
    txt = raw.decode("utf-8", errors="replace")
    hdr = None if txt.split(",", 1)[0].strip().lstrip("-").isdigit() else 0
    df = pd.read_csv(io.StringIO(txt), header=hdr, usecols=[0, 2, 3, 4])
    df.columns = ["open_time", "high", "low", "close"]
    ot = pd.to_numeric(df["open_time"], errors="coerce")
    unit = "us" if float(ot.dropna().iloc[0]) > 1e14 else "ms"
    out = pd.DataFrame({"prem_close": df["close"].astype("float32"),
                        "prem_high": df["high"].astype("float32"),
                        "prem_low": df["low"].astype("float32")})
    out.index = pd.DatetimeIndex(pd.to_datetime(ot, unit=unit), name="timestamp")
    _store(path, out[~out.index.duplicated(keep="last")].sort_index())


def fetch_spot_month(sym, y, m):
    path = os.path.join(CACHE, "spot", sym, f"{y}-{m:02d}.parquet")
    if os.path.exists(path):
        return
    url = f"{BASE}/spot/monthly/klines/{sym}/1m/{sym}-1m-{y}-{m:02d}.zip"
    blob = _get(url, timeout=120, retries=3)
    if blob is None:
        _store(path, pd.DataFrame(columns=["close", "quote_volume", "taker_quote"],
                                  index=pd.DatetimeIndex([], name="timestamp")))
        return
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        raw = z.read(z.namelist()[0])
    txt = raw.decode("utf-8", errors="replace")
    hdr = None if txt.split(",", 1)[0].strip().lstrip("-").isdigit() else 0
    df = pd.read_csv(io.StringIO(txt), header=hdr, usecols=[0, 4, 7, 10])
    df.columns = ["open_time", "close", "quote_volume", "taker_quote"]
    ot = pd.to_numeric(df["open_time"], errors="coerce")
    unit = "us" if float(ot.dropna().iloc[0]) > 1e14 else "ms"
    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce").astype("float32")
                        for c in ("close", "quote_volume", "taker_quote")})
    out.index = pd.DatetimeIndex(pd.to_datetime(ot, unit=unit), name="timestamp")
    _store(path, out[~out.index.duplicated(keep="last")].sort_index())


def run(jobs, fn, workers, label):
    t0, n, err = time.time(), 0, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fn, *j) for j in jobs]
        for f in as_completed(futs):
            n += 1
            try:
                f.result()
            except Exception:
                err += 1
            if n % 2000 == 0:
                print(f"  {label} {n}/{len(jobs)} ({time.time()-t0:.0f}s, {err} echecs)",
                      file=sys.stderr, flush=True)
    print(f"{label} termine : {n} fichiers, {err} echecs, {time.time()-t0:.0f}s",
          file=sys.stderr)
