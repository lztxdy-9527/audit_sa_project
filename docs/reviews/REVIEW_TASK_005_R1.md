# TASK-005-R1 复验：四项原修订通过，关闭错误仍需修复

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED。

上一轮 F01—F04 的修订均已通过本轮独立复现，正常装载与往返保持正确。尚有一处成功条件未满足：正常流程关闭数据库时抛出的 SQLite 异常被吞掉，API 仍发布数据库并返回成功。下一轮只修这一项，指令见 `docs/tasks/TASK-005-R2.md`；不推进任务六。

GPT 本轮没有修改实现、schema、测试入口、装载说明或执行回执。新增内容仅为本轮验收证据、本文及修订卡。未运行 R01—R04，未改变既有业务批次，也未批准 Gate 1／Gate 2。

## 1. 实际重跑结果

在全新测试目录执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r1_gpt_20261011_061018'

退出 0。39 个案例：入库成功 18、质量阻断 8、装载阻断 6、运行失败 7；测试失败 0；26 次真实 checker CLI。与新回执一致。

GPT 以只读连接逐项核验全部 18 个成功库，共 3130 条业务记录、20617 个固定字段的 data／source／cells。业务字段、完整来源、整数分类型与合计、对象指纹、标准化上下文、开发态边界、外键和完整性均通过。

主文件四表仍为 20／993／1000／1005 行，净额 267249329 分 = 已知关联 266249329 分 + 缺失关联 1000000 分。C03 资金净额未因一对多分摊翻倍。未知应付关联、收款对象差异、退款、非结算和空资金正例均继续保留。

## 2. 上一轮四项独立复现全部通过

复用上一轮探针的断言，在本轮新容器创建全新现场。仅为 Q03 的内部 verify_database 包装器转发新增加的元数据参数，没有改变预期结果。

- Q01：应付合计预期增加 1 分，在数据库独立核对阶段抛 SqliteLoadError；暂存库六表全 0，无最终库，核对失败没有提交。
- Q02：一个单元格来源只剩 input_field／target_field／standard_value，写入前抛 SqliteLoadBlocked，无目标库、无暂存库。
- Q03：核对成功后、发布前新建目标标记，发布抛 SqliteLoadError；标记字节原样保留，没有覆盖；暂存库保留已提交数据，失败状态没有假报回滚。
- Q04：运行元数据写入函数不写任何行，数据库实际核验发现缺项并抛 SqliteLoadError；暂存库六表全 0，无最终库。

四项 contract_met 均为 true。本轮没有重新打开这些已通过的要求。

## 3. 关闭／发布路径的补充核验

针对本轮变更的路径另做四项有限检查，全部只使用新文件和临时内存接缝：

- R02：模拟硬链接不受支持，实际走独占创建后复制的备用路径，正常发布成功，目标字节哈希与暂存哈希精确相等。
- R03：同样进入复制备用路径，但发布前目标晚出现，明确拒绝覆盖，标记字节保持不变。
- R04：只令最终目标文件的哈希读取失败，API 抛 SqliteLoadError，阶段为 final_hash；最终数据库实际保留，未返回成功，也未假报回滚。
- R01：关闭数据库的 SQLite 异常被正常路径吞掉，仍返回成功；这是本轮唯一阻断项，详见下一节。

独立探针共 8 项（上一轮 4 项 + 本节 4 项），7 项满足要求、1 项未满足。探针脚本退出 0 表示完成复现，不表示全部探针通过。未额外调用 checker，原正常输入来自本轮真实 checker／标准化过程。

## 4. 唯一阻断项：关闭失败仍被当作成功

位置：`scripts/store_demo_sqlite.py:826` 的 `_cleanup()`，及 `:884`—`:886` 的正常关闭步骤。

当前 `_cleanup()` 捕获 `sqlite3.Error` 后仅向 close_notes 加入消息，并把 connection 设为 None。正常流程也调用这个宽松清理函数，因此关闭异常未中断流程；close_notes 仅在别的错误发生时才进入错误说明，没有参与成功判定。

R01 用代理保留真实连接的数据库操作，在 `close()` 实际释放句柄后抛出 `sqlite3.OperationalError("GPT injected sqlite3.OperationalError from close")`。先释放真实句柄是为了防止 Windows 文件占用把这个控制流程错误掩盖成另一种文件错误，不代表正常运行中已经观察到真实关闭故障。

实际结果：代理确实抛出关闭异常，但 API 返回 DEV_SQLITE_VERIFIED，最终库已发布，暂存库不再存在。最终库本身 data／source／metadata 正常，不能据此把关闭异常当成成功。

这违反原任务五第 6 节“只有检查、提交、关闭和最终文件哈希取得均成功后，API 才返回 DEV_SQLITE_VERIFIED”的要求；R1 卡第 3 节也明确关闭错误应按提交后失败处理。

应区分两种调用：正常流程中的关闭必须严格成功，否则立即进入 SqliteLoadError，不继续哈希／发布；已有错误后的尽力清理允许附记关闭失败，但不能覆盖原错误。关闭失败发生在提交之后，保留已提交暂存库，如实报告，不宣称回滚或六表零行。

## 5. 文件保护与交付版本

本轮开始前 8101 个已有文件全部未变、无缺失。相对上一轮 TASK-005 的 7506 文件基线，恰有本卡授权的装载器、测试入口、装载说明三个文件变化；schema 与其他历史文件无变化、无缺失。

TASK-004-R1 的 6511 文件、TASK-003-R3 的 4902 文件、TASK-002-R2 的 874 文件基线均为 0 变化、0 缺失。

本次收到的哈希与回执一致：

- scripts/store_demo_sqlite.py：6128f09b64eb5ef8554e448b023d382cb142bcb3c933e198c138d9c740d7fc35
- tests/test_store_demo_sqlite.py：6cc9c932e369e7e0452613bc7425731d641b9d8c7d4c7ae30aaf7a5a40162914
- docs/SQLITE_LOAD_GUIDE.md：15cbb356b31d212000261bef3cc127461cc00c9673c7e66cb541b9432500b48f
- sql/demo_schema.sql：7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205（未变）
- docs/EXEC_REPORT_005_R1.md：aa1cc9e0f5141dfb7187d7bc272e62c97f4bd92d43f2abe6c768bf4af7c22f48

## 6. 证据与转交

验收目录：`data/reviews/task005_r1_20261011_061018/`。

- command_log.json、regression.stdout.txt／stderr.txt：39 例重跑；26 次 checker 细项见新测试容器 command_log.json。
- independent_command_log.json、replay_task005_probes.py、probe_results.json：上一轮四项探针的新复现。
- independent_roundtrip.json：18 个成功库的逐项只读核验。
- publication_command_log.json、probe_publication_boundaries.py、publication_boundary_results.json：本轮关闭／发布四项检查。
- protected_files_comparison.json、source_hashes_before.json／after.json、acceptance_summary.json：文件保护与机器可读结论。

具体新数据库和注入说明分别位于新测试容器 acceptance_probes 和 publication_boundary_probes 子目录。

主理人无需手工复测或批准守门点。请将本文和 `docs/tasks/TASK-005-R2.md` 全文转给 DeepSeek，仅修正常关闭异常处理，完成后回传 EXEC_REPORT_005_R2.md。当前不发 TASK-006，不扩展业务范围。
