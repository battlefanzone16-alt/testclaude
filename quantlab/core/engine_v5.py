"""Moteur fidèle à la spec Kalman v5 (trend-following H4, 1 position par token).

Écarts assumés par rapport au moteur `engine.py` du dépôt, qui divergeait :
  - entrée à l'OUVERTURE de la bougie suivant le croisement (et non à sa clôture) ;
  - sortie souple à DEUX PHASES (Kalman tant que sous la médiane, puis médiane) ;
  - time-stops, stratagème pente, stratagème surchauffe, break-even, TP en R.

Conventions anti-biais :
  - tous les indicateurs de la bougie i n'utilisent que l'information <= clôture i
    (les pivots Donchian sont publiés avec pvt_right bougies de retard) ;
  - le signal est lu à la clôture de i, l'exécution a lieu à l'ouverture de i+1 :
    aucune information de i+1 ne sert à décider ;
  - le stop dur est vérifié en intrabar et prime sur toute sortie à la clôture.

Le stop dur est testé sur le low/high H4. C'est strictement équivalent à un test
minute par minute pour la DÉTECTION (le low H4 est le min des lows 1-min) ; seul
le remplissage exact en cas de gap diffère.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .indicators import kalman_bq, donchian_combined


@dataclass
class CfgV5:
    # indicateurs
    kalman_pn: float = 0.001
    kalman_mn: float = 1.0
    dc_length: int = 20
    pvt_left: int = 2
    pvt_right: int = 4
    # sens
    enable_long: bool = True
    enable_short: bool = False
    # stop dur
    sl_donchian: bool = False
    max_sl_dist: float | None = None
    max_dist_kalman: float | None = None
    min_dist_kalman: float | None = None      # cassure trop timide -> on saute
    # filtre d'entrée
    entry_above_median: bool = False          # levier n°2 du guide
    # sorties
    variante_kalman_seul: bool = False
    sortie_rr: float | None = None
    be_activation_pct: float | None = None
    time_below_n: int | None = None           # levier n°1 du guide
    time_above_n: int | None = None
    time_above_pct: float | None = None
    sortie_pente: bool = False
    pente_min_r: float = 2.0
    sortie_surchauffe: bool = False
    seuil_surchauffe: float = 0.08
    # sizing / coûts
    risk_pct: float = 0.01
    max_lev: float = 3.0
    frais_ar: float = 0.00086                 # 0,086 % aller-retour
    spread_x: float = 3.0


def backtest_v5(df: pd.DataFrame, cfg: CfgV5, token: str = "TOK",
                spread: float = 0.0002) -> pd.DataFrame:
    """Un token, une position à la fois. Retourne le journal des trades."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float);  c = df["close"].to_numpy(float)
    n = len(df)
    kal = kalman_bq(c, cfg.kalman_pn, cfg.kalman_mn)
    up, lo, med = donchian_combined(h, l, cfg.dc_length, cfg.pvt_left, cfg.pvt_right)

    prev_c = np.concatenate(([np.nan], c[:-1]))
    prev_k = np.concatenate(([np.nan], kal[:-1]))
    cross_up = (c > kal) & (prev_c <= prev_k)
    cross_dn = (c < kal) & (prev_c >= prev_k)

    cost = cfg.frais_ar + spread * cfg.spread_x          # fraction, aller-retour
    trades = []
    i = 0
    while i < n - 1:
        side = 0
        if cfg.enable_long and cross_up[i]:  side = 1
        elif cfg.enable_short and cross_dn[i]: side = -1
        if side == 0:
            i += 1; continue
        if not np.isfinite(med[i]):
            i += 1; continue

        # filtre d'entrée : exiger le bon côté de la médiane DÈS l'entrée
        if cfg.entry_above_median:
            if (side > 0 and c[i] <= med[i]) or (side < 0 and c[i] >= med[i]):
                i += 1; continue

        entry_idx = i + 1
        entry = o[entry_idx]                              # ouverture de la bougie suivante
        if not np.isfinite(entry) or entry <= 0:
            i += 1; continue

        # stop dur : mèche de la bougie de cassure, ou borne Donchian
        if cfg.sl_donchian:
            sl = lo[i] if side > 0 else up[i]
        else:
            sl = l[i] if side > 0 else h[i]
        if not np.isfinite(sl):
            i += 1; continue
        sl_dist = side * (entry - sl) / entry
        if not (sl_dist > 0):
            i += 1; continue
        if cfg.max_sl_dist is not None and sl_dist > cfg.max_sl_dist:
            i += 1; continue
        d_kal = abs(c[i] - kal[i]) / c[i] if np.isfinite(kal[i]) else np.nan
        if cfg.max_dist_kalman is not None and (not np.isfinite(d_kal) or d_kal > cfg.max_dist_kalman):
            i += 1; continue
        if cfg.min_dist_kalman is not None and (not np.isfinite(d_kal) or d_kal < cfg.min_dist_kalman):
            i += 1; continue

        lev = min(cfg.risk_pct / sl_dist, cfg.max_lev)

        # état du trade
        sous_med = (c[i] <= med[i]) if side > 0 else (c[i] >= med[i])
        phase_med = not sous_med                          # bascule irréversible
        sl_cur = sl
        be_done = False
        surchauffe = False
        tp = entry * (1 + side * cfg.sortie_rr * sl_dist) if cfg.sortie_rr else None
        exit_idx = exit_px = None; reason = None

        for j in range(entry_idx, n):
            # --- 1) stop dur / break-even : intrabar, priorité absolue
            hit = (l[j] <= sl_cur) if side > 0 else (h[j] >= sl_cur)
            if hit:
                exit_idx, exit_px, reason = j, sl_cur, ("BE" if be_done else "SL_dur"); break
            # --- 2) TP en R : intrabar, ordre limite
            if tp is not None:
                tph = (h[j] >= tp) if side > 0 else (l[j] <= tp)
                if tph:
                    exit_idx, exit_px, reason = j, tp, "TP_RR"; break
            # --- 3) armement du break-even (intrabar, après les sorties)
            if cfg.be_activation_pct is not None and not be_done:
                ext = h[j] if side > 0 else l[j]
                if side * (ext - entry) / entry >= cfg.be_activation_pct / 100.0:
                    sl_cur = entry; be_done = True
            # --- à partir d'ici : décisions à la CLÔTURE de j
            if not np.isfinite(med[j]) or not np.isfinite(kal[j]):
                continue
            franchi = (c[j] > med[j]) if side > 0 else (c[j] < med[j])
            if franchi:
                phase_med = True
            k = j - entry_idx + 1                          # bougies écoulées depuis l'entrée
            # --- 4) time-stops
            if cfg.time_below_n is not None and not phase_med and k >= cfg.time_below_n:
                exit_idx, exit_px, reason = j, c[j], "time<med"; break
            if (cfg.time_above_n is not None and phase_med and k >= cfg.time_above_n
                    and cfg.time_above_pct is not None):
                if side * (c[j] - entry) / entry < cfg.time_above_pct / 100.0:
                    exit_idx, exit_px, reason = j, c[j], "time+%"; break
            # --- 5) stratagème A : décélération de la pente Kalman en profit
            if cfg.sortie_pente and j > entry_idx:
                gross = side * (c[j] - entry) / entry
                if gross / sl_dist >= cfg.pente_min_r:
                    p_now = side * (kal[j] - kal[j - 1])
                    p_prev = side * (kal[j - 1] - kal[j - 2]) if j >= 2 else p_now
                    if p_now < p_prev:
                        exit_idx, exit_px, reason = j, c[j], "ralentissement_kal"; break
            # --- 6) stratagème B : trail serré sur surchauffe (verrou)
            if cfg.sortie_surchauffe:
                ecart = side * (c[j] - kal[j]) / kal[j]
                if ecart > cfg.seuil_surchauffe:
                    surchauffe = True
                if surchauffe and j > entry_idx:
                    if (side > 0 and c[j] < l[j - 1]) or (side < 0 and c[j] > h[j - 1]):
                        exit_idx, exit_px, reason = j, c[j], "surchauffe"; break
            # --- 7) sortie souple : deux phases
            if cfg.variante_kalman_seul or not phase_med:
                if (side > 0 and c[j] < kal[j]) or (side < 0 and c[j] > kal[j]):
                    exit_idx, exit_px, reason = j, c[j], "clot_kalman"; break
            else:
                if (side > 0 and c[j] < med[j]) or (side < 0 and c[j] > med[j]):
                    exit_idx, exit_px, reason = j, c[j], "clot_mediane"; break

        if exit_idx is None:
            exit_idx, exit_px, reason = n - 1, c[n - 1], "fin_data"

        gross = side * (exit_px - entry) / entry
        net = gross - cost
        trades.append(dict(token=token, entry_time=df.index[entry_idx], exit_time=df.index[exit_idx],
                           side="LONG" if side > 0 else "SHORT", entry=entry, sl=sl, exit=exit_px,
                           reason=reason, bars=exit_idx - entry_idx, sl_dist=sl_dist, lev=lev,
                           sous_med=bool(sous_med), gross=gross * 100, net=net * 100,
                           R=net / sl_dist, pnl_frac=net * lev))
        i = exit_idx                                       # pas de ré-entrée avant la sortie
    return pd.DataFrame(trades)
