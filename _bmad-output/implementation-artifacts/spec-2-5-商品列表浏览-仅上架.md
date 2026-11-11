---
title: '商品列表浏览（仅上架）'
type: 'feature'
created: '2026-11-11'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 71861b90bf6a055d02f78d0124f3979dbbda6cf9
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 2.2 已把对外可见性收敛为 `Product.objects.visible()` 唯一门控，2.1–2.4 也已让商品以 `pending / approved / rejected / offline` 四态落库、可驳回重提、卖家可回看本人发布；但全仓没有任何买家侧的商品列表：`config/urls.py:31` 的根路由仍指向只做认证引导的 `templates/index.html`，`listings/urls.py:5-7` 只有三条卖家侧路由，全部模板无 `<img>`、无缩略图。FR-9、`stories.md:106-113`、`epics.md:290-303` 的验收（仅 `approved`、含缩略图/标题/价格/成色、响应 ≤1s）因此既无访问入口也无可执行证据，Epic 2 买家链路（列表 → 搜索 → 筛选 → 详情）断在第一环。

**Approach:** 在 `listings` 内新增一个公开只读的商品列表页：视图只经 `Product.objects.visible()` 取数（不另写 `status='approved'`），用 `prefetch_related('images')` 一次取回首图，模板以 Bootstrap 卡片网格渲染缩略图 / 标题 / 价格 / 中文成色，无图商品给中文占位，空列表给中文空状态；由导航栏与首页正文提供入口。不改模型、不改首页既有认证引导文案、不产生迁移、不引入搜索 / 筛选 / 详情（2.6–2.8）与任何写路径，让 2.6 / 2.7 能在同一 queryset 上叠加查询条件。

**Decision（人类决策，2026-11-11 21:25，全部按推荐）:** ① Q1=A：新增独立公开列表页 `/listings/`（`name='product_list'`），首页 `/` 保持认证引导页不变，入口由导航 + 首页正文提供；2.6 / 2.7 在同一页叠加查询参数，2.8 详情沿 `/listings/<pk>/`。② Q2=A：列表页公开只读，匿名与登录用户均可见，仅 GET/HEAD，不要求 `is_verified`；依据是 NFR-2 只约束「所有写操作需登录」，沿用 `@login_required` 会把游客挡在门外。③ Q3=A：缩略图走 `images` 反向关系取首图 + 视图 `prefetch_related('images')` + CSS 固定尺寸裁切，无图给中文占位；不新增模型 property、不生成新缩略图文件、不动迁移。④ Q4=A：不分页、不截断，全量按 `Product.Meta.ordering` 倒序；NFR-1 由「查询数不随商品数增长」与「单次 GET < 1s」两条用例证明，不引入缓存 / 索引 / 分页配置。⑤ Q5=A：`templates/base.html` 导航栏追加一个所有用户（含匿名）可见的「商品浏览」链接，`templates/index.html` 正文追加一个同目标入口；既有导航项 / 认证引导文案 / 分支结构一字不改。⑥ Q6=A 与 token gate：保留完整规格、不拆分、不新增 deferred 项，沿用 D-029 / D-033 / D-034，context-rot 风险由 Step 4 三层审查兜底；起草时点按 `cl100k_base` 统计 8,624 tokens（15,038 字符 / 140 行），**接受超 1600 门槛的风险**。以上六项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 对外商品查询**唯一入口**是 `Product.objects.visible()`（`listings/models.py:12-14`）；全仓 `status='approved'` 字面量仍只在 `models.py:14`，不得在视图 / 模板 / 测试中另写第二套门控。
- 列表页为 `path('', views.product_list_view, name='product_list')`（URL `/listings/`）；`listings/urls.py` 追加且不设 `app_name`；`config/urls.py` 的 `path("", home)`、accounts include、`listings/` include、DEBUG `static()` 一字不改。
- 列表页**公开**：不加 `@login_required`、不要求 `is_verified`，匿名 / 已登录 / 已登录未认证 GET 均 200；仅放行 GET/HEAD（`@require_safe`），只读、不改 `status`、不写任何记录、不接受请求传值做筛选或排序；非安全方法 405（`Allow: GET, HEAD`）且无 DB 写入。
- 每张卡片含四要素：缩略图、标题、`¥{{ product.price }}`（Decimal 原值）、`get_condition_display()` 中文成色；不展示描述、状态 badge、卖家 QQ/微信、认证徽标、创建时间等非 AC 字段。
- 排序沿用 `Product.Meta.ordering = ('-created_at',)`（`models.py:69`），不另写 `order_by`；不引入分页 / 条数截断，全量上架商品均可达。
- 缩略图取该商品首图（`images` 反向关系），用 CSS 固定尺寸裁切；无图商品渲染中文「暂无图片」占位，不输出空 `src` 或破图标签；视图须消除 N+1（图片集合一次性预取）。
- `templates/base.html` 导航栏追加一个所有用户（含匿名）可见的「商品浏览」链接，`templates/index.html` 正文追加一个同目标入口；两处均为纯追加，既有导航项、认证徽标、退出表单、认证引导文案与匿名 / 已登录分支结构一字不改。
- 服务端渲染 + Bootstrap 5.3.3 CDN + 全中文用户可见文案（`LANGUAGE_CODE='en-us'` 不自译）；不引入 DRF / API / SPA / WebSocket / 新第三方依赖 / 新静态资源。
- 既有 **136** 个用例一字不改且全绿；`templates/base.html` 既有导航项、认证徽标、退出表单与 `templates/index.html` 既有认证引导文案（「请注册或登录」「你的账号已通过认证」等）保持不变，`accounts/tests.py:677-688`、`listings/tests.py:96-102` 等硬断言不破。
- 不产生迁移、不改模型 / 表单 / admin / 既有迁移 / `config/settings.py` / `requirements.txt`；`manage.py check` → 0 issues，`makemigrations --check --dry-run` → `No changes detected`。
- 不往运行时 `db.sqlite3` / `media/` 造演示数据；所有商品 / 图片状态由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

