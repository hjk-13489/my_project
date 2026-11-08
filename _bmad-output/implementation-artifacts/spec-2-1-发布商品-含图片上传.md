---
title: '发布商品（含图片上传）'
type: 'feature'
created: '2026-11-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 6454e04d459728512e87daca8772af7438f1f1d8
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1 已交付注册、登录、学号认证与个人中心，但 `listings` 仍是空脚手架；FR-5「卖家填写字段并上传图片发布」没有承载，商品数据不存在，Epic 2 后续的审核、列表、搜索与详情都无从起步。

**Approach:** 在 `listings` app 建立商品与图片的持久化模型，提供登录保护的发布页（ModelForm + 图片上传），在服务端强制校验字段、枚举、价格与图片真实格式，提交后以 `pending` 状态原子落库并把图片写入本地 `media/`；同时接上开发期媒体服务，让上传图片可被访问。

**Decision（人类决策，2026-11-08）:** ① 图片按架构 ERD 建独立图片实体，每商品 1–5 张，与 FR-12「展示全部图片」一致、2.8 无需返工；② 已登录但未认证用户返回 200 提示页「需先完成学号认证」并给出去认证链接；③ 提交成功后留在发布页显示「已提交，等待管理员审核」成功态，不跳转（2.4「我的发布」尚未实现，跳过去只会看到空状态）；④ 规格约 1920 tokens 超出 1600 建议值，人类选择保留完整规格并接受 context-rot 风险，不拆分次级项（跨层实现属单一目标）。以上四项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 仅已登录且 `is_verified=True` 的用户可提交发布（PRD §4.2 假设、epics Story 2.1 AC）；资格在服务端校验，不做前端隐藏式伪权限。
- 已登录但 `is_verified=False` 的用户访问发布页（GET 或 POST）→ 200 提示页，说明需先完成学号认证并给出去认证链接，不创建任何记录、不写 `media/`。
- 新建 `Product` 的 `owner` 恒为 `request.user`，`status` 恒为 `'pending'`，两者不接受表单或请求传值。
- 标题、描述、价格、成色、分类必填；价格用 `DecimalField(max_digits=10, decimal_places=2)` 且 > 0；分类枚举「教材/日用品/电子数码/其他」、成色枚举「全新/良好/中等」，越界值返回中文表单错误。
- 图片 1–5 张（含边界），仅 JPEG/PNG、单图 ≤5MB；用 Pillow 打开并校验真实格式（不信任扩展名），非法时返回中文表单错误，且不落库、不写 `media/`。
- 提交成功后留在发布页渲染「已提交，等待管理员审核」成功态，不产生跳转、不产生重复提交的第二条记录。
- `status` choices 覆盖 `pending/approved/rejected/offline`（为 2.2/2.4 预留），但本故事不实现任何状态流转动作。
- 闭合 `deferred-work.md` 已登记的「开发期媒体服务」：`config/urls.py` 在 DEBUG 下挂 `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`。
- 全中文文案；Django 模板 + Bootstrap 5.3 CDN 服务端渲染；发布表单带 `enctype="multipart/form-data"`；导航栏已登录分支追加「发布商品」入口。
- 保持 `accounts` 五个视图/路由、`User` 字段、`LOGIN_URL`、`AUTH_USER_MODEL`、admin 审核逻辑与 1.1–1.5 行为不变；不改 `templates/base.html` 中被既有测试硬断言的文案（个人中心 / ✓ 已认证 / 待认证 / 去认证 / 退出）与 `templates/index.html` 的「待认证」。
- 保持 `config/settings.py` 的 `MEDIA_ROOT`/`MEDIA_URL`、`INSTALLED_APPS`、`LANGUAGE_CODE` 等既有配置不变。

