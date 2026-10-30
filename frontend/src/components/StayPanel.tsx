import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import type { ChargeCategory, Room, RoomCard, StayDetail } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { addDaysISO, dateOnly, shortDateTime, todayISO } from "../utils/format";
import { AsyncState, Notice } from "./AsyncState";
import { Modal } from "./Modal";
import { SettlementTag, StayStatusTag } from "./Tags";

type Action = null | "charge" | "extend" | "room" | "checkout";

const CHARGE_OPTIONS: { value: ChargeCategory; label: string }[] = [
  { value: "FOOD", label: "餐饮" },
  { value: "MINIBAR", label: "迷你吧" },
  { value: "LAUNDRY", label: "洗衣" },
  { value: "EXTRA_BED", label: "加床" },
  { value: "DAMAGE", label: "赔偿" },
  { value: "OTHER", label: "其他" },
];

/** 入住单详情 + 所有操作入口。
 *
 * 一个弹窗装下"看"和"改"：前台的场景是"客人站在柜台前"，让他关掉详情、
 * 去另一个页面找单据、再点按钮，等于让他当着客人面走三遍流程。
 */
export function StayPanel({
  open,
  stayId,
  onClose,
  onChanged,
}: {
  open: boolean;
  stayId: number | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { data, error, loading, reload } = useAsync<StayDetail | null>(
    () => (stayId ? api.stays.get(stayId) : Promise.resolve(null)),
    [stayId, open],
  );

  const [action, setAction] = useState<Action>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  // 各动作的字段
  const [category, setCategory] = useState<ChargeCategory>("FOOD");
  const [chargeName, setChargeName] = useState("");
  const [chargeAmount, setChargeAmount] = useState("");
  const [chargeQty, setChargeQty] = useState(1);
  const [newCheckout, setNewCheckout] = useState(addDaysISO(todayISO(), 1));
  const [vacantRooms, setVacantRooms] = useState<Room[]>([]);
  const [targetRoom, setTargetRoom] = useState<number | "">("");
  const [newRate, setNewRate] = useState("");
  const [settleNights, setSettleNights] = useState("");
  const [cardNo, setCardNo] = useState("");

  useEffect(() => {
    if (!open) {
      setAction(null);
      setNotice(null);
      return;
    }
    setAction(null);
    setNotice(null);
    setChargeName("");
    setChargeAmount("");
    setChargeQty(1);
    setTargetRoom("");
    setNewRate("");
    setSettleNights("");
    setCardNo("");
  }, [open, stayId]);

  useEffect(() => {
    if (data) setNewCheckout(addDaysISO(data.expected_checkout_date, 1));
  }, [data]);

  async function openRoomPicker() {
    setAction("room");
    try {
      setVacantRooms(await api.rooms.list({ status: "VACANT" }));
    } catch {
      setVacantRooms([]);
    }
  }

  async function run(fn: () => Promise<StayDetail>, okText: string) {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      setNotice({ kind: "ok", text: okText });
      setAction(null);
      reload();
      onChanged();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    } finally {
      setBusy(false);
    }
  }

  /** 发房卡。USB 键盘仿真读写器会把卡号整串敲进输入框并以回车结尾，回车即提交。 */
  async function submitCard() {
    const no = cardNo.trim();
    if (!no || !data) return;
    setBusy(true);
    setNotice(null);
    try {
      const cards = await api.stays.issueCard(data.id, no);
      const issued = cards.find((c) => c.status === "ACTIVE" && c.card_no === no.toUpperCase());
      setNotice({ kind: "ok", text: `房卡 ${issued?.card_no ?? no.toUpperCase()} 已发放` });
      setCardNo("");
      reload();
      onChanged();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    } finally {
      setBusy(false);
    }
  }

  async function revokeCard(card: RoomCard) {
    if (!data) return;
    setBusy(true);
    setNotice(null);
    try {
      await api.cards.revoke(card.id, undefined, "前台手动退卡");
      setNotice({ kind: "ok", text: `房卡 ${card.card_no} 已收回` });
      reload();
      onChanged();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    } finally {
      setBusy(false);
    }
  }

  const title = data ? `${data.guest_name} · ${data.room_no}` : "入住单详情";

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={title}
      subtitle={data ? `${data.stay_no} · ${data.room_type_name} · ¥${data.room_rate_display}/晚` : undefined}
    >
      <AsyncState loading={loading} error={error} onRetry={reload} empty={!data}>
        {data && (
          <>
            {notice && (
              <Notice kind={notice.kind === "ok" ? "ok" : "error"} text={notice.text} onClose={() => setNotice(null)} />
            )}

            <div className="hd-inline hd-inline--gap" style={{ marginBottom: 12 }}>
              <StayStatusTag status={data.status} label={data.status_label} />
              {data.overdue && <span className="hd-tag hd-tag--danger">已逾期未退</span>}
              <SettlementTag bill={data.bill} />
              {data.guest_phone && <span className="hd-muted">电话 {data.guest_phone}</span>}
              <span className="hd-muted">证件 {data.id_no_masked}</span>
            </div>

            <div className="hd-kv">
              <div><span>入住</span><b>{shortDateTime(data.checkin_at)}</b></div>
              <div><span>预计离店</span><b>{data.expected_checkout_date}</b></div>
              <div><span>实际退房</span><b>{data.checkout_at ? shortDateTime(data.checkout_at) : "—"}</b></div>
              <div><span>间夜</span><b>{data.nights}</b></div>
              <div><span>人数</span><b>{data.adults} 成人{data.children > 0 ? ` · ${data.children} 儿童` : ""}</b></div>
              <div><span>押金</span><b>¥{data.deposit_display}</b></div>
            </div>

            <div className="hd-bill">
              <div className="hd-bill__row">
                <span>房费（{data.bill.nights} 间夜 × ¥{data.room_rate_display}）</span>
                <b>¥{data.bill.room_fee_display}</b>
              </div>
              <div className="hd-bill__row">
                <span>杂费合计</span>
                <b>¥{data.bill.charges_total_display}</b>
              </div>
              <div className="hd-bill__row hd-bill__row--total">
                <span>应收合计</span>
                <b>¥{data.bill.total_display}</b>
              </div>
              <div className="hd-bill__row">
                <span>已收押金</span>
                <b>− ¥{data.bill.deposit_display}</b>
              </div>
              <div className="hd-bill__row hd-bill__row--total">
                <span>{data.bill.settlement_label}</span>
                <b className={data.bill.settlement === "DUE" ? "hd-money--due" : data.bill.settlement === "REFUND" ? "hd-money--refund" : ""}>
                  ¥{data.bill.balance_display}
                </b>
              </div>
              <div className="hd-help">未退房的账单按「当前登记间夜」预估；退房时按实际退房日结算。</div>
            </div>

            {data.status === "IN_HOUSE" && (
              <div className="hd-actions">
                <button className="hd-btn hd-btn--sm" onClick={() => setAction(action === "charge" ? null : "charge")}>
                  加收费用
                </button>
                <button className="hd-btn hd-btn--sm" onClick={() => setAction(action === "extend" ? null : "extend")}>
                  续住
                </button>
                <button className="hd-btn hd-btn--sm" onClick={openRoomPicker}>
                  换房
                </button>
                <button className="hd-btn hd-btn--sm hd-btn--primary" onClick={() => setAction(action === "checkout" ? null : "checkout")}>
                  退房结账
                </button>
                <span className="hd-spacer" />
                <button
                  className="hd-btn hd-btn--sm hd-btn--ghost"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm("确认撤销这张入住单？房间会直接回到空闲，且不留入住记录。")) return;
                    run(() => api.stays.cancel(data.id), "已撤销入住，房间恢复空闲");
                  }}
                >
                  撤销入住
                </button>
              </div>
            )}

            {action === "charge" && (
              <div className="hd-subpanel">
                <div className="hd-subpanel__title">加收费用</div>
                <div className="hd-form">
                  <div className="hd-field">
                    <label className="hd-label">类别</label>
                    <select className="hd-select" value={category} onChange={(e) => setCategory(e.target.value as ChargeCategory)}>
                      {CHARGE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="hd-field">
                    <label className="hd-label">名称 *</label>
                    <input className="hd-input" value={chargeName} onChange={(e) => setChargeName(e.target.value)} placeholder="如 客房送餐" />
                  </div>
                  <div className="hd-field">
                    <label className="hd-label">单价（元）*</label>
                    <input className="hd-input" value={chargeAmount} onChange={(e) => setChargeAmount(e.target.value)} inputMode="decimal" placeholder="88.00" />
                  </div>
                  <div className="hd-field">
                    <label className="hd-label">数量</label>
                    <input className="hd-input" type="number" min={1} max={99} value={chargeQty} onChange={(e) => setChargeQty(Number(e.target.value))} />
                  </div>
                </div>
                <button
                  className="hd-btn hd-btn--primary hd-btn--sm"
                  disabled={busy || !chargeName.trim() || !chargeAmount.trim()}
                  onClick={() =>
                    run(
                      () => api.stays.addCharge(data.id, { category, name: chargeName.trim(), amount: chargeAmount.trim(), quantity: chargeQty }),
                      "已入账，账单已更新",
                    )
                  }
                >
                  {busy ? "提交中…" : "确认入账"}
                </button>
              </div>
            )}

            {action === "extend" && (
              <div className="hd-subpanel">
                <div className="hd-subpanel__title">续住</div>
                <div className="hd-form">
                  <div className="hd-field">
                    <label className="hd-label">新的预计离店日</label>
                    <input className="hd-input" type="date" value={newCheckout} min={addDaysISO(data.expected_checkout_date, 1)} onChange={(e) => setNewCheckout(e.target.value)} />
                    <div className="hd-help">当前：{data.expected_checkout_date}，必须往后延</div>
                  </div>
                </div>
                <button
                  className="hd-btn hd-btn--primary hd-btn--sm"
                  disabled={busy || newCheckout <= data.expected_checkout_date}
                  onClick={() => run(() => api.stays.extend(data.id, newCheckout), `已续住至 ${newCheckout}`)}
                >
                  {busy ? "提交中…" : "确认续住"}
                </button>
              </div>
            )}

            {action === "room" && (
              <div className="hd-subpanel">
                <div className="hd-subpanel__title">换房</div>
                <div className="hd-form">
                  <div className="hd-field">
                    <label className="hd-label">目标房间</label>
                    <select className="hd-select" value={targetRoom} onChange={(e) => setTargetRoom(e.target.value ? Number(e.target.value) : "")}>
                      <option value="">选择一间空房…</option>
                      {vacantRooms.map((r) => (
                        <option key={r.id} value={r.id}>{r.room_no} · {r.room_type_name} · ¥{r.base_price_display}</option>
                      ))}
                    </select>
                    {vacantRooms.length === 0 && <div className="hd-help hd-help--warn">没有空房可换</div>}
                  </div>
                  <div className="hd-field">
                    <label className="hd-label">新房价（元/晚）</label>
                    <input className="hd-input" value={newRate} onChange={(e) => setNewRate(e.target.value)} placeholder={`留空 = 沿用 ¥${data.room_rate_display}`} inputMode="decimal" />
                  </div>
                </div>
                <button
                  className="hd-btn hd-btn--primary hd-btn--sm"
                  disabled={busy || targetRoom === ""}
                  onClick={() =>
                    run(
                      () => api.stays.changeRoom(data.id, Number(targetRoom), newRate.trim() || undefined),
                      "已换房，原房间进入待清扫",
                    )
                  }
                >
                  {busy ? "提交中…" : "确认换房"}
                </button>
              </div>
            )}

            {action === "checkout" && (
              <div className="hd-subpanel">
                <div className="hd-subpanel__title">退房结账</div>
                <div className="hd-form">
                  <div className="hd-field">
                    <label className="hd-label">结算间夜</label>
                    <input className="hd-input" type="number" min={1} value={settleNights} onChange={(e) => setSettleNights(e.target.value)} placeholder={`留空 = 按实际（${data.nights}）`} />
                    <div className="hd-help">提前退房但仍按原预订夜数收费时，在这里填夜数</div>
                  </div>
                </div>
                <button
                  className="hd-btn hd-btn--primary hd-btn--sm"
                  disabled={busy}
                  onClick={() =>
                    run(
                      () => api.stays.checkout(data.id, settleNights.trim() ? Number(settleNights) : undefined),
                      "已退房，房间进入待清扫",
                    )
                  }
                >
                  {busy ? "提交中…" : "确认退房并出账"}
                </button>
              </div>
            )}

            <h3 className="hd-section-title">账单明细</h3>
            <table className="hd-table">
              <thead>
                <tr>
                  <th>类别</th>
                  <th>项目</th>
                  <th className="hd-right">金额</th>
                  <th className="hd-right">数量</th>
                  <th className="hd-right">小计</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {data.charges.length === 0 && (
                  <tr><td colSpan={6} className="hd-table__empty">还没有任何费用（房费在退房时自动入账）</td></tr>
                )}
                {data.charges.map((c) => (
                  <tr key={c.id}>
                    <td>{c.category_label}</td>
                    <td>{c.name}</td>
                    <td className="hd-right">¥{c.amount_display}</td>
                    <td className="hd-right">{c.quantity}</td>
                    <td className="hd-right">¥{c.subtotal_display}</td>
                    <td className="hd-muted">{shortDateTime(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3 className="hd-section-title">房卡</h3>
            {data.status === "IN_HOUSE" && (
              <div className="hd-form" style={{ marginBottom: 8 }}>
                <div className="hd-field hd-field--full">
                  <label className="hd-label">发卡：刷卡或输入卡号后回车</label>
                  <input
                    className="hd-input"
                    value={cardNo}
                    autoFocus
                    disabled={busy}
                    placeholder="把光标点到这里再刷卡（读写器会自动敲入卡号并回车）"
                    onChange={(e) => setCardNo(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void submitCard();
                      }
                    }}
                  />
                  <div className="hd-help">USB 键盘仿真读写器免驱动；回车即发卡，卡号自动归一化（大写、去分隔符）</div>
                </div>
                <button
                  className="hd-btn hd-btn--primary hd-btn--sm"
                  disabled={busy || !cardNo.trim()}
                  onClick={() => void submitCard()}
                >
                  {busy ? "处理中…" : "发卡"}
                </button>
              </div>
            )}
            {data.cards.length === 0 ? (
              <div className="hd-empty">
                {data.status === "IN_HOUSE" ? "还没发卡" : "没有房卡记录"}
              </div>
            ) : (
              <table className="hd-table">
                <thead>
                  <tr>
                    <th>卡号</th>
                    <th>房号</th>
                    <th>状态</th>
                    <th>发卡</th>
                    <th>退卡</th>
                    <th className="hd-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cards.map((c) => (
                    <tr key={c.id}>
                      <td><b>{c.card_no}</b></td>
                      <td>{c.room_no}</td>
                      <td>
                        <span className={`hd-tag ${c.status === "ACTIVE" ? "hd-tag--ok" : "hd-tag--muted"}`}>
                          {c.status_label}
                        </span>
                      </td>
                      <td className="hd-muted">{shortDateTime(c.issued_at)}{c.issued_by ? ` · ${c.issued_by}` : ""}</td>
                      <td className="hd-muted">
                        {c.revoked_at
                          ? `${shortDateTime(c.revoked_at)}${c.revoked_by ? ` · ${c.revoked_by}` : ""}${c.revoke_reason ? `（${c.revoke_reason}）` : ""}`
                          : "—"}
                      </td>
                      <td className="hd-right">
                        {c.status === "ACTIVE" && data.status === "IN_HOUSE" && (
                          <button
                            className="hd-btn hd-btn--sm hd-btn--ghost"
                            disabled={busy}
                            onClick={() => void revokeCard(c)}
                          >
                            退卡
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {data.status === "IN_HOUSE" && (
              <div className="hd-help">退房结账时会自动收回全部在用房卡，不需要手工逐张退。</div>
            )}

            <h3 className="hd-section-title">操作留痕</h3>
            <ol className="hd-timeline">
              {data.events.map((e) => (
                <li key={e.id} className="hd-timeline__item">
                  <span className="hd-timeline__dot" />
                  <div className="hd-timeline__body">
                    <div className="hd-timeline__head">
                      <b>{e.type_label}</b>
                      <span className="hd-muted">{shortDateTime(e.created_at)}</span>
                      {e.amount_cents > 0 && <span className="hd-tag hd-tag--muted">¥{e.amount_display}</span>}
                    </div>
                    {(e.from_value || e.to_value) && (
                      <div className="hd-muted hd-small">
                        {e.from_value ?? "—"} → {e.to_value ?? "—"}
                      </div>
                    )}
                    {e.remark && <div className="hd-small">{e.remark}</div>}
                    {e.operator && <div className="hd-muted hd-small">操作员：{e.operator}</div>}
                  </div>
                </li>
              ))}
            </ol>

            <div className="hd-help" style={{ marginTop: 12 }}>
              制单 {dateOnly(data.created_at)} · 最后更新 {shortDateTime(data.updated_at)}
              {data.remark ? ` · 备注：${data.remark}` : ""}
            </div>
          </>
        )}
      </AsyncState>
    </Modal>
  );
}
