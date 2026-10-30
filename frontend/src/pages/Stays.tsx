import { useState } from "react";

import { api } from "../api/client";
import { AsyncState, Notice } from "../components/AsyncState";
import { Pagination } from "../components/Pagination";
import { StayPanel } from "../components/StayPanel";
import { StayStatusTag } from "../components/Tags";
import { useAsync } from "../hooks/useAsync";
import { dateOnly, shortDateTime } from "../utils/format";

/**
 * 在住客人。
 *
 * 这是"催退房"和"查某人住哪间"的页面，所以默认按**预计离店日**排序 ——
 * 今天该走的人排最上面。逾期的行整行标红，不用再找标签。
 */
export function Stays() {
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [stayId, setStayId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const list = useAsync(
    () => api.stays.list({ status: "IN_HOUSE", keyword: keyword.trim(), page, page_size: 20 }),
    [keyword, page],
  );

  const rows = [...(list.data?.items ?? [])].sort((a, b) =>
    a.expected_checkout_date.localeCompare(b.expected_checkout_date),
  );

  return (
    <div className="hd-stack">
      {notice && <Notice kind="ok" text={notice} onClose={() => setNotice(null)} />}

      <div className="hd-toolbar">
        <input
          className="hd-input hd-input--search"
          value={keyword}
          onChange={(e) => {
            setPage(1);
            setKeyword(e.target.value);
          }}
          placeholder="客人姓名 / 手机号 / 单号 / 房号"
        />
        <span className="hd-muted">共 {list.data?.total ?? 0} 位在住</span>
        <span className="hd-spacer" />
        <button className="hd-btn hd-btn--sm" onClick={list.reload}>
          刷新
        </button>
      </div>

      <div className="hd-card">
        <div className="hd-card__body hd-card__body--flush">
          <AsyncState
            loading={list.loading}
            error={list.error}
            onRetry={list.reload}
            empty={rows.length === 0}
            emptyText="没有在住客人"
          >
            <table className="hd-table hd-table--hover">
              <thead>
                <tr>
                  <th>房间</th>
                  <th>客人</th>
                  <th>入住</th>
                  <th>预计离店</th>
                  <th className="hd-right">间夜</th>
                  <th className="hd-right">房价</th>
                  <th className="hd-right">押金</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} className={s.overdue ? "hd-row--danger" : undefined}>
                    <td>
                      <b>{s.room_no}</b>
                      <div className="hd-muted hd-small">{s.room_type_name}</div>
                    </td>
                    <td>
                      {s.guest_name}
                      <div className="hd-muted hd-small">{s.guest_phone ?? s.id_no_masked}</div>
                    </td>
                    <td className="hd-small">{shortDateTime(s.checkin_at)}</td>
                    <td className="hd-small">
                      {dateOnly(s.expected_checkout_date)}
                      {s.overdue && <span className="hd-tag hd-tag--danger" style={{ marginLeft: 6 }}>逾期</span>}
                    </td>
                    <td className="hd-right">{s.nights}</td>
                    <td className="hd-right">¥{s.room_rate_display}</td>
                    <td className="hd-right">¥{s.deposit_display}</td>
                    <td><StayStatusTag status={s.status} label={s.status_label} /></td>
                    <td className="hd-right">
                      <button className="hd-btn hd-btn--sm" onClick={() => setStayId(s.id)}>
                        详情 / 操作
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </AsyncState>
        </div>
      </div>

      <Pagination
        page={page}
        pageSize={20}
        total={list.data?.total ?? 0}
        onChange={setPage}
      />

      <StayPanel
        open={stayId !== null}
        stayId={stayId}
        onClose={() => setStayId(null)}
        onChanged={() => {
          list.reload();
          setNotice("操作已生效");
        }}
      />
    </div>
  );
}
