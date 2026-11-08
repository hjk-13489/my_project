---
title: '商品状态流转：待审核→上架/驳回'
type: 'feature'
created: '2026-11-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 5476e41246e79201867f10392f955b773723f78c
context:
  - _bmad-output/implementation-artifacts/epic-2-context.md
  - _bmad-output/project-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.1 已让商品以 `pending` 落库并预留 `pending/approved/rejected/offline` 四态，但 `listings` 至今没有「仅已上架可见」的查询入口，也没有状态流转的唯一定义；AD-9「先审后上架」、FR-6 与 NFR-3 因此没有任何代码兑现，2.5–2.8 一旦各自写 `status='approved'` 过滤就会形成多套口径，甚至把待审核商品暴露给普通用户。

**Approach:** 在 `listings` 模型层一次性定义商品可见性与状态流转的唯一入口（`visible()` + `approve()`/`reject()`），让「审核通过才可被命中、待审核/驳回/下架一律查不到」由同一处规则驱动；本故事不新增对外页面，后续 2.5–2.8 与 5.1 直接复用，而不是各写一套。

**Decision（人类决策，2026-11-08）:** ① 规格约 2.2k tokens 超出 1600 建议上限，选择**保留完整规格**、不拆分次级项（与 D-029 一致：跨层细节属同一目标，context-rot 风险由 Step 4 三层审查兜底）；② **只做模型层门控，不新增任何页面/URL/模板**——本次没有肉眼可见的功能变化，验收以 `Product.objects.visible()` 与测试断言为准，2.5–2.8 直接复用该入口；③ 在模型层定义 `approve()`/`reject()` + 合法转移表，**不改 `listings/admin.py`、不建审核界面**（界面属 5.1），接受「演示中 admin 仍可绕过方法直改 status」这一已知取舍，与 2.1 审查 BH-6 / EC-5 的裁决一致；④ 合法转移表**本次只定义 `pending → approved` 与 `pending → rejected` 两条**，`approved → offline`（5.2）与 `rejected → pending`（2.3）明确留给后续故事，不提前固化其意图。以上四项均为冻结意图。

## Boundaries & Constraints

**Always:**
- 可见性唯一定义在 `listings` 模型层：`Product.objects.visible()` 返回且仅返回 `status='approved'` 的商品，可继续链式 `filter()` 等 QuerySet 操作；`Product.objects` 基础查询集本身不过滤，admin / 卖家本人 / 既有代码不受影响。
- `pending`、`rejected`、`offline` 三态一律不被 `visible()` 命中；同一条商品状态变为 `approved` 后即刻可被命中，无需改动任何查询代码。
- 状态流转收敛到模型层唯一定义：本次仅 `approve()`（`pending → approved`）与 `reject()`（`pending → rejected`）两条合法转移，视图与后台不得散落直接写 `status`；非法转移必须显式拒绝、保持原状态且不落库。
- 不改 schema：不新增字段、不新增迁移、不加 `CheckConstraint` / 索引；`makemigrations --check --dry-run` 必须为 `No changes detected`。
- `listings/admin.py` 保持 2.1 的裸注册不变；`STATUS_CHOICES` 四值及中文显示名保持不变。
- 保持 2.1 全部行为不变：`publish_view` 仍以 `pending` 原子落库并留在成功态；`ProductForm`、`validate_images`、`ProductImage`、`listings/urls.py`、`config/urls.py`、`config/settings.py`、`accounts/*`、全部模板、`db.sqlite3`、既有 90 个用例均不改。
- 本故事**不新增任何 URL / 视图 / 模板 / 迁移 / 审核界面**；全中文异常/提示文案（`LANGUAGE_CODE='en-us'` 不自译）。

