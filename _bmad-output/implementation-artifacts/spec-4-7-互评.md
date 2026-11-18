---
title: '互评'
type: 'feature'
created: '2026-11-18'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '120108233f69f4c2d0ca5764279e4677b1a708cc'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 订单在「已完成」后没有评价入口，买卖双方无法对本次交易互评，交易闭环缺少最后一环，也无法沉淀信用。

**Approach:** 在 `orders` app 增加挂在订单上的评价记录，买卖双方各自提交；只有双方都提交后，订单才经状态机 `mark_reviewed()` 从「已完成」流转为「已互评」。单方提交只落评价、不改订单状态。同时提供一个双方都能进入的评价页面，并把评价接入个人中心「我的评价」。

## Boundaries & Constraints

**Always:**
- 仅 `status='completed'`（已完成）可提交评价；单方提交不改订单状态，双方齐备才流转到 `reviewed`。
- 订单状态流转只经 `Order.mark_reviewed()`；视图/模板一律不直接写 `status` 字段。
- 评价人与被评人由登录用户与订单关系推导（买家↔卖家），不接受客户端传入的用户 ID。
- 只有订单当事人（buyer 或 `product.owner`）可访问/提交该订单的评价；无关用户 404。
- 每个订单、每个当事人最多一条评价；写操作需登录且仅 POST，校验与落库在同一事务内完成。

**Never:**
- 不改变支付、确认收货、退款已有的状态路径，不新增 `STATUS_CHOICES` 取值。
- 不接第三方、不做实时推送、不做移动端，沿用 Bootstrap 服务端渲染。
- 不实现管理员对评价的编辑/删除，不在本故事实现 4.8 退款请求。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 买家先评 | 已完成；buyer 提交合法评价 | 评价落库（评人为买家、被评人为卖家），订单仍「已完成」 | 提示等待对方评价 |
| 卖家后评致闭环 | 已完成；买家已评，seller 提交 | 评价落库，订单经 `mark_reviewed()` →「已互评」 | N/A |
| 卖家先评 / 买家后评 | 同上，顺序相反 | 结果对称一致，同样在第二条后闭环 | 提示等待对方评价 |
| 单方未齐 | 已完成；仅一方有评价 | 订单状态保持「已完成」 | 页面提示「等待对方评价」 |
| 状态不符 | 待支付/已支付/纠纷/已互评 提交 | 拒绝，不落评价、不改状态 | 中文错误提示，200 重渲染 |
| 重复提交 | 同一当事人再次提交 | 拒绝，不产生第二条评价 | 中文错误提示 |
| 越权访问 | 非当事人访问评价页/提交 | 404，不泄露订单是否存在 | 服务端过滤 |
| 未登录写操作 | 匿名 POST | 302 跳登录页（带 next） | `@login_required` |

## Decisions（已确认）

- **评价内容形态** = 仅纯文字评论：`Review` 用单个 `TextField` 存评价正文，不设评分字段。
- **个人中心「我的评价」** = 本故事接入，展示「我收到的评价」：按被评人为当前用户过滤。
- **规格篇幅** = 保留完整规格（约 1637 tokens，略超 1600 建议值），不拆分。

</frozen-after-approval>

## Code Map

- `orders/models.py` — `STATUS_CHOICES`（`completed`/`reviewed`）、`ALLOWED_TRANSITIONS`（`completed:('reviewed',)`）、`mark_reviewed()`（L97，已预留供 4.7）为唯一流转入口；新增 `Review` 模型，复用状态机，勿改既有枚举/转移表。
- `orders/forms.py` — `OrderCreateForm` 范式；新增评价表单（单个必填 `TextField` 评论正文）。
- `orders/views.py` — `order_pay`/`order_confirm_receipt`（`@login_required`+`@require_POST`+`transaction.atomic()`+`InvalidTransition`→200 重渲染带 `*_error`）为写入范式；`order_detail` L61 仅 buyer 可见，卖家无详情入口，故需新增买卖双方通用的评价视图。
- `orders/urls.py` — `/orders/<pk>/...` 命名范式，新增评价路由。
- `orders/migrations/0001_initial.py` — 当前仅此一个且与 models 一致；需新增 `0002`。
- `templates/orders/order_detail.html` — 状态徽章、`*_error` 警告、动作表单范式；加买家评价入口。
- `templates/orders/order_list.html` — `mode`=`buyer`/`seller` 分支；两个列表各加评价入口。
- `templates/orders/order_review.html` — 新建，双方通用的评价页（表单 + 已评价状态 + 等待提示）。
- `accounts/views.py` L129 `profile_view`、`templates/accounts/profile.html` L128–139「我的评价」空壳 — 展示接入点：按被评人为 `profile_user` 过滤收到的评价。
- `orders/tests.py` — `setUpTestData` 造 seller/buyer/other + Product，`_make_order(status)`、`_login` 范式；已有 `test_mark_reviewed_*`（L67/L131）可复用。
- `config/urls.py` — `orders` 挂载前缀 `/orders/`（无需改动）。

