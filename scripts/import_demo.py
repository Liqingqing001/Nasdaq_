"""Import Plotly's authentic 2015-2017 example, distinct from research data."""
from pathlib import Path
import io,json,hashlib
from datetime import datetime,timezone
import requests
import pandas as pd
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nasdaq.analytics import clean_prices
URL='https://raw.githubusercontent.com/plotly/datasets/master/dash-stock-ticker-demo.csv'
def main():
    response=requests.get(URL,timeout=30)
    response.raise_for_status()
    raw=pd.read_csv(io.StringIO(response.text))
    frame=raw.rename(columns={'Date':'date','Stock':'symbol','Open':'open','High':'high','Low':'low','Close':'close','AdjClose':'adj_close','Volume':'volume'})
    frame,quality=clean_prices(frame)
    if frame.empty:raise ValueError('示例数据为空')
    frame.to_csv(ROOT/'data/prices_demo.csv',index=False)
    pd.DataFrame([['AAPL','Apple','信息技术','苹果'],['TSLA','Tesla','可选消费','特斯拉'],['COKE','Coca-Cola Consolidated','必需消费','可口可乐装瓶'],['YHOO','Yahoo historical ticker','历史退市证券','雅虎'],['GOOGL','Alphabet','通信服务','谷歌']],columns=['symbol','name','sector','aliases']).to_csv(ROOT/'data/universe_demo.csv',index=False)
    manifest=dict(provider='Plotly official example dataset',source_url=URL,retrieved_at=datetime.now(timezone.utc).isoformat(),source_sha256=hashlib.sha256(response.content).hexdigest(),quality=quality,mode='Historical demonstration only; NOT Nasdaq-100 research dataset',start=str(frame.date.min().date()),end=str(frame.date.max().date()),adjustment='Original OHLC and supplied AdjClose; no additional corporate-action verification')
    (ROOT/'data/demo_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Imported {len(frame)} rows, {frame.symbol.nunique()} historical demo stocks')
if __name__=='__main__':main()
