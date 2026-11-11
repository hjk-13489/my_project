---
title: '查看我的发布'
type: 'feature'
created: '2026-11-11'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 79107cb580469243c5fa772627039889673d19b2
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 2.1–2.3 已让商品以 `pending / approved / rejected / offline` 四种状态落库、可被驳回并经「我的消息」重提，但卖家没有任何一处能查看「自己发过什么、每件处于什么状态」；个人中心「我的发布」仍是 Story 1.5 方案 A 的恒真空状态（`accounts/views.py:140` 的 `my_listings_empty=True`，`templates/accounts/profile.html:61-65` 的 else 分支不可达）。FR-8、`stories.md:98-104` 的验收因此断在占位上，D-031 遗留的重复 `pending` 数据也无从辨认，2.3 的驳回→重提闭环在卖家侧缺少可回看的数据面。

**Approach:** 把「我的发布」接成卖家本人的**只读数据面**：服务端按 `owner=request.user` 从 `Product.objects` **基础查询集**（不经过 `visible()`）取回本人全部商品，四态均用 `get_status_display()` 呈现中文状态；新增独立页 `/listings/mine/`，并把个人中心「我的发布」卡片由恒真空状态改为本人商品摘要 + 「查看全部」入口；仅对已驳回商品复用既有 `resubmit` 路由给「修改并重新提交」链接。不新增模型、迁移、删除或任何写路径，保持 2.5–2.8 与 5.1 的既有边界。

**Decision（人类决策，2026-11-11）:** ① Q1=A：新增独立页 `/listings/mine/`（`name='my_listings'`）与 `templates/listings/my_listings.html`，个人中心「我的发布」卡片同时渲染本人商品摘要（标题 + 中文状态）与跳转该页的「查看全部」入口；不加导航项、不动 `config/urls.py`。② Q2=A：四态 `pending / approved / rejected / offline` 全部展示，以 `get_status_display()` 取 `待审核 / 已上架 / 已驳回 / 已下架`；接受与 FR-8 / `epics.md:286` 字面三态的差异，依据是 `stories.md:103` 的四态断言与 2.3 已落地的 `rejected` 数据面——驳回商品不得从卖家视野消失。③ Q3=A：单列表按创建时间倒序（沿用 `Product.Meta.ordering`），每条含标题 / 价格 / 成色 / 状态 badge / 创建时间；不含缩略图、状态分组、筛选、分页。④ Q4=A：纯只读 + 仅 `rejected` 商品给「修改并重新提交」链接（复用 `{% url 'resubmit' product.pk %}`）；**不实现删除能力**，D-031 的重复 `pending` 数据清理仍留待 5.1。⑤ 规格体量：按 `cl100k_base` 统计 6,327 tokens（按此前 BMAD 会话口径折算约 2,700），**保留完整规格、不拆分、不新增 deferred 项**，context-rot 风险由 Step 4 三层审查兜底（沿用 D-029 / D-033）。以上五项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 独立页放 `listings/mine/`（name=`my_listings`），模板 `templates/listings/my_listings.html` 继承 `templates/base.html` 的 `title` / `content`；个人中心「我的发布」卡片提供「查看全部」链接指向该页，并在有数据时至少呈现本人商品标题与中文状态。
- 仅登录可访问；读操作不要求 `is_verified`（沿用 2.3「我的消息」的读门控），但未登录不得渲染任何商品信息，未登录访问新视图 302 到 `/login/?next=...`；非 GET/HEAD 返回 405 且无写入。
- 所有商品查询在服务端按 `owner=request.user` 过滤（AD-4 / NFR-2），页面不得出现他人标题、价格、状态或时间；禁止前端隐藏式伪权限。
- 卖家本人视图使用 `Product.objects` 基础查询集，**不得**调用 `visible()`、不得另写 `status='approved'` 查询；`visible()`（`listings/models.py:12-14`）一字不改，仍是对外可见性唯一门控。
- 四态全部可展示；状态一律由 `Product.STATUS_CHOICES` / `get_status_display()` 渲染中文名；不在模板 / 视图硬编码中文状态映射，不写 `product.status = ...` 赋值，`status` 绝不接受请求传值（只读比较 `product.status == 'rejected'` 用于渲染重提链接是允许的，与 `RejectionNotice.can_resubmit` 既有做法一致）。
- 列表按创建时间倒序，每条含标题 / 价格 / 成色 / 中文状态 badge / 创建时间；「修改并重新提交」链接**仅**出现在 `rejected` 商品上，且复用既有 `resubmit` 路由，不新建 URL / 视图。
- 全中文用户可见文案（`LANGUAGE_CODE='en-us'` 不自译）；Bootstrap 5.3 + Django 模板服务端渲染，不引入新依赖。
- 既有 123 个用例一字不改且全绿，尤其 `accounts/tests.py:643-654` 的四板块空状态断言——本人无商品时「我的发布」卡片与独立页必须仍显示「暂无发布记录，你还没有发布任何商品」类中文空状态。
- `profile_view` 的 `@login_required` / `@require_safe` 与其余三个板块上下文（`my_orders_empty`、`my_messages` / `my_messages_empty`、`my_reviews_empty`）保持不变；只把 `my_listings_empty` 由恒 `True` 改为按真实数据求值，并追加本人商品摘要上下文。
- 不产生任何迁移、不改模型 / 表单 / admin / `config/urls.py` / `config/settings.py` / `requirements.txt` / 既有迁移；不往运行时 `db.sqlite3` / `media/` 造演示数据。
- 新路由追加在 `listings/urls.py`，不设 `app_name`；`config/urls.py` 的 `listings/` include 与 DEBUG `static()` 一字不改；不加 `templates/base.html` 导航项。

