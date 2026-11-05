---
status: final
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-my_project-2026-11-04/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-my_project-2026-11-05/architecture.md
---

# 校园二手书/闲置物品交易系统 - Epic Breakdown

## Overview

本文档将 PRD（FR-1~FR-29、NFR-1~NFR-6）与架构骨架（AD-1~AD-10 + 结构种子 + 技术栈）拆解为可实施的故事，按**用户价值**组织为 5 个史诗，与架构的 5 个 Django app（`accounts` / `listings` / `chat` / `orders` / `dashboard`）一一对应。每个故事的验收标准均为**可直接翻译成一条测试断言的 Given/When/Then 语句**，并显式标注其所依赖的架构不变量（AD）与功能需求（FR）。

## Requirements Inventory

### Functional Requirements

FR1: 注册 — 学号+密码+昵称注册，注册后账号「待认证」；学号唯一、密码≥6位。
FR2: 登录/登出 — 学号+密码登录、可登出；未登录访问受限页跳转登录。
FR3: 学号身份认证 — 提交学号+姓名，管理员核实通过后标记「已认证」。
FR4: 个人中心 — 查看我的发布/订单/消息/评价，仅本人数据。
FR5: 发布商品 — 标题/描述/价格/成色/分类必填 + 图片≥1张；价格>0；分类预设。
FR6: 待审核与上架 — 提交后「待审核」，审核通过才上架；待审核/驳回不可见。
FR7: 驳回通知与重新提交 — 驳回理由通知卖家，可修改重提。
FR8: 查看我的发布 — 列表展示各商品当前状态。
FR9: 商品列表浏览 — 仅「上架」商品，含缩略图/标题/价格/成色。
FR10: 关键词搜索 — 匹配标题或描述。
FR11: 分类/价格/成色筛选 — 组合筛选，结果满足全部条件。
FR12: 商品详情页 — 全部图片/描述/价格/成色/分类/卖家昵称+认证状态 +「联系卖家」「立即购买」。
FR13: 买家发起聊天 — 下单前对卖家发文字消息，与商品/卖家关联。
FR14: 卖家查看与回复 — 「我的消息」查看并回复。
FR15: 纯文字+轮询刷新 — 仅文字，刷新/轮询更新，无实时推送。
FR16: 未读提示 — 未读数显示，查看后清零。
FR17: 下单 — 订单确认页（商品/价格/留言），创建订单「待支付」。
FR18: 模拟支付 — 「待支付」→「已支付/待交付」，仅状态流转。
FR19: 下单后展示联系方式 — 支付后展示卖家 QQ/微信 + 认证状态。
FR20: 订单状态机 — 仅沿合法状态流转，非法跳转拒绝。
FR21: 订单列表 — 「我的订单」「售出订单」。
FR22: 确认收货 — →「已确认收货」并自动「已完成」，不可再退款。
FR23: 互评 — 双方提交评价后订单「已互评」。
FR24: 退款请求 — 「已支付/待交付」可发起，→「纠纷」。
FR25: 待审核区 — 通过（上架）/ 驳回（填理由）。
FR26: 下架违规商品 — 下架 + 通知卖家。
FR27: 纠纷裁决 — 同意退款（退款成功）/ 不同意（退款失败）。
FR28: 用户管理 — 核实认证 / 封禁。
FR29: 数据看板 — 用户数/发布数/成交数/纠纷数。

### NonFunctional Requirements

NFR1（性能）: 列表/搜索响应 ≤1s（P95）；首屏加载 ≤2s。
NFR2（安全）: 密码哈希加盐存储；所有写操作需登录鉴权；用户只能操作本人数据。
NFR3（一致性）: 订单状态仅合法流转；「待审核」商品不可被搜索/浏览。
NFR4（隐私）: 卖家 QQ/微信仅对已下单买家展示；学号仅管理员可见。
NFR5（兼容性）: 最新版 Chrome/Edge 功能完整可用。
NFR6（可用性）: 核心闭环（发布→审核→浏览→下单→支付→交付→确认→评价）无阻断。

