import React from 'react';
import { Zap, Activity, TrendingUp, BarChart2, AlertCircle, Flame } from 'lucide-react';

const MomentumStocksView = ({
  momentumStocks,
  getScoreColor,
  getScoreBg,
  getOptionsHeatColor,
  getHeatLevelColor
}) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <Zap className="w-5 h-5 text-yellow-600" />
          <h2 className="text-xl font-bold text-slate-900">行业内动能股详细分析</h2>
          <span className="text-sm text-slate-600">共 {momentumStocks.length} 只股票</span>
        </div>
        <div className="flex items-center gap-4">
          <select className="px-4 py-2 bg-white border border-slate-300 rounded-xl text-slate-900 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200">
            <option>全部行业</option>
            <option>SOXX - 半导体</option>
            <option>IGV - 软件</option>
            <option>SMH - 半导体设备</option>
          </select>
          <div className="text-sm text-slate-600">实时更新</div>
        </div>
      </div>

      {momentumStocks.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 border border-slate-200 shadow-lg text-center">
          <Zap className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无数据</h3>
          <p className="text-sm text-slate-500">请先刷新行业 ETF 或上传数据后计算动能股评分</p>
        </div>
      ) : (
        momentumStocks.map((stock, idx) => (
          <div key={stock.symbol} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg hover:border-yellow-300 hover:shadow-xl transition-all">
            {/* 股票头部信息 */}
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-gradient-to-br from-yellow-500 to-orange-600 rounded-xl flex items-center justify-center text-white shadow-md">
                  <span className="text-xl font-bold">{idx + 1}</span>
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-2xl font-bold text-slate-900">{stock.symbol}</h3>
                    <span className="text-slate-600">{stock.name}</span>
                    {stock.priceMomentum?.breakoutTrigger && (
                      <span className="px-3 py-1 bg-red-100 text-red-700 border border-red-300 rounded-lg text-sm font-medium flex items-center gap-1">
                        <TrendingUp className="w-4 h-4" />
                        突破触发
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-slate-500">板块: {stock.sector}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-blue-600">行业: {stock.industry}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-emerald-600 font-medium">价格: ${stock.price || 0}</span>
                  </div>
                </div>
              </div>
              
              {/* 综合得分 */}
              <div className={`px-6 py-3 rounded-xl border ${getScoreBg(stock.finalScore || 0)}`}>
                <div className="text-xs text-slate-600 mb-1">综合得分</div>
                <div className={`text-4xl font-bold ${getScoreColor(stock.finalScore || 0)}`}>
                  {stock.finalScore || 0}
                </div>
              </div>
            </div>

            {/* Delta indicators */}
            {(stock.delta_3d || stock.delta_5d) && (
              <div className="mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-xs text-slate-500 mb-2">变化指标</div>
                <div className="flex gap-6 text-sm">
                  {stock.delta_3d?.final_score !== null && (
                    <span>
                      3D Δ Score: <span className={stock.delta_3d.final_score >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                        {stock.delta_3d.final_score >= 0 ? '+' : ''}{stock.delta_3d.final_score}
                      </span>
                    </span>
                  )}
                  {stock.delta_5d?.final_score !== null && (
                    <span>
                      5D Δ Score: <span className={stock.delta_5d.final_score >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                        {stock.delta_5d.final_score >= 0 ? '+' : ''}{stock.delta_5d.final_score}
                      </span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* 五大模块评分 */}
            <div className="grid grid-cols-5 gap-4">
              {/* 模块1：价格动能 */}
              <div className="col-span-2 bg-blue-50 rounded-xl p-5 border border-blue-200">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-blue-900 flex items-center gap-2">
                    <Activity className="w-4 h-4" />
                    价格动能 (主要权重)
                  </h4>
                  <span className={`text-2xl font-bold ${getScoreColor(stock.priceMomentum?.score || 0)}`}>
                    {stock.priceMomentum?.score || 0}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">20D收益</span>
                    <span className="font-bold text-emerald-600">{stock.priceMomentum?.return20d || '+0.0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">20D收益(去3日)</span>
                    <span className="font-medium text-slate-700">{stock.priceMomentum?.return20dEx3 || '+0.0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">63D收益</span>
                    <span className="font-bold text-blue-600">{stock.priceMomentum?.return63d || '+0.0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">相对行业强度</span>
                    <span className="font-bold text-purple-600">{stock.priceMomentum?.relativeToSector || 1.0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">距20日高点</span>
                    <span className="font-bold text-amber-600">{stock.priceMomentum?.nearHighDist || '0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-700">放量倍数</span>
                    <span className="font-bold text-orange-600">{stock.priceMomentum?.volumeSpike || 1.0}x</span>
                  </div>
                </div>
              </div>

              {/* 模块2：趋势结构 */}
              <div className="bg-emerald-50 rounded-xl p-5 border border-emerald-200">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-emerald-900 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    趋势结构
                  </h4>
                  <span className={`text-2xl font-bold ${getScoreColor(stock.trendStructure?.score || 0)}`}>
                    {stock.trendStructure?.score || 0}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div>
                    <div className="text-emerald-700 mb-1">均线排列</div>
                    <div className="font-bold text-emerald-600 text-xs">{stock.trendStructure?.maAlignment || 'N/A'}</div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-emerald-700">20DMA斜率</span>
                    <span className="font-bold text-blue-600">{stock.trendStructure?.slope20d || '+0.00'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-emerald-700">趋势持续度</span>
                    <span className="font-bold text-purple-600">{stock.trendStructure?.continuity || '0%'}</span>
                  </div>
                </div>
              </div>

              {/* 模块3：量价确认 */}
              <div className="bg-purple-50 rounded-xl p-5 border border-purple-200">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-purple-900 flex items-center gap-2">
                    <BarChart2 className="w-4 h-4" />
                    量价确认
                  </h4>
                  <span className={`text-2xl font-bold ${getScoreColor(stock.volumePrice?.score || 0)}`}>
                    {stock.volumePrice?.score || 0}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-purple-700">突破放量</span>
                    <span className="font-bold text-emerald-600">{stock.volumePrice?.breakoutVolRatio || 1.0}x</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-purple-700">量比结构</span>
                    <span className="font-bold text-blue-600">{stock.volumePrice?.upDownVolRatio || 1.0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-purple-700">OBV趋势</span>
                    <span className="font-medium text-slate-700">{stock.volumePrice?.obvTrend || 'Neutral'}</span>
                  </div>
                </div>
              </div>

              {/* 模块4：质量过滤 */}
              <div className="bg-amber-50 rounded-xl p-5 border border-amber-200">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-amber-900 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    质量过滤
                  </h4>
                  <span className={`text-2xl font-bold ${getScoreColor(stock.qualityFilter?.score || 0)}`}>
                    {stock.qualityFilter?.score || 0}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-amber-700">20D回撤</span>
                    <span className="font-bold text-red-600">{stock.qualityFilter?.maxDrawdown20d || '0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-amber-700">ATR%</span>
                    <span className="font-bold text-orange-600">{stock.qualityFilter?.atrPercent || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-amber-700">偏离20MA</span>
                    <span className="font-bold text-blue-600">{stock.qualityFilter?.distFrom20ma || '+0.0%'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-amber-700">过热程度</span>
                    <span className={`font-medium ${getHeatLevelColor(stock.qualityFilter?.heatLevel || 'Normal')}`}>
                      {stock.qualityFilter?.heatLevel || 'Normal'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 期权覆盖 - 单独一行 */}
            <div className="mt-4 bg-orange-50 rounded-xl p-5 border border-orange-200">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-bold text-orange-900 flex items-center gap-2">
                  <Flame className="w-4 h-4" />
                  期权覆盖 (20%权重)
                </h4>
                <span className={`text-2xl font-bold ${getScoreColor(stock.optionsOverlay?.score || 0)}`}>
                  {stock.optionsOverlay?.score || 0}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-orange-700">热度</span>
                  <span className={`font-bold ${getOptionsHeatColor(stock.optionsOverlay?.heat || 'Low')}`}>
                    {stock.optionsOverlay?.heat || 'Low'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-orange-700">相对成交</span>
                  <span className="font-bold text-blue-600">{stock.optionsOverlay?.relVol || '1.0x'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-orange-700">IVR</span>
                  <span className="font-bold text-purple-600">{stock.optionsOverlay?.ivr || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-orange-700">IV30</span>
                  <span className="font-bold text-amber-600">{stock.optionsOverlay?.iv30 || 0}</span>
                </div>
              </div>
            </div>

            {/* 权重说明 */}
            <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-600 mb-2 font-medium">评分权重分配</div>
              <div className="grid grid-cols-4 gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-500 rounded"></div>
                  <span className="text-slate-700">价格动能+趋势: <span className="font-bold">65%</span></span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-purple-500 rounded"></div>
                  <span className="text-slate-700">量价确认: <span className="font-bold">15%</span></span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded"></div>
                  <span className="text-slate-700">期权覆盖: <span className="font-bold">20%</span></span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-amber-500 rounded"></div>
                  <span className="text-slate-700">质量过滤: <span className="font-bold">降权</span></span>
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
};

export default MomentumStocksView;
