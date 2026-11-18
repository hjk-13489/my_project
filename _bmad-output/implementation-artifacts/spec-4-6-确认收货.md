---
title: '确认收货'
type: 'feature'
created: '2026-11-18'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 1338768809ad3ede44f29cf2acf462bc648be720
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 4.1–4.4 已能下单、支付并驱动状态机到「已支付/待交付」,模型层 `Order.confirm_receipt()` 也早已实现收货两跳流转,但 buyer 在界面上没有任何「确认收货」入口——交易主干停在「已支付/待交付」,无法进入「已完成」,4.7 互评的前置状态因此永远无法达成。FR-22 要求买家当面拿货后能确认收货、转入评价且不可再退款。

**Approach:** 在 `orders` app 新增一个仅 POST、仅 buyer 本人的 `order_confirm_receipt` 视图,调用既有 `order.confirm_receipt()`(paid → received → completed,同一事务),配一条 URL 与详情页上的「确认收货」按钮。完整照搬 4.2 `order_pay` 的 HTTP 层范式(登录门控 + POST 门控 + 事务 + 无效流转 200 重渲染提示 + 成功 PRG)。不改模型层、不新增字段与迁移、不在列表页加按钮。

## Boundaries & Constraints

**Always:**
- 视图 `@login_required`(外层) + `@require_POST`(内层):匿名请求先 302 到登录页并带 `next`,GET/PUT/DELETE 等一律 405(`Allow: POST`)。
- 取订单用 `get_object_or_404(Order, pk=pk, buyer=request.user)`:仅 buyer 本人可操作,他人订单与不存在订单均 404。
- 状态流转只经 `order.confirm_receipt()`,且在 `transaction.atomic()` 内完成取单与流转;视图不得直接写 `order.status`,不得自行拼装 `received`/`completed` 两跳。
- 非法/重复/陈旧实例流转(抛 `InvalidTransition`)以 200 重渲染 `orders/order_detail.html`,上下文带中文拒绝提示(键名 `receipt_error`,避免与既有 `pay_error` 混用),先 `refresh_from_db()` 再渲染,使状态徽章反映库内真实状态。
- 成功后 `redirect('order_detail', pk=pk)`(PRG),最终落库状态为 `completed`(「已完成」),`received` 为事务中间态不对外可见。
- 模板按钮:`order_detail.html` 上仅当 `order.status == 'paid'` 且无 `receipt_error` 时渲染「确认收货」POST 表单(含 `{% csrf_token %}`),action 指向新 URL;错误提示沿用 `alert alert-danger` 范式。

**Never:**
- 不改 `orders/models.py`(4.4 状态机已 done 并冻结)、不改 `ALLOWED_TRANSITIONS`/`_transition`/`confirm_receipt()`、不新增模型字段、不生成迁移。
- 不修改 4.1–4.5 既有视图行为(下单/支付/详情/联系方式门控/列表),不新增或改动 `order_list.html` 的动作按钮。
- 不实现退款入口(4.8)、不实现互评(4.7)、不实现管理员裁决(5.x);收货后退款入口「不可用」由状态机天然保证(`completed` 无出边到 `dispute`),本故事不写任何退款相关 UI 或逻辑。
- 不渲染/改动卖家联系方式门控(4.3),不引入新依赖、不做 AJAX/SPA、不新增 admin 注册。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|------------|----------------|----------|
| 正常收货 | buyer 登录,订单 `paid`,POST 收货 URL | 302 → 订单详情;库内 status=`completed`;updated_at 更新 | N/A |
| 按钮可见性 | 详情页订单 `paid` | 显示「确认收货」POST 表单 | N/A |
| 按钮隐藏-待支付 | 详情页订单 `pending_payment` | 不显示收货按钮(仅显示模拟支付) | N/A |
| 按钮隐藏-终态/纠纷 | 订单 `received`/`completed`/`reviewed`/`dispute`/`refunded`/`refund_failed` | 不显示收货按钮 | N/A |
| 未支付直接收货 | 对 `pending_payment` 订单 POST | 200 重渲染详情,中文拒绝提示;status 仍 `pending_payment` | `InvalidTransition` → 200 + `receipt_error` |
| 重复收货 | 对已 `completed` 订单再次 POST | 200 重渲染详情,中文拒绝提示;status 仍 `completed` | `InvalidTransition` → 200 + `receipt_error` |
| 退款分支订单收货 | 对 `dispute` 订单 POST | 200 重渲染详情,中文拒绝提示;status 不变 | `InvalidTransition` → 200 + `receipt_error` |
| 未登录访问 | 匿名 POST/GET 收货 URL | 302 到登录页并带 `next` | N/A |
| 非安全方法 | 已登录 GET/PUT 收货 URL | 405,`Allow: POST`,无状态变化 | 405 |
| 他人订单 | 非 buyer POST 收货 URL | 404,库内状态不变 | 404 |
| 不存在订单 | POST 不存在的 pk | 404 | 404 |
| 伪造字段 | POST 携带伪造 status 等字段 | 字段被忽略,仅依状态机流转 | N/A |
| 收货后退款不可达 | 订单 `completed`,检查 `request_refund()` 前置 | `completed` 无 → `dispute` 路径,模型层拒绝退款 | `InvalidTransition`(既有行为,本故事不新增 UI) |

