"""
Monitor Data Import API Routes - 监控任务数据导入 API
支持 Finviz 和 MarketChameleon 数据的文本粘贴和文件上传
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import logging

from ..database import get_db
from ..models_monitor import (
    MonitorTask, TaskETFConfig, ETFFinvizData, ETFMCData, DataImportLog
)
from ..schemas_monitor import (
    TextImportRequest, ImportResponse, ImportLogResponse,
    ImportType, InputMethod
)
from ..services.data_parsers import (
    FinvizDataParser, MarketChameleonDataParser, detect_data_source
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor/import", tags=["Monitor Data Import"])


# ==================== Text Import ====================

@router.post("/text", response_model=ImportResponse)
async def import_text_data(
    request: TextImportRequest,
    db: Session = Depends(get_db)
):
    """
    通过文本粘贴导入数据
    
    支持 Finviz 和 MarketChameleon JSON 格式
    """
    task = db.query(MonitorTask).filter(MonitorTask.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 验证 ETF 是否属于该任务
    etf_config = db.query(TaskETFConfig).filter(
        TaskETFConfig.task_id == request.task_id,
        TaskETFConfig.etf_symbol == request.etf_symbol.upper()
    ).first()
    if not etf_config:
        raise HTTPException(status_code=400, detail=f"ETF {request.etf_symbol} not configured for this task")
    
    try:
        # 解析 JSON
        data = json.loads(request.json_data)
        
        if request.import_type == ImportType.FINVIZ:
            return await _import_finviz_data(
                db, task, etf_config, data, InputMethod.TEXT, None
            )
        elif request.import_type == ImportType.MARKET_CHAMELEON:
            return await _import_mc_data(
                db, task, etf_config, data, InputMethod.TEXT, None
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import type: {request.import_type}")
    
    except json.JSONDecodeError as e:
        _log_import(db, request.task_id, request.etf_symbol, request.import_type.value, 
                   InputMethod.TEXT.value, None, 0, "failed", f"JSON 格式错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"Text import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== File Import ====================

@router.post("/file", response_model=ImportResponse)
async def import_file_data(
    file: UploadFile = File(...),
    task_id: int = Form(...),
    etf_symbol: str = Form(...),
    import_type: str = Form(...),  # 'finviz' | 'market_chameleon'
    db: Session = Depends(get_db)
):
    """
    通过文件上传导入数据
    
    支持 .json 文件
    """
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 验证 ETF 是否属于该任务
    etf_config = db.query(TaskETFConfig).filter(
        TaskETFConfig.task_id == task_id,
        TaskETFConfig.etf_symbol == etf_symbol.upper()
    ).first()
    if not etf_config:
        raise HTTPException(status_code=400, detail=f"ETF {etf_symbol} not configured for this task")
    
    # 验证文件类型
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only .json files are supported")
    
    try:
        # 读取文件内容
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # 自动检测数据来源（如果未指定或需要验证）
        detected_source = detect_data_source(data)
        if detected_source and detected_source != import_type:
            logger.warning(f"Import type mismatch: specified={import_type}, detected={detected_source}")
        
        if import_type == 'finviz':
            return await _import_finviz_data(
                db, task, etf_config, data, InputMethod.FILE, file.filename
            )
        elif import_type == 'market_chameleon':
            return await _import_mc_data(
                db, task, etf_config, data, InputMethod.FILE, file.filename
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import type: {import_type}")
    
    except json.JSONDecodeError as e:
        _log_import(db, task_id, etf_symbol, import_type, 
                   InputMethod.FILE.value, file.filename, 0, "failed", f"JSON 格式错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"File import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Auto-detect Import ====================

@router.post("/auto", response_model=ImportResponse)
async def import_auto_detect(
    file: UploadFile = File(...),
    task_id: int = Form(...),
    etf_symbol: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    自动检测数据来源并导入
    
    系统会根据 JSON 结构自动判断是 Finviz 还是 MarketChameleon 数据
    """
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    etf_config = db.query(TaskETFConfig).filter(
        TaskETFConfig.task_id == task_id,
        TaskETFConfig.etf_symbol == etf_symbol.upper()
    ).first()
    if not etf_config:
        raise HTTPException(status_code=400, detail=f"ETF {etf_symbol} not configured for this task")
    
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # 自动检测数据来源
        detected_source = detect_data_source(data)
        if not detected_source:
            raise HTTPException(status_code=400, detail="无法识别数据格式，请手动指定数据来源")
        
        if detected_source == 'finviz':
            return await _import_finviz_data(
                db, task, etf_config, data, InputMethod.FILE, file.filename
            )
        else:
            return await _import_mc_data(
                db, task, etf_config, data, InputMethod.FILE, file.filename
            )
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"Auto import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Import History ====================

