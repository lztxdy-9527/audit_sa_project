# TASK-013-R3：只修测试证据，宿主冻结

## 给新 DeepSeek 对话的最小交接

你是执行端，GPT 是架构与验收端，人类是桥梁。本项目是模拟 ERP 采购付款筛查；金额整数分，R01—R04 仅输出待核实线索。当前宿主已经实际接收、模拟两个 Gate 决定、标准化、SQLite 装载和筛查，停在 DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED（0005）。真实批准恒 0，未执行独立复算、底稿、人类判断或 AI，不能推进 TASK-014。

工作目录：`D:\harness work\audit_sa_project`。用项目 `.venv\Scripts\python.exe -B`；不装依赖、不初始化 Git、不修改历史产物、不清理项目外文件。

先读本卡、`docs/reviews/REVIEW_TASK_013_R2.md`、`docs/EXEC_REPORT_013_R2.md`、`docs/WORKFLOW_HOST_GUIDE.md`；按需查 `docs/SPEC_V1.md`。实现以当前文件为准，不需要粘贴全部对话历史。GPT 已独立证实宿主七阶段恢复及三个真正末次读取变更均通过，本轮不得重新设计或修改宿主。

## 唯一修改范围

只修改既有 `tests/test_screen_demo_workflow.py`；只新增 `docs/EXEC_REPORT_013_R3.md` 和本轮全新测试/批次/SQLite/临时验证容器。宿主和指南冻结：

- `scripts/run_demo_workflow.py`：`ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2`，实现 TASK-013-workflow-host-1.2。
- `docs/WORKFLOW_HOST_GUIDE.md`：`c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5`。
- 测试起点：`e7851240930461486010f68012a497d2ff7b34d34f0633b3185e27c6b17756e3`。
- 主保护基线：`data/reviews/task013_r2_20261012_080320/source_hashes_after.json`。该基线只允许测试 1 项变化、缺失 0；冻结上游、三个旧测试及历史产物不动。更早基线按历史授权累计，不把累计变更误写为 0。

若真实宿主缺陷阻止本卡，保存具体复现并停在受影响部分，不擅自改宿主或放宽断言。

## F01：让三项回归命中真实末次消费

对 status 的报告 / load_report / 0001 三项探针：真实 `_read_screen_outputs` 返回原始对象后，在状态摘要的最后一次读取边界才修改磁盘一次。当前宿主成功路径会读取两次；第一次是恢复链核验，第二次才是末次摘要消费。记录全部读取进入/返回与控制器返回顺序，断言注入命中 1、确实经过第二次读取、注入后无额外控制器调用，也没有新的报告读取。不得仍以 `hits==0` 在第一次读取注入并声称末次。

报告项修改 findings 内容（保留可解析 JSON）；其余两项可以加换行。每项必须：本次公开 API 得到目标路径的 WorkflowHostBlocked；撤销 wrapper、保留变更后新进程 CLI 退出 1；恢复本轮原件后 CLI 退出 0。未变化对照正常。

增加纯内存的时点判定自测：只出现第一次读取、缺少注入或注入后还有读取/控制器调用，均不得被判成合格末次探针。自测单列，不污染正式 failures。

## F02：真实 after 时点与完整调用记录

1. 调用前保存原始字节和 before 文件/目录哈希；调用结束且 wrapper 撤销后，**恢复原件之前**保存 after 文件/目录哈希。逐项断言 after.file 等于 after.tree 中同一文件的哈希、before/after 的目标哈希不同。撤销后的 CLI、恢复后集合与正向结果另存，不混作 after。
2. 补齐三个新 F02 及既有 `g6_tail_0005_change`、`g6_f01_report_tail_change`：真实公开入口名称、完整 args/kwargs/batch_dir（有决定则完整决定）、预期类别及目标原因、完整返回或异常类别/消息/逐帧 traceback/cause、命中数、真实调用顺序、真实 before/after、撤销后 CLI 与成功对照。大对象可以独立文件引用，必须给相对路径与实际字节 SHA-256；摘要引用探针记录也给实际字节哈希。不截断异常消息。
3. 原 G6 的早期 `_verify_screen_tail` 探针如保留，准确标作早期守卫；不能替代 F01 的真正末次读取探针。保留原有断言和故障方向。
4. 筛查失败现场的 failure.json 保留；需要成功对照时使用新的干净小样，不删除诊断、不追认失败运行成功。

## F03：七阶段完整判定

七阶段全部保存实际 API/CLI 返回、调用实参，以及 before/after 文件哈希集合（允许文件引用+字节哈希）。从实际 current_checkpoint 的 workflow.state 读取两项真实批准，要求均为 null；不得用顶层默认 `n/a` 代替。

对 API 与 CLI 两侧都断言实际 phase、next_step_allowed=false、以下动作允许值和只读性：

- Gate1 pending：NORMALIZE_AND_LOAD=false；SCREEN_AND_BUILD_FACTS=false。
- Gate1 approved：true / false。
- Gate2 pending：false / false。
- Gate2 approved：false / true。
- Gate2 held 与 rejected：false / false。
- screened：false / true，另有 RULE_SCREEN_RECORDED 凭证，phase 仍 DEV_GATE2_APPROVED。

计数从入口事件和实际调用记录导出；新增 helper 进入公开 API 也计入。进程内 normalize/load 若为 0，记录明确的 0；CLI 内未观测仍用 null，与推导分列。不要照抄旧轮总数。

## 控制耗时与验收

G10 新增七阶段与三个末次读取探针改用现有 C06b 小样；MAIN 业务基准及原有业务回归保留。先编译源文本、做定向小样验证，修好测试收集器后，再用全新容器运行一次最终完整入口。失败先定位对应小项，避免每次文字/收集器修改都从 MAIN 重跑全部场景。可以在本轮容器内新增临时验证脚本；不能修改生产 API/CLI 或历史文件。

回执报告实际命令/退出码、三项修复与具体证据、完整文件哈希、三条完整产物路径、计数、自测与保护比较；如实记录失败尝试和未运行项。保留 G1—G9、MAIN 12 条与 1,600,000 分、writer 完整文本/40 字节/异常链/旧 checkpoint 不变、接收登记双向审计、来源/退款/缺失关联等原断言。新增检查数量按实际导出。

完成后停住：不得新增 0006、不得运行独立复算/事实底稿/AI、不得填写人类判断、不得提交真实 Gate 或正式契约、不得推进 TASK-014。返回回执和三条产物路径，交 GPT 验收。