</frozen-after-approval>

## Code Map

- `orders/models.py:13-34` — `STATUS_CHOICES`(8 值,含 `received`/`completed`)与 `ALLOWED_TRANSITIONS`;**冻结,勿改**。
- `orders/models.py:71-78` — `Order.confirm_receipt()`:paid → received → completed 两跳,外层 `transaction.atomic()`,非法转移抛 `InvalidTransition`(L6 定义,继承 Exception)。视图直接调用它,勿重写流转。
- `orders/models.py:101-125` — `_transition()`:唯一状态写入通道,条件更新 + 陈旧实例检测;**冻结,勿改**。
- `orders/views.py:69-91` — `order_pay` 是完整照搬范式:`@login_required` + `@require_POST`、`with transaction.atomic()` 内取单 + 流转、`except InvalidTransition` 后 `refresh_from_db()` 再 200 重渲染带 `pay_error`、成功 `redirect('order_detail', pk=pk)`。收货视图同构,错误键名改用 `receipt_error`。
- `orders/views.py:59-64` — `order_detail`:`get_object_or_404(Order, pk=pk, buyer=request.user)`,仅 buyer 可见 —— 收货视图沿用同一取单过滤。
- `orders/views.py` 顶部 — 已 import `transaction`、`get_object_or_404`、`InvalidTransition`、`redirect`、`render`、`login_required`、`require_POST`,收货视图无需新增 import。
- `orders/urls.py:5-12` — 现有 5 条(create/mine/sold/`<int:pk>/`/`<int:pk>/pay/`);新增 `<int:pk>/confirm-receipt/` name=`order_confirm_receipt`,紧随 pay 之后(带 pk 的两段路由,`<int:pk>/` 按段精确匹配不会吞掉)。静态列表路由 mine/sold 须保持在 `<int:pk>/` 之前(既有注释约束)。
- `templates/orders/order_detail.html:42-53` — `pay_error` 的 `alert-danger` 提示块与 `pending_payment` 下的模拟支付 POST 表单(csrf + d-grid + btn-success),是收货按钮与错误提示的直接范式。收货按钮条件为 `order.status == 'paid' and not receipt_error`。
- `templates/orders/order_detail.html:20-40` — 卖家联系方式门控(`status != 'pending_payment'` 显示),**勿改**。
- `templates/orders/order_list.html` + `orders/tests.py:1090` — 列表页只读,测试显式断言两页面 `assertNotContains('确认收货')`;**勿在列表加按钮**,该断言应保持为真。
- `orders/tests.py:458-697` — `OrderPayViewTests` 是视图层测试的现成范式:登录用 `self.client.login(username=user.student_id, password='test123456')`;成功断言 302 + `response.url` + 重读 status + updated_at 变新;非法流转断言 200 + `assertContains('alert-danger')` + 提示文案 + `assertIn('pay_error', context)` + 状态与 updated_at 不变;陈旧/并发用 `Order.objects.filter(...).update(status=...)` 模拟。收货视图测试照此新建 `OrderConfirmReceiptViewTests`。
- `orders/tests.py:16-180` — `OrderStateMachineTests` 已充分覆盖模型层收货两跳与非法拒绝;**本故事不重复测模型层**,只测 HTTP/UI 层。

