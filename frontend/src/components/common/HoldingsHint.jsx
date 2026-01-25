import React, { useState, useMemo } from 'react';
import { Info, Copy, CheckCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

/**
 * 持仓标的提示组件
 * @param {Array} holdings - 持仓数组 [{symbol, name, weight}, ...]
 * @param {number} totalWeight - 累计权重
 * @param {string} coverageLabel - 覆盖范围标签文本
 * @param {object} dataSourceLinks - 数据源快捷链接配置
 */
const HoldingsHint = ({ 
  holdings = [], 
  totalWeight = 0,
  coverageLabel,
  dataSourceLinks = {
    finviz: { name: 'Finviz Screener', url: 'https://finviz.com/screener.ashx' },
    marketChameleon: { name: 'MarketChameleon', url: 'https://marketchameleon.com' }
  }
}) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const symbols = useMemo(() => holdings.map(h => h.symbol), [holdings]);
  
  // 默认显示前5个
  const PREVIEW_COUNT = 5;
  const previewSymbols = symbols.slice(0, PREVIEW_COUNT);
  const hasMore = symbols.length > PREVIEW_COUNT;

  // 复制所有代码
  const handleCopy = async () => {
    const text = symbols.join(', ');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('复制失败:', err);
    }
  };

  if (holdings.length === 0) {
    return (
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
        <div className="flex items-center gap-2 text-gray-500">
          <Info size={16} />
          <span className="text-sm">暂无持仓数据</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
      {/* 主信息行 */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <Info className="text-blue-500 flex-shrink-0" size={16} />
            <span className="text-sm text-blue-700">
              需收集 <strong className="text-blue-800">{symbols.length}</strong> 只持仓标的数据
            </span>
            <span className="text-xs text-blue-500 bg-blue-100 px-2 py-0.5 rounded-full">
              累计权重 {totalWeight.toFixed(1)}%
            </span>
          </div>
          
          {/* 复制按钮 */}
          <button
            onClick={handleCopy}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium 
              transition-all flex-shrink-0
              ${copied 
                ? 'bg-green-100 text-green-700' 
                : 'bg-white text-blue-600 hover:bg-blue-100 border border-blue-200'
              }
            `}
          >
            {copied ? <CheckCircle size={14} /> : <Copy size={14} />}
            {copied ? '已复制' : '复制代码'}
          </button>
        </div>

        {/* 代码预览行 */}
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-sm text-gray-700 font-mono">
            {previewSymbols.map((symbol, i) => (
              <span key={symbol}>
                <span className="font-semibold">{symbol}</span>
                {i < previewSymbols.length - 1 && (
                  <span className="text-gray-400">,</span>
                )}
              </span>
            ))}
            {hasMore && (
              <span className="text-blue-600">
                ... 等 {symbols.length} 只
              </span>
            )}
          </div>
          
          {/* 展开/收起按钮 */}
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 ml-2"
            >
              {expanded ? (
                <>收起 <ChevronUp size={14} /></>
              ) : (
                <>查看全部 <ChevronDown size={14} /></>
              )}
            </button>
          )}
        </div>
      </div>

      {/* 展开的完整列表 */}
      {expanded && (
        <div className="px-4 pb-4 pt-0">
          <div className="bg-white rounded-lg p-3 border border-blue-100 max-h-32 overflow-y-auto">
            <div className="text-sm font-mono text-gray-700 leading-relaxed break-all">
              {symbols.join(', ')}
            </div>
          </div>
        </div>
      )}

      {/* 快捷链接 */}
      <div className="px-4 py-3 border-t border-blue-100 bg-blue-50/50 rounded-b-xl flex items-center gap-4 flex-wrap">
        <span className="text-xs text-blue-600">快速访问:</span>
        {Object.entries(dataSourceLinks).map(([key, link]) => (
          <a 
            key={key}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 hover:underline"
          >
            <ExternalLink size={12} />
            {link.name}
          </a>
        ))}
      </div>
    </div>
  );
};

export default HoldingsHint;
