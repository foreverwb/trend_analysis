"""
Configuration Loader Module
Loads and validates configuration from config.yaml
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass
class IBKRConfig:
    """IBKR API Configuration"""
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 1
    account_id: str = ""
    connection_timeout: int = 10
    enabled: bool = True


@dataclass
class FutuConfig:
    """Futu OpenD API Configuration"""
    host: str = "127.0.0.1"
    port: int = 11111
    api_key: str = ""
    api_secret: str = ""
    max_requests_per_minute: int = 60
    enabled: bool = True


@dataclass
class LoggingConfig:
    """Logging Configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    file: str = "logs/app.log"
    log_api_calls: bool = True
    log_response_data: bool = False
    max_file_size: int = 10
    backup_count: int = 5


@dataclass
class ServerConfig:
    """Server Configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173"
    ])


@dataclass
class DatabaseConfig:
    """Database Configuration"""
    path: str = "backend/trend_analysis.db"
    echo: bool = False


@dataclass
class CacheConfig:
    """Cache Configuration"""
    market_data_ttl: int = 60
    etf_data_ttl: int = 300


@dataclass
class SourceConfig:
    """Single data source configuration"""
    primary: str = "futu"        # Primary data source: ibkr / futu
    fallback: str = "ibkr"       # Fallback data source
    auto_fallback: bool = True   # Auto switch on failure


@dataclass
class DataSourcesConfig:
    """Data Sources Selection Configuration"""
    options_data: SourceConfig = field(default_factory=lambda: SourceConfig(
        primary="futu", fallback="ibkr", auto_fallback=True
    ))
    market_data: SourceConfig = field(default_factory=lambda: SourceConfig(
        primary="ibkr", fallback="futu", auto_fallback=True
    ))


@dataclass
class AppConfig:
    """Main Application Configuration"""
    ibkr: IBKRConfig = field(default_factory=IBKRConfig)
    futu: FutuConfig = field(default_factory=FutuConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    data_sources: DataSourcesConfig = field(default_factory=DataSourcesConfig)


def _find_config_file() -> Optional[Path]:
    """Find config.yaml in various locations"""
    possible_paths = [
        Path("config.yaml"),
        Path("../config.yaml"),
        Path(__file__).parent.parent / "config.yaml",
        Path(__file__).parent.parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path.resolve()
    
    return None


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f) or {}
        logger.info(f"Configuration loaded from: {config_path}")
        return config_dict
    except Exception as e:
        logger.warning(f"Failed to load config from {config_path}: {e}")
        return {}


def _parse_ibkr_config(data: Dict[str, Any]) -> IBKRConfig:
    """Parse IBKR configuration"""
    ibkr_data = data.get('ibkr', {})
    return IBKRConfig(
        host=ibkr_data.get('host', '127.0.0.1'),
        port=int(ibkr_data.get('port', 4001)),
        client_id=int(ibkr_data.get('client_id', 1)),
        account_id=str(ibkr_data.get('account_id', '')),
        connection_timeout=int(ibkr_data.get('connection_timeout', 10)),
        enabled=bool(ibkr_data.get('enabled', True))
    )


def _parse_futu_config(data: Dict[str, Any]) -> FutuConfig:
    """Parse Futu configuration"""
    futu_data = data.get('futu', {})
    return FutuConfig(
        host=futu_data.get('host', '127.0.0.1'),
        port=int(futu_data.get('port', 11111)),
        api_key=str(futu_data.get('api_key', '')),
        api_secret=str(futu_data.get('api_secret', '')),
        max_requests_per_minute=int(futu_data.get('max_requests_per_minute', 60)),
        enabled=bool(futu_data.get('enabled', True))
    )


def _parse_logging_config(data: Dict[str, Any]) -> LoggingConfig:
    """Parse logging configuration"""
    log_data = data.get('logging', {})
    return LoggingConfig(
        level=log_data.get('level', 'INFO'),
        format=log_data.get('format', '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'),
        file=log_data.get('file', 'logs/app.log'),
        log_api_calls=bool(log_data.get('log_api_calls', True)),
        log_response_data=bool(log_data.get('log_response_data', False)),
        max_file_size=int(log_data.get('max_file_size', 10)),
        backup_count=int(log_data.get('backup_count', 5))
    )


def _parse_server_config(data: Dict[str, Any]) -> ServerConfig:
    """Parse server configuration"""
    server_data = data.get('server', {})
    return ServerConfig(
        host=server_data.get('host', '0.0.0.0'),
        port=int(server_data.get('port', 8000)),
        debug=bool(server_data.get('debug', False)),
        cors_origins=server_data.get('cors_origins', [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173"
        ])
    )


def _parse_database_config(data: Dict[str, Any]) -> DatabaseConfig:
    """Parse database configuration"""
    db_data = data.get('database', {})
    return DatabaseConfig(
        path=db_data.get('path', 'backend/trend_analysis.db'),
        echo=bool(db_data.get('echo', False))
    )


def _parse_cache_config(data: Dict[str, Any]) -> CacheConfig:
    """Parse cache configuration"""
    cache_data = data.get('cache', {})
    return CacheConfig(
        market_data_ttl=int(cache_data.get('market_data_ttl', 60)),
        etf_data_ttl=int(cache_data.get('etf_data_ttl', 300))
    )


def _parse_source_config(data: Dict[str, Any], default_primary: str, default_fallback: str) -> SourceConfig:
    """Parse single source configuration"""
    return SourceConfig(
        primary=data.get('primary', default_primary),
        fallback=data.get('fallback', default_fallback),
        auto_fallback=bool(data.get('auto_fallback', True))
    )


def _parse_data_sources_config(data: Dict[str, Any]) -> DataSourcesConfig:
    """Parse data sources configuration"""
    ds_data = data.get('data_sources', {})
    
    options_data = ds_data.get('options_data', {})
    market_data = ds_data.get('market_data', {})
    
    return DataSourcesConfig(
        options_data=_parse_source_config(options_data, 'futu', 'ibkr'),
        market_data=_parse_source_config(market_data, 'ibkr', 'futu')
    )


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    """
    Load and parse application configuration.
    Uses caching to avoid repeated file reads.
    """
    config_path = _find_config_file()
    
    if config_path:
        config_dict = _load_yaml_config(config_path)
    else:
        logger.warning("No config.yaml found, using default configuration")
        config_dict = {}
    
    return AppConfig(
        ibkr=_parse_ibkr_config(config_dict),
        futu=_parse_futu_config(config_dict),
        logging=_parse_logging_config(config_dict),
        server=_parse_server_config(config_dict),
        database=_parse_database_config(config_dict),
        cache=_parse_cache_config(config_dict),
        data_sources=_parse_data_sources_config(config_dict)
    )


def reload_config() -> AppConfig:
    """
    Force reload configuration from file.
    Clears the cache and reloads.
    """
    load_config.cache_clear()
    return load_config()


def get_config() -> AppConfig:
    """
    Get current application configuration.
    Alias for load_config().
    """
    return load_config()


# Environment variable overrides
def apply_env_overrides(config: AppConfig) -> AppConfig:
    """
    Apply environment variable overrides to configuration.
    Environment variables take precedence over config file.
    """
    # IBKR overrides
    if os.getenv('IBKR_HOST'):
        config.ibkr.host = os.getenv('IBKR_HOST')
    if os.getenv('IBKR_PORT'):
        config.ibkr.port = int(os.getenv('IBKR_PORT'))
    if os.getenv('IBKR_CLIENT_ID'):
        config.ibkr.client_id = int(os.getenv('IBKR_CLIENT_ID'))
    if os.getenv('IBKR_ACCOUNT_ID'):
        config.ibkr.account_id = os.getenv('IBKR_ACCOUNT_ID')
    
    # Futu overrides
    if os.getenv('FUTU_HOST'):
        config.futu.host = os.getenv('FUTU_HOST')
    if os.getenv('FUTU_PORT'):
        config.futu.port = int(os.getenv('FUTU_PORT'))
    
    # Server overrides
    if os.getenv('SERVER_HOST'):
        config.server.host = os.getenv('SERVER_HOST')
    if os.getenv('SERVER_PORT'):
        config.server.port = int(os.getenv('SERVER_PORT'))
    if os.getenv('DEBUG'):
        config.server.debug = os.getenv('DEBUG').lower() in ('true', '1', 'yes')
    
    # Logging overrides
    if os.getenv('LOG_LEVEL'):
        config.logging.level = os.getenv('LOG_LEVEL')
    
    # Data sources overrides
    if os.getenv('OPTIONS_DATA_PRIMARY'):
        config.data_sources.options_data.primary = os.getenv('OPTIONS_DATA_PRIMARY')
    if os.getenv('OPTIONS_DATA_FALLBACK'):
        config.data_sources.options_data.fallback = os.getenv('OPTIONS_DATA_FALLBACK')
    if os.getenv('MARKET_DATA_PRIMARY'):
        config.data_sources.market_data.primary = os.getenv('MARKET_DATA_PRIMARY')
    
    return config


# Initialize on import
_config: Optional[AppConfig] = None


def init_config() -> AppConfig:
    """Initialize configuration on application startup"""
    global _config
    _config = load_config()
    _config = apply_env_overrides(_config)
    return _config


def get_current_config() -> AppConfig:
    """Get current initialized configuration"""
    global _config
    if _config is None:
        _config = init_config()
    return _config
