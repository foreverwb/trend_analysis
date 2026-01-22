import React, { useState, useEffect } from 'react';
import { 
  Upload, FileJson, FileSpreadsheet, Download, History, 
  CheckCircle, XCircle, AlertCircle, RefreshCw, Trash2,
  ChevronDown, ChevronUp, FileText
} from 'lucide-react';
import * as api from '../utils/api';

const DataImportView = () => {
  const [activeImportTab, setActiveImportTab] = useState('upload');
  const [importHistory, setImportHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  
  // Upload form states
  const [uploadType, setUploadType] = useState('xlsx'); // xlsx, finviz, marketchameleon
  const [selectedFile, setSelectedFile] = useState(null);
  const [etfType, setEtfType] = useState('sector');
  const [etfSymbol, setEtfSymbol] = useState('XLK');
  const [sectorSymbol, setSectorSymbol] = useState('');
  const [dataDate, setDataDate] = useState(new Date().toISOString().split('T')[0]);
  
  // JSON paste states
  const [jsonData, setJsonData] = useState('');
  const [jsonSource, setJsonSource] = useState('finviz');
  const [jsonEtfSymbol, setJsonEtfSymbol] = useState('XLK');

  // ETF options
  const sectorETFs = ['XLK', 'XLF', 'XLE', 'XLY', 'XLI', 'XLV', 'XLC', 'XLP', 'XLU', 'XLRE', 'XLB'];
  const industryETFs = ['SOXX', 'SMH', 'IGV', 'XOP', 'XRT', 'KBE', 'IBB', 'XHB', 'XME', 'JETS'];

  useEffect(() => {
    loadImportHistory();
  }, []);

  const loadImportHistory = async () => {
    try {
      const res = await api.getImportHistory(20);
      setImportHistory(res.data || []);
    } catch (error) {
      console.error('Failed to load import history:', error);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setUploadStatus(null);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      alert('请选择文件');
      return;
    }

    setLoading(true);
    setUploadStatus(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('etf_type', etfType);
      formData.append('etf_symbol', etfSymbol);
      formData.append('data_date', dataDate);
      
      if (etfType === 'industry' && sectorSymbol) {
        formData.append('sector_symbol', sectorSymbol);
      }

      let res;
      if (uploadType === 'xlsx') {
        res = await api.uploadXLSX(formData);
      } else {
        formData.append('source', uploadType);
        res = await api.uploadJSON(formData);
      }

      setUploadStatus({
        success: true,
        message: res.data.message || `成功导入 ${res.data.record_count} 条记录`
      });
      
      setSelectedFile(null);
      loadImportHistory();
    } catch (error) {
      setUploadStatus({
        success: false,
        message: error.response?.data?.detail || error.message || '上传失败'
      });
    }
    
    setLoading(false);
  };

  const handleJSONImport = async () => {
    if (!jsonData.trim()) {
      alert('请输入 JSON 数据');
      return;
    }

    setLoading(true);
    setUploadStatus(null);

    try {
      let parsedData;
      try {
        parsedData = JSON.parse(jsonData);
      } catch {
        throw new Error('JSON 格式无效');
      }

      // 如果是数组，包装成正确格式
      const dataArray = Array.isArray(parsedData) ? parsedData : 
                        (parsedData.data ? parsedData.data : [parsedData]);

      let res;
      if (jsonSource === 'finviz') {
        res = await api.importFinviz({
          etf_symbol: jsonEtfSymbol,
          data: dataArray
        });
      } else {
        res = await api.importMarketChameleon({
          etf_symbol: jsonEtfSymbol,
          data: dataArray
        });
      }

      setUploadStatus({
        success: true,
        message: res.data.message || `成功导入 ${res.data.record_count} 条记录`
      });
      
      setJsonData('');
      loadImportHistory();
    } catch (error) {
      setUploadStatus({
        success: false,
        message: error.response?.data?.detail || error.message || '导入失败'
      });
    }
    
    setLoading(false);
  };

  const handleDeleteLog = async (logId) => {
    if (!confirm('确定删除此导入记录？')) return;
    
    try {
      await api.deleteImportLog(logId);
      loadImportHistory();
    } catch (error) {
      alert('删除失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const downloadTemplate = async (templateType) => {
    try {
      const res = await api.getImportTemplate(templateType);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${templateType}_template.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      alert('下载模板失败');
    }
  };

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
            <Upload className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">数据导入</h2>
            <p className="text-sm text-slate-600">导入 Finviz、MarketChameleon 或 ETF Holdings 数据</p>
          </div>
        </div>
      </div>

      {/* 子导航 */}
      <div className="flex gap-2 bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
        {[
          { id: 'upload', label: '文件上传', icon: FileSpreadsheet },
          { id: 'json', label: 'JSON 导入', icon: FileJson },
          { id: 'history', label: '导入历史', icon: History },
          { id: 'templates', label: '模板下载', icon: Download }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveImportTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeImportTab === tab.id
                ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-md'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* 状态提示 */}
      {uploadStatus && (
        <div className={`p-4 rounded-xl border ${
          uploadStatus.success 
            ? 'bg-emerald-50 border-emerald-200 text-emerald-800' 
            : 'bg-red-50 border-red-200 text-red-800'
        }`}>
          <div className="flex items-center gap-2">
            {uploadStatus.success 
              ? <CheckCircle className="w-5 h-5" /> 
              : <XCircle className="w-5 h-5" />
            }
            <span className="font-medium">{uploadStatus.message}</span>
          </div>
        </div>
      )}

      {/* 文件上传 */}
      {activeImportTab === 'upload' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900 mb-6">上传文件</h3>
          
          <div className="grid grid-cols-2 gap-6">
            {/* 左侧：配置 */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">文件类型</label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="xlsx">XLSX (ETF Holdings)</option>
                  <option value="finviz">JSON (Finviz)</option>
                  <option value="marketchameleon">JSON (MarketChameleon)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">ETF 类型</label>
                <select
                  value={etfType}
                  onChange={(e) => setEtfType(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="sector">板块 ETF (Sector)</option>
                  <option value="industry">行业 ETF (Industry)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">ETF 代码</label>
                <select
                  value={etfSymbol}
                  onChange={(e) => setEtfSymbol(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  {(etfType === 'sector' ? sectorETFs : industryETFs).map(sym => (
                    <option key={sym} value={sym}>{sym}</option>
                  ))}
                </select>
              </div>

              {etfType === 'industry' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">所属板块 (可选)</label>
                  <select
                    value={sectorSymbol}
                    onChange={(e) => setSectorSymbol(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  >
                    <option value="">-- 选择板块 --</option>
                    {sectorETFs.map(sym => (
                      <option key={sym} value={sym}>{sym}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">数据日期</label>
                <input
                  type="date"
                  value={dataDate}
                  onChange={(e) => setDataDate(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* 右侧：文件选择 */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">选择文件</label>
                <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-green-400 transition-colors">
                  <input
                    type="file"
                    accept={uploadType === 'xlsx' ? '.xlsx,.xls' : '.json'}
                    onChange={handleFileSelect}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <FileSpreadsheet className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                    <p className="text-sm text-slate-600 mb-1">
                      {selectedFile ? selectedFile.name : '点击选择文件或拖拽到此处'}
                    </p>
                    <p className="text-xs text-slate-400">
                      支持 {uploadType === 'xlsx' ? '.xlsx, .xls' : '.json'} 格式
                    </p>
                  </label>
                </div>
              </div>

              {uploadType === 'xlsx' && (
                <div className="p-4 bg-blue-50 rounded-xl border border-blue-200">
                  <p className="text-sm text-blue-800 font-medium mb-2">XLSX 格式要求：</p>
                  <ul className="text-xs text-blue-700 space-y-1">
                    <li>• 必须包含 "Ticker" 列</li>
                    <li>• 必须包含 "Weight" 或 "Weight %" 列</li>
                    <li>• 数据从第二行开始</li>
                  </ul>
                </div>
              )}

              <button
                onClick={handleFileUpload}
                disabled={!selectedFile || loading}
                className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 ${
                  !selectedFile || loading
                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:shadow-lg transition-all'
                }`}
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    上传中...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    上传文件
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* JSON 导入 */}
      {activeImportTab === 'json' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900 mb-6">JSON 数据导入</h3>
          
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">数据来源</label>
              <select
                value={jsonSource}
                onChange={(e) => setJsonSource(e.target.value)}
                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500"
              >
                <option value="finviz">Finviz</option>
                <option value="marketchameleon">MarketChameleon</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">ETF 代码</label>
              <input
                type="text"
                value={jsonEtfSymbol}
                onChange={(e) => setJsonEtfSymbol(e.target.value.toUpperCase())}
                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-green-500"
                placeholder="例如: XLK"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={() => downloadTemplate(jsonSource)}
                className="w-full py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                下载模板
              </button>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">JSON 数据</label>
            <textarea
              value={jsonData}
              onChange={(e) => setJsonData(e.target.value)}
              placeholder='粘贴 JSON 数据，例如：[{"Ticker": "AAPL", "Beta": 1.2, ...}]'
              className="w-full h-64 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-mono text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
          </div>

          <button
            onClick={handleJSONImport}
            disabled={!jsonData.trim() || loading}
            className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 ${
              !jsonData.trim() || loading
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:shadow-lg transition-all'
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                导入中...
              </>
            ) : (
              <>
                <FileJson className="w-5 h-5" />
                导入数据
              </>
            )}
          </button>
        </div>
      )}

      {/* 导入历史 */}
      {activeImportTab === 'history' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-slate-900">导入历史</h3>
            <button
              onClick={loadImportHistory}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <RefreshCw className="w-5 h-5 text-slate-600" />
            </button>
          </div>

          {importHistory.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>暂无导入记录</p>
            </div>
          ) : (
            <div className="space-y-3">
              {importHistory.map((log) => (
                <div 
                  key={log.id} 
                  className={`p-4 rounded-xl border ${
                    log.status === 'success' 
                      ? 'bg-emerald-50 border-emerald-200' 
                      : 'bg-red-50 border-red-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {log.status === 'success' 
                        ? <CheckCircle className="w-5 h-5 text-emerald-600" />
                        : <XCircle className="w-5 h-5 text-red-600" />
                      }
                      <div>
                        <p className="font-medium text-slate-900">
                          {log.source.toUpperCase()} - {log.etf_symbol || 'N/A'}
                        </p>
                        <p className="text-sm text-slate-600">
                          {log.record_count} 条记录 · {new Date(log.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteLog(log.id)}
                      className="p-2 hover:bg-white/50 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4 text-slate-400 hover:text-red-500" />
                    </button>
                  </div>
                  {log.message && (
                    <p className="mt-2 text-sm text-slate-600 pl-8">{log.message}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 模板下载 */}
      {activeImportTab === 'templates' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900 mb-6">数据模板下载</h3>
          
          <div className="grid grid-cols-2 gap-6">
            {/* Finviz 模板 */}
            <div className="p-6 bg-blue-50 rounded-xl border border-blue-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h4 className="font-bold text-slate-900">Finviz 模板</h4>
                  <p className="text-sm text-slate-600">股票筛选数据</p>
                </div>
              </div>
              <p className="text-sm text-slate-600 mb-4">
                包含字段：Ticker, Beta, ATR, SMA50, SMA200, 52W_High, RSI, Price, Volume
              </p>
              <button
                onClick={() => downloadTemplate('finviz')}
                className="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                下载 Finviz 模板
              </button>
            </div>

            {/* MarketChameleon 模板 */}
            <div className="p-6 bg-purple-50 rounded-xl border border-purple-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h4 className="font-bold text-slate-900">MarketChameleon 模板</h4>
                  <p className="text-sm text-slate-600">期权数据</p>
                </div>
              </div>
              <p className="text-sm text-slate-600 mb-4">
                包含字段：symbol, IV30, HV20, IVR, IV_52W_P, CallVolume, PutVolume 等
              </p>
              <button
                onClick={() => downloadTemplate('marketchameleon')}
                className="w-full py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                下载 MarketChameleon 模板
              </button>
            </div>
          </div>

          {/* XLSX 格式说明 */}
          <div className="mt-6 p-6 bg-slate-50 rounded-xl border border-slate-200">
            <h4 className="font-bold text-slate-900 mb-3">XLSX 文件格式说明</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 px-4 font-medium text-slate-700">Ticker</th>
                    <th className="text-left py-2 px-4 font-medium text-slate-700">Weight %</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-slate-100">
                    <td className="py-2 px-4 font-mono">AAPL</td>
                    <td className="py-2 px-4">22.5</td>
                  </tr>
                  <tr className="border-b border-slate-100">
                    <td className="py-2 px-4 font-mono">MSFT</td>
                    <td className="py-2 px-4">20.1</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-4 font-mono">NVDA</td>
                    <td className="py-2 px-4">15.3</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataImportView;
