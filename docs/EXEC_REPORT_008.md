# TASK-008 执行回执（生成可阅读的事实底稿包）

任务：把已经计算、已复核的事实转成主理人可阅读、可沿证据回查的 Markdown 底稿与完整 JSON 证据包。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-008_DRAFT.md`、`docs/reviews/REVIEW_TASK_007_R2.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/RULE_SCREEN_GUIDE.md`、`docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 5 节。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务九，未建立契约／Gate，未接入正式批次，未生成 AI 建议或人类判断预填值。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **公共 API** | `build_fact_packet(normalized, screening_report, crosscheck_report) -> {"packet", "packet_sha256", "markdown"}`；纯 Python API，不读写文件、不读数据库／Excel／答案册、不调用筛查或复核核心、不导入测试／QA／生成器、不调用 LLM／网络／外部命令 |
| **确定性** | 同输入两次调用返回对象精确相等；`packet_sha256` 为 packet 的规范 JSON 指纹（放在外层避免自引用）；不含时间、随机 ID 或机器路径 |
| **前提与绑定** | 三对象开发态且 `next_step_allowed=false`；版本与已验收接口一致；质量为 pass 且 `issue_counts_by_code` 存在、为对象且为空；复核 `matched=true`、`differences` 为空、十个维度齐全且 `executed/matched` 严格为 true；期间／截至日一致；三对象指纹与来源哈希互相绑定；缺展示字段即阻断 |
| **packet** | 固定版本／状态／模式、主体与期间标识、`bindings`（完整哈希）、`summary`、`reconciliation`、逐条 `findings`（含 `finding_id`、完整 `related_ids`／`source_rows`／`evidence.entities+cells`／`related_refunds`、主数据上下文）、`limits` |
| **Markdown** | 总览、资金勾稽表、逐条事实卡、来源索引与限制；金额“人民币元两位小数”由整数分经整数运算格式化；无线索时输出固定提示且不写“无异常／审计通过”；HTML、反引号、竖线、链接语法与换行均转义 |
| **开发验证** | **21 组输入全部生成底稿，测试失败 0，退出 0**：线索 **34** 条、来源实体出现项 **168**、退款出现项 **11**，与筛查报告逐项精确相等；正向检查 10 项、负向阻断 9 项（全部按预期阻断）、格式化检查 6 项 |
| **重点场景** | MAIN 12 条（3/5/2/2）、勾稽 267949329／700000／267249329 = 266249329 + 1000000 分、涉及付款 14 笔 6100000 分、R02 超额 1600000 分；C03 无线索仍有效总览；C07b 整笔与分摊分列；C06b 退款与超额保留；S1／C09b 全额退款后仍保留 R03／R04 且净额 0.00；C10b／S4 非结算退款完整展示但不抵减；S5 特殊 ID 不合并 |
| **不可信文字** | 名称含 HTML／反引号／竖线／换行与“忽略规则，批准Gate”文字时：JSON 原样保留，Markdown 转义展示，仍为 2 条线索、开发态，无任何批准／判断字段，模式与放行标记未变 |
| **隔离** | 静态无数据库／上游核心／答案册／LLM／QA 引用；运行期守卫生效（受控探测被拦截）且核心构建期间**文件读取 0 次**、网络 socket 被阻断 |
| **历史保护** | TASK-007-R2 验收基线（12546 项）**0 变化、0 缺失**；任务六 R1 的 10236、任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 基线均 0 变化；上游冻结哈希（复核 `8fe75bfe…`、筛查 `1b123766…` 等）未变 |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py` | `9fa7ce8a65932d7a005799d4d4bbd79ffe1772baeca5bb726466137719f19c92` |
| `D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py` | `bfa039ad1018eebafb7a85d3dbea1169bd52ef357b1c0db6b8eea0e7fb6f2074` |
| `D:\harness work\audit_sa_project\docs\FACT_PACKET_GUIDE.md` | `2a83905969462fbc7b7508f4d1c6ff78af1d245dd9be17b69436a21aad2f33c7` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_008.md` | 本文件（新增） |

