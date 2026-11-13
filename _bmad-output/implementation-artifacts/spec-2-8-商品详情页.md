---
title: '商品详情页'
type: 'feature'
created: '2026-11-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: dbc6e7ab3837045099108755e3040a6058053680
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 2.5–2.7 已交付公开列表页 `/listings/`（含关键词搜索与分类/价格/成色组合筛选），但 `listings/urls.py:5-8` 只有 4 条路由、`listings/views.py` 无详情视图、`templates/listings/` 无详情模板、`product_list.html:94-111` 卡片也没有任何指向详情的链接；`epics.md:333-347`、`prd.md:189-196`（FR-12）、`stories.md:131-139` 要求的「展示全部图片/描述/价格/成色/分类/卖家昵称 + 认证状态」「「联系卖家」「立即购买」入口」「待审核/驳回/下架商品详情页返回 404」均无实现，全仓 `product_detail` 零命中。Epic 2 买家链路（列表 → 搜索 → 筛选 → 详情）断在最后一环，详情页作为协商（Epic 3）与下单（Epic 4）的入口缺位。

**Approach:** 在 `listings` app 内新增语义路由 `/listings/<pk>/`（`name='product_detail'`）、一个公开只读视图与一个新模板 `templates/listings/product_detail.html`，复用 `Product.objects.visible()` 作为唯一可见性门控（非上架商品一律 `get_object_or_404` → 404），以 `select_related('owner')` / `prefetch_related('images')` 一次取回卖家与全部图片；页面用 Bootstrap 服务端渲染全部字段与图片、卖家昵称（`owner.username`）+ 认证徽标，并让「联系卖家」「立即购买」两个入口只就位、不跳转。不改模型 / 表单 / admin / 迁移 / 配置 / 共享模板，不实现 Epic 3 / 4 / 5 功能。

**Decision（人类决策，2026-11-13 12:28，全部按推荐 A）:** ① Q1=A：**两个操作入口只就位、不跳转** —— 渲染「联系卖家」「立即购买」两个全中文入口（`href="#"` / 纯展示），点击不导航到任何未实现页面；不新建 chat/orders/dashboard 路由、视图或占位页，不改 `config/urls.py`；2.8 的 AC 只验收「入口存在且可见」，FR-13 / FR-17 的实际跳转由 Epic 3 / 4 接入时替换 href，避免 `NoReverseMatch` 与 D-028 否决的死链。② Q2=A：**详情页公开只读 + 匿名登录引导** —— 不加 `@login_required`，匿名 / 已登录 / 卖家本人 / admin 均 200；两个入口仅对已登录用户呈现，匿名位置改为指向 `{% url 'login' %}` 的中文「登录后联系卖家 / 登录后购买」引导（不新增路由）；入口不触发写操作，故不构成 AD-4 所禁的前端隐藏式伪权限。③ Q3=A：**非上架商品对任何角色一律 404** —— 详情查询只经 `Product.objects.visible()`，卖家本人与 `role='admin'` 亦不放行；卖家状态查看走「我的发布」、管理员走 Django admin，不引入第二套门控或身份分支。④ Q4=A：**列表卡片纯追加「查看详情」链接** —— 仅在 `product_list.html` 卡片 `card-body` 内追加一个 `<a href="{% url 'product_detail' product.pk %}">查看详情</a>`，既有节点、文案、`<img count=1>`、空态链与 `{% if search_active %}` 块条件一字不改；`base.html` / `index.html` 零改动。⑤ 门槛 A：**保留完整规格**（起草时点 12,612 tokens / cl100k_base），接受 context-rot 风险，由 Step 4 三层审查兜底（沿用 2.5 决策 ⑥、D-029 / D-038）。

## Boundaries & Constraints

