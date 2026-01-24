import React, { useState, useMemo } from 'react';
import { 
  TrendingUp, Activity, BarChart2, Flame, CheckCircle, Clock, AlertCircle,
  ChevronDown, ChevronUp, Filter
} from 'lucide-react';

// 持仓筛选选项配置
const HOLDINGS_FILTER_OPTIONS = [
  { value: 'top10', label: 'TOP 10', description: '前10大持仓' },
  { value: '70', label: '70%', description: '累计权重达70%' },
  { value: '75', label: '75%', description: '累计权重达75%' },
  { value: '80', label: '80%', description: '累计权重达80%' },
  { value: '85', label: '85%', description: '累计权重达85%' },
  { value: '90', label: '90%', description: '累计权重达90%' },
  { value: 'all', label: '全部', description: '显示所有持仓' }
];

// 根据筛选条件过滤持仓
const filterHoldings = (holdings, filterType) => {
  if (!holdings || holdings.length === 0) return [];
  
  // 按权重排序（降序）
  const sortedHoldings = [...holdings].sort((a, b) => (b.weight || 0) - (a.weight || 0));
  
  if (filterType === 'all') {
    return sortedHoldings;
  }
  
  if (filterType === 'top10') {
    return sortedHoldings.slice(0, 10);
  }
  
  // 百分比筛选
  const targetPercent = parseInt(filterType, 10);
  if (!isNaN(targetPercent)) {
    let cumWeight = 0;
    const result = [];
    for (const holding of sortedHoldings) {
      result.push(holding);
      cumWeight += (holding.weight || 0);
      if (cumWeight >= targetPercent) break;
    }
    return result;
  }
  
  return sortedHoldings;
};

// 计算累计权重
const calculateCumulativeWeight = (holdings) => {
  return holdings.reduce((sum, h) => sum + (h.weight || 0), 0);
};