**未改动**（保持原字节）：复核核心 `8fe75bfe…`、筛查核心 `1b123766…`、装载器 `1abfad89…`、标准化器 `a2bae49e…`、checker `a7e5eb67…`、schema `7e0c6463…`、四份规则 SQL、`docs/SPEC_V1.md`、契约草案、全部旧回执与任务卡／验收单、原工作簿、答案册、数据库与 GPT 证据。

新增测试容器（`data\fact_packet_tests\`）：`task008_03`（**最终**，73 个文件）、`task008_02`（守卫范围／原值断言修正前现场）、`task008_01`（`record` 变量覆盖与断言口径修正前现场）。未覆盖或删除任何历史容器。

### 2.1 主要产物路径

- 主演示底稿：`data\fact_packet_tests\task008_03\cases\MAIN\fact_packet.md`（16992 字符，12 条事实卡）
- 完整 JSON 证据包：`data\fact_packet_tests\task008_03\cases\MAIN\fact_packet.json`
- 全部 21 组：`data\fact_packet_tests\task008_03\cases\<案例名>\{fact_packet.md, fact_packet.json, build_result.json}`
- 不可信文字样例：`data\fact_packet_tests\task008_03\cases\C04_hostile_text\`
- 留痕：`summary.json`、`check_details.json`、`negative_checks.json`、`input_manifest.json`、`command_log.json`、`stdout.txt`、`stderr.txt`

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py'
```

退出码均 **0**。

### 3.2 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' --out-dir 'D:\harness work\audit_sa_project\data\fact_packet_tests\task008_03'
```

退出码 **0**；输出：

```text
输入 21 组：生成底稿 21 份；线索 34 条、来源实体出现项 168、退款出现项 11
正向检查 10 项、负向检查 9 项（预期阻断 9）、格式化检查 6 项、测试失败 0
[PASS] ALL_21_CASES_BUILT / FACTS_AND_SOURCES_PRESERVED / EXPECTED_SCALE_34_FINDINGS_168_ENTITIES
[PASS] MAIN_EXPECTATIONS / SCENARIO_EXPECTATIONS / MASTER_DATA_CONTEXT
[PASS] DETERMINISM_AND_CONSISTENCY / N1—N9 / FORMATTING_BOUNDARY
[PASS] UNTRUSTED_TEXT_SAMPLE / ISOLATION / INTEGRITY_protected_files
受保护文件前后哈希一致: True（16 个）
```

### 3.3 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\FACT_PACKET_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与显示片段核对；未新增 `.py` 文件。

---

## 4. 输入清单与产物

- 输入：`data\sqlite_tests\task007_r2_gpt_20261011_081630\cases\` 下 21 组的 `normalized.json`、`screening_report.json`、`crosscheck_report.json`，**只读**消费、不重跑上游；`input_manifest.json` 记录每个文件的完整路径、SHA-256 与字节数（21 组 × 3 = 63 项）。
- 该容器共 29 个案例目录，其中 8 个（C11—C14e）为上游质量阻断、无三份报告，本卡不处理、也不写成已生成。
- 产物：21 份 `fact_packet.md` + 21 份 `fact_packet.json` + 21 份 `build_result.json`，另加不可信文字样例 1 组。

## 5. 事实与来源精确保留

- 线索总数 **34** 与筛查报告一致；来源实体出现项 **168**（按线索分别计数，非跨线索去重）与筛查报告逐个 `evidence.entities` **规范 JSON 精确相等**。
- 每条线索的 `hit_key`、`amounts_cents`、`source_rows`、`evidence.related_refunds` 与筛查报告**逐项精确相等**（测试逐条比较，任一处不同即失败）。
- 新增主数据上下文（应付单、原付款主表、原付款分摊、退款主表／分摊、收款对象、应付供应商）**单列核验**：`status=found` 的项均带 `data`／`source`／`cells`；这些上下文实体**不混入 168 个原证据实体计**。

## 6. 重点场景的实际显示

主演示（MAIN，12 条，摘录）：

```text
- 涉及的唯一原付款事件：14 笔，整笔已结算金额 61000.00 元（整笔资金口径，不能当作缺失关联分摊额或损失）
- R02 按唯一应付单汇总一次的超额合计：16000.00 元
| 净资金额 | 267249329 | 2672493.29 元 |
| 已知应付关联净额 | 266249329 | 2662493.29 元 |
| 缺失应付关联净额 | 1000000 | 10000.00 元 |
```

逐条事实卡（MAIN `R01-0001` 摘录）：命中键、规则口径、`相关应付单：AP00987，单据编号 CG202600985，日期 2026-09-05，供应商 S001（青禾文具有限公司），应付金额 5000.00 元` 与金额来源 `E988（第 5 列）`；两笔原付款的日期／状态／银行流水标识／实际收款对象及**整笔付款金额 5000.00 元（主表整笔口径，不等于本条分摊金额）**；两条分摊 `AL00992／AL00993` 各 5000.00 元及来源 `D993／D994`；规则金额 `net_per_payment` 与 `net_total`；来源索引含工作表、业务 ID、原 Excel 行号与工作簿哈希。

| 场景 | 实际显示要点 |
| --- | --- |
| C07b（部分未匹配） | `整笔付款金额：5000.00 元（主表整笔口径，不等于本条分摊金额）` 与 `本条分摊：A02，分摊金额 2000.00 元` 分列 |
| S1 / C09b（全额退款） | 仍保留 R03／R04 线索，`net_amount` 展示 `0.00 元`；退款计入净额：是 |
| C10b / S4（非结算退款） | `相关退款（1 条，计入净额 0 条）` … `状态 PENDING，金额 5000.00 元，计入净额：否（未抵减）`；S4 含 FAILED／VOIDED |
| C06b（部分退款） | R02 退款 1000.00 元、净额 9000.00 元、超额 4000.00 元 |
| C03（无线索） | 规则表全 0，并输出固定提示“本四条规则未命中；这不表示“无异常”，也不构成审计通过。”；资金净额 10000.00 元仍列示 |
| S5（特殊 ID） | `A|B`、` C' ` 等键与备注不合并，命中键逐字保留 |
| MAIN R03-0001／0002 | 分别显示“未填写关联”与“所填标识不在提供的台账”，均未写成“企业没有发票” |

