/**
 * API Client Module with Enhanced Logging
 * 强势动能交易系统 - API 客户端
 */
import axios from 'axios';

const API_BASE = '/api';

// ==================== Logging Configuration ====================
let apiLoggingEnabled = localStorage.getItem('apiLogging') === 'true';

/**
 * Enable or disable API logging
 * @param {boolean} enabled - Whether to enable logging
 */
export const setApiLogging = (enabled) => {
  apiLoggingEnabled = enabled;
  localStorage.setItem('apiLogging', enabled ? 'true' : 'false');
  console.log(`[API] Logging ${enabled ? 'enabled' : 'disabled'}`);
};

/**
 * Check if API logging is enabled
 * @returns {boolean}
 */
export const isApiLoggingEnabled = () => apiLoggingEnabled;

/**
 * Format current time for logging
 * @returns {string}
 */
const getTimestamp = () => {
  const now = new Date();
  return now.toLocaleTimeString('en-US', { hour12: false });
};

/**
 * Truncate data for logging
 * @param {any} data - Data to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string}
 */
const truncateData = (data, maxLength = 200) => {
  if (!data) return 'null';
  const str = typeof data === 'string' ? data : JSON.stringify(data);
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength) + '... (truncated)';
};

// ==================== Axios Instance ====================
const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==================== Request Interceptor ====================
api.interceptors.request.use(
  (config) => {
    // Add request timestamp
    config.metadata = { startTime: Date.now() };
    
    if (apiLoggingEnabled) {
      const method = config.method?.toUpperCase() || 'GET';
      const url = config.url || '';
      const params = config.params ? JSON.stringify(config.params) : '';
      
      console.log(
        `%c[API] ${getTimestamp()} → ${method} ${url}`,
        'color: #3B82F6; font-weight: bold'
      );
      
      if (params) {
        console.log(`  Params: ${truncateData(params)}`);
      }
      
      if (config.data) {
        console.log(`  Body: ${truncateData(config.data)}`);
      }
    }
    
    return config;
  },
  (error) => {
    if (apiLoggingEnabled) {
      console.error(
        `%c[API] ${getTimestamp()} ✗ Request Error`,
        'color: #EF4444; font-weight: bold',
        error.message
      );
    }
    return Promise.reject(error);
  }
);

// ==================== Response Interceptor ====================
api.interceptors.response.use(
  (response) => {
    if (apiLoggingEnabled) {
      const duration = Date.now() - (response.config.metadata?.startTime || Date.now());
      const method = response.config.method?.toUpperCase() || 'GET';
      const url = response.config.url || '';
      const status = response.status;
      
      const color = status >= 200 && status < 300 ? '#10B981' : '#F59E0B';
      
      console.log(
        `%c[API] ${getTimestamp()} ← ${method} ${url} [${status}] ${duration}ms`,
        `color: ${color}; font-weight: bold`
      );
      
      if (response.data) {
        console.log(`  Data: ${truncateData(response.data)}`);
      }
    }
    
    return response;
  },
  (error) => {
    if (apiLoggingEnabled) {
      const duration = Date.now() - (error.config?.metadata?.startTime || Date.now());
      const method = error.config?.method?.toUpperCase() || 'GET';
      const url = error.config?.url || '';
      const status = error.response?.status || 'ERR';
      
      console.error(
        `%c[API] ${getTimestamp()} ✗ ${method} ${url} [${status}] ${duration}ms`,
        'color: #EF4444; font-weight: bold'
      );
      
      if (error.response?.data) {
        console.error(`  Error: ${truncateData(error.response.data)}`);
      } else {
        console.error(`  Error: ${error.message}`);
      }
    }
    
    return Promise.reject(error);
  }
);

// ==================== Market ====================
export const getMarketRegime = () => api.get('/market/regime');
export const refreshMarketRegime = () => api.post('/market/regime/refresh');
export const getDashboard = () => api.get('/market/dashboard');
export const getMarketBreadth = () => api.get('/market/breadth');
export const getRsIndicators = () => api.get('/market/rs-indicators');

// ==================== Sector ETF ====================
export const getSectorETFs = () => api.get('/etf/sectors');
export const getSectorETF = (symbol) => api.get(`/etf/sectors/${symbol}`);
export const refreshSectorETF = (symbol) => api.post(`/etf/sectors/${symbol}/refresh`);
export const deleteSectorETF = (symbol) => api.delete(`/etf/sectors/${symbol}`);