**Never:**
- 不实现 2.2/2.3/2.4/2.5–2.8（审核流转、驳回通知、我的发布、列表/搜索/筛选/详情），也不实现 5.1 的管理员审核界面。
- 不实现聊天、下单、支付、联系方式展示、评价、退款；不新增 `chat`/`orders`/`dashboard` 的业务实体，不改其脚手架。
- 不引入云对象存储、DRF/API、SPA 前端构建链、新第三方依赖、WebSocket。
- 不改动 `accounts/migrations/0001_initial.py`、`0002_verificationrequest.py`、`db.sqlite3` 既有结构与数据、既有 62 个测试用例；不造假演示数据。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 已认证卖家 GET | GET `/listings/publish/` | 200，渲染 `listings/publish.html`，含 `enctype="multipart/form-data"` 的表单与图片选择 | N/A |
| 合法提交 | 五字段齐全 + 1–5 张合法 JPEG/PNG（单图 ≤5MB） | 创建 `Product(status='pending', owner=request.user)` 与对应图片实体，图片写入 `media/`；200 留在发布页显示「已提交，等待管理员审核」 | N/A |
| 缺必填 | 标题/描述/价格/成色/分类任一为空 | 不创建 `Product`、不写 `media/`，表单显示中文错误 | `ProductForm.is_valid()` 为 False |
| 价格非法 | 非数字 / 0 / 负数 | 拒绝，中文表单错误 | 表单 `clean_price` / DecimalField 校验 |
| 枚举越界 | 分类或成色不在白名单 | 拒绝，中文表单错误 | ModelForm `ChoiceField` 校验 |
| 图片非法 | 未上传 / GIF 或扩展名伪装 / 单图 >5MB / 少于 1 张或多于 5 张 | 拒绝，中文表单错误；不落库、不写文件 | Pillow `Image.open().verify()` + format/size/张数校验 |
| 已登录未认证 | GET 或 POST `/listings/publish/` | 200 提示页，含「需先完成学号认证」与去认证链接，不创建记录 | 视图在表单处理前的 `is_verified` 分支 |
| 未登录 | GET 或 POST `/listings/publish/` | 302 到 `/login/?next=/listings/publish/` | `@login_required`（外层，先于认证分支） |
| 非允许方法 | PUT / PATCH / DELETE 发布 URL | 405 | `@require_http_methods(['GET','HEAD','POST'])` |
| HEAD | HEAD `/listings/publish/` | 200，不写任何数据 | 放行 HEAD |

</frozen-after-approval>

## Code Map

- `listings/models.py` — 当前仅 3 行空脚手架（`from django.db import models` + 注释）；新建 `Product`（`owner` FK → `settings.AUTH_USER_MODEL`、`title`、`description`、`price` `DecimalField(10,2)`、`condition`/`category`/`status` 三组 `choices`、`created_at`/`updated_at`）与 `ProductImage`（`product` FK、`image` `ImageField(upload_to='products/')`、`created_at`）；勿复制其他 app 的实体。
- `listings/migrations/` — 只有空的 `__init__.py`；由 `makemigrations listings` 生成 `0001_initial.py`（不可逆项）。`accounts/migrations/0001_initial.py`、`0002_verificationrequest.py` 勿改。
- `listings/forms.py` — 0 字节；新建 `ProductForm(ModelForm)`。中文 `error_messages` 与 `clean_*` + `add_error` 范式参照 `accounts/forms.py:46-55、57-69`；价格 > 0 在 `clean_price` 校验。
- `listings/views.py` — 3 行空脚手架；新建 `publish_view`。登录保护与 `is_verified` 分支参照 `accounts/views.py:66-70`；装饰序参照 `accounts/views.py:121-124`（`@login_required` 外层），但本视图需放行 POST，故内层用 `@require_http_methods(['GET','HEAD','POST'])` 而非 `require_safe`/`require_GET`（Django 5.2.19 下 `require_GET` 会拒绝 HEAD）。POST 同时绑定 `request.POST` 与 `request.FILES`，用 `transaction.atomic()` 保证商品与 1–5 张图片同成同败。
- `listings/urls.py` — 0 字节；新建 `path('publish/', views.publish_view, name='publish')`，**不设 `app_name`**（与 `accounts/urls.py:4-10` 一致，避免 namespace 影响既有 `reverse()`）。
- `config/urls.py:27-31` — 现有 `admin/`、`""`→`home`、`""`→`include("accounts.urls")`；追加 `path('listings/', include('listings.urls'))` 与 `if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`。追加项不得排在既有 `path("", ...)` 之前，也不得改动现有三条。
- `config/settings.py` — `INSTALLED_APPS` L34-47 已含 `listings`；`MEDIA_URL` L128 / `MEDIA_ROOT` L129 已配置，直接复用；`AUTH_USER_MODEL` L137、`LOGIN_URL` L140、`LANGUAGE_CODE='en-us'` L112 勿改（`en-us` 不会自动翻译，文案必须手写中文）。
- `accounts/models.py:5-16` — `User` 提供 `student_id`/`is_verified`/`role`/`USERNAME_FIELD='student_id'`；`Product.owner` 引用 `settings.AUTH_USER_MODEL`，勿改 `User`。
- `templates/base.html:10-30` — 仅 `title`(6)/`content`(33) 两 block，Bootstrap 5.3.3 CDN；已登录分支 14-23 追加「发布商品」链接；`:15-23` 的「个人中心」「✓ 已认证」「待认证」「去认证」「退出」被 `accounts/tests.py:454/461` 等硬断言，勿改。
- `templates/accounts/verify.html:34-72` — 表单手动渲染范式（`novalidate`、`{% csrf_token %}`、逐字段 label/errors、Bootstrap 栅格、`submitted` 成功态）；本故事额外需要 `enctype`、图片字段与未认证提示分支。
- `listings/tests.py` — 3 行空脚手架；新增 `PublishViewTests`。范式参照 `accounts/tests.py:1-10`：`reverse()` + `User.objects.create_user(student_id=..., username=..., password=...)` + `client.login(username=<student_id>)`。上传测试用 `SimpleUploadedFile` + `BytesIO`/Pillow 生成内存图片，并以 `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` 隔离 `media/`；断言须锚定本模板独有文案并带 `count=`，避免与 `base.html` 同名内容导致 `assertContains` 假通过。
- `listings/admin.py` — 3 行空脚手架；仅注册模型供人工验收查看 pending 数据，不实现审核 action（属 5.1）。
- `requirements.txt:3-4` — Django 5.2.19 / Pillow 13.0.0 已锁定，实测 `.venv/Scripts/python.exe` 可用；勿改版本。系统 PATH 的 `python` 无 Django，验证一律用 `.venv/Scripts/python.exe`。
- `_bmad-output/implementation-artifacts/deferred-work.md:5-7` — 明确登记「开发期媒体服务由 story 2.1 接入」，本故事闭合该项。

