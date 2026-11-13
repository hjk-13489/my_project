---
title: '下单创建订单'
type: 'feature'
created: '2026-11-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: bf730d22339e11e1ad91540ded51f8e53ad310fb
context:
  - _bmad-output/project-context.md
  - _bmad-output/implementation-artifacts/epic-4-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `orders` 已有 4.4 交付的 `Order` 模型与状态机，但买家没有任何下单入口——商品详情页「立即购买」仍是 `href="#"` 占位，`orders` 的 views/urls/forms 全为空壳。FR-17 的「订单确认页 → 创建待支付订单」这一段完全缺失。

**Approach:** 在 `orders` 内新增一个订单确认/创建视图，从商品详情页「立即购买」进入，展示商品与价格、收集可选留言，确认后以服务端价格快照创建 `Order`；状态依赖模型默认值 `pending_payment`，视图不碰状态机。创建成功后落到最小订单详情页，让买家立刻看到「待支付」，并为 4.2 的「模拟支付」预留挂点。

## Decisions

- **D1（下单约束，选 A）**：禁止卖家购买自己发布的商品；同一 `buyer+product` 若已有进行中订单则拒绝再次下单。进行中 = `status` 不属于 `completed/reviewed/refunded/refund_failed`（即 `pending_payment`/`paid`/`received`/`dispute`）；已收尾的四种状态允许就该商品再下单。两条规则都在服务端应用层校验，以表单非字段错误呈现；**不新增 migration、不加 DB 唯一约束**。
- **D2（成功落点，选 A）**：创建成功后重定向到新建的最小订单详情页 `/orders/<id>/`。该页展示商品、价格、留言与当前状态，仅 `buyer` 本人可见（他人 404），为 4.2「模拟支付」按钮预留挂点；**不引入全站 messages 渲染、不改 `base.html`**。

## Boundaries & Constraints

**Always:**
- 仅「已登录」买家可下单（FR-17 不要求 `is_verified`）；未登录 GET/POST 均由 `login_required` 跳登录页。
- 可下单对象只能经 `Product.objects.visible()` 取得，非 `approved`／不存在一律 404（AD-9）。
- 建单字段全部由服务端决定：`buyer=request.user`、`product=product`、`price=product.price`（下单时快照，商品后续改价不影响历史订单）、`message` 取表单；**不得显式赋值 `status`**，依赖 `Order.status.default='pending_payment'`（AD-5）。
- 价格绝不从请求参数读取；表单只暴露 `message` 一个字段。
- D1 的两条校验与 `Order.objects.create()` 必须在同一个 `transaction.atomic()` 内完成，缩小重复提交的竞态窗口；拒绝时不产生任何订单。
- 订单详情页按 `buyer=request.user` 过滤，他人订单一律 404；卖家侧的「售出订单」属 4.5，本次不提供。
- 错误统一为表单错误，沿用现有模板「逐字段 `text-danger` + 非字段 `alert-danger`」的 Bootstrap 渲染方式。
- 沿用平铺 URL name（无 namespace）；新 include 追加在 `config/urls.py` 既有 `path("", ...)` 之后。

**Never:**
- 不修改 `orders/models.py`、`orders/migrations/`、`InvalidTransition`、`ALLOWED_TRANSITIONS` 与 `orders/tests.py` 既有 18 个状态机用例。
- 不修改 `listings` / `accounts` 的模型、视图、表单、迁移；不改 `Product.owner`、不改 `visible()`。
- 不实现模拟支付（4.2）、联系方式展示（4.3）、订单列表（4.5）、退款／互评；不注册 admin。
- 不渲染卖家 QQ/微信、学号；不改 `templates/accounts/profile.html` 的「我的订单」空态。
- 不改 `templates/base.html`、不引入全站 messages 渲染；不新增 migration／DB 唯一约束。
- 不接外部支付网关、不写支付流水；不引入新依赖。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 确认页 | 已登录 + `approved` 商品 GET | 200，展示标题/价格/卖家昵称/留言框与「确认下单」 | N/A |
| 成功建单 | POST 合法留言 | 新建 `Order`：`status=pending_payment`、`price`=商品当时价格、`buyer`=当前用户、`product`=该商品，随后 302 → `/orders/<id>/` | N/A |
| 留言为空 | POST `message=''` | 建单成功，`message` 为空字符串 | N/A |
| 价格快照 | 建单后改商品 `price` | 订单 `price` 仍为下单时值 | N/A |
| 留言超长 | POST `message` 超过 500 字 | 不建单，重渲染确认页 | 表单字段错误红字 |
| 不可见商品 | `pending/rejected/offline` 或不存在 pk，GET 或 POST | 404，不产生订单 | `get_object_or_404(visible())` |
| 未登录 | GET 或 POST | 302 至 `/login/?next=...`，不产生订单 | `login_required` |
| 非法方法 | PUT / DELETE | 405 | `require_http_methods` |
| 卖家自买 | `request.user == product.owner` 时 POST | 不建单，重渲染确认页 | 表单非字段错误「不能购买自己发布的商品」 |
| 重复下单 | 同一 `buyer+product` 已有进行中订单时 POST | 不建单，重渲染确认页 | 表单非字段错误「该商品已有进行中的订单」 |
| 已收尾再下单 | 同一 `buyer+product` 仅存在 `completed/reviewed/refunded/refund_failed` 订单 | 允许新建一张 `pending_payment` 订单 | N/A |
| 本人订单详情 | `buyer` GET 自己的订单 | 200，展示商品/价格/留言/当前状态 | N/A |
| 他人订单详情 | 非 `buyer` GET 该订单 URL | 404 | `get_object_or_404(buyer=request.user)` |

