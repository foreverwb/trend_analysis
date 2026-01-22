import React, { useState } from 'react';
import { Flame, BarChart2, TrendingUp, RefreshCw } from 'lucide-react';

const TerminalView = ({
  marketRegime,
  sectorETFs,
  industryETFs,
  momentumStocks,
  refreshingETF,
  handleRefreshETF,
  getRegimeColor,
  getRegimeText,
  getScoreColor
}) => {
  const [selectedSector, setSelectedSector] = useState('XLK');

  // 从 sectorETFs 获取数据，或使用默认数据
  const sectors = sectorETFs.length > 0 ? sectorETFs.map(etf => ({
    code: etf.symbol,
    name: etf.name,
    score: etf.compositeScore || 0,
    momentum: etf.relMomentum?.value || '+0.0%',
    heat: (etf.optionsConfirm?.score || 0) > 80 ? 'high' : (etf.optionsConfirm?.score || 0) > 60 ? 'medium' : 'low'
  })) : [
    { code: 'XLK', name: '科技板块', score: 0, momentum: '+0.0%', heat: 'low' },
    { code: 'XLC', name: '通信服务', score: 0, momentum: '+0.0%', heat: 'low' },
    { code: 'XLY', name: '非必需消费', score: 0, momentum: '+0.0%', heat: 'low' },
    { code: 'XLP', name: '必需消费', score: 0, momentum: '+0.0%', heat: 'low' },
    { code: 'XLV', name: '医疗保健', score: 0, momentum: '+0.0%', heat: 'low' },
    { code: 'XLF', name: '金融板块', score: 0, momentum: '+0.0%', heat: 'low' },
  ];

  // 获取选中的板块数据
  const selectedSectorData = sectorETFs.find(s => s.symbol === selectedSector) || {
    symbol: selectedSector,
    name: sectors.find(s => s.code === selectedSector)?.name || '板块',
    compositeScore: 0,
    relMomentum: { score: 0, value: '+0.0%' },
    trendQuality: { score: 0, structure: 'N/A', slope: '0' },
    breadth: { score: 0, above50ma: '0%', above200ma: '0%' },
    optionsConfirm: { score: 0, heat: 'N/A', relVol: '0x', ivr: 0 }
  };

  // 从 industryETFs 获取子行业数据
  const industries = industryETFs.slice(0, 3).map(ind => ({
    name: ind.symbol,
    fullName: ind.name,
    relVol: ind.optionsConfirm?.relVol || '1.0x',
    ivr: ind.optionsConfirm?.ivr || 0,
    change: ind.relMomentum?.value || '+0.0%'
  }));

  const getHeatColor = (heat) => {
    if (heat === 'high') return 'text-red-600';
    if (heat === 'medium') return 'text-amber-600';
    return 'text-slate-500';
  };

  return (
    <div>
      {/* Market Regime Banner */}
      <div className={`mb-6 p-6 rounded-2xl bg-gradient-to-r ${getRegimeColor(marketRegime.status)} shadow-xl text-white`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-white/30 rounded-xl flex items-center justify-center backdrop-blur-sm">
              <span className="text-3xl font-bold">{marketRegime.status}</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold mb-1">{getRegimeText(marketRegime.status)}</h2>
              <p className="text-white/90 text-sm">市场环境评估 · 今日更新</p>
            </div>
          </div>
          
          <div className="flex gap-8">
            <div className="text-center">
              <div className="text-sm text-white/80 mb-1">SPY vs 200MA</div>
              <div className="text-2xl font-bold">{marketRegime.spy?.vs200ma || '+0.0%'}</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-white/80 mb-1">VIX</div>
              <div className="text-2xl font-bold">{marketRegime.vix || 0}</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-white/80 mb-1">市场广度</div>
              <div className="text-2xl font-bold">{marketRegime.breadth || 50}%</div>
            </div>
            
            <button
              onClick={() => handleRefreshETF('MARKET')}
              disabled={refreshingETF === 'MARKET'}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshingETF === 'MARKET' ? 'animate-spin' : ''}`} />
              <span className="text-sm font-medium">刷新</span>
            </button>
          </div>
        </div>
      </div>

      {/* 主体内容：两栏布局 */}
      <div className="grid grid-cols-12 gap-6">
        {/* 左侧：板块热力榜 */}
        <div className="col-span-3">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg">
            <div className="flex items-center gap-2 mb-6">
              <Flame className="w-5 h-5 text-orange-600" />
              <h3 className="text-lg font-bold text-slate-900">板块热力榜</h3>
            </div>
            
            <div className="space-y-3">
              {sectors.slice(0, 6).map((sector, idx) => (
                <div
                  key={sector.code}
                  onClick={() => setSelectedSector(sector.code)}
                  className={`p-4 rounded-xl cursor-pointer transition-all ${
                    selectedSector === sector.code
                      ? 'bg-gradient-to-r from-blue-100 to-purple-100 border border-blue-300 shadow-md'
                      : 'bg-slate-50 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs text-white ${
                        idx < 3 ? 'bg-gradient-to-br from-orange-500 to-red-600' : 'bg-slate-400'
                      }`}>
                        {idx + 1}
                      </div>
                      <div>
                        <div className="font-bold text-sm text-slate-900">{sector.code}</div>
                        <div className="text-xs text-slate-600">{sector.name}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-lg font-bold ${getScoreColor(sector.score)}`}>{sector.score}</div>
                      <div className="text-xs text-emerald-600">{sector.momentum}</div>
                    </div>
                  </div>
                  
                  <div className="mt-2 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-emerald-500 to-blue-500 rounded-full transition-all"
                      style={{ width: `${Math.min(sector.score, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：选中板块详情 */}
        <div className="col-span-9">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-6 h-6 text-blue-600" />
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">
                    {selectedSectorData.symbol} - {selectedSectorData.name}
                  </h2>
                </div>
              </div>
              <div className={`px-6 py-3 rounded-xl border ${
                selectedSectorData.compositeScore >= 85 ? 'bg-emerald-50 border-emerald-200' :
                selectedSectorData.compositeScore >= 70 ? 'bg-blue-50 border-blue-200' :
                selectedSectorData.compositeScore >= 60 ? 'bg-amber-50 border-amber-200' :
                'bg-slate-50 border-slate-200'
              }`}>
                <div className={`text-3xl font-bold ${getScoreColor(selectedSectorData.compositeScore)}`}>
                  {selectedSectorData.compositeScore || 0}
                </div>
              </div>
            </div>

            {/* 四个指标卡片 */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="text-xs text-slate-600 mb-2">相对动量</div>
                <div className={`text-2xl font-bold ${getScoreColor(selectedSectorData.relMomentum?.score || 0)}`}>
                  {selectedSectorData.relMomentum?.score || 0}
                </div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="text-xs text-slate-600 mb-2">趋势质量</div>
                <div className={`text-2xl font-bold ${getScoreColor(selectedSectorData.trendQuality?.score || 0)}`}>
                  {selectedSectorData.trendQuality?.score || 0}
                </div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="text-xs text-slate-600 mb-2">广度</div>
                <div className={`text-2xl font-bold ${getScoreColor(selectedSectorData.breadth?.score || 0)}`}>
                  {selectedSectorData.breadth?.score || 0}
                </div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="text-xs text-slate-600 mb-2">期权热度</div>
                <div className={`text-2xl font-bold ${getScoreColor(selectedSectorData.optionsConfirm?.score || 0)}`}>
                  {selectedSectorData.optionsConfirm?.score || 0}
                </div>
              </div>
            </div>

            {/* 子行业强度排名 */}
            <div>
              <h4 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-blue-600" />
                子行业强度排名
              </h4>
              <div className="space-y-2">
                {industries.length > 0 ? industries.map((ind, idx) => (
                  <div key={ind.name} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-all border border-slate-200">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center font-bold text-sm text-white shadow">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">{ind.name}</span>
                        <span className="text-xs text-slate-600">{ind.fullName}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-slate-600">
                        <span>相对成交: <span className="text-blue-600 font-medium">{ind.relVol}</span></span>
                        <span>IVR: <span className="text-purple-600 font-medium">{ind.ivr}</span></span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-emerald-600">{ind.change}</div>
                      <div className="text-xs text-slate-600">20D涨幅</div>
                    </div>
                  </div>
                )) : (
                  <div className="text-center py-8 text-slate-500">
                    暂无子行业数据
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TerminalView;
