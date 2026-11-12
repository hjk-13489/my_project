---
title: '分类/价格/成色筛选'
type: 'feature'
created: '2026-11-12'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 150e288d31c298002f74c78eba81195093431129
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 2.6 已交付公开列表页 `/listings/?q=` 的关键词搜索，但 `listings/views.py:125-141` 的 `product_list_view` 只消费 `q` 一个 GET 参数（注释 `:117-123` 明示「其余参数一律忽略，为 2.7 组合筛选预留」），`templates/listings/product_list.html:28-35` 只有搜索表单，全仓无 `category` / `condition` / `price__gte` / `price__lte` 消费；`stories.md:123-129`、`epics.md:319-331`、`prd.md:182-187`（FR-11）要求的「买家按分类、价格区间、成色组合筛选，结果仅含满足全部条件的商品，且仅 `approved`」既无入口也无可执行证据，Epic 2 买家链路（列表 → 搜索 → 筛选 → 详情）断在第三环。

**Approach:** 在 2.6 同一个公开只读列表页 `/listings/`、同一条查询集上以 GET 参数叠加分类 / 价格闭区间 / 成色筛选：视图在 `Product.objects.visible()` 唯一门控之后，把各条件以 AND 链式叠加在既有 `q` 关键词链旁，保留 `prefetch_related('images')` 与 `Meta.ordering`；模板纯追加中文筛选表单、控件回显、结果计数与清空链接。不改模型 / 路由 / 配置、不产生迁移、不引入索引与缓存、不实现 2.8，让筛选与搜索在同一页共存。

**Decision（人类决策，2026-11-12 21:59，全部按推荐）:** ① Q1=A：**`q` 与筛选条件在同一 queryset 上全量 AND 叠加**，结果须同时满足「标题或描述包含 `q`」与全部有效筛选条件；筛选表单以隐藏域保留 `q`，先搜索再筛选不丢词；2.6 搜索表单一字不改，故提交搜索会清除筛选参数（本决策的固有结果）。不采用「筛选优先忽略 `q`」或「叠加但 UI 不回显 `q`」。② Q2=A：**逐条静默忽略无效条件** —— 每个参数独立归一化与校验（`strip()` 后空串视为未提供、枚举白名单、`Decimal` 解析、非负、`lo > hi` 时整对价格条件忽略），无效者不叠加 filter，其余有效条件照常 AND 生效，页面恒 200；不返回 400、不因非法值直接返回空结果集、不抛 `InvalidOperation` / `ValidationError`；只填价格一端时按该端叠加、另一端不约束。与 2.6 空 `q` 归一化「退回全量」同口径。③ Q3=A：**完整筛选表单** —— 纯追加在 `templates/listings/product_list.html` 的 2.6 搜索表单之后、卡片循环之前：分类下拉（含「全部分类」空选项）、成色下拉（含「全部成色」空选项）、最低价 / 最高价两个数字输入框、「筛选」提交按钮、各控件回显、`filter_active` 时的「清空筛选」链接；Bootstrap 服务端渲染、全中文；不新增模板文件 / 静态资源，不动 `base.html` / `index.html` / 卡片结构。不采用极简（价格仅靠 URL）或折叠面板。④ Q4=A：**双态并存、搜索文案一字不改** —— 新增 `filter_active`；「找到 {{ result_count }} 件商品」在任一检索态恒定显示（0 命中也显示「找到 0 件商品」，与 2.6 冻结决策 ③ 同口径）；`search_active` 时 2.6 的「清空搜索」「没有找到与「XXX」相关的商品」字面与触发条件**完全不变**；仅当 `filter_active and not search_active and not result_count` 时显示新文案「没有符合筛选条件的商品」，不渲染卡片、不复用「暂无上架商品」；`filter_active` 时显示「清空筛选」链接，仅清除 4 个筛选参数并保留 `q`（无 `q` 时指向 `/listings/`），2.6 既有「清空搜索」节点及其 `/listings/` 指向一字不改。为满足「纯追加」，计数在 `search_active` 时由 2.6 既有块输出、在纯筛选态由新增互斥块输出，用户任一检索态恰好看到一次；**不得修改 2.6 的 `{% if search_active %}` 块条件**。⑤ Token gate = **Keep full spec**：本规格为单一用户目标（分类 / 价格 / 成色组合筛选），跨层实现不可拆，不拆分、不新增 `deferred-work.md` 条目，沿用 D-029 / D-033 / D-038；起草时点按 `cl100k_base` 统计 **11,668 tokens**（19,959 字符 / 149 行），**接受超 1600 门槛的 context-rot 风险**，由 Step 4 三层审查兜底。以上五项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 对外商品查询**唯一入口**是 `Product.objects.visible()`（`listings/models.py:12-14`，`filter(status='approved')`）；所有筛选条件必须链式叠加在它之后，全仓生产代码不得出现第二套 `status` 过滤字面量，视图 / 模板 / 测试不得另写门控（AD-9 `architecture.md:115`、D-034 `decision-log.md:393`、spec-2-5 L27、spec-2-6 L27/L146）。
- 沿用 2.5 冻结决策 ①（spec-2-5 L22）：不新增 URL 路由、不新增 `app_name`、不改 `listings/urls.py` 与 `config/urls.py`，筛选仍走 `reverse('product_list') == '/listings/'`（`listings/tests.py:1454` 硬断言）；表单为 `method="get"`。
- 列表页保持公开只读：`@require_safe`（`listings/views.py:124`），**不加** `@login_required`、不要求 `is_verified`，匿名 / 已登录 / 已登录未认证 GET 均 200；非 GET/HEAD 405（`Allow: GET, HEAD`）且无任何 DB / `media/` 写入。
- **组合语义**：4 个筛选参数固定为 `category` / `condition` / `min_price` / `max_price`，与既有 `q` 同处一条 queryset；所有**有效**条件以 AND 叠加，结果必须同时满足「标题或描述包含 `q`」（有 `q` 时）、分类、价格闭区间、成色（`stories.md:127-128` 的 `assert all(p.category == c and lo <= p.price <= hi and p.condition == cond for p in results)`、`epics.md:329`、`prd.md:187`），且仅 `status='approved'`。筛选表单以隐藏域携带 `q`，提交筛选后搜索词不丢失；2.6 搜索表单一字不改。
- **枚举、值域与容错**：分类取 `CATEGORY_CHOICES`（`listings/models.py:20-25` = 教材 / 日用品 / 电子数码 / 其他）、成色取 `CONDITION_CHOICES`（`:26-30` = 全新 / 良好 / 中等）；价格为 `DecimalField(10,2)`（`:54`），区间为**闭区间** `lo <= price <= hi`（`stories.md:128`）。每个参数独立归一化与校验（`strip()` 后空串视为未提供、枚举白名单、`Decimal` 解析、非负、`lo > hi` 时整对价格条件忽略）；**无效者静默忽略、不叠加 filter**，其余有效条件照常生效，页面恒 200，不返回 400、不因非法值直接返回空集、不抛 `InvalidOperation` / `ValidationError`。越界值不得进入 ORM 查询条件。
- 只经 Django ORM 参数化查询，禁止原始 SQL / 字符串拼接；`request.GET` 仅用于 `q` 与 4 个筛选参数，不用于排序、分页、状态或其他用途；表单回显交给 Django 模板自动转义，不输出未转义的 `|safe`、不做高亮。
- 保留 `Product.objects.visible().prefetch_related('images')` 的图片预取（`views.py:134`）与 `Product.Meta.ordering = ('-created_at',)`（`:69`）；不引入分页 / 条数截断 / 缓存 / 数据库索引 / 新配置项 / 新第三方依赖 / 新模板文件 / 静态资源。
- 卡片四要素（缩略图或中文「暂无图片」占位、标题、`¥{{ product.price }}`、`get_condition_display()` 中文成色）、`images.all|first` 首图取法、CSS 裁切、既有空态「暂无上架商品」、页面标题「商品浏览」、2.6 搜索表单与「找到 N 件商品」/「清空搜索」/「没有找到与「XXX」相关的商品」全部**一字不改**，筛选 UI 纯追加。
- **结果语境双态**：新增 `filter_active`；「找到 {{ result_count }} 件商品」在任一检索态（`search_active` 或 `filter_active`）恒定显示（0 命中也显示「找到 0 件商品」）；`search_active` 时 2.6 的「清空搜索」「没有找到与「XXX」相关的商品」字面与触发条件完全不变；仅当 `filter_active and not search_active and not result_count` 时显示新文案「没有符合筛选条件的商品」，不渲染卡片、不复用「暂无上架商品」；`filter_active` 时显示「清空筛选」链接，仅清除 4 个筛选参数并保留 `q`（无 `q` 时指向 `/listings/`）。2.6 的 `{% if search_active %}` 块条件不得修改，上述新增语义全部由**纯追加的互斥分支**承载。
- `templates/base.html` / `templates/index.html` **完全不动**；首页与导航栏继续沿用「商品浏览」入口，收尾时二者 diff 必须为空。
- 服务端渲染 + Bootstrap 5.3.3 CDN + 全中文用户可见文案（`LANGUAGE_CODE='en-us'` 不自译）。
- 既有 **173** 个用例一字不改且全绿（`listings/tests.py` 6 类 / 111 例 + `accounts/tests.py` 62 例），尤其 `listings/tests.py:1282,1299,1311,1321-1322,1454,1462,1690-1693,1759-1760,1774-1780,1844,1873,1977-1980` 与 `accounts/tests.py:677-688` 的 HTML / 导航硬断言不破。
- 不产生迁移、不改模型 / 表单 / admin / 既有迁移 / `config/settings.py` / `requirements.txt` / `accounts/views.py` / 既有 listing 模板；`manage.py check` → 0 issues，`makemigrations --check --dry-run` → `No changes detected`。
- 不往运行时 `db.sqlite3` / `media/` 造演示数据；四态、有图 / 无图、命中 / 不命中与各类非法输入组合全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。
- NFR-1 沿用 2.5 决策 ④ 的可执行口径（spec-2-5 L22、spec-2-6 L104/L144）：`CaptureQueriesContext` 证明查询数不随 N 增长 + `time.perf_counter` 断言单次 GET < 1s；不引入缓存 / 索引 / 分页。

