"""Fusionne les evenements avec la largeur de marche de leur periode."""
import sys, pandas as pd
ev_in, br_in, out = sys.argv[1], sys.argv[2], sys.argv[3]
ev = pd.read_parquet(ev_in); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
br = pd.read_parquet(br_in)
ev = ev.merge(br, left_on="entry_time", right_index=True, how="left")
ev.to_parquet(out, compression="zstd")
print(f"{len(ev)} evenements, breadth renseignee a {ev.breadth_z2.notna().mean()*100:.0f}% -> {out}")
