"""
Options Data API Routes
期权数据 API 路由

Provides endpoints for:
- Option chain data
- IV term structure (IV30, IV60, IV90)
- Positioning score (OI analysis)
- Term score
- Data source configuration
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
import logging

from ..services import get_options_data_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/options", tags=["Options Data"])


@router.get("/source/info")
async def get_data_source_info():
    """
    获取当前数据源配置信息
    Get current data source configuration info
    """
    service = get_options_data_service()
    return service.get_current_source_info()


@router.post("/source/test")
async def test_data_source_connection(source: Optional[str] = None):
    """
    测试数据源连接
    Test data source connection
    
    Args:
        source: Specific source to test (ibkr/futu), or None for all
    """
    service = get_options_data_service()
    results = await service.test_connection(source)
    return {
        "results": results,
        "timestamp": datetime.now()
    }


@router.get("/chain/{symbol}")
async def get_option_chain(symbol: str):
    """
    获取期权链数据
    Get option chain data for a symbol
    
    Args:
        symbol: Stock symbol (e.g., SPY, AAPL, QQQ)
    
    Returns:
        List of option contracts with OI, IV, strike, expiry, etc.
    """
    service = get_options_data_service()
    
    try:
        result = await service.get_option_chain(symbol.upper())
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to get option chain for {symbol}. Check data source connections."
            )
        
        return {
            "symbol": symbol.upper(),
            "options": result,
            "count": len(result),
            "source_config": service.get_current_source_info()["options_data"],
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting option chain for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iv/{symbol}")
async def get_iv_data(symbol: str):
    """
    获取期权 IV 数据（期限结构）
    Get option IV term structure data
    
    Args:
        symbol: Stock symbol
    
    Returns:
        IV30, IV60, IV90, slope (contango/backwardation)
    """
    service = get_options_data_service()
    
    try:
        result = await service.get_option_iv_data(symbol.upper())
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to get IV data for {symbol}. Check data source connections."
            )
        
        return {
            "symbol": symbol.upper(),
            "iv_data": result,
            "interpretation": _interpret_iv_structure(result),
            "source_config": service.get_current_source_info()["options_data"],
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting IV data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positioning/{symbol}")
async def get_positioning_score(
    symbol: str,
    lookback_days: int = Query(default=5, ge=1, le=30)
):
    """
    获取 PositioningScore（OI 分析）
    Get Positioning Score based on Open Interest analysis
    
    Args:
        symbol: Stock symbol
        lookback_days: Number of days for OI change calculation (1-30)
    
    Returns:
        OI breakdown by expiration bucket (0-7, 8-30, 31-90 days)
    """
    service = get_options_data_service()
    
    try:
        result = await service.calculate_positioning_score(
            symbol.upper(), lookback_days
        )
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to calculate positioning score for {symbol}."
            )
        
        return {
            "symbol": symbol.upper(),
            "positioning": result,
            "interpretation": _interpret_positioning(result),
            "source_config": service.get_current_source_info()["options_data"],
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating positioning score for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/term-score/{symbol}")
async def get_term_score(symbol: str):
    """
    获取 TermScore（IV 期限结构评分）
    Get Term Score based on IV term structure
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Term structure analysis with slope and interpretation
    """
    service = get_options_data_service()
    
    try:
        result = await service.calculate_term_score(symbol.upper())
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to calculate term score for {symbol}."
            )
        
        return {
            "symbol": symbol.upper(),
            "term_score": result,
            "interpretation": _interpret_term_score(result),
            "source_config": service.get_current_source_info()["options_data"],
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating term score for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{symbol}")
async def get_full_options_analysis(symbol: str):
    """
    获取完整的期权分析（IV + Positioning）
    Get full options analysis including IV term structure and positioning
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Combined analysis with IV data, positioning score, and term score
    """
    service = get_options_data_service()
    
    try:
        # 并行获取数据
        import asyncio
        
        iv_task = service.get_option_iv_data(symbol.upper())
        pos_task = service.calculate_positioning_score(symbol.upper())
        
        iv_data, positioning = await asyncio.gather(
            iv_task, pos_task, return_exceptions=True
        )
        
        # 处理可能的异常
        if isinstance(iv_data, Exception):
            logger.warning(f"IV data fetch failed: {iv_data}")
            iv_data = None
        if isinstance(positioning, Exception):
            logger.warning(f"Positioning score fetch failed: {positioning}")
            positioning = None
        
        if iv_data is None and positioning is None:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to get options analysis for {symbol}."
            )
        
        return {
            "symbol": symbol.upper(),
            "iv_data": iv_data,
            "positioning": positioning,
            "iv_interpretation": _interpret_iv_structure(iv_data) if iv_data else None,
            "positioning_interpretation": _interpret_positioning(positioning) if positioning else None,
            "source_config": service.get_current_source_info()["options_data"],
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting full options analysis for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================================
# 解读辅助函数 - Interpretation Helper Functions
# ==========================================================================

def _interpret_iv_structure(iv_data: Optional[dict]) -> Optional[dict]:
    """Interpret IV term structure"""
    if not iv_data:
        return None
    
    slope = iv_data.get('slope', 0)
    iv30 = iv_data.get('iv30', 0)
    iv90 = iv_data.get('iv90', 0)
    
    # 期限结构判断
    if slope > 2:
        structure = "Backwardation (短期IV高于长期)"
        sentiment = "Bearish / High near-term uncertainty"
    elif slope < -2:
        structure = "Contango (长期IV高于短期)"
        sentiment = "Bullish / Normal market"
    else:
        structure = "Flat (平坦)"
        sentiment = "Neutral"
    
    # IV 水平判断
    if iv30 > 40:
        iv_level = "High (高波动)"
    elif iv30 < 15:
        iv_level = "Low (低波动)"
    else:
        iv_level = "Normal (正常波动)"
    
    return {
        "structure": structure,
        "sentiment": sentiment,
        "iv_level": iv_level,
        "slope_value": slope,
        "description": f"IV30={iv30:.1f}%, IV90={iv90:.1f}%, Slope={slope:.1f}%"
    }


def _interpret_positioning(positioning: Optional[dict]) -> Optional[dict]:
    """Interpret positioning score"""
    if not positioning:
        return None
    
    # 短期 (0-7 天) Call/Put 比
    short_call = positioning.get('delta_oi_0_7_call', 0)
    short_put = positioning.get('delta_oi_0_7_put', 0)
    short_ratio = short_call / short_put if short_put > 0 else 1
    
    # 中期 (8-30 天) Call/Put 比
    mid_call = positioning.get('delta_oi_8_30_call', 0)
    mid_put = positioning.get('delta_oi_8_30_put', 0)
    mid_ratio = mid_call / mid_put if mid_put > 0 else 1
    
    # 长期 (31-90 天) Call/Put 比
    long_call = positioning.get('delta_oi_31_90_call', 0)
    long_put = positioning.get('delta_oi_31_90_put', 0)
    long_ratio = long_call / long_put if long_put > 0 else 1
    
    # 整体情绪判断
    total_call = short_call + mid_call + long_call
    total_put = short_put + mid_put + long_put
    overall_ratio = total_call / total_put if total_put > 0 else 1
    
    if overall_ratio > 1.2:
        sentiment = "Bullish (看涨)"
    elif overall_ratio < 0.8:
        sentiment = "Bearish (看跌)"
    else:
        sentiment = "Neutral (中性)"
    
    return {
        "short_term_ratio": round(short_ratio, 2),
        "mid_term_ratio": round(mid_ratio, 2),
        "long_term_ratio": round(long_ratio, 2),
        "overall_ratio": round(overall_ratio, 2),
        "sentiment": sentiment,
        "description": f"Overall Call/Put Ratio: {overall_ratio:.2f}"
    }


def _interpret_term_score(term_score: Optional[dict]) -> Optional[dict]:
    """Interpret term score"""
    if not term_score:
        return None
    
    slope = term_score.get('slope', 0)
    
    # 评分 (-100 to +100)
    score = min(100, max(-100, slope * 10))
    
    if score > 30:
        signal = "Strong Bearish (强烈看跌信号)"
    elif score > 10:
        signal = "Mild Bearish (温和看跌信号)"
    elif score < -30:
        signal = "Strong Bullish (强烈看涨信号)"
    elif score < -10:
        signal = "Mild Bullish (温和看涨信号)"
    else:
        signal = "Neutral (中性)"
    
    return {
        "score": round(score, 1),
        "signal": signal,
        "slope": slope,
        "description": f"Term Score: {score:.1f} ({signal})"
    }
