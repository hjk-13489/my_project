---
title: '订单状态机'
type: 'feature'
created: '2026-11-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 192b931debfe6b629d2a65288bf94dd96497658b
context:
  - _bmad-output/implementation-artifacts/epic-4-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `orders` app 目前只有空脚手架（`orders/models.py` 仅一行 import），订单状态没有任何模型层约束。AD-5 要求状态枚举与合法转移表只在 models 层唯一定义、非法跳转必须被拒绝；否则任何视图、admin 或后续代码都能把「待支付」直接改成「已确认收货」，或收货后再退款，FR-20/FR-22/FR-24 的规则形同虚设。

**Approach:** 在 `orders/models.py` 建立 `Order` 实体与状态机底座：状态枚举、`ALLOWED_TRANSITIONS` 转移表、`_transition()` 唯一写入通道，以及 AD-5 指定的 `pay()` / `confirm_receipt()` / `request_refund()` / `resolve_refund()` 与供 4.7 使用的 `mark_reviewed()`。非法转移抛 `InvalidTransition`，状态保持不变、不落库。

**Decision（人类决策，2026-11-13 17:00，全部按推荐 A）:** ① Q1=A：**随 4.4 落最小 `Order` 实体** —— 4.1–4.3 仍在 backlog、`orders` 无任何实体，故本次一并建 `buyer` / `product` / `price` 快照 / `message` / `status` / `created_at` / `updated_at` 与 `orders/0001_initial.py`；下单确认页、模拟支付按钮、联系方式展示仍分别留给 4.1 / 4.2 / 4.3，本轮不新增任何 URL / 视图 / 模板。② Q2=A：**全量实现状态转移方法** —— `pay()` / `confirm_receipt()` / `request_refund()` / `resolve_refund(agree)` 加 `mark_reviewed()` 全部落在 `Order`，后续故事只加视图与 `Review` / `RefundRequest` 实体，不得另写流转。③ Q3=A：**生成迁移并执行 `migrate`** —— `orders/0001_initial.py` 由 `makemigrations` 生成后立即应用，测试跑真实 schema。

## Boundaries & Constraints

**Always:**
- `status` 只能经 `_transition()` 修改；它先校验当前状态再 `save(update_fields=['status', 'updated_at'])`，非法转移不产生任何数据库写入。
- 枚举取值沿用 `listings` 风格（英文 code + 中文 label）：`pending_payment` 待支付、`paid` 已支付/待交付、`received` 已确认收货、`completed` 已完成、`reviewed` 已互评、`dispute` 纠纷、`refunded` 退款成功、`refund_failed` 退款失败。业务判断一律用 code。
- `confirm_receipt()` 在单个 `transaction.atomic()` 内完成 `paid → received → completed` 两跳（FR-22「自动标记已完成」），任一步失败整体回滚。
- 状态机是 `orders/models.py` 的唯一定义；其他 app（含 `dashboard`）只调用方法，不复刻转移表。
- 订单金额为下单时的价格快照 `price = DecimalField(10, 2)`，商品后续改价不影响历史订单。

**Never:**
- 不新增 URL / 视图 / 模板 / 表单，不注册 admin —— 下单确认页、模拟支付按钮、联系方式展示、订单列表分别属 4.1 / 4.2 / 4.3 / 4.5。
- 不实现 `Review`、`RefundRequest` 实体与「双方均提交」判定（属 4.7 / 4.8）；`mark_reviewed()` 只提供转移入口。
- 不修改 `listings` / `accounts`；不接外部支付网关、不写支付流水。
- 交付路径之外不允许直接赋值 `status`（测试中构造状态用 `Order.objects.create(status=...)` 属夹具，不属业务写入路径）。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|------------|----------------|----------|
| 正常路径 | 新建订单 `pending_payment` | `pay()` → `paid`；`confirm_receipt()` → `completed`（中间经 `received`） | N/A |
| 互评闭环 | `completed` | `mark_reviewed()` → `reviewed` | N/A |
| 退款成功 | `paid` | `request_refund()` → `dispute`；`resolve_refund(True)` → `refunded` | N/A |
| 退款失败 | `dispute` | `resolve_refund(False)` → `refund_failed` | N/A |
| 跳过支付 | `pending_payment` | `confirm_receipt()` 抛 `InvalidTransition` | 状态不变，DB 重读仍为 `pending_payment` |
| 收货后退款 | `received` / `completed` | `request_refund()` 抛 `InvalidTransition` | 状态不变 |
| 待支付退款 | `pending_payment` | `request_refund()` 抛 `InvalidTransition` | 状态不变 |
| 重复支付 | `paid` | `pay()` 抛 `InvalidTransition` | 状态不变（不重复流转） |
| 重复收货 | `completed` | `confirm_receipt()` 抛 `InvalidTransition` | 状态不变 |
| 终态再流转 | `reviewed` / `refunded` / `refund_failed` | 任何转移方法均抛 `InvalidTransition` | 状态不变 |
| 裁决前置 | 非 `dispute` | `resolve_refund(True/False)` 抛 `InvalidTransition` | 状态不变 |