### Additional Requirements

来自架构骨架（AD-1~AD-10 + 技术栈 + 结构种子），作为跨故事的技术约束：

- **Starter Template（脚手架）**：Django 分层单体（MTV）绿场初始化 —— `config/` + 5 个 app（`accounts`/`listings`/`chat`/`orders`/`dashboard`）+ `media/`/`static/`/`templates/` + `manage.py` + `requirements.txt`。落点为 Epic 1 Story 1.1。
- AD-1 分层单体（Django MTV），无 SPA/微服务，服务端渲染。
- AD-2 关系型数据库（SQLite 开发/MySQL 8.4 可选生产），Django ORM + migrations。
- AD-3 服务端 Session 认证（HttpOnly Cookie），非 JWT；密码 PBKDF2 哈希加盐；学号认证 = `User.is_verified` 布尔位，管理员人工审核（格式校验，不做名单对照）。
- AD-4 服务端强制 RBAC（`student`/`admin`），非前端隐藏式伪权限。
- AD-5 订单状态机在 `orders` models 层唯一定义，合法转移封装为 `pay()`/`confirm_receipt()`/`request_refund()`/`resolve_refund()`，视图不得直接改 status。
- AD-6 模拟支付 = 服务端单事务内的原子状态流转（`待支付 → 已支付/待交付`），不调外部支付网关。
- AD-7 聊天纯文字 + 定时 HTTP 轮询（~5s），无 WebSocket/ASGI。
- AD-8 图片 Pillow 校验（仅 JPEG/PNG）并缩略，存本地 `media/`，单图 ≤5MB。
- AD-9 先审后上架，可见性由 `status` 驱动，列表/搜索强制过滤 `status=approved`。
- AD-10 单机本地部署（`runserver`/Gunicorn + SQLite），目标浏览器 Chrome/Edge。
- 一致性约定：价格 `DecimalField(10,2)`；成色 choices = 全新/良好/中等；分类 choices = 教材/日用品/电子数码/其他；时间 UTC（`USE_TZ=True`）；app 复数小写、Model 单数 CamelCase、字段 snake_case。
- 技术栈：Python 3.14 / Django 5.2 LTS / SQLite 3.x / Pillow 13.0 / Bootstrap 5.3。

### UX Design Requirements

（无独立 UX 文档；交互形态由 PRD 用户旅程 UJ-1~UJ-4 与架构服务端渲染约定覆盖，不单独拆分 UX-DR。）

### FR Coverage Map

| FR | Epic | Story |
| --- | --- | --- |
| FR-1 | Epic 1 | 1.2 用户注册 |
| FR-2 | Epic 1 | 1.3 登录与登出 |
| FR-3 | Epic 1 | 1.4 学号身份认证（用户提交） |
| FR-4 | Epic 1 | 1.5 个人中心 |
| FR-5 | Epic 2 | 2.1 发布商品（含图片上传） |
| FR-6 | Epic 2 | 2.2 商品状态流转：待审核→上架/驳回 |
| FR-7 | Epic 2 | 2.3 驳回通知与重新提交 |
| FR-8 | Epic 2 | 2.4 查看我的发布 |
| FR-9 | Epic 2 | 2.5 商品列表浏览（仅上架） |
| FR-10 | Epic 2 | 2.6 关键词搜索 |
| FR-11 | Epic 2 | 2.7 分类/价格/成色筛选 |
| FR-12 | Epic 2 | 2.8 商品详情页 |
| FR-13 | Epic 3 | 3.1 买家发起聊天 |
| FR-14 | Epic 3 | 3.2 卖家查看与回复 |
| FR-15 | Epic 3 | 3.3 纯文字消息 + 轮询刷新 |
| FR-16 | Epic 3 | 3.4 未读提示 |
| FR-17 | Epic 4 | 4.1 下单创建订单 |
| FR-18 | Epic 4 | 4.2 模拟支付 |
| FR-19 | Epic 4 | 4.3 下单后展示联系方式 |
| FR-20 | Epic 4 | 4.4 订单状态机 |
| FR-21 | Epic 4 | 4.5 订单列表 |
| FR-22 | Epic 4 | 4.6 确认收货 |
| FR-23 | Epic 4 | 4.7 互评 |
| FR-24 | Epic 4 | 4.8 退款请求 |
| FR-25 | Epic 5 | 5.1 待审核区（通过/驳回） |
| FR-26 | Epic 5 | 5.2 下架违规商品 |
| FR-27 | Epic 5 | 5.3 纠纷裁决 |
| FR-28 | Epic 5 | 5.4 用户管理（认证核实/封禁） |
| FR-29 | Epic 5 | 5.5 数据看板 |

