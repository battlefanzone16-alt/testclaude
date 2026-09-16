"""Backtest en TEMPS-TICK, avec budget de latence explicite.

Ce que corrige ce moteur. Toute l'etude precedente detecte sur des bougies
1 minute et entre a l'ouverture de la bougie suivante : entre l'information et
l'ordre, il s'ecoule 30 a 60 secondes. Sur un mouvement qui fait l'essentiel de
son chemin en quelques minutes, ce n'est pas un detail de mise en oeuvre, c'est
peut-etre tout le sujet. Un bot reel agit en millisecondes.

Ici tout se passe sur le flux de trades :
  - detection sur une fenetre glissante de W secondes, normalisee par le regime
    du token mesure sur l'heure precedente ;
  - entree au premier trade survenant au moins L millisecondes apres le tick
    declencheur - L est le budget de latence, parametre et assume ;
  - execution par balayage reel du flux agressif, pas par un slippage suppose ;
  - sortie en temps-tick : stop, trailing et time stop exprimes en secondes.

Le detecteur tourne sur la journee entiere, pas seulement autour des evenements
connus : les faux positifs comptent autant que les vrais.
"""
from __future__ import annotations

import numpy as np

SEC = 1.0


def baseline(t, px, qv, grid_s=300.0, look_s=3600.0):
    """Regime du token, recalcule sur une grille et lu de facon causale.

    Renvoie une fonction g(ts) -> (sigma_par_sec, volume_par_sec, trades_par_sec)
    n'utilisant que des trades anterieurs au dernier point de grille <= ts.
    """
    t0, t1 = t[0], t[-1]
    grid = np.arange(t0 + look_s, t1 + grid_s, grid_s)
    sig = np.full(len(grid), np.nan)
    vps = np.full(len(grid), np.nan)
    tps = np.full(len(grid), np.nan)
    for i, g in enumerate(grid):
        a = np.searchsorted(t, g - look_s)
        b = np.searchsorted(t, g)
        if b - a < 200:
            continue
        p = px[a:b]
        # volatilite par seconde, estimee sur des rendements a 10 s
        idx = np.searchsorted(t[a:b], t[a:b] + 10.0)
        idx = np.clip(idx, 0, b - a - 1)
        r = p[idx] / p - 1.0
        r = r[np.isfinite(r)]
        sig[i] = np.std(r) / np.sqrt(10.0) if len(r) > 50 else np.nan
        vps[i] = qv[a:b].sum() / look_s
        tps[i] = (b - a) / look_s
    return grid, sig, vps, tps


def detect(t, px, qv, sell, W=30.0, z_min=6.0, vol_mult=8.0, cooldown=900.0,
           grid=None, sig=None, vps=None, tps=None, buy_ratio_min=0.55):
    """Declenchements en temps-tick. Renvoie les indices des trades declencheurs.

    Conditions, toutes causales :
      - rendement sur W secondes >= z_min fois le mouvement W-secondes typique ;
      - volume agressif sur W secondes >= vol_mult fois le volume normal ;
      - flux majoritairement acheteur sur la fenetre.
    """
    n = len(t)
    back = np.searchsorted(t, t - W, side="left")
    gi = np.searchsorted(grid, t, side="right") - 1     # dernier point de grille <= t
    ok = gi >= 0
    out = []
    last = -1e18
    unit = np.full(n, np.nan)
    unit[ok] = sig[gi[ok]] * np.sqrt(W)
    volref = np.full(n, np.nan)
    volref[ok] = vps[gi[ok]] * W
    cum_qv = np.concatenate([[0.0], np.cumsum(qv)])
    buy = qv * (~sell)
    cum_buy = np.concatenate([[0.0], np.cumsum(buy)])

    for i in range(n):
        if not ok[i] or t[i] - last < cooldown:
            continue
        u, vr = unit[i], volref[i]
        if not (np.isfinite(u) and u > 0 and np.isfinite(vr) and vr > 0):
            continue
        j = back[i]
        if i - j < 10:
            continue
        r = px[i] / px[j] - 1.0
        if r <= 0 or r / u < z_min:
            continue
        v = cum_qv[i + 1] - cum_qv[j]
        if v / vr < vol_mult:
            continue
        b = cum_buy[i + 1] - cum_buy[j]
        if b / v < buy_ratio_min:
            continue
        out.append(i)
        last = t[i]
    return np.array(out, dtype=np.int64)


