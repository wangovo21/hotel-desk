/** 与后端 OpenAPI 一一对应的类型。改后端字段时，先改这里再看编辑器报错。 */

export type RoomStatus = "VACANT" | "OCCUPIED" | "CLEANING" | "MAINTENANCE";
export type StayStatus = "IN_HOUSE" | "CHECKED_OUT" | "CANCELLED";
export type IdType = "ID_CARD" | "PASSPORT" | "HK_MACAO" | "TAIWAN" | "OTHER";
export type Gender = "MALE" | "FEMALE" | "UNKNOWN";
export type ChargeCategory =
  | "ROOM"
  | "FOOD"
  | "LAUNDRY"
  | "MINIBAR"
  | "EXTRA_BED"
  | "DAMAGE"
  | "OTHER";

export interface ErrorEnvelope {
  error: { code: string; message: string; detail?: Record<string, unknown> };
}

export interface Health {
  app_name: string;
  app_version: string;
  app_env: string;
  today: string;
  db: { ok: boolean; detail: string; schema_version: number; tables: number; missing: string[] };
  admin_api_enabled: boolean;
  docs_enabled: boolean;
  hotel_name: string;
}

export interface RoomType {
  id: number;
  code: string;
  name: string;
  base_price_cents: number;
  base_price_display: string;
  capacity: number;
  bed_type: string | null;
  status: "ON" | "OFF";
  status_label: string;
  sort_order: number;
  room_count: number;
}

export interface StayBrief {
  id: number;
  stay_no: string;
  guest_id: number;
  guest_name: string;
  guest_phone: string | null;
  id_no_masked: string;
  room_id: number;
  room_no: string;
  room_type_name: string;
  room_rate_cents: number;
  room_rate_display: string;
  checkin_at: string;
  expected_checkout_date: string;
  checkout_at: string | null;
  nights: number;
  deposit_cents: number;
  deposit_display: string;
  adults: number;
  children: number;
  status: StayStatus;
  status_label: string;
  overdue: boolean;
}

export interface Charge {
  id: number;
  category: ChargeCategory;
  category_label: string;
  name: string;
  amount_cents: number;
  amount_display: string;
  quantity: number;
  subtotal_cents: number;
  subtotal_display: string;
  operator: string | null;
  remark: string | null;
  created_at: string;
}

export interface StayEvent {
  id: number;
  type: string;
  type_label: string;
  from_value: string | null;
  to_value: string | null;
  amount_cents: number;
  amount_display: string;
  operator: string | null;
  remark: string | null;
  created_at: string;
}

export interface Bill {
  nights: number;
  room_fee_cents: number;
  room_fee_display: string;
  charges_total_cents: number;
  charges_total_display: string;
  total_cents: number;
  total_display: string;
  deposit_cents: number;
  deposit_display: string;
  balance_cents: number;
  balance_display: string;
  settlement: "DUE" | "REFUND" | "EVEN";
  settlement_label: string;
}

export interface StayDetail extends StayBrief {
  remark: string | null;
  operator: string | null;
  created_at: string;
  updated_at: string;
  charges: Charge[];
  events: StayEvent[];
  cards: RoomCard[];
  bill: Bill;
}

export type CardStatus = "ACTIVE" | "REVOKED";

export interface RoomCard {
  id: number;
  stay_id: number;
  card_no: string;
  room_no: string;
  status: CardStatus;
  status_label: string;
  issued_at: string;
  issued_by: string | null;
  revoked_at: string | null;
  revoked_by: string | null;
  revoke_reason: string | null;
}

export interface StayPage {
  items: StayBrief[];
  total: number;
  page: number;
  page_size: number;
}

export interface Room {
  id: number;
  room_no: string;
  floor: number;
  status: RoomStatus;
  status_label: string;
  room_type_id: number;
  room_type_code: string;
  room_type_name: string;
  base_price_cents: number;
  base_price_display: string;
  capacity: number;
  note: string | null;
  current_stay: StayBrief | null;
}

export interface RoomBoard {
  hotel_name: string;
  total_rooms: number;
  counts: Record<RoomStatus, number>;
  floors: { floor: number; rooms: Room[] }[];
  generated_at: string;
}

export interface GuestBrief {
  id: number;
  name: string;
  id_type: IdType;
  id_type_label: string;
  id_no: string;
  id_no_masked: string;
  phone: string | null;
  gender: Gender;
  gender_label: string;
  blacklisted: boolean;
  stay_count: number;
  last_checkin_at: string | null;
  created_at: string;
}

export interface GuestStayItem {
  stay_id: number;
  stay_no: string;
  room_no: string;
  checkin_at: string;
  checkout_at: string | null;
  nights: number;
  status: StayStatus;
  status_label: string;
}

export interface GuestDetail extends GuestBrief {
  remark: string | null;
  updated_at: string;
  stays: GuestStayItem[];
}

export interface GuestPage {
  items: GuestBrief[];
  total: number;
  page: number;
  page_size: number;
}

export interface DayPoint {
  date: string;
  checkins: number;
  checkouts: number;
  revenue_cents: number;
  revenue_display: string;
}

export interface Dashboard {
  hotel_name: string;
  today: string;
  generated_at: string;
  total_rooms: number;
  in_house_count: number;
  vacant_count: number;
  cleaning_count: number;
  maintenance_count: number;
  occupancy_percent: number;
  guests_in_house: number;
  today_checkins: number;
  today_checkouts: number;
  today_revenue_cents: number;
  today_revenue_display: string;
  in_house_deposit_cents: number;
  in_house_deposit_display: string;
  due_out_today: StayBrief[];
  overdue_stays: StayBrief[];
  recent_checkouts: StayBrief[];
  room_type_usage: {
    room_type_id: number;
    name: string;
    total: number;
    occupied: number;
    occupancy_percent: number;
  }[];
  trend: DayPoint[];
}

export interface Setting {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 请求体
// ---------------------------------------------------------------------------
export interface GuestInput {
  name: string;
  id_type: IdType;
  id_no: string;
  phone?: string | null;
  gender?: Gender;
  remark?: string | null;
}

export interface CheckinInput {
  guest_id?: number;
  guest?: GuestInput;
  room_id: number;
  checkin_at?: string;
  expected_checkout_date: string;
  room_rate?: string;
  deposit?: string;
  adults?: number;
  children?: number;
  operator?: string;
  remark?: string;
}

export interface RoomTypeInput {
  code?: string;
  name?: string;
  price?: string;
  capacity?: number;
  bed_type?: string | null;
  status?: "ON" | "OFF";
  sort_order?: number;
}

export interface RoomInput {
  room_no?: string;
  room_type_id?: number;
  floor?: number;
  note?: string | null;
}
