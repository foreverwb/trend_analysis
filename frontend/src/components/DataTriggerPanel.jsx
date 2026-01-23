/**
 * 数据触发面板组件
 * 用于在 Finviz/MC 数据导入后提示用户获取 IBKR/Futu 实时数据
 */
import React, { useState, useEffect } from 'react';
import { 
  CheckCircle, XCircle, Clock, RefreshCw, 
  ChevronDown, ChevronUp, Zap, AlertCircle,
  ArrowRight, Database
} from 'lucide-react';
import * as api from '../utils/api';

/**
 * 平台 Logo SVG 组件
 */
const PlatformLogos = {
  // Finviz Logo
  finviz: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.1"/>
      <text x="12" y="16" fontSize="10" fontWeight="bold" fill="currentColor" textAnchor="middle">FV</text>
    </svg>
  ),
  // MarketChameleon Logo
  mc: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" opacity="0.1"/>
      <text x="12" y="16" fontSize="9" fontWeight="bold" fill="currentColor" textAnchor="middle">MC</text>
    </svg>
  ),
  // IBKR Logo (Interactive Brokers 风格)
  ibkr: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="#D92D20" opacity="0.15"/>
      <path d="M7 8h10M7 12h10M7 16h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  // Futu Logo (富途风格)
  futu: ({ size = 20, className = '' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="#FF6600" opacity="0.15"/>
      <path d="M8 7v10M8 12h8M16 7v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
};

/**
 * 数据源状态指示器（带 Logo）
 */
const DataSourceIndicator = ({ source, status, showLabel = true }) => {
  const Logo = PlatformLogos[source];
  const isComplete = status === true || status === 'complete';
  const isPending = status === 'pending';
  
  const colorClass = isComplete 
    ? 'text-emerald-600 bg-emerald-50 border-emerald-200' 
    : isPending
      ? 'text-amber-500 bg-amber-50 border-amber-200'
      : 'text-slate-400 bg-slate-50 border-slate-200';
  
  const labels = {
    finviz: 'Finviz',
    mc: 'MC',
    ibkr: 'IBKR',
    futu: 'Futu'
  };
  
  return (
    <div 
      className={`flex items-center justify-center w-8 h-8 rounded-lg border ${colorClass} transition-all`}
      title={`${labels[source]}: ${isComplete ? '已完成' : isPending ? '待获取' : '缺失'}`}
    >
      {Logo && <Logo size={18} />}
    </div>
  );
};

/**
 * Top N 权重覆盖分析组件
 */
const TopNAnalysis = ({ analysis, threshold, onSelect, selectedTopN }) => {
  if (!analysis || analysis.length === 0) return null;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-slate-700">📊 权重覆盖分析</h4>
        <span className="text-xs text-slate-500">目标阈值: {(threshold * 100).toFixed(0)}%</span>
      </div>
      <div className="flex gap-2">
        {analysis.map(item => (
          <button
            key={item.top_n}
            onClick={() => onSelect(item.top_n)}
            className={`flex-1 p-3 rounded-lg border-2 transition-all ${
              selectedTopN === item.top_n 
                ? 'border-blue-500 bg-blue-50' 
                : item.meets_threshold 
                  ? 'border-emerald-200 bg-emerald-50 hover:border-emerald-400'
                  : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <div className="text-xs text-slate-500">Top {item.top_n}</div>
            <div className={`text-lg font-bold ${
              item.meets_threshold ? 'text-emerald-600' : 'text-slate-600'
            }`}>
              {(item.weight_coverage * 100).toFixed(1)}%
            </div>
            {item.meets_threshold && (
              <CheckCircle className="w-4 h-4 text-emerald-500 mx-auto mt-1" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
};

/**
 * 格式化时间显示
 */
const formatTime = (seconds) => {
  if (!seconds || seconds <= 0) return '--';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${minutes}m ${secs}s`;
};

/**
 * 批量更新进度组件（优化版）
 */
const BatchUpdateProgress = ({ status, onCancel }) => {
  if (!status) return null;

  const { 
    total, completed, current_symbol, current_source, errors, 
    status: updateStatus, rate_stats,
    elapsed_seconds, avg_time_per_symbol, eta_seconds
  } = status;
  
  const progress = total > 0 ? (completed / total) * 100 : 0;

  const statusConfig = {
    pending: { icon: Clock, color: 'text-amber-600', bg: 'bg-amber-100', label: '准备中...' },
    running: { icon: RefreshCw, color: 'text-blue-600', bg: 'bg-blue-100', label: '获取中...' },
    completed: { icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-100', label: '已完成' },
    cancelled: { icon: XCircle, color: 'text-orange-600', bg: 'bg-orange-100', label: '已取消' },
    failed: { icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100', label: '失败' }
  };

  const config = statusConfig[updateStatus] || statusConfig.pending;
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-xl ${config.bg} border border-slate-200`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${config.color} ${updateStatus === 'running' ? 'animate-spin' : ''}`} />
          <span className={`font-medium ${config.color}`}>{config.label}</span>
        </div>
        {updateStatus === 'running' && (
          <button 
            onClick={onCancel}
            className="px-3 py-1 text-xs font-medium text-red-600 bg-red-100 rounded-lg hover:bg-red-200 transition-colors"
          >
            取消
          </button>
        )}
      </div>
      
      {/* 进度条 */}
      <div className="mb-2">
        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      
      {/* 进度信息 - 优化显示 */}
      <div className="flex justify-between items-center text-xs text-slate-600 mb-2">
        <span className="font-bold text-base text-slate-800">{completed} / {total} 个标的</span>
        {current_symbol && (
          <span className="text-blue-600 font-medium">
            当前: {current_symbol} {current_source && `(${current_source.toUpperCase()})`}
          </span>
        )}
      </div>
      
      {/* 时间预估 - 新增 */}
      {updateStatus === 'running' && (
        <div className="flex gap-4 text-xs text-slate-500 mb-3 bg-white/50 rounded-lg px-3 py-2">
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>已用: {formatTime(elapsed_seconds)}</span>
          </div>
          {avg_time_per_symbol && (
            <div className="flex items-center gap-1">
              <span>平均: {avg_time_per_symbol.toFixed(1)}s/个</span>
            </div>
          )}
          {eta_seconds && eta_seconds > 0 && (
            <div className="flex items-center gap-1 text-blue-600 font-medium">
              <span>预计剩余: {formatTime(eta_seconds)}</span>
            </div>
          )}
        </div>
      )}
      
      {/* 速率统计 */}
      {rate_stats && (
        <div className="pt-3 border-t border-slate-200/50">
          <div className="text-xs text-slate-500 mb-2 flex items-center gap-1">
            📊 速率控制
          </div>
          <div className="grid grid-cols-2 gap-2">
            {rate_stats.ibkr && (
              <div className="px-2 py-1.5 bg-white/50 rounded-lg">
                <div className="flex items-center gap-1 mb-1">
                  <PlatformLogos.ibkr size={14} className="text-red-600" />
                  <span className="text-xs text-slate-500">IBKR</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        rate_stats.ibkr.utilization > 80 ? 'bg-red-500' : 
                        rate_stats.ibkr.utilization > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${rate_stats.ibkr.utilization}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-slate-600">
                    {rate_stats.ibkr.current_rate}/{rate_stats.ibkr.max_rate}
                  </span>
                </div>
              </div>
            )}
            {rate_stats.futu && (
              <div className="px-2 py-1.5 bg-white/50 rounded-lg">
                <div className="flex items-center gap-1 mb-1">
                  <PlatformLogos.futu size={14} className="text-orange-600" />
                  <span className="text-xs text-slate-500">Futu</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        rate_stats.futu.utilization > 80 ? 'bg-red-500' : 
                        rate_stats.futu.utilization > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${rate_stats.futu.utilization}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-slate-600">
                    {rate_stats.futu.current_rate}/{rate_stats.futu.max_rate}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      
      {errors && errors.length > 0 && (
        <div className="mt-2 text-xs text-red-600">
          ⚠️ {errors.length} 个错误
        </div>
      )}
    </div>
  );
};

/**
 * 待更新标的列表（使用 Logo 版本）
 */
const PendingSymbolsList = ({ symbols, maxDisplay = 8 }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!symbols || symbols.length === 0) return null;

  const displaySymbols = expanded ? symbols : symbols.slice(0, maxDisplay);

  return (
    <div className="mb-4">
      <h4 className="text-sm font-semibold text-slate-700 mb-2">📋 待更新标的</h4>
      <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
        {/* 表头 - 使用 Logo */}
        <div className="grid grid-cols-7 gap-2 px-3 py-2 bg-slate-100 text-xs font-medium text-slate-500 border-b">
          <div className="col-span-1">标的</div>
          <div className="col-span-1 text-right">权重</div>
          <div className="col-span-1 flex justify-center">
            <PlatformLogos.finviz size={16} className="text-slate-500" />
          </div>
          <div className="col-span-1 flex justify-center">
            <PlatformLogos.mc size={16} className="text-slate-500" />
          </div>
          <div className="col-span-1 flex justify-center">
            <PlatformLogos.ibkr size={16} className="text-slate-500" />
          </div>
          <div className="col-span-1 flex justify-center">
            <PlatformLogos.futu size={16} className="text-slate-500" />
          </div>
          <div className="col-span-1"></div>
        </div>
        <div className="max-h-48 overflow-y-auto">
          {displaySymbols.map((item, idx) => (
            <div 
              key={item.symbol}
              className={`grid grid-cols-7 gap-2 px-3 py-2 text-sm items-center ${idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}`}
            >
              <div className="col-span-1 font-medium text-slate-800">{item.symbol}</div>
              <div className="col-span-1 text-right text-slate-600">{item.weight?.toFixed(2)}%</div>
              <div className="col-span-1 flex justify-center">
                <DataSourceIndicator source="finviz" status={item.has_finviz} />
              </div>
              <div className="col-span-1 flex justify-center">
                <DataSourceIndicator source="mc" status={item.has_mc} />
              </div>
              <div className="col-span-1 flex justify-center">
                <DataSourceIndicator source="ibkr" status={item.has_ibkr ? true : 'pending'} />
              </div>
              <div className="col-span-1 flex justify-center">
                <DataSourceIndicator source="futu" status={item.has_futu ? true : 'pending'} />
              </div>
              <div className="col-span-1"></div>
            </div>
          ))}
        </div>
        {symbols.length > maxDisplay && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 transition-colors flex items-center justify-center gap-1"
          >
            {expanded ? (
              <>收起 <ChevronUp className="w-4 h-4" /></>
            ) : (
              <>显示更多 ({symbols.length - maxDisplay} 条) <ChevronDown className="w-4 h-4" /></>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * 数据触发面板主组件
 */
const DataTriggerPanel = ({ 
  etfSymbol,
  dataType = 'holdings', // 'etf' | 'holdings'
  onClose,
  onUpdateComplete
}) => {
  const [loading, setLoading] = useState(true);
  const [topNAnalysis, setTopNAnalysis] = useState(null);
  const [pendingSymbols, setPendingSymbols] = useState([]);
  const [selectedTopN, setSelectedTopN] = useState(20);
  const [batchStatus, setBatchStatus] = useState(null);
  const [error, setError] = useState(null);

  // 加载分析数据
  useEffect(() => {
    const loadData = async () => {
      if (!etfSymbol) return;
      
      setLoading(true);
      setError(null);
      
      try {
        // 获取 Top N 分析
        const analysisRes = await api.analyzeTopN(etfSymbol);
        if (analysisRes.data) {
          setTopNAnalysis(analysisRes.data);
          setSelectedTopN(analysisRes.data.recommended_top_n || 20);
        }
        
        // 获取待更新标的
        const pendingRes = await api.getPendingSymbols(etfSymbol, 30);
        if (pendingRes.data) {
          setPendingSymbols(pendingRes.data);
        }
      } catch (err) {
        console.error('加载数据失败:', err);
        setError(err.response?.data?.detail || err.message || '加载失败');
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [etfSymbol]);

  // 轮询更新状态
  useEffect(() => {
    let interval;
    
    if (batchStatus && ['pending', 'running'].includes(batchStatus.status)) {
      interval = setInterval(async () => {
        try {
          const res = await api.getBatchUpdateStatus(batchStatus.session_id);
          if (res.data) {
            setBatchStatus(res.data);
            
            if (['completed', 'cancelled', 'failed'].includes(res.data.status)) {
              clearInterval(interval);
              if (res.data.status === 'completed' && onUpdateComplete) {
                onUpdateComplete(res.data);
              }
            }
          }
        } catch (err) {
          console.error('获取更新状态失败:', err);
        }
      }, 1000);
    }
    
    return () => clearInterval(interval);
  }, [batchStatus, onUpdateComplete]);

  // 开始快捷更新
  const handleQuickUpdate = async () => {
    try {
      setError(null);
      const res = await api.quickUpdate(etfSymbol, selectedTopN);
      if (res.data) {
        if (res.data.session_id) {
          setBatchStatus(res.data);
        } else {
          alert(res.data.message || '数据已完备');
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || '更新失败');
    }
  };

  // 取消更新
  const handleCancelUpdate = async () => {
    if (!batchStatus?.session_id) return;
    
    try {
      await api.cancelBatchUpdate(batchStatus.session_id);
    } catch (err) {
      console.error('取消更新失败:', err);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-lg p-6">
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-6 h-6 text-blue-500 animate-spin" />
          <span className="ml-2 text-slate-600">加载中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden">
      {/* 头部 */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-5 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-white font-bold">{etfSymbol} 实时数据获取</h3>
              <p className="text-white/70 text-sm">
                {dataType === 'etf' ? 'ETF 自身数据' : '持仓成分股数据'}
              </p>
            </div>
          </div>
          {onClose && (
            <button 
              onClick={onClose}
              className="text-white/70 hover:text-white transition-colors"
            >
              <XCircle className="w-6 h-6" />
            </button>
          )}
        </div>
      </div>
      
      {/* 内容 */}
      <div className="p-5">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
        
        {/* Top N 分析 */}
        {dataType === 'holdings' && topNAnalysis && (
          <TopNAnalysis
            analysis={topNAnalysis.analysis}
            threshold={topNAnalysis.threshold}
            onSelect={setSelectedTopN}
            selectedTopN={selectedTopN}
          />
        )}
        
        {/* 待更新标的列表 */}
        <PendingSymbolsList 
          symbols={pendingSymbols.slice(0, selectedTopN)}
        />
        
        {/* 更新进度 */}
        {batchStatus ? (
          <BatchUpdateProgress 
            status={batchStatus}
            onCancel={handleCancelUpdate}
          />
        ) : (
          <div className="flex gap-3">
            <button 
              onClick={handleQuickUpdate}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all flex items-center justify-center gap-2"
            >
              <Zap className="w-5 h-5" />
              获取 Top {selectedTopN} 实时数据
            </button>
            {onClose && (
              <button 
                onClick={onClose}
                className="px-4 py-3 bg-slate-100 text-slate-600 rounded-xl font-medium hover:bg-slate-200 transition-colors"
              >
                稍后再说
              </button>
            )}
          </div>
        )}
      </div>
      
      {/* 底部提示 */}
      <div className="px-5 py-3 bg-slate-50 border-t border-slate-100">
        <p className="text-xs text-slate-500 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          建议获取权重覆盖 ≥70% 的 Top N，以确保评分计算准确性
        </p>
      </div>
    </div>
  );
};

export default DataTriggerPanel;