const SectorETFView = ({
  sectorETFs,
  refreshingETF,
  handleRefreshETF,
  HoldingsTable,
  getScoreColor,
  getScoreBg,
  getOptionsHeatColor
}) => {
  // 每个 ETF 的展开/折叠状态
  const [expandedETFs, setExpandedETFs] = useState({});
  // 每个 ETF 的筛选条件
  const [holdingsFilters, setHoldingsFilters] = useState({});

  // 只显示有 holdings 数据的 ETF
  const etfsWithHoldings = useMemo(() => {
    return sectorETFs.filter(etf => etf.holdings && etf.holdings.length > 0);
  }, [sectorETFs]);

  // 切换 ETF 展开状态
  const toggleETFExpanded = (symbol) => {
    setExpandedETFs(prev => ({
      ...prev,
      [symbol]: !prev[symbol]
    }));
  };

  // 更新 ETF 的筛选条件
  const updateHoldingsFilter = (symbol, filterValue) => {
    setHoldingsFilters(prev => ({
      ...prev,
      [symbol]: filterValue
    }));
  };

  // 数据状态徽章组件
  const DataStatusBadge = ({ etf }) => {
    const hasData = etf.holdings && etf.holdings.length > 0;
    const isRecent = etf.updated_at && 
      (new Date() - new Date(etf.updated_at)) < 24 * 60 * 60 * 1000; // 24小时内
    
    if (hasData && isRecent) {
      return (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium">
          <CheckCircle className="w-3.5 h-3.5" />
          <span>数据就绪</span>
        </div>
      );
    } else if (hasData) {
      return (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-medium">
          <Clock className="w-3.5 h-3.5" />
          <span>待更新</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-500 rounded-lg text-xs font-medium">
        <AlertCircle className="w-3.5 h-3.5" />
        <span>无数据</span>
      </div>
    );
  };

  // 内联持仓表格组件（支持筛选）
  const FilterableHoldingsTable = ({ holdings = [], etfSymbol }) => {
    const currentFilter = holdingsFilters[etfSymbol] || 'top10';
    const filteredHoldings = filterHoldings(holdings, currentFilter);
    const cumulativeWeight = calculateCumulativeWeight(filteredHoldings);
    
    // 检查是否有扩展数据
    const hasExtendedData = holdings.some(h => h.sma50 !== undefined || h.sma200 !== undefined);
    
    return (
      <div className="mt-4">
        {/* 筛选器和统计信息 */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <h4 className="text-sm font-bold text-slate-900">持仓明细 (Holdings)</h4>
            <div className="flex items-center gap-1 px-2 py-1 bg-blue-50 rounded text-xs text-blue-600">
              <span>{filteredHoldings.length} 只</span>
              <span className="text-blue-400">|</span>
              <span>累计 {cumulativeWeight.toFixed(1)}%</span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <div className="flex gap-1 bg-slate-100 p-0.5 rounded-lg">
              {HOLDINGS_FILTER_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => updateHoldingsFilter(etfSymbol, option.value)}
                  className={`px-2 py-1 text-xs rounded-md transition-all ${
                    currentFilter === option.value
                      ? 'bg-white text-blue-600 shadow-sm font-medium'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title={option.description}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-400 ml-2">总持仓数: {holdings.length}</span>
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          {/* 表头 */}
          <div className="grid px-4 py-3 bg-gradient-to-r from-slate-50 to-slate-100 border-b border-slate-200 font-semibold text-xs text-slate-600 uppercase tracking-wider"
               style={{ gridTemplateColumns: hasExtendedData ? '48px 80px 80px 90px 90px 70px 80px 70px' : '48px 100px 1fr' }}>
            <div className="text-center">#</div>
            <div>TICKER</div>
            <div className="text-right">WEIGHT</div>
            {hasExtendedData && (
              <>
                <div className="text-right">50DMA</div>
                <div className="text-right">200DMA</div>
                <div className="text-right">RSI</div>
                <div className="text-right">POSITION</div>
                <div className="text-right">TERM</div>
              </>
            )}
          </div>
          
          <div className="max-h-[400px] overflow-y-auto">
            {filteredHoldings.map((holding, idx) => (
              <div 
                key={idx} 
                className={`grid px-4 py-2.5 text-sm items-center ${
                  idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'
                } hover:bg-blue-50/70 transition-colors border-b border-slate-100/80`}
                style={{ gridTemplateColumns: hasExtendedData ? '48px 80px 80px 90px 90px 70px 80px 70px' : '48px 100px 1fr' }}
              >
                <div className="text-center text-slate-400 text-xs font-medium">#{idx + 1}</div>
                <div className="font-mono font-bold text-slate-800 text-sm">{holding.ticker}</div>
                <div className="text-right font-semibold text-blue-600">
                  {typeof holding.weight === 'number' ? holding.weight.toFixed(2) : holding.weight}%
                </div>
                {hasExtendedData && (
                  <>
                    <div className={`text-right font-medium ${
                      holding.sma50 > 0 ? 'text-emerald-600' : holding.sma50 < 0 ? 'text-red-500' : 'text-slate-400'
                    }`}>
                      {holding.sma50 !== null && holding.sma50 !== undefined 
                        ? `${holding.sma50 > 0 ? '+' : ''}${holding.sma50.toFixed(2)}%`
                        : '-'}
                    </div>
                    <div className={`text-right font-medium ${
                      holding.sma200 > 0 ? 'text-emerald-600' : holding.sma200 < 0 ? 'text-red-500' : 'text-slate-400'
                    }`}>
                      {holding.sma200 !== null && holding.sma200 !== undefined 
                        ? `${holding.sma200 > 0 ? '+' : ''}${holding.sma200.toFixed(2)}%`
                        : '-'}
                    </div>
                    <div className={`text-right font-medium ${
                      holding.rsi > 70 ? 'text-red-500' : 
                      holding.rsi < 30 ? 'text-emerald-600' : 'text-slate-600'
                    }`}>
                      {holding.rsi !== null && holding.rsi !== undefined 
                        ? holding.rsi.toFixed(1) 
                        : '-'}
                    </div>
                    <div className={`text-right font-medium ${
                      holding.positioning_score >= 60 ? 'text-emerald-600' : 
                      holding.positioning_score < 40 ? 'text-red-500' : 'text-amber-500'
                    }`}>
                      {holding.positioning_score !== null && holding.positioning_score !== undefined 
                        ? holding.positioning_score.toFixed(0) 
                        : '-'}
                    </div>
                    <div className={`text-right font-medium ${
                      holding.term_score > 0 ? 'text-red-500' : 
                      holding.term_score < 0 ? 'text-emerald-600' : 'text-slate-500'
                    }`}>
                      {holding.term_score !== null && holding.term_score !== undefined 
                        ? holding.term_score.toFixed(1) 
                        : '-'}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
        
        {/* 图例说明 */}
        {hasExtendedData && (
          <div className="mt-2 text-xs text-slate-500 flex gap-4 flex-wrap">
            <span>📊 50DMA/200DMA: 相对均线距离</span>
            <span>🎯 Position: 定位评分</span>
            <span>📈 Term: 期限结构</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <TrendingUp className="w-5 h-5 text-blue-600" />
          <h2 className="text-xl font-bold text-slate-900">板块 ETF 分析矩阵</h2>
          <span className="text-sm text-slate-600">共 {etfsWithHoldings.length} 个板块</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-500">
            💡 请在「数据配置中心」统一更新数据
          </div>
          <div className="text-sm text-slate-600">
            {sectorETFs[0]?.updated_at 
              ? `更新于 ${new Date(sectorETFs[0].updated_at).toLocaleString()}`
              : '数据待更新'
            }
          </div>
        </div>
      </div>

      {etfsWithHoldings.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 border border-slate-200 shadow-lg text-center">
          <TrendingUp className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无数据</h3>
          <p className="text-sm text-slate-500">请先在「数据配置中心」导入 ETF holdings 数据</p>
        </div>
      ) : (
        etfsWithHoldings.map((etf, idx) => {
          const isExpanded = expandedETFs[etf.symbol] || false;
          
          return (
            <div key={etf.symbol} className="bg-white rounded-2xl border border-slate-200 shadow-lg hover:border-blue-300 hover:shadow-xl transition-all overflow-hidden">
              {/* ETF 卡片头部 - 始终显示 */}
              <div className="p-6">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center text-white shadow-md">
                      <span className="text-xl font-bold">{idx + 1}</span>
                    </div>
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-2xl font-bold text-slate-900">{etf.symbol}</h3>
                        <span className="text-slate-600">{etf.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-slate-500">Sector ETF</span>
                        {etf.holdings && (
                          <span className="text-xs text-slate-400">
                            数据覆盖: {etf.holdings.length} 个持仓
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <DataStatusBadge etf={etf} />
                    <div className={`px-6 py-3 rounded-xl border ${getScoreBg(etf.compositeScore || 0)}`}>
                      <div className="text-xs text-slate-600 mb-1">综合分</div>
                      <div className={`text-3xl font-bold ${getScoreColor(etf.compositeScore || 0)}`}>
                        {etf.compositeScore || 0}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Delta indicators */}
                {(etf.delta_3d || etf.delta_5d) && (
                  <div className="mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="text-xs text-slate-500 mb-2">变化指标</div>
                    <div className="flex gap-6 text-sm">
                      {etf.delta_3d?.composite_score !== null && (
                        <span>
                          3D Δ: <span className={etf.delta_3d.composite_score >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                            {etf.delta_3d.composite_score >= 0 ? '+' : ''}{etf.delta_3d.composite_score}
                          </span>
                        </span>
                      )}
                      {etf.delta_5d?.composite_score !== null && (
                        <span>
                          5D Δ: <span className={etf.delta_5d.composite_score >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                            {etf.delta_5d.composite_score >= 0 ? '+' : ''}{etf.delta_5d.composite_score}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* 四个指标卡片 */}
                <div className="grid grid-cols-4 gap-4">
                  {/* 相对动量 */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <div className="flex items-center gap-2 mb-3">
                      <Activity className="w-4 h-4 text-blue-600" />
                      <h4 className="text-sm font-bold text-slate-700">相对动量</h4>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">评分</span>
                        <span className={`text-lg font-bold ${getScoreColor(etf.relMomentum?.score || 0)}`}>
                          {etf.relMomentum?.score || 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">动量值</span>
                        <span className="text-sm font-medium text-emerald-600">{etf.relMomentum?.value || '+0.0%'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">排名</span>
                        <span className="text-sm font-medium text-blue-600">#{etf.relMomentum?.rank || '-'}</span>
                      </div>
                    </div>
                  </div>

                  {/* 趋势质量 */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="w-4 h-4 text-emerald-600" />
                      <h4 className="text-sm font-bold text-slate-700">趋势质量</h4>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">评分</span>
                        <span className={`text-lg font-bold ${getScoreColor(etf.trendQuality?.score || 0)}`}>
                          {etf.trendQuality?.score || 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">结构</span>
                        <span className="text-sm font-medium text-emerald-600">{etf.trendQuality?.structure || 'Neutral'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">斜率</span>
                        <span className="text-sm font-medium text-blue-600">{etf.trendQuality?.slope || '+0.00'}</span>
                      </div>
                    </div>
                  </div>

                  {/* 广度/参与度 */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <div className="flex items-center gap-2 mb-3">
                      <BarChart2 className="w-4 h-4 text-purple-600" />
                      <h4 className="text-sm font-bold text-slate-700">广度/参与度</h4>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">评分</span>
                        <span className={`text-lg font-bold ${getScoreColor(etf.breadth?.score || 0)}`}>
                          {etf.breadth?.score || 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">&gt;50MA</span>
                        <span className="text-sm font-medium text-purple-600">{etf.breadth?.above50ma || '0%'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">&gt;200MA</span>
                        <span className="text-sm font-medium text-blue-600">{etf.breadth?.above200ma || '0%'}</span>
                      </div>
                    </div>
                  </div>

                  {/* 期权确认 */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <div className="flex items-center gap-2 mb-3">
                      <Flame className="w-4 h-4 text-orange-600" />
                      <h4 className="text-sm font-bold text-slate-700">期权确认</h4>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">评分</span>
                        <span className={`text-lg font-bold ${getScoreColor(etf.optionsConfirm?.score || 0)}`}>
                          {etf.optionsConfirm?.score || 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">热度</span>
                        <span className={`text-sm font-medium ${getOptionsHeatColor(etf.optionsConfirm?.heat || 'Low')}`}>
                          {etf.optionsConfirm?.heat || 'Low'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">相对成交</span>
                        <span className="text-sm font-medium text-orange-600">{etf.optionsConfirm?.relVol || '1.0x'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-600">IVR</span>
                        <span className="text-sm font-medium text-amber-600">{etf.optionsConfirm?.ivr || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 展开/折叠按钮 */}
              <div className="border-t border-slate-200">
                <button
                  onClick={() => toggleETFExpanded(etf.symbol)}
                  className="w-full px-6 py-3 flex items-center justify-center gap-2 text-sm font-medium text-slate-600 hover:text-blue-600 hover:bg-slate-50 transition-colors"
                >
                  {isExpanded ? (
                    <>
                      <ChevronUp className="w-4 h-4" />
                      收起持仓明细
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-4 h-4" />
                      显示更多 ({etf.holdings?.length || 0} 条)
                    </>
                  )}
                </button>
              </div>

              {/* 持仓表格 - 可折叠 */}
              {isExpanded && etf.holdings && etf.holdings.length > 0 && (
                <div className="px-6 pb-6 border-t border-slate-100 bg-slate-50/30">
                  <FilterableHoldingsTable 
                    holdings={etf.holdings} 
                    etfSymbol={etf.symbol} 
                  />
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
};

export default SectorETFView;