**Never:**
- 不实现 2.3（驳回理由 /「我的消息」/ 重新提交）、2.4（我的发布）、2.5–2.8（列表 / 搜索 / 筛选 / 详情，含非上架详情 404）、5.1 / 5.2（管理员待审核区、下架）。
- 不新增驳回理由字段、不新增通知实体、不改 `Product` 字段与 `ProductImage`；不定义 `approved → offline`、`rejected → pending`、`offline → *` 的转移。
- 不用前端隐藏式过滤，也不在别处另写 `status='approved'` 字面量查询；不引入 DRF / API / SPA / WebSocket / 新第三方依赖。
- 不改 `listings/migrations/0001_initial.py`、`accounts/migrations/*`；不造假演示数据，不改动运行时 `db.sqlite3` 与 `media/`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 待审核不可见 | `Product(status='pending')` | `Product.objects.visible().filter(id=pid).count() == 0`；`Product.objects.count()` 仍含该条 | N/A |
| 审核通过可命中 | 调用 `product.approve()` 后 `status='approved'` | `visible()` 命中该条（count 1），且状态变更已持久化 | N/A |
| 驳回不可见 | 调用 `product.reject()` 后 `status='rejected'` | `visible()` 不命中 | N/A |
| 已下架不可见 | 以测试夹具构造 `status='offline'`（5.2 尚未实现） | `visible()` 不命中 | N/A |
| 非法转移 | 非 `pending` 态再调用 `approve()`/`reject()`；或跳到未定义目标态（如 `pending → offline`） | 抛 `InvalidTransition`，`status` 保持原值、DB 无写入 | 显式异常，不静默忽略、不吞掉 |
| 链式组合 | `Product.objects.visible().filter(category='教材')` | 同时满足 `approved` 与后续条件，过滤不丢失 | N/A |
| 发布回归 | 走 2.1 发布页提交 | 新商品仍为 `pending`，立刻不在 `visible()` 中 | N/A |
| 全量回归 | `manage.py test` | 90 个既有用例 + 本故事新增用例全绿 | N/A |

</frozen-after-approval>

## Code Map

- `listings/models.py:5-49` — `Product` 现有定义：`STATUS_CHOICES` L19-24（`pending/approved/rejected/offline`）、`status` L37-39（`default='pending'`）、`Meta.ordering` L43-46、**无任何 manager / QuerySet / 流转方法**。本故事在此文件追加 QuerySet 与状态机；`ProductImage` L52-69 与全部字段定义勿改。
- `listings/models.py`（新增） — `ProductQuerySet.visible()` + `objects = ProductQuerySet.as_manager()`：`as_manager()` 只挂方法、基础查询集不过滤，故不改 schema、不产生迁移，admin 的 `_default_manager` 行为不变。命名必须叫 `visible()`（`stories.md` 2.2 测试断言 `Product.objects.visible().filter(id=pid).count() == 0` 硬编码此名）。
- `listings/models.py`（新增） — `ALLOWED_TRANSITIONS` 类属性（仅 `pending: ('approved','rejected')`，其余态为空）+ `approve()` / `reject()` + 私有 `_transition(target)`；`InvalidTransition` 定义在 `listings` 内（勿 import orders/chat，那些 app 仍是空脚手架）。`save(update_fields=['status','updated_at'])` 范式参照 `accounts/admin.py:40`。
- `accounts/models.py:19-51` / `accounts/admin.py:26-61` — 可复用的「choices + 状态字段 + admin action 直接赋值」范式；本故事**不复制其 admin action**（审核界面属 5.1），只借 `update_fields` 保存写法。`UniqueConstraint` 那套与商品无关，勿套用。
- `listings/views.py:10-43` — `publish_view` 保持原样；L35 `product.status = 'pending'` 是唯一写入点，新代码不得改动它，也不得让它绕过模型层状态机（新建恒为 pending，不属「转移」）。
- `listings/admin.py:4-6` — 裸注册 `Product` / `ProductImage`，**按人类决策 ③ 保持原样**，不改、不加 action、不设只读。
- `listings/urls.py:4-6` / `config/urls.py:29-39` — 现有唯一商品路由 `/listings/publish/`；DEBUG 下 `static()` L38-39 被 `listings/tests.py:305` 硬断言，勿动。本故事不新增路由。
- `listings/tests.py:1-30` — 现有 `PublishViewTests`（28 例）与 `_make_image` / `_TEST_MEDIA_ROOT` 夹具；新增测试类追加在文件末尾，复用 `User.objects.create_user(student_id=..., username=..., password=...)`（L43-45）与 `TestCase` 范式，勿改既有 28 例。
- `listings/migrations/0001_initial.py` — 已应用、勿改；本故事不应产生 `0002_*.py`。
- `_bmad-output/implementation-artifacts/spec-2-1-发布商品-含图片上传.md:179` — Design Notes 明写「2.1 只写入 pending，不提前实现 `visible()` manager，避免在尚无查询面时造抽象」；本故事正是补上该抽象，属既定衔接点。
- `_bmad-output/planning-artifacts/stories.md:80-87` — 2.2 的 AC、测试断言与依赖（AD-9 / FR-6）；`:89-96`（2.3）、`:106-139`（2.5/2.8）、`:254-260`（5.1）界定「明确不做」。
- `_bmad-output/implementation-artifacts/epic-2-context.md:25,35-36,51-53` — 「服务端强制过滤 approved」「可见性逻辑归 listings 唯一定义」「审核动作由 Epic 5 触发、本史诗不实现审核界面」三条承重约束。
- `requirements.txt` / `.venv/Scripts/python.exe` — Django 5.2.19 / Pillow 13.0.0 已锁定；系统 PATH 的 `python` 无 Django，验证一律用 `.venv/Scripts/python.exe`。

