# TASK-029 执行回执

状态：交独立 Architect / Reviewer 验收；本回执不自行宣布验收通过。仅实现只读 Gate2 候审请求，真实批次批准仍 null、开发宿主0008、next/AI=false。

## 1. 起点与授权

读取 TASK-029_DRAFT.md、REVIEW_TASK_028_R2.md 与接受登记。起点 verdict=ACCEPTED；基线 `data/reviews/task028_r2_gpt_20261015_211252/source_hashes_after.json`，163456项，SHA `d6155c337413490f16fefaefcd16b53d1322b2ad87f1ce3587553f30b344fc63`。

唯一既有修改文件 runtime_gate1.py 起点155899 B / `cf7f526ae3b6c222b3c0663a8473e9231e3ebcd7091e025d27ebcb238ec7346a`。原字节具名保全于 `data/runtime_gate2_request_tests/task029_setup_01/runtime_gate1_before.py`；starting_identity.json 登记身份。未把哈希当恢复材料。

## 2. 最终文件身份

- scripts/runtime_gate1.py：164079 B，`38168b0eda7a3c4a2e2a2c8dc4ca7c287b03507970afc374fc6004c91a62b515`。
- tests/test_runtime_gate2_request.py：23974 B，`db11e26593f7e606ddf5144da7d824553946aac59705ae0d8b74a7cc2cc82502`，新增。
- docs/RUNTIME_GATE2_REQUEST_GUIDE.md：6021 B，`f3d8e964e682579817d157363a0b0d8a4e17796a2f0407cbb35e270bef7aa9ad`，新增。
- 本回执新增；自身最终长度/哈希只在外部 delivery.json 与交接消息登记，不写回自身。

TASK-028 测试 `48794abb496035732c8af8e96c153d80eaa832c9394a70dddf49cf46daa7a120` /69067 B 与指南 `5941017f45b7d99640471032616220f7ffd47434e035d67537b583da02317357` /16276 B 均未修改。

## 3. 实现与实际停止点

唯一新增公开 API 为 prepare_runtime_gate2_request，签名严格按卡，无 CLI、无新协议字段或持久产物。实现版本常量升 TASK-029-runtime-gate1-1.0。既有函数正文/签名逐项 AST 比较完全相同；仅增加新 API/两项 Gate2 请求常量并更新实现版本值，没有重写已验收 inspect。

操作起始先固定八份来源、两份登记、八份事件、四件装载输出、数据库与静态绑定同缓冲读数；真实调用一次 inspect，闭合 artifacts 与起始文件哈希、完整 Gate1 记录/共享六项运行绑定，再构造请求。返回对象和指纹先定稿，最后复用 `_confirm_approved_terminal` 确认字节、集合、failure/锁及逐级路径，之后直接 return。没有候选重建预期、自比 capture、重复计算核心或保存调用。

成功外层2键，请求6键，materials7/expectations8/evidence7/boundaries7，prior5。files/expected_files 恰十项、固定逻辑映射，文件字节 SHA 与规范对象指纹分列。来源五字段来自本次核验的 context.request.evidence，两清单来自登记；质量仅在真实 inspect 成功后为 OK 三空列表。Gate1与Gate2共享六项相等、材料摘要不同。普通ID原样保留，返回无别名，不产生人类字段。

## 4. 定稿入口实测

命令：

```text
.venv\Scripts\python.exe -B tests\test_runtime_gate2_request.py --out-dir data\runtime_gate2_request_tests\task029_run_04
```

进程退出0；18项检查全部通过；summary=PASS、failures=[]、内容审核 problems=[]、末次 drift=[]、台账同缓冲审核通过。证据根 `data/runtime_gate2_request_tests/task029_run_04/`。

逐组验收证据：

- G1：正常两个请求规范相等；写盘/网络/子进程守卫命中0；源/登记/事件/load/DB集合与字节不变。独立十材料实读、七组键数、prior完整记录、材料和请求指纹、六项共享绑定、两摘要不同；改返回副本不改变其他分支/源；64hex与含换行普通ID原样通过。
- G2：空白/整数 request_id → request_id；错数据库路径 → database_path；有效失败诊断 → failure.fixture；started共享绑定变化 → started.bindings.run_binding；无装载 → load_dir；真实登记 HOLD → gate1.effective。全部定位拒绝且调用现场不因 API 写入改变。HOLD场景只借用正常输出字节以观察更早的有效 Gate1 前提，未声称 HOLD 发生批准装载，亦未把这些借用输出当成功材料。
- G3：包装真实 inspect，返回原结果后单次改本轮DB/context或新增load unknown.json；本次分别定位 runtime.sqlite3/context.json/load_dir，命中各1。撤销wrapper仍拒绝；坏字节保存后精确恢复本轮原件/注入文件原先缺席状态，再次准备成功。未写failure，未改正常接收源。新注入单文件 unlink 仅用于卡明确要求的原状恢复，坏字节均保存在证据根；没有递归删除/移动、清理任何目录或旧证据。
- G4：公开调用完整返回/异常/traceback/cause及参数；冻结/嵌套完整观察89条，真实 dict/list 消费引用三时点一致。原始code对象profile与wrapper条数闭合。独立 canonical/文件SHA；内存期望先定稿，再由冻结 TASK-028 短收尾 helper 实读审核候选与台账。未新增审计框架。

