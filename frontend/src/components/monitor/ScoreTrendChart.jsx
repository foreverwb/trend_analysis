import React, { useState, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, ComposedChart, Bar
} from 'recharts';
import { Calendar, TrendingUp, Filter, Download, Layers, ChevronDown } from 'lucide-react';
import { useCoverageOptions } from '../../hooks/useCoverageOptions';

// 时间范围选项
const TIME_RANGES = [
  { id: '7d', label: '7天', days: 7 },
  { id: '14d', label: '14天', days: 14 },
  { id: '30d', label: '30天', days: 30 },
  { id: '90d', label: '90天', days: 90 }
];

// 显示模式
const VIEW_MODES = [
  { id: 'score', label: '评分趋势' },
  { id: 'rank', label: '排名变化' },
  { id: 'delta', label: 'Delta对比' }
];

// ETF 颜色映射
const ETF_COLORS = [
  '#3B82F6', // blue
  '#10B981', // green
  '#F59E0B', // amber
  '#EF4444', // red
  '#8B5CF6', // purple
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
  '#84CC16', // lime
  '#6366F1'  // indigo
];

// 自定义 Tooltip
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
      <p className="text-sm font-medium text-gray-700 mb-2">{label}</p>
      <div className="space-y-1">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center justify-between gap-4">
            <span className="flex items-center">
              <span 
                className="w-3 h-3 rounded-full mr-2"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-sm text-gray-600">{entry.name}</span>
            </span>
            <span className="text-sm font-medium" style={{ color: entry.color }}>
              {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// 格式化日期
const formatDate = (dateStr) => {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
};

const ScoreTrendChart = ({ 
  taskId,
  scoreHistory = [],
  etfList = [],
  selectedETFs,
  onETFSelectionChange,
  coverageTypes = [],
  height = 400
}) => {
  const [timeRange, setTimeRange] = useState('14d');
  const [viewMode, setViewMode] = useState('score');
  const [selectedCoverage, setSelectedCoverage] = useState('all');
  const [showCoverageDropdown, setShowCoverageDropdown] = useState(false);
  
  // 获取覆盖范围标签
  const { getLabel: getCoverageLabel } = useCoverageOptions();

  // 过滤和处理数据
  const chartData = useMemo(() => {
    if (!scoreHistory || scoreHistory.length === 0) return [];

    const days = TIME_RANGES.find(r => r.id === timeRange)?.days || 14;
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    // 按日期分组数据
    const groupedByDate = {};
    
    scoreHistory
      .filter(item => {
        // 时间范围过滤
        if (new Date(item.snapshot_date) < cutoffDate) return false;
        
        // 覆盖范围过滤
        if (selectedCoverage !== 'all' && item.coverage_type && item.coverage_type !== selectedCoverage) {
          return false;
        }
        
        return true;
      })
      .forEach(item => {
        const date = item.snapshot_date;
        if (!groupedByDate[date]) {
          groupedByDate[date] = { date };
        }
        
        const symbol = item.etf_symbol;
        if (!selectedETFs || selectedETFs.includes(symbol)) {
          switch (viewMode) {
            case 'score':
              groupedByDate[date][symbol] = item.overall_score;
              break;
            case 'rank':
              groupedByDate[date][symbol] = item.rank_in_task;
              break;
            case 'delta':
              groupedByDate[date][`${symbol}_3d`] = item.delta_3d;
              groupedByDate[date][`${symbol}_5d`] = item.delta_5d;
              break;
          }
        }
      });

    return Object.values(groupedByDate).sort((a, b) => 
      new Date(a.date) - new Date(b.date)
    );
  }, [scoreHistory, timeRange, viewMode, selectedETFs, selectedCoverage]);

  // 获取当前选中的 ETF 列表
  const activeETFs = useMemo(() => {
    if (selectedETFs && selectedETFs.length > 0) {
      return etfList.filter(etf => selectedETFs.includes(etf.symbol));
    }
    return etfList.slice(0, 5); // 默认显示前5个
  }, [etfList, selectedETFs]);

  // 渲染评分趋势图
  const renderScoreChart = () => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
        <XAxis 
          dataKey="date" 
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
        />
        <YAxis 
          domain={[0, 100]}
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <ReferenceLine y={50} stroke="#D1D5DB" strokeDasharray="3 3" />
        
        {activeETFs.map((etf, index) => (
          <Line
            key={etf.symbol}
            type="monotone"
            dataKey={etf.symbol}
            name={etf.symbol}
            stroke={ETF_COLORS[index % ETF_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );

  // 渲染排名变化图
  const renderRankChart = () => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
        <XAxis 
          dataKey="date" 
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
        />
        <YAxis 
          reversed
          domain={[1, 'dataMax']}
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
          label={{ value: '排名', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        
        {activeETFs.map((etf, index) => (
          <Line
            key={etf.symbol}
            type="stepAfter"
            dataKey={etf.symbol}
            name={etf.symbol}
            stroke={ETF_COLORS[index % ETF_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );

  // 渲染 Delta 对比图
  const renderDeltaChart = () => (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
        <XAxis 
          dataKey="date" 
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
        />
        <YAxis 
          tick={{ fontSize: 12 }}
          stroke="#9CA3AF"
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <ReferenceLine y={0} stroke="#D1D5DB" />
        
        {activeETFs.map((etf, index) => (
          <React.Fragment key={etf.symbol}>
            <Bar
              dataKey={`${etf.symbol}_3d`}
              name={`${etf.symbol} Δ3D`}
              fill={ETF_COLORS[index % ETF_COLORS.length]}
              fillOpacity={0.6}
            />
            <Line
              type="monotone"
              dataKey={`${etf.symbol}_5d`}
              name={`${etf.symbol} Δ5D`}
              stroke={ETF_COLORS[index % ETF_COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          </React.Fragment>
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );

  // 渲染空状态
  if (!chartData || chartData.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
        <TrendingUp className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">暂无评分历史数据</p>
        <p className="text-sm text-gray-400 mt-1">完成数据导入后将显示趋势图表</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* 头部控制栏 */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* 视图模式切换 */}
          <div className="flex items-center gap-2">
            {VIEW_MODES.map(mode => (
              <button
                key={mode.id}
                onClick={() => setViewMode(mode.id)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors
                  ${viewMode === mode.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                {mode.label}
              </button>
            ))}
          </div>

          {/* 时间范围选择 */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            {TIME_RANGES.map(range => (
              <button
                key={range.id}
                onClick={() => setTimeRange(range.id)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors
                  ${timeRange === range.id
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                {range.label}
              </button>
            ))}
          </div>

          {/* 覆盖范围筛选 */}
          {coverageTypes.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowCoverageDropdown(!showCoverageDropdown)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
              >
                <Layers className="w-4 h-4" />
                <span>
                  {selectedCoverage === 'all' 
                    ? '全部覆盖范围' 
                    : getCoverageLabel(selectedCoverage)}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showCoverageDropdown ? 'rotate-180' : ''}`} />
              </button>
              
              {showCoverageDropdown && (
                <>
                  <div 
                    className="fixed inset-0 z-10"
                    onClick={() => setShowCoverageDropdown(false)}
                  />
                  <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20">
                    <button
                      onClick={() => {
                        setSelectedCoverage('all');
                        setShowCoverageDropdown(false);
                      }}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 transition-colors
                        ${selectedCoverage === 'all' ? 'text-blue-600 bg-blue-50' : 'text-gray-700'}`}
                    >
                      全部覆盖范围
                    </button>
                    {coverageTypes.map(type => (
                      <button
                        key={type}
                        onClick={() => {
                          setSelectedCoverage(type);
                          setShowCoverageDropdown(false);
                        }}
                        className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 transition-colors
                          ${selectedCoverage === type ? 'text-blue-600 bg-blue-50' : 'text-gray-700'}`}
                      >
                        {getCoverageLabel(type)}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* ETF 筛选 */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-500 flex items-center">
            <Filter className="w-4 h-4 mr-1" />
            显示:
          </span>
          {etfList.map((etf, index) => {
            const isSelected = !selectedETFs || selectedETFs.includes(etf.symbol);
            return (
              <button
                key={etf.symbol}
                onClick={() => {
                  if (onETFSelectionChange) {
                    const newSelection = isSelected
                      ? (selectedETFs || etfList.map(e => e.symbol)).filter(s => s !== etf.symbol)
                      : [...(selectedETFs || []), etf.symbol];
                    onETFSelectionChange(newSelection);
                  }
                }}
                className={`px-2 py-1 rounded text-xs transition-colors flex items-center
                  ${isSelected
                    ? 'text-white'
                    : 'bg-gray-100 text-gray-400'}`}
                style={isSelected ? { backgroundColor: ETF_COLORS[index % ETF_COLORS.length] } : {}}
              >
                <span 
                  className="w-2 h-2 rounded-full mr-1"
                  style={{ backgroundColor: ETF_COLORS[index % ETF_COLORS.length] }}
                />
                {etf.symbol}
              </button>
            );
          })}
        </div>
      </div>

      {/* 图表区域 */}
      <div className="p-4">
        {viewMode === 'score' && renderScoreChart()}
        {viewMode === 'rank' && renderRankChart()}
        {viewMode === 'delta' && renderDeltaChart()}
      </div>

      {/* 图例说明 */}
      <div className="px-4 pb-4">
        <p className="text-xs text-gray-400 text-center">
          {viewMode === 'score' && '评分范围 0-100，数值越高表示相对强度越强'}
          {viewMode === 'rank' && '排名越小表示表现越好，数字 1 代表第一名'}
          {viewMode === 'delta' && 'Δ3D/Δ5D 表示相对于 3/5 个交易日前的评分变化'}
        </p>
      </div>
    </div>
  );
};

export default ScoreTrendChart;
