# TASK-005 验收：需要修订

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED。

正常数据装载、金额勾稽与逐项往返均通过；失败回滚、来源契约、文件发布及运行元数据核验存在四处缺口，本轮不冻结装载核心，不推进 TASK-006。修订指令见 `docs/tasks/TASK-005-R1.md`。

GPT 本轮只新增验收证据、本文和修订卡，没有修改实现代码、schema、测试入口、原说明或回执，没有推进任何既有批次，也没有批准 Gate 1／Gate 2。

## 1. 已确认通过的部分

在全新目录实际执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_gpt_20261011_055303'

退出 0。33 个案例中，入库成功 18、质量阻断 8、装载阻断／路径拒绝 4、运行失败 3，测试失败 0；26 次真实 checker CLI。原有断言全部符合预期，这些测试结果属实。

另行以只读连接打开全部 18 个成功数据库，按业务主键逐项读取并比较 3130 条业务记录、20617 个固定字段的 `data`／`source`／`cells`；金额存储类型及整数合计、对象指纹、标准化上下文、开发态标识、外键和完整性检查均通过。该检查没有调用装载器的 `verify_database` 充当独立核验。

主文件四表 20／993／1000／1005 行，三表金额合计分别为 267849329／270149329／270149329 分。净额 267249329 分 = 已知关联 266249329 分 + 缺失关联 1000000 分。C03 主表净额为 1000000 分，没有因两个分摊翻倍。

空／台账外应付关联、部分未匹配付款、收款对象差异、退款、非结算事件和无资金正例均保留；ID 中前导零、空格和单引号的正常输入可以往返。现有 schema 的六表和主要约束方向正确，本轮不要求重做数据库模型。

## 2. 必须修订的四项

以下 Q01—Q04 均使用本轮新生成的 C01 标准化结果，故障只作用于内存副本或新测试文件。没有改旧报告，没有把注入错误冒称为上游正常输出，也没有使用真实业务批次。

### F01：独立核对在 COMMIT 之后，核对失败无法回滚

位置：`scripts/store_demo_sqlite.py:652` 至 `:658`；任务卡第 6 节。

当前代码先 `COMMIT`，再调用 `verify_database`，与模块开头的流程说明不符。原 I5 只验证插入阶段故障，不能覆盖核对阶段故障。

Q01 将新内存副本中的应付合计预期数增加 1 分。实际 SQL 合计 500000 分、预期 500001 分，API 正确抛出 `SqliteLoadError`，但暂存库六表行数仍为：suppliers=2、payables=1、payments=1、allocations=1、source_records=5、run_metadata=17；其中 `batch_status=DEV_SQLITE_VERIFIED`。没有最终目标库，**但失败数据已经提交**。

应在同一未提交事务中完成业务、来源、元数据的读取核验，全部通过才提交。约束／数量／金额／往返核对失败时，保留的暂存库六表数据应均为零。核对错误也须带阶段、路径和具体差异。

### F02：缺少单元格原值、类型和坐标仍被当作完整来源

位置：`scripts/store_demo_sqlite.py:210` 至 `:223`；任务卡第 4、5 节。

Q02 从一个 `supplier_id` 单元格来源中删除原值、编码、类型、列号和坐标，只保留 `input_field`／`target_field`／`standard_value`。API 仍返回 `DEV_SQLITE_VERIFIED`，数据库也确实只保存这三个字段。

对不完整对象做往返比较，仍然会得到相等，无法证明必需来源信息存在。装载前应核验冻结标准化格式中的必需来源字段、适用类型和坐标关系；必需 `raw_value` 的键不能因为值可能为 None 就跳过。缺失时明确 `SqliteLoadBlocked`，不生成数据库，不补造来源。

### F03：最终发布会覆盖检查后新出现的目标

位置：`scripts/store_demo_sqlite.py:665`；任务卡第 6 节。

