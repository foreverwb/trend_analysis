import React from 'react';
import { Target, Activity, TrendingUp, BarChart2, Flame, CheckCircle, Clock, AlertCircle } from 'lucide-react';

const IndustryETFView = ({
  industryETFs,
  refreshingETF,
  handleRefreshETF,
  HoldingsTable,
  getScoreColor,
  getScoreBg,
  getOptionsHeatColor
}) => {
  // 数据状态徽章组件
  const DataStatusBadge = ({ etf }) => {
    const hasData = etf.holdings && etf.holdings.length > 0;
    const isRecent = etf.updated_at && 
      (new Date() - new Date(etf.updated_at)) < 24 * 60 * 60 * 1000;
    
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <Target className="w-5 h-5 text-purple-600" />
          <h2 className="text-xl font-bold text-slate-900">行业 ETF 分析矩阵</h2>
          <span className="text-sm text-slate-600">共 {industryETFs.length} 个行业</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-500">
            💡 请在「数据配置中心」统一更新数据
          </div>
          <div className="text-sm text-slate-600">
            {industryETFs[0]?.updated_at 
              ? `更新于 ${new Date(industryETFs[0].updated_at).toLocaleString()}`
              : '数据待更新'
            }
          </div>
        </div>
      </div>

      {industryETFs.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 border border-slate-200 shadow-lg text-center">
          <Target className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无数据</h3>
          <p className="text-sm text-slate-500">请先在「数据配置中心」导入行业 ETF holdings 数据</p>
        </div>
      ) : (
        industryETFs.map((etf, idx) => (
          <div key={etf.symbol} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg hover:border-purple-300 hover:shadow-xl transition-all">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center text-white shadow-md">
                  <span className="text-xl font-bold">{idx + 1}</span>
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-2xl font-bold text-slate-900">{etf.symbol}</h3>
                    <span className="text-slate-600">{etf.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-slate-500">Industry ETF</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-blue-600">所属板块: {etf.sector}</span>
                    <span className="text-slate-500">({etf.sectorName})</span>
                    {etf.holdings && (
                      <>
                        <span className="text-slate-400">•</span>
                        <span className="text-xs text-slate-400">
                          数据覆盖: {etf.holdings.length} 个持仓
                        </span>
                      </>
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

            <HoldingsTable holdings={etf.holdings || []} maxDisplay={10} etfSymbol={etf.symbol} />
          </div>
        ))
      )}
    </div>
  );
};

export default IndustryETFView;
