# 抓取层行为文档

`app/fetcher/` 与 `SyncService.sync_creator` 的抓取逻辑是**用户校准过的基准行为**。本文档记录这套行为的完整事实，作为今后任何改动的对照基准。**改动前必须先阅读本文档，并与用户确认。**

## 为什么用 Playwright DOM 提取

B 站的 WBI 签名接口有风控，直接调 API 容易被拦。抓取层用 Playwright 无头浏览器打开 UP 主空间投稿页（`https://space.bilibili.com/{uid}/upload/video`），从渲染后的 DOM 视频卡片中逐页提取数据。代价是慢（每个 UP 主要起页面、翻页有延迟），换来的是稳定。

## 反检测与浏览器配置

- 启动参数（`_BROWSER_ARGS`）：`--disable-blink-features=AutomationControlled`、`--disable-features=IsolateOrigins,site-per-process`、`--no-sandbox`、`--disable-setuid-sandbox`
- 上下文：viewport 1920×1080、locale `zh-CN`、时区 `Asia/Shanghai`
- `add_init_script` 注入：`navigator.webdriver` 置空、伪造 `plugins`/`languages`、补 `window.chrome`
- 浏览器实例复用：存在 fetcher 实例上，断开时自动重建；`close()` 在应用关闭时释放

## 抓取流程（fetch_new_videos）

1. 打开投稿页，`wait_until="domcontentloaded"`，页面超时 30s
2. `_wait_for_cards` 等待视频卡片出现（`.bili-video-card__title`，单次等待 10s）；等不到则随机延迟 1.0–2.5s 后刷新重试，最多刷新 4 次，仍失败则 `raise FetchError`（整页失败即整个 UP 主失败）
3. 提取当前页所有卡片（单张卡片解析失败仅跳过该卡片）；按 bvid 全局去重（`seen_bvids`），同一 bvid 即便多次出现也只入列一次，防御 SPA 翻页后 DOM 未刷新时把上一页卡片重复 append
4. 若当前页 bvid 与 `known_videos` 有交集则提前结束；否则若"下一页"按钮 disabled 也结束，否则点击翻页，随机延迟 2.0–4.0s 继续
5. 翻页后先 `_wait_for_page_change` 等激活页码变化（`.vui_pagenation--btns .vui_button--active` textContent 不等于上一页），再 `_wait_for_new_bvid` 等到 DOM 中出现未抓过的 bvid——仅页码变化不足以确认 cards 真切换（B 站 SPA 风控时只改页码 UI 不刷新 cards）。两者任一超时（30s）则触发风控重试
6. 页数上限 1000

`known_videos` 由调用方（`sync_creator`）传入本地已存的该 UP 主视频集合。早停只省抓取量——返回前会把 `known_videos` 中本次未抓到的视频补回，返回值始终是"已知 ∪ 本次新抓"的并集，不因早停而缺失。

## 风控与翻页重试

B 站 SPA 翻页 click 后，前端发 XHR 请求下一页 cards 数据；触发安全风控时 B 站返回 412 错误页，SPA 收到错误后**只更新激活页码 UI，不刷新 cards 列表**——DOM 里仍是上一页的卡片。表现：`_wait_for_new_bvid` 等到 30s 超时仍不见新 bvid，诊断时 cards 数与上一页一致、unique bvid 不变、激活页码已变。

应对：`_wait_for_new_bvid` 失败后 reload 当前页（回到第 1 页），随机延迟 20–40s 等风控冷却，再 click 下一页重新翻页；最多重试 3 次（`_PAGINATION_RETRY_MAX`），仍失败则 `raise FetchError`。重试期间 `_wait_for_new_bvid` 失败会输出 warning 级诊断日志（cards 数 / unique bvid / 当前页码 / seen 数）便于排查。风控是否放行受 IP、访问频率、时间窗口影响，重试只提高恢复概率不保证成功；恢复失败时整个 UP 主本次抓取失败，由 `sync_creator` 上层收集到 `SyncTask.error_message`。

观测性：`fetch_new_videos` 接受可选的 `on_page_progress` 回调，每完成一页以 `(当前页码, 总页数)` 调用一次。总页数从分页按钮 `.vui_pagenation--btns button` 中数字页码的最大值取得，首次抓取第 1 页时提取一次。`sync_creator` 传入回调把页码与总页数写入 `SyncTask.current_creator_pages` / `current_creator_total_pages`，供前端展示页级进度。日志方面，每页抓取完成后输出 info 级日志（页码与本页抓到的视频数）与 debug 级 bvid 列表；翻完或早停后输出 info 级汇总（本次抓到多少、最终返回多少，含补回的 known 视频）。

## 卡片字段提取

| 字段 | 来源 | 解析 |
|------|------|------|
| bvid | 卡片链接 href | 正则 `/video/(BV\w+)`，匹配不到则跳过该卡片 |
| title | `.bili-video-card__title` | 文本去空白 |
| published_at | `.bili-video-card__subtitle span` | 见下方日期解析，解析失败抛 `FetchError` |
| duration_seconds | `.bili-cover-card__stat span` 最后一个 | `分:秒` 或 `时:分:秒` 冒号拆分 |
| cover_url | `.bili-video-card__cover img` src | `//` 开头补 `https:`；提取不到抛 `FetchError` |

日期解析（`_parse_date`）依次尝试：

1. `%Y-%m-%d` 绝对日期
2. `%m-%d`（补当前年；若结果在未来则退一年）
3. 相对时间 `N 分钟/小时/天/个月前`（"个月"按 30 天；统一归零到当天 00:00）
4. 都不匹配抛 `FetchError`

## UP 主信息（fetch_creator_info）

同一投稿页提取：昵称（`.nickname`，提取失败抛 `FetchError`）、头像（`#h-avatar img, .avatar img, .b-avatar img`，`//` 补 `https:`）、视频数（侧栏"视频"项的 `.side-nav__item__sub-text`）。头像/视频数虽是可选信息，但提取过程抛异常也会让整体失败。

## 同步节奏

`last_synced_at` 频率控制：立即同步标签下 UP 主 5 分钟；普通 UP 主 50 分钟。距上次同步不足间隔则整个 UP 主跳过。

同步侧其他节奏：

- 定时调度：`scheduler.py` 按 `SYNC_INTERVAL_MINUTES`（默认 60 分钟）触发全量同步；手动 `POST /api/sync/run` 共用同一幂等入口（运行中返回现有任务，不重复启动）
- 全量同步逐个 UP 主执行，相邻 UP 主之间 sleep 1s
- 单个 UP 主失败不中断整轮：错误收集到 `SyncTask.error_message`，任务最终状态为 failed
- 心跳：执行协程每 15s 更新 `heartbeat_at`；`start_sync` 发现 running 任务心跳超过 45s 未更新，判定进程崩溃，标记 failed 后新建任务
- `enabled=false` 的 UP 主直接跳过（`sync_creator` 顶部守卫）

## 异常约定

- `FetchError`：抓取失败的统一异常。部分抛出点缺少上下文（无 uid/阶段信息）
- `sync_creator` 中 UP 主信息（昵称/头像/视频数）更新失败会被吞掉（`except Exception: pass`），只有 `fetch_new_videos` 失败才向上抛
