import { useState, useEffect } from 'react';

/**
 * 获取数据源快捷链接配置的 Hook
 */
export const useDataSourceLinks = () => {
  const [links, setLinks] = useState({
    finviz: { name: 'Finviz Screener', url: 'https://finviz.com/screener.ashx' },
    marketChameleon: { name: 'MarketChameleon', url: 'https://marketchameleon.com' }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLinks = async () => {
      try {
        const response = await fetch('/api/config/data-source-links');
        if (response.ok) {
          const data = await response.json();
          // 转换后端格式到前端格式
          const formattedLinks = {};
          Object.entries(data).forEach(([key, value]) => {
            formattedLinks[key] = {
              name: value.name,
              url: value.base_url,
              description: value.description
            };
          });
          setLinks(formattedLinks);
        }
      } catch (err) {
        setError(err.message);
        // 保持默认值
      } finally {
        setLoading(false);
      }
    };

    fetchLinks();
  }, []);

  return { links, loading, error };
};

export default useDataSourceLinks;
