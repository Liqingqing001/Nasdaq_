"""Bounded Chinese query parser: no generated SQL, code execution or hidden guesses."""
import re
from dataclasses import dataclass
import pandas as pd

@dataclass
class Query:
    intent: str
    symbols: list
    start: pd.Timestamp
    end: pd.Timestamp
    metric: str = 'total_return'
    ascending: bool = False
    limit: int = 5

def parse_query(text, universe, default_start, default_end):
    text = text.strip()
    if not text:
        raise ValueError('请输入一个分析问题。')
    start, end = pd.Timestamp(default_start), pd.Timestamp(default_end)
    dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
    years = re.findall(r'(?<!\d)(20\d{2})(?![\d-])', text)
    if dates:
        if len(dates) != 2:
            raise ValueError('日期范围请提供起止两个日期，例如2024-01-01至2024-12-31。')
        start, end = map(pd.Timestamp, dates)
    elif years:
        start = pd.Timestamp(f'{years[0]}-01-01')
        end = pd.Timestamp(f'{years[-1]}-12-31')
    elif any(s in text for s in ['近', '最近', '本月', '今年', '上月']):
        raise ValueError('当前支持明确年份或两个日期，请将相对时间改为具体范围。')
    if start > end:
        raise ValueError('开始时间不能晚于结束时间。')
    symbols = []
    upper = text.upper()
    for row in universe.itertuples():
        aliases = [row.name] + str(row.aliases).split('|')
        if re.search(r'(?<![A-Z])'+re.escape(row.symbol)+r'(?![A-Z])', upper) or any(a and a.lower() in text.lower() for a in aliases):
            symbols.append(row.symbol)
    mentioned = re.findall(r'(?<![A-Za-z])[A-Z]{1,5}(?![A-Za-z])', text)
    unknown = set(mentioned) - set(universe.symbol)
    if unknown:
        raise ValueError('未收录的股票代码：' + ', '.join(sorted(unknown)))
    sector = [s for s in universe.sector.unique() if s in text]
    if not symbols and sector:
        symbols = universe[universe.sector.isin(sector)].symbol.tolist()
    if '相关' in text:
        intent = 'correlation'
    elif any(s in text for s in ['月度', '月收益', '热力']):
        intent = 'monthly'
    elif any(s in text for s in ['排名', '前', '最高', '最低', '最大', '最小']):
        intent = 'ranking'
    elif any(s in text for s in ['比较', '对比', '走势', '趋势', '累计收益']):
        intent = 'trend'
    else:
        raise ValueError('尚不支持这个问题。请使用收益/波动/回撤排名、累计收益比较、月度收益或相关性分析。')
    metric = 'max_drawdown' if '回撤' in text else 'annual_volatility' if any(s in text for s in ['波动', '风险']) else 'total_return'
    smallest = any(s in text for s in ['最小', '最低', '最少'])
    # Drawdowns are negative; smaller loss magnitude means closer to zero.
    ascending = (not smallest) if metric == 'max_drawdown' else smallest
    count = re.search(r'前\s*(\d+)\s*', text)
    limit = min(100, max(1, int(count.group(1)))) if count else 5
    return Query(intent, symbols, start, end, metric, ascending, limit)