</frozen-after-approval>

## Code Map

- `orders/models.py:10-64` — `Order` 已具备 `buyer`/`product`/`price`/`message`(blank)/`status`(default `pending_payment`)/时间戳；直接 `objects.create()` 即可，**不需要新 migration**；终态集合见 `STATUS_CHOICES`（:13-22）。
- `orders/views.py`、`orders/urls.py`、`orders/forms.py` — 均为空壳，是本次主要落点；`orders/admin.py` 保持不动。
- `orders/tests.py:14-30` — `setUpTestData` 已有 `create_user` + `Product.objects.create(owner=..., status='approved')` 夹具；本次**追加**视图层用例，勿改既有用例。
- `listings/models.py:12-14, 46-54` — `ProductQuerySet.visible()`（仅 approved）与卖家字段名 `owner`（**不是 `seller`**）、`price` 为 `DecimalField(10,2)`。
- `listings/views.py:224-235` — 详情页用 `get_object_or_404(visible().select_related('owner'), pk=pk)`，可仿照；`listings/views.py:17-18` 示范 `@login_required` + `@require_http_methods` 叠加。
- `templates/listings/product_detail.html:36-41` — 登录态下「立即购买」为 `href="#"` 占位（第 38 行），本次仅替换该 href 为 `{% url 'order_create' product.pk %}`；「联系卖家」占位**保持不动**。
- `templates/listings/publish.html:29-42`、`templates/accounts/login.html:24-30` — `novalidate` + csrf + 逐字段／非字段 Bootstrap 错误渲染范例。
- `templates/orders/` — 本次新建目录，产出 `order_confirm.html` 与 `order_detail.html`；继承 `templates/base.html` 的 `title` / `content` block。
- `config/urls.py:29-35` — 追加 `path("orders/", include("orders.urls"))`，且必须排在两条 `path("", ...)` 之后。
- `config/settings.py:39,70,140` — messages 已启用且 `base.html` 未渲染；本次按 D2 不使用 messages，**不要改 base.html**；`LOGIN_URL='/login/'` 仍生效。

## Tasks & Acceptance

**Execution:**
- [x] `orders/forms.py` — 新增 `OrderCreateForm`（`forms.Form`，仅 `message` 字段，`required=False`、`Textarea`、`max_length=500`、中文 label）— 只暴露可由买家输入的字段，杜绝价格/买家/商品被客户端篡改。
- [x] `orders/views.py` — 新增 `order_create`（登录与 GET/POST 限制、`visible()` 取商品、GET 渲染确认页、POST 在同一事务内做 D1 两条校验并 `Order.objects.create(...)`，成功后 redirect 到 `order_detail`、失败走 `form.add_error(None, ...)`）与 `order_detail`（`@require_safe` + `login_required`，按 `buyer=request.user` 取订单，他人 404）— 完成 FR-17 主干与 D1/D2。
- [x] `orders/urls.py` — 定义 `order_create`（`orders/create/<int:product_pk>/`）与 `order_detail`（`orders/<int:pk>/`）两条 URL — 为 2.8 的「立即购买」与建单后跳转提供可解析的 name。
- [x] `config/urls.py` — 追加 `orders` include — 接通路由。
- [x] `templates/orders/order_confirm.html` — 继承 `base.html`，Bootstrap 渲染商品标题/价格/卖家昵称、留言框、逐字段与非字段错误、「确认下单」按钮 — 完成可见的确认步骤。
- [x] `templates/orders/order_detail.html` — 继承 `base.html`，展示商品/价格/留言/当前状态，不展示联系方式 — 承建 D2 的落点并给 4.2 留挂点。
- [x] `templates/listings/product_detail.html` — 替换第 38 行占位 href — 让「立即购买」真正进入下单。
- [x] `orders/tests.py` — 追加视图层用例覆盖 I/O 矩阵全部 13 行（含 D1 两条拒绝、已收尾可再下单、成功后 302 落点、本人/他人详情页、404、未登录、405、留言为空/超长、价格快照、订单归属）— 证明建单行为与门控。

