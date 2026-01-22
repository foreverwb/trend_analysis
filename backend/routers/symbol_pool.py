"""
Symbol Pool API Routes
标的池管理 - 实现标的去重、统一更新和数据完备性检查
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Set
from datetime import datetime, date
import logging
import uuid
import asyncio

from ..database import get_db
from ..models import (
    SymbolPool, SymbolETFMapping, ETFRefreshConfig, UpdateSession,
    SectorETF, IndustryETF, ETFHolding, FinvizData, MarketChameleonData
)
from ..schemas import (
    SymbolPoolItem, SymbolPoolResponse, ETFConfigItem, ETFConfigUpdate,
    ETFConfigListResponse, DataSourceStatus, DataSourcesStatusResponse,
    UpdateProgressResponse, UnifiedUpdateRequest, ComputeRequest, ComputeResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-config", tags=["Data Configuration"])

# ETF名称映射
SECTOR_ETF_NAMES = {
    "XLK": "科技板块", "XLC": "通信服务", "XLY": "非必需消费",
    "XLP": "必需消费", "XLV": "医疗保健", "XLF": "金融板块",
    "XLI": "工业板块", "XLE": "能源板块", "XLU": "公用事业",
    "XLRE": "房地产", "XLB": "原材料"
}

INDUSTRY_ETF_NAMES = {
    "SOXX": "半导体", "SMH": "半导体设备", "IGV": "软件",
    "XOP": "油气开采", "XRT": "零售", "KBE": "银行",
    "IBB": "生物科技", "XHB": "房屋建筑", "XME": "金属矿业", "JETS": "航空"
}


def calculate_symbol_completeness(symbol: SymbolPool) -> int:
    """计算单个标的的数据完备度"""
    count = 0
    total = 4  # 4个数据源
    
    if symbol.finviz_status == 'ready':
        count += 1
    if symbol.mc_status == 'ready':
        count += 1
    if symbol.ibkr_status == 'ready':
        count += 1
    if symbol.futu_status == 'ready':
        count += 1
    
    return int((count / total) * 100)


def get_unique_symbols_from_configs(db: Session, configs: List[ETFRefreshConfig]) -> Dict[str, Dict]:
    """根据ETF配置获取去重后的标的列表"""
    symbol_map = {}  # ticker -> {max_priority, etfs, weight}
    
    for config in configs:
        # 获取该ETF的持仓
        holdings = db.query(ETFHolding).filter(
            ETFHolding.etf_symbol == config.etf_symbol
        ).order_by(ETFHolding.weight.desc()).limit(config.top_n).all()
        
        for idx, holding in enumerate(holdings):
            ticker = holding.ticker.upper()
            if ticker in symbol_map:
                symbol_map[ticker]['etfs'].append(config.etf_symbol)
                symbol_map[ticker]['max_weight'] = max(
                    symbol_map[ticker]['max_weight'], 
                    holding.weight
                )
            else:
                symbol_map[ticker] = {
                    'etfs': [config.etf_symbol],
                    'max_weight': holding.weight,
                    'rank': idx + 1
                }
    
    return symbol_map


# ==================== 数据源状态 ====================
@router.get("/sources/status", response_model=DataSourcesStatusResponse)
async def get_data_sources_status(db: Session = Depends(get_db)):
    """获取所有数据源状态"""
    # 统计各数据源的覆盖情况
    total_symbols = db.query(SymbolPool).count()
    
    if total_symbols == 0:
        # 无数据时返回默认状态
        return DataSourcesStatusResponse(
            sources=[
                DataSourceStatus(id="finviz", name="Finviz", status="pending", coverage=0),
                DataSourceStatus(id="marketchameleon", name="MarketChameleon", status="pending", coverage=0),
                DataSourceStatus(id="ibkr", name="IBKR", status="pending", coverage=0),
                DataSourceStatus(id="futu", name="Futu", status="pending", coverage=0),
            ],
            overall_completeness=0
        )
    
    # 统计各数据源就绪数量
    finviz_ready = db.query(SymbolPool).filter(SymbolPool.finviz_status == 'ready').count()
    mc_ready = db.query(SymbolPool).filter(SymbolPool.mc_status == 'ready').count()
    ibkr_ready = db.query(SymbolPool).filter(SymbolPool.ibkr_status == 'ready').count()
    futu_ready = db.query(SymbolPool).filter(SymbolPool.futu_status == 'ready').count()
    
    # 获取最新更新时间
    latest_finviz = db.query(func.max(SymbolPool.finviz_last_update)).scalar()
    latest_mc = db.query(func.max(SymbolPool.mc_last_update)).scalar()
    latest_ibkr = db.query(func.max(SymbolPool.ibkr_last_update)).scalar()
    latest_futu = db.query(func.max(SymbolPool.futu_last_update)).scalar()
    
    def get_status(coverage: int) -> str:
        if coverage >= 90:
            return "ready"
        elif coverage >= 50:
            return "warning"
        return "error"
    
    def format_time(dt: datetime) -> Optional[str]:
        if dt:
            return dt.strftime("%H:%M:%S")
        return None
    
    finviz_cov = int((finviz_ready / total_symbols) * 100)
    mc_cov = int((mc_ready / total_symbols) * 100)
    ibkr_cov = int((ibkr_ready / total_symbols) * 100)
    futu_cov = int((futu_ready / total_symbols) * 100)
    
    sources = [
        DataSourceStatus(
            id="finviz", name="Finviz", 
            status=get_status(finviz_cov), 
            coverage=finviz_cov,
            last_update=format_time(latest_finviz)
        ),
        DataSourceStatus(
            id="marketchameleon", name="MarketChameleon", 
            status=get_status(mc_cov), 
            coverage=mc_cov,
            last_update=format_time(latest_mc)
        ),
        DataSourceStatus(
            id="ibkr", name="IBKR", 
            status=get_status(ibkr_cov), 
            coverage=ibkr_cov,
            last_update=format_time(latest_ibkr)
        ),
        DataSourceStatus(
            id="futu", name="Futu", 
            status=get_status(futu_cov), 
            coverage=futu_cov,
            last_update=format_time(latest_futu)
        ),
    ]
    
    # 计算整体完备度
    overall = int((finviz_cov + mc_cov + ibkr_cov + futu_cov) / 4)
    
    return DataSourcesStatusResponse(sources=sources, overall_completeness=overall)


# ==================== 标的池管理 ====================
@router.get("/symbol-pool", response_model=SymbolPoolResponse)
async def get_symbol_pool(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取标的池列表"""
    total = db.query(SymbolPool).count()
    symbols = db.query(SymbolPool).offset(offset).limit(limit).all()
    
    # 获取每个标的所属的ETF
    result = []
    for sym in symbols:
        mappings = db.query(SymbolETFMapping).filter(
            SymbolETFMapping.ticker == sym.ticker
        ).all()
        
        etfs = [m.etf_symbol for m in mappings]
        max_weight = max([m.weight for m in mappings]) if mappings else 0
        
        result.append(SymbolPoolItem(
            ticker=sym.ticker,
            name=sym.name,
            price=sym.price,
            etfs=etfs,
            max_weight=max_weight,
            finviz=sym.finviz_status == 'ready',
            mc=sym.mc_status == 'ready',
            ibkr=sym.ibkr_status == 'ready',
            futu=sym.futu_status == 'ready',
            completeness=sym.completeness or 0
        ))
    
    # 按最大权重排序
    result.sort(key=lambda x: x.max_weight, reverse=True)
    
    latest_update = db.query(func.max(SymbolPool.updated_at)).scalar()
    
    return SymbolPoolResponse(
        total_count=total,
        symbols=result,
        last_update=latest_update
    )


