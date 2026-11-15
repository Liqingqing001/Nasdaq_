from pathlib import Path
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from nasdaq.analytics import clean_prices, price_matrix, daily_returns, metrics, cluster_stocks, common_window
from nasdaq.query import parse_query

ROOT = Path(__file__).parent
st.set_page_config(page_title='Nasdaq Lens · 纳斯达克研究台', page_icon='↗', layout='wide')
st.markdown('''<style>
.block-container{padding-top:3.5rem;max-width:1480px} h1{letter-spacing:-1.5px}
[data-testid="stMetric"]{background:white;border:1px solid #e3e9f3;padding:18px;border-radius:12px}
[data-testid="stSidebar"]{border-right:1px solid #e3e9f3}
</style>''', unsafe_allow_html=True)

@st.cache_data
def load_data(path, mtime):
    return clean_prices(pd.read_csv(path))

def chart(fig, key):
    fig.update_layout(template='plotly_white', font=dict(family='Microsoft YaHei, Arial', size=12),
                      margin=dict(l=12,r=12,t=45,b=20), height=370,
                      paper_bgcolor='white', plot_bgcolor='white', legend_title_text='')
    labels={'total_return':'区间收益率','annual_volatility':'年化波动率','max_drawdown':'最大回撤','symbol':'股票代码','date':'交易日期','volume':'成交量','value':'指标值','variable':'指标'}
    for axis in ['xaxis','yaxis']:
        title=getattr(fig.layout,axis).title.text
        if title in labels:getattr(fig.layout,axis).title.text=labels[title]
    st.plotly_chart(fig, width='stretch', key=key)

def wide_line(frame, title, key, percent=True):
    fig=px.line(frame, title=title)
    if percent:fig.update_yaxes(tickformat='.0%')
    chart(fig,key)

st.caption('NASDAQ LENS  /  数据可视化课程项目')
st.title('从价格走势，到风险洞察')
st.write('在同一个研究窗口里比较股票，用图表解释差异，用自然语言提出问题。')
demo_exists=(ROOT/'data/prices_demo.csv').exists()
mode=st.sidebar.selectbox('数据模式',['研究数据','公开历史演示'],index=1 if demo_exists and not (ROOT/'data/prices.csv').exists() else 0)
demo=mode=='公开历史演示'
universe_path=ROOT/('data/universe_demo.csv' if demo else 'data/universe.csv')
path=ROOT/('data/prices_demo.csv' if demo else 'data/prices.csv')
if not universe_path.exists():
    st.info('请运行 py scripts/import_demo.py 获取公开历史示例。');st.stop()
universe=pd.read_csv(universe_path)
if demo:
    st.warning('历史演示模式：Plotly公开的2015—2017年5只股票示例，含非指数样本和历史退市代码；仅用于体验功能，不是纳斯达克100研究数据。')
if not path.exists():
    st.info('还没有本地行情。研究数据运行 py scripts/download_data.py；公开历史演示运行 py scripts/import_demo.py。系统不使用模拟行情替代真实数据。')
    st.dataframe(universe[['symbol','name','sector']],hide_index=True)
    st.stop()
try:
    all_data, quality=load_data(str(path),path.stat().st_mtime_ns)
except ValueError as exc:
    st.error(str(exc));st.stop()
if all_data.empty:
    st.error('数据清洗后没有有效行情。');st.stop()
available=sorted(all_data.symbol.unique())
with st.sidebar:
    st.header('研究范围')
    st.caption('公开历史示例，非指数样本。' if demo else '首版：10只代表性股票开发样本\n非完整指数，也不复刻历史成分。')
    selected=st.multiselect('股票池',available,default=available)
    dates=st.date_input('分析区间',value=(all_data.date.min().date(),all_data.date.max().date()),
                        min_value=all_data.date.min().date(),max_value=all_data.date.max().date())
    page=st.radio('工作台',['市场概览','个股分析','风险聚类','智能问数','数据与口径'])
    st.divider()
    st.caption('收益采用复权收盘价；K线采用原始价格。\n离线缓存运行，不提供实时行情。')
if not selected or len(dates)!=2:
    st.info('请选择至少一只股票和完整的起止日期。');st.stop()
