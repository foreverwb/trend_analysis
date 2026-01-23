# Trend Analysis System (强势动能交易系统)

一个基于 FastAPI + React 的动能股票分析系统，支持板块/行业 ETF 分析和动能股筛选。

## 系统架构

```
trend_analysis/
├── config.yaml               # 配置文件 (API、日志、数据源)
├── start.sh                  # 一键启动脚本
├── requirements.txt          # Python 依赖
├── backend/                  # FastAPI 后端
│   ├── cli/                  # CLI 工具
│   │   └── uploads.py        # XLSX 上传命令行工具
│   ├── routers/              # API 路由
│   │   ├── etf.py            # ETF 相关接口
│   │   ├── momentum.py       # 动能股接口
│   │   ├── market.py         # 市场数据接口
│   │   ├── options.py        # 期权数据接口
│   │   ├── import_data.py    # 数据导入接口
│   │   └── config.py         # 配置接口
│   ├── services/             # 业务服务
│   │   ├── ibkr_service.py   # IBKR API 服务
│   │   ├── futu_service.py   # 富途 API 服务
│   │   ├── options_data_service.py  # 统一期权数据服务
│   │   ├── calculation.py    # 评分计算服务
│   │   └── delta_calc.py     # 3D/5D 变化计算
│   ├── config_loader.py      # 配置加载器
│   ├── logging_utils.py      # 日志工具
│   ├── database.py           # 数据库配置
│   ├── models.py             # SQLAlchemy 模型
│   ├── schemas.py            # Pydantic 模式
│   └── main.py               # FastAPI 应用入口
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/       # React 组件
│   │   ├── utils/            # 工具函数
│   │   ├── App.jsx           # 主应用
│   │   └── main.jsx          # 入口
│   └── package.json
└── logs/                     # 日志目录 (自动创建)
    └── app.log
```

## 功能特性

### 1. 板块/行业 ETF 分析
- 支持 11 个 GICS 板块 ETF (XLK, XLF, XLE 等)
- 行业 ETF 分析 (SOXX, IGV, SMH 等)
- 四模块评分体系：
  - 相对动量 (Relative Momentum)
  - 趋势质量 (Trend Quality)
  - 广度/参与度 (Breadth)
  - 期权确认 (Options Confirm)
- 持仓明细展示

### 2. 动能股池
- 个股动能评分
- 五模块分析：价格动能、趋势结构、量价确认、质量过滤、期权覆盖
- 突破触发识别
- 3D/5D 变化指标

### 3. 期权数据分析
- **OI 分析**: 持仓量变化追踪
- **IV 期限结构**: IV30, IV60, IV90 计算
- **PositioningScore**: 基于 OI 的情绪分析
- **TermScore**: 基于 IV 期限结构的信号

### 4. 数据导入
- **Finviz 导入**: 股票筛选数据 (Beta, ATR, SMA, RSI 等)
- **MarketChameleon 导入**: 期权数据 (IV30, HV20, IVR 等)
- **XLSX 上传**: ETF 持仓数据
- **导入历史**: 查看和管理导入记录

### 5. 数据源集成
- **IBKR (IB Gateway)**: 行情数据、历史 K 线、期权数据
- **富途 OpenD**: 期权链数据、持仓量分析
- **可配置数据源**: 支持切换主/备数据源
- **Finviz**: 股票筛选数据导入
- **MarketChameleon**: 期权数据导入

### 6. 市场环境评估 (Regime Gate)
- A档 (Risk-On): 满火力
- B档 (Neutral): 半火力
- C档 (Risk-Off): 低火力

---

## 快速开始

### 方式一：使用启动脚本（推荐）

**一键启动**，自动处理虚拟环境、依赖安装、服务启动：

```bash
cd trend_analysis

# 添加执行权限（仅首次需要）
chmod +x start.sh

# 启动系统
./start.sh
```

**启动脚本功能：**
- ✅ 自动检测 Python 版本（≥3.10）
- ✅ 自动创建虚拟环境 (`.venv`)
- ✅ 自动安装 Python 依赖
- ✅ 自动安装 Node.js 依赖
- ✅ 创建日志目录
- ✅ 启动后端和前端服务
- ✅ 彩色输出显示进度
- ✅ `Ctrl+C` 优雅关闭所有服务

**启动成功后输出：**
```
==========================================
  System Started Successfully!
==========================================

  Frontend:  http://localhost:5173
  Backend:   http://localhost:8000
  API Docs:  http://localhost:8000/docs

  Configuration:
    - Edit config.yaml to change settings
    - Logs are saved to logs/app.log

  Press Ctrl+C to stop all services
==========================================
```

### 方式二：手动启动

如果需要单独控制各服务，可手动启动：

```bash
# 1. 创建并激活虚拟环境
cd trend_analysis
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 启动后端服务 (从项目根目录运行)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 4. 新开终端，安装并启动前端
cd trend_analysis
source .venv/bin/activate  # 激活虚拟环境
cd frontend
npm install
npm run dev
```

### 访问系统

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

---

## start.sh 使用指南

### 前提条件

在运行 `start.sh` 之前，请确保已安装以下软件：

