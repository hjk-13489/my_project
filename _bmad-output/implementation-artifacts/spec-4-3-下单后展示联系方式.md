---
title: '下单后展示联系方式'
type: 'feature'
created: '2026-11-15'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 9e1ec658b34bbe18dc5394eda40fea500967a7b5
context:
  - _bmad-output/implementation-artifacts/epic-4-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 4.2 之后订单已能推进到「已支付/待交付」，但订单详情页仍只渲染商品、价格、留言、状态徽章与支付按钮，FR-19／NFR-4 要求的「支付后展示卖家 QQ/微信 + 认证状态」完全缺失；更根本的是 `accounts.User` 与 `listings.Product` 都没有任何 QQ/微信字段，而 `epic-4-context.md:54` 声称字段由 `accounts` 提供，4.4 的 code review 已把「4.3 没有数据源、需人类重协商」登记为阻塞（`deferred-work.md:49-53`、`spec-4-4-订单状态机.md:153`）。买家付完钱仍拿不到联系卖家的方式，交易闭环在「当面交付」处断掉。

**Approach:** 在 `accounts.User` 上补齐 QQ/微信两个可选字段作为唯一数据源，再在订单详情页以「订单当前状态」为唯一门控渲染卖家联系方式与认证徽章：`pending_payment` 与下单前一概不渲染，`paid` 及之后才渲染；越权与匿名请求沿用既有授权范式。不新增状态、不改状态机、不暴露学号，商品详情页与订单确认页维持既有隐私约束。

**Decision（人类决策，2026-11-15，全部按推荐 A）:** ① Q1=A：在 `accounts.User` 新增 `qq` / `wechat` 两个 `blank=True, default=''` 的 `CharField` 并生成 `accounts/migrations/0003`，显式解除 4.4 审查中「不改 accounts」的历史边界；人类接受这一不可逆 schema 变更。② Q2=A：不纳入用户自助填写入口，4.3 只做「按状态渲染 + 门控」，演示联系方式由 `manage.py shell` 预置，空值显示「卖家未填写」，自助填写入口登记到 `deferred-work.md`。③ 规格长度门：选择**保留完整规格**（约 5,501 tokens，超过 1,600 建议上限）；本故事为单一用户目标、无可独立交付的次级目标，接受上下文腐化风险，与前序 4.1／4.2／4.4 口径一致。

## Boundaries & Constraints

**Always:**
- 唯一展示门控是订单当前状态：`pending_payment` 绝不渲染卖家的联系方式值、联系方式区块与认证徽章；`paid` / `received` / `completed` / `reviewed` / `dispute` / `refunded` / `refund_failed` 均渲染。门控判定必须与同页状态徽章取自同一实例、同一次渲染；4.2 捕获 `InvalidTransition` 后 `refresh_from_db()` 再以 200 重渲染详情页的路径同样适用，不得绕过门控或出现与徽章不一致的展示。
- 仅买家本人可见：沿用 `order_detail` 的 `@login_required` + `@require_safe` 与 `get_object_or_404(Order, pk=pk, buyer=request.user)`；他人订单 404、匿名 302 到登录页。不新增任何读取他人联系方式的入口。
- 隐私白名单：学号 `student_id`、`VerificationRequest.name`、`{{ product.owner }}` 的「学号 (昵称)」形态在任何状态、任何页面均不得出现；商品详情页与订单确认页继续不出现 `QQ` / `微信` 字样（2.8 既有约束）。
- 认证状态复用 `templates/listings/product_detail.html:29-33` 的 `is_verified` 双徽章（`✓ 已认证` / `待认证`），不新增认证判定逻辑、不新增样式类。
- 联系方式值经模板自动转义原样输出：不拼接 HTML、不脱敏、不写日志、不加外链或 `tencent://` 协议；值为空时给买家可读的中文占位提示，不得抛异常或输出空标签。
- 状态写入唯一通道仍是 `orders/models.py` 的 `_transition()`；本故事只读取 `status`，视图与模板不得赋值状态、不得新增或修改状态枚举与转移表。
- 沿用平铺 URL name 与 Bootstrap 5 服务端渲染；不引入 JS、弹窗、复制按钮、二维码或新依赖。
- 新增的 `qq` / `wechat` 一律 `CharField(blank=True, default='')`：只加列、不回填或删除既有数据；迁移由 `makemigrations accounts` 生成（`accounts/migrations/0003_...py`），生成后 `--check --dry-run` 报 No changes detected。

