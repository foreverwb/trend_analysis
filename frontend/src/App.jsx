import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, BarChart2, Activity, Flame, Zap, 
  AlertCircle, Terminal, 
  ChevronDown, ChevronUp, RefreshCw 
} from 'lucide-react';
import * as api from './utils/api';

// Sub-components
import TerminalView from './components/TerminalView';
import DataConfigCenter from './components/DataConfigCenter';
import SectorETFView from './components/SectorETFView';
import IndustryETFView from './components/IndustryETFView';
import MomentumStocksView from './components/MomentumStocksView';

// 控制台日志开关
const DEBUG_MODE = localStorage.getItem('debugMode') === 'true';

const log = {
  info: (...args) => DEBUG_MODE && console.log('[App]', ...args),
  error: (...args) => console.error('[App Error]', ...args),
  warn: (...args) => DEBUG_MODE && console.warn('[App Warn]', ...args),
};

const App = () => {
  const [activeTab, setActiveTab] = useState('terminal');
  const [selectedSector, setSelectedSector] = useState('XLK');
  const [expandedHoldings, setExpandedHoldings] = useState({});
  const [refreshingETF, setRefreshingETF] = useState(null);
  
  // Data states
  const [marketRegime, setMarketRegime] = useState({
    status: 'B',
    spy: { price: 0, vs200ma: '+0.0%', trend: 'neutral' },
    vix: 0,
    breadth: 50
  });
  const [sectorETFs, setSectorETFs] = useState([]);
  const [industryETFs, setIndustryETFs] = useState([]);
  const [momentumStocks, setMomentumStocks] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load data on mount and tab change
  useEffect(() => {
    log.info('Tab changed to:', activeTab);
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    log.info('Loading data for tab:', activeTab);
    
    try {
      if (activeTab === 'terminal') {
        log.info('Fetching terminal data...');
        const [regimeRes, sectorsRes, industriesRes, stocksRes] = await Promise.all([
          api.getMarketRegime(),
          api.getSectorETFs(),
          api.getIndustryETFs(),
          api.getTopMomentumStocks(5)
        ]);
        setMarketRegime(regimeRes.data);
        setSectorETFs(sectorsRes.data);
        setIndustryETFs(industriesRes.data);
        setMomentumStocks(stocksRes.data);
        log.info('Terminal data loaded successfully');
      } else if (activeTab === 'sector-etf') {
        const res = await api.getSectorETFs();
        setSectorETFs(res.data);
        log.info('Sector ETF data loaded:', res.data.length, 'items');
      } else if (activeTab === 'industry-etf') {
        const res = await api.getIndustryETFs();
        setIndustryETFs(res.data);
        log.info('Industry ETF data loaded:', res.data.length, 'items');
      } else if (activeTab === 'momentum-stocks') {
        const res = await api.getMomentumStocks();
        setMomentumStocks(res.data);
        log.info('Momentum stocks data loaded:', res.data.length, 'items');
      }
    } catch (error) {
      log.error('Error loading data:', error);
    }
    setLoading(false);
  };

  const handleRefreshETF = async (etfSymbol, etfType = 'sector') => {
    setRefreshingETF(etfSymbol);
    log.info('Refreshing ETF:', etfSymbol, 'Type:', etfType);
    
    try {
      if (etfSymbol === 'MARKET') {
        await api.refreshMarketRegime();
        const res = await api.getMarketRegime();
        setMarketRegime(res.data);
        log.info('Market regime refreshed');
      } else if (etfType === 'sector') {
        await api.refreshSectorETF(etfSymbol);
        const res = await api.getSectorETFs();
        setSectorETFs(res.data);
        log.info('Sector ETF refreshed:', etfSymbol);
      } else {
        await api.refreshIndustryETF(etfSymbol);
        const res = await api.getIndustryETFs();
        setIndustryETFs(res.data);
        log.info('Industry ETF refreshed:', etfSymbol);
      }
    } catch (error) {
      log.error(`Error refreshing ${etfSymbol}:`, error);
      alert(`刷新失败: ${error.response?.data?.detail || error.message}`);
    }
    setRefreshingETF(null);
  };

  // Helper functions
  const getRegimeColor = (status) => {
    if (status === 'A') return 'from-emerald-400 to-green-500';
    if (status === 'B') return 'from-amber-400 to-orange-500';
    return 'from-red-400 to-rose-500';
  };

  const getRegimeText = (status) => {
    if (status === 'A') return '牛市 Bullish';
    if (status === 'B') return '震荡 Neutral';
    return '熊市 Bearish';
  };

  const getScoreColor = (score) => {
    if (score >= 85) return 'text-emerald-600';
    if (score >= 70) return 'text-blue-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-slate-500';
  };

  const getScoreBg = (score) => {
    if (score >= 85) return 'bg-emerald-50 border-emerald-200';
    if (score >= 70) return 'bg-blue-50 border-blue-200';
    if (score >= 60) return 'bg-amber-50 border-amber-200';
    return 'bg-slate-50 border-slate-200';
  };

  const getOptionsHeatColor = (heat) => {
    if (heat === 'Very High') return 'text-red-600';
    if (heat === 'High') return 'text-orange-600';
    if (heat === 'Medium') return 'text-amber-600';
    return 'text-slate-500';
  };

  const getHeatLevelColor = (level) => {
    if (level === 'Moderate') return 'text-emerald-600';
    if (level === 'Slightly Hot') return 'text-amber-600';
    return 'text-red-600';
  };

  // Holdings Table Component - 扩展版本
  // 修复 Bug #3: 增加 50DMA, 200DMA, PositioningScore, TermScore 字段
  const HoldingsTable = ({ holdings = [], maxDisplay = 10, etfSymbol }) => {
    const isExpanded = expandedHoldings[etfSymbol] || false;
    const displayHoldings = isExpanded ? holdings : holdings.slice(0, maxDisplay);
    
    // 检查是否有扩展数据
    const hasExtendedData = holdings.some(h => h.sma50 !== undefined || h.sma200 !== undefined);
    
    return (
      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-bold text-slate-900">持仓明细 (Holdings)</h4>
          <span className="text-xs text-slate-600">总持仓数: {holdings.length}</span>
        </div>
        
        <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
          {/* 表头 - 根据是否有扩展数据显示不同列 */}
          <div className={`grid ${hasExtendedData ? 'grid-cols-16' : 'grid-cols-12'} gap-2 px-4 py-3 bg-slate-100 border-b border-slate-200 font-medium text-xs text-slate-700`}>
            <div className="col-span-1">#</div>
            <div className="col-span-2">Ticker</div>
            <div className="col-span-2 text-right">Weight</div>
            {hasExtendedData && (
              <>
                <div className="col-span-2 text-right">50DMA</div>
                <div className="col-span-2 text-right">200DMA</div>
                <div className="col-span-2 text-right">RSI</div>
                <div className="col-span-2 text-right">Position</div>
                <div className="col-span-2 text-right">Term</div>
              </>
            )}
          </div>
          
          <div className="max-h-96 overflow-y-auto">
            {displayHoldings.map((holding, idx) => (
              <div 
                key={idx} 
                className={`grid ${hasExtendedData ? 'grid-cols-16' : 'grid-cols-12'} gap-2 px-4 py-3 text-sm ${
                  idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'
                } hover:bg-blue-50 transition-colors border-b border-slate-100`}
              >
                <div className="col-span-1 text-slate-600 font-medium">#{idx + 1}</div>
                <div className="col-span-2 font-mono font-bold text-slate-900">{holding.ticker}</div>
                <div className="col-span-2 text-right font-medium text-blue-600">
                  {typeof holding.weight === 'number' ? holding.weight.toFixed(2) : holding.weight}%
                </div>
                {hasExtendedData && (
                  <>
                    <div className={`col-span-2 text-right font-medium ${
                      holding.sma50 > 0 ? 'text-emerald-600' : holding.sma50 < 0 ? 'text-red-600' : 'text-slate-400'
                    }`}>
                      {holding.sma50 !== null && holding.sma50 !== undefined 
                        ? `${holding.sma50 > 0 ? '+' : ''}${holding.sma50.toFixed(2)}%` 
                        : '-'}
                    </div>
                    <div className={`col-span-2 text-right font-medium ${
                      holding.sma200 > 0 ? 'text-emerald-600' : holding.sma200 < 0 ? 'text-red-600' : 'text-slate-400'
                    }`}>
                      {holding.sma200 !== null && holding.sma200 !== undefined 
                        ? `${holding.sma200 > 0 ? '+' : ''}${holding.sma200.toFixed(2)}%` 
                        : '-'}
                    </div>
                    <div className={`col-span-2 text-right font-medium ${
                      holding.rsi > 70 ? 'text-red-600' : holding.rsi < 30 ? 'text-emerald-600' : 'text-slate-600'
                    }`}>
                      {holding.rsi !== null && holding.rsi !== undefined 
                        ? holding.rsi.toFixed(1) 
                        : '-'}
                    </div>
                    <div className={`col-span-2 text-right font-medium ${
                      holding.positioning_score > 60 ? 'text-emerald-600' : 
                      holding.positioning_score < 40 ? 'text-red-600' : 'text-amber-600'
                    }`}>
                      {holding.positioning_score !== null && holding.positioning_score !== undefined 
                        ? holding.positioning_score.toFixed(0) 
                        : '-'}
                    </div>
                    <div className={`col-span-2 text-right font-medium ${
                      holding.term_score > 0 ? 'text-red-600' : 
                      holding.term_score < 0 ? 'text-emerald-600' : 'text-slate-600'
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
          
          {holdings.length > maxDisplay && (
            <div className="px-4 py-3 bg-slate-100 border-t border-slate-200">
              <button
                onClick={() => setExpandedHoldings(prev => ({ ...prev, [etfSymbol]: !prev[etfSymbol] }))}
                className="w-full flex items-center justify-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    收起
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    显示更多 ({holdings.length - maxDisplay} 条)
                  </>
                )}
              </button>
            </div>
          )}
        </div>
        
        {/* 图例说明 */}
        {hasExtendedData && (
          <div className="mt-3 text-xs text-slate-500 flex gap-4 flex-wrap">
            <span>📊 50DMA/200DMA: 相对均线距离</span>
            <span>🎯 Position: 定位评分 (Call/Put)</span>
            <span>📈 Term: 期限结构 (IV30-HV20)</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 text-slate-900 p-4">
      {/* 顶部导航 */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
            <Terminal className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">强势动能交易系统</h1>
            <p className="text-sm text-slate-600">Momentum Trading System</p>
          </div>
        </div>
        
        <div className="flex gap-2 bg-white p-1 rounded-xl border border-slate-200 shadow-sm flex-wrap">
          {[
            { id: 'terminal', label: '核心终端' },
            { id: 'sector-etf', label: '板块 ETF' },
            { id: 'industry-etf', label: '行业 ETF' },
            { id: 'momentum-stocks', label: '动能股池' },
            { id: 'data-config', label: '数据配置中心' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 shadow-xl flex items-center gap-3">
            <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
            <span className="text-slate-700">加载中...</span>
          </div>
        </div>
      )}

      {/* 核心终端界面 */}
      {activeTab === 'terminal' && (
        <TerminalView 
          marketRegime={marketRegime}
          sectorETFs={sectorETFs}
          industryETFs={industryETFs}
          momentumStocks={momentumStocks}
          refreshingETF={refreshingETF}
          handleRefreshETF={handleRefreshETF}
          getRegimeColor={getRegimeColor}
          getRegimeText={getRegimeText}
          getScoreColor={getScoreColor}
        />
      )}

      {/* 板块ETF界面 */}
      {activeTab === 'sector-etf' && (
        <SectorETFView
          sectorETFs={sectorETFs}
          refreshingETF={refreshingETF}
          handleRefreshETF={handleRefreshETF}
          HoldingsTable={HoldingsTable}
          getScoreColor={getScoreColor}
          getScoreBg={getScoreBg}
          getOptionsHeatColor={getOptionsHeatColor}
        />
      )}

      {/* 行业ETF界面 */}
      {activeTab === 'industry-etf' && (
        <IndustryETFView
          industryETFs={industryETFs}
          refreshingETF={refreshingETF}
          handleRefreshETF={handleRefreshETF}
          HoldingsTable={HoldingsTable}
          getScoreColor={getScoreColor}
          getScoreBg={getScoreBg}
          getOptionsHeatColor={getOptionsHeatColor}
        />
      )}

      {/* 动能股池界面 */}
      {activeTab === 'momentum-stocks' && (
        <MomentumStocksView
          momentumStocks={momentumStocks}
          getScoreColor={getScoreColor}
          getScoreBg={getScoreBg}
          getOptionsHeatColor={getOptionsHeatColor}
          getHeatLevelColor={getHeatLevelColor}
        />
      )}

      {/* 数据配置中心界面 */}
      {activeTab === 'data-config' && (
        <DataConfigCenter />
      )}
    </div>
  );
};

export default App;