**Never:**
- 不实现 2.5–2.8（列表浏览 / 搜索 / 筛选 / 详情）、5.1 / 5.2（审核区 / 下架）、Epic 3 聊天与 FR-16 未读提示、Epic 4 订单、个人中心「我的订单 / 我的评价」真实数据。
- 不改 `ProductQuerySet.visible()`、`STATUS_CHOICES`、`ALLOWED_TRANSITIONS`、`_transition()`、`RejectionNotice.can_resubmit`、`ProductImage`、`ProductForm` / `validate_images`、`publish_view` / `resubmit_view`、`listings/admin.py`。
- **不新增任何写路径**：不实现删除商品、不改状态、不改字段、不加 POST 表单或管理动作；页面与卡片全部只读（重提链接只跳到既有的 `resubmit` 视图，不在 2.4 内写入）。
- 不新增商品详情 URL / 模板、不改 `templates/base.html` 导航结构（既有测试硬断言）、不改 `accounts` 模型层；不展示缩略图、不做状态分组 / 筛选 / 分页。
- 不引入 DRF / API / SPA / WebSocket / 新第三方依赖；不做任何跨用户可猜测的商品主键入口；不把他人商品以「隐藏」「占位」形式带进模板上下文。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 本人无商品（独立页） | 已登录、无 `Product` | 200 + 中文空状态「暂无发布记录」 | 空状态分支 |
| 本人无商品（个人中心） | 同上 | 卡片仍显示「暂无发布记录，你还没有发布任何商品」，四板块空状态断言不破 | 空状态分支 |
| 四态全展示 | 本人 `pending / approved / rejected / offline` 各至少 1 件 | 独立页单列表按 `-created_at` 倒序，逐条显示标题 / 价格 / 成色 / `get_status_display()` 中文状态 / 时间 | N/A |
| 状态值合法性 | 任一展示商品 | `product.status in {'pending','approved','offline','rejected'}`（`stories.md:103`） | N/A |
| 已驳回项入口 | 本人 `rejected` 商品 | 该条出现「修改并重新提交」链接，`href` 指向既有 `/listings/<pk>/resubmit/`；其余三态不出现该链接 | N/A |
| 个人中心摘要 | 本人有商品 | 「我的发布」卡片出现本人商品标题、中文状态与「查看全部」链接 | N/A |
| 他人数据隔离 | 库中另有他人商品（含不同状态） | 独立页与卡片均不出现他人标题 / 价格 / 状态 / 时间；服务端 queryset 仅 `owner=request.user` | 按 owner 过滤 |
| 未登录 | 匿名访问独立页 | 302 到登录页并带 `next` | N/A |
| 只读方法 | 已登录 POST / PUT / DELETE 独立页 | 405（Allow: GET, HEAD），无任何写入 | `require_safe` |
| 已认证与未认证 | 已登录但 `is_verified=False` | 与已认证用户同规则渲染本人数据（其无法发布，通常为空状态） | N/A |
| 个人中心回归 | 62 个 accounts + 61 个 listings 既有用例 | 123 例全绿，四板块空状态断言不变 | N/A |

</frozen-after-approval>

## Code Map

