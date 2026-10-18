# 采购付款 CAAT 审计辅助原型（合成演示）

> 合成数据、本地离线运行；**不是审计报告，不构成审计结论**；真实批准 `null`、真实初判未保存、`next_step_allowed=false`、`ai_enabled=false`。

## 快速开始

| 入口 | 用途 |
| --- | --- |
| 双击 **`一键对账.cmd`** | 正常四相符 + GL 借贷核对，七步跑完并打开 HTML |
| 双击 **`一键对账_允许差异.cmd`** | 四相符有差异时仍出站点，整体记为 `SUCCESS_WITH_DIFFERENCES` |
| 双击 **`一键对账_差异演示.cmd`** | 用“银行影子流水”演示包，预期出现差异 |

结果在 `outputs/<run_id>/`：

```
index.html                 主入口（四相符、全量清单、GL、筛选、审阅）
gl/                        GL 六类核对报告
excel/证据链底稿.xlsx      Excel 底稿（自动筛选、超链接定位）
logs/                      七步日志
run_summary.json           步骤、退出码、总体状态
```

## 项目能做什么

- **账证相符（L1）**：账务记录 ↔ 发票/合同/入库/审批/回单；金额、日期、对象、方向、状态；缺失/多余。
- **账实相符（银行）**：账面付款/退款 ↔ 银行流水；期间合计；未达账项。
- **GL 借贷核对**：凭证平衡、试算平衡、账证、账账、账表、账实（+附件）。
- **证据链**：线索 → 账务行 → 凭证 → 原始表行，可下钻、可追溯。
- **全量清单 + 筛选 + 网页审阅 + 审阅记录 Excel**。
- **数据投放指引**：`data/inbox/` 目录骨架 + 状态页（已提供/缺失/需校验）。

## 文档

- [项目技术说明（五层结构图 + 名词悬停人话版）](docs/PROJECT_EXPLAINER.html)
- [一键运行指南](docs/RUN_ALL_GUIDE.md)
- [GL 核对指南](docs/GL_RECONCILE_GUIDE.md)
- [求职演示与面试说明](docs/JOB_DEMO_PLAYBOOK_20261017.md)
- [测试数据与错误识别规范（供生成 Agent 使用）](docs/TEST_DATA_AND_DETECTION_SPEC.md)
- [最终验收入口](docs/FINAL_ACCEPTANCE_ENTRY.md)

## 目录

- `scripts/`：输入契约、运行层演示、账证/账实/GL 核对、索引、站点、Excel、审阅、投放指引、一键编排
- `config/`：一键运行配置（正常 / 差异演示）
- `data/`：批次与输入、各阶段运行证据、评审基线（体积大，默认不入 git）
- `outputs/`：每次运行的产物（`<run_id>/index.html`）
- `docs/`：任务卡、评审记录、决策记录、说明文档

## 边界

不做数据清洗、影像/OCR、银行版式适配、外部查验、函证、监盘、期后付款、截止测试、账龄分析、AI 建议、人类终判。真实数据接入需另行授权、脱敏与输入映射。

## 技术栈

Python 3（标准库 + openpyxl）、SQLite、纯静态 HTML/CSS、Excel 超链接；无服务器、无外部 CDN、不联网。
