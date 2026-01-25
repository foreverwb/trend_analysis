import React, { useState, useCallback, useRef } from 'react';
import { 
  Upload, FileText, AlertCircle, CheckCircle, Loader2, 
  X, Copy, Download, FileJson, RefreshCw, ChevronDown
} from 'lucide-react';
import { HoldingsHint } from '../common';
import { useCoverageOptions } from '../../hooks/useCoverageOptions';
import { useEtfHoldings } from '../../hooks/useEtfHoldings';
import { useDataSourceLinks } from '../../hooks/useDataSourceLinks';

// 数据源类型
const DATA_SOURCES = [
  { id: 'finviz', name: 'Finviz', description: '技术指标数据' },
  { id: 'market_chameleon', name: 'MarketChameleon', description: '期权数据' }
];

// 输入方式
const INPUT_METHODS = [
  { id: 'text', name: '文本粘贴', icon: FileText },
  { id: 'file', name: '文件上传', icon: Upload }
];

const DataImportPanel = ({ 
  taskId, 
  etfSymbol,
  etfName,
  onImportSuccess, 
  onClose,
  defaultSource = 'finviz',
  isDrawerMode = false
}) => {
  const [dataSource, setDataSource] = useState(defaultSource);
  const [inputMethod, setInputMethod] = useState('text');
  const [textContent, setTextContent] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  
  // 覆盖范围选择状态
  const [selectedCoverage, setSelectedCoverage] = useState('top15');
  const [showCoverageDropdown, setShowCoverageDropdown] = useState(false);
  
  const fileInputRef = useRef(null);
  const coverageDropdownRef = useRef(null);

  // 获取覆盖范围选项
  const { options: coverageOptions, getLabel: getCoverageLabel } = useCoverageOptions();
  
  // 获取持仓数据
  const { 
    holdings, 
    totalWeight, 
    loading: holdingsLoading 
  } = useEtfHoldings(etfSymbol, selectedCoverage);

  // 获取数据源快捷链接
  const { links: dataSourceLinks } = useDataSourceLinks();

  // 验证 JSON 格式
  const validateJSON = (content) => {
    try {
      const data = JSON.parse(content);
      if (!Array.isArray(data)) {
        return { valid: false, error: '数据必须是数组格式' };
      }
      if (data.length === 0) {
        return { valid: false, error: '数据数组不能为空' };
      }
      return { valid: true, data };
    } catch (e) {
      return { valid: false, error: `JSON 格式错误: ${e.message}` };
    }
  };

  // 处理文件选择
  const handleFileSelect = useCallback((event) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.json')) {
        setErrors(['请选择 .json 文件']);
        return;
      }
      setSelectedFile(file);
      setErrors([]);
      
      // 读取文件内容预览
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result;
        const validation = validateJSON(content);
        if (!validation.valid) {
          setErrors([validation.error]);
        } else {
          setTextContent(content);
        }
      };
      reader.readAsText(file);
    }
  }, []);

  // 拖拽处理
  const handleDrop = useCallback((event) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) {
      if (!file.name.endsWith('.json')) {
        setErrors(['请拖入 .json 文件']);
        return;
      }
      setSelectedFile(file);
      setErrors([]);
      
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result;
        const validation = validateJSON(content);
        if (!validation.valid) {
          setErrors([validation.error]);
        } else {
          setTextContent(content);
        }
      };
      reader.readAsText(file);
    }
  }, []);

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  // 执行导入
  const handleImport = async () => {
    setErrors([]);
    setWarnings([]);
    setImportResult(null);

    // 验证 ETF symbol
    if (!etfSymbol) {
      setErrors(['请选择要导入数据的 ETF']);
      return;
    }

    // 验证内容
    const content = textContent.trim();
    if (!content) {
      setErrors(['请输入或上传数据']);
      return;
    }

    const validation = validateJSON(content);
    if (!validation.valid) {
      setErrors([validation.error]);
      return;
    }

    setIsImporting(true);

    try {
      const endpoint = inputMethod === 'text' 
        ? '/api/monitor/import/text'
        : '/api/monitor/import/file';

      const requestBody = inputMethod === 'text' ? {
        task_id: taskId,
        etf_symbol: etfSymbol,
        import_type: dataSource,
        json_data: content
      } : (() => {
        const formData = new FormData();
        formData.append('task_id', taskId);
        formData.append('etf_symbol', etfSymbol);
        formData.append('import_type', dataSource);
        formData.append('file', selectedFile);
        return formData;
      })();

      const response = await fetch(endpoint, {
        method: 'POST',
        ...(inputMethod === 'text' ? {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        } : {
          body: requestBody
        })
      });

      const result = await response.json();

      if (!response.ok) {
        // 处理 FastAPI 验证错误格式
        let errorMessages = [];
        if (result.detail) {
          if (typeof result.detail === 'string') {
            errorMessages = [result.detail];
          } else if (Array.isArray(result.detail)) {
            errorMessages = result.detail.map(err => 
              typeof err === 'string' ? err : (err.msg || JSON.stringify(err))
            );
          } else {
            errorMessages = [JSON.stringify(result.detail)];
          }
        } else {
          errorMessages = ['导入失败'];
        }
        setErrors(errorMessages);
        return;
      }

      setImportResult(result);
      const warningMessages = (result.warnings || []).map(w => 
        typeof w === 'string' ? w : JSON.stringify(w)
      );
      setWarnings(warningMessages);
      
      if (result.success) {
        onImportSuccess?.(result);
      }

    } catch (error) {
      setErrors([`导入错误: ${error.message}`]);
    } finally {
      setIsImporting(false);
    }
  };

  // 清除内容
  const handleClear = () => {
    setTextContent('');
    setSelectedFile(null);
    setErrors([]);
    setWarnings([]);
    setImportResult(null);
  };

  // 加载示例数据
  const loadSampleData = () => {
    const samples = {
      finviz: JSON.stringify([
        {
          "Ticker": "NVDA",
          "Beta": 2.31,
          "ATR": 5.38,
          "SMA50": 0.43,
          "SMA200": 11.85,
          "52W_High": -12.89,
          "RSI": 50.33,
          "Price": 184.84
        },
        {
          "Ticker": "AAPL",
          "Beta": 1.24,
          "ATR": 3.21,
          "SMA50": 1.25,
          "SMA200": 8.45,
          "52W_High": -8.32,
          "RSI": 55.12,
          "Price": 225.50
        }
      ], null, 2),
      market_chameleon: JSON.stringify([
        {
          "symbol": "LRCX",
          "RelVolTo90D": "1.22",
          "CallVolume": "24,635",
          "PutVolume": "21,919",
          "PutPct": "47.1%",
          "IV30": "58.8",
          "IVR": "94%",
          "HV20": "53.1",
          "PriceChgPct": "-3.4%"
        }
      ], null, 2)
    };
    setTextContent(samples[dataSource] || '');
    setErrors([]);
  };

  // 动态生成 placeholder
  const getPlaceholder = () => {
    if (holdings.length > 0) {
      const previewSymbols = holdings.slice(0, 3).map(h => h.symbol).join(', ');
      return `粘贴包含 ${previewSymbols} 等标的的 JSON 数据...`;
    }
    return `粘贴 ${DATA_SOURCES.find(s => s.id === dataSource)?.name} JSON 数据...`;
  };

  // 合并所有覆盖范围选项
  const allCoverageOptions = [
    ...(coverageOptions.quantity_based || []),
    ...(coverageOptions.weight_based || [])
  ];

  return (
    <div className={isDrawerMode ? '' : 'bg-white rounded-lg shadow-lg p-6 max-w-2xl w-full'}>
      {/* Header - 仅在非 Drawer 模式下显示 */}
      {!isDrawerMode && (
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">导入数据</h2>
            <p className="text-sm text-gray-500 mt-1">
              {etfSymbol ? `为 ${etfSymbol} 导入第三方数据` : '请先选择 ETF'}
            </p>
          </div>
          {onClose && (
            <button 
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          )}
        </div>
      )}

      {/* 覆盖范围选择 */}
      <div className="mb-4">
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          覆盖范围
        </label>
        <div className="relative" ref={coverageDropdownRef}>
          <button
            type="button"
            onClick={() => setShowCoverageDropdown(!showCoverageDropdown)}
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-left bg-gray-50
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
              flex items-center justify-between"
          >
            <span className="text-gray-700">
              {getCoverageLabel(selectedCoverage)} - {
                allCoverageOptions.find(o => o.value === selectedCoverage)?.description || ''
              }
            </span>
            <ChevronDown 
              className={`text-gray-400 transition-transform ${showCoverageDropdown ? 'rotate-180' : ''}`} 
              size={18} 
            />
          </button>
          
          {showCoverageDropdown && (
            <>
              <div 
                className="fixed inset-0 z-10"
                onClick={() => setShowCoverageDropdown(false)}
              />
              <div className="absolute z-20 w-full mt-1 bg-white rounded-xl shadow-lg border border-gray-200 py-2 max-h-64 overflow-y-auto">
                {/* 数量型选项 */}
                {coverageOptions.quantity_based?.length > 0 && (
                  <>
                    <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      数量型
                    </div>
                    {coverageOptions.quantity_based.filter(opt => opt.enabled !== false).map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => {
                          setSelectedCoverage(opt.value);
                          setShowCoverageDropdown(false);
                        }}
                        className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 transition-colors
                          ${selectedCoverage === opt.value ? 'text-blue-600 bg-blue-50' : 'text-gray-700'}`}
                      >
                        <span className="font-medium">{opt.label}</span>
                        <span className="text-gray-500 ml-2">- {opt.description}</span>
                      </button>
                    ))}
                  </>
                )}
                
                {/* 权重型选项 */}
                {coverageOptions.weight_based?.length > 0 && (
                  <>
                    <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide mt-2">
                      权重型
                    </div>
                    {coverageOptions.weight_based.filter(opt => opt.enabled !== false).map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => {
                          setSelectedCoverage(opt.value);
                          setShowCoverageDropdown(false);
                        }}
                        className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 transition-colors
                          ${selectedCoverage === opt.value ? 'text-amber-600 bg-amber-50' : 'text-gray-700'}`}
                      >
                        <span className="font-medium">{opt.label}</span>
                        <span className="text-gray-500 ml-2">- {opt.description}</span>
                      </button>
                    ))}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* 持仓标的提示 */}
      <div className="mb-4">
        {holdingsLoading ? (
          <div className="bg-gray-50 rounded-xl p-4 text-center text-gray-500 flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            加载持仓数据中...
          </div>
        ) : (
          <HoldingsHint 
            holdings={holdings}
            totalWeight={totalWeight}
            coverageLabel={getCoverageLabel(selectedCoverage)}
            dataSourceLinks={dataSourceLinks}
          />
        )}
      </div>

      {/* 数据源选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          数据来源
        </label>
        <div className="flex gap-3">
          {DATA_SOURCES.map(source => (
            <button
              key={source.id}
              onClick={() => {
                setDataSource(source.id);
                handleClear();
              }}
              className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all text-left
                ${dataSource === source.id 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 hover:border-gray-300'}`}
            >
              <p className={`font-medium ${dataSource === source.id ? 'text-blue-700' : 'text-gray-700'}`}>
                {source.name}
              </p>
              <p className="text-xs text-gray-500 mt-1">{source.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* 输入方式选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          输入方式
        </label>
        <div className="flex gap-2">
          {INPUT_METHODS.map(method => {
            const Icon = method.icon;
            return (
              <button
                key={method.id}
                onClick={() => setInputMethod(method.id)}
                className={`flex items-center px-4 py-2 rounded-lg border transition-colors
                  ${inputMethod === method.id 
                    ? 'bg-blue-100 text-blue-700 border-blue-300' 
                    : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200'}`}
              >
                <Icon className="w-4 h-4 mr-2" />
                {method.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* 输入区域 */}
      <div className="mb-4">
        {inputMethod === 'text' ? (
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-700">
                粘贴 JSON 数据
              </label>
              <button
                onClick={loadSampleData}
                className="text-xs text-blue-600 hover:text-blue-700"
              >
                加载示例数据
              </button>
            </div>
            <textarea
              value={textContent}
              onChange={(e) => {
                setTextContent(e.target.value);
                setErrors([]);
              }}
              placeholder={getPlaceholder()}
              rows={8}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 font-mono text-sm
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                bg-gray-50 resize-none"
            />
          </div>
        ) : (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${selectedFile 
                ? 'border-green-400 bg-green-50' 
                : 'border-gray-300 hover:border-gray-400'}`}
          >
            {selectedFile ? (
              <div>
                <FileJson className="w-12 h-12 text-green-500 mx-auto mb-2" />
                <p className="font-medium text-gray-700">{selectedFile.name}</p>
                <p className="text-sm text-gray-500 mt-1">
                  {(selectedFile.size / 1024).toFixed(2)} KB
                </p>
                <button
                  onClick={() => {
                    setSelectedFile(null);
                    setTextContent('');
                  }}
                  className="mt-3 text-sm text-red-600 hover:text-red-700"
                >
                  移除文件
                </button>
              </div>
            ) : (
              <div>
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600">
                  拖拽 .json 文件到此处
                </p>
                <p className="text-sm text-gray-500 mt-1">或</p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  选择文件
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* 错误提示 */}
      {errors.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              {errors.map((error, index) => (
                <p key={index} className="text-sm text-red-600">{error}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 警告提示 */}
      {warnings.length > 0 && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-yellow-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-700 mb-1">解析警告:</p>
              {warnings.map((warning, index) => (
                <p key={index} className="text-sm text-yellow-600">{warning}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 导入结果 */}
      {importResult && importResult.success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start">
            <CheckCircle className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-green-700">导入成功</p>
              <p className="text-sm text-green-600 mt-1">
                成功导入 {importResult.imported_count} 条记录
                {importResult.updated_count > 0 && `, 更新 ${importResult.updated_count} 条`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3">
        <button
          onClick={handleClear}
          className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          清除
        </button>
        <button
          onClick={handleImport}
          disabled={isImporting || !textContent.trim()}
          className={`flex items-center px-6 py-2 rounded-lg transition-colors
            ${isImporting || !textContent.trim()
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-500 text-white hover:bg-blue-600'}`}
        >
          {isImporting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              导入中...
            </>
          ) : (
            <>
              <Download className="w-4 h-4 mr-2" />
              解析并导入
            </>
          )}
        </button>
      </div>

      {/* 格式说明 */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          <strong>格式说明：</strong>
          {dataSource === 'finviz' ? (
            <span> Finviz JSON 需包含 Ticker, Beta, ATR, SMA50, SMA200, 52W_High, RSI, Price 字段</span>
          ) : (
            <span> MarketChameleon JSON 需包含 symbol, RelVolTo90D, CallVolume, PutVolume, IV30, IVR 等字段</span>
          )}
        </p>
      </div>
    </div>
  );
};

export default DataImportPanel;
