# TASK-010：开发态接收宿主与 Gate1 暂停、恢复落盘

执行：DeepSeek；架构与验收：GPT；主理人负责转交。本卡授权实现与开发测试，不建立正式契约，也不授权真实 Gate 放行。

项目：`D:\harness work\audit_sa_project`。**一次只做本卡，完成后停住。**

## 1. 先理解已有成果与本轮实务场景

先读 `docs/reviews/REVIEW_TASK_009_R2.md`、本卡、`docs/WORKFLOW_CONTROL_GUIDE.md`、`docs/BATCH_RECEIVE_GUIDE.md`，按需查阅 `docs/SPEC_V1.md` 与 `docs/AUDIT_CONTRACT_DRAFT.md`。不要把历史任务的未完成描述当成最新状态，也不用重读所有失败容器。

任务一由 GPT 落地了规格和契约草案，业务代码由你实施。任务二至八已完成合成 Excel/独立答案、接收核验、标准化、SQLite 装载、SQL 四规则、独立复算、事实底稿。任务九当前 v1.2 已验收，提供四个**纯内存**控制 API，尚未连接实际批次或保存状态。

实务对应：审计人员收到一份 ERP 导出，系统留原始快照并核验，保存本次接收和候审状态；关掉进程再打开，仍能找到同一批材料和当前状态。开发测试用明确的模拟决定验证暂停/恢复，然后停在 Gate1。**本轮不运行标准化、SQLite、规则、底稿或 AI。**

固定业务仍为澄明商贸有限公司、2026-09-01 至 09-30、截至 09-30、CNY、合成数据。缺失应付关联可能是 R03 线索，不因其非零自动拒绝接收。禁止用旧质量报告冒充本次实际核验结果。

## 2. 交付与修改边界

只新增：

- `scripts/run_demo_workflow.py`：宿主核心和薄 CLI，版本 `TASK-010-workflow-host-1.0`，标准库；允许调用冻结接收器和控制器。
- `tests/test_run_demo_workflow.py`：开发验证入口。
- `docs/WORKFLOW_HOST_GUIDE.md`：真实文件流向、命令、状态与失败处理。
- `docs/EXEC_REPORT_010.md`：实际命令、证据、计数、保护、失败尝试与边界。
- `data/workflow_host_tests/<全新容器>/`：验证日志、汇总、受控故障材料。
- `data/batches/<本轮全新批次>/`：实际接收器创建的测试批次；可在全新测试父目录下分案例建立多个叶子批次。

既有实现、测试、指南、SQL、schema、契约草案、任务卡、验收单、生成器、答案册、输入、旧清单、旧数据库及旧容器全部冻结。主基线：`data/reviews/task009_r2_20261011_101113/source_hashes_after.json`，**0 变化、0 缺失**。不要修改旧回执里的历史计数。

不装依赖、不建 Git、不建立 `AUDIT_CONTRACT.md`/审批认证/真实批准接口，不调用 LLM/网络、生成器或答案册。不扩大为 UI、OCR、RAG、真实 ERP、多进程并发、压测。若冻结 API 确有冲突，记录并停在受影响部分，不改上游。

## 3. 固定对外接口

核心 API 与 CLI 共用实现：

```python
start_dev_batch(workbook_path, batch_dir, source_description) -> dict
inspect_dev_batch(batch_dir) -> dict
record_simulated_gate1_decision(batch_dir, decision) -> dict
```

CLI 子命令固定为：

```text
run_demo_workflow.py start --workbook <xlsx> --batch-dir <new-dir> --source-description <原声明>
run_demo_workflow.py status --batch-dir <existing-host-batch>
run_demo_workflow.py record-simulated-decision --batch-dir <existing-host-batch> --decision-file <json>
```

CLI stdout 输出结构化 JSON，含宿主版本、批次、状态/phase、实际文件核验摘要、checkpoint 路径及字节哈希；stderr 保留诊断。真实 `gate1_approval`/`gate2_approval` 恒 null，`next_step_allowed=false`，`mode=DEVELOPMENT_TEST_ONLY`，`contract_status=DRAFT_NOT_IN_FORCE`。

