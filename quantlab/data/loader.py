"""OHLCV loading with tolerant column detection.

The point of this module is that you should be able to point it at whatever CSV
your exchange / broker / data vendor spat out and get a clean, sorted,
duplicate-free, tz-naive UTC DataFrame with columns open/high/low/close/volume.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

# Every spelling of an OHLCV column we have ever had to deal with.
_ALIASES = {
    "open": ["open", "o", "Open", "OPEN", "open_price", "px_open"],
    "high": ["high", "h", "High", "HIGH", "high_price", "px_high"],
    "low": ["low", "l", "Low", "LOW", "low_price", "px_low"],
    "close": ["close", "c", "Close", "CLOSE", "close_price", "px_close",
              "adj_close", "Adj Close", "adjclose", "last", "price"],
    "volume": ["volume", "v", "Volume", "VOLUME", "vol", "qty", "base_volume",
               "Volume USDT", "quote_volume"],
}
_TIME_ALIASES = ["timestamp", "time", "date", "datetime", "Date", "Datetime",
                 "Timestamp", "open_time", "OpenTime", "candle_begin_time", "ts"]


def _find(cols, aliases):
    lower = {str(c).strip().lower(): c for c in cols}
    for a in aliases:
        if a in cols:
            return a
        if a.lower() in lower:
            return lower[a.lower()]
    return None


def _to_datetime(s: pd.Series) -> pd.Series:
    """Parse a time column that may be ISO strings, or epoch s/ms/us/ns.

    On teste la numéricité avec l'API pandas et non np.issubdtype : cette
    dernière lève sur les dtypes d'extension (StringDtype, Int64, ...) que
    pandas produit de plus en plus par défaut à la lecture d'un CSV.
    """
    if pd.api.types.is_datetime64_any_dtype(s):
        out = pd.to_datetime(s, utc=True)
        return out.dt.tz_localize(None)
    if pd.api.types.is_numeric_dtype(s):
        nn = s.dropna()
        if nn.empty:
            return pd.Series(pd.NaT, index=s.index)
        v = float(nn.iloc[0])
        # Pick the epoch unit by order of magnitude of a sample value.
        unit = "s" if v < 1e11 else "ms" if v < 1e14 else "us" if v < 1e17 else "ns"
        return pd.to_datetime(s, unit=unit, utc=True).dt.tz_localize(None)
    out = pd.to_datetime(s.astype("object"), utc=True, format="mixed", errors="coerce")
    return out.dt.tz_localize(None)


def load_ohlcv(path: str, tz_naive: bool = True) -> pd.DataFrame:
    """Read a CSV/parquet of bars and normalise it.

    Returns a DataFrame indexed by DatetimeIndex with float columns
    open, high, low, close, volume — sorted, de-duplicated, NaN-free on close.
    """
    if str(path).endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    # The time key may already be the index.
    tcol = _find(df.columns, _TIME_ALIASES)
    if tcol is not None:
        idx = _to_datetime(df[tcol])
        df = df.drop(columns=[tcol])
    elif isinstance(df.index, pd.DatetimeIndex):
        idx = pd.Series(df.index)
    else:
        raise ValueError(
            f"No time column found. Looked for {_TIME_ALIASES}, got {list(df.columns)}"
        )

    out = pd.DataFrame(index=pd.DatetimeIndex(idx))
    for canon, aliases in _ALIASES.items():
        c = _find(df.columns, aliases)
        if c is None:
            if canon == "volume":
                out[canon] = np.nan  # volume is optional
                continue
            raise ValueError(f"Missing '{canon}' column. Got {list(df.columns)}")
        out[canon] = pd.to_numeric(pd.Series(df[c]).astype("object"),
                                   errors="coerce").to_numpy(dtype=float)

    out.index.name = "timestamp"
    out = out[~out.index.isna()]
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out = out.dropna(subset=["open", "high", "low", "close"])

    if (out["close"] <= 0).any():
        out = out[out["close"] > 0]
    return out


def infer_bars_per_year(index: pd.DatetimeIndex) -> float:
    """Annualisation factor inferred from the median bar spacing.

    Uses calendar time (365d) so that crypto 24/7 series and daily equity series
    are both handled without the caller declaring an asset class. For daily
    equity bars the median spacing is ~1d over weekdays, which yields ~252.
    """
    if len(index) < 3:
        return 252.0
    deltas = pd.Series(index).diff().dropna()
    med = deltas.median().total_seconds()
    if med <= 0:
        return 252.0
    bars_per_day = 86400.0 / med
    if bars_per_day <= 1.05:
        # Daily-or-slower: count actual observed bars per calendar year.
        span_years = (index[-1] - index[0]).total_seconds() / (365.25 * 86400)
        if span_years > 0.25:
            return len(index) / span_years
        return 252.0
    return bars_per_day * 365.25
