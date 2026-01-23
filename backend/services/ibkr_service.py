"""
IBKR API Service using ib_insync
Connects to IB Gateway for market data
增强日志版本 + 期权数据支持

修复: 使用 nest_asyncio 解决 "This event loop is already running" 错误
"""
import asyncio
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from ib_insync import IB, Stock, Index, Option, util
import logging
import numpy as np

# 修复事件循环冲突问题
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

from ..config_loader import get_current_config
from ..logging_utils import get_api_logger, LogContext

logger = logging.getLogger(__name__)
api_logger = get_api_logger("IBKR")


class IBKRService:
    """IBKR API Service for market data retrieval"""
    
    def __init__(self, host: str = None, port: int = None, client_id: int = None):
        # Load from config if not provided
        config = get_current_config()
        self.host = host or config.ibkr.host
        self.port = port or config.ibkr.port
        self.client_id = client_id or config.ibkr.client_id
        self.connection_timeout = config.ibkr.connection_timeout
        self.enabled = config.ibkr.enabled
        self.log_api_calls = config.logging.log_api_calls
        self.log_response_data = config.logging.log_response_data
        
        # 从配置加载超时设置
        self.request_timeout = config.ibkr.request_timeout
        self.qualify_timeout = config.ibkr.qualify_timeout
        self.historical_timeout = config.ibkr.historical_timeout
        self.market_data_type = config.ibkr.market_data_type
        
        self.ib: Optional[IB] = None
        self._connected = False
        
        logger.debug(f"IBKRService 初始化: {self.host}:{self.port} (数据类型: {self.market_data_type})")
    
    async def connect(self) -> bool:
        """Connect to IB Gateway"""
        if not self.enabled:
            logger.debug("IBKR 服务已禁用")
            return False
        
        start_time = time.time()
        
        if self.log_api_calls:
            api_logger.log_request("CONNECT", f"{self.host}:{self.port}", {
                "client_id": self.client_id,
                "timeout": self.connection_timeout
            })
        
        try:
            if self.ib is None:
                self.ib = IB()
            
            if not self.ib.isConnected():
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: self.ib.connect(self.host, self.port, clientId=self.client_id)
                    ),
                    timeout=self.connection_timeout
                )
            
            self._connected = self.ib.isConnected()
            duration_ms = (time.time() - start_time) * 1000
            
            if self._connected:
                self.ib.reqMarketDataType(self.market_data_type)
                logger.info(f"IBKR 连接成功 ({duration_ms:.0f}ms)")
                api_logger.log_connection("ESTABLISHED", True, f"Connected to {self.host}:{self.port}")
            else:
                logger.error("IBKR 连接失败")
                api_logger.log_connection("FAILED", False, "Connection returned but not connected")
            
            return self._connected
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"IBKR 连接超时 ({self.connection_timeout}s)")
            api_logger.log_error("CONNECT", f"{self.host}:{self.port}", 
                TimeoutError(f"Connection timeout after {self.connection_timeout}s"), duration_ms)
            self._connected = False
            return False
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"IBKR 连接异常: {e}")
            api_logger.log_error("CONNECT", f"{self.host}:{self.port}", e, duration_ms)
            self._connected = False
            return False
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self.ib and self.ib.isConnected()
    
    async def get_market_data(self, symbol: str, sec_type: str = "STK") -> Optional[Dict]:
        """Get market data for a symbol using historical data
        
        盘后分析模式：使用 reqHistoricalData 获取最近收盘价
        """
        start_time = time.time()
        endpoint = f"market_data/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint, {"sec_type": sec_type})
        
        if not self.is_connected:
            await self.connect()
        
        if not self.is_connected:
            logger.debug(f"{symbol} - 连接失败")
            return None
        
        try:
            with LogContext(logger, "get_market_data", symbol=symbol, sec_type=sec_type):
                # 创建合约
                if sec_type == "IND":
                    contract = Index(symbol, "CBOE" if symbol == "VIX" else "NYSE")
                else:
                    contract = Stock(symbol, "SMART", "USD")
                
                # 验证合约（带超时）
                loop = asyncio.get_event_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, self.ib.qualifyContracts, contract),
                        timeout=self.qualify_timeout
                    )
                except asyncio.TimeoutError:
                    logger.debug(f"{symbol} - 合约验证超时")
                    return None
                
                # 使用 reqHistoricalData 获取历史数据（盘后分析模式）
                bars = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.ib.reqHistoricalData(
                            contract,
                            endDateTime='',
                            durationStr='5 D',
                            barSizeSetting='1 day',
                            whatToShow='TRADES',
                            useRTH=True,
                            formatDate=1
                        )
                    ),
                    timeout=self.historical_timeout
                )
                
                if not bars or len(bars) == 0:
                    logger.warning(f"{symbol} - 无历史数据")
                    return None
                
                # 使用最后一根K线
                last_bar = bars[-1]
                
                data = {
                    "symbol": symbol,
                    "price": last_bar.close,
                    "price_source": "historical",
                    "open": last_bar.open,
                    "high": last_bar.high,
                    "low": last_bar.low,
                    "close": last_bar.close,
                    "volume": last_bar.volume,
                    "bar_date": str(last_bar.date),
                    "timestamp": datetime.now()
                }
                
                duration_ms = (time.time() - start_time) * 1000
                
                if self.log_api_calls:
                    api_logger.log_response("GET", endpoint, "success", duration_ms, 
                        data={"price": data["price"], "date": data["bar_date"]}, 
                        log_data=self.log_response_data)
                
                return data
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
    
    async def get_historical_data(
        self, 
        symbol: str, 
        duration: str = "3 M",
        bar_size: str = "1 day",
        sec_type: str = "STK"
    ) -> Optional[List[Dict]]:
        """Get historical bars for a symbol"""
        start_time = time.time()
        endpoint = f"historical_data/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint, {
                "duration": duration, 
                "bar_size": bar_size, 
                "sec_type": sec_type
            })
        
        if not self.is_connected:
            await self.connect()
        
        if not self.is_connected:
            logger.debug(f"{symbol} - 历史数据连接失败")
            return None
        
        try:
            with LogContext(logger, "get_historical_data", symbol=symbol, duration=duration):
                # 创建合约
                if sec_type == "IND":
                    contract = Index(symbol, "CBOE" if symbol == "VIX" else "NYSE")
                else:
                    contract = Stock(symbol, "SMART", "USD")
                
                # 验证合约（带超时）
                loop = asyncio.get_event_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, self.ib.qualifyContracts, contract),
                        timeout=self.qualify_timeout
                    )
                except asyncio.TimeoutError:
                    logger.debug(f"{symbol} - 历史数据合约验证超时")
                    return None
                
                # 请求历史数据（带超时）
                def fetch_historical():
                    return self.ib.reqHistoricalData(
                        contract,
                        endDateTime="",
                        durationStr=duration,
                        barSizeSetting=bar_size,
                        whatToShow="TRADES" if sec_type == "STK" else "TRADES",
                        useRTH=True,
                        formatDate=1
                    )
                
                try:
                    bars = await asyncio.wait_for(
                        loop.run_in_executor(None, fetch_historical),
                        timeout=self.historical_timeout
                    )
                except asyncio.TimeoutError:
                    logger.debug(f"{symbol} - 历史数据请求超时")
                    return None
                
                if not bars:
                    return None
                
                result = []
                for bar in bars:
                    result.append({
                        "date": bar.date,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                        "average": bar.average,
                        "barCount": bar.barCount
                    })
                
                duration_ms = (time.time() - start_time) * 1000
                if self.log_api_calls:
                    api_logger.log_response("GET", endpoint, "success", duration_ms,
                        data={"bars_count": len(result)}, log_data=self.log_response_data)
                
                return result
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
            return None
    
    async def get_spy_data(self) -> Optional[Dict]:
        """Get SPY market data with moving averages
        
        修复: 当实时/延迟数据不可用时，使用历史数据的最后收盘价
        """
        logger.debug("Getting SPY data with moving averages")
        
        historical = await self.get_historical_data("SPY", "1 Y", "1 day")
        
        if not historical:
            logger.warning("Failed to get SPY historical data")
            return None
        
        closes = [bar["close"] for bar in historical]
        
        # 尝试获取市场数据（延迟数据）
        current = await self.get_market_data("SPY")
        
        # 如果市场数据不可用或价格为 None，使用历史数据的最后收盘价
        if current and current.get("price") is not None:
            price = current["price"]
            logger.debug(f"Using market data price: {price}")
        else:
            logger.warning("Market data unavailable, using last historical close")
            price = closes[-1] if closes else 0
        
        # Calculate moving averages
        ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]
        ma200 = np.mean(closes[-200:]) if len(closes) >= 200 else closes[-1]
        
        # Calculate slopes
        if len(closes) >= 25:
            ma20_5d_ago = np.mean(closes[-25:-5])
            ma20_slope = (ma20 - ma20_5d_ago) / ma20_5d_ago * 100
        else:
            ma20_slope = 0
        
        vs_200ma = ((price - ma200) / ma200) * 100
        vs_50ma = ((price - ma50) / ma50) * 100
        
        result = {
            "price": price,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "ma20_slope": ma20_slope,
            "vs_200ma": vs_200ma,
            "vs_50ma": vs_50ma,
            "historical": historical
        }
        
        logger.debug(f"SPY data calculated: price={price}, vs_200ma={vs_200ma:.2f}%")
        return result
    
    async def get_vix(self) -> Optional[float]:
        """Get current VIX value
        
        使用延迟数据，如果不可用则使用历史数据
        """
        logger.debug("Getting VIX value")
        data = await self.get_market_data("VIX", "IND")
        
        if data and data.get("price") is not None:
            logger.debug(f"VIX value from market data: {data['price']}")
            return data["price"]
        
        # 市场数据不可用，尝试获取历史数据
        logger.warning("VIX market data unavailable, trying historical data")
        try:
            historical = await self.get_historical_data("VIX", "5 D", "1 day", "IND")
            if historical and len(historical) > 0:
                vix_close = historical[-1]["close"]
                logger.debug(f"VIX from historical: {vix_close}")
                return vix_close
        except Exception as e:
            logger.warning(f"Failed to get VIX historical data: {e}")
        
        # 都失败则返回默认值
        logger.warning("VIX data unavailable, using default value 15.0")
        return 15.0
    
    async def calculate_etf_metrics(self, symbol: str) -> Optional[Dict]:
        """Calculate ETF metrics for scoring"""
        start_time = time.time()
        
        with LogContext(logger, "calculate_etf_metrics", symbol=symbol):
            historical = await self.get_historical_data(symbol, "6 M", "1 day")
            spy_historical = await self.get_historical_data("SPY", "6 M", "1 day")
            
            if not historical or not spy_historical:
                logger.warning(f"Missing data for ETF metrics calculation: {symbol}")
                return None
            
            closes = [bar["close"] for bar in historical]
            volumes = [bar["volume"] for bar in historical]
            spy_closes = [bar["close"] for bar in spy_historical]
            
            # Align data
            min_len = min(len(closes), len(spy_closes))
            closes = closes[-min_len:]
            spy_closes = spy_closes[-min_len:]
            volumes = volumes[-min_len:]
            
            # Calculate relative strength
            if len(closes) >= 63 and len(spy_closes) >= 63:
                rs_5d = (closes[-1] / closes[-5]) / (spy_closes[-1] / spy_closes[-5]) if closes[-5] > 0 and spy_closes[-5] > 0 else 1
                rs_20d = (closes[-1] / closes[-20]) / (spy_closes[-1] / spy_closes[-20]) if closes[-20] > 0 and spy_closes[-20] > 0 else 1
                rs_63d = (closes[-1] / closes[-63]) / (spy_closes[-1] / spy_closes[-63]) if closes[-63] > 0 and spy_closes[-63] > 0 else 1
            else:
                rs_5d = rs_20d = rs_63d = 1
            
            # Relative momentum calculation
            rel_mom = 0.45 * (rs_20d - 1) * 100 + 0.35 * (rs_63d - 1) * 100 + 0.20 * (rs_5d - 1) * 100
            
            # Moving averages
            ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
            ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]
            ma200 = np.mean(closes[-200:]) if len(closes) >= 200 else closes[-1]
            
            current_price = closes[-1]
            
            # Trend structure
            price_above_50ma = current_price > ma50
            ma20_above_50ma = ma20 > ma50
            
            # MA20 slope
            if len(closes) >= 25:
                ma20_5d_ago = np.mean(closes[-25:-5])
                ma20_slope = (ma20 - ma20_5d_ago) / ma20_5d_ago
            else:
                ma20_slope = 0
            
            # Max drawdown (20 days)
            if len(closes) >= 20:
                peak = max(closes[-20:])
                trough = min(closes[-20:])
                max_dd = (trough - peak) / peak * 100
            else:
                max_dd = 0
            
            # Volume ratio
            if len(volumes) >= 50:
                avg_vol_50d = np.mean(volumes[-50:])
                current_vol = volumes[-1]
                vol_ratio = current_vol / avg_vol_50d if avg_vol_50d > 0 else 1
            else:
                vol_ratio = 1
            
            # Calculate returns
            return_5d = (closes[-1] / closes[-5] - 1) * 100 if len(closes) >= 5 else 0
            return_20d = (closes[-1] / closes[-20] - 1) * 100 if len(closes) >= 20 else 0
            return_63d = (closes[-1] / closes[-63] - 1) * 100 if len(closes) >= 63 else 0
            
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"ETF metrics calculated for {symbol} in {duration_ms:.2f}ms: rel_mom={rel_mom:.2f}")
            
            return {
                "symbol": symbol,
                "price": current_price,
                "ma20": ma20,
                "ma50": ma50,
                "ma200": ma200,
                "rs_5d": rs_5d,
                "rs_20d": rs_20d,
                "rs_63d": rs_63d,
                "rel_momentum": rel_mom,
                "price_above_50ma": price_above_50ma,
                "ma20_above_50ma": ma20_above_50ma,
                "ma20_slope": ma20_slope,
                "max_drawdown_20d": max_dd,
                "volume_ratio": vol_ratio,
                "return_5d": return_5d,
                "return_20d": return_20d,
                "return_63d": return_63d,
                "historical": historical
            }
    
    async def calculate_stock_metrics(self, symbol: str, sector_symbol: str = None) -> Optional[Dict]:
        """Calculate individual stock metrics for momentum scoring"""
        start_time = time.time()
        
        with LogContext(logger, "calculate_stock_metrics", symbol=symbol):
            historical = await self.get_historical_data(symbol, "6 M", "1 day")
            
            if not historical:
                logger.warning(f"No historical data for stock metrics: {symbol}")
                return None
            
            closes = [bar["close"] for bar in historical]
            highs = [bar["high"] for bar in historical]
            lows = [bar["low"] for bar in historical]
            volumes = [bar["volume"] for bar in historical]
            
            if len(closes) < 63:
                logger.warning(f"Insufficient data for stock metrics: {symbol} ({len(closes)} bars)")
                return None
            
            current_price = closes[-1]
            
            # Price momentum
            return_20d = (closes[-1] / closes[-20] - 1) * 100 if closes[-20] > 0 else 0
            return_20d_ex3 = (closes[-3] / closes[-20] - 1) * 100 if closes[-20] > 0 else 0
            return_63d = (closes[-1] / closes[-63] - 1) * 100 if closes[-63] > 0 else 0
            
            # Distance from 20-day high
            high_20d = max(closes[-20:])
            near_high_dist = (current_price / high_20d) * 100
            
            # Moving averages
            ma20 = np.mean(closes[-20:])
            ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else ma20
            
            # MA alignment
            if current_price > ma20 > ma50:
                ma_alignment = "P>20MA>50MA"
            elif current_price > ma20:
                ma_alignment = "P>20MA"
            else:
                ma_alignment = "Weak"
            
            # MA20 slope
            ma20_5d_ago = np.mean(closes[-25:-5]) if len(closes) >= 25 else ma20
            slope_20d = (ma20 - ma20_5d_ago) / ma20_5d_ago if ma20_5d_ago > 0 else 0
            
            # Continuity (days above 20MA)
            days_above_20ma = 0
            for i in range(-20, 0):
                period_ma = np.mean(closes[i-20:i]) if abs(i) <= len(closes) - 20 else ma20
                if closes[i] > period_ma:
                    days_above_20ma += 1
            continuity = days_above_20ma / 20
            
            # Volume analysis
            avg_vol_50d = np.mean(volumes[-50:]) if len(volumes) >= 50 else volumes[-1]
            volume_spike = volumes[-1] / avg_vol_50d if avg_vol_50d > 0 else 1
            
            # Up/Down volume ratio
            up_volume = sum(v for i, v in enumerate(volumes[-20:]) if closes[-20+i] > closes[-21+i])
            down_volume = sum(v for i, v in enumerate(volumes[-20:]) if closes[-20+i] < closes[-21+i])
            up_down_vol_ratio = up_volume / down_volume if down_volume > 0 else 1
            
            # ATR calculation
            true_ranges = []
            for i in range(-14, 0):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                true_ranges.append(tr)
            atr = np.mean(true_ranges)
            atr_percent = (atr / current_price) * 100
            
            # Max drawdown
            peak = max(closes[-20:])
            trough = min(closes[-20:])
            max_dd = (trough - peak) / peak * 100
            
            # Distance from 20MA
            dist_from_20ma = (current_price - ma20) / ma20 * 100
            
            # Breakout detection
            prev_high_20d = max(closes[-21:-1])
            breakout_trigger = current_price > prev_high_20d and volume_spike > 1.5
            
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Stock metrics calculated for {symbol} in {duration_ms:.2f}ms")
            
            return {
                "symbol": symbol,
                "price": current_price,
                "return_20d": return_20d,
                "return_20d_ex3": return_20d_ex3,
                "return_63d": return_63d,
                "near_high_dist": near_high_dist,
                "ma_alignment": ma_alignment,
                "slope_20d": slope_20d,
                "continuity": continuity,
                "volume_spike": volume_spike,
                "up_down_vol_ratio": up_down_vol_ratio,
                "atr_percent": atr_percent,
                "max_drawdown_20d": max_dd,
                "dist_from_20ma": dist_from_20ma,
                "breakout_trigger": breakout_trigger,
                "ma20": ma20,
                "ma50": ma50
            }

    # ==========================================================================
    # 期权数据方法 - Options Data Methods
    # ==========================================================================
    
    async def get_option_chain_params(self, symbol: str) -> Optional[List[Dict]]:
        """
        获取期权链参数（到期日、行权价）
        Get option chain parameters (expirations, strikes)
        """
        start_time = time.time()
        endpoint = f"option_chain_params/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            await self.connect()
        
        if not self.is_connected:
            return None
        
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            logger.debug(f"Requesting option chain params for {symbol}")
            
            # 获取期权参数
            chains = self.ib.reqSecDefOptParams(
                underlyingSymbol=symbol,
                futFopExchange='',
                underlyingSecType='STK',
                underlyingConId=stock.conId
            )
            
            if not chains:
                logger.warning(f"No option chain params found for {symbol}")
                return None
            
            result = []
            for chain in chains:
                result.append({
                    'exchange': chain.exchange,
                    'underlyingConId': chain.underlyingConId,
                    'tradingClass': chain.tradingClass,
                    'multiplier': chain.multiplier,
                    'expirations': sorted(chain.expirations),
                    'strikes': sorted(chain.strikes)
                })
            
            duration_ms = (time.time() - start_time) * 1000
            if self.log_api_calls:
                api_logger.log_response("GET", endpoint, "success", duration_ms,
                    data={"chains_count": len(result)}, log_data=self.log_response_data)
            
            logger.info(f"Option chain params retrieved for {symbol}: {len(result)} chains")
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
    
    async def get_option_data(self, symbol: str, expiry: str, strike: float, 
                              right: str = 'C') -> Optional[Dict]:
        """
        获取单个期权合约的数据（OI, IV）
        Get single option contract data (Open Interest, Implied Volatility)
        
        Args:
            symbol: 标的代码
            expiry: 到期日 (YYYYMMDD 格式)
            strike: 行权价
            right: 'C' for Call, 'P' for Put
        """
        start_time = time.time()
        endpoint = f"option_data/{symbol}/{expiry}/{strike}/{right}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        if not self.is_connected:
            await self.connect()
        
        if not self.is_connected:
            return None
        
        try:
            option = Option(symbol, expiry, strike, right, 'SMART')
            
            qualified = self.ib.qualifyContracts(option)
            if not qualified:
                logger.warning(f"Could not qualify option contract: {symbol} {expiry} {strike} {right}")
                return None
            
            logger.debug(f"Requesting option market data: {symbol} {expiry} {strike} {right}")
            
            # 订阅市场数据，包含 IV (106) 和 Historical Vol (101)
            ticker = self.ib.reqMktData(option, genericTickList='106,101', 
                                        snapshot=True, regulatorySnapshot=False)
            
            # 等待数据返回
            await asyncio.sleep(2)
            
            data = {
                'symbol': symbol,
                'expiry': expiry,
                'strike': strike,
                'right': right,
                'open_interest': ticker.openInterest if ticker.openInterest else 0,
                'implied_volatility': ticker.impliedVol if ticker.impliedVol else None,
                'last_price': ticker.last if ticker.last else None,
                'bid': ticker.bid if ticker.bid else None,
                'ask': ticker.ask if ticker.ask else None,
                'volume': ticker.volume if ticker.volume else 0,
                'delta': ticker.modelGreeks.delta if ticker.modelGreeks else None,
                'gamma': ticker.modelGreeks.gamma if ticker.modelGreeks else None,
                'theta': ticker.modelGreeks.theta if ticker.modelGreeks else None,
                'vega': ticker.modelGreeks.vega if ticker.modelGreeks else None,
                'timestamp': datetime.now()
            }
            
            self.ib.cancelMktData(option)
            
            duration_ms = (time.time() - start_time) * 1000
            if self.log_api_calls:
                api_logger.log_response("GET", endpoint, "success", duration_ms,
                    data={"oi": data['open_interest'], "iv": data['implied_volatility']}, 
                    log_data=self.log_response_data)
            
            return data
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            return None
    
    async def get_option_chain(self, symbol: str, max_expirations: int = 4) -> Optional[List[Dict]]:
        """
        获取期权链数据
        Get option chain data for a symbol
        
        Note: IBKR 需要逐个合约获取，效率较低
        """
        start_time = time.time()
        endpoint = f"option_chain/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        # 获取期权链参数
        chains = await self.get_option_chain_params(symbol)
        if not chains:
            return None
        
        # 获取标的价格
        stock_data = await self.get_market_data(symbol)
        if not stock_data or not stock_data.get('price'):
            logger.warning(f"Could not get underlying price for {symbol}")
            return None
        
        underlying_price = stock_data['price']
        
        # 选择 SMART 交易所的链
        chain = None
        for c in chains:
            if c['exchange'] == 'SMART':
                chain = c
                break
        if not chain:
            chain = chains[0]
        
        expirations = chain['expirations'][:max_expirations]
        strikes = chain['strikes']
        
        # 找到 ATM 附近的行权价 (±10%)
        atm_strikes = [s for s in strikes 
                       if underlying_price * 0.9 <= s <= underlying_price * 1.1]
        
        if not atm_strikes:
            # 如果没有找到，选择最接近的5个行权价
            atm_strikes = sorted(strikes, key=lambda x: abs(x - underlying_price))[:5]
        
        logger.info(f"Getting option chain for {symbol}: {len(expirations)} expirations, "
                   f"{len(atm_strikes)} strikes around ATM {underlying_price:.2f}")
        
        all_options = []
        
        for expiry in expirations:
            for strike in atm_strikes:
                # 获取 Call
                call_data = await self.get_option_data(symbol, expiry, strike, 'C')
                if call_data:
                    call_data['option_type'] = 'CALL'
                    call_data['expiry_date'] = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
                    all_options.append(call_data)
                
                # 获取 Put
                put_data = await self.get_option_data(symbol, expiry, strike, 'P')
                if put_data:
                    put_data['option_type'] = 'PUT'
                    put_data['expiry_date'] = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
                    all_options.append(put_data)
                
                # 避免请求过快
                await asyncio.sleep(0.1)
        
        duration_ms = (time.time() - start_time) * 1000
        if self.log_api_calls:
            api_logger.log_response("GET", endpoint, "success", duration_ms,
                data={"options_count": len(all_options)}, log_data=self.log_response_data)
        
        logger.info(f"Option chain retrieved for {symbol}: {len(all_options)} contracts")
        return all_options
    
    async def get_option_iv_data(self, symbol: str) -> Optional[Dict]:
        """
        获取期权 IV 数据用于期限结构计算
        Get option IV data for term structure calculation
        
        Returns IV30, IV60, IV90 通过插值计算
        """
        start_time = time.time()
        endpoint = f"option_iv/{symbol}"
        
        if self.log_api_calls:
            api_logger.log_request("GET", endpoint)
        
        with LogContext(logger, "get_option_iv_data", symbol=symbol):
            # 获取标的价格
            stock_data = await self.get_market_data(symbol)
            if not stock_data or not stock_data.get('price'):
                logger.warning(f"Could not get underlying price for {symbol}")
                return None
            
            underlying_price = stock_data['price']
            
            # 获取期权链参数
            chains = await self.get_option_chain_params(symbol)
            if not chains:
                return None
            
            # 选择链
            chain = None
            for c in chains:
                if c['exchange'] == 'SMART':
                    chain = c
                    break
            if not chain:
                chain = chains[0]
            
            expirations = chain['expirations'][:6]  # 最近6个到期日
            strikes = chain['strikes']
            
            # 找到最接近 ATM 的行权价
            atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
            
            logger.debug(f"Calculating IV term structure for {symbol}: "
                        f"ATM strike={atm_strike}, price={underlying_price:.2f}")
            
            today = datetime.now().date()
            iv_by_dte = {}
            
            for expiry in expirations:
                try:
                    expiry_date = datetime.strptime(expiry, '%Y%m%d').date()
                    dte = (expiry_date - today).days
                    
                    if dte <= 0:
                        continue
                    
                    # 获取 ATM Call 的 IV
                    option_data = await self.get_option_data(symbol, expiry, atm_strike, 'C')
                    
                    if option_data and option_data.get('implied_volatility'):
                        iv_by_dte[dte] = option_data['implied_volatility']
                        logger.debug(f"IV for {symbol} DTE={dte}: {option_data['implied_volatility']:.4f}")
                    
                    await asyncio.sleep(0.2)  # 速率限制
                    
                except Exception as e:
                    logger.warning(f"Error getting IV for {symbol} expiry {expiry}: {e}")
                    continue
            
            if len(iv_by_dte) < 2:
                logger.warning(f"Insufficient IV data points for {symbol}: {len(iv_by_dte)}")
                return None
            
            # 插值计算 IV30, IV60, IV90
            dtes = sorted(iv_by_dte.keys())
            ivs = [iv_by_dte[d] for d in dtes]
            
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
            
            result = {
                'symbol': symbol,
                'iv30': iv30 * 100,  # 转为百分比
                'iv60': iv60 * 100,
                'iv90': iv90 * 100,
                'slope': slope * 100,
                'raw_data': {k: v * 100 for k, v in iv_by_dte.items()},
                'underlying_price': underlying_price,
                'atm_strike': atm_strike,
                'timestamp': datetime.now()
            }
            
            duration_ms = (time.time() - start_time) * 1000
            if self.log_api_calls:
                api_logger.log_response("GET", endpoint, "success", duration_ms,
                    data={"iv30": result['iv30'], "iv60": result['iv60'], "iv90": result['iv90']},
                    log_data=self.log_response_data)
            
            logger.info(f"IV data calculated for {symbol} | IV30: {result['iv30']:.2f}% | "
                       f"IV60: {result['iv60']:.2f}% | IV90: {result['iv90']:.2f}% | "
                       f"Slope: {result['slope']:.2f}%")
            
            return result
    
    async def calculate_positioning_score(self, symbol: str, lookback_days: int = 5) -> Optional[Dict]:
        """
        计算 PositioningScore（基于 OI 数据）
        Calculate PositioningScore based on Open Interest data
        """
        with LogContext(logger, "calculate_positioning_score", symbol=symbol, lookback=lookback_days):
            # 获取期权链数据
            options = await self.get_option_chain(symbol)
            
            if not options:
                return None
            
            today = datetime.now().date()
            
            # 按到期日分组统计 OI
            delta_oi_0_7_call = 0
            delta_oi_0_7_put = 0
            delta_oi_8_30_call = 0
            delta_oi_8_30_put = 0
            delta_oi_31_90_call = 0
            delta_oi_31_90_put = 0
            
            for opt in options:
                try:
                    expiry_str = opt.get('expiry_date', opt.get('expiry', ''))
                    if not expiry_str:
                        continue
                    
                    # 处理不同的日期格式
                    if '-' in expiry_str:
                        expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                    else:
                        expiry = datetime.strptime(expiry_str, '%Y%m%d').date()
                    
                    dte = (expiry - today).days
                    oi = opt.get('open_interest', 0) or 0
                    opt_type = opt.get('option_type', opt.get('right', ''))
                    
                    if 0 <= dte <= 7:
                        if 'CALL' in str(opt_type).upper() or opt_type == 'C':
                            delta_oi_0_7_call += oi
                        else:
                            delta_oi_0_7_put += oi
                    elif 8 <= dte <= 30:
                        if 'CALL' in str(opt_type).upper() or opt_type == 'C':
                            delta_oi_8_30_call += oi
                        else:
                            delta_oi_8_30_put += oi
                    elif 31 <= dte <= 90:
                        if 'CALL' in str(opt_type).upper() or opt_type == 'C':
                            delta_oi_31_90_call += oi
                        else:
                            delta_oi_31_90_put += oi
                            
                except Exception:
                    continue
            
            return {
                'symbol': symbol,
                'delta_oi_0_7_call': delta_oi_0_7_call,
                'delta_oi_0_7_put': delta_oi_0_7_put,
                'delta_oi_8_30_call': delta_oi_8_30_call,
                'delta_oi_8_30_put': delta_oi_8_30_put,
                'delta_oi_31_90_call': delta_oi_31_90_call,
                'delta_oi_31_90_put': delta_oi_31_90_put,
                'timestamp': datetime.now()
            }
    
    async def calculate_term_score(self, symbol: str) -> Optional[Dict]:
        """
        计算 TermScore（基于 IV 期限结构）
        Calculate TermScore based on IV term structure
        """
        with LogContext(logger, "calculate_term_score", symbol=symbol):
            iv_data = await self.get_option_iv_data(symbol)
            
            if not iv_data:
                return None
            
            return {
                'symbol': symbol,
                'iv30': iv_data['iv30'],
                'iv60': iv_data['iv60'],
                'iv90': iv_data['iv90'],
                'slope': iv_data['slope'],
                'delta_slope': 0,  # 需要历史数据
                'timestamp': datetime.now()
            }


# Singleton instance
_ibkr_service: Optional[IBKRService] = None


def get_ibkr_service(host: str = None, port: int = None, client_id: int = None) -> IBKRService:
    """Get or create IBKR service instance"""
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService(host, port, client_id)
    return _ibkr_service