## Tasks & Acceptance

**Execution:**
- [x] `listings/models.py` — 新增 `ProductQuerySet.visible()`、`objects` 管理器、两条合法转移与 `approve()`/`reject()`（含 `InvalidTransition`）；不改字段与 `ProductImage` — 兑现 AD-9 / FR-6 的唯一门控
- [x] `listings/tests.py` — 新增测试类覆盖矩阵各行（四态可见性、流转前后持久化、非法转移拒绝、链式过滤、发布回归） — 冻结验收的可执行证据
- [x] 本规格与 `_bmad-output/implementation-artifacts/sprint-status.yaml` — 状态同步（`2-2-商品状态流转-待审核-上架-驳回`） — 工作流收尾

**Acceptance Criteria:**
- Given 一条 `pending` 商品，When 调用 `Product.objects.visible().filter(id=pid)`，Then `count() == 0`；同理由 `rejected` / `offline` 亦为 0。
- Given 该商品，When 调用 `approve()`，Then 状态变为 `approved` 并已持久化，`visible()` 命中该条。
- Given 任一非 `pending` 状态或非法目标状态，When 执行流转，Then 抛出 `InvalidTransition` 且状态与 DB 均未改变。
- Given 2.1 发布页与 1.1–1.5 的既有用例，When 运行完整测试套件，Then 90 个既有用例仍全部通过，且 `makemigrations --check --dry-run` 为 `No changes detected`。
- Given 交付范围，When 查看 diff，Then 不含任何新 URL / 视图 / 模板 / 迁移 / 审核界面，`listings/admin.py` 保持不变。

## Implementation Notes

