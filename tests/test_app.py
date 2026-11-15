"""UI integration with explicitly artificial fixtures in temporary folders."""
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

@pytest.fixture
def app_path(tmp_path):
    root=Path(__file__).resolve().parents[1]
    shutil.copy(root/'app.py',tmp_path/'app.py')
    (tmp_path/'data').mkdir()
    shutil.copy(root/'data/universe.csv',tmp_path/'data/universe.csv')
    universe=pd.read_csv(root/'data/universe.csv')
    dates=pd.bdate_range('2023-01-02','2025-12-31')
    rows=[]
    for i,symbol in enumerate(universe.symbol):
        values=100*np.exp(np.arange(len(dates))*(i+1)*.00005+.03*np.sin(np.arange(len(dates))/(i+2)))
        for day,p in zip(dates,values):
            rows.append(dict(date=day,symbol=symbol,open=p,high=p+1,low=p-1,close=p,adj_close=p,volume=10000))
    pd.DataFrame(rows).to_csv(tmp_path/'data/prices.csv',index=False)
    return tmp_path/'app.py'

def test_all_pages_and_query(app_path):
    at=AppTest.from_file(str(app_path),default_timeout=60).run()
    assert not at.exception
    for page in ['个股分析','风险聚类','智能问数','数据与口径']:
        at.radio[0].set_value(page).run()
        assert not at.exception, page
    at.radio[0].set_value('智能问数').run()
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert len(at.get('plotly_chart'))==1
    at.text_input[0].set_value('预测明天买什么').run()
    at.button[0].click().run()
    assert len(at.error)==1 and not at.exception

def test_no_data(tmp_path):
    root=Path(__file__).resolve().parents[1]
    shutil.copy(root/'app.py',tmp_path/'app.py')
    (tmp_path/'data').mkdir()
    shutil.copy(root/'data/universe.csv',tmp_path/'data/universe.csv')
    at=AppTest.from_file(str(tmp_path/'app.py')).run()
    assert not at.exception and len(at.info)==1
