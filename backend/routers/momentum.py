"""
Momentum Stock API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from ..database import get_db
from ..models import MomentumStock, ETFHolding, MarketChameleonData, IndustryETF
from ..schemas import (
    MomentumStockResponse, 
    PriceMomentumData, TrendStructureData, VolumePriceData,
    QualityFilterData, OptionsOverlayData,
    CalculationResult
)
from ..services import get_ibkr_service, CalculationService, DeltaCalculationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/momentum", tags=["Momentum Stocks"])


def convert_stock_to_response(stock: MomentumStock, db: Session) -> MomentumStockResponse:
    """Convert MomentumStock model to response schema"""
    delta_service = DeltaCalculationService(db)
    deltas = delta_service.calculate_stock_deltas(stock)
    
    return MomentumStockResponse(
        symbol=stock.symbol,
        name=stock.name or stock.symbol,
        price=stock.price or 0,
        sector=stock.sector or "",
        industry=stock.industry or "",
        finalScore=stock.final_score or 0,
        priceMomentum=PriceMomentumData(
            score=stock.price_momentum_score or 0,
            return20d=stock.return_20d or "+0.0%",
            return20dEx3=stock.return_20d_ex3 or "+0.0%",
            return63d=stock.return_63d or "+0.0%",
            relativeToSector=stock.relative_to_sector or 1.0,
            nearHighDist=stock.near_high_dist or "0%",
            breakoutTrigger=stock.breakout_trigger or False,
            volumeSpike=stock.volume_spike or 1.0
        ),
        trendStructure=TrendStructureData(
            score=stock.trend_structure_score or 0,
            maAlignment=stock.ma_alignment or "N/A",
            slope20d=stock.slope_20d or "+0.00",
            continuity=stock.continuity or "0%",
            above20maRatio=stock.above_20ma_ratio or 0
        ),
        volumePrice=VolumePriceData(
            score=stock.volume_price_score or 0,
            breakoutVolRatio=stock.breakout_vol_ratio or 1.0,
            upDownVolRatio=stock.up_down_vol_ratio or 1.0,
            obvTrend=stock.obv_trend or "Neutral"
        ),
        qualityFilter=QualityFilterData(
            score=stock.quality_filter_score or 0,
            maxDrawdown20d=stock.max_drawdown_20d or "0%",
            atrPercent=stock.atr_percent or 0,
            distFrom20ma=stock.dist_from_20ma or "+0.0%",
            heatLevel=stock.heat_level or "Normal"
        ),
        optionsOverlay=OptionsOverlayData(
            score=stock.options_overlay_score or 0,
            heat=stock.options_heat or "Low",
            relVol=stock.options_rel_vol or "1.0x",
            ivr=stock.options_ivr or 0,
            iv30=stock.options_iv30 or 0
        ),
        delta_3d=deltas.get("delta_3d"),
        delta_5d=deltas.get("delta_5d"),
        updated_at=stock.updated_at
    )


@router.get("/stocks", response_model=List[MomentumStockResponse])
async def get_momentum_stocks(
    industry: Optional[str] = None,
    sector: Optional[str] = None,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Get all momentum stocks with optional filtering"""
    query = db.query(MomentumStock)
    
    if industry:
        query = query.filter(MomentumStock.industry == industry.upper())
    if sector:
        query = query.filter(MomentumStock.sector == sector.upper())
    if min_score:
        query = query.filter(MomentumStock.final_score >= min_score)
    
    stocks = query.order_by(MomentumStock.final_score.desc()).all()
    return [convert_stock_to_response(stock, db) for stock in stocks]


