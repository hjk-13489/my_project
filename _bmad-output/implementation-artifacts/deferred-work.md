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