NFR 覆盖：NFR-2（安全）→ 1.2/1.3/1.5/4.5/5.x；NFR-3（一致性）→ 2.2/4.4；NFR-4（隐私）→ 4.3；NFR-1（性能）→ 2.5/2.6/2.7；NFR-5/6（兼容/可用）→ 1.1（脚手架）+ 全局。

## Epic List

### Epic 1: 用户账号与身份认证（`accounts`）
学生能注册、登录、完成学号认证，并在个人中心查看本人数据——建立「同校可信」的身份基座，是后续所有交易的基础。
**FRs covered:** FR-1, FR-2, FR-3, FR-4

### Epic 2: 商品发布与浏览（`listings`）
卖家发布闲置（经审核后上架），买家浏览、搜索、筛选并查看详情——跑通「发布→审核→浏览/搜索」闭环。
**FRs covered:** FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12

### Epic 3: 站内聊天（`chat`）
买家在商品详情页发起纯文字协商，卖家查看回复，未读消息有提示——补齐「下单前协商」环节。
**FRs covered:** FR-13, FR-14, FR-15, FR-16

### Epic 4: 交易订单与评价（`orders`）
买家下单、模拟支付、查看联系方式、确认收货、互评，支持退款请求——跑通完整交易状态机。
**FRs covered:** FR-17, FR-18, FR-19, FR-20, FR-21, FR-22, FR-23, FR-24

### Epic 5: 管理员后台（`dashboard`）
管理员审核/下架商品、裁决纠纷、管理用户、查看数据看板——维护平台秩序。
**FRs covered:** FR-25, FR-26, FR-27, FR-28, FR-29

---

## Epic 1: 用户账号与身份认证（`accounts`）

**Epic goal:** 学生获得可信账号身份，可注册、登录、认证学号、查看本人数据。

### Story 1.1: 项目脚手架（Django 分层单体初始化）

As a 开发团队,
I want 初始化 Django 分层单体骨架（`config` + `accounts`/`listings`/`chat`/`orders`/`dashboard` 五个 app + `media`/`static`/`templates` + `requirements.txt` + SQLite）,
So that 后续所有故事在同一个可部署单元上构建。

**Acceptance Criteria:**

**Given** 一个全新空仓库
**When** 执行脚手架初始化并运行 `python manage.py migrate` 与 `python manage.py check`
**Then** 项目包含 5 个 Django app 与 `config` 包，`check` 无错误，`runserver` 可启动
**And** `INSTALLED_APPS` 含 5 个 app，`USE_TZ=True`，默认数据库为 SQLite 且迁移可生成
**And** `requirements.txt` 锁定 Django 5.2 LTS、Pillow 13.0、Bootstrap 5.3

**依赖架构:** AD-1（分层单体）、AD-2（SQLite/ORM）、AD-10（单机本地部署）。无 FR（来自结构种子）。

### Story 1.2: 用户注册

