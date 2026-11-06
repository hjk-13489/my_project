---
title: '用户注册'
type: 'feature'
created: '2026-11-06'
status: 'done'
baseline_commit: 261485671001e8230a59b1c4000b5f8a04b1ef5d
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-1-context.md
  - _bmad-output/planning-artifacts/epics.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 学生无法获得账号身份——系统中尚无注册功能，所有后续操作（登录、认证、发布、交易）都需要一个已存在的 User 记录作为身份锚点。

**Approach:** 在 `accounts` app 中定义自定义 User 模型（`student_id` 唯一、`is_verified` 默认 False、`role` 默认 `'student'`），创建注册表单（学号 + 密码 ≥6 位 + 昵称），实现注册视图（GET 渲染表单 / POST 校验并创建用户），配置 `AUTH_USER_MODEL` 并在首次 migrate 前完成，删除旧的 `db.sqlite3` 重迁移。

## Boundaries & Constraints

**Always:**
- 自定义 User 模型继承 `AbstractUser`，扩展字段：`student_id`（CharField，unique）、`is_verified`（BooleanField，default=False）、`role`（CharField，choices=[('student', '学生'), ('admin', '管理员')]，default='student'）。
- `AUTH_USER_MODEL = 'accounts.User'` 必须在 `settings.py` 中设置，且在首次 migrate 之前生效。
- 密码哈希加盐由 Django 默认 PBKDF2 处理（AD-3），不自行实现加密。
- 注册表单字段：学号（`student_id`）、密码（`password`，≥6 位）、确认密码（`password_confirm`）、昵称（`nickname`，即 `User.username`）。后端校验所有字段。
- 学号唯一性在 model 层（`unique=True`）和表单层双重保证。
- 注册成功后 `is_verified=False`、`role='student'`，自动登录（`login(request, user)`）并跳转首页，首页显示「待认证」状态提示。
- 页面使用 Django 模板 + Bootstrap 5.3（CDN），服务端渲染（AD-1）。
- 语言：所有用户可见文本使用中文。

**Never:**
- 不在注册时做学号格式校验（如限定学校前缀/数字长度）——仅做非空校验。格式校验属 story 1.4（学号认证）。
- 不实现邮箱/手机验证、验证码、第三方登录。
- 不实现登录功能（属 story 1.3）。
- 不实现认证审核（属 story 1.4）。
- 不引入 Django REST Framework 或任何 API 端点。
- 不引入前端构建链（Webpack/Vite）。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 预期输出 / 行为 | 错误处理 |
|------|------------|---------------|---------|
| 正常注册 | 新学号 + 密码(≥6位) + 确认密码一致 + 昵称 | 创建 User，`is_verified=False`, `role='student'`，自动登录并跳转至首页，首页显示「待认证」状态提示 | N/A |
| 学号重复 | 已存在的学号 | 拒绝创建，表单错误提示「该学号已被注册」 | 返回表单页，保留已填写字段（密码除外） |
| 密码过短 | 密码 < 6 位 | 拒绝，表单错误提示「密码长度不能少于 6 位」 | 返回表单页 |
| 确认密码不一致 | password ≠ password_confirm | 拒绝，表单错误提示「两次输入的密码不一致」 | 返回表单页 |
| 学号为空 | 学号留空提交 | 拒绝，表单错误提示「请输入学号」 | 返回表单页 |
| 昵称为空 | 昵称留空提交 | 拒绝，表单错误提示「请输入昵称」 | 返回表单页 |
| 已登录用户访问注册页 | 已有活跃 Session | 重定向至首页，不展示注册表单 | HTTP 302 → 首页 |

</frozen-after-approval>

## Code Map

- `config/settings.py:134` -- 当前无 `AUTH_USER_MODEL`。需在 `DEFAULT_AUTO_FIELD` 之前添加 `AUTH_USER_MODEL = "accounts.User"`。
- `accounts/models.py` -- 空文件，需创建自定义 `User(AbstractUser)` 模型。关键字段：`student_id`、`is_verified`、`role`。`username` 重用为昵称字段（Django 自带，不作改动）。
- `accounts/forms.py` -- 空文件，需创建 `RegisterForm`，校验密码长度（≥6）、确认密码一致性、学号唯一。
- `accounts/views.py` -- 目前仅含 `render` 导入。需添加 `register` 视图（FBV：GET 渲染表单，POST 校验并创建用户）。
- `accounts/urls.py` -- 空文件，需添加 `path('register/', ...)` 路由。
- `config/urls.py:22` -- 当前仅 admin 路由。需添加 `path('', include('accounts.urls'))` 或带前缀的 include。
- `templates/base.html` -- 不存在，需创建含 Bootstrap 5.3 CDN 的基础模板。
- `templates/accounts/register.html` -- 不存在，需创建注册表单模板（继承 base.html）。
- `templates/index.html` -- 不存在（首页模板），需创建简单首页用于注册后跳转。
- `accounts/tests.py` -- 目前仅含 `TestCase` 导入。需添加注册视图测试。
- `accounts/admin.py` -- 需注册自定义 User 模型到 Django Admin。
- `accounts/apps.py:4-7` -- `AccountsConfig` 已定义，可能需添加 `verbose_name`。当前无需改动。
- `db.sqlite3`（如有）-- 需删除后重新 migrate（因为 AUTH_USER_MODEL 变更）。

