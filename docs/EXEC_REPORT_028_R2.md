# TASK-028-R2 执行回执（GPT 执行端，待独立验收）

日期：2026-10-15。依据 TASK-028-R2_DRAFT.md 与 REVIEW_TASK_028_R1.md。人类授权 GPT 接替执行端，
范围不变；本回执只报告实施与实测，不宣布架构验收通过、不批准任何批次，未推进下一任务。

## 1. 起点和范围

三件起点逐项 SHA/长度与任务卡一致，基线 `data/reviews/task028_r1_gpt_20261015_185902/source_hashes_after.json`
162842项、SHA `ff2c2c4e07b44b509adfe3c6476d8215a583f79628afac094199e7db3d3ce81d`，verdict=NOT_ACCEPTED。
只修改 runtime_gate1.py、本任务测试及指南；新增本回执和 task028r2 明示新根。原字节保全在
`data/runtime_approved_load_tests/task028r2_setup_01/backup_manifest.json` 所列三份单文件副本。

旧五 API 的 AST 与起点相等；未改准备器/P1/store/业务核心/schema/契约/配置/宿主/旧测试指南/旧证据。
未进行递归删除/移动/清理。新反例只对本轮自己创建的产物作受控改写或精确恢复，坏副本另存。

## 2. 修复内容

- B1：两个真实核心入口前复用起始 capture 检查来源/登记/事件八文件、固定集合和锁；
  report 读回与该次 writer 缓冲精确相等。成功返回对象在最终只读确认前构造。
- B2：文件大小使用严格整数 helper；inspect 传已有 workbook_capture；source 七键、字段类型、
  输入/checker/spec路径及SHA闭合；net_checks 固定六键、每项严格true。保留四表只读实查。
- B3：按实际模块异常类对象分类；完整 `.reasons` 列表保存在现有 reason，cause/context 不丢；
  failure 六字段、版本及类型先验后消费，不新增协议字段。
- E1：观察实际消费引用三时点及完整快照；末端覆盖七载荷+台账，预期来自待写字节；
  终端后不读候选生成输出，实际审核/字节失败支配非零与磁盘FAIL/非空failures。

## 3. 实际执行与结果

修复前用实际 main 的 replay 分支复现“审核后台账LF仍0/PASS”，单次命中；源证据未变，业务核心0调用。
见 setup_01/probe_before.py、cli_post_audit_ledger.json 和独立新输出根。

最终命令：

```text
.venv\Scripts\python.exe -B tests\test_runtime_approved_load.py --only r2 --out-dir data\runtime_approved_load_tests\task028r2_gpt_run_02
```

实际退出0，41项/0失败，summary=PASS、failures=[]、problems=[]、drift=[]。

- 正常小样真实 normalize/loader 各一次，落盘报告与真实返回规范相等、四表2/1/3/3，inspect计算调用0。
- before_normalize context LF：命中1，field=gate1.context.json，两计算核心0；额外事件failure控制
  命中1，field=event，两核心0。before_loader LF：normalizer1/loader0，field相同。
- 真实report writer写完返回后把磁盘round_trip_exact改false：命中1，field=load_report.json，
  核心原返回仍true，本层failure与坏报告保留。
- 同值float/bool大小、输入SHA、source未知键/checkerSHA、net_checks=false六例独立隔离。
  每例先正常inspect、只改该例候选并同步直接依赖摘要、精确命中目标field；坏副本在isolated/。
  canonical键序变化对照成功。恢复的仅是本轮自建正常原件，没有覆盖旧现场。
- 两真实Blocked类各带两项不同reasons的受控映射均为Blocked/kind=BLOCKED，两项原因在API cause及
  磁盘reason可查。非法failure_version恢复定位拒绝。没有把注入的异常称为核心自行发现业务问题。
