---
title: '模拟支付'
type: 'feature'
created: '2026-11-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: ba35694c7d1c4f40b9a40ff517aad6c1704c95ac
context:
  - _bmad-output/implementation-artifacts/epic-4-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 4.1 建单后订单停在「待支付」，`templates/orders/order_detail.html:20` 的「模拟支付」仍只是一行 HTML 注释挂点，买家没有任何推进支付的入口。4.4 交付的 `Order.pay()` 已在模型层备好 `pending_payment → paid` 的唯一合法转移却无人调用，FR-18 的原子支付流转缺失，4.3 联系方式、4.6 确认收货、4.8 退款请求全部卡在这个前置状态上。

**Approach:** 在 `orders` 增加一条仅接受 POST 的支付动作（新 URL + 视图），按 `buyer=request.user` 取订单，在单个数据库事务内调用 `Order.pay()` 完成状态流转；订单详情页仅在 `pending_payment` 时渲染「模拟支付」按钮，成功后回到详情页由状态徽章呈现「已支付/待交付」。视图绝不直接写 `status`、不接外部网关、不写支付流水、不新增任何模型字段或迁移。

**Decision（人类决策，2026-11-14，全部按推荐 A）:** ① Q1=A：**页面内错误条** —— 捕获 `InvalidTransition` 后以 200 重渲染订单详情页并给出 `alert-danger` 中文提示，明确「被拒绝」而非静默忽略；不改 `base.html`、不引入 session／query 传参。② Q2=A：**PRG 回订单详情页** —— POST 成功后 302 至 `/orders/<id>/`，由状态徽章与按钮消失呈现结果，不新增支付结果页。③ Q3=A：**详情页一键支付** —— 不设中间确认页，仅一个 POST 端点。④ 规格长度门：选择**保留完整规格**（约 3,669 tokens，超过 1600 建议上限）；本故事为单一用户目标、无可独立交付的次级目标，接受上下文腐化风险，与前序 4.1／4.4 规格口径一致。

## Boundaries & Constraints

**Always:**
- 仅已登录买家本人可支付：`@login_required` 外层 + 仅 POST 的方法门控内层；查询按 `buyer=request.user` 过滤，他人订单与不存在的 pk 一律 404，沿用 4.1 的授权范式。
- 状态写入的唯一通道是 `Order.pay()` → `_transition('paid')`；视图不得赋值 `status`、不得复刻 `ALLOWED_TRANSITIONS`、不得调用其它转移方法。
- 「取订单 + `pay()`」置于同一个 `transaction.atomic()` 内；并发重复提交由 `_transition()` 的条件更新 `filter(pk, status=self.status).update(...)` 兜底，绝不二次流转。
- 支付请求不读取任何业务字段（`price`／`status`／`buyer`／`product` 一律忽略），金额沿用 4.1 的价格快照。
- 成功后重定向回订单详情页；反馈只用页面内上下文变量 + Bootstrap `alert-*`，不使用 Django messages（`templates/base.html` 未渲染，且 4.1 的 D2 明确不改 `base.html`）。
- 沿用平铺 URL name（无 namespace）；`config/urls.py` 的 `orders/` include 已存在，不改路由总表。
- 错误统一表现为「拒绝」：状态不变、不落库、不产生任何外部副作用，禁止静默忽略或降级为纯日志；重复支付须给出可见的 `alert-danger` 提示。

