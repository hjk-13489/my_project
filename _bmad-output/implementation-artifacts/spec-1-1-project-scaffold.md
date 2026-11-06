---
title: '项目脚手架（Django 分层单体初始化）'
type: 'chore'
created: '2026-11-06'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 151d55cf8b656295e42dbe3ff159ad507768b66e
context:
  - _bmad-output/planning-artifacts/architecture/architecture-my_project-2026-11-05/architecture.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 全新空仓库缺少 Django 分层单体骨架，后续 29 个故事（用户/商品/聊天/订单/管理员后台）都要在同一可部署单元上构建，必须先有一个可运行、可验证的项目骨架。

**Approach:** 初始化 Django 5.2 LTS 分层单体：创建 `config` 项目包 + 5 个 app（`accounts`/`listings`/`chat`/`orders`/`dashboard`）+ `media`/`static`/`templates` 目录 + `manage.py` + `requirements.txt`，并确保 `check` 无错误、SQLite 迁移可生成、`runserver` 可启动。

## Boundaries & Constraints

**Always:**
- 分层单体（Django MTV 服务端渲染），非 SPA / 微服务 / 前后端分离。
- 5 个 app（`accounts`/`listings`/`chat`/`orders`/`dashboard`）全部注册进 `INSTALLED_APPS`。
- `USE_TZ=True`、时间 UTC、默认数据库 SQLite（开发/演示）。
- 项目包名为 `config`（`config/settings.py`）。
- `requirements.txt` 锁定 Django 5.2 LTS、Pillow 13.0；Bootstrap 5.3 作为前端版本声明（前端资产，非 pip 依赖）。
- 命名约定：app 复数小写、Model 单数 CamelCase、字段 snake_case。
- 本故事只建骨架（空 models/views/urls/forms），不实现任何业务逻辑。
- 依赖经项目 `.venv` 虚拟环境安装并锁定 Django 5.2 LTS + Pillow 13.0；不使用全局已装的 Django 6.0.4 / Pillow 11.0.0。

**Never:**
- 不引入 React/Vue 前端构建链、REST API、微服务。
- 不配置 MySQL 生产环境（仅 SQLite）。
- 不实现注册/登录/商品等业务功能（属 1.2+ 与后续史诗）。
- 不提交 `db.sqlite3`、`media/` 上传内容、`.venv`、`__pycache__`。

## I/O & Edge-Case Matrix

</frozen-after-approval>

## Code Map

- 仓库当前无任何代码（仅 `.git`、`.claude`、`_bmad/`、`_bmad-output/`、`decision-log.md`、一个 .pptx 讲义）—— 绿场初始化，无可复用文件、无需要避开的既有代码。
- 环境：Python 3.13.1（全局）、pip 26.3、Django 6.0.4（全局）、Pillow 11.0.0（全局）。
- 结构种子（源自 architecture.md「结构种子」）：`config/` + 5 个 app + `media/`/`static/`/`templates/` + `manage.py` + `requirements.txt`。
- 一致约定：`USE_TZ=True`、价格 `DecimalField(10,2)`（后续故事）、成色 choices=全新/良好/中等、分类 choices=教材/日用品/电子数码/其他（后续故事）。

## Tasks & Acceptance

**Execution:**
- [x] `.venv/` -- 创建虚拟环境并安装 Django 5.2 LTS + Pillow 13.0 -- 满足版本锁定决策
- [x] `requirements.txt` -- 写入 Django 5.2 LTS 与 Pillow 13.0 依赖锁定，并声明 Bootstrap 5.3 前端版本 -- 满足 AC「锁定依赖」
- [x] `config/`（`settings.py`/`urls.py`/`wsgi.py`/`asgi.py`） -- `django-admin startproject config .` 生成项目包 -- 建立可运行项目
- [x] `config/settings.py` -- 注册 5 个 app、`USE_TZ=True`、SQLite 默认库、模板/静态/media 路径、时区 UTC -- 满足 AC「INSTALLED_APPS 含 5 app、USE_TZ=True」
- [x] `accounts/` `listings/` `chat/` `orders/` `dashboard/` -- `startapp` 生成 5 个 app 骨架 -- 满足 AC「5 个 app」
- [x] `media/` `static/` `templates/` -- 创建目录（含 `.gitkeep` 占位） -- 满足结构种子
- [x] `.gitignore` -- 忽略 `db.sqlite3`、`media/`、`__pycache__`、`.venv`、`*.pyc` -- 保持仓库干净
- [x] 验证 -- 运行 `python manage.py check` 与 `migrate`，确认无错误 -- 满足 AC「check 无错误、迁移可生成」

