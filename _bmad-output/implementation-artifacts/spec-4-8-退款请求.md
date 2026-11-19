---
title: '退款请求'
type: 'feature'
created: '2026-11-19'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: []
baseline_commit: 82fa9d8f30bdcb7e951c094105f2009efec4ee53
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 4.1–4.7 已跑通下单→支付→交付→确认→互评主干，模型层 `Order.request_refund()`（paid→dispute）在 4.4 已就位且 docstring 明确为 4.8 预留原因实体，但 buyer 在「已支付/待交付」阶段没有任何提交退款的入口，也没有落库原因的地方——FR-24 要求货不对板时提交退款请求+原因转入「纠纷」等待裁决，该分支目前完全不可达。

**Approach:** 在 `orders` app 新增 `RefundRequest` 实体（挂订单、存原因）与迁移、`RefundRequestForm`（原因必填）、一个仅 buyer、仅 `paid` 可提交的视图（同事务落原因并调用既有 `order.request_refund()` 完成 paid→dispute）、一条 URL。**入口形态经确认采用独立退款页**（仿 4.7 评价页）：详情页 `paid` 时放「申请退款」链接，新增 `order_refund.html`（GET 展示原因表单、POST 提交）承载 textarea 与校验。不改冻结的状态机、不实现管理员裁决（Epic 5）、不改 4.1–4.7 既有行为。

## Boundaries & Constraints

**Always:**
- 视图 `@login_required` 最外层 + `@require_http_methods(['GET','HEAD','POST'])`（GET 展示表单、POST 提交，其余方法 405）；仅 buyer 本人可进入/提交：`get_object_or_404(Order, pk=pk, buyer=request.user)`，他人/不存在订单 404。
- 原因必填且服务端校验：经 `RefundRequestForm` 拒绝空/纯空白原因，返回表单错误，无状态变化、无记录落库。
- 状态流转只经既有 `order.request_refund()`，且在 `transaction.atomic()` 内完成「校验 + 落 `RefundRequest` + 流转」；视图不得直接写 `order.status`，不得改冻结的模型层方法/转移表。
- `RefundRequest` 记录（order 外键 + reason）与状态流转同事务，任一步失败整体回滚，不留孤立原因记录。
- 仅 `paid` 可发起：`pending_payment`/`received`/`completed`/`reviewed`/`dispute`/`refunded`/`refund_failed` 一律拒绝，中文提示、状态与记录不变；非法流转（`InvalidTransition`，含并发陈旧实例）按同一拒绝路径处理，先 `refresh_from_db()` 再渲染，徽章反映库内真实状态。
- 成功后 `redirect('order_detail', pk=pk)`（PRG），最终状态 `dispute`；`received` 中间态不涉及本故事。
- 退款入口（详情页链接）仅在 `order.status == 'paid'` 时呈现；独立退款页仅对 `paid` 订单渲染可提交表单，非 `paid` 订单 GET 只显示拒绝提示、POST 拒绝；确认收货后（completed）及一切其它状态均不可见/不可用。

