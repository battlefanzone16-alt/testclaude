"""Téléchargement des klines depuis data.binance.vision.

Source officielle, gratuite, sans clé API : les archives mensuelles de Binance.
    https://data.binance.vision/data/futures/um/monthly/klines/SOLUSDT/4h/SOLUSDT-4h-2025-01.zip

Le cache disque est la règle : un mois téléchargé n'est jamais retéléchargé.
Un 404 signifie simplement que le mois n'existe pas (token pas encore listé, ou
mois en cours pas encore archivé) — ce n'est pas une erreur.
"""
from __future__ import annotations

import io
import os
import time
import zipfile
import urllib.request
import urllib.error

import numpy as np
import pandas as pd

BASE = "https://data.binance.vision/data"

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]


class ReseauBloque(RuntimeError):
    """L'hôte est injoignable — politique réseau, pas panne transitoire."""


def _url(symbol: str, interval: str, year: int, month: int, market: str) -> str:
    seg = {"futures": "futures/um", "spot": "spot"}[market]
    return (f"{BASE}/{seg}/monthly/klines/{symbol}/{interval}/"
            f"{symbol}-{interval}-{year}-{month:02d}.zip")


def _download(url: str, timeout: int = 60, retries: int = 3) -> bytes | None:
    """Renvoie le contenu, None si 404, lève ReseauBloque si l'hôte est filtré."""
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None                      # mois inexistant : normal
            last = e
        except (urllib.error.URLError, OSError) as e:
            msg = str(e).lower()
            if any(k in msg for k in ("403", "tunnel", "proxy", "forbidden", "refused")):
                raise ReseauBloque(
                    f"data.binance.vision injoignable ({e}).\n"
                    "L'environnement filtre cet hôte. Deux options :\n"
                    "  - autoriser data.binance.vision dans la politique réseau de\n"
                    "    l'environnement (voir code.claude.com/docs — Claude Code on the web)\n"
                    "  - ou lancer ce script sur ta machine, où le réseau est libre."
                ) from e
            last = e
        time.sleep(2 ** attempt)
    raise ReseauBloque(f"échec après {retries} tentatives : {last}")


def parse_klines(raw: bytes) -> pd.DataFrame:
    """Parse un CSV de klines Binance, avec ou sans ligne d'en-tête.

    Les archives récentes portent un en-tête, les anciennes non. On teste si la
    première cellule est un entier (un timestamp) plutôt que de supposer.
    """
    text = raw.decode("utf-8", errors="replace")
    first = text.split(",", 1)[0].strip().lstrip("-")
    has_header = not first.isdigit()

    df = pd.read_csv(io.StringIO(text), header=0 if has_header else None)
    df.columns = KLINE_COLS[:len(df.columns)]
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()

    # open_time est en ms, parfois en us sur certaines archives récentes.
    ot = pd.to_numeric(df["open_time"], errors="coerce")
    unit = "us" if ot.dropna().iloc[0] > 1e14 else "ms"
    idx = pd.to_datetime(ot, unit=unit, utc=True).dt.tz_localize(None)

    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce")
                        for c in ("open", "high", "low", "close", "volume")})
    out.index = pd.DatetimeIndex(idx)
    out.index.name = "timestamp"
    return out.dropna(subset=["open", "high", "low", "close"]).sort_index()


def fetch_symbol(symbol: str, start: str, end: str, interval: str = "4h",
                 market: str = "futures", cache_dir: str = "cache_binance",
                 verbose: bool = True) -> pd.DataFrame:
    """Télécharge un symbole sur une plage de mois, avec cache disque."""
    os.makedirs(cache_dir, exist_ok=True)
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    frames, n_dl, n_cache, n_404 = [], 0, 0, 0

    y, m = t0.year, t0.month
    while (y, m) <= (t1.year, t1.month):
        cache = os.path.join(cache_dir, f"{symbol}-{interval}-{y}-{m:02d}.csv")
        if os.path.exists(cache):
            frames.append(pd.read_csv(cache, index_col=0, parse_dates=True))
            n_cache += 1
        else:
            blob = _download(_url(symbol, interval, y, m, market))
            if blob is None:
                n_404 += 1
            else:
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    raw = z.read(z.namelist()[0])
                df = parse_klines(raw)
                df.to_csv(cache)
                frames.append(df)
                n_dl += 1
        m += 1
        if m > 12:
            m, y = 1, y + 1

    if not frames:
        raise FileNotFoundError(f"Aucune donnée pour {symbol} entre {start} et {end}")

    full = pd.concat(frames).sort_index()
    full = full[~full.index.duplicated(keep="last")]
    full = full[(full.index >= t0) & (full.index < t1)]
    if verbose:
        print(f"  {symbol:<14} {len(full):>6} bougies  "
              f"{full.index[0]:%Y-%m-%d} -> {full.index[-1]:%Y-%m-%d}  "
              f"({n_dl} téléchargés, {n_cache} en cache, {n_404} mois absents)")
    return full


def fetch_universe(symbols, start: str, end: str, interval: str = "4h",
                   market: str = "futures", cache_dir: str = "cache_binance") -> dict:
    uni = {}
    for s in symbols:
        try:
            uni[s] = fetch_symbol(s, start, end, interval, market, cache_dir)
        except ReseauBloque:
            raise
        except Exception as e:
            print(f"  {s:<14} ECHEC : {e}")
    return uni
