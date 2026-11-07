---
title: '学号身份认证（用户提交）'
type: 'feature'
created: '2026-11-07'
status: 'done'
baseline_commit: ccdc56ecc53a9b82f59f0ec5064ecb92fd7c9cf2
route: 'dispatch'
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-1-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 学生已能注册（story 1.2）并登录（story 1.3），但账号始终处于「待认证」状态——系统缺少学号认证的提交流程，学生无法向管理员发起身份认证请求，后续交易功能（商品发布需 `is_verified=True`）也因此无法使用。

**Approach:** 创建 `VerificationRequest` 模型存储认证申请记录；在 `accounts` app 中实现认证提交页面（预填学号 + 输入真实姓名）；管理员通过 Django 管理后台查看申请并手动通过/驳回（通过后设置 `User.is_verified=True`）；导航栏与首页根据 `is_verified` 状态显示「已认证」标识或「待认证」提示与认证入口。

## Boundaries & Constraints

**Always:**
- 仅已登录且 `is_verified=False` 的用户可提交认证申请（`login_required` + `is_verified` 检查）。
- 已认证用户（`is_verified=True`）访问认证页 → 302 重定向至首页。
- 认证表单字段：学号（预填当前用户的 `student_id`，只读）+ 姓名（必填，非空）。
- 学号格式校验：仅允许数字，长度 4–20 位（服务端 `RegexValidator`，正则 `^\d{4,20}$`）。此格式覆盖绝大多数中国高校学号，已确认为项目目标格式。
- 姓名校验：非空，长度 1–30 个字符。
- 提交后创建 `VerificationRequest` 记录，状态 `pending`；用户侧显示「认证申请已提交，等待管理员审核」。
- 同一用户只能有一个 `pending` 状态的申请（重复提交被拒绝并提示「你已有待审核的认证申请」）。
- 管理员通过 Django 管理后台审核（`/admin/`），不实现自定义审核页面——自定义审核页面留给 Story 5.4。通过 → `VerificationRequest.status='approved'` + `User.is_verified=True`；驳回 → `VerificationRequest.status='rejected'`。
- 被驳回后可重新提交：`rejected` 状态的申请可以重新提交（更新为 `pending`），不创建新记录。
- 导航栏：已认证用户昵称旁显示「✓ 已认证」绿色标识；未认证用户显示「待认证」+ 认证入口链接。
- 首页：已认证用户显示「你的账号已通过认证」（已有逻辑，保持）；未认证用户显示「你的账号尚未认证」+ 跳转认证页的入口。
- 页面使用 Django 模板 + Bootstrap 5.3 CDN，服务端渲染（AD-1）。
- 语言：所有用户可见文本使用中文。
- 数据库迁移：通过 Django ORM migration 创建 `VerificationRequest` 表。

**Never:**
- 不实现自动认证（不做真实学号名单对照）。
- 不修改 `User` 模型的字段（`is_verified`/`role`/`student_id` 保持不变）。
- 不上传学生证照片或任何附件。
- 不实现管理员自定义审核页面（Story 5.4 将扩展）。
- 不发送通知（邮件/站内信审核结果通知不在本故事范围）。
- 不引入 Django REST Framework 或任何 API 端点。
- 不引入前端构建链。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 正常提交认证 | 已登录 + `is_verified=False`，学号只读预填，输入姓名 | 创建 `VerificationRequest(status=pending)`，显示成功提示 | N/A |
| 重复提交 | 已有一个 `pending` 申请，再次提交 | 拒绝并提示「你已有待审核的认证申请」 | 返回表单页 + 错误提示 |
| 学号格式非法 | 学号含非数字字符或长度 <4 或 >20 | 拒绝，表单错误提示学号格式不正确 | 返回表单页 + 字段错误 |
| 姓名为空 | 姓名留空提交 | 拒绝，表单错误提示「请输入姓名」 | 返回表单页 + 字段错误 |
| 未登录访问 | 未登录访问 `/verify/` | 302 跳转 `/login/?next=/verify/` | N/A |
| 已认证访问 | 已登录 + `is_verified=True` 访问 `/verify/` | 302 重定向首页 | N/A |
| 驳回后重新提交 | `VerificationRequest.status='rejected'`，再次访问认证页 | 渲染表单，可修改姓名重新提交，状态更新为 `pending` | N/A |
| 已认证标识可见性 | `is_verified=True` 用户浏览任意页面 | 导航栏昵称旁显示「✓ 已认证」绿色标识 | N/A |

</frozen-after-approval>

## Code Map

