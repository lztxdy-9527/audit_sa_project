# 一键对账启动器指南（TASK-059）

标识：`TASK-059-run-all-1.0`（+ `TASK-059-R2` 允许差异开关）。实现：`scripts/run_all.py`（仅标准库）
+ 根目录 `一键对账.cmd`、`一键对账_允许差异.cmd`。
依据：`docs/decisions/DECISION_20261018_DSH_INTAKE_AND_ONECLICK.md`（`DSH-SCOPE-20261017-07` D-IO-2/3）。
边界：一键运行只做**机器核对与出页**，不构成审计结论；真实批准 `null`、真实初判未保存、0008、
`next/AI=false`。

## 1. 使用方式

双击项目根目录的 `一键对账.cmd`（内部 `chcp 65001`、`-B`、结束 `pause`）：

```text
一键对账.cmd
  → .venv\Scripts\python.exe -B scripts\run_all.py --open
```

PowerShell 备用命令：

```powershell
.venv\Scripts\python.exe -B scripts\run_all.py --open
# 指定运行号、不打开浏览器：
.venv\Scripts\python.exe -B scripts\run_all.py --run-id task059_run_01 --no-open
# 允许差异：demo 的账证/账实差异不再中止，站点照常出（见第 5.1 节）
.venv\Scripts\python.exe -B scripts\run_all.py --run-id task059_diff_01 --no-open --allow-differences
```

也可以双击根目录的 `一键对账_允许差异.cmd`（等价于 `--allow-differences --open`）。

## 2. 配置 `config/run_all.json`

```json
{
  "inputs": {
    "batch_dir": "data/batches/task027r1_run_04/batch_normal",
    "task043_input_root": "data/evidence_inputs/task043_v1_1",
    "ledger_db": "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3",
    "gl_root": "data/evidence_inputs/gl_v1"
  },
  "output_root": "outputs",
  "open_browser": true,
  "review_notes": null
}
```

路径按项目根解析；`review_notes` 非空时追加第 8 步审阅合并。`--run-id` 缺省
`run_YYYYmmdd_HHMMSS`；`--out-root` 可覆盖输出根。

## 3. 步骤与依赖

| 序 | 步骤 | 说明 |
| --- | --- | --- |
| 1 | 输入契约校验 | `input_contract_v1.py` |
| 2 | GL v1 契约校验 | `gl_input_contract_v1.py` |
| 3 | 运行层演示 | `run_runtime_demo.py`（新运行根） |
| 4 | GL 六类核对 | `reconcile_gl_v1.py`（索引 gl 节依赖此报告，故先于索引） |
| 5 | 证据链索引（含 gl） | `build_trace_index.py --gl-root --gl-report` |
| 6 | 站点（含借贷核对页） | `build_drilldown_site.py` |
| 7 | Excel 底稿（含借贷核对页） | `build_excel_workbook.py` |
| 8 | 可选：审阅合并 | `apply_review_notes.py`（配置了 review_notes 时） |

> 卡片原文把“索引”列在“GL 核对”之前；索引 v1.2 的 `gl` 节需要核对报告，故实际执行顺序为
> **核对 → 索引**，其余步骤不变。

## 4. 输出 `outputs/<run_id>/`

- `index.html`（入口）+ 站点其他页面；
- `gl/`：借贷核对六页 + `gl_reconcile_report.json/.md`；
- `excel/证据链底稿.xlsx`；
- `logs/`：每步 stdout/stderr；
- `run_summary.json`：`steps[]`（id/name/command/exit_code/error_field）、`overall`、
  `failed_step`、`outputs`、`read_only_ok`、`unperformed`、`boundaries`。

## 5. 行为约束

1. **只读输入**：批次、task043、GL 根、账务库在每步后校验哈希；漂移立即停止并失败。
2. **每次新目录**：`outputs/<run_id>` 必须不存在；不覆盖旧运行、不清理旧证据。
3. **失败即停**：任一步非零 → 写 `FAILED` 汇总、不发布 `index.html`、整体 exit 1。
   （例外：显式开启 `--allow-differences` 且失败仅来自第 3 步的四相符差异，见 5.1。）
