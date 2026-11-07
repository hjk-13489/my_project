---
title: '个人中心'
type: 'feature'
created: '2026-11-07'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 0652f63dad05a78a7cd356ecfc655c6cb753f73e
context:
  - _bmad-output/implementation-artifacts/epic-1-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 学生已能注册、登录、提交学号认证（1.2–1.4），却没有统一的个人中心入口，FR-4 / AD-4 要求的「仅返回本人数据」没有承载页面。

**Approach:** 在 `accounts` app 新增受登录保护的个人中心页，以 `request.user` 为唯一数据边界，展示本人账号信息、认证状态与申请历史，以及「我的发布 / 订单 / 消息 / 评价」四个板块，并在导航栏加入口。

**Decision（人类决策，2026-11-07）:** 采用方案 A「壳 + 空状态」——本故事只交付个人中心页、登录鉴权、本人账号信息与认证申请历史等真实数据；四个板块以中文空状态呈现并预留后续接入点，不新建业务模型、不产生迁移、不伪造演示数据。四类真实数据待 Epic 2/3/4 完成后接入。规格长度 2794 tokens 超出 1600 建议值，人类选择保留完整规格并接受 context-rot 风险。

## Boundaries & Constraints

**Always:**
- 未登录访问 `/profile/` → 302 `/login/?next=/profile/`；页面只读，已登录用户非 GET/HEAD → 405，不写入任何数据。
- 所有查询在服务端按 `request.user.pk` 过滤（AD-4），页面不出现他人数据；不做前端隐藏式伪权限。
- 路由 `path('profile/', views.profile_view, name='profile')`（`accounts.urls` 顶级、无 namespace）；模板 `templates/accounts/profile.html`，继承 `base.html` 的 `title` / `content`。
- 导航栏已登录分支追加「个人中心」链接，保留「✓ 已认证」「待认证」「去认证」及退出 POST 表单（既有测试硬断言）。
- 文案全中文；Django 模板 + Bootstrap 5.3 CDN 服务端渲染；无数据显示中文空状态，不抛异常、不造假数据。
- 保持 `accounts` 现有 4 条路由/name、`LOGIN_URL`、`User` 字段、admin 审核逻辑与 1.1–1.4 行为不变。

**Never:**
- 不引入 DRF / API / 前端构建链 / 新依赖；不实现资料编辑、改密、头像上传。
- 不新增 `listings` / `chat` / `orders` / `dashboard` 的业务实体（架构：实体归所属 app 唯一定义），不改其脚手架。
- 不改动 `accounts/migrations/0001_initial.py`、`0002_verificationrequest.py` 与 `db.sqlite3` 既有结构。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 未登录 | GET `/profile/` | 302 `/login/?next=/profile/` | N/A |
| 已登录 | GET `/profile/` | 200，只含本人信息 | N/A |
| 他人数据存在 | 库中有其他用户的账号/认证申请 | 页面不出现其昵称、学号、状态、时间 | queryset 按 `user=request.user` 过滤 |
| 无认证申请 | 从未提交 | 「尚未提交认证申请」+ 去认证入口 | 空状态分支 |
| 有认证申请 | pending/approved/rejected | 显示 `get_status_display()` 与提交时间，按 `-created_at` 排序 | N/A |
| 四板块无数据 | 模型不存在或本人无记录 | 各板块中文空状态提示 | 空状态分支 |
| 已登录 POST | POST `/profile/` | 405，无写入 | `require_GET`；`@login_required` 置外层故未登录 POST 仍先 302 |

</frozen-after-approval>

## Code Map