## Tasks & Acceptance

**Execution:**
- [x] `accounts/models.py` -- 定义 `User(AbstractUser)` 模型，添加 `student_id`（CharField, unique）、`is_verified`（BooleanField, default=False）、`role`（CharField, choices, default='student'）字段；设置 `USERNAME_FIELD='student_id'`、`REQUIRED_FIELDS=['username']` -- 建立用户数据模型，所有后续故事依赖此模型
- [x] `accounts/admin.py` -- 注册自定义 User 模型 -- 使管理员可通过 Django Admin 管理用户
- [x] `config/settings.py` -- 添加 `AUTH_USER_MODEL = "accounts.User"` -- 告知 Django 使用自定义 User 模型（在首次 migrate 前必须设置）
- [x] `accounts/forms.py` -- 创建 `RegisterForm(ModelForm)`，包含 `password` 和 `password_confirm` 字段，`clean()` 校验密码长度 ≥6 和确认密码一致性 -- 实现注册表单校验逻辑
- [x] `accounts/views.py` -- 实现 `register` 视图：GET 渲染注册表单，POST 校验并创建用户（`user.set_password()`），`login(request, user)` 自动登录，重定向至首页 -- 处理注册请求的核心逻辑
- [x] `templates/base.html` -- 创建基础模板，引入 Bootstrap 5.3 CDN（CSS + JS），定义 `{% block content %}` 区块 -- 提供统一的前端框架
- [x] `templates/accounts/register.html` -- 创建注册页面模板（继承 base.html），渲染学号/密码/确认密码/昵称输入框，显示表单错误 -- 注册表单的前端呈现
- [x] `templates/index.html` -- 创建首页模板（继承 base.html），显示「待认证」状态提示（当 `user.is_authenticated and not user.is_verified` 时）-- 注册后跳转目标页，满足 AC「页面状态显示待认证」
- [x] `accounts/urls.py` -- 添加 `path('register/', views.register, name='register')` 路由 -- 注册页面的 URL 映射
- [x] `config/urls.py` -- 添加首页视图路由和 accounts URL 引入 -- 将 accounts 的路由接入项目
- [x] `accounts/tests.py` -- 添加注册视图测试：正常注册、学号重复拒绝、密码过短拒绝、确认密码不一致拒绝、学号/昵称为空拒绝 -- 验证所有 AC 和边界条件

**Acceptance Criteria:**
- Given 注册表单已呈现，When 输入学号、密码（≥6位）、昵称并提交，Then 创建 `User` 记录且 `is_verified=False`、`role='student'`，页面状态显示「待认证」
- And 重复学号提交被拒绝并提示
- And 密码长度 < 6 位被拒绝

## Implementation Notes

## Spec Change Log

## Review Triage Log