**Never:**
- 不实现 2.8 商品详情页（含 `/listings/<pk>/` 与 404 规则）、5.1 / 5.2 审核区与下架、Epic 3 聊天、Epic 4 订单；不新增「联系卖家」「立即购买」入口。
- 不改 `listings/models.py`（`visible()` / `CATEGORY_CHOICES` / `CONDITION_CHOICES` / `STATUS_CHOICES` / `ALLOWED_TRANSITIONS` / `_transition()` / `ProductImage` / `RejectionNotice`）、`listings/forms.py`、`listings/admin.py`、`listings/migrations/`、`listings/urls.py`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`accounts/views.py`、`templates/base.html`、`templates/index.html`、`templates/listings/my_listings.html`、`publish.html`、`resubmit.html`、`templates/accounts/profile.html`。
- 不新增模型字段 / property / 方法、不生成缩略图文件、不改图片上传校验与 `ProductImage` 存储路径；不新增写路径、不改 `status`、不写 `media/`。
- 不把 `pending / rejected / offline` 商品以任何形式（隐藏、占位、注释、上下文变量）带进模板；不泄露未上架商品的标题 / 描述 / 价格 / 图片 URL / 卖家信息。
- 不引入全文检索引擎、独立筛选结果页 / 新路由 / API / SPA / WebSocket / 新静态资源 / 新模板文件 / 第二套可见性判断；不改写卡片渲染结构以承载非 AC 内容。
- 不实现排序切换、结果分页、条数截断、关键词高亮、价格滑块、多选分类 / 多选成色；不新增「重置为全站」以外的状态语义。
- 不修改 2.6 的 `{% if search_active %}` 块条件与 `{% url 'product_list' %}` 的「清空搜索」指向；不把「清空筛选」实现为清除 `q`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 单条件分类 | 仅 `category=教材`，库中有各分类 `approved` 商品 | 结果全为 `category='教材'` 且 `approved`，其余条件不叠加 | `visible()` 门控 + 链式 filter |
| 单条件成色 | 仅 `condition=全新` | 结果全为 `condition='全新'` 且 `approved` | 同上 |
| 价格闭区间 | 仅 `min_price=10` + `max_price=100`，含边界值 10 / 100 的商品 | 两端点商品均命中（`lo <= price <= hi`），区间外不出现 | `Decimal` 比较，不经字符串比较 |
| 半区间 | 仅 `min_price=10` / 仅 `max_price=100` | 按已提供的一端叠加，另一端不约束 | 缺失端不叠加 filter |
| 三条件组合 | `category` + `condition` + `min_price/max_price` 同时给出 | 结果满足**全部**条件（AND），`assert all(p.category == c and lo <= p.price <= hi and p.condition == cond ...)` 成立 | 逐条链式 filter |
| 与关键词叠加 | `q=教材` + 三条件同时给出 | 结果同时满足「标题或描述包含 `q`」与全部筛选条件，仅 `approved`；筛选表单隐藏域回显 `q`、提交后不丢词 | `Q(...)` 链与筛选 filter 共存于同一 queryset |
| 双字段与四态混合 | 库中同时有命中 / 不命中 × `pending / approved / rejected / offline` | 仅「命中全部条件且 `approved`」出现；`all(p.status == 'approved' for p in results)` 成立 | 服务端强制过滤 |
| 非上架不泄露 | `pending / rejected / offline` 商品恰好满足全部筛选条件 | 其标题 / 描述 / 价格 / 图片 URL 均不出现在 HTML 与 context；`visible().count()` 与结果一致 | `visible()` 门控 |
| 卡片与排序 | 多件命中商品，含图 / 无图混合，`created_at` 互异 | 每卡片仍含缩略图或中文占位、标题、`¥` 价格、中文成色；按 `-created_at` 倒序；每张卡片只输出 1 个 `<img>` | `prefetch_related` 消 N+1 |
| 非法枚举值 | `category=不存在` / `condition=九成新` | 该条件被静默忽略，其余有效条件照常 AND 叠加，页面 200，不产生 500 / 400 | 枚举白名单 |
| 非数字价格 | `min_price=abc` / `max_price=` 乱码 | 该价格条件被静默忽略，其余有效条件照常生效，不触发 `ValidationError` / `InvalidOperation` 冒泡 | `Decimal` 解析守卫 |
| 负价格 / 倒置区间 | `min_price=-5` / `min_price=200&max_price=10` | 负价端或倒置时整对价格条件被静默忽略，其余有效条件照常 AND 生效，页面 200、不返回 400、不直接呈现空结果集、不报错、不泄露数据 | 逐条独立校验 |
| 空串与首尾空白 | `category=''` / `condition=%20` / `min_price=%20%20` | `strip()` 归一化为「未提供」，退回不叠加该条件 | 输入归一化 |
| 无参数回归 | GET `/listings/`（2.5 / 2.6 原始形态） | 与 2.6 完全一致的全量上架列表与「暂无上架商品」空态，既有 173 例断言不变 | 不叠加过滤 |
| 仅 q 回归 | GET `/listings/?q=教材` | 与 2.6 搜索态**完全一致**：回显、找到 N 件、清空搜索、无结果文案、结果集均不变；不出现「清空筛选」与筛选态文案 | 筛选链不介入 |
| 结果语境与回显 | 有筛选条件且命中 K 件 | 各控件回显已归一化取值、显示「找到 K 件商品」、`filter_active` 时显示「清空筛选」链接（仅清除筛选参数、保留 `q`）；0 命中时计数仍显示 | 纯追加模板节点 |
| 无匹配结果 | 有筛选条件但 0 件命中（库中另有未上架且满足条件的商品） | 纯筛选态显示「没有符合筛选条件的商品」、`search_active` 时沿用 2.6「没有找到与「XXX」相关的商品」；均不渲染卡片、不出现「暂无上架商品」、不泄露未上架商品 | 筛选态空分支 |
| 转义 | `category=<script>alert(1)</script>` / `q=%_` | 回显为 HTML 转义形式，页面不执行脚本；`%` / `_` 被 ORM 转义为字面量 | 模板自动转义 + 参数化查询 |
| 查询数 | N=2 与 N=20 件命中商品（含图） | 查询数不随商品数增长（图片预取仍生效） | 预取一次取图 |
| 响应时间 | 演示规模 N 件命中商品 | 单次 GET 耗时 < 1s（NFR-1，`time.perf_counter` 计时断言） | 性能用例 |
| 访问门控 | 匿名 / 已登录已认证 / 已登录未认证携带筛选参数 GET | 三者均 200，看到同一份命中且仅 `approved` 的列表 | 无 |
| 只读方法 | 携带筛选参数的 POST / PUT / PATCH / DELETE | 405（`Allow: GET, HEAD`），无任何 DB / `media/` 写入 | `require_safe` |
| 回归 | 既有 173 例 + 首页 / 导航 / 我的发布硬断言 | 全绿，既有文案与链接不变；`base.html` / `index.html` diff 为空 | 全量回归 |

