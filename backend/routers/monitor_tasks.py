"""
Monitor Tasks API Routes - 监控任务管理 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
import logging

from ..database import get_db
from ..models_monitor import (
    MonitorTask, TaskETFConfig, ETFFinvizData, ETFMCData,
    ETFMarketData, ETFOptionsData, TaskScoreSnapshot, DataImportLog
)
from ..schemas_monitor import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    ETFConfigCreate, ETFConfigResponse,
    TaskStatus, TaskType, ETFLevel,
    DataStatusResponse, TaskDataStatusResponse,
    ScoreResponse, TaskScoreResponse,
    get_etf_metadata
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor/tasks", tags=["Monitor Tasks"])


# ==================== Task CRUD ====================

@router.post("", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """创建监控任务"""
    try:
        # 创建任务
        task = MonitorTask(
            task_name=task_data.task_name,
            task_type=task_data.task_type.value,
            description=task_data.description,
            benchmark_symbol=task_data.benchmark_symbol,
            coverage_type=task_data.coverage_type,
            is_auto_refresh=task_data.is_auto_refresh,
            status=TaskStatus.DRAFT.value
        )
        db.add(task)
        db.flush()  # 获取 task.id
        
        # 创建 ETF 配置
        for etf_config in task_data.etf_configs:
            config = TaskETFConfig(
                task_id=task.id,
                etf_symbol=etf_config.etf_symbol.upper(),
                etf_name=etf_config.etf_name or _get_etf_name(etf_config.etf_symbol),
                etf_level=etf_config.etf_level.value,
                parent_etf_symbol=etf_config.parent_etf_symbol.upper() if etf_config.parent_etf_symbol else None
            )
            db.add(config)
        
        db.commit()
        db.refresh(task)
        
        logger.info(f"Created monitor task: {task.task_name} (ID: {task.id})")
        
        return _task_to_response(task)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    query = db.query(MonitorTask)
    
    if status:
        query = query.filter(MonitorTask.status == status.value)
    if task_type:
        query = query.filter(MonitorTask.task_type == task_type.value)
    
    total = query.count()
    tasks = query.order_by(MonitorTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=total
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取任务详情"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return _task_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db)
):
    """更新任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # 更新字段
        if task_data.task_name is not None:
            task.task_name = task_data.task_name
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.benchmark_symbol is not None:
            task.benchmark_symbol = task_data.benchmark_symbol
        if task_data.coverage_type is not None:
            task.coverage_type = task_data.coverage_type
        if task_data.is_auto_refresh is not None:
            task.is_auto_refresh = task_data.is_auto_refresh
        if task_data.status is not None:
            task.status = task_data.status.value
        
        task.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(task)
        
        logger.info(f"Updated task: {task.task_name} (ID: {task.id})")
        
        return _task_to_response(task)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update task: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """删除任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_name = task.task_name
    db.delete(task)
    db.commit()
    
    logger.info(f"Deleted task: {task_name} (ID: {task_id})")
    
    return {"message": f"Task '{task_name}' deleted successfully"}


# ==================== Task Status ====================

@router.post("/{task_id}/activate", response_model=TaskResponse)
async def activate_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """激活任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.ACTIVE.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    return _task_to_response(task)


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """暂停任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.PAUSED.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    return _task_to_response(task)


@router.post("/{task_id}/archive", response_model=TaskResponse)
async def archive_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """归档任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.ARCHIVED.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    return _task_to_response(task)


# ==================== ETF Config ====================

