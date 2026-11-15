"""Fetch authentic daily bars; fail explicitly, never substitute synthetic prices."""
from pathlib import Path
import argparse
import hashlib
import json
from datetime import datetime, timezone
import sys
import pandas as pd
import yfinance as yf
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nasdaq.analytics import clean_prices

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2023-01-01')
    parser.add_argument('--end', default='2026-01-01', help='Exclusive end date')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    universe = pd.read_csv(root/'data/universe.csv')
    yf.set_tz_cache_location(str(root/'.cache/yfinance'))
    frames, errors = [], {}
    for symbol in universe.symbol:
        try:
            bars = yf.Ticker(symbol).history(start=args.start, end=args.end, auto_adjust=False, actions=False, timeout=20)
            if bars.empty or 'Adj Close' not in bars:
                raise ValueError('No adjusted historical bars returned')
            bars = bars.reset_index().rename(columns={'Date':'date','Open':'open','High':'high','Low':'low','Close':'close','Adj Close':'adj_close','Volume':'volume'})
            bars['date'] = pd.to_datetime(bars.date).dt.tz_localize(None)
            bars['symbol'] = symbol
            frames.append(bars)
            print(f'{symbol}: {len(bars)} rows', flush=True)
        except Exception as e:
            errors[symbol] = str(e)
            print(f'{symbol}: FAILED {e}', flush=True)
    (root/'data/download_errors.json').write_text(json.dumps(errors, indent=2), encoding='utf-8')
    if not frames:
        raise SystemExit('Download failed. Existing cache was not changed.')
    df, quality = clean_prices(pd.concat(frames))
    payload = df.to_csv(index=False).encode('utf-8')
    temp = root/'data/prices.tmp'
    temp.write_bytes(payload)
    temp.replace(root/'data/prices.csv')
    manifest = dict(provider='Yahoo Finance via yfinance', retrieved_at=datetime.now(timezone.utc).isoformat(),
                    requested_start=args.start, requested_end_exclusive=args.end, symbols=sorted(df.symbol.unique()),
                    failed_symbols=errors, adjustment='raw OHLC; Adj Close for return calculations',
                    sha256=hashlib.sha256(payload).hexdigest(), quality=quality,
                    universe='Explicit 10-stock development sample, not the complete Nasdaq-100 or a historical constituent reconstruction')
    (root/'data/manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if errors:
        print('Partial download: inspect data/download_errors.json; UI discloses actual coverage.')

if __name__ == '__main__':
    main()
