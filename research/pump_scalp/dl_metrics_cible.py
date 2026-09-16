"""Telechargement CIBLE de l'open interest : uniquement les jours qui portent
des evenements (plus la veille, pour le recul de 60 min a cheval sur minuit).

Le telechargement exhaustif demandait 116 435 fichiers pour n'en exploiter
qu'une fraction. On ne perd aucune information utile : les features d'OI ne
sont lues qu'aux minutes d'ignition.
"""
import sys, pandas as pd, bv_extra
import sys
j = pd.read_parquet(sys.argv[1] if len(sys.argv)>1 else "oi_jobs.parquet")
jobs = [(r.symbol, pd.Timestamp(r.day)) for r in j.itertuples()]
print(f"{len(jobs)} fichiers metrics cibles", file=sys.stderr)
bv_extra.run(jobs, bv_extra.fetch_metrics_day, 40, "metrics-cible")