@router.post("/{task_id}/etfs", response_model=ETFConfigResponse)
async def add_etf_to_task(
    task_id: int,
    etf_config: ETFConfigCreate,
    db: Session = Depends(get_db)
):
    """添加 ETF 到任务"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查是否已存在
    existing = db.query(TaskETFConfig).filter(
        TaskETFConfig.task_id == task_id,
        TaskETFConfig.etf_symbol == etf_config.etf_symbol.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="ETF already exists in this task")
    
    config = TaskETFConfig(
        task_id=task_id,
        etf_symbol=etf_config.etf_symbol.upper(),
        etf_name=etf_config.etf_name or _get_etf_name(etf_config.etf_symbol),
        etf_level=etf_config.etf_level.value,
        parent_etf_symbol=etf_config.parent_etf_symbol.upper() if etf_config.parent_etf_symbol else None
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return config


@router.delete("/{task_id}/etfs/{etf_symbol}")
async def remove_etf_from_task(
    task_id: int,
    etf_symbol: str,
    db: Session = Depends(get_db)
):
    """从任务中移除 ETF"""
    config = db.query(TaskETFConfig).filter(
        TaskETFConfig.task_id == task_id,
        TaskETFConfig.etf_symbol == etf_symbol.upper()
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="ETF not found in this task")
    
    db.delete(config)
    db.commit()
    
    return {"message": f"ETF {etf_symbol} removed from task"}


# ==================== Data Status ====================

@router.get("/{task_id}/data-status", response_model=TaskDataStatusResponse)
async def get_task_data_status(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取任务的数据状态"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    etf_statuses = []
    total_completeness = 0
    
    for config in task.etf_configs:
        etf_symbol = config.etf_symbol
        
        # 统计 Finviz 数据
        finviz_count = db.query(ETFFinvizData).filter(
            ETFFinvizData.task_id == task_id,
            ETFFinvizData.etf_symbol == etf_symbol
        ).count()
        
        # 统计 MC 数据
        mc_count = db.query(ETFMCData).filter(
            ETFMCData.task_id == task_id,
            ETFMCData.etf_symbol == etf_symbol
        ).count()
        
        # 获取市场数据
        market_data = db.query(ETFMarketData).filter(
            ETFMarketData.task_id == task_id,
            ETFMarketData.etf_symbol == etf_symbol
        ).order_by(ETFMarketData.trade_date.desc()).first()
        
        # 获取期权数据
        options_data = db.query(ETFOptionsData).filter(
            ETFOptionsData.task_id == task_id,
            ETFOptionsData.etf_symbol == etf_symbol
        ).order_by(ETFOptionsData.trade_date.desc()).first()
        
        # 计算完备度
        completeness = 0
        if finviz_count > 0:
            completeness += 25
        if mc_count > 0:
            completeness += 25
        if market_data:
            completeness += 25
        if options_data:
            completeness += 25
        
        total_completeness += completeness
        
        etf_statuses.append(DataStatusResponse(
            etf_symbol=etf_symbol,
            finviz_status="ready" if finviz_count > 0 else "pending",
            finviz_record_count=finviz_count,
            finviz_updated_at=config.finviz_data_updated_at,
            mc_status="ready" if mc_count > 0 else "pending",
            mc_record_count=mc_count,
            mc_updated_at=config.mc_data_updated_at,
            market_data_status="ready" if market_data else "pending",
            market_data_updated_at=config.market_data_updated_at,
            options_data_status="ready" if options_data else "pending",
            options_data_updated_at=config.options_data_updated_at
        ))
    
    overall_completeness = total_completeness / len(task.etf_configs) if task.etf_configs else 0
    
    return TaskDataStatusResponse(
        task_id=task_id,
        task_name=task.task_name,
        etf_statuses=etf_statuses,
        overall_completeness=overall_completeness
    )


# ==================== Scores ====================

@router.get("/{task_id}/scores", response_model=TaskScoreResponse)
async def get_task_scores(
    task_id: int,
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """获取任务评分"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not snapshot_date:
        snapshot_date = date.today()
    
    snapshots = db.query(TaskScoreSnapshot).filter(
        TaskScoreSnapshot.task_id == task_id,
        TaskScoreSnapshot.snapshot_date == snapshot_date
    ).order_by(TaskScoreSnapshot.rank_in_task).all()
    
    scores = [
        ScoreResponse(
            etf_symbol=s.etf_symbol,
            overall_score=float(s.overall_score) if s.overall_score else None,
            trend_score=float(s.trend_score) if s.trend_score else None,
            momentum_score=float(s.momentum_score) if s.momentum_score else None,
            rs_score=float(s.rs_score) if s.rs_score else None,
            options_score=float(s.options_score) if s.options_score else None,
            rank_in_task=s.rank_in_task,
            delta_3d=float(s.delta_3d) if s.delta_3d else None,
            delta_5d=float(s.delta_5d) if s.delta_5d else None,
            snapshot_date=s.snapshot_date
        )
        for s in snapshots
    ]
    
    return TaskScoreResponse(
        task_id=task_id,
        task_name=task.task_name,
        snapshot_date=snapshot_date,
        scores=scores
    )


# ==================== Helper Functions ====================

def _get_etf_name(symbol: str) -> str:
    """获取 ETF 名称"""
    metadata = get_etf_metadata(symbol)
    return metadata.name if metadata else symbol


def _task_to_response(task: MonitorTask) -> TaskResponse:
    """转换任务模型到响应"""
    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        task_type=TaskType(task.task_type),
        description=task.description,
        benchmark_symbol=task.benchmark_symbol,
        coverage_type=task.coverage_type,
        is_auto_refresh=task.is_auto_refresh,
        status=TaskStatus(task.status),
        created_at=task.created_at,
        updated_at=task.updated_at,
        last_refresh_at=task.last_refresh_at,
        etf_configs=[
            ETFConfigResponse(
                id=c.id,
                task_id=c.task_id,
                etf_symbol=c.etf_symbol,
                etf_name=c.etf_name,
                etf_level=ETFLevel(c.etf_level),
                parent_etf_symbol=c.parent_etf_symbol,
                finviz_data_updated_at=c.finviz_data_updated_at,
                mc_data_updated_at=c.mc_data_updated_at,
                market_data_updated_at=c.market_data_updated_at,
                options_data_updated_at=c.options_data_updated_at,
                created_at=c.created_at
            )
            for c in task.etf_configs
        ]
    )
