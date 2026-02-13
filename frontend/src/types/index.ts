export interface DataSource {
  id: number;
  name: string;
  url: string;
  source_type: 'website' | 'youtube';
  status: 'active' | 'paused' | 'deleted';
  health_status: 'healthy' | 'pending' | 'error';
  fetch_frequency_minutes: number;
  cron_expression: string | null;
  extraction_instructions: string | null;
  last_fetch_timestamp: string | null;
  last_fetch_status: 'success' | 'error' | 'captcha' | 'timeout' | null;
  error_message: string | null;
  error_count: number;
  created_at: string;
  updated_at: string;
}

export interface DataSourceCreate {
  name: string;
  url: string;
  source_type: 'website' | 'youtube';
  fetch_frequency_minutes: number;
  cron_expression: string | null;
  extraction_instructions?: string | null;
}

export interface StockMention {
  id: number;
  ticker_symbol: string;
  company_name: string;
  stock_exchange: string | null;
  market_segment: string | null;
  sentiment_score: number;
  sentiment_label: 'very_negative' | 'negative' | 'neutral' | 'positive' | 'very_positive' | null;
  confidence_score: number | null;
  context_snippet: string | null;
}

export interface NewsArticle {
  id: number;
  data_source_id: number;
  url: string;
  title: string;
  content: string;
  summary: string | null;
  main_topic: string | null;
  author: string | null;
  published_date: string | null;
  fetched_at: string;
  is_high_impact: boolean;
  stock_mentions: StockMention[];
}

export interface StockInfo {
  ticker_symbol: string;
  company_name: string;
  mention_count: number;
  avg_sentiment: number;
  latest_mention: string;
}

export interface StockSentimentTrend {
  date: string;
  avg_sentiment: number;
  mention_count: number;
}

export interface StockDetail {
  ticker_symbol: string;
  company_name: string;
  total_mentions: number;
  avg_sentiment: number;
  sentiment_trend: StockSentimentTrend[];
}

export interface HealthCheck {
  status: string;
  timestamp: string;
  database: string;
  ollama: string;
}

export interface SystemStatus {
  active_sources: number;
  paused_sources: number;
  total_articles: number;
  processing_queue_size: number;
  global_pause: boolean;
  ollama_status: string;
}

export interface SchedulerStatus {
  is_running: boolean;
  total_jobs: number;
  active_jobs: number;
  paused_jobs: number;
  global_pause: boolean;
}