**Never:**
- 不修改 `orders/models.py`（状态机、枚举、转移表、字段、五个转移方法）、`orders/migrations/0001_initial.py`、`InvalidTransition` 与 `orders/tests.py` 既有 34 个用例。
- 不修改 `orders/views.py` 中既有的 `order_create` / `order_detail`（尤其 `@require_safe` 与 buyer 过滤），不改 `CLOSED_STATUSES`。
- 不修改 `listings` / `accounts` 的模型、视图、表单、迁移；不改 `templates/base.html`；不改 `config/settings.py`。
- 不接真实第三方支付网关、不写支付流水／支付时间字段、不发通知、不新增 migration 或 DB 约束、不引入新依赖。
- 不实现 4.3 联系方式展示（绝不渲染卖家 QQ/微信、认证状态、学号）、4.5 订单列表、4.6 确认收货、4.7 互评、4.8 退款请求、管理员裁决；不注册 admin；不改个人中心订单空态。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|------------|----------------|----------|
| 正常支付 | 已登录 buyer + `pending_payment` 订单，POST `/orders/<id>/pay/` | 302 → `/orders/<id>/`；DB 重读 `status='paid'`、徽章「已支付/待交付」、按钮消失 | N/A |
| 按钮门控 | 详情页 GET，`status` 非 `pending_payment` | 200 且不出现支付表单，状态徽章显示当前状态 | N/A |
| 非法方法 | 已登录 buyer + GET / PUT / DELETE 到支付 URL | 405，状态不变 | 方法门控（匿名请求按「未登录」行先跳登录页，不返回 405） |
| 未登录 | 匿名 POST / GET | 302 至 `/login/?next=...`，状态不变 | `login_required` |
| 他人订单 | 非 buyer POST | 404，状态不变 | `get_object_or_404(buyer=request.user)` |
| 不存在订单 | 不存在的 pk | 404 | 同上 |
| 重复支付 | `paid` / `received` / `completed` / `dispute` / 终态 POST | `pay()` 抛 `InvalidTransition`，状态与 `updated_at` 不变；以 200 重渲染详情页并显示 `alert-danger` 中文拒绝提示 | 捕获 `InvalidTransition` 并传入 `pay_error` |
| 并发双击 | 同一待支付订单两个并发 POST | 恰好一次流转到 `paid`，第二次被条件更新挡住 | `InvalidTransition` → 可见拒绝提示 |
| 伪造字段 | POST 携带 `status=paid` / `price=0.01` / `buyer=<他人>` | 全部忽略，仅经 `pay()` 流转 | 视图不读请求业务字段 |
| 支付后商品改价／下架 | 已 `paid` 订单 | 订单 `price` 与 `status` 均不变 | N/A |

</frozen-after-approval>

## Code Map

- `orders/models.py:25-34, 67-69, 101-125` — `ALLOWED_TRANSITIONS['pending_payment'] == ('paid',)`；`pay()` 即 `_transition('paid')`；`_transition()` 已在 `transaction.atomic()` 内用 `filter(pk, status=self.status).update(status=target, updated_at=now)` 做条件更新，非法或陈旧实例抛 `InvalidTransition`。**唯一支付入口，绝不修改**。
- `orders/views.py:12, 17-18, 59-64` — `CLOSED_STATUSES`、`@login_required` + `@require_http_methods` / `@require_safe` 的装饰器叠放顺序、`get_object_or_404(Order, pk=pk, buyer=request.user)` 授权范式、`redirect('order_detail', pk=...)` 写法；新视图照此追加，**既有两视图不动**。
- `orders/urls.py:5-8` — 平铺 name 的 `create/<int:product_pk>/` 与 `<int:pk>/`；追加 `<int:pk>/pay/`，`path('<int:pk>/')` 不会吞掉带尾段的路径。
- `orders/forms.py:4-19` — 仅 `OrderCreateForm`；模拟支付无买家输入，**不新增表单**。
- `orders/tests.py:29-197, 226-443` — 既有 34 例（`OrderStateMachineTests` 18 + `OrderCreateViewTests` 16）；`setUpTestData`、`_make_order(status=...)`、`_post()` 夹具可复用；`test_pay_twice_rejected`（:120）、`test_stale_instance_cannot_overwrite_concurrent_state`（:140）、`test_owner_can_view_order_detail`（:394）是支付视图用例的直接参照。追加新用例，勿改既有用例。
- `templates/orders/order_detail.html:15, 20` — 状态徽章 `{{ order.get_status_display }}` 与第 20 行「4.2 模拟支付入口预留挂点」注释；在此渲染 `csrf_token` POST 表单，按 `order.status == 'pending_payment'` 门控，并预留错误条位置。
- `templates/orders/order_confirm.html`、`templates/listings/publish.html:29-42` — `novalidate` + csrf + 逐字段 `text-danger` / 非字段 `alert-danger` 的 Bootstrap 渲染范例。
- `templates/base.html:6, 35` — 仅 `title` / `content` block，**未渲染 messages**，故本故事不走 messages 框架。
- `config/urls.py:29-35` — `orders/` include 已在末位，无需改动；`config/settings.py:140` — `LOGIN_URL='/login/'`。
- `_bmad-output/implementation-artifacts/epic-4-context.md` — 模拟支付／事务／授权／联系方式隐私的约束来源；`spec-4-1-下单创建订单.md`（D2 与挂点）、`spec-4-4-订单状态机.md`（状态机边界）为连续性依据。