- `accounts/models.py:1-16` — `User(AbstractUser)`，含 `student_id`（学号，CharField 32）、`is_verified`（BooleanField default=False）、`role`（student/admin）。需在同一个文件中新增 `VerificationRequest` 模型。
- `accounts/views.py:1-61` — 当前含 `register`、`login_view`、`logout_view` 三个 FBV。需添加 `verify_view`（FBV：GET 渲染认证表单，POST 校验并创建/更新 VerificationRequest）。复用 `login_required`、`redirect`、`render` 模式。
- `accounts/forms.py:1-62` — 当前含 `LoginForm`、`RegisterForm`。需添加 `VerificationForm`（`forms.Form`），字段：`student_id`（只读 CharField）、`name`（CharField 非空）。
- `accounts/urls.py:1-8` — 当前含 `register/`、`login/`、`logout/` 路由。需添加 `verify/` 路由。
- `accounts/admin.py:1-22` — 当前注册 `UserAdmin`。需注册 `VerificationRequestAdmin`，列表显示 `user`、`student_id`、`name`、`status`、`created_at`，支持按 `status` 过滤，审核操作通过 `list_editable` 或自定义 action 修改 `status` 并同步 `User.is_verified`。
- `templates/base.html:1-31` — 导航栏当前根据 `user.is_authenticated` 显示昵称+退出或注册+登录。需在已登录状态下根据 `user.is_verified` 显示「✓ 已认证」或「待认证」+ 认证入口。
- `templates/accounts/verify.html` — 不存在。需创建认证提交页面模板（继承 `base.html`），渲染只读学号 + 姓名输入框，显示表单错误和成功提示。
- `templates/index.html` — 首页当前根据认证状态显示不同文案。需更新为根据 `is_verified` 状态显示「已认证」或「待认证+认证入口」。
- `accounts/tests.py:1-266` — 当前含 `RegisterViewTests`、`LoginViewTests`、`LogoutViewTests` 共 27 个测试。需添加 `VerificationViewTests` 测试类：正常提交、重复提交拒绝、学号格式校验、姓名非空、未登录重定向、已认证重定向、驳回后重新提交、导航栏标识显示。

## Tasks & Acceptance

**Execution:**
- [x] `accounts/models.py` — 添加 `VerificationRequest` 模型（`user` FK → User、`student_id` CharField、`name` CharField、`status` CharField with choices pending/approved/rejected、`created_at` DateTimeField auto_now_add、`updated_at` DateTimeField auto_now），执行 `python manage.py makemigrations` + `migrate` — 存储认证申请的数据库层
- [x] `accounts/forms.py` — 添加 `VerificationForm(forms.Form)`：`student_id`（CharField，disabled widget，预填当前用户学号）、`name`（CharField，非空校验，max_length=30）— 认证表单校验逻辑
- [x] `accounts/views.py` — 添加 `verify_view`：检查 `is_verified`（已认证重定向首页），检查是否已有 `pending` 申请（有则拒绝），GET 渲染 `VerificationForm`（预填学号），POST 校验并创建/更新 `VerificationRequest` — 认证提交的核心逻辑
- [x] `accounts/urls.py` — 添加 `path('verify/', views.verify_view, name='verify')` 路由 — 认证页面的 URL 映射
- [x] `templates/accounts/verify.html` — 创建认证页面模板（继承 `base.html`），渲染只读学号 + 姓名输入框 + 提交按钮，显示字段错误、非字段错误、成功提示 — 认证表单的前端呈现
- [x] `templates/base.html` — 在导航栏已登录区域根据 `user.is_verified` 条件显示「✓ 已认证」绿色标识或「待认证」+ 认证入口链接 — 全局认证状态标识
- [x] `templates/index.html` — 更新首页认证状态文案：已认证保持「你的账号已通过认证」，未认证改为「你的账号尚未认证」+ 跳转认证页入口 — 首页认证引导
- [x] `accounts/admin.py` — 注册 `VerificationRequestAdmin`：`list_display`（user, student_id, name, status, created_at）、`list_filter`（status）、`search_fields`（student_id, name）、`actions`（通过/驳回操作同步更新 `User.is_verified`）— 管理员审核入口
- [x] `accounts/tests.py` — 添加 `VerificationViewTests` 测试类：正常提交 + 记录验证、重复 pending 拒绝、学号格式非法拒绝、姓名为空拒绝、未登录重定向、已认证用户重定向、驳回后重新提交、导航栏标识显示 — 覆盖所有 AC 和边界条件