**Always:**
- **对外可见性唯一入口**是 `ProductQuerySet.visible()`（`listings/models.py:9-14`，`filter(status='approved')`）。详情查询必须写成 `get_object_or_404(Product.objects.visible(), pk=pk)`（或等价的链式 `visible()` 后的 `get_object_or_404`）；`pending / approved / rejected / offline` 四态中仅 `approved` 返回 200，其余三态与不存在的 `pk` 一律 404。全仓生产代码不得出现第二套 `status` 过滤字面量，视图 / 模板 / 测试不得另写门控（AD-9 `architecture.md:111-117`、D-034 `decision-log.md:388-396`、spec-2-5 L27、spec-2-6 L27、spec-2-7 L27/L163）。按 Decision ③，非上架商品**对任何角色一律 404**：卖家本人与 `role='admin'` 也不放行，视图不得新增身份分支或第二条查询路径。收尾时 `status='approved'` 字面量仍只在 `listings/models.py:14`。
- **路由**：在 `listings/urls.py` 新增 `path('<int:pk>/', views.product_detail_view, name='product_detail')`，`reverse('product_detail', args=[pk]) == '/listings/<pk>/'`；沿用 `spec-2-5-商品列表浏览-仅上架.md:22` 冻结决策 ①「2.8 详情沿 `/listings/<pk>/`」。`<int:pk>` 只匹配整数，不与既有 `publish/` / `mine/` / `<int:pk>/resubmit/` / `''` 冲突；不改 `listings/urls.py` 既有 4 条、`config/urls.py`（L31-34 的 `path("", ...)` 顺序注释仍成立）、不新增 `app_name`。既有 `reverse('product_list') == '/listings/'`（`listings/tests.py:1454`）不变。
- **公开只读（Decision ②）**：视图用 `@require_safe`（`listings/views.py:9` 已导入），**不加** `@login_required`、不要求 `is_verified`；匿名 / 已登录已认证 / 已登录未认证 / 卖家本人 / `role='admin'` 访问同一 `approved` 商品均 200 且看到同一份商品信息。两个操作入口仅对已登录用户呈现；匿名位置改为指向 `{% url 'login' %}` 的中文「登录后联系卖家 / 登录后购买」引导（不新增路由）。入口不触发任何写操作，故该呈现差异不构成 AD-4 所禁的「前端隐藏式伪权限」。非 GET/HEAD → 405（`Allow: GET, HEAD`），HEAD 200；任何请求不产生 DB / `media/` 写入、不改 `status`。
- **字段与图片**：展示 `title`、`description`、`¥{{ product.price }}`（`DecimalField(10,2)`）、`get_condition_display()` 中文成色、`category`、`created_at` 可省略但**全部图片**必须展示 —— 经 `product.images.all`（`ProductImage.product` 反向名 `images`，`listings/models.py:113-118`）遍历该商品 1–5 张图的 `<img src="{{ image.image.url }}">`，不得只取首图；0 图商品显示中文占位（不报错、不留空 `<img>`）。图片顺序按 `ProductImage` 默认主键升序即可。
- **卖家信息与隐私**：卖家昵称取 `{{ product.owner.username }}`（`accounts/models.py:13` 明注「username 复用为昵称」）；认证状态两态沿用 `templates/base.html:20,22` 的 Bootstrap 徽标与文案 `✓ 已认证` / `待认证`。**禁止** `{{ product.owner }}`（`User.__str__` 会输出 `学号 (昵称)`，违反 NFR-4 `prd.md:366-368`「学号不在公开页面展示」）；不展示 `student_id`、`VerificationRequest.name`、卖家 QQ/微信（FR-19 `prd.md:253-259`「下单前不展示」、NFR-4）。延续 `listings/tests.py:1444-1449` 的 `assertNotContains('QQ','微信')` 口径到详情页。
- **操作入口（Decision ①）**：详情页提供「联系卖家」「立即购买」两个全中文入口（`epics.md:344`、FR-12 `prd.md:191`），二者**只就位、不跳转**：渲染为 `href="#"` 的锚点或纯展示按钮，点击不导航到任何未实现页面；不新建 `chat` / `orders` / `dashboard` 的路由、视图或占位页，不改 `config/urls.py`。`chat/urls.py` / `orders/urls.py` / `dashboard/urls.py` 均为 0 字节且 `config/urls.py:29-35` 未 include，**严禁** `{% url %}` 或 `reverse()` 指向它们（`NoReverseMatch`），也严禁 hardcoded `/chat/…` / `/orders/…` 死链（D-028 `decision-log.md:322-330` 否决跳未实现页）。本故事 AC 只验收「入口存在且可见」，FR-13 / FR-17 的实际跳转由 Epic 3 / 4 接入时替换入口 href。
- **模板与渲染**：新增 `templates/listings/product_detail.html`（`{% extends 'base.html' %}`，`block title` / `block content`），Bootstrap 5.3.3 CDN（已在 `base.html:7,38`）、服务端渲染、全中文用户可见文案（`LANGUAGE_CODE='en-us'` 不自译）、仅桌面 Chrome/Edge；表单回显 / 商品字段一律交给 Django 模板自动转义，禁止 `|safe`、禁止未转义拼接、禁止原始 SQL。
- **共享表面零改动**：`templates/base.html` / `templates/index.html` **完全不动**，收尾时二者 diff 必须为空 —— `listings/tests.py:1462,1979,2714` 硬断言 `href="/listings/" count=2`，`accounts/tests.py:698,722` 硬断言 `✓ 已认证 count=2`（导航栏 + 个人中心卡片各一）、`:571-574` `待认证 count=2`、`:726` `去认证 count=1`，任何共享模板新增链接 / 徽标都会破坏这些断言。新增详情页链接用 `/listings/<pk>/`，不含 `href="/listings/"` 完整子串。
- **既有测试一字不改且全绿**：`listings/tests.py` 现有 140 例（7 类）+ `accounts/tests.py` 62 例 = **202 例**，`manage.py test -v 2` 全绿、0 失败 / 0 跳过；新测试类**追加在 `listings/tests.py` 末尾**，不修改任何既有行。
- **不改不动清单**：`listings/models.py`、`forms.py`、`admin.py`、`migrations/`、`config/settings.py`、`config/urls.py`、`requirements.txt`、`accounts/` 全部文件、`templates/listings/{publish,resubmit,my_listings}.html`、`templates/base.html`、`templates/index.html` 均无改动；不产生迁移（`makemigrations --check --dry-run` → `No changes detected`）、不引入新依赖 / 新配置 / 新静态资源 / 索引 / 缓存 / 分页 / API。
- **演示数据**：不往运行时 `db.sqlite3` / `media/` 造数；四态、0–5 图、认证两态、隐私、404、读写方法与组合访问全部由测试用例在测试库 + 独立临时 `MEDIA_ROOT`（沿用 `_STORY27_MEDIA_ROOT:2012` / `_story27_image:2015` 的 `tempfile.mkdtemp` 范式，新建 `_STORY28_*`）构造后断言。
- **NFR-1 沿用 2.5 决策 ④ 的可执行口径**（`spec-2-5-商品列表浏览-仅上架.md:22`、spec-2-6 L104、spec-2-7 L41/L167）：`CaptureQueriesContext` 证明查询数不随图片数 N 增长（`select_related('owner')` + `prefetch_related('images')` 消除 N+1），并以 `time.perf_counter` 断言单次 GET < 1s；不引入缓存 / 索引 / 分页。

