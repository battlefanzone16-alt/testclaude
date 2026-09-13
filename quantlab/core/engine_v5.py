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

from .indicators import kalman_bq, donchian_combined, atr


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
    # modes de stop alternatifs. "wick" = mèche de la bougie de cassure (spec v5).
    #   "buffer"  : mèche élargie de sl_buffer (le prix vient de visiter ce niveau,
    #               33 % des stops tombaient dès la 1re bougie)
    #   "atr"     : entrée -/+ sl_atr_mult * ATR(sl_atr_len)
    #   "swing"   : plus bas/haut des sl_swing_n dernières bougies
    #   "none"    : aucun stop dur, la sortie souple gère seule
    sl_mode: str = "wick"
    sl_buffer: float = 0.005
    sl_atr_mult: float = 2.0
    sl_atr_len: int = 14
    sl_swing_n: int = 5
    sl_pct: float = 0.015                     # mode "pct" : stop fixe en % du prix d'entrée
    max_sl_dist: float | None = None
    max_dist_kalman: float | None = None
    min_dist_kalman: float | None = None      # cassure trop timide -> on saute
    # filtre d'entrée
    entry_above_median: bool = False          # levier n°2 du guide
    # côtés auxquels le filtre médiane s'applique : "both" | "long" | "short".
    # Mesuré : le filtre aide les longs (+0,86 -> +1,10) et nuit aux shorts
    # (+0,82 -> +0,48). Symétrique, les deux effets s'annulent.
    entry_median_sides: str = "both"
    # Durcissement du filtre médiane : exiger que la MÉDIANE elle-même soit du
    # bon côté du Kalman (med < kal pour un long). Implique entry_above_median
    # puisque med < kal < close, mais exige en plus que la structure Donchian
    # soit déjà sous la moyenne — pas seulement le prix.
    entry_median_vs_kalman: bool = False
    # Confirmation par le volume : volume de la bougie de cassure > SMA(n).
    entry_vol_ma: int | None = None
    entry_vol_mult: float = 1.0
    entry_vol_sides: str = "both"             # côtés soumis au filtre volume
    # Pente de la médiane Donchian à la bougie de signal, en ATR par bougie et
    # signée par le sens du trade (positive = médiane qui va dans le sens du
    # trade). Bornes inclusives, None = pas de borne.
    entry_slope_n: int | None = None
    entry_slope_min: float | None = None
    entry_slope_max: float | None = None
    entry_slope_sides: str = "both"
    # Pente de la LARGEUR du canal Donchian (haut - bas), en ATR par bougie,
    # NON signée : un canal qui s'écarte est une expansion de volatilité, quel
    # que soit le sens du trade.
    entry_width_n: int | None = None
    entry_width_min: float | None = None
    entry_width_sides: str = "both"
    # sorties
    variante_kalman_seul: bool = False
    sortie_rr: float | None = None
    # Prise partielle : on solde tp_part_frac de la position à tp_part_r fois le
    # risque, le reste continue avec la sortie souple. Le morceau sorti paie ses
    # propres frais. None = désactivé.
    tp_part_r: float | None = None
    tp_part_frac: float = 0.5
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
    # levier imposé : None = dimensionnement par le risque (risk_pct / distance au
    # stop), une valeur = taille fixe (1.0 = tout le capital, sans levier).
    fixed_lev: float | None = None
    frais_ar: float = 0.00086                 # 0,086 % aller-retour
    spread_x: float = 3.0


