import type { Bill, RoomStatus, StayStatus } from "../api/types";

const ROOM_CLASS: Record<RoomStatus, string> = {
  VACANT: "hd-tag--ok",
  OCCUPIED: "hd-tag--brand",
  CLEANING: "hd-tag--warn",
  MAINTENANCE: "hd-tag--danger",
};

export function RoomStatusTag({ status, label }: { status: RoomStatus; label: string }) {
  return (
    <span className={`hd-tag ${ROOM_CLASS[status]}`}>
      <span className={`hd-dot ${ROOM_CLASS[status]}`} style={{ marginRight: 5 }} />
      {label}
    </span>
  );
}

const STAY_CLASS: Record<StayStatus, string> = {
  IN_HOUSE: "hd-tag--brand",
  CHECKED_OUT: "hd-tag--muted",
  CANCELLED: "hd-tag--warn",
};

export function StayStatusTag({ status, label }: { status: StayStatus; label: string }) {
  return <span className={`hd-tag ${STAY_CLASS[status]}`}>{label}</span>;
}

/** 结账方向：还需收款（红） / 需退客人（绿） / 已结清（灰）。 */
export function SettlementTag({ bill }: { bill: Bill }) {
  const cls =
    bill.settlement === "DUE" ? "hd-tag--danger" : bill.settlement === "REFUND" ? "hd-tag--ok" : "hd-tag--muted";
  return (
    <span className={`hd-tag ${cls}`}>
      {bill.settlement_label} ¥{bill.balance_display}
    </span>
  );
}

export function Tag({ children, kind = "muted" }: { children: React.ReactNode; kind?: string }) {
  return <span className={`hd-tag hd-tag--${kind}`}>{children}</span>;
}
