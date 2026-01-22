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
        
        logger.info(
            f"FutuService initialized | Host: {self.host}:{self.port} | "
            f"Enabled: {self.enabled} | RateLimit: {self._max_requests_per_minute}/min"
        )
    
    async def connect(self) -> bool:
        """Connect to Futu OpenD"""
        if not self.enabled:
            logger.warning("Futu service is disabled in configuration")
            return False
        
        start_time = time.time()
        api_logger.log_request("CONNECT", f"{self.host}:{self.port}")
        
        try:
            if self._context is None:
                logger.debug(f"Creating OpenQuoteContext for {self.host}:{self.port}")
                self._context = OpenQuoteContext(host=self.host, port=self.port)
            
            # Test connection with a simple request
            ret, data = self._context.get_global_state()
            duration_ms = (time.time() - start_time) * 1000
            
            if ret == RET_OK:
                self._connected = True
                api_logger.log_connection("ESTABLISHED", True, 
                    f"Connected to Futu OpenD at {self.host}:{self.port}")
                api_logger.log_response("CONNECT", f"{self.host}:{self.port}", 
                                       "success", duration_ms)
                return True
            else:
                self._connected = False
                api_logger.log_connection("FAILED", False, f"Futu connection failed: {data}")
                api_logger.log_response("CONNECT", f"{self.host}:{self.port}", 
                                       "failed", duration_ms)
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
                logger.warning(f"Rate limit reached ({self._request_count}/{self._max_requests_per_minute}), "
                              f"waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._last_reset = datetime.now()
        
        self._request_count += 1
        logger.debug(f"Rate limit check passed: {self._request_count}/{self._max_requests_per_minute}")
    
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
            # Get US stock code format
            us_symbol = f"US.{symbol}"
            logger.debug(f"Getting option expiration dates for {us_symbol}")
            
            # Get option expiry dates
            ret, data = self._context.get_option_expiration_date(code=us_symbol)
            if ret != RET_OK:
                api_logger.log_error("GET", endpoint, 
                    Exception(f"Failed to get option expiration dates: {data}"))
                return None
            
            expiry_dates = data['strike_time'].tolist() if 'strike_time' in data.columns else []
            
            if not expiry_dates:
                logger.warning(f"No expiry dates found for {symbol}")
                return None
            
            logger.debug(f"Found {len(expiry_dates)} expiry dates for {symbol}")
            
            # Get option chain for nearest expirations
            all_options = []
            for expiry in expiry_dates[:4]:  # Get first 4 expirations
                await self._rate_limit_check()
                
                logger.debug(f"Getting option chain for {symbol} expiry {expiry}")
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
            
            logger.info(f"Retrieved {len(all_options)} options for {symbol}")
            return all_options
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            api_logger.log_error("GET", endpoint, e, duration_ms)
            logger.error(f"Error getting option chain for {symbol}: {e}", exc_info=True)
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
    
    async def get_option_iv_data(self, symbol: str) -> Optional[Dict]:
        """Get implied volatility data for term structure calculation"""
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
            logger.debug(f"Getting option expiration dates for IV data: {us_symbol}")
            ret, data = self._context.get_option_expiration_date(code=us_symbol)
            if ret != RET_OK:
                api_logger.log_error("GET", endpoint, 
                    Exception(f"Failed to get option expiration dates: {data}"))
                return None
            
            expiry_dates = data['strike_time'].tolist() if 'strike_time' in data.columns else []
            
            if len(expiry_dates) < 3:
                logger.warning(f"Insufficient expiry dates for IV data: {symbol} (only {len(expiry_dates)})")
                return None
            
            # Calculate days to expiry and collect IV
            today = datetime.now().date()
            iv_by_dte = {}
            
            for expiry in expiry_dates[:6]:
                await self._rate_limit_check()
                
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                dte = (expiry_date - today).days
                
                logger.debug(f"Getting option chain for IV calculation: {symbol} DTE={dte}")
                ret, chain_data = self._context.get_option_chain(
                    code=us_symbol,
                    start=expiry,
                    end=expiry,
                    option_cond_type=OptionCondType.ALL
                )
                
                if ret == RET_OK and len(chain_data) > 0:
                    # Get ATM option IV
                    # Get underlying price first
                    snapshot = await self.get_market_snapshot([symbol])
                    if snapshot:
                        underlying_price = snapshot[0]["price"]
                        
                        # Find ATM strike
                        strikes = chain_data["strike_price"].unique()
                        atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
                        
                        atm_options = chain_data[chain_data["strike_price"] == atm_strike]
                        if len(atm_options) > 0:
                            # Get call IV
                            call_iv = atm_options[atm_options["option_type"] == "CALL"]["implied_volatility"].mean()
                            if not pd.isna(call_iv):
                                iv_by_dte[dte] = call_iv
                                logger.debug(f"IV for {symbol} DTE={dte}: {call_iv:.2f}")
            
            # Interpolate to get IV30, IV60, IV90
            if len(iv_by_dte) < 2:
                logger.warning(f"Insufficient IV data points for {symbol}")
                return None
            
            dtes = sorted(iv_by_dte.keys())
            ivs = [iv_by_dte[d] for d in dtes]
            
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
            api_logger.log_response("GET", endpoint, "success", duration_ms,
                                   {"iv30": iv30, "iv60": iv60, "iv90": iv90} if self.log_response_data else None,
                                   self.log_response_data)
            
            logger.info(f"IV data calculated for {symbol} | IV30: {iv30:.2f} | IV60: {iv60:.2f} | "
                       f"IV90: {iv90:.2f} | Slope: {slope:.2f}")
            
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
            logger.error(f"Error getting option IV data for {symbol}: {e}", exc_info=True)
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
                    logger.warning(f"No option data available for positioning score: {symbol}")
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
                
                logger.info(f"Positioning score calculated for {symbol} | "
                           f"OI_0-7: Call={delta_oi_0_7_call}, Put={delta_oi_0_7_put}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error calculating positioning score for {symbol}: {e}", exc_info=True)
                return None
    
    async def calculate_term_score(self, symbol: str) -> Optional[Dict]:
        """Calculate TermScore based on IV term structure"""
        with LogContext(logger, "calculate_term_score", symbol=symbol):
            iv_data = await self.get_option_iv_data(symbol)
            if not iv_data:
                logger.warning(f"No IV data available for term score: {symbol}")
                return None
            
            result = {
                "symbol": symbol,
                "iv30": iv_data["iv30"],
                "iv60": iv_data["iv60"],
                "iv90": iv_data["iv90"],
                "slope": iv_data["slope"],
                "delta_slope": 0,  # Would need historical data
                "timestamp": datetime.now()
            }
            
            logger.info(f"Term score calculated for {symbol} | Slope: {iv_data['slope']:.2f}")
            return result


# Singleton instance
_futu_service: Optional[FutuService] = None


def get_futu_service(host: str = None, port: int = None) -> FutuService:
    """Get or create Futu service instance"""
    global _futu_service
    
    if _futu_service is None:
        _futu_service = FutuService(host, port)
        logger.info("Created new FutuService instance")
    elif host or port:
        # Update configuration if provided
        if host:
            _futu_service.host = host
        if port:
            _futu_service.port = port
        logger.info(f"Updated FutuService configuration | Host: {_futu_service.host}:{_futu_service.port}")
    
    return _futu_service


def reset_futu_service():
    """Reset the Futu service instance"""
    global _futu_service
    if _futu_service:
        logger.info("Resetting FutuService instance")
    _futu_service = None


# Import pandas for IV calculations
try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("pandas not available, some IV calculations may fail")
