---
title: '关键词搜索'
type: 'feature'
created: '2026-11-12'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: bede6255c0617bfd04b4b293308def75c56009fa
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 2.5 已交付公开列表页 `/listings/`，买家能看到全部 `approved` 商品的缩略图 / 标题 / 价格 / 成色，但 `listings/views.py:122-129` 的 `product_list_view` 只做 `visible().prefetch_related('images')` 全量取值，全仓无任何 `request.GET` 消费、无 `Q` / `icontains` 查询，`templates/listings/product_list.html` 也没有搜索框；`stories.md:115-121`、`epics.md:305-317`、`prd.md:175-180`（FR-10）要求的「买家按关键词搜索、命中标题或描述、且仅 `approved`」因此既无入口也无可执行证据，Epic 2 买家链路（列表 → 搜索 → 筛选 → 详情）断在第二环。

**Approach:** 在 2.5 的同一个公开只读列表页 `/listings/` 上以 GET 参数叠加关键词过滤：视图先 `Product.objects.visible()` 拿唯一门控查询集，再链式叠加「标题或描述包含关键词」的 ORM 条件，保留 `prefetch_related('images')` 与 `Meta.ordering`；模板纯追加中文搜索框、结果语境与无结果中文提示，卡片四要素、空列表文案与既有硬断言一字不改。不改模型 / 路由 / 配置、不产生迁移、不引入索引与缓存、不实现 2.7 / 2.8，让 2.7 能在同一查询集上继续叠加筛选条件。

**Decision（人类决策，2026-11-12 12:54，全部按推荐）:** ① Q1=A：整串作为**单一子串**、**大小写不敏感**包含匹配（`Q(title__icontains=q) | Q(description__icontains=q)`），与 `stories.md:120` 的 `assert all(kw in (p.title + p.description) for p in results)` 完全一致；不分词、不拆词，不做 AND / OR 多词逻辑，不做关键词高亮。② Q2=A：`q` 缺失、空串或仅空白时先 `strip()` 归一化为「未搜索」，退回 2.5 全量上架列表，空态仍为「暂无上架商品」，不显示搜索结果语境。③ Q3=A：标题下新增中文 GET 搜索表单（输入框回显归一化关键词 +「搜索」按钮）；有搜索词时显示「找到 N 件商品」与「清空搜索」链接；无结果显示中文「没有找到与「XXX」相关的商品」，**不复用**「暂无上架商品」。④ Q4=A：搜索框**仅**放在 `templates/listings/product_list.html` 内；首页与导航栏继续沿用 2.5 已交付的「商品浏览」入口，`templates/base.html` / `templates/index.html` **完全不动**。⑤ Token gate = **Keep full spec**：本规格为单一用户目标（关键词搜索），跨层实现不可拆，不拆分、不新增 `deferred-work.md` 条目，沿用 D-029 / D-033 / D-038；起草时点按 `cl100k_base` 统计 **7,631 tokens**（13,651 字符 / 125 行），**接受超 1600 门槛的 context-rot 风险**，由 Step 4 三层审查兜底。以上五项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 对外商品查询**唯一入口**是 `Product.objects.visible()`（`listings/models.py:12-14`，`filter(status='approved')`）；搜索条件必须链式叠加在它之后，全仓生产代码不得出现第二套 `status` 过滤字面量，视图 / 模板 / 测试不得另写门控。
- 沿用 2.5 冻结决策 ①：不新增 URL 路由、不新增 `app_name`、不改 `listings/urls.py` 与 `config/urls.py`，搜索仍走 `reverse('product_list') == '/listings/'`；表单为 `method="get"`，参数名 `q`。
- 列表页保持公开只读：`@require_safe`，**不加** `@login_required`、不要求 `is_verified`，匿名 / 已登录 / 已登录未认证 GET 均 200；非 GET/HEAD 405（`Allow: GET, HEAD`）且无任何 DB / `media/` 写入。
- 关键词为**整串单一子串**、**大小写不敏感**包含匹配：`Q(title__icontains=q) | Q(description__icontains=q)`，不分词、不拆词、不做 AND / OR 多词逻辑；只经 Django ORM 参数化查询，禁止原始 SQL / 字符串拼接；`request.GET` 仅用于该关键词，不用于排序、分页、状态或其他筛选。
- `q` 缺失 / 空串 / 仅空白：`request.GET.get('q', '').strip()` 归一化为「未搜索」，**不叠加任何过滤**，退回 2.5 全量上架列表与「暂无上架商品」空态，不显示结果语境。
- 保留 `Product.objects.visible().prefetch_related('images')` 的图片预取与 `Product.Meta.ordering = ('-created_at',)` 排序；不引入分页 / 条数截断 / 缓存 / 数据库索引 / 新配置项 / 新第三方依赖。
- 卡片四要素（缩略图或中文「暂无图片」占位、标题、`¥{{ product.price }}`、`get_condition_display()` 中文成色）、`images.all|first` 首图取法、CSS 裁切、空态「暂无上架商品」、页面标题「商品浏览」与 `templates/base.html:14` / `templates/index.html:30` 的「商品浏览」入口文案保持原样，纯追加不改写。
- `templates/listings/product_list.html` 标题区下**纯追加**中文 GET 搜索表单（`method="get"`、参数名 `q`、输入框 `value` 回显归一化关键词、「搜索」按钮）；有搜索词时显示「找到 N 件商品」与「清空搜索」链接（指向 `/listings/`）；无结果显示「没有找到与「XXX」相关的商品」且不渲染任何卡片、不复用「暂无上架商品」。搜索态与无结果态的提示均为新增节点，不改 `products_empty` 既有分支语义。
- `templates/base.html` / `templates/index.html` **完全不动**；不新增首页 / 导航栏搜索框，不新增模板文件、静态资源或路由。
- 服务端渲染 + Bootstrap 5.3.3 CDN + 全中文用户可见文案（`LANGUAGE_CODE='en-us'` 不自译）；关键词回显由 Django 模板自动转义，不输出未转义的 `|safe`，不做 `<mark>` 高亮。
- 既有 **151** 个用例一字不改且全绿（`listings/tests.py` 5 类 / 89 例 + `accounts/tests.py` 62 例），尤其 `listings/tests.py:1282,1299,1311,1321-1322,1462,1488` 与 `accounts/tests.py:677-688` 的 HTML / 导航硬断言不破。
- 不产生迁移、不改模型 / 表单 / admin / 既有迁移 / `config/settings.py` / `requirements.txt` / `accounts/views.py` / 既有 listing 模板；`manage.py check` → 0 issues，`makemigrations --check --dry-run` → `No changes detected`。
- 不往运行时 `db.sqlite3` / `media/` 造演示数据；四态、有图 / 无图与关键词组合全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

