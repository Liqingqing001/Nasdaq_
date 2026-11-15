import numpy as np
import pandas as pd
import pytest
from nasdaq.query import parse_query
from nasdaq.query_engine import execute_query

@pytest.fixture
def universe():
    return pd.DataFrame({'symbol':['AAPL','MSFT','NVDA'],'name':['Apple','Microsoft','NVIDIA'],'aliases':['苹果','微软','英伟达'],'sector':['信息技术']*3})

@pytest.fixture
def data():
    days=pd.bdate_range('2024-01-01','2025-12-31');t=np.arange(len(days))
    prices={'AAPL':100*np.exp(.0003*t+.01*np.sin(t)),
            'MSFT':100*np.exp(.0004*t+.012*np.sin(t)),
            'NVDA':100*np.exp(.0002*t+.02*np.cos(t))}
    return pd.concat([pd.DataFrame({'date':days,'symbol':s,'open':v,'high':v+1,'low':v-1,'close':v,'adj_close':v,'volume':100}) for s,v in prices.items()],ignore_index=True)

@pytest.mark.parametrize('text,start,end',[
    ('近一年收益最高','2025-01-01','2025-12-31'),
    ('最近三个月收益最高','2025-10-01','2025-12-31'),
    ('去年收益最高','2024-01-01','2024-12-31'),
    ('上月收益最高','2025-11-01','2025-11-30'),
    ('近30天收益最高','2025-12-02','2025-12-31')])
def test_relative_time_anchored_to_data_end(universe,text,start,end):
    q=parse_query(text,universe,'2023-01-01','2025-12-31')
    assert q.start==pd.Timestamp(start) and q.end==pd.Timestamp(end)
    assert q.time_basis=='relative_to_selected_end'

def test_correlation_ranking_excludes_self_and_counts_pairs(data,universe):
    q=parse_query('与苹果近一年相关性最高的前二只股票',universe,'2024-01-01','2025-12-31')
    result=execute_query(q,data,['AAPL','MSFT','NVDA'])
    assert 'AAPL' not in result.table.index
    assert result.table.index[0]=='MSFT' and len(result.table)==2
    assert result.table.paired_observations.min()>=20

def test_volatility_query_is_not_cumulative_return(data,universe):
    q=parse_query('比较苹果和微软近三个月的波动率',universe,'2024-01-01','2025-12-31')
    result=execute_query(q,data,['AAPL','MSFT','NVDA'])
    assert result.table.iloc[0].isna().all()
    assert '滚动年化波动率' in result.explanation

@pytest.mark.parametrize('text',['2025年近一年收益最高','2025年第一季度收益排名','明年收益最高','股票排名','近一年市值最高','与苹果和微软相关性最高的前3只股票','比较tsla和AAPL','近一年和近三个月收益最高','收益最高且回撤最小'])
def test_ambiguous_and_unsupported_rejected(universe,text):
    with pytest.raises(ValueError):parse_query(text,universe,'2024-01-01','2025-12-31')

def test_missing_and_short_history_not_silently_included(data,universe):
    short=data[~(data.symbol.eq('NVDA') & (data.date<pd.Timestamp('2025-10-01')))]
    q=parse_query('近一年收益最高的前3只股票',universe,'2024-01-01','2025-12-31')
    result=execute_query(q,short,['AAPL','MSFT','NVDA'])
    assert 'NVDA' not in result.table.index and result.notes

def test_query_outside_data_rejected(data,universe):
    q=parse_query('2020年收益最高',universe,'2024-01-01','2025-12-31')
    with pytest.raises(ValueError,match='超出'):execute_query(q,data,['AAPL','MSFT'])

def test_case_insensitive_symbols_and_english_names(universe):
    q=parse_query('比较Apple和msft近一年收益走势',universe,'2024-01-01','2025-12-31')
    assert q.symbols==['AAPL','MSFT']
