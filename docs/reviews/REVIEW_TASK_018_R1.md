# TASK-018-R1验收记录

日期：2026-10-13；验收端：GPT。

结论：**原B1/B2/E1复验关闭；TASK-018整体暂不通过。** 本轮新增批次ID字段校验缺陷B3须按 `docs/tasks/TASK-018-R2.md` 定点修正。原卡与R1保持待整体验收，暂不制定TASK-019；DSH由人类操作，GPT未访问GUI或关闭卡片。宿主仍停开发态0008，真实人类初判未保存、真实批准null、next=false、AI不允许。

## 1. 最终交付身份

实读SHA-256与交接一致，复验期间未变：

- 工具 `scripts/export_demo_review_bundle.py`：`7b78eefca18916c44d9dbc12f73bf480308fa3717b3bb0fc2ce02f67995788a5`。
- 测试 `tests/test_export_demo_review_bundle.py`：`99370503d3904c5f3a1e950e8a03eb7230c05fb473cea5ce58b1380f078ab9bc`。
- 指南 `docs/DEV_REVIEW_BUNDLE_GUIDE.md`：`9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7`。
- R1回执 `docs/EXEC_REPORT_018_R1.md`：`69c326d7f0ddde136e2132f6aa157fe9cb256df592229e68702540725bced26a`。

宿主仍为 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`，控制器/纯核心/旧测试/历史现场冻结。本轮未修改实现文件或冻结产物，未创建批次/SQLite、未重建上游链。

## 2. 实际复验与证据层级

执行端最终task018r1_run_01自报6/6 PASS。GPT实读23个API/CLI文件引用、相应台账和registry双向对应、完整异常/traceback/链及单删registry的隔离自测；文件存在且SHA正确。

GPT经 `data/reviews/task018_r1_gpt_20261013_144137/run_review.py` 实际运行交付 `--only r1` 一次：新证据容器 `data/review_bundle_tests/task018_r1_gpt_20261013_144137`，**退出0、6/6 PASS、failures=[]**。另实读该新容器23个API/CLI引用。

独立profile绑定交付测试实际使用的冻结宿主代码帧：公开API15次（工具12、直接宿主3），工具CLI4次；真实宿主status帧11次（直接3、工具嵌套8），所有公开调用标签与登记对应；六个真实核心代码帧0。子进程核心未观察，记null。这些是GPT实际观察，不是仅复述测试wrapper计数。

输入源固定为既有task018_run_06/c06b。GPT在入口执行前取得全部37文件及外置DB哈希，入口后及补充探针后再次核对一致，避免使用收尾时才创建的缓存自比。没有重跑默认七组、MAIN/零条、源晚变更、writer故障或历史入口。

## 3. B1/B2/E1关闭

B1：导出末尾已在manifest保存/读回、来源/DB消费后实读24份payload和manifest，与本次确切待写字节比较；离线核验所有对象解析与首次25文件缓冲绑定，身份消费后再做有限最终字节确认。真实README晚变更与离线记录LF反例均在本次Blocked，后续CLI1、只读verify不写诊断，正常包保持不变。

交付manifest反例在真实writer返回后立即注入，随后被manifest初次读回拒绝，早于原卡要求的最后来源消费点。GPT不将这个反例当作最终收尾覆盖，另用一个全新输出补测：真实_read_sources第3次（无注入实际观察的最后一次）返回原缓冲后仅给manifest追加LF，**本次正确Blocked，field=manifest.json**，失败诊断exit1。SHA `01a9910015dfb7eb48847487b087793c28a1890179f7901a6775a10492282c69` → `0d3bdcc3cced5c8c3cf320a4f9210b98f8418b2fec9b666724c22e5dae0f07df`。证据exact_late_manifest_supplement.json。该缺口由GPT补证关闭，不要求执行端为此重跑或追改历史记录。

B2：四个既定格式合法来源/身份反例均被实际拒绝，消息指向矛盾字段；22复制件与初始status映射、manifest文件SHA/规范指纹、十处批次身份、0008前驱及开发边界在正常包中相符。离线核验继续只访问包内材料，未调用宿主/DB/冻结核心。

E1：共享status_of的两次正常直接调用已登记完整实际返回；另一次真实缺失批次宿主调用已登记完整WorkflowHostBlocked，独立真实帧各1次。工具缺失批次前置拒绝的宿主增量0，与直接真实宿主观察分列。registry/引用核验及隔离自测实际执行，missing/unregistered为已执行结果0/0。

## 4. 新阻断B3：批次ID类型检查错误

位置：工具_verify_manifest_shape的source_batch.batch_id检查（当前约736行）以及_require_identity_relations构造distinct集合（约995行）。前者只要求 `_is_hash(batch_id) is False`，并未要求字符串；后者在验证类型前直接把十处值放进set。

GPT在正常包的隔离副本中**仅**将manifest.source_batch.batch_id改为 `[]`，所有payload及其哈希、文件集合均未改变。公开verify抛出原生 **TypeError: unhashable type: 'list'**，没有协议异常类型和field；新进程CLI退出**2**并报DevReviewBundleError。原卡R1§3要求非法结构为可定位Blocked/退出1，此处未满足。证据id_shape_result.json、id_cli_result.json及CLI原文。

同一个检查又拒绝合法字符串形状：将一个manifest内的两个批次声明设为64个小写a，单独调用shape helper，就因“像哈希”被拒绝。这里只验证shape helper，不宣称构造了真实绑定的64字符批次。冻结宿主批次路径resolver接受这种叶目录名且未创建目录；已有协议对批次身份采用字符串精确比较，没有“不得为64位十六进制文本”的规则。ID内容与SHA字段的格式要求应分开，不以哈希检测代替字符串类型检查。

这是一个局部协议/输入校验缺陷，不涉及业务口径、审计判断、身份认证或Gate批准。修正为明确字符串检查，并在集合/跨文件比较之前逐字段验证类型；不得全局捕获TypeError后把所有程序错误伪装成协议阻断，也不得放宽真正哈希字段的严格格式。

## 5. 保护与后续有界范围

定点入口实际执行一次完整保护扫描：基线131256项，实扫**132487文件**；changed恰为获准工具/测试/指南，missing=[]、unexpected=[]、读取错误0，六件重点冻结哈希一致。扫描字典从实际函数返回帧保存为current_scan.json，后续只刷新本轮新增产物/文档，不重复扫描项目树。

新source_hashes_after.json冻结当前未通过交付，文件哈希/项数和排除项见review_result.json，供R2使用。它不是通过声明或Git恢复点。

R2仅改工具/测试的局部ID校验，指南及所有历史现场冻结；新定点模式复用既有批次只读导出一个正常包，少量manifest类型反例在隔离副本进行，64字符字符串只作明确shape对照。已关闭B1/B2/E1不重跑，六组/七组/writer/上游/历史入口均不重跑；真实流程仍不启用。
