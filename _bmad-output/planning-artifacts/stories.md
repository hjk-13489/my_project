---
title: 校园二手书/闲置物品交易系统 — 故事清单
status: final
created: 2026-11-05
sources:
  - _bmad-output/planning-artifacts/prds/prd-my_project-2026-11-04/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-my_project-2026-11-05/architecture.md
stories_count: 30
epics_count: 5
---

# 故事清单（Stories）

> 5 个史诗、30 个故事（≥12）。每个故事的验收标准均为 **Given/When/Then**，并附一条 **「测试断言」**（可直接翻译为 `pytest`/`Django TestCase` 断言）。每个故事标注其依赖的 **架构不变量（AD）** 与 **功能需求（FR）**。

---

## Epic 1：用户账号与身份认证（`accounts`）

### 1.1 项目脚手架（Django 分层单体初始化）

- **用户故事**：作为开发团队，我想要初始化 Django 分层单体骨架，以便后续所有故事在同一可部署单元上构建。
- **验收标准**：
  - Given 全新空仓库，When 执行脚手架初始化并 `migrate`/`check`，Then 生成 5 个 app 与 `config` 包，`check` 无错误。
  - And `INSTALLED_APPS` 含 5 个 app，`USE_TZ=True`，SQLite 迁移可生成。
  - And `requirements.txt` 锁定 Django 5.2 LTS / Pillow 13.0 / Bootstrap 5.3。
- **测试断言**：`assert set(['accounts','listings','chat','orders','dashboard']).issubset(settings.INSTALLED_APPS) and settings.USE_TZ is True`
- **依赖**：AD-1、AD-2、AD-10；无 FR（结构种子）。

### 1.2 用户注册

- **用户故事**：作为学生，我想用学号+密码+昵称注册，以便获得「待认证」账号。
- **验收标准**：
  - Given 注册表单，When 提交学号/密码/昵称，Then 创建 `User` 且 `is_verified=False`、`role='student'`。
  - And 重复学号被拒绝；密码 < 6 位被拒绝。
- **测试断言**：`assert User.objects.get(student_id=sid).is_verified is False`
- **依赖**：AD-3；FR-1。

### 1.3 登录与登出

- **用户故事**：作为学生，我想用学号+密码登录并登出，以便以本人身份访问平台。
- **验收标准**：
  - Given 已注册账号，When 正确凭据登录，Then 建立 Session 并跳转首页；错误凭据提示「学号或密码错误」。
  - And 登出清除 Session；未登录访问受限页跳转登录页（302）。
- **测试断言**：`assert response.status_code == 302 and response.url.startswith('/login')`（未登录访问受限页）
- **依赖**：AD-3、AD-4；FR-2。

### 1.4 学号身份认证（用户提交）

- **用户故事**：作为学生，我想提交学号+姓名等待认证，以便标记「已认证」并展示可信身份。
- **验收标准**：
  - Given 待认证账号，When 提交学号+姓名，Then `is_verified` 仍为 `False`，用户侧不显示「已认证」。
  - And `is_verified=True` 时商品详情页/联系方式旁显示「已认证」标识。
- **测试断言**：`assert user.is_verified is False`（提交后、审核前）
- **依赖**：AD-3；FR-3。

### 1.5 个人中心

- **用户故事**：作为学生，我想在个人中心查看本人发布/订单/消息/评价，以便管理本人数据。
- **验收标准**：
  - Given 已登录用户，When 访问个人中心各入口，Then 仅返回本人数据。
- **测试断言**：`assert set(view.qs.values_list('owner', flat=True)) == {request.user.pk}`
- **依赖**：AD-4；FR-4。

---

## Epic 2：商品发布与浏览（`listings`）

### 2.1 发布商品（含图片上传）

- **用户故事**：作为卖家，我想填写字段并上传图片发布，以便闲置进入审核。
- **验收标准**：
  - Given 已认证卖家，When 填齐字段并传 ≥1 图提交，Then 创建 `Product` 且 `status='pending'`。
  - And 必填缺失不可提交；价格非数字或 ≤0 被拒绝。
  - And 分类仅「教材/日用品/电子数码/其他」；成色仅「全新/良好/中等」。
  - And 图片仅 JPEG/PNG、单图 ≤5MB，存本地 `media/`。
- **测试断言**：`assert Product.objects.get(id=pid).status == 'pending'`
- **依赖**：AD-8、AD-9；FR-5。

### 2.2 商品状态流转：待审核→上架/驳回

- **用户故事**：作为平台，我想商品待审核时不可见、审核通过才上架，以便拦截违规商品。
- **验收标准**：
  - Given `status='pending'`，When 普通用户浏览/搜索，Then 查询不到该商品（强制过滤 `approved`）。
  - And 审核通过后 `status='approved'` 可被命中。
- **测试断言**：`assert Product.objects.visible().filter(id=pid).count() == 0`（pending 时）
- **依赖**：AD-9；FR-6。

### 2.3 驳回通知与重新提交

