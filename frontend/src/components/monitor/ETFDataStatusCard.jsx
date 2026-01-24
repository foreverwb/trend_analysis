import React, { useState } from 'react';
import { 
  CheckCircle, AlertCircle, Clock, RefreshCw, Upload,
  TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp,
  Database, BarChart2, Activity
} from 'lucide-react';

// 数据状态组件
const DataStatusBadge = ({ status, lastUpdated }) => {
  const statusConfig = {
    complete: { 
      icon: CheckCircle, 
      color: 'text-green-500', 
      bg: 'bg-green-100',
      label: '完整' 
    },
    partial: { 
      icon: AlertCircle, 
      color: 'text-yellow-500', 
      bg: 'bg-yellow-100',
      label: '部分' 
    },
    missing: { 
      icon: Clock, 
      color: 'text-gray-400', 
      bg: 'bg-gray-100',
      label: '未导入' 
    },
    error: { 
      icon: AlertCircle, 
      color: 'text-red-500', 
      bg: 'bg-red-100',
      label: '错误' 
    }
  };

  const config = statusConfig[status] || statusConfig.missing;
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <span className={`flex items-center px-2 py-1 rounded-full text-xs ${config.bg} ${config.color}`}>
        <Icon className="w-3 h-3 mr-1" />
        {config.label}
      </span>
      {lastUpdated && (
        <span className="text-xs text-gray-400">
          {formatTimeAgo(lastUpdated)}
        </span>
      )}
    </div>
  );
};

// 时间格式化
const formatTimeAgo = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString('zh-CN');
};

// Delta 显示组件
const DeltaDisplay = ({ value, label }) => {
  if (value === null || value === undefined) {
    return (
      <div className="text-center">
        <p className="text-xs text-gray-400">{label}</p>
        <p className="text-sm text-gray-300">--</p>
      </div>
    );
  }

  const isPositive = value > 0;
  const isNegative = value < 0;
  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const color = isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-500';

  return (
    <div className="text-center">
      <p className="text-xs text-gray-400">{label}</p>
      <div className={`flex items-center justify-center ${color}`}>
        <Icon className="w-4 h-4 mr-1" />
        <span className="font-medium">{value > 0 ? '+' : ''}{value.toFixed(2)}</span>
      </div>
    </div>
  );
};