As a 学生,
I want 用学号+密码+昵称注册账号,
So that 获得一个「待认证」账号开始使用平台。

**Acceptance Criteria:**

**Given** 注册表单已呈现
**When** 输入学号、密码（≥6位）、昵称并提交
**Then** 创建 `User` 记录且 `is_verified=False`、`role='student'`，页面状态显示「待认证」
**And** 重复学号提交被拒绝并提示
**And** 密码长度 < 6 位被拒绝

**依赖架构:** AD-3（Session 认证、密码哈希）。**需求:** FR-1。

### Story 1.3: 登录与登出

As a 学生,
I want 用学号+密码登录并登出,
So that 以本人身份访问平台功能。

**Acceptance Criteria:**

**Given** 已注册账号
**When** 输入正确学号+密码登录
**Then** 建立服务端 Session（HttpOnly Cookie）并跳转首页
**And** 错误凭据提示「学号或密码错误」
**And** 登出清除 Session
**And** 未登录访问需登录页面时跳转登录页（HTTP 302）

**依赖架构:** AD-3（Session）、AD-4（RBAC）。**需求:** FR-2。

### Story 1.4: 学号身份认证（用户提交）

As a 学生,
I want 提交学号+姓名等待管理员认证,
So that 账号可标记为「已认证」并在交易中展示可信身份。

**Acceptance Criteria:**

**Given** 已登录且「待认证」（`is_verified=False`）账号
**When** 提交学号+姓名
**Then** 提交记录进入待审核状态，`is_verified` 仍为 `False`，用户侧不显示「已认证」标识
**And** 当 `is_verified=True` 时，商品详情页与下单后联系方式旁显示「已认证」标识

**依赖架构:** AD-3（学号认证 = `is_verified` 布尔位，管理员人工审核）。**需求:** FR-3。

### Story 1.5: 个人中心

As a 学生,
I want 在个人中心查看我的发布/订单/消息/评价,
So that 集中管理本人交易数据。

**Acceptance Criteria:**

**Given** 已登录用户
**When** 访问个人中心各入口
**Then** 仅返回当前登录用户本人的数据（他人数据不出现）

**依赖架构:** AD-4（服务端 RBAC，仅本人数据）。**需求:** FR-4。

---

## Epic 2: 商品发布与浏览（`listings`）

**Epic goal:** 卖家发布闲置（经审核后上架），买家浏览、搜索、筛选并查看详情。

### Story 2.1: 发布商品（含图片上传）

As a 卖家（已认证学生）,
I want 填写标题/描述/价格/成色/分类并上传图片后发布,
So that 我的闲置进入审核流程。

**Acceptance Criteria:**

**Given** 已登录且已认证（`is_verified=True`）卖家
**When** 填写标题、描述、价格、成色、分类并上传 ≥1 张图片提交
**Then** 创建 `Product` 记录且 `status='pending'`（待审核）
**And** 任一必填项（标题/描述/价格/成色/分类）缺失时不可提交
**And** 价格非数字或 ≤0 被拒绝
**And** 分类仅允许「教材/日用品/电子数码/其他」，成色仅允许「全新/良好/中等」
**And** 图片经 Pillow 校验仅 JPEG/PNG、单图 ≤5MB，存储于本地 `media/`

**依赖架构:** AD-8（图片本地存储）、AD-9（先审后上架）。**需求:** FR-5。

### Story 2.2: 商品状态流转：待审核→上架/驳回

As a 平台,
I want 商品提交后为「待审核」、审核通过才上架、待审核/驳回不可见,
So that 违规商品不直接对外可见。

**Acceptance Criteria:**

**Given** 商品 `status='pending'`（待审核）
**When** 普通用户浏览列表或搜索
**Then** 查询不到该商品（服务端强制过滤 `status='approved'`）
**And** 管理员审核通过后 `status='approved'`，可被列表/搜索命中