**Never:**
- 不改 `orders/models.py` 中冻结的状态机（`STATUS_CHOICES`/`ALLOWED_TRANSITIONS`/`_transition()`/`request_refund()`/`resolve_refund()`）——仅在其后**新增** `RefundRequest` 模型类。
- 不改 4.1–4.7 既有视图/模板行为（支付、联系方式门控、订单列表、确认收货、互评），不在列表页加退款按钮。
- 不实现管理员裁决界面或调用 `resolve_refund()`（Epic 5 / 5.3），不实现通知（5.x）；仅把原因落库供后续裁决读取。
- 不引入新依赖、不做 AJAX/SPA、不新增 admin 注册、不接受客户端传入的状态或买家身份字段。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望行为 | 错误处理 |
|------|------------|----------|----------|
| 正常退款 | buyer 登录，订单 `paid`，提交合法原因 | 302 回详情；库内 status=`dispute`；`RefundRequest` 落库含原因与所属订单 | N/A |
| 原因必填 | 提交空/纯空白原因 | 200 重渲染带表单错误；status 与记录不变 | `RefundRequestForm` 校验失败 |
| 入口可见性 | 详情为 `paid` | 详情页显示「申请退款」链接；其余 7 种状态均不显示 | N/A |
| 独立页 GET | buyer 对 `paid` 订单 GET 退款页 | 200 展示含原因 textarea 的空表单 | N/A |
| GET 非 paid | buyer 对非 `paid` 订单 GET 退款页 | 200 仅显示拒绝提示，无可提交表单 | N/A |
| 非安全方法 | 已登录 PUT/DELETE 退款页 | 405，无状态变化 | `require_http_methods` |
| 待支付退款 | 对 `pending_payment` 提交 | 200 拒绝 + 中文提示；状态/记录不变 | 视图状态前置校验 |
| 已收货/已完成/纠纷等退款 | 对 `received`/`completed`/`reviewed`/`dispute`/`refunded`/`refund_failed` 提交 | 200 拒绝 + 中文提示；状态/记录不变 | 视图校验 + `InvalidTransition` |
| 未登录 | 匿名访问退款入口/提交 | 302 到登录页并带 `next` | N/A |
| 他人订单 / 不存在订单 | 非 buyer 或对不存在 pk 提交 | 404；无状态变化 | `get_object_or_404` |
| 伪造字段 | 提交携带伪造 `status`/`buyer` | 字段被忽略，仅依状态机流转 | N/A |
| 并发重复提交 | 同一订单连续/并发两次提交 | 仅一次成功落 `dispute`，另一次 200 拒绝且不产生第二条记录 | 事务 + `_transition()` 条件更新 |

</frozen-after-approval>

## Code Map

- `orders/models.py:6-8` — `InvalidTransition`（继承 Exception）；视图据此捕获拒绝。
- `orders/models.py:13-34` — 8 值 `STATUS_CHOICES` 与 `ALLOWED_TRANSITIONS`；退款唯一出边为 `paid: ('received', 'dispute')`，`dispute` 无回退边；**冻结勿改**。
- `orders/models.py:80-85` — `Order.request_refund()`：无参数，`self._transition('dispute')`，docstring 明确原因字段由 4.8 的 RefundRequest 承载；视图直接调用，**勿改方法本体**。
- `orders/models.py:101-125` — `_transition()`：`atomic()` 内 `filter(pk=self.pk, status=self.status).update(...)`，命中 0 行或非法目标抛 `InvalidTransition`；并发重复提交的第二笔由它拒绝；**冻结勿改**。
- `orders/models.py:128-164` — `Review` 模型是新 `RefundRequest` 的形状范式：order FK（`related_name`, CASCADE）、`created_at=auto_now_add`、`Meta ordering`、`__str__`。新增类追加在文件末尾，改 `Order`/`Review` 之外。
- `orders/forms.py:22-35` — `ReviewForm`（`CharField`+`Textarea`、`error_messages={'required': ...}`）是 `RefundRequestForm(reason)` 的直接范式。
- `orders/views.py:1-10` — 已 import `transaction`、`get_object_or_404`、`InvalidTransition`、`redirect`、`render`、`login_required`、`require_POST` 及 `Q`/`require_http_methods`；新增视图需 import `RefundRequestForm`、`RefundRequest`（方案 B 沿用已导入的 `require_http_methods`）。
- `orders/views.py:66-74` — `order_detail`：`get_object_or_404(Order, pk=pk, buyer=request.user)`，退款视图沿用同一 buyer 过滤。
- `orders/views.py:157-228` — `order_review`（**方案 B 直接范式**）：`@login_required`+`@require_http_methods(['GET','HEAD','POST'])`、GET 空表单/POST `form.is_valid()`、事务内 `select_for_update()` 取单 + `form.add_error(None, ...)`、成功 PRG、失败 `refresh_from_db()` 后 200 重渲染；退款视图照此，把 `Review`/`ReviewForm` 换成 `RefundRequest`/`RefundRequestForm`，`mark_reviewed()` 换成 `request_refund()`，并在 `form.is_valid()` 后、事务内先校验 `locked.status == 'paid'` 再落库+流转。
- `orders/views.py:76-96` — `order_pay`：`atomic()` 内取单+流转、`except InvalidTransition` 的处理是并发拒绝的补充范式（退款视图可复用其拒绝提示结构，但错误经 `form.add_error` 回到退款页表单）。
- `orders/urls.py:5-15` — 静态路由 mine/sold 须在 `<int:pk>/` 之前；新增带 pk 的两段路由（如 `<int:pk>/refund/`）放在 pay/confirm-receipt 附近，不会被单段 `<int:pk>/` 吞掉。
- `templates/orders/order_detail.html:59-66` — `paid` 区块现有「确认收货」POST 表单；在其后追加一个指向 `order_refund` 的「申请退款」链接（仅 `paid` 显示），不改动收货表单本身；`:15` 状态徽章与 `:20-40` 联系方式门控**勿改**。
- `templates/orders/order_review.html:27-58`（**方案 B 退款模板直接范式**）— 新建 `templates/orders/order_refund.html`：仿其卡片页头 + `form.non_field_errors`/字段错误 `alert-danger` + `form.reason` textarea + 提交按钮；非 `paid` 时改渲染拒绝提示、不渲染表单。
- `orders/migrations/` — 现有 `0001_initial`/`0002_review`；用 `makemigrations orders` 生成 `0003_refundrequest` 并应用（测试跑真实 schema）。
- `orders/tests.py:18-224` — `OrderStateMachineTests` 已覆盖 `request_refund` 的模型层拒绝路径（含 `test_request_refund_after_receipt_rejected`/`test_request_refund_when_pending_payment_rejected`/陈旧实例/终态）；**本故事不重复测模型流转**。
- `orders/tests.py:460-696` / `:697-921` / `:1395+` — `OrderPayViewTests`/`OrderConfirmReceiptViewTests`/`OrderReviewTests`：HTTP 层测试范式（登录用 `student_id`，成功断言 302+重读 status，非法断言 200+`alert-danger`+状态不变，陈旧用 `Order.objects.filter(...).update(...)`）；新建 `OrderRefundViewTests` 与 `RefundRequestModelTests` 覆盖 I/O 矩阵。

