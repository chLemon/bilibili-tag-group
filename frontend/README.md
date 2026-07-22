# frontend — B 站订阅管理前端

Vite + React + TypeScript 单页应用，三个页面：标签视图、UP 主管理、同步状态。接口详细字段见 `../docs/api.md`。

## 常用命令

```bash
npm install        # 安装依赖
npm run dev        # 开发服务器（/api 代理到 http://localhost:8000，需先启动后端）
npm test           # vitest 全部测试
npx vitest run tests/TagsPage.test.tsx   # 单个测试文件
npm run build      # 类型检查 + 构建（tsc && vite build）
npm run preview    # 预览构建产物
```

## 目录结构

```
src/
├── main.tsx                      # 入口，挂载 App
├── App.tsx                       # 导航栏 + 路由（/ → /tags）
├── api/
│   └── client.ts                 # API 请求封装与 TypeScript 类型（复用后端 snake_case 字段）
├── hooks/
│   ├── useTags.ts                # 标签列表加载
│   └── useSync.ts                # 同步任务轮询（3s）、调度配置、立即同步标签管理
├── pages/
│   ├── TagsPage.tsx              # 标签视图：标签切换、未看视频列表、逐条/批量标记
│   ├── CreatorsPage.tsx          # UP 主管理：列表统计、添加/编辑、批量导入
│   ├── CreatorDetailPage.tsx     # UP 主详情：视频列表、观看状态标记
│   └── SyncPage.tsx              # 同步状态：进度轮询、手动同步、立即同步标签配置
├── components/
│   ├── VideoCard.tsx             # 视频卡片（封面、标题、状态操作）
│   ├── CreatorForm.tsx           # UP 主添加/编辑表单（含昵称解析预填）
│   ├── BatchImportModal.tsx      # 批量导入弹窗
│   ├── CreatorAnchorNav.tsx      # UP 主锚点导航
│   ├── ImmediateTagsSection.tsx  # 立即同步标签配置区
│   └── SyncLogCard.tsx           # 同步任务日志卡片
└── styles/
    └── index.css                 # 全局样式
tests/                            # vitest + Testing Library（jsdom）
```

## 路由

| 路径 | 页面 |
|------|------|
| `/` | 重定向到 `/tags` |
| `/tags` | TagsPage |
| `/creators` | CreatorsPage |
| `/creators/:id` | CreatorDetailPage |
| `/sync` | SyncPage |

## 约定

- **字段命名**：直接复用后端 `snake_case` 响应字段，不做 camelCase 转换
- **时间**：后端返回北京时间 ISO 字符串（无时区后缀），前端 `new Date()` 按本地时间解析即可正确显示；展示层不再做时区换算
- **同步轮询**：`useSync` 每 3 秒轮询 `/api/sync/task/current`；心跳超过 45 秒未更新判定任务终止（与后端 `_HEARTBEAT_DEAD_SEC` 一致）
- **错误处理**：`api/client.ts` 只负责发请求，错误提示由调用方（页面/hooks）处理
- **图标**：统一使用 `lucide-react`

## 测试

vitest + @testing-library/react + jsdom，测试文件在 `tests/` 目录，与页面一一对应。`tests/setup.ts` 注册 jest-dom 匹配器。