@router.post("/symbol-pool/sync")
async def sync_symbol_pool(db: Session = Depends(get_db)):
    """同步标的池 - 从ETF持仓数据构建去重后的标的池"""
    # 获取所有ETF配置
    configs = db.query(ETFRefreshConfig).all()
    
    if not configs:
        # 如果没有配置，先初始化默认配置
        await initialize_etf_configs(db)
        configs = db.query(ETFRefreshConfig).all()
    
    # 获取去重后的标的
    symbol_map = get_unique_symbols_from_configs(db, configs)
    
    # 清空旧的映射关系
    db.query(SymbolETFMapping).delete()
    
    # 更新标的池和映射关系
    for ticker, info in symbol_map.items():
        # 检查标的是否存在
        symbol = db.query(SymbolPool).filter(SymbolPool.ticker == ticker).first()
        if not symbol:
            symbol = SymbolPool(ticker=ticker)
            db.add(symbol)
            db.flush()
        
        # 添加映射关系
        for etf_symbol in info['etfs']:
            config = db.query(ETFRefreshConfig).filter(
                ETFRefreshConfig.etf_symbol == etf_symbol
            ).first()
            
            mapping = SymbolETFMapping(
                ticker=ticker,
                etf_symbol=etf_symbol,
                etf_type=config.etf_type if config else 'sector',
                weight=info['max_weight'],
                rank=info['rank']
            )
            db.add(mapping)
    
    db.commit()
    
    return {
        "message": f"标的池同步完成，共 {len(symbol_map)} 个唯一标的",
        "unique_symbols": len(symbol_map)
    }