**Acceptance Criteria:**
- Given 已登录买家与一件 `approved` 商品，when 从详情页点「立即购买」并确认提交，then 生成一张 `Order`，其 `buyer`/`product` 正确、`status == 'pending_payment'`、`price` 等于提交时商品价格、`message` 等于所填内容（可为空），and 响应 302 至该订单详情页。
- Given 买家就是商品 `owner`，或同一 `buyer+product` 已有进行中订单，when 提交确认，then 不产生任何 `Order`、页面重渲染并给出对应的表单非字段错误；and 若已有订单均已收尾，then 允许再建一张。
- Given 一张订单，when `buyer` 本人访问 `/orders/<id>/`，then 200 且展示商品、价格、留言与「待支付」状态；when 其他用户访问同一 URL，then 404。
- Given 本轮改动，when 全仓检索，then `status` 的赋值仍只出现在 `orders/models.py` 的 `_transition()` 内，视图未直接写状态、未调用任何转移方法。
- Given 非 `approved` 商品或匿名请求，when 尝试进入确认页或直接 POST，then 无任何 `Order` 产生。
- Given 本轮改动，when 跑全量测试，then 既有 242 例与新增用例全绿、`makemigrations --check --dry-run` 报 No changes detected。

### Review Findings

**第二轮审查（2026-11-13，full 模式）**：审查基线 `bf730d2..HEAD`（12 文件，+589/−10）；团队定制 `_bmad/custom/bmad-code-review.toml` 启用 Edge Case Hunter 与 Acceptance Auditor，Blind Hunter / Verification Gap 被禁用。两层共 10 条发现，分诊后 `decision-needed` 0、`patch` 0、`defer` 0、rejected 10，零发现存活；`review_loop_iteration` 保持 0，无 loopback。本轮未修改 AC、Execution、Verification 等任何冻结区或验收口径，仅追加本审查记录。

**Rejected**

- `low` — 并发 POST 双建（`orders/views.py:32-45`）：D1 冻结决策明确不加 DB 唯一约束／新 migration，Design Notes 已把该理论窗口列为已接受取舍；SQLite 下 `select_for_update()` 为 no-op，修复需新增守卫或公共表面，非直接修正，演示环境难触发。
- `low` — 事务内复用事务外 `product`（卖家并发改价／下架）：与上一条同源 TOCTOU，`visible()` 事务外取商品符合 Always 字面要求，修复需事务内重取加锁，增加复杂度且落在同一已接受窗口。
- `low` — 确认页与提交间卖家改价（`order_confirm.html` / `orders/views.py`）：Always 与 AC1 明确 `price` 取「提交时商品价格」，按提交时价正是规格要求，且 4.2 之前无实际收费；修复需签名价格令牌／版本号等新公共表面。
- `false` — `listings/tests.py` 移除 `/orders` 死链守卫但用例名仍含 Epic 4：`/orders/create/<pk>/` 已接通为真实路由，不再是死链；同处补了 `reverse('order_create')` 正向断言，`/chat`／`/dashboard` 守卫保留；紧邻注释已说明，且 `spec-2-8-商品详情页.md:131` 明确引用该用例名，改名反会破坏既有规格引用。
- `low` — AC4「全仓检索」口径被自身 grep 命令与新增测试夹具证伪：`git grep` 确认 `orders/views.py`／`forms.py` 无 `status=` 赋值，`status=target`／`self.status = target` 仅在 `orders/models.py:_transition()` 内，新增 `status=status` 只出现在 `orders/tests.py` 夹具且 Verification 已注明夹具不在范围；属 AC 措辞而非代码缺陷，修复需编辑本规格。
- `false` — D2「4.2 模拟支付挂点」仅一行 HTML 注释：独立 `order_detail.html` + 注释即为锚点，4.2 添加支付按钮本就必须编辑该模板；补 URL name／视图桩违反 Never「不实现模拟支付（4.2）」，坏结果不成立。
- `low` — `CharField` 默认 `strip=True` 与 AC1「message 等于所填内容」不符：Django 标准表单行为、用户不可见；改 `strip=False` 需新增参数，且会让纯空白串变成「非空留言」、与矩阵「留言为空」行语义冲突，属增加复杂度而非直接修正。
- `false` — 矩阵「PUT/DELETE → 405」对匿名不成立：RequestFactory 实测匿名 PUT／DELETE／POST／GET 一律 302 到 `/login/?next=...`，符合 Always「未登录跳登录页」与项目既定装饰器顺序（`listings/views.py:17-18`）；已登录 405 由 `test_unsafe_methods_405` 覆盖，匿名请求不产生订单或状态变更，无用户可见坏结果。
- `low` — `listings/tests.py` 属 Execution／Code Map 清单外改动且移除 2.8 的 `/orders` 否定断言：Implementation Notes 已逐条披露，Never 只禁止 `listings` 的模型／视图／表单／迁移（tests.py 不在其列），否定断言移除已由 `reverse('order_create')` 正向断言补偿；「回填清单」的修复需编辑本规格。
- `low` — AC6／Verification 基线数字（242）与 Implementation Notes（255／258）口径不一致：全量测试实跑全绿、代码与测试无缺陷，属验收期望值文档口径；修复需编辑本规格。