- `listings/models.py:12-14,31-36,57-69` — `ProductQuerySet.visible()`（`filter(status='approved')`，对外唯一门控，**不改**）；`STATUS_CHOICES` 四值中文显示名（待审核 / 已上架 / 已驳回 / 已下架）；`status` 字段与 `Meta.ordering=('-created_at',)`。2.4 用 `get_status_display()` 与默认排序，不新增模型方法、不改状态机。
- `listings/models.py:64` — `objects = ProductQuerySet.as_manager()`：基础查询集**不过滤**，是「我的发布」能查到 `pending / rejected / offline` 的前提（spec-2-3:165 明确该前提留给 2.4）。禁止改用 `visible()`。
- `listings/models.py:110-127,130-162` — `ProductImage`（`related_name='images'`）与 `RejectionNotice.can_resubmit`（只读属性，`product.status == 'rejected'`）：本次**不展示缩略图**，重提链接用同样的只读状态比较判断，不改模型层。
- `listings/views.py:12-43,48-98` — `publish_view` / `resubmit_view` 的装饰器与编排范式（`@login_required` 外层 + `require_http_methods` 内层；越权统一 404；`transaction.atomic()`）。新增 `my_listings_view` 只读，参照 `accounts/views.py:123-125` 的 `@login_required + @require_safe`；不要复制写入逻辑，两个既有视图一字不改。
- `listings/urls.py:4-7` / `config/urls.py:29-39` — 现有 `publish/` 与 `<int:pk>/resubmit/` 两条路由；新增 `path('mine/', views.my_listings_view, name='my_listings')` 追加在 `listings/urls.py`（注意放在 `<int:pk>/resubmit/` 之后或之前均可，但不得让 `mine/` 被 `<int:pk>` 捕获）；`config/urls.py` 的 include（L34）、注释（L33）、DEBUG `static()`（L38-39，被 `listings/tests.py:305` 硬断言）均不改；不设 `app_name`。
- `accounts/views.py:123-145` — `profile_view`：`@login_required` + `@require_safe`，`my_listings_empty=True`（L140）是唯一需要替换的恒真标志；`my_messages` 查询范式（L130-134，`filter(owner).select_related(...).order_by(...)`）可复用——本人商品摘要同样按 `owner=profile_user` 从 `Product.objects` 基础集取；其余三个空状态标志与 `verification_requests` 上下文保持不变。跨 app 只读 import `Product` 沿用 2.3 的 `RejectionNotice` 先例（`accounts/views.py:9`）。
- `templates/accounts/profile.html:56-68` — 「我的发布」卡片（`my_listings_empty` 空状态 L61-62、else 占位注释 L64）：接入本人商品摘要（标题 + 中文状态 badge）与 `{% url 'my_listings' %}` 的「查看全部」链接，保留中文空状态文案（被 `accounts/tests.py:651` 硬断言）；`:83-110` 「我的消息」卡片的 `list-group` / `badge` / `can_resubmit` + `{% url 'resubmit' pk %}` 是渲染范式；其余三板块 L70-123 不动。
- `templates/listings/resubmit.html:1-117` / `publish.html:1-103` — 三分支模板、`card` / `badge` / `text-muted` 空状态、`d-grid` 按钮风格、返回个人中心链接范式；新模板 `templates/listings/my_listings.html` 继承 `templates/base.html` 的 `title` / `content` block（`:6,34`），Bootstrap 5.3 CDN，用 `list-group` 单列表、不用 `<table>`（spec-2-3:77）。
- `templates/base.html:10-31` — 已登录导航含「个人中心」「发布商品」与认证徽标 / 退出表单，被 `accounts/tests.py:677-688,690-703` 硬断言；**不加新导航项**，新页面入口从个人中心卡片进入。
- `listings/tests.py` — 3 个测试类（L30 / L379 / L554）共 61 例，`_make_image` L21、`_TEST_MEDIA_ROOT` L18 + `@override_settings` 夹具；新增测试类追加在文件末尾，勿改既有用例。`accounts/tests.py:544-728` 的 `ProfileViewTests` 15 例（含四板块空状态 L643-654）必须保持全绿。
- `listings/admin.py:5-6` / `listings/migrations/0001_initial.py` / `0002_rejectionnotice.py` / `listings/forms.py` / `config/settings.py:112,137,140` / `requirements.txt` — 全部不改；`makemigrations --check --dry-run` 必须仍为 `No changes detected`。
- `_bmad-output/planning-artifacts/stories.md:98-104` — 2.4 用户故事 / AC / 四态测试断言 / AD-9、AD-4、FR-8 依赖；`epics.md:276-288`（FR-8 三态 AC，本次由冻结决策 ② 覆盖为四态）、`prd.md:157-162`（FR-8）、`:120-125`（FR-4）、`:356-360`（NFR-2）；`epic-2-context.md:27,47,51-53` — 「按状态展示本人各商品，仅本人数据」「个人中心入口由 accounts 提供」「本史诗只消费 status」。
- `decision-log.md:322-330`（D-028 否决跳到未实现的「我的发布」）、`:355-363`（D-031 重复 `pending` 数据待 2.4 / 5.1 提供删除能力，本次冻结决策 ④ 明确**不做删除**，仍留待 5.1）、`:333-341 / :377-385`（D-029 / D-033 超长规格保留完整）、`spec-2-3:76,112,165-170`（profile 卡片是共享表面、基础查询集留给 2.4、返回 profile 的链接范式）。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:51` — `2-4-查看我的发布: backlog`，收尾时同步为 `review`。
- `.venv/Scripts/python.exe` — Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0；系统 PATH 的 `python` 无 Django，验证一律用该解释器。

## Tasks & Acceptance

**Execution:**
- [x] `listings/views.py` — 新增 `my_listings_view`（`@login_required` + `@require_safe`），按 `owner=request.user` 从 `Product.objects` 基础查询集取回本人全部商品（沿用默认 `-created_at` 排序）并构造上下文；不调用 `visible()`、不写任何状态 — 兑现 FR-8 的服务端数据面。
- [x] `listings/urls.py` — 追加 `path('mine/', views.my_listings_view, name='my_listings')`，`config/urls.py` 不动 — 兑现独立页入口（Q1=A）。
- [x] `templates/listings/my_listings.html` — 继承 `base.html`，单列表按时间倒序渲染标题 / 价格 / 成色 / `get_status_display()` 状态 badge / 创建时间；仅 `rejected` 项渲染「修改并重新提交」链接（`{% url 'resubmit' product.pk %}`）；无数据显示中文空状态 — 兑现四态视图与重提入口（Q2/Q3/Q4=A）。
- [x] `accounts/views.py` — 把 `my_listings_empty` 由恒 `True` 改为按本人商品求值，并追加本人商品摘要上下文（同样按 `owner=profile_user` 过滤）；其余上下文与两个装饰器不变 — 兑现 FR-4 个人中心入口。
- [x] `templates/accounts/profile.html` — 「我的发布」卡片渲染本人商品标题 + 中文状态与「查看全部」链接（`{% url 'my_listings' %}`），保留「暂无发布记录，你还没有发布任何商品」中文空状态，其余三板块一字不改 — 兑现 Epic 2 与 `accounts` 的衔接。
- [x] `listings/tests.py` — 末尾追加新测试类（自包含夹具），覆盖矩阵各行：两处空状态、四态全展示与 `get_status_display()`、`status ∈` 四态断言、倒序、仅 `rejected` 出现重提链接及其 `href`、个人中心摘要与「查看全部」链接、他人数据隔离（含 `response.context` owner 断言）、未登录 302+next、只读 405 且无写入、未认证用户可读、123 例全量回归；既有 61 例一字不改 — 冻结验收的可执行证据。
- [x] `spec-2-4-查看我的发布.md` 与 `sprint-status.yaml` — 状态同步（`2-4-查看我的发布`） — 工作流收尾。

**Acceptance Criteria:**
- Given 已登录卖家本人存在 `pending / approved / rejected / offline` 四态商品，When 访问独立页与个人中心卡片，Then 两者均显示 `get_status_display()` 中文状态、只含本人数据（`owner=request.user`，AD-4 / FR-8），独立页按创建时间倒序且 `status in {'pending','approved','offline','rejected'}`。
- Given 本人 `rejected` 商品，When 查看独立页，Then 该条有指向既有 `resubmit` 路由的「修改并重新提交」链接，其余三态没有；且 2.4 自身不产生任何写操作。
- Given 库中存在他人商品，When 卖家访问独立页或个人中心，Then 页面不泄露他人任何字段，服务端 queryset 按 owner 过滤而非前端隐藏。
- Given 本人无商品，When 访问独立页与个人中心，Then 保留中文空状态，且既有 123 个用例全部通过。
- Given 未登录或非 GET/HEAD 请求，When 访问独立页，Then 分别 302 带 `next` / 405，且不产生任何 DB 写入。
- Given 交付范围，When 查看 diff 并跑校验，Then 不含删除能力、2.5–2.8 / 5.1 / 5.2 / Epic 3 / Epic 4 内容；`visible()`、模型层、表单、admin、`config/urls.py`、`settings.py`、`requirements.txt`、`base.html` 与既有迁移均无改动；`manage.py check` 0 issues、`makemigrations --check --dry-run` 为 `No changes detected`。

## Implementation Notes

- 实现按冻结意图完成，改动文件：`listings/views.py`、`listings/urls.py`、`templates/listings/my_listings.html`（新增）、`accounts/views.py`、`templates/accounts/profile.html`、`listings/tests.py`（仅末尾追加，既有 61 例一字未改）、本规格与 `sprint-status.yaml`。`listings/models.py`（含 `visible()` / `STATUS_CHOICES` / `Meta.ordering` / `objects`）、`listings/admin.py`、`listings/forms.py`、`listings/migrations/`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`templates/base.html`、`accounts/tests.py` 均无改动；未产生迁移，未往运行时 `db.sqlite3` / `media/` 造数据。
- `listings/views.py`：新增 `my_listings_view`，`@login_required` 外层 + `@require_safe` 内层；`Product.objects.filter(owner=request.user)` 走基础查询集（不经 `visible()`、不写 `status='approved'`），转 list 后按 `Product.Meta.ordering('-created_at')` 倒序，构造 `my_listings` / `my_listings_empty` 上下文；只读、不改状态、不接受请求传值。`listings/urls.py` 追加 `path('mine/', ..., name='my_listings')`，`config/urls.py` 未动，未设 `app_name`。
- `templates/listings/my_listings.html`：继承 `base.html` 的 `title` / `content`，`list-group` 单列表渲染标题 / 价格 / 成色（`get_condition_display()`）/ `get_status_display()` 状态 badge / 创建时间；仅 `{% if product.status == 'rejected' %}` 时给 `{% url 'resubmit' product.pk %}` 的「修改并重新提交」链接；空数据显示「暂无发布记录，你还没有发布任何商品」；末尾「返回个人中心」链接。无缩略图 / 分组 / 筛选 / 分页 / 写表单。
- `accounts/views.py`：`profile_view` 两个装饰器与 `my_orders_empty` / `my_messages` / `my_messages_empty` / `my_reviews_empty` / `verification_requests` 上下文保持不变；`my_listings_empty` 由恒 `True` 改为 `not my_listings`，新增 `my_listings = list(Product.objects.filter(owner=profile_user))`（同样基础查询集、服务端过滤）。跨 app 只读 import 沿用 2.3 的 `RejectionNotice` 先例，合并为 `from listings.models import Product, RejectionNotice`。
- `templates/accounts/profile.html`：「我的发布」卡片非空时渲染本人商品标题 + `get_status_display()` 中文状态徽标，并始终给出 `{% url 'my_listings' %}` 的「查看全部」入口；保留原中文空状态文案；其余三板块一字未改。新入口使用 `btn btn-outline-secondary btn-sm`，避开既有 `accounts/tests.py` 对 `btn btn-outline-primary btn-sm` 的 `assertNotContains` 断言；未新增 `base.html` 导航项。
- `listings/tests.py` 末尾追加自包含 `MyListingsViewTests`（13 例）：独立页 / 个人中心两处空状态与四板块回归、四态中文展示与字段、`status ∈` 四态且显示名来自 `STATUS_CHOICES`、按 `-created_at` 倒序（context 与 HTML 双重断言）、仅 `rejected` 出现重提链接及其 `href`、个人中心摘要与「查看全部」、他人数据隔离（含 `response.context` owner 断言）、未登录 302+`next`（GET / POST）、只读方法 405（`Allow: GET, HEAD`）且无写入、两页 GET 无写入、未认证用户可读。
- 验证（`.venv/Scripts/python.exe`，Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0）：`manage.py check` → `System check identified no issues (0 silenced)`；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 2` → **136 tests OK**（既有 123 + 新增 13，0 失败 / 跳过），13 个新用例单独复跑亦全绿；`git diff -- listings/models.py listings/admin.py listings/forms.py config/urls.py config/settings.py requirements.txt templates/base.html listings/migrations/` 为空；`git diff -- accounts/tests.py` 为空，`listings/tests.py` 为 259 行纯追加（0 删除）；全仓 `status='approved'` 查询字面量仍只在 `listings/models.py:14` 的 `visible()`。
- 状态同步：`sprint-status.yaml` 的 `2-4-查看我的发布` 由 `in-progress` 置 `review`（实现完成、待独立代码审查），本规格 frontmatter `status` 同步置 `review`；`done` 留待后续独立代码审查收尾写入（沿用 spec-2-3 的 Step 5 惯例）。`review_loop_iteration` 保持 0，Review Triage Log 待首轮审查填写。
- 已知取舍（交付范围外）：D-031 的重复 `pending` 数据仍无删除能力（冻结决策 ④，留待 5.1）；个人中心「查看全部」入口在空状态时也渲染，点击后独立页同样显示中文空状态，不泄露任何商品信息。
- 状态更正与主代理 Step 3 复核：实现子代理越权把本规格 frontmatter 置为**未识别状态** `review`（模板识别值仅 `draft / ready-for-dev / in-progress / in-review / done`），并把 `sprint-status.yaml` 的 `2-4` 提前置 `review`，**均已撤回**——Step 3 期间二者应保持 `in-progress`，`in-review` / `review` 属 Step 4 / Step 5 收尾终态（与 spec-2-3:116、:121 同类更正一致）。上一条「状态同步」记述的是被撤回的中间态，以本条为最终口径；`last_updated` 同步为 `11-11-2026 17:10`。
- 主代理独立验收（不依赖实现子代理报告）：把 `79107cb..工作树` 的完整统一 diff（含 3 个未跟踪文件，48,795 B / 597 行）读入上下文逐行核对，7 项任务与 6 条 AC 均满足，冻结区未被修改；独立复跑 `.venv/Scripts/python.exe` 得 `check` → 0 issues、`makemigrations --check --dry-run` → `No changes detected`、`test -v 2` → **136 tests OK**（既有 123 + 新增 13，0 失败 / 跳过），13 个 `MyListingsViewTests` 用例在 `-v 2` 输出中逐条 `... ok`，无跳过 / 未注册；矩阵 11 行均有对应且已运行通过的覆盖用例。