**Never:**
- 不实现 2.8 以外任何故事：Epic 3 聊天（3.1–3.4）、Epic 4 下单 / 支付 / 订单（4.1–4.8）、Epic 5 审核区 / 下架 / 看板（5.1–5.5）；按 Decision ①，不新建 `chat` / `orders` / `dashboard` 的路由、视图、占位页或消息 / 订单实体，也不为两个入口生成任何可跳转目标。
- 不新增模型字段 / property / 方法 / 迁移、不改 `Product` 与 `ProductImage`、不改图片上传校验与存储路径；不新增写路径、不改 `status`、不写 `media/`。
- 不把 `pending / rejected / offline` 商品以任何形式（隐藏、占位、注释、上下文变量、404 页文案）带进模板或 context；不泄露其标题 / 描述 / 价格 / 图片 URL / 卖家信息。
- 不改 `base.html` / `index.html`；不新增导航项、不新增 `/listings/` 链接、不新增全局徽标。
- 不引入第二套可见性判断（视图里任何 `filter(status=...)` / `if product.status == ...` 都意味着重复门控）；不引入 SPA / API / WebSocket / 全文检索 / 高亮 / 轮播组件 / 灯箱 / 新静态资源 / 新第三方依赖。
- 不展示学号 / 真实姓名 / QQ / 微信；不使用 `{{ product.owner }}`；不输出未转义 HTML、不拼接原始 SQL。
- 不改 2.5–2.7 已冻结的列表页语义（搜索表单、`{% if search_active %}` 块条件、「清空搜索」「清空筛选」、卡片四要素、`<img count=1>`、空态文案）；`product_list.html` 除 Decision ④ 的「卡片内纯追加一个查看详情链接」外，既有节点一字不改，不把整张卡片包进 `<a>`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 上架单图详情 | `approved` 商品 + 1 张图 | 200，模板 `product_detail.html`，全部 6 类字段 + 1 个 `<img>` + 卖家昵称 + 对应认证徽标 + 两个操作入口 | `visible()` 命中 |
| 上架多图详情 | `approved` 商品 + 5 张图 | 5 个 `<img>`，URL 各不相同，顺序稳定；不得只显示首图 | `prefetch_related('images')` |
| 上架零图 | `approved` 商品 + 0 张图 | 200，中文占位且无空 `<img src="">`，其余字段照常 | 模板 `{% if %}` 空分支 |
| 四态门控 | `pending` / `rejected` / `offline` 各一件，带图带字段 | 三者详情页均 404；HTML 与 context 不含其标题 / 描述 / 价格 / 图片 URL / 卖家昵称 | `get_object_or_404(visible(), pk=...)` |
| 角色无关的 404 | 卖家本人 / `role='admin'` 访问自己的 `pending` 商品详情 | 仍 404，不因身份放行；视图无身份分支、无第二条查询路径 | Decision ③ / `visible()` 唯一门控 |
| 操作入口 | 已登录用户访问 `approved` 详情 | 页面含「联系卖家」「立即购买」两个中文入口，均不指向 chat/orders 路径、不产生导航；全仓无新增 chat/orders 路由 | Decision ① / `href="#"` |
| 匿名入口 | 匿名访问 `approved` 详情 | 200；不显示两个操作入口，改显示「登录后联系卖家 / 登录后购买」引导，指向 `{% url 'login' %}` | Decision ② |
| 混合态 | 库中同时有 `approved` 与三种非上架 | 仅 `approved` 的 pk 返回 200，其余 404；`visible().filter(pk=...).exists()` 与响应一致 | 服务端强制过滤 |
| 不存在 / 非法主键 | `pk=999999` / `/listings/abc/` / `/listings/-1/` | 不存在 → 404；非整数路径 → 404（路由不匹配），均不 500 | `get_object_or_404` / URL converter |
| 认证两态 | 卖家 `is_verified=True` / `False` | 分别显示 `✓ 已认证` / `待认证` 徽标；昵称取自 `owner.username` | 模板分支 |
| 隐私 | 卖家含学号 / 真实姓名 / QQ / 微信字样 | 详情页 HTML 不含卖家 `student_id`，不含 `QQ` / `微信` / `VerificationRequest.name`；`{{ owner }}` 未使用 | 字段白名单 |
| 转义 | `title` / `description` 含 `<script>alert(1)</script>` | HTML 中为转义形式，页面不执行脚本，`assertNotContains('<script>')` | 模板自动转义 |
| 访问门控 | 匿名 / 已登录已认证 / 已登录未认证 / 卖家本人 / admin GET | 均 200、同一份商品信息；已登录见两个操作入口，匿名见登录引导（Decision ②） | 无登录装饰器 |
| 只读方法 | POST / PUT / PATCH / DELETE 详情页 | 405（`Allow: GET, HEAD`），无任何 DB / `media/` 写入 | `require_safe` |
| HEAD | HEAD `/listings/<pk>/` | 200，无 body，无写入 | `require_safe` |
| 列表入口 | 列表 / 搜索 / 筛选态各一件命中商品 | 卡片内「查看详情」链接可进入对应详情页，`reverse('product_detail', args=[pk])` 命中 200；既有节点与 `<img count=1>` 不变 | Decision ④ / `{% url %}` 参数化 |
| 查询数 | 同一商品分别挂 1 张 / 5 张图 | `CaptureQueriesContext` 查询数相等（不随图片数增长） | `select_related` + `prefetch_related` |
| 响应时间 | 演示规模多图商品 | 单次 GET 耗时 < 1s（NFR-1 口径） | `time.perf_counter` 计时断言 |
| 共享表面回归 | 交付 diff | `base.html` / `index.html` diff 为空；首页仍 `href="/listings/" count=2`；`✓ 已认证 count=2` 等 accounts 断言不破 | 既有 202 例全绿 |
| 禁改回归 | 交付 diff | models / forms / admin / migrations / config / requirements / accounts / 既有 listing 模板均无改动 | `git diff --name-status` |
| 无迁移 | 交付校验 | `check` 0 issues、`makemigrations --check --dry-run` → `No changes detected` | CLI |

</frozen-after-approval>

## Code Map