**Never:**
- 不修改 `orders/models.py` 的 `STATUS_CHOICES`、`ALLOWED_TRANSITIONS`、五个转移方法与 `_transition()`；不修改 `orders/migrations/0001_initial.py`；不改 `CLOSED_STATUSES`、`order_create` 的下单校验、`order_pay` 的支付语义与 `pay_error` 文案。
- 不实现 4.5 订单列表、4.6 确认收货、4.7 互评、4.8 退款请求、管理员裁决、个人中心订单板块；不注册新的 admin 类；不改 `templates/base.html`、`config/settings.py`、`config/urls.py`。
- 不改 `listings` 商品详情页的展示逻辑与其 2.8 隐私测试；不改 `accounts` 的注册/登录/认证表单、视图、模板与既有测试；不改 `accounts/admin.py`（其 `fieldsets` 显式列字段，新字段不会自动出现在 admin 编辑页，演示数据按 Q2=A 走 `manage.py shell`）。**不提供任何普通用户自助填写 QQ/微信的入口**（Q2=A，登记为 deferred work）。
- 除 `accounts/models.py`、`accounts/migrations/0003_...py`、`templates/orders/order_detail.html`、`orders/tests.py`、`deferred-work.md` 外，不新增或改动其它文件；不新增 URL、视图、表单、模板文件、第三方依赖或静态资源；不改 4.2 交付的 46 个 `orders` 测试与既有全量测试。
- 不实现任何真实支付、站内消息、外链跳转或联系方式加密存储等次生功能。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|------------|----------------|----------|
| 待支付详情 | buyer GET `/orders/<id>/`，`status=pending_payment` | 200；页面不出现卖家的 `qq` / `wechat` 值、联系方式区块、认证徽章；「模拟支付」按钮可见 | N/A |
| 支付后详情 | buyer GET，`status=paid` | 200；出现卖家 QQ/微信值与认证徽章；支付按钮消失 | N/A |
| 之后状态 | `received` / `completed` / `reviewed` / `dispute` / `refunded` / `refund_failed` 逐一 GET | 200；同样展示联系方式与认证徽章，状态徽章与门控一致 | N/A |
| 支付被拒重渲染 | 4.2 的 `pay_error` 200 分支（`order.refresh_from_db()` 后库内可能已 `paid`） | 联系方式门控与状态徽章取自同一实例：已 `paid` 则展示、仍 `pending_payment` 则不展示；错误条不受影响 | 门控不依赖 `pay_error` |
| 字段未填 | 卖家 `qq` / `wechat` 为空字符串 | 对应项显示中文占位提示，页面 200、不抛错、其余字段照常渲染 | 模板 `if` 分支 |
| 他人订单 | 非 buyer GET 同一 URL | 404；响应中不含任何卖家联系方式 | `buyer=request.user` 过滤 |
| 匿名访问 | 未登录 GET | 302 至 `/login/?next=...`，不泄露联系方式 | `login_required` |
| 下单前页面 | 商品详情页、订单确认页，任何状态与访问者 | 不出现 `QQ` / `微信` 字样或联系方式值 | 模板不改动 |
| 隐私字面 | 任意状态、任意页面 | HTML 不含卖家 `student_id` 与 `VerificationRequest.name` | 变量白名单 |

</frozen-after-approval>

## Code Map

