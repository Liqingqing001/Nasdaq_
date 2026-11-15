import pandas as pd
import pytest
from nasdaq.analytics import clean_prices, metrics, daily_returns, price_matrix, cluster_stocks
from nasdaq.query import parse_query

def fixture():
    rows=[]
    for symbol,values in {'AAPL':[100,120,90,110],'MSFT':[100,105,110,115],'NVDA':[100,130,150,160],'COST':[100,99,102,103]}.items():
        for date,value in zip(pd.date_range('2025-01-01',periods=4),values):
            rows.append(dict(date=date,symbol=symbol,open=value,high=value+1,low=value-1,close=value,adj_close=value,volume=100))
    return pd.DataFrame(rows)

def test_metrics_known_path():
    result=metrics(fixture())
    assert result.loc['AAPL','total_return']==pytest.approx(.1)
    assert result.loc['AAPL','max_drawdown']==pytest.approx(-.25)

def test_cleaning_invalid_and_duplicates():
    f=fixture();bad=f.iloc[[0]].copy();bad['adj_close']=-1
    clean,report=clean_prices(pd.concat([f,f.iloc[[0]],bad]))
    assert len(clean)==16
    assert report['invalid_rows']==1 and report['duplicate_rows']==1

def test_missing_not_filled():
    prices=pd.DataFrame({'A':[100,None,110]})
    assert daily_returns(prices)['A'].isna().all()

@pytest.fixture
def universe():
    return pd.DataFrame({'symbol':['AAPL','MSFT'],'name':['Apple','Microsoft'],'aliases':['苹果','微软'],'sector':['信息技术']*2})

def test_chinese_query(universe):
    q=parse_query('比较苹果和微软2025年的累计收益',universe,'2023-01-01','2025-12-31')
    assert q.symbols==['AAPL','MSFT'] and q.start==pd.Timestamp('2025-01-01')

def test_drawdown_order(universe):
    q=parse_query('最大回撤最小的前2只股票',universe,'2023-01-01','2025-12-31')
    assert q.metric=='max_drawdown' and not q.ascending and q.limit==2

@pytest.mark.parametrize('question',['买什么能赚钱','最近一年收益最高','比较TSLA和AAPL','比较2025-01-01股票'])
def test_unsupported_questions(universe,question):
    with pytest.raises(ValueError):parse_query(question,universe,'2023-01-01','2025-12-31')

def test_cluster_reproducible():
    stats=metrics(fixture())
    a,score,_,_=cluster_stocks(stats,2);b,*_=cluster_stocks(stats,2)
    assert a.cluster.equals(b.cluster) and -1<=score<=1

def test_cluster_too_few():
    with pytest.raises(ValueError):cluster_stocks(metrics(fixture()),4)
