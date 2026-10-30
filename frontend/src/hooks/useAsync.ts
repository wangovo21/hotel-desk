import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";

interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/**
 * 一页数据的最小状态机：loading / error / data + 手动 reload。
 *
 * ★ 用 `alive` 标记挡掉"组件已卸载再 setState"的警告，也挡掉**竞态**：
 *   快速切筛选时，慢的那个请求晚回来会把新数据覆盖掉 —— 这类 bug
 *   在房态页特别容易复现（切楼层时手快一点就中）。
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const runId = useRef(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const id = ++runId.current;
    let alive = true;
    setLoading(true);

    fn()
      .then((result) => {
        if (!alive || id !== runId.current) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (!alive || id !== runId.current) return;
        setError(
          err instanceof ApiError
            ? err
            : new ApiError(0, "UNKNOWN", String((err as Error)?.message ?? err)),
        );
      })
      .finally(() => {
        if (alive && id === runId.current) setLoading(false);
      });

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, error, loading, reload };
}