@router.get("/history/{task_id}", response_model=List[ImportLogResponse])
async def get_import_history(
    task_id: int,
    etf_symbol: Optional[str] = None,
    import_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取导入历史"""
    query = db.query(DataImportLog).filter(DataImportLog.task_id == task_id)
    
    if etf_symbol:
        query = query.filter(DataImportLog.etf_symbol == etf_symbol.upper())
    if import_type:
        query = query.filter(DataImportLog.import_type == import_type)
    
    logs = query.order_by(DataImportLog.imported_at.desc()).limit(limit).all()
    return logs


@router.delete("/history/{log_id}")
async def delete_import_log(
    log_id: int,
    db: Session = Depends(get_db)
):
    """删除导入日志"""
    log = db.query(DataImportLog).filter(DataImportLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Import log not found")
    
    db.delete(log)
    db.commit()
    return {"message": "Import log deleted"}


# ==================== Data Templates ====================

@router.get("/template/{template_type}")
async def get_import_template(template_type: str):
    """获取导入模板"""
    templates = {
        "finviz": [
            {
                "Ticker": "NVDA",
                "Beta": 2.31,
                "ATR": 5.38,
                "SMA50": 0.43,
                "SMA200": 11.85,
                "52W_High": -12.89,
                "RSI": 50.33,
                "Price": 184.84
            }
        ],
        "market_chameleon": [
            {
                "symbol": "LRCX",
                "RelVolTo90D": "1.22",
                "CallVolume": "24,635",
                "PutVolume": "21,919",
                "PutPct": "47.1%",
                "IV30": "58.8",
                "IVR": "94%",
                "HV20": "53.1",
                "OI_PctRank": "10%",
                "Earnings": "28-Jan-2026 AMC",
                "PriceChgPct": "-3.4%"
            }
        ]
    }
    
    if template_type not in templates:
        raise HTTPException(status_code=404, detail=f"Template {template_type} not found")
    
    return templates[template_type]


# ==================== Internal Functions ====================

async def _import_finviz_data(
    db: Session,
    task: MonitorTask,
    etf_config: TaskETFConfig,
    data: List[dict],
    input_method: InputMethod,
    file_name: Optional[str]
) -> ImportResponse:
    """导入 Finviz 数据"""
    
    # 验证数据
    is_valid, errors = FinvizDataParser.validate(data)
    if not is_valid:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    
    # 解析数据
    parsed_data, warnings = FinvizDataParser.parse(data)
    
    if not parsed_data:
        _log_import(db, task.id, etf_config.etf_symbol, ImportType.FINVIZ.value,
                   input_method.value, file_name, 0, "failed", "No valid records found")
        raise HTTPException(status_code=400, detail="No valid records found")
    
    try:
        # 清除旧数据（同一任务、同一ETF）
        db.query(ETFFinvizData).filter(
            ETFFinvizData.task_id == task.id,
            ETFFinvizData.etf_symbol == etf_config.etf_symbol
        ).delete()
        
        # 插入新数据
        for record in parsed_data:
            db_record = ETFFinvizData(
                task_id=task.id,
                etf_symbol=etf_config.etf_symbol,
                ticker=record['ticker'],
                beta=record.get('beta'),
                atr=record.get('atr'),
                sma50=record.get('sma50'),
                sma200=record.get('sma200'),
                week52_high=record.get('week52_high'),
                rsi=record.get('rsi'),
                price=record.get('price'),
                import_source='finviz'
            )
            db.add(db_record)
        
        # 更新 ETF 配置的数据更新时间
        etf_config.finviz_data_updated_at = datetime.utcnow()
        
        db.commit()
        
        # 记录导入日志
        _log_import(
            db, task.id, etf_config.etf_symbol, ImportType.FINVIZ.value,
            input_method.value, file_name, len(parsed_data), "success",
            warnings="; ".join(warnings) if warnings else None
        )
        
        return ImportResponse(
            success=True,
            task_id=task.id,
            etf_symbol=etf_config.etf_symbol,
            import_type=ImportType.FINVIZ.value,
            record_count=len(parsed_data),
            message=f"成功导入 {len(parsed_data)} 条 Finviz 记录",
            warnings=warnings,
            timestamp=datetime.now()
        )
    
    except Exception as e:
        db.rollback()
        _log_import(db, task.id, etf_config.etf_symbol, ImportType.FINVIZ.value,
                   input_method.value, file_name, 0, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))


async def _import_mc_data(
    db: Session,
    task: MonitorTask,
    etf_config: TaskETFConfig,
    data: List[dict],
    input_method: InputMethod,
    file_name: Optional[str]
) -> ImportResponse:
    """导入 MarketChameleon 数据"""
    
    # 验证数据
    is_valid, errors = MarketChameleonDataParser.validate(data)
    if not is_valid:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    
    # 解析数据
    parsed_data, warnings = MarketChameleonDataParser.parse(data)
    
    if not parsed_data:
        _log_import(db, task.id, etf_config.etf_symbol, ImportType.MARKET_CHAMELEON.value,
                   input_method.value, file_name, 0, "failed", "No valid records found")
        raise HTTPException(status_code=400, detail="No valid records found")
    
    try:
        # 清除旧数据
        db.query(ETFMCData).filter(
            ETFMCData.task_id == task.id,
            ETFMCData.etf_symbol == etf_config.etf_symbol
        ).delete()
        
        # 插入新数据
        for record in parsed_data:
            db_record = ETFMCData(
                task_id=task.id,
                etf_symbol=etf_config.etf_symbol,
                symbol=record['symbol'],
                rel_vol_to_90d=record.get('rel_vol_to_90d'),
                call_volume=record.get('call_volume'),
                put_volume=record.get('put_volume'),
                put_pct=record.get('put_pct'),
                single_leg_pct=record.get('single_leg_pct'),
                multi_leg_pct=record.get('multi_leg_pct'),
                contingent_pct=record.get('contingent_pct'),
                rel_notional_to_90d=record.get('rel_notional_to_90d'),
                call_notional=record.get('call_notional'),
                put_notional=record.get('put_notional'),
                iv30_chg_pct=record.get('iv30_chg_pct'),
                iv30=record.get('iv30'),
                hv20=record.get('hv20'),
                hv1y=record.get('hv1y'),
                ivr=record.get('ivr'),
                iv_52w_p=record.get('iv_52w_p'),
                volume=record.get('volume'),
                oi_pct_rank=record.get('oi_pct_rank'),
                earnings=record.get('earnings'),
                price_chg_pct=record.get('price_chg_pct'),
                import_source='market_chameleon'
            )
            db.add(db_record)
        
        # 更新 ETF 配置的数据更新时间
        etf_config.mc_data_updated_at = datetime.utcnow()
        
        db.commit()
        
        # 记录导入日志
        _log_import(
            db, task.id, etf_config.etf_symbol, ImportType.MARKET_CHAMELEON.value,
            input_method.value, file_name, len(parsed_data), "success",
            warnings="; ".join(warnings) if warnings else None
        )
        
        return ImportResponse(
            success=True,
            task_id=task.id,
            etf_symbol=etf_config.etf_symbol,
            import_type=ImportType.MARKET_CHAMELEON.value,
            record_count=len(parsed_data),
            message=f"成功导入 {len(parsed_data)} 条 MarketChameleon 记录",
            warnings=warnings,
            timestamp=datetime.now()
        )
    
    except Exception as e:
        db.rollback()
        _log_import(db, task.id, etf_config.etf_symbol, ImportType.MARKET_CHAMELEON.value,
                   input_method.value, file_name, 0, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))


def _log_import(
    db: Session,
    task_id: int,
    etf_symbol: str,
    import_type: str,
    input_method: str,
    file_name: Optional[str],
    record_count: int,
    status: str,
    error_message: Optional[str] = None,
    warnings: Optional[str] = None
):
    """记录导入日志"""
    log = DataImportLog(
        task_id=task_id,
        etf_symbol=etf_symbol,
        import_type=import_type,
        input_method=input_method,
        file_name=file_name,
        record_count=record_count,
        status=status,
        error_message=error_message,
        warnings=warnings
    )
    db.add(log)
    db.commit()
