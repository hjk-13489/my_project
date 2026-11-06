# Epic 1 Context: 用户账号与身份认证（accounts）

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

建立「同校可信」的身份基座：学生能注册账号、登录/登出、提交学号认证（待管理员审核），并在个人中心查看本人数据。这是后续所有交易（发布、聊天、下单）的前置——所有涉及「本人身份」与「他人身份」的功能都建立在 `accounts` app 的 `User`（含 `student_id` / `is_verified` / `role`）之上。

## Stories

- Story 1.1: 项目脚手架（Django 分层单体初始化）
- Story 1.2: 用户注册
- Story 1.3: 登录与登出
- Story 1.4: 学号身份认证（用户提交）
- Story 1.5: 个人中心

## Requirements & Constraints

- 注册：学号 + 密码（≥6 位）+ 昵称；学号唯一；注册后账号「待认证」（`is_verified=False`、`role='student'`）。
- 登录/登出：学号 + 密码登录，建立服务端 Session；错误凭据提示「学号或密码错误」；登出清除 Session；未登录访问受限页跳转登录页（HTTP 302）。
- 学号认证：提交学号 + 姓名，由管理员人工核实通过后置 `is_verified=True`；核实标准为格式校验（学号格式、姓名非空），**不做真实名单对照**。
- 个人中心：查看我的发布/订单/消息/评价，服务端强制仅返回本人数据。
- 安全：密码哈希加盐存储（Django 默认 PBKDF2），不存明文；所有写操作需登录鉴权；用户只能操作本人数据；学号仅管理员可见。

## Technical Decisions

- **整体形态**：分层单体，落地 Django MTV（Model-Template-View）服务端渲染，无 SPA/微服务，前端为 Django 模板 + Bootstrap。
- **数据存储**：关系型数据库，全程 Django ORM + migrations；开发/演示用 SQLite。
- **认证与会话**：Django 内置认证 + 服务端 Session（`HttpOnly` Cookie），非 JWT；`User` 扩展 `student_id`（学号，唯一）、`is_verified`（布尔认证位）、`role`（`student`/`admin`）。
- **授权**：服务端强制 RBAC（`student`/`admin`），用 `login_required`/权限装饰器 + 查询过滤，禁止仅前端隐藏式伪权限。
- **部署**：单机本地（`runserver`/Gunicorn + SQLite），目标浏览器 Chrome/Edge。
- **结构种子**：`config/` 项目配置 + 5 个 app（`accounts`/`listings`/`chat`/`orders`/`dashboard`）+ `media/`/`static/`/`templates/` + `manage.py` + `requirements.txt`。
- **命名约定**：app 复数小写、Model 单数 CamelCase、字段 snake_case；时间 UTC（`USE_TZ=True`）。
- **技术栈**：Python 3.14 / Django 5.2 LTS / SQLite 3.x / Pillow 13.0 / Bootstrap 5.3（以 `requirements.txt` 锁定为准）。

## Cross-Story Dependencies

- Story 1.1（脚手架）是结构种子，所有后续故事（本史诗及其他史诗）都在其之上构建。
- Story 1.2（注册）是 1.3（登录）与 1.4（认证）的前置——先有账号才能登录/认证。
- Story 1.5（个人中心）依赖登录态（1.3）与 `role` 字段（1.2 建立）。
- 本史诗的 `User` 与 `is_verified`/`role` 字段是 Epic 2（商品发布需 `is_verified=True`）、Epic 5（管理员认证核实/封禁）等下游史诗的依赖。
