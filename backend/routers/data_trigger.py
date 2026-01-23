"""
数据触发路由
负责处理 Finviz/MarketChameleon 数据导入后的 IBKR/Futu 数据获取触发逻辑
实现机构化多级锚定框架的数据层级管理
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum
import asyncio
import uuid
from datetime import datetime, date
import logging
import time

from ..database import get_db
from ..models import (
    FinvizData, MarketChameleonData, ETFHolding,
    SectorETF, IndustryETF, SymbolPool, SymbolETFMapping
)
from ..config_loader import get_current_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-trigger", tags=["数据触发"])


# ==================== 速率控制器 ====================

class RateLimiter:
    """
    速率控制器
    用于控制 API 调用频率，避免触发限流
    """
    def __init__(self, max_requests_per_minute: int = 50, name: str = "default"):
        self.max_requests_per_minute = max_requests_per_minute
        self.name = name
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """
        获取请求许可
        如果超过速率限制，会等待直到可以发送请求
        """
        async with self._lock:
            now = time.time()
            
            # 清理超过 60 秒的请求记录
            self._request_times = [t for t in self._request_times if now - t < 60]
            
            # 检查是否超过限制
            if len(self._request_times) >= self.max_requests_per_minute:
                # 计算需要等待的时间
                oldest = self._request_times[0]
                wait_time = 60 - (now - oldest) + 0.1  # 额外 0.1 秒缓冲
                
                if wait_time > 0:
                    logger.info(f"[{self.name}] 速率限制: 已达 {len(self._request_times)}/{self.max_requests_per_minute} 次/分钟, "
                               f"等待 {wait_time:.1f} 秒")
                    await asyncio.sleep(wait_time)
                    
                    # 重新清理
                    now = time.time()
                    self._request_times = [t for t in self._request_times if now - t < 60]
            
            # 记录本次请求
            self._request_times.append(now)
            
            logger.debug(f"[{self.name}] 速率: {len(self._request_times)}/{self.max_requests_per_minute} 次/分钟")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取速率统计"""
        now = time.time()
        recent = [t for t in self._request_times if now - t < 60]
        return {
            "name": self.name,
            "current_rate": len(recent),
            "max_rate": self.max_requests_per_minute,
            "utilization": len(recent) / self.max_requests_per_minute * 100
        }


# 创建速率控制器实例
_ibkr_rate_limiter = RateLimiter(max_requests_per_minute=45, name="IBKR")  # 预留 5 次缓冲
_futu_rate_limiter = RateLimiter(max_requests_per_minute=55, name="Futu")  # 预留 5 次缓冲


# ==================== 数据模型 ====================

class DataSourceStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ETFType(str, Enum):
    MARKET = "market"       # Level 0: SPY, QQQ
    SECTOR = "sector"       # Level 1: XLK, XLF, XLE...
    INDUSTRY = "industry"   # Level 2: SOXX, SMH, IGV...


class TopNAnalysisRequest(BaseModel):
    etf_symbol: str
    holdings_count: int = 40


class TopNAnalysisResult(BaseModel):
    top_n: int
    weight_coverage: float
    meets_threshold: bool


class TopNAnalysisResponse(BaseModel):
    etf_symbol: str
    total_holdings: int
    analysis: List[TopNAnalysisResult]
    recommended_top_n: int
    threshold: float = 0.70


class BatchUpdateRequest(BaseModel):
    symbols: List[str]
    sources: List[str] = ["ibkr", "futu"]
    etf_symbol: Optional[str] = None


class BatchUpdateStatus(BaseModel):
    session_id: str
    status: str  # pending, running, completed, cancelled, failed
    total: int
    completed: int
    current_symbol: Optional[str] = None
    current_source: Optional[str] = None
    errors: List[Dict[str, str]] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rate_stats: Optional[Dict[str, Any]] = None
    # 新增：预估时间相关
    elapsed_seconds: Optional[float] = None  # 已用时间（秒）
    avg_time_per_symbol: Optional[float] = None  # 每个标的平均时间（秒）
    eta_seconds: Optional[float] = None  # 预估剩余时间（秒）


class PendingSymbol(BaseModel):
    symbol: str
    weight: float
    has_finviz: bool
    has_mc: bool
    has_ibkr: bool
    has_futu: bool


class DataLayerItem(BaseModel):
    symbol: str
    name: str
    etf_type: ETFType
    data_status: Dict[str, str]
    etf_self_status: Dict[str, str] = {}
    holdings_status: Dict[str, str] = {}
    score: Optional[float] = None
    can_calculate: bool = False
    is_anchor: bool = False
    is_attack: bool = False
    holdings_count: int = 0
    top_n: int = 20
    industries: Optional[List[str]] = None


class DataOverviewResponse(BaseModel):
    level_0: List[DataLayerItem]
    level_1: List[DataLayerItem]
    level_2: Dict[str, List[DataLayerItem]]
    active_sector: Optional[str] = None


class QuickUpdateRequest(BaseModel):
    top_n: int = 20
    sources: List[str] = ["ibkr", "futu"]


# ==================== ETF 配置 ====================

