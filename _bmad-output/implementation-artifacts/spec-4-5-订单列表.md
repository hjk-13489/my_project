---
title: '订单列表'
type: 'feature'
created: '2026-11-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 80f393f980f60acfc53498f2e15f84e6dd521461
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 4.1–4.4 已能下单、支付、看详情并驱动状态机,但用户没有总览交易的入口:买家无法列出「我的订单」,卖家无法列出「售出订单」,只能靠记住订单 ID 访问详情;个人中心「我的订单」卡片仍是硬编码空状态。FR-4 / FR-21 要求按身份只读汇总交易进度。

**Approach:** 在 `orders` app 新增两个只读列表视图——买家按 `buyer=request.user`、卖家按 `product__owner=request.user` 过滤——配套 URL 与模板,展示每条订单的中文状态与关键信息。沿用 2.4「我的发布」范式(`login_required` + `require_safe`、创建时间倒序、不分页),只读不改状态、不新增字段、不新增迁移。

**Decision（人类决策，2026-11-17）:** Q1=A：除两个独立列表页外，一并加顶部导航「我的订单」入口，并把个人中心「我的订单」占位卡填成真实摘要（最近若干条 +「查看全部」链接）；据此改 `accounts/views.py` 与 `templates/accounts/profile.html`，但个人中心其余空状态板块保持不变。

## Boundaries & Constraints

**Always:**
- 两个视图均 `@login_required`(外层) + `@require_safe`(内层):匿名 GET/HEAD 先 302 到登录页并带 `next`,POST/PUT/DELETE 等 405(`Allow: GET, HEAD`)。
- 买家列表 `Order.objects.filter(buyer=request.user)`;卖家列表 `Order.objects.filter(product__owner=request.user)`。过滤在服务端强制,他人订单不进入查询集,不可经 URL 越权。
- 纯只读:不写订单、不调用任何状态流转方法、不新增/修改 ORM 字段、不生成迁移。
- 状态用 `get_status_display` 中文标签;排序沿用 `Order.Meta.ordering('-created_at')`;不分页、全量返回。
- 模板继承 `base.html`,用 `block title` / `block content`,Bootstrap 服务端渲染,遵循现有中文界面措辞。

**Never:**
- 不渲染卖家 QQ/微信(联系方式门控属 4.3 详情页,列表不暴露);不放确认收货/退款/互评等操作按钮(属 4.6/4.7/4.8)。
- 不复用 epic context 中的 `product__seller`;真实字段是 `product__owner`。
- 不改 `Order` 模型与状态机(4.4 已 done 并冻结),不改 4.1–4.3 的既有视图行为。
- 不引入新依赖、不分页、不做 SPA/AJAX、不新增 admin 注册。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|------------|----------------|----------|
| 买家看我的订单 | 买家登录,本人 2 单 + 他人 1 单 | 列表仅含本人 2 单,显示商品标题/成交价/订单号/下单时间/中文状态 | N/A |
| 卖家看售出订单 | 卖家登录,本人商品被下 2 单 + 他人商品订单 1 单 | 列表仅含本人商品相关 2 单(按 `product__owner`) | N/A |
| 空列表 | 登录但无相关订单 | 200 + 中文空状态提示,context 为空查询集 | N/A |
| 未登录访问 | 匿名 GET 任一列表 URL | 302 到登录页,带 `next` | N/A |
| 非安全方法 | 已登录 POST/PUT 列表 URL | 405,`Allow: GET, HEAD`,无写入 | 405 |
| 终态/纠纷订单 | 订单为 reviewed/dispute/refunded/refund_failed | 按 `get_status_display` 正常展示,不报错、不改状态 | N/A |
| 直接访问他人订单详情 | 非本人 buyer 且非本人商品的 URL | 404(既有 `order_detail` 行为,本故事保持不变) | 404 |

</frozen-after-approval>

## Code Map

- `orders/views.py` — 现有 `order_create`/`order_detail`/`order_pay`(均为函数视图,`@login_required` 外层 + 内层方法门控);本次在其后追加两个列表视图,复用同一组合与 `render` 风格。
- `orders/urls.py` — 现有 `create/<pk>/`、`<pk>/`、`<pk>/pay/`;追加 `mine/`、`sold/` 两条,注意放在 `<int:pk>/` 之前避免被动态路由吞掉。
- `listings/views.py:110-118` — `my_listings_view` 是最接近的只读列表范式(`@login_required` + `@require_safe`、`filter(owner=request.user)`、`list()`、倒序、空状态 context),照此写法。
- `orders/models.py:10-64` — `Order` 字段与 `STATUS_CHOICES`/`get_status_display`;卖家经 `product.owner` 取得,过滤用跨关系 `product__owner`。
- `listings/models.py:46-51` — `Product.owner` 是卖家字段(真名,非 `seller`)。
- `accounts/models.py:5-16` — `User` 有 `student_id`/`username`/`is_verified`/`qq`/`wechat`;列表不渲染联系方式。
- `accounts/views.py:125-150` — `profile_view` 当前硬编码 `my_orders_empty: True`,Q1 选 A 时以 `filter(buyer=request.user)` 摘要替换(仍需保持其他空状态不变)。
- `templates/listings/my_listings.html` — 列表模板范式(继承 base、空状态、list-group、状态徽章、返回个人中心)。
- `templates/accounts/profile.html:78-89` — 「我的订单」占位卡,Q1 选 A 时填摘要 + 查看全部链接。
- `templates/base.html:10-32` — 顶部导航,Q1 选 A 时加「我的订单」入口。
- `templates/orders/order_detail.html` — 详情页既有行为(仅 buyer 可见);列表项链接按 Design Notes 处理以避免卖家点击 404。
- `orders/tests.py` — `TestCase` + `setUpTestData`,`User.objects.create_user(student_id=..., username=..., password=...)`、`Product.objects.create(owner=...)`、`Order.objects.create(...)`、`force_login`、`reverse`;新增列表视图测试类。
- `listings/tests.py:896-964` — `MyListingsViewTests` 提供只读列表测试的现成范式(空状态、隔离、405、登录门控)。

