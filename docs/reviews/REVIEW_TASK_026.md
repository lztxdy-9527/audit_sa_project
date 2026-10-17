# TASK-026 验收：NOT_ACCEPTED

日期：2026-10-15。**本次不通过，不推进TASK-027。** 原三API/无CLI/无下游的范围保持；修复属B类，不引入新架构或新的业务决定。

## 通过的部分

四份交付实读身份与交接一致：runtime `360be2f50d441f0c7d8c883704bba3da6c57b57920ef6e83ed4bce7b4db834a5` / 43166 B；test `f15681114d59b5a08ccf2d6643afb0a981828d3318d6f7382c8011fdc389f633` / 39889 B；guide `3928887b9f8fee78766aca488afd101143c5b30e0cb05e6a69c571d20ffce62e` / 5932 B；回执 `4dd216e81cdbcfc88be61ec0821b40f6c1efac0b7f09637f84333bde02df77a4` / 11456 B。

GPT实际调用正常read/prepare成功；按现实现要求提供旧已存在scope时build也成功。外层3/2/2、正常13键登记/六键请求、14/32构成及当前false边界可用。既有文件保护另见末节。这些局部事实不等于正确实现了任务卡或失败阻断。

DSH的91项结果是**读取的执行端结果**。GPT没有重跑原测试入口：它把源/运行叶硬编码为task026_run_01，fresh_leaf会删除旧目录；换out-dir也会重写旧现场。不能为了复验破坏历史。

## B1：三API末端确认仍会误报成功（阻断）

GPT使用真实函数包装器，先返回/保留真实读取结果，再仅改本轮隔离目标，不改输入对象/预期，不修改生产代码。

- `build_late_output`：真实readback读取返回之后给登记文件加LF，**build返回成功**；返回registry_file_sha256已与磁盘不同。`_final_confirm`只重新解析JSON，没有和已绑定原始字节比较。
- `read_late_output`：初始两文件读取之后，在真实`read.self`返回时给登记文件加LF，**read返回成功**，返回SHA与磁盘不同；没有末端复测。
- `prepare_late_readback_LF/failure_added/unknown_added`：真实source核验返回后，分别改readback、加failure、加未知文件，**本次prepare均返回PREPARED**；撤销包装后的新read分别拒绝。末端只看registry本体，漏readback/目录集合/failure。
- `late_source_result.json`：GPT真实运行冻结接收器一次创建新隔离批次（退出0），正常build/prepare成功；其后另一build在真实source核验返回后仅给该新批次input追加LF。**build成功，但registry.batch_files里输入SHA与run_binding.input互相矛盾**。来源读数没有固定/收尾确认；不能称“同缓冲及来源变化必阻断”。

定位：runtime `build_runtime_registry/_final_confirm`（563/635附近）、`read_runtime_registry`（645附近）、`_final_confirm_request`（822附近）。原始记录与命中次数见本轮api_records/extra_api_records/late_source_result。最后成功必须建立在全部已消费文件的初始或writer读数上；正常本地变更检测是原卡要求，不是新增同权限攻击防御。

## B2：恢复schema、跨字段绑定与I/O映射不足（阻断）

隔离副本中只改变目标并同步外层readback的对象/字节哈希与长度，排除“外层摘要先失败”的遮蔽：

- `note=""`、`contract_effective=false`、`code_manifest.entries=[]`、配置SHA错、input未知键、batch_files.byte_size变float，read均接受。
- run_binding.code.manifest_fingerprint追加LF，**同步registry.run_binding_sha256及全部外层摘要后仍接受**（extra_api_records）；初次未同步内层摘要的反例提前被拒，仅作早期检查对照，不作为这项证明。
- code_manifest=[]、registry顶层=[]均泄漏**原生AttributeError**，不是定位Blocked。
- 真实Path.iterdir接缝抛OSError，read直接传播**原生OSError**，未映射RuntimeGate1Error(stage)+cause。

read只核对少量常量与当前自身SHA，未完整核验嵌套封闭键/严格类型/清单集合/排序/六项派生关系和当前静态字节。构建端也没给冻结prepare自身的SHA提供独立预期：冻结准备器的21项字典不包含其自身，而本层直接动态加载并接受其实读值。不得把“自己读取自己并与自己比较”作为冻结身份。

## B3：scope规则反转，路径收尾不足（阻断）