</frozen-after-approval>

## Code Map

- `listings/models.py` — `ProductQuerySet.visible()` `:12-14` = `filter(status='approved')`，**对外可见性唯一定义、一字不改**；可链式，所有筛选条件必须叠加在它之后。`CATEGORY_CHOICES` `:20-25` = 教材 / 日用品 / 电子数码 / 其他（存储值即中文词）；`CONDITION_CHOICES` `:26-30` = 全新 / 良好 / 中等；`STATUS_CHOICES` `:31-36`；字段 `title:52` / `description:53` / `price:54`（`DecimalField(10,2)`）/ `condition:55` / `category:56` / `status:57-59` / `created_at:60`；`objects:64`、`Meta.ordering=('-created_at',):69`、`ProductImage` 反向关系 `images:116`。
- `listings/views.py:116-141` — `product_list_view` 现状：`@require_safe:124`（**无** `@login_required`）；注释 `:117-123` 明示「其余参数一律忽略，为 2.7 组合筛选预留」；`search_query = request.GET.get('q','').strip():127`、`search_active:128`、`products_qs = Product.objects.visible():129`、`if search_active:` 链式 `.filter(Q(title__icontains=...) | Q(description__icontains=...)):130-133`、`list(products_qs.prefetch_related('images')):134`；上下文 `:135-141` = `products` / `products_empty`(`not products`) / `search_query` / `search_active` / `result_count`(`len(products)`)。本故事在**唯一视图**内追加 4 个 GET 参数读取与 AND 链式 filter，保留门控 / `q` 链 / 预取 / 排序；`my_listings_view:108-113` 的 `filter(owner=...)` 是卖家侧范式，**不得**照抄。导入 `Q:3`、`require_safe:5`。
- `listings/urls.py:4-9` — 4 条路由，无 `app_name`，`path('', views.product_list_view, name='product_list'):8` → `reverse('product_list') == '/listings/'`（`listings/tests.py:1454` 硬断言）。**不改**：筛选复用同一路由。`config/urls.py:31,34,38-39`（home / listings include / DEBUG `static()`，被 `listings/tests.py:305` 断言）同样不改。
- `templates/listings/product_list.html:1-72` — `extends 'base.html':1`；`block title:3` / `block content:5`；`<style>` 裁切 `:6-20`；`h2`「商品浏览」`:22-26`；2.6 搜索表单 `method="get" action="{% url 'product_list' %}"` `:28-35`（`name="q" value="{{ search_query }}":30`、「搜索」按钮 `:33`）；`{% if search_active %}` 结果语境块 `:37-42`（「找到 {{ result_count }} 件商品」`:39`、「清空搜索」`:40`）；搜索无结果 `:44-45`「没有找到与「{{ search_query }}」相关的商品」；`products_empty` 分支 `:47-48`「暂无上架商品」；卡片网格 `:50-69`（`product.images.all|first:54`、`<img>:56`、中文占位 `:58`、四要素 `:62-64`）。筛选 UI 须**纯追加**在搜索表单之后、卡片循环之前，上述所有既有节点与文案一字不改；`{% if search_active %}` 块条件不得修改，筛选态语境用互斥的追加分支承载。
- `templates/base.html:14` / `templates/index.html:30` — 「商品浏览」入口，`href="{% url 'product_list' %}"`；被 `listings/tests.py:1462,1979` 断言 `href="/listings/" count=2`。冻结约束要求二者**完全不动**，收尾时其 diff 必须为空。
- `listings/tests.py`（1984 行 / 111 例）— 6 类：`PublishViewTests:30`(28)、`ProductVisibilityTests:379`(12)、`RejectionNoticeAndResubmitTests:554`(21)、`MyListingsViewTests:896`(13)、`ProductListViewTests:1175`(15)、`ProductSearchViewTests:1526`(22)。模块级自包含夹具：`_STORY25_MEDIA_ROOT:1163` / `_story25_image:1166` / `_STORY26_MEDIA_ROOT:1514` / `_story26_image:1517`（均 `tempfile.mkdtemp`）；类级 `@override_settings(MEDIA_ROOT=...):1174,1525`。`ProductSearchViewTests` 可复用范式：`_make_product:1549`、`_attach_images:1561`、`_set_created_at:1567`、`_snapshot:1572`、`_media_snapshot:1580`、`_get:1589`、`_count_queries_for_get:1594`。硬断言：暂无上架商品 `:1321,1330,1691,1765,1775,1844,1873`、暂无图片 `:1299,1312,1729`、`<img count=1>:1282,1311`、¥ `:1287,1302,1730-1732`、中文成色 `:1288,1303,1619`、`找到 N 件商品` `:1759,1780,1816`、`没有找到与` `:1690,1774,1794`、`清空搜索` `:1760,1832,1846,1864,1977`、`href="/listings/" count=2` `:1462,1979`、`card h-100` 不出现 `:1322,1692,1778,1875`。**新测试类追加在文件末尾**，既有 111 例一字不改。
- `accounts/tests.py:677-688`（62 例）— 遍历 home / verify / profile 断言个人中心链接与匿名页 `assertNotContains`；`:100,135,448-462` 认证引导 / 徽标文案。共享模板改动会破坏这些断言。
- `config/settings.py:64`（TEMPLATES DIRS）、`:68`（request context）、`:82-87`（sqlite3 唯一后端）、`:112`（`en-us`）、`:118`（`USE_TZ=True`）、`:128-129`（MEDIA）、`:137`（`AUTH_USER_MODEL`）— 全部不改；`requirements.txt:3-4` = Django 5.2.19 / Pillow 13.0.0，不新增依赖。
- 规划依据：`stories.md:123-129`（2.7 故事 / AC / `assert all(p.category == c and lo <= p.price <= hi and p.condition == cond ...)` / AD-9、AD-2、FR-11）、`:110-112,119-120`（2.5 / 2.6 的 approved 门控）、`:75`（枚举）；`epics.md:29`（FR11 组合筛选）、`:73`（枚举与 Decimal 约定）、`:241`、`:301`（NFR-1 ≤1s）、`:319-331`（2.7 AC 含 `且仅限 status='approved'`）；`prds/prd-my_project-2026-11-04/prd.md:182-187`（FR-11）、`:143-147,173`（先审后上架）、`:352-354`（NFR-1）、`:362-364`（NFR-3）；`architecture-*/architecture.md:55-61`（AD-2 ORM）、`:71-77`（AD-4 服务端授权）、`:111-117`（AD-9 列表与搜索服务端强制 approved）、`:131-133`（枚举约定）、`:214`（FR-9~FR-12 归 listings）。
- 前序与决策：`spec-2-5-商品列表浏览-仅上架.md` 冻结区 Decision ①（`2.6 / 2.7 在同一页叠加查询参数，2.8 详情沿 /listings/<pk>/`）、④（NFR-1 口径）、⑥（Keep full spec）、`L20,27,34,36,40-41,176-177`；`spec-2-6-关键词搜索.md` 冻结区 Decision ①–⑤（`:22`）、`L20,27-35,42-48,110-116,144-150`（尤其 L47「不实现与 2.7 筛选的组合行为」、L147「未识别的其他 GET 参数一律忽略，为 2.7 预留组合空间」）；`decision-log.md:333-341`（D-029）、`:377-385`（D-033）、`:388-396`（D-034 2.5–2.8 共用同一套 approved 过滤）、`:399-407`（D-035）、`:432-440`（D-038）、`:268`（D-023 成色取值）；`epic-2-context.md:25-28,34-36,51`（可见性门控、枚举、跨故事依赖）。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:54` — `2-7-分类-价格-成色筛选: backlog`，`:32` `last_updated: 11-12-2026 18:46`，`:48-55` 其余 Epic 2 条目；收尾时按工作流同步本故事状态与 `last_updated`，不改其他故事条目。`deferred-work.md` 现有 10 条全部属 Epic 1，无 2.5–2.8 条目。
- `.venv/Scripts/python.exe` — Python / Django 5.2.19 / Pillow 13.0.0；系统 PATH 的 `python` 无 Django，验证一律用该解释器。HEAD `150e288d31c298002f74c78eba81195093431129`（`完成了2.6`），工作树干净，分支 `master`。

## Tasks & Acceptance

**Execution:**
- [x] `listings/views.py` — 在 `product_list_view` 内读取并归一化 4 个筛选 GET 参数，逐条校验（`strip()` 后空串视为未提供、枚举白名单、`Decimal` 解析、非负、`lo > hi` 时整对价格条件忽略），无效者静默忽略；把有效条件以 AND 链式叠加在 `Product.objects.visible()`（及既有 `q` 链）之后，保留 `prefetch_related('images')` 与默认排序，构造筛选回显 / `filter_active` / `result_count` 上下文；不写 `status` 字面量、不引入第二套门控、不消费其他请求参数 — 兑现 FR-11、AD-9、冻结决策 ① / ② 与「结果满足全部条件」。
- [x] `templates/listings/product_list.html` — 在 2.6 搜索表单之后**纯追加**中文 GET 筛选表单（隐藏域 `q`、分类 / 成色下拉含「全部」空选项、最低价 / 最高价输入、提交按钮、控件回显）、互斥的纯筛选态结果计数、`filter_active` 时的「清空筛选」链接（保留 `q`）、以及 `filter_active and not search_active and not result_count` 时的「没有符合筛选条件的商品」；2.6 的 `{% if search_active %}` 块条件、搜索表单、三处搜索态文案、卡片四要素、首图取法、CSS、既有空态「暂无上架商品」、页面标题与 `products_empty` 分支一字不改 — 兑现冻结决策 ③ / ④ 与「无匹配 vs 无商品」区分。
- [x] `listings/tests.py` — 末尾追加自包含 `ProductFilterViewTests`（独立临时 `MEDIA_ROOT`、图片构造 helper），覆盖矩阵全部行：单条件 / 半区间 / 三条件 AND 组合 / 与 `q` 叠加且不丢词 / 四态混合仅 approved / 非上架不泄露 / 卡片四要素与倒序 / 非法枚举与非数字与负价与倒置区间 / 空串与首尾空白 / 无参数与仅 `q` 回归 2.5–2.6 / 结果语境与回显与清空筛选 / 筛选态无结果提示 / 转义 / 查询数不随 N 增长 / 单次 GET < 1s / 三类访问门控 / 只读 405 且无写入 / 既有 173 例全量回归；既有 173 例一字不改 — 冻结验收的可执行证据。
- [x] `spec-2-7-分类-价格-成色筛选.md` 与 `sprint-status.yaml` — 按工作流同步状态（`2-7-分类-价格-成色筛选`）与 `last_updated`，不改其他故事条目 — 工作流收尾。

**Acceptance Criteria:**
- Given 库中同时有 `pending / approved / rejected / offline` 且条件命中 / 不命中混合的商品，When 以分类 + 价格区间 + 成色组合 GET `/listings/`，Then 结果仅含「满足全部条件且 `approved`」的商品，`all(p.category == c and lo <= p.price <= hi and p.condition == cond for p in results)` 与 `all(p.status == 'approved' for p in results)` 同时成立，且 `visible()` 仍是全仓唯一 approved 门控（FR-11 / AD-9 / NFR-3）。
- Given 只提供部分筛选条件或只填价格区间一端，When GET 列表页，Then 已提供条件按 AND 生效、缺失条件不叠加、价格按 `Decimal` 闭区间比较（含端点），页面恒 200 且无异常。
- Given 非法枚举值 / 非数字价格 / 负价格 / 倒置区间 / 空串 / 首尾空白，When GET 列表页，Then 无效条件被逐条静默忽略、其余有效条件照常 AND 生效、页面恒 200、不抛异常、不返回 400、不因非法值直接呈现空结果集、不泄露未上架商品。
- Given 同时携带 `q` 与筛选参数，When GET 列表页，Then `q` 与全部有效筛选条件在同一 queryset 上 AND 叠加、结果同时满足两者且仅 `approved`，筛选表单以隐藏域保留 `q`、提交筛选后搜索词不丢失；Given 仅携带 `q` 或完全无参数，Then 与 2.6 / 2.5 行为完全一致（既有 173 例断言不破）。
- Given 命中商品含图 / 无图两种，When 查看结果卡片，Then 每张仍含缩略图或中文「暂无图片」占位、标题、`¥` + Decimal 价格、`get_condition_display()` 中文成色，按 `-created_at` 倒序，且每张只输出 1 个 `<img>`。
- Given 有筛选条件且命中 K 件，When GET 列表页，Then 各控件回显归一化取值、显示「找到 K 件商品」与「清空筛选」链接（仅清除筛选参数、保留 `q`）；Given 有筛选但 0 件命中，Then 纯筛选态显示「没有符合筛选条件的商品」、`search_active` 时沿用 2.6「没有找到与「XXX」相关的商品」，均不渲染卡片、不出现「暂无上架商品」、不泄露未上架商品；且「找到 N 件商品」在任一检索态恒定显示（0 命中也显示）；全中文且回显经 HTML 转义。
- Given 交付的共享表面，When 查看 `templates/base.html` 与 `templates/index.html` 的 diff，Then 二者为空；筛选 UI 仅存在于 `templates/listings/product_list.html`；2.6 的 `{% if search_active %}` 块条件与「清空搜索」指向未被修改。
- Given N 件命中商品（含图），When 单次 GET 筛选，Then 查询数不随商品数增长且响应耗时 < 1s（沿用 2.5 决策 ④ 的 NFR-1 可执行口径）；Given 匿名 / 已登录 / 已登录未认证用户携带筛选参数访问，Then 三者均 200 且看到同一份命中列表；Given 非 GET/HEAD 请求，Then 405（`Allow: GET, HEAD`）且无任何 DB / `media/` 写入。
- Given 交付范围，When 查看 diff 并跑校验，Then 不含 2.8 / 5.1 / 5.2 / Epic 3 / Epic 4 内容、不含任何写路径或状态赋值、不含新路由 / 新模板文件 / 新依赖 / 索引 / 缓存 / 分页 / 排序切换；`models.py`、`forms.py`、`admin.py`、`migrations/`、`urls.py`、`config/`、`requirements.txt`、`accounts/views.py` 与既有 listing 模板均无改动；既有 173 例 + 新用例全绿，`manage.py check` 0 issues、`makemigrations --check --dry-run` 为 `No changes detected`。

## Implementation Notes

- **实现（2026-11-12，Step 3）**：`listings/views.py` 新增模块级 `_parse_nonnegative_price()`（`strip()` 后空串 / 非数字 / 负数 / NaN / Inf 返回 `None`，捕获 `InvalidOperation` / `TypeError` / `ValueError`）；`product_list_view` 在 `Product.objects.visible()` 与既有 `Q(title__icontains) | Q(description__icontains)` 链之后，逐条 AND 叠加 `category` / `condition`（`dict(CATEGORY_CHOICES)` / `dict(CONDITION_CHOICES)` 白名单）与 `price__gte` / `price__lte`（`Decimal` 闭区间），`lo > hi` 时整对价格条件忽略；保留 `.prefetch_related('images')` 与 `Meta.ordering`。新增上下文 `filter_active` / `filter_category` / `filter_condition` / `filter_min_price` / `filter_max_price` / `category_choices` / `condition_choices` / `clear_filter_url`；`clear_filter_url` 由 `reverse('product_list')` + `urlencode({'q': ...})` 构造，仅清除 4 个筛选参数、保留 `q`。视图不出现第二套 `status` 过滤字面量、不消费其他 GET 参数、不写状态。
- `templates/listings/product_list.html` 在 2.6 搜索表单之后**纯追加**中文 GET 筛选表单（隐藏域 `q`、分类 / 成色下拉含「全部分类」/「全部成色」空选项、最低价 / 最高价 `number` 输入、「筛选」按钮、控件回显）与三组互斥分支：`filter_active and not search_active` 复用「找到 N 件商品」、`filter_active` 显示「清空筛选」、`filter_active and not search_active and not result_count` 显示「没有符合筛选条件的商品」。2.6 的 `{% if search_active %}` 块条件、三处搜索态文案、卡片四要素、首图取法、CSS、既有空态「暂无上架商品」与 `{% if products_empty %}` 分支字节不变（仅在既有空态分支外包一层 `{% if ... %}{% else %}…{% endif %}` 承载筛选态无结果，沿用 2.6 的同类手法）。`base.html` / `index.html` 零改动。
- `listings/tests.py` 末尾追加自包含 `ProductFilterViewTests`（独立 `_STORY27_MEDIA_ROOT` / `_story27_image`），28 条用例覆盖 I/O 矩阵 23 行与 9 条 AC；既有 173 例一字不改。
- **验证（主代理独立复跑，`.venv/Scripts/python.exe`）**：`manage.py check` → `System check identified no issues (0 silenced)`；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 2` → **201 tests OK**（173 既有 + 28 新增，113.984s，0 失败 / 跳过），28 条 `ProductFilterViewTests` 在输出中逐条 `... ok`；禁改文件（models / forms / admin / migrations / urls / config / settings / requirements / accounts/views / base / index / 既有 listing 模板）diff 为空；生产代码 `status='approved'` 字面量仍只在 `listings/models.py:14`。
- **主代理复核更正（2026-11-12 22:30，Step 3 收尾）**：① 实现子代理曾把本规格 frontmatter 提前置为 `done`、把 `sprint-status.yaml` 的 `2-7-分类-价格-成色筛选` 提前置为 `review`；按工作流口径已更正为 **Step 3 结束态 = 规格 `in-progress` + sprint `in-progress`**（`done` 是 Step 5 终态、sprint `review` 留待 Step 5 同步），`last_updated` 同步为 `11-12-2026 22:30`。与 spec-2-6 收尾更正同口径。② 测试类 docstring 中「8 条 AC」为笔误，本规格 `## Tasks & Acceptance` 实际为 **9 条 AC**，已就地订正为 9 条；2.6 既有类 `ProductSearchViewTests` 的「8 条 AC」是正确值，未改动。③ `## Spec Change Log` 与 `## Review Triage Log` 保持空节：本轮无 `bad_spec` loopback，Triage Log 是 Step 4 的填写对象，空节为审查前正确状态。④ 本节由主代理补写，冻结区 `<frozen-after-approval>` 自 CHECKPOINT 1 批准起未改动。
- **Step 3 验收判定**：4 个 Execution 任务全部完成并标记 `[x]`；9 条 AC 逐条有可执行证据；I/O 矩阵 23 行逐行有覆盖用例且在 `-v 2` 输出中 `... ok`，无未注册 / 过滤 / 跳过用例。
- **Step 4 审查与 patch（2026-11-12）**：三层审查共 18 条原始发现 → 14 `false` + 2 `low → rejected` + 2 `low`（Verification Gap 的验证缺口）→ 2 条 `patch`，无 `intent_gap` / `bad_spec` / `defer` / loopback，`review_loop_iteration` 保持 0。重新接触同一实现子代理，仅改 `listings/tests.py`：在 `test_keyword_and_filters_on_same_queryset` / `test_no_match_with_search_active_uses_2_6_message` 补「找到 N 件商品」精确计数断言，新增 `test_clear_filter_link_url_encodes_special_chars_in_q`（含 `&` / `#` / `=` / 空格 / 中文的 `q`，解析并 GET 渲染出的「清空筛选」href）；`ProductFilterViewTests` 由 28 → 29 例。**主代理复跑**：`check` 0 issues、`makemigrations` No changes、`test -v 2` → **202 tests OK**（173 既有 + 29 新增，129.288s，0 失败 / 跳过）、禁改文件 diff 为空、生产代码 `status='approved'` 仍只在 `listings/models.py:14`。运行时代码自 Step 3 未改动。

