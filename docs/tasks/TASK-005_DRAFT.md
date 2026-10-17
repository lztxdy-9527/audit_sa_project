# TASK-005 草案：开发态 SQLite 入库、往返核对与 SQL 勾稽

日期：2026-10-11。执行端：DeepSeek；GPT 负责架构和验收；主理人负责转交。

只完成本卡，提交 EXEC_REPORT_005.md 后停住。不要实现 R01—R04 或进入任务六，不代表获准推进任何既有业务批次。

## 1. 当前成果和实务场景

任务一规格、任务二合成输入／checker、任务三接收器、任务四标准化器均已验收。任务四经 R1 通过，结果版本 TASK-004-normalized-1.1。不要重做或修改这些成果。

实务场景：标准化后，需要把供应商、应付、资金事件和分摊存入可查询的表，并证明“入库没有丢行、改 ID、错用金额单位或重复计算资金”。以后 SQL 筛查只应在这些证据齐备并经人工放行后开展。

本次仅实现可调用的 SQLite 装载核心及开发测试：将新生成的标准化结果装入新数据库，读取回来逐行对照，再用 SQL 独立勾稽数量和金额。数据库入库通过不表示没有业务线索，也不是审计结论。

继续使用 DEVELOPMENT_TEST_ONLY：测试输入只从 data/generated 的已验收合成工作簿／fixture 制作新副本，真实运行 checker，再调用冻结标准化 API。不能复用旧 normalized.json 或旧 checks 作为本次运行结果；不读取 data/batches 作为处理对象，不修改旧 batch_manifest.json。

本卡不接正式业务流程，不建立契约或批准命令，不自动推进 Gate 1／Gate 2。开发测试属于模块验证，不代替主理人对具体批次的批准。

## 2. 开始前读取与环境

项目：D:\harness work\audit_sa_project

解释器：D:\harness work\audit_sa_project\.venv\Scripts\python.exe

读取本卡、docs/reviews/REVIEW_TASK_004_R1.md、docs/NORMALIZATION_GUIDE.md、SPEC_V1.md 第 2—4 节及 AUDIT_CONTRACT_DRAFT.md 第 2、3 节。了解标准化返回结构和冻结脚本接口，不把历史旧方案作为施工依据。

核对冻结 SHA-256，不一致先记录并停止：

- 标准化器：a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310
- checker：a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8
- 接收器：5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6
- SPEC：5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236
- 契约草案：af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27

使用标准库 sqlite3、json、hashlib 与已有 openpyxl；记录实际 SQLite 版本，不安装依赖，不初始化 Git。

## 3. 只允许新增

- scripts/store_demo_sqlite.py：装载核心 Python API，不提供面向业务批次的 CLI。
- sql/demo_schema.sql：本次数据库建表及基础约束，允许新建 sql 目录。
- tests/test_store_demo_sqlite.py：开发验证入口，支持 --out-dir。
- docs/SQLITE_LOAD_GUIDE.md：结构、装载、勾稽、产物及边界。
- docs/EXEC_REPORT_005.md：真实执行回执。
- data/sqlite_tests 下全新测试容器及其输入副本、报告、标准化结果、数据库、日志和测试汇总，允许创建父目录。

其余全部只读，包括冻结脚本／测试、任务卡、规格、契约草案、答案册、旧回执、评审及全部既有数据。不要向旧容器补文件，不改旧代码以便导入，不导入生成器或读取答案册决定运行结果。

## 4. 装载 API、前提与文件边界

提供简单公共 API，例如：

    load_normalized_to_sqlite(normalized: dict, database_path: Path) -> dict

读取内存中的标准化结果，写入全新数据库，返回本次装载核对报告。调用方负责保存报告；本核心不重跑标准化、不写回 Excel、不接收业务批次批准。

明确区分前提阻断与装载／一致性运行错误，例如 SqliteLoadBlocked、SqliteLoadError。报告缺结构、输入类型不符等不能靠默认空表／默认零继续；文件、数据库约束或勾稽错误保留阶段、路径及原始原因，不返回成功报告。

装载前检查本层实际需要的结构：

- 标准化版本为已验收的 1.1，mode=DEVELOPMENT_TEST_ONLY、next_step_allowed=false；质量结果 pass；标准化勾稽标记及 checks 为明确通过。
- 四表及 records、每条 data／source／cells 存在且类型正确，业务字段与本版固定字段一致；数量和金额统计可用，不把缺项解释为空表。
- 必需文本为实际 str，可空字段只接收 str 或 None；金额为实际 int、非 bool，严格正数；日期为标准 ISO 日期字符串。禁止为入库把数值 ID str()、把金额字符串 int() 或自动改写字段。
- 每条来源工作簿哈希与本结果 source 一致；sheet、原 Excel 行号可用；cells 覆盖固定输入字段，目标字段和 standard_value 与 data 对应，不能静默丢来源。

