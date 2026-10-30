# 云栖酒店 · 酒店录入系统（hotel-desk）

参照 nfc-market（NFC 智能超市会员积分卡系统）的架构与代码风格重写的**酒店前台一体化系统**：房态看板、入住登记、续住/换房/退房结账、客人档案、经营看板，一站式覆盖酒店前台日常流程。

## 技术栈

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端 | Python 3.13+ · FastAPI · SQLite（WAL） | 无 ORM，手写 SQL，分 api / services / repo / db 四层 |
| 前端 | Vite · React 18 · TypeScript | 无 UI 框架，纯手写组件，与原项目视觉风格一致 |
| 文档 | Swagger UI（离线资源内置） | `/docs` 页面无需外网即可使用 |

## 目录结构

```
hotel-desk/
├── start.py / start.bat / run-local.sh   # 一键启动脚本（自动建库 + 起服务）
├── backend/
│   ├── app/
│   │   ├── config.py            # 环境变量配置（.env）
│   │   ├── core/                # errors（统一错误信封）、money（分/元换算）、dates、labels
│   │   ├── db/                  # schema.sql、连接管理、init_db（含演示数据）
│   │   ├── models/              # Pydantic 模型：房型/房间/客人/入住单/统计/设置
│   │   ├── repo/                # 纯 SQL 数据访问层
│   │   ├── services/            # 业务逻辑：入住/续住/换房/退房/结账/留痕/统计
│   │   └── api/                 # 路由层 + deps（管理员口令校验）
│   ├── tests/                   # 55 个单元/接口测试（unittest + httpx 内存 HTTP）
│   └── data/hotel.db            # SQLite 数据库（首次运行自动生成）
└── frontend/
    └── src/
        ├── api/                 # client.ts（统一请求封装）+ types.ts
        ├── components/          # Layout、Modal、CheckinDialog、StayPanel 等
        ├── pages/               # 九个页面（见下）
        └── hooks/ utils/        # useAsync、金额/日期格式化
```

## 功能页面

1. **前台工作台** — 房态看板（楼层 × 房卡），点空房直接登记入住，点在住房办理续住/换房/加杂费/退房
2. **入住登记** — 客人信息（姓名/证件/手机）、房号、入住/离店日期、押金、同行人数
3. **在住客人** — 当前在住列表与快捷操作
4. **入住记录** — 全部历史单据检索（状态/日期/关键词）
5. **房间管理** — 新增/修改/停用房间，状态流转（空闲→在住→待清扫→空闲、维修）
6. **房型管理** — 房型与门市价维护
7. **客人档案** — 回头客信息、拉黑管理
8. **经营看板** — 出租率、今日入住/退房、今日营收、最近退房
9. **参数设置** — 酒店名称、默认押金、延时退房时间等

## 快速开始

```bash
# Windows：双击
start.bat

# 或任意平台
python start.py          # 自动选 Python → 建库（含演示数据）→ 起 8000 端口
bash run-local.sh        # Git Bash / Linux / macOS
```

打开 <http://127.0.0.1:8000> 即可使用；演示数据内置 4 个房型、20 间房、4 位客人、在住/待清扫/已退房各状态的示例单据。

### 开发模式（前端热更新）

```bash
cd backend  && <python> -m uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 管理口令

新增/修改/删除房间、房型、拉黑客人等写操作需要管理口令，默认 `dev-admin-token`：

- 后端通过 `X-Admin-Token` 请求头传入
- 前端在 `.env` 中配置：`VITE_ADMIN_TOKEN=dev-admin-token`
- 生产环境务必修改 `backend/.env` 的 `ADMIN_TOKEN`

## 核心业务规则

- **入住**：房间必须处于"空闲"；客人可复用已有档案（按证件号去重）；离店日期必须晚于入住日期
- **证件号（6 位虚拟号）**：本系统是模拟系统，**不对标真实身份证**。证件类型为"身份证"时必须是 **6 位数字虚拟号**：入住表单自动预填、可点「换一个虚拟号」更换，也可手改；18 位真身份证号一律拒绝。其他证件类型（护照等）不限制长度。控制点：后端 `app/models/guest.py` 的 `ID_CARD_PATTERN`
- **押金**：入住时登记，退房结算时冲抵；账单 = 房费（房价 × 晚数）+ 杂费 − 押金
- **续住**：只能顺延，新的离店日期必须晚于原日期
- **换房**：目标房必须空闲，换房事件全量留痕
- **退房结账**：一次性出账（房费 + 各类杂费 − 押金 = 应收），房间转"待清扫"
- **房卡（刷卡机制）**：入住详情面板可发卡/退卡；USB 键盘仿真读写器免驱动，刷卡 = 往输入框敲卡号并以回车结尾。一张实体卡同时只能绑一张在住单（数据库部分唯一索引兜底）；退卡是逻辑回收可再发放；**退房/撤销自动收回全部在用卡**，发卡退卡全部进操作留痕
- **留痕**：入住、续住、换房、加杂费、发卡、退卡、退房全部写入 `stay_events`，单据详情页可查完整轨迹
- **黑名单**：被拉黑客人无法办理入住（`GUEST_BLACKLISTED`）

## 常用接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/rooms/board` | 房态看板（按楼层分组） |
| POST | `/api/stays` | 入住登记（guest 或 guest_id 二选一） |
| POST | `/api/stays/{id}/extend` | 续住 |
| POST | `/api/stays/{id}/change-room` | 换房 |
| POST | `/api/stays/{id}/charges` | 加收杂费 |
| POST | `/api/stays/{id}/cards` | 发放房卡（card_no，读写器回车即发） |
| GET | `/api/stays/{id}/cards` | 入住单的房卡记录 |
| POST | `/api/cards/{id}/revoke` | 收回房卡 |
| POST | `/api/stays/{id}/checkout` | 退房结账（自动收卡） |
| GET | `/api/stats/dashboard` | 经营看板 |

完整接口见 `http://127.0.0.1:8000/docs`（离线 Swagger UI）。

## 配置

复制 `.env.example` 为 `.env` 后按需修改：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ADMIN_TOKEN` | dev-admin-token | 管理口令 |
| `DB_PATH` | `data/hotel.db` | 数据库文件位置 |
| `CORS_ORIGINS` | localhost:5173 | 允许的跨域来源 |
| `DOCS_ENABLED` | 1 | 是否开启 Swagger 文档 |

## 测试

```bash
cd backend && <python> -m unittest discover -s tests -t . -v   # 55 个用例
cd frontend && npm run typecheck && npm run build              # 类型检查 + 构建
```

## 与原项目（nfc-market）的关系

- 沿用同一套分层约定（api → services → repo → db）、统一错误信封、分计价金额工具、留痕事件表、离线 Swagger 与启动脚本方案
- 移除会员/积分/NFC 硬件相关模块，替换为酒店领域的房态机、押金结算与账单模型
