# TASK-011-R2 执行回执（只修 checkpoint 初始字节与哈希的取值时点）

任务：关闭 F02 剩余反例——`_load_checkpoint_chain` 先解析、再重放、最后才取链哈希，导致期间的文件变化被当成新的预期值，本次 `status` 可能仍返回 READY。
日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-011-R2.md`、`docs/reviews/REVIEW_TASK_011_R1.md`、R1 卡 §3、GPT 证据 `data/reviews/task011_r1_20261011_142537/checkpoint_timing_probe.{py,json}`。
状态：完成并自检通过，**停在 `DEV_GATE2_PENDING`**；未新增或提交任何 Gate2 决定，未推进 TASK-012。

---

## 1. 最小改动（仅 checkpoint 读取与链哈希附近）

宿主 `scripts/run_demo_workflow.py`：

1. 新增 `_read_json_with_bytes(path, path_label, stage)`：**一次**把文件字节读入缓冲，用**该缓冲**解析 JSON，并对**该缓冲**计算 SHA-256；异常类别／字段路径／异常链与既有 `_read_json` 一致（不可读 → `WorkflowHostError`；非法 JSON／非对象 → `WorkflowHostBlocked`）。
2. `_load_checkpoint_chain` 的逐份循环改用它，`label` 先于读取确定；链中的 `file_sha256` 不再事后 `file_sha256(entry)`，而用**初始读取的 SHA**。
3. 该初始 SHA 统一用于：本份 `file_sha256`、下一份 `previous_file_sha256` 比对、`_verify_prepare_operation(previous_file_sha256=…)`、`current` 元数据、Gate2 收尾预期。
4. 循环结束后（即**最后一次控制器调用之后**）新增**收尾复测**：按固定路径逐份复测 `0001`／`0002`／`0003` 磁盘字节是否仍等于初始 SHA；不同即按该 checkpoint 路径给 `WorkflowHostBlocked`（含"收尾复测发现 checkpoint 字节在本次读取之后发生变化"与预期（初始读取）／实际值），不可读同样阻断并带路径。

未做：解析前后各读一次再假定同内容、重放后覆盖初始哈希、给特定 `0003` 探针加特殊分支、重写宿主、遍历任意路径、改控制器、加生产测试开关。缺文件／不可读／非法 JSON／形状错误的既有类别与路径保留；F01／F03／F04 与其他收尾核验行为不变。

版本：宿主实现版本升 **`TASK-011-workflow-host-1.2`**（`prepare_version` 随 HOST_VERSION＝1.2）；**不新增字段、不改持久化形状**，`TASK-011-host-manifest-1.1`／`TASK-011-checkpoint-1.1`／artifacts 1.1／failure 1.1 协议版本保留；未迁移旧批次。

## 2. 文件与产物

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py` | `4ee841b1e925f148979fdecb2906f471cb37239a89630d7e2f558a3bb12285b1` |
| `tests\test_prepare_demo_gate2.py` | `11d4fe57690ff5d5438aaf25b9a3953ced9a1e500ccef1620f61f39ec548b4e4` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `99f91242a06f78bec6f508c1541d81916d9ccf70c4ea4ab6ac70fd7b3858c23a` |
| `docs\EXEC_REPORT_011_R2.md` | 本文件（新增） |

起点哈希（本轮修改前）：宿主 `e950895a…`、测试 `5ee6c4bd…`、指南 `6861fec2…`。

**三条新产物路径**：

- 测试容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task011r2_02`（1 目录 / **213 文件**）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task011r2_02`（334 目录 / **701 文件**；**32 份 `0003.json`、0 份 `0004.json`**）
- 推导外置 SQLite 目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task011r2_02`（51 目录 / 34 文件）

过程现场保留：`data\batches\task011r2_smoke`（冒烟，含 `c02_small` 等未建）与 `data\workflow_host_tests\task011r2_01`／`task011r2_smoke`、`r2_run.log`。

## 3. 真实命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"        # 0
& $py -B -c "src = open(r'...\tests\test_prepare_demo_gate2.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B 'D:\harness work\audit_sa_project\tests\test_prepare_demo_gate2.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task011r2_02'
```

最终一次：**退出 0**，**10 组全 PASS，failures=[]**，`final_readback ok=true`，受保护文件前后一致。组数按实际记录（G1—G9 原九组 + G10 定向探针组，本卡探针并入 G10）。

## 4. 本卡定向探针证据（正向 + 负向）

正向控制（无变化）：`status` 退出 **0**，`phase=DEV_GATE2_PENDING`，`gate1_approval=null`、`gate2_approval=null`、`next_step_allowed=false`。

负向（新合法批次 `g10_f02_ckpt_timing`，先真实 `prepare-gate2` 到 Gate2 pending）：