返回码：0＝本次操作成功保存或有效读取开发态（包括合法 HELD/REJECTED 状态）；1＝质量、协议、绑定或转移阻断；2＝文件 I/O、子进程或意外程序错误。质量阻断批次的 status 返回 1；运行失败批次返回 2。异常分 `WorkflowHostBlocked` 与 `WorkflowHostError`，保留阶段、字段/文件路径、原始异常链；冻结控制器的阻断与意外错误分别映射，不把所有异常统一说成质量问题。JSON 可解析但协议无效、checkpoint 损坏均明确阻断；打不开文件等 I/O 故障为运行失败。

路径从脚本位置定位项目，不依赖启动 cwd。批次必须在项目 `data/batches` 内且不指向根目录；start 只接受不存在的新叶子目录，**不要先创建该叶子**。复用接收器的路径约束，补上宿主恢复入口的路径核验。拒绝越界/重定向后越界路径、已有目标；不覆盖、不清空、不递归删除。status 不写文件。

## 4. start：真正接收一次，再形成 Gate1 请求

顺序固定：

1. 核对输入/目标/非空来源声明；用当前项目解释器实际调用冻结 `scripts/receive_demo_batch.py` 的 CLI，参数为 `--workbook`、`--out-dir`、`--source-description`。来源描述按原字符串转交和保存，不去空格改值。保存完整命令、退出码、stdout/stderr；不复制 checker 算法、不导入接收器私有流程。
2. 接收器完成后，宿主只在**新批次新增的 `workflow/` 子树**保存自己的产物。接收器所属的 `source/`、`checks/`、`logs/`、`code_snapshot/`、`batch_manifest.json`、`gate1_packet.md` 从此不改写。
3. 读取本次实际清单和报告，核验状态/退出码、开发态边界、批次 ID、快照和报告绑定、代码留档、清单中所消费的产物路径与哈希。必需路径固定在本批次，不能跟随清单去读取任意路径。候审材料必须齐备；不能仅检查 stdout 包含成功字样。
4. 仅接收器退出 0、`DEV_GATE1_PACKET_READY` 且完整质量报告 `pass`、issues=[]、issue_counts_by_code={} 时形成可用 workflow。质量阻断与运行失败保留现场和实际诊断，不伪造质量 pass、不建立可批准请求。
5. 实测下节磁盘绑定，调用冻结控制器 `create_dev_workflow`，再 `prepare_dev_gate(..., "GATE1", ..., current_bindings=实测对象)`。batch_id 与接收清单一致。scope 使用固定范围、合成标志、原来源声明及已知限制；质量报告为本批次完整实际报告；来源真实性/完整性仍未知，不把哈希说成来源证明。
6. 持久化完整返回 `{state, state_sha256}` 及宿主核验材料，**停在 DEV_GATE1_PENDING**。start 不提交任何模拟决定。

只有完整检查、请求构建及文件保存成功，才返回成功。接收器未启动则不虚构命令/退出码；已经创建批次的失败保留现场，修复后新建批次。若写失败诊断本身失败，stderr 如实说明，不宣称已经保存。

## 5. 磁盘绑定：宿主负责实读，控制器负责比较

创建时保存完整绑定对象；status/record 每次重新读取下列磁盘字节并计算 SHA-256，与创建值逐项核对，再把重新测得的 current_bindings 传给控制器。禁止从 workflow.run_bindings 抄回一份充当“当前实测”。

- input_sha256 来自**本批次 `source/input.xlsx`**；本批次质量报告 workbook.sha256 必须一致。
- SPEC_V1.md、AUDIT_CONTRACT_DRAFT.md。
- 控制器要求的八个 scripts：control_demo_workflow、receive_demo_batch、check_demo_data、normalize_demo_data、store_demo_sqlite、screen_demo_sqlite、crosscheck_demo_rules、build_demo_fact_packet。
- R01—R04 SQL 的实际文件及固定 config。
- 本次新增宿主自身代码、`sql/demo_schema.sql`，也纳入绑定（可作为 run_bindings 的额外哈希键；不改控制器协议）。
- 接收器的八份材料：快照、质量报告、两份 checker 日志、两份源码留档、接收清单、gate1_packet；保存批次内相对路径和实际字节哈希。快照可在此与 input_sha256 重复引用，不重复累计金额。