**Acceptance Criteria:**
- Given 已登录且 `is_verified=False` 的账号，When 提交学号+姓名，Then 创建 `VerificationRequest(status=pending)`，`is_verified` 仍为 `False`，页面显示「认证申请已提交」
- Given 用户已有一个 `pending` 状态的认证申请，When 再次提交，Then 被拒绝并提示「你已有待审核的认证申请」
- Given `is_verified=True` 的账号，When 访问 `/verify/`，Then 302 重定向至首页
- Given 管理员在 Django 管理后台通过认证申请，When 审核通过，Then `User.is_verified=True` 且导航栏显示「✓ 已认证」
- Given `is_verified=True` 的用户，When 浏览任意页面，Then 导航栏昵称旁显示「✓ 已认证」绿色标识

### Review Findings

> 2026-11-07 ad hoc code review（`/bmad-code-review`），范围 `ccdc56e..HEAD`，模式 `full`；生效审查层：Edge Case Hunter + Acceptance Auditor（团队精简配置）。

**Patch**

- [x] [Review][Patch] `\d` 匹配 Unicode 数字，非 ASCII 学号可通过格式校验入库 [accounts/forms.py:5-8] — 实测 `re.search(r'^\d{4,20}$', '２０２４００１')` 为 True；`student_id` 为 `disabled=True`，表单取 `initial` 值校验后 `is_valid()` 为 True，全角数字与阿拉伯-印度数字学号会写入 `VerificationRequest`。与 spec「仅允许数字」的意图不符。已修复：正则收紧为 `^[0-9]{4,20}$`。
- [x] [Review][Patch] `student_id` 缺 `max_length` 中文错误文案，超长学号页面出现英文 [accounts/forms.py:73-83] — `config/settings.py:112` 为 `LANGUAGE_CODE='en-us'`，实测 21 位学号的表单错误为 `['学号格式不正确，应为 4–20 位数字', 'Ensure this value has at most 20 characters (it has 21).']`，违反 Always「所有用户可见文本使用中文」。已修复：补 `error_messages={'max_length': '学号长度不能超过 20 位'}`。

**Defer**

- [x] [Review][Defer] 条件唯一约束在 MySQL 上被 Django 静默跳过，「数据库层双保险」在生产后端不成立 [accounts/models.py:42-48] — deferred: 演示项目不切 MySQL（课堂作业/演示用途，生产不会切到 MySQL 8.4，当前 SQLite 下约束有效）；若未来切换生产后端，须先重新设计该约束。`accounts/models.py:42-48` 与 `accounts/migrations/0002_verificationrequest.py` 定义 `UniqueConstraint(condition=Q(status='pending'))`，`accounts/views.py:105-110` 依赖 `except IntegrityError` 兜底并发重复提交。实测 Django 5.2.19：SQLite `supports_partial_indexes=True`（约束生效，重复 pending 抛 `IntegrityError`），MySQL `supports_partial_indexes=False`（迁移时约束被跳过，兜底分支永不触发）。`project-context.md` 标注 MySQL 8.4 为可选生产后端；一旦切换，并发提交可写入两条 pending，破坏 Always「同一用户只能有一个 pending 状态的申请」，并使下游 `is_verified` 授权依据不可靠。

**Rejected**

- `low` → rejected — 已存在 `approved` 申请但 `is_verified=False` 时会新建 pending 申请：正常流程中 `approve_requests` 与 `save_model` 均同步 `is_verified=True`，`views.py:69` 已挡住已认证用户；仅管理员在 UserAdmin 手动撤销认证后可达，此时保留 approved 历史并新建申请符合「一人可多次申请」的数据模型，不违反任何 AC。修复需新增守卫分支，日常几乎不会遇到，收益不抵复杂度。
- `false` → rejected — `approve_requests` 缺少 `transaction.atomic()` 会导致状态不一致：两次 save 均为单表单行 UPDATE，未展示任何可达的 `user.save()` 失败路径；且该 action 幂等可重入，重跑即可补齐 `is_verified`，不一致状态不会持久（与既有 Review Triage Log 结论一致）。
- `false` → rejected — 后台编辑产生重复 pending 时 `IntegrityError` 未捕获导致 500：实测 Django 5.2 `BaseModelForm._post_clean` 调用 `full_clean(validate_constraints=True)`，`UniqueConstraint.validate()` 在表单层返回 `Constraint "unique_pending_verification_per_user" is violated.`，不会穿透到视图层；SQLite 下数据库约束亦实测生效，不产生 500。
- `low` → rejected — Design Notes 伪代码 `request.user.is_verified = True` 与实际代码语义矛盾：属 spec 文档措辞问题，修复方式是编辑被审查的 spec 本身（工作流规定此类发现不予保留）；实际代码使用 `verification.user.is_verified = True`，符合 AC4。
- `false` → rejected — AC4 缺「审核通过 → 导航栏 ✓ 已认证」端到端测试：`test_admin_approve_action_syncs_is_verified` 已断言 action 写入 `user.is_verified`，`test_verified_badge_shown_in_navbar` 已断言 `is_verified=True` 时渲染徽标；模板直接读 `user.is_verified`，两者之间不存在未测试的中间逻辑，未展示任何能让徽标出错而两个测试仍通过的改动。

