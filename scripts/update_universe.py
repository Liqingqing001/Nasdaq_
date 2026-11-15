"""Extract a dated Nasdaq issuer snapshot. Retain source bytes locally for audit."""
from pathlib import Path
import re,json,hashlib,sys,argparse
from datetime import datetime,timezone
import requests
import pandas as pd
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
URL='https://www.nasdaq.com/docs/global-indexes/NDX'

def parse_snapshot(pdf):
    reader=PdfReader(pdf)
    records=[];asof=None
    for page in reader.pages:
        text=page.extract_text()
        match=re.search(r'Data as of:\s*(\d{2}/\d{2}/\d{4})',text)
        if match:asof=pd.to_datetime(match[1],format='%m/%d/%Y').date().isoformat()
        header=re.search(r'Name\s+Symbol\s+Weight\s*\(%\)',text)
        if not header:continue
        body=text[header.end():].split('Data Explanation')[0]
        for name,symbol,weight in re.findall(r'(.+?)\s+([A-Z]{1,5})\s+(\d+\.\d+)',body,re.S):
            records.append(dict(symbol=symbol,name=re.sub(r'\s+',' ',name).strip(),weight_pct=float(weight)))
    df=pd.DataFrame(records)
    if not asof or not 90<=len(df)<=110 or df.symbol.duplicated().any() or not 98<=df.weight_pct.sum()<=102:
        raise ValueError('Snapshot structure/count/weight verification failed; existing universe unchanged')
    return df,asof

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-pdf',type=Path)
    args=parser.parse_args()
    cache=ROOT/'.cache/universe';cache.mkdir(parents=True,exist_ok=True)
    if args.source_pdf:content=args.source_pdf.read_bytes()
    else:
        r=requests.get(URL,timeout=40,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status();content=r.content
    pdf=cache/'nasdaq-source.pdf';pdf.write_bytes(content)
    df,asof=parse_snapshot(pdf)
    old=pd.read_csv(ROOT/'data/universe.csv').fillna('')
    aliases=old.set_index('symbol').aliases.to_dict()
    sectors={
      '信息技术':'ADBE AMD ADI AAPL AMAT APP ARM ASML ALAB ADSK AVGO CDNS CSCO CRWD DDOG FTNT INTC INTU KLAC LRCX LITE MRVL MCHP MU MSFT MPWR NXPI PLTR PANW QCOM ROP SNDK STX SHOP SNPS TER TXN WDC WDAY',
      '通信服务':'GOOGL GOOG META CMCSA NFLX TMUS TTWO',
      '可选消费':'ABNB AMZN BKNG DASH MAR MELI ORLY PDD ROST SBUX TSLA',
      '必需消费':'CCEP COST KDP MDLZ MNST PEP WMT',
      '医疗健康':'ALNY AMGN DXCM GEHC GILD IDXX ISRG MRNA REGN VRTX',
      '工业':'ADP AXON CTAS CPRT CSX FAST FER HONA HON ODFL PCAR RKLB SPCX TRI PAYX',
      '公用事业':'AEP CEG EXC XEL', '能源':'BKR FANG', '材料':'LIN',
      '金融科技':'PYPL MSTR', '云计算服务':'CRWV NBIS'}
    sector_map={s:k for k,v in sectors.items() for s in v.split()}
    df['sector']=df.symbol.map(sector_map).fillna('待分类')
    df['aliases']=df.symbol.map(aliases).fillna('')
    extra={'TSLA':'特斯拉','GOOG':'谷歌C类','GOOGL':'谷歌|谷歌A类','WMT':'沃尔玛','INTC':'英特尔','PEP':'百事','PLTR':'帕兰提尔','PDD':'拼多多','SBUX':'星巴克','QCOM':'高通'}
    for s,a in extra.items():df.loc[df.symbol.eq(s),'aliases']=a
    df['snapshot_date']=asof
    df.to_csv(ROOT/'data/universe.csv',index=False)
    meta=dict(source_url=URL,snapshot_date=asof,retrieved_at=datetime.now(timezone.utc).isoformat(),
              source_sha256=hashlib.sha256(content).hexdigest(),securities=len(df),
              companies=len(df)-int({'GOOG','GOOGL'}.issubset(set(df.symbol))),
              sector_method='Project-defined broad grouping; not official GICS/ICB or Nasdaq classification',
              scope='Fixed snapshot retrospective sample; not historical constituent reconstruction')
    (ROOT/'data/universe_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False))
if __name__=='__main__':main()
