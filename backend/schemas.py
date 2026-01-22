"""
Pydantic Schemas for API Request/Response Validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# ==================== Data Source Config ====================
class DataSourceConfigBase(BaseModel):
    host: str = "127.0.0.1"
    port: int
    client_id: Optional[str] = None
    account_id: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class IBKRConfig(DataSourceConfigBase):
    port: int = 4001  # IB Gateway default
    client_id: str = "1"
    account_id: Optional[str] = None


class FutuConfig(DataSourceConfigBase):
    port: int = 11111
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class DataSourceConfigResponse(BaseModel):
    source: str
    host: str
    port: int
    is_connected: bool
    last_connected_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConnectionTestResult(BaseModel):
    source: str
    success: bool
    message: str
    timestamp: datetime


# ==================== ETF Holdings ====================
class HoldingBase(BaseModel):
    ticker: str
    weight: float


class HoldingCreate(HoldingBase):
    pass


class HoldingResponse(HoldingBase):
    id: int

    class Config:
        from_attributes = True


class HoldingsUpload(BaseModel):
    etf_symbol: str
    etf_type: str = "sector"  # 'sector' or 'industry'
    sector_symbol: Optional[str] = None  # For industry ETF
    data_date: date
    holdings: List[HoldingBase]


# ==================== Sector ETF ====================
class RelMomentumData(BaseModel):
    score: float = 0
    value: str = "+0.0%"
    rank: int = 0


class TrendQualityData(BaseModel):
    score: float = 0
    structure: str = "Neutral"
    slope: str = "+0.00"


class BreadthData(BaseModel):
    score: float = 0
    above50ma: str = "0%"
    above200ma: str = "0%"


class OptionsConfirmData(BaseModel):
    score: float = 0
    heat: str = "Low"
    relVol: str = "1.0x"
    ivr: float = 0


class SectorETFResponse(BaseModel):
    symbol: str
    name: str
    compositeScore: float
    relMomentum: RelMomentumData
    trendQuality: TrendQualityData
    breadth: BreadthData
    optionsConfirm: OptionsConfirmData
    holdings: List[HoldingResponse] = []
    
    # Delta values (3D/5D changes)
    delta_3d: Optional[Dict[str, Any]] = None
    delta_5d: Optional[Dict[str, Any]] = None
    
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Industry ETF ====================
class IndustryETFResponse(BaseModel):
    symbol: str
    name: str
    sector: str
    sectorName: str
    compositeScore: float
    relMomentum: RelMomentumData
    trendQuality: TrendQualityData
    breadth: BreadthData
    optionsConfirm: OptionsConfirmData
    holdings: List[HoldingResponse] = []
    
    # Delta values
    delta_3d: Optional[Dict[str, Any]] = None
    delta_5d: Optional[Dict[str, Any]] = None
    
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Momentum Stock ====================
class PriceMomentumData(BaseModel):
    score: float = 0
    return20d: str = "+0.0%"
    return20dEx3: str = "+0.0%"
    return63d: str = "+0.0%"
    relativeToSector: float = 1.0
    nearHighDist: str = "0%"
    breakoutTrigger: bool = False
    volumeSpike: float = 1.0


class TrendStructureData(BaseModel):
    score: float = 0
    maAlignment: str = "N/A"
    slope20d: str = "+0.00"
    continuity: str = "0%"
    above20maRatio: float = 0


class VolumePriceData(BaseModel):
    score: float = 0
    breakoutVolRatio: float = 1.0
    upDownVolRatio: float = 1.0
    obvTrend: str = "Neutral"


class QualityFilterData(BaseModel):
    score: float = 0
    maxDrawdown20d: str = "0%"
    atrPercent: float = 0
    distFrom20ma: str = "+0.0%"
    heatLevel: str = "Normal"


class OptionsOverlayData(BaseModel):
    score: float = 0
    heat: str = "Low"
    relVol: str = "1.0x"
    ivr: float = 0
    iv30: float = 0


class MomentumStockResponse(BaseModel):
    symbol: str
    name: str
    price: float
    sector: str
    industry: str
    finalScore: float
    priceMomentum: PriceMomentumData
    trendStructure: TrendStructureData
    volumePrice: VolumePriceData
    qualityFilter: QualityFilterData
    optionsOverlay: OptionsOverlayData
    
    # Delta values
    delta_3d: Optional[Dict[str, Any]] = None
    delta_5d: Optional[Dict[str, Any]] = None
    
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Market Regime ====================
class SPYData(BaseModel):
    price: float = 0
    vs200ma: str = "+0.0%"
    vs50ma: str = "+0.0%"
    trend: str = "neutral"


class MarketRegimeResponse(BaseModel):
    status: str = "B"  # A/B/C
    spy: SPYData
    vix: float = 0
    breadth: float = 0
    
    # Delta values
    delta_3d: Optional[Dict[str, Any]] = None
    delta_5d: Optional[Dict[str, Any]] = None
    
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Data Import ====================
class FinvizDataItem(BaseModel):
    Ticker: str
    Beta: Optional[float] = 0
    ATR: Optional[float] = 0
    SMA50: Optional[float] = 0
    SMA200: Optional[float] = 0
    High_52W: Optional[float] = Field(0, alias="52W_High")
    RSI: Optional[float] = 0
    Price: Optional[float] = 0
    Volume: Optional[int] = 0

    class Config:
        populate_by_name = True


class FinvizImportRequest(BaseModel):
    etf_symbol: str
    data: List[FinvizDataItem]
    data_date: Optional[date] = None


class MarketChameleonDataItem(BaseModel):
    symbol: str
    RelNotionalTo90D: Optional[float] = 0
    RelVolTo90D: Optional[float] = 0
    TradeCount: Optional[int] = 0
    IV30: Optional[float] = 0
    HV20: Optional[float] = 0
    IVR: Optional[float] = 0
    IV_52W_P: Optional[float] = 0
    IV30_Chg: Optional[float] = 0
    MultiLegPct: Optional[float] = 0
    ContingentPct: Optional[float] = 0
    PutPct: Optional[float] = 0
    CallVolume: Optional[int] = 0
    PutVolume: Optional[int] = 0


class MarketChameleonImportRequest(BaseModel):
    etf_symbol: Optional[str] = None
    data: List[MarketChameleonDataItem]
    data_date: Optional[date] = None


class ImportResponse(BaseModel):
    success: bool
    source: str
    etf_symbol: Optional[str]
    record_count: int
    message: str
    timestamp: datetime


class ImportLogResponse(BaseModel):
    id: int
    source: str
    etf_symbol: Optional[str]
    record_count: int
    status: str
    message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Calculation Request ====================
class RefreshRequest(BaseModel):
    symbol: str
    refresh_type: str = "full"  # 'full', 'price', 'options'


class CalculationResult(BaseModel):
    symbol: str
    success: bool
    message: str
    scores: Optional[Dict[str, float]] = None
    timestamp: datetime


# ==================== CLI Upload ====================
class CLIUploadRequest(BaseModel):
    data_date: date
    etf_type: str  # 'sector' or 'industry'
    sector_symbol: Optional[str] = None  # -s param for industry
    etf_symbol: str  # -a param


# ==================== Dashboard Summary ====================
class DashboardSummary(BaseModel):
    market_regime: MarketRegimeResponse
    top_sectors: List[Dict[str, Any]]
    top_industries: List[Dict[str, Any]]
    top_momentum_stocks: List[Dict[str, Any]]
    options_signals: Dict[str, Any]
    rs_indicators: Dict[str, Any]
    last_updated: datetime


# ==================== Symbol Pool ====================
class SymbolDataStatus(BaseModel):
    """单个数据源状态"""
    status: str = "pending"  # pending, ready, error
    last_update: Optional[datetime] = None


class SymbolPoolItem(BaseModel):
    """标的池中的单个标的"""
    ticker: str
    name: Optional[str] = None
    price: Optional[float] = None
    etfs: List[str] = []  # 所属ETF列表
    max_weight: float = 0  # 最大权重（用于排序）
    
    finviz: bool = False
    mc: bool = False  # MarketChameleon
    ibkr: bool = False
    futu: bool = False
    
    completeness: int = 0  # 完备度 0-100
    
    class Config:
        from_attributes = True


class SymbolPoolResponse(BaseModel):
    """标的池响应"""
    total_count: int
    symbols: List[SymbolPoolItem]
    last_update: Optional[datetime] = None


# ==================== ETF Refresh Config ====================
class ETFConfigItem(BaseModel):
    """ETF配置项"""
    symbol: str
    name: str
    type: str  # sector or industry
    total_holdings: int = 0
    top_n: int = 20
    frequency: str = "daily"  # daily, weekly, monthly
    status: str = "pending"  # pending, ready, updating, error
    last_refresh: Optional[datetime] = None


class ETFConfigUpdate(BaseModel):
    """ETF配置更新请求"""
    top_n: Optional[int] = None
    frequency: Optional[str] = None
    auto_refresh: Optional[bool] = None


class ETFConfigListResponse(BaseModel):
    """ETF配置列表响应"""
    sector_etfs: List[ETFConfigItem]
    industry_etfs: List[ETFConfigItem]
    unique_symbol_count: int  # 去重后的标的数量
    estimated_time: int  # 预计更新时间（秒）


# ==================== Data Source Status ====================
class DataSourceStatus(BaseModel):
    """数据源状态"""
    id: str
    name: str
    status: str  # ready, warning, error
    coverage: int  # 覆盖率 0-100
    last_update: Optional[str] = None


class DataSourcesStatusResponse(BaseModel):
    """所有数据源状态响应"""
    sources: List[DataSourceStatus]
    overall_completeness: int  # 整体完备度


# ==================== Unified Update ====================
class UpdateProgressResponse(BaseModel):
    """更新进度响应"""
    session_id: str
    status: str  # idle, fetching, validating, computing, complete, error
    phase: Optional[str] = None
    total: int = 0
    completed: int = 0
    failed: int = 0
    progress_percent: int = 0
    can_compute: bool = False
    message: Optional[str] = None


class UnifiedUpdateRequest(BaseModel):
    """统一更新请求"""
    etf_symbols: Optional[List[str]] = None  # 指定ETF，为空则更新全部
    force_refresh: bool = False  # 强制刷新已有数据


class ComputeRequest(BaseModel):
    """执行计算请求"""
    etf_symbols: Optional[List[str]] = None  # 指定ETF，为空则计算全部


class ComputeResponse(BaseModel):
    """计算结果响应"""
    success: bool
    message: str
    etfs_computed: int = 0
    stocks_computed: int = 0
    timestamp: datetime
