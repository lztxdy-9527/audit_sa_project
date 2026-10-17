# TASK-028-R2 独立验收：通过

日期：2026-10-15。技术结论 **ACCEPTED**，TASK-028、R1、R2 可由人类关闭。架构端本轮未修改生产实现、测试或指南，未调用子 Agent、未操作看板。本结论不批准任何批次。

证据根：`data/reviews/task028_r2_gpt_20261015_211252/`。本次独立复验关闭 REVIEW_TASK_028_R1.md 中四组残余；下一任务为只读 Gate2 候审请求。

## 1. 接受的文件身份

- `scripts/runtime_gate1.py`：155899 B，SHA-256 `cf7f526ae3b6c222b3c0663a8473e9231e3ebcd7091e025d27ebcb238ec7346a`。
- `tests/test_runtime_approved_load.py`：69067 B，`48794abb496035732c8af8e96c153d80eaa832c9394a70dddf49cf46daa7a120`。
- `docs/RUNTIME_APPROVED_LOAD_GUIDE.md`：16276 B，`5941017f45b7d99640471032616220f7ffd47434e035d67537b583da02317357`。
- `docs/EXEC_REPORT_028_R2.md`：7651 B，`062667ade972028f285539abd5e0e9b96b33f46f7a7072ed24b4b6f56f0d64b1`。

四件均与 delivery.json 和本轮实读一致。旧五公开函数 AST 与 R1 保全起点相等；公共接口、开发宿主和冻结核心未变。辅助函数的修正属于本次允许范围，不据此宣称整文件未变。

## 2. 生产残余的独立实测

`verify_current.py` 建立本轮新登记/夹具事件/装载，真实 normalizer、loader 各一次；inspect 只读成功，四表实际行数为 2/1/3/3。12 个隔离反例均定位拒绝：最后必要消费后 DB/context/快照变更，started 批次与 artifacts 两项身份错误，数据库大小同值 float，失败 round_trip_exact，实际删除 allocations 后同步直接外层 SHA，normalized 输入绑定错误与未知键并同步依赖摘要，以及 net_checks=false。反例使用本轮自建产物，坏候选另存；未覆盖旧现场。

`probe_run_boundaries.py` 三个独立新场景证明：

- started 真实 writer 返回后事件 context 加 LF，本次在计算前拒绝：normalizer/loader 增量 0/0。
- normalized 真实 writer 返回后事件 context 加 LF，本次在第二核心前拒绝：增量 1/0。
- load_report 真实 writer 返回后改落盘 round_trip_exact，核心返回仍 true，本次拒绝且保留失败现场：增量 1/1。

因此核心前复确认已包含事件八文件；较晚 report capture 不再覆盖本次 writer 缓冲预期。原先自比式末端检查未重新引入。

`probe_errors.py` 验证 mkdir 真实 OSError 的映射与现场；两个实际模块的 Blocked 类型各携带两项原始 reasons，API 与磁盘诊断均保留原因；failure 版本、reason、field、cause_chain 非法形状均定位拒绝，无原生消费异常。受控核心异常明确作为映射测试，不称核心发现了业务问题。

## 3. 实际 CLI 末端与观察证据

`run_cli_controls.py` 启动四个新进程，调用测试 actual main 的 replay 分支；复用已保存观察，不重复业务链：

- normal：0 / PASS / 空 failures。
- 真实 audit_candidate 返回后台账加 LF：1 / FAIL / 非空 failures。
- 同一实际消费边界后 checks 加 LF：1 / FAIL / 非空 failures。
- 候选返回值替换：1 / FAIL / 非空 failures。

每例源证据字节不变；读取观察确认末次原始字节循环覆盖六证据、audit_failure 与 file_ledger，之后无候选读取。CLI 返回由内容/字节审核实际支配。

`verify_observer.py` 经当前真实观察器调用 normalizer，真实返回后、API 收尾前改同一 quality_report 引用；前两时点一致、第三时点检出，正式 audit_candidate 拒绝 core_input_changed。该负向控制单列，不放入正向通过集合。

`delivery_evidence_audit.json` 独立读取执行端最终容器：47 条 API、6 条正向核心载荷及 41 条检查与写盘前冻结观察 canonical 相等；核心三时点引用/快照指纹自洽，七份台账条目逐文件长度/SHA 一致。完整套件未由架构端重跑；“41 项通过”属于读取并核对的执行端证据。

本轮架构端实际新增：**56 条直接公开 API 记录、normalizer 5 次、loader 2 次、四个 CLI 进程**。API 内部 prepare/P1/store 为嵌套调用，不混入直接 API 计数；replay 中的 47/6/41 是旧观察数量，不称本轮真实核心调用。未重跑原 42、R1 31、R2 41 或 TASK-002—027 历史入口，未重新接收批次。

## 4. 保护、历史事实与范围

本轮最终一次完整保护比较见同根 `protection_result.json`，基线为 `task028_r1_gpt_20261015_185902/source_hashes_after.json`（162842 项，SHA `ff2c2c4e07b44b509adfe3c6476d8215a583f79628afac094199e7db3d3ce81d`）。仅三件允许文件变化；范围外变化/新增、新缺失、读取错误及交付产物漂移均须为零，才发布本次 ACCEPTED 的 review_result.json。新增按确切路径登记，无目录前缀豁免。末次全树扫描后仅有限登记本轮评审元数据，不再次遍历。

139 项历史证据损失继续单列；27 项精确恢复、R5 326 项越界现场和 R1 19 项命名偏差保持原身份，不追认、不清理、不重建。当前基线 missing=0 不代表历史损失为零。

TASK-028 的已批准装载接线与只读恢复至此通过。`RT_NORMALIZED` 只说明本层完成；合成夹具 APPROVE 不形成真实批准，开发宿主仍为 0008，真实批准 null、next/AI=false，真实独立初判仍未保存。

下一步仅 `docs/tasks/TASK-029_DRAFT.md`，由 GPT 执行端实施，架构端独立验收。看板清单补注属流程工作，无需为勾选重建业务链。