**Never:**
- 不实现 2.7 分类 / 价格 / 成色筛选、2.8 商品详情页（含 `/listings/<pk>/` 与 404 规则）、5.1 / 5.2 审核区与下架、Epic 3 聊天、Epic 4 订单；不新增「联系卖家」「立即购买」入口。
- 不改 `listings/models.py`（`visible()` / `STATUS_CHOICES` / `ALLOWED_TRANSITIONS` / `_transition()` / `ProductImage` / `RejectionNotice`）、`listings/forms.py`、`listings/admin.py`、`listings/migrations/`、`listings/urls.py`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`accounts/views.py`、`templates/listings/my_listings.html`、`publish.html`、`resubmit.html`、`templates/accounts/profile.html`。
- 不新增模型字段 / property / 方法、不生成缩略图文件、不改图片上传校验与 `ProductImage` 存储路径；不新增写路径、不改 `status`、不写 `media/`。
- 不把 `pending / rejected / offline` 商品以任何形式（隐藏、占位、注释、上下文变量）带进模板；不泄露未上架商品的标题 / 描述 / 价格 / 图片 URL / 卖家信息。
- 不引入全文检索引擎、拼音 / 分词库、独立搜索结果页 / 新路由 / API / SPA / WebSocket / 新静态资源；不改写卡片渲染结构以承载非 AC 内容，不做 `<mark>` 关键词高亮。
- 不拆词 / 不做多词 AND / OR、不实现排序切换、结果分页或与 2.7 筛选的组合行为；不引入第二套可见性判断。
- 不改 `templates/base.html` / `templates/index.html`；不在首页正文或导航栏追加搜索框；不新增模板文件。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 标题命中 | `approved` 商品标题含关键词、描述不含 | 该商品出现在 `response.context['products']` 与 HTML | `visible()` 门控 + ORM 条件 |
| 描述命中 | `approved` 商品描述含关键词、标题不含 | 该商品出现在结果，卡片仍为四要素 | 同上 |
| 大小写不敏感 | 关键词 `Python` 与商品标题 `python 教材` | 命中（整串单一子串、不分大小写），不拆词 | `icontains` |
| 整串不拆词 | `q=高数 教材`，商品标题仅含「高数」 | 按「高数 教材」整串匹配，该商品不出现 | 单一子串语义 |
| 双字段与四态混合 | 库中同时有命中 / 不命中 × `pending / approved / rejected / offline` | 仅「命中且 `approved`」出现；`all(p.status == 'approved' for p in results)` 且 `all(kw in (p.title + p.description) for p in results)` 成立 | 服务端强制过滤 |
| 非上架不泄露 | `pending / rejected / offline` 商品标题与描述均含关键词 | 其标题 / 描述 / 价格 / 图片 URL 均不出现在 HTML 与 context；`visible().count()` 与结果一致 | `visible()` 门控 |
| 卡片与排序 | 多件命中商品，含图 / 无图混合，`created_at` 互异 | 每卡片仍含缩略图或中文占位、标题、`¥` 价格、中文成色；按 `-created_at` 倒序；每张卡片只输出 1 个 `<img>` | `prefetch_related` 消 N+1 |
| 结果语境 | 有搜索词且命中 K 件 | 搜索框回显该词，显示「找到 K 件商品」与「清空搜索」链接（指向 `/listings/`） | 模板新增节点 |
| 无匹配结果 | 有搜索词但 0 件命中（库中另有未上架命中商品） | 显示「没有找到与「XXX」相关的商品」，不渲染任何卡片、不出现「暂无上架商品」、不泄露未上架商品 | 搜索态空分支 |
| 搜索框回显与转义 | `q=<script>alert(1)</script>` 或 `q=%_` | 输入框 `value` 为该词的 HTML 转义形式，页面不执行脚本；`%` / `_` 被 ORM 转义为字面量而非 LIKE 通配 | 模板自动转义 + 参数化查询 |
| 首尾空白 | `q=  教材  ` | `strip()` 后按「教材」匹配，回显已归一化关键词 | 输入归一化 |
| 空关键词 | `?q=` / `?q=%20%20` | 视为「未搜索」，退回 2.5 全量上架列表，空态仍为「暂无上架商品」，不显示结果语境 | 不叠加过滤 |
| 无 q 参数 | GET `/listings/`（2.5 原始形态） | 与 2.5 完全一致的全量上架列表与「暂无上架商品」空态，既有 151 例断言不变 | 不叠加过滤 |
| 查询数 | N=2 与 N=20 件命中商品（含图） | 查询数不随商品数增长（图片预取仍生效） | 预取一次取图 |
| 响应时间 | 演示规模 N 件命中商品 | 单次 GET 耗时 < 1s（NFR-1，`time.perf_counter` 计时断言） | 性能用例 |
| 访问门控 | 匿名 / 已登录已认证 / 已登录未认证携带关键词 GET | 三者均 200，看到同一份命中且仅 `approved` 的列表 | 无 |
| 只读方法 | 携带关键词的 POST / PUT / PATCH / DELETE | 405（`Allow: GET, HEAD`），无任何 DB 写入 | `require_safe` |
| 回归 | 既有 151 例 + 首页 / 导航 / 我的发布硬断言 | 全绿，既有文案与链接不变；`base.html` / `index.html` diff 为空 | 全量回归 |