# ==================== ETF配置管理 ====================
@router.get("/available-etfs")
async def get_available_etfs(db: Session = Depends(get_db)):
    """获取所有可用的ETF列表（包括没有holdings的）
    用于数据导入选择器
    """
    sector_etfs = []
    industry_etfs = []
    
    # 获取所有板块ETF
    for symbol, name in SECTOR_ETF_NAMES.items():
        # 检查是否有holdings
        holdings_count = db.query(ETFHolding).filter(
            ETFHolding.sector_etf_symbol == symbol
        ).count()
        
        sector_etfs.append({
            "symbol": symbol,
            "name": name,
            "has_holdings": holdings_count > 0,
            "holdings_count": holdings_count
        })
    
    # 获取所有行业ETF
    for symbol, name in INDUSTRY_ETF_NAMES.items():
        holdings_count = db.query(ETFHolding).filter(
            ETFHolding.industry_etf_symbol == symbol
        ).count()
        
        industry_etfs.append({
            "symbol": symbol,
            "name": name,
            "has_holdings": holdings_count > 0,
            "holdings_count": holdings_count
        })
    
    return {
        "sector_etfs": sector_etfs,
        "industry_etfs": industry_etfs
    }


@router.get("/etf-configs", response_model=ETFConfigListResponse)
async def get_etf_configs(db: Session = Depends(get_db)):
    """获取所有ETF更新配置
    
    修复: 只返回有 holdings 数据的 ETF，没有 holdings 的 ETF 不展示
    """
    configs = db.query(ETFRefreshConfig).all()
    
    if not configs:
        # 初始化默认配置
        await initialize_etf_configs(db)
        configs = db.query(ETFRefreshConfig).all()
    
    sector_etfs = []
    industry_etfs = []
    
    for config in configs:
        # 检查该 ETF 是否有 holdings 数据
        if config.etf_type == 'sector':
            holdings_count = db.query(ETFHolding).filter(
                ETFHolding.sector_etf_symbol == config.etf_symbol
            ).count()
        else:
            holdings_count = db.query(ETFHolding).filter(
                ETFHolding.industry_etf_symbol == config.etf_symbol
            ).count()
        
        # 只有有 holdings 数据的 ETF 才加入列表
        if holdings_count == 0:
            continue
        
        # 更新 total_holdings 字段
        if config.total_holdings != holdings_count:
            config.total_holdings = holdings_count
            db.add(config)
        
        item = ETFConfigItem(
            symbol=config.etf_symbol,
            name=config.etf_name or config.etf_symbol,
            type=config.etf_type,
            total_holdings=holdings_count,
            top_n=config.top_n,
            frequency=config.frequency,
            status=config.status,
            last_refresh=config.last_refresh
        )
        
        if config.etf_type == 'sector':
            sector_etfs.append(item)
        else:
            industry_etfs.append(item)
    
    db.commit()
    
    # 计算去重后的标的数量
    unique_count = db.query(func.count(func.distinct(SymbolETFMapping.ticker))).scalar() or 0
    
    # 预估更新时间（每个标的约2秒）
    estimated_time = unique_count * 2
    
    return ETFConfigListResponse(
        sector_etfs=sector_etfs,
        industry_etfs=industry_etfs,
        unique_symbol_count=unique_count,
        estimated_time=estimated_time
    )