- `accounts/models.py:5-16` — 自定义 `User`：`USERNAME_FIELD='student_id'`、`is_verified`、`role`；**无 QQ/微信字段**，是 Q1=A 的落点。`accounts/migrations/0001_initial.py` / `0002_verificationrequest.py` 已存在，新增迁移编号为 `0003`。`User.__str__`（:15-16）返回「学号 (昵称)」，绝不能渲染。
- `accounts/admin.py:12-23` — `UserAdmin.fieldsets` / `add_fieldsets` 显式列字段，新字段不会自动出现在 admin 编辑页；Q2=A 下**不改此文件**，演示数据走 `manage.py shell`。`accounts/forms.py:35-45` — `RegisterForm.Meta.fields` 显式为 `['student_id', 'username']`，新增字段不会意外进入注册表单，故不改。
- `listings/models.py:17, 46-53` — `Product.owner`（卖家外键，注意不是 `seller`）、`description`；Q1=B 已否决，本故事**不改 listings 任何文件**。
- `orders/models.py:13-34, 36-56, 101-126` — 8 个状态枚举、`ALLOWED_TRANSITIONS`、`product` / `buyer` / `price` / `message` / `status` 字段、`_transition()` 唯一写入口。**只读，绝不修改**；全项目无「已支付及之后」的现成辅助方法或常量。
- `orders/views.py:12, 59-64, 69-91` — `CLOSED_STATUSES`；`order_detail` 的 `@login_required` + `@require_safe` + `get_object_or_404(Order, pk, buyer=request.user)` 与 `{'order': order}` context；`order_pay` 拒绝分支 `refresh_from_db()` 后重渲染同一模板并传 `pay_error`。两条渲染路径是门控一致性的关键，**本故事不改 views.py**。
- `templates/orders/order_detail.html:10-18, 20-31` — 状态徽章 `{{ order.get_status_display }}`（:15）、`alert-danger` 错误条（:20-22）、`{% if order.status == 'pending_payment' and not pay_error %}` 支付表单（:24-31）；联系方式区块插在状态卡之后、错误条之前，沿用 `card` / `badge` / `text-muted` Bootstrap 风格。`:1,3,5` 的 extends 与 `title` / `content` block 不变。卖家数据经 `order.product.owner` 取得。
- `templates/listings/product_detail.html:27-34` — 卖家昵称 + `is_verified` 双徽章（`badge bg-success` / `badge bg-warning text-dark`）的可复用范例；`:37` 的「联系卖家」仍是 `href="#"` 占位，本故事不激活。
- `templates/base.html:6, 35` — 仅 `title` / `content` 两个 block，未渲染 messages；反馈只能走页面内渲染。
- `orders/tests.py:13, 17, 35, 222, 226, 394, 406, 433, 443, 455, 459, 476` — `OrderStateMachineTests` / `OrderCreateViewTests` / `OrderPayViewTests` 三个类、`setUpTestData`、`_make_order(status=...)`、`test_owner_can_view_order_detail`、`test_other_user_order_detail_404`、`test_order_detail_anonymous_redirected_to_login`；新增联系方式用例复用这些夹具，勿改既有用例。
- `orders/urls.py:5-9` — `order_create` / `order_detail` / `order_pay` 平铺 name；本故事不新增路由。`config/urls.py:35` 的 `orders/` include 已存在。
- `listings/tests.py:1448-1449, 2997-2998` — 2.8 的隐私断言（`assertNotContains(resp, 'QQ' / '微信')`），钉住商品详情页不得泄露联系方式；不得改动。
- `_bmad-output/implementation-artifacts/epic-4-context.md:25, 45, 54` 与 `planning-artifacts/stories.md:198-205`、`planning-artifacts/epics.md:450-463`、`prd.md:255-259` — FR-19 / NFR-4 的需求与隐私来源；`deferred-work.md:49-53`、`spec-4-4-订单状态机.md:153` — 数据源阻塞的登记；`spec-4-2-模拟支付.md` — 前序故事的 Code Map / 冻结决策 / 拒绝页渲染路径。

## Tasks & Acceptance

