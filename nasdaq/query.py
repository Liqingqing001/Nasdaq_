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
    time_basis: str = 'explicit_or_sidebar'
    anchor: str | None = None

def parse_query(text, universe, default_start, default_end):
    text = text.strip()
    if not text:
        raise ValueError('请输入一个分析问题。')
    start, end = pd.Timestamp(default_start), pd.Timestamp(default_end)
    start, end, time_basis = parse_time(text, start, end)
    if start > end:
        raise ValueError('开始时间不能晚于结束时间。')
    symbols = []
    upper = text.upper()
    common_names={'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','AMZN':'Amazon','META':'Meta','AVGO':'Broadcom','NFLX':'Netflix','AMD':'AMD','COST':'Costco'}
    known_words=set()
    for row in universe.itertuples():
        aliases = [row.name, common_names.get(row.symbol,'')] + str(row.aliases if pd.notna(row.aliases) else '').split('|')
        known_words.update(a.upper() for a in aliases if a and a.isalpha())
        if re.search(r'(?<![A-Z])'+re.escape(row.symbol)+r'(?![A-Z])', upper) or any(a and a.lower() in text.lower() for a in aliases):
            symbols.append(row.symbol)
    mentioned = re.findall(r'(?<![A-Za-z])[A-Za-z]{1,5}(?![A-Za-z])', text)
    unknown = {s.upper() for s in mentioned} - set(universe.symbol) - known_words
    if unknown:
        raise ValueError('未收录的股票代码：' + ', '.join(sorted(unknown)))
    sector = [s for s in universe.sector.unique() if s in text]
    if not symbols and sector:
        symbols = universe[universe.sector.isin(sector)].symbol.tolist()
    ranking=any(s in text for s in ['排名','前','最高','最低','最大','最小','最强','最弱'])
    if any(s in text for s in ['市值','市盈率','营收','利润','成交额','成交量','预测','买入','卖出']):
        raise ValueError('该问题涉及尚未支持的指标或预测。支持收益、波动、回撤及收益率相关性。')
    if '相关' in text:
        intent = 'correlation_ranking' if ranking else 'correlation'
        if intent=='correlation_ranking' and len(symbols)!=1:
            raise ValueError('相关性排名需要明确一只参考股票，例如与苹果相关性最高的前5只股票。')
    elif any(s in text for s in ['月度', '月收益', '热力']):
        intent = 'monthly'
    elif any(s in text for s in ['排名', '前', '最高', '最低', '最大', '最小']):
        intent = 'ranking'
    elif any(s in text for s in ['比较', '对比', '走势', '趋势', '累计收益']):
        intent = 'trend'
    else:
        raise ValueError('尚不支持这个问题。请使用收益/波动/回撤排名、累计收益比较、月度收益或相关性分析。')
    families=sum([bool('收益' in text),bool('回撤' in text),any(s in text for s in ['波动','风险'])])
    if intent in ['ranking','trend'] and families>1:
        raise ValueError('一次请指定一个分析指标：收益、波动率或回撤。')
    metric = 'max_drawdown' if '回撤' in text else 'annual_volatility' if any(s in text for s in ['波动', '风险']) else 'total_return'
    smallest = any(s in text for s in ['最小', '最低', '最少', '最弱'])
    # Drawdowns are negative; smaller loss magnitude means closer to zero.
    ascending = (not smallest) if metric == 'max_drawdown' else smallest
    count = re.search(r'前\s*([一二三四五六七八九十\d]+)', text)
    limit = min(100, max(1, number(count.group(1)))) if count else 5
    if intent=='ranking' and not any(s in text for s in ['收益','波动','风险','回撤']):
        raise ValueError('请说明排名指标：收益、波动率或最大回撤。')
    return Query(intent, symbols, start, end, metric, ascending, limit,time_basis,symbols[0] if intent=='correlation_ranking' else None)


def number(value):
    if value.isdigit():return int(value)
    digits={c:i for i,c in enumerate('零一二三四五六七八九')}
    if value=='十':return 10
    if '十' in value:
        a,b=value.split('十');return (digits.get(a,1)*10)+digits.get(b,0)
    if value in digits:return digits[value]
    raise ValueError('无法识别数量，请使用阿拉伯数字。')


def parse_time(text,start,end):
    if any(v in text for v in ['未来','明年','明天','昨天','本周','上周']):
        raise ValueError('当前不支持该时间表达，请使用明确日期或近一年、近三个月等范围。')
    dates=re.findall(r'20\d{2}-\d{2}-\d{2}',text)
    years=re.findall(r'(?<!\d)(20\d{2})(?![\d-])',text)
    relative=re.findall(r'(?:最近|近)([一二三四五六七八九十\d]+)(个月|月|年|天|日)',text)
    calendars=[v for v in ['今年','去年','本月','上月'] if v in text]
    if len(relative)+len(calendars)>1:raise ValueError('一次请指定一个时间范围。')
    rel=re.search(r'(?:最近|近)([一二三四五六七八九十\d]+)(个月|月|年|天|日)',text)
    calendar=calendars[0] if calendars else None
    if (rel or calendar) and (dates or years):raise ValueError('相对时间和明确日期不能混用，请只指定一种时间范围。')
    if dates:
        if len(dates)!=2:raise ValueError('日期范围请提供起止两个日期，例如2024-01-01至2024-12-31。')
        return *map(pd.Timestamp,dates),'explicit_dates'
    if re.search(r'Q[1-4]|季度|\d月',text) and not rel:
        raise ValueError('月份或季度请写成两个明确日期，例如2025-01-01至2025-03-31。')
    if years:return pd.Timestamp(f'{years[0]}-01-01'),pd.Timestamp(f'{years[-1]}-12-31'),'explicit_years'
    if rel:
        n=number(rel[1]);unit=rel[2]
        if n<1:raise ValueError('时间长度必须大于0。')
        delta=pd.DateOffset(years=n) if unit=='年' else pd.DateOffset(months=n) if unit in ['月','个月'] else pd.Timedelta(days=n)
        return end-delta+pd.Timedelta(days=1),end,'relative_to_selected_end'
    if calendar:
        if calendar=='今年':return end.replace(month=1,day=1),end,'relative_to_selected_end'
        if calendar=='去年':return pd.Timestamp(end.year-1,1,1),pd.Timestamp(end.year-1,12,31),'relative_to_selected_end'
        month=end.replace(day=1)
        return (month,end,'relative_to_selected_end') if calendar=='本月' else (month-pd.DateOffset(months=1),month-pd.Timedelta(days=1),'relative_to_selected_end')
    if any(s in text for s in ['最近','近','本周','上周']):raise ValueError('时间未识别，请使用近一年、近三个月或两个明确日期。')
    return start,end,'sidebar'