## Tasks & Acceptance

**Execution:**
- [x] `listings/models.py` — 定义 `Product` 与 `ProductImage`，三组 choices 完整、状态默认 `pending` — 承载 FR-5、AD-8 与 AD-9
- [x] `listings/migrations/0001_initial.py` — 生成并提交初始迁移 — schema 可迁移（不可逆项）
- [x] `listings/forms.py` — `ProductForm`：必填、中文错误、`price > 0`；图片按 Pillow 校验格式/大小/1–5 张 — 服务端输入边界
- [x] `listings/views.py` — `publish_view`：登录 + 认证双门控、方法约束、绑定 `request.POST`/`request.FILES`、`transaction.atomic()` 原子保存、成功态上下文 — 业务编排
- [x] `listings/urls.py` + `config/urls.py` — 暴露 `/listings/publish/`、DEBUG 下挂 `static()` 媒体服务 — 页面可达与图片可预览
- [x] `templates/listings/publish.html` — 新建：中文表单、`enctype`、逐字段错误、图片多选、未认证提示、成功态 — 用户可见呈现
- [x] `templates/base.html` — 已登录导航追加「发布商品」入口（不改既有断言文案） — 全局入口
- [x] `listings/admin.py` — 注册模型供验收查看 — 人工核对 pending 数据
- [x] `listings/tests.py` — 新增 `PublishViewTests` 覆盖矩阵各行（合法/缺字段/价格/枚举/图片格式/大小/张数/未认证/未登录/方法/归属/无部分落库） — 回归证据
- [x] 本规格与 `sprint-status.yaml` — 状态同步 — 工作流收尾

**Acceptance Criteria:**
- Given 已登录且已认证卖家，When 填齐五字段并上传 1–5 张合法图片提交，Then 创建 `Product` 且 `status='pending'`、`owner=request.user`，图片落在 `media/`，页面显示成功态。
- Given 任一必填缺失、价格非法、枚举越界、图片非法或张数越界，When 提交，Then 无 `Product`、无图片文件落盘，页面给出中文错误。
- Given 已登录但未认证用户，When 访问发布页，Then 200 提示页含去认证链接，且不创建任何记录。
- Given 未登录访客，When 访问发布页，Then 302 到登录页且带 `next`。
- Given 1.1–1.5 的既有用例，When 运行完整测试套件，Then 62 个既有用例仍全部通过。
- Given 迁移已生成，When 运行 `makemigrations --check --dry-run`，Then 无新增变更。

