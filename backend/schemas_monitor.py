"""
Monitor Task Schemas - Pydantic models for request/response
监控任务的请求和响应模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ==================== Enums ====================

class TaskType(str, Enum):
    """任务类型"""
    CROSS_SECTOR = "cross_sector"  # 跨板块轮动
    SECTOR_DRILLDOWN = "sector_drilldown"  # 科技板块内下钻
    MOMENTUM_STOCK = "momentum_stock"  # 动能股追踪


class TaskStatus(str, Enum):
    """任务状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ETFLevel(str, Enum):
    """ETF 级别"""
    SECTOR = "sector"
    INDUSTRY = "industry"


class ImportType(str, Enum):
    """导入类型"""
    FINVIZ = "finviz"
    MARKET_CHAMELEON = "market_chameleon"
    IBKR = "ibkr"
    FUTU = "futu"


class InputMethod(str, Enum):
    """输入方式"""
    TEXT = "text"
    FILE = "file"


# ==================== ETF Config ====================

class ETFConfigBase(BaseModel):
    """ETF 配置基础模型"""
    etf_symbol: str = Field(..., description="ETF 代码")
    etf_name: Optional[str] = Field(None, description="ETF 名称")
    etf_level: ETFLevel = Field(..., description="ETF 级别: sector/industry")
    parent_etf_symbol: Optional[str] = Field(None, description="父级 ETF 代码（用于下钻关系）")


class ETFConfigCreate(ETFConfigBase):
    """创建 ETF 配置"""
    pass


class ETFConfigResponse(ETFConfigBase):
    """ETF 配置响应"""
    id: int
    task_id: int
    finviz_data_updated_at: Optional[datetime] = None
    mc_data_updated_at: Optional[datetime] = None
    market_data_updated_at: Optional[datetime] = None
    options_data_updated_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Task ====================

class TaskBase(BaseModel):
    """任务基础模型"""
    task_name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    task_type: TaskType = Field(..., description="任务类型")
    description: Optional[str] = Field(None, description="任务描述")
    benchmark_symbol: str = Field(default="SPY", description="基准指数")
    # 保留旧字段以向后兼容
    coverage_type: Optional[str] = Field(default="top15", description="覆盖范围类型（单选，向后兼容）")
    # 新增：支持多选
    coverage_types: Optional[List[str]] = Field(default=None, description="覆盖范围类型数组（多选）")
    is_auto_refresh: bool = Field(default=True, description="是否自动刷新")


class TaskCreate(TaskBase):
    """创建任务请求"""
    etf_configs: List[ETFConfigCreate] = Field(..., min_length=1, description="ETF 配置列表")


class TaskUpdate(BaseModel):
    """更新任务请求"""
    task_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    benchmark_symbol: Optional[str] = None
    coverage_type: Optional[str] = Field(None, description="覆盖范围类型（单选，向后兼容）")
    coverage_types: Optional[List[str]] = Field(None, description="覆盖范围类型数组（多选）")
    is_auto_refresh: Optional[bool] = None
    status: Optional[TaskStatus] = None


class CoverageUpdateRequest(BaseModel):
    """覆盖范围更新请求"""
    coverage_types: List[str] = Field(..., description="覆盖范围类型数组")


class TaskResponse(TaskBase):
    """任务响应"""
    id: int
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    last_refresh_at: Optional[datetime] = None
    etf_configs: List[ETFConfigResponse] = []
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int


# ==================== Data Import ====================

class FinvizDataItem(BaseModel):
    """Finviz 数据项"""
    Ticker: str
    Beta: Optional[float] = None
    ATR: Optional[float] = None
    SMA50: Optional[float] = None
    SMA200: Optional[float] = None
    High_52W: Optional[float] = Field(None, alias="52W_High")
    RSI: Optional[float] = None
    Price: Optional[float] = None
    Pirce: Optional[float] = None  # 兼容拼写错误
    
    class Config:
        populate_by_name = True


