import { useState, useEffect, useCallback } from 'react';
import * as api from '../utils/api';

/**
 * Hook for fetching and managing market regime data
 */
export const useMarketRegime = () => {
  const [regime, setRegime] = useState({
    status: 'B',
    spy: { price: 0, vs200ma: '+0.0%', trend: 'neutral' },
    vix: 0,
    breadth: 50
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRegime = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getMarketRegime();
      setRegime(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  const refreshRegime = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await api.refreshMarketRegime();
      const res = await api.getMarketRegime();
      setRegime(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRegime();
  }, [fetchRegime]);

  return { regime, loading, error, refresh: refreshRegime };
};

/**
 * Hook for fetching and managing sector ETFs
 */
export const useSectorETFs = () => {
  const [etfs, setEtfs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchETFs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getSectorETFs();
      setEtfs(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  const refreshETF = useCallback(async (symbol) => {
    try {
      await api.refreshSectorETF(symbol);
      await fetchETFs();
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, [fetchETFs]);

  useEffect(() => {
    fetchETFs();
  }, [fetchETFs]);

  return { etfs, loading, error, refresh: fetchETFs, refreshETF };
};

/**
 * Hook for fetching and managing industry ETFs
 */
export const useIndustryETFs = (sector = null) => {
  const [etfs, setEtfs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchETFs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getIndustryETFs(sector);
      setEtfs(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [sector]);

  const refreshETF = useCallback(async (symbol) => {
    try {
      await api.refreshIndustryETF(symbol);
      await fetchETFs();
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, [fetchETFs]);

  useEffect(() => {
    fetchETFs();
  }, [fetchETFs]);

  return { etfs, loading, error, refresh: fetchETFs, refreshETF };
};

/**
 * Hook for fetching and managing momentum stocks
 */
export const useMomentumStocks = (filters = {}) => {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStocks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getMomentumStocks(filters);
      setStocks(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [filters]);

  const refreshStock = useCallback(async (symbol) => {
    try {
      await api.refreshMomentumStock(symbol);
      await fetchStocks();
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, [fetchStocks]);

  useEffect(() => {
    fetchStocks();
  }, [fetchStocks]);

  return { stocks, loading, error, refresh: fetchStocks, refreshStock };
};

/**
 * Hook for managing data source connections
 */
export const useDataSources = () => {
  const [configs, setConfigs] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDataSources();
      setConfigs(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  const testConnection = useCallback(async (source) => {
    try {
      const res = source === 'ibkr' 
        ? await api.testIBKRConnection()
        : await api.testFutuConnection();
      await fetchConfigs();
      return res.data;
    } catch (err) {
      return { success: false, message: err.message };
    }
  }, [fetchConfigs]);

  const updateConfig = useCallback(async (source, config) => {
    try {
      if (source === 'ibkr') {
        await api.updateIBKRConfig(config);
      } else {
        await api.updateFutuConfig(config);
      }
      await fetchConfigs();
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, [fetchConfigs]);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  return { configs, loading, error, refresh: fetchConfigs, testConnection, updateConfig };
};

/**
 * Hook for data import functionality
 */
export const useDataImport = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchLogs = useCallback(async (limit = 20) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getImportHistory(limit);
      setLogs(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  const importFinviz = useCallback(async (etfSymbol, data) => {
    try {
      const res = await api.importFinvizData({ etf_symbol: etfSymbol, data });
      await fetchLogs();
      return res.data;
    } catch (err) {
      return { success: false, message: err.response?.data?.detail || err.message };
    }
  }, [fetchLogs]);

  const importMarketChameleon = useCallback(async (etfSymbol, data) => {
    try {
      const res = await api.importMarketChameleonData({ etf_symbol: etfSymbol, data });
      await fetchLogs();
      return res.data;
    } catch (err) {
      return { success: false, message: err.response?.data?.detail || err.message };
    }
  }, [fetchLogs]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return { logs, loading, error, refresh: fetchLogs, importFinviz, importMarketChameleon };
};

/**
 * Hook for dashboard summary
 */
export const useDashboard = () => {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboard();
      setDashboard(res.data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  return { dashboard, loading, error, refresh: fetchDashboard };
};
