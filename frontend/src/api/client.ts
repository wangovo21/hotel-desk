/**
 * 前端**唯一**发请求的地方。
 *
 * 四条规矩（都是吃过亏才写下来的）：
 *
 * 1. 只解析一种错误形状：后端的 `{error:{code,message,detail?}}`。
 *    解析不出来说明没打到 FastAPI（代理 502、静态页兜底），
 *    这时降级成 UNEXPECTED_RESPONSE，而不是把一段 HTML 当 message 显示给前台。
 *
 * 2. **不抄一份错误码→中文的表**。后端的 errors.py 已经把话写成面向客人的句子，
 *    这里原样透传；只有"前端才知道的上下文"（比如管理口令要配在哪）才在 HINTS 里补。
 *
 * 3. 网络失败与业务失败分开。前台看到的应该是"连不上服务器，检查网线"，
 *    而不是一个空红框 —— 这两种情况的处理动作完全不同。
 *
 * 4. 金额一律传**字符串**（"289.00"）。让 JS 先算一遍浮点再序列化，
 *    迟早出现 0.1+0.2 那种尾数，最后在账单上变成莫名其妙的一分钱。
 */
import type {
  ChargeCategory,
  CheckinInput,
  Dashboard,
  ErrorEnvelope,
  GuestDetail,
  GuestInput,
  GuestPage,
  Health,
  Room,
  RoomBoard,
  RoomCard,
  RoomInput,
  RoomStatus,
  RoomType,
  RoomTypeInput,
  Setting,
  StayBrief,
  StayDetail,
  StayPage,
  StayStatus,
} from "./types";

const ADMIN_TOKEN: string = import.meta.env.VITE_ADMIN_TOKEN ?? "";
const BASE: string = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: Record<string, unknown> | undefined;

  constructor(status: number, code: string, message: string, detail?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }

  get isNetwork() {
    return this.code === "NETWORK_ERROR";
  }

  get isServerError() {
    return this.status >= 500;
  }

  /** 字段级校验错误（后端 INVALID_PARAM.detail.errors）—— 表单要高亮到具体输入框。 */
  get fieldErrors(): { field: string; message: string }[] {
    const errors = this.detail?.errors;
    return Array.isArray(errors) ? (errors as { field: string; message: string }[]) : [];
  }
}

const HINTS: Record<string, (detail?: Record<string, unknown>) => string> = {
  UNAUTHORIZED: () =>
    "无权限：这个动作需要后台口令。若刚部署，请检查构建时是否注入了 VITE_ADMIN_TOKEN",
  ADMIN_TOKEN_NOT_CONFIGURED: () =>
    "服务端没配 ADMIN_TOKEN，后台写接口已关闭。请在服务器上配置该环境变量后重启",
  DB_ERROR: () => "数据库写入冲突，请刷新后重试；若反复出现，联系管理员",
};

function messageOf(code: string, fallback: string, detail?: Record<string, unknown>): string {
  const hint = HINTS[code];
  return hint ? hint(detail) : fallback;
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    // ★ 跳过空值：把 `?status=` 发出去，后端会当成"筛选 status=''"，于是"没筛"变"查不到"
    if (value === null || value === undefined || value === "") continue;
    qs.append(key, String(value));
  }
  const tail = qs.toString();
  return `${BASE}${path}${tail ? `?${tail}` : ""}`;
}

async function request<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  options: { query?: Query; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (ADMIN_TOKEN) headers["X-Admin-Token"] = ADMIN_TOKEN;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let resp: Response;
  try {
    resp = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (cause) {
    throw new ApiError(0, "NETWORK_ERROR", "连不上服务器，请检查前台机与服务器的网络", {
      cause: String(cause),
    });
  }

  const text = await resp.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null; // 代理的 HTML 错误页会走到这里
    }
  }

  if (!resp.ok) {
    const envelope = parsed as ErrorEnvelope | null;
    const err = envelope?.error;
    if (err && typeof err.code === "string") {
      throw new ApiError(
        resp.status,
        err.code,
        messageOf(err.code, err.message || "请求失败", err.detail),
        err.detail,
      );
    }
    throw new ApiError(
      resp.status,
      "UNEXPECTED_RESPONSE",
      `服务器返回了非预期响应（HTTP ${resp.status}），请确认后端是否正常`,
      { body: text.slice(0, 300) },
    );
  }

  return parsed as T;
}

