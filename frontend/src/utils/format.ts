/** 日期与展示格式的小工具。金额一律用后端给的 *_display 字段，这里不做除法。 */

export function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** 本地时区的今天，YYYY-MM-DD（不能用 toISOString —— 那是 UTC，晚上会差一天）。 */
export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDaysISO(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + days);
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
}

/** 2026-10-23 14:10:00 → 10-23 14:10 */
export function shortDateTime(value: string | null): string {
  if (!value) return "—";
  const [day, clock] = value.split(" ");
  return `${day.slice(5)} ${(clock ?? "").slice(0, 5)}`.trim();
}

export function dateOnly(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

/** 两个日期之间差几天（用于前端预览"住几晚"，后端仍会自己算一遍） */
export function nightsBetween(checkinISO: string, checkoutISO: string): number {
  const a = new Date(`${checkinISO}T00:00:00`);
  const b = new Date(`${checkoutISO}T00:00:00`);
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

export function yuanToCents(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

/** 6 位模拟身份证号（演练 / 演示用，不是真号）。 */
export function mockIdNo(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}