**依赖架构:** AD-9（可见性由 status 驱动）。**需求:** FR-6。

### Story 2.3: 驳回通知与重新提交

As a 卖家,
I want 收到驳回理由并可修改重新提交,
So that 被驳回商品可修正后再进入审核。

**Acceptance Criteria:**

**Given** 商品被管理员驳回（`status='rejected'`）
**When** 卖家查看「我的消息」
**Then** 显示驳回理由
**And** 卖家可基于该商品修改并重新提交，提交后 `status` 回到 `'pending'`

**依赖架构:** AD-9。**需求:** FR-7。

### Story 2.4: 查看我的发布

As a 卖家,
I want 查看我的发布列表及各商品状态,
So that 掌握每件商品当前处于待审核/已上架/已下架。

**Acceptance Criteria:**

**Given** 已登录卖家
**When** 访问「我的发布」
**Then** 列表展示每件商品当前状态（待审核/已上架/已下架），仅本人数据

**依赖架构:** AD-9、AD-4。**需求:** FR-8。

### Story 2.5: 商品列表浏览（仅上架）

As a 买家,
I want 浏览已上架商品列表,
So that 看到可购买的闲置。

**Acceptance Criteria:**

**Given** 存在多件商品
**When** 访问商品列表页
**Then** 仅展示 `status='approved'` 的商品，含缩略图/标题/价格/成色
**And** 列表/搜索接口响应 ≤1s（NFR-1）

**依赖架构:** AD-9（强制过滤 approved）、NFR-1。**需求:** FR-9。

### Story 2.6: 关键词搜索

As a 买家,
I want 按关键词搜索商品,
So that 快速找到想要的教材/闲置。

**Acceptance Criteria:**

**Given** 存在已上架商品
**When** 输入关键词搜索
**Then** 返回标题或描述匹配关键词的商品，且仅限 `status='approved'`

**依赖架构:** AD-9、AD-2（ORM 查询）。**需求:** FR-10。

### Story 2.7: 分类/价格/成色筛选

As a 买家,
I want 按分类、价格区间、成色组合筛选,
So that 缩小范围找到合意商品。

**Acceptance Criteria:**

**Given** 存在已上架商品
**When** 组合分类、价格区间、成色条件筛选
**Then** 结果仅含满足全部条件的商品，且仅限 `status='approved'`

**依赖架构:** AD-9、AD-2。**需求:** FR-11。

### Story 2.8: 商品详情页

As a 买家,
I want 查看商品详情页的全部信息与操作入口,
So that 决定是否联系卖家或购买。

**Acceptance Criteria:**

**Given** 一件已上架商品
**When** 访问详情页
**Then** 展示全部图片/描述/价格/成色/分类/卖家昵称 + 认证状态
**And** 「联系卖家」进入站内聊天（FR-13），「立即购买」进入下单（FR-17）
**And** 待审核/驳回/下架商品详情页对普通用户返回 404 或不可见

**依赖架构:** AD-9、AD-4。**需求:** FR-12。

---

## Epic 3: 站内聊天（`chat`）

**Epic goal:** 买卖双方在系统内用纯文字协商，未读消息有提示。

### Story 3.1: 买家发起聊天

As a 买家,
I want 在商品详情页点「联系卖家」发送文字消息,
So that 下单前与卖家协商议价/成色。

**Acceptance Criteria:**

**Given** 已登录买家查看某已上架商品
**When** 点「联系卖家」并发送文字消息
**Then** 消息创建并关联对应商品与卖家
**And** 下单前可发送消息

**依赖架构:** AD-7（纯文字 + HTTP 轮询）。**需求:** FR-13。

### Story 3.2: 卖家查看与回复

As a 卖家,
I want 在「我的消息」查看并回复买家,
So that 完成协商。

**Acceptance Criteria:**

**Given** 已登录卖家收到消息
**When** 打开「我的消息」
**Then** 列出收到的对话并可回复文字

