import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, api } from "../api/client";
import type { GuestBrief, Room, RoomType, StayDetail } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { StayPanel } from "../components/StayPanel";
import { addDaysISO, mockIdNo, nightsBetween, todayISO } from "../utils/format";

/**
 * 入住登记（整页版）。
 *
 * 和弹窗版的分工：弹窗用于"在房态图上顺手点一间空房"，
 * 整页版用于"客人多、要慢慢录"的场景（团队、证件信息长、要写备注）。
 * 两者共用同一套后端校验，前端各自的表单只为各自的场景优化。
 */
export function Checkin() {
  const navigate = useNavigate();

  const [vacant, setVacant] = useState<Room[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([]);

  const [roomId, setRoomId] = useState<number | "">("");
  const [checkinDate, setCheckinDate] = useState(todayISO());
  const [checkoutDate, setCheckoutDate] = useState(addDaysISO(todayISO(), 1));
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [guestName, setGuestName] = useState("");
  const [idType, setIdType] = useState("ID_CARD");
  const [idNo, setIdNo] = useState(mockIdNo()); // 模拟系统：默认给一个 6 位虚拟证件号
  const [phone, setPhone] = useState("");
  const [gender, setGender] = useState("UNKNOWN");
  const [guestKeyword, setGuestKeyword] = useState("");
  const [guestHits, setGuestHits] = useState<GuestBrief[]>([]);
  const [guestId, setGuestId] = useState<number | "">("");
  const [rate, setRate] = useState("");
  const [deposit, setDeposit] = useState("");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [remark, setRemark] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<StayDetail | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    api.rooms
      .list({ status: "VACANT" })
      .then(setVacant)
      .catch((err: ApiError) => setLoadError(err));
    api.roomTypes.list().then(setRoomTypes).catch(() => setRoomTypes([]));
  }, []);

  useEffect(() => {
    const keyword = guestKeyword.trim();
    if (mode !== "existing" || !keyword) {
      setGuestHits([]);
      return;
    }
    let alive = true;
    const timer = window.setTimeout(() => {
      api.guests
        .list({ keyword, page_size: 6 })
        .then((p) => alive && setGuestHits(p.items))
        .catch(() => alive && setGuestHits([]));
    }, 250);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [mode, guestKeyword]);

  const room = useMemo(() => vacant?.find((r) => r.id === roomId) ?? null, [vacant, roomId]);
  const nights = nightsBetween(checkinDate, checkoutDate);
  const effRate = rate.trim() ? Number(rate) : Number(room?.base_price_display ?? 0);
  const estimate = nights > 0 && Number.isFinite(effRate) ? nights * effRate : 0;

  const canSubmit =
    room !== null &&
    nights > 0 &&
    !busy &&
    (mode === "existing" ? guestId !== "" : guestName.trim() !== "" && idNo.trim() !== "");

  function reset() {
    setResult(null);
    setRoomId("");
    setGuestName("");
    setIdNo(mockIdNo());
    setPhone("");
    setGuestKeyword("");
    setGuestId("");
    setRate("");
    setDeposit("");
    setRemark("");
    setAdults(1);
    setChildren(0);
    setError(null);
    api.rooms.list({ status: "VACANT" }).then(setVacant).catch(() => undefined);
  }

  async function submit() {
    if (!room) return;
    setBusy(true);
    setError(null);
    try {
      const stay = await api.stays.checkin({
        room_id: room.id,
        expected_checkout_date: checkoutDate,
        checkin_at: `${checkinDate} 14:00`,
        adults,
        children,
        ...(rate.trim() ? { room_rate: rate.trim() } : {}),
        ...(deposit.trim() ? { deposit: deposit.trim() } : {}),
        ...(remark.trim() ? { remark: remark.trim() } : {}),
        ...(mode === "existing"
          ? { guest_id: Number(guestId) }
          : {
              guest: {
                name: guestName.trim(),
                id_type: idType as "ID_CARD",
                id_no: idNo.trim(),
                phone: phone.trim() || null,
                gender: gender as "MALE",
              },
            }),
      });
      setResult(stay);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="hd-stack">
        <Notice kind="ok" text={`入住成功 · 单号 ${result.stay_no}`} />
        <div className="hd-card">
          <div className="hd-card__head">
            <h2 className="hd-card__title">入住凭证</h2>
            <span className="hd-tag hd-tag--brand">{result.status_label}</span>
          </div>
          <div className="hd-card__body">
            <div className="hd-kv">
              <div><span>房间</span><b>{result.room_no} · {result.room_type_name}</b></div>
              <div><span>客人</span><b>{result.guest_name}</b></div>
              <div><span>入住</span><b>{result.checkin_at.slice(0, 16)}</b></div>
              <div><span>预计离店</span><b>{result.expected_checkout_date}</b></div>
              <div><span>间夜</span><b>{result.nights}</b></div>
              <div><span>房价</span><b>¥{result.room_rate_display}/晚</b></div>
              <div><span>押金</span><b>¥{result.deposit_display}</b></div>
              <div><span>预计房费</span><b>¥{result.bill.room_fee_display}</b></div>
            </div>
            <div className="hd-actions">
              <button className="hd-btn hd-btn--primary" onClick={() => setPanelOpen(true)}>
                查看这张入住单
              </button>
              <button className="hd-btn" onClick={reset}>
                继续登记下一位
              </button>
              <button className="hd-btn hd-btn--ghost" onClick={() => navigate("/frontdesk")}>
                回房态图
              </button>
            </div>
          </div>
        </div>
        <StayPanel open={panelOpen} stayId={result.id} onClose={() => setPanelOpen(false)} onChanged={() => undefined} />
      </div>
    );
  }

  return (
    <div className="hd-stack">
      {error && <Notice kind="error" text={error.message} onClose={() => setError(null)} />}

      <AsyncState loading={vacant === null && !loadError} error={loadError}>
        <div className="hd-split">
          <section className="hd-card">
            <div className="hd-card__head">
              <h2 className="hd-card__title">1 · 选房间</h2>
              <span className="hd-muted">空闲 {vacant?.length ?? 0} 间</span>
            </div>
            <div className="hd-card__body hd-card__body--scroll">
              {(vacant ?? []).length === 0 && <div className="hd-empty">没有空房</div>}
              <div className="hd-pick-list">
                {(vacant ?? []).map((r) => (
                  <button
                    key={r.id}
                    className={`hd-pick${roomId === r.id ? " is-active" : ""}`}
                    onClick={() => setRoomId(r.id)}
                    type="button"
                  >
                    <span className="hd-pick__main">
                      <b>{r.room_no}</b>
                      <span className="hd-muted">{r.room_type_name}</span>
                    </span>
                    <span className="hd-pick__side">
                      ¥{r.base_price_display}
                      <span className="hd-muted hd-small">可住 {r.capacity} 人</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="hd-card">
            <div className="hd-card__head">
              <h2 className="hd-card__title">2 · 登记信息</h2>
              {room && <span className="hd-tag hd-tag--brand">已选 {room.room_no}</span>}
            </div>
            <div className="hd-card__body">
              <div className="hd-form">
                <div className="hd-field">
                  <label className="hd-label">入住日期</label>
                  <input className="hd-input" type="date" value={checkinDate} onChange={(e) => {
                    setCheckinDate(e.target.value);
                    if (e.target.value >= checkoutDate) setCheckoutDate(addDaysISO(e.target.value, 1));
                  }} />
                </div>
                <div className="hd-field">
                  <label className="hd-label">预计离店</label>
                  <input className="hd-input" type="date" value={checkoutDate} min={addDaysISO(checkinDate, 1)} onChange={(e) => setCheckoutDate(e.target.value)} />
                </div>

                <div className="hd-field hd-field--full">
                  <div className="hd-seg">
                    <button className={`hd-seg__item${mode === "new" ? " is-active" : ""}`} onClick={() => setMode("new")} type="button">新客录入</button>
                    <button className={`hd-seg__item${mode === "existing" ? " is-active" : ""}`} onClick={() => setMode("existing")} type="button">老客查找</button>
                  </div>
                </div>

                {mode === "new" ? (
                  <>
                    <div className="hd-field">
                      <label className="hd-label">姓名 *</label>
                      <input className="hd-input" value={guestName} onChange={(e) => setGuestName(e.target.value)} />
                    </div>
                    <div className="hd-field">
                      <label className="hd-label">证件类型</label>
                      <select className="hd-select" value={idType} onChange={(e) => setIdType(e.target.value)}>
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
                      <input className="hd-input" value={phone} onChange={(e) => setPhone(e.target.value)} />
                    </div>
                    <div className="hd-field">
                      <label className="hd-label">性别</label>
                      <select className="hd-select" value={gender} onChange={(e) => setGender(e.target.value)}>
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
                      <input className="hd-input" value={guestKeyword} onChange={(e) => { setGuestKeyword(e.target.value); setGuestId(""); }} placeholder="姓名 / 手机号 / 证件号" />
                    </div>
                    {guestHits.length > 0 && (
                      <div className="hd-field hd-field--full">
                        <div className="hd-hit-list">
                          {guestHits.map((g) => (
                            <button key={g.id} type="button" className={`hd-hit${guestId === g.id ? " is-active" : ""}`} onClick={() => setGuestId(g.id)}>
                              <span className="hd-hit__name">{g.name}</span>
                              <span className="hd-hit__meta">{g.id_type_label} {g.id_no_masked} · 住过 {g.stay_count} 次</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                <div className="hd-field">
                  <label className="hd-label">房价（元/晚）</label>
                  <input className="hd-input" value={rate} onChange={(e) => setRate(e.target.value)} placeholder={room ? `留空 = ¥${room.base_price_display}` : "留空按房型价"} inputMode="decimal" />
                </div>
                <div className="hd-field">
                  <label className="hd-label">押金（元）</label>
                  <input className="hd-input" value={deposit} onChange={(e) => setDeposit(e.target.value)} placeholder="留空 = 默认押金" inputMode="decimal" />
                </div>
                <div className="hd-field">
                  <label className="hd-label">成人</label>
                  <input className="hd-input" type="number" min={1} max={room?.capacity ?? 10} value={adults} onChange={(e) => setAdults(Number(e.target.value))} />
                </div>
                <div className="hd-field">
                  <label className="hd-label">儿童</label>
                  <input className="hd-input" type="number" min={0} max={10} value={children} onChange={(e) => setChildren(Number(e.target.value))} />
                </div>
                <div className="hd-field hd-field--full">
                  <label className="hd-label">备注</label>
                  <textarea className="hd-textarea" rows={2} value={remark} onChange={(e) => setRemark(e.target.value)} />
                </div>
              </div>

              <div className="hd-summary">
                <div><span>{nights > 0 ? `${nights} 间夜` : "日期不合法"}</span><b>¥{estimate.toFixed(2)}</b></div>
                {roomTypes.length > 0 && room && (
                  <div className="hd-help">
                    {room.room_type_name}：最多住 {room.capacity} 人
                  </div>
                )}
                <button className="hd-btn hd-btn--primary hd-btn--block" disabled={!canSubmit} onClick={submit}>
                  {busy ? "提交中…" : "确认入住"}
                </button>
              </div>
            </div>
          </section>
        </div>
      </AsyncState>
    </div>
  );
}
