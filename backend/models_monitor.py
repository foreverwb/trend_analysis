"""
Monitor Task Models - 监控任务相关数据模型
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Date, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class MonitorTask(Base):
    """监控任务主表"""
    __tablename__ = "monitor_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)  # 'cross_sector' | 'sector_drilldown' | 'momentum_stock'
    description = Column(Text)
    
    # 配置
    benchmark_symbol = Column(String(20), default='SPY')
    top_n_coverage = Column(Integer, default=15)
    
    # 状态
    status = Column(String(20), default='draft')  # 'draft' | 'active' | 'paused' | 'archived'
    is_auto_refresh = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_refresh_at = Column(DateTime)
    
    # 关联
    etf_configs = relationship("TaskETFConfig", back_populates="task", cascade="all, delete-orphan")
    finviz_data = relationship("ETFFinvizData", back_populates="task", cascade="all, delete-orphan")
    mc_data = relationship("ETFMCData", back_populates="task", cascade="all, delete-orphan")
    market_data = relationship("ETFMarketData", back_populates="task", cascade="all, delete-orphan")
    options_data = relationship("ETFOptionsData", back_populates="task", cascade="all, delete-orphan")
    score_snapshots = relationship("TaskScoreSnapshot", back_populates="task", cascade="all, delete-orphan")
    import_logs = relationship("DataImportLog", back_populates="task", cascade="all, delete-orphan")


class TaskETFConfig(Base):
    """任务 ETF 配置表"""
    __tablename__ = "task_etf_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    
    # ETF 信息
    etf_symbol = Column(String(20), nullable=False)
    etf_name = Column(String(100))
    etf_level = Column(String(20), nullable=False)  # 'sector' | 'industry'
    parent_etf_symbol = Column(String(20))  # 用于下钻关系
    
    # 数据状态
    finviz_data_updated_at = Column(DateTime)
    mc_data_updated_at = Column(DateTime)
    market_data_updated_at = Column(DateTime)
    options_data_updated_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="etf_configs")


class ETFFinvizData(Base):
    """Finviz 导入数据表"""
    __tablename__ = "etf_finviz_data"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20), nullable=False)
    
    # Finviz 原始字段
    ticker = Column(String(20), nullable=False)
    beta = Column(DECIMAL(10, 4))
    atr = Column(DECIMAL(10, 4))
    sma50 = Column(DECIMAL(10, 4))
    sma200 = Column(DECIMAL(10, 4))
    week52_high = Column(DECIMAL(10, 4))
    rsi = Column(DECIMAL(10, 4))
    price = Column(DECIMAL(10, 4))
    
    # 元数据
    import_source = Column(String(20), default='finviz')
    imported_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="finviz_data")


class ETFMCData(Base):
    """MarketChameleon 导入数据表"""
    __tablename__ = "etf_mc_data"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20), nullable=False)
    
    # MarketChameleon 原始字段
    symbol = Column(String(20), nullable=False)
    rel_vol_to_90d = Column(DECIMAL(10, 4))
    call_volume = Column(Integer)
    put_volume = Column(Integer)
    put_pct = Column(DECIMAL(10, 4))
    single_leg_pct = Column(DECIMAL(10, 4))
    multi_leg_pct = Column(DECIMAL(10, 4))
    contingent_pct = Column(DECIMAL(10, 4))
    rel_notional_to_90d = Column(DECIMAL(10, 4))
    call_notional = Column(DECIMAL(20, 4))
    put_notional = Column(DECIMAL(20, 4))
    iv30_chg_pct = Column(DECIMAL(10, 4))
    iv30 = Column(DECIMAL(10, 4))
    hv20 = Column(DECIMAL(10, 4))
    hv1y = Column(DECIMAL(10, 4))
    ivr = Column(DECIMAL(10, 4))
    iv_52w_p = Column(DECIMAL(10, 4))
    volume = Column(Integer)
    oi_pct_rank = Column(DECIMAL(10, 4))
    earnings = Column(String(50))
    price_chg_pct = Column(DECIMAL(10, 4))
    
    # 元数据
    import_source = Column(String(20), default='market_chameleon')
    imported_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="mc_data")


class ETFMarketData(Base):
    """ETF 自身市场数据表"""
    __tablename__ = "etf_market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20), nullable=False)
    
    # 价格数据
    price = Column(DECIMAL(10, 4))
    price_change = Column(DECIMAL(10, 4))
    price_change_pct = Column(DECIMAL(10, 4))
    volume = Column(Integer)
    
    # 技术指标
    sma20 = Column(DECIMAL(10, 4))
    sma50 = Column(DECIMAL(10, 4))
    sma200 = Column(DECIMAL(10, 4))
    rsi = Column(DECIMAL(10, 4))
    atr = Column(DECIMAL(10, 4))
    
    # 相对强度
    rs_vs_spy = Column(DECIMAL(10, 4))
    
    # 元数据
    data_source = Column(String(20))  # 'ibkr' | 'futu'
    trade_date = Column(Date, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="market_data")


class ETFOptionsData(Base):
    """ETF 自身期权数据表"""
    __tablename__ = "etf_options_data"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20), nullable=False)
    
    # 期权数据
    iv30 = Column(DECIMAL(10, 4))
    iv30_chg = Column(DECIMAL(10, 4))
    hv20 = Column(DECIMAL(10, 4))
    ivr = Column(DECIMAL(10, 4))
    put_call_ratio = Column(DECIMAL(10, 4))
    total_oi = Column(Integer)
    call_oi = Column(Integer)
    put_oi = Column(Integer)
    
    # 元数据
    data_source = Column(String(20), default='market_chameleon')
    trade_date = Column(Date, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="options_data")


class TaskScoreSnapshot(Base):
    """评分快照表"""
    __tablename__ = "task_score_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20), nullable=False)
    
    # 评分
    overall_score = Column(DECIMAL(10, 4))
    trend_score = Column(DECIMAL(10, 4))
    momentum_score = Column(DECIMAL(10, 4))
    rs_score = Column(DECIMAL(10, 4))
    options_score = Column(DECIMAL(10, 4))
    
    # 排名
    rank_in_task = Column(Integer)
    
    # Delta 计算值（后端自动填充）
    delta_3d = Column(DECIMAL(10, 4))
    delta_5d = Column(DECIMAL(10, 4))
    
    # 元数据
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="score_snapshots")


class DataImportLog(Base):
    """数据导入日志表"""
    __tablename__ = "data_import_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"))
    etf_symbol = Column(String(20))
    
    # 导入信息
    import_type = Column(String(20), nullable=False)  # 'finviz' | 'market_chameleon' | 'ibkr' | 'futu'
    input_method = Column(String(20), nullable=False)  # 'text' | 'file'
    file_name = Column(String(255))
    record_count = Column(Integer)
    
    # 状态
    status = Column(String(20), default='success')  # 'success' | 'partial' | 'failed'
    error_message = Column(Text)
    warnings = Column(Text)
    
    # 时间戳
    imported_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    task = relationship("MonitorTask", back_populates="import_logs")


class SchedulerJobLog(Base):
    """调度任务执行日志表"""
    __tablename__ = "scheduler_job_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), nullable=False)
    job_name = Column(String(100))
    
    # 执行信息
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    status = Column(String(20))  # 'running' | 'success' | 'failed'
    
    # 结果
    tasks_processed = Column(Integer)
    etfs_refreshed = Column(Integer)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