上述定位、命中、坏场景快照及恢复调用ID均在 checks.json；完整 API/core载荷分别为 api_records.json/core_records.json；独立期望 expected_observations.json；台账 file_ledger.json。

## 5. 调用口径

定稿数据轮直接 API 29：build3、Gate1 prepare3、Gate1 save3、approved load1、Gate2 prepare19。后者每次进入真实新API，成功时 inspect恰1，前提早拒时不超过1；normalizer/loader/store.save均0。

嵌套完整观察89条：冻结prepare23、P1 17、store.save3、store.verify14、Gate1 verify15、inspect15、normalizer1、loader1。normalizer/loader仅属建立唯一正常装载的小样阶段。公开函数profile还包括 save内部的Gate1 prepare（公开prepare入口合计6），不与29次直接调用混称。profile与完整条目按层分别相等。

local_validation.json 另行独立读回核对29/89的唯一ID、每个成功Gate2返回完整规范指纹、实际引用三时点、旧函数AST原文语义、末端位置及文件身份。源接收器未新运行，旧 checker stdout/stderr/quality报告实读哈希在 summary.results.source_receiver_evidence；子进程内部核心次数 null。

## 6. 四个真实 CLI 收尾控制

证据：`data/runtime_gate2_request_tests/task029_finalization_01/closure_controls.json`，各命令/stdout/stderr齐备。四个新进程均走测试 main，读取 run_04 冻结观察，不再接收或建立业务链；源证据逐文件哈希前后相等。

- replay none：0 / PASS / failures空。
- candidate-return：首个实际返回的候选载荷增加probe，由真实 canonical 内容审核拒绝；1 / FAIL / failures非空。
- ledger-late：真实 finish 已完成内容/台账消费、进入原始字节循环后追加LF；1 / FAIL，drift:file_ledger.json，命中1。
- checks-late：同一真实边界追加LF；1 / FAIL，drift:checks.json，命中1。

两类晚变更的 control_observation.json 登记真实边界、前后长度/SHA。没有按注入标志直接判失败，没有刷新期望、回填坏字节或重建台账；失败元数据如实写FAIL，坏checks/ledger保留。各replay目录的29/89为历史观察载荷，新增业务调用0。

## 7. 过程记录与未重跑

task029_run_01实际退出1（18项/2失败）：HOLD定位断言错误，和profile计数误取观察别名。还在代码核对中修正了测试返回副本与API登记对象共享引用的问题，避免无别名控制改写原始观察。未篡改首轮证据。

修正后 run_02、run_03 各18/0、退出0；期间逐步收紧成功请求inspect必须1、直接新API入口必须1，并修正摘要中公开profile与冻结计数混列，最终run_04再次完整执行本卡小入口。三轮通过不冒充三个独立架构验收；前两轮保留过程现场。

四个数据轮真实总计直接API116、Gate2请求76、normalizer4/loader4；每轮只建立一个正常装载和两个Gate1前提样本。最终有效结论仅依当前定稿run_04及四CLI控制；早期代码绑定不同的旧运行凭证按历史现场保留，不迁移。

TASK-026/027/028历史大套件、writer/loader故障大组、真实junction新建、Gate2保存/筛查/复算/事实/真实初判/AI/终判、开发宿主/控制器动作均未执行，相关计数null并注明原因。没有新接收批次、没有新身份/决定夹具或任何真实人类批次批准。

## 8. 保护与交付状态

本回执、代码、测试、指南和局部验证定稿后，运行一次最终完整保护扫描。实际保护结论及全量确切新增路径以 `data/runtime_gate2_request_tests/task029_finalization_01/protection_result.json` 与 allowed_new_paths.json 为权威，不在扫描前预填计数。扫描后仅有限登记本轮 delivery.json 元数据，不改写本回执/代码/测试/指南或旧证据。

保护要求：changed只能为runtime_gate1.py，其他新增均为四份交付文件/本轮明示根展开的确切路径；无前缀兜底；范围外变化/新增、新missing、读取错误为0。139历史损失、27精确恢复、326越界及19命名偏差继续单列，不重建不追认；其实际核对结果随扫描记录。

看板只读访问返回“dsh web authentication required”，无法关闭 TASK-028三卡或将本卡移至in_review；未修改任何看板状态。本地授权实施和完整交付已继续完成，待Architect独立验收及有认证权限的看板操作。

本卡停止于内存候审请求，未制定或实施下一任务。
