"""
SQLAlchemy Models for Trend Analysis System
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class SectorETF(Base):
    """板块 ETF"""
    __tablename__ = "sector_etfs"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100))
    
    # 综合评分
    composite_score = Column(Float, default=0)
    
    # 模块1: 相对动量
    rel_momentum_score = Column(Float, default=0)
    rel_momentum_value = Column(String(20))
    rel_momentum_rank = Column(Integer)
    rs_5d = Column(Float)
    rs_20d = Column(Float)
    rs_63d = Column(Float)
    
    # 模块2: 趋势质量
    trend_quality_score = Column(Float, default=0)
    trend_structure = Column(String(20))
    trend_slope = Column(String(20))
    price_vs_50dma = Column(Float)
    ma20_vs_50dma = Column(Float)
    ma20_slope = Column(Float)
    max_drawdown_20d = Column(Float)
    
    # 模块3: 广度/参与度
    breadth_score = Column(Float, default=0)
    pct_above_50ma = Column(String(10))
    pct_above_200ma = Column(String(10))
    new_high_count = Column(Integer)
    new_high_pct = Column(Float)
    
    # 模块4: 期权确认
    options_score = Column(Float, default=0)
    options_heat = Column(String(20))
    rel_vol = Column(String(10))
    ivr = Column(Float)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    holdings = relationship("ETFHolding", back_populates="sector_etf", cascade="all, delete-orphan")
    industry_etfs = relationship("IndustryETF", back_populates="sector_etf")


class IndustryETF(Base):
    """行业 ETF"""
    __tablename__ = "industry_etfs"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100))
    sector_symbol = Column(String(10), ForeignKey("sector_etfs.symbol"))
    
    # 综合评分
    composite_score = Column(Float, default=0)
    
    # 模块1: 相对动量
    rel_momentum_score = Column(Float, default=0)
    rel_momentum_value = Column(String(20))
    rel_momentum_rank = Column(Integer)
    rs_5d = Column(Float)
    rs_20d = Column(Float)
    rs_63d = Column(Float)
    
    # 模块2: 趋势质量
    trend_quality_score = Column(Float, default=0)
    trend_structure = Column(String(20))
    trend_slope = Column(String(20))
    price_vs_50dma = Column(Float)
    ma20_vs_50dma = Column(Float)
    ma20_slope = Column(Float)
    max_drawdown_20d = Column(Float)
    
    # 模块3: 广度/参与度
    breadth_score = Column(Float, default=0)
    pct_above_50ma = Column(String(10))
    pct_above_200ma = Column(String(10))
    new_high_count = Column(Integer)
    new_high_pct = Column(Float)
    
    # 模块4: 期权确认
    options_score = Column(Float, default=0)
    options_heat = Column(String(20))
    rel_vol = Column(String(10))
    ivr = Column(Float)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    sector_etf = relationship("SectorETF", back_populates="industry_etfs")
    holdings = relationship("ETFHolding", back_populates="industry_etf", cascade="all, delete-orphan")


class ETFHolding(Base):
    """ETF 持仓"""
    __tablename__ = "etf_holdings"
    
    id = Column(Integer, primary_key=True, index=True)
    etf_type = Column(String(10), nullable=False)  # 'sector' or 'industry'
    etf_symbol = Column(String(10), nullable=False, index=True)
    sector_etf_symbol = Column(String(10), ForeignKey("sector_etfs.symbol"), nullable=True)
    industry_etf_symbol = Column(String(10), ForeignKey("industry_etfs.symbol"), nullable=True)
    
    ticker = Column(String(10), nullable=False)
    weight = Column(Float, nullable=False)
    
    # 时间戳
    data_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    sector_etf = relationship("SectorETF", back_populates="holdings")
    industry_etf = relationship("IndustryETF", back_populates="holdings")


class MomentumStock(Base):
    """动能股"""
    __tablename__ = "momentum_stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    name = Column(String(100))
    price = Column(Float)
    sector = Column(String(10))
    industry = Column(String(10))
    
    # 综合得分
    final_score = Column(Float, default=0)
    
    # 模块1: 价格动能
    price_momentum_score = Column(Float, default=0)
    return_20d = Column(String(20))
    return_20d_ex3 = Column(String(20))
    return_63d = Column(String(20))
    relative_to_sector = Column(Float)
    near_high_dist = Column(String(10))
    breakout_trigger = Column(Boolean, default=False)
    volume_spike = Column(Float)
    
    # 模块2: 趋势结构
    trend_structure_score = Column(Float, default=0)
    ma_alignment = Column(String(30))
    slope_20d = Column(String(10))
    continuity = Column(String(10))
    above_20ma_ratio = Column(Float)
    
    # 模块3: 量价确认
    volume_price_score = Column(Float, default=0)
    breakout_vol_ratio = Column(Float)
    up_down_vol_ratio = Column(Float)
    obv_trend = Column(String(20))
    
    # 模块4: 动能质量过滤
    quality_filter_score = Column(Float, default=0)
    max_drawdown_20d = Column(String(10))
    atr_percent = Column(Float)
    dist_from_20ma = Column(String(10))
    heat_level = Column(String(20))
    
    # 期权覆盖
    options_overlay_score = Column(Float, default=0)
    options_heat = Column(String(20))
    options_rel_vol = Column(String(10))
    options_ivr = Column(Float)
    options_iv30 = Column(Float)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketRegime(Base):
    """市场环境"""
    __tablename__ = "market_regime"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)
    
    # Regime 状态
    status = Column(String(1), default='B')  # A/B/C
    
    # SPY 数据
    spy_price = Column(Float)
    spy_vs_200ma = Column(String(20))
    spy_vs_50ma = Column(String(20))
    spy_trend = Column(String(20))
    
    # VIX
    vix = Column(Float)
    
    # 市场广度
    breadth = Column(Float)
    pct_above_50ma = Column(Float)
    pct_above_200ma = Column(Float)
    
    # 均线数据
    spy_20ma = Column(Float)
    spy_50ma = Column(Float)
    spy_200ma = Column(Float)
    spy_20ma_slope = Column(Float)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FinvizData(Base):
    """Finviz 导入数据"""
    __tablename__ = "finviz_data"
    
    id = Column(Integer, primary_key=True, index=True)
    etf_symbol = Column(String(10), index=True, nullable=False)
    ticker = Column(String(10), nullable=False)
    
    beta = Column(Float)
    atr = Column(Float)
    sma50 = Column(Float)
    sma200 = Column(Float)
    high_52w = Column(Float)
    rsi = Column(Float)
    price = Column(Float)
    volume = Column(Integer)
    
    data_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketChameleonData(Base):
    """MarketChameleon 导入数据"""
    __tablename__ = "marketchameleon_data"
    
    id = Column(Integer, primary_key=True, index=True)
    etf_symbol = Column(String(10), index=True)
    symbol = Column(String(10), index=True, nullable=False)
    
    # 热度指标
    rel_notional_to_90d = Column(Float)
    rel_vol_to_90d = Column(Float)
    trade_count = Column(Integer)
    
    # 波动率指标
    iv30 = Column(Float)
    hv20 = Column(Float)
    ivr = Column(Float)
    iv_52w_p = Column(Float)
    iv30_chg = Column(Float)
    
    # 结构指标
    multi_leg_pct = Column(Float)
    contingent_pct = Column(Float)
    put_pct = Column(Float)
    
    # 成交量
    call_volume = Column(Integer)
    put_volume = Column(Integer)
    
    data_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FutuOptionsData(Base):
    """富途期权数据"""
    __tablename__ = "futu_options_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    
    # Positioning Score
    delta_oi_0_7_call = Column(Float)
    delta_oi_0_7_put = Column(Float)
    delta_oi_8_30_call = Column(Float)
    delta_oi_8_30_put = Column(Float)
    delta_oi_31_90_call = Column(Float)
    delta_oi_31_90_put = Column(Float)
    
    # Term Structure
    iv30 = Column(Float)
    iv60 = Column(Float)
    iv90 = Column(Float)
    slope = Column(Float)  # IV30 - IV90
    delta_slope = Column(Float)
    
    data_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class HistoricalData(Base):
    """历史数据用于计算3D/5D变化"""
    __tablename__ = "historical_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    data_type = Column(String(30), nullable=False)  # 'etf', 'stock', 'market'
    
    # 所有可能的指标（JSON存储）
    metrics = Column(JSON)
    
    data_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ImportLog(Base):
    """导入记录"""
    __tablename__ = "import_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(30), nullable=False)  # 'finviz', 'marketchameleon', 'xlsx'
    etf_symbol = Column(String(10))
    record_count = Column(Integer)
    status = Column(String(20), default='success')  # 'success', 'failed', 'partial'
    message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DataSourceConfig(Base):
    """数据源配置"""
    __tablename__ = "data_source_config"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(30), unique=True, nullable=False)  # 'ibkr', 'futu'
    
    host = Column(String(100))
    port = Column(Integer)
    client_id = Column(String(50))
    account_id = Column(String(50))
    api_key = Column(String(200))
    api_secret = Column(String(200))
    
    is_connected = Column(Boolean, default=False)
    last_connected_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SymbolPool(Base):
    """标的池 - 去重后的唯一数据源"""
    __tablename__ = "symbol_pool"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100))
    price = Column(Float)
    
    # 数据源状态
    finviz_status = Column(String(20), default='pending')  # pending, ready, error
    finviz_last_update = Column(DateTime)
    mc_status = Column(String(20), default='pending')
    mc_last_update = Column(DateTime)
    ibkr_status = Column(String(20), default='pending')
    ibkr_last_update = Column(DateTime)
    futu_status = Column(String(20), default='pending')
    futu_last_update = Column(DateTime)
    
    # 综合完备度 (0-100)
    completeness = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SymbolETFMapping(Base):
    """标的与ETF的映射关系（多对多）"""
    __tablename__ = "symbol_etf_mapping"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), index=True, nullable=False)
    etf_symbol = Column(String(10), index=True, nullable=False)
    etf_type = Column(String(10), nullable=False)  # 'sector' or 'industry'
    weight = Column(Float, nullable=False)
    rank = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class ETFRefreshConfig(Base):
    """ETF更新策略配置"""
    __tablename__ = "etf_refresh_config"
    
    id = Column(Integer, primary_key=True, index=True)
    etf_symbol = Column(String(10), unique=True, index=True, nullable=False)
    etf_type = Column(String(10), nullable=False)  # 'sector' or 'industry'
    etf_name = Column(String(100))
    
    total_holdings = Column(Integer, default=0)
    top_n = Column(Integer, default=20)  # 更新前N个标的
    frequency = Column(String(20), default='daily')  # daily, weekly, monthly
    auto_refresh = Column(Boolean, default=False)
    
    status = Column(String(20), default='pending')  # pending, ready, updating, error
    last_refresh = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UpdateSession(Base):
    """更新会话记录"""
    __tablename__ = "update_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), unique=True, index=True, nullable=False)
    
    status = Column(String(20), default='idle')  # idle, fetching, validating, computing, complete, error
    phase = Column(String(50))
    
    total_symbols = Column(Integer, default=0)
    completed_symbols = Column(Integer, default=0)
    failed_symbols = Column(Integer, default=0)
    
    can_compute = Column(Boolean, default=False)
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