- `listings/models.py` — `ProductQuerySet.visible():9-14` = `filter(status='approved')`，**对外可见性唯一定义、一字不改**，可传给 `get_object_or_404`；`Product:17` 字段 `owner:46-51`（FK `AUTH_USER_MODEL`, `related_name='products'`）/ `title:52` / `description:53` / `price:54`（DecimalField(10,2)）/ `condition:55` / `category:56`（存储值即中文词）/ `status:57-59` / `created_at:60`；`CATEGORY_CHOICES:20-25`、`CONDITION_CHOICES:26-30`、`STATUS_CHOICES:31-36`；`objects:64`、`Meta.ordering:69`；`ProductImage:110-120`，反向名 `images:116`，`image` 为 `ImageField(upload_to='products/')`。**无 `get_absolute_url()`**，详情页链接须显式 `{% url 'product_detail' product.pk %}`。
- `listings/views.py` — 导入 `get_object_or_404`, `render`:6、`require_safe`:9 已就位；既有视图 `publish_view:19`（`@login_required` + `@require_http_methods`）、`resubmit_view:55`（唯一 `get_object_or_404` 用法在 `:64`）、`my_listings_view:112`（`@login_required` + `@require_safe`，卖家侧 `filter(owner=...)` 范式**不得照抄**）、`product_list_view:149`（`@require_safe`、公开只读、`Product.objects.visible():173`、`prefetch_related('images'):192`、`render(...):199-213`）。新增 `product_detail_view` 追加在文件末尾或 `product_list_view` 之后，沿用 `@require_safe` 与 `render` 风格；不写 `status` 字面量、不消费 GET 参数、不做任何写入。
- `listings/urls.py:1-9` — 4 条路由，无 `app_name`；`publish/:5`、`<int:pk>/resubmit/:6`、`mine/:7`、`''→product_list:8`。新增 `<int:pk>/` 放在 `mine/` 之后、`''` 之前；`<int:pk>` 只匹配整数，与字符串路径和 `''` 均不冲突。`config/urls.py:29-35` — `path("listings/", include("listings.urls")):34`，`:33` 注释「追加项不排在既有 path("", ...) 之前」；**不改**。`listings/tests.py:1454` 硬断言 `reverse('product_list') == '/listings/'`。
- `templates/listings/product_list.html:1-116` — `extends 'base.html':1`；卡片 `:94-111`（`product.images.all|first:97`、`<img>:99`、中文占位「暂无图片」`:101`、`{{ product.title }}:105`、`¥{{ product.price }}:106`、`{{ product.get_condition_display }}:107`）。按 Decision ④ 仅在此卡片 `card-body` 内**纯追加一个**「查看详情」链接（`{% url 'product_detail' product.pk %}`），既有节点一字不改；`:28-35` 搜索表单、`:37-64` 筛选表单、`:66-82` 结果语境、`:84-115` 空态链、`{% if search_active %}` 块条件、三处搜索态文案一字不改。2.5–2.7 硬断言锁定「暂无上架商品」`:1321,1691`、`<img count=1>` `:1282,1311`、¥ `:1287,1302`、中文成色 `:1288,1303`、`card h-100` 不出现 `:1322,1692`、`找到 N 件商品` `:1759,1780`、搜索文案 `:1690,1774`、`清空搜索` `:1760,1977`、`清空筛选` href `:2529,2537`、`href="/listings/" count=2` `:1462,1979,2714`。
- `templates/base.html:1-40` / `templates/index.html:30` — 导航「商品浏览」`:14` / 首页入口 `:30`（合计 `href="/listings/"` 恰 2 次）；认证徽标 `✓ 已认证:20`（`badge bg-success`）/ `待认证:22`（`badge bg-warning text-dark`）；Bootstrap CDN `:7,38`；`block content:35`。**零改动**，收尾 diff 必须为空。
- `accounts/models.py:5-16` — `User(AbstractUser)`；`student_id:6`（`USERNAME_FIELD:12`）、`is_verified:7`、`role:8-11`、注释 `:13`「username 复用为昵称」；`__str__:16` 返回 `学号 (昵称)` → **详情页必须用 `owner.username`**，否则泄露学号（NFR-4）。`VerificationRequest.name:31` 是真实姓名，勿展示。`accounts/templates/` 不存在，账户模板在 `templates/accounts/`。
- `accounts/tests.py:41,135,454-455,461-462,468-469,571,574,647-654,680,687-688,698,699,722,726`（62 例）— 尤其 `✓ 已认证 count=2` `:698,722`、`待认证 count=2` `:571-574`、`去认证 count=1` `:726`；共享模板新增徽标 / 链接会全破。
- `listings/tests.py`（2719 行 / 140 例 / 7 类）— `PublishViewTests:30`(28)、`ProductVisibilityTests:379`(12)、`RejectionNoticeAndResubmitTests:554`(21)、`MyListingsViewTests:896`(13)、`ProductListViewTests:1175`(15)、`ProductSearchViewTests:1526`(22)、`ProductFilterViewTests:2024`(29，末类至 `:2719`)。模块级夹具 `_STORY27_MEDIA_ROOT:2012` / `_story27_image:2015` / `@override_settings:2023`；末类内 helper `_make_product:2048` / `_attach_images:2060` / `_media_snapshot:2079` / `_get:2088` / `_count_queries_for_get:2091`（2.6 同类在 `:1549,1561,1580,1589,1594`），可照此新建 `_STORY28_*` 与自包含测试类追加在文件末尾；既有 140 例一字不改。隐私断言范式 `listings/tests.py:1444-1449`（`assertNotContains` '卖家甲/乙'、'描述文本'、'QQ'、'微信'）。
- 规划依据：`epics.md:333-347`（2.8 用户故事 / AC / FR-12 / AD-9、AD-4）、`:30`（FR12 覆盖）、`:54`（NFR-4）、`:71`（AD-9）、`:95`（FR-12 → 2.8）、`:204`（已认证标识）、`:114`（NFR 覆盖表，NFR-1 归 2.5/2.6/2.7，详情页按普通页面 ≤2s 口径）；`prd.md:189-196`（FR-12 原文「展示全部图片、描述、价格、成色、分类、卖家昵称 + 认证状态，并提供「联系卖家」「立即购买」按钮」+ 三条 testable consequences）、`:202-208`（FR-13 下单前发消息）、`:237-243`（FR-17 进订单确认页）、`:253-259`（FR-19 下单前不展示 QQ/微信）、`:352-354`（NFR-1）、`:358-360`（NFR-2）、`:366-368`（NFR-4 学号 + 联系方式）；`stories.md:131-139`（2.8 AC、`assert response.status_code == 200 and seller_verified_badge_present`、404、AD-9/AD-4/FR-12）；`architecture.md:55-61`（AD-2 ORM）、`:71-77`（AD-4 服务端授权）、`:111-117`（AD-9 列表/搜索/详情强制 approved）、`:131`（URL 语义命名 `/listings/<id>/`）、`:214`（FR-9~FR-12 归 listings）；`project-context.md:11-12,39,43-48`（分层单体、唯一定义、服务端权限、图片与 Decimal 约定）。
- 前序与决策：`spec-2-5-商品列表浏览-仅上架.md:22` 冻结决策 ①「2.6 / 2.7 在同一页叠加查询参数，**2.8 详情沿 `/listings/<pk>/`**」、④ NFR-1 可执行口径、⑥ Keep full spec；`:40` Never「不实现 2.8 商品详情页（含 `/listings/<pk>/` 路由与 404 规则）…不新增「联系卖家」「立即购买」入口」；`spec-2-6-关键词搜索.md:42`、`spec-2-7-分类-价格-成色筛选.md:44` 同款 Never，`:160-169` Design Notes（门控唯一性、纯追加结构、NFR-1、共享表面回归）；`decision-log.md:300-308`（D-026 多图实体 1–5 张为 FR-12「全部图片」预留，「2.8 详情页尚未实现，契合待该故事验收」）、`:322-330`（D-028 否决跳未实现页）、`:333-341`（D-029 Keep full spec）、`:388-396`（D-034 2.5–2.8 共用同一套过滤）、`:432-440`（D-038）、`:454-462`（D-040 界面入口回归断言）；`epic-2-context.md:25,29,46,51-54`（404、隐私、买家流程、跨故事依赖、「联系卖家」交 Epic 3 /「立即购买」交 Epic 4，本史诗只需就位并可跳转）。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:55` — `2-8-商品详情页: backlog`；`:32` `last_updated: 11-13-2026 11:27`；`:47-56` Epic 2 其余条目全 `done`。收尾时按工作流同步本故事状态与 `last_updated`，不改其他故事条目。`deferred-work.md` 现有条目均属 Epic 1，无 2.5–2.8 条目。
- `.venv/Scripts/python.exe`（Python 3.14 / Django 5.2.19 / Pillow 13.0.0，`requirements.txt:3-4`）为唯一验证解释器；`manage.py` 在根目录；`config/settings.py:61`（TEMPLATES）、`:118`（USE_TZ）、`:128-129`（MEDIA_URL / MEDIA_ROOT）。HEAD `dbc6e7a`（`完成2.7`），工作树干净，分支 `master`。

## Tasks & Acceptance

**Execution:**
- [x] `listings/urls.py` — 新增 `path('<int:pk>/', views.product_detail_view, name='product_detail')`（放在 `mine/` 之后、`''` 之前），不改既有 4 条、不加 `app_name`、不动 `config/urls.py` — 兑现 `architecture.md:131` 语义命名与 spec-2-5 冻结决策 ①。
- [x] `listings/views.py` — 追加 `@require_safe` 的 `product_detail_view`：`get_object_or_404(Product.objects.visible().select_related('owner').prefetch_related('images'), pk=pk)`，渲染 `listings/product_detail.html` 并传入该商品；不写 `status` 字面量、不消费 GET 参数、不加登录装饰器、不产生写入 — 兑现唯一门控、404 AC 与 NFR-1 查询数口径。
- [x] `templates/listings/product_detail.html` — 新建全中文 Bootstrap 详情页：`extends 'base.html'`，展示全部图片（0 图中文占位）、`title` / `description` / `¥{{ product.price }}` / `get_condition_display()` / `category`、`{{ product.owner.username }}` 与 `✓ 已认证` / `待认证` 两态徽标、按 Decision ① 只就位不跳转的「联系卖家」「立即购买」两个入口（`href="#"`、已登录才呈现）与按 Decision ② 的匿名「登录后联系卖家 / 登录后购买」登录引导；不展示学号 / 真实姓名 / QQ / 微信，不用 `|safe` — 兑现 FR-12、FR-3、NFR-4。
- [x] `templates/listings/product_list.html` — 按 Decision ④ 在卡片 `card-body` 内**纯追加一个**「查看详情」链接（`<a href="{% url 'product_detail' product.pk %}">查看详情</a>`），不改卡片结构、不包整卡 `<a>`；既有节点、文案、`<img count=1>`、空态链与 `{% if search_active %}` 块条件一字不改；`base.html` / `index.html` 零改动 — 兑现 `epic-2-context.md:46` 买家链路与共享表面回归。
- [x] `listings/tests.py` — 末尾追加自包含 `ProductDetailViewTests`（独立 `_STORY28_MEDIA_ROOT` / `_story28_image`、类内 helper 沿用 2.7 范式），覆盖 I/O 矩阵全部行：单图 / 5 图 / 0 图、四态 404、混合态、不存在与非法 pk、认证两态、隐私、转义、五类访问者、只读 405 与 HEAD 200、列表入口、查询数不随图片数增长、单次 GET < 1s、共享表面与禁改回归、既有 202 例全绿；既有 140 例一字不改 — 冻结验收的可执行证据。
- [x] `spec-2-8-商品详情页.md` 与 `sprint-status.yaml` — 按工作流同步状态（`2-8-商品详情页`）与 `last_updated`，不改其他故事条目 — 工作流收尾。

**Acceptance Criteria:**
- Given 库中同时有 `approved` 与 `pending / rejected / offline` 商品（均带图带字段），When GET `/listings/<pk>/`，Then 仅 `approved` 返回 200 且渲染 `product_detail.html`；其余三态与不存在的 pk 一律 404，卖家本人与 `role='admin'` 访问自己的非上架商品同样 404（Decision ③，视图无身份分支）；`Product.objects.visible().filter(pk=pk).exists()` 与响应一致，且 `visible()` 仍是全仓唯一 `approved` 门控（FR-12 / AD-9 / NFR-3 / D-034）。
- Given 一件 `approved` 商品挂 1–5 张图，When 查看详情页，Then HTML 含对应数量且各不相同的 `<img src>`（全部图片，非仅首图）、`title` / `description` / `¥` + Decimal 价格 / 中文成色 / 分类、卖家昵称与 `is_verified` 对应的认证徽标；`response.status_code == 200 and seller_verified_badge_present`（`stories.md:138`）；Given 0 图，Then 显示中文占位且无空 `<img>`，页面仍 200。
- Given 详情页任何状态与任何访问者，When 检查输出，Then 不出现卖家 `student_id`、`VerificationRequest.name`、`QQ` / `微信` 字样，也不出现 `{{ product.owner }}` 的「学号 (昵称)」形态（FR-19 / NFR-4）；Given 标题或描述含 HTML，Then 输出被转义、不执行脚本。
- Given 匿名 / 已登录已认证 / 已登录未认证 / 卖家本人 / `role='admin'` 访问同一 `approved` 商品，When GET，Then 五者均 200、看到同一份商品信息；已登录者看到「联系卖家」「立即购买」两个入口，匿名者不看到这两个入口而看到指向 `{% url 'login' %}` 的「登录后联系卖家 / 登录后购买」引导（Decision ②）；Given POST / PUT / PATCH / DELETE，Then 405（`Allow: GET, HEAD`）且无任何 DB / `media/` 写入，HEAD 返回 200。
- Given 已登录用户查看 `approved` 详情页，When 检查两个操作入口，Then 「联系卖家」「立即购买」均存在且可见，均不指向 chat/orders 路径、不产生导航（`href="#"`）；全仓无新增 chat/orders 路由或占位页，无 `NoReverseMatch`、无死链（Decision ① / D-028），FR-13 / FR-17 的实际跳转留给 Epic 3 / 4。
- Given 列表 / 搜索 / 组合筛选任一态，When 查看命中商品卡片，Then 卡片内「查看详情」链接可到达其详情页且返回 200（Decision ④：既有节点与 `<img count=1>` 不变、整卡不包 `<a>`）；`reverse('product_detail', args=[pk]) == '/listings/<pk>/'`，既有 `reverse('product_list') == '/listings/'` 与「清空搜索」「清空筛选」行为不变。
- Given 同一商品挂 1 张与 5 张图，When 单次 GET 详情，Then `CaptureQueriesContext` 查询数相等（不随图片数增长）且 `time.perf_counter` 计时 < 1s（沿用 2.5 决策 ④ 的 NFR-1 可执行口径）。
- Given 交付的共享表面，When 查看 diff，Then `templates/base.html` 与 `templates/index.html` 为空；首页 `href="/listings/" count=2`、`accounts/tests.py` 的 `✓ 已认证 count=2` / `待认证 count=2` / `去认证 count=1` 等既有 202 例断言全部不破。
- Given 交付范围，When 查看 diff 并跑校验，Then 不含 Epic 3 / 4 / 5 的路由 / 视图 / 实体 / 占位页（Decision ①）、不含任何写路径或状态赋值、不含迁移 / 新依赖 / 新静态资源 / 索引 / 缓存 / 分页；`models.py`、`forms.py`、`admin.py`、`migrations/`、`config/`、`requirements.txt`、`accounts/` 与既有 listing 模板（仅 `product_list.html` 按 Decision ④ 纯追加一个链接）无改动；既有 202 例 + 新用例全绿，`manage.py check` 0 issues、`makemigrations --check --dry-run` 为 `No changes detected`。

### Review Findings

第二轮独立复审（2026-11-13，基线 `dbc6e7a` → 提交 `b5739ea`；层：Edge Case Hunter + Acceptance Auditor，Blind Hunter / Verification Gap 按 `_bmad/custom/bmad-code-review.toml` 团队定制禁用）。核验：`check` 0 issues、`makemigrations --check --dry-run` → No changes detected、全量 224 例 OK。

- [x] [Review][Patch] 匿名「登录后联系卖家 / 登录后购买」引导未带 `next`，登录后落到首页、丢失当前商品页 [templates/listings/product_detail.html:41-42]
  - 证据：`accounts/views.py:49` 为 `next_url = request.GET.get('next') or 'home'`，匿名入口只写 `{% url 'login' %}`，故 `next` 恒为空 → 恒跳 `home`；登录模板 `<form method="post">` 无 `action`，POST 保留查询串，因此追加 `?next={{ request.path|urlencode }}` 即可端到端生效。
  - 修复：两个匿名入口 href 追加 `?next={{ request.path|urlencode }}`；`assertContains(resp, 'href="%s"' % login_url)` 为子串匹配，不会被打断。仅调整 Decision ② 的字面 href、不新增路由，若坚持逐字遵守决策原文可改判为 defer。
- [x] [Review][Patch] `test_no_epic3_4_5_routes_or_dead_links` 把「Epic 3/4/5 尚未存在」写成永久守卫，Epic 3 接入即变红 [listings/tests.py:3157-3160]
  - 证据：该测试遍历 `config.urls.urlpatterns` 断言 `'chat' / 'orders' / 'dashboard'` 不出现在任何 pattern 字符串中。Epic 3（`3-1-买家发起聊天` 已是下一个待开发故事）一旦在 `config/urls.py` 加入 `path("chat/", include(...))`，该断言必然失败，后续故事只能删掉 2.8 的测试来解红——交付时点边界不该由永久回归测试承担，本轮 diff 本身已足以证明未新增这些路由。同方法内 `assertNotContains(resp, 'NoReverseMatch')` 恒为真（200 页不会渲染该字符串）。
  - 修复：删除 `config.urls` 遍历断言（连同 `import config.urls`），保留响应级死链断言（`/chat` `/orders` `/dashboard` 不出现在详情页 HTML）。
- [x] [Review][Patch] 图片顺序未显式固定，且「顺序稳定」断言以同源无序查询集自证 [listings/views.py:224-232；listings/tests.py:2857-2864]
  - 证据：`ProductImage` 无 `Meta.ordering`（`listings/models.py:110-125`），视图 `prefetch_related('images')` 未带 `order_by`，模板直接遍历 `product.images.all`；`test_approved_five_images_all_distinct_not_just_first` 的期望值取自同一个无序 `product.images.all()`，即「无序对无序」，顺序实际漂移时该断言仍通过。当前 SQLite 下 rowid 序 == 主键升序，无用户可见坏结果，故仅 `low`。
  - 修复：视图改 `Prefetch('images', queryset=ProductImage.objects.order_by('pk'))`，测试期望改 `product.images.order_by('pk')`；不动模型（避免违反「不改模型」约束）。
- [x] [Review][Patch] Decision ④「纯追加」守卫是恒真断言，缺「查看详情 count=1」「整卡未包 `<a>`」有效断言 [listings/tests.py:3148-3155]
  - 证据：`self.assertNotIn('href="/listings/"', 'href="/listings/<pk>/"')` 是两个常量互比（后者不以 `/"` 结尾），永远为真；`assertContains(detail, 'href="/listings/"', count=1)` 实际只数到 `base.html:14` 导航项。测试既未断言卡片「查看详情」出现 1 次，也未断言整卡未被 `<a>` 包裹，Decision ④ 的「既有节点一字不改」目前只能人工读 diff 确认。
  - 修复：删除恒真 `assertNotIn`，改为 `assertContains(list_page, '查看详情', count=1)`；如需证明整卡未包 `<a>`，可断言卡片区 `<a href="/listings/<pk>/"` 之外不出现包裹 `card h-100` 的开标签。