## Tasks & Acceptance

**Execution:**
- [x] `orders/models.py` — 末尾新增 `RefundRequest` 模型（order FK `related_name='refund_requests'`、reason `TextField`、created_at `auto_now_add`）— 提供原因落库实体，供 Epic 5 裁决读取。
- [x] `orders/migrations/0003_refundrequest.py` — `makemigrations` 生成并应用 — 让测试与演示跑真实 schema。
- [x] `orders/forms.py` — 新增 `RefundRequestForm`（reason 必填 + 中文 required 错误）— 服务端校验原因。
- [x] `orders/views.py` — 新增 `order_refund` 视图（`@login_required`+`@require_http_methods(['GET','HEAD','POST'])`、buyer 门控、GET 空表单/非 `paid` 拒绝提示、POST 在事务内 `select_for_update()` 校验 `paid` 后落 `RefundRequest` + `request_refund()`、`InvalidTransition`/校验失败 `form.add_error` 后 200 重渲染、成功 PRG）— 提供退款 HTTP 入口。
- [x] `orders/urls.py` — 新增 `<int:pk>/refund/` name=`order_refund`（置于静态路由之后、`<int:pk>/` 附近的带 pk 段）— 暴露端点。
- [x] `templates/orders/order_refund.html` + `templates/orders/order_detail.html` — 新建独立退款页（原因 textarea + 表单错误提示 + 非 `paid` 拒绝提示），详情页 `paid` 区块追加「申请退款」链接 — 提供买家可见入口。
- [x] `orders/tests.py` — 新增 `OrderRefundViewTests`（覆盖 I/O 矩阵）与 `RefundRequestModelTests`（落库字段/关系）— 证明流转、原因必填、状态门控、越权与方法/并发。