- **用户故事**：作为卖家，我想收到驳回理由并可修改重提，以便商品再进入审核。
- **验收标准**：
  - Given 商品 `status='rejected'`，When 查看「我的消息」，Then 显示驳回理由。
  - And 修改重提后 `status` 回到 `'pending'`。
- **测试断言**：`assert product.status == 'rejected'`（驳回后）
- **依赖**：AD-9；FR-7。

### 2.4 查看我的发布

- **用户故事**：作为卖家，我想查看我的发布列表及各状态，以便掌握进度。
- **验收标准**：
  - Given 已登录卖家，When 访问「我的发布」，Then 展示各商品状态，仅本人数据。
- **测试断言**：`assert product.status in {'pending','approved','offline','rejected'}`
- **依赖**：AD-9、AD-4；FR-8。

### 2.5 商品列表浏览（仅上架）

- **用户故事**：作为买家，我想浏览已上架商品列表，以便看到可购买的闲置。
- **验收标准**：
  - Given 多件商品，When 访问列表页，Then 仅展示 `status='approved'`，含缩略图/标题/价格/成色。
  - And 响应 ≤1s（NFR-1）。
- **测试断言**：`assert all(p.status == 'approved' for p in listed_products)`
- **依赖**：AD-9、NFR-1；FR-9。

### 2.6 关键词搜索

- **用户故事**：作为买家，我想按关键词搜索，以便找到想要的商品。
- **验收标准**：
  - Given 已上架商品，When 输入关键词，Then 返回标题或描述匹配且 `approved` 的商品。
- **测试断言**：`assert all(kw in (p.title + p.description) for p in results)`
- **依赖**：AD-9、AD-2；FR-10。

### 2.7 分类/价格/成色筛选

- **用户故事**：作为买家，我想组合筛选分类/价格/成色，以便缩小范围。
- **验收标准**：
  - Given 已上架商品，When 组合筛选，Then 结果仅含满足全部条件的商品。
- **测试断言**：`assert all(p.category == c and lo <= p.price <= hi and p.condition == cond for p in results)`
- **依赖**：AD-9、AD-2；FR-11。

### 2.8 商品详情页

- **用户故事**：作为买家，我想查看详情页全信息与操作入口，以便决定联系/购买。
- **验收标准**：
  - Given 已上架商品，When 访问详情页，Then 展示全部图片/字段/卖家昵称+认证状态。
  - And 「联系卖家」→聊天（FR-13）、「立即购买」→下单（FR-17）。
  - And 待审核/驳回/下架商品详情页返回 404。
- **测试断言**：`assert response.status_code == 200 and seller_verified_badge_present`（approved）
- **依赖**：AD-9、AD-4；FR-12。

---

## Epic 3：站内聊天（`chat`）

### 3.1 买家发起聊天

- **用户故事**：作为买家，我想点「联系卖家」发文字，以便下单前协商。
- **验收标准**：
  - Given 已登录买家查看已上架商品，When 发文字消息，Then 消息关联商品+卖家，下单前可发。
- **测试断言**：`assert Message.objects.filter(product=pid, sender=buyer, receiver=seller).exists()`
- **依赖**：AD-7；FR-13。

### 3.2 卖家查看与回复

- **用户故事**：作为卖家，我想在「我的消息」查看并回复，以便完成协商。
- **验收标准**：
  - Given 卖家收到消息，When 打开「我的消息」，Then 列出对话并可回复文字。
- **测试断言**：`assert Message.objects.filter(receiver=seller).count() >= 1`
- **依赖**：AD-7；FR-14。

### 3.3 纯文字消息 + 轮询刷新

- **用户故事**：作为用户，我想聊天仅纯文字并轮询刷新，以便简化实现跑通协商。
- **验收标准**：
  - Given 聊天窗口，When 发图片/富文本，Then 被拒绝或按纯文本处理。
  - And 消息仅文字，新消息在刷新/轮询（约 5s）后可见，无 WebSocket。
- **测试断言**：`assert message.body == plain_text_stripped`（富文本被剥离）
- **依赖**：AD-7；FR-15。

### 3.4 未读提示

- **用户故事**：作为用户，我想「我的消息」显示未读数并查看后清零，以便不漏消息。
- **验收标准**：
  - Given 收到新消息，When 查看入口，Then 显示未读数；查看后清零。
- **测试断言**：`assert unread_count(user) == 0`（查看后）
- **依赖**：AD-7；FR-16。

---

## Epic 4：交易订单与评价（`orders`）

### 4.1 下单创建订单

- **用户故事**：作为买家，我想确认订单后创建订单，以便发起交易。
- **验收标准**：
  - Given 已登录买家查看已上架商品，When 点「立即购买」确认，Then 创建 `Order` 且 `status='待支付'`；留言可为空。
- **测试断言**：`assert order.status == '待支付'`
- **依赖**：AD-2、AD-5；FR-17。

### 4.2 模拟支付