// ==================== Industry ETF ====================
export const getIndustryETFs = (sector = null) => {
  const params = sector ? { sector } : {};
  return api.get('/etf/industries', { params });
};
export const getIndustryETF = (symbol) => api.get(`/etf/industries/${symbol}`);
export const refreshIndustryETF = (symbol) => api.post(`/etf/industries/${symbol}/refresh`);
export const deleteIndustryETF = (symbol) => api.delete(`/etf/industries/${symbol}`);

// ==================== Holdings ====================
export const uploadHoldings = (data) => api.post('/etf/holdings', data);
export const getHoldings = (symbol) => api.get(`/etf/holdings/${symbol}`);

// ==================== Momentum Stocks ====================
export const getMomentumStocks = (params = {}) => api.get('/momentum/stocks', { params });
export const getMomentumStock = (symbol) => api.get(`/momentum/stocks/${symbol}`);
export const refreshMomentumStock = (symbol) => api.post(`/momentum/stocks/${symbol}/refresh`);
export const deleteMomentumStock = (symbol) => api.delete(`/momentum/stocks/${symbol}`);
export const getTopMomentumStocks = (limit = 10) => api.get('/momentum/top', { params: { limit } });
export const getBreakoutStocks = () => api.get('/momentum/breakouts');
export const refreshIndustryStocks = (industry) => api.post(`/momentum/refresh-industry/${industry}`);

// ==================== Configuration ====================
export const getDataSources = () => api.get('/config/datasources');
export const getDataSource = (source) => api.get(`/config/datasources/${source}`);
export const updateIBKRConfig = (config) => api.put('/config/datasources/ibkr', config);
export const updateFutuConfig = (config) => api.put('/config/datasources/futu', config);
export const testIBKRConnection = () => api.post('/config/datasources/ibkr/test');
export const testFutuConnection = () => api.post('/config/datasources/futu/test');
export const disconnectSource = (source) => api.post(`/config/datasources/${source}/disconnect`);
export const getConfigInfo = () => api.get('/config/info');

// ==================== Data Import ====================
export const importFinviz = (data) => api.post('/import/finviz', data);
export const importMarketChameleon = (data) => api.post('/import/marketchameleon', data);
export const uploadJSON = (formData) => api.post('/import/upload/json', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
export const uploadXLSX = (formData) => api.post('/import/upload/xlsx', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
export const getImportHistory = (limit = 20, source = null) => {
  const params = { limit };
  if (source) params.source = source;
  return api.get('/import/history', { params });
};
export const deleteImportLog = (logId) => api.delete(`/import/history/${logId}`);
export const getImportTemplate = (templateType) => api.get(`/import/template/${templateType}`);

// ==================== Data Configuration Center ====================
// 数据源状态
export const getDataSourcesStatus = () => api.get('/data-config/sources/status');

// 获取所有可用ETF（用于数据导入选择器）
export const getAvailableETFs = () => api.get('/data-config/available-etfs');

// 标的池管理
export const getSymbolPool = (limit = 100, offset = 0) => 
  api.get('/data-config/symbol-pool', { params: { limit, offset } });
export const syncSymbolPool = () => api.post('/data-config/symbol-pool/sync');

// ETF配置管理
export const getETFConfigs = () => api.get('/data-config/etf-configs');
export const updateETFConfig = (symbol, config) => 
  api.put(`/data-config/etf-configs/${symbol}`, config);

// 统一更新
export const getUpdateStatus = () => api.get('/data-config/update/status');
export const startUnifiedUpdate = (request) => api.post('/data-config/update/start', request);
export const cancelUpdate = () => api.post('/data-config/update/cancel');

// 执行计算
export const executeCompute = (request) => api.post('/data-config/compute', request);

// ==================== Debug Utilities ====================
/**
 * Enable debug mode (verbose logging)
 */
export const enableDebugMode = () => {
  localStorage.setItem('debugMode', 'true');
  setApiLogging(true);
  console.log('[API] Debug mode enabled - verbose logging active');
};

/**
 * Disable debug mode
 */
export const disableDebugMode = () => {
  localStorage.setItem('debugMode', 'false');
  setApiLogging(false);
  console.log('[API] Debug mode disabled');
};

export default api;