4. 不联网、不安装依赖；只调用项目内脚本与标准库。
5. 成功判据：七步全 0 且 `index.html`、`gl/gl-checks.html`、`excel/证据链底稿.xlsx` 存在。
6. 汇总附“未执行项”（函证/监盘/期后付款/截止测试等）与边界横幅。

### 5.1 `--allow-differences`（默认关闭）

**动机**：默认策略下，demo 步一旦发现账证/账实不是 `ALL_MATCHED` 就中止，站点不会生成，
因此带差异的数据永远看不到“红色事项”页面。该开关让“差异”以页面形式呈现，同时不改变默认行为。

**判据（只容忍这一种失败）**：
`demo` 步非零 **且** `task059_demo_<run_id>/demo_summary.json` 已写出、其中
`four_way.account_voucher.conclusion` 或 `four_way.account_reality.conclusion` 不是 `ALL_MATCHED`。
运行层演示是在写完 `demo_summary.json` 与三份报告之后才抛 `DemoFailure` 的，所以可用“summary 存在”
把它与契约拒收等更早的失败区分开。

**行为**：

| 项 | 不加开关 | 加开关且命中上述判据 |
| --- | --- | --- |
| 第 3 步 | 失败即停 | `steps[demo].tolerated=true`、`error_field=four_way_differences`，继续第 4~7 步 |
| `overall` | `FAILED` | `SUCCESS_WITH_DIFFERENCES` |
| `failed_step` | `demo` | `null` |
| 终端退出码 | 1 | 0 |
| 站点 | 不发布 | 发布；差异渲染为红色 case |
| 其它失败（契约/GL/索引/站点/只读漂移/publish） | FAILED | **仍然 FAILED**（开关不掩盖） |

**`run_summary.json` 新增字段**：

```json
{
  "overall": "SUCCESS_WITH_DIFFERENCES",
  "failed_step": null,
  "allow_differences": true,
  "tolerated_steps": ["demo"],
  "differences_tolerated": true,
  "steps": [{"id": "demo", "exit_code": 1, "tolerated": true,
             "error_field": "four_way_differences", "...": "..."}]
}
```

> 边界：站点里的红色事项是**机器差异**，不是审计结论；开关只影响“是否继续出页”，
> 不改变任何核对口径，也不把差异写成“已解决”。

## 6. 测试与证据

`.venv\Scripts\python.exe -B tests\test_run_all.py --out-dir data\runtime_initial_judgment_recording_tests\task059_run_02`

- 正常：七步全 0、`index.html`/`gl/gl-checks.html`/`excel`/`logs`/`run_summary` 齐全；
- 失败：task043 输入缺文件 → 第 1 步失败、exit 1、无 `index.html`；GL 契约坏 → 第 2 步失败；
- 输出目录已存在 → exit 2；启动器/配置检查；确定性（两个 run-id 的 index/gl-check/excel 字节相同）；
- 只读：输入根/批次/账务库前后哈希一致。
- 证据：`task059_evidence_01/`（成功/失败日志、run_summary、哈希快照）。

**开关测试（TASK-059-R2）**：

`.venv\Scripts\python.exe -B tests\test_run_all_allow_differences.py --out-dir data\runtime_initial_judgment_recording_tests\task059r2_allow_diff_01`

- 差异包（发票 +1 分，契约过、账证差异）：不加开关 → `failed_step=demo`、exit 1、无 `index.html`；
- 同一包加开关 → 七步全跑完、exit 0、`overall=SUCCESS_WITH_DIFFERENCES`、`tolerated_steps=["demo"]`、
  `steps[demo].tolerated=true`、站点 `case-*.html` > 1（R02 线索 + 账证差异）、只读 OK；
- 加开关但第 1 步（契约）或第 2 步（GL 契约）失败 → 仍然失败即停，不被开关掩盖。

**可重复运行（TASK-059-R1）**：测试每次使用**唯一 run-id**（`normal_<时间戳>_<随机>` 等）
与**本次专属输出根**（`<out-dir>/outputs_<时间戳>_<随机>`），不复用 `outputs/task059_run_01`
等既有目录；因此可在已有 `outputs/` 与历史测试产物的工作区**连续运行多次**，每次均为 6/6。
测试创建的目录唯一命名并保留（不删除项目既有证据）；引擎/启动器/配置行为不变。

## 7. 未做

不做审计结论/终判；不做函证/监盘/期后付款；不改看板；不联网。
