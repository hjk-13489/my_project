<!-- bmad:context -->
<!-- Verified 2026-11-05 against 948aea6. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## my_project — 校园二手书/闲置物品交易系统

福州大学旗山校区网页端二手交易平台，课堂作业。Django 分层单体（MTV），SQLite 开发 / MySQL 8.4 生产。规划文档在 `_bmad-output/planning-artifacts/`，人机决策在 `decision-log.md`，架构不变量在 `architecture.md`。

## Policy

- 不做真实第三方支付、物流/快递、完整即时通讯（图片/实时推送）、移动端 App、跨校区交易；v1 仅网页端、同校当面交付。
- 系统为单一 Django 单体，按 `accounts`/`listings`/`chat`/`orders`/`dashboard` 五个 app 垂直切分；不引入独立前端构建产物（React/Vue）与服务间 RPC，前端用 Django 模板 + Bootstrap 服务端渲染。
- 实体及其生命周期方法归所属 app 唯一定义，其他 app 只调用、不复刻：订单状态机归 `orders`、商品可见性归 `listings`、学号认证位归 `accounts`；`dashboard` 复用而非另写一套。

## Where things are

- 架构骨架（10 条 AD 不变量 + 结构种子）：`_bmad-output/planning-artifacts/architecture/architecture-my_project-2026-11-05/architecture.md`
- 需求（FR-1~FR-29、NFR-1~NFR-6）：`_bmad-output/planning-artifacts/prds/prd-my_project-2026-11-04/prd.md`
- 人机决策日志（D-001~D-015）：`decision-log.md`
- app 分工：`accounts` 用户/学号认证，`listings` 商品/审核/搜索，`chat` 站内聊天，`orders` 订单/支付/评价/退款，`dashboard` 管理员后台。

## Running and verifying

所需工具版本（2026-11-05 核实，代码建立后以 `requirements.txt` 为准）：

| 组件 | 版本 |
| --- | --- |
| Python | 3.14 |
| Django | 5.2 LTS |
| SQLite | 3.x（开发/演示） |
| MySQL | 8.4 LTS（可选生产） |
| Pillow | 13.0 |
| Bootstrap | 5.3 |

- 开发：`python manage.py runserver`；演示可用 Gunicorn；单机本地运行，不用 Docker/K8s。

## Conventions that differ from defaults

- 认证用 Django 内置认证 + 服务端 Session（HttpOnly Cookie），不用 JWT；学号认证 = `User.is_verified` 布尔位，管理员人工审核后置真。
- 权限在服务端强制校验（视图装饰器/查询过滤），角色仅 `student`/`admin`；不用前端隐藏式伪权限。
- 订单状态机在 `orders` models 层唯一定义，合法转移封装为 Model 方法 `pay()`/`confirm_receipt()`/`request_refund()`/`resolve_refund()`，视图不得直接改 status 字段。
- 模拟支付是服务端单事务内的原子状态流转（`待支付 → 已支付/待交付`），不调用任何外部支付网关。
- 站内聊天仅纯文本 + 定时 HTTP 轮询（约 5 秒），不引入 WebSocket/ASGI channel。
- 商品图片经 Pillow 校验（仅 JPEG/PNG）并缩略，存本地 `media/`，单图 ≤5MB。
- 商品可见性由 `status` 字段驱动，列表/搜索在服务端强制过滤 `status=approved`（先审后上架）。
- 价格用 `DecimalField(max_digits=10, decimal_places=2)`，不用 float。
- 成色 `choices` = 全新/良好/中等；分类 `choices` = 教材/日用品/电子数码/其他。
- app 名复数小写；Model 单数 CamelCase；字段 snake_case。
- 时间统一 UTC（`USE_TZ=True`）；`SECRET_KEY`、DB 口令走环境变量，不入库。

<!-- /bmad:context -->
