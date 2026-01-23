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
from ..models import SectorETF, IndustryETF, ETFHolding, FinvizData, MarketChameleonData, SymbolPool
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
    """Convert SectorETF model to response schema
    
    数据优先级：
    1. SymbolPool（IBKR/Futu 实时数据）- 跨 ETF 共享
    2. Finviz/MarketChameleon（手动导入数据）- 优先当前 ETF，然后跨 ETF 查询
    
    修复：确保即使数据是通过其他 ETF 更新的，也能正确显示
    """
    from sqlalchemy import func
    
    # Get holdings - 使用子查询获取每个 ticker 的最新记录
    # 避免重复记录
    subquery = db.query(
        ETFHolding.ticker,
        func.max(ETFHolding.id).label('max_id')
    ).filter(
        ETFHolding.sector_etf_symbol == etf.symbol
    ).group_by(ETFHolding.ticker).subquery()
    
    holdings = db.query(ETFHolding).join(
        subquery,
        (ETFHolding.ticker == subquery.c.ticker) & 
        (ETFHolding.id == subquery.c.max_id)
    ).order_by(ETFHolding.weight.desc()).all()
    
    # 获取 SymbolPool 实时数据（跨 ETF 共享）
    tickers = [h.ticker for h in holdings]
    pool_records = db.query(SymbolPool).filter(SymbolPool.ticker.in_(tickers)).all()
    pool_map = {r.ticker: r for r in pool_records}
    
    # 获取 Finviz 数据 - 先查当前 ETF，再查所有 ETF
    finviz_data_map = {}
    
    # 先查当前 ETF 的数据
    finviz_records = db.query(FinvizData).filter(
        FinvizData.etf_symbol == etf.symbol,
        FinvizData.ticker.in_(tickers)
    ).order_by(FinvizData.data_date.desc()).all()
    
    for record in finviz_records:
        if record.ticker not in finviz_data_map:
            finviz_data_map[record.ticker] = record
    
    # 对于没有找到的 ticker，跨 ETF 查询
    missing_tickers = [t for t in tickers if t not in finviz_data_map]
    if missing_tickers:
        cross_etf_finviz = db.query(FinvizData).filter(
            FinvizData.ticker.in_(missing_tickers)
        ).order_by(FinvizData.data_date.desc()).all()
        
        for record in cross_etf_finviz:
            if record.ticker not in finviz_data_map:
                finviz_data_map[record.ticker] = record
    
    # 获取 MarketChameleon 数据 - 同样策略
    mc_data_map = {}
    
    mc_records = db.query(MarketChameleonData).filter(
        MarketChameleonData.etf_symbol == etf.symbol,
        MarketChameleonData.symbol.in_(tickers)
    ).order_by(MarketChameleonData.data_date.desc()).all()
    
    for record in mc_records:
        if record.symbol not in mc_data_map:
            mc_data_map[record.symbol] = record
    
    # 跨 ETF 查询 MarketChameleon 数据
    missing_mc_tickers = [t for t in tickers if t not in mc_data_map]
    if missing_mc_tickers:
        cross_etf_mc = db.query(MarketChameleonData).filter(
            MarketChameleonData.symbol.in_(missing_mc_tickers)
        ).order_by(MarketChameleonData.data_date.desc()).all()
        
        for record in cross_etf_mc:
            if record.symbol not in mc_data_map:
                mc_data_map[record.symbol] = record
    
    holdings_response = []
    for h in holdings:
        pool = pool_map.get(h.ticker)
        finviz = finviz_data_map.get(h.ticker)
        mc = mc_data_map.get(h.ticker)
        
        # 优先使用 SymbolPool 数据，其次是 Finviz/MC
        sma50 = pool.sma50 if pool and pool.sma50 else (finviz.sma50 if finviz else None)
        sma200 = pool.sma200 if pool and pool.sma200 else (finviz.sma200 if finviz else None)
        price = pool.price if pool and pool.price else (finviz.price if finviz else None)
        rsi = pool.rsi if pool and pool.rsi else (finviz.rsi if finviz else None)
        
        # 期权数据优先从 SymbolPool 获取
        positioning_score = pool.positioning_score if pool and pool.positioning_score else None
        term_score = pool.term_score if pool and pool.term_score else None
        
        # 如果 SymbolPool 没有期权数据，从 MC 计算
        if positioning_score is None and mc:
            put_pct = mc.put_pct or 0
            if put_pct > 0:
                positioning_score = 50 - (put_pct - 50)
        
        if term_score is None and mc:
            if mc.iv30 and mc.hv20:
                term_score = mc.iv30 - mc.hv20
        
        holding_resp = HoldingResponse(
            id=h.id, 
            ticker=h.ticker, 
            weight=h.weight,
            sma50=sma50,
            sma200=sma200,
            price=price,
            rsi=rsi,
            positioning_score=positioning_score,
            delta_oi_8_30=None,
            delta_oi_31_90=None,
            term_score=term_score
        )
        holdings_response.append(holding_resp)
    
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
    """Convert IndustryETF model to response schema
    
    数据优先级：
    1. SymbolPool（IBKR/Futu 实时数据）- 跨 ETF 共享
    2. Finviz/MarketChameleon（手动导入数据）- 优先当前 ETF，然后跨 ETF 查询
    
    修复：确保即使数据是通过其他 ETF 更新的，也能正确显示
    """
    from sqlalchemy import func
    
    # Get holdings - 使用子查询获取每个 ticker 的最新记录
    subquery = db.query(
        ETFHolding.ticker,
        func.max(ETFHolding.id).label('max_id')
    ).filter(
        ETFHolding.industry_etf_symbol == etf.symbol
    ).group_by(ETFHolding.ticker).subquery()
    
    holdings = db.query(ETFHolding).join(
        subquery,
        (ETFHolding.ticker == subquery.c.ticker) & 
        (ETFHolding.id == subquery.c.max_id)
    ).order_by(ETFHolding.weight.desc()).all()
    
    # 获取 SymbolPool 实时数据（跨 ETF 共享）
    tickers = [h.ticker for h in holdings]
    pool_records = db.query(SymbolPool).filter(SymbolPool.ticker.in_(tickers)).all()
    pool_map = {r.ticker: r for r in pool_records}
    
    # 获取 Finviz 数据 - 先查当前 ETF，再查所有 ETF
    finviz_data_map = {}
    
    finviz_records = db.query(FinvizData).filter(
        FinvizData.etf_symbol == etf.symbol,
        FinvizData.ticker.in_(tickers)
    ).order_by(FinvizData.data_date.desc()).all()
    
    for record in finviz_records:
        if record.ticker not in finviz_data_map:
            finviz_data_map[record.ticker] = record
    
    # 跨 ETF 查询
    missing_tickers = [t for t in tickers if t not in finviz_data_map]
    if missing_tickers:
        cross_etf_finviz = db.query(FinvizData).filter(
            FinvizData.ticker.in_(missing_tickers)
        ).order_by(FinvizData.data_date.desc()).all()
        
        for record in cross_etf_finviz:
            if record.ticker not in finviz_data_map:
                finviz_data_map[record.ticker] = record
    
    # 获取 MarketChameleon 数据
    mc_data_map = {}
    
    mc_records = db.query(MarketChameleonData).filter(
        MarketChameleonData.etf_symbol == etf.symbol,
        MarketChameleonData.symbol.in_(tickers)
    ).order_by(MarketChameleonData.data_date.desc()).all()
    
    for record in mc_records:
        if record.symbol not in mc_data_map:
            mc_data_map[record.symbol] = record
    
    # 跨 ETF 查询
    missing_mc_tickers = [t for t in tickers if t not in mc_data_map]
    if missing_mc_tickers:
        cross_etf_mc = db.query(MarketChameleonData).filter(
            MarketChameleonData.symbol.in_(missing_mc_tickers)
        ).order_by(MarketChameleonData.data_date.desc()).all()
        
        for record in cross_etf_mc:
            if record.symbol not in mc_data_map:
                mc_data_map[record.symbol] = record
    
    holdings_response = []
    for h in holdings:
        pool = pool_map.get(h.ticker)
        finviz = finviz_data_map.get(h.ticker)
        mc = mc_data_map.get(h.ticker)
        
        # 优先使用 SymbolPool 数据，其次是 Finviz/MC
        sma50 = pool.sma50 if pool and pool.sma50 else (finviz.sma50 if finviz else None)
        sma200 = pool.sma200 if pool and pool.sma200 else (finviz.sma200 if finviz else None)
        price = pool.price if pool and pool.price else (finviz.price if finviz else None)
        rsi = pool.rsi if pool and pool.rsi else (finviz.rsi if finviz else None)
        
        # 期权数据优先从 SymbolPool 获取
        positioning_score = pool.positioning_score if pool and pool.positioning_score else None
        term_score = pool.term_score if pool and pool.term_score else None
        
        # 如果 SymbolPool 没有期权数据，从 MC 计算
        if positioning_score is None and mc:
            put_pct = mc.put_pct or 0
            if put_pct > 0:
                positioning_score = 50 - (put_pct - 50)
        
        if term_score is None and mc:
            if mc.iv30 and mc.hv20:
                term_score = mc.iv30 - mc.hv20
        
        holding_resp = HoldingResponse(
            id=h.id, 
            ticker=h.ticker, 
            weight=h.weight,
            sma50=sma50,
            sma200=sma200,
            price=price,
            rsi=rsi,
            positioning_score=positioning_score,
            delta_oi_8_30=None,
            delta_oi_31_90=None,
            term_score=term_score
        )
        holdings_response.append(holding_resp)
    
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
