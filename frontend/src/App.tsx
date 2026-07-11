/**
 * App：应用根组件，包含导航栏与路由配置。
 */
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Tags, Users, RefreshCw, Hash } from "lucide-react";
import TagsPage from "./pages/TagsPage";
import CreatorsPage from "./pages/CreatorsPage";
import { SyncPage } from "./features/sync";

const navItems = [
  { to: "/tags", label: "标签视图", Icon: Tags },
  { to: "/creators", label: "UP 主管理", Icon: Users },
  { to: "/sync", label: "同步状态", Icon: RefreshCw },
];

export default function App() {
  return (
    <BrowserRouter>
      <nav className="navbar">
        <div className="navbar-inner">
          <span className="navbar-brand">
            <Hash size={22} />
            我的 B 站
          </span>
          <div className="navbar-links">
            {navItems.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `nav-link${isActive ? " nav-link-active" : ""}`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/tags" replace />} />
          <Route path="/tags" element={<TagsPage />} />
          <Route path="/creators" element={<CreatorsPage />} />
          <Route path="/sync" element={<SyncPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
