# TASK-002-R1 复验结论

日期：2026-10-11；复验：GPT；执行：DeepSeek；主理人负责转交。

## 1. 结论

**R1 的主要修复有效，但 TASK-002 尚未最终通过。执行 TASK-002-R2 收尾，不启动 TASK-003。**

GPT 独立重跑所交付的回归脚本，42 个用例全部通过；原日期缺失、表头空格、标识去空格、布尔标识和未知金额报告等既有案例的行为均已改正。原主文件及 22 份 fixture 保持预期结果。

追加验证仍发现：Excel 错误类型单元格被当作合法标识；回归脚本在发现只读输入哈希不一致时仍返回成功。另外，日期解析新增了未经规格约定的文本日期时间格式，需收回。本次收尾限定输入类型、测试退出行为和证据准确性，不重做数据、不扩展业务功能。

GPT 本轮没有修改 checker、生成器、回归源码、既有文档或工作簿，只新增验收证据和本报告／返修卡。

## 2. 已独立确认的修复

- 运行所提交的 tests/test_check_demo_data_regression.py，进程退出 0；42 个用例通过，失败 0。包含主文件、22 个原 fixture 和 19 个边界／正向／覆盖保护用例；实际调用 checker 43 次，因为覆盖保护会调用两次。
- 付款／应付必填日期为空、原生 datetime 含非零时间，均已阻断；合法午夜原生日期仍通过。
- 表头尾空格不再匹配固定列名，报告结构问题；标识值内空格保留，不再偷偷匹配。
- 布尔与数值标识已阻断，真实文本前导零仍保留。
- N/A、空值、公式、非正金额均有不可用金额记录；完整结果不再补零，相关勾稽为 NOT_ASSESSED，比较结果为 null。有效批次仍准确计算整数分。
- 本轮另测纯空白日期，退出 1；文本负金额 -1.00 也退出 1，记两处 AMOUNT_INVALID，不可用金额计数正确。
- 运行时仍为 Python 3.11.1，openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9；未安装依赖。
- 对原验收记录的 94 个文件重新核对，只有 checker 与 DEMO_DATA_GUIDE 两个授权修改文件变化；另外 92 个未变。
- 本轮复验前后对 280 个既有文件计算哈希，包括源码、原数据、R1 成果和原验收证据，均保持不变。

本次正常回归输出目录：

    D:\harness work\audit_sa_project\data\generated\task002_r1_gpt_20261011_054724

## 3. 尚需修复

### F01（P1）：Excel 错误类型仍被接受为文本标识

位置：scripts/check_demo_data.py 第 176 行附近，read_text。

函数阻断了布尔／数值，却只凭 isinstance(value, str) 接受字符串。Excel 错误单元格读取后，值也可能是 Python 字符串，但 cell.data_type 为 e，不能当作真实文本标识。

GPT 创建并重新读取落盘副本，确认以下单元格实际类型均为 e：

- E01：payments!A2 和 allocations!B2 的 payment_id 都为错误值 #N/A。实际退出 0、无问题，勾稽 ASSESSED。
- E02：payments!I2 的已结算 bank_reference 为错误值 #REF!。实际退出 0、无问题，勾稽 ASSESSED。
- E03：allocations!C2 的可空 ap_id 为错误值 #N/A。实际退出 0，被当作普通台账外标识。

上述均违反“真实文本单元格”要求，应报告标识类型问题并退出 1。可空标识允许为空，不允许错误类型。

正向控制 E04：将付款 ID 及分摊引用都写为真正文本 #N/A，落盘类型为 s，实际通过。这类普通文本不能仅因显示内容像错误码而被一刀切禁止。修复必须依据单元格类型，不能只黑名单匹配字符串。

### F02（P1）：只读输入完整性检查失败，验证进程仍成功

位置：tests/test_check_demo_data_regression.py 第 581—625 行附近。

