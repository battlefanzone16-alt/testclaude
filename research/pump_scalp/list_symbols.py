"""Enumere tous les symboles perp USDT (futures/um) presents sur data.binance.vision."""
import re, sys, urllib.request

BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
PREFIX = "data/futures/um/monthly/klines/"

def listing(marker=""):
    url = f"{BASE}?delimiter=/&prefix={PREFIX}&max-keys=1000"
    if marker:
        url += f"&marker={urllib.parse.quote(marker)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()

import urllib.parse
syms, marker = [], ""
while True:
    xml = listing(marker)
    found = re.findall(r"<Prefix>" + re.escape(PREFIX) + r"([^<]+?)/</Prefix>", xml)
    syms.extend(found)
    if "<IsTruncated>true</IsTruncated>" not in xml:
        break
    m = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
    marker = m.group(1) if m else PREFIX + found[-1] + "/"

usdt = sorted(s for s in syms if s.endswith("USDT"))
print(f"{len(syms)} symboles au total, {len(usdt)} en USDT", file=sys.stderr)
print("\n".join(usdt))
