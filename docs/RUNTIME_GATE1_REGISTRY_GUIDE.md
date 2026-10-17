# 共享运行登记与只读 Gate1 候审请求使用指南（TASK-026）

适用范围：`scripts/runtime_gate1.py`（新运行层第一段）。**本文不构成任何批准**；
登记不是决定，`RUNTIME_GATE1_REQUEST_PREPARED` 不是批准，两者都不赋予任何执行许可。

## 1. 本层做什么、不做什么

| 做 | 不做 |
| --- | --- |
| 核验接收批次来源（真实调用冻结准备器一次） | 保存 Gate1 决定、生成 submission、接受任何人类字段 |
| 独占固定本批次共享运行登记（两份文件） | 调用冻结 P1 公开入口、store、标准化/DB、Gate2 |
| 只读恢复登记并核对内部关系 | 运行筛查/复算/事实底稿/初判/AI/终判 |
| 只读构造 Gate1 候审请求（六键） | 创建决定记录目录、SQLite 目录、运行 profile、宿主检查点 |

## 2. 三个公开 API（无 CLI）

```python
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)
    -> {"registry", "registry_sha256", "registry_file_sha256"}      # 恰三键

read_runtime_registry(runtime_dir)
    -> {"registry", "registry_file_sha256"}                         # 恰两键

prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)
    -> {"request", "request_sha256"}                                # 恰两键；调用方先取 ["request"]
```

- `batch_dir`：冻结接收器认可的**新接收批次**目录（`data/batches/` 内严格后代，恰八文件）。
- `runtime_dir`：**显式技术输出路径**，必须是 `data/runtime/` 的严格后代，且**从未存在**的新叶
  （空目录也拒绝）；`data/runtime/<runtime_name>/` 由调用方指定，**不由业务 ID 拼接**。
- `scope_dir`：`data/human_gate_decision_records/gate1/` 的严格后代、**尚不存在**的计划技术路径
  （创建它的动作属后续保存层）；本层只登记其**项目相对路径引用**，**不创建、不写入**。
  **已存在的 scope 一律拒绝**（包括空目录），以免把旧历史绑定到新的运行版本。
- `request_id`：非空字符串，**原文保留**（允许前导零、换行、64hex 外观；不 strip、不转数字）。

## 3. 异常分类

| 异常 | 含义 | 处理 |
| --- | --- | --- |
| `RuntimeGate1Blocked(field, reason)` | 类型/协议/来源/路径/既有目标/不一致 | 修正输入后重试；**不要**重试同一输入 |
| `RuntimeGate1Error(stage, reason)` | I/O 或运行故障（保留 `__cause__`） | 检查环境；失败现场保留，不覆盖 |

`field` 与 `stage` 用于定位。冻结准备器的拒绝**保留其原始定位与原因**（映射为
`prepare.<field>` / `prepare.<stage>`），不会被吞成成功。

## 4. 磁盘产物

成功叶目录**恰两份文件**：

- `runtime_registry.json`：登记对象本体（13 键），canonical UTF-8 + 单个 LF。
- `runtime_registry_readback.json`：恰五键
  `readback_version / registry_sha256 / registry_file_sha256 / registry_byte_size / run_binding_sha256`；
  不含自身哈希。

失败（叶目录已创建之后）在**本次新叶**独占写 `failure.json`，恰五键
`failure_version / stage / field / reason / cause_chain`。创建叶之前的拒绝**不留输出**。
`read` / `prepare` 全程只读；发现 `failure.json` 即拒绝。

登记 13 键：`registry_version, batch_id, registered_at, scope_ref, batch_files, code_manifest,
rules_manifest, config, input, contract, run_binding, run_binding_sha256, note`。

- `batch_files`：恰 8 项 `batch/...` 逻辑相对路径（与批次八文件一致，逐项长度/文件 SHA）。
- `code_manifest`：恰 14 项 = 冻结 13 项代码 + **本脚本自身**；每项仅 `relative/file_sha256`，
  项目相对路径无 `project/` 前缀，按 UTF-8 升序唯一。
