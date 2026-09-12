#!/usr/bin/env python3
"""Diagnostic des dossiers de données — A LANCER SUR TON PC.

    python inspect_data.py "C:\\Users\\...\\kheirbot_sniper"

Parcourt data/, data_2024/, data_npy/ (et tout autre sous-dossier), identifie
le format de chaque fichier, déduit l'agencement des colonnes OHLC, et dit
exactement quelle commande `prepare` lancer ensuite.

Colle-moi la sortie et j'adapte le chargeur si quelque chose résiste.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quantlab.data.npy_loader import load_any, scan_directory
from quantlab.data.loader import infer_bars_per_year


def describe(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path) / 1e6
    try:
        if ext == ".npy":
            a = np.load(path, allow_pickle=True)
            shape = f"npy{a.shape} {a.dtype}"
        elif ext in (".pkl", ".pickle"):
            o = pd.read_pickle(path)
            shape = (f"pkl DataFrame{o.shape} cols={list(o.columns)[:8]}"
                     if isinstance(o, pd.DataFrame) else f"pkl {type(o).__name__}")
        else:
            shape = ext.lstrip(".")
    except Exception as e:
        shape = f"illisible ({e})"

    try:
        df = load_any(path)
        bpy = infer_bars_per_year(df.index)
        step = pd.Series(df.index).diff().median()
        return (f"{shape} | {size:.1f}Mo | {len(df)} bougies | pas={step} "
                f"| {df.index[0]:%Y-%m-%d}->{df.index[-1]:%Y-%m-%d} "
                f"| ~{bpy:.0f} bougies/an | close median={df['close'].median():.6g} OK")
    except Exception as e:
        return f"{shape} | {size:.1f}Mo | ECHEC CHARGEMENT: {e}"


def main(root: str):
    if not os.path.isdir(root):
        print(f"Dossier introuvable : {root}")
        return 1

    subdirs = [root] + [os.path.join(root, d) for d in sorted(os.listdir(root))
                        if os.path.isdir(os.path.join(root, d)) and not d.startswith("__")]

    total_ok = 0
    for d in subdirs:
        files = scan_directory(d)
        if not files:
            continue
        print("\n" + "=" * 100)
        print(f"{d}   ({len(files)} fichiers)")
        print("=" * 100)
        for f in files[:6]:
            line = describe(f)
            print(f"  {os.path.basename(f):<28} {line}")
            if line.endswith("OK"):
                total_ok += 1
        if len(files) > 6:
            print(f"  ... et {len(files)-6} autres fichiers")

    print("\n" + "=" * 100)
    print("ETAPE SUIVANTE")
    print("=" * 100)
    print("""
Si les lignes ci-dessus se terminent par OK, lance :

  # dossier d'entrainement (tout SAUF 2024)
  python -m quantlab.run prepare --src <dossier_1m> --out data_h4

  # holdout scellé — à préparer maintenant, à NE REGARDER QU'UNE FOIS
  python -m quantlab.run prepare --src <dossier_2024> --out data_h4_2024

  python -m quantlab.run ablation --data data_h4
  python -m quantlab.run optimize --data data_h4 --folds 4
  python -m quantlab.run validate --data data_h4

Si des lignes affichent ECHEC CHARGEMENT, colle-les-moi telles quelles.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
