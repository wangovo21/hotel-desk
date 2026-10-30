-- ============================================================================
-- 酒店前台录入系统 · SQLite Schema
-- 版本：1
--
-- 全局约定（改表时必须遵守）：
--   1) 金额一律用「分」为单位的整数，列名以 _cents 结尾 —— 绝不用 REAL 存钱
--   2) 日期存 'YYYY-MM-DD'，时刻存 'YYYY-MM-DD HH:MM:SS'（本地时间），
--      由应用层写入，不依赖 SQLite 的 datetime('now') —— 跨机器时区才不会飘
--   3) 凡是有业务含义的枚举，都用 CHECK 约束钉死取值，别指望应用层永远传对
--   4) 本文件全部用 CREATE ... IF NOT EXISTS，可反复执行（init_db.py 幂等的前提）
--
-- 安全底线（三处，重构时不许去掉）：
--   ★ uq_stays_room_in_house   一间房同时只能有一张在住单（房态与单据不可能打架）
--   ★ stays CHECK (nights >= 1) 间夜不许为 0 —— 账目从根上不出负数/零元单
--   ★ uq_guests_identity       同一证件只能有一份客人档案（避免同一人两份住史）
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. 房型（挂牌价与床型的唯一来源；房价快照在入住时写进 stays）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS room_types (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  code             TEXT    NOT NULL UNIQUE,        -- STD / DBL / TWN / SUITE
  name             TEXT    NOT NULL,               -- 标准大床房
  base_price_cents INTEGER NOT NULL,               -- 挂牌价（分/晚）
  capacity         INTEGER NOT NULL DEFAULT 2,     -- 可住人数
  bed_type         TEXT,                           -- 1.8m 大床 / 双床
  status           TEXT    NOT NULL DEFAULT 'ON',  -- ON 启用 / OFF 停用
  sort_order       INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT    NOT NULL,
  updated_at       TEXT    NOT NULL,
  CHECK (base_price_cents > 0),
  CHECK (capacity > 0),
  CHECK (status IN ('ON','OFF')),
  UNIQUE (name)
);

-- ---------------------------------------------------------------------------
-- 2. 房间
--    房态机：VACANT --入住--> OCCUPIED --退房--> CLEANING --打扫完--> VACANT
--            VACANT --报修--> MAINTENANCE --修好--> VACANT
--    只有 VACANT 能办入住；退房后**不直接回空房**，必须经过 CLEANING ——
--    这是酒店的真实流程，也让保洁有个待办列表。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rooms (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  room_no      TEXT    NOT NULL UNIQUE,            -- 8301
  room_type_id INTEGER NOT NULL REFERENCES room_types(id),
  floor        INTEGER NOT NULL,
  status       TEXT    NOT NULL DEFAULT 'VACANT',
  note         TEXT,
  created_at   TEXT    NOT NULL,
  updated_at   TEXT    NOT NULL,
  CHECK (status IN ('VACANT','OCCUPIED','CLEANING','MAINTENANCE')),
  CHECK (floor BETWEEN -5 AND 200)
);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_type   ON rooms(room_type_id);

-- ---------------------------------------------------------------------------
-- 3. 客人档案
--    一个客人一辈子一份档案（按证件号去重），住史挂在 stays 上。
--    ★ 不存"会员/积分"：本系统只做前台录入，不做会员运营。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guests (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT    NOT NULL,
  id_type    TEXT    NOT NULL DEFAULT 'ID_CARD',
  id_no      TEXT    NOT NULL,                     -- 身份证号 / 护照号
  phone      TEXT,
  gender     TEXT    NOT NULL DEFAULT 'UNKNOWN',
  blacklisted INTEGER NOT NULL DEFAULT 0,          -- 1 = 黑名单（入住时拦截）
  remark     TEXT,
  created_at TEXT    NOT NULL,
  updated_at TEXT    NOT NULL,
  CHECK (id_type IN ('ID_CARD','PASSPORT','HK_MACAO','TAIWAN','OTHER')),
  CHECK (gender IN ('MALE','FEMALE','UNKNOWN')),
  CHECK (blacklisted IN (0,1)),
  -- ★ 同一证件只能有一份档案；不同类型下同号可以并存（护照号碰巧等于身份证号的情况）
  UNIQUE (id_type, id_no)
);
CREATE INDEX IF NOT EXISTS idx_guests_phone ON guests(phone);
CREATE INDEX IF NOT EXISTS idx_guests_name  ON guests(name);