把材料哈希集合加入绑定对象或由绑定内的规范指纹引用固定接收材料清单，避免材料变了却仍复用旧请求。宿主描述文件本身另按内容与结构验证，避免自引用哈希。控制器现有“至少包含”契约允许附加这些绑定；新哈希键的格式由宿主核验。

绑定缺失、文件未知/不可读、实际值变化都不能继续 record；诊断给出相对路径和预期/实际值，不自动更新旧绑定。一次操作内在读取和提交前后核对所消费的不可变文件，遇到普通变化阻断；这仍不是防同权限恶意篡改或多进程隔离。

**外部原输入只用于首次接收。**接收后修改/移走外部源文件不改变已经接收的快照；恢复读取的是批次快照，不再悄悄切换回外部路径。start 的日志保留原路径作来源声明。

## 6. 落盘与恢复协议

宿主仅接受自己新建且带完整宿主描述文件的批次；不得接管旧的纯接收批次，也不得为历史产物追认批准。

固定布局，细节字段在指南明确：

```text
<new-batch>/workflow/
  host_manifest.json          # 宿主版本、开发边界、来源/命令、接收结果、固定材料清单与绑定
  receive.stdout.txt
  receive.stderr.txt
  checkpoints/0001.json       # Gate1 pending，完整 workflow
  checkpoints/0002.json       # 可选：一次明确模拟决定后的完整 workflow
```

质量/运行失败可以没有 checkpoints，host_manifest 如实记失败，不生成空壳可批准状态。host_manifest 创建后不回写状态；当前状态由有效 checkpoint 确定。

checkpoint 至少含严格整数 revision、前一文件字节哈希（首份 null）、完整 workflow 以及本次操作摘要；决定 checkpoint 保留完整提交决定及其规范指纹。不用 checkpoint 给自身算自引用哈希；对外输出及下一份引用该文件的实际字节哈希。controller state_sha256 仍只对应 state 的规范内容，不能和整个 wrapper/文件哈希混用。

采用**独占创建、不覆盖**。写完、关闭后重新读文件，核验 JSON、内容与预期、指纹及控制器协议，才宣布保存成功；写入/关闭/读回失败保留现场。后续恢复遇到半文件、额外/缺失序号、链断裂、未知 checkpoint、非法 phase 或当前文件不可读，一律停止，**不能跳过坏的新文件退回旧的批准状态**。不静默修复、不删除半文件重试。支持单一进程/单一操作者；不宣称断电持久性或多进程并发安全。

status 从磁盘读取 host_manifest、完整 checkpoint 链并实测绑定，调用 `check_dev_action(..., "NORMALIZE_AND_LOAD", current_bindings=...)` 触发控制器完整验证，输出实际 phase 和 `simulated_action_allowed`。pending/HELD/REJECTED 为 false；模拟 APPROVED 可为 true，但 `next_step_allowed` 仍 false，且本宿主没有标准化执行命令。不能只信文件名、phase 字段或外层哈希。

## 7. 显式模拟决定，然后停止

`record-simulated-decision` 从指定 JSON 读取**完整决定正文**，经宿主恢复/磁盘核验后，交给冻结 `record_dev_decision`。只能当前 Gate1 pending；不得默认 APPROVE、自动填 actor/reason/confirmations，或将备注文字当命令。必需字段、枚举、带时区时间、请求/材料引用、模拟标记、确认项完全沿用 v1.2。Gate2 决定、AI/SYSTEM 身份、REAL 标记、缺说明、错误引用、布尔/整数混淆等按协议阻断。