| 软件 | 最低版本 | 检查命令 |
|------|----------|----------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 16+ | `node --version` |
| npm | 8+ | `npm --version` |

### 基本用法

```bash
# 进入项目目录
cd trend_analysis

# 首次运行：添加执行权限
chmod +x start.sh

# 启动系统
./start.sh
```

### 脚本执行流程

`start.sh` 按以下步骤自动执行：

```
[1/6] 检查前提条件
      ├── 检测 Python 版本 (≥3.10)
      ├── 检测 Node.js
      └── 检测 npm

[2/6] 设置 Python 虚拟环境
      ├── 创建 .venv 目录 (首次运行)
      └── 激活虚拟环境

[3/6] 安装 Python 依赖
      ├── 升级 pip
      └── 安装 requirements.txt

[4/6] 安装 Node.js 依赖
      └── 运行 npm install (frontend/)

[5/6] 启动后端服务
      └── uvicorn main:app --host 0.0.0.0 --port 8000

[6/6] 启动前端服务
      └── npm run dev (端口 5173)
```

### 停止服务

按 `Ctrl+C` 可优雅地停止所有服务：

```bash
^C
Stopping services...
Services stopped.
```

### 重新启动

直接再次运行 `./start.sh` 即可，脚本会：
- 复用已存在的虚拟环境
- 跳过已安装的 node_modules
- 重新启动后端和前端服务

### 清理环境

如需完全重置环境：

```bash
# 删除虚拟环境
rm -rf .venv

# 删除 Node.js 依赖
rm -rf frontend/node_modules

# 删除日志
rm -rf logs

# 删除数据库（慎用！会丢失数据）
rm -f backend/trend_analysis.db

# 重新启动
./start.sh
```

### 后台运行

如需在后台运行服务：

```bash
# 使用 nohup 后台运行
nohup ./start.sh > start.log 2>&1 &

# 查看日志
tail -f start.log

# 查找进程
ps aux | grep -E "uvicorn|vite"

# 停止服务
pkill -f "uvicorn main:app"
pkill -f "vite"
```

### 仅启动后端/前端

如果只需要启动其中一个服务：

```bash
# 激活虚拟环境
cd trend_analysis
source .venv/bin/activate

# 仅启动后端 (从项目根目录运行)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 仅启动前端 (新终端)
cd frontend && npm run dev
```

### 使用环境变量

可在启动前设置环境变量覆盖配置：

```bash
# 设置环境变量后启动
export IBKR_PORT=4002          # 使用模拟账户
export LOG_LEVEL=DEBUG         # 开启调试日志
export OPTIONS_DATA_PRIMARY=ibkr  # IBKR 作为期权数据主源
./start.sh
```

### 常见问题

#### 1. "Permission denied" 错误

```bash
# 添加执行权限
chmod +x start.sh
```

#### 2. "Python not found" 错误

```bash
# 检查 Python 版本
python3 --version

# macOS 安装 Python
brew install python@3.11

# Ubuntu 安装 Python
sudo apt update && sudo apt install python3.11
```

#### 3. "Node.js not found" 错误

```bash
# macOS 安装 Node.js
brew install node

# Ubuntu 安装 Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

#### 4. 端口被占用

```bash
# 查看占用端口的进程
lsof -i :8000  # 后端端口
lsof -i :5173  # 前端端口

# 终止进程
kill -9 <PID>
```

#### 5. 虚拟环境问题

```bash
# 删除并重建虚拟环境
rm -rf .venv
./start.sh
```

---

## 配置文件

系统配置位于 `config.yaml`，支持以下设置：

### IBKR 配置

```yaml
ibkr:
  host: "127.0.0.1"
  port: 4002              # 4001=Gateway Live, 4002=Gateway Paper
  client_id: 3
  account_id: ""
  connection_timeout: 10
  enabled: true           # 是否启用
```

### 富途配置

```yaml
futu:
  host: "127.0.0.1"
  port: 11111
  api_key: ""
  api_secret: ""
  max_requests_per_minute: 60
  enabled: true
```

### 数据源配置

控制期权数据和市场数据使用哪个 API：

```yaml
data_sources:
  # 期权数据源 (OI, IV, 期限结构)
  options_data:
    primary: futu         # 主数据源: ibkr / futu
    fallback: ibkr        # 备用数据源
    auto_fallback: true   # 自动降级
  
  # 市场数据源 (股票/ETF 价格)
  market_data:
    primary: ibkr
    fallback: futu
    auto_fallback: true
```

**切换数据源示例：**

```yaml
# 使用 IBKR 作为期权数据主源
options_data:
  primary: ibkr
  fallback: futu
  auto_fallback: true
```

### 日志配置

```yaml
logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  file: "logs/app.log"
  log_api_calls: false     # 是否记录 API 调用
  log_response_data: false
  max_file_size: 10       # MB
  backup_count: 5
```

### 环境变量覆盖

配置可通过环境变量覆盖（优先级高于配置文件）：

```bash
# 示例
export IBKR_HOST=192.168.1.100
export IBKR_PORT=4001
export LOG_LEVEL=DEBUG
export OPTIONS_DATA_PRIMARY=ibkr