- 注入点：包装**真实** `prepare_dev_gate`，先执行原函数，在 **Gate2 纯重放返回时**（旧 JSON 已被消费）仅一次把磁盘 `0003.operation.materials_sha256` 改为 64 个 0。
- **命中恰为 1**；`before_sha256 = 5687b7724e3bcdbf939ee960b5013b807fb74f0ba03a68513ad7129e62838f33`（故障调用**之前**取得），`after_sha256 = 134e31da64af4c56cc49bdaac9ef05161aa240e38999ff07d302f58888508dbe`（调用结束**之后**取得），二者**不同**。
- **本次 `status` 即拒绝**：退出 **1**，类别 `WorkflowHostBlocked`，原因：
  `字段 workflow/checkpoints/0003.json 不可用：收尾复测发现 checkpoint 字节在本次读取之后发生变化：预期（初始读取）5687b772…，实际 134e31da…`（含 checkpoint 路径与收尾字节变化，不是只验证下一次调用）。
- 撤销 wrapper 后**新进程 CLI**：`status --batch-dir …/g10_f02_ckpt_timing` 退出 **1**，原因指向语义错误
  `字段 workflow/checkpoints/0003.json.operation.materials_sha256 不可用：必须等于本次实际材料对象的规范指纹`。
- 完整返回／异常、真实 before/after、变更字段、注入时点与次数均落盘于容器 `summary.json` 的 G10 组 `probes`（`case=g10_f02_checkpoint_initial_bytes_timing`）。

保留通过：原 40 字节 `0003` writer 故障、完整 `0003` 后失败诊断（F01 及其四个变体）、报告／数据库晚变更（F02 原三探针）、artifact 字节引用与语义（F03）、真实计数与隔离自测（F04）、MAIN/C02/C07b、失败接收、HOLD/REJECT、只读与静态守卫。

## 5. 计数（本轮实际导出，不以 R1 次数为目标值）

| 类别 | 本轮 |
| --- | --- |
| CLI | start 24／status 35／record-simulated-decision 22／prepare-gate2 10 |
| 公开宿主 API | 16 |
| 私有探针调用（G4 直接 `_run_receiver`） | 1 |
| 控制器调用 | 20 |
| **receiver** | **25** = 宿主启动 24（逐条 `receive_invocation.json`）+ 直接/私有启动 1（测试侧登记命令与退出码） |
| **checker** | **25**（25 个接收身份 `checker_invocation.started=true`，含 C12 阻断 exit 1 与非 ZIP 运行失败 exit 2） |
| normalize／load | 进程内 11／10（含故障前真实调用）；CLI 子进程内 **未观测 `null`**，另按成功 CLI prepare 推导 7／7 分列 |
| 副本 | 16（登记来源后排除） |
| 故障注入 | 28（含本卡新增 1） |
| 拒绝 | 38（探针层定向记录 28 为子集） |
| 模拟决定 | 21 |
| **真实批准** | **0** |

计数审计仍内嵌于容器 `summary.json`／`checks.json` 的 **G9** 组（**不存在独立的 `count_audit.json`**——纠正旧回执的引用；旧回执不回写，也不以此扩展 F04 代码修复）；一一对应审计与"少一条／多一条记录"隔离自测均通过，`self_tests.json` 两项 `ok=true`。

## 6. 保护结果

- 主基线 `data/reviews/task011_r1_20261011_142537/source_hashes_after.json`（34813 项）：变化 **3**（宿主、测试、指南）、缺失 **0**。
- 旧基线按各自起点累计变化：`task011`（28489）3 项（宿主＋测试＋指南）；`task010`（16340）3 项（宿主＋旧测试 `test_run_demo_workflow.py`＋指南，为历史授权累计）；`task009_r2`（14691）及更早 13330／12546／10236／8547／6511／4902／874 **全部 0 变化、0 缺失**。
- 冻结上游逐项未变：控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、schema `7e0c6463`、SPEC `5df632ed`、契约 `af405cb6`、旧入口 `test_run_demo_workflow.py` `852bf336`。
- 旧回执/卡片/验收单/GPT 证据/旧批次/旧数据库未回写；四文件 UTF-8 无 BOM；临时补丁脚本与 `__pycache__` 已清理；宿主内**无任何 Gate2 决定接口**（CLI 仍 4 个子命令）。

## 7. 失败尝试

1. 测试硬编码旧宿主版本 `TASK-011-workflow-host-1.1` → G4 报"宿主版本不是 …1.1"；按卡把实现版本预期改为 1.2（协议版本仍 1.1）后通过。
2. 第一版收尾复测误把 `file_sha256` 直接放在 `_require` 表达式里，文件被替换为目录时可能抛 `IsADirectoryError` → 改为 `try/except OSError` 转 `WorkflowHostBlocked` 带路径与预期值。
3. 冒烟脚本首次运行前需先清空同名批次目录（`start` 拒绝已存在目标），已按固定路径删除后重跑。

## 8. 未执行（不写通过）

Gate2 决定的实现与提交、`record`/`prepare` Gate2、R01—R04、复算、底稿、AI 建议、正式契约、真实 Gate、人类判断保存、UI、真实 ERP、并发／锁／断电／原子快照／无边界 fuzz；未重跑 TASK-002—010 历史入口（旧 `test_run_demo_workflow.py` 未运行）。

**停止状态**：停在 `DEV_GATE2_PENDING`（**不是** Gate2 已放行）；未新增或提交任何 Gate2 决定；未建立契约、未签真实 Gate、未保存人类判断、未生成 AI 建议；**未推进 TASK-012**；未修改任务看板，未宣布任务完成。
