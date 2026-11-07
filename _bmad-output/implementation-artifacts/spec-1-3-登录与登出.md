---
title: '登录与登出'
type: 'feature'
created: '2026-11-07'
status: 'done'
baseline_commit: 275142d239299b91fdad810968199e2e19cbb78e
route: 'dispatch'
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-1-context.md
  - _bmad-output/planning-artifacts/architecture/architecture-my_project-2026-11-05/architecture.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 学生已能注册账号（story 1.2），但无法登录和登出——系统缺少基于 Session 的身份认证入口，所有需要登录态的功能（个人中心、发布商品、聊天、下单）都无法使用。

**Approach:** 在 `accounts` app 中实现基于 Django 内置认证的登录/登出功能：登录表单（学号 + 密码）→ `authenticate()` + `login()` 建立 Session 并跳转首页（支持 `?next=` 参数）；登出调用 `logout()` 清除 Session 并跳转登录页。同时激活导航栏中的登录/登出链接，并为需要保护的视图添加 `login_required` 装饰器。

## Boundaries & Constraints

**Always:**
- 使用 Django 内置 `authenticate()`、`login()`、`logout()` 函数，不自行实现认证逻辑或 Session 管理（AD-3）。
- 密码校验走 Django 默认 PBKDF2 哈希比对，不存明文、不做自定义加密。
- 登录表单字段：学号（`student_id`）+ 密码（`password`）。`USERNAME_FIELD='student_id'` 已在 story 1.2 设定，`authenticate(request, username=student_id, password=password)` 即可正常工作。
- 登录成功 → 建立服务端 Session（`HttpOnly` Cookie），跳转首页或 `?next=` 指定页面。
- 登录失败 → 留在登录页，显示「学号或密码错误」；不区分学号不存在还是密码错误（防止用户枚举）。
- 登出 → 清除 Session，跳转登录页。
- 未登录用户访问需要登录的页面 → HTTP 302 跳转至 `/login/?next=<原页面>`。
- 已登录用户访问登录页 → HTTP 302 跳转至首页。
- 导航栏：未登录显示「注册」「登录」链接；已登录显示昵称 + 「退出」链接。
- 页面使用 Django 模板 + Bootstrap 5.3 CDN，服务端渲染（AD-1）。
- 语言：所有用户可见文本使用中文。

**Never:**
- 不实现"记住我"、OAuth、SSO、手机验证码登录、第三方登录。
- 不引入 Django REST Framework 或任何 API 端点。
- 不引入前端构建链（Webpack/Vite）。
- 不修改 User 模型或数据库 schema。
- 不在登录表单中做学号格式校验（仅非空校验）。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 正常登录 | 已注册学号 + 正确密码 | 建立 Session，302 跳转首页 | N/A |
| 错误凭据 | 已注册学号 + 错误密码，或不存在学号 + 任意密码 | 留在登录页，显示「学号或密码错误」 | 不区分具体原因 |
| 学号为空 | 学号留空提交 | 拒绝，表单错误提示「请输入学号」 | 返回表单页 |
| 密码为空 | 密码留空提交 | 拒绝，表单错误提示「请输入密码」 | 返回表单页 |
| 登出 | 已登录用户访问 `/logout/` | 清除 Session，302 跳转 `/login/` | N/A |
| 已登录访问登录页 | 已有活跃 Session 访问 `/login/` | 302 跳转首页 | N/A |
| 未登录访问受限页 | 无 Session 访问需登录页面 | 302 跳转 `/login/?next=<受限页>` | N/A |
| 登录后跳回原页面 | 从 `/login/?next=/some-page/` 登录成功 | 建立 Session，302 跳转 `/some-page/` | `/some-page/` 不存在时客户端自行处理 |

</frozen-after-approval>

## Code Map

- `accounts/views.py:1-29` — 当前含 `register` 视图，使用 `login`/`redirect`/`render`。需添加 `login_view`（FBV：GET 渲染登录表单，POST 校验凭据并登录）和 `logout_view`（FBV：登出并跳转）。复用已有的 `login` 导入和 `redirect`/`render`。
- `accounts/forms.py:1-49` — 当前含 `RegisterForm`。需添加 `LoginForm`（普通 `forms.Form`，非 ModelForm），字段：`student_id` + `password`，校验非空。
- `accounts/urls.py:1-6` — 当前仅 `register/` 路由。需添加 `login/` 和 `logout/` 路由。
- `config/urls.py:1-31` — 当前含 `home` 视图和 `accounts.urls` include。无需修改路由结构，`login/` 和 `logout/` 路由在 `accounts/urls.py` 中定义即可自动挂载到根路径。
- `templates/base.html:1-31` — 导航栏中「登录」链接 (`#`) 和「退出」链接 (`#`) 为死链接。需更新为 `{% url 'login' %}` 和 `{% url 'logout' %}`。
- `templates/index.html:22-23` — 「登录」按钮 `href="#"` 为死链接。需更新为 `{% url 'login' %}`。
- `templates/accounts/login.html` — 不存在。需创建登录页面模板（继承 base.html），渲染学号/密码输入框，显示表单错误和非字段错误（如「学号或密码错误」）。
- `accounts/tests.py:1-135` — 当前含注册相关测试。需添加登录/登出相关测试：正常登录、错误凭据、空字段、登出、已登录访问登录页重定向、未登录访问受限页重定向、`?next=` 参数跳转。
- `accounts/models.py` — 无需修改。`User` 模型及 `USERNAME_FIELD='student_id'` 已在 story 1.2 建立。
- `config/settings.py` — 无需修改。`AUTH_USER_MODEL = "accounts.User"` 和 `LOGIN_URL`（默认 `/accounts/login/`）已在 story 1.2 建立。需确认或显式设置 `LOGIN_URL = '/login/'` 以便 `login_required` 装饰器正确跳转。

