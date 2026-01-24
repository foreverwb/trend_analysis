"""
Trend Analysis System - FastAPI Main Application
强势动能交易系统 - 主程序
"""
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .database import init_db
from .config_loader import init_config, get_current_config
from .logging_utils import setup_logging, get_api_logger
from .routers import (
    etf_router, 
    momentum_router, 
    market_router, 
    import_router,
    config_router,
    options_router,
    symbol_pool_router,
    data_trigger_router,
    monitor_tasks_router,
    monitor_data_import_router
)

# Initialize configuration
config = init_config()

# Setup logging with configuration
setup_logging(
    level=config.logging.level,
    log_format=config.logging.format,
    log_file=config.logging.file,
    max_file_size=config.logging.max_file_size,
    backup_count=config.logging.backup_count
)

logger = logging.getLogger(__name__)
api_logger = get_api_logger("HTTP")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting 强势动能交易系统 (Trend Analysis System)...")
    logger.info("=" * 60)
    
    # Log configuration
    logger.info("Configuration loaded:")
    logger.info(f"  - IBKR: {config.ibkr.host}:{config.ibkr.port} (Enabled: {config.ibkr.enabled})")
    logger.info(f"  - Futu: {config.futu.host}:{config.futu.port} (Enabled: {config.futu.enabled})")
    logger.info(f"  - Options Data Source: Primary={config.data_sources.options_data.primary}, "
               f"Fallback={config.data_sources.options_data.fallback}")
    logger.info(f"  - Market Data Source: Primary={config.data_sources.market_data.primary}, "
               f"Fallback={config.data_sources.market_data.fallback}")
    logger.info(f"  - Server: {config.server.host}:{config.server.port}")
    logger.info(f"  - Log Level: {config.logging.level}")
    logger.info(f"  - Debug Mode: {config.server.debug}")
    logger.info(f"  - Log API Calls: {config.logging.log_api_calls}")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    logger.info("=" * 60)
    logger.info("System started successfully!")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Trend Analysis System...")


app = FastAPI(
    title="Trend Analysis System",
    description="强势动能交易系统 - Momentum Trading System",
    version="1.0.0",
    lifespan=lifespan
)


# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTTP Request/Response Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses"""
    start_time = time.time()
    
    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    # Log request
    if config.logging.log_api_calls:
        api_logger.log_request(method, path, {"client_ip": client_ip})
    
    # Process request
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        if config.logging.log_api_calls:
            status = "success" if response.status_code < 400 else "error"
            api_logger.log_response(
                method, path, status, duration_ms,
                data={"status_code": response.status_code},
                log_data=config.logging.log_response_data
            )
        
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        api_logger.log_error(method, path, e, duration_ms)
        raise


# Include routers
app.include_router(etf_router)
app.include_router(momentum_router)
app.include_router(market_router)
app.include_router(import_router)
app.include_router(config_router)
app.include_router(options_router)
app.include_router(symbol_pool_router)
app.include_router(data_trigger_router)
app.include_router(monitor_tasks_router)
app.include_router(monitor_data_import_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Trend Analysis System",
        "name_cn": "强势动能交易系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/config/info")
async def get_config_info():
    """Get non-sensitive configuration information"""
    return {
        "ibkr": {
            "host": config.ibkr.host,
            "port": config.ibkr.port,
            "enabled": config.ibkr.enabled,
            "connection_timeout": config.ibkr.connection_timeout
        },
        "futu": {
            "host": config.futu.host,
            "port": config.futu.port,
            "enabled": config.futu.enabled,
            "max_requests_per_minute": config.futu.max_requests_per_minute
        },
        "data_sources": {
            "options_data": {
                "primary": config.data_sources.options_data.primary,
                "fallback": config.data_sources.options_data.fallback,
                "auto_fallback": config.data_sources.options_data.auto_fallback
            },
            "market_data": {
                "primary": config.data_sources.market_data.primary,
                "fallback": config.data_sources.market_data.fallback,
                "auto_fallback": config.data_sources.market_data.auto_fallback
            }
        },
        "server": {
            "host": config.server.host,
            "port": config.server.port,
            "debug": config.server.debug
        },
        "logging": {
            "level": config.logging.level,
            "log_api_calls": config.logging.log_api_calls,
            "log_response_data": config.logging.log_response_data
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=config.server.host, 
        port=config.server.port,
        log_level=config.logging.level.lower()
    )
