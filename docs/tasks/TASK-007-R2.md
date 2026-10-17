# TASK-007-R2：补齐命中键的字符串类型检查

执行端：DeepSeek；验收端：GPT；主理人负责转交。项目：`D:\harness work\audit_sa_project`。

## 1. 当前状态与先读材料

依次读 `docs/reviews/REVIEW_TASK_007_R1.md`、本卡、`docs/tasks/TASK-007-R1.md`、`docs/EXEC_REPORT_007_R1.md`、`docs/RULE_CROSSCHECK_GUIDE.md`。需要业务口径时查原 TASK-007_DRAFT 与 SPEC_V1，不重设计架构。

R1 完整回归已经通过：29 输入、21 一致、8 上游阻断；20 差异、6 前提、确定性和隔离检查正确；34 条线索、168 个来源实体正确；上轮九个探针均已修复。本次仅处理 F01 残留：`_key_tuple` 用 str(value) 构造身份键，导致非字符串 ID 仍可错误 MATCHED。

GPT 没有修改生产代码。不要重写复算公式、比较层或上游模块；保留 R1 已通过的修复。

## 2. 修改范围

仅可修改三个既有文件：

- `scripts/crosscheck_demo_rules.py`：补命中键类型/身份比较，版本升为 `TASK-007-crosscheck-1.2`。
- `tests/test_crosscheck_demo_rules.py`：加入本卡配对回归及留痕，保留现有断言。
- `docs/RULE_CROSSCHECK_GUIDE.md`：说明处理方式、版本与新回归；结果字段表和页首统一为 1.2。

仅新增 `docs/EXEC_REPORT_007_R2.md` 和 `data/sqlite_tests` 下全新测试容器。旧回执、全部任务卡/验收单/GPT 证据、数据库、数据集、答案册、SQL、筛查/装载/标准化/checker、SPEC 和契约草案全部冻结。不安装依赖，不初始化 Git，不创建正式流程。

## 3. 实现要求

命中键的字段类型属于事实身份的一部分。不能通过 str(value)、map(str) 等转换使整数、bool、null 与字符串等同；用于显示或排序的字符串转换不能承担身份归一化。

可选择并固定其中一种处理方式：

- 在公共接口前提核对中明确拒绝命中键里的非法 ID 类型，抛 CrossCheckBlocked，原因包含字段路径、预期字符串及实际类型。此类调用不宣称已完成比较。
- 保留观察值及类型进行比较，返回明确 MISMATCH，hit_keys 等对应维度为 false，记录原始 expected/actual、类型及字段路径；非法类型不得继续合并为同一身份键。

选择与现有接口一致的最小实现即可。不允许通过转换输入、重写观察报告、跳过观察项或修改标准化数据来让错误对象 MATCHED。仍须保留漏报、多报、重复命中、规则身份和 S5 分组键不碰撞的检查。

所有规则的命中键 ID 均须遵守字符串契约：R01 的 ap_id/payee_supplier_id、R02 的 ap_id、R03/R04 的 allocation_id；rule_id 也保持原类型和值。合法的 `"1"`、`"True"`、`"None"`、`"0001"`、含空格/单引号/竖线的字符串 ID 均不能因外观被禁止或规范化。

本卡不要求建立新安全隔离，也不要求重新实现完整数据质量 checker。

## 4. 必须新增的配对回归

使用 C04 的内存对象，参照 GPT QA 的设置（可以阅读，不得导入 QA 到生产核心）：

`data/reviews/task007_r1_20261011_075928/key_type_probes.py` 及同目录 K01—K04 的完整输入/结果。

每组先建立合法正向控制：将相关 ID 在 normalized 和 screening_report 中一致地改为下列字符串，测试侧同步 load_source 与其 run_metadata 的 normalized_payload_sha256。正向控制必须 MATCHED。再深复制该 SQL 报告，只改一个 hit_key 字段：

1. R02：ap_id `"1"` → `1`（int）。
2. R02：ap_id `"True"` → `true`（bool）。
3. R02：ap_id `"None"` → null。
4. R01：payee_supplier_id `"1"` → `1`（int）。

四个负向控制均须按第 3 节固定选择得到 MISMATCH 或 CrossCheckBlocked，不能 MATCHED。证明正向控制与负向调用之间只有指定 hit_key 字段发生变化；类型比较不能只靠序列化后看起来相同的字符串。

同步指纹只发生在新内存控制对象；不得改旧 JSON/工作簿/数据库，不宣称这些样例有对应的新真实来源文件。保存每组正负输入、完整返回值或阻断原因、预期/实际类型与结果，不能只有 stdout 的 PASS 字样。

## 5. 回归、留痕和历史保护

在全新容器完整重跑当前 29 工作簿、20 差异、6 前提、2 确定性和1隔离调用，原有 50 次复核调用分类保持；再加入上述四组正负控制（8 次），正常预期合计 58 次复核调用。采用前提阻断时，新增四次应单列为命中键结构阻断，不混入工作簿质量阻断或初次 MATCHED。checker 仍29次、SQL核心仍21次。

原21输入、34条线索、168个实体、MAIN12键和1600000分不变；原有类型/退款/身份/诊断/质量前提检查不得删除或放宽。仍验证输入不变、确定性、隔离、答案册读取顺序。仅运行本任务链，不要求重跑任务二至六整套历史测试。

保护基线：

`data/reviews/task007_r1_20261011_075928/source_hashes_after.json`

除本卡授权三个文件外，变化/缺失必须为0；尤其旧 EXEC_REPORT_007/007_R1 和全部 GPT 证据保持。任务六R1的10236项以及8547/6511/4902/874项基线全部不变。新容器不能复用或覆盖已有目录。

EXEC_REPORT_007_R2 写明最小修复、完整哈希、真实命令/退出码、50次原调用与8次新增调用的分类、四组正负实测、历史保护、失败尝试及未执行内容。QA/回归退出0表示断言满足，不将预期阻断或MISMATCH写成MATCHED。

## 6. 停止条件

返回新回执、更新后的说明和新容器路径，停止等待 GPT 复验。不推进任务八，不接入 data/batches，不改 batch_manifest，不建立契约/审批/Gate，不创建人类判断表或 AI 建议。

主理人只需转交本卡和验收单，无需人工检测、预填判断或模拟批准。若发现规格矛盾，记录并停止受影响部分，不自行改变规则口径。