const get = <T>(path: string, query?: Query) => request<T>("GET", path, { query });
const post = <T>(path: string, body: unknown = {}, query?: Query) =>
  request<T>("POST", path, { body, query });
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, { body });
const del = <T>(path: string) => request<T>("DELETE", path);

export const api = {
  health: () => get<Health>("/api/health"),

  // ---- 房型 ----
  roomTypes: {
    list: () => get<RoomType[]>("/api/room-types"),
    create: (body: RoomTypeInput) => post<RoomType>("/api/room-types", body),
    update: (id: number, body: RoomTypeInput) => put<RoomType>(`/api/room-types/${id}`, body),
  },

  // ---- 房间 ----
  rooms: {
    board: () => get<RoomBoard>("/api/rooms/board"),
    list: (query: {
      status?: RoomStatus | "";
      floor?: number | "";
      room_type_id?: number | "";
      keyword?: string;
    }) => get<Room[]>(`/api/rooms`, query),
    get: (id: number) => get<Room>(`/api/rooms/${id}`),
    create: (body: RoomInput & { room_no: string; room_type_id: number; floor: number }) =>
      post<Room>("/api/rooms", body),
    update: (id: number, body: RoomInput) => put<Room>(`/api/rooms/${id}`, body),
    setStatus: (id: number, status: Exclude<RoomStatus, "OCCUPIED">, note?: string) =>
      put<Room>(`/api/rooms/${id}/status`, { status, note }),
    remove: (id: number) => del<{ ok: boolean }>(`/api/rooms/${id}`),
  },

  // ---- 客人 ----
  guests: {
    list: (query: { keyword?: string; blacklisted?: boolean; page?: number; page_size?: number }) =>
      get<GuestPage>("/api/guests", query),
    get: (id: number) => get<GuestDetail>(`/api/guests/${id}`),
    create: (body: GuestInput) => post<GuestDetail>("/api/guests", body),
    update: (
      id: number,
      body: Partial<Pick<GuestInput, "name" | "phone" | "gender" | "remark">> & {
        blacklisted?: boolean;
      },
    ) => put<GuestDetail>(`/api/guests/${id}`, body),
  },

  // ---- 入住单 ----
  stays: {
    /** ★ 入住登记。是前台最热的接口，后端在这里做了房态、容量、黑名单三道校验。 */
    checkin: (body: CheckinInput) => post<StayDetail>("/api/stays", body),
    list: (query: {
      status?: StayStatus | "";
      keyword?: string;
      date_from?: string;
      date_to?: string;
      room_id?: number;
      page?: number;
      page_size?: number;
    }) => get<StayPage>("/api/stays", query),
    inHouse: () => get<StayBrief[]>("/api/stays/in-house"),
    get: (id: number) => get<StayDetail>(`/api/stays/${id}`),
    extend: (id: number, expectedCheckoutDate: string, remark?: string) =>
      post<StayDetail>(`/api/stays/${id}/extend`, {
        expected_checkout_date: expectedCheckoutDate,
        remark,
      }),
    changeRoom: (id: number, roomId: number, roomRate?: string) =>
      post<StayDetail>(`/api/stays/${id}/change-room`, { room_id: roomId, room_rate: roomRate }),
    addCharge: (
      id: number,
      body: { category: ChargeCategory; name: string; amount: string; quantity?: number; remark?: string },
    ) => post<StayDetail>(`/api/stays/${id}/charges`, body),
    checkout: (id: number, nights?: number, remark?: string) =>
      post<StayDetail>(`/api/stays/${id}/checkout`, { nights, remark }),
    cancel: (id: number, operator?: string, remark?: string) =>
      post<StayDetail>(`/api/stays/${id}/cancel`, {}, { operator, remark }),
    /** ★ 发房卡。USB 键盘仿真读写器：刷卡 = 往输入框敲卡号 + 回车，前端把回车提交到这里。 */
    issueCard: (id: number, cardNo: string, operator?: string, remark?: string) =>
      post<RoomCard[]>(`/api/stays/${id}/cards`, { card_no: cardNo, operator, remark }),
    listCards: (id: number) => get<RoomCard[]>(`/api/stays/${id}/cards`),
  },

  cards: {
    revoke: (cardId: number, operator?: string, reason?: string) =>
      post<RoomCard[]>(`/api/cards/${cardId}/revoke`, { operator, reason }),
  },

  stats: { dashboard: () => get<Dashboard>("/api/stats/dashboard") },

  settings: {
    list: () => get<Setting[]>("/api/settings"),
    update: (key: string, value: string) => put<Setting>("/api/settings", { key, value }),
  },
};