ETF_CONFIG = {
    # Level 0 - 市场状态锚
    "SPY": {"name": "SPDR S&P 500", "type": ETFType.MARKET, "default_holdings": 503},
    "QQQ": {"name": "Invesco QQQ", "type": ETFType.MARKET, "default_holdings": 101},
    
    # Level 1 - 板块 ETF (11个GICS板块)
    "XLK": {"name": "科技板块", "type": ETFType.SECTOR, "default_holdings": 68, 
            "industries": ["SOXX", "SMH", "IGV", "CLOU", "HACK"]},
    "XLF": {"name": "金融板块", "type": ETFType.SECTOR, "default_holdings": 72,
            "industries": ["KBE", "KRE", "IAI"]},
    "XLE": {"name": "能源板块", "type": ETFType.SECTOR, "default_holdings": 23,
            "industries": ["XOP", "OIH", "VDE"]},
    "XLY": {"name": "非必需消费", "type": ETFType.SECTOR, "default_holdings": 53,
            "industries": ["XRT", "IBUY", "PEJ"]},
    "XLI": {"name": "工业板块", "type": ETFType.SECTOR, "default_holdings": 78,
            "industries": ["XAR", "ITA", "JETS"]},
    "XLV": {"name": "医疗保健", "type": ETFType.SECTOR, "default_holdings": 64,
            "industries": ["XBI", "IBB", "IHI"]},
    "XLC": {"name": "通信服务", "type": ETFType.SECTOR, "default_holdings": 26,
            "industries": ["FCOM", "VOX"]},
    "XLP": {"name": "必需消费", "type": ETFType.SECTOR, "default_holdings": 38,
            "industries": ["PBJ", "VDC"]},
    "XLU": {"name": "公用事业", "type": ETFType.SECTOR, "default_holdings": 31,
            "industries": ["VPU", "FUTY"]},
    "XLRE": {"name": "房地产", "type": ETFType.SECTOR, "default_holdings": 32,
             "industries": ["VNQ", "IYR"]},
    "XLB": {"name": "原材料", "type": ETFType.SECTOR, "default_holdings": 28,
            "industries": ["GDX", "XME", "LIT"]},
    
    # Level 2 - 行业 ETF
    "SOXX": {"name": "半导体行业锚", "type": ETFType.INDUSTRY, "default_holdings": 35, 
             "parent": "XLK", "is_anchor": True},
    "SMH": {"name": "半导体进攻锚", "type": ETFType.INDUSTRY, "default_holdings": 26, 
            "parent": "XLK", "is_attack": True},
    "IGV": {"name": "软件", "type": ETFType.INDUSTRY, "default_holdings": 103, "parent": "XLK"},
    "CLOU": {"name": "云计算", "type": ETFType.INDUSTRY, "default_holdings": 37, "parent": "XLK"},
    "HACK": {"name": "网络安全", "type": ETFType.INDUSTRY, "default_holdings": 26, "parent": "XLK"},
    "XBI": {"name": "生物技术", "type": ETFType.INDUSTRY, "default_holdings": 131, "parent": "XLV"},
    "IBB": {"name": "生物科技", "type": ETFType.INDUSTRY, "default_holdings": 271, "parent": "XLV"},
    "IHI": {"name": "医疗设备", "type": ETFType.INDUSTRY, "default_holdings": 60, "parent": "XLV"},
    "KBE": {"name": "银行", "type": ETFType.INDUSTRY, "default_holdings": 95, "parent": "XLF"},
    "KRE": {"name": "地区银行", "type": ETFType.INDUSTRY, "default_holdings": 135, "parent": "XLF"},
    "XOP": {"name": "油气开采", "type": ETFType.INDUSTRY, "default_holdings": 60, "parent": "XLE"},
    "OIH": {"name": "油服", "type": ETFType.INDUSTRY, "default_holdings": 25, "parent": "XLE"},
    "XRT": {"name": "零售", "type": ETFType.INDUSTRY, "default_holdings": 80, "parent": "XLY"},
    "XHB": {"name": "住宅建筑", "type": ETFType.INDUSTRY, "default_holdings": 35, "parent": "XLY"},
    "GDX": {"name": "黄金矿业", "type": ETFType.INDUSTRY, "default_holdings": 50, "parent": "XLB"},
    "XME": {"name": "金属矿业", "type": ETFType.INDUSTRY, "default_holdings": 30, "parent": "XLB"},
}

# 批量更新会话存储
_batch_sessions: Dict[str, BatchUpdateStatus] = {}


# ==================== 服务调用封装 ====================