- [x] [Review][Defer] 真实部署下非安全方法返回 403 而非 AC 要求的 405（`Allow: GET, HEAD`）[listings/views.py:220] — deferred: pre-existing / 不可在本故事内修

**4 条 patch 已于 2026-11-13 全部应用**：`product_detail.html` 两个匿名入口补 `?next={{ request.path|urlencode }}`（实测匿名点入口 → 登录 → 302 回 `/listings/<pk>/`）；`test_no_epic3_4_5_routes_or_dead_links` 改名 `test_no_epic3_4_5_dead_links` 并删去 `config.urls` 遍历；视图改 `Prefetch('images', queryset=ProductImage.objects.order_by('pk'))`、多图断言期望改 `images.order_by('pk')`；恒真 `assertNotIn` 换为「查看详情 count=1 + 指向详情的 `<a>` 仅 1 处 + 详情页不自链接」。复跑：`check` 0 issues、`makemigrations --check --dry-run` → No changes detected、全量 **224 例 OK**。

**Rejected（4 条，不予修复）**

- `low` — `listings/tests.py:3132-3139` 单次 GET `< 1.0s` 无预热/容差，慢 CI 可能偶发误报：该断言由 spec-2-5 决策 ④ 冻结口径要求，且 2.5 / 2.6 / 2.7 三个测试类已有同款（`tests.py:1415,1906,2638`）；被测页面仅 1 条 JOIN + 1 条预取，1s 上限余量极大，加预热请求反而引入无效复杂度。
- `low` — `listings/tests.py:3171-3179` `test_visible_is_the_only_status_gate_in_source` 只读 `views.py` / `models.py`，撑不起「全仓唯一门控」：全仓检索确认生产代码 `status='approved'` 字面量当前仅在 `listings/models.py:14`（`views.py:64` 的 `status='rejected'` 是卖家侧重提门控，非 approved 门控），无现存缺陷；把守卫扩到全目录需新增文件遍历，超出直接修正。
- `low` — `spec-2-8:5` `status: 'done'` 与 sprint `review` 矛盾：修复动作即编辑本次规格的状态字段，按 triage 规则驳回；状态同步由本工作流收尾步骤统一处理。
- `low` — `listings/tests.py:2723-2739` 重复 import 既有模块顶部已导入的名字，且 `:2741` `tempfile.mkdtemp()` 在模块导入期执行：纯代码卫生，重复导入删除即可但 `mkdtemp` 需迁移到 `setUpClass` 才彻底，属超出直接修正的重构，无功能与可读性实质影响。