- `rules_manifest`：恰 4 项，每项 `rule_id/rule_version/relative/file_sha256`。
- `config`：固定复用冻结 `config/human_flow_v1.json`（不另建配置）。
- `input`：`file_sha256/byte_size/input_ref`，`input_ref = "batch/source/input.xlsx"`。
- `contract`：冻结三键（`contract_file_sha256` 独立核验；人类已确认的生效时间不被规范化）。
- `run_binding`：六字段；`code.file_sha256` 为本脚本，`rules.version` 为规则清单版本；
  `run_binding_sha256` 只取内层对象；登记对象**不含自身指纹**，`registry_sha256` 由调用方从返回取得。

## 5. 候审请求（六键）

```text
request_version = "TASK-025-human-gate1-runtime-request-1.0"
status          = "RUNTIME_GATE1_REQUEST_PREPARED"
materials       = 冻结 P1 七键；files 恰 32 项（冻结准备器 31 项来源 + 本脚本）
expectations    = 冻结 P1 八键；expected_prior_gate1 = null；expected_request_id 原样绑定
evidence        = 冻结七键；code_manifest/rules_manifest 使用**本次登记**的完整对象
boundaries      = 冻结七键，且全部严格 false
```

- `materials.files` 中项目材料使用 `project/` 前缀，与清单通过固定前缀映射；
  **不得**加入旧 Gate1 适配器替代本脚本。
- 质量由真实冻结准备器映射：`OK` 与自洽 `BLOCKED` 均可形成候审请求（保留真实阻断列表）；
  `FAILED`、来源无法核验或材料不完整**不能**产生成功请求。
- 请求**不含**顶层 `batch_id/run_binding/contract/files/quality`，也不含夹具标记。

## 6. 来源变化的处置

`prepare` 自己实读登记与当前批次来源，逐项与登记绑定/冻结基线比较；代码、规则、配置、输入、
批次任何字节变化 → **阻断**，并指向具体目标（如 `registry_file_sha256`、`batch/source/input.xlsx`）。
**不**更新旧登记迎合新值；**不**用旧批准、旧摘要或旧请求对象补齐当前来源。

## 7. 权限与边界（当前状态）

真实批准仍 `null`、宿主仍开发态 `0008`、`next_step_allowed=false`、AI 未开放。
本层产物是**技术登记**与**候审请求**：`PREPARED` 不等于批准，登记不等于放行。
同权限的本地全面重写不在本层防御承诺内；身份声明非强认证。

## 8. R1 修正与早期入口记录（历史）

本节早期命令、计数和故障开关仅说明历史尝试，不作为当前入口或现存证据证明；现行收尾见§10。部分原始证据因§11事故缺失，不再宣称可读取。

- 三 API 都在**操作起始**以同缓冲字节固定读数，并在全部消费/复算之后做**一次**有界原始字节/
  集合/路径确认；之后直接返回，不再解析候选决定成功。
- `read` 完整核验 13 键与全部嵌套封闭键/严格类型/常量/排序/固定集合/派生关系，并核对**本次**
  代码与静态冻结字节；`lstat`/枚举等真实 I/O 失败映射为 `RuntimeGate1Error(stage)` 并保留原因链。
- 测试入口（本轮新容器，不复用旧现场）：

```text
.venv\Scripts\python.exe -B tests\test_runtime_gate1_registry.py \
    --out-dir data\runtime_gate1_registry_tests\task026r1_run_01
→ PASS / checks_total=70 / checks_failed=0 / audit_ok=true
```

  失败支配（R2 改为一套真实收尾，三个控制共用同一 main 与审核 helper）：

  | 控制 | 结果 |
  | --- | --- |
  | 正常 | 入口 0、磁盘 `summary.status=PASS`、`failures=[]`、`audit_ok=true` |
  | `--fault-check`（写盘前只改一项磁盘检查结果） | 入口 1、磁盘 `status=FAIL`、`failures` 非空 |
  | `--fault-payload`（只改一项已记录返回值内容） | 入口 1、磁盘 `status=FAIL`、`audit_failure.problems=['payload_content_mismatch:call_001']` |

  证据载荷全部纳入 `evidence_ledger.json`（含 `audit.json`、`audit_failure.json`、
  `final_confirm.json`）；`expected_audit` 在写盘前声明预期最终状态与预期问题，由审核行核对。