</frozen-after-approval>

## Code Map

- `orders/models.py` — 当前只有 `from django.db import models` 占位；本次状态机的唯一落点。
- `orders/migrations/` — 现仅 `__init__.py`；需新增 `0001_initial.py`。
- `orders/tests.py` — 占位文件；项目约定测试写在各 app 的单一 `tests.py`。
- `listings/models.py:5-7, 31-44, 97-107` — 直接可仿照的既有范式：模块级 `InvalidTransition` 异常、元组列表式 `STATUS_CHOICES`、`ALLOWED_TRANSITIONS: dict[str, tuple]` 与 `_transition()`（先校验后 `save(update_fields=['status', 'updated_at'])`）。
- `listings/models.py:79-91` — `reject()` 示范「转移 + 副作用同一事务」，`confirm_receipt()` 的两跳照此写法。
- `listings/models.py:46-61` — FK 到 `settings.AUTH_USER_MODEL`、`related_name`、`created_at/updated_at`、中文 `verbose_name` 与 `Meta` 约定。
- `accounts/models.py:5-14` — 自定义 `User`（`USERNAME_FIELD='student_id'`，无 QQ/微信字段）；订单 buyer 用 `settings.AUTH_USER_MODEL`，不硬编码。
- `config/settings.py:34-47` — `orders` 已在 `INSTALLED_APPS`，无需改动。
- `_bmad-output/implementation-artifacts/epic-4-context.md` — 状态机唯一定义点、方法名、字段与事务约定。

## Tasks & Acceptance

**Execution:**
- [x] `orders/models.py` — 新增 `InvalidTransition`、`Order`（`STATUS_CHOICES`、`ALLOWED_TRANSITIONS`、字段、`__str__`、`_transition()` 与五个转移方法）— 状态机唯一定义点。
- [x] `orders/migrations/0001_initial.py` — 由 `makemigrations` 生成并 `migrate` — 让模型真正落库可用。
- [x] `orders/tests.py` — 用例覆盖 I/O 矩阵全部 11 行，并断言非法转移后从 DB 重读状态不变 — 证明「拒绝」而非「静默忽略」。

**Acceptance Criteria:**
- Given 一张 `pending_payment` 订单，when 调 `confirm_receipt()`，then 抛 `InvalidTransition` 且从 DB 重读仍为 `pending_payment`。
- Given 一张 `paid` 订单，when 依次调 `pay()`，then 抛 `InvalidTransition`；when 调 `confirm_receipt()`，then 状态为 `completed`。
- Given 一张 `completed` 订单，when 调 `request_refund()`，then 抛 `InvalidTransition`（收货后不可退款）。
- Given `ALLOWED_TRANSITIONS` 与 `STATUS_CHOICES`，when 全仓检索赋值点，then `status` 的写入只出现在 `orders/models.py` 的 `_transition()` 内，无视图/admin/模板参与。
- Given 本轮改动，when 跑全量测试，then 既有用例无回归、新增用例全绿。

## Implementation Notes

