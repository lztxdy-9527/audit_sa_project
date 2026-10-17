# TASK-050 执行回执：证据链底稿 .xlsx（可点击定位到原始表行单元格）

日期：2026-10-17。交付状态：工作簿生成器、测试、指南与证据定稿，**交独立验收**；
本回执不宣布验收通过，不接入演示、不改看板、不推进账表/账账或 AI/终判。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-050_DRAFT.md`（`4e0fcb5b…`）、决策记录 `DSH-SCOPE-20261017-04` D-UI2-1。
前置：TASK-049 ACCEPTED。起点接受快照 `data/reviews/task049_dsh_20261017_01/source_hashes_after.json`
（**179652 项 / `1e617527…`**）。本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task050_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 工作簿生成器（唯一新增代码，使用既有 openpyxl） | `scripts/build_excel_workbook.py` | 27987 B | `3ca6ae54912b529d…` |
| 新测试 | `tests/test_excel_workbook.py` | 14997 B | `69982ea3e407b38c…` |
| 指南 | `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 见 delivery.json | 见 delivery.json |
| 本回执 | `docs/EXEC_REPORT_050.md` | 见 delivery.json | 见 delivery.json |
| 正常底稿 | `data/runtime_initial_judgment_recording_tests/task050_workbook_01/证据链底稿.xlsx` | 17000 B | `f9ca422d1c58bae4…` |
| P02 缺证底稿 | `…/task050_workbook_v1_neg/证据链底稿.xlsx` | 16999 B | `f557ecccde09d6ab…` |

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B scripts\build_excel_workbook.py `
  --index data\runtime_initial_judgment_recording_tests\task048_index_01\trace_index.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task050_workbook_01
```

- 正常：**exit 0**、17,000 B；六页顺序 `说明 / 问题清单 / 台账明细 / 原始表行 / 凭证 / 图像占位`。
- P02 缺证（`task048_index_v1_neg`）→ `task050_workbook_v1_neg`：**exit 0**、16,999 B；
  2 行红色（付款 P02 缺审批单/回单），《凭证》《图像占位》写"未取得"与占位说明。
- 测试：`tests/test_excel_workbook.py --out-dir …\task050_run_02` → **exit 0、8/8 cases PASS、
  `read_only_ok=true`**。

## 3. 工作簿内容（实测）

- **链接**：内部定位链接 53 处（正常底稿）**零断裂**；外部链接仅 1 处（打开原始工作簿
  `…/batch_normal/source/input.xlsx`）。问题清单的金额（元/分）与定位链接指向《原始表行》对应单元格；
  涉及账务指向《台账明细》、凭证指向《凭证》对应行。
- **数值**：元 = 分/100（12 组实测一致）；R02 行为 4000.00 元 / 400000 分；差额 = 应为−实为（有值处）。
- **语言**：剥离格式后禁止词 `JSON/hash/SHA/API/script/pipeline/解析/字段类型/字节/编码/版本号` **零命中**。
- **格式**：表头冻结、列宽适配、金额格式、严重程度底色（红 `FDE8E8`/黄 `FFF8D6`/绿 `E6FFEC`）、
  可点金额加粗下划线、A4 横向打印（fitToWidth）；原始表行涉及单元格黄色高亮。
- **说明页**：边界横幅、"单击带下划线的金额或凭证号可定位…双击是进入单元格编辑，不会触发链接"、
  打开原始工作簿超链接、资料接收记录（接收日期/资料名称/份数）。

## 4. 确定性、规模与只读（实测）

- 确定性：同一索引两次生成（间隔 2 秒）**工作簿字节相同**（生成器固定打包时间与核心属性；
  测试同证 `semantic_identical=true`、`bytes_identical=true`）。
- 规模：TASK-048 的 200 条事项索引 → 问题清单 **201 行**（含表头）、**828 个内部链接零断裂**、
  30,441 B、生成耗时约 0.86 秒（本机，非性能承诺）。
- 只读：生成/测试前后索引、原始工作簿、`data/evidence_inputs/` 字节快照一致（`unchanged=true`）。

## 5. 负例（实测）

- 索引悬空账务引用（注入 `ledger_id=AP99`）→ **exit 1**、`kind=content`、字段含
  `CASE-0001.ledger_refs.ledger_id=AP99`。
- 缺索引 → **exit 2**。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task050_finalization/protection_scan.py`），基线 = TASK-049 接受快照
（179652 项 / `1e617527…`）：既有 changed 必须为 0；新增仅限本卡四件与 `task050_*` 底稿/测试/证据根、
架构端已知增量（本卡已在基线内）；missing/读取错误/未登记新增/身份漂移 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：接入演示（另行评估）、页面生成（TASK-049 已有）、账表/账账、影像/OCR、外部查验、函证/盘点、
AI、终判、真实数据/强认证/物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。
工作簿只读展示既有合成证据，不证明凭证/流水真实，不构成审计结论；核对结论由审计人员填写。