## Tasks & Acceptance

**Execution:**
- [x] `orders/views.py` — 新增 `my_orders_view` 与 `sold_orders_view` 两个只读列表视图 — 服务端强制过滤与身份隔离。
- [x] `orders/urls.py` — 新增 `mine/`、`sold/` 两条 URL(name `my_orders`、`sold_orders`) — 提供入口且不被 `<int:pk>/` 吞掉。
- [x] `templates/orders/order_list.html` — 新增列表模板,两种模式共用 — 渲染中文状态与关键信息、空状态。
- [x] `orders/tests.py` — 新增 `OrderListViewTests` 12 例覆盖 I/O 矩阵 — 证明身份隔离、只读、门控。
- [x] `accounts/views.py` + `templates/accounts/profile.html` + `templates/base.html` — 填个人中心摘要(`[:5]`)并加导航入口 — 个人中心可见真实订单。

**Acceptance Criteria:**
- Given 买家登录,when 访问「我的订单」,then 只见 `buyer=self` 的订单,含中文状态与关键信息,他人订单不出现。
- Given 卖家登录,when 访问「售出订单」,then 只见 `product__owner=self` 的订单,他人商品订单不出现。
- Given 匿名请求,when 访问任一列表,then 302 到登录页并带 `next`。
- Given 已登录,when 用 POST 访问列表,then 405 且数据库订单数不变。
- Given 任意状态(含终态/纠纷)的订单,when 渲染列表,then 中文状态正确显示且库内状态与字段无变化。
- Given 本轮改动,when 跑全量测试,then 既有用例无回归、新增用例全绿。

## Implementation Notes

- 实现代理在 `orders/views.py` 为两个列表查询追加 `select_related('product')`，消除渲染商品标题/价格时的 N+1；属下述「不分页、只读」边界内的纯查询优化，不改变可见行为。
- 个人中心摘要上限取 `PROFILE_ORDERS_SUMMARY_LIMIT = 5`（`accounts/views.py`）：规格 frozen 区只写「最近若干条」，5 为实现层的具体取值，未引入新的公共表面。
- `orders/tests.py` 新增 `OrderListViewTests` 12 例：覆盖 I/O 矩阵全部 7 行，另加静态路由可达、倒序（context + HTML 双断言）、摘要上限、他人订单详情仍 404。
- 验证（仓库解释器 `.venv/Scripts/python.exe`，主代理独立实跑）：`check` → `no issues`；`makemigrations --check --dry-run` → `No changes detected`；`test orders` → 69 例 OK；全量 `test` → 293 例 OK。
- 已知既有测试抖动（非本故事引入）：`test_pre_order_pages_never_show_contact` 用 `assertNotContains(response, 'QQ')`，偶被随机 CSRF token（含字母 QQ）误命中；重跑与隔离运行均通过，未改动该用例，已登记 deferred-work。
- 审查（三层 12 条 → 3 组 patch）：(A) 售出订单页加入口——列表模板底部加模式切换链接（买家页→`sold_orders`，卖家页→`my_orders`），卖家可从「我的订单」进入；(B) 补强测试——个人中心摘要加 `select_related('product')` 与 buyer 隔离用例、重写「最近 5 条」用例（不同 created_at + 导入常量）、补 sold 页排序断言、修正「查看全部」假阳性断言；(C) N+1 并入 B。驳回 3 条（错误修复建议 `product__status='approved'` 会漏历史订单、裸子串定位当前不可达、计数记录错误已修正）。
- 最终验证：patch 后 `check` no issues、`makemigrations --check` No changes、`test orders` 70 例 OK、全量 `test` 294 例 OK（重跑确认 CSRF 抖动为概率性，非本故事回归）。

## Review Triage Log

首轮三层审查（Blind Hunter 6 / Edge Case Hunter 2 / Verification Gap 3 + Other 1，共 12 条），`review_loop_iteration` 保持 0（无 loopback）。Verification Gap 三主发现为 pre-verified，采信其 filed evidence 与 disposition。