## Tasks & Acceptance

**Execution:**
- [x] `orders/models.py` -- 新增 `Review` 模型（order FK + reviewer FK + `content` 文本字段 + `unique_together(order,reviewer)` + 被评人/身份推导属性）并新增迁移 -- 评价挂订单、每人每单一条，状态流转仍复用 `mark_reviewed()`
- [x] `orders/forms.py` -- 新增评价表单（单个必填评论字段）并做服务端校验 -- 空白评价被拒
- [x] `orders/views.py` -- 新增双方通用的评价视图（GET 展示 / POST 事务提交，第二条触发 `mark_reviewed()`） -- 核心闭环，沿用既有写入范式
- [x] `orders/urls.py` -- 注册评价路由 -- 暴露入口
- [x] `templates/orders/order_review.html` -- 新建评价页 -- 双方提交界面与等待提示
- [x] `templates/orders/order_detail.html`、`templates/orders/order_list.html` -- 加评价入口链接 -- 从详情页/订单列表可达
- [x] `accounts/views.py`、`templates/accounts/profile.html` -- 接入「我的评价」展示收到的评价（被评人为当前用户） -- 填充 profile 占位
- [x] `orders/tests.py` -- 补状态机与视图测试（先/后评、单方不流转、状态不符、重复、越权、未登录） -- 覆盖 I/O 矩阵

**Acceptance Criteria:**
- Given 订单「已完成」且买家未评，when 买家提交合法评价，then 生成买家评价且订单仍「已完成」。
- Given 买家已评且订单「已完成」，when 卖家提交评价，then 生成卖家评价且订单变为「已互评」（顺序相反同样成立）。
- Given 只有一方评价，when 查看订单，then 状态仍「已完成」且提示等待对方评价。
- Given 非「已完成」状态或重复提交，when 提交评价，then 拒绝且不落库、不改状态。
- Given 非当事人或未登录，when 访问/提交评价，then 分别 404 / 302 登录页。

## Implementation Notes

- 实现子代理完成全部 8 项 Execution 任务；主代理逐行审阅从 `baseline_commit` 生成的完整 diff（含新增文件），确认与规格一致。
- `Review` 模型：`order`/`reviewer` 双 FK + `content`（TextField）+ `created_at`，`unique_together(order, reviewer)` 作 DB 兜底；`reviewee`、`reviewer_is_buyer` 为推导属性，不落库。新增迁移 `0002_review.py`。
- `order_review` 视图：`@login_required` + `@require_http_methods(['GET','HEAD','POST'])`，`Q(buyer) | Q(product__owner)` 作当事人过滤；事务内 `select_for_update()` 锁单 + 状态/重复校验 + 建评价，第二条经 `mark_reviewed()` 闭环；拒绝走 form 非字段错误 200 重渲染。
- 身份与评价对象完全由登录用户推导，忽略客户端伪造的 `reviewer`/`order`/`status`（有专门测试）。
- 个人中心用 `Q(order__buyer=user, reviewer=F('order__product__owner')) | Q(order__product__owner=user, reviewer=F('order__buyer'))` 推导「我收到的评价」。
- **验证环境**：本地 `python` 无 Django，改用 `uv run`（Django 5.2.19）。`makemigrations --check --dry-run orders` 无变更；`manage.py check` 0 issues；`manage.py test orders` 97 通过（其中 `OrderReviewTests` 16 条详细模式逐条 ok，覆盖 I/O 矩阵全部 8 行）；`manage.py test accounts` 62 通过无回归。
- **已知风险**：`select_for_update()` 在 SQLite 上是 no-op，并发依赖 `unique_together` 与状态机条件更新兜底，未做多线程并发验证；`unique_together` 在 Django 5.x 已 deprecated（仍可用），未来升级可换 `UniqueConstraint`。