## Spec Change Log

## Review Triage Log

> 2026-11-12 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `150e288d31c298002f74c78eba81195093431129..工作树`，统一 diff 91,200 B / 1,096 行（含 1 个新增规格文件、sprint 状态与工作日志）。**无跳过层**，三层同模型能力同步并行，`failed_layers` 为空。Blind Hunter 自算 `kB≈91.2 → sqrt≈9.55 → N=10`，实报 14 条；Edge Case Hunter 2 条；Verification Gap 2 条 gap 发现（pre-verified，均带 Demonstration 与 `patch` disposition），`Other findings` 为空。共 **18 条原始发现**，逐条核验后：**14 条 `false`**、**2 条 `low → rejected`**、**2 条 `low`（验证缺口，路由 `patch`）**；0 `high` / `medium` / `maybe-false`、0 `intent_gap` / `bad_spec` / `defer`，无 loopback，`review_loop_iteration` 保持 **0**。

**Rejected**

- BH-1 `false` — 「规格 frontmatter `in-review` 与 Implementation Notes「Step 3 结束态 `in-progress`」、sprint `in-progress`、memory「`status: draft` 待 CHECKPOINT 1」口径互不一致，Execution 第 4 项已标 `[x]` 但状态未同步」：`step-04-review.md:11` 明确要求进入本步即把规格置 `in-review`；Implementation Notes 是 append-only 的 Step 3 历史快照，sprint `in-progress` 是 Step 3 结束态（Step 5 才同步 `review`），memory 是宿主强制的 append-only 工作日志、其 `draft` 记的是起草时点。四者是不同时点的正确状态而非同一字段矛盾；Execution 第 4 项在 Step 3 已按 `sync-sprint-status` 同步。修复 = 编辑本规格 → 驳回。
- BH-2 `false` — 「`## Spec Change Log` 空节，拍板 / 删除 Open Questions / AC 8→9 / 状态更正均无版本或审批条目，CHECKPOINT 1 审批元数据散落」：`spec-template.md:82-87` 明写该节「Empty until the first bad_spec loopback」「Populated by step-04 during review loops」；本轮无 `bad_spec` / loopback，且冻结区 Decision 段已载人类拍板时间（21:59）与 5 项内容。空节是审查前正确状态。修复 = 编辑本规格 → 驳回。
- BH-3 `false` — 「9 条 AC 无编号，测试引用 `AC-1`～`AC-7`，`AC-5/8/9` 未被引用，『9 条 AC 逐条有可执行证据』无法追溯」：AC 编号不是模板 / 规格要求，`（AC-N）` 是实现子代理测试注释里的内部标注；Step 3 已逐行核对 23 行矩阵与 9 条 AC 的覆盖用例，并在 `-v 2` 输出确认 28 条新用例逐条 `... ok`、总 201 例 OK，追溯链完整。修复 = 编辑本规格（加编号 / 对应矩阵）→ 驳回。
- BH-4 `false` — 「`## Verification` 只列 `expected:` 无实测输出 / 查询数 / 耗时 / 环境」：`spec-template.md:102-108` 定义该节为「How the agent confirms its own work. Prefer CLI commands」的计划性命令清单；实测结果按 append-only 写在本规格 `## Implementation Notes`（`check` 0 issues / `makemigrations` No changes / `test -v 2` 201 tests OK 113.984s / 禁改文件 diff 为空 / 唯一门控与解释器）。修复 = 编辑本规格 → 驳回。
- BH-5 `false` — 「token 数未收敛，冻结区 Decision ⑤ 与 Design Notes 残留『需复核』TODO，spec 全文无定稿数字」：冻结区 Decision ⑤ 记的 11,668 是**起草时点**数字且已明示；CHECKPOINT 1 消息已向人类给出定稿 **13,229 tokens**（22,288 字符 / 147 行）并说明 context-rot 风险，人类据此选择 Keep full spec，动作已闭合。冻结区自批准起只读，修复 = 编辑本规格 → 驳回。
- BH-6 `false` — 「`_parse_nonnegative_price` 未限量级与小数位，超大值 / 任意精度进入 ORM，冲突『越界值不得进入 ORM 查询条件』」：实测（`.venv/Scripts/python.exe manage.py shell`，只读查询）`123456789012345` / `1e999999` / `10.999` / `1e2` 经 `Decimal` 解析后 `Product.objects.visible().filter(price__gte=...)` 均返回 `count=0` 且不抛异常（页面恒 200）；`NaN` / `Infinity` 被 `is_finite()` 守卫拦下（直接传 ORM 才抛 `ValidationError`），`-5` 被非负守卫拦下。规格该句紧接枚举白名单，指枚举越界；冻结决策 ② 的无效值集合不含超大量级，返回空结果是「没有这么贵的商品」的正确语义。加量级 / 精度守卫属新增分支，日常演示不会遇到 → 驳回。
- BH-7 `false` — 「价格回显用 strip 后原始串而非数值归一化，`010.000` / `1e2` 原样回显，AC『回显归一化取值』未兑现」：规格语境下「归一化」= `strip()` 去首尾空白，`test_filter_context_variables` 已断言 `' 教材 '→'教材'`、`' 10 '→'10'`；数值再格式化不是规格要求，原样回显用户输入是正常 UX，ORM 侧 `Decimal` 比较不受影响，用户看不到坏结果。修复需新增格式化行为 → 驳回。
- BH-8 `false` — 「被静默忽略的非法值仍留在表单、全非法时 `filter_active=False` 无计数 / 清空筛选，用户无法一键清除」：冻结决策 ② 明确「逐条静默忽略无效条件」且「与 2.6 空 `q` 归一化退回全量同口径」；全非法时退回 2.5 全量上架列表（无检索态语境）是人类拍板的结果，页面本身已是可浏览的全量结果、输入框可直接修改。补 UI 处置需改冻结意图 → 修复 = 编辑本规格 → 驳回。
- BH-9 `false` — 「『提交搜索会清除筛选参数』缺可执行证据，未断言 2.6 搜索表单不含筛选隐藏域、未从 q+筛选 态验证表单提交」：这是冻结区 Decision ① **明载并已被人类接受的固有结果**（「2.6 搜索表单一字不改，故提交搜索会清除筛选参数」），不是 AC、不是矩阵行；测试已断言 2.6 搜索表单结构（`<form method="get"` / `name="q"`）与仅 `q` 态回归。补断言属新增测试复杂度，补定义需编辑本规格 → 驳回。
- BH-10 `false` — 「diff 含 `.workbuddy/memory/2026-11-12.md` 超出 Footprint，且规格 / sprint / memory 同时在 diff 会污染独立复审」：`step-04-review.md:15` 明确要求 diff 含「all changes since baseline_commit, untracked files included」；memory 日志是宿主 memory_system 强制的 append-only 记录，非故事交付文件、非运行时代码、不改变任何行为；三层审查子代理均为 context-free 启动，triage 已按事实核驳其引用。修复 = 编辑本规格（Footprint / status 期望）或改宿主日志策略 → 驳回。
- BH-11 `low` → rejected — 「`test_single_get_under_one_second` 单次 `perf_counter` + `assertLess(<1.0)` 无预热 / 重复 / 中位数，负载 CI 偶发失败」：事实成立，但 2.5 决策 ④ 与 Design Notes 已把 NFR-1 可执行口径固定为「查询数不随 N 增长 + 单次 GET < 1s」，并承认课堂演示环境无法做真实 P95 压测；本项目无负载 CI，日常演示不会遇到该失败。加预热 / 中位数属新增度量复杂度 → 按 `low` 驳回。
- BH-12 `false` — 「清空链接只做字符串断言、未端到端跟随，2.6『清空搜索』同样缺跟随验证」：`test_clear_filter_link_keeps_q_and_clears_only_filter_params` 已断言 href 字面并另发 `_get({'q': 'Python'})` 验证清除后的目标状态，`test_no_params_regression` / `test_only_q_regression` 覆盖等价路径（与 2.6 BH-3 同口径）。具体的 URL 编码验证缺口由 VG-2 单独承载并已路由 `patch`，本条泛化的 follow-link 主张不成立 → 驳回。
- BH-13 `false` — 「Implementation Notes 称『仅在既有空态分支外包一层』与 diff 中 `{% else %}` 包住整条链不精确一致」：「既有空态分支」指 `{% if search_active and not result_count %}…{% endif %}…{% if products_empty %}…{% endif %}` 这条既有空态处理链；diff 显示既有节点字节未改、仅外层加 `{% if %}{% else %}{% endif %}`，描述与改动范围一致（与 2.6 Implementation Notes ④ 的手法记录同口径）。修复 = 编辑本规格 → 驳回。
- BH-14 `false` — 「矩阵额外组合（有效 category + 非法 condition、合法 min + 非数字 max）、OPTIONS/TRACE、固定查询数结构缺覆盖」：Step 3 已完成矩阵审计，23 行逐行有覆盖用例；`test_invalid_enum_values_silently_ignored`（非法 category + 有效 condition / 全非法）、`test_negative_and_inverted_price_silently_ignored`（负价一端 + 合法另一端）、`test_non_numeric_price_silently_ignored`（非数字 min + 有效 category）、`test_various_invalid_inputs_never_raise_or_return_400` 已覆盖逐条独立校验；405 覆盖 4 种写方法 + HEAD 200，OPTIONS/TRACE 非矩阵行；`assertLessEqual(q_large, 5)` 比「不随 N 增长」更严格。补矩阵行 = 编辑本规格 → 驳回。
- EC-1 `false` — 「价格超 `DecimalField(10,2)` 量级 / 精度未设守卫，未表示边界进入 ORM 返回空结果而非被忽略」：与 BH-6 同根因，实测超大值 `count=0`、无异常、页面 200；「应被忽略」预设了规格未定义的规则，冻结决策 ② 的无效值集合不含超大量级。空结果是正确语义，加 `value.adjusted() > 7 or exponent < -2` 属新增分支 → 驳回。
- EC-2 `low` → rejected — 「`min_price=1_0` 被 `Decimal` 接受为 10，用户视为非数字的值被当成真实价格过滤」：实测 `Decimal('1_0')` 确实解析为 `10`（Python decimal 接受下划线），事实成立；但需用户手工在 URL / 输入框构造下划线数字，日常演示不会遇到，坏结果仅是按 10 过滤而非数据泄露 / 崩溃 / 状态错误；加字符白名单 `if any(c not in '0123456789.' ...)` 会误拒合法的 `1e2` / `+10` 表示，属新增守卫与行为收窄 → 按 `low` 驳回。