## Implementation Notes

- **工作流状态更正（Step 3 主代理）**：实现子代理交付时自行把本规格 `status` 与 `sprint-status.yaml` 的 `2-8-商品详情页` 提前置为 `review`，并改写 `last_updated` 为 `13:24`。按 bmad-build 工作流，状态同步由主代理在 Step 3 / Step 4 收尾时负责，且独立复审尚未执行，故已撤回为 `in-progress`；`review` / `done` 待 Step 4 审查及后续独立复审完成后再同步。此更正不涉及冻结区与任何实现代码（与 Story 2.2 / 2.3 的同类越权处理一致）。

## Spec Change Log

## Review Triage Log

首轮三层审查（Blind Hunter 12 / Edge Case Hunter 4 / Verification Gap 1，共 17 条），`review_loop_iteration` 保持 0（无 loopback）。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 1 | BH | 规格 `in-review` / Implementation Notes `in-progress` / sprint `in-progress` / 工作日志 `draft` 四处状态矛盾，缺 CHECKPOINT 1 批准记录 | `false` | 四处分属不同工件与不同工作流阶段：Implementation Notes 记的是 Step 3 撤回动作、memory 日志按 append-only 分阶段追加、spec 与 sprint 的最终同步由 Step 5 负责；批准发生在对话中，工作流未要求写入文件。且修复=编辑本次 build 规格，按 triage 规则驳回。 |
| 2 | BH | 工作日志只写到 Step 2，缺 Step 3 实现 / Step 4 审查 / 测试结果与状态流转条目 | `false` | Step 4/5 尚未完成，工作日志按约定在收尾阶段追加；当前仍在同一任务中途，非交付缺陷，修复=编辑会话工件。 |
| 3 | BH | `Spec Change Log` / `Review Triage Log` 为空标题，`in-review` 配 `review_loop_iteration: 0` 自相矛盾 | `false` | 模板注释明确前者「Empty until the first bad_spec loopback」、后者「Empty until the first review pass」；本轮即首轮审查，本表正在写入，`iteration: 0` 表示尚无 loopback，符合定义。修复=编辑规格 → 驳回。 |
| 4 | BH | `## Verification` 只列 expected 输出，缺 `check` / `test` / `makemigrations` / `git diff` 实跑证据 | `false` | 模板把该节定义为「how the agent confirms its own work」，只列命令与期望；实跑已由主代理独立执行：`check` 0 issues、`makemigrations --check --dry-run` → No changes detected、禁改清单 diff 为空、全量 `test -v 2` → 224 例 OK、单独 `ProductDetailViewTests` → 22/22 OK。修复=编辑规格 → 驳回。 |
| 5 | BH | `last_updated: 13:24` 是子代理越权写入、撤回状态却未撤回/说明时间戳 | `false` | 该字段记录最后一次同步时间，13:24 为合法时间点；Step 5 收尾会再次同步，Implementation Notes 已收口说明来源，无信息矛盾。修复=编辑状态工件 → 驳回。 |
| 6 | BH | 非法主键用例缺 `pk=0` / 前导零 / 超 64 位整数（可能 OverflowError→500）/ 缺尾斜杠 / 多余段，「均不 500」无证据 | `false` | 隔离测试库实测：`/listings/0/`→404、32 位以上超长整数→**404 而非 500**、`/listings/1/extra/`→404、`/listings/1`→301（Django APPEND_SLASH 正常行为）；矩阵列出的 `999999` / `abc` / `-1` 三个输入均为 404，「均不 500」成立。 |
| 7 | BH | 新路由缺「不遮蔽 `<int:pk>/resubmit/` / `publish/` / `mine/`」回归断言，也未验证 GET 参数无法绕过 404 门控 | `false` | 实测 `/listings/1/resubmit/`→302（既有 resubmit 路由仍命中，未被 `<int:pk>/` 遮蔽，因该 converter 要求路径结束）、`publish/` / `mine/` 为字母不匹配 int converter；`/listings/2/?status=approved`（pending）→404，视图不消费任何 GET 参数，门控只由 `visible()` 决定；既有 140 例全绿已间接覆盖。 |
| 8 | BH | 只读保证只抽查三张表 + media，未用 `CaptureQueriesContext` 证明零 INSERT/UPDATE/DELETE，未覆盖 `VerificationRequest` / session / `LogEntry` | `false` | `product_detail_view` 仅 `get_object_or_404` + `render`，全文件无 `.save()` / `.create()` / `.update()` / `.delete()`；`@require_safe` 在视图执行前把 POST/PUT/PATCH/DELETE 拦为 405；测试已对 Product / ProductImage / RejectionNotice / media 做前后快照全等。声称的「未证明」不构成可复现坏结果。 |
| 9 | BH | HEAD 只断言 `status_code == 200`，未断言 `resp.content == b''` | `false` | 实测 `client.head('/listings/1/')` → 200 且 `content_len = 0`；Django 对 HEAD 剥离响应体，视图无流式输出，规格「无 body」已由框架满足。 |
| 10 | BH | `test_visible_is_the_only_status_gate_in_source` 只读 views.py / models.py、只匹配单引号，撑不起「全仓唯一门控」 | `false` | 全仓 Grep 生产代码 `status='approved'` / `filter(status` 仅命中 `listings/models.py:14`；`accounts/admin.py:39` 是 `VerificationRequest.status` 赋值，非商品门控；测试守卫虽窄，但「当前存在第二套商品门控」这一坏结果不成立。 |
| 11 | BH | 徽标两态测试只断言文案，未断言 Bootstrap class 与 `base.html` 一致 | `false` | 实测未认证卖家详情页渲染 `badge bg-warning text-dark`，与 `base.html:22` 一致；diff `:739` 的已认证态为 `badge bg-success`，与 `base.html:20` 一致。class 一致性由代码本身保证，无当前缺陷。 |
| 12 | BH | Decision ④ 缺 `detail_href count=1` / 整卡不包 `<a>` 断言；`assertNotIn` 恒真；两条登录引导未 `count=2` | `low` → rejected | diff 显示 `product_list.html` 仅 +1 行，既有节点、`card h-100`、`<img count=1>` 全未改动，整卡未包 `<a>`；恒真断言与缺计数属测试强度问题，不产生用户可见坏结果，修复需新增断言与守卫而非直接修正。 |
| 13 | EC | `ProductImage.image` 为空时 `.url` 抛 ValueError → 详情页 500 | `false` | `ProductImage.image` 由 `publish_view` / `resubmit_view` 的 `validate_images` 保证为真实上传文件（AD-8 / D-026），无生产调用者写入空 image；该状态在交付程序中不可达， loudly failing 不等于缺陷（同 2.2 BH-7 / 2.3 EC-2 根因）。 |
| 14 | EC | 图片文件从 `MEDIA_ROOT` 缺失时渲染破图而非中文占位 | `false` | 规格「0 图」定义为无 `ProductImage` 行，模板 `{% if images %}` 已覆盖；文件被外部删除属数据完整性问题，非本故事代码路径；修复需 `storage.exists()`，增加每请求 I/O 与分支复杂度。 |
| 15 | EC | 前导零 pk `/listings/007/` 返回 200，产生非规范别名 URL | `low` → rejected | 实测 `/listings/001/` → 200，别名行为真实；但前导零 URL 在日常使用中不可达，规格亦未要求规范化，修复需新增 redirect 分支 / 视图逻辑，超出直接修正。 |
| 16 | EC | `ProductImage` 无 `Meta.ordering`、`prefetch_related` 无序，图片顺序未定义 | `false` | 规格 Always 明确「图片顺序按 `ProductImage` 默认主键升序即可」，未指定 ordering 即采用 DB 默认；SQLite 演示环境按 rowid 返回，`test_approved_five_images_all_distinct_not_just_first` 已断言渲染顺序与 `images.all()` 完全一致；新增 `Meta.ordering` 还会违反冻结区「不改模型」。 |
| 17 | VG | NFR-1 查询数测试只比较 1 图 / 5 图差值并断言 `<=5`，删除 `.select_related().prefetch_related()` 后仍全绿，优化回归无法被发现 | `medium` → `patch` | verification-gap 层为 pre-verified gap，采信其 filed evidence：优化视图 `q=2`、无优化 `q=3`，两种情况下 `assertEqual(q_one, q_five)`、`assertLessEqual(q_five, 5)`、`elapsed < 1.0` 均成立；坏结果明确（详情页丢失 N+1 优化时现有测试不报错，开发者侧无告警上线）。最小修复只改测试、不加公共表面、守卫的是已实测的 `q=2` 基线 → `patch`。 |