## Implementation Notes

- 实现按冻结规格完成；改动共 12 个文件：`listings/models.py`、`listings/forms.py`、`listings/views.py`、`listings/urls.py`、`listings/admin.py`、`listings/tests.py`、`listings/migrations/0001_initial.py`（新建）、`templates/listings/publish.html`（新建）、`templates/base.html`、`config/urls.py`、本规格、`sprint-status.yaml`。未改动 `accounts` 五个视图/路由、`User` 字段、`config/settings.py`、`accounts` 既有迁移、既有 62 个用例；`db.sqlite3`/`media/` 为 gitignore 的运行时内容，`migrate` 仅新增 listings 两张表。
- `Product.category/condition` 的 choices 以规格枚举的中文串同时作为存储值与显示标签；`status` 按规格用 `pending/approved/rejected/offline` 英文键 + 中文显示名（与 `accounts.VerificationRequest` 一致）。`owner`/`status` 均不在 `ProductForm.fields` 内，由 `publish_view` 强制写入。
- 图片校验落在 `listings/forms.py` 的 `validate_images(files)`：先查张数 1–5、单图 ≤5MB，再用 Pillow `Image.open().verify()` 按 `img.format` 判定 JPEG/PNG（忽略扩展名），校验前后 `seek(0)` 复位。`publish_view` 在表单 `is_valid()` 之后用 `form.add_error(None, ...)` 把图片错误汇入同一 `non_field_errors` 区；全部校验通过后才进入 `transaction.atomic()` 保存，因此不存在「商品已建、图片失败」的部分落库，校验失败也不会写入 `media/`。
- 装饰器顺序按 `accounts/views.py:121-124`：`@login_required`（外层）→ `@require_http_methods(['GET','HEAD','POST'])`（内层）。显式列出 HEAD 以放行 HEAD 且对 PUT/PATCH/DELETE 返回 405。
- `config/urls.py` 在既有三条 path 之后追加 `path('listings/', include('listings.urls'))` 与 `if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`，闭合 `deferred-work.md:5-7` 登记的「开发期媒体服务」（按该文件既有惯例，历史登记条目保留不删除）。
- 模板文案刻意与 `base.html` 既有硬断言文案错开；`listings/tests.py` 的断言锚定本模板独有文案并带 `count=`，`MEDIA_ROOT` 用 `@override_settings` + 临时目录隔离并在 `setUp` 清空，避免用例间残留导致假通过。
- 验证（`.venv` Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0）：`manage.py check` 无问题；`makemigrations --check --dry-run` → `No changes detected`；`manage.py migrate` → `Applying listings.0001_initial... OK`；`manage.py test` → 84 tests OK（62 既有 + 22 新增 `PublishViewTests`）。另手工验证 `reverse('publish') = /listings/publish/`、`resolve('/media/products/...')` 命中 `django.views.static.serve`、DEBUG 下 `GET /media/...` 返回 200 与文件字节。系统 PATH 的 `python` 无 Django，验证一律用 `.venv/Scripts/python.exe`。
- 状态同步：按项目既有惯例（见 spec-1-4/1-5 开发提交），开发完成置本规格 frontmatter `status: done`、`sprint-status.yaml` 的 `2-1` 为 `review`；代码审查收尾阶段再由审查方将 sprint 状态置为 `done`。二者分属工作流不同阶段，非遗漏。
- 2026-11-08 三层审查补丁：仅改 `listings/tests.py`，新增 6 个用例（DEBUG 媒体路由 GET 200 + 字节一致、合法 PNG、真实 JPEG 伪装 .png 扩展名仍被接受、12 组合法分类×成色 subTest、已登录导航发布入口、4 组表单边界中文文案 subTest），补 `importlib` / `config.urls` / `clear_url_caches` 导入；媒体路由用例在 `finally` 中还原 `urlpatterns` 与 URL 缓存，避免污染同进程用例。4 组变异检查（删 static() / 删导航链接 / 允许格式缩为只 JPEG / 中文文案改英文）均使对应用例失败，临时改动已按字节还原。
- 补丁后完整复验（主代理执行）：`manage.py check` 无问题；`makemigrations --check --dry-run` → `No changes detected`；`manage.py migrate` → `No migrations to apply`（迁移已在补丁前应用）；`manage.py test -v 2` → **90 tests OK**（62 既有 + 28 `PublishViewTests`），无失败/跳过，6 个新增用例逐个 ok。
- 状态更正：上面的 `status: done` 是实现收尾时记述；Step 4 审查开始后本规格 frontmatter 已置 `status: 'in-review'`，最终状态由 Step 5 收尾同步。`listings/tests.py` 的 84/22 记述为补丁前口径，以本条 90/28 为准。

