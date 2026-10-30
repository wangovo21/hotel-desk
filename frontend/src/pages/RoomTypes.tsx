import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { RoomType } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { Modal } from "../components/Modal";
import { useAsync } from "../hooks/useAsync";

/**
 * 房型管理。
 *
 * 挂牌价在这里改，**不影响已经开出的入住单** —— 入住时房价已经快照进
 * stays.room_rate_cents。这条规则要在页面上说清楚，否则店长会以为
 * "改完价所有在住客人都该跟着变"。
 */
export function RoomTypes() {
  const types = useAsync(() => api.roomTypes.list(), []);
  const [editing, setEditing] = useState<RoomType | "new" | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  return (
    <div className="hd-stack">
      {notice && <Notice kind={notice.kind} text={notice.text} onClose={() => setNotice(null)} />}

      <div className="hd-toolbar">
        <span className="hd-muted">改挂牌价只影响新开单，在住单据按入住时的房价结算</span>
        <span className="hd-spacer" />
        <button className="hd-btn hd-btn--primary hd-btn--sm" onClick={() => setEditing("new")}>
          新增房型
        </button>
      </div>

      <AsyncState loading={types.loading} error={types.error} onRetry={types.reload} empty={(types.data ?? []).length === 0} emptyText="还没有房型">
        <div className="hd-typecards">
          {types.data?.map((t) => (
            <div key={t.id} className={`hd-typecard${t.status === "OFF" ? " is-off" : ""}`}>
              <div className="hd-typecard__head">
                <div>
                  <div className="hd-typecard__name">{t.name}</div>
                  <div className="hd-muted hd-small">{t.code} · {t.bed_type ?? "床位未填"}</div>
                </div>
                <span className={`hd-tag ${t.status === "ON" ? "hd-tag--ok" : "hd-tag--muted"}`}>{t.status_label}</span>
              </div>
              <div className="hd-typecard__price">
                ¥{t.base_price_display}
                <span className="hd-muted hd-small"> /晚</span>
              </div>
              <div className="hd-typecard__meta">
                可住 {t.capacity} 人 · 名下 {t.room_count} 间房
              </div>
              <button className="hd-btn hd-btn--sm hd-btn--block" onClick={() => setEditing(t)}>
                编辑
              </button>
            </div>
          ))}
        </div>
      </AsyncState>

      <TypeDialog
        target={editing}
        onClose={() => setEditing(null)}
        onSaved={(msg) => {
          setEditing(null);
          setNotice({ kind: "ok", text: msg });
          types.reload();
        }}
      />
    </div>
  );
}

function TypeDialog({
  target,
  onClose,
  onSaved,
}: {
  target: RoomType | "new" | null;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const isNew = target === "new";
  const type = target && target !== "new" ? target : null;

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [capacity, setCapacity] = useState("2");
  const [bedType, setBedType] = useState("");
  const [status, setStatus] = useState<"ON" | "OFF">("ON");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = isNew ? "new" : type?.id ?? "closed";
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) {
    setLastKey(key);
    setCode(type?.code ?? "");
    setName(type?.name ?? "");
    setPrice(type?.base_price_display ?? "");
    setCapacity(String(type?.capacity ?? 2));
    setBedType(type?.bed_type ?? "");
    setStatus(type?.status ?? "ON");
    setError(null);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: name.trim(),
        price: price.trim(),
        capacity: Number(capacity),
        bed_type: bedType.trim() || null,
        status,
      };
      if (isNew) {
        await api.roomTypes.create({ ...payload, code: code.trim().toUpperCase(), sort_order: 99 });
        onSaved(`房型 ${name} 已创建`);
      } else if (type) {
        await api.roomTypes.update(type.id, payload);
        onSaved(`房型 ${name} 已更新`);
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
      title={isNew ? "新增房型" : `编辑房型 ${type?.name ?? ""}`}
      footer={
        <>
          <span className="hd-spacer" />
          <button className="hd-btn" onClick={onClose} disabled={busy}>取消</button>
          <button className="hd-btn hd-btn--primary" onClick={save} disabled={busy || !name.trim() || !price.trim()}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      {error && <Notice kind="error" text={error} onClose={() => setError(null)} />}
      <div className="hd-form">
        <div className="hd-field">
          <label className="hd-label">代码 *</label>
          <input className="hd-input" value={code} onChange={(e) => setCode(e.target.value)} disabled={!isNew} placeholder="STD / SUITE" />
        </div>
        <div className="hd-field">
          <label className="hd-label">名称 *</label>
          <input className="hd-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="标准大床房" />
        </div>
        <div className="hd-field">
          <label className="hd-label">挂牌价（元/晚）*</label>
          <input className="hd-input" value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" placeholder="289.00" />
        </div>
        <div className="hd-field">
          <label className="hd-label">可住人数</label>
          <input className="hd-input" type="number" min={1} max={10} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </div>
        <div className="hd-field">
          <label className="hd-label">床型</label>
          <input className="hd-input" value={bedType} onChange={(e) => setBedType(e.target.value)} placeholder="1.8m 大床" />
        </div>
        <div className="hd-field">
          <label className="hd-label">状态</label>
          <select className="hd-select" value={status} onChange={(e) => setStatus(e.target.value as "ON" | "OFF")}>
            <option value="ON">启用</option>
            <option value="OFF">停用</option>
          </select>
          <div className="hd-help">停用后该房型不能安排入住，已有房间不受影响</div>
        </div>
      </div>
    </Modal>
  );
}
