import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
// Run with the bundled artifact runtime. Course data and notes remain local.
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const facts=JSON.parse(await fs.readFile(path.join(root,'submission/analysis-facts.json'),'utf8'));
const p=Presentation.create({slideSize:{width:1280,height:720}});
const build=path.join(root,'.cache/slides');await fs.mkdir(build,{recursive:true});
function text(s,value,x,y,w,h,size=26,color='#202632',bold=false){const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});t.text=value;t.text.style={typeface:'Microsoft YaHei',fontSize:size,color,bold};return t;}
function slide(title,notes){const s=p.slides.add();s.background.fill='#F5F6F8';text(s,title,64,44,1150,74,40,'#202632',true);text(s,`Nasdaq Lens   数据可视化技术课程项目                                      ${p.slides.items.length}`,64,675,1150,26,15,'#687182');s.speakerNotes.text=notes;return s;}
function body(s,items,x=68,y=165,w=1130){items.forEach((item,i)=>text(s,item,x,y+i*95,w,80,27));}
function chart(s,type,categories,values,name,format='0.0%') {return s.charts.add(type,{position:{left:64,top:165,width:1135,height:405},categories,series:[{name,values:values.map(v=>Number(v.toFixed(10))),fill:'#D83C43'}],hasLegend:false,title:name,titleTextStyle:{typeface:'Microsoft YaHei',fontSize:22},xAxis:{textStyle:{typeface:'Microsoft YaHei',fontSize:18}},yAxis:{numberFormatCode:format,textStyle:{typeface:'Microsoft YaHei',fontSize:18}},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'});}
let s=slide('Nasdaq Lens','报告人李晴，学号202400702062。选题为纳斯达克100成分股样本金融信息服务。');
text(s,'纳斯达克100成分股样本\n风险收益可视化与智能问数系统',68,180,1120,190,48,'#B52F38',true);
text(s,'李晴  202400702062\n深圳技术大学  2024级数据科学与大数据技术',68,430,1120,110,28);
s=slide('用户需求与研究问题','从学习者角度介绍需求。演示不是交易软件，不承诺预测收益。');body(s,['比较股票在同一历史窗口中的收益和风险','用超过10类交互图表解释差异','通过中文问题获得可核验的图表与数据','保留来源、排除规则和离线复现能力']);
s=slide('股票池与实际数据范围','来源 https://www.nasdaq.com/docs/global-indexes/NDX 。快照日期2026-11-02。行情来源见提交包data/manifest.json。');body(s,['官方快照为100家公司、101个证券代码','已获取71个证券的49,228条日线','正式分析使用63个日期完整证券、47,376条记录','研究窗口为2023-01-03至2025-12-31']);text(s,'固定当前快照回看历史，存在样本选择偏差。',68,590,1120,45,22,'#B52F38');
s=slide('数据处理与指标','来源：项目nasdaq/analytics.py、nasdaq/providers.py。前复权价格变化不直接等同于经独立核验的分红再投资总回报。');body(s,['原始价格用于K线，前复权收盘价用于收益分析','校验代码身份、日期对齐、OHLC关系和文件哈希','构造累计收益、年化波动、回撤与相关性','保留缺失记录，不以零收益或模拟价格补齐']);
s=slide('系统结构与技术实现','实现见app.py、nasdaq/query.py、nasdaq/query_engine.py；需求见docs/requirements.md。');body(s,['数据层：公开接口、本地缓存和来源清单','计算层：Pandas指标处理与scikit-learn聚类','交互层：Streamlit页面与Plotly交互图表','问数层：规则解析、参数验证和统一计算模块']);
s=slide('样本区间收益排名','来源：submission/分析结果/样本指标.csv。单位为调整后价格收益。取63个完整样本中的前5名，非全市场排名。');chart(s,'bar',facts.top_symbols,facts.top_returns,'2023—2025年样本收益前五名');text(s,'收益排名需结合波动和回撤解读，不能直接作为投资建议。',68,590,1130,55,23,'#687182');
s=slide('收益与风险的不同维度','来源：同一63个完整样本计算结果。三个数值均是横截面中位数，不代表某只股票或组合收益。');body(s,[`区间收益中位数 ${(facts.median_return*100).toFixed(2)}%`,`年化波动中位数 ${(facts.median_vol*100).toFixed(2)}%`,`最大回撤中位数 ${(facts.median_drawdown*100).toFixed(2)}%`]);text(s,'收益与最大回撤使用窗口内复权价格，波动按252交易日年化。',68,570,1130,70,23,'#687182');
s=slide('聚类模型与K值选择','来源：submission/分析结果/K值比较.csv。输入为收益、波动率和最大回撤，经StandardScaler标准化，KMeans(random_state=42,n_init=20)。');chart(s,'line',facts.k_values.map(String),facts.scores,'不同K值的轮廓系数','0.000');text(s,`K=${facts.best_k}的轮廓系数最高，为${facts.best_score.toFixed(3)}。分组用于历史描述，不预测未来走势。`,68,590,1130,60,23,'#687182');
s=slide('聚类结果的解释边界','来源：submission/分析结果/聚类结果.csv。聚类编号无大小顺序，标签不能直接理解成评级。');chart(s,'bar',Object.keys(facts.cluster_counts),Object.values(facts.cluster_counts),'最优候选模型各组证券数量','0');text(s,'标准化减少尺度差异，不能消除偏态和离群点的影响。',68,590,1130,60,23,'#687182');
s=slide('自然语言问数演示','现场输入示例并展示解析条件、实际日期和排除样本。相对时间锚定侧栏结束日，而不是当前系统日期。');body(s,['与苹果近一年相关性最高的前5只股票','比较苹果和微软近三个月的波动率','近三个月最大回撤最小的前5只股票']);text(s,'结果包含图表、数值解释、条件明细与CSV下载。',68,570,1130,65,24,'#B52F38');
s=slide('测试与复现','测试命令见README，自动化测试覆盖40项。最终运行结果以验收记录为准。');body(s,['40项测试覆盖数据质量、公式、时间解析和页面状态','浏览器验证五个页面、实际问数和结果下载','桌面与窄屏检查，折线悬浮框采用浅色高对比样式','提交包包含真实缓存，安装依赖后可离线演示']);
s=slide('结论与改进方向','最终研究范围为63个完整历史证券样本。未完成的指数全量行情和大模型理解层不属于当前已实现事实。');body(s,['形成采集、处理、建模、图表和问数的完整流程','样本分析可复现，数据局限和计算口径明确披露','后续补齐未覆盖历史，并引入独立交易日历核对','逐步扩展语言理解，继续保留确定性的数值计算']);
const candidate=path.join(build,'coursework-draft.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
try { for(let i=0;i<p.slides.items.length;i++){const image=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));} }catch(e){console.log('Native rendering needed:',e.message);}
const skill=process.env.PRESENTATION_SKILL;
if(!skill)throw new Error('Set PRESENTATION_SKILL to the bundled presentation skill directory');
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'submission/202400702062-李晴-项目汇报.pptx'),pythonExecutable:process.env.ARTIFACT_PYTHON,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000'],fontPolicy:{basis:'design',families:['Microsoft YaHei']},requiredNativeChartOwnerSlides:[6,8,9],materializeLiteralChartWorkbooks:true,verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});console.log(result);
