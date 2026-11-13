- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: 生产配置加固 — DEBUG/ALLOWED_HOSTS 环境拆分、补 STATIC_ROOT 与 logging。
  evidence: 架构一致性约定要求敏感配置走环境变量；但 AD-10 明确本地单机演示，生产部署细节属其 Deferred 范围，非本故事（脚手架）缺陷。（SECRET_KEY 已在本故事修为环境变量读取。）

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: 开发期媒体服务 — config/urls.py 增加 static(settings.MEDIA_URL, document_root=MEDIA_ROOT)。
  evidence: 图片上传与展示属 story 2.1（FR-5）；届时接入媒体服务即可。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: 自定义 User 模型 — story 1.2 需在首次 migrate 前设置 AUTH_USER_MODEL（含 student_id/is_verified/role）。
  evidence: 架构 AD-3 要求字段在 User 上；本故事已用默认 User 跑过 migrate，story 1.2 需删除 db.sqlite3（已 gitignore）后重迁移。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: 本地化 — LANGUAGE_CODE 改为 zh-hans（中文项目）。
  evidence: TIME_ZONE=UTC 正确（架构要求）；LANGUAGE_CODE=en-us 为外观项，可后续调整。

## Deferred from: code review of spec-1-1-project-scaffold (2026-11-06)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: 规划文档中硬编码绝对 Windows 路径 — BMad 工具链生成工件（deferred-work.md、sprint-status.yaml、spec-1-1 的 context 元数据），非应用代码。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: epic-1-context.md 与 spec Code Map 中 Python 版本不一致（Python 3.14 vs 3.13.1） — 规划文档不一致，无代码影响。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-1-project-scaffold.md`
  summary: .gitignore 缺少跨平台条目（.env、.vscode/、.idea/、*.log、.DS_Store） — 次要代码卫生问题。

## Deferred from: code review of spec-1-2-用户注册 (2026-11-06)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-2-用户注册.md`
  summary: 导航栏中存在死链接（登录/退出 `href="#"`） — 登录/登出功能属 story 1.3，占位链接预期在该 story 中激活。

## Deferred from: code review of spec-1-4-学号身份认证-用户提交 (2026-11-07)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-4-学号身份认证-用户提交.md`
  summary: `VerificationRequestAdmin.save_model` 覆盖路径无独立测试 — 该路径逻辑与 `approve_requests` action 完全一致，当前功能已验证；若未来 save_model 逻辑与 action 分叉（如增加 side effect），需单独添加测试覆盖。
  evidence: review triage log low finding — save_model only tested implicitly via action test

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-1-4-学号身份认证-用户提交.md`
  summary: 条件唯一约束（`UniqueConstraint` + `condition=Q(status='pending')`）在 MySQL 8.4 生产后端被 Django 静默跳过 — `supports_partial_indexes=False`，`accounts/views.py:105-110` 的 `except IntegrityError` 并发兜底永不触发，并发提交可写入两条 pending。
  evidence: deferred reason — 演示项目不切 MySQL（课堂作业/演示用途，生产不会切到 MySQL 8.4，当前 SQLite 下约束有效）；若未来切换生产后端，须先重新设计该约束。

## Deferred from: code review of spec-2-8-商品详情页 (2026-11-13)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-2-8-商品详情页.md`
  summary: 详情页非安全方法在真实部署下返回 403 而非 AC 要求的 405（`Allow: GET, HEAD`） — `@require_safe` 在 `CsrfViewMiddleware.process_view` 之后执行，实测 `Client(enforce_csrf_checks=True)` 的 POST/PUT/PATCH/DELETE 全部 403 且无 `Allow` 头；只有未启用 CSRF 校验的默认测试客户端才得 405。
  evidence: deferred reason — 既有 `/listings/` 等全部 `@require_safe` 页面同一行为（项目级 Django 中间件顺序既定事实），两种情况下均无写入、不改 `status`，AC 的只读意图成立；修正需调整 config 级中间件或绕开 CSRF，超出 2.8 边界。

## Deferred from: code review of spec-4-4-订单状态机 (2026-11-13)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-4-4-订单状态机.md`
  summary: `epic-4-context.md` 声称卖家 QQ/微信字段由 `accounts` 提供，而 `accounts.User`（`accounts/models.py:5-14`）只有 `student_id` / `is_verified` / `role`，无任何 QQ/微信字段 — 4.3「下单后展示联系方式」当前没有数据源。
  evidence: deferred reason — 规划工件缺口；修复需在 `accounts` 增字段，而 spec-4-4 的 Never 明确禁止改 `accounts`，属需人类重协商的规划决策，须在 4.3 开工前解决。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-4-4-订单状态机.md`
  summary: `epic-4-context.md` 要求售出订单按 `product__seller` 过滤，而 `listings.Product` 的卖家字段名是 `owner`（`listings/models.py:46-49`） — 4.5 照抄会触发 `FieldError`。
  evidence: deferred reason — 上下文文档编译时未与代码核对，修复=编辑规划工件，非代码缺陷。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-4-4-订单状态机.md`
  summary: `refund_failed` 为终态且无出边，管理员驳回退款后订单永久卡死 — 既不能 `confirm_receipt()`（只接受 `paid`），也不能再 `request_refund()`，更不能 `mark_reviewed()`，买卖双方无法收尾。
  evidence: deferred reason — 转移表由 spec-4-4 冻结区 Decision 与 Implementation Notes 明确写死（「其余终态无出边」），缺口在 Epic 4 需求层，需规划层补一条「驳回退款后订单何去何从」的规则。

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-4-4-订单状态机.md`
  summary: 无「卖家不可购买自己商品」「同一商品不可并行多张非终态订单」约束；`buyer == product.owner` 时 4.7 的「双方互评」语义塌陷。
  evidence: deferred reason — 下单入口属 4.1，约束加在 `Order` 上会扩大 spec-4-4 的 schema 公共表面；属规划层待定规则。

## Deferred from: code review of spec-4-1-下单创建订单 (2026-11-13)

- source_spec: `C:/Users/18165/Desktop/my_project/_bmad-output/implementation-artifacts/spec-4-1-下单创建订单.md`
  summary: 个人中心「我的订单」恒为空态 — `accounts/views.py:146` 把 `my_orders_empty` 写死为 True，`templates/accounts/profile.html:82` 的 `{% else %}` 分支为空；4.1 后买家已能建单，但离开 `/orders/<id>/` 后没有任何入口能回到订单。
  evidence: deferred reason — 该空态属 story 1.5 既有实现，4.1 未改；spec-4-1 的 Never 明确把个人中心订单板块与「我的订单」列表留给 4.5。4.5 交付时需同时移除该硬编码常量并补上渲染分支，否则订单列表接通后仍显示空态。
