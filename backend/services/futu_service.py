"""
Futu OpenAPI Service for Options Data
Provides PositioningScore and TermScore calculations

借鉴 volatility_analysis 项目的最佳实践:
1. 使用 delta ≈ 0.5 选择 ATM 期权
2. 从 get_market_snapshot 获取 IV 和 OI
3. 使用方差插值计算 IV30/IV60/IV90
4. OI 缓存支持 ΔOI 计算
"""
import asyncio
import json
import os
import time
import threading
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import logging

from futu import OpenQuoteContext, RET_OK, Market, OptionType, OptionCondType

from ..config_loader import get_current_config
from ..logging_utils import get_api_logger, LogContext

logger = logging.getLogger(__name__)
api_logger = get_api_logger("FUTU")

# OI 缓存配置
OI_CACHE_FILE = "oi_cache.json"
CACHE_LOCK = threading.Lock()


class RateLimiter:
    """
    速率限制器（借鉴 volatility_analysis）
    
    Futu API 限制：
    - get_option_chain: 10次/30秒
    - get_market_snapshot: 60次/30秒
    """
    def __init__(self, max_calls: int, period_seconds: int):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.calls: List[float] = []
        self._lock = threading.Lock()
    
    async def acquire(self):
        """获取配额（异步版本）"""
        with self._lock:
            now = time.time()
            # 清理过期的调用记录
            self.calls = [t for t in self.calls if now - t < self.period_seconds]
            
            if len(self.calls) >= self.max_calls:
                # 需要等待
                sleep_seconds = self.period_seconds - (now - self.calls[0]) + 0.1
                if sleep_seconds > 0:
                    logger.info(f"速率限制，等待 {sleep_seconds:.1f}s")
                    await asyncio.sleep(sleep_seconds)
                    # 重新清理
                    now = time.time()
                    self.calls = [t for t in self.calls if now - t < self.period_seconds]
            
            self.calls.append(time.time())


@dataclass
class OptionContract:
    """期权合约信息"""
    code: str
    option_type: str  # "CALL" or "PUT"
    strike_price: float
    expiry_date: str


@dataclass
class IVTermResult:
    """IV 期限结构结果"""
    iv7: Optional[float] = None
    iv30: Optional[float] = None
    iv60: Optional[float] = None
    iv90: Optional[float] = None
    total_oi: Optional[int] = None
    raw_data: Optional[Dict[int, float]] = None


# ==================== OI 缓存函数 ====================

def load_oi_cache() -> dict:
    """加载 OI 缓存（线程安全）"""
    with CACHE_LOCK:
        if not os.path.exists(OI_CACHE_FILE):
            return {}
        try:
            with open(OI_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}