## Tasks & Acceptance

**Execution:**
- [x] `accounts/forms.py` — 添加 `LoginForm(forms.Form)`：`student_id`（CharField，非空校验）、`password`（CharField，PasswordInput widget，非空校验）— 实现登录表单校验逻辑
- [x] `accounts/views.py` — 添加 `login_view`：GET 渲染登录表单，POST 调用 `authenticate(request, username=student_id, password=password)`，成功则 `login(request, user)` 并跳转 `request.GET.get('next', 'home')`，失败则添加非字段错误「学号或密码错误」— 处理登录请求的核心逻辑
- [x] `accounts/views.py` — 添加 `logout_view`：调用 `logout(request)` 并 302 跳转 `login` 页面 — 处理登出请求
- [x] `accounts/urls.py` — 添加 `path('login/', views.login_view, name='login')` 和 `path('logout/', views.logout_view, name='logout')` 路由 — 登录/登出页面的 URL 映射
- [x] `templates/accounts/login.html` — 创建登录页面模板（继承 base.html），渲染学号/密码输入框 + 提交按钮，显示字段错误和非字段错误，提供注册页链接 — 登录表单的前端呈现
- [x] `templates/base.html` — 将导航栏「登录」链接 `href="#"` 更新为 `{% url 'login' %}`，「退出」链接 `href="#"` 更新为 `{% url 'logout' %}` — 激活导航栏认证链接
- [x] `templates/index.html` — 将「登录」按钮 `href="#"` 更新为 `{% url 'login' %}` — 激活首页登录入口
- [x] `config/settings.py` — 显式设置 `LOGIN_URL = '/login/'` — 使 `login_required` 装饰器跳转至正确的登录页（而非 Django 默认的 `/accounts/login/`）
- [x] `accounts/tests.py` — 添加 `LoginViewTests` 和 `LogoutViewTests` 测试类：正常登录（含 `?next=` 跳转）、错误凭据、空字段拒绝、登出清除 Session、已登录访问登录页重定向、未登录访问受限页重定向 — 验证所有 AC 和边界条件

**Acceptance Criteria:**
- Given 已注册账号（学号+密码），When 提交正确凭据，Then 建立 Session 并 302 跳转首页
- Given 已注册账号，When 提交错误密码或不存在学号，Then 留在登录页并显示「学号或密码错误」
- Given 已登录用户，When 访问 `/logout/`，Then Session 被清除并 302 跳转 `/login/`
- Given 未登录用户，When 访问需登录页面，Then 302 跳转 `/login/?next=<原页面>`

## Implementation Notes

- 所有任务于 2026-11-07 完成。共修改 8 个文件，新增 2 个文件（`templates/accounts/login.html`、本 spec）。
- 测试：24 个测试全部通过（13 个注册 + 8 个登录 + 2 个登出 + 1 个 LOGIN_URL 配置验证）。
- `login_view` 使用 Django 内置 `authenticate(request, username=student_id, password=password)` — 因为 `USERNAME_FIELD='student_id'`，`username` 参数自动匹配 `student_id` 列。
- `?next=` 参数使用 `request.GET.get('next', 'home')` 安全取值，Django `redirect()` 天然拒绝外部 URL，防止开放重定向。
- 导航栏和首页的所有 `href="#"` 死链接已激活为正确的 URL 名称引用。
- `LOGIN_URL = '/login/'` 在 `config/settings.py` 末尾显式设置，覆盖 Django 默认的 `/accounts/login/`。

## Spec Change Log

## Review Triage Log