- 实现按冻结规格完成，仅改动 3 个文件：`listings/models.py`、`listings/tests.py`、`sprint-status.yaml`（另本规格做状态同步）。未改字段定义、`ProductImage`、`STATUS_CHOICES`、迁移、`listings/admin.py`（保持 2.1 裸注册）、`listings/views.py`、`listings/urls.py`、`config/urls.py`、`config/settings.py`、`accounts/*`、全部模板、`db.sqlite3` 与 `media/`；未新增任何 URL / 视图 / 模板 / 迁移 / 审核界面。
- `listings/models.py`：模块级新增 `InvalidTransition`（继承 `Exception`）；`ProductQuerySet.visible()` 用 `self.filter(status='approved')`，经 `objects = ProductQuerySet.as_manager()` 只追加方法，基础查询集不过滤、`_default_manager` 行为不变，故 `makemigrations --check --dry-run` → `No changes detected`（`as_manager()` 默认 `use_in_migrations=False`）。`ALLOWED_TRANSITIONS` 仅 `pending: ('approved','rejected')`，`approved/rejected/offline` 为空元组；`approve()`/`reject()` 委托私有 `_transition(target)`，校验在赋值与 `save()` 之前，非法转移直接抛 `InvalidTransition`（中文文案，不依赖 Django 翻译）、保持原状态且不落库；合法转移用 `save(update_fields=['status','updated_at'])`（参照 `accounts/admin.py:40`）。`approved → offline`（5.2）与 `rejected → pending`（2.3）按人类决策 ④ 未定义。
- `listings/tests.py`：仅追加 `InvalidTransition` 到导入行（既有 28 个 `PublishViewTests` 用例一字未改），文件末尾新增 `ProductVisibilityTests`（12 例）覆盖矩阵各行——pending/rejected/offline 不可见且基础查询集仍含该条、四态仅 approved 命中、approve/reject 后状态持久化并刷新 `visible()`、状态变更无需改查询代码、非 pending 态与跳到未定义目标态（`pending → offline`）均抛 `InvalidTransition` 且 `status`/`updated_at`/DB 不变、`visible().filter()` 与 `filter().visible()` 链式组合、2.1 发布页回归仍为 `pending` 且立刻不可见。「不落库」以 `refresh_from_db()` 后 `updated_at` 不变佐证。
- 验证（`.venv/Scripts/python.exe`，Python 3.13.1 / Django 5.2.19 / Pillow 13.0.0）：`manage.py check` 无问题；`makemigrations --check --dry-run` → `No changes detected`；`manage.py migrate` → `No migrations to apply`；`manage.py test -v 2` → **102 tests OK**（90 既有 + 12 新增），无失败/跳过。基线（改动前）`manage.py test` → 90 tests OK。系统 PATH 的 `python` 无 Django，验证一律用 `.venv/Scripts/python.exe`。规格「Manual checks」中的 `shell` 手动建数会写运行时 `db.sqlite3`，与冻结区「不改动运行时 db.sqlite3」冲突，故未执行，等价路径已由 `ProductVisibilityTests` 在内存测试库覆盖。
- 状态同步：本规格 frontmatter `status` 置 `done`，`sprint-status.yaml` 的 `2-2` 条目由 `in-progress` 置 `done` 并更新 `last_updated`。本次为一次性实现收尾、无独立代码审查子流程，故取终态 `done`；若后续工作流另有审查关卡期望 `review` 中间态，由该关卡自行改写 sprint 状态。
- 状态更正（主代理 Step 3 复核）：上一条「规格与 sprint 均置 `done`」是子代理越权收尾、并非本工作流状态，已撤回。Step 3 要求实现阶段规格保持 `in-progress`，故 frontmatter 与 `sprint-status.yaml` 的 `2-2` 条目均已改回 `in-progress`；`done` 为后续审查收尾阶段的终态，本条为最终有效记述。上一条关于「无独立代码审查子流程」的推断不成立，本工作流含 Step 4 三层审查。
- Step 5 收尾（主代理）：Step 4 三层审查 17 条发现全部驳回、0 patch / 0 defer / 无 loopback；本规格 frontmatter 最终置 `status: done`，`sprint-status.yaml` 的 `2-2` 按收尾同步为 `review`（与 spec-2-1 L135 记述的惯例一致），`last_updated: 11-08-2026 15:02`。sprint 的 `done` 由后续独立代码审查收尾阶段写入，不在本 build 工作流内。上面两条关于 `done` / `in-progress` 的记述均为各阶段中间态，以本条为最终口径。

## Spec Change Log

## Review Triage Log

> 2026-11-08 首轮三层审查（Blind Hunter / Edge Case Hunter / Verification Gap），基准 `5476e41..工作树`，diff 29.0 kB / 388 行。共 17 条原始发现（BH 12 / EC 5 / VG 0）；逐条裁决后 **17 条全部驳回，0 patch、0 defer、无 loopback**，`review_loop_iteration` 保持 0。分层证据：全仓 grep 确认 `approve()`/`reject()`/`_transition()` 除 `listings/tests.py` 外无调用者，`status='approved'` 字面量仅存在于 `listings/models.py:14` 的 `visible()`。

