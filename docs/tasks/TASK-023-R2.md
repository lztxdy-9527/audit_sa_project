# TASK-023-R2：补齐helper完整观察保存与终审闭合

日期：2026-10-14。**B类，DSH处理**。依据 `docs/reviews/REVIEW_TASK_023_R1.md`。生产B1/B2/B3及快照、checks LF漂移已关闭；本卡仅修剩余E1证据层，不重开已通过实现。先建看板卡，完成后停止实施交GPT；人类操作看板。

## 1. 严格范围

只允许修改 `tests/test_prepare_demo_human_gate1.py`（起点SHA `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518`），限helper观察、登记/保存/终审及必要定点验证；可同步指南 `docs/HUMAN_GATE1_REQUEST_GUIDE.md` 的受影响证据说明（起点 `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f`，非必改）。

仅新增 `docs/EXEC_REPORT_023_R2.md`、全新 `data/human_gate1_request_tests/task023r2_<唯一轮次>/` 及同轮 `data/batches/task023r2_<唯一轮次>/`。旧回执/评审/测试产物/批次/junction全部冻结，不执行旧脚本、不覆盖、不清理。

**生产适配器冻结**SHA `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`；配置 `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`、P1/存储/契约/生效登记/receiver/checker/宿主/控制器/业务文件全部冻结。不新增或变更生产API、31材料、P1字段、质量/路径/ID/快照行为、Gate时序/历史/执行边界。

基线 `data/reviews/task023_r1_gpt_20261014_031403/source_hashes_after.json`；先实读同目录NOT_ACCEPTED及清单完整SHA/项数和两个确切自指排除。它是施工起点，不是验收通过。

## 2. 根因与必须修正

当前HelperObserver.payload的14条records只在内存，未进入最终bodies/PAYLOAD_FILES/真实观察expectation；entry没有完整输入快照。收尾helper只比两个total，实际条目数/ID/完整性未核验，导致“实际14次、声明14、完整entry13”仍70项PASS。

### 2.1 完整真实观察与保存

- 在进入**真实冻结validate_report函数前**保存实际输入快照（如inputs.report），及其规范指纹；保留同一引用核对调用后指纹。保存完整真实返回，异常保存真实traceback/field或stage/reason（适用时）及cause/context链。不再调用helper/P1生成对照，不改入参/返回，不在I/O守卫内写文件。
- 增加一份固定测试载荷 `helper_call_records.json`，至少保留当前total与完整records；每条有唯一call_id、实际完整输入、真实完整返回或异常。返回[]是合法完整结果，不能用bool(result)把它判为缺失。
- 将该文件纳入实际待写缓冲、PAYLOAD_FILES、文件台账、首轮同缓冲读回、字节漂移确认及完整canonical内容比较，不能放入layered/extra豁免。完整预期在终审之前直接从本次真实观察独立深拷贝定稿，不从候选磁盘或“已截短的待审核payload”刷新。

### 2.2 实际计数、ID与载荷闭合

- 以函数代码对象或等价的轻量真实入口观察分别计数prepare、P1、冻结validate_report；与各自完整记录分列闭合。可扩展已有P1 profile回调，不能在每个Python帧中做文件路径解析，不包装外层API冒充helper次数。
- 实际收尾审核同时核对：独立helper入口观察数、声明total、records长度、registry.helper_call_ids与record.call_id双向唯一集合、完整记录。缺/额外/重复ID、缺entry、空壳entry、声明与实际不符均拒绝。保持prepare/P1现有正确审核，不把P1次数要求等于prepare。
- 名为disk的收尾审核应消费本轮_audited_read得到的实际候选对象；只把内存对象再审核一遍不能称磁盘审核。实际独立观察数/固定完整预期仍来自内存真实观察，两类来源明确分列。
- 完整内容主判据继续为canonical JSON字节相等，任一输入/返回/异常/关联字段被合法形状改写也拒绝，不靠计数和schema替代与真实观察的比较。字段差异按helper call_id定位。

## 3. 最小验证

先做隔离审核，不再建业务链：正常完整原件通过；只删一条helper完整entry、保留total/ID/入口数 → 同一实际审核helper拒绝；删ID/重复entry/空壳entry各必要控制拒绝；合法[]返回原件通过；只改一条返回为合法字符串列表 → 完整内容比较拒绝并定位。所有隔离调用如实登记，不声称运行生产函数。

再一次新正常完整本卡入口：原70项及实际新增项通过、prepare/P1/helper完整保存并与真实入口观察闭合、台账含新增helper文件且与磁盘字节一致、独立完整预期与同缓冲候选一致。保留生产prepare的P1/存储0、只读守卫0及干净/故意变化scope。子进程内部未知次数null。

一次分离新轮次的**真实套件helper缺entry故障**：在helper文件已经完整保存、固定真实预期已定稿后、首轮终审读取前，只从磁盘helper_call_records.json删一条完整entry，保留total/registry ID/实际入口观察数。调用真实reader并返回原值，不替换审核结论。套件必须**非零、summary FAIL、failures非空**，定位缺失helper ID/载荷；不回填或重建候选凑PASS。可以另用评审原“真实payload返回后删entry”的隔离方式确认计数闭合，但不能用它替代磁盘故障验证。

本轮**不单独重跑已通过checks LF完整故障、来源/链接/ID生产定点、P1/存储历史入口**。正常入口已有覆盖继续保持；若实际修改了首轮读回/漂移确认/失败写入顺序，则明确报告变化并仅补必要LF故障，不无限扩大回归。

## 4. 不退化的收尾

完整实际观察定稿 → 一次性最终载荷写入 → 首轮同缓冲对象与SHA审核 → 任何后续写入前按保留读数做真实字节漂移确认 → 正常路径只保存台账。不得恢复第二次write_bodies覆盖候选、重新采集已漂移文件当期望、无限“改文件→重建台账”。

内容/ID/entry/计数/台账/漂移失败必须追加正式failures、FAIL、非零及诊断，保留坏载荷；异常不包装成功。失败写入摘要/诊断如实说明，不能称失败台账与已更新摘要仍全部一致。未执行写null/not_executed，不默认零。

## 5. 保护、回执与停止

局部通过后一次正常入口、一次缺helper entry故障；全部文件定稿后一次最终全树保护。changed仅允许测试及实际改过的指南；生产适配器和所有其他旧件不变，missing/读取错误/范围外变化/新增0。按本轮确切文件/根逐项登记，无前缀兜底；扫描后只有限登记身份，不改测试仍声称原扫描有效。

回执区分完整真实helper记录、独立入口观察、磁盘候选及固定预期四者；写实际正常/故障返回、记录字段/数量/台账、保护身份/次数、过程及未执行。R1回执实际13839字节、SHA `882c19ce9f403972d6064ffaa59282c347f552b721a217bc461b44ccee74be50`（原交接仅给字节数，未给SHA），不伪称旧哈希不一致。新回执自身最终SHA只在交接给出，不写回自指。

若需修改生产/配置/冻结上游或改变原范围，立即停止受影响处理、保留现场并报告重新定界升级，不扩大本卡继续。验收通过前不制定或实施TASK-024；真实批准null、next=false、AI未开放，人类继续负责业务判断和看板。
