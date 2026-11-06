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