def sweep_buy(t, px, qv, sell, t_start, taille, horizon=120.0):
    """Prix moyen paye par un achat au marche de `taille` dollars a t_start."""
    a = np.searchsorted(t, t_start)
    b = np.searchsorted(t, t_start + horizon)
    if b - a < 3:
        return np.nan
    m = ~sell[a:b]
    p, q = px[a:b][m], qv[a:b][m]
    if len(p) < 2:
        return np.nan
    cum = np.cumsum(q)
    k = np.searchsorted(cum, taille)
    if k >= len(cum):
        return np.nan
    w = q[:k + 1].copy()
    w[-1] -= (cum[k] - taille)
    return float(np.dot(p[:k + 1], w) / w.sum())


def sweep_sell(t, px, qv, sell, t_start, taille, horizon=120.0):
    """Prix moyen obtenu par une vente au marche de `taille` dollars."""
    a = np.searchsorted(t, t_start)
    b = np.searchsorted(t, t_start + horizon)
    if b - a < 3:
        return np.nan
    m = sell[a:b]
    p, q = px[a:b][m], qv[a:b][m]
    if len(p) < 2:
        return np.nan
    cum = np.cumsum(q)
    k = np.searchsorted(cum, taille)
    if k >= len(cum):
        return np.nan
    w = q[:k + 1].copy()
    w[-1] -= (cum[k] - taille)
    return float(np.dot(p[:k + 1], w) / w.sum())


def run_trade(t, px, qv, sell, i_sig, latence_ms, taille,
              stop_pct, trail_pct, max_hold_s, fee_bps=4.5):
    """Un trade complet, en temps-tick. Renvoie (ret_net, duree_s, raison)."""
    t_ent = t[i_sig] + latence_ms / 1000.0
    px_in = sweep_buy(t, px, qv, sell, t_ent, taille)
    if not np.isfinite(px_in):
        return None
    a = np.searchsorted(t, t_ent)
    b = np.searchsorted(t, t_ent + max_hold_s)
    if b - a < 5:
        return None
    seg_t, seg_p = t[a:b], px[a:b]
    peak = px_in
    stop = px_in * (1.0 - stop_pct)
    for k in range(len(seg_p)):
        p = seg_p[k]
        if p <= stop:
            out = sweep_sell(t, px, qv, sell, seg_t[k], taille)
            if not np.isfinite(out):
                out = p
            c = fee_bps / 1e4
            return ((out / px_in - 1.0) - 2 * c, seg_t[k] - t_ent,
                    "trail" if stop > px_in * (1.0 - stop_pct) else "stop")
        if p > peak:
            peak = p
            stop = max(stop, peak * (1.0 - trail_pct))
    out = sweep_sell(t, px, qv, sell, seg_t[-1], taille)
    if not np.isfinite(out):
        out = seg_p[-1]
    c = fee_bps / 1e4
    return ((out / px_in - 1.0) - 2 * c, seg_t[-1] - t_ent, "time")


def fill_passif(t, px, sell, t0, limite, fenetre_s, strict=True):
    """Un ordre limite ACHAT pose a `limite` est-il execute dans la fenetre ?

    En temps-tick il n'y a aucune ambiguite d'ordonnancement : les trades sont
    sequentiels et horodates. C'est precisement le piege qui avait fabrique un
    faux resultat sur bougies 1 minute, et il ne peut pas se produire ici.

    Un ordre d'achat au repos est execute quand un VENDEUR agressif descend
    jusqu'a notre niveau. Dans la convention Binance, ces trades portent
    is_buyer_maker = true (l'acheteur etait maker). `strict` exige que le prix
    passe SOUS la limite plutot que de l'effleurer : sans cela on suppose etre
    toujours en tete de file, ce qui est faux.
    """
    a = np.searchsorted(t, t0)
    b = np.searchsorted(t, t0 + fenetre_s)
    if b - a < 2:
        return None
    seg_p, seg_s, seg_t = px[a:b], sell[a:b], t[a:b]
    cond = seg_s & (seg_p < limite if strict else seg_p <= limite)
    k = np.argmax(cond)
    if not cond[k]:
        return None
    return float(seg_t[k])