./start.sh
```

---

## CLI 工具使用

### 上传板块 ETF Holdings

```bash
python -m backend.cli.uploads -d 2024-01-15 -t sector -a XLK path/to/holdings.xlsx
```

### 上传行业 ETF Holdings

```bash
python -m backend.cli.uploads -d 2024-01-15 -t industry -s XLK -a SOXX path/to/holdings.xlsx
```

### XLSX 文件格式要求

| Ticker | Weight % |
|--------|----------|
| AAPL   | 22.5     |
| MSFT   | 20.1     |
| NVDA   | 15.3     |

---

## API 接口

### ETF 相关
- `GET /api/etf/sectors` - 获取所有板块 ETF
- `GET /api/etf/industries` - 获取所有行业 ETF
- `POST /api/etf/sectors/{symbol}/refresh` - 刷新板块 ETF 数据
- `POST /api/etf/holdings` - 上传 ETF 持仓

### 动能股
- `GET /api/momentum/stocks` - 获取动能股列表
- `POST /api/momentum/stocks/{symbol}/refresh` - 刷新股票数据
- `GET /api/momentum/breakouts` - 获取突破股票

### 期权数据
- `GET /api/options/source/info` - 获取数据源配置
- `POST /api/options/source/test` - 测试数据源连接
- `GET /api/options/chain/{symbol}` - 获取期权链
- `GET /api/options/iv/{symbol}` - 获取 IV 期限结构
- `GET /api/options/positioning/{symbol}` - 获取 OI 分析
- `GET /api/options/term-score/{symbol}` - 获取 TermScore
- `GET /api/options/analysis/{symbol}` - 获取完整分析

### 数据导入
- `POST /api/import/finviz` - 导入 Finviz 数据
- `POST /api/import/marketchameleon` - 导入 MarketChameleon 数据
- `POST /api/import/upload/xlsx` - 上传 XLSX 文件

### 市场数据
- `GET /api/market/regime` - 获取市场环境状态
- `POST /api/market/regime/refresh` - 刷新市场数据
- `GET /api/market/dashboard` - 获取仪表盘摘要

### 配置信息
- `GET /api/config/info` - 获取系统配置

---

## 数据源配置

### IBKR (IB Gateway)

1. 下载并安装 [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php)
2. 启动 IB Gateway 并登录
3. 在 `config.yaml` 中配置：
   ```yaml
   ibkr:
     host: "127.0.0.1"
     port: 4001    # live: 4001, paper: 4002
     client_id: 1
     enabled: true
   ```

### 富途 OpenD

1. 下载并安装 [Futu OpenD](https://www.futunn.com/download/OpenAPI)
2. 启动 OpenD 并登录
3. 在 `config.yaml` 中配置：
   ```yaml
   futu:
     host: "127.0.0.1"
     port: 11111
     enabled: true
   ```

---

## 评分计算公式

### ETF 综合评分
```
Composite = 0.55 × Price/RS + 0.20 × Breadth + 0.25 × Options
其中 Price/RS = 0.65 × RelMom + 0.35 × TrendQuality
```

### 相对动量
```
RelMom = 0.45 × RS_20D + 0.35 × RS_63D + 0.20 × RS_5D
```

### 个股综合评分
```
Final = 0.65 × (PriceMomentum + TrendStructure)/2 
      + 0.15 × VolumePrice 
      + 0.20 × OptionsOverlay
      × (1 - QualityPenalty)
```

---

## 日志查看

日志文件位于 `logs/app.log`：

```bash
# 实时查看日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log

# 查看 API 调用
grep "\[API\]" logs/app.log
```

**日志示例：**
```
2024-01-15 14:23:45 - api.IBKR - INFO - [IBKR] → REQUEST: GET market_data/SPY
2024-01-15 14:23:46 - api.IBKR - INFO - [IBKR] ← RESPONSE: GET market_data/SPY | Status: success | Time: 1234.56ms
```

---

## 技术栈

- **后端**: FastAPI, SQLAlchemy, SQLite, ib_insync, futu-api, PyYAML
- **前端**: React, Vite, Tailwind CSS, Axios, Lucide Icons
- **数据库**: SQLite
- **日志**: Python logging, RotatingFileHandler

---

## 常见问题

### 1. start.sh 执行报错 "Python not found"

确保已安装 Python 3.10 或更高版本：
```bash
python3 --version
```

### 2. IBKR 连接失败

- 确认 IB Gateway 已启动并登录
- 检查端口号（Live: 4001, Paper: 4002）
- 确认 `config.yaml` 中 `ibkr.enabled: true`

### 3. 前端无法访问后端

- 检查后端是否启动成功
- 确认 CORS 配置包含前端地址

### 4. 如何查看当前数据源配置

```bash
curl http://localhost:8000/api/options/source/info
```

---

## 注意事项

1. IBKR 和富途 API 均为延迟数据，无需额外付费
2. 系统会自动保存历史数据用于计算 3D/5D 变化
3. 建议每日收盘后刷新数据
4. CLI 上传工具会自动过滤无效的 Ticker
5. 修改 `config.yaml` 后需重启服务生效

---

## License

MIT License
