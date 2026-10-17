# TASK-013 执行回执（只读 R01—R04 规则筛查接入开发批次）

任务：把只读规则筛查接入宿主开发批次，保存完整线索报告与 `0005` 完成凭证，新进程恢复后停住。
日期：2026-10-12。执行端：DeepSeek（子代理续做 M2—M6；M1 由同源实例完成）。
依据：`docs/tasks/TASK-013_DRAFT.md`、`docs/reviews/REVIEW_TASK_012_R2.md`、`docs/RULE_SCREEN_GUIDE.md`。

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 新增接口 | `screen_dev_batch(batch_dir) -> dict` 与 CLI **`screen-rules --batch-dir`**（CLI 现共 **6** 个子命令） |
| 真实动作 | 在合法 `0004 / DEV_GATE2_APPROVED` 批次上**真正调用一次**冻结 `screen_sqlite(<推导数据库路径>, load_report, cutoff_date="2026-09-30")`，独占保存 `started.json`／`screening_report.json`／`artifacts.json`／`0005.json`；新进程 `status` 只读复现，**不重新筛查** |
| `0005` 语义 | **宿主筛查完成凭证**，不是新的控制器批准或新阶段：完整 `workflow` 与 `0004` 严格相等、模拟决定恒 2 条、`gate1_approval`／`gate2_approval` 恒 `null`、`next_step_allowed=false`、真实批准 **0**；无 `0006` |
| 版本 | 实现版本 `TASK-013-workflow-host-1.0`；**既有** host-manifest／checkpoint／gate2-artifacts／gate2-failure 协议版本仍为 `TASK-012-*-1.0`（未盲目重命名）；新增筛查协议 `TASK-013-screen-start-1.0`／`TASK-013-screen-artifacts-1.0`／`TASK-013-screen-failure-1.0` |
| 验证 | 新入口 **8 组 + INTEGRITY + FINAL_ARTIFACT_READBACK 全部 PASS，failures=[]，退出 0**；容器 `task013_final_01` 内 `host.sha256` 与当前宿主一致（可复现） |
| 保护 | 主基线 `data/reviews/task012_r2_20261011_180955/source_hashes_after.json`（53983 项）**恰好 2 项变化**（宿主＋指南）、缺失 0；更早 `task012_r1` 累计 3 项、`task011_r2` 2 项；`task009_r2`(14691) 与 13330／12546／10236／8547／6511／4902／874 **全 0 变化 0 缺失** |
| 停止 | 停在 **`DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED`**；HOLD／REJECT 仍为停止态；未执行独立复算／事实底稿／AI、未建立契约、未签真实 Gate、未推进 TASK-014 |

## 2. 修改与新增文件（完整 SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py`（修改） | `2e54e1d76950b50d50a0d9ba5e11f969ab30d73099d721df8ef38608ab4577a4` |
| `docs\WORKFLOW_HOST_GUIDE.md`（修改） | `5d1e731944ba8ef0359d9496f4d86fc6bd3e8b7bf9c89e71f992c278c47603ab` |
| `tests\test_screen_demo_workflow.py`（新增） | `7a4d831c4e2aee51a601688df2e34e125bea939348f60fed1e3c970e42918105` |
| `docs\EXEC_REPORT_013.md`（新增，本文件） | — |

## 3. 三条完整产物路径

| 类型 | 路径 |
| --- | --- |
| 测试容器 | `D:\harness work\audit_sa_project\data\workflow_host_tests\task013_final_01`（203 文件；含 `summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`cli_logs/`／`entry_events.json`／`self_tests.json`） |
| 批次父目录 | `D:\harness work\audit_sa_project\data\batches\task013_final_01`（348 文件；MAIN 批次 `main_01`） |
| 外置数据库父目录 | `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task013_final_01`（14 文件） |

便于直接复验的 MAIN 关键路径：

- `data\batches\task013_final_01\main_01\workflow\screening\screening_report.json`（完整线索报告）
- `data\batches\task013_final_01\main_01\workflow\checkpoints\0005.json`（筛查完成凭证）
- `data\batches\task013_final_01\main_01\workflow\screening\artifacts.json`（报告文件字节哈希／对象指纹与前序引用）

## 4. 真实命令与退出码

```powershell
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"          # 0
& $py -B -c "src = open(r'...\tests\test_screen_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013_final_01'                                    # 0
```

```text
[PASS] G1_MAIN_FULL_FLOW / G2_SMALL_SAMPLES / G3_PRECONDITIONS_AND_REPEAT / G4_REPORT_AND_REFERENCE_TAMPERING
       G5_REAL_FAILURE_SCENES / G6_FINAL_TAIL_PROBES / G7_READONLY_AND_ISOLATION_GUARDS / G8_COUNT_AUDIT_AND_EVIDENCE
