import type { ReactNode } from "react";

import { ApiError } from "../api/client";

/**
 * 加载 / 出错 / 空 三种状态统一包一层。
 *
 * 错误块里**一定显示后端那句 message**：它是写给前台看的话
 * （"该房间有客人在住，请先办理退房或换房"），比"请求失败"有用得多。
 * 网络错误单独加一句排查方向 —— 这两种情况的处理动作不一样。
 */
export function AsyncState({
  loading,
  error,
  onRetry,
  children,
  empty,
  emptyText = "暂无数据",
}: {
  loading: boolean;
  error: ApiError | null;
  onRetry?: () => void;
  children: ReactNode;
  empty?: boolean;
  emptyText?: string;
}) {
  if (loading) {
    return (
      <div className="hd-skeleton-wrap">
        <div className="hd-skeleton" />
        <div className="hd-skeleton hd-skeleton--short" />
        <div className="hd-skeleton" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="hd-error-block">
        <div className="hd-error-block__title">
          {error.isNetwork ? "连不上服务器" : error.isServerError ? "服务器出错了" : "操作未完成"}
        </div>
        <div className="hd-error-block__msg">{error.message}</div>
        {error.isNetwork && (
          <div className="hd-error-block__hint">
            检查前台机与服务器的网络，或确认后端 8000 端口是否在跑。
          </div>
        )}
        {error.isServerError && (
          <div className="hd-error-block__hint">
            这类错误前端照做不了任何事，请联系管理员查看服务端日志（code: {error.code}）。
          </div>
        )}
        {onRetry && (
          <button className="hd-btn hd-btn--sm" onClick={onRetry} style={{ marginTop: 10 }}>
            重试
          </button>
        )}
      </div>
    );
  }

  if (empty) {
    return <div className="hd-empty">{emptyText}</div>;
  }

  return <>{children}</>;
}

/** 单行提示：成功/失败都用它，位置统一（页面顶部），不弹 toast。 */
export function Notice({ kind, text, onClose }: { kind: "ok" | "warn" | "error"; text: string; onClose?: () => void }) {
  return (
    <div className={`hd-notice hd-notice--${kind}`}>
      <span>{text}</span>
      {onClose && (
        <button className="hd-notice__close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  );
}