这层检查装载所需的标准数据契约，不另写一套完整 ERP 质量校验器。身份、退款合法性和业务范围仍依赖上游真实 checker／标准化流程；本地哈希不证明来源真实性或抵御同权限篡改。

数据库路径只允许 data/sqlite_tests 中的新文件；解析绝对路径后核对范围，拒绝根目录、越界或已有目标，在写入前停止。测试容器本身也必须全新；不覆盖、不删除历史。

## 5. 数据库结构

创建四张业务表，字段为标准化 data 的字段：suppliers、payables、payments、allocations。金额仅使用 payable_amount_cents、amount_cents、allocated_amount_cents 的整数分；不另存“元”业务金额列。

基础约束必须包括：

- 四表业务主键为 TEXT、PRIMARY KEY 且显式 NOT NULL；字符串原样保存，保留前导零、空格和标点。日期／枚举为文本，金额为 INTEGER，使用基础 NOT NULL／CHECK 约束保证适用字段类型、金额正数及本版枚举／币种。
- payables.supplier_id、payments.payee_supplier_id 指向 suppliers；allocations.payment_id 指向 payments；原付款和原分摊引用分别为可空自关联外键。
- allocations.ap_id 必须允许 NULL 和不在 payables 的文本，不对它设置强制应付外键、不改成 NULL、不删记录。不同收款对象允许入库。
- 已结算 bank_reference 的唯一性，以及同一事件对同一应付对象的分摊唯一性。SQL 的普通 UNIQUE 会放过多个 NULL，未指定 ap_id 的重复组合需要用适当的部分唯一索引处理。
- 在事务开始前启用 PRAGMA foreign_keys=ON 并实际核验为 1；自关联引用使用可延迟检查或等效可靠安排，不要求原付款／原分摊总在 Excel 较早一行。

SQLite 的类型亲和性会自动转换某些绑定值，不能代替装载前的 Python 严格类型检查。整数分单值或 SQL 汇总超出 SQLite 整数能力时明确停止，不改用 REAL／TOTAL() 或浮点容差。本卡不改变 SPEC 金额口径。

再创建两张辅助表：

- source_records：每条业务记录一条来源，至少含 table_name、record_id、workbook_sha256、sheet、excel_row、cells_json；以表名＋业务 ID 唯一关联，禁止把不同表的相同 ID 混为一条。保留所有固定字段的单元格原值、类型和坐标，不用摘要替代完整 cells。
- run_metadata：登记数据库 schema 版本、DEVELOPMENT_TEST_ONLY、next_step_allowed=false、输入哈希、冻结版本、装载脚本及 schema 哈希，以及标准化上下文。上下文保留版本、来源、质量摘要、数量金额、空白行、额外表／列和限制；不必把所有业务记录再完整复制一遍。

规定 normalized_payload_sha256 的计算方式，例如对完整传入对象按固定 JSON 规则序列化后求哈希；明确它是对象规范化后的指纹，不冒称是某个旧 JSON 文件的字节哈希。JSON 不用 default=str，不允许 NaN／Infinity。

SQL 对业务值一律参数绑定，不把 ID 或名称拼入语句。表名／列名只来自固定白名单。

## 6. 事务、失败现场与成功定义

业务表、来源记录和本次元数据写入必须在同一数据事务内。可先建立空 schema，再 BEGIN 装载数据；注意 Python sqlite3 的 executescript 可能提交已有事务，不得在插入中途误用它造成半批提交。

成功前完成第 7 节的数据库独立核对；约束、数量、金额或往返核对失败时回滚数据事务，关闭连接并保留失败现场。不得靠删除问题行、INSERT OR IGNORE／REPLACE、补零或修改原报告通过。

可采用暂存数据库、成功后更名为目标文件的办法；最终路径不得覆盖已有文件。失败产物明确标为未成功，不能把暂存库当作已核对的数据库继续使用。若文件提交后才发生错误，保留实际文件和失败阶段，如实报告，不能宣称文件不存在。

只有检查、提交、关闭和最终文件哈希取得均成功后，API 才返回 DEV_SQLITE_VERIFIED 报告。数据库元数据始终为开发模式，不写 Gate 已批准；返回报告仍 next_step_allowed=false。这个状态仅表示开发数据库装载已核对，不自动开始规则筛查。

## 7. 独立 SQL 核对和往返

从数据库实际读取，不把传入 JSON 数字直接复制成“SQL 结果”：