分组与路由：17 条中 15 条 `false`、2 条 `low → rejected`，唯一幸存者 #17 单独成组（根因=NFR-1 测试未钉住绝对查询数基线），按最高裁决 `medium` 路由到 `patch`；无 `intent_gap` / `bad_spec`，不触发 loopback，`review_loop_iteration` 保持 0。

## Design Notes

- **沿用 spec-2-5 的人类冻结决策**（编号属 2.5，勿与本规格 `Intent` 的 Decision ①–⑤ 混淆）：spec-2-5 决策 ①「2.8 详情沿 `/listings/<pk>/`」决定只新增 1 条路由 + 1 个视图 + 1 个新模板，不改 `config/urls.py`、不加 `app_name`；spec-2-5 决策 ④ 的 NFR-1 可执行口径（查询数不随 N 增长 + 单次 GET < 1s）与决策 ⑥ / D-029 / D-038 的「保留完整规格、接受 context-rot 风险、由 Step 4 三层审查兜底」一并沿用。D-026（`decision-log.md:300-308`）当年为 FR-12「全部图片」特意选了 1–5 张独立图片实体，本故事是其契合度的验收点。
- **门控唯一性（D-034）**：`get_object_or_404(Product.objects.visible(), pk=pk)` 把「非上架 → 404」和「唯一 `approved` 过滤」合并成一条语句，视图里任何 `filter(status=...)` / `if product.status == 'approved'` 都意味着第二套门控。人类决策 ③ 确定，卖家本人与 admin 也不得通过详情页看到非上架商品（卖家状态查看走「我的发布」、admin 走 Django admin），这样 404 规则无角色分支、可测且无信息泄露。
- **昵称与隐私**：`User.__str__` 输出 `学号 (昵称)`（`accounts/models.py:16`），模板若写 `{{ product.owner }}` 会直接违反 NFR-4；必须显式 `{{ product.owner.username }}`。`VerificationRequest.name`（真实姓名）与联系方式均不在 `Product` 上，本故事天然不需读取；测试以 `assertNotContains` 锁定。
- **徽标两态（代理决定，用户可见但仓库已有范式，不列 Open Question）**：`templates/base.html:20,22` 与 `templates/accounts/profile.html:25,27` 已确立 `✓ 已认证` / `待认证` 两个 Bootstrap badge 文案，详情页沿用同一对文案与 class，保证 FR-12「卖家昵称 + 认证状态」两态都有明确输出；不在 `base.html` 新增徽标，避免 `accounts/tests.py:698,722` 的 `count=2` 断言失效。
- **入口与死链**：`chat/urls.py` / `orders/urls.py` / `dashboard/urls.py` 为 0 字节、`config/urls.py:29-35` 未 include，`{% url %}` 指向它们必抛 `NoReverseMatch`；D-028 已否决「跳到尚未实现的页面」。人类决策 ① 确定，本故事只让入口在 DOM 中就位而不产生跳转，把「进入聊天 / 进入下单」的真正落地留给 Epic 3 / 4（与 `epic-2-context.md:54`「只需就位并可跳转」的边界一致）；规格 AC 据此只断言「入口存在」，不虚构可跳转的目标。
- **URL 顺序**：`<int:pk>/` 与 `publish/` / `mine/` 是不同 pattern（整数 converter 不匹配字母），与 `''` 也不冲突；但为保持既有顺序，追加项放在 `mine/` 之后、`''` 之前。`config/urls.py:33` 的注释约束的是 config 级 `path("", ...)`，本故事不动 config 级路由。
- **查询结构**：`select_related('owner')` 消除卖家信息的额外查询，`prefetch_related('images')` 一次取回全部图片；详情是单对象页，不引入分页 / 缓存 / 索引。既有 `product_list.html` 的 `product.images.all|first` 取法不动。
- **共享表面回归**：`base.html` / `index.html` 被 `accounts/tests.py` 62 例与 `listings/tests.py:1462,1979,2714` 锁定；`href="/listings/<pk>/"` 不含 `href="/listings/"` 这一完整子串（`assertContains` 是子串计数），故卡片追加详情链接不影响首页 `count=2`。`product_list.html` 既有搜索 / 筛选文案与卡片四要素被 2.5 的 15 例、2.6 的 22 例、2.7 的 29 例硬断言锁定，只做追加。
- **演示数据**：沿用 2.1–2.7 惯例，不往运行时 `db.sqlite3` / `media/` 造数；四态 × 0–5 图 × 认证两态 × 五类访问者 × 合法 / 非法 pk 全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: `System check identified no issues (0 silenced)`
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（本次不改模型）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 202 例 + 本故事新增用例全绿，无失败 / 跳过；新用例逐条 `... ok`
- `git diff --name-status` 及 `git diff -- listings/models.py listings/forms.py listings/admin.py listings/migrations/ config/urls.py config/settings.py requirements.txt accounts/ templates/base.html templates/index.html templates/listings/publish.html templates/listings/resubmit.html templates/listings/my_listings.html` — expected: 上述文件 diff 为空；`templates/listings/product_list.html` 仅有纯追加的详情链接
- `git status --porcelain=v1` — expected: 仅含本故事交付文件与本规格 / sprint 状态文件
- 全仓 `status='approved'` 字面量检索 — expected: 生产代码仍只在 `listings/models.py:14`

**Manual checks (if no CLI):**
- 在测试库构造一件 `approved` 商品（挂多图、已认证卖家）与 `pending / rejected / offline` 各一件，分别打开 `/listings/<pk>/` 核对：上架页全部图片与字段、卖家昵称与 `✓ 已认证`、两个操作入口齐备；其余三态与不存在的 pk 均 404；详情页不出现学号 / QQ / 微信。退出登录后再访问确认仍 200；从列表页点「查看详情」确认可达；从首页与导航栏各点一次「商品浏览」确认 `href="/listings/"` 仍是两处。
