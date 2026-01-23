"""
Futu OpenAPI Service for Options Data
Provides PositioningScore and TermScore calculations
Enhanced with comprehensive logging and config file support
"""
import asyncio
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging
from futu import OpenQuoteContext, RET_OK, Market, OptionType, OptionCondType

from ..config_loader import get_current_config
from ..logging_utils import get_api_logger, LogContext

logger = logging.getLogger(__name__)
api_logger = get_api_logger("FUTU")


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
        
        # Rate limiting
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
        """Check and enforce rate limiting"""
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
    
    async def get_option_chain(self, symbol: str) -> Optional[List[Dict]]:
        """Get option chain for a symbol"""
        start_time = time.time()
        endpoint = f"option_chain/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            if not await self.connect():
                return None
        
        await self._rate_limit_check()
        
        try:
            us_symbol = f"US.{symbol}"
            
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
                await self._rate_limit_check()
                
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
        
        await self._rate_limit_check()
        
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
        Get implied volatility data for term structure calculation
        
        注意: Futu get_option_chain 只返回静态数据，不含 IV
        需要先获取期权代码，然后通过 get_market_snapshot 获取包含 IV 的动态数据
        
        Args:
            symbol: 股票代码
            underlying_price: 标的价格（从IBKR获取，避免调用Futu行情接口）
        """
        start_time = time.time()
        endpoint = f"option_iv/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            if not await self.connect():
                return None
        
        await self._rate_limit_check()
        
        try:
            us_symbol = f"US.{symbol}"
            
            # Get option expiry dates
            ret, data = self._context.get_option_expiration_date(code=us_symbol)
            if ret != RET_OK:
                logger.warning(f"无法获取 {symbol} 的期权到期日: {data}")
                return None
            
            expiry_dates = data['strike_time'].tolist() if 'strike_time' in data.columns else []
            
            if len(expiry_dates) < 3:
                logger.warning(f"{symbol} 期权到期日不足3个: {len(expiry_dates)}")
                return None
            
            # 如果没有提供价格，尝试从期权链数据推断 ATM strike
            if underlying_price is None:
                ret, first_chain = self._context.get_option_chain(
                    code=us_symbol,
                    start=expiry_dates[0],
                    end=expiry_dates[0],
                    option_cond_type=OptionCondType.ALL
                )
                if ret == RET_OK and len(first_chain) > 0:
                    strikes = sorted(first_chain["strike_price"].unique())
                    underlying_price = strikes[len(strikes) // 2]
                else:
                    logger.warning(f"无法推断 {symbol} 的标的价格")
                    return None
            
            # Calculate days to expiry and collect IV
            today = datetime.now().date()
            iv_by_dte = {}
            
            for expiry in expiry_dates[:6]:
                await self._rate_limit_check()
                
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                dte = (expiry_date - today).days
                
                if dte <= 0:
                    continue
                
                # 获取期权链（静态数据）以获得期权代码
                ret, chain_data = self._context.get_option_chain(
                    code=us_symbol,
                    start=expiry,
                    end=expiry,
                    option_cond_type=OptionCondType.ALL
                )
                
                if ret != RET_OK or len(chain_data) == 0:
                    continue
                
                # Find ATM strike
                strikes = chain_data["strike_price"].unique()
                atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
                
                # 获取 ATM 期权代码
                atm_options = chain_data[chain_data["strike_price"] == atm_strike]
                if len(atm_options) == 0:
                    continue
                
                # 获取 CALL 期权代码
                call_options = atm_options[atm_options["option_type"] == "CALL"]
                if len(call_options) == 0:
                    continue
                
                option_codes = call_options["code"].tolist()
                
                if not option_codes:
                    continue
                
                # 方法1: 尝试通过 get_market_snapshot 获取 IV
                # get_market_snapshot 返回的期权数据包含 option_implied_volatility 字段
                await self._rate_limit_check()
                
                try:
                    ret, snapshot_data = self._context.get_market_snapshot(option_codes[:1])  # 只取第一个
                    
                    if ret == RET_OK and len(snapshot_data) > 0:
                        # 尝试从 snapshot 中获取 IV
                        # 字段可能是 'option_implied_volatility' 或 'implied_volatility'
                        iv_value = None
                        
                        for col in ['option_implied_volatility', 'implied_volatility']:
                            if col in snapshot_data.columns:
                                iv_raw = snapshot_data[col].iloc[0]
                                if pd.notna(iv_raw) and iv_raw > 0:
                                    iv_value = float(iv_raw)
                                    break
                        
                        if iv_value and iv_value > 0:
                            # Futu IV 可能是百分比形式（如 35.5 表示 35.5%）
                            # 统一转换为小数形式存储
                            if iv_value > 5:  # 如果大于5，可能是百分比形式
                                iv_value = iv_value / 100.0
                            iv_by_dte[dte] = iv_value
                            logger.debug(f"{symbol} DTE={dte}: IV={iv_value:.4f}")
                            
                except Exception as snapshot_err:
                    logger.debug(f"get_market_snapshot 获取 {symbol} IV 失败: {snapshot_err}")
            
            # Interpolate to get IV30, IV60, IV90
            if len(iv_by_dte) < 2:
                logger.warning(f"{symbol} 有效 IV 数据点不足: {len(iv_by_dte)}")
                return None
            
            dtes = sorted(iv_by_dte.keys())
            ivs = [iv_by_dte[d] for d in dtes]
            
            logger.debug(f"{symbol} IV 数据: {dict(zip(dtes, ivs))}")
            
            # Simple linear interpolation
            def interpolate_iv(target_dte):
                if target_dte <= dtes[0]:
                    return ivs[0]
                if target_dte >= dtes[-1]:
                    return ivs[-1]
                
                for i in range(len(dtes) - 1):
                    if dtes[i] <= target_dte <= dtes[i+1]:
                        ratio = (target_dte - dtes[i]) / (dtes[i+1] - dtes[i])
                        return ivs[i] + ratio * (ivs[i+1] - ivs[i])
                return ivs[-1]
            
            iv30 = interpolate_iv(30)
            iv60 = interpolate_iv(60)
            iv90 = interpolate_iv(90)
            
            slope = iv30 - iv90
            
            duration_ms = (time.time() - start_time) * 1000
            if self.log_api_calls:
                api_logger.log_response("GET", endpoint, "success", duration_ms,
                                       {"iv30": iv30, "iv60": iv60, "iv90": iv90} if self.log_response_data else None,
                                       self.log_response_data)
            
            return {
                "symbol": symbol,
                "iv30": iv30,
                "iv60": iv60,
                "iv90": iv90,
                "slope": slope,
                "raw_data": iv_by_dte
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
    
    async def calculate_positioning_score(self, symbol: str, lookback_days: int = 5) -> Optional[Dict]:
        """Calculate PositioningScore based on delta OI"""
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
                
                for opt in options:
                    expiry = datetime.strptime(opt["expiry_date"], "%Y-%m-%d").date()
                    dte = (expiry - today).days
                    oi = opt.get("open_interest", 0)
                    opt_type = opt.get("option_type", "")
                    
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
                
                result = {
                    "symbol": symbol,
                    "delta_oi_0_7_call": delta_oi_0_7_call,
                    "delta_oi_0_7_put": delta_oi_0_7_put,
                    "delta_oi_8_30_call": delta_oi_8_30_call,
                    "delta_oi_8_30_put": delta_oi_8_30_put,
                    "delta_oi_31_90_call": delta_oi_31_90_call,
                    "delta_oi_31_90_put": delta_oi_31_90_put,
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
                "iv30": iv_data["iv30"],
                "iv60": iv_data["iv60"],
                "iv90": iv_data["iv90"],
                "slope": iv_data["slope"],
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


# Import pandas for IV calculations
try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("pandas not available, some IV calculations may fail")