- `false` — Blind Hunter: 无 email 字段导致密码重置不可行。证据：spec 明确排除邮箱验证（Never:"不实现邮箱/手机验证"），AbstractUser 自带 `blank=True` 的 email 字段，密码重置属 story 1.3+ 范围。
- `false` — Blind Hunter: 无学号格式校验。证据：spec Never 块明确"不在注册时做学号格式校验…格式校验属 story 1.4"。
- `low` → patch → fixed — Blind Hunter: admin.py 的 list_display/search_fields 未包含 email 字段。证据：email 从 AbstractUser 继承（blank=True）。已添加 `'email'` 到 list_display 和 search_fields。
- `false` — Blind Hunter: test_empty_student_id_rejected 断言用 username 验证而非 student_id。证据：student_id 在测试中为空字符串，无法用于查询；用 username 验证"未创建任何用户"是正确的测试逻辑，非 false positive。
- `false` — Blind Hunter: config/urls.py 中 `path("", include(...))` 与 `path("", home)` 命名空间冲突。证据：Django 按序解析 URL，accounts.urls 无空路径匹配时 fall through 到 home 视图，无冲突。
- `false` — Blind Hunter: 注册视图无 ?next= 重定向参数。证据：spec 明确"自动登录并跳转首页"，?next= 参数属登录功能（story 1.3），注册场景无需此参数。
- `false` — Blind Hunter: 测试无 CSRF 校验。证据：Django TestClient 默认关闭 CSRF 中间件，模板已含 `{% csrf_token %}`，属标准 Django 测试行为。
- `low` → patch → fixed — Edge Case Hunter: `user.save()` 可能因并发重复学号触发 IntegrityError 导致 500。修复：在 `user.save()` 处捕获 `IntegrityError` 并转为表单错误。
- `false` — Edge Case Hunter: spec 说密码校验在 `clean()` 中，代码在 `clean_password()` 中。证：两者同属表单校验流程，功能正确。修复只需编辑 spec 文字，规则要求拒绝"fix is to edit this build's spec"的发现。
- `low` → patch → fixed — Verification Gap: Admin 配置无测试覆盖。已添加 `test_admin_user_changelist` 验证 admin changelist 渲染。
- `low` → patch → fixed — Verification Gap: 首页未登录分支无测试覆盖。已添加 `test_home_page_unauthenticated` 验证未登录首页渲染。
- `low` → patch → fixed — Blind Hunter + Edge Case Hunter: `IntegrityError` 捕获过宽（`accounts/views.py:18-19`）。修复：检查异常字符串区分 `student_id`/`username` 约束冲突，分别返回正确的中文错误提示。
- `false` — Blind Hunter: `clean_password` 缺少 None 守卫（`accounts/forms.py:37`）。Django 表单引擎仅在 `required` 校验通过后才调用 `clean_password`，此时 password 必定为非空字符串，`len(None)` 场景不可达。
- `false` — Blind Hunter: `UserManager.create_user()` 被绕过导致缺少 NFKC 规范化（`accounts/views.py:14-17`）。`CharField.strip=True` 已处理空白字符，学生号为 ASCII 数字，NFKC 规范化无实际影响；修复需要重构视图保存逻辑，增加复杂度不划算。
- `low` → patch → fixed — Blind Hunter: 两个 `path("", ...)` 路由项排序依赖（`config/urls.py:29-30`）。修复：`path("", home)` 前置，`path("", include("accounts.urls"))` 后置，确保 home 视图不会被未来 accounts 根路由静默覆盖。
- `medium` → patch → fixed — Blind Hunter + Edge Case Hunter + Acceptance Auditor: `username` 唯一约束冲突时显示英文默认错误（`accounts/forms.py:31-33`）。修复：添加 `'username': {'unique': '该昵称已被使用'}` 到 `error_messages`。
- `low` → patch → fixed — Blind Hunter: admin `list_display` 中 `role` 显示原始值（`accounts/admin.py:8`）。修复：`'role'` → `'get_role_display'`。
- `low` → defer — Blind Hunter: 导航栏中存在死链接（登录/退出 `href="#"`，`templates/base.html:16,19`）。登录/登出属 story 1.3，占位链接预期在该 story 中激活。
- `medium` → patch → fixed — Edge Case Hunter + Verification Gap: `IntegrityError` 处理块无测试覆盖（`accounts/views.py:18-20`）。修复：添加 `test_integrity_error_during_save_shows_student_id_error` 和 `test_integrity_error_during_save_shows_username_error` 测试。
- `low` → patch → fixed — Edge Case Hunter + Verification Gap: 首页已认证用户分支无测试覆盖（`templates/index.html:14-17`）。修复：添加 `test_home_page_verified_user` 测试。

## Design Notes

### 自定义 User 模型设计

```python
class User(AbstractUser):
    student_id = models.CharField(max_length=32, unique=True, verbose_name='学号')
    is_verified = models.BooleanField(default=False, verbose_name='是否已认证')
    role = models.CharField(
        max_length=16, choices=[('student', '学生'), ('admin', '管理员')],
        default='student', verbose_name='角色'
    )
    USERNAME_FIELD = 'student_id'
    REQUIRED_FIELDS = ['username']  # username 复用为昵称
```

### 路由策略

- 注册页 URL：`/register/`（accounts app 内）
- 首页 URL：`/`，直接写在 `config/urls.py`（简单 FBV，无需拆分到 app）
- accounts 路由不设前缀（`path('', include('accounts.urls'))`），保持 URL 简洁

### 密码校验策略

不在 `models.py` 中重复定义密码长度校验——利用 Django 表单的 `clean_password()` 方法，结合 `AUTH_PASSWORD_VALIDATORS` 中的 `MinimumLengthValidator`。但 AC 明确要求密码 ≥6 位，故在表单 `clean()` 中显式校验，与 AC 保持一致。

## Verification

**Commands:**
- `python manage.py check` -- expected: `System check identified no issues (0 silenced).`
- `python manage.py makemigrations accounts --dry-run --check` -- expected: 检测到新 migration 且无错误
- `python manage.py migrate` -- expected: 应用 migration 无错误
- `python manage.py test accounts` -- expected: 全部测试通过