**依赖架构:** AD-7。**需求:** FR-14。

### Story 3.3: 纯文字消息 + 轮询刷新

As a 用户,
I want 聊天仅支持纯文字并通过轮询刷新,
So that 以简化实现跑通协商且不引入实时推送。

**Acceptance Criteria:**

**Given** 聊天窗口
**When** 尝试发送/粘贴图片或富文本
**Then** 被拒绝或按纯文本处理
**And** 消息内容仅文字；新消息在页面刷新或轮询周期（约 5s）后可见，不依赖 WebSocket

**依赖架构:** AD-7。**需求:** FR-15。

### Story 3.4: 未读提示

As a 用户,
I want 「我的消息」入口显示未读数并在查看后清零,
So that 不漏掉新消息。

**Acceptance Criteria:**

**Given** 收到新消息
**When** 查看「我的消息」入口
**Then** 显示未读数
**And** 查看后未读数清零

**依赖架构:** AD-7。**需求:** FR-16。

---

## Epic 4: 交易订单与评价（`orders`）

**Epic goal:** 买家下单、模拟支付、查看联系方式、确认收货、互评，支持退款请求。

### Story 4.1: 下单创建订单

As a 买家,
I want 在订单确认页确认后创建订单,
So that 发起一笔交易。

**Acceptance Criteria:**

**Given** 已登录买家查看已上架商品
**When** 点「立即购买」、填写可选留言并确认
**Then** 创建 `Order` 且 `status='待支付'`
**And** 留言可为空

**依赖架构:** AD-2（ORM）、AD-5（状态机）。**需求:** FR-17。

### Story 4.2: 模拟支付

As a 买家,
I want 点「模拟支付」使订单进入「已支付/待交付」,
So that 完成支付环节（不接真实支付）。

**Acceptance Criteria:**

**Given** 订单 `status='待支付'`
**When** 点「模拟支付」
**Then** 在单个数据库事务内订单 `status` 变为「已支付/待交付」
**And** 不调用任何外部支付网关

**依赖架构:** AD-6（模拟支付单事务）、AD-5。**需求:** FR-18。

### Story 4.3: 下单后展示联系方式

As a 买家,
I want 支付成功后看到卖家 QQ/微信 + 认证状态,
So that 联系卖家约定当面交付。

**Acceptance Criteria:**

**Given** 订单 `status='待支付'`（或下单前）
**When** 查看订单/详情
**Then** 不展示卖家 QQ/微信
**And** 订单为「已支付/待交付」及之后时，展示卖家 QQ/微信 + 认证状态

**依赖架构:** NFR-4（隐私）。**需求:** FR-19。

### Story 4.4: 订单状态机

As a 平台,
I want 订单状态仅沿合法状态机流转,
So that 杜绝非法跳转（跳过支付直接确认收货、收货后再退款）。

**Acceptance Criteria:**

**Given** 订单处于任意状态
**When** 尝试非法跳转（如「待支付」直接「确认收货」）
**Then** 被拒绝（模型方法抛错/返回非法）
**And** 状态枚举与合法转移表在 `orders` models 层唯一定义，视图不得直接改 `status` 字段
**And** 状态沿 FR-20 正常路径（待支付→已支付待交付→已确认收货→已完成→已互评）与退款分支（→退款成功/退款失败）流转

**依赖架构:** AD-5（状态机 models 层）。**需求:** FR-20。

### Story 4.5: 订单列表

As a 用户,
I want 查看「我的订单」/「售出订单」,
So that 掌握交易进度。

**Acceptance Criteria:**

**Given** 已登录买家或卖家
**When** 访问「我的订单」/「售出订单」
**Then** 列表展示各订单当前状态与关键信息，且仅本人数据

**依赖架构:** AD-4。**需求:** FR-21。

### Story 4.6: 确认收货

As a 买家,
I want 当面拿到货后点「确认收货」,
So that 订单进入「已确认收货」并转入评价，且不可再退款。

