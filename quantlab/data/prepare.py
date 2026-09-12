"""1-min -> H4.

Note sur le stop intrabar : le low d'une bougie H4 EST le minimum des 240 lows
1-min qu'elle contient. Tester « le low H4 touche-t-il le stop » est donc
strictement équivalent à boucler minute par minute pour DETECTER le touch. La
seule chose que la minute apporte en plus est l'ORDRE intrabar quand stop dur et
sortie souple tombent dans la même bougie — et là le moteur donne toujours la
priorité au stop, ce qui est l'hypothèse conservatrice. On peut donc travailler
en H4 sans rien perdre, et gagner deux ordres de grandeur de vitesse.
"""
from __future__ import annotations

import os
import glob
import pandas as pd

from .loader import load_ohlcv
from .npy_loader import load_any, scan_directory

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample_ohlcv(df: pd.DataFrame, rule: str = "4h") -> pd.DataFrame:
    out = df.resample(rule, label="right", closed="left").agg(AGG)
    return out.dropna(subset=["open", "high", "low", "close"])


def _write_bars(h4: pd.DataFrame, out_dir: str, token: str) -> str:
    """Ecrit en parquet si possible, sinon en CSV.

    pyarrow est un extra : il ne doit pas être un point de rupture. Le reste du
    pipeline relit indifféremment les deux formats.
    """
    try:
        h4.to_parquet(os.path.join(out_dir, f"{token}.parquet"))
        return "parquet"
    except (ImportError, ValueError):
        h4.to_csv(os.path.join(out_dir, f"{token}.csv"))
        return "csv"


def prepare_directory(src_dir: str, out_dir: str, rule: str = "4h",
                      pattern: str = "*", min_bars: int = 500) -> dict:
    """Convertit tous les fichiers de bougies d'un dossier en H4 parquet.

    Le nom du token est déduit du nom de fichier (BTCUSDT_1m.csv -> BTCUSDT).
    """
    os.makedirs(out_dir, exist_ok=True)
    files = [f for f in scan_directory(src_dir)
             if pattern == "*" or glob.fnmatch.fnmatch(os.path.basename(f), pattern + ".*")]
    if not files:
        raise FileNotFoundError(f"Aucun fichier de données dans {src_dir}")

    report = {}
    for f in sorted(files):
        name = os.path.basename(f)
        token = name.split(".")[0].split("_")[0].upper()
        try:
            raw = load_any(f)
            h4 = resample_ohlcv(raw, rule)
            if len(h4) < min_bars:
                report[token] = f"ignoré ({len(h4)} bougies < {min_bars})"
                continue
            ext = _write_bars(h4, out_dir, token)
            report[token] = (f"{len(h4)} bougies  {h4.index[0]:%Y-%m-%d} -> "
                             f"{h4.index[-1]:%Y-%m-%d}  [{ext}]")
        except Exception as e:
            report[token] = f"ERREUR: {e}"
    return report


def load_universe(data_dir: str, exclude: list[str] | None = None,
                  min_bars: int = 500) -> dict:
    """Charge un dossier de fichiers H4 en dict {token: DataFrame}."""
    exclude = set(exclude or [])
    universe = {}
    files = scan_directory(data_dir)
    for f in files:
        token = os.path.basename(f).split(".")[0].split("_")[0].upper()
        if token in exclude:
            continue
        df = pd.read_parquet(f) if f.endswith(".parquet") else load_any(f)
        if len(df) >= min_bars:
            universe[token] = df
    if not universe:
        raise FileNotFoundError(f"Aucun token exploitable dans {data_dir}")
    return universe


def align_universe(universe: dict, start=None, end=None) -> dict:
    """Restreint tous les tokens à une fenêtre commune."""
    out = {}
    for t, df in universe.items():
        d = df
        if start is not None:
            d = d[d.index >= pd.Timestamp(start)]
        if end is not None:
            d = d[d.index < pd.Timestamp(end)]
        if len(d) > 250:
            out[t] = d
    return out