1. 四表行数分别与标准化结果相等；source_records 数量及对应关系完整，每条业务行恰有一条来源。
2. 三个金额字段分别 SQL SUM，与标准化完整金额逐项相等；付款按类型／状态核对数量和金额，双向比较分组，不能漏掉非结算组。
3. 每笔资金事件金额等于其全部分摊金额之和；已结算 PAY／REFUND 的主表总额分别等于对应分摊总额。
4. 主表净额=已知应付关联净额+缺失关联净额，缺失再分空 ap_id／台账未找到；与标准化的三项完整净额及缺失分类对照。
5. PRAGMA foreign_key_check 无问题，PRAGMA integrity_check 返回 ok；明确它们不是审计结论检查。
6. 从业务表和 source_records 重建每条 data／source／cells，按原 Excel 行号读取，与传入记录逐项精确相等；不只比较总数或总金额。JSON 解码后核对来源内容，不能只断言 cells_json 非空。

主表资金总额须单独从 payments 计算；不能在一对多关联后重复 SUM 主表金额。分摊总额按 allocations 粒度计算，两者不相加。真实空表的 SUM 无行可按 0 展示；缺失／无效金额不可用这种方式填零。不要强求应付金额等于付款金额。

返回装载报告给出上述实际数量、整数分金额、各比较结果、版本、最终数据库路径及字节哈希。任何差异须明确失败，不能返回“一致”。本卡不计算超付、重复付款、风险等级或损失。

## 8. 必须实际执行的开发验证

测试入口 --out-dir 指向 data/sqlite_tests 下全新容器。各案保存输入副本、新 checker 报告／独立 stdout 和 stderr、新标准化结果、数据库及装载报告或明确失败记录；命令完整留痕。

覆盖以下情况，实际数量从结果统计，不为凑数增加大量案例：

- 主文件及 14 份质量有效 fixture：新标准化后全部入库并往返精确相等。主文件四表 20／993／1000／1005 行，净额 267249329 分、已知 266249329 分、缺失 1000000 分；C03 主表净额仍为 1000000 分，不能因两个分摊变成 2000000 分。
- C07／C08／C07b 的空／未知／部分未匹配关联，C09 对象差异，C06／C06b 退款及 C10／C10b 非结算事件都保留，具体记录和金额可从数据库查回。
- 8 份质量阻断 fixture：保存真实 checker 问题，不建立可用数据库，不把未标准化输入伪装成合法结果。可以沿用标准化器的明确阻断，不重复实现质量规则。
- 小正例一：无付款／退款／分摊但存在应付，仍可入库，资金为 0、应付保留。
- 小正例二：前导零、首尾空格及含单引号的 ID、日期／小额整数分、来源坐标往返保真。所有引用同步保持有效，真实 checker 必须通过。
- 小正例三：把退款及退款分摊放在原记录之前，重新生成报告并标准化后仍可入库，验证不依赖 Excel 行顺序满足自关联。
- 同一成功数据库路径再次装载：写入前拒绝，原库全部字节哈希未变；越界路径在写入前拒绝，未创建目标。
- 对新正常结果的内存副本，分别注入金额字符串／bool、重复主键或缺失强制资金关联，不能静默转换或忽略。保留注入说明和原标准化结果，不冒称这些错误来自上游标准化器。
- 数据事务中已插入部分行后，在内存中模拟一次写入故障：无成功报告，事务回滚；保留的暂存库不能留下半批业务、来源或运行元数据。此项只作用于全新测试库，不改真实磁盘源码。

可将有关正例合并为少量小样；不重跑任务二 50 例、任务三 61 例或任务四 47 例整套测试。实际接收／核验／标准化调用只服务于本卡新数据库验证。

任何断言、未预期异常或只读保护失败，使整个测试进程非零。预期质量阻断、装载阻断、运行失败与测试失败分开统计。成功与失败现场都保留；不覆盖旧目录后重跑。

建议命令（目录存在则换新后缀）：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_01'

## 9. 回执与停止

SQLITE_LOAD_GUIDE.md 固定公共 API、六表结构／关键约束、NULL 应付关联为何允许、事务及失败产物、SQL 勾稽和往返方式、真实测试命令与开发边界。

EXEC_REPORT_005.md 记录新增文件及最终哈希、Python／SQLite 实际版本、完整执行命令和日志位置、实际输入／入库／预期阻断／运行失败／测试失败数量、主文件和定点结果、失败尝试、原输入及冻结代码保护、未解决问题。没有执行的检查不得写为通过。

若冻结规格或标准化结构有矛盾，记录具体数据及来源后停在受影响部分，不自行修改旧代码或扩大业务口径。同一问题三次仍失败或上下文不足，保存实际进度、错误及下一条命令后停止。

完成后返回 EXEC_REPORT_005.md、SQLITE_LOAD_GUIDE.md 的完整路径和简短摘要，等待 GPT 验收。不做 R01—R04、不导出 AI 结论、不建立正式契约／审批控制、不推进任务六。主理人本轮只需转交，不需技术复测或模拟守门批准。
