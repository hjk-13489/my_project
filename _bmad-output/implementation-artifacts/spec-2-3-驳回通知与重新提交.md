---
title: '驳回通知与重新提交'
type: 'feature'
created: '2026-11-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: da46035c9615b35f0568fd04e934a375caada2e9
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.2 已把商品状态流转收敛到模型层，并明确把 `rejected → pending` 留给 2.3，但商品被驳回后卖家既收不到任何驳回理由，也没有把原商品改回待审核的入口；FR-7 与 UJ-1 的驳回分支因此断在「已驳回」这一终态，审核闭环无法继续，2.4「我的发布」与 5.1 管理员待审核区也没有可衔接的数据面。

**Approach:** 在 `listings` 内补齐驳回理由的落库与展示，让卖家在「我的消息」看到本人被驳回商品的理由，并基于原商品修改后重新提交；重提仍走 2.2 的模型层状态机（新增唯一合法转移 `rejected → pending`），不新建商品、不绕过 `visible()` 的 approved 唯一门控。

**Decision（人类决策，2026-11-09）:** ① Q1=A：只做消费端——扩展模型层 `reject()` 使其可携带驳回理由，并在合法流转时生成通知供 5.1 调用；**不新增任何驳回 / 审核入口**，`listings/admin.py` 保持 2.2 的裸注册不变，驳回数据由测试夹具或后续 5.1 产生（接受「演示中无法从界面造出驳回」这一代价）；② Q2=A：新增独立通知实体并落在 `listings`（随 `0002` 迁移），个人中心「我的消息」卡片渲染本人通知列表，**重提后历史驳回理由仍保留**，后续 5.2 下架通知与 FR-27 裁决通知可复用该实体，不新建独立消息页面；③ Q3=A：重提复用 `ProductForm` 五字段，**图片为可选**——不传则保留原图，传了则按 `validate_images` 校验后在事务内替换原图；④ Q4=A：允许由 `makemigrations` 生成 `listings/migrations/0002_*.py` 并执行 `migrate` 更新本地 `db.sqlite3`（已 gitignore），不动 `media/` 已有文件，接受本地 schema 变更不可逆；⑤ 规格体量选择**保留完整规格**、不拆分次级项（与 D-029 及 2.2 决策 ① 一致），context-rot 风险由 Step 4 三层审查兜底。以上五项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 驳回理由必须能在卖家「我的消息」中被看到，且仅本人可见：通知记录归属本人，服务端按 `owner=request.user` 过滤，禁止仅靠前端隐藏，跨用户访问不得泄露商品标题或理由。
- 驳回理由以**独立通知实体**落在 `listings`，由 `reject()` 在合法流转时原子生成；通知不随商品状态变化而被删除或清空，**重提后历史理由仍可在「我的消息」看到**。
- 重新提交作用于**原商品**（主键、`owner`、`created_at` 不变），不新建 `Product`；成功后 `status='pending'` 且已持久化，`status` 绝不接受请求传值。
- `rejected → pending` 是本次新增的唯一合法转移，必须落在 `ALLOWED_TRANSITIONS` 与 `_transition()` 的既有唯一入口；非法转移仍抛 `InvalidTransition` 且不落库、**不生成通知**，`pending → approved/rejected` 语义不变。
- `Product.objects.visible()` 的定义与语义一字不变，`approved` 仍是唯一对外可见状态；重提后的 `pending` 商品立即不被 `visible()` 命中。
- 重提复用 `ProductForm` 五字段；**图片为可选**——不传则保留原图，传了则按 `validate_images`（≥1 张、仅 JPEG/PNG、单图 ≤5MB）校验后在**同一事务内**替换原图，不得部分替换。
- 所有写操作要求登录 + `is_verified`；读「我的消息」要求登录；越权重提与不存在的商品返回 404（不泄露存在性）。
- 保持 2.1 / 2.2 全部行为与既有 102 个用例不变。
- 全中文用户可见文案与异常消息（`LANGUAGE_CODE='en-us'` 不自译）；Bootstrap 5.3 + Django 模板服务端渲染，不引入新依赖。
- 审核动作（通过 / 驳回 / 填写理由）由 Epic 5 的 5.1 触发，本故事不实现管理员待审核区或审核界面。