- `orders/models.py`：`Order` 含 `buyer`(FK→`settings.AUTH_USER_MODEL`, CASCADE)、`product`(FK→`listings.Product`, PROTECT, 字符串引用避免跨 app 导入耦合)、`price`、`message`(blank)、`status`(max_length=20, default `pending_payment`)、`created_at`、`updated_at`；`Meta.ordering = ('-created_at',)`。
- 转移表：`pending_payment→paid`；`paid→received|dispute`；`received→completed`；`completed→reviewed`；`dispute→refunded|refund_failed`；其余终态无出边。
- `confirm_receipt()` 在 `transaction.atomic()` 内做 `paid→received→completed` 两跳；`resolve_refund(agree)` 以布尔决定 `refunded` / `refund_failed`。
- `orders/migrations/0001_initial.py` 由 `makemigrations orders` 生成，依赖 `listings.0002_rejectionnotice` 与 swappable user，已应用。
- `orders/tests.py`：12 个用例覆盖 I/O 矩阵全部 11 行（终态与「裁决前置」用子循环展开），另加价格快照用例；非法转移断言统一经 `refresh_from_db()` 确认库内状态未变。
- 审查补丁（Step 4）：`_transition()` 改为在 `transaction.atomic()` 内按「库内状态 = 实例内存状态」做条件更新，命中 0 行抛 `InvalidTransition`（陈旧实例不再覆盖并发推进后的状态）；`resolve_refund()` 增加 `bool` 类型闸门；`confirm_receipt()` 两跳仍同事务，第二跳失败整体回滚。测试补 4 例（陈旧实例覆盖、两跳回滚、`dispute` 拒绝普通转移、非布尔裁决），`test_price_is_snapshot` 改用独立商品避免夹具污染，用例数 12 → 16。
- 复审补丁（第二轮 Step 5）：补 `test_new_order_defaults_to_pending_payment`（不传 `status` 建单必为 `pending_payment`，4.1 的下单视图依赖该默认值）与 `test_mark_reviewed_requires_completed`（`pending_payment` / `paid` / `received` 调 `mark_reviewed()` 均拒绝）；已做变异验证：把 default 改为 `paid`、给 `paid` 增 `reviewed` 出边，两条新用例分别转红。用例数 16 → 18，全量 242 例 OK。

## Spec Change Log

## Review Triage Log

首轮三层审查（Blind Hunter 21 / Edge Case Hunter 4 / Verification Gap 2，共 27 条），`review_loop_iteration` 保持 0（无 loopback）。