**Never:**
- 不实现 2.6 关键词搜索、2.7 分类/价格/成色筛选、2.8 商品详情页（含 `/listings/<pk>/` 路由与 404 规则）、5.1 / 5.2 审核区与下架、Epic 3 聊天、Epic 4 订单；不新增「联系卖家」「立即购买」入口。
- 不改 `listings/models.py`（`visible()` / `STATUS_CHOICES` / `ALLOWED_TRANSITIONS` / `_transition()` / `ProductImage` / `RejectionNotice`）、`listings/forms.py`、`listings/admin.py`、`listings/migrations/`、`config/settings.py`、`requirements.txt`。
- 不新增模型字段 / property / 方法、不生成缩略图文件、不改图片上传校验与 `ProductImage` 存储路径。
- 不新增任何写路径：无 POST 表单、无状态流转、无删除 / 下架 / 审核动作、不写 `media/`。
- 不把 `pending / rejected / offline` 商品以任何形式（隐藏、占位、注释、上下文变量）带进模板；不泄露未上架商品的标题 / 价格 / 成色 / 图片 URL / 卖家信息。
- 不引入分页控件 / 缓存 / 数据库索引 / 新增配置项；不做跨用户可猜测的商品主键入口。
- 不改 `templates/listings/my_listings.html`、`templates/listings/publish.html`、`templates/listings/resubmit.html`、`templates/accounts/profile.html`；不改 `accounts/views.py`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 多状态混合 | 库中同时有 `pending / approved / rejected / offline` | 200，仅 `approved` 出现在 `response.context['products']`；断言 `all(p.status == 'approved' for p in listed_products)`（`stories.md:112`） | `visible()` 门控 |
| 四要素渲染 | 至少 1 件 `approved` 且有图 | 卡片含缩略图 `<img>`、标题、`¥` + 价格、`get_condition_display()` 中文成色 | N/A |
| 首图 | `approved` 商品挂 1–5 张图 | 卡片 `<img src>` 指向 `images` 反向关系的首图 URL，且只输出 1 个 `<img>`/卡片 | 预取图片集 |
| 无图商品 | `approved` 但 `images` 为空 | 中文「暂无图片」占位，该卡片无 `<img>` 标签 | 占位分支 |
| 空列表 | 无任何 `approved`（含仅有 `pending`） | 中文空状态「暂无上架商品」，不渲染任何卡片 | 空状态分支 |
| 倒序 | 多件 `approved`、`created_at` 互异 | 按 `-created_at` 倒序（context 与 HTML 双重断言） | `Meta.ordering` |
| 访问门控 | 匿名 / 已登录 / 已登录未认证 GET | 三者均 200，看到同一份仅 `approved` 的列表；不要求 `is_verified`、不加登录门控 | 无 |
| 只读方法 | POST / PUT / PATCH / DELETE | 405（`Allow: GET, HEAD`），无任何 DB 写入 | `require_safe` |
| 查询数 | N=2 与 N=20 件 `approved`（含图） | 查询数不随商品数增长（预取生效） | `prefetch_related` |
| 响应时间 | 演示规模 N 件 `approved` | 单次 GET 耗时 < 1s（NFR-1，`time.perf_counter` 计时断言） | 性能用例 |
| 数据隔离 | 库中另有他人 `approved` 商品 | 列表展示所有已上架商品（含他人），但仅 AC 四要素，无卖家隐私字段 | N/A |
| 回归 | 既有 136 例 + 首页 / 导航硬断言 | 全绿，`index.html` / `base.html` 既有文案与链接不变 | 全量回归 |

</frozen-after-approval>

## Code Map

