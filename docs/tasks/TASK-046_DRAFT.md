# TASK-046：四相符演示集成（账-证-实一条命令）+ 校验器版本声明集 + 求职稿更新

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-045 ACCEPTED**。依据 `DSH-SCOPE-20261017-02`：只做字段级 L1；不引入清洗/OCR/银行格式适配；不采集人类结论；不开放 AI/终判。

本卡把已接受的三个核对器（契约/账证/账实）串进**一条命令的演示**，并关闭 TASK-043-R1 记录的"校验器版本硬编码"残差。允许修改的既有文件**仅四件**（见 §1）；其余全部纯新增。

## 1. 允许修改/新增

**允许修改（changed 恰这四件）**：
- `scripts/input_contract_v1.py`：版本声明集支持（见 §2）。
- `scripts/run_runtime_demo.py`：演示集成（见 §3）。
- `docs/JOB_DEMO_PLAYBOOK_20261017.md`：四相符口径与演示命令/产物更新。
- `docs/FINAL_ACCEPTANCE_ENTRY.md`：任务链与最终交付更新（如本轮定稿）。

**允许新增**：`docs/EXEC_REPORT_046.md`；证据根 `data/runtime_initial_judgment_recording_tests/task046_*`；演示运行根按既有 `task042_*`/`task046_*` 规则新建。**禁止**修改：适配器 `runtime_gate1.py`、输入根（v1/v1.1）、voucher_match/bank_reconcile、测试、指南、既有卡/评审/证据、看板。

## 2. 校验器版本声明集（关闭 R1 残差）

- `input_contract_v1.py` 接受声明版本集 `{task043-input-1.0, task043-input-1.1}`；登记中原样回显 `input_version`；未知版本 → `MANIFEST_VERSION` 整批拒收；**其余 schema/哈希/索引/ledger 校验保持不变**。
- 测试：v1.1 原样 → exit 0、`INPUT_V1_ACCEPTED`、计数 8 凭证/8 links/3 bank；v1 原样 → exit 0（回归）；未知版本（如 `task043-input-1.2`）→ exit 1、仅 `MANIFEST_VERSION`。

## 3. 演示集成（一条命令跑完账-证-实）

`run_runtime_demo.py` 在既有链（注册→Gate1→装载→Gate2→筛查→复算→事实→初判保存→只读恢复）之后，增加**只读**步骤：
1. 用 canonical 输入 `data/evidence_inputs/task043_v1_1` 调已接受 `voucher_match_v1.py`（账证）；
2. 调已接受 `bank_reconcile_v1.py`（账实）；
3. 把两者摘要写入 `demo_summary.json`/`demo_readme.md`：账证 `8/8 MATCHED`（P02 含 V-APR-0002/V-BR-0003）、账实 `3/3 MATCHED`（REFERENCE_INDEX）、期间合计差异 0、未达账项空、`human_conclusion` 留空、验证层级与边界声明。
4. 新增可选参数 `--evidence-input`（默认 `data/evidence_inputs/task043_v1_1`）；输入缺失或版本不被接受时演示**失败退出**（不静默降级）。账证/账实任一步出现差异时，演示退出码非 0（`DIFFERENCES_FOUND` 不被吞掉）。
5. 演示不得写输入根/凭证/银行/账务/Gate/历史；新增输出只写本次 `--out-dir`。

## 4. 证据

- 单命令演示：`.venv\Scripts\python.exe -B scripts\run_runtime_demo.py --out-dir data\runtime_initial_judgment_recording_tests\task046_demo_01` → **exit 0**，`demo_summary.json` 含四相符摘要；记录耗时（本机约 2 分钟级，非性能结论）。
- 负例：把 `--evidence-input` 指向 v1（P02 缺证）→ 账证 2 条 `MISSING_VOUCHER`、演示退出码非 0；把输入版本改为未知 → 契约 `MANIFEST_VERSION` 拒收、演示非 0。原输入不改（副本注入）。
- 既有四 CLI（正常/内容反例/台账替换/末次读后漂移）在新代码下重跑仍 0/1/1/1。
- 只读：演示前后 v1/v1.1、账务 normalized/started/artifacts 字节不变。

## 5. 保护与停止

定稿后一次全树扫描，基线 = TASK-045 接受基线：相对该基线**既有 changed 恰为 §1 四件**（新增内容逐文件登记），其余均为新增；missing/读取错误/未登记新增/身份漂移 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不改看板、不推进账账/账表或 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；演示仍为合成数据，不证明凭证/流水真实，不构成审计结论。
