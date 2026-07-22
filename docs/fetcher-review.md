# 抓取层疑点记录

日期：2026-07-22（建议补充于同日，**每条建议均待用户确认后才可动代码**）

`app/fetcher/` 与 `sync_creator` 的抓取逻辑是校准过的基准行为（见 `docs/superpowers/specs/2026-07-22-refactor-design.md` D4），本次重构不改动。以下是阅读代码时发现的疑点，每条附处理建议，后续逐一确认。基准行为的完整描述见 `docs/fetcher.md`。

## 1. `_any_known` 早停逻辑未生效

`playwright_fetcher.py:338` 的 `_any_known()` 恒返回 `False`，导致"翻到包含已知视频的页就提前停止"的优化从未触发，每次都翻完整分页（或靠 TTL 兜底）。原设计意图应是基于本地已存 bvid 集合判断。当前作为静态方法拿不到本地数据，需要注入已知 bvid 集合才能实现。

**建议：暂不处理。** 5min/50min 间隔已经挡住绝大部分重复抓取，翻全量的成本只在真正同步时发生；修复需要把本地 bvid 集合注入冻结层，风险大于收益。等 UP 主数量增多、单轮同步耗时成为实际问题时再议。

## 2. 内存缓存与 `last_synced_at` TTL 语义重叠

fetcher 内部有 1h（视频）/24h（昵称）内存缓存，`sync_creator` 又按 `last_synced_at` 做 5min/50min 的同步间隔控制，两层 TTL 并存且时长不一致。且内存缓存随进程重启失效、多实例各自持有（本次重构已收敛为单实例，情况有所改善）。是否只保留一层，待讨论。

**建议：保留现状。** 两层语义不同：`last_synced_at` 是持久化的"要不要抓"节奏，内存缓存是进程内"抓过了别重复发请求"的兜底（如批量添加时 resolve-name 与同步撞车）。分工已写入 `docs/fetcher.md`，不改代码。

## 3. 可选字段提取失败导致整体失败

`fetch_creator_info` 中头像、视频数属于可选信息，但提取失败会 `raise FetchError` 让整个调用失败。昵称已拿到的情况下因头像失败而整体报错，粒度是否过粗，待讨论。

**建议：处理（小改，需确认）。** 头像/视频数提取失败降级为 `None` 并记 warning，昵称失败才抛 `FetchError`。改动局限在 `fetch_creator_info` 内部，外部契约（返回 dict 结构）不变。

## 4. `FetchError` 缺少上下文信息

`_wait_for_cards` 重试耗尽后 `raise FetchError`（无消息），排查时无法直接定位是哪个 uid、哪个环节。建议异常携带 uid 与阶段信息。

**建议：处理（小改，需确认）。** `fetch_new_videos` 捕获后重新抛出带 uid 与页码的 `FetchError`，或在 `_wait_for_cards` 调用点补充上下文。纯日志可观测性改进，不改流程。

## 5. `_parse_date` 可返回 None 与类型标注不符

`FetchedVideo.published_at` 声明为 `datetime`，但 `_parse_date` 对无法识别的日期返回 `None`。本次重构仅修正类型标注、在 `sync_service` 侧跳过 None 视频；是否应在抓取侧兜底（如用当天日期），待讨论。

**建议：保持现状（不兜底）。** 跳过带 warning 比写入一个编造的日期好——错误日期会污染排序且不可追溯。

## 6. `fetch_creator_name` 无人调用

`playwright_fetcher.py:299` 的 `fetch_creator_name` 是死方法（仅 `fetch_creator_info` 的薄封装），全仓库无调用方。

**建议：处理（删除，需确认）。** 死代码删除无行为变化，但属于冻结层文件，仍先确认。

## 7. 缓存时间戳用字符串存储

`_set_cache` 把 `datetime` 转成 ISO 字符串再存内存 dict，读取时又 `fromisoformat` 解析。内存缓存直接存 `datetime` 对象即可，字符串序列化只在落盘时才需要。

**建议：不处理。** 行为正确，纯实现审美问题，不值得动冻结层。

## 8. 缓存无上限

`_cache` 是普通 dict，无容量上限。UP 主数量有限，实际风险低，仅记录。

**建议：不处理。** 个人工具 UP 主量级下内存可忽略。

## 9. `--no-sandbox` 启动参数

浏览器以 `--no-sandbox` 启动。纯本地个人工具可接受，但如果未来在共享环境运行需重新评估。

**建议：不处理。** 当前部署形态（本地单机）下无风险；部署形态变化时再重评。