- `listings/models.py:9-14` — `ProductQuerySet.visible()`：`filter(status='approved')`，**对外可见性唯一定义、一字不改**；2.5 必须直接链式复用，不得复制字面量。
- `listings/models.py:17-72` — `Product` 字段（`title` / `price` Decimal / `condition` / `category` / `status` / `owner` / `created_at`）、`CONDITION_CHOICES`（全新/良好/中等）、`STATUS_CHOICES` 四态中文名、`Meta.ordering=('-created_at',)`、`objects = ProductQuerySet.as_manager()`；`get_condition_display()` 是成色文案唯一来源。
- `listings/models.py:110-127` — `ProductImage`：`related_name='images'`、`image = ImageField(upload_to='products/')`；**无首图 property / 无缩略图字段**，模板只能通过反向关系取图；`image.url` 用法见 `listings/tests.py:313`。
- `listings/views.py:1-7,100-113` — import 与三个既有视图；`my_listings_view` 是 `@require_safe` 只读范式（返回 `render(...)` + 空状态标志），但其 `Product.objects.filter(owner=...)` 是**卖家基础查询集**，列表页不得照抄，须改用 `visible()`；`publish_view` / `resubmit_view` 一字不改。
- `listings/urls.py:4-7` — 现有 `publish/`、`<int:pk>/resubmit/`、`mine/`；追加 `path('', ...)` 时注意不与 `<int:pk>` 路由冲突，不设 `app_name`。
- `config/urls.py:25-39` — `home()` 渲染 `index.html`（`:31` 根路由，会先尝试 accounts include 再落到 `listings/` include）；`:34` include、`:38-39` DEBUG `static(settings.MEDIA_URL, ...)` 被 `listings/tests.py:305` 硬断言，**全部不改**。
- `templates/base.html:1-38` — 仅 `title`(`:6`) / `content`(`:34`) 两个 block；导航 brand→`home`(`:12`)，已登录分支 `:14-24`（个人中心 / 发布商品 / 认证徽标 / 退出 POST），未登录分支 `:25-28`；Bootstrap 5.3.3 CDN(`:7`, `:37`)。追加导航项须避开「发布商品」「个人中心」「✓ 已认证」等被硬断言的文案。
- `templates/index.html:1-29` — 首页认证引导（`请注册或登录`、认证成功 / 待认证提示、`verify` / `register` / `login` 按钮），被 `accounts/tests.py` 多处 `assertContains` 与 `assertRedirects(home_url)` 锁定；只追加入口，不改既有分支。
- `templates/listings/my_listings.html:1-40` — 可复用范式：`extends 'base.html'`、`list-group` 卡片、`badge bg-secondary`、`¥{{ product.price }}`、`get_condition_display()`、`text-muted` 中文空状态、`|date` 过滤；本故事用卡片网格 + `<img>` 缩略图，不改该文件。
- `templates/accounts/profile.html:56-73,83-110` — 卡片 / badge / 「查看全部」入口范式；本故事不改。
- `listings/forms.py:7-10,13-42,47-52` — `validate_images`（1–5 张、≤5MB、仅 JPEG/PNG）与 `ProductForm`（五字段、不含 `status` / `owner`）；2.5 不碰表单，但无图商品只能由测试构造（`ProductImage` 无强制约束），故占位分支必须可测。
- `listings/tests.py` — 4 个类共 **74** 例：`PublishViewTests`:30、`ProductVisibilityTests`:379、`RejectionNoticeAndResubmitTests`:554、`MyListingsViewTests`:896；夹具 `_TEST_MEDIA_ROOT`:18、`_make_image`:21、`@override_settings`:29/378、`_STORY23_MEDIA_ROOT`:542 / `_story23_image`:545。新测试类**追加在文件末尾**，既有 74 例一字不改。硬断言：`:96-102` 首页 `href=publish` +「发布商品」各 `count=1`；`:305` DEBUG `static()`；`:962` `assertNotContains('<img')` 只作用于 `my_listings.html`；`:965-982` profile 四板块空状态。
- `accounts/tests.py` — 62 例；`:677-688` `test_navbar_profile_link_only_for_authenticated`（遍历 home/verify/profile 断言 `href=/profile/`，匿名页 `assertNotContains`）、`:690-703` 徽标 `count=2`；导航改动不得破坏。
- `config/settings.py:64`（TEMPLATES DIRS）、`:82-87`（sqlite3）、`:112/114/118`（en-us / UTC / USE_TZ）、`:128-129`（MEDIA_URL / MEDIA_ROOT）、`:140`（LOGIN_URL=`/login/`） — 全部不改；无分页 / 缓存 / 性能配置，NFR-1 需在代码层用预取与计时用例证明。
- `_bmad-output/planning-artifacts/stories.md:106-113` — 2.5 用户故事 / AC / 测试断言 / AD-9、NFR-1、FR-9；`epics.md:290-303`（含缩略图/标题/价格/成色、≤1s）、`prd.md:168-173`（FR-9）、`prd.md:352-354`（NFR-1 ≤1s P95 / 首屏 ≤2s）、`prd.md:356-360` 附近（NFR-2 只约束写操作）。
- `decision-log.md:247-253`（D-021 本地 media / Pillow 缩略）、`:322-328`（D-028 否决跳到未实现页面）、`:388-396`（**D-034 2.2 只做模型层，列表页明确留给 2.5–2.8，且共用同一套 approved 过滤**）、`:454-462`（D-040 界面入口回归断言）；`epic-2-context.md:25,28,30,35,51`（强滤 approved、四要素、可见性唯一定义、2.5–2.8 共用过滤）。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:52` — `2-5-商品列表浏览-仅上架: backlog`，收尾时按工作流同步；`spec-2-4-查看我的发布.md:64-80,168-175` — 前一故事的 Code Map 与「基础集 vs `visible()`」边界，2.5 是对外侧首次消费 `visible()`。
- `.venv/Scripts/python.exe` — Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0；系统 PATH 的 `python` 无 Django，验证一律用该解释器。

## Tasks & Acceptance

**Execution:**
- [x] `listings/views.py` — 末尾新增 `product_list_view`（`@require_safe`，**不加** `@login_required`），以 `Product.objects.visible().prefetch_related('images')` 取全量上架商品并构造 `products` / `products_empty` 上下文；不写 `status='approved'` 字面量、不写任何状态、不接受请求传值 — 兑现 AD-9 唯一门控与 FR-9 服务端过滤。
- [x] `listings/urls.py` — 追加 `path('', views.product_list_view, name='product_list')`，不设 `app_name`；`config/urls.py` 不动 — 兑现 `/listings/` 可访问入口。
- [x] `templates/listings/product_list.html`（新增） — 继承 `base.html`，Bootstrap 卡片网格渲染缩略图 / 标题 / `¥` 价格 / `get_condition_display()` 中文成色；首图用 `images` 反向关系 + CSS 固定尺寸，无图中文占位；空列表中文空状态；全中文文案 — 兑现 AC 四要素与无图 / 空列表分支。
- [x] `templates/base.html` / `templates/index.html` — 纯追加「商品浏览」入口链接（导航栏所有用户可见 + 首页正文），既有导航项 / 认证引导文案 / 分支结构一字不改 — 兑现买家可达路径且不破硬断言。
- [x] `listings/tests.py` — 末尾追加新测试类（自包含夹具、临时 `MEDIA_ROOT`），覆盖矩阵各行：仅 approved（含四态混合与 context 断言）、四要素与首图 URL、无图占位、空列表、倒序、三类访问门控均 200、只读 405 且无写入、查询数不随 N 增长、单次 GET < 1s、他人 approved 可见但无隐私字段、既有 136 例全量回归；既有 74 例一字不改 — 冻结验收的可执行证据。
- [x] `spec-2-5-商品列表浏览-仅上架.md` 与 `sprint-status.yaml` — 按工作流同步状态（`2-5-商品列表浏览-仅上架`），不改其他故事条目 — 工作流收尾。

**Acceptance Criteria:**
- Given 库中同时存在 `pending / approved / rejected / offline` 商品，When 访问商品列表页，Then `response.context['products']` 与页面 HTML 均只含 `approved` 商品，`all(p.status == 'approved' for p in listed_products)` 成立，且 `visible()` 仍是全仓唯一 approved 门控（AD-9 / FR-9）。
- Given 已上架商品（含图 / 无图两种），When 查看列表卡片，Then 每张含缩略图或中文「暂无图片」占位、标题、`¥` + Decimal 价格、`get_condition_display()` 中文成色，且按 `-created_at` 倒序。
- Given N 件已上架商品（含图），When 单次 GET 列表页，Then 查询数不随商品数增长（图片预取生效）且响应耗时 < 1s（NFR-1）。
- Given 匿名访客、已登录用户或已登录未认证用户，When 访问列表页，Then 三者均 200 且看到同一份仅 `approved` 的列表；Given 非 GET/HEAD 请求，Then 405 且无任何 DB 写入。
- Given 交付范围，When 查看 diff 并跑校验，Then 不含 2.6 / 2.7 / 2.8 / 5.1 / 5.2 / Epic 3 / Epic 4 内容，不含任何写路径或状态赋值；`listings/models.py`、`forms.py`、`admin.py`、`migrations/`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`accounts/views.py` 与既有 listing 模板均无改动；既有 136 例 + 新用例全绿，`manage.py check` 0 issues、`makemigrations --check --dry-run` 为 `No changes detected`。
- Given 首页与导航栏，When 访问 `home` / `verify` / `profile` 等既有页面，Then 既有文案与链接硬断言保持成立，且存在指向商品列表页的中文入口。

## Implementation Notes

- 实现按冻结意图完成，改动文件：`listings/views.py`（末尾追加 1 视图）、`listings/urls.py`（追加 1 路由）、`templates/listings/product_list.html`（新增）、`templates/base.html` / `templates/index.html`（各纯追加 1 处「商品浏览」入口）、`listings/tests.py`（末尾追加 15 例，既有 74 例一字未改）、本规格与 `sprint-status.yaml`（`last_updated` 更新为 `11-11-2026 21:46`，故事条目保持 `in-progress`）。`listings/models.py`（含 `visible()` / `STATUS_CHOICES` / `Meta.ordering` / `objects`）、`listings/forms.py`、`listings/admin.py`、`listings/migrations/`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`accounts/views.py`、既有 listing 模板、`accounts/tests.py` 均无改动；未产生迁移，未往运行时 `db.sqlite3` / `media/` 造数据。
- `listings/views.py`：新增 `product_list_view`，仅 `@require_safe`（不加 `@login_required`、不要求 `is_verified`）；`Product.objects.visible().prefetch_related('images')` 链式复用唯一门控，`list()` 求值后构造 `products` / `products_empty`；不写 `status` 字面量、不写任何状态、不接受 `request.GET` 做筛选 / 排序；排序沿用 `Product.Meta.ordering('-created_at')` 且无分页 / 截断。`prefetch_related` 一次取回全部首图，消除 N+1。
- `listings/urls.py`：末尾追加 `path('', views.product_list_view, name='product_list')`（`reverse` → `/listings/`），未设 `app_name`；`config/urls.py` 的根路由 / accounts include / `listings/` include / DEBUG `static()` 一字未改。空路径 `path('', ...)` 不与 `<int:pk>/resubmit/` 冲突。
- `templates/listings/product_list.html`：继承 `base.html` 的 `title` / `content`；模板内 `<style>` 以 `width:100% / height:180px / object-fit:cover` 做 CSS 固定尺寸裁切（不新增静态资源、不生成缩略图文件）；首图走 `product.images.all|first` 的 `images` 反向关系，无图渲染中文「暂无图片」`<div>` 占位（不输出 `<img>` / 空 `src`）；空列表渲染中文「暂无上架商品」且不渲染任何卡片；每张卡片仅缩略图、`{{ product.title }}`、`¥{{ product.price }}`、`成色：{{ product.get_condition_display }}` 四要素，无描述 / 状态 badge / 卖家隐私 / 创建时间。
- `templates/base.html`：在 `navbar-nav ms-auto` 内、`{% if user.is_authenticated %}` 之前纯追加一行 `<a class="nav-link" href="{% url 'product_list' %}">商品浏览</a>`，故匿名 / 已登录均可见；既有导航项、认证徽标、退出表单与分支结构一字未改。`templates/index.html`：在 `{% endif %}` 之后纯追加一个 `href` 指向同目标的「商品浏览」按钮；既有认证引导文案与匿名 / 已登录分支结构一字未改。两处均避开被硬断言的「发布商品」「个人中心」「✓ 已认证」「请注册或登录」「btn btn-outline-primary btn-sm」等文案 / class。
- `listings/tests.py` 末尾追加自包含 `ProductListViewTests`（15 例，独立 `_STORY25_MEDIA_ROOT` + `@override_settings`）：四态混合仅 approved（context + HTML 双重断言 + `visible().count()` 一致）、四要素与首图 URL（3 图只输出 1 个 `<img>`、首图 URL 命中而其余图 URL 不出现）、无图中文占位、有图 / 无图混合、空列表（含仅有 pending 与全空）、倒序（context 与 HTML 双重断言）、匿名 / 已登录已认证 / 已登录未认证三态均 200 且同一份列表、POST / PUT / PATCH / DELETE 405（`Allow: GET, HEAD`）且 DB 快照不变、GET / HEAD 只读、`CaptureQueriesContext` 证明 N=2 与 N=20 查询数相等且 ≤5、 `time.perf_counter` 单次 GET < 1s、他人 approved 可见但无卖家隐私字段、导航 / 首页入口与既有硬断言回归、`my_listings.html` 仍无 `<img>`。
- 验证（`.venv/Scripts/python.exe`，Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0）：`manage.py check` → `System check identified no issues (0 silenced)`；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 2` → 既有 136 例 + 新增 15 例全绿（0 失败 / 跳过）；`git diff -- listings/models.py listings/forms.py listings/admin.py listings/migrations/ config/urls.py config/settings.py requirements.txt accounts/views.py` 为空；`templates/base.html` / `templates/index.html` / `listings/views.py` / `listings/urls.py` 均为纯追加（0 删除）；全仓 `status='approved'` 查询字面量仍只在 `listings/models.py:14` 的 `visible()`。
- 状态口径（沿用 `spec-2-4:112` 的 Step 3 更正）：本轮为 Step 3 实现，本规格 frontmatter `status: 'in-progress'` 与 `sprint-status.yaml` 的 `2-5-商品列表浏览-仅上架: in-progress` 均保持不变（进入 Step 4 独立审查前二者应停留在 `in-progress`）；`in-review` / `review` / `done` 是 Step 4 / Step 5 收尾终态，不在此处提前置入，仅同步 `last_updated`。Execution 六项复选框已勾选，`review_loop_iteration` 保持 0，`## Spec Change Log` / `## Review Triage Log` 按模板保持空节（无 `bad_spec` / loopback）。
- 已知取舍（交付范围外）：2.6 关键词搜索、2.7 分类 / 价格 / 成色筛选、2.8 商品详情（含 `/listings/<pk>/` 与 404 规则）、5.1 / 5.2 审核与下架、Epic 3 聊天、Epic 4 订单均未实现；列表页不分页、不缓存、不加索引，NFR-1 仅由「查询数不随 N 增长」与「单次 GET < 1s」两条机械用例证明；缩略图走 `media/` 原图 + CSS 裁切，不生成新缩略图文件。
- Step 4 / Step 5 收尾：首轮三层审查 23 条原始发现全部驳回（21 `false`、2 `low → rejected`），Clean review、无 `patch` / `defer` / loopback，`review_loop_iteration` 保持 0；本规格 `status` 由 `in-review` 置 `done`，`sprint-status.yaml` 的 `2-5-商品列表浏览-仅上架` 由 `in-progress` 置 `review`（`done` 留待后续独立 `bmad-code-review`，沿用 spec-2-4 惯例），`last_updated` 同步为 `11-11-2026 22:33`。上一条 Implementation Notes 记述的 `in-progress` 是 Step 3 时点快照，以本条为最终口径。

