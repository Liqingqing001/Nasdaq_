"""Public Eastmoney daily endpoint, with explicit raw/qfq alignment and identity checks."""
from pathlib import Path
import json,time
from datetime import datetime,timezone
from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from urllib.parse import urlencode
import pandas as pd

ENDPOINT='https://push2his.eastmoney.com/api/qt/stock/kline/get'

def parse_bars(payload,symbol):
    data=payload.get('data')
    if not data or not data.get('klines'):raise ValueError('No daily history returned')
    if str(data.get('code','')).upper()!=symbol.upper():raise ValueError('Provider symbol identity mismatch')
    rows=[]
    for line in data['klines']:
        fields=line.split(',')
        if len(fields)<7:raise ValueError('Unexpected kline schema')
        rows.append(dict(date=fields[0],open=float(fields[1]),close=float(fields[2]),
                         high=float(fields[3]),low=float(fields[4]),volume=float(fields[5])))
    df=pd.DataFrame(rows)
    df['date']=pd.to_datetime(df.date)
    if df.date.duplicated().any():raise ValueError('Duplicate provider dates')
    return df

def combine_bars(raw,adjusted,symbol):
    a=parse_bars(raw,symbol);b=parse_bars(adjusted,symbol)
    if set(a.date)!=set(b.date):raise ValueError('Raw and qfq dates do not align')
    result=a.merge(b[['date','close']].rename(columns={'close':'adj_close'}),on='date',validate='one_to_one')
    result['symbol']=symbol
    return result

def fetch_eastmoney(symbol,start,end,cache,refresh=False,cache_only=False):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    failures=[]
    for market in [105,106,107]:
        secid=f'{market}.{symbol}'
        payloads=[];evidence=[]
        try:
            for fqt in [0,1]:
                file=cache/f'{secid}_{start}_{end}_{fqt}.json'
                if file.exists() and not refresh:
                    saved=json.loads(file.read_text(encoding='utf-8'))
                else:
                    if cache_only:raise ValueError('No verified local cache for this market/code')
                    params=dict(fields1='f1,f2,f3,f4,f5,f6',fields2='f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                                klt=101,fqt=fqt,secid=secid,beg=start.replace('-',''),
                                end=(pd.Timestamp(end)-pd.Timedelta(days=1)).strftime('%Y%m%d'),lmt=10000)
                    last=None
                    for attempt in range(2):
                        try:
                            r=requests.get(ENDPOINT+'?'+urlencode(params,safe=','),timeout=18,impersonate='chrome')
                            r.raise_for_status();payload=r.json();parse_bars(payload,symbol)
                            saved=dict(retrieved_at=datetime.now(timezone.utc).isoformat(),url=r.url,payload=payload)
                            file.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8');last=None;break
                        except (RequestException,ValueError) as exc:
                            last=exc
                            # No history is not a transient network failure.
                            if isinstance(exc,ValueError):break
                            if attempt==0:time.sleep(1)
                    if last:raise last
                parse_bars(saved['payload'],symbol)
                payloads.append(saved['payload'])
                evidence.append({k:saved[k] for k in ['retrieved_at','url']})
            result=combine_bars(*payloads,symbol)
            result=result[result.date.between(pd.Timestamp(start),pd.Timestamp(end),inclusive='left')]
            if result.empty:raise ValueError('No observations in requested window')
            return result,dict(secid=secid,requests=evidence)
        except (RequestException,ValueError,KeyError) as exc:
            failures.append(f'{secid}: {exc}')
    raise ValueError('; '.join(failures))