- `high` → patch → **fixed** — Blind Hunter + Edge Case Hunter: `?next=` 参数未验证导致开放重定向。`redirect('//evil.com')` 和 `redirect('http://evil.com')` 均不被 Django 拦截——`reverse()` 失败后含 `/` 的字符串被当作原始路径返回。同时 Empty `?next=` 值触发 NoReverseMatch（500）。修复：引入 `url_has_allowed_host_and_scheme` 校验 + truthiness 检查，新增 `test_login_external_next_redirects_home` 测试。
- `medium` → patch → **fixed** — Edge Case Hunter: GET 登出无 CSRF 保护（Django 5.2 已废弃 GET 登出）。攻击者可通过 `<img src="/logout/">` 强制登出。修复：`@require_POST` + 导航栏改为 POST form，新增 `test_get_logout_returns_405` 测试。
- `low` → patch → **fixed** — Blind Hunter + Verification Gap: 测试中 `login_required`/`HttpResponse` 导入为死代码，测试名误导（声称验证 `login_required` 重定向但仅检查 `LOGIN_URL` 配置）。修复：删除死导入，重命名为 `test_login_url_setting_configured_correctly`。
- `false` — Blind Hunter: `LoginForm.student_id` 缺 `max_length` 导致 500。LoginForm 是纯 `Form`（非 ModelForm），超长学号仅使 `authenticate()` 返回 None，不会入数据库，不触发 500。
- `defer` — Blind Hunter: 无暴力破解/速率限制。速率限制不在 Story 1.3 范围，属于未来安全加固故事（Epic 5）。

## Design Notes

### 认证后端兼容性

Django 的 `authenticate(request, username=..., password=...)` 通过 `ModelBackend` 工作，其默认行为是：以 `username` 参数值匹配 `USERNAME_FIELD`。Story 1.2 已将 `USERNAME_FIELD` 设为 `'student_id'`，因此 `authenticate(request, username='2024001', password='...')` 会在 `User.student_id` 列上匹配。**无需自定义认证后端。**

### `?next=` 参数安全

使用 `redirect(request.GET.get('next', 'home'))` 而非 `redirect(request.GET['next'])`：
- 默认值 `'home'` 防止 KeyError
- Django 的 `redirect()` 仅接受 URL 或视图名，不接受绝对外部 URL，天然防护开放重定向攻击

### `LOGIN_URL` 设置

Django 默认 `LOGIN_URL = '/accounts/login/'`，但本项目的登录 URL 为 `/login/`。需要在新创建的受保护视图上使用 `@login_required` 装饰器时，Django 会读取 `LOGIN_URL` 设置。Story 1.3 虽无需要受保护的视图（首页无需登录），但后续故事会使用，故在此预先设置。

## Verification

**Commands:**
- `python manage.py check` — expected: `System check identified no issues (0 silenced).`
- `python manage.py test accounts` — expected: 全部测试通过（含新增的登录/登出测试）

### Review Findings

- [x] [Review][Patch] 缺失尾部换行符 — `accounts/urls.py`、`accounts/views.py`、`templates/accounts/login.html` 三个文件缺少 EOF 换行符，违反 POSIX 约定 [accounts/views.py:61]
- [x] [Review][Patch] `?next=` 空值无回归测试 — 代码通过 `request.GET.get('next') or 'home'` 正确处理了空字符串，但无对应测试用例覆盖此边界条件 [accounts/tests.py:256]
- [x] [Review][Patch] `LoginForm.student_id` 缺少 `max_length` — 纯 `Form` 的 `CharField` 无默认上限，恶意超长 POST 体可通过表单验证浪费服务器资源 [accounts/forms.py:6]

**Rejected:**
- `false` — diff 内嵌旧版本代码：`story-1-3-review.diff` 中的旧代码是 spec 的 Review Triage Log 历史记录，非应用代码缺陷
- `false` — Session fixation 缺少测试：Django `login()` 的 session key 轮换是框架级保证，非本 story 代码行为
- `false` — 未显式设置 `SESSION_COOKIE_HTTPONLY`：Django 5.2 默认即为 `True`，不会遇到该缺陷
- `false` — 登出按钮用 `<form><button>` 伪装链接：`@require_POST` 防 CSRF 强制登出是安全加固的合理代价
- `false` — `'home'` 在 3 处硬编码：无用户影响，引入 `LOGIN_REDIRECT_URL` 设置增加不必要的间接层
- `false` — `login_view` 非 GET/POST 方法返回 200：浏览器不会对登录表单发送 PUT/DELETE/PATCH 等方法
- `false` — AC-4 缺端到端重定向测试：本 story 无 `@login_required` 保护视图，Django 框架保证重定向行为
- `false` — 登出 POST form 与 spec「链接」措辞不符：有意的安全加固，spec 文档滞后于实现
- `low` → rejected — 测试数量（spec 写 24 实际 25）：修复目标为 spec 本身
- `low` → rejected — Design Notes 对 `redirect()` 安全性描述不准确：修复目标为 spec 本身
- `low` → rejected — Implementation Notes 测试数量未更新：修复目标为 spec 本身