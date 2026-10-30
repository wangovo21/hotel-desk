import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { Setting } from "../api/types";
import { AsyncState, Notice } from "../components/AsyncState";
import { useAsync } from "../hooks/useAsync";
import { shortDateTime } from "../utils/format";

/** 参数的中文名与输入提示。key 必须在后端 REGISTRY 里，否则保存会 400。 */
const META: Record<string, { label: string; hint: string; unit?: string }> = {
  HOTEL_NAME: { label: "酒店名称", hint: "显示在页面标题与看板抬头" },
  DEFAULT_DEPOSIT_CENTS: { label: "默认押金", hint: "入住时留空押金则用这个值", unit: "分" },
  MAX_ROOM_RATE_CENTS: { label: "房价上限", hint: "防误输入：单间夜房价不得超过", unit: "分" },
  CHECKOUT_TIME: { label: "退房时限", hint: "仅用于前台提示，不会自动加收房费", unit: "HH:MM" },
  MAX_CHARGE_CENTS: { label: "杂费上限", hint: "单笔杂费上限", unit: "分" },
};

/**
 * 参数设置。
 *
 * 每一项都是"改了立刻生效"的运行时参数（不用重启），所以这个页面
 * 实际上是**业务规则开关**而不是配置文件编辑器。key 白名单在后端，
 * 这里只负责把值改对；写错了会收到一句中文报错，而不是静默存进去。
 */
export function Settings() {
  const settings = useAsync(() => api.settings.list(), []);
  const [editing, setEditing] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  function startEdit(row: Setting) {
    setEditing(row.key);
    setValue(row.value);
    setNotice(null);
  }

  async function save(key: string) {
    setBusy(true);
    setNotice(null);
    try {
      await api.settings.update(key, value.trim());
      setEditing(null);
      setNotice({ kind: "ok", text: "已保存，立刻生效" });
      settings.reload();
    } catch (err) {
      setNotice({ kind: "error", text: (err as ApiError).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="hd-stack">
      {notice && <Notice kind={notice.kind} text={notice.text} onClose={() => setNotice(null)} />}

      <div className="hd-toolbar">
        <span className="hd-muted">
          修改后立即生效，不需要重启服务。金额单位是「分」，例如 300 元 = 30000。
        </span>
      </div>

      <div className="hd-card">
        <div className="hd-card__body hd-card__body--flush">
          <AsyncState loading={settings.loading} error={settings.error} onRetry={settings.reload} empty={(settings.data ?? []).length === 0}>
            <table className="hd-table">
              <thead>
                <tr>
                  <th>参数</th>
                  <th>当前值</th>
                  <th>说明</th>
                  <th>更新时间</th>
                  <th className="hd-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {settings.data?.map((row) => {
                  const meta = META[row.key];
                  const isEditing = editing === row.key;
                  return (
                    <tr key={row.key}>
                      <td>
                        <b>{meta?.label ?? row.key}</b>
                        <div className="hd-muted hd-small hd-mono">{row.key}</div>
                      </td>
                      <td>
                        {isEditing ? (
                          <input
                            className="hd-input hd-input--inline"
                            value={value}
                            autoFocus
                            onChange={(e) => setValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") save(row.key);
                              if (e.key === "Escape") setEditing(null);
                            }}
                          />
                        ) : (
                          <span className="hd-mono">{row.value}</span>
                        )}
                        {meta?.unit && <span className="hd-muted hd-small"> {meta.unit}</span>}
                      </td>
                      <td className="hd-small hd-muted">{meta?.hint ?? row.description ?? "—"}</td>
                      <td className="hd-small hd-muted">{shortDateTime(row.updated_at)}</td>
                      <td className="hd-right hd-inline hd-inline--gap">
                        {isEditing ? (
                          <>
                            <button className="hd-btn hd-btn--sm hd-btn--primary" onClick={() => save(row.key)} disabled={busy}>
                              {busy ? "保存中…" : "保存"}
                            </button>
                            <button className="hd-btn hd-btn--sm" onClick={() => setEditing(null)} disabled={busy}>
                              取消
                            </button>
                          </>
                        ) : (
                          <button className="hd-btn hd-btn--sm" onClick={() => startEdit(row)}>
                            修改
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </AsyncState>
        </div>
      </div>

      <div className="hd-help">
        后台写接口需要口令（X-Admin-Token）。若这里点「保存」提示无权限，说明构建前端时没有注入
        VITE_ADMIN_TOKEN，或服务端没配 ADMIN_TOKEN。
      </div>
    </div>
  );
}
