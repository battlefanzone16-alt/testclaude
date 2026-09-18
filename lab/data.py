"""Donnee de marche : klines et funding, depuis les archives publiques Binance.

Une seule responsabilite : rendre un DataFrame propre, indexe UTC, sans trou
silencieux. Un mois telecharge n'est jamais retelecharge.

Le prix vient de Binance (historique long, granularite 1 min disponible).
L'execution simulee, elle, est facturee au bareme Hyperliquid (voir lab/costs.py).
"""
from __future__ import annotations

import http.client
import io
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BASE = "https://data.binance.vision/data"
CACHE = Path(__file__).resolve().parent.parent / "data_cache"

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]


def _months(start: str, end: str) -> list[tuple[int, int]]:
    return [(p.year, p.month) for p in pd.period_range(start=start, end=end, freq="M")]


def _fetch(url: str, retries: int = 5) -> bytes | None:
    """Contenu brut valide, None si 404 (mois inexistant : normal, pas une erreur).

    Le proxy de l'environnement coupe parfois un transfert en cours : on ne fait
    donc pas confiance a une reponse 200, on verifie que le zip s'ouvre.
    """
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                raw = r.read()
            zipfile.ZipFile(io.BytesIO(raw)).testzip()
            return raw
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except (urllib.error.URLError, OSError, http.client.HTTPException,
                zipfile.BadZipFile) as e:
            last = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"echec reseau sur {url} : {last!r}")


def _unzip(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return z.read(z.namelist()[0]).decode("utf-8", errors="replace")


def _read_csv(text: str, cols: list[str]) -> pd.DataFrame:
    first = text.split(",", 1)[0].strip().lstrip("-")
    df = pd.read_csv(io.StringIO(text), header=None if first.isdigit() else 0)
    df.columns = cols[:df.shape[1]]
    return df


def _ts(series: pd.Series) -> pd.DatetimeIndex:
    v = pd.to_numeric(series, errors="coerce")
    unit = "us" if v.dropna().iloc[0] > 1e14 else "ms"
    return pd.DatetimeIndex(pd.to_datetime(v, unit=unit, utc=True).dt.tz_localize(None))


def _cached(key: Path, build) -> pd.DataFrame | None:
    if key.exists():
        return pd.read_parquet(key)
    df = build()
    if df is None:
        return None
    key.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(key)
    return df


def load(symbol: str = "BTCUSDT", interval: str = "1h",
         start: str = "2019-09", end: str = "2026-09") -> pd.DataFrame:
    """OHLCV perp USDT-M, mois concatenes, tries, dedoublonnes."""
    out = []
    for year, month in _months(start, end):
        key = CACHE / "klines" / symbol / interval / f"{year}-{month:02d}.parquet"

        def build(y=year, m=month):
            url = (f"{BASE}/futures/um/monthly/klines/{symbol}/{interval}/"
                   f"{symbol}-{interval}-{y}-{m:02d}.zip")
            raw = _fetch(url)
            if raw is None:
                return None
            df = _read_csv(_unzip(raw), KLINE_COLS)
            df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
            df.index = _ts(df["open_time"])
            df = df.drop(columns=["open_time"]).astype(float)
            df.index.name = "ts"
            return df

        df = _cached(key, build)
        if df is not None:
            out.append(df)
    if not out:
        raise RuntimeError(f"aucune donnee pour {symbol} {interval}")
    df = pd.concat(out).sort_index()
    return df[~df.index.duplicated(keep="first")]


def load_funding(symbol: str = "BTCUSDT",
                 start: str = "2019-09", end: str = "2026-09") -> pd.Series:
    """Taux de funding 8 h (fraction du notionnel), indexe sur l'heure de calcul.

    Proxy du funding Hyperliquid, dont l'API est hors d'atteinte depuis cet
    environnement. Structure identique (premium + interet), meme basis sur BTC.
    """
    out = []
    for year, month in _months(start, end):
        key = CACHE / "funding" / symbol / f"{year}-{month:02d}.parquet"

        def build(y=year, m=month):
            url = (f"{BASE}/futures/um/monthly/fundingRate/{symbol}/"
                   f"{symbol}-fundingRate-{y}-{m:02d}.zip")
            raw = _fetch(url)
            if raw is None:
                return None
            df = _read_csv(_unzip(raw),
                           ["calc_time", "funding_interval_hours", "last_funding_rate"])
            df.index = _ts(df["calc_time"])
            df.index.name = "ts"
            return df[["funding_interval_hours", "last_funding_rate"]].astype(float)

        df = _cached(key, build)
        if df is not None:
            out.append(df)
    if not out:
        raise RuntimeError(f"aucun funding pour {symbol}")
    df = pd.concat(out).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df["last_funding_rate"]


def audit(df: pd.DataFrame, interval: str = "1h") -> dict:
    """Trous, incoherences OHLC, NaN — a regarder avant tout backtest."""
    full = pd.date_range(df.index[0], df.index[-1], freq=pd.Timedelta(interval))
    bad = ((df["high"] < df["low"]) |
           (df["close"] > df["high"]) | (df["close"] < df["low"]) |
           (df["open"] > df["high"]) | (df["open"] < df["low"]))
    return {
        "debut": str(df.index[0]), "fin": str(df.index[-1]),
        "barres": len(df), "attendues": len(full),
        "manquantes": len(full.difference(df.index)),
        "ohlc_incoherent": int(bad.sum()),
        "close_nan": int(df["close"].isna().sum()),
        "volume_zero": int((df["volume"] == 0).sum()),
    }


if __name__ == "__main__":
    px = load("BTCUSDT", "1h")
    print("klines :", audit(px, "1h"))
    fr = load_funding("BTCUSDT")
    print(f"funding : {len(fr)} points, {fr.index[0]} -> {fr.index[-1]}, "
          f"moyenne 8h = {fr.mean()*100:.4f}% ({fr.mean()*3*365*100:.1f}%/an)")