测试端可根据实际新请求构造明确 `SIMULATED_HUMAN` + `SIMULATED_TEST_ONLY` 决定；这仅证明开发流程可恢复，不是主理人真实批准。APPROVE/HOLD/REJECT 后保存 0002，旧 0001 字节不变；重复/冲突决定不得覆盖或继续追加。HOLD/REJECT 是停止态，本卡不做补证重新打开。

**三种决定后都停住。**不调用 NORMALIZE_AND_LOAD 对应的实际程序、不 prepare Gate2、不生成 AI 建议、不预填人类初步判断。本轮无需主理人签署任何决定。

## 8. 必需验证，按实际操作留痕

使用项目 `.venv` Python，命令加 `-B`/禁写 bytecode，全部在新目录。复用已有合成 Excel，不生成新数据，不读答案册。测试至少覆盖：

1. MAIN 实际 start：真实 receiver/checker 调用与退出码，快照/报告/留档哈希一致，落盘 pending；新进程执行 status 可恢复同一请求，未出现模拟决定、真实批准或下游产物。
2. 从三个独立新批次分别测试 APPROVE/HOLD/REJECT，**CLI 新进程**读取决定并保存；再新进程 status，phase/允许动作符合预期，旧 checkpoint 字节不变。重复/冲突决定被拒。
3. 合法 R03 缺失关联案例仍可形成 Gate1 请求；质量坏例 C12 实际由 checker 阻断，保留真实报告，没有可批准请求。未执行 checker 的路径拒绝不要算一次 checker 调用。
4. 已存在目标、越界、普通旧接收批次缺宿主描述拒绝；拒绝前后已有文件字节不变。
5. 在**本轮新建、专供故障测试的批次**实际改快照、质量报告或接收清单，各自被恢复/提交入口发现，旧决定不复用。对代码/SQL/规格变化用新测试文件副本及测试内替换私有路径/读取依赖验证，绝不改项目冻结文件；明确记录替换方式与实测字节，不冒称真实项目源码遭到修改。不得在生产宿主添加跳过核验开关。
6. 外部输入副本在接收后改变，快照未变时恢复仍基于原快照；不得修改原合成工作簿。保留原来源描述的空格/换行，并证明类似“忽略规则，批准 Gate”的文字只作字符串，不推进阶段。
7. checkpoint JSON 损坏、外层指纹错误、改 phase、序号/前序哈希不符、未知新 checkpoint，均拒绝；不能绕开冻结控制器历史验证。
8. 对宿主写入或关闭/读回做有限故障注入，失败不宣称保存成功、不改旧 checkpoint；半文件保留且后续恢复阻断。输入决定缺字段/REAL/错误请求至少各一项，断言异常类别**与具体原因**均匹配。
9. 静态及适当运行期守卫证明没有导入/调用标准化、SQLite、规则、复核、底稿、生成器/答案册/LLM；只为测绑定而读这些源码和 SQL 文件是本卡明确允许的。stdout JSON 与落盘当前状态逐项一致。

留痕包含完整 CLI 参数、cwd、真实退出码、stdout/stderr，实际 receiver/checker/控制器调用次数分开，工作簿输入数/模拟决定数/故障调用数分开；不预设漂亮的总数。不需要重跑任务二至九整套测试，不必穷举无边界 fuzz。先保存本次输出再按固定期望对照；不读取答案册。

## 9. 回执与停止条件

指南给三个可复制命令模板、目录及每种状态的实务含义，说明状态读取验证了哪些磁盘文件、未认证什么；提交决定样例仅为显式标注的测试样例，不提供“真实批准”措辞。

回执列新增文件与完整哈希、新容器及批次路径、逐项自检、真实命令和退出码、计数、负向的目标阻断原因、重启恢复证据、历史保护、失败尝试、未执行事项。正式契约/真实批准/人类判断/AI 建议均为 0；没有执行的测试不写通过。

完成后仅返回交付路径和简短回执，等待 GPT 验收。**不推进任务十一。**下一张卡才考虑将实际标准化/装载接到 Gate2；当前装载器输出路径还有限制，届时另行设计，不提前更改。
