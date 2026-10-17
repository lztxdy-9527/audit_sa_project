# TASK-021 评审：未通过（前序/历史记录完整校验与证据收尾）

评审日期：2026-10-13。结论：**NOT_ACCEPTED**。不关闭TASK-021，不推进P2；转交TASK-021-R1定点修正。人类操作DSH，GPT不操作看板。

## 1. 实际复核与交付身份

四份交付的字节大小与交接SHA均实读一致：

- 核心 `1355dce0b22a90dbe1d1d08bb05c49a6d5e76c2c6b21d15a8ae6b512463d6a68`，44307字节。
- 测试 `f7a6c8c8a073a891c2505c69a09409e2e1f5739eebc1156d34d2ee55ac67b02b`，65762字节。
- 指南 `5a753b15c0ca378cb07b4e2fb7e782fed7b2944dc7f2cad599c8bd5f6ce50caa`，15225字节。
- 回执 `4a834f454a1788d23886f3a35cb83b25bf399e1f4dbef2026ea8f16dda0b2b44`，13878字节。

已审查当前核心、测试、任务卡和对应协议条款，读取执行端132次调用/267检查的既有证据。本评审没有把其PASS声明当作GPT复验结果。

新评审根：`data/reviews/task021_gpt_20261013_195927/`。

实际运行 `targeted_probes.py`：从已验收夹具JSON深拷贝，真实调用公开核心14次，用Python实际函数代码帧入口观察计数；观察14=登记14，全部入参前后指纹不变。两项正常控制返回成功；12项本应Blocked的输入**也全部返回成功**，完整输入/返回在`probe_records.json`。没有修改核心、没有导入测试或旧夹具脚本、没有调用宿主/控制器/业务链。

实际运行 `evidence_audit.py`：只读最终证据台账并重新取文件字节SHA；结果见`evidence_audit.json`。本轮已有明确阻断，未重跑132调用完整入口或历史测试，避免无效重复回归。

## 2. B1：摘要闭合不能替代完整前序/历史record协议校验

权威要求：TASK-021 §4.2/§4.4；冻结协议 §3.5（所有对象封闭字段、严格类型）、§3.6（wrapper包含完整record）、§9.3及§14（记录常量、嵌套形状、来源/原文/指纹/边界）。

核心 `_step11_prior` 第608—751行仅核验record顶层键、部分常量/身份、记录摘要和选定绑定值，没有验证若干record字段，也未对actor/binding/contract/run/文件项/quality_summary等嵌套对象完整执行封闭schema。特别是：record.decision_source、reason、decided_at_raw、actor_id/declaration_note、contract_effective、binding.materials_fingerprint格式、materials_files成员、Gate1的prior_gate1等可绕过；run_binding只查所需键存在而不拒绝多余键。

本评审每例只改变一个前序record字段，随后**正确重算wrapper记录指纹、同步当前独立前序预期和历史中的同一wrapper**；当前Gate2材料/运行/契约/文件/材料指纹不变。这样不以旧摘要或不同历史的提前拒绝遮蔽目标字段。下列11例均返回 `HUMAN_GATE_DECISION_MEMORY_VALIDATED`：

1. `record.decision_source="AI_SUGGESTION"`。
2. `record.reason=""`。
3. `record.decided_at_raw="2026-02-30"`。
4. `record.actor.role="admin"`（未知嵌套键）。
5. 删除 `record.actor.actor_id`。
6. `record.binding.contract_binding.contract_effective=false`。
7. `record.binding.materials_fingerprint="a"×64+LF`。
8. `record.binding.run_binding.code.extra=true`。
9. `record.binding.materials_files[0].byte_size=-1`。
10. `record.prior_gate1={}`（Gate1应为null）。
11. `record.quality_summary.extra=true`。

**另一个历史路径也有同类缺口**：`_step4_prior_history`第448—486行只取gate/batch/event/decision/actor_kind等少量字段；其他历史wrapper版本/摘要和完整record未核验就进入`_step12_history`。以正常Gate1提交为控制，历史放入另一批次的HOLD：wrapper_version=`INVALID-WRAPPER`、record_fingerprint=`not-a-sha`，record仅5键且actor_kind=`SYSTEM`，仍成功返回。这不是隐藏历史发现问题，而是**已提供历史对象本身不符合明文协议**。