原卡§4明确：scope是**尚不存在的计划路径**，本卡不建scope/记录；已存在scope拒绝。实现`_check_scope_dir`和read却要求scope已经存在。GPT实际验证：合法未存在scope被Blocked，已存在scope被接受；指南/测试还把相反行为写成正向期望。

另 `_read_project_file`、批次内部文件/最终确认没有独立逐级reparse检查；`_is_reparse_point`把所有lstat OSError变成false。原卡要求检查原始路径、固定集合及末次路径状态，不能依靠较早一次冻结准备器检查覆盖后续窗口。此项依据源码；本轮未另建junction，不声称运行了真实junction反例。

发现 `data/human_gate_decision_records/gate1/task026_run_01_scope` 为空目录，创建时间为本机2026-10-15 02:28:32。它不在本卡允许新增根中；文件哈希扫描不能发现空目录。本轮未建立创建者证据，**不据此断言是谁创建**，也不删改/追认；执行端需说明来源。GPT只引用它复现现实现行为，不表示认可用旧scope绑定新登记。

## E1：测试证据不支持关键声明（阻断）

1. “半写”实际在**完整registry写完后**生产INJECTION_HOOK抛OSError；没有部分write、没有进入真实writer的except OSError分支。可称写后受控异常，不能代替卡要求的真实独占句柄半写。
2. install_guards加载另外的临时module，函数替换没有装在实际消费的模块上，也没覆盖全部下游；三个计数始终是初始0。不能用它证明实际入口0。
3. 只保存summary/checks/failures等，未落完整API/真实prepare返回/异常记录和call_id对应；没有文件台账，也没用同一审核helper删登记/改载荷做隔离自测。报告所说“组2错绑定/组4改登记被API拒绝”是业务反例，不能替代证据登记审核。
4. 收尾audit仅比较总数与名字唯一。若checks中的ok变false但总数不变，仍可audit_ok；audit失败时也只打印，不把FAIL和非空failure落盘。关键原文记录缺失，无法补做可信的旧终审，因此应修正测试后在新容器验证。
5. out-dir未经允许根/新目录约束，业务路径硬编码且删旧现场，不能作为可重复验收入口。

这些均为原任务卡§5/§6已有要求。修复使用小型记录和共享审核helper即可，禁止复刻TASK-024的庞大观察框架。

## 实际执行、过程局限与保护

GPT原隔离脚本23次API记录，额外脚本2次API，新接收源脚本3次API：**共28次登记的直接API调用**（不含prepare内部嵌套read，不声称等于全部入口帧）。一条未存在scope负向、若干恢复反例和晚变更已实际执行；不是28项通过。真实接收器CLI一次；其子进程内入口次数未观察，记null；没有标准化/DB/业务后链、P1/store公开入口执行。额外脚本用代码帧观察到P1/store/normalize/load为0，覆盖范围仅该脚本两次API，不外推全部运行。

第一次来源隔离副本因目录名与batch_id不一致而提前拒绝；第二次保留目录名后又因报告绝对workbook.path提前拒绝，命中均0，**不作晚变更通过/失败证据**。随后用一次真实接收建立合法新批次，得到上述明确复现。source_probe首次写成非法关键字语法，运行前解析失败；修正后才执行接收。均发生于最终扫描之前，无历史回写。

GPT一次最终全树文件扫描实读157436文件：changed=[]，范围外新增/missing/读取错误均0；旧R5越界326项逐项不变、不追认。所有本轮新增按确切路径登记，无前缀豁免；原上轮两个自指元数据单列。冻结实现与本次交付均未被GPT修改。这项文件级保护通过不替空scope目录补授权，也不改变本卡NOT_ACCEPTED。扫描后只有限核对身份及定稿本轮评审/基线元数据，未二次扫描。

DSH保护脚本使用startswith前缀豁免，还残留旧024说明；本轮按实际文件独立比较。其回执自身字节表11462与最终实读11456仅登记为非阻断辅助差异。symlink的WinError1314只能说明该symlink尝试失败，**不能推断mklink /J也不可用**；未执行不计PASS。不要求为本轮再扩大测试场景。

## 后续

交 `docs/tasks/TASK-026-R1_DRAFT.md` 定点修复上述四组。工作区当前代码保持原交付，GPT未代改实现/测试。修复通过前不制定/实施TASK-027；不接Gate1保存/有效批准/标准化/数据库/Gate2。真实批准null，开发宿主0008，next/AI false；人类处理看板。