## Tasks & Acceptance

**Execution:**
- [x] `orders/urls.py` — 新增 `order_pay` 路由 `<int:pk>/pay/`，平铺 name — 给支付按钮提供可解析、且独立于只读详情页的写入口。
- [x] `orders/views.py` — 新增 `order_pay`（`@login_required` + 仅 POST 门控；按 `buyer=request.user` 取订单；`transaction.atomic()` 内调用 `order.pay()`；成功 `redirect('order_detail', pk=pk)`；捕获 `InvalidTransition` 后以 200 重渲染详情页并传入 `pay_error` 文案）— 接通状态机唯一入口且视图不写 `status`。
- [x] `templates/orders/order_detail.html` — 在第 20 行挂点处渲染「模拟支付」POST 表单（csrf + 按钮），仅 `pending_payment` 可见；新增 `alert-danger` 错误条渲染 — 完成可见入口、拒绝反馈与「状态即界面」。
- [x] `orders/tests.py` — 追加支付视图用例，覆盖 I/O 矩阵全部 10 行（成功流转且 DB 重读、302 落点、按钮门控、405、匿名、他人／不存在 404、重复支付状态与 `updated_at` 不变且错误条可见、并发／陈旧实例、伪造 POST 字段被忽略、支付后改价不影响订单）— 证明唯一入口、授权门控与拒绝语义。

**Acceptance Criteria:**
- Given 一张 `pending_payment` 订单，when buyer 提交模拟支付，then DB 中 `status == 'paid'` 且 `updated_at` 被更新；and 全仓检索 `status` 的赋值仍只出现在 `orders/models.py:_transition()` 内，视图与模板未直接写状态。
- Given 任意非 `pending_payment` 状态、越权或未登录请求，when 发起支付，then 订单状态与 `updated_at` 均不变，且不产生任何支付流水、迁移或外部调用。
- Given 本轮改动，when 跑全量测试，then 既有 258 例与新增用例全绿、`makemigrations --check --dry-run` 报 No changes detected，`orders/models.py` 与 `orders/migrations/` 的 diff 为空。

## Implementation Notes

- 4 条 Execution 全部完成：`orders/urls.py` 追加 `order_pay` 路由；`orders/views.py` 新增 `order_pay` 视图（新增 `require_POST` / `InvalidTransition` 两个 import）；`templates/orders/order_detail.html:20` 挂点换成 `alert-danger` 错误条与仅 `pending_payment` 可见的 POST 表单；`orders/tests.py` 追加 `OrderPayViewTests` 11 例（I/O 矩阵 10 行逐行覆盖，并发行配 2 例）。既有 34 例、`orders/models.py`、迁移、`base.html`、`config/urls.py`、`listings` / `accounts` 均未改动。
- 规格对齐：Always 要求「取订单 + `pay()`」同处一个 `transaction.atomic()`，而原黄金骨架把 `get_object_or_404` 留在事务外；实现按规范性文字把取单也纳入事务，并同步修正本文件 Design Notes 的骨架示例，消除内部不一致（冻结区未改）。
- 主代理独立实跑（未采信实现子代理报告）：`check` → 0 issues；`makemigrations --check --dry-run` → No changes detected；`test orders --verbosity=2` → 45 例逐例 `ok`（34 既有 + 11 新增，全部 ran & passed）；全量 `test` → 269 例 OK（258 基线 + 11 新增）；`git grep -nE "status[[:space:]]*=" -- orders/views.py` → 无输出；`git diff --stat <baseline> -- orders/models.py orders/migrations/` → 空。
- 已知取舍：错误分支沿用骨架直接把 `order` 实例传给模板，并发／陈旧实例被拒时徽章可能短暂显示陈旧状态，但错误条明确可见且库内状态不变；并发用例以 `mock.patch` 返回陈旧实例触发 `_transition()` 条件更新兜底，属测试替身而非真实多进程压测。
- 首轮审查补丁（Step 4，3 组 `patch`）：`templates/orders/order_detail.html` 表单门控加 `and not pay_error`，拒绝页不再重现支付按钮；`orders/views.py` 的 `pay_error` 改为固定买家可读中文拒绝语（不再透传状态机异常原文）；`orders/tests.py` 同步 3 处文案断言、给陈旧实例用例补 `assertNotContains(pay_url)`、新增 `test_pay_form_is_post_and_completes_payment` 钉住表单 `method="post"` 与按 action 走通支付。主代理复跑：`check` 0 issues、`makemigrations --check --dry-run` No changes detected、`test orders --verbosity=2` 46 例逐例 `ok`、全量 `test` 270 例 OK、视图无 `status=` 赋值、受保护文件 diff 为空；另有 4 条 `false` 与 7 条 `low` 驳回，无 loopback。

