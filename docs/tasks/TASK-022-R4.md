# TASK-022-R4：规范JSON相等判定的最小修正

执行分类：**B类，DSH处理**。依据 `docs/reviews/REVIEW_TASK_022_R3.md`。只修一个测试判定根因：Python宽松数值相等不等于既定canonical JSON字节相等。涉及PASS有效性，继续由当前执行端处理；不是新业务/架构设计。

## 1. 严格文件范围

仅允许修改 `tests/test_store_demo_human_gate_decision.py`，起点SHA `43884b406b1f70293d31d9dadac0b925021e7bc37b36e015b06d4e32fe26d817`，限_content_compare/_field_diff的相等与诊断及最小定点验证。

仅新增 `docs/EXEC_REPORT_022_R4.md`、新 `data/human_gate_decision_store_tests/task022r4_<唯一名>/` 与同轮新 `data/human_gate_decision_records/task022r4_<唯一名>/`。正常/故障分离；旧容器/回执/评审/junction全部冻结，不执行旧脚本、不覆盖、不清理。

冻结：生产存储SHA `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`，指南SHA `3d3805f42444f3e6f06b3a77e55744dcf9c3849252e105c9f67078067ae2582f`，P1/正式契约/登记/宿主/控制器/业务文件，以及R3已通过的真实观察预期来源、固定时点、终审顺序、IO/调用观察。**不改生产代码、不改指南、不重写收尾**。

基线 `data/reviews/task022_r3_gpt_20261014_000920/source_hashes_after.json`；先核验同目录review_result为NOT_ACCEPTED及清单完整SHA/项数，仅两个确切自指元数据路径分类，无目录前缀豁免。

## 2. 修正要求

1. 完整内容是否相等直接按**已约定canonical JSON字节**判定（UTF-8/ensure_ascii=False/sort_keys=True/固定separators/allow_nan=False），不用Python `==`、`!=`或“field_diff为空”代替主判据。规范SHA不同不得仍equal=true；不转换类型、不strip或规范化业务字符串。
2. 差异诊断正确定位False→0、整数→浮点等规范差异到具体字段；field_diff是有界诊断，不能决定忽略真实差异。可在叶节点用同样canonical比较；不需要复制P1算法或逐字段写类型黑名单。
3. 完整观察深拷贝预期继续固定于终审前，不读候选磁盘生成预期、不刷新、不二次调P1。内容错误继续影响failures/summary/返回码，保留已通过的字节漂移逻辑和故障现场。

## 3. 最小验证

先在隔离对象上走实际helper：原件通过；False与整数0拒绝；整数0与浮点0.0拒绝；至少一个字典键顺序不同但canonical字节相同的控制通过。候选记录/ID/计数及关联不变，错误须指向实际差异路径；不要同步修改真实预期。

再一次**真实入口类型故障**：在新容器第一次终审读取之前，仅把一条真实returned entry的 `result.record.boundaries.persisted` 从False改成整数0，保留ID/计数/内存真实观察；调用真实reader并返回原值。套件必须非零、FAIL、failures非空，内容比较equal=false且定位该字段。不得仅返回伪造diff/错误列表或只做helper就称入口通过。

一次新正常入口确认全部134项原检查及实际新增项通过、台账13项与磁盘一致、API/core/入口观察闭合。生产存储未变，本轮不单独重跑加载/路径/writer、已通过的{}替换/自洽reason替换/checks LF三个完整故障，不重跑P1/业务/宿主/历史入口。

若加入定点模式，必须执行该模式所需的真实审核和证据收尾，未执行项null/not_executed。全部调用/helper/正常/故障scope分列，不用预期故障的包装脚本退出0替代套件应非零的结果。

## 4. 保护、回执与停止

测试/新回执定稿、定点与正常/类型故障完成后一次最终保护扫描：changed恰为测试文件，所有冻结身份一致；missing/读取错误/范围外变化0，新增按确切路径登记。扫描后只有限登记身份，不再改测试声称同一次扫描有效。

新回执写明根因、主相等判据与诊断分工、正常/故障真实返回、独立规范字节及SHA对照、最终调用/台账、起点/写后SHA、保护基线/次数、过程问题/未执行。R3回执的交接SHA与实际读取差异只在新回执说明，旧回执不改；自身最终SHA只在交接消息给出。

如果发现需扩大到生产存储/P1/协议/契约/宿主、改变材料时序或允许根/历史/放行边界，立即停止本卡受影响处理并报告重新定界/升级C类，不扩大修改范围继续。完成后交GPT验收并停止；技术验收通过前不推进Gate1/Gate2，不生成真实批准/初判/0009，不开放AI。人类操作看板和作出业务决定。
