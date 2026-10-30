import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type { GuestBrief, Room, StayDetail } from "../api/types";
import { addDaysISO, mockIdNo, nightsBetween, todayISO } from "../utils/format";
import { AsyncState } from "./AsyncState";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
  onDone: (stay: StayDetail) => void;
  /** 从房卡点进来时预选房间 */
  initialRoom?: Room | null;
}

/**
 * 入住登记弹窗 —— 全系统最热的表单。
 *
 * 设计取舍：
 *   · **客人二选一**（老客搜索 / 新客录入）放在最上面。前台 80% 的情况是
 *     "客人递身份证"，所以新客表单默认展开，老客搜索是次要入口。
 *   · 房价、押金**留空即用默认值**（房型挂牌价 / 参数里的默认押金），
 *     输入框里放的是提示语而不是预填数字 —— 预填了反而让人以为必须改。
 *   · 预计离店日默认明天。当天来当天走要按 1 个间夜算，日期必须填次日，
 *     这一点后端会拦，这里把默认值设对，减少一次报错往返。
 *   · 提交按钮旁边实时显示"预计房费"，输错一位数能立刻看出来。
 */
export function CheckinDialog({ open, onClose, onDone, initialRoom }: Props) {
  const [vacantRooms, setVacantRooms] = useState<Room[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);

  const [mode, setMode] = useState<"new" | "existing">("new");
  const [roomId, setRoomId] = useState<number | "">("");
  const [checkinDate, setCheckinDate] = useState(todayISO());
  const [checkoutDate, setCheckoutDate] = useState(addDaysISO(todayISO(), 1));
  const [guestId, setGuestId] = useState<number | "">("");
  const [guestKeyword, setGuestKeyword] = useState("");
  const [guestHits, setGuestHits] = useState<GuestBrief[]>([]);
  const [guestName, setGuestName] = useState("");
  const [idNo, setIdNo] = useState("");
  const [phone, setPhone] = useState("");
  const [gender, setGender] = useState<"MALE" | "FEMALE" | "UNKNOWN">("UNKNOWN");
  const [idType, setIdType] = useState<"ID_CARD" | "PASSPORT" | "HK_MACAO" | "TAIWAN" | "OTHER">("ID_CARD");
  const [rate, setRate] = useState("");
  const [deposit, setDeposit] = useState("");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [remark, setRemark] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // 每次打开都重置：上次的客人信息留在表单里是最容易出的事故（张冠李戴）
  useEffect(() => {
    if (!open) return;
    setMode("new");
    setRoomId(initialRoom ? initialRoom.id : "");
    setCheckinDate(todayISO());
    setCheckoutDate(addDaysISO(todayISO(), 1));
    setGuestId("");
    setGuestKeyword("");
    setGuestHits([]);
    setGuestName("");
    setIdNo(mockIdNo()); // 模拟系统默认给一个 6 位虚拟证件号，前台不用手敲
    setPhone("");
    setGender("UNKNOWN");
    setIdType("ID_CARD");
    setRate("");
    setDeposit("");
    setAdults(1);
    setChildren(0);
    setRemark("");
    setError(null);

    setVacantRooms(null);
    setLoadError(null);
    api.rooms
      .list({ status: "VACANT" })
      .then(setVacantRooms)
      .catch((err: ApiError) => setLoadError(err));
  }, [open, initialRoom]);

  // 从"老客"切回"新客"时补一个虚拟号，避免空着手提交
  useEffect(() => {
    if (open && mode === "new" && idType === "ID_CARD" && !idNo.trim()) {
      setIdNo(mockIdNo());
    }
  }, [open, mode, idType, idNo]);

  useEffect(() => {
    if (!open || mode !== "existing") return;
    const keyword = guestKeyword.trim();
    if (!keyword) {
      setGuestHits([]);
      return;
    }
    let alive = true;
    const timer = window.setTimeout(() => {
      api.guests
        .list({ keyword, page_size: 6 })
        .then((page) => alive && setGuestHits(page.items))
        .catch(() => alive && setGuestHits([]));
    }, 250); // 防抖：前台打字快，不必每个按键都发请求
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [open, mode, guestKeyword]);

  const selectedRoom = useMemo(
    () => vacantRooms?.find((r) => r.id === roomId) ?? initialRoom ?? null,
    [vacantRooms, roomId, initialRoom],
  );

  const nights = nightsBetween(checkinDate, checkoutDate);
  const effectiveRate = rate.trim() ? Number(rate) : Number(selectedRoom?.base_price_display ?? 0);
  const estimate = Number.isFinite(nights) && nights > 0 ? nights * effectiveRate : 0;

  const canSubmit =
    roomId !== "" &&
    nights > 0 &&
    !submitting &&
    (mode === "existing" ? guestId !== "" : guestName.trim() !== "" && idNo.trim() !== "");

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const body = {
        room_id: Number(roomId),
        expected_checkout_date: checkoutDate,
        checkin_at: `${checkinDate} 14:00`,
        ...(rate.trim() ? { room_rate: rate.trim() } : {}),
        ...(deposit.trim() ? { deposit: deposit.trim() } : {}),
        adults,
        children,
        ...(remark.trim() ? { remark: remark.trim() } : {}),
        ...(mode === "existing"
          ? { guest_id: Number(guestId) }
          : {
              guest: {
                name: guestName.trim(),
                id_type: idType,
                id_no: idNo.trim(),
                phone: phone.trim() || null,
                gender,
              },
            }),
      };
      const stay = await api.stays.checkin(body);
      onDone(stay);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="入住登记"
      subtitle={selectedRoom ? `房间 ${selectedRoom.room_no} · ${selectedRoom.room_type_name}` : "请选择房间"}
      footer={
        <>
          <span className="hd-modal__foot-hint">
            {nights > 0 ? `${nights} 间夜 · 预计房费 ¥${estimate.toFixed(2)}` : "离店日期需晚于入住日期"}
          </span>
          <span className="hd-spacer" />
          <button className="hd-btn" onClick={onClose} disabled={submitting}>
            取消
          </button>
          <button className="hd-btn hd-btn--primary" onClick={submit} disabled={!canSubmit}>
            {submitting ? "提交中…" : "确认入住"}
          </button>
        </>
      }
    >
      <AsyncState loading={vacantRooms === null && !loadError} error={loadError}>
        <div className="hd-form">
          <div className="hd-field hd-field--full">
            <label className="hd-label">房间</label>
            <select
              className="hd-select"
              value={roomId}
              onChange={(e) => setRoomId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">选择一间空房…</option>
              {(vacantRooms ?? []).map((room) => (
                <option key={room.id} value={room.id}>
                  {room.room_no} · {room.room_type_name} · ¥{room.base_price_display} · 可住 {room.capacity} 人
                </option>
              ))}
            </select>
            {(vacantRooms ?? []).length === 0 && (
              <div className="hd-help hd-help--warn">当前没有空房。先把待清扫的房间标记为「空闲」，或换房腾出来。</div>
            )}
          </div>

          <div className="hd-field">
            <label className="hd-label">入住日期</label>
            <input
              className="hd-input"
              type="date"
              value={checkinDate}
              onChange={(e) => {
                setCheckinDate(e.target.value);
                if (e.target.value >= checkoutDate) setCheckoutDate(addDaysISO(e.target.value, 1));
              }}
            />
          </div>

          <div className="hd-field">
            <label className="hd-label">预计离店</label>
            <input
              className="hd-input"
              type="date"
              value={checkoutDate}
              min={addDaysISO(checkinDate, 1)}
              onChange={(e) => setCheckoutDate(e.target.value)}
            />
            <div className="hd-help">当天入住当天走按 1 个间夜算，离店日请填次日</div>
          </div>

          <div className="hd-field hd-field--full">
            <label className="hd-label">客人</label>
            <div className="hd-seg">
              <button
                className={`hd-seg__item${mode === "new" ? " is-active" : ""}`}
                onClick={() => setMode("new")}
                type="button"
              >
                新客录入
              </button>
              <button
                className={`hd-seg__item${mode === "existing" ? " is-active" : ""}`}
                onClick={() => setMode("existing")}
                type="button"
              >
                老客查找
              </button>
            </div>
          </div>

          {mode === "new" ? (
            <>
              <div className="hd-field">
                <label className="hd-label">姓名 *</label>
                <input className="hd-input" value={guestName} onChange={(e) => setGuestName(e.target.value)} placeholder="与证件一致" />
              </div>
              <div className="hd-field">
                <label className="hd-label">证件类型</label>
                <select className="hd-select" value={idType} onChange={(e) => setIdType(e.target.value as typeof idType)}>
                  <option value="ID_CARD">身份证</option>
                  <option value="PASSPORT">护照</option>
                  <option value="HK_MACAO">港澳通行证</option>
                  <option value="TAIWAN">台湾通行证</option>
                  <option value="OTHER">其他</option>
                </select>
              </div>
              <div className="hd-field">
                <label className="hd-label">证件号 *</label>
                <input
                  className="hd-input"
                  value={idNo}
                  onChange={(e) => setIdNo(e.target.value)}
                  placeholder={idType === "ID_CARD" ? "6 位虚拟号" : "证件号"}
                  maxLength={idType === "ID_CARD" ? 6 : undefined}
                  inputMode={idType === "ID_CARD" ? "numeric" : undefined}
                />
                {idType === "ID_CARD" && (
                  <div className="hd-inline hd-inline--gap" style={{ marginTop: 2 }}>
                    <button
                      type="button"
                      className="hd-btn hd-btn--ghost hd-btn--sm"
                      onClick={() => setIdNo(mockIdNo())}
                    >
                      换一个虚拟号
                    </button>
                    <span className="hd-help" style={{ marginTop: 0 }}>本模拟系统的证件号一律是 6 位虚拟号，已自动生成，可改可换</span>
                  </div>
                )}
              </div>
              <div className="hd-field">
                <label className="hd-label">手机号</label>
                <input className="hd-input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="11 位，可不填" />
              </div>
              <div className="hd-field">
                <label className="hd-label">性别</label>
                <select className="hd-select" value={gender} onChange={(e) => setGender(e.target.value as typeof gender)}>
                  <option value="UNKNOWN">未填</option>
                  <option value="MALE">男</option>
                  <option value="FEMALE">女</option>
                </select>
              </div>
            </>
          ) : (
            <>
              <div className="hd-field hd-field--full">
                <label className="hd-label">搜索客人</label>
                <input
                  className="hd-input"
                  value={guestKeyword}
                  onChange={(e) => {
                    setGuestKeyword(e.target.value);
                    setGuestId("");
                  }}
                  placeholder="姓名 / 手机号 / 证件号"
                />
              </div>
              {guestHits.length > 0 && (
                <div className="hd-field hd-field--full">
                  <div className="hd-hit-list">
                    {guestHits.map((g) => (
                      <button
                        key={g.id}
                        type="button"
                        className={`hd-hit${guestId === g.id ? " is-active" : ""}`}
                        onClick={() => setGuestId(g.id)}
                      >
                        <span className="hd-hit__name">{g.name}</span>
                        <span className="hd-hit__meta">
                          {g.id_type_label} {g.id_no_masked}
                          {g.phone ? ` · ${g.phone}` : ""} · 住过 {g.stay_count} 次
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {guestKeyword && guestHits.length === 0 && (
                <div className="hd-field hd-field--full">
                  <div className="hd-help">没找到，切到「新客录入」建档</div>
                </div>
              )}
            </>
          )}

          <div className="hd-field">
            <label className="hd-label">房价（元/晚）</label>
            <input className="hd-input" value={rate} onChange={(e) => setRate(e.target.value)} placeholder={selectedRoom ? `留空 = ¥${selectedRoom.base_price_display}` : "留空按房型价"} inputMode="decimal" />
            <div className="hd-help">协议价/团队价在这里覆盖</div>
          </div>
          <div className="hd-field">
            <label className="hd-label">押金（元）</label>
            <input className="hd-input" value={deposit} onChange={(e) => setDeposit(e.target.value)} placeholder="留空 = 参数里的默认押金" inputMode="decimal" />
          </div>
          <div className="hd-field">
            <label className="hd-label">成人</label>
            <input className="hd-input" type="number" min={1} max={10} value={adults} onChange={(e) => setAdults(Number(e.target.value))} />
          </div>
          <div className="hd-field">
            <label className="hd-label">儿童</label>
            <input className="hd-input" type="number" min={0} max={10} value={children} onChange={(e) => setChildren(Number(e.target.value))} />
          </div>
          <div className="hd-field hd-field--full">
            <label className="hd-label">备注</label>
            <textarea className="hd-textarea" rows={2} value={remark} onChange={(e) => setRemark(e.target.value)} placeholder="如：需要安静房间 / 加婴儿床 / 团队单号" />
          </div>

          {error && <div className="hd-field hd-field--full"><div className="hd-form-error">{error.message}</div></div>}
        </div>
      </AsyncState>
    </Modal>
  );
}
