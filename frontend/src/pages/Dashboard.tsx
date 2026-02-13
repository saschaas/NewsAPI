import { useQuery } from '@tanstack/react-query';
import { articlesApi } from '@/api/client';
import { format } from 'date-fns';
import { ExternalLink, TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';
import type { NewsArticle } from '@/types';

function getSentimentIcon(score: number) {
  if (score > 0.3) return <TrendingUp className="w-4 h-4 text-green-600" />;
  if (score < -0.3) return <TrendingDown className="w-4 h-4 text-red-600" />;
  return <Minus className="w-4 h-4 text-gray-400" />;
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
                {format(new Date(article.published_date), 'MMM d, yyyy h:mm a')}
              </time>
              <span className="text-xs text-gray-400">
                Published
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-end">
              <time>
                {format(new Date(article.fetched_at), 'MMM d, h:mm a')}
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
  const { data: articles, isLoading, error } = useQuery({
    queryKey: ['articles'],
    queryFn: () => articlesApi.list({ limit: 50, sort: 'published_date', order: 'desc' }),
    refetchInterval: 30000, // 30 seconds
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">News Feed</h2>
        <p className="text-gray-600 mt-1">
          Latest stock market news and analysis
        </p>
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
            No articles yet. Add a data source to get started!
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