## Spec Change Log

## Review Triage Log

> 2026-11-08 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `6454e04..工作树`，diff 57 kB / 1049 行。共 21 条发现，逐条裁决如下；`VG-*` 为验证缺口层预验证发现，按流程免复核。

- BH-1 `false` — 「spec frontmatter `in-review` 与 Implementation Notes 声称 `done` 不一致」：`in-review` 由本步骤写入，`done` 是实现收尾时的记述，属不同时间点的状态；修复为编辑本 build 规格，按 triage 规则 reject。
- BH-2 `false` — 「`deferred-work.md` 未标记媒体服务已闭合」：该文件是历史 deferred 日志，既有已解决项（AUTH_USER_MODEL、导航死链）同样保留不删；本次以代码实现闭合属既定惯例。
- BH-3 `false` — 「`epic-2-context.md` 缺 1–5 张上限」：compile-epic-context 规则明确「No story-level details」，张数上限是 Story 2.1 的实现细节，由本规格承载，epic 上下文只做定位。
- BH-4 `false` — 「未生成缩略图 / 未限像素尺寸 / 未防解压炸弹」：本故事不产生任何对外图片展示路径（列表/详情属 2.5/2.8），「未缩略」在交付程序中无可观测坏结果；冻结区把图片处理限定为格式/大小/张数校验，缩略应随后续展示需求生成。
- BH-5 `low` → rejected — 「`price > 0` 只在表单层，模型无 CheckConstraint」：本故事唯一写入路径是 `publish_view`（表单已拦截），admin 仅用于验收查看；补模型约束需新增迁移，超出本故事范围。已知取舍：后续故事若新增非表单写入路径，须在模型层补约束。
- BH-6 `low` → rejected — 「admin 裸注册使 `status`/`owner` 可编辑」：Django admin 默认可编辑是框架行为，演示中管理员只查看 pending 数据；限制写入需新增 ModelAdmin 与权限配置，非直接修正。与 BH-5 同根因。
- BH-7 `false` — 「`status`/`created_at` 无 `db_index`」：当前无任何对外查询面（列表/搜索/筛选属 2.5–2.8），「查询慢」的坏结果在交付程序中不可达。
- BH-8 `false` — 「`ProductImage` 无 ordering / 封面字段」：同上，当前无图片展示路径，2.5/2.8 需要时再定义封面与顺序，现在加字段只会产生用不上的 schema。
- BH-9 `low` → rejected — 「刷新 / 双击重放 POST 会再建一条 Product」：与 EC-2 同根因，见该行裁决。
- BH-10 `low` → rejected — 「I/O 矩阵把 PUT/PATCH/DELETE 一律标 405，但未登录会先 302」：`@login_required` 在外层本就是预期安全行为；补前提行需改冻结区矩阵，修复=编辑本 build 规格，按 triage 规则 reject。
- BH-11 `medium` → patch — 「合法 PNG 上传路径从未被用例执行」：与 VG-2 同根因，见该行。
- BH-12 `low` → patch — 「`title.max_length` / `price.max_digits` 等自定义中文错误文案无边界用例」：删除这些 `error_messages` 后现有用例不会失败；补边界断言是最小且不增加公开表面的修复。
- BH-13 `medium` → patch — 「DEBUG 下 `/media/` 路由无自动化回归」：与 VG-1 同根因，见该行。
- BH-14 `low` → rejected — 「多张图片出错时只返回第一条笼统提示」：规格只要求「中文表单错误」，未要求逐张定位；按文件聚合错误需新增错误聚合分支，属增加复杂度且用户日常不会因此受阻。
- EC-1 `false` — 「事务中第二张图片保存异常，首张文件残留」：所有图片在进入 `transaction.atomic()` 前已完成 Pillow 格式/大小/张数校验，保存阶段无可证明的异常路径；`test_mixed_valid_and_invalid_images_write_nothing` 已覆盖「校验失败零落盘」。
- EC-2 `low` → rejected — 「浏览器刷新 / 后退重放已成功的 POST 会重复建单」：真实但低危——成功页刷新会先被浏览器二次确认，且冻结区明确「不产生跳转」，常规 PRG 修复被排除；幂等令牌需引入 session 状态与隐藏字段，不是直接修正，且与已批准的成功态体验冲突。已知代价：用户确认重放后会多一条 `pending` 商品。与 BH-9 同组。
- EC-3 `false` — 「删除 Product / ProductImage 后文件不清理」：交付程序中没有任何删除商品的路径（下架/删除属 2.2/5.1），admin 仅用于验收查看，该场景不可达。
- VG-1 `medium` → patch — 预验证：删除 `config/urls.py` 的 `static()` 后 84 个用例仍全绿，但浏览器访问 `/media/...` 得到 404，「图片可被访问」无回归保护。补 `@override_settings(DEBUG=True)` + 重载 URLconf 的 GET 断言。
- VG-2 `medium` → patch — 预验证：把 `ALLOWED_IMAGE_FORMATS` 缩成只含 JPEG 后 22 个用例仍全绿，合法 PNG 会被误拒且测试不报错。补 PNG 成功用例与「按真实格式判定」的正向用例。
- VG-3 `medium` → patch — 预验证：把 `CATEGORY_CHOICES` 缩到只剩「教材」后现有用例仍全绿，其余合法分类/成色可静默失效。补遍历全部合法枚举值的 subTest 用例。
- VG-4 `medium` → patch — 预验证：删除 `base.html:16` 导航链接后 84 个用例仍全绿，但整个 UI 失去发布页唯一入口。补已登录页面对 `href` 与「发布商品」的断言。

