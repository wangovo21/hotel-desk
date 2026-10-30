import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { GuestDetail } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { Modal } from "../components/Modal";
import { Pagination } from "../components/Pagination";
import { StayPanel } from "../components/StayPanel";
import { useAsync } from "../hooks/useAsync";
import { dateOnly, shortDateTime } from "../utils/format";

/**
 * 客人档案。
 *
 * 列表里证件号是脱敏的（大厅屏幕谁都能看见），点进详情才显示全号。
 * 「拉黑」是后台动作，需要 admin token —— 它会影响下一次能不能入住，
 * 不该是随手能点的按钮，所以放在详情里、并且要求二次确认。
 */
export function Guests() {
  const [keyword, setKeyword] = useState("");
  const [blacklistedOnly, setBlacklistedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [stayId, setStayId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const list = useAsync(
    () => api.guests.list({ keyword: keyword.trim(), blacklisted: blacklistedOnly, page, page_size: 20 }),
    [keyword, blacklistedOnly, page],
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
          placeholder="姓名 / 手机号 / 证件号"
        />
        <label className="hd-inline hd-small">
          <input
            type="checkbox"
            checked={blacklistedOnly}
            onChange={(e) => {
              setPage(1);
              setBlacklistedOnly(e.target.checked);
            }}
          />
          只看黑名单
        </label>
        <span className="hd-spacer" />
        <span className="hd-muted">共 {list.data?.total ?? 0} 位</span>
      </div>

      <div className="hd-card">
        <div className="hd-card__body hd-card__body--flush">
          <AsyncState
            loading={list.loading}
            error={list.error}
            onRetry={list.reload}
            empty={(list.data?.items.length ?? 0) === 0}
            emptyText="没有匹配的客人档案"
          >
            <table className="hd-table hd-table--hover">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>证件</th>
                  <th>手机号</th>
                  <th className="hd-right">入住次数</th>
                  <th>最近入住</th>
                  <th>标记</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.data?.items.map((g) => (
                  <tr key={g.id}>
                    <td><b>{g.name}</b> <span className="hd-muted hd-small">{g.gender_label}</span></td>
                    <td className="hd-small">
                      {g.id_type_label}
                      <div className="hd-mono hd-muted">{g.id_no_masked}</div>
                    </td>
                    <td className="hd-small">{g.phone ?? "—"}</td>
                    <td className="hd-right">{g.stay_count}</td>
                    <td className="hd-small">{g.last_checkin_at ? shortDateTime(g.last_checkin_at) : "—"}</td>
                    <td>
                      {g.blacklisted ? (
                        <span className="hd-tag hd-tag--danger">黑名单</span>
                      ) : (
                        <span className="hd-tag hd-tag--muted">正常</span>
                      )}
                    </td>
                    <td className="hd-right">
                      <button className="hd-btn hd-btn--sm" onClick={() => setDetailId(g.id)}>
                        档案
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

      <GuestDetailDialog
        guestId={detailId}
        onClose={() => setDetailId(null)}
        onChanged={() => {
          list.reload();
          setNotice("客人档案已更新");
        }}
        onOpenStay={(id) => setStayId(id)}
      />

      <StayPanel open={stayId !== null} stayId={stayId} onClose={() => setStayId(null)} onChanged={() => undefined} />
    </div>
  );
}

function GuestDetailDialog({
  guestId,
  onClose,
  onChanged,
  onOpenStay,
}: {
  guestId: number | null;
  onClose: () => void;
  onChanged: () => void;
  onOpenStay: (stayId: number) => void;
}) {
  const detail = useAsync<GuestDetail | null>(
    () => (guestId ? api.guests.get(guestId) : Promise.resolve(null)),
    [guestId],
  );

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [remark, setRemark] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const data = detail.data;

  function startEdit() {
    if (!data) return;
    setName(data.name);
    setPhone(data.phone ?? "");
    setRemark(data.remark ?? "");
    setEditing(true);
    setError(null);
  }

  async function save() {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await api.guests.update(data.id, { name: name.trim(), phone: phone.trim() || null, remark: remark.trim() || null });
      setEditing(false);
      detail.reload();
      onChanged();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleBlacklist() {
    if (!data) return;
    const next = !data.blacklisted;
    if (!window.confirm(next ? `确认把「${data.name}」列入黑名单？列入后将无法办理入住。` : `确认解除「${data.name}」的黑名单？`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.guests.update(data.id, { blacklisted: next });
      detail.reload();
      onChanged();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={guestId !== null} onClose={onClose} size="md" title={data ? data.name : "客人档案"} subtitle={data ? `${data.id_type_label} ${data.id_no}` : undefined}>
      <AsyncState loading={detail.loading} error={detail.error} onRetry={detail.reload} empty={!data}>
        {data && (
          <>
            {error && <Notice kind="error" text={error} onClose={() => setError(null)} />}

            {editing ? (
              <div className="hd-form">
                <div className="hd-field">
                  <label className="hd-label">姓名</label>
                  <input className="hd-input" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div className="hd-field">
                  <label className="hd-label">手机号</label>
                  <input className="hd-input" value={phone} onChange={(e) => setPhone(e.target.value)} />
                </div>
                <div className="hd-field hd-field--full">
                  <label className="hd-label">备注</label>
                  <textarea className="hd-textarea" rows={2} value={remark} onChange={(e) => setRemark(e.target.value)} />
                </div>
                <div className="hd-field hd-field--full hd-inline hd-inline--gap">
                  <button className="hd-btn hd-btn--primary hd-btn--sm" onClick={save} disabled={busy}>
                    {busy ? "保存中…" : "保存"}
                  </button>
                  <button className="hd-btn hd-btn--sm" onClick={() => setEditing(false)} disabled={busy}>
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="hd-kv">
                  <div><span>手机号</span><b>{data.phone ?? "—"}</b></div>
                  <div><span>性别</span><b>{data.gender_label}</b></div>
                  <div><span>入住次数</span><b>{data.stay_count}</b></div>
                  <div><span>建档时间</span><b>{dateOnly(data.created_at)}</b></div>
                  <div><span>备注</span><b>{data.remark || "—"}</b></div>
                  <div><span>状态</span><b>{data.blacklisted ? "黑名单" : "正常"}</b></div>
                </div>

                <div className="hd-actions">
                  <button className="hd-btn hd-btn--sm" onClick={startEdit}>编辑资料</button>
                  <button className={`hd-btn hd-btn--sm ${data.blacklisted ? "" : "hd-btn--ghost"}`} onClick={toggleBlacklist} disabled={busy}>
                    {data.blacklisted ? "解除黑名单" : "列入黑名单"}
                  </button>
                </div>

                <h3 className="hd-section-title">住史（最近 20 次）</h3>
                <table className="hd-table">
                  <thead>
                    <tr>
                      <th>单号</th>
                      <th>房间</th>
                      <th>入住</th>
                      <th className="hd-right">间夜</th>
                      <th>状态</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.stays.length === 0 && (
                      <tr><td colSpan={6} className="hd-table__empty">还没有入住记录</td></tr>
                    )}
                    {data.stays.map((s) => (
                      <tr key={s.stay_id}>
                        <td className="hd-mono hd-small">{s.stay_no}</td>
                        <td>{s.room_no}</td>
                        <td className="hd-small">{shortDateTime(s.checkin_at)}</td>
                        <td className="hd-right">{s.nights}</td>
                        <td className="hd-small">{s.status_label}</td>
                        <td className="hd-right">
                          <button className="hd-btn hd-btn--sm" onClick={() => onOpenStay(s.stay_id)}>查看</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}
      </AsyncState>
    </Modal>
  );
}