</frozen-after-approval>

## Code Map

- `listings/models.py:12-14` — `ProductQuerySet.visible()` = `filter(status='approved')`，**对外可见性唯一定义、一字不改**；可链式，搜索条件必须叠加在它之后。`Product` 字段 `title:52` / `description:53` / `price:54` / `condition:55` / `category:56` / `status:57-59` / `created_at:60`；`objects:64`、`Meta.ordering=('-created_at',):69`、`ProductImage` 反向关系 `images:116`。
- `listings/views.py:116-129` — `product_list_view` 现状：仅 `@require_safe:122`，`products = list(Product.objects.visible().prefetch_related('images')):125`，`render('listings/product_list.html', {'products', 'products_empty'}):126-128`；注释 `:119` 明确禁止另写 status 过滤与请求传值筛选。本故事在此**唯一视图**内增加 GET 关键词读取与链式 `Q` 过滤，保留门控 / 预取 / 排序；`my_listings_view:105-113` 是卖家侧基础查询集范式，**不得**照抄其 `filter(owner=...)`。
- `listings/urls.py:4-9` — 4 条路由，无 `app_name`，`path('', views.product_list_view, name='product_list'):8` → `reverse('product_list') == '/listings/'`（`listings/tests.py:1454` 硬断言）。**不改**：搜索复用同一路由。`config/urls.py:31,34,38-39`（home / listings include / DEBUG `static()`）同样不改。
- `templates/listings/product_list.html:1-52` — `extends 'base.html'`；`block title:3` / `block content:5-52`；`<style>` 裁切 `:6-20`；`h2`「商品浏览」`:24`；`products_empty` 分支「暂无上架商品」`:28-29`；卡片网格 `:31-50`（`product.images.all|first:35`、`<img>:37`、中文占位 `:39`、四要素 `:43-45`）。搜索表单须**纯追加**在标题区与空态分支之前，卡片循环与既有文案一字不改。
- `templates/base.html:14` / `templates/index.html:30` — 「商品浏览」入口，`href="{% url 'product_list' %}"`；被 `listings/tests.py:1452-1473` 断言 `href="/listings/" count=2`。冻结决策 ④ 要求二者**完全不动**，收尾时其 diff 必须为空。
- `listings/tests.py` — 5 类共 **89** 例：`PublishViewTests:30`、`ProductVisibilityTests:379`、`RejectionNoticeAndResubmitTests:554`、`MyListingsViewTests:896`、`ProductListViewTests:1175`。2.5 夹具可复用范式：`_STORY25_MEDIA_ROOT:1163`、`_story25_image:1166`、`@override_settings(MEDIA_ROOT=...):1174`、`_make_product:1198`、`_attach_images:1210`、`_set_created_at:1216`、`_four_status_products:1229`。硬断言：`暂无上架商品:1321,1330`、`暂无图片:1299,1312`、`<img count=1>:1282,1311`、`¥25.00:1287,1302`、`visible().count():1258`、`href="/listings/" count=2:1462`、`my_listings.html` 无 `<img>:1488`。**新测试类追加在文件末尾**，既有 151 例一字不改。
- `accounts/tests.py:677-688` — 遍历 home / verify / profile 断言个人中心链接与匿名页 `assertNotContains`；`:100,135,448-462` 认证引导 / 徽标文案。共享模板改动会破坏这些断言。
- `config/settings.py:64`（TEMPLATES DIRS）、`:68`（request context）、`:82-87`（sqlite3 唯一后端）、`:112`（`en-us`）、`:118`（`USE_TZ=True`）、`:128-129`（MEDIA）、`:140`（LOGIN_URL） — 全部不改；`requirements.txt:3-4` = Django 5.2.19 / Pillow 13.0.0，Bootstrap 5.3 CDN 注释 `:7-8`，不新增依赖。
- 规划依据：`_bmad-output/planning-artifacts/stories.md:115-121`（2.6 故事 / AC / `assert all(kw in (p.title + p.description) ...)` / AD-9、AD-2、FR-10）、`epics.md:305-317`（标题或描述匹配且仅 `approved`）、`epics.md:301`（列表 / 搜索 ≤1s NFR-1）、`prds/prd-my_project-2026-11-04/prd.md:175-180`（FR-10 标题或描述）、`:352-354`（NFR-1 ≤1s P95 / 首屏 ≤2s）、`:364`（NFR-3 待审核不可被搜索）、`architecture-*/architecture.md:55-61`（AD-2 ORM）、`:111-117`（AD-9 列表与搜索服务端强制 `approved`）。
- 前序与决策：`spec-2-5-商品列表浏览-仅上架.md` 冻结区 Decision ①（2.6 / 2.7 在同一页叠加查询参数）、④（NFR-1 口径 = 查询数不随 N 增长 + 单次 GET < 1s）、`Implementation Notes:108-117`、`Design Notes:174-182`；`decision-log.md:388-396`（D-034 2.5–2.8 共用同一套 approved 过滤）、`:399-406`（D-035 唯一门控）、`:333 / :377 / :432`（D-029 / D-033 / D-038 超长规格保留完整）。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:53` — `2-6-关键词搜索: backlog`，收尾时按工作流同步 `last_updated`，不改其他故事条目。
- `.venv/Scripts/python.exe` — Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0；系统 PATH 的 `python` 无 Django，验证一律用该解释器。HEAD `bede6255c0617bfd04b4b293308def75c56009fa`（`完成2.5`），工作树干净。

## Tasks & Acceptance

**Execution:**
- [x] `listings/views.py` — 在 `product_list_view` 内 `request.GET.get('q', '').strip()` 归一化关键词；仅当非空时在 `Product.objects.visible()` 之后链式叠加 `Q(title__icontains=q) | Q(description__icontains=q)`（整串、大小写不敏感、不拆词），保留 `prefetch_related('images')` 与默认排序，构造 `search_query` / `search_active` / `result_count` 上下文；不写 `status` 字面量、不引入第二套门控、不消费其他请求参数 — 兑现 FR-10 与 AD-9。
- [x] `templates/listings/product_list.html` — 标题区下纯追加中文 GET 搜索表单（`name="q"`、回显归一化关键词、「搜索」按钮）、「找到 N 件商品」与「清空搜索」链接、以及「没有找到与「XXX」相关的商品」无结果中文提示；卡片四要素、首图取法、CSS、既有空态「暂无上架商品」、页面标题与 `products_empty` 分支一字不改 — 兑现可操作入口与「无匹配 vs 无商品」区分。
- [x] `listings/tests.py` — 末尾追加自包含 `ProductSearchViewTests`（独立临时 `MEDIA_ROOT`、图片构造 helper），覆盖矩阵全部行：标题 / 描述命中、大小写不敏感与整串不拆词、四态混合仅 approved、非上架不泄露、卡片四要素与倒序、结果数 / 清空搜索 / 无结果中文提示、搜索词转义与 `%` `_` 字面量、首尾空白与空关键词退回全量、无 q 参数回归 2.5、查询数不随 N 增长、单次 GET < 1s、三类访问门控、只读 405 且无写入、既有 151 例全量回归；既有 151 例一字不改 — 冻结验收的可执行证据。
- [x] `spec-2-6-关键词搜索.md` 与 `sprint-status.yaml` — 按工作流同步状态（`2-6-关键词搜索`）与 `last_updated`，不改其他故事条目 — 工作流收尾。

**Acceptance Criteria:**
- Given 库中同时有 `pending / approved / rejected / offline` 且部分商品标题或描述含关键词，When 以该关键词 GET `/listings/`，Then 结果仅含「命中且 `approved`」的商品，`all(p.status == 'approved' for p in results)` 与 `all(kw in (p.title + p.description) for p in results)` 同时成立，且 `visible()` 仍是全仓唯一 approved 门控（AD-9 / FR-10 / NFR-3）。
- Given 命中商品含图 / 无图两种，When 查看搜索结果卡片，Then 每张仍含缩略图或中文「暂无图片」占位、标题、`¥` + Decimal 价格、`get_condition_display()` 中文成色，按 `-created_at` 倒序，且每张只输出 1 个 `<img>`。
- Given 有搜索词且命中 K 件，When GET 列表页，Then 搜索框回显归一化关键词、显示「找到 K 件商品」与「清空搜索」链接；Given 有词但 0 件命中，Then 显示「没有找到与「XXX」相关的商品」、不渲染卡片、不出现「暂无上架商品」、不泄露未上架商品；全中文且关键词回显经 HTML 转义，`%` / `_` 按字面量匹配。
- Given `q` 缺失、空串或仅空白（含首尾空白包裹的有效词），When GET 列表页，Then 缺失 / 空串 / 纯空白退回 2.5 全量上架列表且空态仍为「暂无上架商品」，含首尾空白的有效词按 `strip()` 后的词匹配；Given 无 `q` 参数，Then 与 2.5 全量列表行为完全一致（既有 151 例断言不破）。
- Given 交付的共享表面，When 查看 `templates/base.html` 与 `templates/index.html` 的 diff，Then 二者为空；搜索框仅存在于 `templates/listings/product_list.html`。
- Given N 件命中商品（含图），When 单次 GET 搜索，Then 查询数不随商品数增长且响应耗时 < 1s（沿用 2.5 决策 ④ 的 NFR-1 可执行口径）。
- Given 匿名 / 已登录 / 已登录未认证用户携带关键词访问，Then 三者均 200 且看到同一份命中列表；Given 非 GET/HEAD 请求，Then 405（`Allow: GET, HEAD`）且无任何 DB / `media/` 写入。
- Given 交付范围，When 查看 diff 并跑校验，Then 不含 2.7 / 2.8 / 5.1 / 5.2 / Epic 3 / Epic 4 内容、不含任何写路径或状态赋值、不含新路由 / 新模板文件 / 新依赖 / 索引 / 缓存 / 分页；`models.py`、`forms.py`、`admin.py`、`migrations/`、`urls.py`、`config/`、`requirements.txt`、`accounts/views.py` 与既有 listing 模板均无改动；既有 151 例 + 新用例全绿，`manage.py check` 0 issues、`makemigrations --check --dry-run` 为 `No changes detected`。

## Implementation Notes

- **实现（2026-11-12）**：`listings/views.py` 的 `product_list_view` 在 `@require_safe` 下增加 `q = request.GET.get('q', '').strip()` 归一化；仅当 `search_active` 为真时在 `Product.objects.visible()` 之后链式叠加 `Q(title__icontains=q) | Q(description__icontains=q)`（唯一门控、整串单一子串、大小写不敏感、不拆词），末尾保留 `.prefetch_related('images')` 与 `Meta.ordering`；新增 `search_query` / `search_active` / `result_count` 三个上下文变量，`products_empty = not products` 语义不变。视图不出现第二套 `status` 过滤字面量、不消费其他 GET 参数、不写状态。
- `templates/listings/product_list.html` 标题区下**纯追加**中文 GET 搜索表单（`method="get"` / `name="q"` / `value="{{ search_query }}"` /「搜索」按钮）、`search_active` 时的「找到 N 件商品」与指向 `/listings/` 的「清空搜索」链接、以及 `search_active and not result_count` 时的「没有找到与「XXX」相关的商品」；用一层模板条件包住既有 `products_empty` 分支，卡片循环 / 四要素 / CSS /「暂无上架商品」/「暂无图片」/ 页面标题与既有文案一字不改，无结果态不再复用「暂无上架商品」。关键词回显由模板自动转义，无未转义输出与关键词高亮。`templates/base.html` / `templates/index.html` 零改动。
- `listings/tests.py` 末尾追加自包含 `ProductSearchViewTests`（独立 `_STORY26_MEDIA_ROOT` 与 `_story26_image`），22 条用例覆盖 I/O 矩阵全部行与 7 条 AC；既有 151 例一字不改。
- **验证（`.venv/Scripts/python.exe`）**：`manage.py check` → `System check identified no issues (0 silenced)`；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 1` → **173 tests OK**（151 既有 + 22 新增，0 失败 / 跳过）；`git diff` 仅含 `listings/views.py` / `templates/listings/product_list.html` / `listings/tests.py` 与本规格 / sprint 状态；禁改文件与 `base.html` / `index.html` diff 均为空；生产代码 `status='approved'` 字面量仍只在 `listings/models.py:14`；未产生迁移 / 新路由 / 新模板 / 新依赖 / 写路径。