## Spec Change Log

## Review Triage Log

首轮三层审查（Blind Hunter 10 / Edge Case Hunter 6 / Verification Gap 1 gap + 1 other，共 18 条），`review_loop_iteration` 保持 0（无 loopback）。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 1 | BH | 开启 CSRF 时 PUT/DELETE/匿名 POST 得 403 而非 405/302，测试客户端默认关闭 CSRF 使断言失真 | `low` → rejected | 项目级既有行为，`deferred-work.md:46` 已就 2.8 登记；表单带 `{% csrf_token %}`，正常买家点击不受影响；补 `enforce_csrf_checks=True` 用例或改矩阵前提属编辑本规格／新增测试配置，非直接修正。 |
| 2 | BH | 并发／陈旧实例被拒的 200 页上 `alert-danger` 与「模拟支付」表单同时出现 | `medium` | 与 #11/#12/#15/#18 同根因：except 分支直接传内存实例，`_transition()` 条件更新命中 0 行时未改写 `self.status`（`orders/models.py:116-124`），模板仍按 `pending_payment` 渲染表单 → patch。 |
| 3 | BH | `str(exc)` 原样透传，重复支付文案同标签重复两次且无面向买家的拒绝语 | `low` | 真实且双击可遇；最小修复是替换为固定中文拒绝语并同步断言，属直接修正 → patch。 |
| 4 | BH | 审批后改 Design Notes 骨架但 Spec Change Log 为空 | `false` | 模板规定 Spec Change Log「Empty until the first bad_spec loopback」，本轮即首轮；冻结区未改，Design Notes 属非冻结区且为对齐 Always 的规范性文字，与 4.1 首轮 #3 同一情形。 |
| 5 | BH | Verification 未列 models/migrations diff 命令、`<baseline>` 仍是占位符 | `low` → rejected | 主代理已实跑该命令并把结果与完整 SHA 记入 Implementation Notes，验收可复现；修复需编辑本规格 → 按规则驳回。 |
| 6 | BH | expected 只写 34/258 基线，未同步 45/269 | `low` → rejected | 实跑 45/269 全绿并已记入 Implementation Notes，属文档期望值口径；与 4.1 首轮 #15 同源，修复需编辑本规格 → 驳回。 |
| 7 | BH | AC1「全仓检索」口径宽于 `git grep -- orders/views.py`，且无用钉住 `Order.pay()` 被调用 | `low` → rejected | Verification 的 grep 已能检出把 `order.pay()` 换成内联 `status=` 改写；补 mock 调用断言属新增测试复杂度，扩范围／写明豁免需编辑本规格；与 4.1 首轮 #5 同源。 |
| 8 | BH | 匿名 PUT/DELETE/HEAD 无断言，装饰器顺序调换不会转红 | `low` → rejected | 匿名非法方法不产生写入或状态变更，无用户可见坏结果；已登录 GET/PUT/DELETE 405 与匿名 GET/POST 302 已覆盖；与 4.1 首轮 #10 口径一致。 |
| 9 | BH | 矩阵「两个并发 POST」超出实际验证（顺序双击 + mock 陈旧实例） | `low` → rejected | SQLite 演示环境无法可靠构造真实并发；`mock.patch` 已触发 `_transition()` 条件更新兜底，Implementation Notes 已披露替身性质；改措辞需编辑本规格，补真实并发用例超出范围。 |
| 10 | BH | spec `in-review` 与 sprint `in-progress` 不一致 | `false` | 流程中间态：sprint 的 `review` 由 Step 5 收尾统一同步，Step 4 只改 spec；与 4.1 首轮 #1 / 4-4 审查 #17 同一情形。 |
| 11 | EC | `orders/views.py:83-85` 未 refresh，徽章显示陈旧「待支付」 | `medium` | 并入 #2 组，同一根因 → patch。 |
| 12 | EC | 模板在 `pay_error` 与陈旧 status 下仍渲染可提交表单 | `medium` | 并入 #2 组，同一根因 → patch。 |
| 13 | EC | `pay()` 抛 DatabaseError 等非 InvalidTransition 时得 500 | `false` | `update()` 故障必须由 `transaction.atomic()` 传播以回滚；捕获后伪装成 200「支付被拒绝」会掩盖系统故障，且规格只要求非法状态转移被拒绝。 |
| 14 | EC | 空 `str(exc)` 使 `pay_error` 为假、静默忽略 | `false` | `orders/models.py:110-113, 120-123` 两处 `raise InvalidTransition(...)` 均带中文消息，全仓无无参抛出，`str(exc)` 恒非空。 |
| 15 | EC | claim「明确被拒绝／状态即界面」被陈旧实例重渲染破坏 | `medium` | 并入 #2 组 → patch。 |
| 16 | EC | claim「两个并发 POST 恰好一次流转」被 mock 覆盖 | `low` → rejected | 同 #9，修复需编辑本规格或引入真实多进程压测 → 驳回。 |
| 17 | VG | 表单 `method="post"` 与仅 POST 端点的接线无自动化验证（pre-verified gap） | `medium` | 采信 filed evidence：把 `method="post"` 改成 `get` 后 11 例与全量仍全绿，但买家点按钮得 405、支付永远无法完成 → patch。 |
| 18 | VG | Other：拒绝页重现支付按钮，用例未断言 `assertNotContains(pay_url)` | `medium` | 并入 #2 组 → patch。 |

