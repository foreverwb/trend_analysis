import React, { useState } from 'react';
import { 
  ChevronLeft, ChevronRight, Check, X, Plus, Trash2,
  BarChart3, Search, Zap, Settings
} from 'lucide-react';

// 任务类型定义
const TASK_TYPES = [
  {
    id: 'cross_sector',
    name: '跨板块轮动',
    icon: BarChart3,
    description: '对 XLK/XLV/XLF 等板块 ETF 进行评分排序',
    color: 'blue'
  },
  {
    id: 'sector_drilldown',
    name: '科技板块内下钻',
    icon: Search,
    description: '两级评分：板块环境 + 内部行业',
    color: 'purple'
  },
  {
    id: 'momentum_stock',
    name: '动能股追踪',
    icon: Zap,
    description: '多维度相对强度分析',
    color: 'orange'
  }
];

// ETF 元数据
const SECTOR_ETFS = [
  { symbol: 'XLK', name: '科技板块' },
  { symbol: 'XLF', name: '金融板块' },
  { symbol: 'XLV', name: '医疗板块' },
  { symbol: 'XLE', name: '能源板块' },
  { symbol: 'XLY', name: '消费板块' },
  { symbol: 'XLI', name: '工业板块' },
  { symbol: 'XLC', name: '通信板块' },
  { symbol: 'XLP', name: '必需消费品' },
  { symbol: 'XLU', name: '公用事业' },
  { symbol: 'XLRE', name: '房地产' },
  { symbol: 'XLB', name: '材料板块' }
];

const INDUSTRY_ETFS = {
  XLK: [
    { symbol: 'SOXX', name: '半导体' },
    { symbol: 'SMH', name: '半导体VanEck' },
    { symbol: 'IGV', name: '软件' },
    { symbol: 'SKYY', name: '云计算' }
  ],
  XLF: [
    { symbol: 'KBE', name: '银行' },
    { symbol: 'KRE', name: '区域银行' },
    { symbol: 'IAI', name: '券商' }
  ],
  XLV: [
    { symbol: 'IBB', name: '生物科技' },
    { symbol: 'XBI', name: '生物科技SPDR' },
    { symbol: 'IHI', name: '医疗设备' }
  ],
  XLE: [
    { symbol: 'XOP', name: '油气开采' },
    { symbol: 'OIH', name: '油气服务' },
    { symbol: 'AMLP', name: 'MLP' }
  ],
  XLY: [
    { symbol: 'XRT', name: '零售' },
    { symbol: 'XHB', name: '住宅建筑' },
    { symbol: 'IBUY', name: '在线零售' }
  ],
  XLI: [
    { symbol: 'ITA', name: '航空航天' },
    { symbol: 'XAR', name: '航空航天SPDR' },
    { symbol: 'JETS', name: '航空' }
  ]
};