**Never:**
- 不实现 2.4「我的发布」、2.5–2.8（列表 / 搜索 / 筛选 / 详情）、5.1 / 5.2（管理员待审核区 / 下架）、Epic 3 聊天与 FR-16 未读提示、Epic 4 订单。
- **不新增任何驳回 / 审核入口**（含 admin action、演示用驳回页 / URL）；`listings/admin.py` 保持裸注册一字不改；不改 `chat` / `accounts` 的模型层、不新建独立「我的消息」页面。
- 不改 `visible()`、`STATUS_CHOICES` 四值与中文显示名、`ProductImage`、`approve()` 签名与语义、已应用的 `listings/migrations/0001_initial.py`；不定义 `approved → offline` / `offline → *` 的转移。
- 不在视图里直接写 `status` 字面量、不在别处另写 `status='approved'` 查询；不改 `config/urls.py` 的 DEBUG `static()`（`listings/tests.py:305` 硬断言）、不改 `listings/views.py:35` 新建商品的 pending 写入点。
- 不引入 DRF / API / SPA / WebSocket / 新第三方依赖；不往运行时 `db.sqlite3` / `media/` 手工造演示数据（等价路径由测试用例在内存测试库覆盖）；不改动 `media/` 中已有文件。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 卖家看到驳回理由 | 本人存在一条驳回通知（关联 `rejected` 商品） | 「我的消息」展示商品标题 + 驳回理由 + 状态，且仅本人数据 | N/A |
| 重提后历史仍在 | 同一商品重提后 `status='pending'` | 原驳回通知仍可在「我的消息」看到，理由不被清空或删除 | N/A |
| 消息空状态 | 登录卖家无任何通知记录 | 「我的消息」保持中文空状态文案 | N/A |
| 越权隔离 | 用 A 账号访问 B 的通知 / 重提 B 的商品 | 看不到 B 的任何标题与理由；直接重提返回 404 | 404，不泄露存在性 |
| 未登录 | 匿名访问消息 / 重提页 | 302 到登录页并带 `next` | N/A |
| 修改重提（不传图） | 本人 `rejected` 商品 + 合法五字段、无新图片 | 五字段更新、`status='pending'` 持久化、`visible()` 不命中、原图数量与内容不变、主键与 owner 不变 | N/A |
| 修改重提（传图） | 同上 + 1–5 张合法新图 | 原图在同一事务内被替换为新图，字段与状态同步更新，不留部分替换 | N/A |
| 表单 / 图片校验失败 | 价格 ≤0、缺必填、图片格式或数量不合法 | 留在表单页显示中文错误，不写库，状态仍为 `rejected`，原图不变 | 表单错误 |
| 非驳回态重提 | `pending` / `approved` / `offline` 商品访问重提 | 拒绝重提，状态与 DB 不变 | 404 或中文提示 |
| 非法转移 | 直接对非 `rejected` 实例调用重提方法 | 抛 `InvalidTransition`，状态与 DB 不变，且不生成通知 | 显式异常，不静默忽略 |
| 重提后再审核 | 重提后的商品再走 `approve()` / `reject()` | 与 2.2 完全一致（`pending → approved/rejected`），新驳回生成新通知 | N/A |
| 全量回归 | `manage.py test` | 既有 102 用例 + 本故事新增用例全绿 | N/A |

</frozen-after-approval>

## Code Map