@router.get("/stocks/{symbol}", response_model=MomentumStockResponse)
async def get_momentum_stock(symbol: str, db: Session = Depends(get_db)):
    """Get a specific momentum stock"""
    stock = db.query(MomentumStock).filter(MomentumStock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Momentum stock {symbol} not found")
    return convert_stock_to_response(stock, db)


@router.post("/stocks/{symbol}/refresh", response_model=CalculationResult)
async def refresh_momentum_stock(symbol: str, db: Session = Depends(get_db)):
    """Refresh a momentum stock's data and scores"""
    symbol = symbol.upper()
    
    stock = db.query(MomentumStock).filter(MomentumStock.symbol == symbol).first()
    
    try:
        ibkr = get_ibkr_service()
        await ibkr.connect()
        
        if not ibkr.is_connected:
            return CalculationResult(
                symbol=symbol,
                success=False,
                message="Failed to connect to IBKR",
                timestamp=datetime.now()
            )
        
        # Get stock metrics from IBKR
        metrics = await ibkr.calculate_stock_metrics(symbol)
        if not metrics:
            return CalculationResult(
                symbol=symbol,
                success=False,
                message="Failed to get stock data from IBKR",
                timestamp=datetime.now()
            )
        
        # Get MarketChameleon data if available
        mc_data = db.query(MarketChameleonData).filter(
            MarketChameleonData.symbol == symbol
        ).order_by(MarketChameleonData.data_date.desc()).first()
        
        # Determine sector and industry from holdings
        sector = None
        industry = None
        if stock:
            sector = stock.sector
            industry = stock.industry
        else:
            # Try to find from holdings
            holding = db.query(ETFHolding).filter(ETFHolding.ticker == symbol).first()
            if holding:
                if holding.sector_etf_symbol:
                    sector = holding.sector_etf_symbol
                if holding.industry_etf_symbol:
                    industry = holding.industry_etf_symbol
        
        # Calculate and update scores
        calc_service = CalculationService(db)
        updated_stock = calc_service.update_momentum_stock_scores(
            symbol=symbol,
            name=symbol,  # Would need another data source for full name
            ibkr_metrics=metrics,
            mc_data=mc_data,
            sector=sector or "",
            industry=industry or ""
        )
        
        return CalculationResult(
            symbol=symbol,
            success=True,
            message="Momentum stock refreshed successfully",
            scores={
                "final": updated_stock.final_score,
                "price_momentum": updated_stock.price_momentum_score,
                "trend_structure": updated_stock.trend_structure_score,
                "volume_price": updated_stock.volume_price_score,
                "quality_filter": updated_stock.quality_filter_score,
                "options_overlay": updated_stock.options_overlay_score
            },
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error refreshing momentum stock {symbol}: {e}")
        return CalculationResult(
            symbol=symbol,
            success=False,
            message=str(e),
            timestamp=datetime.now()
        )


@router.post("/refresh-industry/{industry_symbol}", response_model=List[CalculationResult])
async def refresh_industry_stocks(industry_symbol: str, db: Session = Depends(get_db)):
    """Refresh all stocks in an industry ETF"""
    industry_symbol = industry_symbol.upper()
    
    # Get holdings for the industry
    holdings = db.query(ETFHolding).filter(
        ETFHolding.industry_etf_symbol == industry_symbol
    ).all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"No holdings found for industry {industry_symbol}")
    
    # Get industry's sector
    industry_etf = db.query(IndustryETF).filter(IndustryETF.symbol == industry_symbol).first()
    sector = industry_etf.sector_symbol if industry_etf else None
    
    results = []
    ibkr = get_ibkr_service()
    await ibkr.connect()
    
    if not ibkr.is_connected:
        return [CalculationResult(
            symbol=industry_symbol,
            success=False,
            message="Failed to connect to IBKR",
            timestamp=datetime.now()
        )]
    
    for holding in holdings[:20]:  # Limit to top 20 holdings
        try:
            metrics = await ibkr.calculate_stock_metrics(holding.ticker)
            if not metrics:
                results.append(CalculationResult(
                    symbol=holding.ticker,
                    success=False,
                    message="Failed to get data",
                    timestamp=datetime.now()
                ))
                continue
            
            mc_data = db.query(MarketChameleonData).filter(
                MarketChameleonData.symbol == holding.ticker
            ).order_by(MarketChameleonData.data_date.desc()).first()
            
            calc_service = CalculationService(db)
            updated_stock = calc_service.update_momentum_stock_scores(
                symbol=holding.ticker,
                name=holding.ticker,
                ibkr_metrics=metrics,
                mc_data=mc_data,
                sector=sector or "",
                industry=industry_symbol
            )
            
            results.append(CalculationResult(
                symbol=holding.ticker,
                success=True,
                message="Updated",
                scores={"final": updated_stock.final_score},
                timestamp=datetime.now()
            ))
        except Exception as e:
            logger.error(f"Error refreshing {holding.ticker}: {e}")
            results.append(CalculationResult(
                symbol=holding.ticker,
                success=False,
                message=str(e),
                timestamp=datetime.now()
            ))
    
    return results


@router.delete("/stocks/{symbol}")
async def delete_momentum_stock(symbol: str, db: Session = Depends(get_db)):
    """Delete a momentum stock"""
    stock = db.query(MomentumStock).filter(MomentumStock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Momentum stock {symbol} not found")
    
    db.delete(stock)
    db.commit()
    
    return {"message": f"Momentum stock {symbol} deleted successfully"}


@router.get("/top", response_model=List[MomentumStockResponse])
async def get_top_momentum_stocks(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get top momentum stocks by final score"""
    stocks = db.query(MomentumStock).order_by(
        MomentumStock.final_score.desc()
    ).limit(limit).all()
    
    return [convert_stock_to_response(stock, db) for stock in stocks]


@router.get("/breakouts", response_model=List[MomentumStockResponse])
async def get_breakout_stocks(db: Session = Depends(get_db)):
    """Get stocks with active breakout triggers"""
    stocks = db.query(MomentumStock).filter(
        MomentumStock.breakout_trigger == True
    ).order_by(MomentumStock.final_score.desc()).all()
    
    return [convert_stock_to_response(stock, db) for stock in stocks]
