# TASK-058 独立验收（DSH Architect）

结论：**NOT_ACCEPTED**（发现 1 类健壮性缺陷，需 TASK-058-R1 修复后重验）。2026-10-18，DSH 架构/测试验收端对"数据投放指引与目录骨架"独立复验。

## 1. 复验结果

- **目录骨架**：`data/inbox/` 四类目录、`_放入说明.md`、`放入此处.txt`、README 齐全；说明含文件清单、命名、整数分、校验命令、整包退回声明。
- **空 inbox**：exit 0；四类均 **缺失**；状态页纯静态、无脚本、有"不构成审计结论"横幅；manifest `categories` 四项齐全；链接可解析。
- **合法样例**（我自建：合法 xlsx + index.json 与一张凭证 + `{"transactions":[...]}` 银行流水 + GL 十个文件）：exit 0；四类 **已提供**。
- **坏样例**（坏 xlsx、缺凭证文件、银行缺字段、GL 非法 JSON）：exit 0；四类 **需校验**。
- **确定性**：空 inbox 两次生成，状态页/manifest 字节相同；**只读**：`data/inbox` 前后字节不变；测试 6/6。
- **但发现 B1（健壮性）**：

### B1 结构异常的 JSON 会让生成器崩溃（而非"需校验"）

把 `03_银行流水/bank_transactions.json` 写成 **JSON 数组**（而不是 `{"transactions":[...]}`，这是很常见的误存形状）：

```
AttributeError: 'list' object has no attribute 'get'
  build_intake_guide.py line 109 in validate_bank
```

生成器 **exit 1、无状态页**，而不是按卡片要求把该类别标为 **需校验** 并继续出页。同类风险：附件 `index.json` 缺少 `vouchers` 键、GL 文件为数组等非对象结构，均可能抛未捕获异常。这是"坏数据应显示需校验、生成器不崩"的 fail-safe 缺陷；虽然不损坏数据，但会让审计人员拿不到状态页。

## 2. 处置

- 本卡不发布接受基线、不更新 review_result；
- 发 **TASK-058-R1**：给每个类别的校验加异常兜底（任何解析/结构/IO 错误 → `需校验` + 精确 detail，exit 0），并把这些形状写进测试；
- 修复后重跑：空/合法/坏/结构异常四类 + 确定性 + 只读 + 保护扫描。

## 3. 边界

指引页只说明放置与校验，不构成审计结论；不复制/移动/修改 inbox 文件；不做数据清洗；不做一键启动器（TASK-059）；`real_approval=null`、真实初判未保存、0008、`next/AI=false`。
