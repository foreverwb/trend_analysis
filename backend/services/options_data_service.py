"""
Unified Options Data Service
统一期权数据服务

Handles data source switching between IBKR and Futu based on configuration.
Provides automatic fallback when primary source fails.
"""
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

from ..config_loader import get_current_config
from ..logging_utils import get_api_logger, LogContext

logger = logging.getLogger(__name__)
api_logger = get_api_logger("OPTIONS")


class DataSource(Enum):
    """Data source enumeration"""
    IBKR = "ibkr"
    FUTU = "futu"


class OptionsDataService:
    """
    统一期权数据服务
    Unified Options Data Service
    
    Features:
    - 根据配置选择主数据源 (Configurable primary data source)
    - 主数据源失败时自动降级 (Auto fallback on failure)
    - 统一的数据接口 (Unified data interface)
    """
    
    def __init__(self):
        self.config = get_current_config()
        self._ibkr_service = None
        self._futu_service = None
        
        # 获取数据源配置
        self.options_config = self.config.data_sources.options_data
        self.primary_source = self.options_config.primary.lower()
        self.fallback_source = self.options_config.fallback.lower()
        self.auto_fallback = self.options_config.auto_fallback
        
        logger.info(
            f"OptionsDataService initialized | "
            f"Primary: {self.primary_source} | "
            f"Fallback: {self.fallback_source} | "
            f"Auto-fallback: {self.auto_fallback}"
        )
    
    @property
    def ibkr_service(self):
        """Lazy load IBKR service"""
        if self._ibkr_service is None:
            from .ibkr_service import get_ibkr_service
            self._ibkr_service = get_ibkr_service()
        return self._ibkr_service
    
    @property
    def futu_service(self):
        """Lazy load Futu service"""
        if self._futu_service is None:
            from .futu_service import get_futu_service
            self._futu_service = get_futu_service()
        return self._futu_service
    
    def _get_service(self, source: str):
        """Get service instance by source name"""
        if source == "ibkr":
            return self.ibkr_service
        elif source == "futu":
            return self.futu_service
        else:
            raise ValueError(f"Unknown data source: {source}")
    
    def _is_source_enabled(self, source: str) -> bool:
        """Check if a data source is enabled in configuration"""
        if source == "ibkr":
            return self.config.ibkr.enabled
        elif source == "futu":
            return self.config.futu.enabled
        return False
    
    async def _try_with_fallback(self, method_name: str, *args, **kwargs) -> Optional[Any]:
        """
        Try to call a method on primary source, fallback to secondary if failed.
        
        Args:
            method_name: Name of the method to call on the service
            *args, **kwargs: Arguments to pass to the method
        
        Returns:
            Result from the successful call, or None if both failed
        """
        # 确定数据源顺序
        sources = [self.primary_source]
        if self.auto_fallback:
            sources.append(self.fallback_source)
        
        last_error = None
        
        for source in sources:
            if not self._is_source_enabled(source):
                logger.debug(f"Data source {source} is disabled, skipping")
                continue
            
            try:
                service = self._get_service(source)
                method = getattr(service, method_name, None)
                
                if method is None:
                    logger.warning(f"Method {method_name} not found on {source} service")
                    continue
                
                logger.debug(f"Trying {method_name} on {source} source")
                result = await method(*args, **kwargs)
                
                if result is not None:
                    logger.info(f"Successfully got data from {source} source via {method_name}")
                    return result
                else:
                    logger.warning(f"{source} source returned None for {method_name}")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to get data from {source} source: {e}")
                
                if self.auto_fallback and source == self.primary_source:
                    logger.info(f"Falling back to {self.fallback_source} source")
                    continue
                else:
                    break
        
        if last_error:
            logger.error(f"All data sources failed for {method_name}: {last_error}")
        
        return None
    
    # ==========================================================================
    # 统一数据接口 - Unified Data Interface
    # ==========================================================================
    
    async def get_option_chain(self, symbol: str) -> Optional[List[Dict]]:
        """
        获取期权链数据
        Get option chain data for a symbol
        
        Args:
            symbol: Stock symbol (e.g., 'SPY', 'AAPL')
        
        Returns:
            List of option contracts with OI, IV, etc.
        """
        with LogContext(logger, "get_option_chain", symbol=symbol, 
                       primary=self.primary_source):
            return await self._try_with_fallback("get_option_chain", symbol)
    
    async def get_option_iv_data(self, symbol: str) -> Optional[Dict]:
        """
        获取期权 IV 数据（用于期限结构计算）
        Get option IV data for term structure calculation
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dict with iv30, iv60, iv90, slope, etc.
        """
        with LogContext(logger, "get_option_iv_data", symbol=symbol,
                       primary=self.primary_source):
            return await self._try_with_fallback("get_option_iv_data", symbol)
    
    async def calculate_positioning_score(self, symbol: str, 
                                          lookback_days: int = 5) -> Optional[Dict]:
        """
        计算 PositioningScore（基于 OI 数据）
        Calculate PositioningScore based on Open Interest
        
        Args:
            symbol: Stock symbol
            lookback_days: Number of days to look back for OI change
        
        Returns:
            Dict with OI breakdown by expiration bucket
        """
        with LogContext(logger, "calculate_positioning_score", symbol=symbol,
                       primary=self.primary_source):
            return await self._try_with_fallback(
                "calculate_positioning_score", symbol, lookback_days
            )
    
    async def calculate_term_score(self, symbol: str) -> Optional[Dict]:
        """
        计算 TermScore（基于 IV 期限结构）
        Calculate TermScore based on IV term structure
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dict with IV term structure data
        """
        with LogContext(logger, "calculate_term_score", symbol=symbol,
                       primary=self.primary_source):
            return await self._try_with_fallback("calculate_term_score", symbol)
    
    async def get_market_snapshot(self, symbols: List[str]) -> Optional[List[Dict]]:
        """
        获取市场快照数据
        Get market snapshot for symbols
        
        Note: This uses market_data configuration, not options_data
        """
        market_config = self.config.data_sources.market_data
        primary = market_config.primary.lower()
        fallback = market_config.fallback.lower()
        
        sources = [primary]
        if market_config.auto_fallback:
            sources.append(fallback)
        
        for source in sources:
            if not self._is_source_enabled(source):
                continue
            
            try:
                service = self._get_service(source)
                result = await service.get_market_snapshot(symbols)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Failed to get market snapshot from {source}: {e}")
                continue
        
        return None
    
    # ==========================================================================
    # 数据源状态和配置
    # ==========================================================================
    
    def get_current_source_info(self) -> Dict:
        """
        获取当前数据源配置信息
        Get current data source configuration info
        """
        return {
            "options_data": {
                "primary": self.primary_source,
                "fallback": self.fallback_source,
                "auto_fallback": self.auto_fallback,
                "primary_enabled": self._is_source_enabled(self.primary_source),
                "fallback_enabled": self._is_source_enabled(self.fallback_source)
            },
            "market_data": {
                "primary": self.config.data_sources.market_data.primary,
                "fallback": self.config.data_sources.market_data.fallback,
                "auto_fallback": self.config.data_sources.market_data.auto_fallback
            }
        }
    
    async def test_connection(self, source: str = None) -> Dict[str, bool]:
        """
        测试数据源连接
        Test data source connections
        
        Args:
            source: Specific source to test, or None for all
        
        Returns:
            Dict mapping source name to connection status
        """
        results = {}
        
        sources_to_test = [source] if source else ["ibkr", "futu"]
        
        for src in sources_to_test:
            if not self._is_source_enabled(src):
                results[src] = False
                continue
            
            try:
                service = self._get_service(src)
                connected = await service.connect()
                results[src] = connected
            except Exception as e:
                logger.error(f"Connection test failed for {src}: {e}")
                results[src] = False
        
        return results


# ==========================================================================
# Singleton Instance
# ==========================================================================

_options_data_service: Optional[OptionsDataService] = None


def get_options_data_service() -> OptionsDataService:
    """
    获取期权数据服务单例
    Get options data service singleton instance
    """
    global _options_data_service
    
    if _options_data_service is None:
        _options_data_service = OptionsDataService()
        logger.info("OptionsDataService instance created")
    
    return _options_data_service


def reset_options_data_service():
    """
    重置期权数据服务实例
    Reset options data service instance (useful for config reload)
    """
    global _options_data_service
    if _options_data_service:
        logger.info("Resetting OptionsDataService instance")
    _options_data_service = None
