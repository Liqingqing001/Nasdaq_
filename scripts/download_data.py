"""Acquire research bars with evidence and explicit coverage."""
from pathlib import Path
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nasdaq.analytics import clean_prices
from nasdaq.providers import fetch_eastmoney
ROOT=Path(__file__).resolve().parents[1]

def quality_report(df,expected):
    calendar=pd.DatetimeIndex(sorted(df.date.unique()))
    rows=[]
    for symbol in expected:
        part=df[df.symbol.eq(symbol)].sort_values('date')
        present=pd.DatetimeIndex(part.date)
        internal=calendar[(calendar>=present.min())&(calendar<=present.max())] if len(present) else calendar[:0]
        rows.append(dict(symbol=symbol,rows=len(part),first_date=str(present.min().date()) if len(present) else None,
                         last_date=str(present.max().date()) if len(present) else None,
                         missing_sessions=len(calendar.difference(present)),internal_missing_sessions=len(internal.difference(present)),
                         complete_window=bool(len(present) and set(present)==set(calendar))))
    return rows

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--start',default='2023-01-01')
    parser.add_argument('--end',default='2026-01-01',help='Exclusive end')
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--cache-only',action='store_true',help='Use acquired raw evidence without network requests')
    parser.add_argument('--min-coverage',type=float,default=.95)
    args=parser.parse_args()
    if pd.Timestamp(args.start)>=pd.Timestamp(args.end):parser.error('start must precede end')
    if not 0<args.min_coverage<=1:parser.error('min-coverage must be in (0,1]')
    universe=pd.read_csv(ROOT/'data/universe.csv');expected=universe.symbol.tolist()
    frames=[];evidence={};errors={}
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as pool:
        futures={pool.submit(fetch_eastmoney,s,args.start,args.end,ROOT/'.cache/eastmoney',args.refresh,args.cache_only):s for s in expected}
        for future in as_completed(futures):
            symbol=futures[future]
            try:
                frame,proof=future.result();frames.append(frame);evidence[symbol]=proof
                print(f'{symbol}: {len(frame)} rows',flush=True)
            except Exception as exc:
                errors[symbol]=str(exc);print(f'{symbol}: FAILED {exc}',flush=True)
    (ROOT/'data/download_errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    if len(frames)/len(expected)<args.min_coverage:
        raise SystemExit(f'Only {len(frames)}/{len(expected)} covered; active data not replaced. Inspect errors and resume.')
    df,quality=clean_prices(pd.concat(frames,ignore_index=True))
    if df.empty or not np.isfinite(df.select_dtypes(include='number')).all().all():raise SystemExit('Invalid numeric data; active data not replaced')
    coverage=quality_report(df,expected);payload=df.to_csv(index=False).encode('utf-8')
    snapshot=json.loads((ROOT/'data/universe_manifest.json').read_text(encoding='utf-8')) if (ROOT/'data/universe_manifest.json').exists() else {}
    manifest=dict(provider='Eastmoney public daily history',retrieved_at=datetime.now(timezone.utc).isoformat(),
                  requested_start=args.start,requested_end_exclusive=args.end,symbols=sorted(df.symbol.unique()),
                  expected_symbols=expected,failed_symbols=errors,security_coverage=len(evidence)/len(expected),
                  status='complete' if len(evidence)==len(expected) else 'partial',accepted_min_coverage=args.min_coverage,
                  adjustment='raw OHLC fqt=0; provider qfq close fqt=1, not independently certified total return',
                  universe=snapshot,sha256=hashlib.sha256(payload).hexdigest(),quality=quality,coverage=coverage,requests=evidence,
                  limitations=['Fixed current snapshot viewed retrospectively; survivorship/selection bias',
                               'qfq return is provider-adjusted price return, not independently verified reinvested-dividend total return',
                               'Unavailable or short histories are disclosed, never backfilled from another ticker'])
    for name,data in [('prices.csv',payload),('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))]:
        temp=ROOT/'data'/f'{name}.tmp';temp.write_bytes(data);temp.replace(ROOT/'data'/name)
    summary={k:manifest[k] for k in ['provider','retrieved_at','requested_start','requested_end_exclusive','security_coverage','quality','limitations']}
    summary.update(snapshot=snapshot,covered_securities=len(evidence),expected_securities=len(expected),unavailable=sorted(errors),
                   complete_securities=sum(x['complete_window'] for x in coverage),coverage=coverage,research_csv_sha256=manifest['sha256'])
    (ROOT/'data/quality_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'ACTIVE: {len(df)} rows; {len(evidence)}/{len(expected)} securities; {summary["complete_securities"]} full-window securities',flush=True)
if __name__=='__main__':main()