**Acceptance Criteria:**

**Given** 订单 `status='已支付/待交付'`
**When** 点「确认收货」
**Then** 订单 `status` →「已确认收货」并自动标记「已完成」
**And** 退款入口不可用

**依赖架构:** AD-5（`confirm_receipt()`）。**需求:** FR-22。

### Story 4.7: 互评

As a 买卖双方,
I want 对本次交易互相评价,
So that 完成交易闭环并沉淀信用。

**Acceptance Criteria:**

**Given** 订单 `status='已完成'`
**When** 双方各自提交评价
**Then** 双方均提交后订单 `status` →「已互评」

**依赖架构:** AD-5。**需求:** FR-23。

### Story 4.8: 退款请求

As a 买家,
I want 在「已支付/待交付」阶段提交退款请求+原因,
So that 货不对板/质量问题时转入纠纷等待裁决。

**Acceptance Criteria:**

**Given** 订单 `status='已支付/待交付'`
**When** 提交退款请求 + 原因
**Then** 订单 `status` →「纠纷」，等待管理员裁决
**And** 「待支付」「已确认收货」状态不可发起退款

**依赖架构:** AD-5（`request_refund()`）。**需求:** FR-24。

---

## Epic 5: 管理员后台（`dashboard`）

**Epic goal:** 管理员审核/下架商品、裁决纠纷、管理用户、查看数据看板。

### Story 5.1: 待审核区（通过/驳回）

As a 管理员,
I want 在待审核区通过或驳回商品,
So that 上架合规商品、拦截违规商品。

**Acceptance Criteria:**

**Given** 管理员登录后台并进入待审核区
**When** 查看待审核商品并点「通过」
**Then** 商品 `status` → `'approved'`（上架）
**And** 点「驳回」并填理由时，商品 `status` → `'rejected'` 且理由通知卖家（FR-7）

**依赖架构:** AD-4（仅 admin 可入）、AD-9。**需求:** FR-25。

### Story 5.2: 下架违规商品

As a 管理员,
I want 下架已上架违规商品,
So that 违规内容不再对外可见。

**Acceptance Criteria:**

**Given** 一件已上架违规商品
**When** 管理员点「下架」
**Then** 商品 `status` → `'offline'`，不再对外可见
**And** 卖家「我的消息」收到「商品违规已下架」通知

**依赖架构:** AD-4、AD-9。**需求:** FR-26。

### Story 5.3: 纠纷裁决

As a 管理员,
I want 查看退款请求并裁决同意/不同意,
So that 了结纠纷。

**Acceptance Criteria:**

**Given** 订单 `status='纠纷'`
**When** 管理员同意退款
**Then** 订单 `status` →「退款成功」并通知用户
**And** 不同意退款时，订单 `status` →「退款失败」并通知用户

**依赖架构:** AD-4、AD-5（`resolve_refund()`）。**需求:** FR-27。

### Story 5.4: 用户管理（认证核实/封禁）

As a 管理员,
I want 核实认证用户、封禁违规用户,
So that 维护用户可信度与秩序。

**Acceptance Criteria:**

**Given** 管理员查看用户列表
**When** 对「待认证」账号执行核实通过
**Then** 账号 `is_verified=True`（FR-3）
**And** 封禁违规用户时，该账号无法登录/发布

**依赖架构:** AD-3（认证位）、AD-4。**需求:** FR-28。

### Story 5.5: 数据看板

As a 管理员,
I want 查看用户数/发布数/成交数/纠纷数统计,
So that 掌握平台运营状况。

**Acceptance Criteria:**

**Given** 管理员访问看板
**When** 查询统计
**Then** 展示用户数、发布数、成交数、纠纷数四个指标
**And** 数值与后台数据一致（聚合查询）

**依赖架构:** AD-2（ORM 聚合）。**需求:** FR-29。