## Implementation Notes

- `accounts/models.py`：新增 `VerificationRequest`（含 `unique_pending_verification_per_user` 条件唯一约束）；迁移 `accounts/migrations/0002_verificationrequest.py`。
- `accounts/forms.py`：新增 `VerificationForm`；学号字段 `disabled=True`（服务端忽略 POST 篡改值，始终取当前用户学号），`RegexValidator(r'^\d{4,20}$')`；姓名 `max_length=30` 且空白输入按必填处理。
- `accounts/views.py`：新增 `@login_required` 的 `verify_view`；已认证 302 首页；GET 渲染（pending 时显示等待审核提示）；POST 校验后创建 pending 或复用最近一条 rejected 记录更新为 pending；捕获 `IntegrityError` 兜底并发重复提交。
- `accounts/admin.py`：新增 `VerificationRequestAdmin`（列表/过滤/搜索 + 通过/驳回 action）；action 通过时同步 `User.is_verified=True`，驳回不改 User；详情页保存为 approved 时亦同步。
- 模板：新增 `templates/accounts/verify.html`；`base.html` 导航栏按认证状态显示「✓ 已认证」或「待认证 + 去认证」；`index.html` 未认证文案改为「你的账号尚未认证」并附认证入口。
- `accounts/tests.py`：新增 `VerificationViewTests`（20 个用例，覆盖提交、重复拒绝、学号格式、姓名非空、未登录/已认证重定向、驳回重提、导航栏标识、admin 审核同步）。
- 验证结果：`manage.py check` 无问题；`makemigrations --check` 无变更；`migrate` 成功；`manage.py test` 47 个测试全部通过。

## Spec Change Log

## Review Triage Log

- `low` → rejected — `approve_requests` 缺少 `transaction.atomic()`：`User.save(update_fields=['is_verified'])` 是单字段更新，SQLite 下不可能失败，不会产生不一致状态。
- `low` → rejected — `except IntegrityError` 笼统捕获：前面 `pending_request is not None` 守卫已双重保护，无关 IntegrityError 在正常流程中不会触发。
- `low` → rejected — `reject_requests` 未使用 `select_related`：该方法不访问 `.user` 属性，添加 `select_related` 反而浪费不必要的 JOIN 查询。
- `low` → deferred — `save_model` 覆盖路径无独立测试：该路径逻辑与 `approve_requests` action 完全一致，功能已验证；若未来 `save_model` 逻辑与 action 分叉，需单独测试。

## Design Notes

### VerificationRequest 模型设计

```python
class VerificationRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_requests')
    student_id = models.CharField(max_length=32, verbose_name='学号')
    name = models.CharField(max_length=30, verbose_name='姓名')
    status = models.CharField(
        max_length=16,
        choices=[('pending', '待审核'), ('approved', '已通过'), ('rejected', '已驳回')],
        default='pending',
        verbose_name='状态'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='pending'),
                name='unique_pending_verification_per_user'
            )
        ]
```

`UniqueConstraint` 在数据库层面保证每个用户最多一个 `pending` 申请，同时应用层也做检查（双保险）。

### 管理员审核同步 is_verified

管理员通过 Django admin action 审核时，需同步更新 `User.is_verified`：
- 通过 → `request.user.is_verified = True; request.user.save()`
- 驳回 → 仅更新 `VerificationRequest.status`，不改 User

### 学号格式

考虑到不同高校学号格式差异（纯数字/含字母、长度不等），使用 RegexValidator `r'^\d{4,20}$'` 在表单层校验，不阻塞数据库（CharField 存储原始字符串）。

## Verification

**Commands:**
- `python manage.py check` — expected: `System check identified no issues (0 silenced).`
- `python manage.py makemigrations accounts --dry-run --check` — expected: 检测到新迁移
- `python manage.py migrate` — expected: 迁移成功执行
- `python manage.py test accounts` — expected: 全部测试通过（含新增的认证提交测试）