- `listings/models.py:5-14` — `InvalidTransition` 与 `ProductQuerySet.visible()`（`filter(status='approved')`）：本次**不改**，它是对外可见性唯一门控；新增代码不得另写 `status='approved'` 字面量查询。
- `listings/models.py:31-44` — `STATUS_CHOICES` 四值与 `ALLOWED_TRANSITIONS`（`pending: ('approved','rejected')`，其余为空元组；L37-38 注释明确 `rejected → pending` 留给 2.3）。本次把 `rejected` 改为 `('pending',)`，新增 `resubmit()` 委托 `_transition('pending')`；不改 `approve()` 签名与语义。
- `listings/models.py`（新增） — 驳回通知实体（模型名 / 字段由实现按项目约定确定，建议含 `owner` FK、`product` FK、`reason` 文本、`created_at`），落在 `listings` 内、不跨 app import；`reject(reason=...)` 在 `_transition()` 校验通过后，与状态写入处于同一 `transaction.atomic()` 内创建通知记录，非法转移不得留下通知。通知按 `owner` 过滤展示，重提后不删除。
- `listings/models.py:75-93` — `approve()` / `reject()` / `_transition()`：校验在赋值与 `save(update_fields=['status','updated_at'])` 之前，非法转移抛 `InvalidTransition` 且不落库。扩展 `reject()` 时必须保持「先校验、后写入」顺序，通知生成只能发生在校验通过之后，否则非法转移会留下脏通知。
- `listings/models.py:96-113` / `listings/migrations/0001_initial.py` — `ProductImage`（`product` FK `related_name='images'`、`ImageField(upload_to='products/')`）与已应用迁移均不改；替换图片须在同一事务内增删记录，沿用 2.1 的 `upload_to` 约定。
- `listings/migrations/0002_*.py`（新增） — 由 `makemigrations` 生成通知实体所需表；冻结决策 ④ 允许生成并执行 `migrate` 更新本地 `db.sqlite3`（已 gitignore），禁止手改 `0001_initial.py`。
- `listings/views.py:12-43` — `publish_view` 范式：`@login_required` 外层 + `require_http_methods(['GET','HEAD','POST'])` 内层、未认证 200 提示页、`transaction.atomic()` + `form.save(commit=False)` + 服务端强制 `owner` / `status='pending'`（L35 不得改）、图片错误经 `form.add_error(None, ...)` 汇入 `non_field_errors`、成功留在 `submitted` 成功态。重提视图照此编排，但不得复制新建商品的 pending 写入点。
- `listings/forms.py:13-44,47-103` — `validate_images`（1–5 张 / 单图 5MB / Pillow `verify()` 按真实格式判 JPEG·PNG / `seek(0)` 复位）与 `ProductForm`（五字段、`clean_price()>0`、全中文 `error_messages`）。重提直接复用，不另建第二套校验。
- `listings/urls.py:4-6` / `config/urls.py:29-39` — 现有唯一商品路由 `publish/`（name=`publish`）；新路由追加在 `listings/urls.py`，`config/urls.py` 不改（`listings/` include 已存在）；DEBUG `static()` L38-39 被 `listings/tests.py:305` 硬断言。
- `listings/admin.py:4-6` — 裸注册 `Product` / `ProductImage`：按冻结决策 ① 与 2.2 决策 ③ **一字不改**，不加 action、不注册通知模型；本次交付须以空 diff 佐证。
- `accounts/views.py:122-136` — `profile_view`：`@login_required` + `@require_safe`，硬编码 `my_messages_empty=True` 等四个空状态标志；本次把「我的消息」接上本人通知查询（`owner=request.user` 过滤）并去掉该标志的恒真，其余三个板块与装饰器保持不变。
- `templates/accounts/profile.html:83-94` — 「我的消息」卡片空状态占位（注释指向 Epic 3）；`:12-54` 展示 `card` / `list-group` / `badge` / `dl.row` 风格，未用 `<table>`。`templates/base.html:6,34` 为 `title` / `content` block，`:10-31` 导航按登录态分支，Bootstrap 5.3 CDN。新模板沿用此风格。
- `templates/listings/publish.html:26-94` — 表单渲染范式（`enctype="multipart/form-data"`、`novalidate`、`non_field_errors` 警示块、逐字段 `form-control` / `form-select`、文件 `multiple`、中文标签）；重提页复用同一结构。
- `listings/tests.py` — `PublishViewTests`（28 例，L30）、`ProductVisibilityTests`（12 例，L379）、`_make_image` L21、`_TEST_MEDIA_ROOT` L18 + `@override_settings` L29/378、`setUp` 用 `User.objects.create_user(student_id=..., username=..., password=...)` L43。新增测试类追加在文件末尾，勿改既有 40 例。
- `accounts/tests.py` — 62 例（含个人中心断言，改 `profile_view` 上下文必须回归）；`chat/orders/dashboard` 的 tests.py 为空壳。全项目基线 102 例。
- `requirements.txt` / `.venv/Scripts/python.exe` — Django 5.2.19 / Pillow 13.0.0 / Python 3.13.1 已锁定；系统 PATH 的 `python` 无 Django，验证一律用 `.venv/Scripts/python.exe`。
- `_bmad-output/planning-artifacts/stories.md:89-96` — 2.3 的 AC（`rejected` 时「我的消息」显示理由；修改重提后回到 `pending`）、测试断言与 FR-7 依赖；`prd.md:149-155`（FR-7）、`:311-317`（FR-25 驳回填理由 → 通知卖家）、`:43-46`（UJ-1 驳回分支）、`:86`（「我的消息」术语）、`:359-360`（写操作需登录、只访问本人数据）。
- `_bmad-output/implementation-artifacts/epic-2-context.md:26,45,51-54` — 「驳回理由送达卖家『我的消息』，卖家可修改原商品重提，状态回到 pending」；「审核动作由 Epic 5 触发，本史诗只消费由此产生的 status，不实现审核界面」。
- `_bmad-output/project-context.md:12,38-48` — 实体归所属 app 唯一定义、服务端强制权限、中文文案、命名与 `DecimalField` 约定。
- `_bmad-output/implementation-artifacts/spec-2-2-商品状态流转-待审核-上架-驳回.md:22,36-38,106-112,142-148` — 2.2 冻结决策 ③④（不建审核界面、`rejected → pending` 留给 2.3）、`as_manager()` 不产生迁移、admin 保持裸注册、`_transition` 唯一入口、中文文案不依赖 Django 翻译。
- `_bmad-output/implementation-artifacts/sprint-status.yaml:50` — `2-3-驳回通知与重新提交: backlog`，收尾时同步。

## Tasks & Acceptance

**Execution:**
- [x] `listings/models.py` — 新增驳回通知实体、`ALLOWED_TRANSITIONS['rejected'] = ('pending',)` 与 `resubmit()`，并让 `reject()` 可携带理由且在合法流转时原子生成通知；不改 `visible()` / `STATUS_CHOICES` / `ProductImage` / `approve()` 语义 — 兑现 FR-7 的数据面与状态机唯一入口。
- [x] `listings/migrations/0002_*.py` — 由 `makemigrations` 生成与模型一致的迁移并执行 `migrate`；不手改已应用的 `0001_initial.py` — 兑现冻结决策 ④ 的 schema 落地。
- [x] `listings/views.py` + `listings/urls.py` — 新增重提视图与语义化路由（如 `/listings/<int:pk>/resubmit/`），复用 `ProductForm` / `validate_images`，服务端强制 owner + `status='rejected'`，事务内更新五字段、可选替换图片并调用 `resubmit()` — 兑现「修改重提」与越权门控。
- [x] `templates/listings/resubmit.html`（或等价命名） — 复用 `publish.html` 结构渲染表单、驳回理由、原图提示与中文错误 / 成功态 — 兑现可操作的用户入口。
- [x] `accounts/views.py` + `templates/accounts/profile.html` — 「我的消息」卡片渲染本人通知列表（标题 + 理由 + 时间 + 状态），保留中文空状态；不改其他三个板块与 `profile_view` 的装饰器 — 兑现 FR-7 的「驳回理由送达」。
- [x] `listings/tests.py`（并回归 `accounts/tests.py` 的个人中心用例） — 新增测试类覆盖 I/O 矩阵各行：通知可见性与越权、重提后历史仍在、空状态、未登录、重提成功与持久化、不传图 / 传图两分支、校验失败不落库、非驳回态 / 非法转移拒绝且不生成通知、重提后再审核、全量回归 — 冻结验收的可执行证据。
- [x] `spec-2-3-驳回通知与重新提交.md` 与 `sprint-status.yaml` — 状态同步（`2-3-驳回通知与重新提交`） — 工作流收尾。

