# 只读 Gate2 候审请求

实现：`scripts/runtime_gate1.py`，版本 `TASK-029-runtime-gate1-1.0`。

## 接口与停止点

```python
prepare_runtime_gate2_request(
    batch_dir, runtime_dir, request_id, *,
    scope_dir, event_relative, database_path
) -> {"request": ..., "request_sha256": ...}
```

调用前须已在当前运行版本完成登记、合成夹具 Gate1 APPROVE 保存和批准装载。路径参数沿用现有运行层规则；`event_relative` 是项目相对路径，`request_id` 是原样保留的非空字符串（可以是64位十六进制或含换行），不是事件或身份凭证。

接口全程只读，无 CLI，不创建目录、请求文件或 failure。它真实调用一次 `inspect_gate1_approved_load`；后者内部允许既有 Gate1/store.verify/P1 核验。准备本身不调用 store.save、normalizer、loader，也不运行筛查。既有七个 API 的前提与协议不变。

成功返回外层恰两键。`request` 恰六键：request_version、status、materials、expectations、evidence、boundaries。

- request_version：`TASK-025-human-gate2-runtime-request-1.0`。
- status：`RUNTIME_GATE2_REQUEST_PREPARED`。
- materials：冻结 P1 七键，gate=GATE2，共享登记 run_binding 和契约绑定。
- expectations：冻结八键；expected_prior_gate1 恰 gate/batch_id/event_id/record_fingerprint/run_binding 五键，取本次核验的完整 Gate1 记录。
- evidence：现有七键；五项来源说明来自本次核验的 context.request.evidence，两清单来自本次登记。
- boundaries：现有七键全部严格 false，包括 request_persisted、decision_recorded、execution_allowed、workflow_connected、ai_enabled、identity_authenticated、source_authenticity_proven。

PREPARED 不代表 Gate2 决定、批准、运行放行或审计结论；不会建立持久 RT_G2_PENDING 状态。真实批次批准仍 null、开发宿主仍0008、next/AI=false。

## 十项材料与摘要

files 每项恰 relative/file_sha256/byte_size，按 relative 的 UTF-8 字节序升序；relative 是固定逻辑映射，不供任意路径解析：

1. registry/runtime_registry.json → 登记叶 runtime_registry.json。
2. registry/runtime_registry_readback.json → 登记叶 runtime_registry_readback.json。
3. gate1/decision_result.json → 本次事件 snapshots/decision_result.json。
4. source/batch_manifest.json → 批次 batch_manifest.json。
5. source/quality_report.json → 批次 checks/quality_report.json。
6. load/started.json → 同级 load 叶 started.json。
7. normalized/normalized.json → load 叶 normalized.json。
8. load/load_report.json → load 叶 load_report.json。
9. load/artifacts.json → load 叶 artifacts.json。
10. sqlite/runtime.sqlite3 → 本次显式、已核验 database_path。

文件 SHA 取确切原始字节，byte_size 为严格非负整数。expected_files 沿用 P1 形状：逻辑 relative 到文件 SHA 的十项字典，与 files 双向完整一致。

材料正文只删除顶层 materials_fingerprint；指纹是正文 canonical JSON 的 SHA-256。request_sha256 是完整 request 的 canonical 指纹。canonical 统一 UTF-8、ensure_ascii=False、sort_keys=True、separators=(",", ":")、allow_nan=False。文件 SHA 不替代对象指纹。

Gate1、登记、装载六项运行绑定必须规范相等；Gate2 材料摘要与 Gate1 不同。代码清单仍14项，Gate1材料仍32项。quality 只在真实 inspect 成功后取 OK 与三个空列表。结果深拷贝，不生成 actor/event_id/决定时间/原因，不预填判断。

## 读取、末端和异常

调用 inspect 前，以本次同缓冲 capture 固定八份批次来源、两份登记、八份事件文件、四件装载产物、数据库、自脚本及静态文件。inspect 的 artifacts、文件 SHA、Gate1完整记录和运行绑定与这些起始读数闭合。

全部解析、对象构造、摘要计算和返回对象深拷贝之后，复用 `_confirm_approved_terminal` 确认起始字节、固定目录集合、failure/锁不存在及逐级 reparse；之后直接返回，不再解析候选或加载核心。没有“新 capture 与自身比较”的末端预期。

协议/路径/前提失败复用 RuntimeGate1Blocked(field, reason)，I/O 运行失败复用 RuntimeGate1Error(stage, reason) 并保留 cause。失败也不写诊断。

## 定点验证

```text
.venv\Scripts\python.exe -B tests\test_runtime_gate2_request.py --out-dir data\runtime_gate2_request_tests\task029_<新名>
```

测试只读复用 task027r1_run_04/batch_normal，按当前代码新建登记/已登记合成夹具 Gate1 事件/装载。正常准备两次、十材料独立核对、普通ID/无别名、最小前提反例、真实 inspect 返回后 DB/context LF 和 load 未知项构成四组。故意变更只作用于本轮自有文件，坏字节先保全，再精确恢复该原件或新注入文件的缺席状态；无递归删除、移动或目录清理。

完整观察与简短证据收尾只读复用冻结 `tests/test_runtime_approved_load.py` 的 helper，不修改该测试。原函数 code 对象 profile 与完整 wrapper 条目分列闭合；实际消费的 dict/list 引用在调用前、返回后、所属 API 收尾复测。直接 API 次数与内部调用不可相加冒充同一口径。

```text
... --out-dir data\runtime_gate2_request_tests\task029_<新收尾根> --replay <本轮正常证据根> --mutate none|candidate-return|ledger-late|checks-late
```

replay 读取冻结观察，不重复任何业务调用。两类字节注入发生在真实 finish 完成内容/台账消费、进入末端原始字节循环之后；候选返回替换由同一真实内容审核拒绝。期望不刷新，坏字节不回填，失败支配真实进程非零、磁盘 FAIL 与非空 failures。

真实链接设施、历史大套件及后续 Gate2 保存/筛查/初判/AI/终判未执行。历史139项损失、27项精确恢复、326项越界和19项命名偏差仍单列保留，不由本卡追认或重建。
