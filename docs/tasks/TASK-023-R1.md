# TASK-023-R1：来源闭合、逐级路径和真实终审的定点修正

日期：2026-10-14。**B类，DSH处理**，落实已批准TASK-023设计，不修改架构或冻结上游。依据 `docs/reviews/REVIEW_TASK_023.md` 的NOT_ACCEPTED及同名评审根实际探针。人类操作看板；实施前建卡。完成后停止实施交GPT，不推进TASK-024或Gate接线。

## 1. 严格范围

仅允许修改：

- `scripts/prepare_demo_human_gate1.py`，起点 `5e8ed565cc6567b210c65c475ec16a8e2f271da49b4bcb6a745cad6cb329da02`。
- `tests/test_prepare_demo_human_gate1.py`，起点 `4e7662f599c665ea3ea43fc6809c2ae25c863c79cdc537ea73efed0ec3c9dcae`。
- `docs/HUMAN_GATE1_REQUEST_GUIDE.md`，起点 `0230ac8787743f002adbe27dab275d4697b60ab304cce335c06ffca1c3e6458f`。

仅新增 `docs/EXEC_REPORT_023_R1.md`、全新 `data/human_gate1_request_tests/task023r1_<唯一轮次>/` 与同轮 `data/batches/task023r1_<唯一轮次>/`。旧现场、回执、评审、junction均冻结，不删除/迁移/补写。

新配置也冻结：`config/human_flow_v1.json` SHA `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`。P1、存储、正式契约/生效登记、receiver/checker、宿主/控制器/规则/其他原文件全部冻结。

基线 `data/reviews/task023_gpt_20261014_023810/source_hashes_after.json`；先实读同目录review_result的NOT_ACCEPTED、完整清单SHA/项数及两个确切自指排除。不得以旧ACCEPTED清单漏掉本轮已交付文件；NOT_ACCEPTED是施工起点，不是验收通过。

唯一生产API、六/七/八/七/七键形状、31材料、契约与运行绑定、质量映射和只读停止点全部沿用TASK-023，不增字段、不接存储/历史/宿主，不生成决定/身份/时间。

## 2. B1：来源与独立冻结预期闭合

1. **所有既有项目材料**逐项与独立冻结SHA比较，覆盖现有代码/SQL及遗漏的SPEC、旧契约草案、schema、正式契约/登记。用统一小范围校验即可，不只比较候选初始/末次值。新adapter仍无自指硬编码SHA，新config按既定精确对象及canonical+LF核验。
2. 把接收器实际声明与同次真实读数闭合：hashes.receive_script/checker的固定path、before/end SHA、stable；hashes.spec/contract_draft的path/exists/read_error/SHA；checker_invocation.report_result、report_checker_sha256与报告实际字段/冻结checker相等。沿用冻结接收器实际字段名/路径，不臆造新producer协议，不跟随其original_path/argv读取外部文件。
3. 必须为null的消费字段先确认键存在，再检查null，包括gate1/gate2_approval、failure.stage和各消费read_error。缺键不能被.get(None)当作合法凭证。只补本卡实际消费字段的必需性，不重写接收器完整schema。
4. config.synthetic_data必须严格true，整数1不能冒充；其余固定值同样核对类型和值。冻结配置文件不改，反例用真实reader的受控读缓冲映射，不声称修改了冻结磁盘。

最小反例按评审probe_records各单独隔离：接收器end SHA错、checker stable=false、report_result矛盾、report_checker SHA错、删除approval/read_error、SPEC/draft/schema分别变字节、synthetic_data=1。初始与末次映射使用同候选、保持其他字段合法，证明拒绝来自独立关系/类型而非晚读不一致。均须公开API Blocked并精确定位；正常/合法BLOCKED对照保留。

## 3. B2：逐级路径及I/O边界

31份消费文件的原始路径逐级检查祖先目录（含允许根），然后resolve复查；不能只检查批次根和最终文件。固定source/checks/logs/code_snapshot目录及项目路径也不能包含link/junction/reparse，文件须正常文件。复测仍保留该要求。不改变data/batches严格后代规则或白名单。

真实子目录junction最小例：在本轮独立新接收样本把checks移至本轮新目标，以原checks路径建立真实junction；业务字节/声明不改，先正常对照。公开prepare须Blocked并指向路径，源/目标字节不变；现场保留，不改旧junction。可复用本轮已有接收样本作此独立场景，不为每个轻量反例重建链。

lstat/枚举/stat/resolve失败应Error(stage)+原cause，不能吞OSError返回“无链接”，重复枚举同样放入错误边界。补一个受控路径检查OSError的公开API例，标为映射注入；不以catch-all或默认false替代具体检查。已有末次final_read Error例保持。

## 4. B3：普通ID保真