def save_oi_cache(cache: dict) -> None:
    """保存 OI 缓存（线程安全）"""
    with CACHE_LOCK:
        try:
            with open(OI_CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save OI cache: {e}")


def compute_delta_oi(symbol: str, current_oi: int) -> Tuple[int, Optional[int]]:
    """
    计算 ΔOI（当前 OI - 昨日 OI）
    
    Returns:
        (current_oi, delta_oi) - delta_oi 可能为 None（首次运行）
    """
    if current_oi is None:
        return (None, None)
    
    cache = load_oi_cache()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 查找最近的历史数据（考虑周末/节假日）
    symbol_cache = cache.get(symbol, {})
    yesterday_oi = None
    
    for days_ago in range(1, 8):  # 最多向前查找 7 天
        past_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        if past_date in symbol_cache:
            yesterday_oi = symbol_cache[past_date]
            break
    
    # 计算 delta
    delta_oi = current_oi - yesterday_oi if yesterday_oi is not None else None
    
    # 更新缓存
    if symbol not in cache:
        cache[symbol] = {}
    cache[symbol][today] = current_oi
    
    # 清理超过 7 天的数据
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cache[symbol] = {
        date: oi for date, oi in cache[symbol].items()
        if date >= cutoff
    }
    
    save_oi_cache(cache)
    return (current_oi, delta_oi)


# ==================== IV 计算辅助函数 ====================

def _normalize_iv(iv_value: float) -> float:
    """
    标准化 IV 值为百分比形式
    Futu IV 可能是小数形式(0.35)或百分比形式(35.0)
    """
    iv = float(iv_value)
    if iv <= 1.5:  # 小数形式
        return iv * 100.0
    return iv  # 已经是百分比形式


def _variance_interpolation(
    lower: Tuple[int, float],
    upper: Tuple[int, float],
    target_day: int
) -> float:
    """
    方差插值法计算目标 DTE 的 IV
    比线性插值更准确地反映波动率期限结构
    """
    d1, iv1 = lower
    d2, iv2 = upper
    if d2 == d1:
        return iv1
    
    # 转换为方差
    var1 = (iv1 / 100.0) ** 2
    var2 = (iv2 / 100.0) ** 2
    
    # 线性插值方差
    weight = (target_day - d1) / (d2 - d1)
    var_t = var1 + (var2 - var1) * weight
    
    # 转换回 IV
    return (var_t ** 0.5) * 100.0


def _interpolate_iv(points: List[Tuple[int, float]], target_day: int) -> Optional[float]:
    """
    插值计算目标 DTE 的 IV
    
    Args:
        points: [(dte, iv), ...] 已排序的 DTE-IV 数据点
        target_day: 目标 DTE（如 30, 60, 90）
    
    Returns:
        插值后的 IV（百分比形式）
    """
    if not points:
        return None
    if len(points) == 1:
        return points[0][1]
    
    lower = None
    upper = None
    
    for dte, iv in points:
        if dte == target_day:
            return iv
        if dte < target_day:
            lower = (dte, iv)
        if dte > target_day and upper is None:
            upper = (dte, iv)
            break
    
    if lower and upper:
        return _variance_interpolation(lower, upper, target_day)
    if lower:
        return lower[1]
    if upper:
        return upper[1]
    return None


def _get_snapshot_value(snapshot: Dict, keys: List[str]) -> Optional[float]:
    """从快照中获取指定字段的值"""
    for key in keys:
        if key in snapshot and snapshot[key] is not None:
            try:
                return float(snapshot[key])
            except Exception:
                return None
    return None


def _pick_atm_iv_by_delta(
    option_contracts: List[OptionContract],
    snapshot_map: Dict[str, Dict]
) -> Optional[float]:
    """
    使用 delta ≈ 0.5 选择 ATM 期权的 IV
    这比通过 strike price 推断更准确
    """
    best_iv = None
    best_diff = None
    
    for contract in option_contracts:
        # 只使用 CALL 期权
        if contract.option_type != "CALL":
            continue
        
        snapshot = snapshot_map.get(contract.code)
        if not snapshot:
            continue
        
        # 获取 delta 和 IV
        delta = _get_snapshot_value(snapshot, ["option_delta", "delta"])
        iv = _get_snapshot_value(snapshot, ["option_implied_volatility", "implied_volatility", "iv"])
        
        if delta is None or iv is None:
            continue
        
        # 选择 delta 最接近 0.5 的期权
        diff = abs(delta - 0.5)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_iv = _normalize_iv(iv)
    
    return best_iv


# ==================== FutuService 类 ====================

class FutuService:
    """Futu OpenAPI Service for options data retrieval"""
    
    def __init__(self, host: str = None, port: int = None):
        # Load from config if not provided
        config = get_current_config()
        
        self.host = host or config.futu.host
        self.port = port or config.futu.port
        self.enabled = config.futu.enabled
        self.log_api_calls = config.logging.log_api_calls
        self.log_response_data = config.logging.log_response_data
        
        self._context: Optional[OpenQuoteContext] = None
        self._connected = False
        
        # 专用速率限制器（按 Futu API 限制）
        self._chain_limiter = RateLimiter(max_calls=10, period_seconds=30)
        self._snapshot_limiter = RateLimiter(max_calls=60, period_seconds=30)
        
        # 通用速率限制（向后兼容）
        self._request_count = 0
        self._last_reset = datetime.now()
        self._max_requests_per_minute = config.futu.max_requests_per_minute
        
        logger.debug(f"FutuService 初始化: {self.host}:{self.port}")
    
    async def connect(self) -> bool:
        """Connect to Futu OpenD"""
        if not self.enabled:
            logger.debug("Futu 服务已禁用")
            return False
        
        start_time = time.time()
        api_logger.log_request("CONNECT", f"{self.host}:{self.port}")
        
        try:
            if self._context is None:
                self._context = OpenQuoteContext(host=self.host, port=self.port)
            
            # Test connection with a simple request
            ret, data = self._context.get_global_state()
            duration_ms = (time.time() - start_time) * 1000
            
            if ret == RET_OK:
                self._connected = True
                logger.info(f"Futu 连接成功 ({duration_ms:.0f}ms)")
                api_logger.log_connection("ESTABLISHED", True, f"Connected to {self.host}:{self.port}")
                return True
            else:
                self._connected = False
                api_logger.log_connection("FAILED", False, f"Futu connection failed: {data}")
                return False
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("CONNECT", f"{self.host}:{self.port}", e, duration_ms)
            self._connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Futu OpenD"""
        if self._context:
            try:
                self._context.close()
                api_logger.log_connection("CLOSED", True, "Disconnected from Futu OpenD")
            except Exception as e:
                api_logger.log_error("DISCONNECT", "", e)
            self._context = None
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._context is not None
    
    async def _rate_limit_check(self):
        """Check and enforce rate limiting (通用，向后兼容)"""
        now = datetime.now()
        if (now - self._last_reset).total_seconds() > 60:
            self._request_count = 0
            self._last_reset = now
        
        if self._request_count >= self._max_requests_per_minute:
            wait_time = 60 - (now - self._last_reset).total_seconds()
            if wait_time > 0:
                logger.debug(f"Futu 速率限制，等待 {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._last_reset = datetime.now()
        
        self._request_count += 1
    
    async def _fetch_option_chain_with_retry(
        self, 
        code: str, 
        start_date: str, 
        end_date: str,
        max_retries: int = 2
    ) -> Tuple[int, Any]:
        """
        获取期权链（带重试和频率检测）
        
        Args:
            code: 股票代码（如 US.AAPL）
            start_date: 开始日期
            end_date: 结束日期
            max_retries: 最大重试次数
        """
        last_data = None
        
        for attempt in range(max_retries + 1):
            ret, data = self._context.get_option_chain(
                code=code,
                start=start_date,
                end=end_date,
                option_cond_type=OptionCondType.ALL
            )
            last_data = data
            
            if ret == RET_OK:
                return ret, data
            
            # 检测频率限制错误
            if isinstance(data, str) and ("频率" in data or "rate" in data.lower() or "limit" in data.lower()):
                if attempt < max_retries:
                    wait_time = 30.0  # Futu 的限制周期是 30 秒
                    logger.warning(f"触发频率限制，等待 {wait_time}s 后重试 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
            
            # 其他错误直接返回
            return ret, data
        
        return ret, last_data
    
    async def get_option_chain(self, symbol: str) -> Optional[List[Dict]]:
        """Get option chain for a symbol"""
        start_time = time.time()
        endpoint = f"option_chain/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            if not await self.connect():
                return None
        
        try:
            us_symbol = f"US.{symbol}"
            
            # 使用 chain_limiter
            await self._chain_limiter.acquire()
            
            # Get option expiry dates
            ret, data = self._context.get_option_expiration_date(code=us_symbol)
            if ret != RET_OK:
                return None
            
            expiry_dates = data['strike_time'].tolist() if 'strike_time' in data.columns else []
            
            if not expiry_dates:
                return None
            
            # Get option chain for nearest expirations
            all_options = []
            for expiry in expiry_dates[:4]:  # Get first 4 expirations
                # 使用 chain_limiter
                await self._chain_limiter.acquire()
                
                ret, data = self._context.get_option_chain(
                    code=us_symbol,
                    start=expiry,
                    end=expiry,
                    option_cond_type=OptionCondType.ALL
                )
                
                if ret == RET_OK and len(data) > 0:
                    for _, row in data.iterrows():
                        all_options.append({
                            "code": row.get("code"),
                            "name": row.get("name"),
                            "option_type": row.get("option_type"),
                            "strike_price": row.get("strike_price"),
                            "expiry_date": expiry,
                            "open_interest": row.get("open_interest", 0),
                            "volume": row.get("volume", 0)
                        })
            
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_response("GET", endpoint, "success", duration_ms,
                                   {"options_count": len(all_options)} if self.log_response_data else None,
                                   self.log_response_data)
            
            return all_options
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
    
    async def get_market_snapshot(self, symbols: List[str]) -> Optional[List[Dict]]:
        """Get market snapshot for symbols"""
        start_time = time.time()
        endpoint = f"market_snapshot"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint, {"symbols": symbols})
        
        if not self.is_connected:
            if not await self.connect():
                return None
        
        # 使用 snapshot_limiter
        await self._snapshot_limiter.acquire()
        
        try:
            # Convert to US stock format
            us_symbols = [f"US.{s}" for s in symbols]
            
            logger.debug(f"Getting market snapshot for {len(us_symbols)} symbols")
            ret, data = self._context.get_market_snapshot(us_symbols)
            
            if ret != RET_OK:
                api_logger.log_error("GET", endpoint, 
                    Exception(f"Failed to get market snapshot: {data}"))
                return None
            
            result = []
            for _, row in data.iterrows():
                result.append({
                    "code": row.get("code", "").replace("US.", ""),
                    "name": row.get("name"),
                    "price": row.get("last_price"),
                    "volume": row.get("volume"),
                    "turnover": row.get("turnover"),
                    "open": row.get("open_price"),
                    "high": row.get("high_price"),
                    "low": row.get("low_price"),
                    "prev_close": row.get("prev_close_price")
                })
            
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_response("GET", endpoint, "success", duration_ms,
                                   {"symbols_count": len(result)} if self.log_response_data else None,
                                   self.log_response_data)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            logger.error(f"Error getting market snapshot: {e}", exc_info=True)
            return None
    
    async def get_option_iv_data(self, symbol: str, underlying_price: float = None) -> Optional[Dict]:
        """
        获取 IV 期限结构数据 (IV7/IV30/IV60/IV90)
        
        借鉴 volatility_analysis 的实现:
        1. 使用日期窗口滑动获取期权链（不依赖 get_option_expiration_date）
        2. 使用 delta ≈ 0.5 选择 ATM 期权
        3. 从 get_market_snapshot 获取 IV
        4. 使用方差插值计算目标 DTE 的 IV
        
        Args:
            symbol: 股票代码
            underlying_price: 标的价格（可选，用于备选 ATM 判断）
        """
        start_time = time.time()
        endpoint = f"option_iv/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            if not await self.connect():
                return None
        
        try:
            us_symbol = f"US.{symbol}"
            today = datetime.now().date()
            max_days = 120  # 最多查看 120 天
            window_days = 30  # 每次查询 30 天的窗口
            
            # 使用日期窗口滑动获取期权链（借鉴 volatility_analysis）
            expirations: Dict[str, List[OptionContract]] = defaultdict(list)
            
            window_start = today
            end_date = today + timedelta(days=max_days)
            
            while window_start <= end_date:
                window_end = min(window_start + timedelta(days=window_days), end_date)
                
                # 使用 chain_limiter（10次/30秒）
                await self._chain_limiter.acquire()
                
                # 获取期权链（带重试）
                ret, chain_data = await self._fetch_option_chain_with_retry(
                    us_symbol,
                    window_start.strftime("%Y-%m-%d"),
                    window_end.strftime("%Y-%m-%d")
                )
                
                if ret == RET_OK and len(chain_data) > 0:
                    for _, row in chain_data.iterrows():
                        code = row.get("code")
                        opt_type = row.get("option_type", "")
                        strike = row.get("strike_price", 0)
                        
                        # 从返回数据中提取到期日（尝试多个字段名）
                        expiry = None
                        for key in ["expiry_date", "expire_date", "expiration_date", "expiry", "strike_time"]:
                            if key in row and row[key]:
                                expiry = str(row[key]).split()[0]  # 去掉可能的时间部分
                                break
                        
                        if code and opt_type and expiry:
                            opt_type_str = "CALL" if "CALL" in str(opt_type).upper() else "PUT"
                            expirations[expiry].append(OptionContract(
                                code=code,
                                option_type=opt_type_str,
                                strike_price=strike,
                                expiry_date=expiry
                            ))
                
                window_start = window_end + timedelta(days=1)
            
            if not expirations:
                logger.warning(f"{symbol}: 无可用期权数据")
                return None
            
            logger.info(f"{symbol} 获取到 {len(expirations)} 个到期日的期权数据")
            
            # 批量获取期权快照（获取 delta 和 IV）
            all_codes = []
            for contracts in expirations.values():
                all_codes.extend(c.code for c in contracts)
            
            logger.info(f"{symbol} 共 {len(all_codes)} 个期权合约，开始获取快照")
            
            snapshot_map: Dict[str, Dict] = {}
            chunk_size = 400  # Futu 每次最多查询 400 个
            
            for idx in range(0, len(all_codes), chunk_size):
                batch = all_codes[idx:idx + chunk_size]
                # 使用 snapshot_limiter（60次/30秒）
                await self._snapshot_limiter.acquire()
                
                ret, snap_data = self._context.get_market_snapshot(batch)
                if ret != RET_OK:
                    logger.debug(f"快照获取失败: {snap_data}")
                    continue
                
                for _, row in snap_data.iterrows():
                    code = row.get("code")
                    if code:
                        snapshot_map[code] = row.to_dict()
            
            if not snapshot_map:
                logger.warning(f"{symbol}: 无法获取期权快照数据")
                return None
            
            # 为每个到期日选择 ATM IV（使用 delta ≈ 0.5）
            dte_points: List[Tuple[int, float]] = []
            total_oi = 0
            
            for expiry, contracts in expirations.items():
                try:
                    # 解析日期
                    expiry_date = None
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                        try:
                            expiry_date = datetime.strptime(expiry, fmt).date()
                            break
                        except ValueError:
                            continue
                    
                    if expiry_date is None:
                        continue
                    
                    dte = (expiry_date - today).days
                    if dte <= 0:
                        continue
                    
                    # 使用 delta 选择 ATM IV
                    chosen_iv = _pick_atm_iv_by_delta(contracts, snapshot_map)
                    
                    # 备选方案：如果 delta 方法失败，使用 strike price
                    if chosen_iv is None and underlying_price:
                        for contract in contracts:
                            if contract.option_type != "CALL":
                                continue
                            snapshot = snapshot_map.get(contract.code)
                            if not snapshot:
                                continue
                            
                            if abs(contract.strike_price - underlying_price) / underlying_price < 0.05:
                                iv = _get_snapshot_value(snapshot, 
                                    ["option_implied_volatility", "implied_volatility", "iv"])
                                if iv:
                                    chosen_iv = _normalize_iv(iv)
                                    break
                    
                    if chosen_iv is not None:
                        dte_points.append((dte, chosen_iv))
                        logger.debug(f"{symbol} DTE={dte}: IV={chosen_iv:.2f}%")
                    
                    # 统计 OI
                    for contract in contracts:
                        snapshot = snapshot_map.get(contract.code)
                        if snapshot:
                            oi = _get_snapshot_value(snapshot, 
                                ["option_open_interest", "open_interest", "oi"])
                            if oi:
                                total_oi += int(oi)
                    
                except Exception as e:
                    logger.debug(f"处理 {symbol} 到期日 {expiry} 失败: {e}")
                    continue
            
            # 排序并插值计算 IV7/IV30/IV60/IV90
            dte_points.sort(key=lambda x: x[0])
            
            if len(dte_points) < 2:
                logger.warning(f"{symbol} 有效 IV 数据点不足: {len(dte_points)}")
                return None
            
            iv7 = _interpolate_iv(dte_points, 7)
            iv30 = _interpolate_iv(dte_points, 30)
            iv60 = _interpolate_iv(dte_points, 60)
            iv90 = _interpolate_iv(dte_points, 90)
            
            # 计算斜率（IV30 - IV90）
            slope = (iv30 - iv90) if iv30 and iv90 else None
            
            duration_ms = (time.time() - start_time) * 1000
            
            if self.log_api_calls:
                api_logger.log_response("GET", endpoint, "success", duration_ms,
                    {"iv30": iv30, "iv60": iv60, "iv90": iv90} if self.log_response_data else None,
                    self.log_response_data)
            
            logger.info(f"{symbol} IV: IV7={iv7:.1f}% IV30={iv30:.1f}% IV60={iv60:.1f}% IV90={iv90:.1f}%")
            
            return {
                "symbol": symbol,
                "iv7": iv7,
                "iv30": iv30,
                "iv60": iv60,
                "iv90": iv90,
                "slope": slope,
                "total_oi": total_oi if total_oi > 0 else None,
                "raw_data": {dte: iv for dte, iv in dte_points}
            }
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            logger.error(f"获取 {symbol} IV 数据失败: {e}", exc_info=True)
            return None
    
    async def calculate_positioning_score(self, symbol: str, lookback_days: int = 5) -> Optional[Dict]:
        """
        Calculate PositioningScore based on delta OI
        
        改进：支持 ΔOI 计算（当前 OI - 昨日 OI）
        """
        with LogContext(logger, "calculate_positioning_score", symbol=symbol, lookback=lookback_days):
            if not self.is_connected:
                if not await self.connect():
                    return None
            
            try:
                # Get current option chain
                options = await self.get_option_chain(symbol)
                if not options:
                    return None
                
                # Group by expiry bucket
                today = datetime.now().date()
                
                delta_oi_0_7_call = 0
                delta_oi_0_7_put = 0
                delta_oi_8_30_call = 0
                delta_oi_8_30_put = 0
                delta_oi_31_90_call = 0
                delta_oi_31_90_put = 0
                total_oi = 0
                
                for opt in options:
                    expiry = datetime.strptime(opt["expiry_date"], "%Y-%m-%d").date()
                    dte = (expiry - today).days
                    oi = opt.get("open_interest", 0) or 0
                    opt_type = opt.get("option_type", "")
                    
                    total_oi += oi
                    
                    if 0 <= dte <= 7:
                        if "CALL" in str(opt_type).upper():
                            delta_oi_0_7_call += oi
                        else:
                            delta_oi_0_7_put += oi
                    elif 8 <= dte <= 30:
                        if "CALL" in str(opt_type).upper():
                            delta_oi_8_30_call += oi
                        else:
                            delta_oi_8_30_put += oi
                    elif 31 <= dte <= 90:
                        if "CALL" in str(opt_type).upper():
                            delta_oi_31_90_call += oi
                        else:
                            delta_oi_31_90_put += oi
                
                # 计算 ΔOI
                current_oi, delta_oi_1d = compute_delta_oi(symbol, total_oi)
                
                result = {
                    "symbol": symbol,
                    "delta_oi_0_7_call": delta_oi_0_7_call,
                    "delta_oi_0_7_put": delta_oi_0_7_put,
                    "delta_oi_8_30_call": delta_oi_8_30_call,
                    "delta_oi_8_30_put": delta_oi_8_30_put,
                    "delta_oi_31_90_call": delta_oi_31_90_call,
                    "delta_oi_31_90_put": delta_oi_31_90_put,
                    "total_oi": total_oi,
                    "delta_oi_1d": delta_oi_1d,
                    "timestamp": datetime.now()
                }
                
                return result
                
            except Exception as e:
                logger.debug(f"Futu positioning {symbol} 异常: {e}")
                return None
    
    async def calculate_term_score(self, symbol: str, underlying_price: float = None) -> Optional[Dict]:
        """
        Calculate TermScore based on IV term structure
        
        Args:
            symbol: 股票代码
            underlying_price: 标的价格（从IBKR获取）
        """
        with LogContext(logger, "calculate_term_score", symbol=symbol):
            iv_data = await self.get_option_iv_data(symbol, underlying_price)
            if not iv_data:
                return None
            
            return {
                "symbol": symbol,
                "iv7": iv_data.get("iv7"),
                "iv30": iv_data.get("iv30"),
                "iv60": iv_data.get("iv60"),
                "iv90": iv_data.get("iv90"),
                "slope": iv_data.get("slope"),
                "total_oi": iv_data.get("total_oi"),
                "delta_slope": 0,  # Would need historical data
                "timestamp": datetime.now()
            }


# Singleton instance
_futu_service: Optional[FutuService] = None


def get_futu_service(host: str = None, port: int = None) -> FutuService:
    """Get or create Futu service instance"""
    global _futu_service
    
    if _futu_service is None:
        _futu_service = FutuService(host, port)
    elif host or port:
        if host:
            _futu_service.host = host
        if port:
            _futu_service.port = port
    
    return _futu_service


def reset_futu_service():
    """Reset the Futu service instance"""
    global _futu_service
    _futu_service = None
