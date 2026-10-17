# TASK-036-R1 执行回执：原始路径链及辅助失败诊断

状态：执行端交付，等待 Architect 独立验收；不自行 ACCEPTED，不操作看板，不推进 TASK-037。范围仍为 `STORED_SNAPSHOTS_ONLY`。本回执在最终全树扫描前定稿；扫描实际数值及交付身份由本轮 `protection_result.json` 和 `delivery.json` 有限发布，回执不写入自身哈希或尚未执行的保护零值。

## 1. 依据、起点及修改范围

依据 `docs/tasks/TASK-036-R1.md`（SHA `47b12250c4d43ba4973690fd0d4c8821b05ff33d72525b6cd4e01a3709c72972`）、`docs/reviews/REVIEW_TASK_036.md` 和 `data/reviews/task036_gpt_20261016_190210/review_result.json`。已有限检查适用 AGENTS.md，未发现。未调用子 Agent、跨会话消息、网络、Git 或新依赖。

修复保护起点为 NOT_ACCEPTED 观察快照：167210 项，SHA `d122a56245cb2800fbd76759ee748dbe85dc77304534d449bc84ec0f28c46494`。最新接受基线仍 TASK-035-R1，166390 项，SHA `63ba73224065bdcdf53538b58a23d966ab6469aed8cdf7330445846828005948`。两份基线、任务卡及冻结源均逐项实读核对；原字节保全见 `task036_r1_setup_02/starting_identity.json`、`store.before.bin`、`test.before.bin`。

仅修改两个既有文件：