入口的“目标不存在”检查只反映开始时的情况。Q03 在真正数据库核对成功后、新文件发布前，于本次全新测试目标写入一段标记内容；随后 `os.replace` 覆盖了该文件，API 返回成功，标记字节未保留。

需要使用在本机遇到已有目标就失败的发布操作，并实测目标字节不变。仅在 `os.replace` 前再加一次 `exists()` 仍留下同类窗口；不得先删除目标再发布。本项是任务卡的“不覆盖文件”要求，不是要求建立抵御恶意篡改的安全隔离。

### F04：独立核对没有读取 run_metadata

位置：`scripts/store_demo_sqlite.py:382` 的 `verify_database`；任务卡第 5、6 节。

Q04 对一次新调用临时将 `insert_run_metadata` 替换为无写入函数，其余业务与来源装载正常。API 仍返回 `DEV_SQLITE_VERIFIED`，最终库 `run_metadata` 行数为 0。这个故障注入说明成功判定不能发现必需运行上下文未落库，不代表正常路径已观察到元数据丢失。

提交前还应从库中读取实际元数据，核验必需键、开发态边界、对象指纹、输入及版本哈希、行数和完整标准化上下文与本次预期相等。预期应来自本次输入及本次生成的元数据，不能只检查行数或值非空。缺项或不一致必须失败并回滚。

## 3. 文档口径

`SQLITE_LOAD_GUIDE.md` 第 3 节及异常说明把所有失败现场概括为已回滚、六表零行，当前实现不满足；即使修正事务顺序，提交后的关闭／文件发布／最终哈希失败也不能一概声称数据已经回滚。

修订说明应区分提交前可回滚的失败和提交后需保留实际文件的失败。保留阶段、路径和原始原因；已有最终文件时如实说明，不能宣称不存在。原 `EXEC_REPORT_005.md` 保留为历史，在新回执说明修复和新增验证。

## 4. 文件保护与当前交付版本

本轮 7506 个既有文件：0 变化、0 缺失。TASK-004-R1 的 6511 文件基线、TASK-003-R3 的 4902 文件基线、TASK-002-R2 的 874 文件基线也全部未变。

收到的交付哈希与回执一致：

- scripts/store_demo_sqlite.py：1aae12e3c3b3c8dc661e2467aaf793668678104efab1f78b82db6d065c855407
- sql/demo_schema.sql：7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205
- tests/test_store_demo_sqlite.py：7fc33bb81db41e147e20d3ac4264e595eb56fe79eb66a1264c72ff61486c293e
- docs/SQLITE_LOAD_GUIDE.md：f5f266fa858e0b90527fb27cbc94d55b41a191415f157c2a03ffbde8bbc04aed
- docs/EXEC_REPORT_005.md：ff6549b7dea8ba33b86810318c81b4cb3fdb31b0b60f49ec92541c96e49e792e

## 5. 证据与下一步

验收证据：`data/reviews/task005_20261011_055303/`。

- command_log.json、regression.stdout.txt／stderr.txt：33 例重跑及退出码；26 次 checker 细项在新测试容器的 command_log.json。
- independent_command_log.json、probe_sqlite_acceptance.py：独立检查的实际命令和复现代码。
- independent_roundtrip.json：18 个库的逐项只读核对。
- probe_results.json：Q01—Q04 的观察结果；新库／注入副本／说明在新测试容器的 acceptance_probes 子目录。
- protected_files_comparison.json、source_hashes_before.json／after.json：历史保护核验。
- acceptance_summary.json：机器可读结论。

独立脚本退出 0 只表示复现脚本完整执行；四项 `contract_met=false`，不能写成四项通过。

主理人本轮无需手工复测、签署契约或批准 Gate。请把本文和 `docs/tasks/TASK-005-R1.md` 全文转给 DeepSeek，按修订卡完成后停住交回。任务四保持验收通过状态；本轮未运行 R01—R04，未开始任务六。
