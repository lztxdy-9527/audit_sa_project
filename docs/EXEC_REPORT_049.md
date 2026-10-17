# TASK-049 执行回执：证据链下钻 HTML（多页跳转版 + 单页比对版）

日期：2026-10-17。交付状态：站点生成器、测试、指南与证据定稿，**交独立验收**；
本回执不宣布验收通过，不生成 Excel 底稿（TASK-050）、不改演示、不改看板、不推进账表/账账或 AI/终判。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-049_DRAFT.md`（`d895b2a5…`）、决策记录 `DSH-SCOPE-20261017-04`。
前置：TASK-048 ACCEPTED（`trace_index.json` 已接受）。起点接受快照
`data/reviews/task048_dsh_20261017_01/source_hashes_after.json`（**176844 项 / `dc980413…`**）。
本卡**纯新增**：未修改任何既有文件（含 TASK-047 的 HTML 生成器与既有报告）。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task049_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 站点生成器（唯一新增代码，仅标准库） | `scripts/build_drilldown_site.py` | 31155 B | `3f606013221eede4…` |
| 新测试 | `tests/test_drilldown_site.py` | 12855 B | `1f85ad5b71346225…` |
| 指南 | `docs/DRILLDOWN_SITE_GUIDE.md` | 4946 B | `8b5c18bccc13d552…` |
| 本回执 | `docs/EXEC_REPORT_049.md` | 见 delivery.json | 见 delivery.json |

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B scripts\build_drilldown_site.py `
  --index data\runtime_initial_judgment_recording_tests\task048_index_01\trace_index.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task049_site_01
```

- 正常：**exit 0**；**26 页**、总大小 91,431 B：问题清单（1 页）、R02 事项页、4 条账务行页、
  8 张凭证页、7 条原始表行页、资料接收记录、逐格比对页。
- P02 缺证（`task048_index_v1_neg`）→ `task049_site_v1_neg`：**exit 0**；**28 页**、98,528 B；
  事项页显示"未取得审批单/回单"、红色标记、灰色占位框。
- 测试：`tests/test_drilldown_site.py --out-dir …\task049_run_01` → **exit 0、8/8 cases PASS、
  `read_only_ok=true`**。

## 3. 页面与链接（实测）

- 清单页 `index.html`：R02 事项可点、金额可点；红/黄/绿标记；页码链接。
- 事项页：金额、差异原因、账务链接、凭证链接、原始表行链接、核对结论「由审计人员填写」、上一/下一事项。
- 账务行页：逐字段值（审计语言）+ 来源（工作表/行/列/原值/整理值）+ 原始表行链接；
  分摊行（A01/A02/AR01）也有独立页面，来源行匹配按编号列确定（A02 不再被原分摊列误匹配）。
- 凭证页：字段 + 图像占位 + 资料接收记录链接；原始表行页：各列原值/整理值 + "打开原始 Excel 文件（见资料接收记录）"。
- 链接完整性：遍历 26 页全部 `href`，**全部为相对路径且目标存在（0 处不可解析）**；无 `http(s)://`、
  无 `<script>`、无 `<img>`/`<link>`、无外部字体；动态文本转义（注入 `<b>注入</b>` → `&lt;b&gt;注入&lt;/b&gt;`，
  不出现裸标签）。
- 语言红线：剥离标签（含样式块）后禁止词 `JSON/hash/SHA/API/script/pipeline/解析/字段类型/字节/编码/版本号`
  **零命中**；技术路径/SHA 不出现在可见文本。
- 确定性：同一索引两次生成（`task049_det_a`/`task049_det_b`）26 个页面**字节全部相同**。

## 4. 规模（实测，非性能承诺）

- TASK-048 的 **200 条事项**索引（`task048_run_01/task048_index_scale/trace_index.json`）→ 站点 **413 页**、
  总大小 **1,506,353 B**、生成耗时 **约 0.38 秒**（本机）；全部 `.html` 的 `href` 均可解析；
  清单分 4 页（50 条/页）、200 个事项页、200 个比对页。只报告本机实测，不承诺任意大数据。

## 5. 只读与负例（实测）

- 只读：生成/测试前后 `task048_index_01`、`task048_index_v1_neg`、`data/evidence_inputs/`、账务
  `normalized.json` 字节快照一致（`read_only_ok=true`）。
- 负例：索引内悬空账务引用（注入 `ledger_id=AP99`）→ **exit 1**、`kind=content`、字段含
  `CASE-0001.ledger_refs.ledger_id=AP99`；缺索引 → **exit 2**。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task049_finalization/protection_scan.py`），基线 = TASK-048 接受快照
（176844 项 / `dc980413…`）：既有 changed 必须为 0；新增仅限本卡四件与 `task049_*` 站点/测试/证据根、
架构端已知增量（本卡/049/050/决策记录已在基线内）；missing/读取错误/未登记新增/身份漂移 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：Excel 底稿（TASK-050）、账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证/
物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。页面只读展示既有合成证据，不证明凭证/流水真实，
不构成审计结论；核对结论由审计人员填写。