- `accounts/views.py` — 4 个现有 FBV，末尾追加 `profile_view`；`verify_view` 是 `@login_required` + 上下文分支的参考范式。装饰序 `@login_required` 外层、`@require_safe`（`django.views.decorators.http`）内层：实测 Django 5.2.19 的 `require_GET` 只放行 GET，HEAD 会返回 405，与「仅非 GET/HEAD → 405」不符，故用 `require_safe`（放行 GET/HEAD）。勿改既有函数。
- `accounts/urls.py` — 现有 `register/login/logout/verify` 四条 path，无 `app_name`；追加 `profile/`。
- `accounts/models.py` — 唯一真实数据源：`User`（`username` 昵称 / `student_id` / `is_verified` / `role` / `date_joined`）与 `VerificationRequest`（`user` FK，related_name `verification_requests`；`status`；`created_at`；`Meta.ordering=('-created_at',)`；`get_status_display()`）。只读，勿新增模型/迁移。
- `templates/base.html` — 仅 `title`/`content` 两 block，Bootstrap CDN 硬编码；导航栏已登录分支（15–22 行）含认证徽标与退出 POST 表单；追加链接，勿改被 `accounts/tests.py:454/461` 断言的文案。
- `templates/accounts/verify.html` — 模板写法参考（`{% extends 'base.html' %}`、手动字段渲染、`alert`、`{% url %}`）。`templates/index.html` 不改。
- `accounts/tests.py` — 现有 47 个测试；`setUp` 用 `reverse()` + `User.objects.create_user(student_id=..., username=..., password=...)` + `client.login(username=<student_id>)`，有 `_login`/`_make_user` 辅助方法。新增 `ProfileViewTests`，勿改既有用例。
- `config/settings.py` / `config/urls.py` — `AUTH_USER_MODEL='accounts.User'`、`LOGIN_URL='/login/'`、顶级 `include('accounts.urls')`；无需改动。
- `listings/` `chat/` `orders/` `dashboard/` — 空脚手架，勿触碰。

## Tasks & Acceptance

**Execution:**
- [x] `accounts/urls.py` — 追加 `profile/` → `profile_view`, `name='profile'` — 暴露 URL
- [x] `accounts/views.py` — 追加 `profile_view`：取 `request.user` 与 `request.user.verification_requests.all()`，传 `profile_user` / `verification_requests` / 四板块空状态标识 — 服务端本人数据边界
- [x] `templates/accounts/profile.html` — 新建：账号信息卡（昵称/学号/认证状态/注册时间）、认证申请历史、四个板块卡与中文空状态 — 用户可见呈现
- [x] `templates/base.html` — 已登录导航栏追加 `{% url 'profile' %}` 的「个人中心」链接 — 全局入口
- [x] `accounts/tests.py` — 新增 `ProfileViewTests`：未登录重定向含 next、已登录 200 与模板、只显示本人学号昵称、他人申请不出现、无/有申请两种状态、四板块空状态、POST 405、导航栏入口仅登录可见 — 覆盖矩阵与 AC

**Acceptance Criteria:**
- Given 已登录用户，When 访问 `/profile/`，Then 只呈现本人账号信息与认证申请，无任何其他用户数据。
- Given 未登录访客，When 访问 `/profile/`，Then 302 到登录页且 `next=/profile/`。
- Given 库中存在另一用户的认证申请，When 当前用户访问个人中心，Then 响应不含其姓名、学号或状态。
- Given 已登录用户，When 浏览任意页面，Then 导航栏「个人中心」链接指向 `/profile/`。
- Given 1.1–1.4 的既有用例，When 运行完整测试套件，Then 47 个既有用例仍全部通过。

### Review Findings

> 2026-11-07 ad hoc code review（`/bmad-code-review`），范围 `0652f63..HEAD (2bc8c45)`，模式 `full`；生效审查层：Edge Case Hunter + Acceptance Auditor（团队精简配置 `_bmad/custom/bmad-code-review.toml` 禁用 Blind Hunter / Verification Gap）。7 条原始发现 → 1 decision-needed（已裁决转 patch）、1 patch、0 defer、6 rejected。

**Decision Needed（已裁决）**

- [x] [Review][Decision] 冻结区 I/O 矩阵「无认证申请」行要求无条件给出「去认证入口」，实现额外附加 `not is_verified` 条件并由测试锁定 — [templates/accounts/profile.html:49-54; accounts/tests.py:715-722] 冻结矩阵写「从未提交 → 尚未提交认证申请 + 去认证入口」；`profile.html` 在无申请分支内再嵌 `{% if not profile_user.is_verified %}` 才渲染按钮，`test_go_verify_button_hidden_verified_without_history` 显式断言「已认证且无申请」时隐藏。该状态可达（`accounts/admin.py:14/21` 允许管理员直接置 `is_verified=True` 而不产生申请记录，`test_verified_user_shows_verified_status` 亦构造此状态），因此用户会看到「✓ 已认证」+「尚未提交认证申请」却无去认证入口。但 `views.py:69-70` 对已认证用户访问 `/verify/` 直接 302 首页、`base.html:17-22` 也已对已认证用户隐藏去认证链接，去掉守卫反而制造死链。**人类裁决（2026-11-07，选项 2）：以冻结规格为准改代码**，转为下方 Patch；冻结区不修改。

