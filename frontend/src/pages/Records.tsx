import { useState } from "react";

import { api } from "../api/client";
import type { StayStatus } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { Pagination } from "../components/Pagination";
import { StayPanel } from "../components/StayPanel";
import { StayStatusTag } from "../components/Tags";
import { useAsync } from "../hooks/useAsync";
import { addDaysISO, dateOnly, shortDateTime, todayISO } from "../utils/format";

/**
 * 入住记录。
 *
 * 默认时间范围是**近 30 天**，而不是"全部"：
 * 一间 20 房的店一年就几千条，默认拉全部既慢又没用。查更早的记录，
 * 客人报了日期再改范围 —— 这也是前台真实的提问方式。
 */
export function Records() {
  const [status, setStatus] = useState<StayStatus | "">("");
  const [keyword, setKeyword] = useState("");
  const [dateFrom, setDateFrom] = useState(addDaysISO(todayISO(), -30));
  const [dateTo, setDateTo] = useState(todayISO());
  const [page, setPage] = useState(1);
  const [stayId, setStayId] = useState<number | null>(null);

  const list = useAsync(
    () =>
      api.stays.list({
        status,
        keyword: keyword.trim(),
        date_from: dateFrom,
        date_to: dateTo,
        page,
        page_size: 20,
      }),
    [status, keyword, dateFrom, dateTo, page],
  );

  return (
    <div className="hd-stack">
      <div className="hd-toolbar hd-toolbar--wrap">
        <input
          className="hd-input hd-input--search"
          value={keyword}
          onChange={(e) => {
            setPage(1);
            setKeyword(e.target.value);
          }}
          placeholder="客人姓名 / 手机号 / 单号 / 房号"
        />
        <select
          className="hd-select hd-select--sm"
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value as StayStatus | "");
          }}
        >
          <option value="">全部状态</option>
          <option value="IN_HOUSE">在住</option>
          <option value="CHECKED_OUT">已退房</option>
          <option value="CANCELLED">已撤销</option>
        </select>
        <label className="hd-inline hd-small hd-muted">
          入住日期
          <input
            className="hd-input hd-input--date"
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setPage(1);
              setDateFrom(e.target.value);
            }}
          />
          <span>至</span>
          <input
            className="hd-input hd-input--date"
            type="date"
            value={dateTo}
            onChange={(e) => {
              setPage(1);
              setDateTo(e.target.value);
            }}
          />
        </label>
        <span className="hd-spacer" />
        <span className="hd-muted">共 {list.data?.total ?? 0} 条</span>
      </div>

      <div className="hd-card">
        <div className="hd-card__body hd-card__body--flush">
          <AsyncState
            loading={list.loading}
            error={list.error}
            onRetry={list.reload}
            empty={(list.data?.items.length ?? 0) === 0}
            emptyText="这个范围内没有入住记录"
          >
            <table className="hd-table hd-table--hover">
              <thead>
                <tr>
                  <th>单号</th>
                  <th>房间</th>
                  <th>客人</th>
                  <th>入住</th>
                  <th>退房</th>
                  <th className="hd-right">间夜</th>
                  <th className="hd-right">房价</th>
                  <th className="hd-right">押金</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.data?.items.map((s) => (
                  <tr key={s.id}>
                    <td className="hd-mono hd-small">{s.stay_no}</td>
                    <td>
                      {s.room_no}
                      <div className="hd-muted hd-small">{s.room_type_name}</div>
                    </td>
                    <td>
                      {s.guest_name}
                      <div className="hd-muted hd-small">{s.guest_phone ?? s.id_no_masked}</div>
                    </td>
                    <td className="hd-small">{shortDateTime(s.checkin_at)}</td>
                    <td className="hd-small">{s.checkout_at ? shortDateTime(s.checkout_at) : dateOnly(s.expected_checkout_date)}</td>
                    <td className="hd-right">{s.nights}</td>
                    <td className="hd-right">¥{s.room_rate_display}</td>
                    <td className="hd-right">¥{s.deposit_display}</td>
                    <td><StayStatusTag status={s.status} label={s.status_label} /></td>
                    <td className="hd-right">
                      <button className="hd-btn hd-btn--sm" onClick={() => setStayId(s.id)}>
                        查看
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </AsyncState>
        </div>
      </div>

      <Pagination page={page} pageSize={20} total={list.data?.total ?? 0} onChange={setPage} />

      <StayPanel open={stayId !== null} stayId={stayId} onClose={() => setStayId(null)} onChanged={list.reload} />
    </div>
  );
}