**Acceptance Criteria:**
- Given 一条带驳回理由的 `rejected` 商品，When 卖家查看「我的消息」，Then 能看到该商品标题与理由，且其他账号看不到任何相关信息；商品重提后该理由仍可见。
- Given 卖家基于该商品修改并重新提交，When 表单合法且不传图片或传合法图片，Then 原商品主键与 owner 不变、`status='pending'` 已持久化、`visible()` 不命中、图片按对应策略处理，且可再次被 `approve()` / `reject()` 流转。
- Given 任一非法路径（越权、非 `rejected` 态、未登录、表单 / 图片不合法、直接调用非法转移），When 尝试重提，Then 不产生任何 DB 写入、状态变化或通知记录，并返回 404 / 中文错误 / `InvalidTransition`。
- Given 2.1 / 2.2 与 1.1–1.5 的既有实现，When 运行完整测试套件与 `check`，Then 既有 102 个用例全部通过且 0 issues。
- Given 交付范围，When 查看 diff，Then 不含 5.1 审核界面、2.4 / 2.5–2.8 页面、Epic 3 聊天与未读提示，`visible()`、`0001_initial.py` 与 `listings/admin.py` 保持不变，且无任何新增驳回入口。

## Implementation Notes

- 实现按冻结意图完成，改动文件：`listings/models.py`、`listings/views.py`、`listings/urls.py`、`listings/migrations/0002_rejectionnotice.py`（makemigrations 生成）、`templates/listings/resubmit.html`、`accounts/views.py`、`templates/accounts/profile.html`、`listings/tests.py`（仅末尾追加，既有 40 例一字未改）。`listings/admin.py`、`listings/migrations/0001_initial.py`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`ProductForm` / `validate_images`、`ProductImage`、`STATUS_CHOICES`、`visible()` 均未改。
- `listings/models.py`：新增 `RejectionNotice`（`owner` FK → `related_name='rejection_notices'`、`product` FK → `related_name='notices'`、`reason` TextField、`created_at`，`Meta.ordering=('-created_at',)`），落在 `listings` 内、不跨 app import 模型。`ALLOWED_TRANSITIONS['rejected'] = ('pending',)` 并新增 `resubmit()` 委托 `_transition('pending')`；`reject(reason='')` 在 `transaction.atomic()` 内先经 `_transition()` 校验、状态写入后用 `save(update_fields=['status','updated_at'])` 持久化，再原子创建通知，故非法转移不落库、不生成通知。`approve()` 签名与语义、`visible()`、`ProductImage` 均保持 2.2 原样。通知不随商品状态变化删除，重提后历史理由仍在。
- 迁移：`.venv/Scripts/python.exe manage.py makemigrations listings` 生成 `0002_rejectionnotice.py` 后执行 `migrate` 更新本地 `db.sqlite3`（冻结决策 ④，文件已 gitignore）；未手改 `0001_initial.py`，未往 `media/` 造演示数据。
- `listings/views.py` / `urls.py`：`resubmit_view` 采用与 `publish_view` 相同的 `@login_required` 外层 + `require_http_methods(['GET','HEAD','POST'])` 内层；未认证统一 200 提示页且不做商品查询，避免存在性泄露；`get_object_or_404(Product, pk=pk, owner=request.user, status='rejected')` 让越权 / 不存在 / 非驳回态统一 404。复用 `ProductForm(instance=product)` 与 `validate_images`，图片可选（不传跳过校验、保留原图；传图则校验后在同一 `transaction.atomic()` 内先删后增完成整体替换）；`status` 不接受请求传值，仅由 `product.resubmit()` 写回 `pending`；成功留在 `submitted` 成功态。路由 `listings/<int:pk>/resubmit/`（name=`resubmit`）追加在 `listings/urls.py`，`config/urls.py` 未动。
- `templates/listings/resubmit.html`：复用 `publish.html` 的表单 / 错误 / 提示结构，渲染驳回理由、原图数量提示、可选图片上传与中文成功态。`accounts/views.py` 的 `profile_view` 按 `owner=request.user` 用 `RejectionNotice.objects.filter(...).select_related('product')` 查询本人通知，保留其余三个空状态标志与装饰器；`my_messages_empty` 改为按实际列表求值（无通知仍为 `True`，既有个人中心用例不受影响）。`profile.html`「我的消息」卡片保留原中文空状态文案，非空时渲染标题 + 理由 + 时间 + 商品状态，并在商品仍为 `rejected` 时给出「修改并重新提交」入口。
- `listings/tests.py` 末尾追加 `RejectionNoticeAndResubmitTests`（18 例，自包含夹具，独立 `@override_settings(MEDIA_ROOT=临时目录)`），覆盖矩阵各行：本人可见 / 跨用户不可见、重提后历史理由仍在、空状态、未登录 302+next、未认证提示页、GET 预填与理由展示、不传图与传图两分支、请求伪造 status 被忽略、表单 / 图片校验失败不落库、非驳回态 404、非法 `resubmit()` / `reject()` 抛 `InvalidTransition` 且不生成通知、重提后 `approve()` / 再 `reject()` 生成新通知、`visible()` 不命中。
- 验证（`.venv/Scripts/python.exe`，Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0）：`manage.py check` → 0 issues；`makemigrations --check --dry-run` → `No changes detected`；`migrate` → `0002` 正常应用（复跑为 `No migrations to apply`）；`manage.py test -v 2` → **120 tests OK**（既有 102 + 新增 18），无失败 / 跳过。`git diff -- listings/admin.py`、`0001_initial.py`、`config/urls.py` 均为空；`git diff --name-status` 仅含上述交付文件；全仓 grep 确认 `status='approved'` 字面量查询仍只在 `listings/models.py:14` 的 `visible()`。
- 范围复核：未新增任何驳回 / 审核入口（`listings/admin.py` 保持裸注册，无 admin action、无演示驳回页），未实现 2.4 / 2.5–2.8 / 5.1 / 5.2 / Epic 3 聊天与 FR-16 未读提示 / Epic 4 订单；未引入新依赖。演示中仍无法从界面造出驳回数据（冻结决策 ① 的已知代价），等价路径由测试用例在内存测试库覆盖。
- 状态更正与主代理 Step 3 复核：实现子代理越权把本规格 frontmatter 与 `sprint-status.yaml` 的 `2-3` 由 `in-progress` 直接置 `done`，**已撤回**——Step 3 期间二者应保持 `in-progress`，`done` 属 Step 5 收尾终态（与 spec-2-2 L111 的同类更正一致）；`last_updated` 同步为 `11-09-2026 10:39`。上一段「验证」描述的是实现完成态，不是工作流状态。
- 主代理独立验收（不依赖实现子代理报告）：把 `da46035..工作树` 的完整统一 diff（含 3 个未跟踪文件，920 行）读入上下文逐项核对，7 项任务与 5 条 AC 均满足；独立复跑 `.venv/Scripts/python.exe` 得 `check` → 0 issues、`makemigrations --check --dry-run` → `No changes detected`、`migrate` → `No migrations to apply`、`test -v 2` → **120 tests OK**（102 既有 + 18 新增，0 失败 / 跳过）。矩阵 12 行均有覆盖测试，且 18 个 `RejectionNoticeAndResubmitTests` 用例在 `-v 2` 输出中逐条 `... ok`，无跳过 / 未注册。`git diff` 对 `listings/admin.py`、`0001_initial.py`、`config/urls.py`、`config/settings.py`、`requirements.txt`、`listings/forms.py` 均为空；全仓 `status='approved'` 字面量查询仍只在 `listings/models.py:14`。
- 已知取舍（交付范围外，供 Step 4 / 后续故事评估）：① 实现新增 `RejectionNotice.can_resubmit` 只读模型属性（规格未点名），用途是让模板不出现 `status` 字面量；② 图片替换删的是 `ProductImage` 记录，磁盘旧文件不删除，`media/` 会累积孤儿文件（冻结区要求「不改动 `media/` 中已有文件」，故本次不清理）；③ `reject()` 不传理由也会生成通知（`reason` 为空，模板显示「无」），与「合法流转即生成通知」一致；④ `RejectionNotice` 两个 FK 均为 `CASCADE`，删除商品 / 用户会连带删通知，5.4 落地时需评估；⑤ 本地 `db.sqlite3` schema 变更不可逆（冻结决策 ④ 允许，文件已 gitignore）。
- Step 4 三层审查与补丁（主代理）：首轮 26 条发现（BH 17 / EC 8 / VG 1），逐条核验后 **24 条驳回、2 条 `medium` → `patch`**，0 `intent_gap` / `bad_spec` / `defer`、无 loopback，`review_loop_iteration` 保持 0；逐条裁决与证据见 `Review Triage Log`。`patch` 由同一实现子代理（resume `agent-750e9e3f-c3a9-4c48-b7e2-7c4cd6294bd1`）执行：`resubmit_view` 增加「0 图商品不传新图则报中文错误且不写库」守卫，`RejectionNoticeAndResubmitTests` 由 18 例增至 21 例（界面入口出现 / 消失、`can_resubmit` 两态、0 图守卫），并给 2 个受守卫影响的既有新增夹具补 1 张图。
- 主代理补丁后独立复验：`check` → 0 issues；`makemigrations --check --dry-run` → `No changes detected`；`migrate` → `No migrations to apply`；`test -v 2` → **123 tests OK**（102 既有 + 21 新增，0 失败 / 跳过），21 个新用例在 `-v 2` 输出逐条 `... ok`；`git diff` 对 `admin.py` / `0001_initial.py` / `forms.py` / `settings.py` / `requirements.txt` / `config/urls.py` 均为空；`diff_file` 已重刷为 73,165 B / 1002 行。
- Step 5 收尾（主代理）：本规格 `status` 置 `done`；`sprint-status.yaml` 的 `2-3` 按 `sync-sprint-status.md` 置 `review`（`done` 由后续独立代码审查收尾写入，与 spec-2-2 L112 惯例一致），`last_updated: 11-09-2026 11:24`。上述各阶段状态记述以本条为最终口径。