async def fetch_ibkr_data(symbol: str, rate_limiter: RateLimiter) -> Dict[str, Any]:
    """
    从 IBKR 获取数据（带速率控制）
    仅获取市场数据（价格），期权数据由 Futu 提供
    """
    await rate_limiter.acquire()
    
    try:
        from ..services.ibkr_service import get_ibkr_service
        
        ibkr = get_ibkr_service()
        if not ibkr.enabled:
            return {"success": False, "error": "IBKR 服务未启用", "symbol": symbol}
        
        # 仅获取市场数据
        market_data = await ibkr.get_market_data(symbol)
        
        return {
            "success": market_data is not None and market_data.get('price') is not None,
            "symbol": symbol,
            "source": "ibkr",
            "market_data": market_data,
            "positioning_data": None,  # 期权数据由 Futu 获取
            "term_data": None,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.debug(f"IBKR {symbol} 异常: {e}")
        return {"success": False, "error": str(e), "symbol": symbol, "source": "ibkr"}


async def fetch_futu_data(symbol: str, rate_limiter: RateLimiter, underlying_price: float = None) -> Dict[str, Any]:
    """
    从 Futu 获取数据（带速率控制）
    主要获取期权数据（OI, IV）
    
    Args:
        symbol: 股票代码
        rate_limiter: 速率控制器
        underlying_price: 标的价格（从IBKR获取，用于计算ATM strike）
    """
    await rate_limiter.acquire()
    
    try:
        from ..services.futu_service import get_futu_service
        
        futu = get_futu_service()
        if not futu.enabled:
            return {"success": False, "error": "Futu 服务未启用", "symbol": symbol}
        
        # 获取期权数据（不再调用 get_market_snapshot，因为 Futu 没有美股行情权限）
        positioning_data = None
        term_data = None
        positioning_error = None
        term_error = None
        
        try:
            positioning_data = await futu.calculate_positioning_score(symbol)
        except Exception as e:
            positioning_error = str(e)
        
        try:
            # 传递 underlying_price 用于计算 ATM strike
            term_data = await futu.calculate_term_score(symbol, underlying_price)
        except Exception as e:
            term_error = str(e)
        
        # 判断成功：至少获取到 positioning 或 term 数据之一
        success = positioning_data is not None or term_data is not None
        
        # 构建错误信息
        error_msg = None
        if not success:
            errors = []
            if positioning_error:
                errors.append(f"positioning: {positioning_error}")
            if term_error:
                errors.append(f"term: {term_error}")
            if not errors:
                if underlying_price is None:
                    error_msg = "无标的价格，无法计算IV数据"
                else:
                    error_msg = "期权数据不可用"
            else:
                error_msg = "; ".join(errors)
        
        return {
            "success": success,
            "symbol": symbol,
            "source": "futu",
            "snapshot_data": None,  # Futu 没有美股行情权限
            "positioning_data": positioning_data,
            "term_data": term_data,
            "error": error_msg,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.debug(f"Futu {symbol} 异常: {e}")
        return {"success": False, "error": str(e), "symbol": symbol, "source": "futu"}


# ==================== 辅助函数 ====================

def get_etf_data_status(db: Session, symbol: str, today: date = None) -> Dict[str, str]:
    """获取 ETF 自身的数据完备状态"""
    if today is None:
        today = date.today()
    
    status = {}
    
    # 检查 Finviz 数据
    finviz = db.query(FinvizData).filter(
        FinvizData.etf_symbol == symbol,
        FinvizData.ticker == symbol,
        FinvizData.data_date == today
    ).first()
    status["finviz"] = DataSourceStatus.COMPLETE if finviz else DataSourceStatus.MISSING
    
    # 检查 MarketChameleon 数据
    mc = db.query(MarketChameleonData).filter(
        MarketChameleonData.symbol == symbol,
        MarketChameleonData.data_date == today
    ).first()
    status["mc"] = DataSourceStatus.COMPLETE if mc else DataSourceStatus.MISSING
    
    # IBKR 和 Futu 暂时标记为待获取（需要集成实际服务）
    status["ibkr"] = DataSourceStatus.MISSING
    status["futu"] = DataSourceStatus.MISSING
    
    return status


def get_holdings_data_status(db: Session, etf_symbol: str, today: date = None) -> Dict[str, str]:
    """获取 ETF 持仓成分股的数据完备状态"""
    if today is None:
        today = date.today()
    
    # 获取持仓列表
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == etf_symbol,
        ETFHolding.data_date == today
    ).all()
    
    if not holdings:
        return {
            "finviz": DataSourceStatus.MISSING,
            "mc": DataSourceStatus.MISSING,
            "ibkr": DataSourceStatus.MISSING,
            "futu": DataSourceStatus.MISSING
        }
    
    tickers = [h.ticker for h in holdings]
    
    # 检查各数据源覆盖情况
    finviz_count = db.query(FinvizData).filter(
        FinvizData.etf_symbol == etf_symbol,
        FinvizData.ticker.in_(tickers),
        FinvizData.data_date == today
    ).count()
    
    mc_count = db.query(MarketChameleonData).filter(
        MarketChameleonData.etf_symbol == etf_symbol,
        MarketChameleonData.symbol.in_(tickers),
        MarketChameleonData.data_date == today
    ).count()
    
    total = len(tickers)
    threshold = 0.7  # 70% 覆盖认为完整
    
    return {
        "finviz": DataSourceStatus.COMPLETE if finviz_count >= total * threshold else (
            DataSourceStatus.PARTIAL if finviz_count > 0 else DataSourceStatus.MISSING
        ),
        "mc": DataSourceStatus.COMPLETE if mc_count >= total * threshold else (
            DataSourceStatus.PARTIAL if mc_count > 0 else DataSourceStatus.MISSING
        ),
        "ibkr": DataSourceStatus.MISSING,
        "futu": DataSourceStatus.MISSING
    }


def calculate_weight_coverage(holdings: List, top_n: int) -> float:
    """计算 Top N 的权重覆盖率"""
    sorted_holdings = sorted(holdings, key=lambda x: x.weight, reverse=True)
    return sum(h.weight for h in sorted_holdings[:top_n]) / 100.0


async def _sync_to_momentum_stocks(db: Session, symbols: List[str]) -> int:
    """
    同步指定标的到 MomentumStock 表
    
    Args:
        db: 数据库会话
        symbols: 要同步的标的列表
    
    Returns:
        同步成功的数量
    """
    from ..models import SymbolPool, MomentumStock, ETFHolding, MarketChameleonData, FinvizData
    from ..services.calculation import CalculationService
    
    calc_service = CalculationService(db)
    synced = 0
    
    for ticker in symbols:
        try:
            # 获取 SymbolPool 数据
            pool = db.query(SymbolPool).filter(SymbolPool.ticker == ticker).first()
            if not pool or not pool.price:
                continue
            
            # 获取 ETF 关联信息
            holding = db.query(ETFHolding).filter(ETFHolding.ticker == ticker).first()
            
            # 获取 MarketChameleon 数据
            mc_data = db.query(MarketChameleonData).filter(
                MarketChameleonData.symbol == ticker
            ).order_by(MarketChameleonData.data_date.desc()).first()
            
            # 获取 Finviz 数据
            finviz_data = db.query(FinvizData).filter(
                FinvizData.ticker == ticker
            ).order_by(FinvizData.data_date.desc()).first()
            
            # 构建指标
            ibkr_metrics = {
                "price": pool.price or 0,
                "sma50": pool.sma50 or 0,
                "sma200": pool.sma200 or 0,
                "rsi": pool.rsi or 50,
                "return_20d": 0,
                "return_63d": 0,
                "near_high_dist": 0,
                "breakout_trigger": False,
                "volume_spike": 1.0,
                "ma_alignment": _get_ma_alignment(pool.price, pool.sma50, pool.sma200) if pool.price else "N/A",
                "slope_20d": 0,
                "continuity": 0.5,
                "max_drawdown_20d": 0,
                "atr_percent": finviz_data.atr / pool.price * 100 if finviz_data and finviz_data.atr and pool.price else 3,
                "dist_from_20ma": 0,
                "up_down_vol_ratio": 1.0
            }
            
            if finviz_data and pool.price:
                if finviz_data.sma50 and finviz_data.sma50 > 0:
                    ibkr_metrics["dist_from_20ma"] = ((pool.price - finviz_data.sma50) / finviz_data.sma50) * 100
                if finviz_data.high_52w and finviz_data.high_52w > 0:
                    ibkr_metrics["near_high_dist"] = (pool.price / finviz_data.high_52w) * 100
            
            # 确定板块和行业
            sector = holding.sector_etf_symbol if holding else ""
            industry = holding.industry_etf_symbol if holding else ""
            
            # 更新或创建 MomentumStock
            stock = db.query(MomentumStock).filter(MomentumStock.symbol == ticker).first()
            if not stock:
                stock = MomentumStock(symbol=ticker)
                db.add(stock)
            
            stock.name = ticker
            stock.price = pool.price
            stock.sector = sector or ""
            stock.industry = industry or ""
            
            # 计算评分
            pm_score = calc_service.calculate_price_momentum_score(ibkr_metrics)
            ts_score = calc_service.calculate_trend_structure_score(ibkr_metrics)
            vp_score = calc_service.calculate_volume_price_score(ibkr_metrics)
            qf_score, heat_level = calc_service.calculate_quality_filter_score(ibkr_metrics)
            oo_score, heat, rel_vol, ivr, iv30 = calc_service.calculate_options_overlay_score(mc_data)
            
            stock.price_momentum_score = pm_score
            stock.trend_structure_score = ts_score
            stock.volume_price_score = vp_score
            stock.quality_filter_score = qf_score
            stock.heat_level = heat_level
            stock.options_overlay_score = oo_score
            stock.options_heat = heat
            stock.options_rel_vol = rel_vol
            stock.options_ivr = ivr
            stock.options_iv30 = pool.iv30 if pool.iv30 else iv30
            
            stock.final_score = calc_service.calculate_stock_composite_score(
                pm_score, ts_score, vp_score, oo_score, qf_score
            )
            
            stock.return_20d = f"+{ibkr_metrics.get('return_20d', 0):.1f}%"
            stock.return_63d = f"+{ibkr_metrics.get('return_63d', 0):.1f}%"
            stock.near_high_dist = f"{ibkr_metrics.get('near_high_dist', 0):.0f}%"
            stock.ma_alignment = ibkr_metrics.get("ma_alignment", "N/A")
            
            synced += 1
            
        except Exception as e:
            logger.debug(f"同步 {ticker} 失败: {e}")
    
    db.commit()
    return synced


def can_calculate_score(etf_status: Dict[str, str], holdings_status: Dict[str, str]) -> bool:
    """判断是否满足评分计算的最低条件"""
    # 至少需要 ETF 自身和持仓的 finviz + mc 完备
    etf_ok = (etf_status.get("finviz") == DataSourceStatus.COMPLETE and
              etf_status.get("mc") == DataSourceStatus.COMPLETE)
    holdings_ok = (holdings_status.get("finviz") in [DataSourceStatus.COMPLETE, DataSourceStatus.PARTIAL] and
                   holdings_status.get("mc") in [DataSourceStatus.COMPLETE, DataSourceStatus.PARTIAL])
    return etf_ok or holdings_ok


async def batch_update_task(session_id: str, symbols: List[str], sources: List[str]):
    """
    后台批量更新任务（集成真实服务调用和速率控制）
    日志格式：✓ [1/10] MU $98.50
    
    数据流：
    1. IBKR 获取市场数据（价格）
    2. Futu 获取期权数据（使用IBKR的价格计算ATM strike）
    3. 保存数据到 SymbolPool 表
    """
    from ..database import SessionLocal
    from ..models import SymbolPool
    
    session = _batch_sessions.get(session_id)
    if not session:
        return
    
    session.status = "running"
    session.started_at = datetime.now()
    
    total = len(symbols)
    sources_str = '+'.join(s.upper() for s in sources)
    logger.info(f"📊 批量更新 [{sources_str}] 共 {total} 个标的")
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        for i, symbol in enumerate(symbols):
            if session.status == "cancelled":
                logger.info(f"📊 任务已取消 [{i}/{total}]")
                break
            
            session.current_symbol = symbol
            symbol_success = True
            underlying_price = None
            market_data = None
            positioning_data = None
            term_data = None
            
            for source in sources:
                if session.status == "cancelled":
                    break
                
                session.current_source = source
                
                try:
                    if source == "ibkr":
                        result = await fetch_ibkr_data(symbol, _ibkr_rate_limiter)
                        session.rate_stats = {
                            "ibkr": _ibkr_rate_limiter.get_stats(),
                            "futu": _futu_rate_limiter.get_stats()
                        }
                        if result.get("success") and result.get("market_data"):
                            market_data = result["market_data"]
                            underlying_price = market_data.get("price")
                            if underlying_price is None:
                                logger.debug(f"{symbol} - IBKR 返回数据但价格为空")
                        else:
                            logger.debug(f"{symbol} - IBKR 获取失败: {result.get('error', '无数据')}")
                            
                    elif source == "futu":
                        result = await fetch_futu_data(symbol, _futu_rate_limiter, underlying_price)
                        session.rate_stats = {
                            "ibkr": _ibkr_rate_limiter.get_stats(),
                            "futu": _futu_rate_limiter.get_stats()
                        }
                        if result.get("success"):
                            positioning_data = result.get("positioning_data")
                            term_data = result.get("term_data")
                    else:
                        result = {"success": False, "error": f"未知数据源: {source}"}
                    
                    if not result.get("success"):
                        session.errors.append({
                            "symbol": symbol, 
                            "source": source, 
                            "error": result.get("error", "未知错误")
                        })
                        symbol_success = False
                        
                except Exception as e:
                    session.errors.append({
                        "symbol": symbol, 
                        "source": source, 
                        "error": str(e)
                    })
                    symbol_success = False
            
            # 保存数据到 SymbolPool（只要有任何数据就保存，不要求全部成功）
            # 修复：即使 Futu 失败，IBKR 数据也应该保存
            has_any_data = market_data or positioning_data or term_data
            if has_any_data:
                try:
                    pool_record = db.query(SymbolPool).filter(SymbolPool.ticker == symbol).first()
                    if not pool_record:
                        pool_record = SymbolPool(ticker=symbol)
                        db.add(pool_record)
                    
                    # 更新市场数据（IBKR）
                    if market_data:
                        pool_record.price = market_data.get("price")
                        pool_record.sma50 = market_data.get("sma50")
                        pool_record.sma200 = market_data.get("sma200")
                        pool_record.rsi = market_data.get("rsi")
                        pool_record.ibkr_status = "ready"
                        pool_record.ibkr_last_update = datetime.now()
                    
                    # 更新期权数据（Futu）
                    if positioning_data:
                        pool_record.positioning_score = positioning_data.get("positioning_score")
                        pool_record.total_oi = positioning_data.get("total_oi")
                        pool_record.delta_oi_1d = positioning_data.get("delta_oi_1d")
                        pool_record.futu_status = "ready"
                        pool_record.futu_last_update = datetime.now()
                    
                    if term_data:
                        pool_record.term_score = term_data.get("slope")
                        pool_record.iv7 = term_data.get("iv7")
                        pool_record.iv30 = term_data.get("iv30")
                        pool_record.iv60 = term_data.get("iv60")
                        pool_record.iv90 = term_data.get("iv90")
                        pool_record.iv_slope = term_data.get("slope")
                        # 如果 positioning_data 没有 total_oi，从 term_data 获取
                        if not pool_record.total_oi and term_data.get("total_oi"):
                            pool_record.total_oi = term_data.get("total_oi")
                    
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.debug(f"保存 {symbol} 数据失败: {e}")
            
            session.completed = i + 1
            
            # 增强的队列式日志（参考 volatility_analysis 风格）
            log_parts = [f"[{session.completed}/{total}]", symbol]
            
            # 价格信息
            if underlying_price:
                log_parts.append(f"${underlying_price:.2f}")
            
            if symbol_success:
                # IV 期限结构信息
                iv_parts = []
                if term_data:
                    iv30 = term_data.get("iv30")
                    iv60 = term_data.get("iv60")
                    iv90 = term_data.get("iv90")
                    if iv30 is not None:
                        # IV 可能是小数形式(0.35)或百分比形式(35.0)，统一显示为百分比
                        iv30_pct = iv30 * 100 if iv30 < 5 else iv30
                        iv_parts.append(f"IV30={iv30_pct:.1f}%")
                    if iv60 is not None:
                        iv60_pct = iv60 * 100 if iv60 < 5 else iv60
                        iv_parts.append(f"IV60={iv60_pct:.1f}%")
                    if iv90 is not None:
                        iv90_pct = iv90 * 100 if iv90 < 5 else iv90
                        iv_parts.append(f"IV90={iv90_pct:.1f}%")
                
                if iv_parts:
                    log_parts.append("|")
                    log_parts.extend(iv_parts)
                
                # OI 信息
                if positioning_data:
                    total_oi = positioning_data.get("total_oi")
                    delta_oi = positioning_data.get("delta_oi_1d")
                    if total_oi:
                        oi_str = f"OI={total_oi:,}"
                        if delta_oi is not None:
                            sign = "+" if delta_oi >= 0 else ""
                            oi_str += f" (Δ{sign}{delta_oi:,})"
                        log_parts.append(f"| {oi_str}")
                
                # Positioning Score 信息
                if positioning_data:
                    ps = positioning_data.get("positioning_score")
                    if ps is not None:
                        log_parts.append(f"| PS={ps:.2f}")
                
                logger.info(f"✓ {' '.join(log_parts)}")
            else:
                # 失败时显示具体原因
                last_error = session.errors[-1] if session.errors else {}
                error_source = last_error.get("source", "").upper()
                error_msg = last_error.get("error", "未知错误")
                
                # 简化错误信息
                if "implied_volatility" in error_msg.lower() or "iv" in error_msg.lower():
                    error_hint = "IV数据不可用"
                elif "timeout" in error_msg.lower() or "超时" in error_msg:
                    error_hint = "连接超时"
                elif "connect" in error_msg.lower() or "连接" in error_msg:
                    error_hint = "连接失败"
                elif "期权" in error_msg or "option" in error_msg.lower():
                    error_hint = "无期权数据"
                elif "标的价格" in error_msg or "underlying" in error_msg.lower():
                    error_hint = "无法获取标的价格"
                elif "price" in error_msg.lower() or "价格" in error_msg:
                    error_hint = "价格数据不可用"
                elif error_msg == "未知错误":
                    # 尝试根据数据源给出更有意义的提示
                    if error_source == "FUTU":
                        error_hint = "Futu期权数据不可用"
                    elif error_source == "IBKR":
                        error_hint = "IBKR市场数据不可用"
                    else:
                        error_hint = "数据获取失败"
                else:
                    error_hint = error_msg[:30] if len(error_msg) > 30 else error_msg
                
                if underlying_price:
                    logger.warning(f"⚠ {' '.join(log_parts)} | {error_source}: {error_hint}")
                else:
                    logger.warning(f"✗ {' '.join(log_parts)} | {error_hint}")
        
        if session.status != "cancelled":
            session.status = "completed"
        
        session.completed_at = datetime.now()
        session.current_symbol = None
        session.current_source = None
        
        duration = (session.completed_at - session.started_at).total_seconds()
        error_count = len(session.errors)
        avg_time = duration / total if total > 0 else 0
        
        # 增强的汇总日志
        if error_count > 0:
            logger.info(f"📊 完成 {session.completed}/{total} (失败: {error_count}) 耗时 {duration:.1f}s | 平均 {avg_time:.1f}s/标的")
        else:
            logger.info(f"📊 完成 {session.completed}/{total} 耗时 {duration:.1f}s | 平均 {avg_time:.1f}s/标的")
        
        # 自动同步到 MomentumStock 表（确保动能股池有数据）
        try:
            synced_count = await _sync_to_momentum_stocks(db, symbols)
            if synced_count > 0:
                logger.info(f"📊 已同步 {synced_count} 条数据到动能股池")
        except Exception as sync_err:
            logger.warning(f"同步到动能股池失败: {sync_err}")
    
    finally:
        db.close()


# ==================== API 端点 ====================

@router.get("/overview", response_model=DataOverviewResponse)
async def get_data_overview(db: Session = Depends(get_db)):
    """
    获取数据层级概览
    返回 Level 0/1/2 各层级的 ETF 数据状态
    
    优化：只有配置/上传了 holdings 的 ETF 才会显示在列表中
    """
    today = date.today()
    level_0 = []
    level_1 = []
    level_2 = {}
    
    # 从数据库获取实际的 ETF 列表
    sector_etfs = db.query(SectorETF).all()
    industry_etfs = db.query(IndustryETF).all()
    
    # 构建已存在的 ETF 集合
    db_sectors = {e.symbol for e in sector_etfs}
    db_industries = {e.symbol for e in industry_etfs}
    
    # 获取所有有持仓数据的 ETF 符号（不限制日期）
    etfs_with_holdings = set(
        row[0] for row in db.query(ETFHolding.etf_symbol).distinct().all()
    )
    
    for symbol, config in ETF_CONFIG.items():
        etf_type = config["type"]
        
        # 【优化变更】板块 ETF 和行业 ETF 必须有 holdings 才显示
        # Level 0 (市场锚如 SPY, QQQ) 始终显示
        if etf_type != ETFType.MARKET and symbol not in etfs_with_holdings:
            continue
        
        etf_self_status = get_etf_data_status(db, symbol, today)
        holdings_status = get_holdings_data_status(db, symbol, today)
        
        # 合并状态
        combined_status = {}
        for key in ["finviz", "mc", "ibkr", "futu"]:
            etf_val = etf_self_status.get(key, DataSourceStatus.MISSING)
            hold_val = holdings_status.get(key, DataSourceStatus.MISSING)
            if etf_val == DataSourceStatus.COMPLETE and hold_val == DataSourceStatus.COMPLETE:
                combined_status[key] = DataSourceStatus.COMPLETE
            elif etf_val != DataSourceStatus.MISSING or hold_val != DataSourceStatus.MISSING:
                combined_status[key] = DataSourceStatus.PARTIAL
            else:
                combined_status[key] = DataSourceStatus.MISSING
        
        # 获取持仓数量（任意日期）
        holdings_count = db.query(ETFHolding).filter(
            ETFHolding.etf_symbol == symbol
        ).count()
        
        item = DataLayerItem(
            symbol=symbol,
            name=config["name"],
            etf_type=config["type"],
            data_status=combined_status,
            etf_self_status=etf_self_status,
            holdings_status=holdings_status,
            can_calculate=can_calculate_score(etf_self_status, holdings_status),
            is_anchor=config.get("is_anchor", False),
            is_attack=config.get("is_attack", False),
            holdings_count=holdings_count or config.get("default_holdings", 0),
            top_n=20 if config["type"] == ETFType.SECTOR else 15,
            industries=config.get("industries")
        )
        
        if config["type"] == ETFType.MARKET:
            level_0.append(item)
        elif config["type"] == ETFType.SECTOR:
            level_1.append(item)
        elif config["type"] == ETFType.INDUSTRY:
            parent = config.get("parent", "OTHER")
            if parent not in level_2:
                level_2[parent] = []
            level_2[parent].append(item)
    
    return DataOverviewResponse(
        level_0=level_0,
        level_1=level_1,
        level_2=level_2
    )


@router.post("/analyze-top-n", response_model=TopNAnalysisResponse)
async def analyze_top_n(request: TopNAnalysisRequest, db: Session = Depends(get_db)):
    """
    分析 ETF 持仓的 Top N 权重覆盖率
    返回 Top 10/15/20/25 各档位的覆盖率和推荐值
    """
    etf_symbol = request.etf_symbol.upper()
    today = date.today()
    
    # 获取持仓数据
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == etf_symbol,
        ETFHolding.data_date == today
    ).order_by(ETFHolding.weight.desc()).all()
    
    if not holdings:
        # 尝试获取任意日期的数据
        holdings = db.query(ETFHolding).filter(
            ETFHolding.etf_symbol == etf_symbol
        ).order_by(ETFHolding.weight.desc()).all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"未找到 {etf_symbol} 的持仓数据")
    
    threshold = 0.70
    top_n_values = [10, 15, 20, 25, 30]
    analysis = []
    recommended = 20
    
    total_weight = sum(h.weight for h in holdings)
    
    for n in top_n_values:
        if n > len(holdings):
            continue
        top_weight = sum(h.weight for h in holdings[:n])
        coverage = top_weight / total_weight if total_weight > 0 else 0
        meets = coverage >= threshold
        analysis.append(TopNAnalysisResult(
            top_n=n,
            weight_coverage=round(coverage, 4),
            meets_threshold=meets
        ))
        if meets and recommended == 20:
            recommended = n
    
    return TopNAnalysisResponse(
        etf_symbol=etf_symbol,
        total_holdings=len(holdings),
        analysis=analysis,
        recommended_top_n=recommended,
        threshold=threshold
    )


