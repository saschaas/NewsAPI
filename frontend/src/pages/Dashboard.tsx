import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { articlesApi } from '@/api/client';
import { formatFullDateTime, formatShortDateTime } from '@/utils/date';
import { ExternalLink, TrendingUp, TrendingDown, Minus, AlertCircle, Globe, Youtube, Rss } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { NewsArticle } from '@/types';

// ---------------------------------------------------------------------------
// Date range options
// ---------------------------------------------------------------------------

interface DateRange {
  key: string;
  label: string;
  days: number;
}

const DATE_RANGES: DateRange[] = [
  { key: '2d', label: 'Last 2 Days', days: 2 },
  { key: '30d', label: 'Last 30 Days', days: 30 },
  { key: '6m', label: 'Last 6 Months', days: 180 },
];

function getFromDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSentimentIcon(score: number) {
  if (score > 0.3) return <TrendingUp className="w-4 h-4 text-green-600" />;
  if (score < -0.3) return <TrendingDown className="w-4 h-4 text-red-600" />;
  return <Minus className="w-4 h-4 text-gray-400" />;
}

function getSourceIcon(sourceType: string | null) {
  switch (sourceType) {
    case 'youtube': return <Youtube className="w-3.5 h-3.5" />;
    case 'rss': return <Rss className="w-3.5 h-3.5" />;
    default: return <Globe className="w-3.5 h-3.5" />;
  }
}

function getSentimentColor(score: number) {
  if (score > 0.3) return 'bg-green-100 text-green-800';
  if (score < -0.3) return 'bg-red-100 text-red-800';
  return 'bg-gray-100 text-gray-800';
}

function NewsCard({ article }: { article: NewsArticle }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="text-lg font-semibold text-gray-900 flex-1">
          {article.title}
        </h3>
        {article.is_high_impact && (
          <span className="flex-shrink-0 inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded">
            <AlertCircle className="w-3 h-3" />
            High Impact
          </span>
        )}
      </div>

      {/* Summary */}
      {article.summary && (
        <p className="text-gray-700 mb-4 line-clamp-2">{article.summary}</p>
      )}

      {/* Stock Mentions */}
      {article.stock_mentions.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {article.stock_mentions.map((stock) => (
            <div
              key={stock.id}
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getSentimentColor(
                stock.sentiment_score
              )}`}
            >
              {getSentimentIcon(stock.sentiment_score)}
              <span>{stock.ticker_symbol}</span>
              <span className="text-xs opacity-75">
                {stock.sentiment_score > 0 ? '+' : ''}
                {stock.sentiment_score.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center gap-4">
          {article.source_name && (
            <span className="inline-flex items-center gap-1.5 text-gray-600">
              {getSourceIcon(article.source_type)}
              {article.source_name}
            </span>
          )}
          {article.author && <span>{article.author}</span>}
          {article.main_topic && (
            <span className="px-2 py-1 bg-gray-100 rounded text-xs">
              {article.main_topic}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {article.published_date ? (
            <div className="flex flex-col items-end">
              <time className="font-medium text-gray-700">
                {formatFullDateTime(article.published_date)}
              </time>
              <span className="text-xs text-gray-400">
                Published
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-end">
              <time>
                {formatShortDateTime(article.fetched_at)}
              </time>
              <span className="text-xs text-gray-400">
                Fetched
              </span>
            </div>
          )}
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:text-primary/80"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [dateRange, setDateRange] = useState('2d');
  const selectedRange = DATE_RANGES.find((r) => r.key === dateRange) ?? DATE_RANGES[0];

  const { data: articles, isLoading, error } = useQuery({
    queryKey: ['articles', dateRange],
    queryFn: () =>
      articlesApi.list({
        limit: 50,
        sort: 'published_date',
        order: 'desc',
        from_date: getFromDate(selectedRange.days),
      }),
    refetchInterval: 30000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">News Feed</h2>
          <p className="text-gray-600 mt-1">
            Latest stock market news and analysis
          </p>
        </div>

        {/* Date range selector */}
        <div className="flex gap-2">
          {DATE_RANGES.map((range) => (
            <button
              key={range.key}
              onClick={() => setDateRange(range.key)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                dateRange === range.key
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50',
              )}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600">Loading articles...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          Error loading articles: {error.message}
        </div>
      )}

      {articles && articles.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">
            No articles found for the selected time range. Try expanding the date range or add a data source to get started!
          </p>
        </div>
      )}

      {articles && articles.length > 0 && (
        <div className="space-y-4">
          {articles.map((article) => (
            <NewsCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