## Spec Change Log

## Review Triage Log

> 2026-11-09 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `da46035..工作树`，diff 62,889 B / 923 行（含 3 个未跟踪文件）。共 26 条原始发现（BH 17 / EC 8 / VG 1）；逐条核验后 **24 条驳回、2 条 `medium` → patch**，0 个 `intent_gap` / `bad_spec` / `defer`、无 loopback，`review_loop_iteration` 保持 0。Verification Gap 层唯一 gap finding 按其证据规则预验证并采信。

**Rejected**
- BH-1 `false` — 「Spec Change Log / Review Triage Log 空节」：模板明写「Empty until the first bad_spec loopback」与「Empty until the first review pass」，本轮正是首轮且正在写入；修复=编辑本规格。
- BH-2 `false` — 「spec `in-review` 与 sprint `in-progress` 不一致」：Step 4 要求规格置 `in-review`，Step 3 只把 sprint 同步为 `in-progress`，Step 5 收尾才统一；与 spec-2-2 L136 同类裁决一致，属阶段差。
- BH-3 `false` — 「frontmatter 缺 last_updated」：模板 frontmatter 无该字段；修复=编辑本规格。
- BH-4 `false` — 「context 清单未收录 Code Map 引用的文档」：模板要求 context「Keep short — only what isn't already distilled into the spec body」，这些引用已写入 Code Map 正文，无需实现代理重复加载。
- BH-5 `false` — 「矩阵缺 `is_verified=False` 行」：冻结 Always 已约束，`test_unverified_user_gets_prompt_page` 已运行通过；修复=编辑冻结区规格。
- BH-6 `false` — 「矩阵缺多条通知 / 多次驳回循环场景」：`Meta.ordering=('-created_at',)` 与重提页 `.first()` 已确定展示最新理由；所有通知指向同一商品，`can_resubmit` 随商品状态一致变化，历史与最新按钮行为不矛盾。
- BH-7 `false` — 「Always 漏写 ≤5 张上限」：图片约束唯一定义在 `validate_images`（`MAX_IMAGES=5`），Code Map / 矩阵 / 模板均为 1–5 张，上传 6 张被拒；修复=编辑冻结区规格。
- BH-8 `low` → rejected — 「`reject()` 空理由也生成通知」：冻结决策 ① 已接受该取舍并记入 Implementation Notes，5.1 之前无生产调用者；修复需新增非空校验分支，属新增状态。
- BH-9 `low` → rejected — 「缺事务中途故障注入验证」：`transaction.atomic()` 语义由 Django 保证，「非法转移不留通知」已由 `test_illegal_reject_creates_no_notice` / `test_illegal_resubmit_raises_and_creates_no_notice` 覆盖；补 mock 注入属新增测试复杂度而非修正缺陷。
- BH-10 `false` — 「未认证页未断言不泄露商品信息」：`resubmit.html` 的 `needs_verification` 分支只渲染提示，不输出 `product` / `reason` / `image_count`，读模板即可反证。
- BH-11 `low` → rejected — 「未登录门控缺匿名 POST 覆盖」：`@login_required` 对 GET/POST 一致生效，矩阵「未登录」行明确 302 + next；补一条 POST 断言属额外证明。
- BH-12 `low` → rejected — 「图片校验失败未断言通知数不变」：该分支在 `form_valid and not image_errors` 之外，根本不进入写库 / 通知创建路径，通知数不变由代码结构保证。
- BH-13 `false` — 「Verification Commands 未逐项列出未改动清单」：主代理 Step 3 已独立执行 `git diff` 对 `forms.py` / `settings.py` / `requirements.txt` / `0001_initial.py` / `config/urls.py` 的空检查并记入 Implementation Notes；修复=编辑本规格。
- BH-14 `false` — 「跨 app import 未纳入决策」：架构允许同层跨 app import，`accounts/views.py` 只做只读查询、未改 `accounts` 模型层、未复刻实体，符合 `project-context.md:12`；Design Notes 已把 profile 卡片列为共享表面。
- BH-15 `false` — 「矩阵↔测试缺机械追溯表」：Step 3 主代理已逐行核对 12 行矩阵与 18 个用例的 `-v 2` 输出并记入 Implementation Notes；修复=编辑本规格。
- BH-16 `low` → rejected — 「无原图缩略图预览」：冻结区只要求「原图提示」，已实现；补缩略图需新增媒体 URL 渲染，属新增 UI 复杂度，演示环境 NFR 未要求。
- BH-17 `false` — 「Implementation Notes 记 920 行而当前 diff 923 行」：920 是 Step 3 时点快照，之后追加 3 行主代理复核记述与状态变更；Step 4 已重刷 `diff_file`；修复=编辑本规格。
- EC-1 `low` → rejected — 「重提成功后刷新重发 POST 命中 404」：与 2.1 D-011「POST 成功后 200 成功态不跳转」及 spec-2-1 审查「不引入幂等 token」的既有裁决一致；且 404 不产生重复数据，比 2.1 的重复商品更轻；改 PRG 需改变冻结成功态体验。
- EC-2 `low` → rejected — 「并发在 `get_object_or_404` 之后改动状态」：与 2.2 审查 BH-7 / EC-2 同根因，spec-2-2 已记载「5.1 引入真实审核调用者时必须补 DB 端校验」；本次无生产调用者，修复需 `select_for_update` / 条件更新。
- EC-3 `low` → rejected — 「通知列表查询无上限」：演示数据量小，NFR-1 只约束列表 / 搜索；加切片或分页会隐藏历史通知，与「重提后历史理由仍保留」冲突。
- EC-4 `false` — 「`owner` 与 `product.owner` 不一致时泄露」：`RejectionNotice` 唯一创建点 `reject()` 取 `owner=self.owner`（即商品 owner），二者恒一致；`profile_view` 已按 `owner=request.user` 过滤，无可到达的不一致路径。
- EC-5 `low` → rejected — 「并发 `reject()` 生成多条通知」：同 EC-2 根因（陈旧实例 / 并发），2.2 已裁决并留待 5.1，修复需新增锁或唯一约束。
- EC-6 `low` → rejected — 「通知创建失败后内存 `status` 脏」：`reason` 为 `TextField(blank=True)` 且 `reject()` 默认 `''`，需显式传 `None` 且无生产调用者；修复需异常路径 `refresh_from_db()` 新分支，与 2.2 EC-1 同类裁决。
- EC-8 `false` — 「AC-3 要求未登录返回 404 但实现为 302」：矩阵「未登录」行明确 302 + `next`，`test_login_required_for_messages_and_resubmit` 断言 302 并通过；AC-3 的斜杠列表是概括性错误枚举而非逐项映射，修复=编辑本规格。