@router.get("/pending-symbols/{etf_symbol}", response_model=List[PendingSymbol])
async def get_pending_symbols(
    etf_symbol: str, 
    top_n: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取 ETF 持仓中待更新实时数据的标的列表
    """
    etf_symbol = etf_symbol.upper()
    today = date.today()
    
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == etf_symbol
    ).order_by(ETFHolding.weight.desc()).limit(top_n).all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"未找到 {etf_symbol} 的持仓数据")
    
    result = []
    for h in holdings:
        ticker = h.ticker
        
        # 检查各数据源
        has_finviz = db.query(FinvizData).filter(
            FinvizData.ticker == ticker,
            FinvizData.data_date == today
        ).first() is not None
        
        has_mc = db.query(MarketChameleonData).filter(
            MarketChameleonData.symbol == ticker,
            MarketChameleonData.data_date == today
        ).first() is not None
        
        result.append(PendingSymbol(
            symbol=ticker,
            weight=h.weight,
            has_finviz=has_finviz,
            has_mc=has_mc,
            has_ibkr=False,  # 待实现
            has_futu=False   # 待实现
        ))
    
    return result


@router.post("/batch-update", response_model=BatchUpdateStatus)
async def start_batch_update(
    request: BatchUpdateRequest, 
    background_tasks: BackgroundTasks
):
    """
    启动批量更新任务（带速率控制）
    
    速率限制:
    - IBKR: ~45 次/分钟 (预留 5 次缓冲)
    - Futu: ~55 次/分钟 (预留 5 次缓冲)
    """
    session_id = str(uuid.uuid4())
    
    status = BatchUpdateStatus(
        session_id=session_id,
        status="pending",
        total=len(request.symbols),
        completed=0,
        errors=[],
        rate_stats={
            "ibkr": _ibkr_rate_limiter.get_stats(),
            "futu": _futu_rate_limiter.get_stats()
        }
    )
    
    _batch_sessions[session_id] = status
    background_tasks.add_task(batch_update_task, session_id, request.symbols, request.sources)
    
    logger.info(f"[批量更新] 创建任务 {session_id}: {len(request.symbols)} 个标的")
    
    return status


@router.get("/batch-update/{session_id}", response_model=BatchUpdateStatus)
async def get_batch_update_status(session_id: str):
    """获取批量更新任务状态，包含预估完成时间"""
    status = _batch_sessions.get(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="未找到该更新会话")
    
    # 更新速率统计
    status.rate_stats = {
        "ibkr": _ibkr_rate_limiter.get_stats(),
        "futu": _futu_rate_limiter.get_stats()
    }
    
    # 计算预估时间
    if status.started_at and status.status == "running":
        elapsed = (datetime.now() - status.started_at).total_seconds()
        status.elapsed_seconds = round(elapsed, 1)
        
        if status.completed > 0:
            avg_time = elapsed / status.completed
            status.avg_time_per_symbol = round(avg_time, 2)
            
            remaining = status.total - status.completed
            eta = avg_time * remaining
            status.eta_seconds = round(eta, 1)
    
    return status


@router.post("/batch-update/{session_id}/cancel")
async def cancel_batch_update(session_id: str):
    """取消批量更新任务"""
    status = _batch_sessions.get(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="未找到该更新会话")
    
    if status.status == "running":
        status.status = "cancelled"
        logger.info(f"[批量更新] 任务 {session_id} 已请求取消")
        return {"message": "已取消更新任务", "session_id": session_id}
    return {"message": f"任务状态为 {status.status}，无法取消", "session_id": session_id}


@router.post("/quick-update/{etf_symbol}")
async def quick_update(
    etf_symbol: str, 
    request: QuickUpdateRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    快捷更新：一键获取 ETF 持仓 Top N 的实时数据
    
    速率限制:
    - IBKR: ~45 次/分钟
    - Futu: ~55 次/分钟
    - 预计耗时: Top 20 约 1-2 分钟（取决于数据源）
    """
    etf_symbol = etf_symbol.upper()
    
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == etf_symbol
    ).order_by(ETFHolding.weight.desc()).limit(request.top_n).all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"未找到 {etf_symbol} 的持仓数据")
    
    symbols_to_update = [h.ticker for h in holdings]
    
    if not symbols_to_update:
        return {"message": "所有标的数据已完备", "symbols_updated": 0}
    
    # 估算耗时
    estimated_time = len(symbols_to_update) * len(request.sources) * 1.5  # 每个请求约 1.5 秒
    
    batch_request = BatchUpdateRequest(
        symbols=symbols_to_update,
        sources=request.sources,
        etf_symbol=etf_symbol
    )
    
    result = await start_batch_update(batch_request, background_tasks)
    
    return {
        **result.dict(),
        "estimated_time_seconds": estimated_time,
        "message": f"已启动 Top {request.top_n} 更新任务，预计耗时 {estimated_time:.0f} 秒"
    }


