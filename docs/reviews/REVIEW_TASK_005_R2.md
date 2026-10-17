# TASK-005-R2 复验通过：SQLite 装载核心冻结

日期：2026-10-11（北京时间）。验收端：GPT。结论：ACCEPTED_DEVELOPMENT_SCOPE。

任务五在当前开发范围内通过，不再要求 TASK-005-R3。提交前核对与回滚、完整单元格来源、运行元数据读取核验、无覆盖发布及严格正常关闭均已补齐。当前装载实现为 TASK-005-sqlite-load-1.2，schema 为 demo-schema-1.0。

本结论是模块开发验收，不构成 Gate 1／Gate 2 批准。正式契约仍为草案；既有业务批次未推进。本轮没有执行 R01—R04、生成 AI 建议或填写人类判断。下一步施工范围另见 TASK-006_DRAFT.md。

## 1. 实际回归

GPT 在全新容器执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r2_gpt_20261011_062240'

实际退出 0。41 个案例：入库成功 18、质量阻断 8、装载阻断 6、运行失败 9；测试失败 0；26 次真实 checker CLI。原 39 例和 R2 两个新增案例均符合预期。

测试中的质量阻断和预期运行错误不等于测试失败，也没有被写成“规则零命中”。受保护的 34 个文件在测试前后哈希一致。

## 2. 两项关闭错误的独立复现

另用本轮新 C01 标准化结果和全新数据库，临时包装真实连接；其他操作委托原连接，第一次 close 实际释放句柄后抛 OperationalError。原始结果和注入说明分别保存，未改实现文件。

- A：正常关闭出错，API 抛 SqliteLoadError，阶段为 close_database，异常链保留 OperationalError。后续清理第二次关闭成功，API 仍保持失败；发布函数调用 0 次，暂存／最终文件哈希调用 0 次，没有目标库。暂存库保留已提交的 2／1／1／1／5／17 行，提交为 True、发布为 False，未假报回滚。
- B：应付预期合计增加 1 分，先发生真实数据库核对差异，随后清理关闭报错。主错误仍为核对失败，保留 500000 与 500001 分差异及 verify_database 阶段；关闭失败仅为附记。提交为 False，暂存六表全为 0，没有目标库，也没有成功报告。

两项 contract_met 均为 true，独立脚本退出 0。严格正常关闭与尽力错误清理已按要求分开。

## 3. 数据与来源的独立往返核验

以只读连接重新打开全部 18 个成功数据库，按业务主键直接读取并比较 3130 条业务记录、20617 个固定字段的 data／source／cells，未调用装载器的 verify_database 充当独立验证。

业务字段、整数分类型及合计、完整来源、对象指纹、标准化上下文、开发模式、外键与完整性均通过。

主文件四表仍为 20／993／1000／1005 行；三表金额合计为 267849329／270149329／270149329 分；净额 267249329 分 = 已知关联 266249329 分 + 缺失关联 1000000 分。C03 净额仍为 1000000 分，没有因两个分摊翻倍。

空／台账外应付关联、部分未匹配、收款对象差异、退款及非结算记录继续保留；无资金正例、ID 保真和退款先出现正例仍通过。所有成功报告仍为 DEVELOPMENT_TEST_ONLY、next_step_allowed=false。

R1 已独立验证的硬链接备用复制、复制冲突保护、最终哈希失败三个路径本轮未额外重复注入；本轮没有改动发布实现，原发布冲突回归仍通过。

## 4. 冻结版本与历史保护

收到的 SHA-256 与回执一致：

- scripts/store_demo_sqlite.py：1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446
- sql/demo_schema.sql：7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205
- tests/test_store_demo_sqlite.py：5c057ff65243977af84c6c8aad602a8e11d494019ef57b897647e23b6fb92557
- docs/SQLITE_LOAD_GUIDE.md：93bf2c821a00aff8d23a4e98c78f541e7688579bb73107ca3e4cd620542695c2
- docs/EXEC_REPORT_005_R2.md：58ff61b09852cc75bd6136c6a2d44c8fd19115d8d245244ab94adb5f2b741369

本轮开始前 8547 个已有文件全部未变，无缺失。相对 R1 的 8101 文件基线及原任务五的 7506 文件基线，只有授权的装载器、测试、说明三个文件变化；schema 与其他历史文件无变化、无缺失。

任务四 R1 的 6511 文件、任务三 R3 的 4902 文件、任务二 R2 的 874 文件基线也全部未变。GPT 本轮只新增验收证据、本文和下一张任务卡，没有修改实现代码或历史产物。

## 5. 证据、边界与转交

验收证据目录：`data/reviews/task005_r2_20261011_062240/`。

- command_log.json、regression.stdout.txt／stderr.txt：41 例重跑；26 次 checker 细项位于新测试容器 command_log.json。
- independent_command_log.json、probe_close_acceptance.py、close_probe_results.json：独立关闭复现。
- independent_roundtrip.json：18 个成功数据库的只读往返核验。
- protected_files_comparison.json、source_hashes_before.json／after.json、acceptance_summary.json：保护核对与机器可读结论。

本验收不证明真实 ERP 兼容性、真实数据完整性或审计结论正确；本地哈希与状态记录不构成抵御同权限篡改的安全隔离。

主理人本轮无需技术复测、签署正式契约或模拟守门批准。可将本文和 `docs/tasks/TASK-006_DRAFT.md` 全文转给 DeepSeek，启动下一张开发任务。任务六只允许在新合成测试容器中开发确定性规则；既有业务批次和正式判断流程保持原状态。