**Acceptance Criteria:**
- Given 全新空仓库，When 执行脚手架初始化并运行 `python manage.py migrate` 与 `check`，Then 项目含 5 个 app 与 `config` 包、`check` 无错误、`runserver` 可启动。
- And `INSTALLED_APPS` 含 5 个 app、`USE_TZ=True`、SQLite 迁移可生成。
- And `requirements.txt` 锁定 Django 5.2 LTS / Pillow 13.0 / Bootstrap 5.3。

## Implementation Notes

## Spec Change Log

## Review Triage Log

- `low` → patch — SECRET_KEY 已修为环境变量读取（`os.environ` DJANGO_SECRET_KEY，含 dev 占位回退）。证据：架构一致性约定要求敏感配置走环境变量、不入库；提交时被安全分类器拦截，故改为环境变量。DEBUG/ALLOWED_HOSTS 环境拆分仍属 AD-10 Deferred。
- `low` → defer — MEDIA_URL/MEDIA_ROOT 已配置但 config/urls.py 未加 static(media) 服务。证据：图片上传与展示属 story 2.1（FR-5），届时接入媒体服务。
- `low` → defer — STATIC_ROOT 缺失，collectstatic 无目标。证据：本地开发用 STATICFILES_DIRS + runserver 即可；生产静态部署属 AD-10 Deferred。
- `low` → defer — 未设置 AUTH_USER_MODEL / 自定义 User。证据：User 的 student_id/is_verified/role 字段属 story 1.2；届时需在首次 migrate 前设置 AUTH_USER_MODEL，可删除 db.sqlite3（已 gitignore）重迁移。
- `low` → defer — 无 logging 配置。证据：生产日志属 AD-10 Deferred，非本故事 AC。
- `low` → defer — LANGUAGE_CODE=en-us（中文项目可改 zh-hans）。证据：TIME_ZONE=UTC 正确（架构要求）；语言为外观项。
- `false` — 5 个 app 为空骨架（models/views/forms/urls 空）。证据：frozen 块「Always」明确「只建骨架，不实现业务逻辑」。
- `false` — 无 migrations。证据：无模型即无迁移，业务模型属后续故事。
- `false` — chat 应支持 WebSocket/channels。证据：AD-7 明确「不引入 WebSocket/ASGI」，聊天为纯文字 HTTP 轮询。
- `false` — 无测试。证据：测试随各故事业务逻辑引入，骨架阶段无业务可测。
- `false` — 无模板（templates/ 仅 .gitkeep）。证据：模板随 UI 故事（1.2+）引入。
- `false` — requirements.txt 缺少 test/lint/env 依赖。证据：AC 明确锁定范围仅 Django/Pillow/Bootstrap。
- `false` — 无 README/.env.example/CI。证据：超出本故事意图。
- `low` → patch — MEDIA_URL="media/" 缺前导斜杠（已修为 "/media/"）。证据：Django 文档约定 "/media/"；缺斜杠时非根路径页面 {{ MEDIA_URL }} 会解析为相对路径。
- `low` → patch — requirements.txt 版本锁定未被任何校验命令覆盖（verification-gap 主发现，预验证）。证据：check/migrate/assert 均不触碰 requirements.txt，锁定可静默漂移；已在 Verification 增加版本断言命令。

## Verification

**Commands:**
- `python manage.py check` -- expected: `System check identified no issues (0 silenced).`
- `python manage.py migrate` -- expected: 应用全部初始迁移、无报错、生成 `db.sqlite3`
- `python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.conf import settings; assert set(['accounts','listings','chat','orders','dashboard']).issubset(settings.INSTALLED_APPS) and settings.USE_TZ is True"` -- expected: 无异常退出
- `python -c "import django, PIL; assert django.get_version().startswith('5.2'), django.get_version(); assert PIL.__version__.startswith('13.0'), PIL.__version__; print('VERSIONS_OK', django.get_version(), PIL.__version__)"` -- expected: 输出 VERSIONS_OK 且 Django 5.2.x、Pillow 13.0.x