影响：核心将不合规或带明确错误来源/契约声明的“前序APPROVE”纳入当前Gate2内存成功记录，也会在损坏历史输入下成功构建记录。当前execution_allowed仍false，没有实际放行或AI解锁；但P1校验边界已失效，不能作为P2可信输入。

本项需要完整嵌套schema/字段语义校验，不需要新参数、磁盘I/O、全局历史发现或修改已验收协议。正常当前输入的schema检查、14步框架、11f六字段比较、完整返回基准和固定false边界可保留；不为重构而重写全部核心。

## 3. B2：最终证据审核未闭合，计数缺少真实入口观察

### 3.1 台账记录的是收尾前文件

测试第1200—1236行先写checks并建台账/验证，然后追加台账检查与隔离检查、再次写checks，最后写summary。读最终交付现场：

- 台账声称checks.json为56119字节、SHA `f47f59737cb79b9bee7a932f037e03619cd795ce050c4e82b94c906b40469b0f`。
- 实际为56447字节、SHA **`ef93657a23c5ce99e348ccebc919cb4be02b82b579eed0d41c659bc73603b0ff`**。
- 排除台账自身后，summary.json、protection_result.json、scan_protection.py不在清单中；至少最终summary属于核心测试结果载荷，不能仅审核其写入前目录就宣称最终证据闭合。后置保护元数据可明确分层有限登记，不要求自指哈希。

因此evidence_ledger.validated的missing/unregistered空列表是早期审核快照，不能代表交付后的实际文件。此处影响“267项最终检查已被台账核验”的证据可信度，属于阻断，不能作为普通旧文案登记。

### 3.2 计数与隔离并非要求的独立观察/权威登记审核

`Registry.call`第329行起在测试封装入口直接`self.calls += 1`，再调用核心；call_registry/counts都取该计数，没有在真实核心函数入口独立观察并核对覆盖。当前132个API记录与132个登记ID实读一致，不据此声称实际调用数错误；问题是未实现任务要求的独立入口计数与漏登记检测。

隔离自测删的是文件台账副本中的checks.json条目，没有删权威call_registry一条调用，也没有调用ID/调用记录的双向audit。因此它只能证明文件台账漏文件会被发现，不能证明漏登记的真实核心调用会被发现。Blocked记录也未统一保存cause/context链；有链的异常须如实保留。

修正需真实入口观察、登记↔API记录双向审核、删权威登记副本一条的隔离自测，以及在最终载荷稳定后的文件审核。无需额外业务链或重复上游样本。

## 4. 非阻断与保留事项

- C-80使用完整未知字段路径、C-82在合法Gate1基线上构造、C-61形状按submission.gate分支均已披露，未为这些文字/构造差异阻断。
- 外层恰两键、基准record17键、固定false边界、纯标准库、材料正文自指排除、当前材料双向名单和六字段绑定等已读取并在正常控制中观察；不扩充当前业务范围。
- 执行端过程失败现场保留；本评审不改写旧回执/证据，不将旧132调用重述为GPT实际运行。

## 5. 保护与交接

一次最终全树保护扫描使用已验收TASK-020-R3基线（133396项，SHA `cb90782134bdf5763ab5aa0d2a7ae4d916ced33b654a620e0ea9988b0bc27047`），实扫**133479文件**：**changed=[]、missing=[]、读取错误=[]、范围外新增=[]**。执行端新增66项、先前两个评审元数据及本次评审产物按确切路径分别登记，详见本评审根`protection_result.json`；随后仅有限登记本评审文件，不重复全树扫描。冻结契约/协议/案例/宿主/控制器与旧证据不修改。

交接 `docs/tasks/TASK-021-R1.md`。范围只修上述两类阻断、对应测试与必要指南同步，新增R1回执/新容器；通过前不制定P2卡，不创建真实Gate批准/初判/0009，不接AI/终判。人类D1/D2/D3与契约生效确认沿用，不重开业务决定。