[PASS] INTEGRITY 受保护文件 13 个前后一致
[PASS] FINAL_ARTIFACT_READBACK
CLI 调用：start 15、status 16、record 14、prepare-gate2 14、record-gate2 13、screen 13
进程内公开 API 6（含 helper 进入的 status）；控制器重放 57；筛查核心（进程内可观测）4
接收 15、checker 15、副本 1、故障注入 12、模拟决定 27、真实批准 0
测试失败 0；受保护文件前后一致: True
全部预期成立。
```

## 5. MAIN 实测（§7.1）

- 报告 `findings` **12 条**，分布 **R01 3／R02 5／R03 2／R04 2**；`statistics.r02_overpayment_total_cents = 1 600 000`。
- `overall_reconciliation`：已结算付款主表 **267 949 329**、退款主表 **700 000**、资金净额 **267 249 329 = 已知应付关联 266 249 329 + 缺失应付关联 1 000 000**（分）；缺失关联未被误拦为质量阻断。
- 宿主保存的报告与该次**冻结核心真实返回**逐项严格相等（测试在同一进程内以同一 `load_report` 与数据库独立再调一次 `screen_sqlite` 比较）。
- 新进程 `status`：`screening_status=RULE_SCREEN_RECORDED`、`completed_actions` 含 `GATE1_SIMULATED_DECISION／NORMALIZE_AND_LOAD／GATE2_SIMULATED_DECISION／RULE_SCREEN`、报告引用与筛查时一致、**未再次调用筛查核心**；`real_approvals=0`、`next_step_allowed=false`。
- 筛查与 `status` 前后：数据库字节不变，`0001`—`0003`（以及筛查后的 `0004`）字节不变，旧产物一律未改。

## 6. 其余分组证据

| 组 | 关键事实 |
| --- | --- |
| G2 小样 | C03（合并付款）**无命中**且金额未翻倍；C07b（部分未匹配）保留 **R03** 线索且缺失关联净额非零；C06b（部分退款）退款净额与实体证据保留；三者都走真实全链并成功筛查 |
| G3 阶段与重复 | Gate1 pending／Gate2 pending／Gate2 **HELD**／Gate2 **REJECTED** 四种状态的 `screen-rules` 均退出 1，**拒绝时不创建 `screening/`**、拒绝前后字节不变，且**筛查核心调用为 0**；重复筛查退出 1 且**不新增 `0006`** |
| G4 报告与引用 | 5 个定向探针各命中目标字段：报告字节变化→`report_file_sha256`；`artifacts.json.report_file_sha256` 改零→目标字段；`0005.previous_file_sha256` 改零→前序哈希；`0005.workflow` 改动（同步 `state_sha256`）→冻结控制器历史校验；未知 `0006.json`→拒绝未知项。全部在**专用探针批次内造样并即时恢复原位**，恢复后 `status` 重新通过；另有整批副本对照：推导数据库路径不一致时退出 1（不冒称上游重算） |
| G5 真实失败 | ① `0005` 部分写入：真实 writer 捕获**完整待写 text**（`full_utf8_bytes` 记为真实字节数）、opens／writes／raises 各 1、部分文件 < 完整字节数、`__cause__` 为 sentinel `OSError`、`0001`—`0004` 调用前后字节相同、failure.json 落盘、后续 `status` 非 0；② 完整 `0005` 后抛错：原命令失败但 `0005` 落盘、`failure.json` 保存、新进程 `status` **退出 2 并复现 sentinel 原因**（失败记录优先于完整 `0005`）；③ 非法 `failure.json`（造样后即时恢复）→**协议阻断退出 1** |
| G6 最终复测 | 三个探针在**最后一次动作检查真实返回之后**改变现场：筛查提交入口改 `0005`→本次 `screen_dev_batch` 即拒绝（指向 `workflow/checkpoints/0005.json` 与初始读取／实际哈希）；`status` 入口改数据库→本次 `status` 即拒绝（指向数据库字节）；`status` 入口改输入快照→本次 `status` 即拒绝（混合读取守卫）。各命中 1、before≠after、撤销 wrapper 后新进程仍拒绝；未变化的正向批次（G1／G2／G7）全部正常通过 |
| G7 只读与隔离 | 守卫下 `status` **不启子进程、不建网络、不写文件**，批次树字节前后一致；运行期未导入 `crosscheck`／`fact_packet`／LLM 相关模块，AST 无复算／底稿调用；筛查只调用冻结核心 `screen_sqlite`（进程内可观测 4 次，含故障前真实调用） |
| G8 计数与证据 | 接收启动登记与 `receive_invocation.json` **一一对应**（`missing`／`unregistered` 均为空）；共用审计规则自测：删一条已登记记录→判定 FAIL，加入一条未登记记录→判定 FAIL 并列出该记录；`summary/checks/counts/self_tests` 由同一最终对象一次落盘并读回逐项一致 |

## 7. 计数口径（全部来自本轮实际留痕）

- **CLI（子进程）**：`start 15`／`status 16`／`record-simulated-decision 14`／`prepare-gate2 14`／`record-simulated-gate2-decision 13`／`screen-rules 13`。
- **进程内公开宿主 API 6**（含经 `status` 进入的 `inspect_dev_batch`、直接调用与抛错前已进入的调用；同一次调用只计一次）。
- **宿主内部控制器重放 57**（进程内可观测；**CLI 子进程内次数 `null`／未观测**，不冒充总数）。
- **筛查核心调用 4**（进程内可观测，含故障包裹前的真实调用）；**CLI 内筛查次数未观测**（按 `screen-rules` 成功次数另列推导值 13，非实测）。
- **接收 15／checker 15**：接收以每条 `receive_invocation.json` 计，checker 按各接收身份清单 `checker_invocation.started` 计。
- **副本 1**（登记来源，不计接收／checker／筛查）；**故障注入 12**；**模拟决定 27**（Gate1 与 Gate2 各按真实记录）；**真实批准 0**。

## 8. 保护核对

- 主基线 `task012_r2`（53983 项）：**变化 2（`scripts\run_demo_workflow.py`、`docs\WORKFLOW_HOST_GUIDE.md`）、缺失 0** —— 恰好是本卡授权的两项既有文件；新增文件不计作既有文件变化。
- 更早基线按各自授权集合累计：`task012_r1`（50404）3 项、`task011_r2`（39831）2 项；`task009_r2`（14691）与 13330／12546／10236／8547／6511／4902／874 **全 0 变化 0 缺失**。
- 冻结未改（入口自校验 13 项）：控制器 `a6b7b8e1…`、接收器 `52195620…`、checker `a7e5eb67…`、标准化 `a2bae49e…`、装载器 `1abfad89…`、**筛查核心 `1b123766…`**、复算 `8fe75bfe…`、底稿 `f4998d92…`、schema `7e0c6463…`、SPEC `5df632ed…`、契约草案 `af405cb6…`、旧入口 `test_run_demo_workflow.py`（`852bf336…`）与 `test_record_demo_gate2_decision.py`（`184ccb39…`）。

## 9. 失败尝试（如实记录）

1. M1 报告校验器按**猜测形状**写了 `period.start/end`，真实核心用 `period_start/period_end/range_ok` → 以核心实际返回为准修正；
2. `findings[].amounts_cents` 存在按实体嵌套的整数分映射 → 改为递归叶子整数检查（新增 `_require_int_cents`）；
3. `statistics.involved_payments` 是对象（`count`／`payment_ids`／`settled_amount_cents`／`note`）→ 对齐并补 `overall_reconciliation` 类型与布尔协议；
4. 重复筛查时宿主把 `failure.json` 写进**已成功**批次（只按目录存在判断"已开始"）→ 改为**本次真正创建 screening 目录后才留痕**（`screen_started` 标记）；该缺陷由测试 G3 暴露；
5. 最终复测漏掉 `0005` 自身字节（G6a 探针因此错误通过）→ 在 `screen_dev_batch` 与 `inspect_dev_batch` 的最后一次控制器调用之后补测当前 checkpoint 字节；该缺口由 G6 暴露；
6. 测试自身缺陷若干：G3 先走到 APPROVED 再记 HOLD/REJECT 导致决定未生效（改为在 Gate2 pending 上记录）、G4/G5 整批副本因**路径派生**在目标语义前就被拦（改为专用探针批次内造样并即时恢复原位 + 保留一项副本路径对照）、G6 探针误用同一批次变量、G6c 断言词不含 `bindings`、G8 自测断言只认 `missing`、G7 用裸词扫描误报注释里的"答案册／LLM"（改为运行期模块与 AST 口径）。

## 10. 未执行（不写通过）

独立复算（R01—R04 之外的交叉复算）、可读事实底稿、AI 候选结论、人类判断预填、正式契约、真实 Gate 批准、正式部署（外置开发数据库仍位于批次目录之外，属保留冻结装载器的架构选择）、UI、真实 ERP／OCR／RAG、并发／锁／断电试验、无边界 fuzz、TASK-014；未重跑 TASK-002—012 的整套历史入口（本卡最小回归由新入口覆盖，旧 `test_run_demo_workflow.py` 与 `test_record_demo_gate2_decision.py` 未改动、未运行）。本地哈希只证明字节一致，不证明来源真实，也不抵御同权限篡改。

## 11. 停止声明

停在 **`DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED`**（`0005` 已保存）；**`0005` 是宿主筛查完成凭证，不是新的控制器批准、不是 Gate2 放行，也不代表项目完成**。HOLD／REJECT 批次保持停止态。未新增 `0006`，未执行独立复算／事实底稿／AI，未建立正式契约、未签真实 Gate、未保存人类判断，未推进 TASK-014。