**Patch**

- [x] [Review][Patch] 去掉 `profile.html:51/53` 的 `{% if not profile_user.is_verified %}` 守卫，使「无认证申请」分支无条件渲染「去认证」按钮；同步调整 `accounts/tests.py` 的 `test_go_verify_button_hidden_verified_without_history` → `test_go_verify_button_shown_verified_without_history`，断言已认证且无申请时按钮存在且全页 `去认证` 仅出现 1 次 [templates/accounts/profile.html:49-52; accounts/tests.py:715-727] — 同步更新 Implementation Notes 的「去认证入口」记述。**已应用（2026-11-07）**：`manage.py check` 无问题、`makemigrations --check --dry-run` → `No changes detected`、`manage.py test` → 62 tests OK（47 既有 + 15 `ProfileViewTests`）。

**Defer**

_无。_

**Rejected**

- `false` → rejected — EC-1「我的发布 `{% else %}` 分支空白」：`accounts/views.py:132` 的 `my_listings_empty` 是字面 `True`，全仓仅此一处赋值且无任何请求路径可置为 False（Grep 全库确认），`profile.html:65-67` 的 else 分支只含 Django 注释，在交付程序中不可达；人类决策 A 明确要求「壳 + 空状态」，补齐 else 需新增上下文契约、扩大公开表面，不构成当前缺陷。
- `false` → rejected — EC-2「我的订单 `{% else %}` 分支空白」：同 EC-1，`views.py:133` 字面 `True`，`profile.html:78-80` 分支不可达。
- `false` → rejected — EC-3「我的消息 `{% else %}` 分支空白」：同 EC-1，`views.py:134` 字面 `True`，`profile.html:91-93` 分支不可达。
- `false` → rejected — EC-4「我的评价 `{% else %}` 分支空白」：同 EC-1，`views.py:135` 字面 `True`，`profile.html:104-106` 分支不可达。
- `low` → rejected — 冻结区 I/O 矩阵写 `require_GET` 而实现用 `@require_safe`：代码本身正确（Django 5.2.19 的 `require_GET` 对 HEAD 返回 405，违反 Always #1「仅非 GET/HEAD → 405」；`tests.py:661/674/675` 已断言 `Allow: GET, HEAD` 与 HEAD 200），矩阵单元格属冻结区实现提示措辞，差异已由 Implementation Notes 记录。修复方式是编辑被审查的 spec 本身，按 triage 规则 reject。
- `low` → rejected — spec frontmatter `status: done` 与 `sprint-status.yaml` 的 `1-5-个人中心: review` 状态不一致：两者由工作流不同阶段写入，代码审查收尾阶段会同步 sprint 状态；修复方式是编辑被审查的 spec / 跟踪工件，按 triage 规则 reject。

## Implementation Notes

