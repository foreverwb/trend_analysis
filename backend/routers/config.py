"""
Data Source Configuration API Routes
Handles IBKR and Futu connection configuration
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..database import get_db
from ..models import DataSourceConfig
from ..schemas import (
    IBKRConfig, FutuConfig, 
    DataSourceConfigResponse, ConnectionTestResult
)
from ..services import get_ibkr_service, get_futu_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("/datasources")
async def get_all_configs(db: Session = Depends(get_db)):
    """Get all data source configurations"""
    configs = db.query(DataSourceConfig).all()
    
    # Ensure default configs exist
    sources = {c.source for c in configs}
    
    if "ibkr" not in sources:
        ibkr_config = DataSourceConfig(
            source="ibkr",
            host="127.0.0.1",
            port=4001,
            client_id="1"
        )
        db.add(ibkr_config)
        configs.append(ibkr_config)
    
    if "futu" not in sources:
        futu_config = DataSourceConfig(
            source="futu",
            host="127.0.0.1",
            port=11111
        )
        db.add(futu_config)
        configs.append(futu_config)
    
    db.commit()
    
    return [
        {
            "source": c.source,
            "host": c.host,
            "port": c.port,
            "client_id": c.client_id,
            "account_id": c.account_id,
            "is_connected": c.is_connected,
            "last_connected_at": c.last_connected_at
        }
        for c in configs
    ]


@router.get("/datasources/{source}", response_model=DataSourceConfigResponse)
async def get_config(source: str, db: Session = Depends(get_db)):
    """Get configuration for a specific data source"""
    config = db.query(DataSourceConfig).filter(DataSourceConfig.source == source).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config for {source} not found")
    return config


@router.put("/datasources/ibkr")
async def update_ibkr_config(config: IBKRConfig, db: Session = Depends(get_db)):
    """Update IBKR configuration"""
    db_config = db.query(DataSourceConfig).filter(DataSourceConfig.source == "ibkr").first()
    
    if not db_config:
        db_config = DataSourceConfig(source="ibkr")
        db.add(db_config)
    
    db_config.host = config.host
    db_config.port = config.port
    db_config.client_id = config.client_id
    db_config.account_id = config.account_id
    db_config.is_connected = False  # Reset connection status
    
    db.commit()
    
    return {
        "message": "IBKR configuration updated",
        "config": {
            "host": db_config.host,
            "port": db_config.port,
            "client_id": db_config.client_id,
            "account_id": db_config.account_id
        }
    }


@router.put("/datasources/futu")
async def update_futu_config(config: FutuConfig, db: Session = Depends(get_db)):
    """Update Futu configuration"""
    db_config = db.query(DataSourceConfig).filter(DataSourceConfig.source == "futu").first()
    
    if not db_config:
        db_config = DataSourceConfig(source="futu")
        db.add(db_config)
    
    db_config.host = config.host
    db_config.port = config.port
    db_config.api_key = config.api_key
    db_config.api_secret = config.api_secret
    db_config.is_connected = False
    
    db.commit()
    
    return {
        "message": "Futu configuration updated",
        "config": {
            "host": db_config.host,
            "port": db_config.port
        }
    }


@router.post("/datasources/ibkr/test", response_model=ConnectionTestResult)
async def test_ibkr_connection(db: Session = Depends(get_db)):
    """Test IBKR connection"""
    config = db.query(DataSourceConfig).filter(DataSourceConfig.source == "ibkr").first()
    
    if not config:
        return ConnectionTestResult(
            source="ibkr",
            success=False,
            message="IBKR not configured",
            timestamp=datetime.now()
        )
    
    try:
        ibkr = get_ibkr_service(
            host=config.host,
            port=config.port,
            client_id=int(config.client_id) if config.client_id else 1
        )
        
        connected = await ibkr.connect()
        
        if connected:
            config.is_connected = True
            config.last_connected_at = datetime.now()
            db.commit()
            
            return ConnectionTestResult(
                source="ibkr",
                success=True,
                message="Successfully connected to IB Gateway",
                timestamp=datetime.now()
            )
        else:
            config.is_connected = False
            db.commit()
            
            return ConnectionTestResult(
                source="ibkr",
                success=False,
                message="Failed to connect to IB Gateway. Please check if IB Gateway is running.",
                timestamp=datetime.now()
            )
    except Exception as e:
        logger.error(f"IBKR connection test error: {e}")
        config.is_connected = False
        db.commit()
        
        return ConnectionTestResult(
            source="ibkr",
            success=False,
            message=str(e),
            timestamp=datetime.now()
        )


@router.post("/datasources/futu/test", response_model=ConnectionTestResult)
async def test_futu_connection(db: Session = Depends(get_db)):
    """Test Futu OpenD connection"""
    config = db.query(DataSourceConfig).filter(DataSourceConfig.source == "futu").first()
    
    if not config:
        return ConnectionTestResult(
            source="futu",
            success=False,
            message="Futu not configured",
            timestamp=datetime.now()
        )
    
    try:
        futu = get_futu_service(
            host=config.host,
            port=config.port
        )
        
        connected = await futu.connect()
        
        if connected:
            config.is_connected = True
            config.last_connected_at = datetime.now()
            db.commit()
            
            return ConnectionTestResult(
                source="futu",
                success=True,
                message="Successfully connected to Futu OpenD",
                timestamp=datetime.now()
            )
        else:
            config.is_connected = False
            db.commit()
            
            return ConnectionTestResult(
                source="futu",
                success=False,
                message="Failed to connect to Futu OpenD. Please check if OpenD is running.",
                timestamp=datetime.now()
            )
    except Exception as e:
        logger.error(f"Futu connection test error: {e}")
        config.is_connected = False
        db.commit()
        
        return ConnectionTestResult(
            source="futu",
            success=False,
            message=str(e),
            timestamp=datetime.now()
        )


@router.post("/datasources/{source}/disconnect")
async def disconnect_source(source: str, db: Session = Depends(get_db)):
    """Disconnect a data source"""
    config = db.query(DataSourceConfig).filter(DataSourceConfig.source == source).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Config for {source} not found")
    
    try:
        if source == "ibkr":
            ibkr = get_ibkr_service()
            await ibkr.disconnect()
        elif source == "futu":
            futu = get_futu_service()
            await futu.disconnect()
        
        config.is_connected = False
        db.commit()
        
        return {"message": f"{source} disconnected successfully"}
    except Exception as e:
        logger.error(f"Disconnect error for {source}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