| # | 层 | 发现 | 裁决 | 证据 / 路由 |
|---|----|------|------|------|
| 1 | BH | `accounts/views.py:145` 个人中心摘要 `filter(buyer=...)[:5]` 缺 `select_related('product')`，模板取 `order.product.title` 产生 N+1 | `low` | 坏结果真实（多 5 次查询），演示规模无感；最小修复是直接加 `.select_related('product')` → patch。 |
| 2 | BH | 售出订单页无任何 UI 入口，卖家只能手输 `/orders/sold/` | `medium` | 属实（`templates/` 全仓无 `sold_orders` 链接），卖家侧 FR-21 无法从界面达成；最小修复只是加一个指向既有 `sold_orders` 的链接，无新 URL/view、不 guard 新状态 → patch。 |
| 3 | BH | `test_profile_summary_and_nav_entry` 用 `assertContains(href="/orders/mine/")` 验证「查看全部」按钮是假阳性：`base.html` 导航已提供同 href，删按钮仍绿 | `low` | 属实（base.html:17 渲染同 href）；最小修复是改断言按钮文案「查看全部」→ patch。 |
| 4 | BH | `test_profile_summary_is_limited_to_recent` 硬编码 5，与生产常量 `PROFILE_ORDERS_SUMMARY_LIMIT` 脱钩 | `low` | 属实；最小修复是断言改用导入常量 → patch，与 #5 同用例一并处理。 |
| 5 | BH | 同一测试只断言 `len==5`，7 单 `created_at` 相近，未验证取的是「最近」5 条 | `low` | 属实，与 VG#2 同根因 → 合并 patch。 |
| 6 | BH | `test_ordered_by_created_at_desc` 用 `html.index('#1')` 裸子串定位，`#1` 可命中 `#10` | `low` | 潜在脆弱但当前数据未触发；修复需换正则边界/DOM 顺序解析，多于直接修正，且演示数据下坏结果不可达 → reject。 |
| 7 | EC | sold 页商品链到 `product_detail`，非 approved 商品会 404；建议过滤 `product__status='approved'` | `low` | 坏结果轻微（订单信息仍显示，仅链接 404）；**建议修复错误**——过滤会漏掉下单后下架的历史订单，违反「售出订单展示本人商品全部订单」与冻结 Design Notes 的既定选择；修复需新增分支且违背意图 → reject。 |
| 8 | EC | 规格声称 14 例，实际 12 个 `test_` 方法 | `false` | 代码实际 12 例、全绿；不准确的是 spec 记录与实现代理报告（均已修正为 12），find=编辑受审 spec → reject。 |
| 9 | VG | 个人中心摘要 buyer 过滤无测试覆盖：把 `filter` 改成 `all()` 三处测试仍绿，他人订单可出现在本人卡片 | `medium` | pre-verified，采信变异验证（改 `all()` 全绿）；身份隔离属 NFR-2 安全属性 → patch（加他人订单隔离用例）。 |
| 10 | VG | 摘要「最近若干条」被弱测试掩盖，取最早 5 条测试仍绿 | `low` | pre-verified，同 #5 → 合并 patch。 |
| 11 | VG | 售出订单列表排序无测试覆盖（倒序测试只覆盖买家页），改升序仍绿 | `low` | pre-verified，采信变异验证 → patch（补 sold 页顺序断言）。 |
| 12 | VG-Other | 同 #2：`sold_orders` 无模板入口 | `medium` | 与 #2 同根因 → 合并 patch。 |

分组与路由：12 条中 2 条 `low → reject`（#6/#7）、1 条 `false → reject`（#8，文档已修正）；其余 9 条归为三组 patch——(A) 售出订单入口缺失（#2/#12，medium）；(B) 测试覆盖缺口：身份隔离 + 最近语义 + sold 排序 + 假阳性断言 + 常量硬编码（#3/#4/#5/#9/#10/#11）；(C) N+1（#1）。无 `intent_gap` / `bad_spec`，不触发 loopback。

## Design Notes

- 卖家过滤用跨关系 `product__owner`(订单本身无卖家字段);epic-4-context 的 `product__seller` 是编译期笔误,实现以模型真实字段为准。
- 列表不渲染 QQ/微信:隐私门控已在 4.3 详情页按状态实现,列表重复渲染会绕过该门控。
- 买家列表项链接到 `order_detail`(仅 buyer 可见);卖家列表项链接到 `product_detail`(公开)而非 `order_detail`,因后者只认 buyer,卖家点击进入会 404。
- 沿用 2.4 只读列表范式:不分页、创建时间倒序、`list()` 求值与空状态 context,不引入 Paginator。

## Verification

**Commands:**
- `python manage.py check` — 期望:`System check identified no issues`。
- `python manage.py makemigrations --check --dry-run` — 期望:`No changes detected`(本故事不新增迁移)。
- `python manage.py test orders -v 2` — 期望:全部用例 ok。
- `python manage.py test -v 2` — 期望:全量通过,无失败/跳过。
- 仓库约定解释器为 `.venv/Scripts/python.exe`(根目录下)。