**Patch（存活项）**
- EC-7 `medium` — `listings/views.py:70-82`：0 图商品重提且不传新图时 `image_errors=[]` 直接放行，可让 0 图商品回到 `pending` 并经 5.1 上架，违反 `epic-2-context.md:24`「每商品 ≥1 张图片」。0 图状态可达（`listings/admin.py` 裸注册可删 `ProductImage`，测试夹具亦可构造）。最小修复：无新图且 `product.images.count() == 0` 时 `form.add_error(None, 中文错误)` 并留在表单页、不写库；补一条用例断言状态与原图数不变。修复琐碎、不增公共表面、只守护已演示状态 → `patch`。
- VG-1 `medium`（Verification Gap 层预验证，采信其 filed evidence） — `templates/accounts/profile.html` 的「修改并重新提交」分支与 `listings/models.py` 的 `can_resubmit`：二者无任何断言覆盖。该层实跑 33 个相关用例确认全绿但未观察入口，并给出 Demonstration——把 `can_resubmit` 改为恒 `False`（或恒 `True`）后 120 用例仍全绿，而按冻结决策 ① 这是唯一的界面入口，回归会让 FR-7 闭环从界面不可达，或重提后残留必然 404 的死链。最小修复：在 `RejectionNoticeAndResubmitTests` 补 1–2 个用例，断言 `rejected` 时按钮文案与 `href` 出现、重提后（`pending`）按钮消失，并断言 `can_resubmit` 两态取值 → `patch`。

