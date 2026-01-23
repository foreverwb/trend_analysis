/**
 * 数据层级视图组件
 * 展示 Level 0 (市场状态) -> Level 1 (板块) -> Level 2 (行业) 的层级结构
 */
import React, { useState, useEffect, useCallback } from 'react';
import { 
  TrendingUp, Layers, Database, RefreshCw,
  ChevronDown, ChevronUp, CheckCircle, XCircle, Clock,
  AlertCircle, Zap, ArrowRight, Target, Shield
} from 'lucide-react';
import * as api from '../utils/api';
import DataTriggerPanel from './DataTriggerPanel';

// 数据完备度计算
const calculateCompleteness = (dataStatus) => {
  if (!dataStatus) return 0;
  const sources = ['finviz', 'mc', 'ibkr', 'futu'];
  const complete = sources.filter(s => dataStatus[s] === 'complete').length;
  return Math.round((complete / sources.length) * 100);
};

/**
 * 平台 Logo SVG 组件
 */
const PlatformLogos = {
  // Finviz Logo - 绿色主题
  finviz: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.15"/>
      <path d="M7 8h10M7 12h7M7 16h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  // MarketChameleon Logo - 紫色主题
  mc: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.15"/>
      <circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" strokeWidth="2"/>
      <path d="M12 9v6M9 12h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  // IBKR Logo - 红色主题 (Interactive Brokers 风格)
  ibkr: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.15"/>
      <path d="M8 7v10M8 12h8M16 7v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  // Futu Logo - 橙色主题 (富途风格)
  futu: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.15"/>
      <path d="M7 8h10M7 12h10M7 16h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="16" cy="16" r="2" fill="currentColor"/>
    </svg>
  )
};

/**
 * 数据完备度环形图
 */
const CompletenessRing = ({ percentage, size = 48 }) => {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  let color = '#EF4444'; // red
  if (percentage >= 75) color = '#10B981'; // green
  else if (percentage >= 50) color = '#F59E0B'; // yellow
  
  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="#E5E7EB"
        strokeWidth="4"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        className="transition-all duration-500"
      />
      <text 
        x={size / 2} 
        y={size / 2} 
        textAnchor="middle" 
        dominantBaseline="central"
        className="transform rotate-90 origin-center text-xs font-bold fill-slate-700"
        style={{ transform: 'rotate(90deg)', transformOrigin: 'center' }}
      >
        {percentage}%
      </text>
    </svg>
  );
};

/**
 * 单个数据源 Logo 指示器
 */
const DataSourceLogo = ({ source, status }) => {
  const Logo = PlatformLogos[source];
  if (!Logo) return null;
  
  const isComplete = status === 'complete';
  const isPartial = status === 'partial';
  
  // 颜色配置
  const colorConfig = {
    finviz: { complete: 'text-green-600', partial: 'text-green-400', missing: 'text-slate-300' },
    mc: { complete: 'text-purple-600', partial: 'text-purple-400', missing: 'text-slate-300' },
    ibkr: { complete: 'text-red-600', partial: 'text-red-400', missing: 'text-slate-300' },
    futu: { complete: 'text-orange-600', partial: 'text-orange-400', missing: 'text-slate-300' }
  };
  
  const bgConfig = {
    finviz: { complete: 'bg-green-50 border-green-200', partial: 'bg-green-50/50 border-green-100', missing: 'bg-slate-50 border-slate-200' },
    mc: { complete: 'bg-purple-50 border-purple-200', partial: 'bg-purple-50/50 border-purple-100', missing: 'bg-slate-50 border-slate-200' },
    ibkr: { complete: 'bg-red-50 border-red-200', partial: 'bg-red-50/50 border-red-100', missing: 'bg-slate-50 border-slate-200' },
    futu: { complete: 'bg-orange-50 border-orange-200', partial: 'bg-orange-50/50 border-orange-100', missing: 'bg-slate-50 border-slate-200' }
  };
  
  const labels = {
    finviz: 'Finviz',
    mc: 'MarketChameleon',
    ibkr: 'Interactive Brokers',
    futu: 'Futu 富途'
  };
  
  const statusKey = isComplete ? 'complete' : isPartial ? 'partial' : 'missing';
  const colorClass = colorConfig[source]?.[statusKey] || 'text-slate-300';
  const bgClass = bgConfig[source]?.[statusKey] || 'bg-slate-50 border-slate-200';
  
  return (
    <div 
      className={`w-8 h-8 rounded-lg border flex items-center justify-center transition-all ${bgClass} ${
        isComplete ? 'shadow-sm' : ''
      }`}
      title={`${labels[source]}: ${isComplete ? '完整' : isPartial ? '部分' : '缺失'}`}
    >
      <Logo size={18} className={colorClass} />
    </div>
  );
};

/**
 * 四源数据状态指示器（Logo 版本）
 */
const DataSourceIndicator = ({ dataStatus, compact = false }) => {
  const sources = ['finviz', 'mc', 'ibkr', 'futu'];
  
  return (
    <div className="flex gap-1">
      {sources.map(source => (
        <DataSourceLogo 
          key={source} 
          source={source} 
          status={dataStatus?.[source] || 'missing'} 
        />
      ))}
    </div>
  );
};

