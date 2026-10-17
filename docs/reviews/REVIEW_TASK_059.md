# TASK-059 独立验收（DSH Architect）

结论：**NOT_ACCEPTED**（测试不可重复运行，1 类缺陷；引擎本身通过独立复验）。2026-10-18，DSH 架构/测试验收端对"一键对账启动器"独立复验。

## 1. 通过的部分（引擎功能）

- **正常**：我用新 run-id `task059_dsh_run_01` 运行 → **exit 0、overall=SUCCESS、七步全 0、read_only_ok=true**；`index.html`、`gl/gl-checks.html`、`excel/证据链底稿.xlsx`、`logs/`、`run_summary.json` 齐全。
- **失败即停**：task043 输入缺文件 → **exit 1、failed_step=input_contract、无 index.html**；GL 非法 JSON → **exit 1、failed_step=gl_contract、无 index.html**。
- **拒绝覆盖**：同 run-id 再跑 → **exit 2**。
- **确定性**：两个 run-id 的 `index.html`、`gl-checks.html`、底稿 **字节相同**。
- **只读**：批次、task043 输入、GL 包、账务库前后哈希一致。
- **启动器/配置**：`一键对账.cmd` 含 `run_all.py`、`chcp 65001`、`pause`；`config/run_all.json` 路径全部可解析。

## 2. 缺陷 B1（测试不可重复运行）

用现有工作区（`outputs/` 已有 `task059_run_01` 等）重跑 `tests/test_run_all.py`：

```
cases_total=6, cases_passed=2, status=FAIL
失败：normal / bad_input / bad_gl / determinism
normal 的 observed.outputs=null
```

原因：测试内部使用**固定 run-id**（与 `outputs/` 中已存在的目录相同），重跑时被"目录已存在 → exit 2"挡住；bad_input/bad_gl/determinism 同理。测试首次在干净工作区能过（执行端 6/6），但**任何再次运行都会失败**，不满足"测试可重复运行"，也会让后续全链回归误报。

## 3. 处置

- 本卡不发布接受基线、不更新 review_result；
- 发 **TASK-059-R1**：测试改用**临时 out-root + 每次唯一 run-id**（或等价隔离），保证在已有 `outputs/` 的工作区连续跑两次都 6/6；引擎行为不变；
- 修复后我重跑：两次连续 6/6 + 我的独立七步/负例/确定性/只读复验。

## 4. 边界

一键运行只做机器核对与出页，不构成审计结论或终判；不联网、不安装依赖；`real_approval=null`、真实初判未保存、0008、`next/AI=false`。