## Implementation Notes

- 8 条 Execution 全部完成：`orders/forms.py` / `views.py` / `urls.py` 三个空壳填实，新增 `templates/orders/order_confirm.html` 与 `order_detail.html`，`config/urls.py` 追加 `orders` include，`product_detail.html:38` 占位 href 接通 `order_create`。
- 视图用 `@login_required` + `@require_http_methods(['GET','HEAD','POST'])` 与 `@require_safe`；D1 两条校验与 `Order.objects.create()` 同处 `transaction.atomic()`；建单不传 `status`，复用模型默认值 `pending_payment`。
- 规格清单外的必要联动改动：`listings/tests.py` 3 处 story-2.8 交付时点守卫断言。原断言假定「立即购买」是 `href="#"` 且页面不含 `/orders`，与 4.1 接通真实路由必然冲突；改为 `href="#"` 计数 2→1、从死链守卫移除 `/orders`，并新增 `reverse('order_create', ...)` 正向断言，保留 `/chat` 与 `/dashboard` 守卫。属更新过期守卫而非削弱覆盖：既有 242 例数量不变，全量 255 例 OK；未触碰 listings 的模型/视图/表单/迁移。
- 主代理独立实跑：`check` → 0 issues；`makemigrations --check --dry-run` → No changes detected；`test orders --verbosity=2` → 31 例 OK（18 既有 + 13 新增，I/O 矩阵 13 行逐行有对应用例且全部 ran & passed）；全量 `test` → 255 例 OK；`git grep -nE "status[[:space:]]*=" -- orders/views.py orders/forms.py` → 无输出。
- 已知取舍：D1 无 DB 唯一约束，极端并发双击存在理论重复窗口（Design Notes 已接受）；`orders/models.py`、迁移、状态机与既有 18 例均未改动。
- 首轮审查补丁（Step 4，2 组 `medium → patch`）：`orders/tests.py` 追加 3 例 — 伪造 `price`/`buyer`/`product` POST 字段仍被忽略且表单字段集合仅 `['message']`、`order_detail` 匿名 GET 302 到登录页、已登录非法方法 405。主代理复跑：`check` 0 issues、`makemigrations --check --dry-run` → No changes detected、`test orders` 34 例 OK、全量 `test` 258 例 OK、status 赋值 grep 无输出。23 条裁决见 `## Review Triage Log`；1 组个人中心空态缺口已登记 `deferred-work.md`。

## Spec Change Log

## Review Triage Log

