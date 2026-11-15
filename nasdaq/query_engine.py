"""Auditable query execution shared by UI and tests. Never generates executable code."""
from dataclasses import dataclass
import pandas as pd
import numpy as np
from nasdaq.analytics import metrics,price_matrix,daily_returns,common_window,complete_symbols

@dataclass
class Result:
    kind: str
    table: pd.DataFrame
    context: dict
    explanation: str
    notes: list

def execute_query(query,data,candidates,full_only=True):
    q=query;notes=[]
    if q.start<data.date.min()-pd.Timedelta(days=7) or q.end>data.date.max()+pd.Timedelta(days=7):
        raise ValueError('请求超出本地行情覆盖范围，请缩小时间范围或补充数据。')
    window=data[data.date.between(q.start,q.end)]
    if window.empty:raise ValueError('该区间没有交易数据。')
    if set(q.symbols)-set(window.symbol):raise ValueError('请求股票在该区间没有本地行情：'+', '.join(sorted(set(q.symbols)-set(window.symbol))))
    chosen=list(dict.fromkeys(candidates if q.intent=='correlation_ranking' or not q.symbols else q.symbols))
    if q.intent=='correlation_ranking' and q.anchor not in chosen:chosen.append(q.anchor)
    if full_only and (not q.symbols or q.intent=='correlation_ranking'):
        complete=set(complete_symbols(window))
        removed=sorted(set(chosen)-complete)
        if q.intent=='correlation_ranking' and q.anchor in removed:
            raise ValueError('参考股票在请求区间历史不完整，请缩小区间。')
        chosen=[s for s in chosen if s in complete]
        if removed:notes.append('日期不足或无记录，已排除：'+', '.join(removed))
    missing=set(chosen)-set(window.symbol)
    if missing:raise ValueError('候选股票在该区间没有记录：'+', '.join(sorted(missing)))
    part=window[window.symbol.isin(chosen)]
    if part.empty:raise ValueError('筛选后没有可用股票。')
    part,start,end=common_window(part)
    stats=metrics(part)
    if stats.empty:raise ValueError('共同区间至少需要3个交易日。')
    if set(chosen)-set(stats.index):raise ValueError('部分股票有效记录不足3个交易日，请缩小股票范围。')
    if (end-start).days<(q.end-q.start).days-10:notes.append(f'共同窗口缩小至{start:%Y-%m-%d}—{end:%Y-%m-%d}，请注意历史不足。')
    prices=price_matrix(part);returns=daily_returns(prices)
    label={'total_return':'区间收益率','annual_volatility':'年化波动率','max_drawdown':'最大回撤'}[q.metric]
    context=dict(intent=q.intent,symbols=chosen,requested_start=str(q.start.date()),requested_end=str(q.end.date()),
                 actual_start=str(start.date()),actual_end=str(end.date()),metric=q.metric,time_basis=q.time_basis,
                 ranking_limit=q.limit,anchor=q.anchor,full_only=full_only)
    if q.intent=='ranking':
        table=stats.sort_values(q.metric,ascending=q.ascending).head(q.limit)
        first=table.iloc[0]
        explanation=f'在{start:%Y-%m-%d}至{end:%Y-%m-%d}的{len(stats)}只有效样本中，{table.index[0]}按本次排序位列首位，{label}为{first[q.metric]:.2%}。'
    elif q.intent=='correlation_ranking':
        anchor=returns[q.anchor]
        rows=[]
        for symbol in returns.columns:
            if symbol==q.anchor:continue
            pairs=pd.concat([anchor.rename('a'),returns[symbol].rename('b')],axis=1).dropna()
            if len(pairs)<20 or pairs.a.std()==0 or pairs.b.std()==0:continue
            rows.append(dict(symbol=symbol,correlation=pairs.a.corr(pairs.b),paired_observations=len(pairs)))
        if not rows:raise ValueError('相关性排名至少需要两只股票及20组成对有效日收益。')
        table=pd.DataFrame(rows).set_index('symbol').sort_values('correlation',ascending=q.ascending).head(q.limit)
        explanation=f'{table.index[0]}与{q.anchor}的日收益相关系数为{table.correlation.iloc[0]:.3f}，基于{int(table.paired_observations.iloc[0])}组成对观测，位列本次排序首位。'
        notes.append('按相关系数数值排序，参考股票自身已排除；相关性不表示因果或未来同步。')
    elif q.intent=='correlation':
        if len(prices.columns)<2:raise ValueError('相关性矩阵至少需要两只股票；找相似股票请问“与苹果相关性最高的前5只股票”。')
        if len(prices.columns)>20:raise ValueError('相关性矩阵最多展示20只股票，请缩小候选范围或指定股票。')
        table=returns.corr(min_periods=20)
        if table.isna().all().all():raise ValueError('相关性计算至少需要20组成对有效日收益。')
        explanation=f'展示{len(table)}只股票的日收益率相关性矩阵，每对至少需要20组有效观测。'
    elif q.intent=='monthly':
        if len(prices.columns)>20:raise ValueError('月度热力图最多展示20只股票，请明确股票或缩小候选范围。')
        table=prices.resample('ME').last().pct_change(fill_method=None).iloc[1:]
        if table.empty:raise ValueError('月度收益至少需要两个有记录的月份。')
        explanation='按区间内各月最后一个有效价格计算月度收益；首月因缺少基期而省略。'
        notes.append('末月若未覆盖完整月份，其收益只计算至实际结束日。')
    else:
        if len(prices.columns)>10:raise ValueError('走势图最多比较10只股票，请明确股票或缩小候选范围。')
        if q.metric=='annual_volatility':
            table=returns.rolling(20).std()*np.sqrt(252)
            if table.dropna(how='all').empty:raise ValueError('20日滚动波动率至少需要21个价格观测。')
            explanation='展示20日滚动年化波动率，以252个交易日进行年化。'
        elif q.metric=='max_drawdown':
            table=prices/prices.cummax()-1;explanation='展示相对所选窗口内历史高点的回撤，负值绝对值越大表示回撤越深。'
        else:
            table=prices/prices.iloc[0]-1;explanation='以共同窗口首个价格为基期，展示数据源复权价格的累计变化。'
    return Result(q.intent,table,context,explanation,notes)