### 审查修复（step-04 patch）

- 三层审查（盲审/边界/验证缺口）共 14 条候选，逐条验证后 3 条归为 `patch` 并修复：
  1. `orders/views.py` — `order_review` 补捕获 `IntegrityError`（并发重复提交触发 `unique_together`），按 `REVIEW_DUPLICATE_ERROR` 中文提示 200 重渲染，避免 500。
  2. `templates/accounts/profile.html` — 空状态文案改为「暂无评价记录，你还没有收到任何评价」，与「收到的评价」口径一致。
  3. `orders/tests.py` — 新增 `test_both_reviewed_get_shows_banner_and_other_review`，覆盖双方齐备后 GET 评价页的闭环横幅与对方评价正文（原删除该上下文全套测试仍绿）。
- 其余发现经核对为 false / low（外观性、需额外复杂度）/ maybe-false（既有数据模型，延后），详见 Review Triage Log。
- 修复后验证：`makemigrations --check` 无变更；`check` 0 issues；`test orders` 98 通过、`test accounts` 62 通过。

## Spec Change Log

<!-- Append-only. Empty until first review loopback. -->

## Review Triage Log

- **false** — spec 为 `in-review` 而 sprint 仍 `in-progress`：审查阶段不要求同步 sprint，收尾步骤统一置 `done`，非代码缺陷。
- **low（拒）** — Verification 段写 `python manage.py` 而需 `uv run`：属 spec 文档，Implementation Notes 已记录环境；修复需改 spec，按规则拒绝。
- **low（拒）** — `ReviewForm.content` 无 `max_length`：用户日常不提交超大文本，加长度参数属额外复杂度，非必要。
- **medium** — 双方评价齐备后 GET 评价页的「对方评价」正文与「已互评」闭环横幅无测试覆盖：逐条核对 16 条用例，GET 用例分别为 1 条/0 条评价；删除 `other_review` 上下文全套测试仍绿。验证层已预验证。→ 与验证缺口层发现合并为一组。
- **maybe-false（延后）** — `Review.order/reviewer` 为 CASCADE，删除用户后订单停在 `reviewed` 却不足两条评价：既有数据模型设计使然，需产品层决定删除用户时如何处理历史评价。
- **low（拒）** — 个人中心 `my_reviews` 无分页/切片：评价数受本人订单数约束，不会无界增长，加分页属额外复杂度。
- **low** — 个人中心空状态文案「你还没有任何评价」与「收到的评价」口径不符：真实文案错误，修复为直接替换文案。
- **low（拒）** — 评价页状态徽章硬编码 `bg-warning`：`reviewed` 显示警告色属外观问题，修复需加模板分支。
- **low（拒）** — 入口链接一律显示「去评价」不区分已评：外观性，修复需加模板条件分支。
- **low（拒）** — 评价页返回链接固定 `my_orders`，卖家从 `sold_orders` 进入后返回错位：外观性，修复需加角色判断分支。
- **false** — HEAD 无专门测试：`@require_http_methods(['GET','HEAD','POST'])` 放行 GET 时 Django 自动放行 HEAD 并走同一渲染分支，非缺陷。
- **medium** — 并发重复提交：SQLite 下 `select_for_update()` 为 no-op，`exists()` 检查与 `create()` 竞态时 `unique_together` 抛 `IntegrityError`，而 views.py:203 仅捕获 `InvalidTransition`，将返回 500 而非中文重复提示。数据完整性由唯一约束兜底，故定为 medium。
- **low（拒）** — `ReviewForm.content` 无 `max_length`（边界层重复发现）：同前，拒绝。
- **medium** — 闭环成功态展示无测试（验证缺口层发现）：与前述“双方评价齐备后 GET 无测试”同根因，合并为一组。

## Verification

**Commands:**
- `python manage.py makemigrations --check --dry-run orders` -- expected: 无待生成迁移（模型与迁移一致）
- `python manage.py test orders` -- expected: 全部通过
- `python manage.py check` -- expected: 无报错
