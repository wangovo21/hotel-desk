/**
 * 路由表。9 个页面：
 *   前台工作台（房态）/ 入住登记 / 在住客人 / 入住记录 / 客人档案 /
 *   经营看板 / 房间管理 / 房型管理 / 参数设置
 *
 * ★ `/` 重定向到**前台工作台**而不是看板：这是台前台机，开机第一件事是
 *   看哪间房空着、给客人办入住。看板一天看两次，房态图一天看两百次。
 *
 * ★ 没有登录路由：本系统是单店、内网、员工共用的机器。管理动作靠
 *   `X-Admin-Token` 静态口令区分（构建期注入），界面上不做门禁 ——
 *   给一台只有收银员用的机器做登录页，挡住的是收银员自己。
 *   这个取舍的强度和代价写在 README「权限边界」里。
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Checkin } from "./pages/Checkin";
import { Dashboard } from "./pages/Dashboard";
import { FrontDesk } from "./pages/FrontDesk";
import { Guests } from "./pages/Guests";
import { NotFound } from "./pages/NotFound";
import { Records } from "./pages/Records";
import { RoomTypes } from "./pages/RoomTypes";
import { Rooms } from "./pages/Rooms";
import { Settings } from "./pages/Settings";
import { Stays } from "./pages/Stays";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/frontdesk" replace />} />
        <Route path="/frontdesk" element={<FrontDesk />} />
        <Route path="/checkin" element={<Checkin />} />
        <Route path="/stays" element={<Stays />} />
        <Route path="/records" element={<Records />} />
        <Route path="/guests" element={<Guests />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/rooms" element={<Rooms />} />
        <Route path="/room-types" element={<RoomTypes />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