| # | 层 | 发现 | 裁决 | 证据 |
|---|----|------|------|------|
| 1 | BH | `received` 是永远无法到达也走不出去的死状态，与架构两段式收货不一致 | `false` | 冻结区 Decision ② 与 Always 明文要求 `confirm_receipt()` 在单事务内 `paid → received → completed` 两跳；4.6 的 AC 又要求「status →「已确认收货」并自动标记「已完成」」，故 `received` 必须在枚举里可表示、但只在事务内瞬时存在。架构图的两次跳转在本实现中被合并为一次调用，属已批准的实现选择，非缺陷。 |
| 2 | BH | `pay()` 没有 `transaction.atomic()`，与 AD-6 单事务承诺不符 | `low` | 实际上是单条 `UPDATE`，在 SQLite/MySQL 下本身原子，用户与开发者都不会遇到坏结果；但确实缺了声明的事务边界，归入 #3 同组一并修补（把事务下沉到 `_transition()`）。 |
| 3 | BH | `_transition()` 只读内存 `self.status`，无 `select_for_update()`，陈旧实例可覆盖库内状态 | `medium` | 成立且可复现：#26 在测试库实测「A 退款后库内 `dispute`、仍持 `paid` 的 B 调 `confirm_receipt()` 不抛错并把状态改写为 `completed`」，等于绕过管理员裁决（FR-24）。修复须改为按库内状态做条件更新。 |
| 4 | BH | `status` 可被 `.update()` / admin / `save()` 绕过 `_transition()`，无 `CheckConstraint` | `low` | 无生产调用者可触发；AD-5 要求的是「models 层唯一定义」，DB 约束只能挡非法码值、挡不住非法跳转；`listings` 的 admin 裸注册属已接受取舍（D-035）。修复需新增守卫机制而非直接修正 → 驳回。 |
| 5 | BH | `ALLOWED_TRANSITIONS.get(self.status, ())` 把脏状态伪装成终态 | `low` | 只有人工改库才能造出未知状态，交付路径不可达；修复需新增分支。驳回。 |
| 6 | BH | 缺「枚举与转移表一致」的元测试 | `low` | 8 个码与转移表同在 `orders/models.py` 一处可见，新增状态本就须同时改两处；属测试强度偏好，修复需新增用例而非直接修正 → 驳回。 |
| 7 | BH | `dispute` 这一非终态没有被任何用例断言拒绝其它转移 | `low` | 成立（`test_terminal_states_reject_every_transition` 只跑 `reviewed/refunded/refund_failed`），属测试覆盖缺口，随 #8 的补测一并补齐。 |
| 8 | BH | `confirm_receipt()` 两跳原子回滚无测试，拆掉 `atomic()` 仍全绿 | `medium` | 与 #27 同根因，合并处理。 |
| 9 | BH | `resolve_refund(agree)` 不校验类型，`'false'` / `'0'` 走真值分支记为退款成功 | `medium` | 成立：`if agree` 对非空字符串恒真，管理员误传 `request.POST.get('agree')` 会把「不同意」记成「退款成功」，且为不可恢复终态。 |
| 10 | BH | `test_price_is_snapshot` 改 `cls.product.price` 污染后续用例 | `low` | 成立（`setUpTestData` 类属性被就地修改，后续 `_make_order` 取到 99.00），当前无用例断言价格所以未暴露；修复是直接修正夹具，并入 #25 一并处理。 |
| 11 | BH | 缺 `paid_at` / `completed_at` 等分阶段时间戳 | `low` | 4.4 意图只覆盖状态机；新增字段会扩大 schema 公共表面，且 Epic 5 统计尚未提出具体口径。驳回（若将来需要按阶段统计，属新故事）。 |
| 12 | BH | `buyer` 用 CASCADE 而 `product` 用 PROTECT，删除买家协会抹掉订单与成交数 | `low` | 仓库无任何用户删除路径（`accounts` 无删除功能），交付程序中不可达；改 `SET_NULL` 需动 schema 与权限模型，超出直接修正。驳回。 |
| 13 | BH | `request_refund()` 不接收 reason，「原因必填」在 4.4 无兜底 | `false` | 冻结区 Decision ② 与 Design Notes 明确原因字段与必填校验属 4.8 的 `RefundRequest` 实体；本故事交付面内不存在「产生无原因纠纷」的调用者（无视图）。 |
| 14 | BH | `InvalidTransition` 与 `_transition()` 是 `listings` 的第二份复制，跨 app 无法统一 `except` | `low` | 架构明确「实体及其生命周期方法归其所属 app 唯一定义，其他 app 只调用、不复刻」，抽公共基类反而制造跨 app 耦合；异常按 app 分域是本项目既定形态。驳回。 |
| 15 | BH | `InvalidTransition` 不继承 `ValidationError`，4.2 需自写转换 | `low` | 属 4.2 的视图契约选择，4.4 冻结意图未要求；当前无调用者。驳回。 |
| 16 | BH | `## Verification` 只列命令无实跑输出，且裸 `python` 因缺 Django 失败 | `false` | 主代理已独立实跑：`check` 0 issues、`makemigrations --check --dry-run` → No changes detected、`test orders` → 12 例 OK、全量 `test` → 236 例 OK；仓库约定用 `.venv/Scripts/python.exe`。修复=编辑本次 build 的规格 → 驳回。 |
| 17 | BH | spec `in-review` 与 sprint `in-progress` 不一致 | `false` | sprint 的 `review` 同步由 Step 5 收尾统一写入，Step 4 只改 spec；修复=编辑状态工件。驳回。 |
| 18 | BH | Implementation Notes 的用例计数自相矛盾 | `false` | 12 例 = 11 行矩阵（逐行一一对应）+ 1 例价格快照，口径可通；措辞松散的修复=编辑规格 → 驳回。 |
| 19 | BH | `epic-4-context.md` 未记录 `mark_reviewed()` 与「两跳合一」 | `false` | 该文件是编译产物、根因在规划工件；`mark_reviewed()` 已由冻结区 Decision ② 明确要求。修复=编辑规划/规格工件 → 驳回。 |
| 20 | BH | `message` 无长度上限、`price` 无非负校验 | `low` | 4.1 的表单校验才是入口约束，本故事不提供写入路径；加校验器属新公共表面。驳回。 |
| 21 | BH | `status` 无 `db_index`，4.5 / 看板按状态过滤会扫全表 | `low` | 演示规模（SQLite、单机）下无性能坏结果，本故事亦未提出性能要求；加索引属未验证的提前优化。驳回。 |
| 22 | EC | 并发/陈旧实例可双重流转，无守卫 | `medium` | 与 #3 / #26 同根因，合并为一条 patch。 |
| 23 | EC | `resolve_refund` 非布尔入参被当真值处理 | `medium` | 与 #9 同根因，合并为一条 patch。 |
| 24 | EC | 第二跳失败回滚后内存 `self.status` 仍为 `received`，重试会抛错 | `low` | 当前转移表下第二跳恒合法、该分支不可达；异常向上抛出即中止调用，坏结果不成立。驳回。 |
| 25 | EC | `test_price_is_snapshot` 污染类级夹具 | `low` | 与 #10 同根因，合并为一条 patch。 |
| 26 | VG | 「同一订单两个实例」的非法流转无任何用例，实测 `dispute` 被覆盖为 `completed` | `medium` | 该层为 pre-verified gap，采信其 filed evidence（真实执行：A 退款后陈旧 B 调 `confirm_receipt()` 无异常且改写库内状态）；坏结果违反 FR-24「纠纷分支不再通向确认收货」。最小修复=按库内状态条件更新，不加公共表面。 |
| 27 | VG | `confirm_receipt()` 两跳原子性无测试，删掉 `atomic()` 仍 12 例全绿 | `medium` | 该层为 pre-verified gap，采信其 evidence（实际删 `atomic()` 后全绿）；坏结果=确认收货半提交，订单永久停在 `received`，既不能退也不能完成。最小修复=补一条故障注入用例。 |