**分组与处置：** 2 条存活项根因不同（0 图边界缺守卫 vs 界面入口缺回归断言），不构成同组，各自路由 `patch`；无 `intent_gap` / `bad_spec` / `defer`，不触发 loopback，`review_loop_iteration` 保持 0。

## Design Notes

- **路径判定（Step 2 事实）**：Intent gaps 原为 4 项，已由人类于 2026-11-09 全部拍板（冻结区 Decision ①–④），规格体量按决策 ⑤ 保留完整、不拆分；Irreversibles = 新增 `0002_*.py` 迁移与执行 `migrate` 更新本地 `db.sqlite3`（已 gitignore，schema 变更需手工回滚）；Footprint ≈ 8–10 个文件，新增 1 个 URL / 1 个模板 / 1 个通知实体 / 1 个模型方法，且 `profile_view` 的上下文与 profile.html 的「我的消息」卡片是后续 Epic 也要依赖的共享表面。故 `route: dispatch`、写完整规格，不走 oneshot。
- **状态机复用**：`rejected → pending` 只应作为 `ALLOWED_TRANSITIONS` 的一条新增项接入既有 `_transition()`，而不是在视图里直接 `product.status = 'pending'`；这与 2.2 冻结决策 ④ 的预留注释、以及 `project-context.md:12`「实体生命周期方法归所属 app 唯一定义」一致。重提方法应沿用 `save(update_fields=[...])` 范式并在校验通过后才写入，避免非法转移留下副作用。
- **可见性不动**：`visible()` 是 2.5–2.8 与 5.1 共用的唯一门控，本次任何新增查询都不得绕过它；`Product.objects` 基础查询集仍需含非 `approved` 商品，否则重提视图与 2.4「我的发布」将查不到被驳回商品。「我的消息」走通知实体而非商品状态派生，因此重提后历史理由仍在。
- **消息载体归属**：按冻结决策 ②，通知实体落在 `listings`（Epic 2 归属，且理由与商品强关联），避免提前动 `chat`（Epic 3）或 `accounts` 的模型层；「我的消息」复用个人中心现有卡片渲染本人通知列表，不新建独立页面，也不实现 FR-16 未读提示。后续 5.2 下架通知、FR-27 裁决通知可复用该实体。
- **产生端边界与演示数据**：按冻结决策 ①，本次**只做消费端**——`reject(reason=...)` 是供 5.1 调用的模型层 API，本次与 2.2 的 `approve()`/`reject()` 一样没有生产调用者；不得新增 admin action 或演示驳回页。驳回数据由测试用例在内存测试库构造，等价路径覆盖 FR-7，不往运行时 `db.sqlite3` 造数（沿用 spec-2-2 Implementation Notes 的做法）。独立审查应重点核验「通知生成与状态写入是否同事务」及「非法转移是否留下通知」。
- **迁移尺度**：本项目为 SQLite 演示环境、数据量小，不为通知表额外加索引或 `CheckConstraint`；迁移只由 `makemigrations` 生成并执行 `migrate`，禁止手改已应用的 `0001_initial.py`（沿用 2.2「不改 schema」被否决后确立的最小迁移尺度）。
- **文案与验证**：`LANGUAGE_CODE='en-us'`，所有用户可见文案与异常消息手写中文，不依赖 Django 翻译；验证一律用 `.venv/Scripts/python.exe`，系统 PATH 的 `python` 无 Django。
- **回归风险**：`accounts/views.py:127-136` 的四个空状态标志被 `accounts/tests.py` 的个人中心用例断言，替换 `my_messages_empty` 时须保留其余三个标志与既有渲染结构，避免 62 个用例回归失败。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 0 issues
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: 生成 `0002` 后为 `No changes detected`
- `.venv/Scripts/python.exe manage.py migrate` — expected: `0002` 正常应用，本地 `db.sqlite3` schema 更新（依冻结决策 ④ 允许执行，文件已 gitignore）
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 既有 102 用例 + 本故事新增用例全绿，无失败 / 跳过
- `git diff --name-status`、`git diff -- listings/models.py` 与 `git diff -- listings/admin.py` — expected: 交付文件与 AC-5 范围一致，`visible()` 与 `0001_initial.py` 未变，`admin.py` diff 为空

