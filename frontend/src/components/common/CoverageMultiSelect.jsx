import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import CoverageTag from './CoverageTag';

/**
 * 覆盖范围多选组件
 * @param {string[]} value - 已选择的值数组
 * @param {function} onChange - 变更回调
 * @param {object} options - 选项配置 { quantity_based: [], weight_based: [] }
 * @param {string} placeholder - 占位文本
 */
const CoverageMultiSelect = ({
  value = [],
  onChange,
  options = { quantity_based: [], weight_based: [] },
  placeholder = '选择覆盖范围...'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleOption = (optValue) => {
    const newValue = value.includes(optValue)
      ? value.filter(v => v !== optValue)
      : [...value, optValue];
    onChange(newValue);
  };

  const getLabel = (optValue) => {
    const allOptions = [...(options.quantity_based || []), ...(options.weight_based || [])];
    return allOptions.find(o => o.value === optValue)?.label || optValue;
  };

  const getType = (optValue) => {
    return (options.quantity_based || []).some(o => o.value === optValue) ? 'quantity' : 'weight';
  };

  return (
    <div ref={containerRef} className="relative">
      {/* 触发按钮 */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full border border-gray-200 rounded-xl px-4 py-3 text-left bg-gray-50
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          flex items-center justify-between"
      >
        <span className="text-gray-500">{placeholder}</span>
        <ChevronDown 
          className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          size={18} 
        />
      </button>

      {/* 下拉面板 */}
      {isOpen && (
        <div className="absolute z-20 w-full mt-2 bg-white rounded-xl shadow-2xl border border-gray-100 p-4">
          {/* 数量型 */}
          {(options.quantity_based || []).length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                数量型
              </p>
              <div className="flex flex-wrap gap-2">
                {(options.quantity_based || []).filter(opt => opt.enabled !== false).map(opt => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleOption(opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-all
                      ${value.includes(opt.value)
                        ? 'bg-blue-500 text-white shadow-md'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                  >
                    {value.includes(opt.value) && <Check size={12} className="inline mr-1" />}
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 权重型 */}
          {(options.weight_based || []).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                权重型
              </p>
              <div className="flex flex-wrap gap-2">
                {(options.weight_based || []).filter(opt => opt.enabled !== false).map(opt => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleOption(opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-all
                      ${value.includes(opt.value)
                        ? 'bg-amber-500 text-white shadow-md'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                  >
                    {value.includes(opt.value) && <Check size={12} className="inline mr-1" />}
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 已选择标签展示 */}
      {value.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap mt-3">
          <span className="text-sm text-gray-500">已选择:</span>
          {value.map(v => (
            <CoverageTag
              key={v}
              value={v}
              label={getLabel(v)}
              type={getType(v)}
              removable
              onRemove={() => toggleOption(v)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CoverageMultiSelect;