## Spec Change Log

## Review Triage Log

> 2026-11-11 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `71861b9..工作树`，diff 55,193 B / 671 行（含 2 个未跟踪文件）。无跳过层；Blind Hunter 自算 `kB=53.90 → N=8`，实报 20 条；Edge Case Hunter 3 条；Verification Gap 0 条（明确返回 `No verification gaps found.`，其实跑 151 用例 + 15 个新用例 `-v 2`，无发现故不产生行）。共 23 条原始发现，逐条核验后 **23 条驳回（21 `false`、2 `low → rejected`）**，0 `high` / `medium` / `maybe-false`、0 `intent_gap` / `bad_spec` / `patch` / `defer`、无 loopback，`review_loop_iteration` 保持 0 → Clean review。

**Rejected**

- BH-1 `false` — 「记忆日志停在 Step 2 HALT，缺 CHECKPOINT 1 批准记录与状态流转审计」：`.workbuddy/memory/` 是工作流日志而非运行时代码，其 21:25 段是当时时点快照；规格 frontmatter 已按 step-02/03/04 依次流转为 `draft → ready-for-dev → in-progress → in-review`，磁盘与 diff 可核。修复=编辑日志 / 本规格 → 驳回。
- BH-2 `false` — 「spec frontmatter `in-review`、Implementation Notes `in-progress`、sprint `in-progress`、memory `draft` 四处不一致」：step-04 L11 明确要求进入审查前把规格置 `in-review`，sync-sprint-status 只把 sprint 置 `in-progress`，Step 5 才统一；Implementation Notes 是 Step 3 时点快照。与 spec-2-4 BH-1 / EC-3 同类阶段差，修复=编辑本规格 → 驳回。
- BH-3 `false` — 「`<frozen-after-approval>` 缺批准人 / 时间 / 冻结轮次属性」：spec-template.md 的标签本就只有 `reason` 属性；批准时点与六项决策已写入冻结区 `Decision` 段。修复=编辑本规格 → 驳回。
- BH-4 `false` — 「体量度量过期，应补最终 `cl100k_base` 实测值」：8,624 是人类拍板时点的草稿计数、7,875 是决策写入后复核值，均已在 CHECKPOINT 1 向人类明示；实现后新增 Implementation Notes 属 append-only 记录，不改变冻结意图。修复=编辑本规格 → 驳回。
- BH-5 `false` — 「Q1–Q6 未向 `decision-log.md` 追加 D-xxx」：本项目既往 2.3 / 2.4 的人类决策同样写在各自 spec 冻结区而非逐条 D 条目；`decision-log.md` 的 D-034 已承载「列表页留给 2.5–2.8、共用 approved 过滤」的架构级依据。补登记不构成功能缺陷。
- BH-6 `false` — 「缺 AC → Task → `test_*` 可追溯矩阵」：模板无该节；6 条 AC 与 12 行矩阵的覆盖关系已由 Step 3 Matrix Test Audit 逐行核对（15 个新用例在 `-v 2` 输出中逐条 `... ok`）。修复=编辑本规格 → 驳回。
- BH-7 `false` — 「D-029 / D-033 出处未出现在 Code Map」：二者是 `decision-log.md` 中 2.3 / 2.4 的「超长规格保留完整」决策，本规格 `Decision ⑥` 引用其结论而非全文；Code Map 定位的是本次实现需要的文件，不含全部决策条目。修复=编辑本规格 → 驳回。
- BH-8 `false` — 「首图从未被定义、`images.all|first` 依赖默认排序」：冻结决策 ③ 明确「走 `images` 反向关系取首图」；`ProductImage` 无 `Meta.ordering` 时 SQLite 对同一查询按 rowid 稳定返回，`test_card_four_elements_and_first_image_url` 已断言 3 图只输出 1 个 `<img>` 且首图 URL 命中、其余图 URL 不出现。补确定性排序属新增守卫，补定义=编辑本规格 → 驳回。
- BH-9 `false` — 「I/O 矩阵缺 DB 异常 / 并发 / 畸形 Decimal 等负向行」：矩阵 12 行已覆盖四态混合、无图、空列表、只读 405、查询数、计时与回归；DB 异常与并发状态流转在本故事（纯只读、无写路径）无可达生产路径，冻结意图也排除写场景。补行=编辑冻结区 → 驳回。
- BH-10 `false` — 「缺 1 / 5 张图边界与门控不变量自动化断言」：5 张图边界已由 `listings/tests.py:123,243` 既有用例覆盖（2.1），列表页恒定只输出 1 个 `<img>` 与挂图数无关；门控唯一性由 `Verification` 全仓 `status='approved'` 检索 + 主代理独立复跑证明（生产代码仅 `models.py:14`，视图走 `visible()`），当前不存在第二套过滤。补用例=新增测试复杂度且无可达坏结果 → 驳回。
- BH-11 `false` — 「非上架商品缺带图隐私泄露用例」：`visible()` 在视图层已把 `pending / rejected / offline` 排除在 `products` 之外，模板只遍历 `products`，其图片 URL 不可能进入 HTML；`test_only_approved_products_in_context_and_html` 已断言非上架标题 / 价格不出现且 `Product.objects.visible().count()` 与 context 一致。补带图隐藏商品用例不改变结果。
- BH-12 `false` — 「`reverse('resubmit')` 与匿名导航回归缺口」：新 `path('', ...)` 追加在 urlpatterns 末尾，`<int:pk>/resubmit/` 只匹配数字前缀，不会被空路径抢占，2.3 的 21 个既有用例持续覆盖 resubmit；`base.html` 新链接位于 `{% if user.is_authenticated %}` 之前，所有渲染 base.html 的页面均可见，匿名首页已由 `test_nav_and_home_entries_for_all_users` 断言 `href="/listings/"` count=2，而匿名访问 `verify` / `profile` 本就 302 到登录页（既有门控），不是 200 页面。
- BH-13 `false` — 「NFR-1 从 P95 / 首屏 ≤2s 降为单次 GET < 1s，且计时用例 flaky」：冻结决策 ④ 由人类拍板「用查询数不随 N 增长 + 单次 GET < 1s 两条用例证明」，课堂演示环境无法做真实 P95 压测；`test_single_get_under_one_second` 在 20 件含图商品下通过，151 用例 0 失败，未展示 flaky 的坏结果。改口径=编辑冻结区 → 驳回。
- BH-14 `low` → rejected — 「alt 文案、占位 `aria-label`、`<main>` landmark、`loading="lazy"` / CLS 等 a11y 整块缺失」：冻结意图只要求桌面 Chrome/Edge 的 Bootstrap 服务端卡片四要素，`alt="商品缩略图"` 已是中文描述；加 `<main>` 会改 `base.html` 结构（被既有硬断言锁定），`loading="lazy"` / 尺寸属性属新增优化，日常演示不会遇到该缺陷 → 按 `low` 驳回。
- BH-15 `false` — 「Spec Change Log / Review Triage Log 空节」：spec-template.md 明写二者「Empty until the first bad_spec loopback / review pass」；本轮无 `bad_spec` / loopback，Triage Log 正是本轮填写对象，空节是审查前正确状态。修复=编辑本规格 → 驳回。
- BH-16 `false` — 「记忆日志缺 21:46 Step 3 实现段」：工作流日志粒度不属交付范围（2.4 AA-1 同类裁定），主代理在 Step 5 收尾时会补记实现与审查结论。修复=编辑日志 → 驳回。
- BH-17 `false` — 「缺 Definition of Done / handoff 清单」：模板无该节，DoD 由 `Tasks & Acceptance` 的 6 条 AC 与 `Verification` 命令承载，Step 4 输入由 `diff_file` / `claims_file` 承载。补段=编辑本规格 → 驳回。
- BH-18 `false` — 「验证结果只有转述、无原始输出附件」：主代理独立复跑并留日志 `/tmp/story-2-5-test-215200.txt`（`check` 0 issues、`No changes detected`、`Ran 151 tests ... OK`、15 个新用例逐条 `... ok`）；规格模板不要求附日志正文。修复=编辑本规格 → 驳回。
- BH-19 `false` — 「`index.html` 末尾无换行」：`git show HEAD:templates/index.html | od -c` 证明原文件 `{% endblock %}` 后同样无 `\n`，非本故事引入；HTML 末尾换行不产生任何渲染差异。
- BH-20 `low` → rejected — 「`tempfile.mkdtemp` 在模块导入时创建、`ignore_errors=True` 可能泄漏临时目录」：`manage.py check` 不导入测试模块，`manage.py test` 必执行 `tearDownClass` 删除；仅「导入但不运行」的收集场景会留一个空目录，日常不会遇到，改用 `TemporaryDirectory` 属夹具重构 → 按 `low` 驳回。
- EC-1 `false` — 「`ProductImage` 行存在但 `image` 为空时 `thumb.image.url` 抛 ValueError → 公开页 500」：生产中 `ProductImage` 仅在 `listings/views.py:38,85` 创建，参数都是经 `validate_images` 校验的 `request.FILES` 对象（必有文件名）；`listings/admin.py` 裸注册但 `ImageField` 默认 `blank=False`，表单必填且无 Clear 入口；模型中无 `image=''` 写入路径。该状态未被展示为可达，按「未展示可达路径的失败不是缺陷」驳回（与 2.4 EC-3 / EC-4 同口径）。
- EC-2 `false` — 「多图且 `ProductImage` 无排序导致首图不稳定、首图 URL 断言偶发失败」：冻结决策 ③ 指定的就是 `images` 反向关系取首图；SQLite 对无 ORDER BY 的同一查询按 rowid 稳定返回，`test_card_four_elements_and_first_image_url` 已断言首图 URL 命中且只输出 1 个 `<img>`，151 用例中通过。补 `dictsort:"pk"` 属新增排序守卫、无用户可见收益 → 驳回。
- EC-3 `false` — 「`rmtree(ignore_errors=True)` 静默失败致残留图片串入下一用例」：模板渲染的是 DB 里 `ProductImage.image.url` 而非目录扫描；各用例图片 prefix 互异（`first_` / `mixed` / `q2_` / `q20_` / `perf_` / `other`），Django 对同名文件自动加后缀，残留文件不会进入任何断言；151 用例 0 失败 / 0 跳过。声称的坏结果不成立。