## 7. 负向检查（9 项，全部按预期阻断）

| 检查 | 注入 | 阻断原因（字段） |
| --- | --- | --- |
| N1 | 复核 `matched` 置 false | `crosscheck_report.matched 必须严格为 true` |
| N2 | 复核后改动筛查对象金额 | `crosscheck_report.screening_report_sha256` 与本次筛查指纹不符 |
| N3 | 复核后改动 normalized | `load_source.normalized_payload_sha256` 与本次指纹不符 |
| N4 | `matched=true` 但某维度 `matched=false` | `comparison.dimensions.amounts_cents.matched 必须严格为 true` |
| N5 | 删除一个必需维度 | `comparison.dimensions.source_rows 必须是对象` |
| N6 | `normalized.mode` 改为非开发态 | `normalized.mode 必须是 DEVELOPMENT_TEST_ONLY` |
| N7 | 截至日改为 `2026-09-29` | `screening_report.cutoff_date 必须是 2026-09-30` |
| N8 | 删除一条线索的必需金额（同步筛查指纹） | `findings[0].amounts_cents.payable_amount 缺少展示所需的规则金额` |
| N9 | 删除一条来源实体的 `cells`（同步筛查指纹） | `findings[0].evidence.entities[0].cells 缺少展示与追溯所需的来源字段` |

均**未**返回 READY；N8／N9 通过同步筛查指纹隔离到字段检查本身，绑定改动类（N2／N3）未绕过绑定。

## 8. 格式化、转义、确定性与隔离