/**
 * ETF 卡片组件
 */
const ETFCard = ({ item, level, onDrillDown, onFetchData, isExpanded, children }) => {
  const completeness = calculateCompleteness(item.data_status);
  
  return (
    <div className={`bg-white rounded-xl border ${
      isExpanded ? 'border-blue-300 shadow-md' : 'border-slate-200'
    } overflow-hidden transition-all`}>
      <div className="p-4">
        <div className="flex items-center justify-between">
          {/* 左侧信息 */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <CompletenessRing percentage={completeness} size={40} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-800">{item.symbol}</span>
                {item.is_anchor && (
                  <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                    行业锚
                  </span>
                )}
                {item.is_attack && (
                  <span className="px-1.5 py-0.5 bg-pink-100 text-pink-700 rounded text-xs font-medium">
                    进攻锚
                  </span>
                )}
              </div>
              <span className="text-sm text-slate-500">{item.name}</span>
            </div>
          </div>
          
          {/* 右侧状态和操作 */}
          <div className="flex items-center gap-3">
            {/* ETF自身数据状态 */}
            <div className="text-right">
              <div className="text-xs text-slate-500 mb-1">ETF 自身</div>
              <DataSourceIndicator dataStatus={item.etf_self_status} compact />
            </div>
            
            {/* 持仓数据状态 */}
            <div className="text-right">
              <div className="text-xs text-slate-500 mb-1">持仓 Top {item.top_n || 20}</div>
              <DataSourceIndicator dataStatus={item.holdings_status} compact />
            </div>
            
            {/* 操作按钮 */}
            <div className="flex gap-2">
              {!item.can_calculate && (
                <button 
                  onClick={() => onFetchData(item.symbol)}
                  className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-200 transition-colors"
                >
                  获取数据
                </button>
              )}
              {item.can_calculate && (
                <span className="px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium">
                  ✓ 可计算
                </span>
              )}
              {level < 2 && item.industries && item.industries.length > 0 && (
                <button 
                  onClick={() => onDrillDown(item.symbol)}
                  className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-200 transition-colors flex items-center gap-1"
                >
                  {isExpanded ? (
                    <>收起 <ChevronUp className="w-3 h-3" /></>
                  ) : (
                    <>下钻 <ChevronDown className="w-3 h-3" /></>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* 展开的子内容 */}
      {isExpanded && children && (
        <div className="border-t border-slate-100 bg-slate-50 p-4">
          {children}
        </div>
      )}
    </div>
  );
};

/**
 * 双锚判定显示
 */
const DualAnchorIndicator = ({ industryAnchor, attackAnchor }) => {
  if (!industryAnchor && !attackAnchor) return null;
  
  const getJudgment = () => {
    const indComplete = calculateCompleteness(industryAnchor?.data_status) >= 75;
    const atkComplete = calculateCompleteness(attackAnchor?.data_status) >= 75;
    
    if (indComplete && atkComplete) {
      return { text: '双锚完备，可执行评分计算', icon: '🚀', className: 'bg-emerald-50 border-emerald-200 text-emerald-700' };
    } else if (indComplete && !atkComplete) {
      return { text: '行业锚完备，进攻锚待补充', icon: '📊', className: 'bg-blue-50 border-blue-200 text-blue-700' };
    } else if (!indComplete && atkComplete) {
      return { text: '进攻锚完备，行业锚待补充', icon: '🎯', className: 'bg-amber-50 border-amber-200 text-amber-700' };
    } else {
      return { text: '双锚数据均待补充', icon: '⏳', className: 'bg-slate-50 border-slate-200 text-slate-600' };
    }
  };
  
  const judgment = getJudgment();
  
  return (
    <div className={`p-3 rounded-lg border ${judgment.className} mb-3`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">{judgment.icon}</span>
          <div>
            <div className="text-sm font-medium">双锚判定</div>
            <div className="text-xs opacity-80">{judgment.text}</div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <Shield className="w-4 h-4" />
            <span>行业锚: {industryAnchor?.symbol || '-'}</span>
          </div>
          <div className="flex items-center gap-1">
            <Target className="w-4 h-4" />
            <span>进攻锚: {attackAnchor?.symbol || '-'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * 数据层级视图主组件
 */
const DataLayerView = () => {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSectors, setExpandedSectors] = useState(new Set());
  const [showTriggerPanel, setShowTriggerPanel] = useState(null);

  // 加载数据概览
  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDataOverview();
      if (res.data) {
        setOverview(res.data);
      }
    } catch (err) {
      console.error('加载数据层级失败:', err);
      setError(err.response?.data?.detail || err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    loadOverview();
  }, [loadOverview]);
  
  // 展开/收起板块
  const toggleSector = (sectorSymbol) => {
    setExpandedSectors(prev => {
      const next = new Set(prev);
      if (next.has(sectorSymbol)) {
        next.delete(sectorSymbol);
      } else {
        next.add(sectorSymbol);
      }
      return next;
    });
  };
  
  // 打开数据获取面板
  const openFetchPanel = (etfSymbol, dataType = 'holdings') => {
    setShowTriggerPanel({ etfSymbol, dataType });
  };
  
  // 关闭面板并刷新
  const closeFetchPanel = () => {
    setShowTriggerPanel(null);
    loadOverview();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
        <span className="ml-3 text-slate-600">加载数据层级...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertCircle className="w-12 h-12 text-red-400 mb-3" />
        <p className="text-slate-600 mb-4">{error}</p>
        <button 
          onClick={loadOverview}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 弹出面板 */}
      {showTriggerPanel && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="max-w-lg w-full">
            <DataTriggerPanel
              etfSymbol={showTriggerPanel.etfSymbol}
              dataType={showTriggerPanel.dataType}
              onClose={closeFetchPanel}
              onUpdateComplete={closeFetchPanel}
            />
          </div>
        </div>
      )}
      
      {/* Level 0: 市场状态锚 */}
      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-4">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-6 h-6 text-white" />
            <div>
              <h2 className="text-white font-bold">Level 0: 市场状态锚</h2>
              <p className="text-white/70 text-sm">Risk-On/Off 判断基准 (必须 100% 完备)</p>
            </div>
          </div>
        </div>
        <div className="p-4 space-y-3">
          {overview?.level_0?.map(item => (
            <ETFCard
              key={item.symbol}
              item={item}
              level={0}
              onFetchData={() => openFetchPanel(item.symbol, 'etf')}
            />
          ))}
          {(!overview?.level_0 || overview.level_0.length === 0) && (
            <div className="text-center py-8 text-slate-500">
              <Database className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>暂无市场锚数据</p>
            </div>
          )}
        </div>
      </section>
      
      {/* Level 1: 板块 ETF */}
      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-gradient-to-r from-blue-500 to-indigo-500 px-5 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Layers className="w-6 h-6 text-white" />
              <div>
                <h2 className="text-white font-bold">Level 1: 板块 ETF</h2>
                <p className="text-white/70 text-sm">11 个 GICS 板块轮动</p>
              </div>
            </div>
            <span className="px-3 py-1 bg-white/20 rounded-full text-white text-sm">
              {overview?.level_1?.length || 0} / 11 已配置
            </span>
          </div>
        </div>
        <div className="p-4 space-y-3">
          {overview?.level_1?.map(item => (
            <ETFCard
              key={item.symbol}
              item={item}
              level={1}
              isExpanded={expandedSectors.has(item.symbol)}
              onDrillDown={toggleSector}
              onFetchData={() => openFetchPanel(item.symbol, 'holdings')}
            >
              {/* Level 2: 行业 ETF */}
              {overview?.level_2?.[item.symbol] && (
                <div className="space-y-3">
                  <DualAnchorIndicator
                    industryAnchor={overview.level_2[item.symbol]?.find(i => i.is_anchor)}
                    attackAnchor={overview.level_2[item.symbol]?.find(i => i.is_attack)}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {overview.level_2[item.symbol].map(industry => (
                      <ETFCard
                        key={industry.symbol}
                        item={industry}
                        level={2}
                        onFetchData={() => openFetchPanel(industry.symbol, 'holdings')}
                      />
                    ))}
                  </div>
                </div>
              )}
            </ETFCard>
          ))}
          {(!overview?.level_1 || overview.level_1.length === 0) && (
            <div className="text-center py-10 text-slate-500">
              <div className="w-16 h-16 mx-auto mb-4 bg-slate-100 rounded-2xl flex items-center justify-center">
                <Layers className="w-8 h-8 text-slate-400" />
              </div>
              <p className="font-medium text-slate-600 mb-1">暂无板块 ETF 数据</p>
              <p className="text-sm text-slate-400 mb-4">请先在数据配置中心导入 ETF 持仓数据</p>
              <div className="flex flex-wrap justify-center gap-2 text-xs text-slate-400">
                <span className="px-2 py-1 bg-slate-100 rounded">XLK 科技</span>
                <span className="px-2 py-1 bg-slate-100 rounded">XLF 金融</span>
                <span className="px-2 py-1 bg-slate-100 rounded">XLE 能源</span>
                <span className="px-2 py-1 bg-slate-100 rounded">XLV 医疗</span>
                <span className="px-2 py-1 bg-slate-100 rounded">...</span>
              </div>
            </div>
          )}
        </div>
      </section>
      
      {/* 底部操作栏 */}
      <div className="flex justify-center gap-4">
        <button 
          onClick={loadOverview}
          className="px-6 py-3 bg-white border border-slate-200 rounded-xl font-medium text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-2"
        >
          <RefreshCw className="w-5 h-5" />
          刷新数据
        </button>
        <button 
          className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all flex items-center gap-2"
        >
          <Zap className="w-5 h-5" />
          批量更新所有缺失数据
        </button>
      </div>
    </div>
  );
};

export default DataLayerView;
