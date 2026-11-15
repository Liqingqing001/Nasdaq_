"""Create an attachment-ready package, excluding credentials, caches and environments."""
from pathlib import Path
import shutil,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'submission';PROGRAM=OUT/'程序';PROGRAM.mkdir(exist_ok=True)

def main():
    for name in ['app.py','README.md','运行系统.ps1','requirements.txt','requirements-dev.txt','requirements-lock.txt','.gitattributes']:
        shutil.copy2(ROOT/name,PROGRAM/name)
    for directory in ['nasdaq','assets','scripts','tests','.streamlit','docs']:
        for src in (ROOT/directory).rglob('*'):
            if not src.is_file() or '__pycache__' in src.parts or src.suffix=='.pyc' or src.name=='secrets.toml':continue
            target=PROGRAM/src.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    for name in ['prices.csv','manifest.json','universe.csv','universe_manifest.json','quality_summary.json']:
        target=PROGRAM/'data'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(ROOT/'data'/name,target)
    shutil.copy2(ROOT/'docs/data-sources.md',OUT/'数据来源说明.md')
    shutil.copy2(ROOT/'docs/课程验收清单.md',OUT/'课程验收清单.md')
    guide='''# 提交与演示说明

作者：李晴 202400702062

1. 作品文档.html：双击用Edge或Chrome打开，报告与12张交互图表均已内嵌，离线可读。
2. 项目汇报.pptx：PowerPoint打开，12页，图表可编辑，备注含数据依据和讲述提示。
3. 程序：用PowerShell进入程序目录，运行 .\\运行系统.ps1。若脚本被本机策略阻止，可按README手动创建环境并运行；不需要修改系统全局执行策略。
4. 首次安装Python依赖需要网络。数据已随包提供，正常演示不需要再次联网下载行情。端口8501已有项目运行时，可直接打开 http://127.0.0.1:8501，或手动另选端口。
5. 分析结果目录：63个完整样本的行情、指标、K值比较和聚类分组，可核查报告数字。

建议现场演示约6分钟：
市场概览说明研究范围1分钟；个股K线、月收益和回撤1分钟；风险聚类选择K=2并说明轮廓系数1分钟；智能问数输入“与苹果近一年相关性最高的前5只股票”和“比较苹果和微软近三个月的波动率”2分钟；数据页说明来源与缺失1分钟。

答辩口径：股票池来自官方101个代码快照，实际获取71个代码；正式分析是63个日期完整证券样本。自然语言功能采用规则解析而非大模型。聚类是描述性分析，不是价格预测。前复权价格收益不能未经核验就当作分红再投资总回报。
'''
    (OUT/'提交与演示说明.md').write_text(guide,encoding='utf-8')
    inventory=[]
    for file in OUT.rglob('*'):
        if file.is_file() and file.name!='文件校验清单.json':inventory.append(dict(path=file.relative_to(OUT).as_posix(),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    (OUT/'文件校验清单.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT/'deliverables/202400702062-李晴-数据可视化课程项目.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in OUT.rglob('*'):
            if file.is_file():z.write(file,Path('202400702062-李晴-数据可视化课程项目')/file.relative_to(OUT))
    print(json.dumps(dict(zip=str(archive),files=len(inventory)+1,bytes=archive.stat().st_size),ensure_ascii=False))
if __name__=='__main__':main()
