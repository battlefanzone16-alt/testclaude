"""Lecture des dossiers .npy / .pkl du projet kheirbot_sniper.

On ne sait pas a priori dans quel ordre les colonnes sont rangées ni quelle est
l'unité du timestamp. Plutôt que de deviner, on DEDUIT l'agencement en testant
les invariants OHLC : high >= max(open, close) et low <= min(open, close).
Un mauvais agencement les viole presque partout ; le bon les respecte quasiment
toujours. C'est un test qui ne peut pas se tromper silencieusement.
"""
from __future__ import annotations

import os
import glob
import itertools

import numpy as np
import pandas as pd

from .loader import load_ohlcv, _to_datetime


def _scale_coherent(a: np.ndarray, cols: tuple, max_ratio: float = 3.0) -> bool:
    """Les 4 colonnes OHLC doivent être sur la MEME échelle.

    Sans ce garde-fou, une colonne de volume (~1e4) satisfait trivialement
    h >= max(o, c) et se fait élire "high". Quatre prix de la même bougie ne
    diffèrent jamais d'un facteur 3 en médiane ; un volume, si.
    """
    meds = [np.nanmedian(np.abs(a[:, j])) for j in cols]
    if any((not np.isfinite(m)) or m <= 0 for m in meds):
        return False
    return (max(meds) / min(meds)) <= max_ratio


def _score_layout(a: np.ndarray, cols: tuple) -> float:
    """Fraction de bougies respectant les invariants OHLC pour cet agencement."""
    if not _scale_coherent(a, cols):
        return 0.0
    o, h, l, c = (a[:, cols[k]] for k in range(4))
    ok = (h >= np.maximum(o, c) - 1e-9) & (l <= np.minimum(o, c) + 1e-9) & (l > 0)
    return float(np.mean(ok))


def _continuity_error(a: np.ndarray, cols: tuple) -> float:
    """Ecart moyen |open[i] - close[i-1]| / close[i-1].

    Les invariants OHLC sont SYMETRIQUES en open/close : h >= max(o,c) et
    l <= min(o,c) restent vrais si on échange les deux. Il faut donc un second
    critère pour les départager. En crypto (marché continu 24/7, sans gap
    d'ouverture), l'open d'une bougie colle au close de la précédente : le bon
    agencement a une erreur de continuité quasi nulle, l'agencement inversé a
    l'amplitude d'une bougie entière.
    """
    o, c = a[:, cols[0]], a[:, cols[3]]
    prev = c[:-1]
    good = np.isfinite(prev) & (prev > 0)
    if good.sum() < 10:
        return np.inf
    return float(np.mean(np.abs(o[1:][good] - prev[good]) / prev[good]))


def _detect_time_column(a: np.ndarray) -> int | None:
    """Une colonne de temps est strictement croissante et de grande magnitude."""
    for j in range(a.shape[1]):
        v = a[:, j]
        if not np.all(np.isfinite(v)):
            continue
        if np.all(np.diff(v) > 0) and np.nanmedian(np.abs(v)) > 1e8:
            return j
    return None