首轮三层审查（Blind Hunter 15 / Edge Case Hunter 5 / Verification Gap 2 gaps + 1 other，共 23 条），`review_loop_iteration` 保持 0（无 loopback）。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 1 | BH | spec `in-review` 与 sprint `in-progress` 状态不一致 | `false` | 与 spec-4-4 审查 #17 同一情形：sprint 的 `review` 同步由 Step 5 收尾统一写入，Step 4 只改 spec；此刻是流程中间态，非缺陷。 |
| 2 | BH | `listings/tests.py` 未列入 Execution / Code Map，实现超出清单 | `false` | Code Map 已列 `product_detail.html` 占位替换，2.8 死链守卫是其必然联动；Implementation Notes 逐条记录改动与理由，主代理已基于 diff 核对并实跑 255 例，「无从核对」不成立。 |
| 3 | BH | Spec Change Log / Review Triage Log 为空 | `false` | 模板规定二者分别「Empty until the first bad_spec loopback」与「Empty until the first review pass」；本轮即首轮审查，Triage Log 正由本表填充。 |
| 4 | BH | frozen 块无批准人 / 批准时间记录 | `false` | 工作流以 status 转换与 CHECKPOINT 1 的人类批准为凭，模板 frontmatter 无审批字段；本规格经用户「批准并继续」后由 draft → ready-for-dev 锁定。 |
| 5 | BH | AC「全仓检索」口径与 grep 范围、tests.py 夹具赋值相矛盾 | `low` | 措辞偏宽确实存在，但 4.4 冻结区 Never 已明确 `Order.objects.create(status=...)` 属测试夹具、不属业务写入路径；grep 的 expected 亦注明夹具不在范围内。修复需编辑本次 build 的规格 → 驳回。 |
| 6 | BH | 无测试锁住伪造 `price`/`buyer`/`product` 被忽略 | `medium` | 与 #21 同根因，VG 已实跑变异验证（把 `price=product.price` 改为读 `request.POST` 后 35 例仍全绿）。真实回归缺口 → patch。 |
| 7 | BH | 确认页与提交之间卖家改价会按新价静默建单 | `low` | Always 明确 `price` 是「下单时快照」，只有一种读法，非意图缺口；修复需引入锁价令牌 / 版本号等新公共表面，非直接修正，演示环境难触发 → 驳回。 |
| 8 | BH | `order_detail` 未用 `select_related('product')` | `low` | 单笔订单详情页多一次关联查询，NFR-1 只约束列表/搜索；无用户可见性能坏结果，属提前优化 → 驳回。 |
| 9 | BH | `order_detail` 缺匿名 / 非法方法 / 不存在 pk 场景与用例 | `medium` | 与 #22 同根因，VG 已实跑验证删 `@login_required` 匿名 GET 得 500、删 `@require_safe` 放行 POST，35 例仍全绿 → patch。 |
| 10 | BH | 矩阵「PUT/DELETE→405」缺认证前提、HEAD 无场景 | `false` | 已登录非法方法实测 405（`test_unsafe_methods_405`）；匿名请求按 Always「未登录跳登录页」本就应 302，`login_required` 在外层是项目既定顺序；HEAD 由 Django 自动映射 GET 渲染路径，无独立坏结果。 |
| 11 | BH | 卖家在详情页仍见「立即购买」，须提交后才被拒 | `low` | D1 只要求服务端拒绝，已实现且给出明确表单错误；隐藏按钮需新增模板分支，卖家自买场景日常不可见 → 驳回。 |
| 12 | BH | `atomic()` 无 `select_for_update`，并发仍可双建 | `low` | 与 #16/#17 同根因；SQLite 下 `select_for_update()` 是 no-op（全仓本就无该用法），锁不住；D1 冻结决策明确不加 DB 约束，Design Notes 已把理论窗口列为已接受取舍 → 驳回。 |
| 13 | BH | D2「模拟支付挂点」只有一行 HTML 注释 | `false` | 独立 `order_detail.html` + 注释即为锚点；补 URL name / 视图桩会违反 Never「不实现模拟支付（4.2）」，坏结果不成立。 |
| 14 | BH | 离开订单 URL 后无入口回到刚创建的订单 | `low` | 与 #23 同根因（个人中心恒空态 + 4.5 未交付），真实但属本故事之前既有，规格 Never 明确排除 → defer。 |
| 15 | BH | Implementation Notes 写 255 例、Verification 期望仍写基线 242 | `low` | 文档期望值未同步确实存在，但主代理已实跑 255 例 OK 并记入 Implementation Notes；修复需编辑本次 build 的规格 → 驳回。 |
| 16 | EC | 并发 POST 同时通过 `exists()` 双建 | `low` | 同 #12：SQLite 行锁无效、D1 已接受该窗口，修复需新公共表面 → 驳回。 |
| 17 | EC | 事务内复用事务外取得的 `product`（并发改价/状态） | `low` | 与 #12/#16 同源 TOCTOU；`visible()` 在事务外取商品符合 Always 字面要求，并发变更窗口与已接受的 D1 窗口同源，非独立缺陷 → 驳回。 |
| 18 | EC | 匿名 PUT/DELETE 返回 302 而非 405 | `false` | 同 #10；匿名非法方法先跳登录页，不产生写入或状态变更，坏结果不成立。 |
| 19 | EC | 测试名 `test_no_epic3_4_5_dead_links` 仍含 Epic 4 | `low` | 紧邻注释已写明「Epic 4 的 /orders/create/<pk>/ 已由 4.1 接通…故从守卫中移除」，误导已消解；且 spec-2-8:131 明确引用该用例名，改名会使既有规格引用脱节，收益低于风险 → 驳回。 |
| 20 | EC | `CharField` 默认 strip 裁剪首尾空格，与「等于所填内容」不符 | `low` | Django 标准表单行为、用户不可见损害；改 `strip=False` 反使纯空白串变成「非空留言」，AC 的「等于所填内容」指语义内容 → 驳回。 |
| 21 | VG | 防篡改约束无测试钉住（pre-verified gap） | `medium` | 采信 filed evidence：实跑把 `price=product.price` 改为 `request.POST.get('price', …)` 后 35 例仍全 OK，买家可 POST `price=0.01` 造低价单。与 #6 合并 → patch。 |
| 22 | VG | `order_detail` 登录 / 方法门控无用例（pre-verified gap） | `medium` | 采信 filed evidence：删 `@login_required` 匿名 GET 得 500、删 `@require_safe` 放行 POST，35 例仍全绿。与 #9 合并 → patch。 |
| 23 | VGO | `accounts/views.py:146` `my_orders_empty=True` 恒空态 | `low` | 真实（已核实 profile.html:82 消费该值），但属 1.5 既有、4.1 未改，规格 Never 明确把个人中心订单板块留到 4.5；与 #14 合并 → defer。 |