- 实现由无上下文子代理按本规格完成；改动共 7 个文件：`accounts/urls.py`、`accounts/views.py`、`accounts/tests.py`、`templates/accounts/profile.html`（新建）、`templates/base.html`、本规格、`sprint-status.yaml`。
- `profile_view` 用 `@login_required`（外层）+ `@require_safe`（内层）；`profile_user = request.user`，`verification_requests = profile_user.verification_requests.all()`（FK 过滤即服务端本人数据边界），四个板块空状态标识硬编码为 `True`，模板内用 `{# #}` 注释标出 Epic 2/3/4 的接入点。
- 审查补丁后新增 `ProfileViewTests` 共 15 个用例（首轮 11 个 + 补强 4 个）；未改动 47 个既有用例、未改动模型/迁移/配置/其余四个 app。
- 审查补丁把 `@require_GET` 换为 `@require_safe`：Django 5.2.19 的 `require_GET` = `require_http_methods(['GET'])`，HEAD 返回 405 且 `Allow: GET`；`require_safe` 放行 GET/HEAD 并对 PUT/PATCH/DELETE/POST 返回 405 且 `Allow: GET, HEAD`，符合冻结区「仅非 GET/HEAD → 405」。冻结区 I/O 矩阵中的 `require_GET` 是实现提示措辞，按工作流不可修改，此处记录实际实现。
- 验证（项目 `.venv` Python 3.13.1 / Django 5.2.19）：`manage.py check` 无问题；`makemigrations --check --dry-run` → `No changes detected`；`manage.py test` → 62 tests OK（47 既有 + 15 新增）；`accounts.tests.ProfileViewTests -v 2` → 15 个用例逐个 ok，矩阵 7 行均有覆盖且实际执行通过。
- 环境注意：系统 PATH 上的 `python` 未安装 Django，须用 `.venv/Scripts/python.exe`。
- 已知取舍：时间按 `TIME_ZONE='UTC'` 显示，未做本地化；「去认证」入口在**无认证申请**时出现（含有认证历史以外的全部情形；有认证历史时只展示历史，不再显示入口）。2026-11-07 代码审查人类裁决（选项 2）以冻结区矩阵为准，去掉了原先的 `not is_verified` 守卫：管理员在 `UserAdmin` 直接置 `is_verified=True` 且无申请记录的用户也会看到该按钮；已知代价是 `verify_view` 会把已认证用户 302 回首页，按钮此时不产生提交行为。四板块为空是人类决策 A 的预期结果，非遗漏。

## Spec Change Log

## Review Triage Log

> 2026-11-07 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `0652f63..工作树`，diff 24.67 kB。共 20 条发现，逐条裁决如下；`VG-*` 为验证缺口层预验证发现，按流程免复核。

