"""Screen in-sample : on balaie un catalogue borne, on compte les essais.

Le nombre de configurations testees est affiche avec les resultats. Sans lui, un
profit factor de 1.4 ne veut rien dire : sur 200 essais, le meilleur tirage d'une
piece truquee ressemble a un edge.
"""
from __future__ import annotations

import itertools
from functools import partial

import pandas as pd

from lab import backtest, data, protocole as P, strategies as S


def grilles():
    """(nom_famille, fabrique_de_signal, dict de parametres) pour chaque config."""
    out = []

    for ne, ns, sens in itertools.product([24, 48, 96, 168, 336], [12, 24, 48, 96],
                                          ["long", "both"]):
        out.append(("donchian", partial(S.donchian, n_entree=ne, n_sortie=ns, sens=sens),
                    {"n_entree": ne, "n_sortie": ns, "sens": sens}))

    for r, l, sens in itertools.product([12, 24, 48, 96], [96, 200, 400, 800],
                                        ["long", "both"]):
        if r < l:
            out.append(("ema_cross", partial(S.ema_cross, rapide=r, lent=l, sens=sens),
                        {"rapide": r, "lent": l, "sens": sens}))

    for n, e, s, sens in itertools.product([48, 96, 168, 336], [1.5, 2.0, 2.5],
                                           [0.0, 0.5], ["long", "short", "both"]):
        out.append(("zscore_mr", partial(S.zscore_mr, n=n, entree=e, sortie=s, sens=sens),
                    {"n": n, "entree": e, "sortie": s, "sens": sens}))

    for n, e, s in itertools.product([8, 14, 24], [20, 25, 30], [50, 55, 60]):
        out.append(("rsi_mr", partial(S.rsi_mr, n=n, entree=e, sortie=s),
                    {"n": n, "entree": e, "sortie": s}))

    for d, duree, sens in itertools.product(range(0, 24, 4), [4, 8], ["long", "short"]):
        out.append(("heure_du_jour",
                    partial(S.heure_du_jour, debut=d, fin=(d + duree) % 24, sens=sens),
                    {"debut": d, "duree": duree, "sens": sens}))

    for seuil, sortie in itertools.product([0.15, 0.30, 0.50, 0.80], [0.0, 0.05, 0.10]):
        out.append(("funding_fade",
                    partial(S.funding_fade, seuil_annuel=seuil, sortie_annuel=sortie),
                    {"seuil": seuil, "sortie": sortie}))

    for lent, seuil in itertools.product([100, 200, 400], [0.30, 0.50, 1.00]):
        out.append(("tendance_filtre_funding",
                    partial(S.tendance_filtre_funding, lent=lent, seuil_annuel=seuil),
                    {"lent": lent, "seuil": seuil}))

    for k, n_atr, sens in itertools.product([0.3, 0.5, 0.8, 1.2], [24, 48], ["long", "both"]):
        out.append(("range_breakout",
                    partial(S.range_breakout, k=k, n_atr=n_atr, sens=sens),
                    {"k": k, "n_atr": n_atr, "sens": sens}))

    return out


def signal_de(fabrique, px, fr):
    """Les familles qui lisent le funding le recoivent ; les autres non."""
    try:
        return fabrique(px, fr)
    except TypeError:
        return fabrique(px)


def evaluer(px, fr, fabrique, latence=0) -> dict:
    sig = signal_de(fabrique, px, fr)
    res = backtest.lancer(px, sig, funding=fr, latence=latence)
    m = dict(res.metriques)
    # coherence par trimestre : un PF global porte par un seul trimestre ne vaut rien
    pf_trim = []
    for _, bloc in res.pnl.groupby(pd.Grouper(freq="QE")):
        if bloc.abs().sum() == 0:
            continue
        pf_trim.append(backtest.profit_factor(bloc[bloc != 0]))
    m["trimestres"] = len(pf_trim)
    m["trimestres_ok"] = sum(1 for x in pf_trim if x > 1.0)
    m["pf_trim_min"] = min(pf_trim) if pf_trim else float("nan")
    return m


def lancer_screen() -> pd.DataFrame:
    px = data.load(P.SYMBOLE, P.TIMEFRAME, "2021-06", "2023-07").loc[P.IS[0]:P.IS[1]]
    fr = data.load_funding(P.SYMBOLE, "2021-06", "2023-07")
    bh = backtest.buy_and_hold(px, fr)
    print(f"IS {P.IS[0]} -> {P.IS[1]} | {len(px)} barres | "
          f"buy & hold net = {bh.metriques['rendement_net']*100:+.1f}% "
          f"(DD {bh.metriques['max_dd']*100:.0f}%)\n")

    lignes = []
    configs = grilles()
    for i, (famille, fab, params) in enumerate(configs, 1):
        m = evaluer(px, fr, fab)
        lignes.append({"famille": famille, **params, **m})
        if i % 50 == 0:
            print(f"  ... {i}/{len(configs)} configurations")
    df = pd.DataFrame(lignes)
    print(f"\n{len(df)} configurations testees.")
    return df


if __name__ == "__main__":
    df = lancer_screen()
    df.to_csv("lab_out/screen_is.csv", index=False)
    cols = ["famille", "profit_factor", "rendement_net", "sharpe", "max_dd",
            "n_trades", "exposition", "trimestres_ok", "trimestres", "pf_trim_min"]
    ok = df[(df.n_trades >= P.MIN_TRADES) & (df.profit_factor >= P.MIN_PF) &
            (df.trimestres_ok >= P.MIN_TRIMESTRES_OK) & (df.max_dd >= P.MAX_DD)]
    print(f"\n--- {len(ok)} configurations passent les criteres pre-enregistres ---")
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print(ok.sort_values("profit_factor", ascending=False)[cols].head(25).to_string(index=False))
        print("\n--- meilleures par famille (sans filtre) ---")
        print(df.loc[df.groupby("famille").profit_factor.idxmax()][cols].to_string(index=False))
