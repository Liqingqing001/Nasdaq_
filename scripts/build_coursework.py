"""Build a reproducible offline HTML report and analysis tables from verified cache."""
from pathlib import Path
import hashlib,json,sys
from html import escape
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nasdaq.analytics import clean_prices,complete_symbols,metrics,price_matrix,daily_returns,cluster_stocks

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'submission';OUT.mkdir(exist_ok=True)
AN=OUT/'分析结果';AN.mkdir(exist_ok=True)
PALETTE=['#D83C43','#557A95','#A87936','#3F8276','#7C6B9A','#A75F79']
px.defaults.color_discrete_sequence=PALETTE

def main():
    manifest=json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
    payload=(ROOT/'data/prices.csv').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=manifest['sha256']:raise ValueError('Research hash mismatch')
    raw,quality=clean_prices(pd.read_csv(ROOT/'data/prices.csv'))
    names=pd.read_csv(ROOT/'data/universe.csv').fillna('').set_index('symbol')
    symbols=complete_symbols(raw);df=raw[raw.symbol.isin(symbols)]
    stats=metrics(df).join(names[['name','sector']]);prices=price_matrix(df);ret=daily_returns(prices)
    stats.to_csv(AN/'样本指标.csv',encoding='utf-8-sig')
    scores=[];models={}
    for k in range(2,7):
        clustered,score,_,_=cluster_stocks(stats,k);scores.append({'K':k,'silhouette':score});models[k]=clustered
    score_df=pd.DataFrame(scores);best=int(score_df.loc[score_df.silhouette.idxmax(),'K']);clustered=models[best]
    score_df.to_csv(AN/'K值比较.csv',index=False,encoding='utf-8-sig');clustered.to_csv(AN/'聚类结果.csv',encoding='utf-8-sig')
    sample=df.to_csv(index=False).encode('utf-8');(AN/'完整样本行情.csv').write_bytes(sample)
    top=stats.nlargest(5,'total_return');low=stats.nsmallest(5,'annual_volatility')
    base=['AAPL','MSFT','NVDA','AMD','COST'];base=[s for s in base if s in prices]
    monthly=prices[base].resample('ME').last().pct_change(fill_method=None).iloc[1:]
    p=prices['AAPL'];part=df[df.symbol.eq('AAPL')].set_index('date')
    figs=[]
    def add(fig,caption):
        fig.update_layout(template='plotly_white',height=370,margin=dict(l=55,r=20,t=50,b=45),font=dict(family='Microsoft YaHei',size=12),hoverlabel=dict(bgcolor='white',font_color='#202632'))
        number=len(figs)+1
        if number in [2,3,8,9]:fig.update_yaxes(tickformat='.0%',title='比率')
        if number==6:fig.update_xaxes(tickformat='.0%',title='日收益率');fig.update_yaxes(title='频数')
        if number==11:fig.update_xaxes(tickformat='.0%',title='年化波动率');fig.update_yaxes(tickformat='.0%',title='区间收益率')
        if number==7:fig.update_layout(coloraxis_colorbar_tickformat='.0%')
        if number==1:fig.update_xaxes(title='行业')
        if number==2:fig.update_xaxes(title='证券代码')
        if number in [3,4,5,8,9]:fig.update_xaxes(title='交易日期')
        figs.append((fig,caption))
    add(px.bar(stats.reset_index().groupby('sector').size().rename('数量').reset_index(),x='sector',y='数量',title='完整样本行业分布'),'项目自定义行业粗分类，只反映本研究样本构成。')
    add(px.bar(stats.nlargest(15,'total_return').reset_index(),x='symbol',y='total_return',title='三年区间调整后价格收益前15名'),'固定2026年快照回看历史，排名存在选样偏差，不代表当年可实现策略。')
    add(px.line(prices[base]/prices[base].iloc[0]-1,title='代表股票累计收益比较'),'所有序列以2023年第一个交易日为统一基期。')
    add(go.Figure(go.Candlestick(x=part.index,open=part.open,high=part.high,low=part.low,close=part.close)).update_layout(title='苹果原始价格K线',xaxis_rangeslider_visible=False),'原始OHLC与复权收益分别处理，拆股附近需结合复权数据解读。')
    add(px.bar(part,x=part.index,y='volume',title='苹果日成交量'),'成交量沿用供应商股数，不解释为成交金额。')
    add(px.histogram(ret['AAPL'].dropna(),nbins=45,title='苹果日收益率分布'),'直方图呈现经验分布，不预设正态分布。')
    add(px.imshow(monthly.T,color_continuous_scale='RdBu',color_continuous_midpoint=0,aspect='auto',title='代表股票月度收益热力图'),'首月缺少上月末基期，因此从第二个月开始计算。')
    add(px.line(ret[base].rolling(20).std()*252**.5,title='20日滚动年化波动率'),'样本标准差乘以252的平方根，前20个价格观测不足时不计算。')
    add(px.line(prices[base]/prices[base].cummax()-1,title='窗口内回撤'),'高点只在研究窗口内累计，不包含窗口开始前的损失。')
    add(px.imshow(ret[base].corr(min_periods=20),zmin=-1,zmax=1,color_continuous_scale='RdBu',title='代表股票日收益率相关性'),'相关性为样本内统计关系，不表示因果关系或未来稳定性。')
    add(px.scatter(clustered.reset_index(),x='annual_volatility',y='total_return',color='cluster',hover_name='symbol',title=f'风险收益聚类 K={best}'),'模型输入还包括最大回撤；图中二维投影不能完全展示三维特征距离。')
    add(px.line(score_df,x='K',y='silhouette',markers=True,title='聚类数量与轮廓系数'),'在同一标准化样本上比较K=2至6，选择轮廓系数最高的候选值。')
    facts=dict(n=len(stats),rows=len(df),sessions=len(prices),start=str(prices.index.min().date()),end=str(prices.index.max().date()),
               median_return=float(stats.total_return.median()),median_vol=float(stats.annual_volatility.median()),median_drawdown=float(stats.max_drawdown.median()),
               top_symbols=list(top.index),top_returns=list(top.total_return),low_symbols=list(low.index),low_vol=list(low.annual_volatility),
               best_k=best,best_score=float(score_df.silhouette.max()),k_values=score_df.K.tolist(),scores=score_df.silhouette.tolist(),
               cluster_counts=clustered.cluster.value_counts().sort_index().to_dict(),sample_sha256=hashlib.sha256(sample).hexdigest(),
               source_sha256=manifest['sha256'],observed_securities=raw.symbol.nunique(),universe_size=len(names))
    (OUT/'analysis-facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
    table=top[['total_return','annual_volatility','max_drawdown']].copy()
    table.columns=['区间收益率','年化波动率','最大回撤']
    table=table.map(lambda x:f'{x:.2%}')
    sections=[
    ('摘要',f'本项目面向缺乏编程经验的金融数据学习者，设计并实现Nasdaq Lens风险收益可视化与中文智能问数系统。股票池以Nasdaq官网2026年11月2日快照为依据，包含100家公司、101个证券代码。采集2023—2025年日线后，取得71个代码的49,228条记录，正式分析限定为日期完整的{len(stats)}个证券样本，共{len(df):,}条观测。系统完成原始与前复权价格分离、数据校验、指标构造、K-means聚类及五个交互页面，展示超过10类图表，并支持自然语言筛选、排名和趋势比较。模型在K=2至6之间比较轮廓系数，最优候选为K={best}。项目提供离线数据缓存、来源清单、可重复构建脚本及自动化测试。研究结果用于描述样本的历史差异，不等同于完整指数重建或收益预测。'),
    ('1 需求分析与产品设计','目标用户是希望比较股票历史表现、但不熟悉数据处理代码的课程学习者。核心需求包括按股票与日期筛选数据、在相同窗口比较收益与风险、发现相似样本，以及用中文问题触发可核验的计算。系统采用市场概览、个股分析、风险聚类、智能问数和数据与口径五个页面。侧栏负责股票池、日期和完整样本筛选，顶部导航切换分析任务。红色用于强调交互状态，浅灰背景和白色图表区域保持信息层级。图表提供悬停、缩放和下载，滚轮缩放关闭以避免妨碍页面滚动。非功能需求包括本地缓存、数据来源可追溯、异常输入明确反馈和离线展示。'),
    ('2 数据来源与研究范围','成分股名单来自Nasdaq官方PDF，脚本解析日期、名称、证券代码和权重，并检查代码唯一性、记录数与权重合计范围。快照包含Alphabet的两个股份类别，因此证券数量与公司数量不同。行情采用东方财富公开美股日线接口，分别请求原始价格和前复权价格，记录URL、获取时间和缓存哈希。项目未将未取得的30个代码或历史不足的8个代码用模拟数据补齐。正式研究以63个完整历史证券为样本，样本单位是证券代码，并非63家互不重复的公司。行业采用项目自定义粗分类，不声称属于官方GICS或ICB体系。固定2026年快照回看2023—2025年存在幸存者和选样偏差，因此结果不用于复现当时的可投资股票池。'),
    ('3 数据处理与质量控制','处理流程首先检查字段、日期、正价格、非负成交量与OHLC关系，删除非法记录并对同一股票同一日期去重。原始与复权序列必须具有相同日期且供应商返回的代码身份必须一致，否则拒绝合并。采集按证券缓存，可在网络中断后恢复。默认95%的证券覆盖门槛用于阻止失败采集覆盖活动缓存，本机部分研究模式显式记录较低门槛及缺失清单。当前完整样本参照所有已观测交易日期筛选，不前向填充停牌或缺失值。该参考日历能发现单只股票相对其他样本缺少记录，但无法发现所有股票同日同时缺失。活动CSV与来源清单通过SHA256核对，防止数据和元信息错配。'),
    ('4 指标构造与模型方法','区间收益率为复权收盘价末值除以初值减一；日收益采用相邻有效交易日价格变化；年化波动率使用日收益样本标准差乘以√252；回撤为价格除以窗口内历史最高价减一，最大回撤取最小值。前复权价格由数据源调整，不将其未经核验地解释成分红再投资总回报。聚类使用区间收益、年化波动和最大回撤三个特征，先通过StandardScaler标准化，再运行固定随机种子42、20次初始化的K-means。比较K=2至6的轮廓系数，兼顾分组区分程度和解释成本。该模型属于无监督描述性分析，不是价格预测模型，不使用随机划分来虚构未来预测准确率。'),
    ('5 可视化系统与智能问数','后端采用Pandas和NumPy处理数据，scikit-learn完成聚类，Plotly绘图，Streamlit组织交互。计算、采集、问数解析和结果执行分为独立模块。中文问数识别股票代码、常用中文别名、明确年份或日期以及相对时间。相对时间锚定侧栏所选结束日，并在页面显示基准日期。问题转换为结构化条件，由固定计算函数执行，而不是让模型生成任意Python或SQL。相关性排名排除参考股票自身，并要求每对股票至少有20组有效日收益。波动率请求绘制滚动年化波动，回撤请求绘制窗口内回撤，避免不同问法都返回累计收益。对财务指标、未来预测、多目标排序和含糊时间表达，系统给出明确限制。图表、表格和CSV共用同一结果，表单重新渲染或下载后仍保留结果，切换研究范围则清除旧结果。'),
    ('6 结果分析',f'共同研究窗口为{facts["start"]}至{facts["end"]}，包含{facts["sessions"]}个已观测交易日。完整样本区间收益中位数为{facts["median_return"]:.2%}，年化波动中位数为{facts["median_vol"]:.2%}，最大回撤中位数为{facts["median_drawdown"]:.2%}。收益排名前列包括{", ".join(top.index[:3])}，具体数值见下表。这些结果只描述样本和时间窗口内的复权价格变化。三维特征聚类最优候选K={best}，轮廓系数为{facts["best_score"]:.3f}；高收益样本可能同时具有较高波动或较深回撤，不能只依据收益高低判断风险。最大回撤、波动率和相关性关注不同维度，组合使用比单一收益排名更有解释力。K-means对尺度和离群点敏感，标准化不能消除所有偏态影响，分组结果也不应被解释为永久固定的股票类别。'),
    ('7 测试验收与复现','自动测试覆盖已知价格路径的收益与回撤、非法值清洗、缺失值不填零、代码身份、复权日期对齐、快照截断拒绝、相对时间边界、相关性自相关排除和排名方向等。页面测试覆盖五个工作台、成功与失败问数、无数据入口、来源哈希错配、下载与重绘后的结果保留。最终测试结果由随包验收记录给出，不用未经运行的项目替代通过项。浏览器实际检查浅色主题、图表白色悬浮框、窄屏无横向溢出以及鼠标位于图表时页面正常滚动。提交包附带真实缓存，安装依赖后运行无需再次联网采集；首次安装Python依赖需要网络或预先准备的环境。分析构建脚本可以重新生成样本指标、聚类结果和图表报告。'),
    ('8 局限与改进方向','最主要限制是行情覆盖尚未达到完整101个证券，且短历史、交易所迁移和代码变化需要进一步核验。正式报告以63个完整历史样本收口，不能把这一样本推广为整个美股市场。行业粗分类、前复权定义和参考交易日历均在数据说明中披露。系统使用受控规则解析，表达范围有限，未接入生成式大模型，这符合课程中大模型功能可选的要求。后续可引入带历史生效日期的成分股集合、独立交易日历、第二行情源交叉核对，以及基于结构化查询工具的大模型理解层。任何增强都应继续保留计算口径和可追溯证据。'),
    ('9 结论','项目已形成从公开数据采集、清洗、指标与聚类建模到交互可视化、中文问数和结果导出的完整链路。实际成果是一个可以离线展示的金融信息分析系统，而研究结论明确限定于已核验样本。课程重点在于数据分析建模与可视化表达，项目通过多视角图表、可解释问数、可复现构建和异常处理满足这一目标。完整指数行情覆盖及更广泛自然语言能力保留为后续改进，不作为当前研究已经完成的事实。')]
    css='body{max-width:1040px;margin:40px auto;padding:0 28px;color:#202632;background:#f5f6f8;font:17px/1.8 "Times New Roman",SimSun,serif}h1,h2,h3{font-family:"Microsoft YaHei",SimHei,sans-serif}h1{font-size:32px}h2{font-size:23px;margin-top:35px;color:#a62d36}article{background:white;padding:45px;border:1px solid #e2e5eb}p{text-indent:2em;text-align:justify}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d8dce3;padding:8px}figure{margin:22px 0;break-inside:avoid}figcaption{font-size:14px;color:#626c7a}.meta{color:#626c7a;text-indent:0}a{color:#a62d36}@media print{body{background:white;margin:0;max-width:none;padding:0;font-size:11pt}article{border:0;padding:0}h2{break-after:avoid}figure{break-inside:avoid}.plotly-graph-div{height:290px!important} @page{size:A4;margin:18mm}}'
    body=f'<h1>纳斯达克100成分股样本风险收益可视化与智能问数系统</h1><p class="meta">数据可视化技术课程项目作品文档<br>李晴　202400702062<br>深圳技术大学　2024级数据科学与大数据技术<br>研究窗口：{facts["start"]}—{facts["end"]}</p>'
    for title,text in sections:
        body+=f'<h2>{title}</h2><p>{escape(text)}</p>'
        if title=='6 结果分析':body+=table.to_html()
    body+='<h2>参考资料与数据依据</h2><ol>'
    for name,url in [('Nasdaq官方成分股快照','https://www.nasdaq.com/docs/global-indexes/NDX'),('AKShare公开行情接口实现','https://github.com/akfamily/akshare/blob/main/akshare/stock/quote/stock_hist_em.py'),('scikit-learn K-means文档','https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html'),('Streamlit文档','https://docs.streamlit.io/'),('Plotly文档','https://plotly.com/python/')]:body+=f'<li><a href="{url}">{name}</a>，访问日期2026-11-15。</li>'
    body+='</ol><h2>附录 图表分析</h2>'
    for i,(fig,caption) in enumerate(figs,1):
        body+=f'<figure>{fig.to_html(full_html=False,include_plotlyjs=False,div_id=f"chart-{i}",config={"scrollZoom":False,"displaylogo":False})}<figcaption>图{i}　{escape(caption)}</figcaption></figure>'
    html=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Nasdaq Lens课程项目作品文档</title><style>{css}</style><script>{get_plotlyjs()}</script><article>{body}</article></html>'
    (OUT/'202400702062-李晴-作品文档.html').write_text(html,encoding='utf-8')
    print(json.dumps(facts,ensure_ascii=False))
if __name__=='__main__':main()