## Tasks & Acceptance

**Execution:**
- [x] `orders/views.py` — 新增 `order_confirm_receipt` 视图(`@login_required` + `@require_POST`,事务内取单 + `confirm_receipt()`,`InvalidTransition` → 200 + `receipt_error`,成功 PRG) — 提供 4.6 的 HTTP 入口。
- [x] `orders/urls.py` — 新增 `<int:pk>/confirm-receipt/` name=`order_confirm_receipt` — 暴露收货端点,置于 pay 之后。
- [x] `templates/orders/order_detail.html` — 新增 `receipt_error` 提示块与 `paid` 状态下的「确认收货」POST 表单 — 提供买家可见入口。
- [x] `orders/tests.py` — 新增 `OrderConfirmReceiptViewTests` 覆盖 I/O 矩阵 — 证明收货流转、按钮可见性、非法/重复/越权/方法门控。

**Acceptance Criteria:**
- Given buyer 登录且订单为 `paid`,when POST 收货 URL,then 302 回详情页、库内 status=`completed` 且 updated_at 更新。
- Given 订单详情为 `paid`,when 渲染详情页,then 显示「确认收货」表单;为其它任何状态时均不显示。
- Given 订单为 `pending_payment`/`completed`/`dispute`,when POST 收货 URL,then 200 重渲染带中文拒绝提示、status 与 updated_at 不变。
- Given 匿名请求,when 访问收货 URL(GET 或 POST),then 302 到登录页并带 `next`。
- Given 已登录且非 buyer 或订单不存在,when POST 收货 URL,then 404 且无状态变化。
- Given 已登录,when 用 GET 访问收货 URL,then 405(`Allow: POST`)且无状态变化。
- Given 本轮改动,when 跑全量测试,then 既有用例无回归(尤其列表页 `assertNotContains('确认收货')` 仍为真)、新增用例全绿。

## Implementation Notes

- 实现严格照搬 `order_pay` 范式:视图 `@login_required` 外层 + `@require_POST` 内层,事务内 `get_object_or_404(Order, pk=pk, buyer=request.user)` + `order.confirm_receipt()`,非法流转捕获 `InvalidTransition` 后 `refresh_from_db()` 再 200 重渲染带 `receipt_error`,成功 PRG;未直接写 `status`,未碰冻结的模型层。
- URL 新增 `<int:pk>/confirm-receipt/`(name `order_confirm_receipt`),置于 pay 之后;它带 pk 参数为两段路由,不会被单段的 `<int:pk>/` 吞掉,放在其后是安全的。
- 模板收货按钮条件 `order.status == 'paid' and not receipt_error`,与支付按钮同构;错误条复用 `alert-danger`。订单列表页未加任何按钮,`test_links_and_privacy` 的 `assertNotContains('确认收货')` 仍为真。
- `OrderConfirmReceiptViewTests` 11 例覆盖 I/O 矩阵 12 行:正常两跳落 `completed`、8 状态按钮门控、表单 POST/action、405+`Allow: POST`、匿名 302 带 next、他人/不存在订单 404、7 类非法状态 200 拒绝、连续提交只流转一次、并发陈旧实例拒绝、`receipt_error` 时隐藏表单、伪造字段忽略。「收货后退款不可达」由既有 `OrderStateMachineTests.test_request_refund_after_receipt_rejected` 覆盖,本故事不新增退款 UI。
- 主代理独立验证(仓库解释器 `.venv/Scripts/python.exe`):`check` → no issues;`makemigrations --check --dry-run` → No changes detected;`test orders` → 81 例 OK(新增 11 + 原有 70);`test` 全量 → 305 例 OK,无失败/跳过,无回归。
- 已知说明(非风险):`received` 为事务中间态、对外始终呈现 `completed`,符合 FR-22;若后续 4.7 需单独展示该阶段需另立需求。

