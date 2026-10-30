import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { Room, StayDetail } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { CheckinDialog } from "../components/CheckinDialog";
import { StayPanel } from "../components/StayPanel";
import { RoomStatusTag } from "../components/Tags";
import { useAsync } from "../hooks/useAsync";

/**
 * 前台工作台 = 房态看板。
 *
 * 这是前台开机后停留最久的页面，所以它只做一件事：**让 20 间房的状态一眼可读**。
 * 房卡上的信息顺序是"房号 → 房型价格 → 谁在住/离店日"，因为前台被问得最多的
 * 就是"这间房空不空、多少钱、住到几号"。
 *
 * 点空房 = 直接办入住；点在住 = 打开这一单。没有第三步。
 */
export function FrontDesk() {
  const board = useAsync(() => api.rooms.board(), []);

  const [checkinRoom, setCheckinRoom] = useState<Room | null>(null);
  const [panelStayId, setPanelStayId] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "warn" | "error"; text: string } | null>(null);

  function refreshAll() {
    board.reload();
  }

  async function quickStatus(room: Room, status: "VACANT" | "MAINTENANCE") {
    try {
      await api.rooms.setStatus(room.id, status);
      setNotice({
        kind: "ok",
        text: status === "VACANT" ? `${room.room_no} 已置为空闲` : `${room.room_no} 已报修`,
      });
      refreshAll();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    }
  }

  function afterCheckin(stay: StayDetail) {
    setCheckinRoom(null);
    setNotice({ kind: "ok", text: `${stay.guest_name} 已入住 ${stay.room_no}，单号 ${stay.stay_no}` });
    refreshAll();
  }

  const counts = board.data?.counts;

  return (
    <div className="hd-stack">
      {notice && <Notice kind={notice.kind} text={notice.text} onClose={() => setNotice(null)} />}

      <div className="hd-page-head">
        <div>
          <h1 className="hd-h1">{board.data?.hotel_name ?? "房态看板"}</h1>
          <div className="hd-muted">
            {board.data ? `共 ${board.data.total_rooms} 间房 · 更新于 ${board.data.generated_at.slice(11, 16)}` : "加载中…"}
          </div>
        </div>
        <div className="hd-inline hd-inline--gap">
          {counts && (
            <>
              <span className="hd-chip hd-chip--ok">空闲 {counts.VACANT}</span>
              <span className="hd-chip hd-chip--brand">在住 {counts.OCCUPIED}</span>
              <span className="hd-chip hd-chip--warn">待清扫 {counts.CLEANING}</span>
              <span className="hd-chip hd-chip--danger">维修 {counts.MAINTENANCE}</span>
            </>
          )}
        </div>
      </div>

      <AsyncState loading={board.loading} error={board.error} onRetry={board.reload}>
        <div className="hd-stack">
          {board.data?.floors.map((floor) => (
            <section key={floor.floor} className="hd-card">
              <div className="hd-card__head">
                <h2 className="hd-card__title">{floor.floor} 层</h2>
                <span className="hd-muted">{floor.rooms.length} 间</span>
              </div>
              <div className="hd-card__body">
                <div className="hd-rooms">
                  {floor.rooms.map((room) => (
                    <RoomCard
                      key={room.id}
                      room={room}
                      onCheckin={() => setCheckinRoom(room)}
                      onOpenStay={() => room.current_stay && setPanelStayId(room.current_stay.id)}
                      onCleanDone={() => quickStatus(room, "VACANT")}
                      onReportBroken={() => quickStatus(room, "MAINTENANCE")}
                    />
                  ))}
                </div>
              </div>
            </section>
          ))}
        </div>
      </AsyncState>

      <CheckinDialog
        open={checkinRoom !== null}
        initialRoom={checkinRoom}
        onClose={() => setCheckinRoom(null)}
        onDone={afterCheckin}
      />

      <StayPanel
        open={panelStayId !== null}
        stayId={panelStayId}
        onClose={() => setPanelStayId(null)}
        onChanged={refreshAll}
      />
    </div>
  );
}

function RoomCard({
  room,
  onCheckin,
  onOpenStay,
  onCleanDone,
  onReportBroken,
}: {
  room: Room;
  onCheckin: () => void;
  onOpenStay: () => void;
  onCleanDone: () => void;
  onReportBroken: () => void;
}) {
  const stay = room.current_stay;
  const clickable = room.status === "VACANT" || (room.status === "OCCUPIED" && stay);

  return (
    <div
      className={`hd-room hd-room--${room.status.toLowerCase()}${clickable ? " is-clickable" : ""}`}
      onClick={() => {
        if (room.status === "VACANT") onCheckin();
        else if (room.status === "OCCUPIED" && stay) onOpenStay();
      }}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={(e) => {
        if (!clickable) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          room.status === "VACANT" ? onCheckin() : onOpenStay();
        }
      }}
    >
      <div className="hd-room__top">
        <span className="hd-room__no">{room.room_no}</span>
        <RoomStatusTag status={room.status} label={room.status_label} />
      </div>
      <div className="hd-room__type">
        {room.room_type_name} · ¥{room.base_price_display}
      </div>

      {stay ? (
        <div className="hd-room__guest">
          <div className="hd-room__guest-name">
            {stay.guest_name}
            {stay.overdue && <span className="hd-tag hd-tag--danger" style={{ marginLeft: 6 }}>逾期</span>}
          </div>
          <div className="hd-room__meta">离店 {stay.expected_checkout_date.slice(5)}</div>
        </div>
      ) : (
        <div className="hd-room__meta">
          {room.status === "VACANT" ? "点击办理入住" : room.status === "CLEANING" ? "打扫完成后标记为空闲" : room.note || "暂不可用"}
        </div>
      )}

      {room.status === "CLEANING" && (
        <button
          className="hd-btn hd-btn--sm hd-btn--block"
          onClick={(e) => {
            e.stopPropagation();
            onCleanDone();
          }}
        >
          打扫完成
        </button>
      )}
      {room.status === "VACANT" && (
        <button
          className="hd-btn hd-btn--sm hd-btn--block hd-btn--ghost"
          onClick={(e) => {
            e.stopPropagation();
            onReportBroken();
          }}
        >
          报修停用
        </button>
      )}
      {room.status === "MAINTENANCE" && (
        <button
          className="hd-btn hd-btn--sm hd-btn--block"
          onClick={(e) => {
            e.stopPropagation();
            onCleanDone();
          }}
        >
          维修完成
        </button>
      )}
    </div>
  );
}