-- ---------------------------------------------------------------------------
-- 4. 入住单（本系统的核心单据）
--    room_rate_cents 是**房价快照**：房型调价后，老单据的账不会跟着变。
--    nights 在入住时先写"预计间夜"，退房时改写为"实际结算间夜"（留痕见 stay_events）。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stays (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  stay_no                TEXT    NOT NULL UNIQUE,  -- 入住单号 RS20261023-001
  guest_id               INTEGER NOT NULL REFERENCES guests(id),
  room_id                INTEGER NOT NULL REFERENCES rooms(id),
  room_rate_cents        INTEGER NOT NULL,         -- 房价快照（分/晚）
  checkin_at             TEXT    NOT NULL,         -- 入住时刻
  expected_checkout_date TEXT    NOT NULL,         -- 预计离店日 YYYY-MM-DD
  checkout_at            TEXT,                     -- 实际退房时刻（在住为 NULL）
  nights                 INTEGER NOT NULL DEFAULT 1,
  deposit_cents          INTEGER NOT NULL DEFAULT 0,
  adults                 INTEGER NOT NULL DEFAULT 1,
  children               INTEGER NOT NULL DEFAULT 0,
  status                 TEXT    NOT NULL DEFAULT 'IN_HOUSE',
  operator               TEXT,
  remark                 TEXT,
  created_at             TEXT    NOT NULL,
  updated_at             TEXT    NOT NULL,
  CHECK (status IN ('IN_HOUSE','CHECKED_OUT','CANCELLED')),
  CHECK (nights >= 1),
  CHECK (room_rate_cents > 0),
  CHECK (deposit_cents >= 0),
  CHECK (adults >= 1),
  CHECK (children >= 0),
  -- ★ 状态自洽：在住单没有退房时刻；已退房/已撤销必须有退房时刻
  CHECK (status = 'IN_HOUSE' OR checkout_at IS NOT NULL)
);
-- ★★ 一间房同时只能有一张在住单。业务层会先查房态，但真正的保险在这行索引上：
--    两个前台同时点"入住"、或者程序 bug 绕过校验，数据库这一层仍然挡得住。
CREATE UNIQUE INDEX IF NOT EXISTS uq_stays_room_in_house
  ON stays(room_id) WHERE status = 'IN_HOUSE';
CREATE INDEX IF NOT EXISTS idx_stays_guest ON stays(guest_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stays_status ON stays(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stays_time ON stays(created_at DESC);

-- ---------------------------------------------------------------------------
-- 5. 杂费（房费在退房时也落一行到这里，账单因此是"逐项可读"的）
--    amount_cents 恒为正，数量单独存；退款/减免不在本期范围。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stay_charges (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  stay_id      INTEGER NOT NULL REFERENCES stays(id) ON DELETE CASCADE,
  category     TEXT    NOT NULL,
  name         TEXT    NOT NULL,
  amount_cents INTEGER NOT NULL,
  quantity     INTEGER NOT NULL DEFAULT 1,
  operator     TEXT,
  remark       TEXT,
  created_at   TEXT    NOT NULL,
  CHECK (category IN ('ROOM','FOOD','LAUNDRY','MINIBAR','EXTRA_BED','DAMAGE','OTHER')),
  CHECK (amount_cents > 0),
  CHECK (quantity > 0)
);
CREATE INDEX IF NOT EXISTS idx_charges_stay ON stay_charges(stay_id, created_at);

-- ---------------------------------------------------------------------------
-- 6. 操作留痕（append-only）
--    换房、续住、加费、退房都写一条。前台有纠纷时，这张表就是"谁在几点做了什么"。
--    amount_cents 只对 ADD_CHARGE/CHECKOUT 有意义，其余为 0。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stay_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  stay_id      INTEGER NOT NULL REFERENCES stays(id) ON DELETE CASCADE,
  type         TEXT    NOT NULL,
  from_value   TEXT,
  to_value     TEXT,
  amount_cents INTEGER NOT NULL DEFAULT 0,
  operator     TEXT,
  remark       TEXT,
  created_at   TEXT    NOT NULL,
  CHECK (type IN ('CHECKIN','EXTEND','CHANGE_ROOM','ADD_CHARGE','CHECKOUT','CANCEL',
                  'ISSUE_CARD','REVOKE_CARD')),
  CHECK (amount_cents >= 0)
);
CREATE INDEX IF NOT EXISTS idx_events_stay ON stay_events(stay_id, created_at);

-- ---------------------------------------------------------------------------
-- 6.5 房卡（刷卡机制：USB 键盘仿真读写器，刷卡=往输入框敲卡号并以回车结尾）
--    发卡 = 把卡号绑到入住单；退卡 = 逻辑回收（留痕，不删行）。
--    ★ uq_room_cards_active_no  一张实体卡同时只能绑一张在住单 ——
--      部分唯一索引只在 ACTIVE 上生效，退卡后同一张卡可以再发给别的客人。
--    room_no 是发卡时刻的快照：换房后老卡的归属以留痕为准，不改写历史。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS room_cards (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  stay_id       INTEGER NOT NULL REFERENCES stays(id) ON DELETE CASCADE,
  card_no       TEXT    NOT NULL,                 -- 读写器读出的卡号（大写归一化后）
  room_no       TEXT    NOT NULL,                 -- 发卡时的房间号快照
  status        TEXT    NOT NULL DEFAULT 'ACTIVE',
  issued_at     TEXT    NOT NULL,
  issued_by     TEXT,
  revoked_at    TEXT,
  revoked_by    TEXT,
  revoke_reason TEXT,
  created_at    TEXT    NOT NULL,
  updated_at    TEXT    NOT NULL,
  CHECK (status IN ('ACTIVE','REVOKED')),
  CHECK (card_no <> ''),
  CHECK (room_no <> ''),
  CHECK (status = 'ACTIVE' OR revoked_at IS NOT NULL)
);
-- ★★ 一张实体卡同时只能有一张在用记录。业务层先查，这行索引兜底并发。
CREATE UNIQUE INDEX IF NOT EXISTS uq_room_cards_active_no
  ON room_cards(card_no) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_cards_stay ON room_cards(stay_id, id);

-- ---------------------------------------------------------------------------
-- 7. 业务参数（改规则不用改代码、不用重启）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  description TEXT,
  updated_at  TEXT NOT NULL
);