## 9. R2 补充（静态读数/集合/预检）

- 身份核验消费的代码/规则/配置/契约/准备器读数全部并入本次读数集合，与 registry/readback/自身
  字节一起在末端复测；来源核验声明的 **23 份既有 project 材料**逐份同缓冲实读并与声明闭合。
- 批次固定顶层（八文件中的顶层文件 + 四个固定子目录）与四个固定子目录（各自叶子集合）在
  build/prepare 末端按**集合相等**核验：多一项即拒绝。
- 恢复（read）额外预检：`registered_at` 必须是带时区的合法 ISO 8601 技术登记时间；
  `rules_manifest.entries[].rule_id` 必须是**非空字符串**（先判类型再做字典查询，不泄漏 TypeError）；
  `scope_ref` 指向的计划路径必须**尚不存在**（已存在即拒绝）。
- **read 也有末端计划 scope 检查**：在登记、静态绑定与自身字节全部消费并复测之后、返回之前，
  重新确认 `registry.scope_ref` 仍是尚不存在的技术路径；初始未存在而末端已存在即 Blocked
  （`registry.scope_ref`）。与 build/prepare 的末端检查一致。
- `_recheck_capture` 在比较当前磁盘字节之前，先对本次已消费路径调用 `_reject_reparse_chain`
  （原始路径逐级 lstat + resolve 复查），使静态绑定文件的路径状态同样被末端覆盖。

## 10. R3 收尾与两个模式

测试入口有两种模式，共用同一套冻结/写盘/末次审核/字节确认代码：

```text
# 1) 正常观察并定稿（业务只跑一次）
.venv\Scripts\python.exe -B tests\test_runtime_gate1_registry.py \
    --out-dir data\runtime_gate1_registry_tests\task026r3_run_01

# 2) 真实收尾重放（复用上面观察的独立副本；业务调用增量 0）
... --replay <只读观察来源> --out-dir <从未存在的新证据目录> \
    --mutate none|checks|payload|args|late-checks
```

- 独立期望来自写盘前冻结的本次实际观察内存深拷贝；`expected_observations.json` 仅是其落盘记录，不能再从该候选文件刷新审核预期。直接 API 记录含 args/kwargs/
  调用前读数/完整返回或异常链，嵌套冻结准备器记录每条完整输入与返回/异常，以及检查载荷。
  审核按 canonical 字节逐条比较完整记录，并核对独立完整ID集合，而不是只比返回指纹或候选自身计数。
- 台账期望取本次待写缓冲；七份载荷和台账自身在所有必要消费后逐项实读确认。已有检查失败、缺记录、候选预期文件改变或字节漂移都必须拒绝成功。
- 注入边界在**正常待写缓冲定稿并写盘之后、正式末次审核之前**：`checks` 改一项检查结果、
  `payload` 改一项完整返回、`args` 改一项输入、`late-checks` 在末次语义审核返回后追加字节。
- 任一审核失败/漂移：顶层返回 1、磁盘 `summary.status=FAIL`、`failures.json` 非空；
  坏候选保留，不重建期望或台账消除差异。
- `--out-dir`：任何 mkdir 之前先解析，必须是证据根的**严格后代**（拒绝 `..` 越界、同前缀兄弟、
  证据根本身），并保留原路径逐级 reparse 检查。
- 重放来源只读，输出必须从未存在；无论正常/重放均不覆盖旧目录，也不自动清理隔离目录。测试无需执行任何递归删除。

## 11. TASK-026-R3 证据删除事故

执行端误删旧证据树166个文件。GPT核对原基线及现存副本后，精确恢复27个字节/SHA完全相同的文件；其余139个登记为历史证据缺失。哈希清单不是备份，新复验不冒充恢复。原R3范围违规与保护失败结论保留，不改成missing=0。

处置、新复验和当前测试修正见 `docs/reviews/REVIEW_TASK_026_R3.md`；完整损失与恢复台账在 `data/reviews/task026_r3_gpt_20261015_043939/`。所有旧评审/回执原样保留。本事件处理不构成批次批准。