- `scripts/store_demo_human_initial_judgment.py`：25318 B / `ff25a5b5d82b76ca17d2edd745f287b9b816ba684d44ece83023109b5e6c194c` → 25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`。
- `tests/test_store_demo_human_initial_judgment.py`：32446 B / `77182f1f509a4a0ab9e62b3840ab568589a0a16fbb93d825d996c8a8f6f2974f` → 38400 B / `68c802e6ea1872acc67d4021bc1c3119039fa6298b248328a8576c5eefd3c66a`。

新增仅本回执与任务卡明示的 `task036_r1_*` 测试/合成记录具名根。旧指南 7305 B / `d6e98f8116b0d5df2b3a646490ea8f65490836f7162dfd4bbb407b33d594c450`、原回执 14468 B / `fda1e58b2790de7653c145601099cc8200dc43b70bbfa912595e42284d716e7c` 均冻结，仍表达原 1.0 时点。完整交付长度与 SHA 以 `task036_r1_finalization_01/delivery.json` 为入口。

补丁版本为 `TASK-036-human-initial-judgment-store-1.1`。AST 对照确认仅 STORE_VERSION 常量改变；其他模块常量、两个公开签名均保持。manifest/failure 协议版本、failure 十键、六文件、十一键返回、核心八 false 与存储九 false 不变。未新增生产模块、CLI、通用路径或异常框架。

## 2. 修前复现与保全

在生产修改前执行新根脚本 `task036_r1_setup_02/prepare_and_reproduce.py`，退出 0；证据 `before_observations.json` 保存 4 条完整公开 API 和 4 条真实嵌套核心观察。源码身份与上节一致，普通 alias 为本轮新建正常目录。

- B1：仅对 alias 段真实 `lstat` 返回附加合成 reparse 属性。公开 verify 和 save 传入 `alias/../leaf` 均成功、alias 命中 0；同一 `_reject_chain` 私有对照实际命中 1、Blocked(record_dir)。私有对照不计入公开 API 或核心。
- B2：真正 `xb` 句柄写入 expectations 缓冲一半并 flush 后抛主 OSError；第一次技术登记真实成功，第二次诊断技术登记抛受控 OSError。顶部实际为裸 OSError、stage=null；主 StoreError 仅留在 context 中。半文件保留、failure 未建。

这不是物理 junction 攻击验证；仅是源码问题及合成元数据控制的公开入口复现。输入/返回或 traceback/cause/context、父调用、原引用三时点、I/O 场景均落盘，不将旧评审调用冒充本轮调用。

## 3. B1 修正及修后实测

`_resolve_leaf` 先把原字符串构造成 Path。正常绝对/相对路径以 cwd 连接；Windows drive-relative 路径仅查询该盘当前目录作为基座，调用方的 `alias/..` 段不参与 abspath。连接保留原段 → 原始逐级 lstat/reparse 拒绝 → resolve → 解析后严格根范围/链和目标形状检查。save/verify 共用此入口，无字符串黑名单、调用方绕过开关或基于人类 ID 拼目录。

定稿套件 `raw_path_controls.json`：绝对 save、相对 save、绝对 verify、相对 verify 四例，真实 alias lstat 各命中 1，全部以对应 `out_dir` / `record_dir` Blocked，核心增量均 0，save 目标未建。相对路径通过 `relative_to(cwd)` 保留原段，未使用会消去 `..` 的 relpath 来构造负例。

私有 raw-chain 单独控制：原函数代码对象 profile 命中 1，公开 API / 核心增量实测 0；与四条公开调用分列。新正常绝对及相对 save/verify 均成功，各真实核心 1 次，完整核心返回与独立预期规范相等。

物理 junction 动态控制本轮 null，原因是既有 OS 权限拒绝；未重试创建、未以合成元数据冒称物理 PASS。原命令输出仅只读引用 `task036_run_03/junction_probe.json`。

## 4. B2 修正及修后实测

`_write_failure` 的整个 failure 构建、主原因链、技术时间、规范编码和独占写入放入同一有限 try。任何诊断次异常只附在原异常 `secondary_errors` 和 args 中；原异常类、stage、reason、reasons、cause 不改。即使诊断 chain helper 自身失败，次错误保留使用实际次异常类型/args 的有限后备，不重新调用已失败的 helper，不生成替代时间或重试写文件。

`R1.diagnostic_clock` 使用真实生产 writer 的 `xb` 句柄：expectations 半写并 flush，主 OSError 原文 `TASK036_R1_REAL_HALF_WRITE`。第一次 `_registration` 调真实函数并保存返回；仅第二次抛 `TASK036_R1_DIAGNOSTIC_CLOCK_ERROR`。结果：

- 顶部为 `HumanInitialJudgmentStoreError(stage=write.expectations.json)`；reason 仍恰主 OSError 原文、reasons 恰其单元素列表、直接 cause 仍该主 OSError。
- registrations=2、真实半写命中 1、mode=xb；secondary 含真实诊断 OSError。原始 traceback、完整链及次错误落 `api_records.json` / `diagnostic_clock_control.json`。
- 半文件长度与本次真实写入长度一致，failure.json 未建，不编造失败凭证或成功返回。
- 撤销注入后对该不完整新叶 verify：Blocked(files)、核心 0；目录字节前后相同，不写 failure、不读当前时间。

原有 failure 写句柄本身第二 OSError 对照仍实际运行：主 stage 保留，主次原因均可见，0 字节 failure 保留。有效 failure 优先、非法 failure、核心精确 Blocked/Error 分类均保持。chain helper 后备分支仅按源码核对，不声称另做动态故障。

## 5. 定稿有限入口及观察闭合

实际命令（cwd 为项目根，Python -B）：

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_store_tests\task036_r1_run_02
```

退出 0；84 项检查 / 0 失败；真实内容审核与末次字节确认均通过、problems=[]、drift=[]。这是本卡现有有限存储回归一次定稿入口，未运行纯核心 156 项或历史 Gate/SQL/事实/运行大套件。

公开原代码对象 42 次（save 21 / verify 21），嵌套冻结核心原代码对象 17 次，调用父 ID 与实际增量闭合，不要求两层数量相等。API 结果为返回 7、Blocked 31、Error 4；核心返回 13、Blocked 3、Error 1。十三份成功核心返回均按冻结协议独立重建并完整比较。公开输入与真实核心消费输入分别保留同引用调用前/返回后/API 收尾三时点，原值和指纹一致。

正常完整六文件待写缓冲、manifest 和十一键 save/verify 返回独立构造见 `independent_normal_expectation.json`；技术时间仅取本次真实程序返回，人类时间/assessment/reason 保留已登记原文。实际返回对象无输入别名；FILE/FP、严格类型、错误完整结果防自比均保持。旧快照未迁移/补签：新 store 字节 SHA 已变，旧组件绑定按冻结规则失配；所有修后正例均新目录，未对旧记录执行重保存或修改。

真实晚变更：在完整返回构建后给本轮 judgment_result 加 LF，本次 verify Blocked；撤销 wrapper 保留坏字节仍拒绝；具名保全坏缓冲后只精确恢复本轮单文件原件，verify 成功。save 晚变更同样拒绝且有效十键 failure 保留。证据 `late_controls.json`、`late_judgment_result.bad.bin`；未递归删除、移动或清理任何现场。