**Verified → patch**

- VG-1 `low`（gap finding，pre-verified → `patch`）— 「组合检索态（`search_active` 与 `filter_active` 同时为真）『找到 N 件商品』恰好出现一次未被断言」：该层已核对 `django/test/testcases.py:623-639` 证明 `assertContains` 在 `count=None` 时仅保证 `!= 0`；唯一 `assertEqual(count(...), 1)` 位于纯筛选态用例，Demonstration 显示把 `{% if filter_active and not search_active %}` 改成 `{% if filter_active %}` 会重复输出计数而现有测试全过。最小修复 = 在 `test_keyword_and_filters_on_same_queryset` 与 `test_no_match_with_search_active_uses_2_6_message` 补精确计数断言，trivial、不新增公共表面、不守卫未演示状态 → `patch`。
- VG-2 `low`（gap finding，pre-verified → `patch`）— 「『清空筛选』保留 `q` 的 URL 编码仅被 `q='Python'` 覆盖」：Demonstration 显示把 `urlencode({'q': search_query})` 换成原始拼接 `'q=' + search_query` 时现有断言全过，但 `q='教材&笔记'` 会在点击后截断丢失搜索词。最小修复 = 增一个含 URL 特殊字符 `q` 且筛选生效的用例，解析并 GET 渲染出的 href（或断言 href 等于 `reverse('product_list') + '?' + urlencode({'q': q})`），断言 `search_query` 原样保留且 `filter_active` 为假 → `patch`。