- BH-1 `false` — 「规格 in-review 与 sprint-status in-progress 矛盾」：两者由工作流不同阶段写入（step-03 同步 in-progress、step-04 置规格 in-review），收尾阶段统一同步；且修复方式是编辑本 build 的规格/状态工件，按 triage 规则 reject。
- BH-2 `low` → reject — Verification 段的 `python manage.py ...` 在系统 PATH 上确实无 Django；但实际验证已用 `.venv/Scripts/python.exe` 完成，修复仅为编辑本 build 规格，规则明确 reject。
- BH-3 `low` → reject — Implementation Notes 的「6 个文件」与 diff 的 7 个文件不符属实，属文字记述，修复=编辑规格，reject。
- BH-4 `low` → reject — 矩阵只列 POST 属实，但补 PUT/PATCH/DELETE/HEAD 行需改只读的 `<frozen-after-approval>`，reject；`Always` 的方法约束由 BH-5 的测试补齐。
- BH-5 `low` → patch — 仅 `POST` 405 有断言，PUT/PATCH/DELETE/HEAD 与 `Allow` 头未验证；补断言是最小且不增加公开表面的修复。**补丁执行补记**：写断言时实测 `@require_GET` 在本机 Django 5.2.19 只放行 GET（HEAD 405、`Allow: GET`），与冻结区「仅非 GET/HEAD → 405」不符，故最小实现修正为 `@require_safe`（GET/HEAD）；此为无新增公开表面的装饰器替换，已在 Implementation Notes 与 Code Map 同步记录，未修改冻结区。
- BH-6 `low` → patch — `test_other_user_data_not_shown` 只在「本人无申请」下验证隔离，混合数据场景与 context 只含本人 pk 未覆盖；queryset 本身正确，缺的是回归证据。
- BH-7 `low` → patch — 「无申请且未认证才显示去认证」分支无用例，与 VG-1 同根因合并处置。
- BH-8 `low` → patch — AC「浏览任意页面」只测首页，需补其他会渲染 `base.html` 的页面。
- BH-9 `false` — 「四板块预留接入点不是可用数据槽」：四个 `my_*_empty` 在 `accounts/views.py` 中是字面常量 `True`，无任何请求路径可置为 False，`{% else %}` 分支不可达；空白卡片在交付程序中不会发生，修复需新增上下文契约（改规格/加公开表面），不构成本 story 缺陷。
- BH-10 `false` — 规格任务明确枚举「昵称/学号/认证状态/注册时间」四项；`role` 是内部授权值（student/admin），向用户展示原始值无需求依据亦无用户可见损害。卡片字段断言缺口由 VG-2 单独捕获。
- BH-11 `false` — `TIME_ZONE='UTC'` + `USE_TZ=True` 是架构要求，`|localtime` 在 UTC 下与 `|date` 输出一致，不存在本地化缺陷；时间格式断言缺口由 VG-3 单独捕获。
- BH-12 `low` → reject — 空章节属实，但 Review Triage Log 正由本步骤填充、Spec Change Log 仅首轮 loopback 才写；修复=编辑规格，reject。
- BH-13 `false` — 测试内局部 import 合法无副作用；文件末尾无换行继承自基线（`tests.py` 原本即无）；Code Map 行号是描述性标注非可执行引用，三者均无坏结果。
- EC-1 `false` — 「我的发布 else 分支空白」：`my_listings_empty` 恒为字面 `True`，分支不可达，与 BH-9 同一事实。
- EC-2 `false` — 「我的订单 else 分支空白」：`my_orders_empty` 恒为字面 `True`，分支不可达。
- EC-3 `false` — 「我的消息 else 分支空白」：`my_messages_empty` 恒为字面 `True`，分支不可达。
- EC-4 `false` — 「我的评价 else 分支空白」：`my_reviews_empty` 恒为字面 `True`，分支不可达。
- VG-1 `medium` → patch — 预验证：`去认证` 与 `href="/verify/"` 由 `templates/base.html:21` 导航栏同名链接满足，删除 `profile.html:52` 按钮后 58 个用例仍全绿；矩阵「去认证入口」一行失守。`btn btn-outline-primary btn-sm` 经检索为该按钮独有标记，可作断言锚点。
- VG-2 `medium` → patch — 预验证：`✓ 已认证` 同时出现在 `base.html:18` 与 `profile.html:25`，删除卡片徽标块后 `test_verified_user_shows_verified_status` 仍通过；「注册时间」行同样无断言，任务清单两项缺保护。
- VG-3 `medium` → patch — 预验证：`profile.html:45` 的 `created_at|date` 从未被断言，用例 docstring 声称覆盖但只查状态标签与 context 顺序，删除时间 `<span>` 测试仍全绿。

**分组与处置：** 存活项按根因分两组，均 route `patch`，无 `intent_gap` / `bad_spec` / `defer`，不触发 loopback，`review_loop_iteration` 保持 0。
- 组 A（VG-1、VG-2、VG-3、BH-7，最高 `medium`）：新增模板输出用通用文案断言或根本未断言，被导航栏同名内容满足 —— 补模板独有锚点与次数断言、时间字符串断言、去认证分支用例。
- 组 B（BH-5、BH-6、BH-8，最高 `low`）：场景与方法覆盖不全 —— 补混合数据隔离、多页面导航、HTTP 方法与 `Allow` 头断言。

## Design Notes

- 架构结构种子将 FR-1~FR-4 归 `accounts`，且实体由所属 app 唯一定义；个人中心是聚合只读视图，不在 `accounts` 复制 Product/Order/Message/Review。
- `VerificationRequest.user` 是现成归属字段，可用 `request.user.verification_requests` 构造可验证的服务端过滤；后续 Epic 接入时沿用 `filter(owner=request.user)` / `filter(buyer=request.user)` 替换空状态。
- `base.html` 未接 `django.contrib.messages`，前台提示一律用视图上下文 + 模板 `alert`；本故事不新增全局 messages 区块。

## Verification

**Commands:**
- `python manage.py check` — expected: 无问题
- `python manage.py makemigrations --check --dry-run` — expected: `No changes detected`（不应产生迁移）
- `python manage.py test` — expected: 62 个用例（47 既有 + 15 新增 `ProfileViewTests`）全部通过

**Manual checks (if no CLI):**
- `runserver` 后用两个不同账号登录 `/profile/`，各自只看到自己的昵称、学号与认证申请。
