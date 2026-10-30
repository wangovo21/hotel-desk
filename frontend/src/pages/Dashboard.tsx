import { useState } from "react";

import { api } from "../api/client";
import type { StayBrief } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { StayPanel } from "../components/StayPanel";
import { StayStatusTag } from "../components/Tags";
import { useAsync } from "../hooks/useAsync";
import { shortDateTime } from "../utils/format";

/**
 * 经营看板。
 *
 * 只放店长每天真正会看的数字：出租率、今日进出、今日营收、押金池。
 * 刻意不做"环比增长 xx%"这种需要历史基线才成立的指标 —— 新店第一天
 * 就显示 -100% 除了吓人没别的用。
 */
export function Dashboard() {
  const dash = useAsync(() => api.stats.dashboard(), []);
  const [stayId, setStayId] = useState<number | null>(null);

  const data = dash.data;

  return (
    <div className="hd-stack">
      <AsyncState loading={dash.loading} error={dash.error} onRetry={dash.reload}>
        {data && (
          <>
            <div className="hd-page-head">
              <div>
                <h1 className="hd-h1">{data.hotel_name}</h1>
                <div className="hd-muted">数据截至 {shortDateTime(data.generated_at)}</div>
              </div>
              <button className="hd-btn hd-btn--sm" onClick={dash.reload}>刷新</button>
            </div>

            <div className="hd-stats">
              <Stat label="出租率" value={`${data.occupancy_percent}%`} hint={`${data.in_house_count} / ${data.total_rooms - data.maintenance_count} 可售房`} accent />
              <Stat label="在住人数" value={`${data.guests_in_house}`} hint={`${data.in_house_count} 间房`} />
              <Stat label="今日入住" value={`${data.today_checkins}`} hint="按入住时刻统计" />
              <Stat label="今日退房" value={`${data.today_checkouts}`} hint="按结账时刻统计" />
              <Stat label="今日营收" value={`¥${data.today_revenue_display}`} hint="今日结账单的房费 + 杂费" />
              <Stat label="在住押金池" value={`¥${data.in_house_deposit_display}`} hint="退房时抵扣" />
            </div>

            <div className="hd-stat-strip">
              <span className="hd-chip hd-chip--ok">空闲 {data.vacant_count}</span>
              <span className="hd-chip hd-chip--warn">待清扫 {data.cleaning_count}</span>
              <span className="hd-chip hd-chip--danger">维修 {data.maintenance_count}</span>
              <span className="hd-chip hd-chip--muted">总房 {data.total_rooms}</span>
            </div>

            <div className="hd-card">
              <div className="hd-card__head">
                <h2 className="hd-card__title">近 7 天</h2>
                <span className="hd-muted">入住 / 退房 / 营收（按结账日）</span>
              </div>
              <div className="hd-card__body">
                <TrendChart points={data.trend} />
              </div>
            </div>

            <div className="hd-split">
              <section className="hd-card">
                <div className="hd-card__head">
                  <h2 className="hd-card__title">今日预离</h2>
                  <span className="hd-tag hd-tag--warn">{data.due_out_today.length}</span>
                </div>
                <div className="hd-card__body hd-card__body--flush">
                  {data.due_out_today.length === 0 ? (
                    <div className="hd-empty">今天没有预离的客人</div>
                  ) : (
                    <StayRowList rows={data.due_out_today} onOpen={setStayId} />
                  )}
                </div>
              </section>

              <section className="hd-card">
                <div className="hd-card__head">
                  <h2 className="hd-card__title">逾期未退</h2>
                  <span className={data.overdue_stays.length ? "hd-tag hd-tag--danger" : "hd-tag hd-tag--muted"}>
                    {data.overdue_stays.length}
                  </span>
                </div>
                <div className="hd-card__body hd-card__body--flush">
                  {data.overdue_stays.length === 0 ? (
                    <div className="hd-empty">没有逾期</div>
                  ) : (
                    <StayRowList rows={data.overdue_stays} onOpen={setStayId} />
                  )}
                </div>
              </section>
            </div>

            <div className="hd-split">
              <section className="hd-card">
                <div className="hd-card__head">
                  <h2 className="hd-card__title">房型出租</h2>
                </div>
                <div className="hd-card__body">
                  {data.room_type_usage.map((t) => (
                    <div key={t.room_type_id} className="hd-usage">
                      <div className="hd-usage__head">
                        <span>{t.name}</span>
                        <span className="hd-muted hd-small">{t.occupied}/{t.total} · {t.occupancy_percent}%</span>
                      </div>
                      <div className="hd-usage__bar">
                        <div className="hd-usage__fill" style={{ width: `${Math.min(100, t.occupancy_percent)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="hd-card">
                <div className="hd-card__head">
                  <h2 className="hd-card__title">最近退房</h2>
                </div>
                <div className="hd-card__body hd-card__body--flush">
                  {data.recent_checkouts.length === 0 ? (
                    <div className="hd-empty">还没有退房记录</div>
                  ) : (
                    <StayRowList rows={data.recent_checkouts} onOpen={setStayId} showCheckout />
                  )}
                </div>
              </section>
            </div>
          </>
        )}
      </AsyncState>

      <StayPanel open={stayId !== null} stayId={stayId} onClose={() => setStayId(null)} onChanged={dash.reload} />
    </div>
  );
}

function Stat({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <div className={`hd-stat${accent ? " hd-stat--accent" : ""}`}>
      <div className="hd-stat__label">{label}</div>
      <div className="hd-stat__value">{value}</div>
      {hint && <div className="hd-stat__hint">{hint}</div>}
    </div>
  );
}

function StayRowList({
  rows,
  onOpen,
  showCheckout,
}: {
  rows: StayBrief[];
  onOpen: (id: number) => void;
  showCheckout?: boolean;
}) {
  return (
    <ul className="hd-minilist">
      {rows.map((s) => (
        <li key={s.id} className="hd-minilist__item">
          <div>
            <b>{s.room_no}</b> <span>{s.guest_name}</span>
            <div className="hd-muted hd-small">
              {showCheckout
                ? `${shortDateTime(s.checkin_at)} 入住 · ${shortDateTime(s.checkout_at)} 退房`
                : `预计 ${s.expected_checkout_date} 离店 · ${s.nights} 间夜`}
            </div>
          </div>
          <div className="hd-inline hd-inline--gap">
            <StayStatusTag status={s.status} label={s.status_label} />
            <button className="hd-btn hd-btn--sm" onClick={() => onOpen(s.id)}>查看</button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function TrendChart({ points }: { points: { date: string; checkins: number; checkouts: number; revenue_cents: number; revenue_display: string }[] }) {
  const maxRev = Math.max(1, ...points.map((p) => p.revenue_cents));
  return (
    <div className="hd-bars">
      {points.map((p) => {
        const h = Math.round((p.revenue_cents / maxRev) * 100);
        return (
          <div key={p.date} className="hd-bars__col" title={`${p.date} 营收 ¥${p.revenue_display}`}>
            <div className="hd-bars__value">{p.revenue_cents > 0 ? `¥${Math.round(p.revenue_cents / 100)}` : ""}</div>
            <div className="hd-bars__track">
              <div className="hd-bars__fill" style={{ height: `${h}%` }} />
            </div>
            <div className="hd-bars__label">{p.date.slice(5)}</div>
            <div className="hd-bars__sub">入 {p.checkins} / 退 {p.checkouts}</div>
          </div>
        );
      })}
    </div>
  );
}
