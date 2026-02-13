import axios from 'axios';
import type {
  DataSource,
  NewsArticle,
  StockInfo,
  StockDetail,
  HealthCheck,
  SystemStatus,
  SchedulerStatus,
} from '@/types';

const API_BASE = '/api/v1';

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Data Sources
export const dataSourcesApi = {
  list: async (): Promise<DataSource[]> => {
    const { data } = await client.get('/sources/');
    return data.sources;
  },

  get: async (id: number): Promise<DataSource> => {
    const { data } = await client.get(`/sources/${id}/`);
    return data;
  },

  create: async (source: Partial<DataSource>): Promise<DataSource> => {
    const { data } = await client.post('/sources/', source);
    return data;
  },

  update: async (id: number, source: Partial<DataSource>): Promise<DataSource> => {
    const { data } = await client.put(`/sources/${id}`, source);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await client.delete(`/sources/${id}`);
  },

  updateStatus: async (id: number, status: 'active' | 'paused'): Promise<DataSource> => {
    const { data } = await client.patch(`/sources/${id}/status`, { status });
    return data;
  },

  test: async (id: number): Promise<any> => {
    const { data } = await client.post(`/sources/${id}/test`, {}, {
      timeout: 900000, // 15 minutes for long-running test operations
    });
    return data;
  },
};

// Articles
export const articlesApi = {
  list: async (params?: {
    page?: number;
    limit?: number;
    source_id?: number;
    ticker?: string;
    from_date?: string;
    to_date?: string;
    sentiment?: string;
    high_impact?: boolean;
    sort?: string;
    order?: 'asc' | 'desc';
  }): Promise<NewsArticle[]> => {
    const { data } = await client.get('/articles/', { params });
    return data;
  },

  get: async (id: number): Promise<NewsArticle> => {
    const { data } = await client.get(`/articles/${id}/`);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await client.delete(`/articles/${id}`);
  },
};

// Stocks
export const stocksApi = {
  list: async (limit = 50): Promise<StockInfo[]> => {
    const { data } = await client.get('/stocks/', { params: { limit } });
    return data;
  },

  get: async (ticker: string): Promise<StockDetail> => {
    const { data } = await client.get(`/stocks/${ticker}/`);
    return data;
  },

  articles: async (ticker: string, limit = 20): Promise<NewsArticle[]> => {
    const { data } = await client.get(`/stocks/${ticker}/articles/`, { params: { limit } });
    return data;
  },

  sentiment: async (ticker: string, days = 30): Promise<any> => {
    const { data} = await client.get(`/stocks/${ticker}/sentiment/`, { params: { days } });
    return data;
  },
};

// System
export const systemApi = {
  health: async (): Promise<HealthCheck> => {
    const { data } = await client.get('/health/');
    return data;
  },

  status: async (): Promise<SystemStatus> => {
    const { data } = await client.get('/status/');
    return data;
  },
};

// Scheduler
export const schedulerApi = {
  status: async (): Promise<SchedulerStatus> => {
    const { data } = await client.get('/scheduler/status/');
    return data;
  },

  pause: async (paused: boolean): Promise<any> => {
    const { data } = await client.post('/scheduler/pause', { paused });
    return data;
  },

  trigger: async (sourceId: number): Promise<any> => {
    const { data } = await client.post(`/scheduler/trigger/${sourceId}`);
    return data;
  },
};

// Database
export const databaseApi = {
  stats: async (): Promise<any> => {
    const { data } = await client.get('/database/stats');
    return data;
  },

  deleteAllArticles: async (): Promise<any> => {
    const { data } = await client.delete('/database/articles');
    return data;
  },
};

export default client;