**Acceptance Criteria:**
- Given buyer 登录且订单为 `paid`，when 提交合法原因，then 302 回详情、库内 status=`dispute`、`RefundRequest` 含原因落库。
- Given 空/纯空白原因，when 提交，then 200 带表单错误、status 与记录不变。
- Given 订单详情为 `paid`，when 渲染，then 显示退款入口；其余任一状态时均不显示。
- Given 订单为 `pending_payment`/`received`/`completed`/`reviewed`/`dispute`/`refunded`/`refund_failed`，when 提交，then 200 中文拒绝、status 与记录不变。
- Given 匿名请求，when 访问退款入口或提交，then 302 到登录页并带 `next`。
- Given 已登录且非 buyer 或订单不存在，when 提交，then 404 且无状态变化。
- Given 提交伪造字段，when 提交，then 字段被忽略、仅依状态机流转。
- Given 本轮改动，when 跑全量测试，then 既有用例无回归、新增用例全绿。

## Implementation Notes

- 严格按方案 B（独立退款页）实现：`order_refund` 直接照搬 `order_review` 的 `@login_required` + `@require_http_methods(['GET','HEAD','POST'])` + GET/POST 分流 + `form.add_error` + 成功 PRG 范式；状态流转只经既有 `order.request_refund()`，事务内 `select_for_update()` + 落 `RefundRequest` + 流转，视图未直接写 `order.status`，未碰冻结的模型层方法/转移表。
- 并发/重复提交：事务内锁订单行 + `request_refund()` 的条件更新（`filter(pk, status=paid).update()` 命中 0 行抛 `InvalidTransition`），第二次提交整体回滚、不产生第二条原因记录；`test_double_submit_only_once` 与 `test_concurrent_stale_instance_rejected_visibly` 分别证明连续与陈旧实例两路拒绝。
- 实现期发现并处理：Django 5.2 未绑定表单无 `cleaned_data`，GET 非 `paid` 不能对空表单 `add_error`；改用独立 `refund_error` 上下文变量渲染拒绝提示，模板据 `can_refund` 决定是否渲染表单（已由 `test_get_non_paid_shows_rejection_without_form` 覆盖）。
- I/O 矩阵审计：12 行矩阵全部有覆盖用例且明确运行通过——正常/原因必填/入口可见性/GET paid/GET 非 paid/405/待支付拒绝/7 状态拒绝/匿名 302/越权与不存在 404/伪造字段/并发重复；新增 14 例（OrderRefundViewTests 12 + RefundRequestModelTests 2）逐条 `-v 2` 确认无 skip/filter。
- 主代理独立验证（仓库解释器 `.venv/Scripts/python.exe`）：`check` → no issues；`makemigrations --check --dry-run` → No changes detected；`test orders` → 112 例 OK；`test` 全量 → 336 例 OK，无失败/跳过、无回归。
- 未加 `RefundRequest.unique_together`（spec 未要求）：防重复依赖状态机条件更新而非数据库约束，符合冻结边界「不改模型层状态机」；管理员裁决与通知属 Epic 5，本故事仅落原因供后续读取。

## Spec Change Log

## Review Triage Log

三层审查（Blind Hunter 9 条 / Edge Case Hunter 2 条 / Verification Gap 0 条）。`review_loop_iteration` 保持 0：无 intent_gap、无 bad_spec、无 patch、无 defer。下列裁决均在忽略审查子代理自带严重度后、依据对代码与流程的独立核实作出。

