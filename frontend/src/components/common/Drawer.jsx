import React, { useEffect, useCallback } from 'react';
import { X } from 'lucide-react';

/**
 * Drawer 抽屉组件
 * @param {boolean} open - 是否打开
 * @param {function} onClose - 关闭回调
 * @param {string} title - 标题
 * @param {string} subtitle - 副标题
 * @param {number} width - 宽度，默认480
 * @param {React.ReactNode} children - 内容
 * @param {React.ReactNode} footer - 底部内容
 */
const Drawer = ({ 
  open, 
  onClose, 
  title, 
  subtitle,
  width = 480,
  children,
  footer
}) => {
  // ESC 键关闭
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && open) {
      onClose();
    }
  }, [open, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // 阻止滚动穿透
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* 遮罩层 */}
      <div 
        className="absolute inset-0 bg-black/50 transition-opacity duration-300"
        onClick={onClose}
      />
      
      {/* Drawer 面板 */}
      <div 
        className="absolute right-0 top-0 h-full bg-white shadow-2xl flex flex-col
          transform transition-transform duration-300 ease-out"
        style={{ width: `${width}px` }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div>
            <h2 className="text-xl font-bold text-gray-800">{title}</h2>
            {subtitle && (
              <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="关闭"
          >
            <X size={20} className="text-gray-400" />
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
        
        {/* Footer */}
        {footer && (
          <div className="p-6 border-t border-gray-100 bg-gray-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

export default Drawer;
