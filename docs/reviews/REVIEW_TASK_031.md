# TASK-031 独立验收：通过

日期：2026-10-16。技术结论 **ACCEPTED**，以同轮 review_result.json 的最终保护确认发布为准。架构端没有修改生产代码、交付测试或指南，没有调用子 Agent、没有操作看板；本结论不批准任何真实批次。

评审证据根：`data/reviews/task031_gpt_20261016_021424/`。

## 1. 实读交付身份与范围

- `scripts/runtime_gate1.py`：213659 B，SHA-256 `540cb273f2b57aa9da1cf57438c9765a0b4346e66db1a46cdd4193f24a9fd609`。
- `tests/test_runtime_approved_screen.py`：23173 B，`5e4f014477ac55cf16166a2eca95d14f79e2a168f6f9d62520ad24389be28440`。
- `docs/RUNTIME_APPROVED_SCREEN_GUIDE.md`：7308 B，`fe0912afbe2bf3a8e1c58f9a1dd1aa19c6fc978a91b984d01c6dc27621efbdf6`。
- `docs/EXEC_REPORT_031.md`：11585 B，`a3801084b47817bf1e5068621910c5600677dd3038770ab7d75e3700b9187fa3`。

全部与执行端 delivery.json 逐项一致。对比 TASK-030 字节备份的 AST，旧定义仅 `_call_frozen_entry` 和 `_prepare_runtime_gate2_captured` 作必要复用；原十个公开 API 签名保持，新增两个筛查 API，没有同名重复定义。冻结 SQL 核心、P1/store/准备器、契约/登记、配置、旧测试/指南和开发宿主不改。

## 2. 独立实测与核心边界

架构端只建立一条当前版本 C06b 新运行链，真实 SQL 核心恰调用一次。新报告 R01/R02/R03/R04 为 0/1/0/0，R02 超额 400000 分；完整真实返回 canonical+单 LF 与保存报告逐字节相等，数据库核心前后 SHA 相同。同一真实 load_report 引用在调用前、返回后、所属 API 收尾三时点指纹相同。

正常 run 与只读 inspect 返回规范相等：成功六键、报告目录三文件、八项边界严格 false。公开 inspect 在写盘/网络/子进程守卫下成功，规则核心、标准化、装载、store.save 增量均为 0。

独立反例：

- 包装真实 Gate2 verify，在其返回后追加本轮数据库 LF：本次 run 阻断，SQL 增量 0，筛查目录尚未创建。坏字节另存，仅恢复本轮原件。
- 先无注入观察最后语义核对字段 `screen.artifacts`，真实 helper 返回后追加报告 LF：本次 inspect 在 `screen.screening_report.json` 拒绝；撤销 wrapper 后保留坏字节仍拒绝；保全坏字节、只恢复本轮原件后成功，未写 failure。
- 分别把 database_unchanged 改整数 1、R02 计数改同值浮点 1.0、SQL SHA 改全零，并同步外层报告文件 SHA 与对象指纹：均由协议/关系核验定位拒绝，键值没有被 Python 等值比较放过，inspect 保持只读。
- 重复运行因已有输出目录拒绝。执行端保留的半写 artifacts 现场由本轮只读 inspect 复验，优先传播有效 failure 的 Error，不被半写 JSON 遮蔽。

本轮共 20 条直接 API 完整记录（18 条初始脚本、2 条剩余检查），26 条 P1 核验/保存观察和 1 条 SQL 观察；P1 调用数含上游准备与只读核验，不混称新决定保存。初始脚本末项曾错误预期旧 HOLD 场景直接到达 decision 拒绝，但该场景已有执行端故意保留的 Gate2 锁，实际正确地先拒绝 gate2_lock。脚本非零记录保留；没有修改旧锁或重建旧场景，余下只读核验由 complete_review.py 接续完成。HOLD 在无锁时的特定拒绝引用执行端已保存观察，不宣称本轮重新实测。

## 3. 执行证据与实际 CLI

有限实读审核执行端 task031_run_01：21 条检查全 true；45 条记录（43 直接 API、2 映射 helper）和 187 条嵌套观察与写盘前定稿 expected_observations 的完整 canonical 内容一致，ID 唯一、父调用闭合；7 项文件台账的长度/SHA 均正确。三次 SQL 返回与数据库前后读数一致；17 个 screen/inspect 窗口无标准化、装载、store.save 调用，5 个 inspect 的 SQL 增量 0。

独立四个新进程走实际 main/replay：normal=0/PASS/空 failures；真实 audit_candidate 返回后台账 LF=1/FAIL；同边界 checks LF=1/FAIL；返回载荷替换=1/FAIL。最后八文件原始字节确认后没有继续读取候选生成成功，replay 来源字节未变；其 45/187 是旧观察，新增业务调用为 0。

真实 artifacts 独占句柄半写、报告 writer 返回后改字节及两类核心异常映射，引用已核对的执行端当前证据；架构端未重跑这些业务场景。异常映射是受控 helper 验证，不描述为 SQL 自己发现业务错误。没有重跑完整 21 项或任何历史大套件。

## 4. 最终保护与后续

本轮一次最终完整扫描比较 TASK-030 ACCEPTED 基线（164607 项，SHA `030f013f3b13104893e69e88666a7cf623419426995dda264c138494440d5c65`）。保护结果与新接受快照见本轮 protection_result.json/source_hashes_after.json/review_result.json。仅 runtime_gate1.py 可作为既有变化；范围外变化/新增、新 missing、读取错误、执行交付漂移必须为 0 才发布接受结论。最后只有限登记明确的评审元数据，无目录前缀豁免。

139 项历史损失、27 项恢复、326 项越界、19 项命名偏差及 TASK-030 的具名锁目录偏差均继续保留；历史损失不记作本轮新增缺失，技术通过不追认历史偏差。

本层停在 RT_RULE_SCREEN_RECORDED。线索不是审计结论；真实批准 null，开发宿主 0008，next/AI=false。下一卡 `docs/tasks/TASK-032_DRAFT.md` 仅接冻结独立复算和只读恢复，不接事实底稿、真实初判或 AI。看板关闭由人类办理。