// 评分条
const ScoreBar = ({ score, maxScore = 100 }) => {
  const percentage = Math.min((score / maxScore) * 100, 100);
  const getColor = () => {
    if (percentage >= 70) return 'bg-green-500';
    if (percentage >= 50) return 'bg-yellow-500';
    if (percentage >= 30) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div 
        className={`h-2 rounded-full transition-all duration-300 ${getColor()}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
};

const ETFDataStatusCard = ({ 
  etf,
  onRefreshData,
  onImportData,
  isRefreshing = false,
  expanded: initialExpanded = false
}) => {
  const [expanded, setExpanded] = useState(initialExpanded);

  // 从 etf 对象解构数据
  const {
    symbol,
    name,
    level,
    parentSymbol,
    // 数据状态
    finvizStatus = 'missing',
    finvizRecordCount = 0,
    finvizUpdatedAt,
    mcStatus = 'missing',
    mcRecordCount = 0,
    mcUpdatedAt,
    marketStatus = 'missing',
    marketUpdatedAt,
    optionsStatus = 'missing',
    optionsUpdatedAt,
    // 评分
    overallScore,
    trendScore,
    momentumScore,
    rsScore,
    optionsScore,
    // 排名
    rank,
    totalInTask,
    // Delta
    delta3d,
    delta5d,
    // 排名变化
    rankChange3d,
    rankChange5d
  } = etf;

  // 计算数据完备度
  const getDataCompleteness = () => {
    const statuses = [finvizStatus, mcStatus, marketStatus, optionsStatus];
    const complete = statuses.filter(s => s === 'complete').length;
    return Math.round((complete / statuses.length) * 100);
  };

  const completeness = getDataCompleteness();

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* 卡片头部 */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* ETF 符号和名称 */}
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg text-gray-800">{symbol}</h3>
                <span className={`px-2 py-0.5 text-xs rounded-full
                  ${level === 'sector' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                  {level === 'sector' ? '板块' : '行业'}
                </span>
              </div>
              <p className="text-sm text-gray-500">{name}</p>
              {parentSymbol && (
                <p className="text-xs text-gray-400 mt-0.5">隶属: {parentSymbol}</p>
              )}
            </div>
          </div>

          {/* 评分和排名 */}
          <div className="text-right">
            {overallScore !== undefined && overallScore !== null ? (
              <div>
                <p className="text-2xl font-bold text-gray-800">
                  {overallScore.toFixed(1)}
                </p>
                {rank && (
                  <p className="text-sm text-gray-500">
                    排名 #{rank}/{totalInTask || '-'}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-gray-400">暂无评分</p>
            )}
          </div>
        </div>

        {/* 评分条 */}
        {overallScore !== undefined && overallScore !== null && (
          <div className="mt-3">
            <ScoreBar score={overallScore} />
          </div>
        )}

        {/* Delta 指标 */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex gap-6">
            <DeltaDisplay value={delta3d} label="Δ3D" />
            <DeltaDisplay value={delta5d} label="Δ5D" />
          </div>
          
          {/* 数据完备度 */}
          <div className="text-right">
            <p className="text-xs text-gray-400">数据完备度</p>
            <p className={`font-medium ${completeness === 100 ? 'text-green-600' : 'text-yellow-600'}`}>
              {completeness}%
            </p>
          </div>
        </div>
      </div>

      {/* 展开/折叠按钮 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 bg-gray-50 flex items-center justify-center text-sm text-gray-500 hover:bg-gray-100 transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-4 h-4 mr-1" />
            收起详情
          </>
        ) : (
          <>
            <ChevronDown className="w-4 h-4 mr-1" />
            查看详情
          </>
        )}
      </button>

      {/* 展开的详情部分 */}
      {expanded && (
        <div className="border-t border-gray-200">
          {/* 数据状态 */}
          <div className="p-4 space-y-3">
            <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
              <Database className="w-4 h-4 mr-2" />
              数据状态
            </h4>
            
            {/* Finviz 数据 */}
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <div className="flex items-center">
                <span className="text-sm text-gray-600 w-32">Finviz</span>
                <DataStatusBadge status={finvizStatus} lastUpdated={finvizUpdatedAt} />
              </div>
              <span className="text-sm text-gray-400">{finvizRecordCount} 条</span>
            </div>
            
            {/* MC 数据 */}
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <div className="flex items-center">
                <span className="text-sm text-gray-600 w-32">MarketChameleon</span>
                <DataStatusBadge status={mcStatus} lastUpdated={mcUpdatedAt} />
              </div>
              <span className="text-sm text-gray-400">{mcRecordCount} 条</span>
            </div>
            
            {/* 市场数据 */}
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <div className="flex items-center">
                <span className="text-sm text-gray-600 w-32">市场数据</span>
                <DataStatusBadge status={marketStatus} lastUpdated={marketUpdatedAt} />
              </div>
              <span className="text-sm text-gray-400">ETF自身</span>
            </div>
            
            {/* 期权数据 */}
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center">
                <span className="text-sm text-gray-600 w-32">期权数据</span>
                <DataStatusBadge status={optionsStatus} lastUpdated={optionsUpdatedAt} />
              </div>
              <span className="text-sm text-gray-400">ETF自身</span>
            </div>
          </div>

          {/* 评分详情 */}
          {overallScore !== undefined && (
            <div className="p-4 bg-gray-50 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center">
                <BarChart2 className="w-4 h-4 mr-2" />
                评分详情
              </h4>
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-xs text-gray-400">趋势</p>
                  <p className="font-medium text-gray-700">{trendScore?.toFixed(1) || '--'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">动量</p>
                  <p className="font-medium text-gray-700">{momentumScore?.toFixed(1) || '--'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">相对强度</p>
                  <p className="font-medium text-gray-700">{rsScore?.toFixed(1) || '--'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">期权</p>
                  <p className="font-medium text-gray-700">{optionsScore?.toFixed(1) || '--'}</p>
                </div>
              </div>
            </div>
          )}

          {/* 操作按钮 */}
          <div className="p-4 flex gap-2 border-t border-gray-200">
            <button
              onClick={() => onRefreshData?.(symbol)}
              disabled={isRefreshing}
              className={`flex items-center px-4 py-2 rounded-lg text-sm transition-colors
                ${isRefreshing 
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                  : 'bg-blue-50 text-blue-600 hover:bg-blue-100'}`}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? '刷新中...' : '刷新数据'}
            </button>
            <button
              onClick={() => onImportData?.(symbol)}
              className="flex items-center px-4 py-2 bg-gray-50 text-gray-600 rounded-lg text-sm hover:bg-gray-100 transition-colors"
            >
              <Upload className="w-4 h-4 mr-2" />
              补充导入
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ETFDataStatusCard;