class MarketChameleonDataItem(BaseModel):
    """MarketChameleon 数据项"""
    symbol: str
    RelVolTo90D: Optional[str] = None
    CallVolume: Optional[str] = None
    PutVolume: Optional[str] = None
    PutPct: Optional[str] = None
    SingleLegPct: Optional[str] = None
    MultiLegPct: Optional[str] = None
    ContingentPct: Optional[str] = None
    RelNotionalTo90D: Optional[str] = None
    CallNotional: Optional[str] = None
    PutNotional: Optional[str] = None
    IV30ChgPct: Optional[str] = None
    IV30: Optional[str] = None
    HV20: Optional[str] = None
    HV1Y: Optional[str] = None
    IVR: Optional[str] = None
    IV_52W_P: Optional[str] = None
    Volume: Optional[str] = None
    OI_PctRank: Optional[str] = None
    Earnings: Optional[str] = None
    PriceChgPct: Optional[str] = None


class TextImportRequest(BaseModel):
    """文本导入请求"""
    task_id: int = Field(..., description="任务 ID")
    etf_symbol: str = Field(..., description="ETF 代码")
    import_type: ImportType = Field(..., description="导入类型")
    json_data: str = Field(..., description="JSON 数据字符串")


class FileImportRequest(BaseModel):
    """文件导入请求（用于 Form 数据）"""
    task_id: int
    etf_symbol: str
    import_type: ImportType


class ImportResponse(BaseModel):
    """导入响应"""
    success: bool
    task_id: int
    etf_symbol: str
    import_type: str
    record_count: int
    message: str
    warnings: List[str] = []
    timestamp: datetime


# ==================== Data Status ====================

class DataStatusResponse(BaseModel):
    """数据状态响应"""
    etf_symbol: str
    finviz_status: str  # 'ready' | 'pending' | 'error'
    finviz_record_count: int
    finviz_updated_at: Optional[datetime]
    mc_status: str
    mc_record_count: int
    mc_updated_at: Optional[datetime]
    market_data_status: str
    market_data_updated_at: Optional[datetime]
    options_data_status: str
    options_data_updated_at: Optional[datetime]


class TaskDataStatusResponse(BaseModel):
    """任务数据状态响应"""
    task_id: int
    task_name: str
    etf_statuses: List[DataStatusResponse]
    overall_completeness: float  # 0-100


# ==================== Score ====================

class ScoreResponse(BaseModel):
    """评分响应"""
    etf_symbol: str
    overall_score: Optional[float]
    trend_score: Optional[float]
    momentum_score: Optional[float]
    rs_score: Optional[float]
    options_score: Optional[float]
    rank_in_task: Optional[int]
    delta_3d: Optional[float]
    delta_5d: Optional[float]
    snapshot_date: date


class TaskScoreResponse(BaseModel):
    """任务评分响应"""
    task_id: int
    task_name: str
    snapshot_date: date
    scores: List[ScoreResponse]


# ==================== Import Log ====================

class ImportLogResponse(BaseModel):
    """导入日志响应"""
    id: int
    task_id: Optional[int]
    etf_symbol: Optional[str]
    import_type: str
    input_method: str
    file_name: Optional[str]
    record_count: Optional[int]
    status: str
    error_message: Optional[str]
    warnings: Optional[str]
    imported_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Refresh ====================

class RefreshRequest(BaseModel):
    """刷新请求"""
    task_id: int
    etf_symbols: Optional[List[str]] = None  # None 表示刷新所有
    data_types: Optional[List[str]] = None  # ['market', 'options'] 或 None 表示全部


class RefreshResponse(BaseModel):
    """刷新响应"""
    task_id: int
    refreshed_etfs: List[str]
    success_count: int
    failed_count: int
    errors: List[str] = []
    timestamp: datetime


# ==================== ETF Metadata ====================

class ETFMetadata(BaseModel):
    """ETF 元数据"""
    symbol: str
    name: str
    level: ETFLevel
    sector: Optional[str] = None  # 所属板块