**分组与处置：** 无存活项，不产生分组；无 `intent_gap` / `bad_spec` 故不触发 loopback，`review_loop_iteration` 保持 0；无 `patch` 故不重派实现子代理；无 `defer` 故不改 `deferred-work.md`。Verification Gap 层的「无发现」结论与主代理独立复跑（`check` 0 issues、`makemigrations --check` → `No changes detected`、`test -v 2` → 151 tests OK、15 个新用例逐条 `... ok`、禁改文件 diff 为空）一致。

### 2026-11-11 独立重审（第 2 轮，`@skill:bmad-code-review`）

- 基准 `71861b90bf6a..HEAD`（`a3a208a`），统一 diff 68,644 B / 716 行 / 9 文件（+629 / −2）；`review_mode: full`，上下文 `epic-2-context.md` 与 `project-context.md` 均已加载；claims 为 `a3a208a` 的提交信息。
- 激活层：团队级覆盖 `_bmad/custom/bmad-code-review.toml` 禁用 `blind-hunter` / `verification-gap`，本轮实际为 **Edge Case Hunter + Acceptance Auditor** 两层，同步并行、同模型能力，`failed_layers` 为空。Acceptance Auditor 独立复跑后确认六条 AC 与冻结功能约束在代码层面均满足。
- 原始发现 9 条（EC 4 + AA 5），逐条核验后 **9 条全部驳回**（8 `false`、1 `low → rejected`），0 `high` / `medium` / `maybe-false`、0 `decision_needed` / `patch` / `defer`、无 `intent_gap` / `bad_spec` / loopback，`review_loop_iteration` 保持 0 → **Clean review**。
- 主代理独立复跑（`.venv/Scripts/python.exe`）：`manage.py check` → 0 issues；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test` → **151 tests OK**（87.878s，0 失败 / 跳过）。

**Rejected（第 2 轮逐条）**

- EC-1 `false` — 「`ProductImage` 行存在但 `image` 为空时 `thumb.image.url` 抛 ValueError → 公开页 500」：该状态不可达。`ProductImage.image = ImageField(upload_to='products/')` 默认 `blank=False`；全仓唯二写入点 `listings/views.py:38,85` 的实参均来自 `request.FILES.getlist('images')` 且经 `validate_images`（≥1 张、Pillow verify）校验，必有文件名；`listings/admin.py` 裸注册且 ImageField 表单必填、无 clear 入口；`resubmit_view:83` 是整行 `delete()` 不留空行。构造 `image=''` 需绕过 ORM 直接造数，未展示可达生产路径 → 按「未展示可达路径的失败不是缺陷」驳回（与首轮 EC-1 同口径）。
- EC-2 `false` — 「`prefetch('images')` 无 `order_by`、`ProductImage` 无 `Meta.ordering`，首图取哪张由 DB 决定」：冻结决策 ③ 明确授权「走 `images` 反向关系取首图」，即接受 DB 默认顺序；`config/settings.py` 唯一后端为 sqlite3，无 ORDER BY 时按 rowid 稳定返回；151 用例中 `test_card_four_elements_and_first_image_url` 断言首图 URL 命中且只输出 1 个 `<img>`，审查者未展示任何一次首图跳变。补 `Prefetch(order_by('pk'))` 需引入 `ProductImage` import，属新增守卫而非直接更正。
- EC-3 `false` — 「测试 `first_url` 取自无序 `images.all()`，非 SQLite 后端首图 URL 断言可能失败」：`settings.py` 只配置 `django.db.backends.sqlite3`，仓库无 MySQL 配置 / 依赖 / 启用路径（规格亦明确不改 `settings.py`）；测试查询与视图 prefetch 后的 `|first` 是同一无 ORDER BY 查询，顺序一致，151 用例通过。未启用的后端不构成当前交付的坏结果。
- EC-4 `false` — 「`rmtree(ignore_errors=True)` 静默失败致残留 media 串入后续用例」：`setUp`（diff:296）在每个用例开头都重做 `rmtree` + `os.makedirs`，即便 `tearDownClass` 删除失败也会在下一用例前重试清理；模板只渲染 DB 中的 `ProductImage.image.url` 而不扫描目录；各用例图片 prefix 互异（`first_` / `mixed` / `q2_` / `q20_` / `perf_` / `other`），Django 对同名文件自动加后缀；151 用例 0 失败。声称的坏结果不成立。
- AA-1 `false` — 「NFR-1 被降级为单次 GET < 1s，P95 ≤1s 与首屏 ≤2s 无任何覆盖」：AC-3 与冻结决策 ④ 已由人类于 21:25 拍板把本故事的可执行口径定为「查询数不随 N 增长 + 单次 GET < 1s」，代码与 `test_single_get_under_one_second` 完全符合 AC-3；`prd.md` 的 P95 / 首屏是上游指标，Implementation Notes 已将其列为交付范围外取舍。修复 = 编辑冻结规格 / PRD → 驳回（与首轮 BH-13 同口径）。
- AA-2 `false` — 「规格声称 Step 4 三层同步并行无跳过层，与团队配置禁用两层矛盾，审计链不自洽」：两套工作流被混淆。团队覆盖文件按 skill-name 只作用于独立 `bmad-code-review`；Step 4 属 `bmad-build` 工作流，其 `.workbuddy/skills/bmad-build/customize.toml` 内置 `blind-hunter` / `edge-case-hunter` / `verification-gap` 三层，且 `_bmad/custom/` 下无 `bmad-build.toml` 覆盖文件（已核）。20 条 BH 发现可由 Step 4 正常产生；记忆日志 L6 的「两层」记述的是 2.4 的独立重审，轮次不同。修复 = 编辑本规格 → 驳回。
- AA-3 `false` — 「新增测试大量 `status='approved'` 字面量，与冻结 Always『全仓字面量只在 `models.py:14`』冲突」：该条款约束的是「不得另写第二套门控」，Implementation Notes:157 与 Verification:214 已分别限定为「**查询**字面量」与「**生产代码**」；新增测试中的字面量全部是夹具赋值与状态断言（`p.status == 'approved'`），无一处用于查询过滤，AC-1 本身还强制该断言；生产代码检索结论可复现（视图走 `visible()`、`models.py:14` 唯一过滤）。不变量未破，修复 = 编辑本规格 → 驳回。
- AA-4 `false` — 「frontmatter `status: done` 与 Implementation Notes 自述 `in-progress` 互相否定」：Implementation Notes:160 已明写「上一条记述的 `in-progress` 是 Step 3 时点快照，以本条为最终口径」；`done` / `review` 是 Step 5 收尾终态，与记忆日志 L36 一致。sprint diff 显示 `backlog → review` 只因单 commit 内的过程态未单独提交，不是流转错误。修复 = 订正规格记述 → 驳回（与 2.4 AA-3 同口径）。
- AA-5 `low` → rejected — 「I/O 矩阵首图行要求 1–5 张图，用例只构造 3 张，缺 1 / 5 图边界」：事实成立，但模板 `product.images.all|first` 恒定只输出 1 个 `<img>`，与挂图数无关，属测试覆盖缺口而非功能缺陷；5 图边界已由 2.1 既有用例 `listings/tests.py:123,243` 覆盖，151 用例全绿。补 1 / 5 图用例属新增测试复杂度，日常演示不会遇到 → 按 `low` 驳回（与首轮 BH-10 同口径）。

**分组与处置（本轮）：** 无存活项，不分组、不产生 `### Review Findings` action items、不改 `deferred-work.md`、不重派实现子代理；`new_status = done`，sprint `2-5-商品列表浏览-仅上架` 由 `review` 置 `done`，`last_updated` 同步为 `11-11-2026 23:11`。规格 frontmatter 已是 `done`，本轮不修改冻结区与 Implementation Notes 旧条（append-only）。

