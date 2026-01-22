/**
 * Helper functions for Trend Analysis System
 */

/**
 * Get score color class based on score value
 * @param {number} score - Score value (0-100)
 * @returns {string} Tailwind color class
 */
export const getScoreColor = (score) => {
  if (score >= 85) return 'text-emerald-600';
  if (score >= 70) return 'text-blue-600';
  if (score >= 60) return 'text-amber-600';
  return 'text-slate-500';
};

/**
 * Get score background class based on score value
 * @param {number} score - Score value (0-100)
 * @returns {string} Tailwind background class
 */
export const getScoreBg = (score) => {
  if (score >= 85) return 'bg-emerald-50 border-emerald-200';
  if (score >= 70) return 'bg-blue-50 border-blue-200';
  if (score >= 60) return 'bg-amber-50 border-amber-200';
  return 'bg-slate-50 border-slate-200';
};

/**
 * Get regime color gradient based on status
 * @param {string} status - Regime status (A/B/C)
 * @returns {string} Tailwind gradient class
 */
export const getRegimeColor = (status) => {
  if (status === 'A') return 'from-emerald-400 to-green-500';
  if (status === 'B') return 'from-amber-400 to-orange-500';
  return 'from-red-400 to-rose-500';
};

/**
 * Get regime text description based on status
 * @param {string} status - Regime status (A/B/C)
 * @returns {string} Regime description text
 */
export const getRegimeText = (status) => {
  if (status === 'A') return 'Risk-On 满火力';
  if (status === 'B') return 'Neutral 半火力';
  return 'Risk-Off 低火力';
};

/**
 * Get options heat color based on heat level
 * @param {string} heat - Heat level (Very High/High/Medium/Low)
 * @returns {string} Tailwind color class
 */
export const getOptionsHeatColor = (heat) => {
  if (heat === 'Very High') return 'text-red-600';
  if (heat === 'High') return 'text-orange-600';
  if (heat === 'Medium') return 'text-amber-600';
  return 'text-slate-500';
};

/**
 * Get heat level color for quality filter
 * @param {string} level - Heat level (Hot/Slightly Hot/Moderate)
 * @returns {string} Tailwind color class
 */
export const getHeatLevelColor = (level) => {
  if (level === 'Moderate') return 'text-emerald-600';
  if (level === 'Slightly Hot') return 'text-amber-600';
  return 'text-red-600';
};

/**
 * Format percentage value
 * @param {number} value - Numeric value
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted percentage string
 */
export const formatPercent = (value, decimals = 1) => {
  if (value === null || value === undefined) return '0%';
  const num = parseFloat(value);
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}%`;
};

/**
 * Format number with thousands separator
 * @param {number} value - Numeric value
 * @returns {string} Formatted number string
 */
export const formatNumber = (value) => {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat().format(value);
};

/**
 * Format currency value
 * @param {number} value - Numeric value
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted currency string
 */
export const formatCurrency = (value, decimals = 2) => {
  if (value === null || value === undefined) return '$0.00';
  return `$${parseFloat(value).toFixed(decimals)}`;
};

/**
 * Format relative time (e.g., "5 minutes ago")
 * @param {string|Date} timestamp - Timestamp to format
 * @returns {string} Relative time string
 */
export const formatRelativeTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  
  const now = new Date();
  const date = new Date(timestamp);
  const diff = Math.floor((now - date) / 1000);
  
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
  
  return date.toLocaleDateString('zh-CN');
};

/**
 * Format datetime for display
 * @param {string|Date} timestamp - Timestamp to format
 * @returns {string} Formatted datetime string
 */
export const formatDateTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN');
};

/**
 * Validate JSON string
 * @param {string} str - String to validate
 * @returns {boolean} Whether the string is valid JSON
 */
export const isValidJSON = (str) => {
  try {
    JSON.parse(str);
    return true;
  } catch {
    return false;
  }
};

/**
 * Parse JSON safely
 * @param {string} str - String to parse
 * @param {*} fallback - Fallback value if parsing fails
 * @returns {*} Parsed value or fallback
 */
export const parseJSONSafe = (str, fallback = null) => {
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
};

/**
 * Calculate delta indicator display
 * @param {number} delta - Delta value
 * @returns {object} Object with text and color class
 */
export const formatDelta = (delta) => {
  if (delta === null || delta === undefined) {
    return { text: 'N/A', color: 'text-slate-400' };
  }
  
  const num = parseFloat(delta);
  if (num > 0) {
    return { text: `+${num.toFixed(2)}`, color: 'text-emerald-600' };
  } else if (num < 0) {
    return { text: num.toFixed(2), color: 'text-red-600' };
  }
  return { text: '0.00', color: 'text-slate-500' };
};

/**
 * Sector ETF names mapping
 */
export const SECTOR_ETF_NAMES = {
  XLK: '科技板块',
  XLC: '通信服务',
  XLY: '非必需消费',
  XLP: '必需消费',
  XLV: '医疗保健',
  XLF: '金融板块',
  XLI: '工业板块',
  XLE: '能源板块',
  XLU: '公用事业',
  XLRE: '房地产',
  XLB: '原材料'
};

/**
 * Get sector name from symbol
 * @param {string} symbol - ETF symbol
 * @returns {string} Sector name
 */
export const getSectorName = (symbol) => {
  return SECTOR_ETF_NAMES[symbol] || symbol;
};

/**
 * All ETFs list for selection
 */
export const ALL_ETFS = [
  { symbol: 'XLK', name: '科技板块', type: 'sector' },
  { symbol: 'XLE', name: '能源板块', type: 'sector' },
  { symbol: 'XLF', name: '金融板块', type: 'sector' },
  { symbol: 'XLY', name: '非必需消费', type: 'sector' },
  { symbol: 'XLI', name: '工业板块', type: 'sector' },
  { symbol: 'XLV', name: '医疗保健', type: 'sector' },
  { symbol: 'XLC', name: '通信服务', type: 'sector' },
  { symbol: 'XLP', name: '必需消费', type: 'sector' },
  { symbol: 'XLU', name: '公用事业', type: 'sector' },
  { symbol: 'XLRE', name: '房地产', type: 'sector' },
  { symbol: 'XLB', name: '原材料', type: 'sector' },
  { symbol: 'SOXX', name: '半导体', type: 'industry' },
  { symbol: 'SMH', name: '半导体设备', type: 'industry' },
  { symbol: 'IGV', name: '软件', type: 'industry' },
  { symbol: 'XOP', name: '油气勘探', type: 'industry' },
  { symbol: 'XRT', name: '零售', type: 'industry' },
  { symbol: 'KBE', name: '银行', type: 'industry' },
];

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};