## Review Triage Log

三层审查（Blind Hunter 8 条 / Edge Case Hunter 0 / Verification Gap 0）。`review_loop_iteration` 保持 0：无 intent_gap、无 bad_spec、无代码 patch。下列裁决均在忽略审查子代理自带严重度后、依据对代码与流程的独立核实作出。

| # | 层 | 发现 | 裁决 | 证据 / 路由 |
|---|----|------|------|------|
| 1 | BH | diff 头出现两行 `+++`（含八进制转义），称补丁无法 git apply | `false` | 该重复行是主代理用 `echo` + `git diff --no-index` 拼接审查产物时的构造伪影，仅存在于系统临时目录的审查 diff，不在仓库代码中，也不用于 git apply；代码无此问题。 |
| 2 | BH | sprint-status 标 4-6 为 in-progress，与 spec 的 in-review 不一致 | `false` | 这是工作流中间态：step-03 设 story 为 in-progress、step-04 把 spec 设为 in-review、step-05 才用 sync-sprint-status 把 story 设为 review。非缺陷，step-05 收敛。 |
| 3 | BH | spec 声称新路由属「静态路由区」「置于 `<int:pk>/` 之前」，与实际代码矛盾 | `low` | 代码正确：`urls.py:12-13` 把两段路由置于 `<int:pk>/pay/` 之后，单段 `<int:pk>/` 不会吞掉；已在 triage 前就地改正 spec 的三处 agent-owned 描述（非 frozen 区、非代码），不触发 loopback 或 patch。 |
| 4 | BH | 拒绝文案硬编码于 view 且测试逐字复制，建议提取共享常量 | `low` | 与既有 `pay_error`（views.py:90 / tests.py:610）完全一致的范式；提取共享常量需新增公共表面，超出 trivial 修正；文案漂移致测试失败在日常不可达 → reject。 |
| 5 | BH | 缺「无 CSRF token 的 POST 被 403 拒绝」用例 | `low` | Django CSRF 中间件在真实请求强制校验、模板已含 `{% csrf_token %}`（测试已断言 token 存在）；全项目视图测试均用默认 client，加此例需引入 `enforce_csrf_checks` 新基建，超出 trivial；I/O 矩阵未要求、Verification Gap 层未报 → reject。 |
| 6 | BH | 收货错误路径缺 pay 那样的门控/徽章一致性断言 | `false` | 模板徽章（`order.get_status_display`，L15）与联系方式门控（`order.status != 'pending_payment'`，L20）读同一 refresh 后的 `order` 对象、天然同源；收货并发测试已断言徽章显示库内真实状态「纠纷」，等价于证明门控同步；本故事未改 4.3 门控逻辑，bad outcome 不会发生。 |
| 7 | BH | `received` 展示名「已确认收货」与按钮「确认收货」重叠致脆弱断言 | `false` | 测试已用表单 URL 而非文案判定按钮（覆盖 received 状态），规避了重叠；成功页 `assertNotContains('确认收货')` 在 completed 状态下有效；改展示名需动 4.4 冻结的模型层，违反边界。bad outcome 不发生。 |
| 8 | BH | 成功收货无 messages 成功提示，缺明确反馈 | `false` | 冻结 intent 明确「成功则 redirect + PRG，由状态徽章呈现结果」，与 4.2 支付范式一致；加 messages 违反冻结 intent 且与既有范式不符，bad outcome 不成立。 |

无 `intent_gap` / `bad_spec` / `patch` / `defer`；无 loopback。4 条 `low` 中 #3 为已改正的文档描述，#4/#5 按 reject 规则处理（日常不可达且修正需新增复杂度），#6/#7/#8 与 #1/#2 为 false。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — 期望:`System check identified no issues`。
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — 期望:`No changes detected`(本故事不新增迁移)。
- `.venv/Scripts/python.exe manage.py test orders -v 2` — 期望:全部用例 ok。
- `.venv/Scripts/python.exe manage.py test -v 2` — 期望:全量通过,无失败/跳过。