分组与路由：27 条中 10 条 `false`、11 条 `low → rejected`、1 条 `low → patch`（#2，#3 同组）、5 组 `medium → patch`（#3/#22/#26 陈旧实例并发、#8/#27 两跳原子、#9/#23 布尔校验、#7 矩阵外状态补测、#10/#25 夹具污染）；无 `intent_gap` / `bad_spec`，不触发 loopback。

## Design Notes

- `request_refund()` 暂不带 `reason` 参数：原因字段与「必填」校验属于 4.8 的 `RefundRequest` 实体，4.8 在调用本方法后于同一事务内落原因记录，不在状态机里伪造一次性字段。
- `resolve_refund(agree)` 只接受布尔裁决，管理员后台（Epic 5）与 4.8 都走这一个方法，避免两套流转。
- `product` 用 `on_delete=PROTECT`：订单是交易凭证，商品被删除不应连带抹掉历史订单。

## Verification

**Commands:**
- `python manage.py check` — 期望：`System check identified no issues`。
- `python manage.py makemigrations --check --dry-run` — 期望：`No changes detected`（迁移已生成）。
- `python manage.py migrate` — 期望：`No migrations to apply`（已应用）。
- `python manage.py test orders -v 2` — 期望：全部用例 ok。
- `python manage.py test -v 2` — 期望：全量通过，无失败/跳过。

## Review Findings

复审（第二轮，全四层：Blind Hunter 15 / Edge Case Hunter 2 / Verification Gap 2 / Acceptance Auditor 6，共 25 条 → 18 组）。本轮打补丁前的首轮权威记录见上方 `Review Triage Log`。

- [x] [Review][Patch] 新建订单的默认状态 `pending_payment` 无任何断言，把 default 改成 `paid` 后 16 例仍全绿 [orders/tests.py:33-40, orders/tests.py:189-193]
- [x] [Review][Patch] `mark_reviewed()` 的非法前置状态（`pending_payment` / `paid` / `received`）无拒绝用例，给 `paid` 补一条到 `reviewed` 的出边仍全绿 [orders/tests.py:62-67, orders/models.py:29]

