"""
Market API Routes
Handles market regime and overview data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, date
import logging

from ..database import get_db
from ..models import MarketRegime, SectorETF, IndustryETF, MomentumStock
from ..schemas import MarketRegimeResponse, SPYData, DashboardSummary
from ..services import get_ibkr_service, CalculationService, DeltaCalculationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/regime", response_model=MarketRegimeResponse)
async def get_market_regime(db: Session = Depends(get_db)):
    """Get current market regime status"""
    today = date.today()
    regime = db.query(MarketRegime).filter(MarketRegime.date == today).first()
    
    if not regime:
        # Return default regime
        return MarketRegimeResponse(
            status="B",
            spy=SPYData(price=0, vs200ma="+0.0%", vs50ma="+0.0%", trend="neutral"),
            vix=0,
            breadth=50
        )
    
    delta_service = DeltaCalculationService(db)
    deltas = delta_service.calculate_market_deltas(regime)
    
    return MarketRegimeResponse(
        status=regime.status or "B",
        spy=SPYData(
            price=regime.spy_price or 0,
            vs200ma=regime.spy_vs_200ma or "+0.0%",
            vs50ma=regime.spy_vs_50ma or "+0.0%",
            trend=regime.spy_trend or "neutral"
        ),
        vix=regime.vix or 0,
        breadth=regime.breadth or 50,
        delta_3d=deltas.get("delta_3d"),
        delta_5d=deltas.get("delta_5d"),
        updated_at=regime.updated_at
    )


@router.post("/regime/refresh", response_model=MarketRegimeResponse)
async def refresh_market_regime(db: Session = Depends(get_db)):
    """Refresh market regime data from IBKR"""
    try:
        ibkr = get_ibkr_service()
        await ibkr.connect()
        
        if not ibkr.is_connected:
            raise HTTPException(status_code=503, detail="Failed to connect to IBKR")
        
        # Get SPY data
        spy_data = await ibkr.get_spy_data()
        if not spy_data:
            raise HTTPException(status_code=503, detail="Failed to get SPY data")
        
        # Get VIX
        vix = await ibkr.get_vix()
        
        # Calculate breadth (simplified - would need to fetch all S&P 500 stocks)
        # For now, use a default value
        breadth_pct = 60  # Placeholder
        
        # Update market regime
        calc_service = CalculationService(db)
        regime = calc_service.update_market_regime(spy_data, vix or 15, breadth_pct)
        
        delta_service = DeltaCalculationService(db)
        deltas = delta_service.calculate_market_deltas(regime)
        
        return MarketRegimeResponse(
            status=regime.status,
            spy=SPYData(
                price=regime.spy_price,
                vs200ma=regime.spy_vs_200ma,
                vs50ma=regime.spy_vs_50ma,
                trend=regime.spy_trend
            ),
            vix=regime.vix,
            breadth=regime.breadth,
            delta_3d=deltas.get("delta_3d"),
            delta_5d=deltas.get("delta_5d"),
            updated_at=regime.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing market regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get complete dashboard summary"""
    today = date.today()
    
    # Market regime
    regime = db.query(MarketRegime).filter(MarketRegime.date == today).first()
    if regime:
        delta_service = DeltaCalculationService(db)
        regime_deltas = delta_service.calculate_market_deltas(regime)
        market_regime = MarketRegimeResponse(
            status=regime.status or "B",
            spy=SPYData(
                price=regime.spy_price or 0,
                vs200ma=regime.spy_vs_200ma or "+0.0%",
                vs50ma=regime.spy_vs_50ma or "+0.0%",
                trend=regime.spy_trend or "neutral"
            ),
            vix=regime.vix or 0,
            breadth=regime.breadth or 50,
            delta_3d=regime_deltas.get("delta_3d"),
            delta_5d=regime_deltas.get("delta_5d"),
            updated_at=regime.updated_at
        )
    else:
        market_regime = MarketRegimeResponse(
            status="B",
            spy=SPYData(price=0, vs200ma="+0.0%", vs50ma="+0.0%", trend="neutral"),
            vix=0,
            breadth=50
        )
    
    # Top sectors
    top_sectors = db.query(SectorETF).order_by(
        SectorETF.composite_score.desc()
    ).limit(6).all()
    
    # Top industries
    top_industries = db.query(IndustryETF).order_by(
        IndustryETF.composite_score.desc()
    ).limit(6).all()
    
    # Top momentum stocks
    top_stocks = db.query(MomentumStock).order_by(
        MomentumStock.final_score.desc()
    ).limit(5).all()
    
    # Format response
    return DashboardSummary(
        market_regime=market_regime,
        top_sectors=[
            {
                "symbol": s.symbol,
                "name": s.name,
                "score": s.composite_score or 0,
                "momentum": s.rel_momentum_value or "+0.0%",
                "heat": s.options_heat or "Low"
            }
            for s in top_sectors
        ],
        top_industries=[
            {
                "symbol": i.symbol,
                "name": i.name,
                "score": i.composite_score or 0,
                "relVol": i.rel_vol or "1.0x",
                "ivr": i.ivr or 0,
                "change": i.rel_momentum_value or "+0.0%"
            }
            for i in top_industries
        ],
        top_momentum_stocks=[
            {
                "symbol": m.symbol,
                "name": m.name,
                "price": m.price or 0,
                "finalScore": m.final_score or 0,
                "return20d": m.return_20d or "+0.0%",
                "breakout": m.breakout_trigger or False
            }
            for m in top_stocks
        ],
        options_signals={
            "trend_heat": 75,  # Would need to aggregate from MC data
            "event_risk": 10,
            "rel_notional": 1.5
        },
        rs_indicators={
            "rs_20d": 1.15,
            "rs_63d": 1.22,
            "rs_126d": 1.30
        },
        last_updated=datetime.now()
    )