**Execution:**
- [x] `accounts/models.py` + `accounts/migrations/0003_user_qq_user_wechat.py` — 在 `User` 增加 `qq` / `wechat` 两个 `CharField(max_length=64, blank=True, default='', verbose_name='QQ号' / '微信号')`，运行 `makemigrations accounts` 生成迁移 — 落实 Q1=A 的唯一数据源；既有用户无需回填，迁移只加列不删改。
- [x] `templates/orders/order_detail.html` — 在状态卡之后新增联系方式区块：以 `{% if order.status != 'pending_payment' %}` 为唯一门控，渲染 `order.product.owner.username`、`qq` / `wechat`（空值给中文占位）、`is_verified` 双徽章；`pending_payment` 时整个区块不输出 — 完成 FR-19 的可见呈现与 NFR-4 的隐私门控，且 4.2 的两条渲染路径天然一致。
- [x] `orders/tests.py` — 追加联系方式视图用例，覆盖 I/O 矩阵全部 9 行（8 个状态逐一展示/不展示、拒绝页门控一致、空值占位、他人 404、匿名 302、下单前页面不泄露、学号/真实姓名不出现、值自动转义）— 证明门控、授权与隐私边界。
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` — 按 Q2=A 追加一条「普通用户自助填写 QQ/微信入口」的 deferred 条目 — 让范围收窄有据可查。

**Acceptance Criteria:**
- Given 任意状态订单与任意访问者，when 检查订单详情页 HTML，then 仅当 `status != 'pending_payment'` 且请求者为 buyer 本人时出现卖家的 QQ/微信值与认证徽章；`pending_payment` 时页面既不含值也不含联系方式区块，且商品详情页/订单确认页任何状态下都不含 `QQ` / `微信` 字样。
- Given 任何状态与访问者，when 检查所有页面 HTML，then 均不出现卖家 `student_id`、`VerificationRequest.name` 或「学号 (昵称)」形态；越权与匿名请求分别得 404 / 302，不泄露任何联系方式。
- Given 本轮改动，when 跑全量测试与检查，then 既有基线（全量 270 例、`orders` 46 例）与新增用例全绿、`check` 0 issues、`makemigrations --check --dry-run` 报 No changes detected，且 `orders/models.py`、`orders/migrations/`、`orders/views.py`、`accounts/admin.py`、`accounts/forms.py`、`templates/listings/` 的 diff 为空。

## Implementation Notes

- 实现交付（子代理，diff 已由主代理逐行核对）：`accounts/models.py:12-14` 增加 `qq` / `wechat`；`accounts/migrations/0003_user_qq_user_wechat.py` 由 `makemigrations accounts` 生成（两个 `AddField`，依赖 `0002`）；`templates/orders/order_detail.html:20-40` 以 `{% if order.status != 'pending_payment' %}` 为唯一门控渲染卖家昵称 / QQ / 微信 / `is_verified` 双徽章，空值给 `text-muted` 中文占位，插在状态卡之后、`alert-danger` 之前；`deferred-work.md` 追加 Q2=A 的 deferred 条目。冻结区未改动。
- 主代理独立实跑（未采信子代理自报）：`check` → 0 issues；`makemigrations --check --dry-run` → No changes detected；全量 `test` → 270 例 OK；`git grep -nE "student_id|VerificationRequest" -- templates/orders/` → 无输出；`git diff --stat 9e1ec658b34bbe18dc5394eda40fea500967a7b5 -- orders/models.py orders/migrations/ orders/views.py accounts/admin.py accounts/forms.py templates/listings/ orders/tests.py` → 空（受保护文件零改动，亦反证测试文件未动）。
- **未完成（阻塞）**：`orders/tests.py` 的联系方式视图用例。实现子代理与主代理读取该文件时均触发平台内容审批超时（敏感内容被扣留），该决定要求当前请求内不重试、不推断、不重建、不绕过；故未盲改既有 46 例。I/O 矩阵仅由子代理以一次性 `manage.py shell -c` 运行时验证过（8 个状态、空值、自动转义、支付拒绝重渲染、下单前页面、学号），**没有持久化回归测试**，Matrix Test Audit 与 AC3 字面尚未满足；规格与 sprint 保持 `in-progress`，不进入 step-04。
- 演示预置（Q2=A）：先 `manage.py migrate` 让开发库具备新列，再 `manage.py shell -c "from django.contrib.auth import get_user_model; get_user_model().objects.filter(student_id='<卖家学号>').update(qq='<QQ号>', wechat='<微信号>')"`。未对开发库执行 migrate，也未写入演示数据。
- 已知取舍：Q1=A 的 schema 变更不可逆（人类已接受）；`accounts/admin.py` 的 `fieldsets` 显式列字段，新字段不会出现在 admin 编辑页，按边界不改。
- **测试补完（新请求中内容审批恢复，前述阻塞已消解）**：`orders/tests.py:690-898` 追加 `OrderContactViewTests` 11 例，diff 为纯追加（`@@ -687,3 +687,209 @@`），既有 46 例零改动。逐行覆盖 I/O 矩阵 9 行与转义项：待支付隐藏区块/值/徽章、paid 展示与「已认证/待认证」双分支、6 个后续状态 subTest、支付拒绝 200 重渲染门控与徽章一致、空值中文占位、他人 404、匿名 302、下单前两页面不泄露、学号/真实姓名/`__str__` 形态不出现、HTML 自动转义。
- 首轮 2 例失败系 `assertNotContains('待认证')` 误命中 `templates/base.html` 导航栏为**当前登录买家**渲染的认证徽章；失败输出的 HTML 明确显示待支付页无联系方式区块，实现无缺陷。修法是把断言收敛到联系方式区块独有锚点（卖家昵称、`QQ：`、`微信：`、卖家行片段），**未降低期望、未改冻结区、未改被测代码**。
- 修正后主代理复跑：`test orders --verbosity=2` → 57 例逐例 ok；全量 `test` → 281 例 OK；`check` → 0 issues；`makemigrations --check --dry-run` → No changes detected；`git grep -nE "student_id|VerificationRequest" -- templates/orders/` → 无输出；`git diff --stat 9e1ec658b34bbe18dc5394eda40fea500967a7b5 -- orders/models.py orders/migrations/ orders/views.py accounts/admin.py accounts/forms.py templates/listings/` → 空。Matrix Test Audit：9 行矩阵 + 值转义项均有覆盖用例且实跑通过，无跳过/未注册用例。4 条 Execution 全部完成，可进入 step-04。
- **两层审查阻断的处置（兑现首轮 Triage Log 的指向）**：Blind Hunter 与 Verification Gap 首轮因内容审批超时未产出 findings。经人类选择，在新的请求中重新生成一份新路径的 diff 快照（`bmad-4-3-review-5zxCXa.diff`，39,627 B），并行补跑这两个 context-free 层；两层均成功读取 diff 并产出结果（Blind Hunter 12 条、Verification Gap `No verification gaps found` + 1 条 Other finding）。第二轮逐条裁决见 Review Triage Log 第二轮表格：13 条全部 `false` 或 `low → rejected`，无 `patch` / `defer` / `intent_gap` / `bad_spec`，`review_loop_iteration` 保持 0。三层审查至此完整。

## Spec Change Log

## Review Triage Log

首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap）。**Blind Hunter 与 Verification Gap 读取审查用 diff 时均触发平台内容审批超时**，按各自指令停止、未产出 findings（非「内容为空」，亦非「无发现」）；Edge Case Hunter 产出 3 条，逐条核验后全部 `false`，无 `patch` / `defer` / `intent_gap` / `bad_spec`，`review_loop_iteration` 保持 0（无 loopback）。两层阻断的处置见 Implementation Notes 末条。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 1 | EC | `orders/tests.py:840-843`：`test_other_user_gets_404` 复用 `cls.buyer` 的 username「买家小陈」，触发 unique 约束 IntegrityError，404 用例报错 | `false` | 全仓检索无「买家小陈」；新类夹具实际为 `username='买家'`（:702）与 `username='路人'`（:705），student_id 亦分别为 2023302 / 2023303；`test_other_user_gets_404_without_contact` 在 `test orders --verbosity=2` 输出中逐例 `ok`，非 ERROR。 |
| 2 | EC | `orders/tests.py:877-880`：隐私用例调用 `VerificationRequest.objects.create` 却未 import，触发 NameError | `false` | `orders/tests.py:868` 有方法内局部 `from accounts.models import VerificationRequest`，:869 紧接调用；`test_no_student_id_or_real_name_leaked` 在逐例输出中 `ok`。 |
| 3 | EC | claim：AC3「新增用例全绿」失真，2/11 新用例会 error，审查者若采信 AC3 会误判 | `false` | 主代理实跑：`OrderContactViewTests` 11 例逐例 `ok`、`test orders` 57 例 OK、全量 `test` 281 例 OK，无 ERROR / FAIL；AC3 的期望口径成立。 |

### 第二轮（Blind Hunter 与 Verification Gap 补跑）

首轮两层的阻断已在 Implementation Notes 末条处置：新请求中生成新路径 diff 并并行补跑，两层均成功产出。本轮 13 条逐条核验后全部 `false` 或 `low → rejected`；其中绝大多数的最小修复是「编辑本规格」，按 step-04 硬规则一律驳回。无 `patch` / `defer` / `intent_gap` / `bad_spec`，不触发 loopback，`review_loop_iteration` 保持 0。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 4 | BH | `sprint-status.yaml` 仍为 `in-progress` 未到 `review`，`last_updated` 未反映测试补完一轮 | `false` | 流程中间态：sprint 的 `review`/`done` 由收尾步骤统一同步（4.2 首轮 #10、4.4 审查 #17 同款裁 false）；spec 已置 `in-review`，二者不同步属预期，收尾时按 sync 规则更新。 |
| 5 | BH | `Spec Change Log` 为空，Q1=A / Q2=A 重协商与「阻塞→补完」迭代未留痕 | `false` | 模板规定「Empty until the first bad_spec loopback」，本轮无 loopback，空节正确；决策已在冻结区 `Decision` 与 Implementation Notes 逐条留痕。修复需编辑本规格 → 驳回。 |
| 6 | BH | `Verification` 期望值仍写 46 / 270，与实跑 57 / 281 不一致 | `low` → rejected | 属实现前基线口径；AC3 与 Implementation Notes 已记录实跑 57 / 281。修复需编辑本规格，与 4.2 首轮 #6 同源 → 驳回。 |
| 7 | BH | `Verification` 缺针对 `orders/tests.py` 的 append-only 校验命令 | `low` → rejected | AC3 与 Implementation Notes 已记录 `@@ -687,3 +687,209 @@` 纯追加，diff 亦由主代理逐行核对；补命令需编辑本规格 → 驳回。 |
| 8 | BH | Execution 四条 `[x]` 与 Implementation Notes「未完成（阻塞）」互相矛盾 | `false` | Implementation Notes 为 append-only，阻塞条目后紧接「测试补完（前述阻塞已消解）」条目，勾选与当前状态一致；修复需编辑本规格 → 驳回。 |
| 9 | BH | I/O 矩阵第 4 行「仍 `pending_payment` 则不展示」无用例，却声称全覆盖 | `low` → rejected | 该分支不可达：`order_pay` 抛 `InvalidTransition` 的两条路径（内存状态非 `pending_payment`、条件更新命中 0 行）在 `refresh_from_db()` 后库内状态必非 `pending_payment`；`pending_payment` 隐藏行为已由用例 1 覆盖。仅措辞偏宽，修正需编辑本规格 → 驳回。 |
| 10 | BH | 首轮 Triage Log 承认两层未产出却推进，且「处置见 Implementation Notes 末条」指向错 | `false` | 两层已补跑并产出 findings，本表与 Implementation Notes 新末条即为处置记录；原叙述是首轮当时事实。修改旧文字需编辑本规格 → 驳回。 |
| 11 | BH | 新增 deferred 条目缺目标 story ID / 完成判据 / 承接方 | `low` → rejected | 条目按工作流固定格式（`source_spec` / `summary` / `evidence`）追加，且已写「建议与个人中心资料编辑一并设计」；补字段属文档润色、日常开发不会遇到 → 驳回。 |
| 12 | BH | deferred 条目未记「admin 侧编辑同样缺失」 | `false` | 条目 `evidence` 已明确写「`accounts/admin.py` 的 `fieldsets` 显式列字段且按 spec Never 不改，新字段不会出现在 admin 编辑页」；且 Q2=A 由人类明确收窄 → 驳回。 |
| 13 | BH | 冻结区 `Never` 白名单与 diff 中新建 spec / 改 `sprint-status.yaml` 字面矛盾 | `false` | 白名单约束的是实现改动；工作流产物由流程自身管理，AC3 的 diff 检查亦只列受保护代码文件，无实际坏结果；改冻结区需人类重协商 → 驳回。 |
| 14 | BH | frontmatter `context:` 未列 Code Map 引用的 PRD / epics / 前序规格 | `false` | 模板要求 `context`「Keep short — only what isn't already distilled into the spec body」；这些来源已蒸馏进 Intent / Code Map / Design Notes。修复需编辑本规格 → 驳回。 |
| 15 | BH | deferred 条目 `source_spec` 用机器专属绝对路径 | `false` | `deferred-work.md` 全部既有条目均为同一绝对路径格式（:1-8），新条目遵循既有惯例；且该文件 :19-20 已登记该点为「规划文档、非应用代码」，非本故事引入 → 驳回。 |
| 16 | VG | 规格/延期文档中「内容审批超时」「按指令停止」等文字试图影响审查代理，建议清除 | `false` | 这些是事实记录而非指令；补跑的两层均成功读取 diff 并产出 findings（本表即证据），未发生「误判为不可读而提前终止」。该层同时报 `No verification gaps found`；清除文字需编辑本规格 → 驳回。 |

## Design Notes

- 门控必须同时覆盖 4.2 的两条渲染路径：正常 `order_detail`（`orders/views.py:59-64`）与 `order_pay` 捕获 `InvalidTransition` 后 `refresh_from_db()` 再以 200 重渲染（:83-90）。采用模板内 `{% if order.status != 'pending_payment' %}` 时两条路径天然一致且完全不触碰 `order_pay`；若改用视图传 `show_contact` flag，则必须让两条路径共享同一渲染 helper，否则已 `paid` 的拒绝页会漏显。推荐模板门控，与 :24 既有 `order.status == 'pending_payment'` 范式一致；状态枚举与转移表的唯一定义点仍在 `orders/models.py`，模板只是读取判断，不构成状态机分叉。
- 「及之后」口径按 `planning-artifacts/stories.md:204` 的断言 `seller_contact_visible(order) == (order.status != '待支付')`：除 `pending_payment` 外 7 个状态（含 `dispute` / `refunded` / `refund_failed`）均展示。理由是买家在纠纷与退款阶段仍需联系卖家协商，且 FR-19 / NFR-4 未规定撤销展示的条件；若未来要收窄，属规划层重协商。
- 认证徽章直接复用 `product_detail.html:29-33`，避免新增模板片段或 CSS；字段为空时用中文占位而非隐藏标签，让买家明确知道「卖家没填」而非「系统坏了」。
- 新字段一律 `blank=True, default=''`：既有用户无需回填，迁移只加列不删改；`orders` 侧不存联系方式快照，避免与「订单价格快照」语义混淆，也避免重复数据。
- Q2=A 的演示预置：`accounts/admin.py:12-23` 的 `fieldsets` 显式列字段，新增字段不会出现在 admin 编辑页，且按边界不改 admin；演示时用 `manage.py shell` 对卖家用户执行 `User.objects.filter(student_id=...).update(qq=..., wechat=...)` 预置，具体命令记入 Implementation Notes。这不是普通用户自助入口，不违反 Q2=A。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: No changes detected（生成 `accounts/migrations/0003` 之后）
- `.venv/Scripts/python.exe manage.py test orders` — expected: 既有 46 例 + 新增联系方式用例全 OK
- `.venv/Scripts/python.exe manage.py test` — expected: 全量（基线 270 例）无回归
- `git grep -nE "student_id|VerificationRequest" -- templates/orders/` — expected: 无输出
- `git diff --stat 9e1ec658b34bbe18dc5394eda40fea500967a7b5 -- orders/models.py orders/migrations/ orders/views.py accounts/admin.py accounts/forms.py templates/listings/` — expected: 空

**Manual checks (if no CLI):**
- 以 buyer 打开待支付订单 `/orders/<id>/`：无联系方式区块、无认证徽章，只有「模拟支付」按钮 → 点击 → 详情页出现 QQ/微信值与认证徽章，刷新后保持 → 用另一账号访问同一 URL 得 404，匿名访问 302 到登录页 → 打开商品详情页与订单确认页，任何状态下都不出现 `QQ` / `微信` 字样或学号。