删除request_id的isprintable限制，只拒非字符串及空/纯空白；不strip保存值、不改大小写、不强制数字/前缀。嵌入LF、首尾tab但非纯空白、前导零、64hex形状与指令样式文本均是普通字符串。

删除按批次叶目录名子串推断下游身份的限制。八文件/目录严格集合已可拒绝实际workflow/下游产物；合法decision_review之类批次名必须通过并精确绑定。保持对实际未知文件/目录、模拟凭证的拒绝。至少一个真实receiver成功建立的此类合法批次与请求原文对照，不用改字符串避开限制凑通过。

## 5. E1：真实终审、登记和观察时点

- 保留真实观察预期来源：全部观察完成后、首次终审读取前深拷贝定稿；完整API/P1/helper/权威登记不从候选磁盘取预期、不刷新，不再调用P1造“相等答案”。canonical字节相等作主判据，保留类型区别。
- **首轮审核读数必须在任何后续写入前做实际字节漂移确认**。当前第二次write_payloads覆盖checks并重新采期望的方式必须修正。可有界两轮更新明确的审核元数据，但完整观察载荷不应无意义重写；每次合法待写缓冲与保留的首次读数明确分列，不能采集已漂移的磁盘当新期望。
- 实际故障：真实_audited_read返回原缓冲后，仅给checks.json加LF。套件必须非零、summary FAIL、failures非空并有具体诊断；保留被改checks字节，不重建台账/抹掉变化凑成功。失败时可写summary/failures/独立诊断，不能覆盖被改文件后继续PASS。这是终审故障，不是生产文件故障。
- 新增小型**实际收尾使用的登记审核helper**，核对prepare/P1/helper完整调用登记与实际入口观察/记录。隔离自测只删审核副本的一条权威登记，必须调用同一helper失败；不再在隔离函数内手写另一个比较充当真实审核。不要为此建立新的通用框架。
- prepare和冻结validate_report实际调用分列；helper观察真实函数的入参/返回/异常，不包装宿主API冒充helper次数。现有P1代码帧观察保留。观察时不写盘，解除守卫后保存完整结果/traceback/cause；子进程内部未知次数null。
- project_snapshot_before移到API之前实读，调用后另测并核对；不把两个调用后值称前后。故意晚变更与干净调用scope分列，避免“全部前后相等”与实际false矛盾。台账/完整内容/登记审核失败必须支配返回码，不默认missing/unregistered为0。

## 6. E2：快照真正有界

对data/、data/batches/、项目根或越界/非合法接收目录，只登记路径、存在性及有限首层观察，**不得rglob/递归哈希**。合法批次固定八文件，按已知八路径及有限目录项检查；如需额外场景目录，必须设置实际遍历条目预算，不能只用首层数量≤60判定整个子树很小。

先做一个隔离快照对照：data/首层仍少于60也不递归、不读取历史内容；合法八文件快照仍保真。随后才跑本卡入口。不得为修局部问题反复做全树扫描或重建业务链。无需读取/哈希所有历史目录来证明一次越界拒绝。

## 7. 最小执行顺序与交付

1. 先修/验证E2及上述各独立API反例，复用最少的新接收样本，保持原字节与干净/故意变化分列；未通过不跑最终全套或全树扫描。
2. 一次新正常完整本卡入口：原52项及实际新增项通过，31文件/质量映射/P1三对照/只读/无别名等保持；真实API/P1/helper/CLI完整登记，台账及内容实读一致。
3. 一次分离新轮次的真实终审checks LF故障：真实reader/写入分支，非零/FAIL，不用包装脚本退出0代替套件返回。不得再跑已验收TASK-021/022或宿主/历史入口；不新增Gate2/DB链。
4. 测试、指南、新回执全部定稿后一次最终保护：changed恰为本卡实际修改的adapter/test/guide（指南若未改须如实），其他旧文件不变；missing/读取错误/范围外变化/新增0。按本轮实际根逐文件确切登记，无前缀豁免；最后仅有限身份登记，不改实现声称旧扫描有效。

新回执写逐组关闭证据、实际调用/计数/时点、正常与故障套件真实返回、字节漂移保留、保护基线/次数/起点及最终SHA、过程/未执行。原TASK-023交接回执为12890字节/7b29f7ad…，GPT实际读到13438字节/`fb01538fadfcc93949a188a5a5f83c548cab17137835edd60208b81c8554e44a`；只在新回执更正并解释，不改旧回执。新回执最终自身SHA只交接，不写回自指。

发现需扩大到配置/冻结上游/P1schema/31材料/允许根/Gate时序/历史/执行边界，立即停止受影响处理、保留现场并报告重新定界升级；不在本卡继续扩大修改。真实批准仍null、next=false、AI未开放；人类判断及看板由人类负责。