@router.get("/breadth")
async def get_market_breadth(db: Session = Depends(get_db)):
    """Get detailed market breadth data"""
    # This would require fetching data for all S&P 500 stocks
    # For now, return aggregated sector breadth
    
    sectors = db.query(SectorETF).all()
    
    total_above_50ma = 0
    total_above_200ma = 0
    total_count = 0
    
    for sector in sectors:
        try:
            above_50 = float(sector.pct_above_50ma.replace('%', '')) if sector.pct_above_50ma else 0
            above_200 = float(sector.pct_above_200ma.replace('%', '')) if sector.pct_above_200ma else 0
            total_above_50ma += above_50
            total_above_200ma += above_200
            total_count += 1
        except:
            pass
    
    avg_above_50ma = total_above_50ma / total_count if total_count > 0 else 50
    avg_above_200ma = total_above_200ma / total_count if total_count > 0 else 50
    
    return {
        "aggregate": {
            "pct_above_50ma": f"{avg_above_50ma:.1f}%",
            "pct_above_200ma": f"{avg_above_200ma:.1f}%"
        },
        "by_sector": [
            {
                "symbol": s.symbol,
                "name": s.name,
                "pct_above_50ma": s.pct_above_50ma or "0%",
                "pct_above_200ma": s.pct_above_200ma or "0%"
            }
            for s in sectors
        ]
    }


@router.get("/rs-indicators")
async def get_rs_indicators(db: Session = Depends(get_db)):
    """Get relative strength indicators for selected sector"""
    # Get the top sector
    top_sector = db.query(SectorETF).order_by(
        SectorETF.composite_score.desc()
    ).first()
    
    if not top_sector:
        return {
            "symbol": "N/A",
            "rs_5d": 1.0,
            "rs_20d": 1.0,
            "rs_63d": 1.0,
            "rs_126d": 1.0
        }
    
    return {
        "symbol": top_sector.symbol,
        "rs_5d": top_sector.rs_5d or 1.0,
        "rs_20d": top_sector.rs_20d or 1.0,
        "rs_63d": top_sector.rs_63d or 1.0,
        "rs_126d": 1.0  # Would need to calculate separately
    }