# 预定义 ETF 配置
ETF_METADATA = {
    # 板块 ETF
    "XLK": ETFMetadata(symbol="XLK", name="科技板块", level=ETFLevel.SECTOR),
    "XLF": ETFMetadata(symbol="XLF", name="金融板块", level=ETFLevel.SECTOR),
    "XLV": ETFMetadata(symbol="XLV", name="医疗板块", level=ETFLevel.SECTOR),
    "XLE": ETFMetadata(symbol="XLE", name="能源板块", level=ETFLevel.SECTOR),
    "XLY": ETFMetadata(symbol="XLY", name="消费板块", level=ETFLevel.SECTOR),
    "XLI": ETFMetadata(symbol="XLI", name="工业板块", level=ETFLevel.SECTOR),
    "XLC": ETFMetadata(symbol="XLC", name="通信板块", level=ETFLevel.SECTOR),
    "XLP": ETFMetadata(symbol="XLP", name="必需消费品", level=ETFLevel.SECTOR),
    "XLU": ETFMetadata(symbol="XLU", name="公用事业", level=ETFLevel.SECTOR),
    "XLRE": ETFMetadata(symbol="XLRE", name="房地产", level=ETFLevel.SECTOR),
    "XLB": ETFMetadata(symbol="XLB", name="材料板块", level=ETFLevel.SECTOR),
    
    # 行业 ETF - 科技
    "SOXX": ETFMetadata(symbol="SOXX", name="半导体", level=ETFLevel.INDUSTRY, sector="XLK"),
    "SMH": ETFMetadata(symbol="SMH", name="半导体VanEck", level=ETFLevel.INDUSTRY, sector="XLK"),
    "IGV": ETFMetadata(symbol="IGV", name="软件", level=ETFLevel.INDUSTRY, sector="XLK"),
    "SKYY": ETFMetadata(symbol="SKYY", name="云计算", level=ETFLevel.INDUSTRY, sector="XLK"),
    
    # 行业 ETF - 金融
    "KBE": ETFMetadata(symbol="KBE", name="银行", level=ETFLevel.INDUSTRY, sector="XLF"),
    "KRE": ETFMetadata(symbol="KRE", name="区域银行", level=ETFLevel.INDUSTRY, sector="XLF"),
    "IAI": ETFMetadata(symbol="IAI", name="券商", level=ETFLevel.INDUSTRY, sector="XLF"),
    
    # 行业 ETF - 医疗
    "IBB": ETFMetadata(symbol="IBB", name="生物科技", level=ETFLevel.INDUSTRY, sector="XLV"),
    "XBI": ETFMetadata(symbol="XBI", name="生物科技SPDR", level=ETFLevel.INDUSTRY, sector="XLV"),
    "IHI": ETFMetadata(symbol="IHI", name="医疗设备", level=ETFLevel.INDUSTRY, sector="XLV"),
    
    # 行业 ETF - 能源
    "XOP": ETFMetadata(symbol="XOP", name="油气开采", level=ETFLevel.INDUSTRY, sector="XLE"),
    "OIH": ETFMetadata(symbol="OIH", name="油气服务", level=ETFLevel.INDUSTRY, sector="XLE"),
    "AMLP": ETFMetadata(symbol="AMLP", name="MLP", level=ETFLevel.INDUSTRY, sector="XLE"),
    
    # 行业 ETF - 消费
    "XRT": ETFMetadata(symbol="XRT", name="零售", level=ETFLevel.INDUSTRY, sector="XLY"),
    "XHB": ETFMetadata(symbol="XHB", name="住宅建筑", level=ETFLevel.INDUSTRY, sector="XLY"),
    "IBUY": ETFMetadata(symbol="IBUY", name="在线零售", level=ETFLevel.INDUSTRY, sector="XLY"),
    
    # 行业 ETF - 工业
    "ITA": ETFMetadata(symbol="ITA", name="航空航天", level=ETFLevel.INDUSTRY, sector="XLI"),
    "XAR": ETFMetadata(symbol="XAR", name="航空航天SPDR", level=ETFLevel.INDUSTRY, sector="XLI"),
    "JETS": ETFMetadata(symbol="JETS", name="航空", level=ETFLevel.INDUSTRY, sector="XLI"),
}


def get_etf_metadata(symbol: str) -> Optional[ETFMetadata]:
    """获取 ETF 元数据"""
    return ETF_METADATA.get(symbol.upper())


def get_sector_etfs() -> List[ETFMetadata]:
    """获取所有板块 ETF"""
    return [m for m in ETF_METADATA.values() if m.level == ETFLevel.SECTOR]


def get_industry_etfs(sector_symbol: Optional[str] = None) -> List[ETFMetadata]:
    """获取行业 ETF，可选按板块筛选"""
    etfs = [m for m in ETF_METADATA.values() if m.level == ETFLevel.INDUSTRY]
    if sector_symbol:
        etfs = [m for m in etfs if m.sector == sector_symbol.upper()]
    return etfs
