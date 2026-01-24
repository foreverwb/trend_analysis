import React, { useState, useEffect } from 'react';
import {
  Plus, Search, Filter, RefreshCw, MoreVertical,
  BarChart3, Zap, Target, Calendar, Clock,
  ChevronRight, Trash2, Archive, Play, Pause
} from 'lucide-react';

// 任务状态配置
const STATUS_CONFIG = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600', dotColor: 'bg-gray-400' },
  active: { label: '运行中', color: 'bg-green-100 text-green-600', dotColor: 'bg-green-500' },
  paused: { label: '已暂停', color: 'bg-yellow-100 text-yellow-600', dotColor: 'bg-yellow-500' },
  archived: { label: '已归档', color: 'bg-red-100 text-red-600', dotColor: 'bg-red-400' }
};

// 任务类型配置
const TASK_TYPE_CONFIG = {
  cross_sector: { 
    label: '跨板块轮动', 
    icon: BarChart3, 
    color: 'text-blue-600',
    bgColor: 'bg-blue-50'
  },
  sector_drilldown: { 
    label: '板块下钻', 
    icon: Target, 
    color: 'text-purple-600',
    bgColor: 'bg-purple-50'
  },
  momentum_stock: { 
    label: '动能股追踪', 
    icon: Zap, 
    color: 'text-orange-600',
    bgColor: 'bg-orange-50'
  }
};

// 单个任务卡片
const TaskCard = ({ task, onView, onAction }) => {
  const [showMenu, setShowMenu] = useState(false);
  
  const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.draft;
  const typeConfig = TASK_TYPE_CONFIG[task.task_type] || TASK_TYPE_CONFIG.cross_sector;
  const TypeIcon = typeConfig.icon;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
      <div className="p-4">
        {/* 头部 */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${typeConfig.bgColor}`}>
              <TypeIcon className={`w-5 h-5 ${typeConfig.color}`} />
            </div>
            <div>
              <h3 className="font-medium text-gray-800">{task.task_name}</h3>
              <p className="text-sm text-gray-500">{typeConfig.label}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className={`flex items-center px-2 py-1 rounded-full text-xs ${statusConfig.color}`}>
              <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${statusConfig.dotColor}`} />
              {statusConfig.label}
            </span>
            
            {/* 操作菜单 */}
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <MoreVertical className="w-4 h-4 text-gray-400" />
              </button>
              
              {showMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10"
                    onClick={() => setShowMenu(false)}
                  />
                  <div className="absolute right-0 mt-1 w-36 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20">
                    {task.status === 'active' && (
                      <button
                        onClick={() => { onAction(task.id, 'pause'); setShowMenu(false); }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <Pause className="w-4 h-4 mr-2" />
                        暂停
                      </button>
                    )}
                    {(task.status === 'paused' || task.status === 'draft') && (
                      <button
                        onClick={() => { onAction(task.id, 'activate'); setShowMenu(false); }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <Play className="w-4 h-4 mr-2" />
                        激活
                      </button>
                    )}
                    <button
                      onClick={() => { onAction(task.id, 'archive'); setShowMenu(false); }}
                      className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center"
                    >
                      <Archive className="w-4 h-4 mr-2" />
                      归档
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 描述 */}
        {task.description && (
          <p className="mt-2 text-sm text-gray-500 line-clamp-2">{task.description}</p>
        )}

        {/* ETF 标签 */}
        <div className="mt-3 flex flex-wrap gap-1">
          {task.etf_symbols?.slice(0, 5).map(symbol => (
            <span 
              key={symbol}
              className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
            >
              {symbol}
            </span>
          ))}
          {task.etf_symbols?.length > 5 && (
            <span className="px-2 py-0.5 text-gray-400 text-xs">
              +{task.etf_symbols.length - 5}
            </span>
          )}
        </div>

        {/* 底部信息 */}
        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-sm">
          <div className="flex items-center gap-4 text-gray-400">
            <span className="flex items-center">
              <Calendar className="w-4 h-4 mr-1" />
              {new Date(task.created_at).toLocaleDateString('zh-CN')}
            </span>
            {task.last_refresh_at && (
              <span className="flex items-center">
                <Clock className="w-4 h-4 mr-1" />
                {new Date(task.last_refresh_at).toLocaleTimeString('zh-CN', { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </span>
            )}
          </div>
          
          <button
            onClick={() => onView(task.id)}
            className="flex items-center text-blue-600 hover:text-blue-700"
          >
            查看详情
            <ChevronRight className="w-4 h-4 ml-1" />
          </button>
        </div>
      </div>
    </div>
  );
};

const MonitorTaskListView = ({ onCreateTask, onViewTask }) => {
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // 筛选状态
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');

  // 加载任务列表
  const loadTasks = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (typeFilter !== 'all') params.append('task_type', typeFilter);
      if (searchQuery) params.append('search', searchQuery);
      
      const res = await fetch(`/api/monitor/tasks?${params}`);
      if (!res.ok) throw new Error('获取任务列表失败');
      
      const data = await res.json();
      setTasks(data.tasks || data);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, [statusFilter, typeFilter]);

  // 搜索防抖
  useEffect(() => {
    const timer = setTimeout(() => {
      loadTasks();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 任务操作
  const handleTaskAction = async (taskId, action) => {
    try {
      const res = await fetch(`/api/monitor/tasks/${taskId}/${action}`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('操作失败');
      await loadTasks();
    } catch (err) {
      setError(err.message);
    }
  };

  // 筛选后的任务
  const filteredTasks = tasks;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 页面头部 */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">监控分析任务</h1>
            <p className="text-gray-500 mt-1">管理板块轮动监控任务，导入数据并追踪评分变化</p>
          </div>
          <button
            onClick={onCreateTask}
            className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            <Plus className="w-5 h-5 mr-2" />
            创建任务
          </button>
        </div>

        {/* 筛选栏 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* 搜索框 */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索任务名称..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            {/* 状态筛选 */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">所有状态</option>
              <option value="active">运行中</option>
              <option value="paused">已暂停</option>
              <option value="draft">草稿</option>
              <option value="archived">已归档</option>
            </select>
            
            {/* 类型筛选 */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">所有类型</option>
              <option value="cross_sector">跨板块轮动</option>
              <option value="sector_drilldown">板块下钻</option>
              <option value="momentum_stock">动能股追踪</option>
            </select>
            
            {/* 刷新按钮 */}
            <button
              onClick={loadTasks}
              disabled={isLoading}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-5 h-5 text-gray-500 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600">
            {error}
          </div>
        )}

        {/* 任务列表 */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <BarChart3 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-600 mb-2">暂无监控任务</h3>
            <p className="text-gray-400 mb-4">创建您的第一个监控分析任务，开始追踪板块轮动</p>
            <button
              onClick={onCreateTask}
              className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              <Plus className="w-5 h-5 mr-2" />
              创建任务
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredTasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onView={onViewTask}
                onAction={handleTaskAction}
              />
            ))}
          </div>
        )}

        {/* 统计信息 */}
        {!isLoading && filteredTasks.length > 0 && (
          <div className="mt-6 text-center text-sm text-gray-400">
            共 {filteredTasks.length} 个任务
          </div>
        )}
      </div>
    </div>
  );
};

export default MonitorTaskListView;