@router.get("/etf-holdings/{etf_symbol}")
async def get_etf_holdings_detail(
    etf_symbol: str, 
    top_n: int = 20,
    db: Session = Depends(get_db)
):
    """获取 ETF 持仓明细及数据状态"""
    etf_symbol = etf_symbol.upper()
    today = date.today()
    
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == etf_symbol
    ).order_by(ETFHolding.weight.desc()).limit(top_n).all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"未找到 {etf_symbol} 的持仓数据")
    
    result = []
    for h in holdings:
        ticker = h.ticker
        
        finviz = db.query(FinvizData).filter(
            FinvizData.ticker == ticker,
            FinvizData.data_date == today
        ).first()
        
        mc = db.query(MarketChameleonData).filter(
            MarketChameleonData.symbol == ticker,
            MarketChameleonData.data_date == today
        ).first()
        
        data_status = {
            "finviz": DataSourceStatus.COMPLETE if finviz else DataSourceStatus.MISSING,
            "mc": DataSourceStatus.COMPLETE if mc else DataSourceStatus.MISSING,
            "ibkr": DataSourceStatus.MISSING,
            "futu": DataSourceStatus.MISSING
        }
        
        # 计算 50MA/200MA 状态
        above_50ma = None
        above_200ma = None
        if finviz and finviz.price and finviz.sma50:
            above_50ma = finviz.price > finviz.sma50
        if finviz and finviz.price and finviz.sma200:
            above_200ma = finviz.price > finviz.sma200
        
        result.append({
            "symbol": ticker,
            "name": "",
            "weight": h.weight,
            "data_status": data_status,
            "above_50ma": above_50ma,
            "above_200ma": above_200ma,
            "price": finviz.price if finviz else None,
            "rsi": finviz.rsi if finviz else None,
            "ivr": mc.ivr if mc else None
        })
    
    # 计算广度统计
    above_50ma_count = sum(1 for r in result if r.get("above_50ma") is True)
    above_200ma_count = sum(1 for r in result if r.get("above_200ma") is True)
    total_with_data = sum(1 for r in result if r.get("above_50ma") is not None)
    
    config = ETF_CONFIG.get(etf_symbol, {"name": etf_symbol, "type": "unknown"})
    
    return {
        "etf_symbol": etf_symbol,
        "config": {
            "name": config.get("name", etf_symbol),
            "type": config.get("type", "unknown"),
            "default_holdings": config.get("default_holdings", 0)
        },
        "holdings": result,
        "total_weight": sum(h.weight for h in holdings),
        "breadth": {
            "above_50ma": f"{above_50ma_count}/{total_with_data}" if total_with_data > 0 else "0/0",
            "above_200ma": f"{above_200ma_count}/{total_with_data}" if total_with_data > 0 else "0/0",
            "above_50ma_pct": round(above_50ma_count / total_with_data * 100, 1) if total_with_data > 0 else 0,
            "above_200ma_pct": round(above_200ma_count / total_with_data * 100, 1) if total_with_data > 0 else 0
        }
    }


