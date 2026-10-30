import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="hd-empty" style={{ padding: "80px 0" }}>
      <div style={{ fontSize: 32, fontWeight: 700 }}>404</div>
      <div style={{ margin: "8px 0 16px" }}>这个页面不存在</div>
      <Link className="hd-btn hd-btn--sm" to="/frontdesk">
        回前台工作台
      </Link>
    </div>
  );
}