@router.put("/etf-configs/{symbol}")
async def update_etf_config(
    symbol: str,
    update: ETFConfigUpdate,
    db: Session = Depends(get_db)
):
    """更新单个ETF的配置"""
    config = db.query(ETFRefreshConfig).filter(
        ETFRefreshConfig.etf_symbol == symbol.upper()
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"ETF config for {symbol} not found")
    
    if update.top_n is not None:
        config.top_n = update.top_n
    if update.frequency is not None:
        config.frequency = update.frequency
    if update.auto_refresh is not None:
        config.auto_refresh = update.auto_refresh
    
    config.updated_at = datetime.utcnow()
    db.commit()
    
    # 重新同步标的池
    await sync_symbol_pool(db)
    
    return {"message": f"ETF {symbol} config updated", "symbol": symbol}


async def initialize_etf_configs(db: Session):
    """初始化ETF配置"""
    # 获取所有已有的Sector ETF
    sector_etfs = db.query(SectorETF).all()
    for etf in sector_etfs:
        existing = db.query(ETFRefreshConfig).filter(
            ETFRefreshConfig.etf_symbol == etf.symbol
        ).first()
        
        if not existing:
            # 计算持仓数量
            holdings_count = db.query(ETFHolding).filter(
                ETFHolding.sector_etf_symbol == etf.symbol
            ).count()
            
            config = ETFRefreshConfig(
                etf_symbol=etf.symbol,
                etf_type='sector',
                etf_name=SECTOR_ETF_NAMES.get(etf.symbol, etf.name),
                total_holdings=holdings_count,
                top_n=20,
                frequency='daily',
                status='pending'
            )
            db.add(config)
    
    # 获取所有已有的Industry ETF
    industry_etfs = db.query(IndustryETF).all()
    for etf in industry_etfs:
        existing = db.query(ETFRefreshConfig).filter(
            ETFRefreshConfig.etf_symbol == etf.symbol
        ).first()
        
        if not existing:
            holdings_count = db.query(ETFHolding).filter(
                ETFHolding.industry_etf_symbol == etf.symbol
            ).count()
            
            config = ETFRefreshConfig(
                etf_symbol=etf.symbol,
                etf_type='industry',
                etf_name=INDUSTRY_ETF_NAMES.get(etf.symbol, etf.name),
                total_holdings=holdings_count,
                top_n=15,
                frequency='daily',
                status='pending'
            )
            db.add(config)
    
    db.commit()


# ==================== 统一更新 ====================
# 存储当前更新会话（简单内存存储，生产环境应使用Redis）
_current_update_session: Optional[Dict] = None


@router.get("/update/status", response_model=UpdateProgressResponse)
async def get_update_status(db: Session = Depends(get_db)):
    """获取当前更新状态"""
    global _current_update_session
    
    if not _current_update_session:
        # 检查数据库中是否有活跃会话
        session = db.query(UpdateSession).filter(
            UpdateSession.status.in_(['fetching', 'validating', 'computing'])
        ).order_by(UpdateSession.created_at.desc()).first()
        
        if session:
            progress = 0
            if session.total_symbols > 0:
                progress = int((session.completed_symbols / session.total_symbols) * 100)
            
            return UpdateProgressResponse(
                session_id=session.session_id,
                status=session.status,
                phase=session.phase,
                total=session.total_symbols,
                completed=session.completed_symbols,
                failed=session.failed_symbols,
                progress_percent=progress,
                can_compute=session.can_compute,
                message=session.error_message
            )
        
        # 无活跃会话
        return UpdateProgressResponse(
            session_id="",
            status="idle",
            can_compute=await check_can_compute(db)
        )
    
    return UpdateProgressResponse(**_current_update_session)


