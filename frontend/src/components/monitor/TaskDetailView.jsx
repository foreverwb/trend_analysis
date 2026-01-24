import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeft, RefreshCw, Settings, Pause, Play, Archive,
  Calendar, Clock, Database, TrendingUp, AlertCircle,
  Download, Plus, Trash2, MoreVertical
} from 'lucide-react';
import DataImportPanel from './DataImportPanel';
import ETFDataStatusCard from './ETFDataStatusCard';
import ScoreTrendChart from './ScoreTrendChart';

// 任务状态映射
const STATUS_CONFIG = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  active: { label: '运行中', color: 'bg-green-100 text-green-600' },
  paused: { label: '已暂停', color: 'bg-yellow-100 text-yellow-600' },
  archived: { label: '已归档', color: 'bg-red-100 text-red-600' }
};

// 任务类型映射
const TASK_TYPE_LABELS = {
  cross_sector: '跨板块轮动',
  sector_drilldown: '板块下钻',
  momentum_stock: '动能股追踪'
};

const TaskDetailView = ({ taskId, onBack }) => {
  // 状态管理
  const [task, setTask] = useState(null);
  const [etfList, setEtfList] = useState([]);
  const [scoreHistory, setScoreHistory] = useState([]);
  const [selectedETFs, setSelectedETFs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshingETF, setRefreshingETF] = useState(null);
  const [error, setError] = useState(null);
  
  // 模态框状态
  const [showImportModal, setShowImportModal] = useState(false);
  const [importETFSymbol, setImportETFSymbol] = useState(null);
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);

  // 加载任务数据
  const loadTaskData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // 获取任务详情
      const taskRes = await fetch(`/api/monitor/tasks/${taskId}`);
      if (!taskRes.ok) throw new Error('获取任务详情失败');
      const taskData = await taskRes.json();
      setTask(taskData);

      // 获取数据状态
      const statusRes = await fetch(`/api/monitor/tasks/${taskId}/data-status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setEtfList(statusData.etf_status || []);
      }

      // 获取评分历史
      const scoresRes = await fetch(`/api/monitor/tasks/${taskId}/scores?days=30`);
      if (scoresRes.ok) {
        const scoresData = await scoresRes.json();
        setScoreHistory(scoresData.scores || []);
      }

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadTaskData();
  }, [loadTaskData]);

  // 刷新所有数据
  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`/api/monitor/tasks/${taskId}/refresh`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('刷新失败');
      await loadTaskData();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  // 刷新单个 ETF 数据
  const handleRefreshETF = async (symbol) => {
    setRefreshingETF(symbol);
    try {
      const res = await fetch(`/api/monitor/tasks/${taskId}/etfs/${symbol}/refresh`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('刷新失败');
      await loadTaskData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshingETF(null);
    }
  };

  // 打开导入面板
  const handleOpenImport = (symbol) => {
    setImportETFSymbol(symbol);
    setShowImportModal(true);
  };

  // 导入成功回调
  const handleImportSuccess = async () => {
    setShowImportModal(false);
    setImportETFSymbol(null);
    await loadTaskData();
  };

  // 任务状态操作
  const handleStatusAction = async (action) => {
    try {
      const res = await fetch(`/api/monitor/tasks/${taskId}/${action}`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('操作失败');
      await loadTaskData();
    } catch (err) {
      setError(err.message);
    }
    setShowSettingsMenu(false);
  };

  // 加载状态
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-gray-500">加载任务详情...</p>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error && !task) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-2" />
          <p className="text-red-600">{error}</p>
          <button
            onClick={loadTaskData}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!task) return null;

  const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.draft;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* 左侧：返回和标题 */}
            <div className="flex items-center gap-4">
              <button
                onClick={onBack}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-500" />
              </button>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-semibold text-gray-800">{task.task_name}</h1>
                  <span className={`px-2 py-1 rounded-full text-xs ${statusConfig.color}`}>
                    {statusConfig.label}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-0.5">
                  {TASK_TYPE_LABELS[task.task_type]} · 创建于 {new Date(task.created_at).toLocaleDateString('zh-CN')}
                </p>
              </div>
            </div>

            {/* 右侧：操作按钮 */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleRefreshAll}
                disabled={isRefreshing}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors
                  ${isRefreshing 
                    ? 'bg-gray-100 text-gray-400' 
                    : 'bg-blue-500 text-white hover:bg-blue-600'}`}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                {isRefreshing ? '刷新中...' : '全部刷新'}
              </button>
              
              {/* 设置菜单 */}
              <div className="relative">
                <button
                  onClick={() => setShowSettingsMenu(!showSettingsMenu)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <MoreVertical className="w-5 h-5 text-gray-500" />
                </button>
                
                {showSettingsMenu && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20">
                    {task.status === 'active' && (
                      <button
                        onClick={() => handleStatusAction('pause')}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <Pause className="w-4 h-4 mr-2" />
                        暂停任务
                      </button>
                    )}
                    {task.status === 'paused' && (
                      <button
                        onClick={() => handleStatusAction('activate')}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <Play className="w-4 h-4 mr-2" />
                        恢复运行
                      </button>
                    )}
                    {task.status === 'draft' && (
                      <button
                        onClick={() => handleStatusAction('activate')}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <Play className="w-4 h-4 mr-2" />
                        激活任务
                      </button>
                    )}
                    <button
                      onClick={() => handleStatusAction('archive')}
                      className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center"
                    >
                      <Archive className="w-4 h-4 mr-2" />
                      归档任务
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 mt-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center">
            <AlertCircle className="w-5 h-5 text-red-500 mr-2" />
            <span className="text-red-600">{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-400 hover:text-red-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* 主要内容 */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 任务概览卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center text-gray-500 mb-1">
              <Database className="w-4 h-4 mr-2" />
              <span className="text-sm">ETF 数量</span>
            </div>
            <p className="text-2xl font-semibold text-gray-800">{etfList.length}</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center text-gray-500 mb-1">
              <TrendingUp className="w-4 h-4 mr-2" />
              <span className="text-sm">基准指数</span>
            </div>
            <p className="text-2xl font-semibold text-gray-800">{task.benchmark_symbol}</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center text-gray-500 mb-1">
              <Clock className="w-4 h-4 mr-2" />
              <span className="text-sm">自动刷新</span>
            </div>
            <p className={`text-2xl font-semibold ${task.is_auto_refresh ? 'text-green-600' : 'text-gray-400'}`}>
              {task.is_auto_refresh ? '开启' : '关闭'}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center text-gray-500 mb-1">
              <Calendar className="w-4 h-4 mr-2" />
              <span className="text-sm">上次刷新</span>
            </div>
            <p className="text-lg font-semibold text-gray-800">
              {task.last_refresh_at 
                ? new Date(task.last_refresh_at).toLocaleString('zh-CN', { 
                    month: 'short', 
                    day: 'numeric', 
                    hour: '2-digit', 
                    minute: '2-digit' 
                  })
                : '从未'}
            </p>
          </div>
        </div>

        {/* 评分趋势图表 */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
            <TrendingUp className="w-5 h-5 mr-2" />
            评分趋势
          </h2>
          <ScoreTrendChart
            taskId={taskId}
            scoreHistory={scoreHistory}
            etfList={etfList.map(e => ({ symbol: e.symbol, name: e.name }))}
            selectedETFs={selectedETFs.length > 0 ? selectedETFs : undefined}
            onETFSelectionChange={setSelectedETFs}
          />
        </div>

        {/* ETF 数据状态列表 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800 flex items-center">
              <Database className="w-5 h-5 mr-2" />
              ETF 数据状态
            </h2>
            <button
              onClick={() => handleOpenImport(etfList[0]?.symbol)}
              className="flex items-center px-3 py-1.5 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition-colors text-sm"
            >
              <Plus className="w-4 h-4 mr-1" />
              导入数据
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {etfList.map(etf => (
              <ETFDataStatusCard
                key={etf.symbol}
                etf={etf}
                onRefreshData={handleRefreshETF}
                onImportData={handleOpenImport}
                isRefreshing={refreshingETF === etf.symbol}
              />
            ))}
          </div>

          {etfList.length === 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <Database className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">暂无 ETF 配置</p>
              <p className="text-sm text-gray-400 mt-1">请先添加 ETF 到此任务</p>
            </div>
          )}
        </div>
      </div>

      {/* 导入面板模态框 */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <DataImportPanel
            taskId={taskId}
            etfSymbol={importETFSymbol}
            onImportSuccess={handleImportSuccess}
            onClose={() => {
              setShowImportModal(false);
              setImportETFSymbol(null);
            }}
          />
        </div>
      )}

      {/* 点击外部关闭设置菜单 */}
      {showSettingsMenu && (
        <div 
          className="fixed inset-0 z-10"
          onClick={() => setShowSettingsMenu(false)}
        />
      )}
    </div>
  );
};

export default TaskDetailView;