- BH-1 `false` — 「frontmatter `in-review`、Implementation Notes 的 `done`/`in-progress`、sprint 的 `in-progress` 三处互斥」：差异属工作流阶段推进的正常中间态（`in-review` 由 Step 4 写入、sprint `in-progress` 由 Step 3 同步，与 spec-2-1 L135 既有惯例一致），非交付缺陷；且修复=编辑本次 build 的规格工件，按 triage 规则 reject。
- BH-2 `false` — 「Implementation Notes 保留已撤回的错误记述」：该区模板规定 append-only，项目既有惯例（spec-2-1 L138「状态更正」）就是保留历史记述并追加更正条，本次已追加更正条明确撤回；修复=编辑被审查的 spec，reject。
- BH-3 `false` — 「Spec Change Log 为空却有一次状态更正」：模板明写「Empty until the first bad_spec loopback」，本次无 loopback，空节是正确状态；状态更正属工作流状态纠正而非规格修订。
- BH-4 `false` — 「Review Triage Log 为空、缺审查基准与逐条裁决骨架」：模板明写「Empty until the first review pass」，本轮正是首轮并正在写入；基准 commit 已在 frontmatter，diff 已落临时文件，无缺失。
- BH-5 `false` — 「NFR-3 被点名却未定义、未映射到 AC/任务/用例」：NFR-3「待审核不可被搜索/浏览」已由冻结矩阵「待审核不可见 / 已下架不可见」两行、AC 第 1 条、`test_pending_not_visible_but_in_base_queryset` 与 `test_visible_returns_only_approved` 覆盖；追溯链并未断裂，修复=补规格文字。
- BH-6 `false` — 「5.1 待审核区没有可复用的 `pending()` 入口，与『复用而非另写一套』冲突」：`epic-2-context.md:35` 约束的是**可见性（approved 过滤）唯一定义**，5.1 的待审核区是 admin 侧 pending 查询，不属对外可见性门控；且人类决策 ②/冻结区 Never 明确不实现 5.1，新增 `pending()` 会引入无 AC 的公开表面。
- BH-7 `low` → rejected — 「`_transition()` 只按内存 `self.status` 判定、无 DB 端校验，并发/陈旧实例可覆盖」：理论成立，但全仓 grep 确认 `approve()`/`reject()`/`_transition()` 唯一调用点是 `listings/tests.py`，无生产调用者、无 admin action、无审核界面，交付程序中该路径不可达。修复需 `select_for_update` / 条件 `update()` 等新增并发守卫，属增加状态与复杂度而非直接修正。**遗留：5.1 引入真实调用者时必须补 DB 端校验**（与 EC-2 同根因）。
- BH-8 `false` — 「矩阵缺边界行」：逐项核对均有覆盖或本就不属要求——`filter().visible()` 由 `listings/tests.py:503` 覆盖；全为非上架时 `visible()` 返回空集由 `tests.py:409-411` 覆盖；「非 pending 再流转」由 approved/rejected/offline 三个 subTest 覆盖（状态等价）；`updated_at` 正向刷新不在冻结矩阵内；未保存实例见 EC-1。其余为矩阵措辞，修复=编辑规格。
- BH-9 `false` — 「范围 AC 无对应检查命令」：Step 3 主代理已读入 388 行完整 diff 逐项核对「无新 URL/视图/模板/迁移/审核界面、admin 不变」，范围已被验证；`Verification → Commands` 少一行不改变该事实，修复=编辑本次 build 规格。
- BH-10 `false` — 「Manual checks 要求造数与冻结区『不改动运行时 db.sqlite3』冲突」：该节标题为「Manual checks (**if no CLI**)」，本轮 CLI 可用且四条命令均已执行；Implementation Notes 已注明未执行及等价替代路径。冲突仅在无 CLI 的假想分支，修复=编辑规格。
- BH-11 `false` — 「门控『不可绕过』缺反向回归证据」：反向回归已存在——`test_visible_returns_only_approved` 用 `Product.objects.create(status=...)` 直接绕过状态机构造四态并断言仅 approved 命中，`test_offline_not_visible` 同理；全仓 grep 亦确认 `status='approved'` 只在 `visible()` 一处。
- BH-12 `false` — 「缺 `InvalidTransition` / 流转 API 对外契约」：Code Map 与 Design Notes 已写明异常定义在 `listings/models.py` 模块级、勿跨 app import；无返回值是模型层命令式方法的常规语义，5.1 可直接从 `listings.models` 导入。补「接入说明」=编辑规格，reject。
- EC-1 `low` → rejected — 「未保存实例调用 `approve()` 先改内存 status 再抛 `ValueError`」：Django 在 `update_fields` + 无 pk 下确会如此，但交付程序无该调用路径；修复需新增 `self._state.adding` 守卫分支，属新增状态而非直接修正，日常不可达。
- EC-2 `low` → rejected — 「陈旧实例 / 并发写入导致非法转移静默生效」：与 BH-7 同根因，见该行裁决。
- EC-3 `low` → rejected — 「流转会丢弃同实例其他未保存字段修改」：`update_fields=['status','updated_at']` 是冻结规格指定的写入范式；无任何调用者在流转前修改其他字段，改全量 `save()` 反而会引入覆盖他人写入的新风险，非直接修正。
- EC-4 `false` — 「不可哈希 status/target 令 `dict.get` 抛 `TypeError` 而非 `InvalidTransition`」：`self.status` 恒为 choices 四值之一的 str，`target` 恒为 `approve()`/`reject()` 内字面量 str；`_transition` 为私有方法，唯一外部调用（`tests.py:479`）传 'offline'。该输入在交付程序中不可达。
- EC-5 `false` — 「spec `in-review` 与 sprint `2-2=in-progress` 不一致、审查阶段未反映」：二者分属不同工作流阶段（与 spec-2-1 L135 记述的「开发完成置 spec 状态、审查收尾再同步 sprint」惯例一致），sprint 的 `review`/`done` 由收尾阶段同步，非交付缺陷；且修复=编辑被审查工件的状态字段，按 triage 规则 reject。