- [x] [Review][Defer] `epic-4-context.md` 声称卖家 QQ/微信字段由 `accounts` 提供，而 `accounts.User` 实际只有 `student_id` / `is_verified` / `role`，无任何 QQ/微信字段 [accounts/models.py:5-14] — deferred: 规划工件缺口，4.3「下单后展示联系方式」当前**没有数据源**；修复需在 `accounts` 增字段（本故事 Never 明确禁止改 `accounts`），属需人类重协商的规划决策。
- [x] [Review][Defer] `epic-4-context.md` 要求售出订单按 `product__seller` 过滤，而 `listings.Product` 卖家字段名是 `owner` [listings/models.py:46-49] — deferred: 上下文文档编译时未与代码核对，4.5 照抄会在 `FieldError` 处炸；修复=编辑规划工件。
- [x] [Review][Defer] `refund_failed` 为终态且无出边，管理员驳回退款后订单永久卡死（既不可 `confirm_receipt()` 也不可再 `request_refund()` / `mark_reviewed()`） [orders/models.py:31-33] — deferred: 转移表由冻结区 Decision 与 Implementation Notes 明确写死（「其余终态无出边」），缺口在 Epic 4 的需求层，需规划层补一条「驳回退款后订单何去何从」的规则。
- [x] [Review][Defer] 无「卖家不可购买自己商品」「同一商品不可并行多张非终态订单」约束；`buyer == product.owner` 时 4.7 的「双方互评」语义塌陷 [orders/models.py:36-48] — deferred: 下单入口属 4.1，约束加在 `Order` 上会扩大本故事 schema 公共表面；属规划层待定规则。

**Rejected（12 组）：**

- `false` — `mark_reviewed()` 不校验评价是否齐备：冻结区 Never 明文「不实现 `Review`/`RefundRequest` 与「双方均提交」判定（属 4.7 / 4.8）；`mark_reviewed()` 只提供转移入口」，本故事边界即如此。
- `false` — `received` 经公开方法不可持久化却出现在 epic 的进度状态里：Decision ② 与 Always 明文要求 `confirm_receipt()` 在单事务内两跳，与本故事已批准实现一致（同首轮 #1）。
- `low` — `_transition()` 对未保存实例（`pk=None`）抛「订单当前状态已被其他操作变更」这一误导性消息（实测成立，`filter(pk=None)` 生成 `id IS NULL`）；但需调用方在 save 前调转移方法，无此调用路径，修法是新增 `pk is None` 分支，超出直接修正。
- `low` — `confirm_receipt()` 第二跳失败回滚后内存 `self.status` 残留为 `received`（与库内 `paid` 分叉），同实例重试会得到误导性错误；但条件更新下第二跳 0 行在 SQLite 单写者事务内不可达，仅在其他未预见的异常下成立，修法需加 try/except 守卫。
- `low` — `resolve_refund()` 的非布尔闸门排在状态校验之前，故「终态 + 非布尔入参」得 `ValueError` 而非 `InvalidTransition`；I/O 矩阵「裁决前置」行只承诺 `resolve_refund(True/False)`，该组合不被规格覆盖，且拒绝后状态不变，属开发者专用错误类型的措辞偏好。
- `low` — `_transition()` 用 `filter().update()` 而非冻结区写的 `save(update_fields=[...])`：当前无 `post_save` 信号与 `save()` 钩子，`updated_at` 亦被显式赋值，无可观测坏结果；且条件更新正是首轮 #3/#22/#26 批准的修法，剩余分歧在冻结区措辞，修复=编辑受审 spec。
- `low` — 状态流转无留痕（`received` 时间戳被立即覆盖、裁决人不记录）：新增字段会扩大 schema 公共表面，Epic 5 统计口径尚未提出。
- `low` — AC 第二句的串行语义（`pay()` 被拒后同一实例继续 `confirm_receipt()`）未被单条用例守护：两半行为分别由 `test_pay_twice_rejected` 与 `test_normal_path_pay_then_confirm_receipt` 覆盖，拒绝路径不改内存与库内状态，链路行为由构造保证。
- 修复=编辑受审 spec — `Review Triage Log` 收尾统计与表内裁决不符（表内实为 6 条 `false`、14 条 `low`、7 条 `medium`，正文写「10 条 false、11 条 low → rejected」并称「21 驳回」）。
- 修复=编辑受审 spec — `Implementation Notes` 前段仍写「12 个用例」，末段写「12 → 16」，而 `orders/tests.py` 实为 16 个测试方法。
- 修复=编辑受审 spec — frontmatter `status: 'done'` 与同 diff 内 `sprint-status.yaml` 的 `review` 并存，`## Spec Change Log` 为空标题。
- 修复=编辑受审 spec — `## Verification` 只列命令与期望、无实跑输出，且写裸 `python`（本仓库需 `.venv/Scripts/python.exe`）。
