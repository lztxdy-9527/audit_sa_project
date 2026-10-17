# TASK-014-R2 验收记录

日期：2026-10-12；验收端：GPT。

结论：**通过；关闭 TASK-014 及其 R1/R2 修正的实施验收。** R1-B2-E 与 R1-B3 剩余阻断已关闭，不再开启 R3。人类可据此在 DSH 关闭三张对应卡片。本结论不构成真实 Gate 批准、审计结论或项目整体完成，不推进 TASK-015。

## 1. 交付身份

实测哈希均与交接一致，GPT 定点复验前后未变，详见 `data/reviews/task014_r2_gpt_20261012_225658/source_hashes_before_selected.json` 和 `source_hashes_after_selected.json`。

- 冻结宿主：`8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7`。
- 本任务测试：`f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43`。
- 指南：`5ce64aee26986a1ace88ac5ef64a016799077ff10ac0d1d933c87fc455bdbb68`。
- R2 回执：`dd823b4148d57f1ef2875f97d6415fdeee2c5197c8be55c359ebd191f59aa4bc`，10178 字节；不回写自身。
- 冻结复算核心：`8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`。
- TASK-013 测试：`27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`。

## 2. 证据层级与实际复验

执行端自报完整入口退出 0；GPT 读取 `task014r2_run_03/summary.json`，确认保存的是 11 项 PASS、failures=[]。**GPT 未重跑完整入口或 MAIN，也未运行 TASK-002—013 历史入口。**

GPT 实际使用项目 Python `-B` 执行本轮 `run_targeted.py`：调用交付入口 `--only g4`，该模式实际执行 B1/B2/B4 三项定点检查，退出 0、三项 PASS；用真实函数代码对象观察到 partial 与 throw 的目标 0006 均进入真实 `_write_exclusive_json` 各 1 次。partial 保持独占模式 x、LF 换行、实际句柄部分写入再抛 OSError，两种场景均恢复退出 2。

GPT 另建一份正常 C06b 批次，经公开 API 完整推进到 0006：真实冻结复算核心调用一次，输入在核心调用前、核心返回后和公开调用完成后三个时点指纹相同，保留的是同一对象引用；完整真实返回单份保存，与落盘报告严格规范 JSON 相等。0006 workflow 与 0005 相同，前序文件哈希正确，无 0007，真实批准 null，next_step_allowed=false。证据：`normal_c06b_readback.json`、`normal_c06b_api_records.json`、`actual_core_return.json`。

本轮 GPT 共直接执行公开宿主 API 11 次，宿主 CLI 22 次；真实 writer 的两次目标入口由直接观察计数。额外正常 C06b 的复算核心直接观察 1 次。未观测的 CLI 内部核心/控制器次数不推导为实测值。

## 3. 剩余阻断关闭

**R1-B2-E 关闭。** 交付 partial 已不再用替身重造 writer。独立读回两份待写文件：partial 76445 字节、throw 76375 字节，文件 SHA-256 与报告声明及真实缓冲哈希一致；partial 的现场字节精确等于待写缓冲前半段，throw 的完整 0006 与待写文件字节一致。原因链、crosscheck 阶段、恢复退出 2 和旧文件不变均有实际记录。

**R1-B3 关闭。** 输入 before 指纹现在位于真实核心调用之前，公开调用后使用保留的同一引用复核；完整核心返回已保存。造样公开 `screen_dev_batch` 经统一记录器登记，7 条 API 与权威登记表一致；异常文件是真实 traceback，不再是 NoneType: None。

GPT 独立读回核对全部交付文件台账引用及 receiver/checker 现场：76 条 CLI、7 条 API；11 份 receiver 命令/退出码与实际调用记录一致；11 次 receiver 内 checker 均有 argv、started=true、exit_code=0，report/stdout/stderr 的文件存在性和哈希均一致。直接 checker CLI 为 0 与下游实际 11 次分别陈述。

从交付现场独立导出总体：11 批次、8 份 MATCHED 报告、1 份 MISMATCH 报告、6 份可解析且无 failure 的成功凭证、3 份失败现场。与新总体字段一致；流程检查子集 4/4 单列，不把故障现场的 MATCHED 报告当作成功。

GPT 还执行了**交付源码中的实际审计 helper**，在内存审核副本中仅删除 `cli:b1_chain_start` 一条 registry 登记，文件台账保持完全不变：原副本审计为空，修改副本返回“调用未登记进权威登记表”。正式 helper 的失败结果已接入原入口 failures/非零判定路径；本轮未伪称运行过修改后的完整入口。真实日志与交付登记文件未变。证据：`single_registry_entry_isolation.json`、`delivery_evidence_audit.json`。

## 4. 保护与非阻断记录

GPT 当前树只扫描一次，118783 文件，复用两组比较：

- **R2 卡指定的正确基线** `task014_r1_gpt_20261012_221645/source_hashes_after.json` 共 117422 项：仅指南与本任务测试变化；宿主未变；missing=[]、unexpected_changes=[]。
- 原 TASK-013-R4 主基线共 115029 项：仅宿主与指南变化；missing=[]、unexpected_changes=[]。

完整结果为本轮 `protected_files_comparison.json`、`source_hashes_scan.json`。下一轮保护读数 `source_hashes_after.json` 由该扫描加本轮已知新增评审文件最终哈希组成，不是代码恢复点。

交付测试仍使用更早的 116059 项读数，回执却标作 R2 基线并解释宿主 changed。实际 R2 卡规定的是 117422 项读数；**本页已按正确基线完成独立比较，宿主没有变化**。登记为非阻断的基线引用/标注错误，不回写旧回执，不要求 R3。交付隔离自测同时删了关联的文件台账行与 registry 行；本轮补做的严格单项删除证明了正式审计性质，无需为该辅助记录再跑完整流程。

## 5. 当前停止点

已验收宿主链到 **0006**：`phase=DEV_GATE2_APPROVED`，`screening_status=RULE_SCREEN_RECORDED`，`crosscheck_status=RULE_CROSSCHECK_RECORDED`。0006 是复算完成凭证，未改变控制器 workflow，也不是整个 SCREEN_AND_BUILD_FACTS 完成。真实 gate1/gate2_approval 仍 null，next_step_allowed=false。

MAIN 的 12 条（3/5/2/2）及 R02 1,600,000 分本轮只读核对交付保存的筛查/完整核心返回/复算报告，不冒充 GPT 重跑。复算一致仅表示两套确定性计算在该输入下相符，不构成审计结论。

GPT 本轮未修改宿主、测试、指南、执行回执或历史产物；只新增独立证据和本验收记录。未执行事实底稿、AI、人类判断、正式契约、真实 Gate、0007 或 TASK-015。后续任务需另行确定，不在本轮派发。

独立证据：`D:\harness work\audit_sa_project\data\reviews\task014_r2_gpt_20261012_225658`。
定点容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task014r2_gpt_20261012_225658`。
批次父目录：`D:\harness work\audit_sa_project\data\batches\task014r2_gpt_20261012_225658`。
数据库父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014r2_gpt_20261012_225658`。

最终机器结论见本轮 `acceptance_summary.json`。
