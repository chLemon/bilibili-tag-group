/**
 * App：应用根组件，包含导航栏与路由配置。
 * 三个页面：标签视图、UP 主管理、同步状态。
 */
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import TagsPage from "./pages/TagsPage";
import CreatorsPage from "./pages/CreatorsPage";
import SyncPage from "./pages/SyncPage";

const navItems = [
  { to: "/tags", label: "标签视图" },
  { to: "/creators", label: "UP 主管理" },
  { to: "/sync", label: "同步状态" },
];

export default function App() {
  return (
    <BrowserRouter>
      {/* 顶部导航 */}
      <nav
        style={{
          display: "flex",
          gap: 16,
          padding: "12px 24px",
          borderBottom: "1px solid #ddd",
          background: "#fff",
        }}
      >
        <span style={{ fontWeight: 700, marginRight: 16 }}>我的 B 站</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              textDecoration: "none",
              color: isActive ? "#3b5bdb" : "#333",
              fontWeight: isActive ? 600 : 400,
              borderBottom: isActive ? "2px solid #3b5bdb" : "none",
              paddingBottom: 2,
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* 页面内容 */}
      <main style={{ padding: "24px 24px" }}>
        <Routes>
          {/* 默认跳转到标签视图 */}
          <Route path="/" element={<Navigate to="/tags" replace />} />
          <Route path="/tags" element={<TagsPage />} />
          <Route path="/creators" element={<CreatorsPage />} />
          <Route path="/sync" element={<SyncPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
