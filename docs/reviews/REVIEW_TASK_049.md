# TASK-049 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"证据链下钻 HTML（多页跳转版 + 单页比对版）"独立复验。页面结构、跳转闭合、语言红线、静态安全、确定性与规模实测均成立；架构端自跑复现。页面只是既有合成证据的只读视图，不证明凭证/流水真实，不构成审计结论。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_drilldown_site.py` | 31155 B | `3f606013221eede4…` |
| `tests/test_drilldown_site.py` | 12855 B | `1f85ad5b71346225…` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 4946 B | `8b5c18bccc13d552…` |
| `docs/EXEC_REPORT_049.md` | 5371 B | `899018cc8ee2dbce…` |

起点 TASK-048 接受身份与卡 `d895b2a5…`、决策 `15e0b8d4…` 一致；纯新增，既有 changed=0。

## 2. 架构端独立运行

- **正常**（`task048_index_01` → 我的新根 `task049_dsh_01_b`）：exit 0；**≥20 页**，含 `index.html`、`case-*`、`compare-*`、`ledger-*`、`voucher-*`、`source-*`；边界横幅、面包屑/返回、A4 打印样式存在；无 `<script>`；**内部链接全部可解析、无外链**；剥离标签后**禁止词零命中**（JSON/hash/SHA/API/script/pipeline/解析/字段类型/字节/编码/版本号），审计语言（差异/核对结论/未取得）存在。
- **确定性**：同索引两次生成，**全部页面字节相同**。
- **P02 缺证**（`task048_index_v1_neg`）：exit 0；事项页显示"未取得"，severity=red；不出现 `MISSING_VOUCHER` 之类技术词。
- **规模**（200 条事项索引）：exit 0；**>300 页**（执行端实测 413 页、约 0.38 秒，本机、非性能承诺）；链接全部可解析。
- **测试复跑**（我的新根 `task049_dsh_test_01_b`）：exit 0、8/8 PASS。
- **只读**：我的生成/测试前后，索引、`data/evidence_inputs/`、账务 `normalized.json` 全部字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 176844 项 / `dc980413…`，`changed=0`、missing 0、读取错误 0、新增 682 项全登记；架构端独立扫描复核（`data/reviews/task049_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界

未生成 Excel 底稿（TASK-050 承担）；未做账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证。图像占位为"模拟数据，当前无对应真实凭证图像"。核对结论由审计人员填写。

## 5. 接受与下一卡

发布新接受基线 `data/reviews/task049_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-050（Excel 证据链底稿，单击定位到《原始表行》单元格）**。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