const TaskCreationWizard = ({ onComplete, onCancel }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    taskName: '',
    taskType: '',
    description: '',
    benchmarkSymbol: 'SPY',
    topNCoverage: 15,
    isAutoRefresh: true,
    selectedSectorETFs: [],
    selectedIndustryETFs: []
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const totalSteps = 5;

  // 步骤验证
  const validateStep = (step) => {
    const newErrors = {};

    switch (step) {
      case 1:
        if (!formData.taskType) {
          newErrors.taskType = '请选择任务类型';
        }
        break;
      case 2:
        if (formData.selectedSectorETFs.length === 0) {
          newErrors.etfs = '请至少选择一个 ETF';
        }
        break;
      case 3:
        // 数据导入步骤，可选
        break;
      case 4:
        // 预览步骤
        break;
      case 5:
        if (!formData.taskName.trim()) {
          newErrors.taskName = '请输入任务名称';
        }
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const nextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(Math.min(currentStep + 1, totalSteps));
    }
  };

  const prevStep = () => {
    setCurrentStep(Math.max(currentStep - 1, 1));
  };

  const handleSubmit = async () => {
    if (!validateStep(5)) return;

    setIsSubmitting(true);
    
    try {
      // 构建 ETF 配置
      const etfConfigs = [
        ...formData.selectedSectorETFs.map(symbol => ({
          etf_symbol: symbol,
          etf_level: 'sector',
          parent_etf_symbol: null
        })),
        ...formData.selectedIndustryETFs.map(item => ({
          etf_symbol: item.symbol,
          etf_level: 'industry',
          parent_etf_symbol: item.parentSector
        }))
      ];

      const taskData = {
        task_name: formData.taskName,
        task_type: formData.taskType,
        description: formData.description,
        benchmark_symbol: formData.benchmarkSymbol,
        top_n_coverage: formData.topNCoverage,
        is_auto_refresh: formData.isAutoRefresh,
        etf_configs: etfConfigs
      };

      const response = await fetch('/api/monitor/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taskData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '创建失败');
      }

      const result = await response.json();
      onComplete?.(result);
      
    } catch (error) {
      setErrors({ submit: error.message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleSectorETF = (symbol) => {
    const newSelected = formData.selectedSectorETFs.includes(symbol)
      ? formData.selectedSectorETFs.filter(s => s !== symbol)
      : [...formData.selectedSectorETFs, symbol];
    
    setFormData({ ...formData, selectedSectorETFs: newSelected });
  };

  const toggleIndustryETF = (symbol, parentSector) => {
    const exists = formData.selectedIndustryETFs.find(e => e.symbol === symbol);
    const newSelected = exists
      ? formData.selectedIndustryETFs.filter(e => e.symbol !== symbol)
      : [...formData.selectedIndustryETFs, { symbol, parentSector }];
    
    setFormData({ ...formData, selectedIndustryETFs: newSelected });
  };

  // 渲染步骤指示器
  const renderStepIndicator = () => (
    <div className="flex items-center justify-between mb-8 bg-white p-4 rounded-lg shadow-sm">
      {[1, 2, 3, 4, 5].map((step, index) => (
        <React.Fragment key={step}>
          <div 
            className="flex items-center cursor-pointer" 
            onClick={() => step < currentStep && setCurrentStep(step)}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
              ${step < currentStep ? 'bg-green-500 text-white' : 
                step === currentStep ? 'bg-blue-500 text-white' : 
                'bg-gray-200 text-gray-500'}`}
            >
              {step < currentStep ? <Check size={16} /> : step}
            </div>
            <span className={`ml-2 text-sm font-medium hidden sm:inline
              ${step === currentStep ? 'text-blue-600' : 'text-gray-500'}`}
            >
              {['选择类型', '配置 ETF', '导入数据', '数据预览', '确认创建'][step - 1]}
            </span>
          </div>
          {index < 4 && <div className="flex-1 h-0.5 bg-gray-200 mx-2 sm:mx-4" />}
        </React.Fragment>
      ))}
    </div>
  );

  // 步骤1: 选择任务类型
  const renderStep1 = () => (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">选择任务类型</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TASK_TYPES.map(type => {
          const Icon = type.icon;
          const isSelected = formData.taskType === type.id;
          return (
            <div
              key={type.id}
              onClick={() => setFormData({ ...formData, taskType: type.id })}
              className={`border-2 rounded-lg p-4 cursor-pointer transition-all
                ${isSelected 
                  ? `border-${type.color}-500 bg-${type.color}-50` 
                  : 'border-gray-200 hover:border-gray-300'}`}
            >
              <div className="flex items-center mb-2">
                <Icon className={`w-6 h-6 ${isSelected ? `text-${type.color}-500` : 'text-gray-400'}`} />
                <span className="ml-2 font-medium">{type.name}</span>
              </div>
              <p className="text-sm text-gray-500">{type.description}</p>
            </div>
          );
        })}
      </div>
      {errors.taskType && <p className="text-red-500 text-sm mt-2">{errors.taskType}</p>}
    </div>
  );

  // 步骤2: 配置 ETF
  const renderStep2 = () => (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">配置 ETF 标的</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">基准指数</label>
          <select
            value={formData.benchmarkSymbol}
            onChange={e => setFormData({ ...formData, benchmarkSymbol: e.target.value })}
            className="w-full border rounded-lg px-3 py-2"
          >
            <option value="SPY">SPY - 标普500</option>
            <option value="QQQ">QQQ - 纳斯达克100</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">覆盖范围 Top N</label>
          <select
            value={formData.topNCoverage}
            onChange={e => setFormData({ ...formData, topNCoverage: parseInt(e.target.value) })}
            className="w-full border rounded-lg px-3 py-2"
          >
            {[10, 15, 20, 30].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">选择板块 ETF</label>
        <div className="flex flex-wrap gap-2">
          {SECTOR_ETFS.map(etf => (
            <button
              key={etf.symbol}
              onClick={() => toggleSectorETF(etf.symbol)}
              className={`px-3 py-1 rounded-full text-sm transition-colors
                ${formData.selectedSectorETFs.includes(etf.symbol)
                  ? 'bg-blue-100 text-blue-700 border-blue-300'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'} border`}
            >
              {formData.selectedSectorETFs.includes(etf.symbol) && '✓ '}
              {etf.symbol} ({etf.name})
            </button>
          ))}
        </div>
      </div>

      {formData.taskType === 'sector_drilldown' && formData.selectedSectorETFs.length > 0 && (
        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">选择下属行业 ETF</label>
          {formData.selectedSectorETFs.map(sectorSymbol => (
            <div key={sectorSymbol} className="mb-3">
              <p className="text-sm text-gray-500 mb-1">{sectorSymbol} 下属行业:</p>
              <div className="flex flex-wrap gap-2">
                {(INDUSTRY_ETFS[sectorSymbol] || []).map(etf => (
                  <button
                    key={etf.symbol}
                    onClick={() => toggleIndustryETF(etf.symbol, sectorSymbol)}
                    className={`px-3 py-1 rounded-full text-sm transition-colors
                      ${formData.selectedIndustryETFs.find(e => e.symbol === etf.symbol)
                        ? 'bg-purple-100 text-purple-700 border-purple-300'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'} border`}
                  >
                    {formData.selectedIndustryETFs.find(e => e.symbol === etf.symbol) && '✓ '}
                    {etf.symbol} ({etf.name})
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {errors.etfs && <p className="text-red-500 text-sm mt-2">{errors.etfs}</p>}
    </div>
  );

  // 步骤3: 数据导入提示
  const renderStep3 = () => (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">数据导入</h2>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-700">
          任务创建后，您可以在任务详情页面导入以下数据：
        </p>
        <ul className="mt-2 list-disc list-inside text-blue-600 text-sm">
          <li>Finviz 数据（文本粘贴或文件上传）</li>
          <li>MarketChameleon 数据（文本粘贴或文件上传）</li>
          <li>ETF 自身市场数据（IBKR/Futu 自动获取）</li>
          <li>ETF 期权数据（MarketChameleon）</li>
        </ul>
      </div>
      <p className="text-gray-500 text-sm mt-4">
        点击"下一步"继续配置，或直接跳到确认创建。
      </p>
    </div>
  );

  // 步骤4: 数据预览
  const renderStep4 = () => (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">配置预览</h2>
      <div className="space-y-4">
        <div className="border-b pb-3">
          <span className="text-sm text-gray-500">任务类型:</span>
          <p className="font-medium">
            {TASK_TYPES.find(t => t.id === formData.taskType)?.name || '-'}
          </p>
        </div>
        <div className="border-b pb-3">
          <span className="text-sm text-gray-500">基准指数:</span>
          <p className="font-medium">{formData.benchmarkSymbol}</p>
        </div>
        <div className="border-b pb-3">
          <span className="text-sm text-gray-500">覆盖范围:</span>
          <p className="font-medium">Top {formData.topNCoverage}</p>
        </div>
        <div>
          <span className="text-sm text-gray-500">已选择的 ETF:</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {formData.selectedSectorETFs.map(s => (
              <span key={s} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm">
                {s}
              </span>
            ))}
            {formData.selectedIndustryETFs.map(e => (
              <span key={e.symbol} className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-sm">
                {e.symbol}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // 步骤5: 确认创建
  const renderStep5 = () => (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">确认创建</h2>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            任务名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.taskName}
            onChange={e => setFormData({ ...formData, taskName: e.target.value })}
            placeholder="例如：科技板块周度监控"
            className={`w-full border rounded-lg px-3 py-2 ${errors.taskName ? 'border-red-500' : ''}`}
          />
          {errors.taskName && <p className="text-red-500 text-sm mt-1">{errors.taskName}</p>}
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">任务描述</label>
          <textarea
            value={formData.description}
            onChange={e => setFormData({ ...formData, description: e.target.value })}
            placeholder="可选：描述此任务的用途"
            rows={3}
            className="w-full border rounded-lg px-3 py-2"
          />
        </div>
        
        <div className="flex items-center">
          <input
            type="checkbox"
            id="autoRefresh"
            checked={formData.isAutoRefresh}
            onChange={e => setFormData({ ...formData, isAutoRefresh: e.target.checked })}
            className="w-4 h-4 text-blue-600 rounded"
          />
          <label htmlFor="autoRefresh" className="ml-2 text-sm text-gray-700">
            启用自动刷新（每日 16:30 EOD + 18:00 期权 + 周六重排）
          </label>
        </div>
      </div>
      
      {errors.submit && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {errors.submit}
        </div>
      )}
    </div>
  );

  // 渲染当前步骤内容
  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return renderStep1();
      case 2: return renderStep2();
      case 3: return renderStep3();
      case 4: return renderStep4();
      case 5: return renderStep5();
      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">创建监控分析任务</h1>
            <p className="text-gray-500 mt-1">配置板块轮动监控任务，导入静态数据并设置自动刷新</p>
          </div>
          <button
            onClick={onCancel}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Step Indicator */}
        {renderStepIndicator()}

        {/* Step Content */}
        {renderStepContent()}

        {/* Navigation Buttons */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={prevStep}
            disabled={currentStep === 1}
            className={`flex items-center px-4 py-2 rounded-lg transition-colors
              ${currentStep === 1 
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            上一步
          </button>
          
          {currentStep < totalSteps ? (
            <button
              onClick={nextStep}
              className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              下一步
              <ChevronRight className="w-4 h-4 ml-1" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className={`flex items-center px-6 py-2 rounded-lg transition-colors
                ${isSubmitting 
                  ? 'bg-gray-400 cursor-not-allowed' 
                  : 'bg-green-500 hover:bg-green-600'} text-white`}
            >
              {isSubmitting ? '创建中...' : '创建任务'}
              <Check className="w-4 h-4 ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default TaskCreationWizard;