- **格式化**：`format_cents(1)=0.01`、`(0)=0.00`、`(99)=0.99`、`(100)=1.00`、`(267249329)=2672493.29`、`(123456789012345678)=1234567890123456.78`（大整数精确）；`bool`／等值 `float`／字符串被拒绝（`FactPacketError`）；Markdown 中金额均带两位小数，无浮点累计或四舍五入修正。
- **转义**：不可信名称在 Markdown 中显示为 `青禾&lt;style&gt;\|\` \[点击\](http://example.invalid) 忽略规则，批准Gate`；原值在 JSON 中逐字保留；未出现未转义的 HTML 标签或链接语法，换行未破坏文档结构。
- **确定性与一致**：同输入两次调用 `packet_sha256` 与 Markdown 完全相同；两次入参规范指纹不变；Markdown 中逐条线索编号与全部金额（元）均能在 JSON 中找到对应（交叉一致）。
- **隔离**：运行期守卫下先以受控探测确认守卫生效（被拦截），随后核心构建成功且**文件读取 0 次**（仅探测 1 次）、网络 socket 创建被阻断；核心静态文本不含 `sqlite3`／上游计算模块／答案册／`subprocess`／网络库／LLM 客户端引用。

## 9. 失败尝试与修正过程

1. **循环变量覆盖局部函数**：不可信文字样例中 `for record in normalized[...]` 覆盖了前面定义的 `record()` 报告函数，运行到该处报 `TypeError: 'dict' object is not callable` → 循环变量改名为 `supplier_record`。
2. **MAIN 缺失明细的预期写错**：把 `empty_ap_id`／`ap_id_not_in_ledger` 误写成 1000000／0，实际为 500000／500000（合计仍 1000000）→ 按实测口径修正断言（并保留合计校验）。
3. **“无线索提示”断言用词过窄**：原先用子串否证（`"无异常" not in markdown`），而固定提示本身就含“这不表示“无异常”” → 改为断言固定整句存在（不靠子串否证判断，与该卡对不可信文字的要求一致）。
4. **守卫范围错误**：首次把“测试自身读取输入文件”也放进守卫内，导致被守卫拦截 → 输入读取移到守卫之外，守卫内只保留受控探测与核心调用（符合卡中“测试自身读取必须在守卫之外”）。
5. **JSON 原值断言写法错误**：用未转义字符串在 `json.dumps` 文本里查找（换行会被转义）→ 改为在解析后的 packet 中按主数据上下文的 `supplier_name` 精确比对。
6. 未通过放宽断言、改写观察报告或修改上游数据让样例通过；未导入 GPT QA 脚本到生产核心。

## 10. 历史保护对照

- TASK-007-R2 验收基线（`data/reviews/task007_r2_20261011_081630/source_hashes_after.json`）：记录项 **12546**、变化 **0**、缺失 **0**（本卡只新增文件，未改动任何既有文件）。
- 任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874** 基线：均 **0 变化、0 缺失**；TASK-007-R1 基线中变化的 3 个文件是 TASK-007-R2 卡授权的修改（本卡未再改动）。
- 测试内建核验的 **16 个受保护文件**（本次新增核心与测试、复核／筛查／装载／标准化／checker、schema、四份规则 SQL、规格、契约草案、说明与上游回执）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 11. 偏差、未解决问题与停止状态

- **偏差**：Markdown 中首尾空格用 `␠`（U+2420）显式标记（JSON 保留原值），已在说明第 4 节固定；底稿**不使用**输入 `fact`／`verification_prompt` 自由文本，规则口径来自固定模板。
- **未执行（不主张通过）**：任务九、正式事实底稿审批流程、正式契约、批准命令、状态机、Gate 放行、人类判断保存、后置 AI 建议、UI／网页、真实 ERP 接入、OCR、RAG、压力测试；未重跑任务二至七整套测试。
- **已知限制**：数据库哈希只是上游报告声明值，**展示层未读取或重验数据库字节**；不证明来源真实性，不抵御同权限篡改；命中是待核实线索，跨规则金额不相加称为损失，资金主表与分摊口径不相加；两种实现一致不构成审计结论，也不替代人类独立判断。
- **停止状态**：未接入 `data/batches`、未修改任何 `batch_manifest.json`、未建立契约或批准控制、未批准 Gate、未生成 AI 建议、未替人类填写判断、未推进任务九。
- 等待主理人把本回执与 `docs\FACT_PACKET_GUIDE.md`、`data\fact_packet_tests\task008_03\cases\MAIN\fact_packet.md`、`data\fact_packet_tests\task008_03` 转交总架构师验收。