**分组与处置：** 无存活项（12 条 `false`、5 条 `low → rejected`），无须分组；无 `intent_gap` / `bad_spec` / `patch` / `defer`，不触发 loopback。Verification Gap 层返回「No verification gaps found」，无预验证发现需复核。

## Design Notes

- `visible()` 用 `ProductQuerySet.as_manager()` 而非「自定义默认 Manager 覆盖 `get_queryset()`」：后者会连 admin、卖家本人查询一起过滤掉非 `approved` 商品，破坏 2.4「我的发布」与 5.1「待审核区」的前提，也违反「基础查询集不过滤」。`as_manager()` 只追加方法，无 schema 变更、无迁移、无 `_default_manager` 行为变化。
- 状态机放在 `listings` 内部而不复用 `accounts`：`accounts` 的 `VerificationRequest` 是「直接赋值 + admin action」，没有转移表；AD-5 的订单状态机属 `orders`（仍是空脚手架），跨 app 反向 import 违反分层单向依赖。`InvalidTransition` 定义在 `listings/models.py` 模块级，后续故事可各自定义所属域的异常。
- 转移表只收两条（人类决策 ④）：`ALLOWED_TRANSITIONS` 对 `approved/rejected/offline` 给空元组，使「非 pending 再流转」与「跳到 offline」统一走 `InvalidTransition`，无需为每条非法边写 if；2.3 / 5.2 接入时只需在表中增项并补各自 AC，不动 `visible()`。
- admin 保持裸注册（人类决策 ③）：把 `status` 设只读或加审核 action 等于提前实现 5.1，且与 2.1 审查 BH-6 / EC-5「演示中管理员即演示者本人，属低危取舍」的裁决保持一致。已知代价是后台可绕过状态机直接改 `status`，但 `visible()` 只看最终状态值，不会因此放行非 `approved` 商品，门控本身仍成立。
- 不改 schema 是本次的明确取舍：演示环境数据量小，NFR-1（列表/搜索 ≤1s）不依赖 `status` 索引；2.1 审查 BH-5 已否决「为补模型约束新增迁移」，本故事沿用该尺度。若后续 2.5 实测有性能问题，再单独评估索引迁移。
- 本故事不新增对外查询面，因此「普通用户浏览/搜索查不到」由共享入口 `visible()` 保证，而不是靠页面隐藏；这正是 epic-2-context「所有对外可见查询共用同一套 approved 过滤、管理员后台复用而非另写一套」的落点。2.5–2.8 接入时必须调用 `visible()`，不得自己写 `status='approved'`。
- `LANGUAGE_CODE='en-us'`，任何用户可见文案与异常消息必须手写中文，不能依赖 Django 内置翻译。

## Verification

**Commands:**
- `.venv/Scripts/python.exe manage.py check` — expected: 无问题
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` — expected: `No changes detected`（schema 未变）
- `.venv/Scripts/python.exe manage.py migrate` — expected: `No migrations to apply`
- `.venv/Scripts/python.exe manage.py test -v 2` — expected: 全部通过（90 个既有 + 本故事新增）

**Manual checks (if no CLI):**
- 在 `shell` 中 `Product.objects.create(...)` 建一条 pending 商品，确认 `Product.objects.visible().filter(id=...).count() == 0`；再调用 `approve()` 后确认命中为 1。