@router.get("/rate-stats")
async def get_rate_stats():
    """获取当前速率控制统计"""
    return {
        "ibkr": _ibkr_rate_limiter.get_stats(),
        "futu": _futu_rate_limiter.get_stats()
    }


@router.post("/reset-sessions")
async def reset_batch_sessions():
    """重置所有批量更新会话（用于调试）"""
    _batch_sessions.clear()
    return {"message": "已重置所有会话"}


@router.post("/sync-momentum-stocks")
async def sync_momentum_stocks(
    industry_symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    从 SymbolPool 同步数据到 MomentumStock 表
    
    这个接口解决"动能股池无数据"的问题：
    - 从 SymbolPool 获取有实时数据的标的
    - 创建/更新 MomentumStock 记录
    - 计算综合评分
    
    Args:
        industry_symbol: 可选，指定行业 ETF 符号，只同步该行业的标的
    """
    from ..models import SymbolPool, MomentumStock, ETFHolding, MarketChameleonData, FinvizData
    from ..services.calculation import CalculationService
    
    calc_service = CalculationService(db)
    
    # 获取有实时数据的 SymbolPool 记录
    pool_query = db.query(SymbolPool).filter(
        SymbolPool.ibkr_status == "ready"  # 至少有 IBKR 数据
    )
    
    pool_records = pool_query.all()
    
    if not pool_records:
        return {
            "success": True,
            "message": "没有可同步的数据",
            "synced": 0,
            "skipped": 0
        }
    
    synced = 0
    skipped = 0
    errors = []
    
    for pool in pool_records:
        try:
            ticker = pool.ticker
            
            # 获取该标的的 ETF 关联信息
            holding = db.query(ETFHolding).filter(
                ETFHolding.ticker == ticker
            ).first()
            
            if not holding:
                skipped += 1
                continue
            
            # 如果指定了行业，只同步该行业的标的
            if industry_symbol:
                if holding.industry_etf_symbol != industry_symbol.upper():
                    skipped += 1
                    continue
            
            # 获取 MarketChameleon 数据
            mc_data = db.query(MarketChameleonData).filter(
                MarketChameleonData.symbol == ticker
            ).order_by(MarketChameleonData.data_date.desc()).first()
            
            # 获取 Finviz 数据
            finviz_data = db.query(FinvizData).filter(
                FinvizData.ticker == ticker
            ).order_by(FinvizData.data_date.desc()).first()
            
            # 构建 IBKR 指标（从 SymbolPool 数据）
            ibkr_metrics = {
                "price": pool.price or 0,
                "sma50": pool.sma50 or 0,
                "sma200": pool.sma200 or 0,
                "rsi": pool.rsi or 50,
                # 计算返回率（如果有历史数据可以更精确）
                "return_20d": 0,
                "return_20d_ex3": 0,
                "return_63d": 0,
                "near_high_dist": 0,
                "breakout_trigger": False,
                "volume_spike": 1.0,
                "ma_alignment": _get_ma_alignment(pool.price, pool.sma50, pool.sma200) if pool.price else "N/A",
                "slope_20d": 0,
                "continuity": 0.5,
                "max_drawdown_20d": 0,
                "atr_percent": finviz_data.atr / pool.price * 100 if finviz_data and finviz_data.atr and pool.price else 3,
                "dist_from_20ma": 0,
                "up_down_vol_ratio": 1.0
            }
            
            # 如果有 Finviz 数据，补充更多指标
            if finviz_data and pool.price:
                if finviz_data.sma50 and finviz_data.sma50 > 0:
                    ibkr_metrics["dist_from_20ma"] = ((pool.price - finviz_data.sma50) / finviz_data.sma50) * 100
                if finviz_data.high_52w and finviz_data.high_52w > 0:
                    ibkr_metrics["near_high_dist"] = (pool.price / finviz_data.high_52w) * 100
            
            # 确定板块和行业
            sector = holding.sector_etf_symbol or ""
            industry = holding.industry_etf_symbol or ""
            
            # 更新或创建 MomentumStock
            stock = db.query(MomentumStock).filter(MomentumStock.symbol == ticker).first()
            if not stock:
                stock = MomentumStock(symbol=ticker)
                db.add(stock)
            
            # 基本信息
            stock.name = ticker
            stock.price = pool.price
            stock.sector = sector
            stock.industry = industry
            
            # 计算评分
            pm_score = calc_service.calculate_price_momentum_score(ibkr_metrics)
            ts_score = calc_service.calculate_trend_structure_score(ibkr_metrics)
            vp_score = calc_service.calculate_volume_price_score(ibkr_metrics)
            qf_score, heat_level = calc_service.calculate_quality_filter_score(ibkr_metrics)
            oo_score, heat, rel_vol, ivr, iv30 = calc_service.calculate_options_overlay_score(mc_data)
            
            stock.price_momentum_score = pm_score
            stock.trend_structure_score = ts_score
            stock.volume_price_score = vp_score
            stock.quality_filter_score = qf_score
            stock.heat_level = heat_level
            
            stock.options_overlay_score = oo_score
            stock.options_heat = heat
            stock.options_rel_vol = rel_vol
            stock.options_ivr = ivr
            stock.options_iv30 = iv30
            
            # 期权 IV 数据（从 SymbolPool）
            if pool.iv30:
                stock.options_iv30 = pool.iv30
            
            # 计算最终评分
            stock.final_score = calc_service.calculate_stock_composite_score(
                pm_score, ts_score, vp_score, oo_score, qf_score
            )
            
            # 填充其他字段
            stock.return_20d = f"+{ibkr_metrics.get('return_20d', 0):.1f}%"
            stock.return_63d = f"+{ibkr_metrics.get('return_63d', 0):.1f}%"
            stock.near_high_dist = f"{ibkr_metrics.get('near_high_dist', 0):.0f}%"
            stock.ma_alignment = ibkr_metrics.get("ma_alignment", "N/A")
            stock.breakout_trigger = ibkr_metrics.get("breakout_trigger", False)
            stock.volume_spike = ibkr_metrics.get("volume_spike", 1.0)
            
            synced += 1
            
        except Exception as e:
            errors.append({"symbol": pool.ticker, "error": str(e)})
            logger.error(f"同步 {pool.ticker} 到 MomentumStock 失败: {e}")
    
    db.commit()
    
    message = f"同步完成: {synced} 条成功, {skipped} 条跳过"
    if errors:
        message += f", {len(errors)} 条失败"
    
    return {
        "success": True,
        "message": message,
        "synced": synced,
        "skipped": skipped,
        "errors": errors[:10]  # 最多返回10条错误
    }


def _get_ma_alignment(price: float, sma50: float, sma200: float) -> str:
    """计算均线排列状态"""
    if not price or not sma50:
        return "N/A"
    
    if price > sma50:
        if sma200 and sma50 > sma200:
            return "P>50MA>200MA (强势)"
        return "P>50MA"
    else:
        if sma200 and price < sma200:
            return "P<50MA<200MA (弱势)"
        return "P<50MA"


@router.get("/ibkr-diagnostic")
async def ibkr_diagnostic():
    """
    IBKR 连接诊断
    用于排查连接问题和数据获取问题
    """
    from ..services.ibkr_service import get_ibkr_service
    from ..config_loader import get_current_config
    
    config = get_current_config()
    result = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "host": config.ibkr.host,
            "port": config.ibkr.port,
            "client_id": config.ibkr.client_id,
            "enabled": config.ibkr.enabled,
            "connection_timeout": config.ibkr.connection_timeout,
            "qualify_timeout": config.ibkr.qualify_timeout,
            "request_timeout": config.ibkr.request_timeout,
            "historical_timeout": config.ibkr.historical_timeout,
            "market_data_type": config.ibkr.market_data_type,
            "market_data_type_desc": "延迟数据(免费)" if config.ibkr.market_data_type == 3 else "实时数据(需订阅)"
        },
        "connection": {
            "status": "unknown",
            "message": ""
        },
        "test_results": {}
    }
    
    if not config.ibkr.enabled:
        result["connection"]["status"] = "disabled"
        result["connection"]["message"] = "IBKR 服务在配置中已禁用"
        return result
    
    try:
        ibkr = get_ibkr_service()
        
        connect_start = time.time()
        connected = await ibkr.connect()
        connect_duration = (time.time() - connect_start) * 1000
        
        result["connection"]["status"] = "connected" if connected else "failed"
        result["connection"]["duration_ms"] = round(connect_duration, 0)
        
        if connected:
            result["connection"]["message"] = "连接成功"
            result["connection"]["accounts"] = ibkr.ib.managedAccounts() if ibkr.ib else []
            
            # 测试获取 SPY 市场数据
            test_start = time.time()
            try:
                spy_data = await ibkr.get_market_data("SPY")
                test_duration = (time.time() - test_start) * 1000
                
                result["test_results"]["spy_market_data"] = {
                    "status": "success" if spy_data and spy_data.get("price") else "no_data",
                    "price": spy_data.get("price") if spy_data else None,
                    "duration_ms": round(test_duration, 0),
                    "data_source": "delayed" if spy_data and spy_data.get("price") else "none"
                }
            except Exception as e:
                result["test_results"]["spy_market_data"] = {
                    "status": "error",
                    "error": str(e),
                    "duration_ms": round((time.time() - test_start) * 1000, 0)
                }
        else:
            result["connection"]["message"] = "连接失败，请检查: 1) IB Gateway/TWS 是否运行 2) 端口配置是否正确 3) API 是否已启用"
    
    except Exception as e:
        result["connection"]["status"] = "error"
        result["connection"]["message"] = f"诊断过程异常: {str(e)}"
    
    return result