- 输入观察器负向控制实际调用normalizer一次，after点干净、API-end点记录同引用真实变化；
  用同一个audit_candidate对实际控制记录判出core_input_changed。控制完整记录单独留在summary.results，
  不进入正向记录集合，不通过修改豁免标志放行；真实profile计数包含该次调用。

最终轮直接API登记47条。真实原函数profile：normalizer5、loader2；正向完整核心记录6 + 隔离负向1=7。
Gate1内部P1/prepare/store计数和内部公开API调用分列在summary.observed，不与直接47条混同。

四个新进程实际main/CLI收尾：

- normal：0/PASS/空failures。
- 真实audit_candidate返回后ledger加LF：1/FAIL/非空，drift:file_ledger.json。
- 同一真实审核返回后checks加LF：1/FAIL/非空，drift:checks.json。
- candidate-return：1/FAIL/非空，实际独立预期内容比较拒绝。

完整command/stdout/stderr/实际returncode在
`data/runtime_approved_load_tests/task028r2_finalization_01/closure_controls.json`；候选新根
`task028r2_gpt_final_cli_*` 保留，重放源字节不变。重放中的47/6/41是旧观察，新增业务核心调用0。

## 4. 过程与全部执行口径

第一次定点 `task028r2_gpt_run_01` 40项/0失败，配套四重放控制也通过。随后定稿前为同一B1入口前检查
补充固定集合/锁状态，并增加一个failure控制；生产字节变化后用新运行/事件/库执行最终run_02。
run_01与其重放全部保留，不冒充最终代码证据。本轮无失败的实现测试尝试；修复前复现是预期缺陷观察。
没有在局部阶段做全树扫描。

两次定点业务轮合计真实normalizer10、loader4；最终轮5/2单列。两轮直接API分别43/47。
四个首轮收尾与四个最终收尾合计8个进程；另修复前复现1个进程，均为只读观察重放，不重复接收/建链。
本轮新接收0，未新建data/batches根。技术锁只按既有经身份核验的释放逻辑删除本次自锁。

## 5. 对R1证据声明的更正

R1的B2反例累积修改一个坏场景，后续被早期错误遮蔽；R2改为每例干净对照和唯一候选、明确field。
R1“float”实际删了键、“删allocations”实际改normalized列表；不能称为对应路径的实测。
R1调用前改文件不称为最后消费后的晚变更；R2入口前/写后/审核后接缝分别标识，不互换。
R1未完成台账真正终端确认，且终端后仍读failures；R2删除该后置读取，终末循环含台账。
R1未记录两内存输入三时点；R2已补，工作簿字节前后与对象指纹分列。
以上只写在新回执，旧回执/检查/扫描/坏现场均未回写。

## 6. 保护与交付身份

代码/指南/本回执定稿后执行一次完整扫描，实际结论及逐项新增清单见
`data/runtime_approved_load_tests/task028r2_finalization_01/protection_result.json` 与 allowed_new_paths.json。
扫描后仅有限登记交付元数据，不重扫全树；实现/测试/指南最终SHA与字节长度见同根delivery.json。
本回执自身不内嵌自身SHA，最终值在交接消息及delivery.json登记。

历史误删原166、精确恢复27、仍缺139，按事故登记单列，不重建、不清零；R5越界326和旧命名偏差保护。
不得把当前基线新missing=0解读为历史139已恢复。扫描范围合规不等于技术验收通过。

## 7. 未执行与停止点

原42项、R1的31项、TASK-026/027及冻结核心历史大套件未重跑；已关闭writer/loader错误大组仅引用旧证据。
未建新junction/符号链接、未直接调用checker或接收器、未运行开发宿主/控制器/其他下游，
未执行的运行检查记null+原因，不能填测试通过。未初始化Git、安装依赖、引入网络或新生产模块。

看板未操作；交付待原架构会话独立验收，done由人类处理。真实批准null、开发宿主0008、next/AI=false。
本卡完成后停止实施，未制定/实施TASK-029、Gate2、筛查、事实、初判、AI、终判或0009。
