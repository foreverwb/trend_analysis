"""
ETF API Routes
Handles Sector ETF and Industry ETF endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
import logging

from ..database import get_db
from ..models import SectorETF, IndustryETF, ETFHolding, FinvizData, MarketChameleonData
from ..schemas import (
    SectorETFResponse, IndustryETFResponse, 
    HoldingResponse, HoldingsUpload,
    RelMomentumData, TrendQualityData, BreadthData, OptionsConfirmData,
    RefreshRequest, CalculationResult
)
from ..services import get_ibkr_service, CalculationService, DeltaCalculationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/etf", tags=["ETF"])

# Sector ETF names mapping
SECTOR_ETF_NAMES = {
    "XLK": "科技板块",
    "XLC": "通信服务",
    "XLY": "非必需消费",
    "XLP": "必需消费",
    "XLV": "医疗保健",
    "XLF": "金融板块",
    "XLI": "工业板块",
    "XLE": "能源板块",
    "XLU": "公用事业",
    "XLRE": "房地产",
    "XLB": "原材料"
}


def convert_sector_etf_to_response(etf: SectorETF, db: Session) -> SectorETFResponse:
    """Convert SectorETF model to response schema"""
    # Get holdings
    holdings = db.query(ETFHolding).filter(
        ETFHolding.sector_etf_symbol == etf.symbol
    ).order_by(ETFHolding.weight.desc()).all()
    
    holdings_response = [
        HoldingResponse(id=h.id, ticker=h.ticker, weight=h.weight)
        for h in holdings
    ]
    
    # Calculate deltas
    delta_service = DeltaCalculationService(db)
    deltas = delta_service.calculate_etf_deltas(etf)
    
    return SectorETFResponse(
        symbol=etf.symbol,
        name=etf.name or SECTOR_ETF_NAMES.get(etf.symbol, etf.symbol),
        compositeScore=etf.composite_score or 0,
        relMomentum=RelMomentumData(
            score=etf.rel_momentum_score or 0,
            value=etf.rel_momentum_value or "+0.0%",
            rank=etf.rel_momentum_rank or 0
        ),
        trendQuality=TrendQualityData(
            score=etf.trend_quality_score or 0,
            structure=etf.trend_structure or "Neutral",
            slope=etf.trend_slope or "+0.00"
        ),
        breadth=BreadthData(
            score=etf.breadth_score or 0,
            above50ma=etf.pct_above_50ma or "0%",
            above200ma=etf.pct_above_200ma or "0%"
        ),
        optionsConfirm=OptionsConfirmData(
            score=etf.options_score or 0,
            heat=etf.options_heat or "Low",
            relVol=etf.rel_vol or "1.0x",
            ivr=etf.ivr or 0
        ),
        holdings=holdings_response,
        delta_3d=deltas.get("delta_3d"),
        delta_5d=deltas.get("delta_5d"),
        updated_at=etf.updated_at
    )


def convert_industry_etf_to_response(etf: IndustryETF, db: Session) -> IndustryETFResponse:
    """Convert IndustryETF model to response schema"""
    holdings = db.query(ETFHolding).filter(
        ETFHolding.industry_etf_symbol == etf.symbol
    ).order_by(ETFHolding.weight.desc()).all()
    
    holdings_response = [
        HoldingResponse(id=h.id, ticker=h.ticker, weight=h.weight)
        for h in holdings
    ]
    
    delta_service = DeltaCalculationService(db)
    deltas = delta_service.calculate_etf_deltas(etf)
    
    sector_name = SECTOR_ETF_NAMES.get(etf.sector_symbol, etf.sector_symbol)
    
    return IndustryETFResponse(
        symbol=etf.symbol,
        name=etf.name or etf.symbol,
        sector=etf.sector_symbol or "",
        sectorName=sector_name,
        compositeScore=etf.composite_score or 0,
        relMomentum=RelMomentumData(
            score=etf.rel_momentum_score or 0,
            value=etf.rel_momentum_value or "+0.0%",
            rank=etf.rel_momentum_rank or 0
        ),
        trendQuality=TrendQualityData(
            score=etf.trend_quality_score or 0,
            structure=etf.trend_structure or "Neutral",
            slope=etf.trend_slope or "+0.00"
        ),
        breadth=BreadthData(
            score=etf.breadth_score or 0,
            above50ma=etf.pct_above_50ma or "0%",
            above200ma=etf.pct_above_200ma or "0%"
        ),
        optionsConfirm=OptionsConfirmData(
            score=etf.options_score or 0,
            heat=etf.options_heat or "Low",
            relVol=etf.rel_vol or "1.0x",
            ivr=etf.ivr or 0
        ),
        holdings=holdings_response,
        delta_3d=deltas.get("delta_3d"),
        delta_5d=deltas.get("delta_5d"),
        updated_at=etf.updated_at
    )


# ==================== Sector ETF Endpoints ====================
@router.get("/sectors", response_model=List[SectorETFResponse])
async def get_sector_etfs(db: Session = Depends(get_db)):
    """Get all sector ETFs with scores"""
    etfs = db.query(SectorETF).order_by(SectorETF.composite_score.desc()).all()
    
    # If no ETFs exist, create default ones
    if not etfs:
        for symbol, name in SECTOR_ETF_NAMES.items():
            etf = SectorETF(symbol=symbol, name=name)
            db.add(etf)
        db.commit()
        etfs = db.query(SectorETF).all()
    
    return [convert_sector_etf_to_response(etf, db) for etf in etfs]


@router.get("/sectors/{symbol}", response_model=SectorETFResponse)
async def get_sector_etf(symbol: str, db: Session = Depends(get_db)):
    """Get a specific sector ETF"""
    etf = db.query(SectorETF).filter(SectorETF.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"Sector ETF {symbol} not found")
    return convert_sector_etf_to_response(etf, db)


@router.post("/sectors/{symbol}/refresh", response_model=CalculationResult)
async def refresh_sector_etf(
    symbol: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Refresh sector ETF data from IBKR and recalculate scores"""
    symbol = symbol.upper()
    
    etf = db.query(SectorETF).filter(SectorETF.symbol == symbol).first()
    if not etf:
        etf = SectorETF(symbol=symbol, name=SECTOR_ETF_NAMES.get(symbol, symbol))
        db.add(etf)
        db.commit()
    
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
        
        # Get IBKR metrics
        metrics = await ibkr.calculate_etf_metrics(symbol)
        if not metrics:
            return CalculationResult(
                symbol=symbol,
                success=False,
                message="Failed to get market data from IBKR",
                timestamp=datetime.now()
            )
        
        # Get Finviz and MarketChameleon data from DB
        finviz_data = db.query(FinvizData).filter(
            FinvizData.etf_symbol == symbol
        ).order_by(FinvizData.data_date.desc()).all()
        
        mc_data = db.query(MarketChameleonData).filter(
            MarketChameleonData.etf_symbol == symbol
        ).order_by(MarketChameleonData.data_date.desc()).all()
        
        # Calculate and update scores
        calc_service = CalculationService(db)
        updated_etf = calc_service.update_sector_etf_scores(symbol, metrics, finviz_data, mc_data)
        
        # Rank all ETFs
        all_etfs = db.query(SectorETF).all()
        calc_service.rank_etfs(all_etfs)
        
        return CalculationResult(
            symbol=symbol,
            success=True,
            message="Sector ETF refreshed successfully",
            scores={
                "composite": updated_etf.composite_score,
                "rel_momentum": updated_etf.rel_momentum_score,
                "trend_quality": updated_etf.trend_quality_score,
                "breadth": updated_etf.breadth_score,
                "options": updated_etf.options_score
            },
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error refreshing sector ETF {symbol}: {e}")
        return CalculationResult(
            symbol=symbol,
            success=False,
            message=str(e),
            timestamp=datetime.now()
        )


@router.delete("/sectors/{symbol}")
async def delete_sector_etf(symbol: str, db: Session = Depends(get_db)):
    """Delete a sector ETF and its holdings"""
    etf = db.query(SectorETF).filter(SectorETF.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"Sector ETF {symbol} not found")
    
    # Delete holdings
    db.query(ETFHolding).filter(ETFHolding.sector_etf_symbol == symbol.upper()).delete()
    db.delete(etf)
    db.commit()
    
    return {"message": f"Sector ETF {symbol} deleted successfully"}


# ==================== Industry ETF Endpoints ====================
@router.get("/industries", response_model=List[IndustryETFResponse])
async def get_industry_etfs(
    sector: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all industry ETFs, optionally filtered by sector"""
    query = db.query(IndustryETF)
    if sector:
        query = query.filter(IndustryETF.sector_symbol == sector.upper())
    
    etfs = query.order_by(IndustryETF.composite_score.desc()).all()
    return [convert_industry_etf_to_response(etf, db) for etf in etfs]


@router.get("/industries/{symbol}", response_model=IndustryETFResponse)
async def get_industry_etf(symbol: str, db: Session = Depends(get_db)):
    """Get a specific industry ETF"""
    etf = db.query(IndustryETF).filter(IndustryETF.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"Industry ETF {symbol} not found")
    return convert_industry_etf_to_response(etf, db)


@router.post("/industries/{symbol}/refresh", response_model=CalculationResult)
async def refresh_industry_etf(symbol: str, db: Session = Depends(get_db)):
    """Refresh industry ETF data from IBKR and recalculate scores"""
    symbol = symbol.upper()
    
    etf = db.query(IndustryETF).filter(IndustryETF.symbol == symbol).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"Industry ETF {symbol} not found")
    
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
        
        metrics = await ibkr.calculate_etf_metrics(symbol)
        if not metrics:
            return CalculationResult(
                symbol=symbol,
                success=False,
                message="Failed to get market data",
                timestamp=datetime.now()
            )
        
        finviz_data = db.query(FinvizData).filter(
            FinvizData.etf_symbol == symbol
        ).all()
        
        mc_data = db.query(MarketChameleonData).filter(
            MarketChameleonData.etf_symbol == symbol
        ).all()
        
        calc_service = CalculationService(db)
        
        # Use same update logic as sector ETF
        etf.rel_momentum_score, etf.rel_momentum_value = calc_service.calculate_rel_momentum_score(metrics)
        etf.trend_quality_score, etf.trend_structure, etf.trend_slope = calc_service.calculate_trend_quality_score(metrics)
        etf.breadth_score, etf.pct_above_50ma, etf.pct_above_200ma = calc_service.calculate_breadth_score(finviz_data)
        etf.options_score, etf.options_heat, etf.rel_vol, etf.ivr = calc_service.calculate_options_confirm_score(mc_data)
        
        etf.composite_score = calc_service.calculate_etf_composite_score(
            etf.rel_momentum_score, etf.trend_quality_score, etf.breadth_score, etf.options_score
        )
        
        db.commit()
        
        return CalculationResult(
            symbol=symbol,
            success=True,
            message="Industry ETF refreshed successfully",
            scores={
                "composite": etf.composite_score,
                "rel_momentum": etf.rel_momentum_score,
                "trend_quality": etf.trend_quality_score,
                "breadth": etf.breadth_score,
                "options": etf.options_score
            },
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error refreshing industry ETF {symbol}: {e}")
        return CalculationResult(
            symbol=symbol,
            success=False,
            message=str(e),
            timestamp=datetime.now()
        )


@router.delete("/industries/{symbol}")
async def delete_industry_etf(symbol: str, db: Session = Depends(get_db)):
    """Delete an industry ETF and its holdings"""
    etf = db.query(IndustryETF).filter(IndustryETF.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"Industry ETF {symbol} not found")
    
    db.query(ETFHolding).filter(ETFHolding.industry_etf_symbol == symbol.upper()).delete()
    db.delete(etf)
    db.commit()
    
    return {"message": f"Industry ETF {symbol} deleted successfully"}


# ==================== Holdings Endpoints ====================
@router.post("/holdings")
async def upload_holdings(data: HoldingsUpload, db: Session = Depends(get_db)):
    """Upload ETF holdings"""
    symbol = data.etf_symbol.upper()
    
    if data.etf_type == "sector":
        # Ensure sector ETF exists
        etf = db.query(SectorETF).filter(SectorETF.symbol == symbol).first()
        if not etf:
            etf = SectorETF(symbol=symbol, name=SECTOR_ETF_NAMES.get(symbol, symbol))
            db.add(etf)
            db.commit()
        
        # Delete existing holdings for this date
        db.query(ETFHolding).filter(
            ETFHolding.sector_etf_symbol == symbol,
            ETFHolding.data_date == data.data_date
        ).delete()
        
        # Add new holdings
        for holding in data.holdings:
            h = ETFHolding(
                etf_type="sector",
                etf_symbol=symbol,
                sector_etf_symbol=symbol,
                ticker=holding.ticker.upper(),
                weight=holding.weight,
                data_date=data.data_date
            )
            db.add(h)
    else:
        # Industry ETF
        etf = db.query(IndustryETF).filter(IndustryETF.symbol == symbol).first()
        if not etf:
            etf = IndustryETF(
                symbol=symbol, 
                name=symbol,
                sector_symbol=data.sector_symbol.upper() if data.sector_symbol else None
            )
            db.add(etf)
            db.commit()
        
        db.query(ETFHolding).filter(
            ETFHolding.industry_etf_symbol == symbol,
            ETFHolding.data_date == data.data_date
        ).delete()
        
        for holding in data.holdings:
            h = ETFHolding(
                etf_type="industry",
                etf_symbol=symbol,
                industry_etf_symbol=symbol,
                ticker=holding.ticker.upper(),
                weight=holding.weight,
                data_date=data.data_date
            )
            db.add(h)
    
    db.commit()
    
    return {
        "message": f"Uploaded {len(data.holdings)} holdings for {symbol}",
        "etf_symbol": symbol,
        "etf_type": data.etf_type,
        "count": len(data.holdings)
    }


@router.get("/holdings/{symbol}", response_model=List[HoldingResponse])
async def get_holdings(symbol: str, db: Session = Depends(get_db)):
    """Get holdings for an ETF"""
    holdings = db.query(ETFHolding).filter(
        ETFHolding.etf_symbol == symbol.upper()
    ).order_by(ETFHolding.weight.desc()).all()
    
    return [HoldingResponse(id=h.id, ticker=h.ticker, weight=h.weight) for h in holdings]
