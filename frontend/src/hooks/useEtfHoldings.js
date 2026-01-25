import { useState, useEffect } from 'react';

/**
 * 获取 ETF 持仓数据的 Hook
 * @param {string} etfSymbol - ETF 代码
 * @param {string} coverageType - 覆盖范围类型
 */
export const useEtfHoldings = (etfSymbol, coverageType) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!etfSymbol || !coverageType) {
      setLoading(false);
      setData(null);
      return;
    }

    const fetchHoldings = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/config/etf-holdings/${etfSymbol}/required?coverage_type=${coverageType}`
        );
        if (!response.ok) {
          if (response.status === 404) {
            // ETF 未找到，返回空数据
            setData({ holdings: [], total_weight: 0, count: 0, symbols_text: '' });
            return;
          }
          throw new Error('Failed to fetch holdings');
        }
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
        setData({ holdings: [], total_weight: 0, count: 0, symbols_text: '' });
      } finally {
        setLoading(false);
      }
    };

    fetchHoldings();
  }, [etfSymbol, coverageType]);

  return { 
    holdings: data?.holdings || [], 
    totalWeight: data?.total_weight || 0,
    count: data?.count || 0,
    symbolsText: data?.symbols_text || '',
    loading, 
    error 
  };
};

export default useEtfHoldings;
