# Nasdaq Lens

面向纳斯达克股票样本的风险收益可视化与中文智能问数系统。

第一版采用10只代表性股票验证完整流程，**尚未覆盖完整纳斯达克100**。不依赖大模型API，不提供实时行情。课程最终作品文档与PPT将在系统验收后整理。

## Windows启动

在PowerShell进入项目目录，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements-dev.txt
py scripts/download_data.py
py -m streamlit run app.py
```

如果本机的py启动器未识别已激活环境，使用`.\.venv\Scripts\python.exe`执行同一命令。无法运行激活脚本时也可以直接使用该解释器，无需改变系统执行策略。

下载日期默认2023-01-01至2026-01-01（结束日不包含）。首次下载需要联网；后续页面使用本地缓存。没有缓存时展示获取提示，不展示虚构行情。

如果Yahoo在本地网络限流或不可达，可先使用官方公开历史示例体验：

```powershell
py scripts/import_demo.py
py -m streamlit run app.py
```

该模式采用Plotly示例仓库中的2015—2017年5只股票数据，含非指数样本和历史退市代码，界面会明确标识，**不得作为2023—2025年纳斯达克100研究结论**。模式不会自动用历史数据覆盖研究缓存。

2026-11-15本地验证：Yahoo/yfinance返回限流；历史示例下载成功；13项核心及页面集成测试通过。精确环境版本见requirements-lock.txt（Python 3.12，Windows开发环境）。

## 使用

- 侧栏选择股票池、日期及页面。
- 概览比较累计收益与行业样本表现；个股页面查看K线、月收益、波动与回撤。
- 聚类页面调整K并查看轮廓系数；问数页面输入“2025年最大回撤最小的前5只股票”等问题。
- 数据页面查看下载来源、覆盖范围与清洗记录，导出指标。

## 测试

```powershell
py -m pytest -q
```

真实行情不随仓库分发；核心公式测试使用明确的人工路径。自动测试不需要外部网络。

需求与验收见[需求文档](docs/requirements.md)，数据口径见[来源说明](docs/data-sources.md)。