分组与路由：23 条中 7 条 `false`、10 条 `low → rejected`、2 组 `medium → patch`（#6+#21 防篡改回归测试、#9+#22 order_detail 门控用例）、1 组 `low → defer`（#14+#23 个人中心恒空态 / 订单可达性）。无 `intent_gap` / `bad_spec`，不触发 loopback，`review_loop_iteration` 保持 0。

## Design Notes

- 用 `forms.Form` 而非 `ModelForm`：`Order` 的 `buyer`/`product`/`price` 是服务端推导的信任数据，暴露为表单字段等于允许改价与代他人下单；只留 `message` 最贴 FR-17「留言可空」。
- 不显式传 `status`：4.4 已专门补 `test_new_order_defaults_to_pending_payment` 锁住默认值，视图复用它即满足 AD-5「视图不得直接改 status」。
- 单视图同时处理 GET 确认页与 POST 建单，与 `listings/views.py:17-18` 的既有装饰器组合一致，避免多出一个只做跳转的薄视图。
- D1 落在应用层而非数据库：加 `UniqueConstraint` 必须新增 migration（D1 明确不做），故以「同事务内先查后建」缩小竞态窗口；极端并发双击的理论重复窗口是本次已接受的取舍，不构成静默状态错误。
- D1「进行中」的判定黄金示例（置于同一 `transaction.atomic()` 内，卖家字段用 `product.owner`）：

  ```python
  CLOSED = ('completed', 'reviewed', 'refunded', 'refund_failed')
  if request.user == product.owner:
      form.add_error(None, '不能购买自己发布的商品')
  elif Order.objects.filter(buyer=request.user, product=product).exclude(status__in=CLOSED).exists():
      form.add_error(None, '该商品已有进行中的订单')
  ```

- 订单详情页按 `buyer` 单人过滤：4.5 才提供卖家侧「售出订单」，若此刻放宽到卖家会提前引入 4.5 的授权面；4.2/4.3 的挂点只需 buyer 视角。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: No changes detected
- `.venv/Scripts/python.exe manage.py test orders` — expected: 既有 18 例 + 新增视图用例全 OK
- `.venv/Scripts/python.exe manage.py test` — expected: 全量（基线 242 例）无回归
- `git grep -nE "status[[:space:]]*=" -- orders/views.py orders/forms.py` — expected: 无输出（视图/表单不写 `status`；`orders/tests.py` 的夹具赋值不在检索范围内）

**Manual checks (if no CLI):**
- 以已登录买家打开任一 `approved` 商品详情页，「立即购买」链接指向订单确认页且可点；提交后落到 `/orders/<id>/` 并显示「待支付」与所填留言；换另一个账号访问同一 URL 得 404。
