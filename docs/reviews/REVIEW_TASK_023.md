# TASK-023评审：正常材料可准备，来源与路径核验及终审仍有阻断

日期：2026-10-14。结论：**NOT_ACCEPTED**。不关闭TASK-023、不制定TASK-024、不推进Gate接线。转 `docs/tasks/TASK-023-R1.md`，由DSH按B类定点修正本卡新增文件；GPT未修改实现代码或既有测试。

## 1. 本轮证据与执行范围

证据根 `data/reviews/task023_gpt_20261014_023810/`。GPT直接观察公开prepare入口15次，代码帧观察15、登记15，冻结接收器validate_report实际12次。另真实接收器CLI2次建立新plain及decision_review批次；完整命令、返回、stdout/stderr及manifest均保存。正常公开prepare返回PREPARED，31项材料与材料正文规范指纹经独立标准库计算一致。

原样公开测试CLI已启动至新 `task023_gpt_normal_20261014_023810`，但在对data/做递归历史快照时长时间运行，GPT停止了本次唯一匹配路径的四个解释器/父子进程，保留全部现场。**该入口未完成，不声称52项通过，也不补造退出码或完整调用登记。** 实际已有五个接收样本；这不等于测试完成。

为定点核验终审，GPT在另一个新 `task023_gpt_audit_20261014_023810` 调用当前真实run_suite，仅将对被拒绝的data/及data/batches/根的测试快照包装为首层名字观察。prepare、写入、终审reader及审核分支未替换。该运行是**有界观察包装下的故障套件**，不是原样正常CLI回归；登记prepare22、P1代码帧3、receiver CLI5。

执行端旧正常现场的52项0失败属于读取既有证据。GPT有限实读其12项台账及本轮故障套件12项台账，均与最终磁盘一致；但下述实证说明“最终台账自洽”仍可能掩盖此前字节漂移。

## 2. B1：接收声明、冻结预期与严格类型未完整闭合

在真实公开API的同缓冲读取通道包装真实reader，保持冻结磁盘不变，仅替换指定候选读缓冲；初始及末次读取使用同一候选。以下各独立反例均错误返回PREPARED：

- `hashes.receive_script.sha256_at_end`改为64个0。
- `hashes.checker.stable_during_run`改为false。
- `checker_invocation.report_result`改为issues_found，与实际pass矛盾。
- `checker_invocation.report_checker_sha256`改为64个0。
- 删除必需的gate1_approval或report.read_error，缺键被.get()当作合法null。
- SPEC_V1、旧契约草案、schema候选字节各独立追加LF；三者虽列入FROZEN_PROJECT_SHA及31材料，却未执行冻结SHA比较。
- 新配置synthetic_data由严格true改为整数1，保存合法canonical+LF；Python宽松相等让非法类型通过。

这些是任务卡§5/6已有要求的缺层，不要求改接收器/P1/材料名单。受控读缓冲映射是协议校验探针，**不是实际改动冻结文件**。每例完整返回、映射命中及真实调用记录见probe_records.json；不能用候选的初始/末次读数彼此一致替代独立冻结预期。

## 3. B2：子目录junction绕过路径拒绝

GPT只操作本轮新plain批次，将其checks目录移至本轮评审根，再用真实mklink /J建立原checks路径的junction。命令退出0，lstat含reparse，resolve与目标相同；八份逻辑文件及全部业务字节不变。

公开prepare仍返回PREPARED。根路径及最终文件的lstat检查未覆盖checks这个中间目录；project侧31清单的路径链也未统一复查。任务卡要求的是逐级无链接，而非只禁止叶文件/批次根链接。现场保留，不删除junction。另源码中lstat的OSError被当作false吞掉、重复iterdir有部分不在错误边界，修正时须同时保持I/O有类型、保留cause；这些补充为源码发现，本轮未另做完整故障运行。

## 4. B3：普通ID被未经授权的格式限制误拒

正常plain批次上，非空 `REVIEW\nREQ-001` 和带首部tab的请求ID被isprintable拒绝。另真实接收器成功建立、仅含合法八文件的decision_review批次，被目录名含decision拒绝。任务卡只要求非空非纯空白字符串与精确绑定；下游阶段应按实际产物判断，不能从普通批次名猜流程身份。三例均有正常对照，未被更早错误遮蔽。

## 5. E1/E2：终审字节漂移被重写掩盖，快照仍无实际上界

真实终审reader返回原缓冲后，GPT仅给checks.json追加一个LF，命中1：13195→13196字节。随后run_suite再次write_payloads重写载荷、重新采集台账期望，覆盖注入。结果**套件0、PASS、failures=[]**。终审内容比较使用原缓冲正常，后续自洽台账没有证明候选曾保持不变。fault_result包含注入前/后/最终三个SHA，最终SHA不同于注入后的SHA；失败现场未被套件承认为失败。这影响PASS有效性，必须阻断。

此外，_dir_snapshot只看首层条目数≤60便递归rglob；当前data/仅17个目录，仍遍历全部历史树。执行端api_records.json已达34804250字节。本轮原样CLI因此中断。这里应明确禁止对被拒绝的父目录遍历，并对合法批次观察设置真正的条目预算，而非首层数量阈值。

证据还需定点修正：project_snapshot_before实际在API结束后采集；prepare/helper没有完整入口计数闭合；“删登记由真实audit拒绝”当前只在隔离函数内手写IDs比较，并未复用生产收尾审核。同类终审关系和观察要求均已在本卡§8明确，不新增通用审计框架。

## 6. 身份、辅助更正和未执行

适配器 `5e8ed565cc6567b210c65c475ec16a8e2f271da49b4bcb6a745cad6cb329da02`（48689字节）、测试 `4e7662f599c665ea3ea43fc6809c2ae25c863c79cdc537ea73efed0ec3c9dcae`（59101）、配置 `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`（219）、指南 `0230ac8787743f002adbe27dab275d4697b60ab304cce335c06ffca1c3e6458f`（9433）与交接一致。

回执实际为**13438字节、SHA `fb01538fadfcc93949a188a5a5f83c548cab17137835edd60208b81c8554e44a`**，不同于交接12890/7b29f7ad…；保存两种身份，非阻断，不替执行端改旧回执。回执“所有调用源/项目前后完全相等”与counts中的source_bytes_unchanged_all_calls=false也需按故意注入/干净调用分列，不能把故意注入计入不变范围。这是措辞与scope更正，不否定正常控制。

GPT首次有限身份核对因回执差异停止，随后保留交接预期和实际身份分别登记，不重跑套件。未运行存储save/verify、宿主/控制器/历史入口、业务链或真实批准，不生成0009/真实初判/AI。旧冻结文件和所有故障现场保留。

## 7. 保护与修正范围

GPT一次最终全树比较，基线140077项、SHA `d36260d94df374d1f2ccd90e2b2127c1b599b075ecb9ff870a842b82d0a5a5c9`。实扫**140865文件**：**changed=[]、missing=[]、读取错误=[]、范围外新增=[]**。执行端五份新增文件/十二个显式根、前轮两个确切自指元数据、本轮评审和五个新运行/批次根按确切路径分列，无前缀豁免，junction保留。保护范围合规不替代功能验收。扫描后仅有限更新本轮评审及元数据身份；R1施工基线完整SHA/项数及两个确切自指排除见同目录review_result.json。

TASK-023-R1只改本卡新增适配器/测试/指南，新建回执及新容器；配置与全部上游冻结。属于落实既定设计的B类修正，若需改变31材料、P1协议、Gate时序/允许根/历史/执行边界，必须停止受影响工作并重新定界升级，不扩大当前范围。