### Review Findings

> 独立代码审查（2026-11-09，`bmad-code-review`，`review_mode=full`，基线 `da46035..HEAD`，diff 12 文件 / +900 −16 / 1064 行）。激活层：Edge Case Hunter、Acceptance Auditor；Blind Hunter 与 Verification Gap 由团队配置置空跳过，`failed_layers` 为空。共 7 条原始发现，逐条核验后 **0 `decision-needed` / 0 `patch` / 0 `defer` / 7 rejected → Clean review**。主代理独立复跑：`.venv/Scripts/python.exe manage.py test -v 1` → 123 tests OK，`check` → 0 issues。

**Rejected**
- `low` → rejected — 【EC-1 并发状态覆盖】`resubmit_view` 无 `select_for_update()`，`_transition()` 只读内存 `self.status`，并发审核确可覆盖写入；但冻结决策 ① 下 `approve()` / `reject()` 无生产调用者、无审核界面，日常路径不可达，修复需 DB 端锁或条件更新（新增复杂度），且 spec-2-2 BH-7 / 本规格 EC-2、EC-5 已裁决留待 5.1 引入真实调用者时补。
- `low` → rejected — 【EC-2 `reject(None)` 内存状态脏】`reason` 为 `TextField(blank=True)`（DB 层 NOT NULL），显式传 `None` 会 `IntegrityError` 回滚 DB 但内存 `status='rejected'` 残留；默认值为 `''` 且无生产调用者，需显式传 `None` 才触发，修复需 `or ''` 或异常路径 `refresh_from_db()` 新分支，与 2.2 EC-1 / 本规格 EC-6 同类裁决。
- `false` — 【EC-3 无通知的驳回商品重提】`RejectionNotice` 唯一创建点是 `reject()`（`listings/models.py:85-91`），无通知即无理由数据；`resubmit_view` 渲染「暂无驳回理由」、`profile_view` 渲染空状态是正确行为，不存在「有理由却未展示」的路径；提议的 `raise Http404` 反会切断冻结决策 ① 下唯一的界面重提入口。
- `false` — 【EC-4 存量 >5 张图未重校验】冻结 Q3=A「不传则保留原图」是既定语义，`MAX_IMAGES=5` 是 `validate_images()` 对上传动作的校验规则而非存量数据不变式（本规格 BH-7 已裁决）；>5 图只能由绕过模型层的 admin 手工操作产生，提议守卫与「保留原图」冲突。
- `low` → rejected — 【EC-5 刷新重发 POST 命中 404】成功态沿用 2.1 D-011 的 200 成功页，刷新重发因 `status='rejected'` 过滤不再匹配而 404；不产生重复写入或状态损坏，成功页已给出「查看我的消息 / 继续发布商品」出口，改 PRG 需改变冻结成功态体验（新增设计，非直接修正），本规格 EC-1 已裁决。
- `low` → rejected — 【AA-1 0 图守卫与冻结区文字不一致】守卫（`listings/views.py:72-73`）与 `test_zero_image_rejected_product_cannot_resubmit_without_images` 确让 0 图商品不传图时保持 `rejected`，冻结区「图片为可选」/ AC-2 未同步 0 图例外；但 0 图本身违反 `epic-2-context.md:24` 的「每商品 ≥1 张图片」不变式，该守卫由人类决策 D-040 明确批准；消除文字歧义的唯一修复是编辑本规格冻结区，按 triage 规则一律驳回（如需修订应由人类重新协商，不属代码 patch）。
- `false` — 【AA-2 视图内 `status` 字面量】`get_object_or_404(..., status='rejected')`（`listings/views.py:59`）是 ORM 查询过滤条件，`can_resubmit`（`listings/models.py:160-162`）是只读属性，二者均无状态赋值，状态写入仍唯一经由 `_transition()`；规格 Code Map L93 / Implementation Notes L111 明文要求该查询过滤，Design Notes 亦把 Never 解释为禁止 `product.status = 'pending'` 式赋值；措辞歧义的修复=编辑本规格，同样驳回。