def backtest_v5(df: pd.DataFrame, cfg: CfgV5, token: str = "TOK",
                spread: float = 0.0002) -> pd.DataFrame:
    """Un token, une position à la fois. Retourne le journal des trades."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float);  c = df["close"].to_numpy(float)
    n = len(df)
    if cfg.entry_vol_ma:
        # moyenne causale : la bougie i incluse, son volume est connu à sa clôture
        vol = df["volume"].to_numpy(float)
        vma = pd.Series(vol).rolling(cfg.entry_vol_ma, min_periods=cfg.entry_vol_ma).mean().to_numpy()
    else:
        vol = vma = None
    kal = kalman_bq(c, cfg.kalman_pn, cfg.kalman_mn)
    up, lo, med = donchian_combined(h, l, cfg.dc_length, cfg.pvt_left, cfg.pvt_right)
    atr_arr = atr(h, l, c, cfg.sl_atr_len)

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
            applique = (cfg.entry_median_sides == "both"
                        or (cfg.entry_median_sides == "long" and side > 0)
                        or (cfg.entry_median_sides == "short" and side < 0))
            if applique and ((side > 0 and c[i] <= med[i]) or (side < 0 and c[i] >= med[i])):
                i += 1; continue

        # médiane Donchian du bon côté du Kalman (durcit le filtre précédent)
        if cfg.entry_median_vs_kalman:
            applique = (cfg.entry_median_sides == "both"
                        or (cfg.entry_median_sides == "long" and side > 0)
                        or (cfg.entry_median_sides == "short" and side < 0))
            if applique and ((side > 0 and med[i] >= kal[i]) or (side < 0 and med[i] <= kal[i])):
                i += 1; continue

        # pente de la médiane Donchian, normalisée par l'ATR
        if cfg.entry_slope_n:
            applique = (cfg.entry_slope_sides == "both"
                        or (cfg.entry_slope_sides == "long" and side > 0)
                        or (cfg.entry_slope_sides == "short" and side < 0))
            if applique:
                j0 = i - cfg.entry_slope_n
                av_i = atr_arr[i]
                if j0 < 0 or not np.isfinite(med[j0]) or not (av_i > 0):
                    i += 1; continue
                pente = side * (med[i] - med[j0]) / cfg.entry_slope_n / av_i
                if cfg.entry_slope_min is not None and pente < cfg.entry_slope_min:
                    i += 1; continue
                if cfg.entry_slope_max is not None and pente > cfg.entry_slope_max:
                    i += 1; continue

        # expansion du canal Donchian
        if cfg.entry_width_n:
            applique = (cfg.entry_width_sides == "both"
                        or (cfg.entry_width_sides == "long" and side > 0)
                        or (cfg.entry_width_sides == "short" and side < 0))
            if applique:
                j0 = i - cfg.entry_width_n
                av_i = atr_arr[i]
                if j0 < 0 or not np.isfinite(up[j0]) or not np.isfinite(lo[j0]) or not (av_i > 0):
                    i += 1; continue
                dw = ((up[i] - lo[i]) - (up[j0] - lo[j0])) / cfg.entry_width_n / av_i
                if cfg.entry_width_min is not None and dw < cfg.entry_width_min:
                    i += 1; continue

        # confirmation par le volume de la bougie de cassure
        if cfg.entry_vol_ma:
            applique = (cfg.entry_vol_sides == "both"
                        or (cfg.entry_vol_sides == "long" and side > 0)
                        or (cfg.entry_vol_sides == "short" and side < 0))
            if applique and not (np.isfinite(vma[i]) and vol[i] > cfg.entry_vol_mult * vma[i]):
                i += 1; continue

        entry_idx = i + 1
        entry = o[entry_idx]                              # ouverture de la bougie suivante
        if not np.isfinite(entry) or entry <= 0:
            i += 1; continue

        # stop dur
        if cfg.sl_donchian or cfg.sl_mode == "donchian":
            sl = lo[i] if side > 0 else up[i]
        elif cfg.sl_mode == "buffer":
            base = l[i] if side > 0 else h[i]
            sl = base * (1.0 - side * cfg.sl_buffer)
        elif cfg.sl_mode == "atr":
            av = atr_arr[i]
            sl = (entry - side * cfg.sl_atr_mult * av) if np.isfinite(av) else np.nan
        elif cfg.sl_mode == "swing":
            k0 = max(0, i - cfg.sl_swing_n + 1)
            sl = l[k0:i + 1].min() if side > 0 else h[k0:i + 1].max()
        elif cfg.sl_mode == "pct":
            sl = entry * (1.0 - side * cfg.sl_pct)
        elif cfg.sl_mode == "none":
            sl = 0.0 if side > 0 else float("inf")
        else:
            sl = l[i] if side > 0 else h[i]
        if not np.isfinite(sl):
            i += 1; continue
        if cfg.sl_mode == "none":
            av = atr_arr[i]
            if not np.isfinite(av) or av <= 0:
                i += 1; continue
            sl_dist = 2.0 * av / entry        # sizing sur l'ATR, faute de stop
        else:
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

        lev = (cfg.fixed_lev if cfg.fixed_lev is not None
               else min(cfg.risk_pct / sl_dist, cfg.max_lev))

        # état du trade
        sous_med = (c[i] <= med[i]) if side > 0 else (c[i] >= med[i])
        phase_med = not sous_med                          # bascule irréversible
        sl_cur = sl
        be_done = False
        surchauffe = False
        tp = entry * (1 + side * cfg.sortie_rr * sl_dist) if cfg.sortie_rr else None
        tp_p = (entry * (1 + side * cfg.tp_part_r * sl_dist)) if cfg.tp_part_r else None
        part_faite = False
        gain_partiel = 0.0          # en fraction du prix d'entrée, déjà net de frais
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
            # --- 2bis) prise partielle : ordre limite, intrabar
            if tp_p is not None and not part_faite:
                touche = (h[j] >= tp_p) if side > 0 else (l[j] <= tp_p)
                if touche:
                    r_brut = side * (tp_p - entry) / entry
                    gain_partiel = cfg.tp_part_frac * (r_brut - cost)
                    part_faite = True
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
        if part_faite:
            # le solde restant ne porte plus que (1 - frac) de la position
            reste = 1.0 - cfg.tp_part_frac
            net = gain_partiel + reste * (gross - cost)
            gross = cfg.tp_part_frac * side * (tp_p - entry) / entry + reste * gross
        else:
            net = gross - cost
        trades.append(dict(token=token, entry_time=df.index[entry_idx], exit_time=df.index[exit_idx],
                           side="LONG" if side > 0 else "SHORT", entry=entry, sl=sl, exit=exit_px,
                           reason=("part+" + reason) if part_faite else reason,
                           bars=exit_idx - entry_idx, sl_dist=sl_dist, lev=lev,
                           sous_med=bool(sous_med), gross=gross * 100, net=net * 100,
                           R=net / sl_dist, pnl_frac=net * lev))
        i = exit_idx                                       # pas de ré-entrée avant la sortie
    return pd.DataFrame(trades)
