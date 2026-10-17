# TASK-047 执行回执：离线静态 HTML 演示报告（四相符 + 线索 + 初判，只读渲染）

日期：2026-10-17。交付状态：生成器、测试、指南与证据定稿，**交独立验收**；
本回执不宣布验收通过，不把 HTML 接入演示主流程、不改看板、不推进账表/账账或 AI/终判。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-047_DRAFT.md`（`4656db94…`）、决策记录
`docs/decisions/DECISION_20261017_DSH_STATIC_HTML_REPORT.md`（`5415c006…`，`DSH-SCOPE-20261017-03`）。
前置：TASK-046 ACCEPTED。起点接受快照 `data/reviews/task046_dsh_20261017_01/source_hashes_after.json`
（**176350 项 / `3c520328…`**）。本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task047_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 生成器（唯一新增代码，仅标准库） | `scripts/build_demo_report_html.py` | 见 delivery.json | 见 delivery.json |
| 新测试 | `tests/test_demo_report_html.py` | 见 delivery.json | 见 delivery.json |
| 指南 | `docs/DEMO_REPORT_HTML_GUIDE.md` | 见 delivery.json | 见 delivery.json |
| 本回执 | `docs/EXEC_REPORT_047.md` | 见 delivery.json | 见 delivery.json |

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B scripts\build_demo_report_html.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task047_report_01
```

- 正常生成：**exit 0**，`index.html` 9519 B、`report_source.json` 2181 B；7 个输入文件身份登记。
- P02 缺证运行根（`task046_demo_v1_neg`）→ `task047_report_v1_neg`：**exit 0**（渲染成功），
  HTML 显示**账证 6/8** 与 **2 条 `MISSING_VOUCHER`**（红黄高亮），差异是内容，不是渲染失败。
- 测试：`tests/test_demo_report_html.py --out-dir …\task047_run_03` → **exit 0、8/8 cases PASS、
  `read_only_ok=true`**；覆盖正常/确定性/转义/3 类负例/P02 缺证。

## 3. 输出（实测）

- `index.html`：单文件、内联 CSS、UTF-8、A4 可打印；**无 `<script>`、无 `http://`/`https://`、
  无 `<link>`/`<img>`/`@import`/`url(`**；全部动态文本 HTML 转义。
- 包含区块：边界横幅；身份（batch_normal / 澄明商贸有限公司 / CNY / 2026-09-01～2026-09-30 / 截至 2026-09-30 /
  运行根）；四相符卡片（契约 `INPUT_V1_ACCEPTED`、账证 8/8、账实 3/3、期间合计 OUT/IN 差异 0、未达 0、
  余额 `not_provided`、初判 `RT_HUMAN_INITIAL_JUDGMENT_VERIFIED` + 记录/材料指纹）；R01–R04 计数与 R02 明细
  （4000 元超额、分与元并列、`payables!E2`/`allocations!D2`/`allocations!D3`/`payments!F2`/`payments!F3`/
  `refunds!F4` 来源）；账证 8 行明细与"核对结论"空列；账实匹配行与期间合计、未达两侧；初判六字段原文 +
  "合成夹具回放、非真人审批"；追溯链路；九边界全 false 与未执行项；页脚（命令、输入身份摘要、
  "本报告不是审计结论"）。
- `report_source.json`：逐输入文件（`demo_summary`、`input_registry`、`voucher_report`、
  `reconcile_report`、`fact_packet`、`judgment`、`record_manifest`）路径/长度/SHA-256、运行根名、
  生成器版本、命令（`--out-dir` 为 `<out-dir>` 占位）；无时间戳/随机数。
- 确定性：同一 `--run-root` 两次生成（`task047_det_a`/`task047_det_b`），`index.html` 与
  `report_source.json` **字节相同**（实测 + 测试双证）。

## 4. 转义与负例（实测）

- 转义注入：复制运行根为夹具、批次名改为 `<b>x</b>` → HTML 出现 `&lt;b&gt;x&lt;/b&gt;`，不出现裸 `<b>x</b>`。
- 负例：out-dir 已存在 → exit 2；run-root 不存在 → exit 2；运行根缺 `demo_summary.json` → exit 2、
  stdout 字段 `demo_summary`；内容缺 `four_way` → exit 1、字段 `demo_summary.four_way`（`kind=content`）。

## 5. 只读与证据

- 只读：生成/测试前后对 `task046_demo_01`、`task046_demo_v1_neg` 运行根、对应业务根（事实包/初判记录/manifest）、
  `data/evidence_inputs/` 做字节快照比较，完全一致（`read_only_ok=true`）。
- 证据根 `data/runtime_initial_judgment_recording_tests/task047_evidence_01/`：`command.json`（命令/退出码）、
  `normal_stdout|stderr.txt`、`v1neg_stdout|stderr.txt`、`det_a|b_stdout|stderr.txt`、
  `report_source_normal.json`、`report_source_v1_neg.json`、`input_snapshot_before|after.json`。
- 报表根：`task047_report_01`（正常）、`task047_report_v1_neg`（P02 缺证）、`task047_det_a|b`（确定性双生成）。
- 测试迭代保留：`task047_run_01`（确定性首失败）、`task047_run_02`（转义/内容夹具缺业务根，已修正）、
  `task047_run_03`（8/8 通过）与同名 `task047_*` 夹具。
- 说明：首次冒烟生成的 `task047_report_01` 产生于确定性修复前（命令含实际 out 路径），已被**最终生成器**
  在同一 out 名重生成；冒烟物为过程物、非证据。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task047_finalization/protection_scan.py`），基线 = TASK-046 接受快照
（176350 项 / `3c520328…`）：既有 changed 必须为 0；新增仅限本卡四件与 `task047_*` 证据/报表/夹具根、
架构端已知增量（本卡与静态报告决策记录逐确切路径登记）；missing/读取错误/未登记新增/身份漂移 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：把 HTML 接入演示主流程（另行评估）、账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、
真实数据/强认证/物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。本报告只读展示既有合成证据，
不证明凭证/流水真实，不构成审计结论。
