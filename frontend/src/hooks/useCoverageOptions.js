import { useState, useEffect } from 'react';

/**
 * 获取覆盖范围配置选项的 Hook
 */
export const useCoverageOptions = () => {
  const [options, setOptions] = useState({
    quantity_based: [],
    weight_based: []
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const response = await fetch('/api/config/coverage-options');
        if (!response.ok) throw new Error('Failed to fetch coverage options');
        const data = await response.json();
        setOptions(data);
      } catch (err) {
        setError(err.message);
        // 使用默认配置作为 fallback
        setOptions({
          quantity_based: [
            { value: 'top10', label: 'Top 10', description: '前10大持仓', enabled: true },
            { value: 'top15', label: 'Top 15', description: '前15大持仓', enabled: true },
            { value: 'top20', label: 'Top 20', description: '前20大持仓', enabled: true },
            { value: 'top30', label: 'Top 30', description: '前30大持仓', enabled: true },
          ],
          weight_based: [
            { value: 'weight70', label: 'Weight 70%', description: '累计权重达70%', enabled: true },
            { value: 'weight75', label: 'Weight 75%', description: '累计权重达75%', enabled: true },
            { value: 'weight80', label: 'Weight 80%', description: '累计权重达80%', enabled: true },
            { value: 'weight85', label: 'Weight 85%', description: '累计权重达85%', enabled: true },
          ]
        });
      } finally {
        setLoading(false);
      }
    };

    fetchOptions();
  }, []);

  // 辅助方法
  const getLabel = (value) => {
    const allOptions = [...options.quantity_based, ...options.weight_based];
    return allOptions.find(o => o.value === value)?.label || value;
  };

  const getType = (value) => {
    return options.quantity_based.some(o => o.value === value) ? 'quantity' : 'weight';
  };

  return { options, loading, error, getLabel, getType };
};

export default useCoverageOptions;
