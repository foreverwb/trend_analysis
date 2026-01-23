import React, { useState, useEffect, useCallback } from 'react';
import { 
  Database, CheckCircle, AlertCircle, Clock, 
  RefreshCw, Settings, Layers, Download, Upload,
  ChevronDown, ChevronUp, Zap, Shield,
  Check, X
} from 'lucide-react';
import * as api from '../utils/api';
import DataTriggerPanel from './DataTriggerPanel';

const DataConfigCenter = () => {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateProgress, setUpdateProgress] = useState(0);
  const [updatePhase, setUpdatePhase] = useState('');
  const [importSource, setImportSource] = useState('finviz');
  const [importType, setImportType] = useState('holdings');
  const [selectedImportETF, setSelectedImportETF] = useState('XLK');
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [jsonData, setJsonData] = useState('');
  const [importStatus, setImportStatus] = useState(null);
  
  // 触发面板状态
  const [showTriggerPanel, setShowTriggerPanel] = useState(null); // { etfSymbol, dataType }

  // API数据状态
  const [dataSources, setDataSources] = useState([]);
  const [overallCompleteness, setOverallCompleteness] = useState(0);
  const [etfConfigs, setEtfConfigs] = useState({ sector_etfs: [], industry_etfs: [] });
  const [availableETFs, setAvailableETFs] = useState({ sector_etfs: [], industry_etfs: [] });
  const [symbolPool, setSymbolPool] = useState([]);
  const [uniqueSymbolCount, setUniqueSymbolCount] = useState(0);
  const [canCompute, setCanCompute] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  // 加载数据
  const loadData = useCallback(async () => {
    try {
      // 加载数据源状态
      const sourcesRes = await api.getDataSourcesStatus();
      setDataSources(sourcesRes.data.sources || []);
      setOverallCompleteness(sourcesRes.data.overall_completeness || 0);

      // 加载ETF配置（有holdings的）
      const configsRes = await api.getETFConfigs();
      setEtfConfigs({
        sector_etfs: configsRes.data.sector_etfs || [],
        industry_etfs: configsRes.data.industry_etfs || []
      });
      setUniqueSymbolCount(configsRes.data.unique_symbol_count || 0);

      // 加载所有可用ETF（用于导入选择器）
      try {
        const availableRes = await api.getAvailableETFs();
        setAvailableETFs({
          sector_etfs: availableRes.data.sector_etfs || [],
          industry_etfs: availableRes.data.industry_etfs || []
        });
      } catch (e) {
        console.warn('Failed to load available ETFs:', e);
      }

      // 加载标的池
      const poolRes = await api.getSymbolPool();
      setSymbolPool(poolRes.data.symbols || []);
      setLastUpdate(poolRes.data.last_update);

      // 检查更新状态
      const statusRes = await api.getUpdateStatus();
      setCanCompute(statusRes.data.can_compute);
      if (statusRes.data.status === 'fetching' || statusRes.data.status === 'validating') {
        setIsUpdating(true);
        setUpdateProgress(statusRes.data.progress_percent);
        setUpdatePhase(statusRes.data.phase);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (isUpdating) {
        checkUpdateStatus();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [isUpdating, loadData]);

  const checkUpdateStatus = async () => {
    try {
      const res = await api.getUpdateStatus();
      setUpdateProgress(res.data.progress_percent);
      setUpdatePhase(res.data.phase);
      setCanCompute(res.data.can_compute);
      
      if (res.data.status === 'complete' || res.data.status === 'error') {
        setIsUpdating(false);
        loadData();
      }
    } catch (error) {
      console.error('Failed to check update status:', error);
    }
  };

  const handleStartUpdate = async () => {
    setIsUpdating(true);
    setUpdateProgress(0);
    setUpdatePhase('初始化...');
    
    try {
      await api.startUnifiedUpdate({});
    } catch (error) {
      console.error('Failed to start update:', error);
      setIsUpdating(false);
      alert('更新启动失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleConfigChange = async (symbol, field, value) => {
    try {
      await api.updateETFConfig(symbol, { [field]: value });
      loadData();
    } catch (error) {
      console.error('Failed to update config:', error);
    }
  };

  const handleJSONImport = async () => {
    if (!jsonData.trim()) {
      alert('请输入 JSON 数据');
      return;
    }

    setImportStatus(null);

    try {
      let parsedData;
      try {
        parsedData = JSON.parse(jsonData);
      } catch {
        throw new Error('JSON 格式无效');
      }

      const dataArray = Array.isArray(parsedData) ? parsedData : 
                        (parsedData.data ? parsedData.data : [parsedData]);

      let res;
      let targetETF = selectedImportETF;
      
      // 处理ETF Data导入类型
      if (importType === 'etf' && dataArray.length > 0) {
        const firstTicker = dataArray[0].Ticker || dataArray[0].symbol;
        if (firstTicker) {
          targetETF = firstTicker.toUpperCase();
        }
      }
      
      if (importSource === 'finviz') {
        res = await api.importFinviz({
          etf_symbol: targetETF,
          data: dataArray
        });
      } else {
        res = await api.importMarketChameleon({
          etf_symbol: targetETF,
          data: dataArray
        });
      }

      setImportStatus({
        success: true,
        message: res.data.message || `成功导入 ${res.data.record_count} 条记录`
      });
      
      setJsonData('');
      await api.syncSymbolPool();
      loadData();
      
      // 导入成功后显示触发面板，询问用户是否获取实时数据
      if (res.data.record_count > 0) {
        setShowTriggerPanel({
          etfSymbol: targetETF,
          dataType: importType === 'etf' ? 'etf' : 'holdings'
        });
      }
    } catch (error) {
      setImportStatus({
        success: false,
        message: error.response?.data?.detail || error.message || '导入失败'
      });
    }
  };

  const handleExecuteCompute = async () => {
    try {
      const res = await api.executeCompute({});
      alert(res.data.message);
      loadData();
    } catch (error) {
      alert('计算失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const StatusBadge = ({ status }) => {
    const configs = {
      ready: { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: CheckCircle, label: '就绪' },
      pending: { bg: 'bg-amber-100', text: 'text-amber-700', icon: Clock, label: '待更新' },
      error: { bg: 'bg-red-100', text: 'text-red-700', icon: AlertCircle, label: '异常' },
      warning: { bg: 'bg-orange-100', text: 'text-orange-700', icon: AlertCircle, label: '警告' },
      updating: { bg: 'bg-blue-100', text: 'text-blue-700', icon: RefreshCw, label: '更新中' },
    };
    const config = configs[status] || configs.pending;
    const Icon = config.icon;
    
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        <Icon className={`w-3.5 h-3.5 ${status === 'updating' ? 'animate-spin' : ''}`} />
        {config.label}
      </span>
    );
  };

  const allETFConfigs = [...etfConfigs.sector_etfs, ...etfConfigs.industry_etfs];

  // 获取用于导入的ETF选项
  const getImportETFOptions = () => {
    const sectorOptions = availableETFs.sector_etfs.length > 0 
      ? availableETFs.sector_etfs 
      : [
          { symbol: 'XLK', name: '科技板块' },
          { symbol: 'XLF', name: '金融板块' },
          { symbol: 'XLE', name: '能源板块' },
          { symbol: 'XLV', name: '医疗保健' },
          { symbol: 'XLY', name: '非必需消费' },
          { symbol: 'XLI', name: '工业板块' },
          { symbol: 'XLC', name: '通信服务' },
          { symbol: 'XLP', name: '必需消费' },
          { symbol: 'XLU', name: '公用事业' },
          { symbol: 'XLRE', name: '房地产' },
          { symbol: 'XLB', name: '原材料' }
        ];
    
    const industryOptions = availableETFs.industry_etfs.length > 0
      ? availableETFs.industry_etfs
      : [
          { symbol: 'SOXX', name: '半导体' },
          { symbol: 'SMH', name: '半导体设备' },
          { symbol: 'IGV', name: '软件' },
          { symbol: 'XOP', name: '油气开采' },
          { symbol: 'XRT', name: '零售' },
          { symbol: 'KBE', name: '银行' },
          { symbol: 'IBB', name: '生物科技' },
          { symbol: 'XHB', name: '房屋建筑' },
          { symbol: 'XME', name: '金属矿业' },
          { symbol: 'JETS', name: '航空' }
        ];
    
    return { sectorOptions, industryOptions };
  };

  const { sectorOptions, industryOptions } = getImportETFOptions();

  // 关闭触发面板
  const closeTriggerPanel = () => {
    setShowTriggerPanel(null);
    loadData(); // 刷新数据
  };

  return (
    <div className="space-y-6">
      {/* 触发面板模态框 */}
      {showTriggerPanel && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="max-w-lg w-full">
            <DataTriggerPanel
              etfSymbol={showTriggerPanel.etfSymbol}
              dataType={showTriggerPanel.dataType}
              onClose={closeTriggerPanel}
              onUpdateComplete={closeTriggerPanel}
            />
          </div>
        </div>
      )}
      
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
            <Database className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">数据配置中心</h1>
            <p className="text-sm text-slate-500">Data Configuration Center · 统一管理数据更新与状态监控</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="text-right mr-4">
            <div className="text-xs text-slate-500">最后更新</div>
            <div className="text-sm font-medium text-slate-700">
              {lastUpdate ? new Date(lastUpdate).toLocaleString() : '暂无数据'}
            </div>
          </div>
          <button
            onClick={handleStartUpdate}
            disabled={isUpdating}
            className={`px-5 py-2.5 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg ${
              isUpdating 
                ? 'bg-slate-200 text-slate-500 cursor-not-allowed' 
                : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:shadow-xl hover:scale-105'
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${isUpdating ? 'animate-spin' : ''}`} />
            {isUpdating ? '更新中...' : '统一更新'}
          </button>
        </div>
      </div>

      {/* 整体状态看板 */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">数据完备性状态</h2>
            <span className="text-sm text-slate-500">实时监控数据源健康度</span>
          </div>

          {/* 更新进度条 */}
          {isUpdating && (
            <div className="mb-5 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-indigo-700">{updatePhase || '正在更新数据...'}</span>
                <span className="text-sm font-bold text-indigo-700">{updateProgress}%</span>
              </div>
              <div className="h-2 bg-indigo-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-300"
                  style={{ width: `${updateProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* 整体完备度 */}
          <div className="flex items-center gap-6 mb-5">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-slate-600">整体数据完备度</span>
                <span className="text-xl font-bold text-indigo-600">{overallCompleteness}%</span>
              </div>
              <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-500 via-blue-500 to-indigo-500 rounded-full"
                  style={{ width: `${overallCompleteness}%` }}
                />
              </div>
            </div>
            
            <div className={`px-4 py-2 rounded-xl text-sm font-medium ${
              overallCompleteness >= 90 
                ? 'bg-emerald-100 text-emerald-700' 
                : overallCompleteness >= 70 
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-red-100 text-red-700'
            }`}>
              {overallCompleteness >= 90 ? '✓ 可执行计算' : '⚠ 数据不完整'}
            </div>
          </div>

          {/* 数据源状态卡片 */}
          <div className="grid grid-cols-4 gap-3">
            {dataSources.map(source => (
              <div 
                key={source.id}
                className={`p-3 rounded-xl border transition-all ${
                  source.status === 'ready' 
                    ? 'bg-emerald-50/50 border-emerald-200' 
                    : source.status === 'warning'
                      ? 'bg-orange-50/50 border-orange-200'
                      : 'bg-red-50/50 border-red-200'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-sm text-slate-800">{source.name}</span>
                  {source.status === 'ready' ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-orange-500" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">覆盖率</span>
                    <span className={`font-medium ${
                      source.coverage >= 90 ? 'text-emerald-600' : 'text-orange-600'
                    }`}>{source.coverage}%</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">更新时间</span>
                    <span className="text-slate-700">{source.last_update || '-'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 两列布局：ETF配置 + 数据导入 */}
      <div className="grid grid-cols-5 gap-5">
        {/* ETF 更新策略配置 */}
        <div className="col-span-3 bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="p-5 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Settings className="w-5 h-5 text-indigo-600" />
                <h2 className="text-base font-bold text-slate-900">ETF 更新策略配置</h2>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-slate-500">去重后标的数:</span>
                <span className="px-2.5 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-bold">{uniqueSymbolCount}</span>
              </div>
            </div>
          </div>
          
          <div className="p-4">
            {/* 表头 */}
            <div className="grid grid-cols-12 gap-3 px-3 py-2 bg-slate-50 rounded-lg text-xs font-medium text-slate-500 mb-2">
              <div className="col-span-3">ETF</div>
              <div className="col-span-2 text-center">持仓总数</div>
              <div className="col-span-2 text-center">更新数量</div>
              <div className="col-span-2 text-center">更新频率</div>
              <div className="col-span-3 text-center">状态</div>
            </div>
            
            {/* 配置行 */}
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {allETFConfigs.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Settings className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">暂无 ETF 配置</p>
                  <p className="text-xs mt-1">请先导入 ETF 持仓数据</p>
                </div>
              ) : (
                allETFConfigs.map(etf => (
                  <div 
                    key={etf.symbol}
                    className="grid grid-cols-12 gap-3 px-3 py-2.5 bg-white hover:bg-slate-50 rounded-lg border border-slate-100 items-center transition-all"
                  >
                    <div className="col-span-3">
                      <div className="flex items-center gap-2">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-white text-xs ${
                          etf.type === 'sector' 
                            ? 'bg-gradient-to-br from-blue-500 to-indigo-600' 
                            : 'bg-gradient-to-br from-purple-500 to-pink-600'
                        }`}>
                          {etf.symbol.slice(0, 2)}
                        </div>
                        <div>
                          <div className="font-semibold text-sm text-slate-800">{etf.symbol}</div>
                          <div className="text-xs text-slate-500">{etf.name}</div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="col-span-2 text-center">
                      <span className="text-base font-bold text-slate-700">{etf.total_holdings}</span>
                    </div>
                    
                    <div className="col-span-2 text-center">
                      <select 
                        value={etf.top_n}
                        onChange={(e) => handleConfigChange(etf.symbol, 'top_n', parseInt(e.target.value))}
                        className="w-16 px-2 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                      >
                        <option value={10}>Top 10</option>
                        <option value={15}>Top 15</option>
                        <option value={20}>Top 20</option>
                        <option value={30}>Top 30</option>
                      </select>
                    </div>
                    
                    <div className="col-span-2 text-center">
                      <select 
                        value={etf.frequency}
                        onChange={(e) => handleConfigChange(etf.symbol, 'frequency', e.target.value)}
                        className="w-16 px-2 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                      >
                        <option value="daily">每日</option>
                        <option value="weekly">每周</option>
                      </select>
                    </div>
                    
                    <div className="col-span-3 flex justify-center">
                      <StatusBadge status={etf.status} />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* 数据导入面板 */}
        <div className="col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="p-5 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <Upload className="w-5 h-5 text-emerald-600" />
              <h2 className="text-base font-bold text-slate-900">数据导入</h2>
            </div>
          </div>
          
          <div className="p-5 space-y-4">
            {importStatus && (
              <div className={`p-3 rounded-lg text-sm ${
                importStatus.success 
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {importStatus.message}
              </div>
            )}

            {/* 导入类型选择 */}
            <div>
              <label className="text-xs text-slate-600 mb-1.5 block">导入类型</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setImportType('holdings')}
                  className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                    importType === 'holdings'
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  📊 持仓数据
                </button>
                <button
                  onClick={() => setImportType('etf')}
                  className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                    importType === 'etf'
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  📈 ETF Data
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {importType === 'etf' 
                  ? '导入 ETF 自身的技术指标数据' 
                  : '导入 ETF 成分股的持仓数据'}
              </p>
            </div>

            <div>
              <label className="text-xs text-slate-600 mb-1.5 block">目标 ETF</label>
              <select 
                value={selectedImportETF}
                onChange={(e) => setSelectedImportETF(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              >
                {importType === 'etf' && (
                  <optgroup label="ETF Data">
                    <option value="ETF_DATA">自动识别 (从数据中提取)</option>
                  </optgroup>
                )}
                <optgroup label="板块 ETF">
                  {sectorOptions.map(etf => (
                    <option key={etf.symbol} value={etf.symbol}>
                      {etf.symbol} - {etf.name} {etf.has_holdings ? `(${etf.holdings_count})` : ''}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="行业 ETF">
                  {industryOptions.map(etf => (
                    <option key={etf.symbol} value={etf.symbol}>
                      {etf.symbol} - {etf.name} {etf.has_holdings ? `(${etf.holdings_count})` : ''}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
            
            <div>
              <label className="text-xs text-slate-600 mb-1.5 block">数据源</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setImportSource('finviz')}
                  className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                    importSource === 'finviz'
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  Finviz
                </button>
                <button
                  onClick={() => setImportSource('marketchameleon')}
                  className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                    importSource === 'marketchameleon'
                      ? 'bg-purple-50 border-purple-300 text-purple-700'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  MarketChameleon
                </button>
              </div>
            </div>
            
            <div>
              <label className="text-xs text-slate-600 mb-1.5 block">JSON 数据</label>
              <textarea
                value={jsonData}
                onChange={(e) => setJsonData(e.target.value)}
                placeholder='粘贴 JSON 数据'
                className="w-full h-28 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl font-mono text-xs focus:ring-2 focus:ring-indigo-200 focus:border-transparent resize-none"
              />
            </div>
            
            <button 
              onClick={handleJSONImport}
              disabled={!jsonData.trim()}
              className={`w-full py-2.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition-all ${
                jsonData.trim()
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:shadow-lg'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}
            >
              <Download className="w-4 h-4" />
              导入数据
            </button>
          </div>
        </div>
      </div>

      {/* 标的池状态明细 */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Layers className="w-5 h-5 text-purple-600" />
              <h2 className="text-base font-bold text-slate-900">标的池状态明细</h2>
              <span className="text-sm text-slate-500">Symbol Pool · 去重后的唯一数据源</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">共</span>
              <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded font-bold text-sm">{symbolPool.length}</span>
              <span className="text-sm text-slate-500">个标的</span>
            </div>
          </div>
        </div>
        
        <div className="p-4">
          {/* 表头 */}
          <div className="grid grid-cols-12 gap-3 px-3 py-2 bg-slate-50 rounded-lg text-xs font-medium text-slate-500 mb-2">
            <div className="col-span-2">标的</div>
            <div className="col-span-3">所属 ETF</div>
            <div className="col-span-1 text-center">Finviz</div>
            <div className="col-span-1 text-center">M.Cham</div>
            <div className="col-span-1 text-center">IBKR</div>
            <div className="col-span-1 text-center">Futu</div>
            <div className="col-span-2 text-center">完备度</div>
            <div className="col-span-1"></div>
          </div>
          
          {/* 标的行 */}
          <div className="space-y-1 max-h-80 overflow-y-auto">
            {symbolPool.length === 0 ? (
              <div className="text-center py-10 text-slate-500">
                <Layers className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p className="text-sm">暂无标的数据</p>
                <p className="text-xs mt-1">请先导入ETF持仓数据</p>
              </div>
            ) : (
              symbolPool.map(symbol => {
                const completeness = symbol.completeness || 0;
                
                return (
                  <div key={symbol.ticker}>
                    <div 
                      className="grid grid-cols-12 gap-3 px-3 py-2.5 bg-white hover:bg-slate-50 rounded-lg border border-slate-100 items-center transition-all cursor-pointer"
                      onClick={() => setExpandedSymbol(expandedSymbol === symbol.ticker ? null : symbol.ticker)}
                    >
                      <div className="col-span-2">
                        <div className="font-semibold text-sm text-slate-800">{symbol.ticker}</div>
                        <div className="text-xs text-slate-500 truncate">{symbol.name}</div>
                      </div>
                      
                      <div className="col-span-3 flex flex-wrap gap-1">
                        {symbol.etfs.map(etf => (
                          <span 
                            key={etf}
                            className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-medium"
                          >
                            {etf}
                          </span>
                        ))}
                      </div>
                      
                      <div className="col-span-1 flex justify-center">
                        {symbol.finviz ? (
                          <Check className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <X className="w-4 h-4 text-slate-300" />
                        )}
                      </div>
                      
                      <div className="col-span-1 flex justify-center">
                        {symbol.mc ? (
                          <Check className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <X className="w-4 h-4 text-slate-300" />
                        )}
                      </div>
                      
                      <div className="col-span-1 flex justify-center">
                        {symbol.ibkr ? (
                          <Check className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <X className="w-4 h-4 text-slate-300" />
                        )}
                      </div>
                      
                      <div className="col-span-1 flex justify-center">
                        {symbol.futu ? (
                          <Check className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <X className="w-4 h-4 text-slate-300" />
                        )}
                      </div>
                      
                      <div className="col-span-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div 
                              className={`h-full rounded-full ${
                                completeness === 100 
                                  ? 'bg-emerald-500' 
                                  : completeness >= 75 
                                    ? 'bg-blue-500' 
                                    : 'bg-amber-500'
                              }`}
                              style={{ width: `${completeness}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-slate-600 w-8">{completeness}%</span>
                        </div>
                      </div>
                      
                      <div className="col-span-1 flex justify-center">
                        {expandedSymbol === symbol.ticker ? (
                          <ChevronUp className="w-4 h-4 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </div>
                    
                    {/* 展开详情 */}
                    {expandedSymbol === symbol.ticker && (
                      <div className="ml-4 p-3 bg-slate-50 rounded-lg border border-slate-200 mt-1 mb-2">
                        <div className="grid grid-cols-4 gap-3 text-xs">
                          <div>
                            <div className="text-slate-500 mb-1">最高权重 ETF</div>
                            <div className="font-medium text-slate-800">{symbol.etfs[0]} ({symbol.max_weight?.toFixed(2) || '0'}%)</div>
                          </div>
                          <div>
                            <div className="text-slate-500 mb-1">关联 ETF 数</div>
                            <div className="font-medium text-slate-800">{symbol.etfs.length} 个</div>
                          </div>
                          <div>
                            <div className="text-slate-500 mb-1">数据来源</div>
                            <div className="font-medium text-slate-800">
                              {[symbol.finviz && 'Finviz', symbol.mc && 'MC', symbol.ibkr && 'IBKR', symbol.futu && 'Futu'].filter(Boolean).join(', ') || '无'}
                            </div>
                          </div>
                          <div>
                            <div className="text-slate-500 mb-1">当前价格</div>
                            <div className="font-medium text-slate-800">
                              ${symbol.price?.toFixed(2) || '-'}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* 执行计算区域 */}
      <div className={`rounded-2xl border-2 p-5 transition-all ${
        canCompute 
          ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200' 
          : 'bg-slate-50 border-slate-200'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              canCompute 
                ? 'bg-emerald-500 text-white' 
                : 'bg-slate-300 text-slate-500'
            }`}>
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800">执行后端计算</h3>
              <p className="text-sm text-slate-500">
                {canCompute 
                  ? '✅ 数据完备，可执行动能评分计算' 
                  : '⚠️ 数据不完整，建议先完成数据更新'}
              </p>
            </div>
          </div>
          
          <button 
            onClick={handleExecuteCompute}
            className={`px-6 py-2.5 rounded-xl font-medium text-sm transition-all ${
              canCompute 
                ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:shadow-lg hover:scale-105' 
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            🔥 执行动能评分计算
          </button>
        </div>
      </div>
    </div>
  );
};

export default DataConfigCenter;
