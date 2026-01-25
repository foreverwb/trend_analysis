import React from 'react';
import { X } from 'lucide-react';

/**
 * 覆盖范围标签组件
 * @param {string} value - 覆盖范围值，如 'top15', 'weight80'
 * @param {string} label - 显示文本
 * @param {'quantity' | 'weight'} type - 类型（可选，自动推断）
 * @param {boolean} removable - 是否显示删除按钮
 * @param {function} onRemove - 删除回调
 * @param {'sm' | 'md'} size - 尺寸
 */
const CoverageTag = ({ 
  value, 
  label, 
  type, 
  removable = false, 
  onRemove,
  size = 'sm'
}) => {
  // 自动推断类型
  const tagType = type || (value?.startsWith('weight') ? 'weight' : 'quantity');
  const isQuantity = tagType === 'quantity';
  
  const sizeClasses = {
    sm: 'px-2.5 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm'
  };
  
  return (
    <span 
      className={`
        inline-flex items-center gap-1 rounded-full font-medium
        ${sizeClasses[size]}
        ${isQuantity 
          ? 'bg-blue-100 text-blue-700' 
          : 'bg-amber-100 text-amber-700'
        }
      `}
    >
      {label}
      {removable && (
        <button 
          onClick={onRemove} 
          className="ml-0.5 hover:opacity-70 transition-opacity"
          aria-label={`移除 ${label}`}
        >
          <X size={size === 'sm' ? 12 : 14} />
        </button>
      )}
    </span>
  );
};

export default CoverageTag;
