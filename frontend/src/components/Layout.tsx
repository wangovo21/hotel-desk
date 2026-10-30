/**
 * 应用外壳：左侧导航 + 顶部条 + 内容区。
 *
 * 导航顺序是**使用频率**，不是"模块重要性"：
 *   前台工作台排第一、`/` 也重定向到它 —— 这是台前台机，开机第一件事是
 *   看哪间房空着、给客人办入住。默认落在经营看板上，等于要求收银员
 *   每来一个客人都先导航一次，而看板一天只看两次。
 *
 * 顶部条右侧的健康指示不是装饰，它显示部署时最容易漏的两项：
 *   后端连不连得上、后台口令配没配（没配时所有后台写操作 401，
 *   而收银员只会看到"无权限"，想不到是服务端少了个环境变量）。
 */
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { api } from "../api/client";
import type { Health } from "../api/types";
import {
  IconBed,
  IconChart,
  IconCheckin,
  IconDesk,
  IconDoor,
  IconGear,
  IconGuest,
  IconLayers,
  IconRecords,
} from "./icons";

const NAV = [
  { to: "/frontdesk", label: "前台工作台", icon: IconDesk },
  { to: "/checkin", label: "入住登记", icon: IconCheckin },
  { to: "/stays", label: "在住客人", icon: IconBed },
  { to: "/records", label: "入住记录", icon: IconRecords },
  { to: "/guests", label: "客人档案", icon: IconGuest },
  { to: "/dashboard", label: "经营看板", icon: IconChart },
  { to: "/rooms", label: "房间管理", icon: IconDoor },
  { to: "/room-types", label: "房型管理", icon: IconLayers },
  { to: "/settings", label: "参数设置", icon: IconGear },
];

function titleOf(pathname: string): string {
  const hit = NAV.find((n) => pathname.startsWith(n.to));
  return hit?.label ?? "";
}

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealthError(true));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="hd-app">
      <aside className="hd-sider">
        <div className="hd-brand">
          <div className="hd-brand__mark">HD</div>
          <div>
            <div className="hd-brand__name">酒店前台</div>
            <div className="hd-brand__sub">录入 · 房态 · 结账</div>
          </div>
        </div>

        <nav className="hd-nav">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `hd-nav__item${isActive ? " is-active" : ""}`}
            >
              <span className="hd-nav__icon">
                <Icon />
              </span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="hd-sider__foot">
          {healthError && <div className="hd-sider__warn">后端未连接</div>}
          {health && (
            <>
              <div>{health.hotel_name || "未命名酒店"}</div>
              <div className="hd-sider__dim">
                v{health.app_version} · {health.app_env}
              </div>
              <div className="hd-sider__dim">今日 {health.today}</div>
            </>
          )}
        </div>
      </aside>

      <div className="hd-main">
        <header className="hd-topbar">
          <span className="hd-topbar__title">{titleOf(pathname)}</span>
          <span className="hd-topbar__spacer" />
          <HealthChip health={health} error={healthError} />
        </header>
        <main className="hd-content">{children}</main>
      </div>
    </div>
  );
}

function HealthChip({ health, error }: { health: Health | null; error: boolean }) {
  if (error) {
    return (
      <span className="hd-tag hd-tag--danger">
        <span className="hd-dot hd-tag--danger" style={{ marginRight: 5 }} />
        后端不可用
      </span>
    );
  }
  if (!health) return <span className="hd-tag hd-tag--muted">连接中…</span>;

  return (
    <span className="hd-inline">
      {!health.admin_api_enabled && (
        <span className="hd-tag hd-tag--warn" title="服务端未配置 ADMIN_TOKEN，后台写操作会 401">
          后台写接口已关闭
        </span>
      )}
      <span
        className={health.db.ok ? "hd-tag hd-tag--ok" : "hd-tag hd-tag--danger"}
        title={health.db.detail}
      >
        <span
          className={`hd-dot ${health.db.ok ? "hd-tag--ok" : "hd-tag--danger"}`}
          style={{ marginRight: 5 }}
        />
        {health.db.ok ? `数据库正常 · ${health.db.tables} 张表` : "数据库异常"}
      </span>
    </span>
  );
}
