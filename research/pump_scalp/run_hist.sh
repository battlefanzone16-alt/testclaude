set -e
cd /home/user/testclaude/research/pump_scalp
echo "--- 1. evenements ---"
python3 extract_events.py --universe universe_hist.txt --start 2024-09-01 --end 2025-09-01 \
    --k 5 --z-min 2.5 --vol-min 2.0 --cooldown 60 --workers 4 --out events_hist.parquet
echo "--- 2. largeur de marche ---"
python3 build_breadth.py --universe universe_hist.txt --start 2024-09-01 --end 2025-09-01 \
    --out breadth_hist.parquet
python3 merge_breadth.py events_hist.parquet breadth_hist.parquet events_hist_br.parquet
echo "--- 3. open interest cible ---"
python3 oi_jobs_from.py events_hist_br.parquet oi_jobs_hist.parquet
python3 dl_metrics_cible.py oi_jobs_hist.parquet
echo "--- 4. features micro ---"
python3 build_micro.py --start 2024-09-01 --end 2025-09-01 \
    --events events_hist_br.parquet --out events_micro_hist.parquet
echo "--- TERMINE ---"