filtered=all_data[all_data.symbol.isin(selected)&all_data.date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
if filtered.empty:
    st.warning('该区间没有交易数据。');st.stop()
df,start,end=common_window(filtered)
stats=metrics(df)
if stats.empty:
    st.warning('共同窗口内至少需要3个交易日。');st.stop()
prices=price_matrix(df);returns=daily_returns(prices)
stats=stats.join(universe.set_index('symbol')[['name','sector']])
coverage=set(selected)-set(stats.index)
if coverage:st.warning('数据不足，未参与统计：'+', '.join(sorted(coverage)))
st.caption(f'共同覆盖窗口 {start:%Y-%m-%d} — {end:%Y-%m-%d} · {len(stats)}只股票 · {len(df):,}条日线 · USD')
a,b,c,d=st.columns(4)
a.metric('样本股票',f'{len(stats)}')
b.metric('区间收益中位数',f'{stats.total_return.median():.1%}')
c.metric('年化波动中位数',f'{stats.annual_volatility.median():.1%}')
d.metric('最大回撤中位数',f'{stats.max_drawdown.median():.1%}')
if page=='市场概览':
    st.subheader('01 / 比较表现')
    left,right=st.columns([2,1])
    with left:wide_line(prices/prices.iloc[0]-1,'累计收益 · 统一起点','cumulative')
    with right:chart(px.bar(stats.sort_values('total_return').reset_index(),x='total_return',y='symbol',orientation='h',title='区间收益排名'), 'ranking')
    left,right=st.columns(2)
    with left:
        counts=stats.groupby('sector').size().rename('数量').reset_index()
        chart(px.bar(counts,x='sector',y='数量',title='样本行业分布 · 按证券数量'),'sector')
    with right:
        chart(px.scatter(stats.reset_index(),x='annual_volatility',y='total_return',color='sector',hover_name='symbol',title='风险与收益 · 历史特征'), 'risk_return')
    wide_line((prices/prices.iloc[0]).T.groupby(stats.sector).mean().T-1,
              '行业样本等权买入持有收益 · 非官方行业指数','sector_returns')
elif page=='个股分析':
    st.subheader('02 / 观察一家公司')
    symbol=st.selectbox('个股',list(stats.index))
    part=df[df.symbol.eq(symbol)].set_index('date').sort_index()
    fig=go.Figure(go.Candlestick(x=part.index,open=part.open,high=part.high,low=part.low,close=part.close,name=symbol))
    fig.add_scatter(x=part.index,y=part.close.rolling(20).mean(),name='MA20',line=dict(color='#2155ED'))
    fig.update_layout(title=f'{symbol} 原始价格与20日均线',xaxis_rangeslider_visible=False)
    chart(fig,'candles')
    left,right=st.columns(2)
    with left:chart(px.bar(part,x=part.index,y='volume',title='成交量 · 股'),'volume')
    with right:chart(px.histogram(returns[symbol].dropna(),nbins=40,title='日收益率分布'),'histogram')
    monthly=prices[symbol].resample('ME').last().pct_change(fill_method=None).dropna()
    # Omit first partial month: no preceding month end inside requested window.
    if len(monthly):
        table=pd.DataFrame({'year':monthly.index.year,'month':monthly.index.month,'return':monthly.values}).pivot(index='year',columns='month',values='return')
        chart(px.imshow(table,color_continuous_scale='RdBu',color_continuous_midpoint=0,text_auto='.1%',aspect='auto',title='月末至月末收益 · 首月无基期不展示'),'monthly')
    wide_line((returns[symbol].rolling(20).std()*np.sqrt(252)).to_frame(), '20日滚动年化波动','rolling')
    wide_line((prices[symbol]/prices[symbol].cummax()-1).to_frame(),'相对窗口内历史高点的回撤','drawdown')
elif page=='风险聚类':
    st.subheader('03 / 发现相似的风险收益特征')
    st.caption('K-means使用区间收益、年化波动、最大回撤；StandardScaler标准化。属于描述性分组，不是未来走势预测。')
    if len(stats)<4:
        st.info('请至少选择4只股票以运行聚类。')
    else:
        k=st.slider('分组数量 K',2,min(5,len(stats)-1),min(3,len(stats)-1))
        try:
            clustered,score,model,scaler=cluster_stocks(stats,k)
            st.metric('轮廓系数',f'{score:.3f}')
            chart(px.scatter(clustered.reset_index(),x='annual_volatility',y='total_return',color='cluster',hover_name='symbol',size=-clustered.max_drawdown+0.01,title='聚类分布 · 点越大表示最大回撤幅度越大'),'clusters')
            centers=clustered.groupby('cluster')[['total_return','annual_volatility','max_drawdown']].mean()
            chart(px.bar(centers.reset_index().melt(id_vars='cluster'),x='cluster',y='value',color='variable',barmode='group',title='每组历史指标均值'),'cluster_means')
            scores=[]
            for candidate in range(2,min(6,len(stats))):
                try:scores.append({'K':candidate,'轮廓系数':cluster_stocks(stats,candidate)[1]})
                except ValueError:pass
            chart(px.line(pd.DataFrame(scores),x='K',y='轮廓系数',markers=True,title='不同K值的分组质量'),'silhouettes')
            st.dataframe(clustered, width='stretch')
        except ValueError as exc:st.warning(str(exc))
    corr=returns.corr(min_periods=20)
    chart(px.imshow(corr,zmin=-1,zmax=1,color_continuous_scale='RdBu',aspect='auto',title='日收益率相关性 · 至少20组有效观测'),'correlation')
elif page=='智能问数':
    st.subheader('04 / 用一句话开始分析')
    st.caption('规则解析版 · 无需API密钥。支持样本股票、中文别名、明确年份/日期；不支持的问题会明确提示。未写时间时使用侧栏范围，未写股票时使用侧栏股票池。')
    year=all_data.date.max().year
    other=available[min(1,len(available)-1)]
    examples=[f'{year}年收益最高的前5只股票',f'比较{available[0]}和{other}在{year}年的累计收益',f'{year}年最大回撤最小的前5只股票',f'展示{available[0]}在{year}年月度收益',f'比较{available[0]}和{other}在{year}年的相关性']
    example=st.selectbox('示例问题',examples)
    question=st.text_input('你的问题',value=example)
    if st.button('分析问题',type='primary'):
        try:
            query=parse_query(question,universe,*dates)
            if query.start<all_data.date.min()-pd.Timedelta(days=7) or query.end>all_data.date.max()+pd.Timedelta(days=7):
                raise ValueError('请求超出本地行情覆盖范围，请缩小日期范围或先下载对应数据。')
            chosen=query.symbols or selected
            if set(chosen)-set(available):raise ValueError('请求股票没有本地行情。')
            subset=all_data[all_data.symbol.isin(chosen)&all_data.date.between(query.start,query.end)]
            if set(chosen)-set(subset.symbol):raise ValueError('部分股票在请求区间没有行情。')
            subset,qs,qe=common_window(subset)
            qm=metrics(subset);qp=price_matrix(subset)
            if qm.empty:raise ValueError('请求区间至少需要3个交易日。')
            st.json({'类型':query.intent,'股票':chosen,'请求开始':str(query.start.date()),'请求结束':str(query.end.date()),'实际开始':str(qs.date()),'实际结束':str(qe.date()),'排序字段':query.metric})
            if query.intent=='ranking':
                result=qm.sort_values(query.metric,ascending=query.ascending).head(query.limit)
                chart(px.bar(result.reset_index(),x='symbol',y=query.metric,title='问数结果 · '+query.metric),'query_ranking')
                st.dataframe(result)
            elif query.intent=='correlation':
                result=daily_returns(qp).corr(min_periods=20)
                chart(px.imshow(result,zmin=-1,zmax=1,color_continuous_scale='RdBu',title='所选股票收益率相关性'),'query_correlation')
                st.dataframe(result)
            elif query.intent=='monthly':
                result=qp.resample('ME').last().pct_change(fill_method=None).iloc[1:]
                chart(px.imshow(result.T,color_continuous_scale='RdBu',color_continuous_midpoint=0,text_auto='.1%',aspect='auto',title='月度收益'),'query_monthly')
                st.dataframe(result)
            else:
                result=qp/qp.iloc[0]-1
                wide_line(result,'累计收益比较','query_trend');st.dataframe(qm)
            st.download_button('下载本次结果CSV',result.to_csv().encode('utf-8-sig'),'query_result.csv','text/csv')
        except (ValueError,KeyError) as exc:st.error(str(exc))
else:
    st.subheader('数据来源与计算口径')
    manifest=ROOT/('data/demo_manifest.json' if demo else 'data/manifest.json')
    if manifest.exists():st.json(json.loads(manifest.read_text(encoding='utf-8')))
    if demo:st.info('本模式数据来自Plotly官方示例仓库，包含历史代码；下列研究口径仅说明系统计算方法，不表示样本属于纳斯达克100。')
    st.write('清洗结果',quality)
    st.dataframe(all_data.groupby('symbol').agg(start=('date','min'),end=('date','max'),rows=('date','size')))
    st.markdown('''- 收益：复权收盘价末值/初值−1；波动率：日收益样本标准差×√252。
- 回撤：复权价格/窗口内累计最高价−1，最大回撤取最小值；窗口起点之前的损失不计算。
- 多股票比较采用共同起止窗口；缺失交易日不前向填充。相关性按成对有效观测计算。
- 名单为明确的开发样本，非完整纳斯达克100，不代表各历史时点成分，存在样本选择偏差。
- 数据来自Yahoo Finance，经yfinance获取；请遵守数据提供方使用条款。缓存默认不提交GitHub。
- 项目用于课程研究，尚未加入实时行情、财报分析或生成式AI。''')
    st.download_button('导出当前分析指标',stats.to_csv().encode('utf-8-sig'),'analysis.csv','text/csv')