def trade_passif(t, px, qv, sell, i_sig, latence_ms, taille, decote_bps,
                 fenetre_s, max_hold_s, trail_pct, stop_pct,
                 fee_maker_bps=2.0, fee_taker_bps=4.5, sortie_passive=False):
    """Entree en LIMITE apres l'ignition, sortie au marche (ou en limite).

    L'entree ne paie ni le spread ni le slippage : c'est tout l'interet. Mais
    elle n'est pas toujours executee, et le taux de remplissage fait partie du
    resultat - un ordre non execute n'est pas un trade gagnant evite, c'est une
    opportunite manquee qu'il faut compter.
    """
    t_sig = t[i_sig] + latence_ms / 1000.0
    lim = px[i_sig] * (1.0 - decote_bps / 1e4)
    t_fill = fill_passif(t, px, sell, t_sig, lim, fenetre_s)
    if t_fill is None:
        return None
    px_in = lim
    a = np.searchsorted(t, t_fill)
    b = np.searchsorted(t, t_fill + max_hold_s)
    if b - a < 3:
        return None
    seg_t, seg_p = t[a:b], px[a:b]
    peak, stop = px_in, px_in * (1.0 - stop_pct)
    t_out, p_out = seg_t[-1], seg_p[-1]
    for k in range(len(seg_p)):
        p = seg_p[k]
        if p <= stop:
            t_out, p_out = seg_t[k], p
            break
        if p > peak:
            peak = p
            stop = max(stop, peak * (1.0 - trail_pct))
    if sortie_passive:
        out = p_out
        fee_out = fee_maker_bps
    else:
        s = sweep_sell(t, px, qv, sell, t_out, taille)
        out = s if np.isfinite(s) else p_out
        fee_out = fee_taker_bps
    c = (fee_maker_bps + fee_out) / 1e4
    return (out / px_in - 1.0 - c, t_out - t_fill)


def trade_mixte(t, px, qv, sell, i_sig, latence_ms, taille,
                max_hold_s, trail_pct, stop_pct, tp_pct=None,
                fee_taker_bps=4.5, fee_maker_bps=2.0, marge_bps=0.0):
    """Entree AU MARCHE, sortie EN LIMITE : la configuration asymetrique.

    L'entree doit traverser - pendant une ignition, un ordre passif est
    anti-selectionne (on n'est servi que quand le mouvement echoue, ce que le
    test precedent chiffre a 80-90 % de remplissage pour un resultat de -19 bps).

    La sortie, elle, n'a pas ce probleme : pendant que le pump continue, des
    acheteurs agressifs viennent lever les offres. Poser une vente en limite,
    c'est se faire servir PAR le flux, pas contre lui. On paie le maker et zero
    slippage de sortie.

    Un ordre de vente passif a `tp` est execute quand un ACHETEUR agressif monte
    jusqu'a ce niveau (is_buyer_maker = false). Si la cible n'est jamais
    atteinte, on sort au marche au stop ou au time stop, et on paie le taker.
    """
    t_ent = t[i_sig] + latence_ms / 1000.0
    px_in = sweep_buy(t, px, qv, sell, t_ent, taille)
    if not np.isfinite(px_in):
        return None
    a = np.searchsorted(t, t_ent)
    b = np.searchsorted(t, t_ent + max_hold_s)
    if b - a < 5:
        return None
    seg_t, seg_p, seg_s = t[a:b], px[a:b], sell[a:b]
    tp = px_in * (1.0 + tp_pct) if tp_pct else np.inf
    peak, stop = px_in, px_in * (1.0 - stop_pct)
    for k in range(len(seg_p)):
        p = seg_p[k]
        if p <= stop:                                   # sortie au marche
            out = sweep_sell(t, px, qv, sell, seg_t[k], taille)
            out = out if np.isfinite(out) else p
            c = (fee_taker_bps + fee_taker_bps) / 1e4
            return (out / px_in - 1.0 - c, seg_t[k] - t_ent, "stop")
        if (not seg_s[k]) and p >= tp * (1.0 + marge_bps / 1e4):
            # Exiger que le prix TRAVERSE la limite, et pas qu'il l'effleure.
            # Supposer un remplissage au premier contact revient a se croire
            # toujours en tete de file. C'est exactement l'optimisme qui avait
            # fabrique un faux resultat sur l'entree en limite en bougies 1 min.
            c = (fee_taker_bps + fee_maker_bps) / 1e4
            return (tp / px_in - 1.0 - c, seg_t[k] - t_ent, "tp_passif")
        if p > peak:
            peak = p
            stop = max(stop, peak * (1.0 - trail_pct))
    out = sweep_sell(t, px, qv, sell, seg_t[-1], taille)
    out = out if np.isfinite(out) else seg_p[-1]
    c = (fee_taker_bps + fee_taker_bps) / 1e4
    return (out / px_in - 1.0 - c, seg_t[-1] - t_ent, "time")