## Design Notes

- **Step 2 事实与路径判定**：Intent gaps 原为 6 项（Q1 页面形态与 URL、Q2 访问门控、Q3 缩略图实现、Q4 列表规模与 NFR-1 口径、Q5 入口位置、Q6 规格体量），已由人类于 2026-11-11 21:25 全部拍板为 A / A / A / A / A / A 并写入冻结区 Decision ①–⑥；token gate 同轮选择 **Keep full spec**（接受 8,624 tokens 的 context-rot 风险，不拆分、不新增 deferred 项，沿用 D-029 / D-033 / D-034，由 Step 4 三层审查兜底）。Irreversibles = **无**（不新增迁移 / schema 变更、不删除或改写数据、不写 `media/`、无外部副作用，列表页是纯只读消费者）；Footprint ≈ 6 个文件（新增 1 视图 / 1 URL / 1 模板 / 1 测试类 + 2 个共享模板的入口追加），新增 1 个对外公开路由与 1 个模板，`base.html` / `index.html` 是 Epic 3/4 也依赖的共享表面。故 `route: dispatch`、写完整规格，不走 oneshot（与 spec-2-3、spec-2-4 一致）。
- **门控唯一性**：D-034 明确「2.2 只做模型层，列表页留给 2.5–2.8，共用同一套 approved 过滤」；2.5 是对外侧**首次**消费 `visible()`。视图里出现任何 `filter(status=...)` 都意味着第二套门控，必须避免；`visible()` 保持可链式，2.6 / 2.7 后续在同一 queryset 上叠加 `filter()`。
- **缩略图不改模型**：AC 要求「含缩略图」但未要求生成新文件；`ProductImage` 无首图 property，模板走 `images` 反向关系 + `prefetch_related` 即可，既满足四要素又不触碰模型层与迁移。CSS 裁切只影响展示尺寸，不改变 `media/` 中已存的原图（与 D-021「本地 media + Pillow 校验」不冲突）。
- **NFR-1 的可执行证据**：课堂演示规模下无法做真实 P95 压测，故用两条机械证据替代——`assertNumQueries`（或等价方式）证明查询数不随商品数线性增长，以及 `time.perf_counter` 断言单次 GET < 1s；不引入缓存 / 索引 / 分页配置，避免为演示环境过度设计。
- **共享表面回归**：`templates/index.html` 与 `templates/base.html` 被 `accounts/tests.py` 62 例与 `listings/tests.py` 74 例中的多处 `assertContains` / `count=1` / `assertNotContains` 锁定；入口只做**追加**，不复用「发布商品」「个人中心」「✓ 已认证」「请注册或登录」等被断言文案，也不改变匿名 / 已登录分支结构。
- **卖家侧与买家侧分界**：`my_listings_view` 用基础查询集按 `owner` 过滤（2.4 冻结区明确「不得调用 `visible()`」），列表页用 `visible()` 且**不按 owner 过滤**（买家要看到所有人的已上架商品）；两者是互补的两类查询，不得互相替换，也不得把卖家隐私字段带进公开页。
- **演示数据**：沿用 2.1–2.4 惯例，不往运行时 `db.sqlite3` / `media/` 造数；四态与有图 / 无图组合全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（本次不改模型）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 136 例 + 本故事新增用例全绿，无失败 / 跳过；新用例逐条 `... ok`
- `git diff --name-status` 及 `git diff -- listings/models.py listings/forms.py listings/admin.py listings/migrations/ config/urls.py config/settings.py requirements.txt accounts/views.py` — expected: 上述文件 diff 为空
- `git status --porcelain=v1` — expected: 仅含本故事交付文件与本规格 / sprint 状态文件
- 全仓 `status='approved'` 字面量检索 — expected: 生产代码仍只在 `listings/models.py:14`

**Manual checks (if no CLI):**
- 构造若干 `approved` 商品（含有图 / 无图）与 `pending / rejected / offline` 各一件，打开商品列表页核对四要素、中文占位、倒序与非上架商品完全不可见；退出登录后确认匿名访问仍 200；从首页与导航栏各点一次「商品浏览」确认可达。
