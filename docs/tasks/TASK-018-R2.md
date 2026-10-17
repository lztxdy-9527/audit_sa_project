# TASK-018-R2：批次ID字符串类型定点修正

日期：2026-10-13。依据 `docs/reviews/REVIEW_TASK_018_R1.md`。原B1/B2/E1已由GPT复验关闭，只修新增B3，不推进TASK-019。

## 1. 允许范围

仅允许修改：

- `scripts/export_demo_review_bundle.py`，起点 `7b78eefca18916c44d9dbc12f73bf480308fa3717b3bb0fc2ce02f67995788a5`。
- `tests/test_export_demo_review_bundle.py`，起点 `99370503d3904c5f3a1e950e8a03eb7230c05fb473cea5ce58b1380f078ab9bc`。

只新增 `docs/EXEC_REPORT_018_R2.md`、全新 `data/review_bundle_tests/task018r2_<唯一>/` 与 `data/review_bundles/task018r2_<唯一>/`。指南冻结（`9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7`），其他所有旧文件/现场、本卡/旧卡/回执/评审、宿主/控制器/全部核心/SQL/测试冻结。不安装依赖、不初始化Git、不迁移/补签/覆盖/删除历史。

只读源仍为 `data/batches/task018_run_06/c06b` 与宿主推导的既有外置DB；不新建batches/SQLite、不重建上游链、不改源文件。

保护基线 `data/reviews/task018_r1_gpt_20261013_144137/source_hashes_after.json`，身份见同目录review_result.json；它冻结当前未通过交付。changed只允许上述两个文件，missing=[]、读取错误0；一次完整扫描复用，再有限刷新本轮新增产物，禁止第二次全树扫描。

## 2. 唯一实现修正B3

当前source_batch.batch_id检查是“不是64位哈希”，会同时造成两种错误：`[]`通过形状检查后在distinct set处抛原生TypeError（公开API异常类型/字段错误、CLI2）；64位十六进制字符串却被误拒。批次ID是原字符串身份，不能用SHA格式排除合法文本。

- `_verify_manifest_shape`对source_batch.batch_id使用明确非空字符串检查；不因其内容像哈希而拒绝。必要时消除同一处身份字符串检查中相同的错误排除，保持实际宿主版本/批次的精确一致性要求。
- 在十处batch_ids构造distinct集合或进行等值比较**之前**逐项确认ID为非空字符串；非字符串/空值应抛DevReviewBundleBlocked并给准确字段路径。使用现有_require或小型直接检查，不建通用校验框架。
- 不strip、截断、转大小写、转成数字或把非字符串强制str；保留原字符串后精确比较。所有来源/文件/对象SHA字段仍要求完整64位小写十六进制，不能放宽哈希helper来绕过ID问题。
- 不全局捕获TypeError/AttributeError后一概改成Blocked，避免掩盖程序错误。无需全面重写verify、接新框架、修改I/O/writer、末尾字节确认、来源映射或身份算法。

这不是业务范围/批准变更；不涉及真实判断、身份认证、正式契约或Gate。

## 3. 最小定点验证

新增 `--only r2`，成功返回前实际执行本模式证据/保护收尾。**不运行R1六组、旧七组、smoke、writer故障、源晚变更、MAIN/零条、上游或历史入口。**

1. **一个正常包对照**：最终工具真实export一次、verify一次，复用§1只读源；25文件/24 payload、22份源字节/初始绑定一致，正常verify及新进程CLI0，C06b1条R02、判断原文/开发边界不变。入口开始前取得源37文件及DB哈希，全部定点结束后比较；不要在收尾才取一份缓存与自己比较。无0009。
2. **协议类型反例**：只在该正常包的隔离副本中，分别只改manifest.source_batch.batch_id为 `[]`、`{}`、`null`、整数、布尔（至多这5例，不穷举协议）；payload/哈希/25固定文件/24清单不变。每个公开verify均DevReviewBundleBlocked/字段精确，不得原生TypeError或Error2；数组反例另用新进程CLI确认退出1。verify只读、不写failure，正常包不变。保存每个完整实际异常/traceback/原因链/字段与对应候选manifest身份。
3. **合法字符串形状**：复制正常manifest到内存，把其中两个批次声明同设为64位小写十六进制字符串，直接调用实际shape helper必须通过；保留该字符串原样，不把它当SHA要求或禁止值。再保留普通ID及前导零字符串的有限对照。清楚标注“shape helper对照”，不是完整包改绑成功、真实批次运行或公开API。不要为此构造/重签整条工作流或新建64字符批次。
4. **证据/只读/保护收尾**：所有实际工具API/CLI与helper对照分列登记，保留完整返回/异常及原文；真实观察工具内部宿主status与六个核心守卫，未观察的子进程次数为null。registry与记录双向、文件台账实读SHA、严格单删登记的隔离自测、正确本轮保护和停止点纳入正式failures，missing/unregistered不能默认零。必要收尾复用现有小helper；不为统计补跑正常包或上游链。

最终定点使用全新容器一次运行；局部错误定点修正并保留过程现场。R1的manifest探针偏早已由GPT在实际最后来源消费点补证关闭；本卡不再重跑晚变更。B1/B2/E1及原真实writer已有证据均明确引用、未重跑。

## 4. 交付与停止

新回执给两个修改文件及自身交接用完整SHA、实际定点命令/退出、正常对照/非法类型/合法字符串shape证明、实际API/CLI/helper/嵌套调用scope、完整证据与failures、源/DB/正常包字节保护、一次保护扫描/基线身份、过程失败及未执行项。列两个新数据根与只读源/DB绝对路径。自身SHA只在交接给出，不写回自身。

完成后停止本卡实施，交GPT整体验收；不做TASK-019/0009，不开放AI/LLM/网络/UI/ERP，不保存真实人类初判或批准，不建立正式契约/真实Gate。GPT通过后继续制定下一卡，DSH由人类操作。