**分组与处置：** 存活项按根因分 5 组，均 route `patch`，无 `intent_gap` / `bad_spec` / `defer`，不触发 loopback，`review_loop_iteration` 保持 0。
- 组 A（VG-1、BH-13）：开发期媒体服务缺少自动化回归。
- 组 B（VG-2、BH-11）：PNG 合法上传路径缺少回归证据。
- 组 C（VG-3）：分类/成色合法枚举值成功路径缺少回归证据。
- 组 D（VG-4）：导航「发布商品」入口缺少断言。
- 组 E（BH-12）：表单边界中文错误文案缺少断言。

## Design Notes

- 架构 ERD 明确 `PRODUCT ||--o{ PRODUCT_IMAGE`，且 FR-12 要求详情页展示「全部图片」；人类决策选定独立 `ProductImage` 实体、每商品 1–5 张，2.8 直接遍历关联集合即可，无需返工改模型。上限 5 张落实 AD-8「限制每商品图片张数」。
- AD-9 的可见性由 `status` 驱动，但 2.1 只写入 `pending`；列表/搜索/详情属 2.5–2.8，本故事不提前实现 `visible()` manager，避免在尚无查询面时造抽象。
- 未认证分支返回 200 提示而非 403/302：与 `accounts/views.py:66-70` 已认证用户访问 `/verify/` 重定向的做法互补，既给出原因也保留去认证出口；`@login_required` 在外层，保证未登录仍优先 302。
- 成功态留在发布页而非跳转：2.4「我的发布」与 2.8 详情页均未实现，跳转会落到空状态或 404，产生死链；参照 `verify.html:10-16` 的 `submitted` 分支做法。
- 图片校验不能信任扩展名：`Image.open(file).verify()` 后按 `img.format` 判定 JPEG/PNG；校验前后需 `file.seek(0)` 复位，保证保存内容完整。
- 表单（`ProductForm`）与图片（`request.FILES.getlist('images')`）分两层校验：图片失败时用 `form.add_error(None, ...)` 汇入同一错误区，并在 `transaction.atomic()` 内保存，避免「商品已建、图片失败」的部分落库。
- `LANGUAGE_CODE='en-us'`，所有用户可见文案必须手写中文，不能依赖 Django 内置翻译。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 无问题
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（迁移已生成）
- `.venv/Scripts/python.exe manage.py migrate` — expected: `listings.0001_initial` 成功应用
- `.venv/Scripts/python.exe manage.py test` — expected: 全部通过（62 个既有 + 新增 `PublishViewTests`）

**Manual checks (if no CLI):**
- `runserver` 后用已认证账号打开发布页上传一张本地 JPEG，确认 `media/products/` 出现文件、DB 中 `Product` 为 `pending`，且 DEBUG 下 `/media/...` 可访问。