async def check_can_compute(db: Session) -> bool:
    """检查是否可以执行计算"""
    # 获取数据源状态
    status = await get_data_sources_status(db)
    # 至少需要70%的整体完备度才能计算
    return status.overall_completeness >= 70


@router.post("/update/start", response_model=UpdateProgressResponse)
async def start_unified_update(
    request: UnifiedUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """开始统一更新"""
    global _current_update_session
    
    # 检查是否有正在进行的更新
    if _current_update_session and _current_update_session.get('status') in ['fetching', 'validating']:
        raise HTTPException(status_code=400, detail="An update is already in progress")
    
    # 创建新的更新会话
    session_id = str(uuid.uuid4())[:8]
    
    # 获取需要更新的标的
    if request.etf_symbols:
        configs = db.query(ETFRefreshConfig).filter(
            ETFRefreshConfig.etf_symbol.in_([s.upper() for s in request.etf_symbols])
        ).all()
    else:
        configs = db.query(ETFRefreshConfig).all()
    
    symbol_map = get_unique_symbols_from_configs(db, configs)
    total_symbols = len(symbol_map)
    
    # 初始化会话状态
    _current_update_session = {
        "session_id": session_id,
        "status": "fetching",
        "phase": "初始化更新...",
        "total": total_symbols,
        "completed": 0,
        "failed": 0,
        "progress_percent": 0,
        "can_compute": False,
        "message": None
    }
    
    # 创建数据库记录
    session = UpdateSession(
        session_id=session_id,
        status="fetching",
        phase="初始化更新...",
        total_symbols=total_symbols,
        started_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    
    # 在后台执行更新
    background_tasks.add_task(
        execute_unified_update, 
        session_id, 
        list(symbol_map.keys()),
        request.force_refresh
    )
    
    return UpdateProgressResponse(**_current_update_session)


async def execute_unified_update(session_id: str, symbols: List[str], force_refresh: bool):
    """执行统一更新（后台任务）"""
    global _current_update_session
    
    from ..database import SessionLocal
    db = SessionLocal()
    
    try:
        completed = 0
        failed = 0
        
        for ticker in symbols:
            try:
                # 更新标的数据
                symbol = db.query(SymbolPool).filter(SymbolPool.ticker == ticker).first()
                if not symbol:
                    symbol = SymbolPool(ticker=ticker)
                    db.add(symbol)
                
                # 检查Finviz数据
                finviz = db.query(FinvizData).filter(
                    FinvizData.ticker == ticker
                ).order_by(FinvizData.data_date.desc()).first()
                
                if finviz:
                    symbol.finviz_status = 'ready'
                    symbol.finviz_last_update = datetime.utcnow()
                
                # 检查MarketChameleon数据
                mc = db.query(MarketChameleonData).filter(
                    MarketChameleonData.symbol == ticker
                ).order_by(MarketChameleonData.data_date.desc()).first()
                
                if mc:
                    symbol.mc_status = 'ready'
                    symbol.mc_last_update = datetime.utcnow()
                
                # 计算完备度
                symbol.completeness = calculate_symbol_completeness(symbol)
                symbol.updated_at = datetime.utcnow()
                
                completed += 1
                
                # 更新进度
                progress = int((completed / len(symbols)) * 100)
                _current_update_session.update({
                    "completed": completed,
                    "failed": failed,
                    "progress_percent": progress,
                    "phase": f"处理标的 {ticker} ({completed}/{len(symbols)})"
                })
                
                # 每10个标的提交一次
                if completed % 10 == 0:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Error updating symbol {ticker}: {e}")
                failed += 1
        
        # 更新会话状态
        _current_update_session.update({
            "status": "validating",
            "phase": "验证数据完整性...",
            "progress_percent": 95
        })
        
        db.commit()
        
        # 验证完成
        can_compute = await check_can_compute(db)
        
        _current_update_session.update({
            "status": "complete",
            "phase": "更新完成",
            "progress_percent": 100,
            "can_compute": can_compute,
            "message": f"成功更新 {completed} 个标的，失败 {failed} 个"
        })
        
        # 更新数据库记录
        session = db.query(UpdateSession).filter(
            UpdateSession.session_id == session_id
        ).first()
        if session:
            session.status = "complete"
            session.completed_symbols = completed
            session.failed_symbols = failed
            session.can_compute = can_compute
            session.completed_at = datetime.utcnow()
            db.commit()
        
        # 更新ETF配置状态
        configs = db.query(ETFRefreshConfig).all()
        for config in configs:
            config.status = 'ready'
            config.last_refresh = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Unified update error: {e}")
        _current_update_session.update({
            "status": "error",
            "message": str(e)
        })
    finally:
        db.close()


@router.post("/compute", response_model=ComputeResponse)
async def execute_compute(
    request: ComputeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """执行后端计算（动能评分等）"""
    # 检查是否可以计算
    can_compute = await check_can_compute(db)
    
    if not can_compute:
        raise HTTPException(
            status_code=400, 
            detail="数据不完整，无法执行计算。请先完成数据更新。"
        )
    
    try:
        from ..services import CalculationService
        
        calc_service = CalculationService(db)
        
        etfs_computed = 0
        stocks_computed = 0
        
        # 计算板块ETF评分
        sector_etfs = db.query(SectorETF).all()
        for etf in sector_etfs:
            if request.etf_symbols and etf.symbol not in request.etf_symbols:
                continue
            
            # 获取该ETF的数据
            finviz_data = db.query(FinvizData).filter(
                FinvizData.etf_symbol == etf.symbol
            ).all()
            mc_data = db.query(MarketChameleonData).filter(
                MarketChameleonData.etf_symbol == etf.symbol
            ).all()
            
            # 计算评分
            calc_service.update_sector_etf_scores(etf.symbol, {}, finviz_data, mc_data)
            etfs_computed += 1
        
        # 计算行业ETF评分
        industry_etfs = db.query(IndustryETF).all()
        for etf in industry_etfs:
            if request.etf_symbols and etf.symbol not in request.etf_symbols:
                continue
            
            finviz_data = db.query(FinvizData).filter(
                FinvizData.etf_symbol == etf.symbol
            ).all()
            mc_data = db.query(MarketChameleonData).filter(
                MarketChameleonData.etf_symbol == etf.symbol
            ).all()
            
            # 更新分数
            if finviz_data:
                etf.breadth_score, etf.pct_above_50ma, etf.pct_above_200ma = \
                    calc_service.calculate_breadth_score(finviz_data)
            if mc_data:
                etf.options_score, etf.options_heat, etf.rel_vol, etf.ivr = \
                    calc_service.calculate_options_confirm_score(mc_data)
            
            etf.composite_score = calc_service.calculate_etf_composite_score(
                etf.rel_momentum_score or 0,
                etf.trend_quality_score or 0,
                etf.breadth_score or 0,
                etf.options_score or 0
            )
            etfs_computed += 1
        
        db.commit()
        
        return ComputeResponse(
            success=True,
            message=f"计算完成：{etfs_computed} 个ETF",
            etfs_computed=etfs_computed,
            stocks_computed=stocks_computed,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Compute error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/cancel")
async def cancel_update(db: Session = Depends(get_db)):
    """取消当前更新"""
    global _current_update_session
    
    if _current_update_session and _current_update_session.get('status') in ['fetching', 'validating']:
        _current_update_session.update({
            "status": "cancelled",
            "message": "更新已取消"
        })
        return {"message": "Update cancelled"}
    
    return {"message": "No active update to cancel"}