网络/子进程/verify 时钟守卫原位置不变；三个权限拒绝 proof 与普通 guard_hits=[] 分列。verify 实际写事件 0、其他业务函数代码入口 0。测试控制的真实 I/O 入口单列，未为注入放宽 verify 权限。

## 6. 四个实际 main 新进程收尾控制

执行 `task036_r1_finalization_01/verify_local.py`，退出 0。有限审核完整载荷、七项台账、原引用三时点、84 检查、独立全返回及修前后控制后，启动四个真实 main 新进程 replay。命令参数、stdout/stderr 原文、profile 和结果见 `closure_controls.json`。

- none：0 / PASS / failures 空。
- candidate-return：1 / FAIL / failures 非空，由定稿独立观察的内容审核拒绝。
- ledger-late：1 / FAIL / failures 非空；末次读取后台账加一 LF，实测命中 1，字节确认拒绝。
- checks-late：1 / FAIL / failures 非空；末次读取后 checks 加一 LF，实测命中 1，字节确认拒绝。

profile 原代码帧实测四进程新增 save/verify/核心/其他业务入口均 0。源 `task036_r1_run_02` 文件逐项 SHA 未变；回放 42/17 仅是历史观察，不是新调用。定稿预期不从候选刷新，坏候选和坏字节具名保留，无按注入标志直接判失败。

## 7. 最终保护与交付入口

本地内容、代码、回执定稿后，执行 `task036_r1_finalization_01/finalize.py prepare`，有限绑定交付及本轮证据身份；随后 `scan` 仅一次遍历项目树，同时比较两个基线：观察快照检查本轮只能改两文件；接受基线检查既有 changed=[]、累计新增与本轮新增分列。允许新增先按具名根展开为确切文件名单，未用前缀兜底；旧观察快照自身及 review_result 仅两条确切元数据单列。结果见 `protection_result.json`，最后 `publish` 有限复核身份并发布 `delivery.json`，不再遍历全树或回写回执。

139 历史损失、27 恢复、326 R5 越界、19 命名偏差、TASK-030 具名 41 B 锁和全部旧 TASK-036 现场按既有身份单列核对，不追认、重建、补造、迁移、移动、清理或删除。139 不混入当前基线新 missing，也不清零。

本轮测试根明确为 setup_01、setup_02、run_01、run_02、finalization_01 及 cli_none / cli_candidate_return / cli_ledger_late / cli_checks_late（均加 `task036_r1_` 前缀）；合成记录仅四个同名 setup/run 根。新字段/新核心输入/人类文本/业务链均未引入。

## 8. 过程问题及未执行

如实保留两次局部失败：

1. setup_01 已运行修前控制，但证据 JSON 未编码 WindowsPath，落盘失败并保留 0 字节候选。修正仅该本轮脚本的路径证据编码，在 setup_02 新根重新局部复现；以 setup_02 完整观察为正式依据，setup_01 不冒充完整证明。
2. run_01 相对反例误用 os.path.relpath，消去了拟检测路径段，后续 err.field 对 None 取值失败。保留所有新建现场，修正为不消段的 relative_to 后在 run_02 新根运行定稿回归。run_01 不算通过，也不将不完整内存计数填入正式调用总数。

setup_02 的 4/4、run_02 的 42/17、四个 replay 的新增 0 分层，不混成一次入口统计。不完整过程观察总量未完整落盘的部分为 null+原因。没有修改旧目录、旧结果、旧回执或旧评审。

本轮未执行项为 null+原因：物理 junction（既有权限拒绝，未重试）；额外合法闰日/±14 人类正例（未提供登记原文）；诊断 chain 后备动态故障（仅源码核对）；纯核心全套及历史业务入口、运行接线、完整历史枚举、真实初判业务保存、AI/终判（超本卡范围）。

## 9. 业务边界与停止

固定合成业务、整数分/字符串 ID、主表与分摊分别计量、线索不是结论的口径不变。prior_history 仅验证调用方提供的声明快照，本组件不声称完整枚举历史或认证身份。

真实批准仍 null，真实独立初判未保存，开发宿主 0008，next/AI=false。技术快照保存和本回执不批准批次、不形成审计结论。交付后停止实施，交 Architect 独立验收；未制定或实施 TASK-037，看板由人类办理。
