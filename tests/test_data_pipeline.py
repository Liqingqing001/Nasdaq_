from io import BytesIO
import pandas as pd
import pytest
from nasdaq.providers import parse_bars,combine_bars
from nasdaq.analytics import complete_symbols,clean_prices
from scripts.download_data import quality_report
from scripts.update_universe import parse_snapshot

def payload(symbol='AAPL',date='2023-01-03',close=100):
    return {'data':{'code':symbol,'klines':[f'{date},100,{close},110,90,1000,0']}}

def test_provider_identity_checked():
    with pytest.raises(ValueError,match='identity'):parse_bars(payload('MSFT'),'AAPL')

def test_provider_dates_must_match():
    with pytest.raises(ValueError,match='align'):combine_bars(payload(),payload(date='2023-01-04'),'AAPL')

def test_raw_and_adjusted_separated():
    result=combine_bars(payload(close=100),payload(close=50),'AAPL')
    assert result.close.iloc[0]==100 and result.adj_close.iloc[0]==50

def test_partial_history_not_filled():
    df=pd.DataFrame({'symbol':['A','A','B'],'date':pd.to_datetime(['2023-01-03','2023-01-04','2023-01-04'])})
    assert complete_symbols(df)==['A']
    report=quality_report(df,['A','B','C'])
    assert report[1]['missing_sessions']==1 and not report[1]['complete_window']
    assert report[2]['rows']==0 and report[2]['first_date'] is None

def test_nonfinite_and_empty_symbol_rejected():
    row=dict(date='2023-01-03',symbol=None,open=1,high=2,low=1,close=1,adj_close=1,volume=1)
    other={**row,'symbol':'AAPL','high':float('inf')}
    result,report=clean_prices(pd.DataFrame([row,other]))
    assert result.empty and report['invalid_rows']==2

def test_snapshot_multiline_names_and_date(monkeypatch):
    class Page:
        def extract_text(self):
            rows=['COCA\n-\nCOLA\nS000\n1.00']
            # Parser accepts uppercase stock tickers, 100 distinct dummy symbols.
            rows=[f'Company {i}\n'+chr(65+i//26)+chr(65+i%26)+'\n1.00' for i in range(100)]
            rows[0]='COCA\n-\nCOLA\nAA\n1.00'
            return 'Data as of: 11/02/2026\nName\nSymbol\nWeight (%)\n'+'\n'.join(rows)
    monkeypatch.setattr('scripts.update_universe.PdfReader',lambda _:type('Reader',(),{'pages':[Page()]})())
    df,date=parse_snapshot(BytesIO())
    assert len(df)==100 and date=='2026-11-02' and df.name.iloc[0]=='COCA - COLA'

def test_snapshot_rejects_truncated_list(monkeypatch):
    class Page:
        def extract_text(self):return 'Data as of: 11/02/2026\nName\nSymbol\nWeight (%)\nApple\nAAPL\n8.00'
    monkeypatch.setattr('scripts.update_universe.PdfReader',lambda _:type('Reader',(),{'pages':[Page()]})())
    with pytest.raises(ValueError,match='verification'):parse_snapshot(BytesIO())