- **用户故事**：作为买家，我想点「模拟支付」使订单进入「已支付/待交付」，以便完成支付。
- **验收标准**：
  - Given `status='待支付'`，When 点「模拟支付」，Then 单事务内 `status` →「已支付/待交付」，不调外部网关。
- **测试断言**：`assert order.status == '已支付/待交付'`
- **依赖**：AD-6、AD-5；FR-18。

### 4.3 下单后展示联系方式

- **用户故事**：作为买家，我想支付成功后看到卖家联系方式，以便约定交付。
- **验收标准**：
  - Given `status='待支付'`，When 查看订单/详情，Then 不展示卖家 QQ/微信。
  - And 「已支付/待交付」及之后展示卖家 QQ/微信 + 认证状态。
- **测试断言**：`assert seller_contact_visible(order) == (order.status != '待支付')`
- **依赖**：NFR-4；FR-19。

### 4.4 订单状态机

- **用户故事**：作为平台，我想订单仅沿合法状态机流转，以便杜绝非法跳转。
- **验收标准**：
  - Given 任意状态，When 尝试非法跳转（待支付→确认收货），Then 被拒绝。
  - And 状态机在 models 层唯一定义，视图不得直接改 `status`。
  - And 沿正常路径与退款分支合法流转。
- **测试断言**：`with pytest.raises(InvalidTransition): order.confirm_receipt()`（待支付时）
- **依赖**：AD-5；FR-20。

### 4.5 订单列表

- **用户故事**：作为用户，我想查看我的订单/售出订单，以便掌握进度。
- **验收标准**：
  - Given 已登录，When 访问订单列表，Then 展示各订单状态，仅本人数据。
- **测试断言**：`assert set(orders.values_list('buyer', flat=True)) <= {request.user.pk}`
- **依赖**：AD-4；FR-21。

### 4.6 确认收货

- **用户故事**：作为买家，我想确认收货，以便订单转入评价且不可退款。
- **验收标准**：
  - Given `status='已支付/待交付'`，When 点「确认收货」，Then `status` →「已确认收货」并自动「已完成」，退款入口不可用。
- **测试断言**：`assert order.status == '已完成'`
- **依赖**：AD-5（`confirm_receipt()`）；FR-22。

### 4.7 互评

- **用户故事**：作为买卖双方，我想互相评价，以便完成闭环沉淀信用。
- **验收标准**：
  - Given `status='已完成'`，When 双方提交评价，Then `status` →「已互评」。
- **测试断言**：`assert order.status == '已互评'`
- **依赖**：AD-5；FR-23。

### 4.8 退款请求

- **用户故事**：作为买家，我想在「已支付/待交付」提交退款请求，以便转入纠纷。
- **验收标准**：
  - Given `status='已支付/待交付'`，When 提交退款请求+原因，Then `status` →「纠纷」。
  - And 「待支付」「已确认收货」不可发起退款。
- **测试断言**：`assert order.status == '纠纷'`
- **依赖**：AD-5（`request_refund()`）；FR-24。

---

## Epic 5：管理员后台（`dashboard`）

### 5.1 待审核区（通过/驳回）

- **用户故事**：作为管理员，我想在待审核区通过/驳回商品，以便上架合规、拦截违规。
- **验收标准**：
  - Given 待审核商品，When 点「通过」，Then `status` → `'approved'`；点「驳回」填理由，Then `status` → `'rejected'` 并通知卖家。
- **测试断言**：`assert product.status == 'approved'`（通过后）
- **依赖**：AD-4、AD-9；FR-25。

### 5.2 下架违规商品

- **用户故事**：作为管理员，我想下架违规商品，以便违规内容不再可见。
- **验收标准**：
  - Given 已上架商品，When 点「下架」，Then `status` → `'offline'` 且卖家收到通知。
- **测试断言**：`assert product.status == 'offline'`
- **依赖**：AD-4、AD-9；FR-26。

### 5.3 纠纷裁决

- **用户故事**：作为管理员，我想裁决退款请求，以便了结纠纷。
- **验收标准**：
  - Given `status='纠纷'`，When 同意退款，Then `status` →「退款成功」并通知；不同意 →「退款失败」并通知。
- **测试断言**：`assert order.status in {'退款成功', '退款失败'}`
- **依赖**：AD-4、AD-5（`resolve_refund()`）；FR-27。

### 5.4 用户管理（认证核实/封禁）

- **用户故事**：作为管理员，我想核实认证、封禁用户，以便维护秩序。
- **验收标准**：
  - Given 待认证账号，When 核实通过，Then `is_verified=True`；封禁后无法登录/发布。
- **测试断言**：`assert user.is_verified is True`（核实通过后）
- **依赖**：AD-3、AD-4；FR-28。

### 5.5 数据看板

- **用户故事**：作为管理员，我想查看四类统计，以便掌握运营状况。
- **验收标准**：
  - Given 后台数据，When 查询看板，Then 展示用户数/发布数/成交数/纠纷数，数值与数据一致。
- **测试断言**：`assert dashboard.user_count == User.objects.count()`
- **依赖**：AD-2；FR-29。