- **主代理复核更正（2026-11-12，Step 3 收尾）**：① 上一条 Implementation Notes 中「7 条 AC」为笔误，本规格 `## Tasks & Acceptance` 实际为 **8 条 AC**，测试类 docstring 已同步订正为 8 条。② 冻结决策 ③ 要求「有搜索词时显示『找到 N 件商品』」是**无条件**于 `search_active` 的，实现子代理曾把 0 结果时的计数隐藏；已改为 `search_active` 时恒定显示 `找到 {{ result_count }} 件商品`（0 结果时与「没有找到与「XXX」相关的商品」并存），并把 `test_no_match_with_existing_approved_products` 的断言由 `assertNotContains('找到 0 件商品')` 改为 `assertContains`，使代码与冻结意图字面一致。③ 实现子代理曾把本规格 frontmatter 与 `sprint-status.yaml` 提前置为 `done`，并在 `## Spec Change Log` 写入非 `bad_spec` loopback 的条目；按工作流口径已更正为：本规格 `status: in-review`（Step 4 输入态）、sprint `2-6-关键词搜索: in-progress`（Step 3 结束态，留待 Step 5 同步为 `review`）、Spec Change Log 恢复空节。`done` 是 Step 5 终态，不在此处提前置入。④ 模板为区分「无匹配」与「平台无商品」，在既有 `{% if products_empty %}` 分支外加了一层 `{% if search_active and not result_count %}…{% else %}…{% endif %}`：内层分支、卡片循环、四要素与既有文案字节不变，非搜索态行为与 2.5 完全一致（既有 151 例全绿为证）；这是同时满足冻结决策 ③「不复用『暂无上架商品』」与「不改既有空态文案」的唯一结构。
- **主代理独立复跑（`.venv/Scripts/python.exe`）**：`manage.py check` → 0 issues；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 2` → **173 tests OK**（151 既有 + 22 新增，100.084s，0 失败 / 跳过），22 条 `ProductSearchViewTests` 在 `-v 2` 输出中逐条 `... ok`；禁改文件（models / forms / admin / migrations / urls / config / settings / requirements / accounts/views / base / index / 既有 listing 模板）diff 为空；生产代码 `status='approved'` 字面量仍只在 `listings/models.py:14`；`git status --porcelain=v1` 仅含 5 个本故事文件。

## Spec Change Log

## Review Triage Log

> 2026-11-12 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `bede6255c0617bfd04b4b293308def75c56009fa..工作树`，统一 diff 59,995 B / 750 行（含 1 个新增规格文件）。**无跳过层**，三层同步并行、同模型能力，`failed_layers` 为空。Blind Hunter 自算 `kB≈58.6 → sqrt≈7.65 → N=8`，实报 11 条；Edge Case Hunter 2 条；Verification Gap 明确返回 `No verification gaps found.`（独立复跑 `manage.py test listings.tests.ProductSearchViewTests -v 2`，22 例全被正常发现且通过、无跳过，0 条发现故不产生行）。共 **13 条原始发现**，逐条核验后 **13 条全部驳回**（10 `false`、3 `low → rejected`），0 `high` / `medium` / `maybe-false`、0 `intent_gap` / `bad_spec` / `patch` / `defer`、无 loopback，`review_loop_iteration` 保持 **0** → **Clean review**。

**Rejected**

- BH-1 `false` — 「Implementation Notes 仍写 7 条 AC，与复核更正声明的 8 条矛盾，未就地订正」：Implementation Notes 是 append-only 记录，复核更正条目已明写「上一条 Implementation Notes 中『7 条 AC』为笔误，本规格实际为 8 条 AC」，并说明测试类 docstring 已同步订正；`grep -c '^- Given'` 实测 8 条 AC。读者不会把旧条当作最终口径（与 2.5 AA-4 同口径）。修复 = 编辑本规格 → 按「修复为编辑本规格的发现一律驳回」处理。
- BH-2 `false` — 「0 命中时「找到 0 件商品」与「没有找到与「XXX」相关的商品」并存，矩阵未说明该组合」：这正是冻结 `Decision ③` 的字面要求——「有搜索词时显示『找到 N 件商品』与『清空搜索』链接」且「无结果显示『没有找到与「XXX」相关的商品』」，二者并存是人类拍板的结果而非冗余缺陷；主代理在 Step 3 已把原先隐藏计数的实现改为字面一致。补矩阵行 = 编辑冻结规格 → 驳回。
- BH-3 `false` — 「『清空搜索』只有字面 HTML 断言，缺 follow-link 行为验证」：链接为 `{% url 'product_list' %}` → `/listings/`（无 q）；`test_no_q_param_matches_2_5_behavior` 已断言无 q 参数 GET 回到 2.5 全量列表、`search_active` 为假、「件商品」/「清空搜索」/「没有找到」全部不出现，即点击后的目标状态已被等价路径覆盖。声称的坏结果不成立，补用例属新增测试复杂度。
- BH-4 `false` — 「缺表单端到端验证（action / 真实提交回合 / `<label for>`）」：`test_result_context_found_n_clear_link_and_echo` 已断言 `<form method="get"`、`name="q"`、`value="Python"`、`搜索</button>`；`action` 解析为当前页 `/listings/`，而全部 22 例都经 `self.client.get('/listings/', {'q': ...})` 触发，正是该表单提交产生的请求。`test_search_form_only_on_product_list_page` 另断言首页无该表单、列表页有。`<label for>` 属 BH-11 的 a11y 项，非功能缺陷。
- BH-5 `false` — 「转义测试漏 `"` / `'` / `&` / `\`，可能突破 `value` 属性边界」：`value="{{ search_query }}"` 走 Django 模板默认 autoescape（全仓 `product_list.html` 无 `|safe`），`"` → `&quot;`、`'` → `&#x27;`、`&` → `&amp;` 由框架保证；`icontains` 经 ORM 参数化并转义 LIKE 特殊字符，`test_percent_underscore_are_literal_not_wildcards` 已证 `%` / `_` 为字面量，`test_search_query_is_html_escaped` 已断言 `<script>` 不出现在 HTML 且回显为实体。补用例不改变结果。
- BH-6 `false` — 「缺『关键词仅命中非搜索字段不应匹配』的反向用例与矩阵行，日后误加 `Q(category__icontains)` 无法拦截」：`listings/views.py:130-133` 全文只有 `Q(title__icontains=q) | Q(description__icontains=q)` 两个条件，grep 确认视图无 `category` / `condition` / `price` / `owner` 的 Q 分支，当前代码不可能命中非搜索字段；「日后若有人误加」是假设性未来回归，不是当前可达的坏结果。补矩阵行 = 编辑冻结规格 → 驳回。
- BH-7 `low` → rejected — 「`q` 无长度上限、输入框无 `maxlength`，超长关键词产生无界 LIKE 扫描」：事实成立，但冻结区 Design Notes 已明确「不设长度上限（课堂演示，无 DoS 面）」，Always 明令不引入索引 / 缓存 / 分页 / 新配置项；SQLite 演示规模（几十件商品）下不会产生用户可见坏结果。加 `maxlength` 与服务端上限属新增守卫 + 改写冻结约束，日常不会遇到 → 按 `low` 驳回（与 2.5 BH-13 同口径）。
- BH-8 `false` — 「HEAD + 关键词路径未覆盖，矩阵只读行只列 4 种 405」：`@require_safe` 对 HEAD 的放行由 Django 框架保证，与 query string 无关；`test_unsafe_methods_with_keyword_return_405_without_writes` 已断言 `client.head(url)` 返回 200，且视图仅一处 `request.GET.get` 读取，HEAD 请求同样可携带 q 并走同一只读路径。补矩阵行 = 编辑冻结规格 → 驳回。
- BH-9 `false` — 「Spec Change Log / Review Triage Log 为空，Step 3 四项更正未登记」：`spec-template.md` 明写二者「Empty until the first bad_spec loopback / review pass」；本轮无 `bad_spec` / loopback，Triage Log 正是本轮填写对象，空节是审查前正确状态；四项更正已按 append-only 记入 Implementation Notes。修复 = 编辑本规格 → 驳回。
- BH-10 `false` — 「缺空 / NULL 描述、仅标题命中的边界用例」：`listings/models.py:53` 的 `description = models.TextField(...)` 默认 `blank=False`，`ProductForm` 必填，无生产写入空描述的路径；`test_title_match_only` 已构造「标题命中、描述不含关键词」的商品覆盖 OR 的 title 分支，NULL 描述亦不影响该分支。未展示可达路径的失败不是缺陷（与 2.5 EC-1 / EC-3 同口径）。
- BH-11 `low` → rejected — 「无可见 `<label for>`、表单缺 `role="search"` 地标」：事实成立，但冻结意图只要求桌面 Chrome/Edge 的中文 Bootstrap 服务端渲染，`aria-label="搜索关键词"` 已提供无障碍名称；加可见标签会新增节点并改变页面结构，`role="search"` 属新增优化，日常演示不会遇到该缺陷 → 按 `low` 驳回（与 2.5 BH-14 同口径）。
- EC-1 `false` — 「`icontains` 大小写不敏感，但 AC-1 的 `all(kw in (p.title + p.description) ...)` 大小写敏感，`q=python` 命中 `Python` 标题时断言为 False」：Q1 人类决策明确「大小写不敏感包含匹配」，代码按此实现且 `test_case_insensitive_single_substring` 覆盖 `Python`/`python`/`PYTHON`/`pYtHoN` 四种输入；AC-1 的断言是 `stories.md:120` 上游提示的照抄，唯一执行它的 `test_four_status_mixed_only_approved_and_keyword` 使用同大小写数据并通过，不存在大小写不同输入下执行该断言的注册用例，运行时无「断言为 False」的坏结果。订正 AC 文字 = 编辑本规格 → 驳回。
- EC-2 `low` → rejected — 「重复 `q`（`?q=a&q=b`）时 `get()` 静默丢弃前一个关键词，建议 `getlist` 并拒绝多值」：Django `QueryDict.get` 取最后一个值，事实成立；但正常 UI 只有一个 `name="q"` 输入框，只会产生一个 q，重复参数需手工构造 URL，且坏结果仅是「以后一个词搜索」而非数据泄露 / 崩溃 / 状态错误；Design Notes 已裁定「未识别的其他 GET 参数一律忽略」。加 `getlist` 守卫属新增分支，日常不会遇到 → 按 `low` 驳回。