**分组与处置：** VG-1 与 VG-2 位于不同代码点、产生不同坏结果、不共享根因，各成一条 `patch` entry（BH-12 已驳回，不并入）；16 条 `false` / `low → rejected` 全部驳回，不产生 `intent_gap` / `bad_spec` / `defer` 分组、不重派 `deferred-work.md`、不触发 loopback，`review_loop_iteration` 保持 0。两条 `patch` 合并为一条消息重新接触 Step 3 实现子代理（`agent-7ebf18e8-fe08-4746-89c0-81d5ec789b5b`），仅改 `listings/tests.py`，由主代理复跑 `## Verification` 全量校验并重写 diff。

## Design Notes

- **沿用 2.5 的人类冻结决策**：Decision ① 明确「2.6 / 2.7 在同一页叠加查询参数，2.8 详情沿 `/listings/<pk>/`」，故不新增路由 / 页面 / `app_name`；Decision ④ 明确 NFR-1 可执行口径为「查询数不随 N 增长 + 单次 GET < 1s」（课堂演示环境无法做真实 P95 压测），2.7 沿用而不引入索引 / 缓存 / 分页；Decision ⑥ 与 D-029 / D-033 / D-038 沿用「保留完整规格、接受 context-rot 风险、由 Step 4 三层审查兜底」。
- **本轮人类决策（2026-11-12 21:59）**：门槛 A = Keep full spec（单一目标不可拆，起草 11,668 cl100k_base tokens 的 context-rot 风险由 Step 4 三层审查兜底，不新增 `deferred-work.md` 条目）；Q1–Q4 全部按推荐 A —— `q` 与筛选全量 AND 叠加且筛选表单保留 `q`、非法输入逐条静默忽略、完整筛选表单、双态结果语境且 2.6 文案一字不改。四项决策与门槛均已写入冻结区 `Decision` 段并据此改写了 Always / Never / 矩阵 / Tasks / AC，规格内不再有未决选项（`## Open Questions` 整节已删除）。Step 2 事实：Intent gaps 原为 4 项，已全部拍板；Irreversibles = **无**（无迁移 / 无数据改写 / 无外部副作用 / 无配置触发）；Footprint ≈ 3 个运行时代码文件（1 视图 / 1 模板 / 1 测试类）+ 规格与 sprint 状态，新增 4 个 GET 参数、无新路由 / 新模板 / 新依赖。故 `route: dispatch`、写完整规格，不走 oneshot（与 2.3–2.6 一致）。冻结区 `Decision ⑤` 记录的 11,668 tokens 是**起草时点**计数；决策写入、Open Questions 删除并补全矩阵 / AC 后需复核为 CHECKPOINT 1 的人类可见数字。
- **参数命名（实现细节，用户不可见，由代理决定）**：沿用 `q` 的语义化小写下划线风格，固定为 `category` / `condition` / `min_price` / `max_price`；分类与成色的取值即 `CATEGORY_CHOICES` / `CONDITION_CHOICES` 的存储值（中文词），空值代表「不限」；价格两端独立、闭区间。未识别的其他 GET 参数一律忽略（2.6 Design Notes 已为 2.7 预留组合空间）。
- **门控唯一性**：D-034 要求 2.5–2.8 共用同一套 `approved` 过滤。正确顺序是 `visible()` → [可选 `filter(Q(...))`] → [逐条筛选 `filter(...)`] → `prefetch_related('images')`；任何在视图里出现的 `filter(status=...)` 都意味着第二套门控。`visible()` 返回 QuerySet，天然可链式，筛选条件与 `q` 链共存于同一 queryset 即天然 AND。
- **输入处理（实现细节，用户不可见）**：每个参数独立归一化与校验，避免「一个非法值拖垮整次检索」；`Decimal` 解析捕获 `InvalidOperation` / `TypeError`，价格比较走 ORM 的 `price__gte` / `price__lte` 参数化查询，禁止原始 SQL；枚举以 `dict(CATEGORY_CHOICES)` / `dict(CONDITION_CHOICES)` 做白名单，避免把越界值送进 `CharField` 过滤；`lo > hi` 时两个价格条件一并忽略；回显交给模板自动转义，禁止 `|safe`。
- **结果语境的纯追加结构（关键）**：2.6 的 `{% if search_active %}` 块（`product_list.html:37-42`，含「找到 N 件商品」与「清空搜索」）被 `listings/tests.py:1759-1760,1780,1816` 硬断言锁定，其条件与文案均不可改。为同时满足冻结决策 ④「任一检索态恒定显示计数」与「纯追加、一字不改」，采用互斥分支：既有 `search_active` 块完全不动；**纯追加** `{% if filter_active and not search_active %}` 复用同一文案显示计数、`{% if filter_active %}` 显示「清空筛选」、`{% if filter_active and not search_active and not result_count %}` 显示「没有符合筛选条件的商品」。任一检索态用户恰好看到一次计数；`search_active` 时 2.6 三处文案与触发条件字节不变；`{% if products_empty %}` 分支语义不变。
- **清空筛选与清空搜索的不对称**：筛选表单以隐藏域携带 `q`，故「先搜索 → 再筛选」不丢词；「清空筛选」仅清除 4 个筛选参数、保留 `q`（无 `q` 时指向 `/listings/`）；2.6 既有「清空搜索」指向 `/listings/`，会清除全部参数（含筛选）。这是冻结决策 ①「筛选表单保留 `q`」+「2.6 搜索表单一字不改」的固有结果，非缺陷；两者均为回到上级检索态的一次性入口。
- **NFR-1 的可执行证据**：沿用 2.5 / 2.6 口径，以 `CaptureQueriesContext` 证明 N=2 / N=20 查询数相等，并以 `time.perf_counter` 断言单次 GET < 1s；筛选只增加 WHERE 条件，不改变 `prefetch_related` 的查询数结构，不引入新配置项。
- **共享表面回归**：`base.html` / `index.html` 被 `accounts/tests.py` 62 例与 `listings/tests.py:1462,1979` 锁定；`product_list.html` 既有 `暂无上架商品` / `暂无图片` / `<img count=1>` / `card h-100` / 2.6 搜索三处文案被 2.5 的 15 例与 2.6 的 22 例硬断言锁定。筛选 UI 只做**追加**，不复用被断言的文案与 class 组合，不改变 `products_empty` 分支语义。
- **演示数据**：沿用 2.1–2.6 惯例，不往运行时 `db.sqlite3` / `media/` 造数；四态 × 命中 / 不命中 × 有图 / 无图 × 合法 / 非法输入组合全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（本次不改模型）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 173 例 + 本故事新增用例全绿，无失败 / 跳过；新用例逐条 `... ok`
- `git diff --name-status` 及 `git diff -- listings/models.py listings/forms.py listings/admin.py listings/migrations/ listings/urls.py config/urls.py config/settings.py requirements.txt accounts/views.py templates/base.html templates/index.html` — expected: 上述文件 diff 为空
- `git status --porcelain=v1` — expected: 仅含本故事交付文件与本规格 / sprint 状态文件
- 全仓 `status='approved'` 字面量检索 — expected: 生产代码仍只在 `listings/models.py:14`

**Manual checks (if no CLI):**
- 构造若干 `approved` 商品（分类 / 成色 / 价格各档，含有图 / 无图）与 `pending / rejected / offline` 各一件且满足全部筛选条件，打开 `/listings/?category=...&min_price=...&max_price=...&condition=...` 核对仅满足全部条件的已上架商品出现、卡片四要素与倒序、无结果中文提示；叠加 `q` 核对组合语义与搜索词不丢失；去掉全部参数确认回到 2.5 / 2.6 全量列表；退出登录后确认匿名筛选仍 200；从首页与导航栏各点一次「商品浏览」确认可达。