分组与路由：18 条中 4 条 `false`、7 条 `low → rejected`、3 组保留（G1 `medium`：#2+#11+#12+#15+#18 陈旧实例重渲染；G2 `low`：#3 拒绝文案；G3 `medium`：#17 表单接线），全部走 `patch`。无 `intent_gap` / `bad_spec` / `defer`，不触发 loopback，`review_loop_iteration` 保持 0。

## Design Notes

- 新增独立 POST 端点而非放宽 `order_detail`：4.1 的 `order_detail` 是 `@require_safe` 且已有「匿名 302／非法方法 405」用例，把 POST 塞进去会破坏既有契约；独立端点让写操作门控清晰、URL 语义明确。
- 视图再包一层 `transaction.atomic()`：`_transition()` 自身已原子，但 epic-4 明确要求「模拟支付在单个事务内原子完成」；把「按 buyer 取订单 + `pay()`」置于同一事务，使读取与流转构成一个不可分割的动作。并发双击由条件更新兜底，SQLite 下 `select_for_update()` 为 no-op（全仓亦无此用法），不引入行锁。
- 反馈不用 messages：`base.html` 未渲染 messages，4.1 的 D2 已把「不改 `base.html`」列为取舍；页面内上下文变量配 `alert-danger` 是既有模板范式。重复支付返回 200 重渲染而非 404／静默重定向，让买家看到明确拒绝理由。
- 视图黄金骨架（Q1=A 的错误分支；取单与流转同处 `atomic`，与 Always 一致）：

  ```python
  @login_required
  @require_POST
  def order_pay(request, pk):
      try:
          with transaction.atomic():
              order = get_object_or_404(Order, pk=pk, buyer=request.user)
              order.pay()
      except InvalidTransition as exc:
          return render(request, 'orders/order_detail.html',
                        {'order': order, 'pay_error': str(exc)})
      return redirect('order_detail', pk=pk)
  ```

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: No changes detected
- `.venv/Scripts/python.exe manage.py test orders` — expected: 既有 34 例 + 新增支付用例全 OK
- `.venv/Scripts/python.exe manage.py test` — expected: 全量（基线 258 例）无回归
- `git grep -nE "status[[:space:]]*=" -- orders/views.py` — expected: 无输出（测试夹具赋值不在检索范围内）

**Manual checks (if no CLI):**
- 以 buyer 打开待支付订单 `/orders/<id>/` 见「模拟支付」按钮 → 点击 → 回到详情页，徽章变「已支付/待交付」且按钮消失，刷新后保持；再次直接 POST 同一 pay URL 得到可见拒绝且状态不变；换另一账号 POST 得 404；直接 GET pay URL 得 405。