| # | 层 | 发现 | 裁决 | 证据 / 路由 |
|---|----|------|------|------|
| 1 | BH | sprint-status 标 4-8 为 in-progress，与 spec 的 in-review 不一致 | `false` | 工作流中间态：step-03 设 in-progress、step-04 设 spec in-review、step-05 才把 story 同步为 review；与 4.6 审查 triage #2 同类，step-05 收敛。 |
| 2 | BH | `order_refund.html:14` 徽章写死 `bg-warning`，纠纷态仍黄色，误导 | `false` | 前提错误：`order_detail.html:15` 同样写死 `bg-warning text-dark`，详情页并无「按状态变色」；徽章**文字**经 `get_status_display` 反映库内真实状态，正是 spec「徽章反映库内真实状态」的要求；颜色为既有模板范式，纯外观无实际损害。 |
| 3 | BH | 并发陈旧测试 patch 了全部 `get_object_or_404`（含 `select_for_update` 重取），未走 `locked.status != 'paid'` 守卫 | `false` | 该守卫由 `test_non_paid_status_rejected`（7 状态逐条 POST）完整覆盖；本测试走的是 `_transition()` 条件更新命中 0 行 → `InvalidTransition` 回滚路径，两者分工明确。两路径均有运行通过的测试，无代码缺陷。 |
| 4 | BH | 无唯一约束限制一订单多条 `RefundRequest` | `false` | epic-4-context.md:36 明确「一个订单可产生多条…退款请求记录」，多条本就被设计允许；`Implementation Notes` 已记录不加 `unique_together` 的决定，与冻结边界一致。用户可见路径只有视图 + 状态机 + 锁事务，重复提交由 `test_double_submit_only_once` 证明被拒；直接 ORM/脚本插入非日常路径。 |
| 5 | BH | reason 无 `max_length`，可接受任意长文本 | `low` | 与既有 `ReviewForm.content`（同样无上限）范式一致，spec 未要求长度上限；日常不会遇到超长原因，且修复需改 form + model + 新增迁移，超出直接修正，按 low 驳回规则拒绝。 |
| 6 | BH | 缺原因逐字存储/渲染（长文本、HTML 特殊字符）与 whitespace `strip` 的测试 | `low` | whitespace 拒绝已由 `test_empty_or_blank_reason_rejected`（`''`/`'   '`/`'\t\n'`）覆盖；逐字存储由 `test_refund_success`/`test_forged_post_fields_ignored` 断言；本故事不向买家渲染原因（Epic 5 才展示），Django 模板默认转义，无 XSS。覆盖建议无实际坏结果，拒绝。 |
| 7 | BH | 成功后原因 nowhere 展示，买家视角「只写不可读」 | `false` | 冻结 intent 明确排除：`Approach` 为「仅把原因落库供后续裁决读取」、`Never` 不含管理员展示，成功反馈经 PRG + 状态徽章「纠纷」；原因对管理员可见属 Epic 5 / 5.3。按 intent 排除，非本故事问题。 |
| 8 | BH | 同一 `REFUND_STATUS_ERROR` 走两条错误通道，若同时设置模板会渲染两次 | `false` | 两通道互斥：`refund_error` 仅在 GET 的 `else` 分支设置（views.py:282-285），`form.non_field_errors` 仅在 POST 分支经 `add_error` 填充（:263/:275）。同一请求不可能同时进入两分支，重复渲染不可达。 |
| 9 | BH | HEAD 无测试、POST 未验 CSRF、登录 `next` 未断言回本页 | `low` | 全项目测试均用默认 client（CSRF 中间件对真实请求仍强制、模板含 `{% csrf_token %}`），加 `enforce_csrf_checks` 属新增基建；HEAD 由 Django 按 GET 处理；`next=` 已断言存在且指向登录页。与 4.6 triage #5 同类，无坏结果，拒绝。 |
| 10 | ECH | 非 paid 订单提交空原因会跳过状态检查、不显示状态拒绝提示 | `low` | 非 paid GET 页不渲染表单（`can_refund=False`）， Crafted POST 才可达；即便如此仍返回「退款原因不能为空」这一真实拒绝、状态与记录不变，无状态损害。所引 `guard_snippet` 并非代码中真实存在的守卫；修复需加分支，日常不可达，拒绝。 |
| 11 | ECH | reason 无 `max_length`（同 BH#5） | `low` | 与 #5 同一问题同一证据，按 low 驳回规则拒绝。 |

Verification Gap 层独立追踪全部行为变更（端点/buyer 与 paid 门控/原因校验/事务回滚/落库/入口门控/PRG 徽章）均有正常运行且断言会失败的测试，未发现 gap。无 loopback，冻结 intent 未被改动。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — 期望:`System check identified no issues`。
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — 期望:`No changes detected`（迁移已生成并提交时）。
- `.venv/Scripts/python.exe manage.py test orders -v 2` — 期望:全部用例 ok。
- `.venv/Scripts/python.exe manage.py test -v 2` — 期望:全量通过，无失败/跳过，无回归。