def array_to_ohlcv(a: np.ndarray, index=None) -> pd.DataFrame:
    """Transforme un tableau 2D en OHLCV en déduisant l'agencement des colonnes."""
    a = np.asarray(a, dtype=float)
    if a.ndim != 2:
        raise ValueError(f"tableau de dimension {a.ndim}, 2D attendu")
    if a.shape[0] < a.shape[1]:          # transposé
        a = a.T
    if a.shape[1] < 4:
        raise ValueError(f"{a.shape[1]} colonnes, au moins 4 (OHLC) attendues")

    tcol = _detect_time_column(a)
    ts = a[:, tcol] if tcol is not None else None
    price_cols = [j for j in range(a.shape[1]) if j != tcol]

    # On teste les agencements des 4 colonnes OHLC parmi les colonnes de prix,
    # puis on départage les ex aequo par la continuité open/close.
    scored = [(_score_layout(a, combo), combo)
              for combo in itertools.permutations(price_cols, 4)]
    best_score = max(s for s, _ in scored)
    if best_score < 0.95:
        raise ValueError(
            f"aucun agencement OHLC cohérent (meilleur score {best_score:.3f}). "
            "Vérifier le contenu du fichier."
        )
    tied = [c for s, c in scored if s >= best_score - 1e-9]
    best = min(tied, key=lambda c: _continuity_error(a, c))

    used = set(best) | ({tcol} if tcol is not None else set())
    vcands = [j for j in range(a.shape[1]) if j not in used]
    vol = a[:, vcands[0]] if vcands else np.full(a.shape[0], np.nan)

    df = pd.DataFrame({"open": a[:, best[0]], "high": a[:, best[1]],
                       "low": a[:, best[2]], "close": a[:, best[3]], "volume": vol})
    if index is not None:
        df.index = pd.DatetimeIndex(index)
    elif ts is not None:
        df.index = pd.DatetimeIndex(_to_datetime(pd.Series(ts)))
    else:
        raise ValueError("aucune colonne de temps détectée et aucun index fourni")
    df.index.name = "timestamp"
    return df.sort_index()[~df.index.duplicated(keep="last")]


def load_any(path: str) -> pd.DataFrame:
    """Charge un fichier de bougies quel que soit son format."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        a = np.load(path, allow_pickle=True)
        if a.dtype.names:                      # tableau structuré
            return load_structured(a)
        if a.dtype == object and a.size == 1:  # dict/DataFrame sérialisé
            return _from_object(a.item())
        return array_to_ohlcv(a)
    if ext == ".npz":
        z = np.load(path, allow_pickle=True)
        return _from_object({k: z[k] for k in z.files})
    if ext in (".pkl", ".pickle"):
        return _from_object(pd.read_pickle(path))
    return load_ohlcv(path)


def load_structured(a: np.ndarray) -> pd.DataFrame:
    return load_ohlcv_frame(pd.DataFrame({n: a[n] for n in a.dtype.names}))


def load_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise un DataFrame déjà en mémoire, en réutilisant les alias du loader."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as fh:
        tmp = fh.name
    try:
        df.to_csv(tmp, index=isinstance(df.index, pd.DatetimeIndex))
        return load_ohlcv(tmp)
    finally:
        os.unlink(tmp)


def _from_object(obj) -> pd.DataFrame:
    if isinstance(obj, pd.DataFrame):
        return (obj if isinstance(obj.index, pd.DatetimeIndex) and
                {"open", "high", "low", "close"} <= set(obj.columns)
                else load_ohlcv_frame(obj))
    if isinstance(obj, dict):
        keys = {k.lower(): k for k in obj}
        if {"open", "high", "low", "close"} <= set(keys):
            cols = {c: np.asarray(obj[keys[c]], dtype=float)
                    for c in ("open", "high", "low", "close")}
            cols["volume"] = (np.asarray(obj[keys["volume"]], dtype=float)
                              if "volume" in keys else np.nan)
            idx = None
            for tk in ("timestamp", "time", "date", "datetime", "open_time"):
                if tk in keys:
                    idx = _to_datetime(pd.Series(np.asarray(obj[keys[tk]])))
                    break
            if idx is None:
                raise ValueError("dict sans colonne de temps")
            return pd.DataFrame(cols, index=pd.DatetimeIndex(idx)).sort_index()
        # dict de tableaux 2D par token -> on ne sait pas lequel choisir ici
        raise ValueError(f"dict non reconnu, clés = {list(obj)[:10]}")
    if isinstance(obj, np.ndarray):
        return array_to_ohlcv(obj)
    raise ValueError(f"type non géré : {type(obj)}")


def scan_directory(d: str) -> list[str]:
    files = []
    for ext in ("npy", "npz", "pkl", "pickle", "csv", "parquet"):
        files += glob.glob(os.path.join(d, f"*.{ext}"))
    return sorted(files)