## Spec Change Log

## Review Triage Log

> 2026-11-11 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `79107cb..工作树`，diff 50,001 B / 599 行（含 3 个未跟踪文件）。无跳过层；Blind Hunter 自算 `kB=48.83 → N=7`（按 1000 B/kB 为 8），实报 14 条；Edge Case Hunter 3 条；Verification Gap 0 条（明确返回 `No verification gaps found.`，其实跑 136 用例 + 13 个新用例 `-v 2`，无发现故不产生行）。共 17 条原始发现，逐条核验后 **17 条驳回（14 `false`、3 `low → rejected`）**，0 `high` / `medium`、0 `intent_gap` / `bad_spec` / `patch` / `defer`、无 loopback，`review_loop_iteration` 保持 0 → Clean review。

**Rejected**

- BH-1 `false` — 「规格 `in-review` 与 sprint `in-progress`、记忆日志 `draft` 三者状态自相矛盾」：step-04 L11 明确要求进入审查前把规格置 `in-review`，sync-sprint-status 只把 sprint 置 `in-progress`，Step 5 才统一；`.workbuddy/memory/2026-11-11.md` 记录的是当时时点快照。与 spec-2-3 BH-2 同类阶段差，且修复=编辑本规格 / 记忆文件 → 驳回。
- BH-2 `false` — 「冻结决策 ⑤ 用草稿期 6,327 tokens 论证、与决策后 7,051 不符」：6,327 是人类拍板时点的草稿计数，7,051 是决策写入后的复核值，已在 CHECKPOINT 1 与记忆日志向人类明示；`<frozen-after-approval>` 按定义不可改，且 token 数不影响任何功能。修复=编辑本规格 → 驳回。
- BH-3 `false` — 「`## Spec Change Log` 空节像漏写」：模板明写「Empty until the first bad_spec loopback」；本轮无 `bad_spec`、无 loopback，空节是正确状态。修复=编辑本规格 → 驳回（与 spec-2-3 BH-1 一致）。
- BH-4 `false` — 「Implementation Notes 提到 `last_updated` 但 frontmatter 无该字段」：模板 frontmatter 本就无 `last_updated`；该句指的是 `sprint-status.yaml:32`，现值 `11-11-2026 17:10` 已核对。修复=编辑本规格 → 驳回（与 spec-2-3 BH-3 一致）。
- BH-5 `false` — 「`Product.Meta.ordering('-created_at')` 不可调用、两处查询无显式 `order_by`，日后改 Meta 会静默破坏」：冻结决策 ③ 明文「单列表按创建时间倒序（沿用 `Product.Meta.ordering`）」，依赖模型默认排序正是既定实现；`listings/models.py:69` 现为 `('-created_at',)`，`test_list_ordered_by_created_at_desc` 对 context 与 HTML 双重断言倒序通过。括号写法是 Implementation Notes 的措辞不严谨，不是代码缺陷；补 `order_by` 不改变任何当前行为，且修复=编辑本规格或加冗余代码 → 驳回。
- BH-6 `false` — 「`accounts/views.py` 注释仍叫人以 `filter(owner=profile_user)` 替换、与 2.4 已实现代码冲突」：该注释在本次已收窄为「订单 / 评价两板块暂无业务数据」，其 `filter(buyer/owner=...)` 指向 Epic 3/4 对那两个仍空板块的未来替换；2.4 的 `my_listings` 查询在 `accounts/views.py:208` 有独立注释，不存在误导后来者重复实现的路径。
- BH-7 `false` — 「规格写 `owner=request.user`，实现用 `owner=profile_user`，且无用例断言二者一致」：`accounts/views.py:127` 是直接赋值 `profile_user = request.user`，二者恒等；`test_other_user_data_isolation`（diff L434-436）与 `test_profile_card_shows_summary_and_view_all_link`（L409-411）已断言 `response.context['my_listings']` 每项 `owner_id == 登录用户.pk`，绑定关系有可执行证据。
- BH-8 `false` — 「独立页用 `product.status == 'rejected'`、我的消息用 `RejectionNotice.can_resubmit`，两页判据可能不一致」：`listings/models.py:160-162` 的 `can_resubmit` 定义就是 `self.product.status == 'rejected'`，与 `my_listings.html:582` 完全同一谓词；冻结决策 ④ 已指定 `rejected` 为准。不存在「一页给链接、一页不给」的可达状态；补冻结决策=编辑本规格 → 驳回。
- BH-9 `false` — 「只断言 `href`、没有 `follow=True` 端到端跳转验证」：`self.url = reverse('my_listings')`，路由或视图缺失会让 `reverse()` 直接抛 `NoReverseMatch`；独立页 GET 200 + 模板已由 5 个新用例覆盖，`resubmit` 视图由 2.3 的 21 个既有用例覆盖。链接目标可达性由组合证据成立，声称的坏结果不会发生。
- BH-10 `false` — 「I/O 矩阵缺『匿名 + 非安全方法』行」：矩阵「未登录」行已覆盖匿名 GET 302；匿名 POST 由 `@login_required` 置于 `@require_safe` 外层的优先级保证，且 `test_unauthenticated_post_also_redirects` 已通过。补矩阵行/AC = 编辑本规格 → 驳回（与 spec-2-3 BH-5 一致）。
- BH-11 `low` → rejected — 「四态徽标一律 `bg-secondary`，视觉上无法区分」：冻结决策 ②/③ 要求的是中文状态名，`test_four_statuses_show_chinese_display_and_fields` 已逐条断言「待审核 / 已上架 / 已驳回 / 已下架」，用户可区分；颜色差异化属新增 UI 设计、需模板分支与可断言标记，不在冻结意图内且日常使用不会遇到该缺陷 → 按 `low` 驳回。
- BH-12 `low` → rejected — 「`assertNotContains('<img')` 过宽、且缺标题 HTML 转义用例」：Django 模板默认自动转义，`{{ product.title }}` 不会输出 `<script>` / `<img` 标签，声称的 XSS 结果不存在；当前 `base.html` 确无 `<img`，该断言成立，未来 logo 导致的误报只是测试维护问题。收紧选择器 / 补转义用例属新增测试复杂度 → 按 `low` 驳回。
- BH-13 `false` — 「时间断言依赖时区巧合」：`config/settings.py:114` `TIME_ZONE="UTC"`、`:118` `USE_TZ=True`，`created_at` 与模板 `|date:'Y-m-d H:i'` 同为 UTC，`strftime` 断言与渲染一致（136 用例中该断言已通过）。「改时区」这一假设路径未被展示，当前不存在坏结果。
- BH-14 `false` — 「新测试的 import 放在第 877 行之后、与顶部重复」：模块级 import 置于类定义之后是合法 Python，13 个用例在 `-v 2` 输出中全部被发现且逐条 `... ok`；「末尾自包含追加、既有 61 例一字不改」是冻结任务约束，合并到顶部反而改动既有内容。无运行期坏结果。
- EC-1 `low` → rejected — 「两件商品 `created_at` 相同时顺序不确定」：冻结决策 ③ 只要求「按创建时间倒序」，同时间戳的次序本就未定义；SQLite 对相同排序键按 rowid 稳定返回，`test_list_ordered_by_created_at_desc` 用四个互异时间戳证明倒序。补 `.order_by('-created_at','-pk')` 属新增排序守卫、无用户可见收益 → 按 `low` 驳回。
- EC-2 `false` — 「`status` / `condition` 越界时显示原始值或空白徽标」：2.4 不创建商品，所有写路径都经表单校验与模型层状态机，越界值无可达生产路径；`STATUS_CHOICES` 四值的中文显示名已由 `test_status_values_are_legal_and_display_from_choices` 断言。补 `default:'未知状态'` 需模板新分支，且与冻结区「状态文案唯一来源」冲突。
- EC-3 `false` — 「spec `in-review` 与 sprint `2-4=in-progress` 不一致（claim, confidence low）」：与 BH-1 同根因，是 step-04 L11 与 Step 3 状态同步的阶段差，Step 5 才统一；该层未给出任何坏结果证据，且修复=编辑本规格 → 驳回。

