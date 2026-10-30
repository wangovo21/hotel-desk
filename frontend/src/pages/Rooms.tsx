import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { Room, RoomStatus, RoomType } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { Modal } from "../components/Modal";
import { RoomStatusTag } from "../components/Tags";
import { useAsync } from "../hooks/useAsync";

/**
 * 房间管理（后台）。
 *
 * 新增/改房型/删除都要 admin token（右上角提示里会说明）；
 * 房态切换（打扫完成 / 报修 / 恢复空闲）也走这里 —— 但工作台上的房卡
 * 有同样的按钮，因为那是保洁和前台的高频动作。
 */
export function Rooms() {
  const [status, setStatus] = useState<RoomStatus | "">("");
  const [floor, setFloor] = useState<string>("");
  const [keyword, setKeyword] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<Room | "new" | null>(null);

  const rooms = useAsync(
    () =>
      api.rooms.list({
        status,
        floor: floor ? Number(floor) : "",
        keyword: keyword.trim(),
      }),
    [status, floor, keyword],
  );
  const types = useAsync(() => api.roomTypes.list(), []);

  const floors = Array.from(new Set((rooms.data ?? []).map((r) => r.floor))).sort((a, b) => a - b);

  async function quickStatus(room: Room, next: "VACANT" | "MAINTENANCE" | "CLEANING") {
    try {
      await api.rooms.setStatus(room.id, next);
      setNotice({ kind: "ok", text: `${room.room_no} 房态已更新` });
      rooms.reload();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    }
  }

  async function remove(room: Room) {
    if (!window.confirm(`确认删除房间 ${room.room_no}？只有从未有过入住记录的房间才能删。`)) return;
    try {
      await api.rooms.remove(room.id);
      setNotice({ kind: "ok", text: `${room.room_no} 已删除` });
      rooms.reload();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    }
  }

  return (
    <div className="hd-stack">
      {notice && <Notice kind={notice.kind} text={notice.text} onClose={() => setNotice(null)} />}

      <div className="hd-toolbar hd-toolbar--wrap">
        <input
          className="hd-input hd-input--search"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="房号 / 房型名"
        />
        <select className="hd-select hd-select--sm" value={status} onChange={(e) => setStatus(e.target.value as RoomStatus | "")}>
          <option value="">全部房态</option>
          <option value="VACANT">空闲</option>
          <option value="OCCUPIED">在住</option>
          <option value="CLEANING">待清扫</option>
          <option value="MAINTENANCE">维修中</option>
        </select>
        <select className="hd-select hd-select--sm" value={floor} onChange={(e) => setFloor(e.target.value)}>
          <option value="">全部楼层</option>
          {floors.map((f) => (
            <option key={f} value={f}>{f} 层</option>
          ))}
        </select>
        <span className="hd-spacer" />
        <button className="hd-btn hd-btn--primary hd-btn--sm" onClick={() => setEditing("new")}>
          新增房间
        </button>
      </div>

      <div className="hd-card">
        <div className="hd-card__body hd-card__body--flush">
          <AsyncState
            loading={rooms.loading}
            error={rooms.error}
            onRetry={rooms.reload}
            empty={(rooms.data ?? []).length === 0}
            emptyText="没有匹配的房间"
          >
            <table className="hd-table hd-table--hover">
              <thead>
                <tr>
                  <th>房号</th>
                  <th>楼层</th>
                  <th>房型</th>
                  <th className="hd-right">挂牌价</th>
                  <th className="hd-right">可住</th>
                  <th>房态</th>
                  <th>备注</th>
                  <th className="hd-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {rooms.data?.map((room) => (
                  <tr key={room.id}>
                    <td><b>{room.room_no}</b></td>
                    <td>{room.floor}</td>
                    <td>{room.room_type_name}<div className="hd-muted hd-small">{room.room_type_code}</div></td>
                    <td className="hd-right">¥{room.base_price_display}</td>
                    <td className="hd-right">{room.capacity}</td>
                    <td><RoomStatusTag status={room.status} label={room.status_label} /></td>
                    <td className="hd-small hd-muted">{room.note ?? "—"}</td>
                    <td className="hd-right hd-inline hd-inline--gap">
                      {room.status === "CLEANING" && (
                        <button className="hd-btn hd-btn--sm" onClick={() => quickStatus(room, "VACANT")}>打扫完成</button>
                      )}
                      {room.status === "VACANT" && (
                        <button className="hd-btn hd-btn--sm hd-btn--ghost" onClick={() => quickStatus(room, "MAINTENANCE")}>报修</button>
                      )}
                      {room.status === "MAINTENANCE" && (
                        <button className="hd-btn hd-btn--sm" onClick={() => quickStatus(room, "VACANT")}>修好</button>
                      )}
                      <button className="hd-btn hd-btn--sm" onClick={() => setEditing(room)}>编辑</button>
                      <button className="hd-btn hd-btn--sm hd-btn--ghost" onClick={() => remove(room)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </AsyncState>
        </div>
      </div>

      <RoomDialog
        target={editing}
        types={types.data ?? []}
        onClose={() => setEditing(null)}
        onSaved={(msg) => {
          setEditing(null);
          setNotice({ kind: "ok", text: msg });
          rooms.reload();
        }}
      />
    </div>
  );
}

function RoomDialog({
  target,
  types,
  onClose,
  onSaved,
}: {
  target: Room | "new" | null;
  types: RoomType[];
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const isNew = target === "new";
  const room = target && target !== "new" ? target : null;

  const [roomNo, setRoomNo] = useState("");
  const [typeId, setTypeId] = useState<number | "">("");
  const [floor, setFloor] = useState("8");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 每次打开时把值填成"当前房间"或空表单
  const key = isNew ? "new" : room?.id ?? "closed";
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) {
    setLastKey(key);
    setRoomNo(room?.room_no ?? "");
    setTypeId(room?.room_type_id ?? "");
    setFloor(String(room?.floor ?? 8));
    setNote(room?.note ?? "");
    setError(null);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (isNew) {
        await api.rooms.create({
          room_no: roomNo.trim().toUpperCase(),
          room_type_id: Number(typeId),
          floor: Number(floor),
          note: note.trim() || null,
        });
        onSaved(`房间 ${roomNo} 已创建`);
      } else if (room) {
        await api.rooms.update(room.id, {
          room_type_id: Number(typeId),
          floor: Number(floor),
          note: note.trim() || null,
        });
        onSaved(`房间 ${room.room_no} 已更新`);
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={target !== null}
      onClose={onClose}
      size="sm"
      title={isNew ? "新增房间" : `编辑房间 ${room?.room_no ?? ""}`}
      footer={
        <>
          <span className="hd-spacer" />
          <button className="hd-btn" onClick={onClose} disabled={busy}>取消</button>
          <button className="hd-btn hd-btn--primary" onClick={save} disabled={busy || !typeId || (isNew && !roomNo.trim())}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      {error && <Notice kind="error" text={error} onClose={() => setError(null)} />}
      <div className="hd-form">
        <div className="hd-field">
          <label className="hd-label">房号 *</label>
          <input className="hd-input" value={roomNo} onChange={(e) => setRoomNo(e.target.value)} disabled={!isNew} placeholder="如 8401" />
          {!isNew && <div className="hd-help">房号是历史单据的锚点，建好后不允许改</div>}
        </div>
        <div className="hd-field">
          <label className="hd-label">楼层 *</label>
          <input className="hd-input" type="number" value={floor} onChange={(e) => setFloor(e.target.value)} />
        </div>
        <div className="hd-field hd-field--full">
          <label className="hd-label">房型 *</label>
          <select className="hd-select" value={typeId} onChange={(e) => setTypeId(Number(e.target.value))}>
            <option value="">选择房型…</option>
            {types.map((t) => (
              <option key={t.id} value={t.id}>{t.name} · ¥{t.base_price_display} · 可住 {t.capacity} 人</option>
            ))}
          </select>
        </div>
        <div className="hd-field hd-field--full">
          <label className="hd-label">备注</label>
          <input className="hd-input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="如 靠电梯 / 空调检修" />
        </div>
      </div>
    </Modal>
  );
}