脚本会计算 hash_problems，并在 JSON 中登记 protected_inputs_unchanged=false，但最后只有 regression.failures 能使进程返回 1。哈希问题没有进入失败结果，随后仍打印“全部回归用例通过”并返回 0。

GPT 用内存加载回归模块的方式，只替换 MAIN_INPUT 第二次读取时的 sha256 返回值，模拟检测到哈希不一致。所有实际文件均未修改。

实际结果：

- 42 个功能用例仍全部通过；
- protected_inputs_unchanged=false，changed 列表明确包含主工作簿；
- 验证进程仍退出 0，并打印“全部回归用例通过”。

这个验证说明完整性失败路径没有影响最终退出结果。应返回 1，保留失败原因，并停止输出总体成功结论。

故障路径模拟输出目录：

    D:\harness work\audit_sa_project\data\generated\task002_r1_gpt_20261011_054724_integrity_probe

其中 changed 字段是故意注入的模拟结果，不代表原始工作簿真的被修改；本轮前后文件哈希证明真实文件未变。

### F03（P2）：无授权扩展文本日期时间格式

位置：scripts/check_demo_data.py 第 97、198、229 行附近。

R1 增加 DATE_TIME_TEXT_PATTERN，接受时间全零的文本日期时间。E05 把 payment_date 写为真正文本 2026-09-10 00:00:00，实际退出 0。

SPEC_V1.md 第 2 节规定日期文本标准表示为 YYYY-MM-DD，原生日期可无损转换，额外时间成分须报告。R1 卡允许原生午夜 datetime，并未授权把带时间的文本纳入第一版输入格式。

应收回这项扩展：带显式时间的文本须阻断；原生午夜日期仍可接受。E06 的非午夜日期时间文本已经阻断，应保留这一行为。

### F04（P3）：回执及日志需准确说明

这组问题不说明原数据被改坏，但需要在新回执勘误：

- 原 R1 回执写保护输入共 26 个，实际 regression_summary.json 中为 28 个：主输入 1 + fixture 22 + 其他只读依据 5。
- 原 R1 回执写 94 个文件中 93 个不变、仅 checker 改动；实际是 92 个不变，checker 与 DEMO_DATA_GUIDE 两个授权文件改动。
- 原回执声称回归脚本覆盖了文本与数值两种负金额；所交脚本中负数案例只有数值 -100。文本负数由 GPT 本轮 E08 独立验证；不能追记成 R1 当时已经执行。
- 覆盖保护两次调用使用相同日志文件名，以 w 模式打开，第一次 stdout 被第二次覆盖。实际 43 次 checker 调用仅保留 42 个 stdout 文件；需使用每次调用唯一的日志名。

不要覆盖原回执或旧日志。R2 回执单独写明勘误，并对新执行的命令和日志如实计数。

## 4. 证据位置与范围

本轮独立验收证据：

    D:\harness work\audit_sa_project\data\reviews\task002_r1_20261011_054723

- acceptance_summary.json：正常回归重跑、追加 E01—E08、完整性失败模拟、依赖及哈希摘要。
- command_log.json：本轮实际调用项目 Python 的完整参数、退出码及 stdout／stderr；含完整的内存故障模拟脚本。
- boundary_inputs/*.xlsx、boundary_reports/*.json：追加类型、日期与负金额的副本及 checker 实际报告。
- source_hashes_before.json、source_hashes_after.json：本轮 280 个既有文件前后哈希。

故障模拟是在内存中替换摘要返回值，不修改磁盘源码或输入，不是对业务文件进行真实篡改。原始来源、旧报告和失败证据均保留。

本轮仍未实现或运行 R01—R04 引擎、入库、Gate 1／Gate 2、AI 建议或正式契约。验收限于上述开发交付与边界，未声称穷尽所有可能的 Excel 输入。

下一张卡为 docs/tasks/TASK-002-R2.md。主理人无需手工复测、安装依赖或填写审计判断，只需转交本报告和返修卡；等待新的 EXEC_REPORT_002_R2.md 后由 GPT 复验。