**分组与处置：** 无存活项，不产生分组、不生成 `### Review Findings` action items、不重派实现子代理、不改 `deferred-work.md`；`intent_gap` / `bad_spec` 为 0 故不触发 loopback 与 `review_loop_iteration` 递增。主代理独立复跑（`.venv/Scripts/python.exe`）：`manage.py check` → 0 issues；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test -v 2` → **173 tests OK**（100.084s，0 失败 / 跳过），22 条 `ProductSearchViewTests` 逐条 `... ok`；禁改文件与 `base.html` / `index.html` diff 为空；生产代码 `status='approved'` 字面量仍只在 `listings/models.py:14`。Verification Gap 层「无发现」结论与主代理复跑一致。

## Design Notes

- **沿用 2.5 的人类冻结决策**：Decision ① 明确「2.6 / 2.7 在同一页叠加查询参数」，故不新增路由 / 页面；Decision ④ 明确 NFR-1 的可执行口径为「查询数不随 N 增长 + 单次 GET < 1s」（课堂演示环境无法做真实 P95 压测），2.6 沿用该口径而不引入索引 / 缓存 / 分页；Decision ⑥ 与 D-029 / D-033 / D-038 沿用「保留完整规格、接受 context-rot 风险、由 Step 4 三层审查兜底」。
- **本轮人类决策（2026-11-12 12:54）**：门槛 A = Keep full spec（单一目标不可拆，7,631 tokens 的 context-rot 风险由 Step 4 三层审查兜底，不新增 `deferred-work.md` 条目）；Q1–Q4 全部按推荐 A —— 整串单一子串 + `icontains` 大小写不敏感、空关键词退回全量、完整搜索 UI 与独立无结果文案、搜索框仅放列表页。四项决策均已写入冻结区 `Decision` 段并据此改写了 Always / Never / 矩阵 / Tasks / AC，规格内不再有未决选项。Step 2 事实：Intent gaps 原为 5 项（Q1–Q4 + token gate），已全部拍板；Irreversibles = **无**（无迁移 / 无数据改写 / 无外部副作用 / 无配置触发）；Footprint ≈ 3 个运行时代码文件（1 视图 / 1 模板 / 1 测试类）+ 规格与 sprint 状态，新增 1 个 GET 参数 `q`、无新路由 / 新模板 / 新依赖。故 `route: dispatch`、写完整规格，不走 oneshot（与 2.3–2.5 一致）。冻结区 `Decision ⑤` 记录的 7,631 tokens 是**起草时点**计数；四项决策写入、Open Questions 删除并补全矩阵 / AC 后复核为 **9,145 tokens**（15,947 字符 / 135 行），两者均为同一次 CHECKPOINT 1 之前的人类可见数字。
- **门控唯一性**：D-034 要求 2.5–2.8 共用同一套 `approved` 过滤。正确顺序是 `visible().filter(Q(...) | Q(...)).prefetch_related('images')`：任何在视图里出现的 `filter(status=...)` 都意味着第二套门控。`visible()` 返回 QuerySet，天然可链式，2.7 后续可在同一查询集上继续叠加分类 / 价格 / 成色条件。
- **输入处理（实现细节，用户不可见）**：参数名固定 `q`；`request.GET.get('q', '')` + `strip()` 归一化首尾空白（Q1 / Q2 已定义匹配与空值语义）；不设长度上限（课堂演示，无 DoS 面）；`icontains` 由 Django ORM 参数化并自动转义 `%` / `_` 等 LIKE 通配与引号，不产生注入或意外通配；回显交给模板自动转义，禁止 `|safe`。未识别的其他 GET 参数一律忽略，为 2.7 预留组合空间。
- **NFR-1 的可执行证据**：`'SQLite 上 icontains 退化为 LIKE'` 不影响复杂度结论，仍以 `CaptureQueriesContext` 证明 N=2 / N=20 查询数相等，并以 `time.perf_counter` 断言单次 GET < 1s；不引入新配置项。
- **共享表面回归**：`base.html` / `index.html` 被 `accounts/tests.py` 62 例与 `listings/tests.py` 的 `nav_and_home_entries_for_all_users:1452` 锁定；`product_list.html` 既有 `暂无上架商品` / `暂无图片` / `<img count=1>` / `card h-100` 被 2.5 的 15 例硬断言锁定。搜索 UI 只做**追加**，不复用被断言的文案与 class 组合，不改变 `products_empty` 分支语义。
- **演示数据**：沿用 2.1–2.5 惯例，不往运行时 `db.sqlite3` / `media/` 造数；四态 × 命中 / 不命中 × 有图 / 无图组合全部由测试用例在测试库 + 临时 `MEDIA_ROOT` 构造后断言。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（本次不改模型）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 151 例 + 本故事新增用例全绿，无失败 / 跳过；新用例逐条 `... ok`
- `git diff --name-status` 及 `git diff -- listings/models.py listings/forms.py listings/admin.py listings/migrations/ listings/urls.py config/urls.py config/settings.py requirements.txt accounts/views.py` — expected: 上述文件 diff 为空
- `git status --porcelain=v1` — expected: 仅含本故事交付文件与本规格 / sprint 状态文件
- 全仓 `status='approved'` 字面量检索 — expected: 生产代码仍只在 `listings/models.py:14`

**Manual checks (if no CLI):**
- 构造若干 `approved` 商品（标题命中 / 描述命中 / 不命中，含有图 / 无图）与 `pending / rejected / offline` 各一件且标题描述均含关键词，打开 `/listings/?q=...` 核对仅命中商品出现、卡片四要素与倒序、无结果中文提示；去掉 `q` 参数确认回到 2.5 全量列表；退出登录后确认匿名搜索仍 200；从首页与导航栏各点一次「商品浏览」确认可达。