**分组与处置：** 无存活项，不产生分组；无 `intent_gap` / `bad_spec` 故不触发 loopback，`review_loop_iteration` 保持 0；无 `patch` 故不重派实现子代理；无 `defer` 故不改 `deferred-work.md`。Verification Gap 层的「无发现」结论与主代理独立复跑（`check` 0 issues、`makemigrations --check` No changes、`test -v 2` 136 tests OK、13 个新用例逐条 `... ok`）一致。

## Design Notes

- **Step 2 事实与路径判定**：Intent gaps 原为 4 项，已由人类于 2026-11-11 全部拍板（冻结区 Decision ①–④），规格体量按决策 ⑤ 保留完整、不拆分；Irreversibles = **无**（无迁移、无 schema 变更、无数据删除 / 写入、无外部副作用；决策 ④ 明确排除删除，故也不引入运行时的不可逆操作）；Footprint ≈ 6 个文件，新增 1 个 URL / 1 个模板 / 1 个视图，`profile_view` 上下文与 `profile.html` 卡片是 Epic 3/4 也要依赖的共享表面。故 `route: dispatch`、写完整规格，不走 oneshot（与 spec-2-3:163 一致）。
- **基础集而非 `visible()`**：`visible()` 是 2.5–2.8 与 5.1 共用的唯一 approved 门控；卖家本人必须看到未上架商品，2.2 / 2.3 已明确把基础查询集留给 2.4（spec-2-3:165）。本次任何新增查询都不得另写 `status='approved'` 字面量。
- **状态文案唯一来源**：`STATUS_CHOICES` 已有 `待审核 / 已上架 / 已驳回 / 已下架` 四个中文显示名，模板用 `get_status_display()`；不在视图 / 模板另建映射，避免与 `accounts/views.py` 的认证状态 `get_status_display()` 范式分叉。只读比较 `product.status == 'rejected'` 只用于渲染既有重提链接，不构成赋值或第二套门控。
- **共享表面与回归**：`my_listings_empty` 是 Story 1.5 方案 A 留下的四个标志之一，2.3 已按同样方式替换 `my_messages_empty`（spec-2-3:112,170）；本次照此最小改动，且必须保留 `accounts/tests.py:651` 断言的「暂无发布记录」文案。不新增导航项，避免破坏 `ProfileViewTests` 的导航硬断言。
- **只读边界**：本故事不改任何模型、不引入删除，因此不应产生迁移；`makemigrations --check --dry-run` 是「无 schema 变更」的机械证据。D-031 的重复 `pending` 清理不在本次范围，5.1 落地时再评估。
- **演示数据**：沿用 2.1–2.3 惯例，不往运行时 `db.sqlite3` / `media/` 造数；所有状态（尤其 `rejected` / `offline`）由测试用例在内存测试库构造后断言，等价覆盖 AC。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（本次不改模型）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 123 例 + 本故事新增用例全绿，无失败 / 跳过
- `git diff --name-status` 及 `git diff -- listings/models.py listings/admin.py listings/forms.py config/urls.py config/settings.py requirements.txt templates/base.html listings/migrations/` — expected: 上述文件 diff 为空，交付面与 AC-6 一致
- `git status --porcelain=v1` — expected: 仅含本故事交付文件与本规格 / sprint 状态文件

**Manual checks (if no CLI):**
- 以已认证卖家登录，依次构造 `pending / approved / rejected / offline` 四态本人商品与一条他人商品，打开个人中心与 `/listings/mine/`，核对中文状态、字段、倒序、仅 `rejected` 有重提链接与「仅本人数据」；退出登录后访问 `/listings/mine/` 应跳登录页。
