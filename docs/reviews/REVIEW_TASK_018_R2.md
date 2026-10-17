# TASK-018-R2验收及TASK-018整体关闭记录

日期：2026-10-13；验收端：GPT。

结论：**通过。TASK-018、TASK-018-R1、TASK-018-R2整体验收完成，可由人类在DSH关闭三卡。** B3已独立复验关闭，与R1已关闭的B1/B2/E1合并接受。下一卡为 `docs/tasks/TASK-019_DRAFT.md`，只形成候选契约和人类审定材料。GPT未修改实现或冻结文件，未操作GUI或关闭卡片。

验收限开发态审阅包导出和COPIED_BYTES_ONLY离线核验。宿主仍停0008、phase=DEV_GATE2_APPROVED、真实批准null、next=false、AI不允许；真实人类独立初判尚未保存，正式契约/真实Gate/后置AI/终判尚未建立或批准。

## 1. 最终交付身份

GPT实读SHA-256与交接一致，复验前后不变：

- 工具 `scripts/export_demo_review_bundle.py`：`0b2f7b288cc49327a124a6defad5b1d9ddd09856d6c907b6120536d932e32577`。
- 测试 `tests/test_export_demo_review_bundle.py`：`042b20e33a37577a9c2c69050b4d34ca082dbfa862f9e061a54a3b0eeeb78fcf`。
- R2回执 `docs/EXEC_REPORT_018_R2.md`：`1ace3ec436568a1d292399084b510bf99718c51d08f0cabb52b480bb3b286ef3`。
- 指南保持冻结：`9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7`。

宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`、控制器/全部纯核心/旧测试/历史现场保持冻结，见本轮保护结果及selected_hashes。

## 2. 实际复验和证据层级

执行端最终task018r2_run_02自报4/4 PASS。GPT读取并独立重读21个API/helper/CLI文件引用、21行文件台账、registry双向对应、完整异常/traceback/链及严格单删一条registry的隔离自测，均有效。

GPT另经 `data/reviews/task018_r2_gpt_20261013_151052/run_review.py` 实际执行交付 `--only r2` 一次，新容器 `data/review_bundle_tests/task018_r2_gpt_20261013_151052`，**退出0、4/4 PASS、failures=[]**；该新容器的21个引用也经独立实读核对。

独立profile绑定交付测试实际使用的模块代码帧：公开API **8次**（工具7、直接宿主1）、显式shape helper **9次**、工具CLI **2次**；真实宿主status **3帧**（直接1、工具嵌套2），六个真实下游核心 **0帧**。每个公开/helper调用与实际登记标签对应；不把嵌套次数与API条数等同。子进程核心未观察，记null。

四个合法字符串helper的实际入参及五个非法类型helper的实际入参在调用前后规范指纹不变，证据actual_code_frames.json；这些是shape对照，不是完整包改绑或新批次运行。GPT未运行R1六组、默认七组、smoke、writer/源晚变更、MAIN/零条、上游或历史入口。

## 3. B3关闭

source_batch.batch_id已明确检查非空字符串，host_version同类身份字符串错误排除也已去除。十处批次身份在构造distinct集合/比较之前逐字段验证类型；不strip/截断/大小写或数字转换，不强制str，不新增全局TypeError/AttributeError捕获。真正SHA字段的完整64位小写十六进制要求保持。

五个候选仅在本轮正常包隔离副本中改manifest.source_batch.batch_id为[]、{}、null、7、True，25文件/24清单及payload字节/哈希不变。实际公开verify均 **DevReviewBundleBlocked**，field精确为manifest.json.source_batch.batch_id；数组新进程CLI退出 **1**，不再是原生TypeError/运行失败2，verify不写failure或其他文件。

普通ID c06b、前导零0abc123、64个a及64个0的实际shape helper调用均通过、字符串原样保留。未创建64字符批次、未重签工作流，也未把helper通过称为整个包成功。

正常真实export、公开verify及新进程CLI通过，25文件/24 payload、22复制件/初始绑定一致，C06b1条R02、模拟判断原文和开发边界保持。GPT独立入口前取得原37文件和DB哈希，全部定点后完全一致；正常包未被类型反例修改。无新batches/SQLite、无0009。

## 4. 保护与合并验收

实际入口执行一次完整扫描，基线132537项、实扫 **133231文件**；changed恰为获准工具和本任务测试，missing=[]、unexpected=[]、读取错误0，六件重点冻结哈希一致。扫描字典从实际保护函数返回帧保存为current_scan.json，后续只有限刷新本轮新增产物/文档，没有重复扫描全项目。

新增路径也与执行端获准证据/导出根、回执及GPT本轮审阅根核对，无未授权新增实施产物。辅助路径筛选首次漏列GPT自有测试/导出根及前一基线的两个自排除元数据文件，已修正筛选范围并复用同一scan；没有据此误拒、重建业务链或重跑扫描。最终结果见new_path_audit.json。

合并证据范围：

- 原TASK-018正常导出/确定性、路径/前提、来源晚变更、真实writer半写/完整后sentinel、离线反例及只读边界的既有证据见REVIEW_TASK_018.md。
- R1的B1/B2/E1实际复验见REVIEW_TASK_018_R1.md，包括GPT在真实最后来源消费之后补测manifest变更并正确拒绝。R1原manifest探针偏早已由该补证关闭，不再次要求执行端重跑。
- 本轮只修身份字符串类型；B3由本轮四组定点关闭。writer方法及B1/B2/E1本轮未重跑，属于已有证据合并，不声称GPT新跑了六组/七组或writer故障。

当前足以接受既定只读导出/离线包内一致性范围；不把这个范围扩展为完整批次备份、可恢复宿主、来源真实性、人类身份认证或独立审计保证。

## 5. 下一卡与人类交接

最新source_hashes_after.json及文件哈希/项数/排除项在review_result.json登记，作为TASK-019冻结基线，不是Git恢复点。TASK-019只新增候选契约、业务决策包、分阶段接入方案与回执/只读核验记录；当前正式契约、运行绑定、批准字段、真实初判和AI许可均不变。

待候选内容具体可审后，由人类明确决定是否采纳契约、是否允许建设真实人工决策保存模式、初判粒度。技术验收和DSH关卡不代替这些业务决定，更不批准任何批次。本轮未代填、保存或批准真实判断；DSH三卡由人类关闭。
