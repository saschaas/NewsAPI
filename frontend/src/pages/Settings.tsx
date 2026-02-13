import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { databaseApi } from '@/api/client';
import { Database, Trash2, TrendingUp, TrendingDown, Minus } from 'lucide-react';

function getSentimentIcon(score: number) {
  if (score > 0.3) return <TrendingUp className="w-4 h-4 text-green-600" />;
  if (score < -0.3) return <TrendingDown className="w-4 h-4 text-red-600" />;
  return <Minus className="w-4 h-4 text-gray-400" />;
}

function getSentimentColor(score: number) {
  if (score > 0.3) return 'text-green-600';
  if (score < -0.3) return 'text-red-600';
  return 'text-gray-600';
}

export function Settings() {
  const queryClient = useQueryClient();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['database-stats'],
    queryFn: () => databaseApi.stats(),
    refetchInterval: 30000,
  });

  const deleteArticlesMutation = useMutation({
    mutationFn: () => databaseApi.deleteAllArticles(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['database-stats'] });
      queryClient.invalidateQueries({ queryKey: ['articles'] });
      setShowDeleteConfirm(false);
    },
  });

  const handleDeleteAll = () => {
    deleteArticlesMutation.mutate();
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Database Settings</h2>
        <p className="text-gray-600 mt-1">
          Manage your database and view statistics
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600">Loading statistics...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          Error loading statistics: {(error as Error).message}
        </div>
      )}

      {stats && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Database className="w-6 h-6 text-primary" />
              <h3 className="text-lg font-semibold text-gray-900">Database Overview</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-600 font-medium mb-1">Total Articles</p>
                <p className="text-3xl font-bold text-blue-900">{stats.total_articles}</p>
              </div>

              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-sm text-green-600 font-medium mb-1">Unique Stocks</p>
                <p className="text-3xl font-bold text-green-900">{stats.unique_stocks}</p>
              </div>

              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <p className="text-sm text-purple-600 font-medium mb-1">Total Stock Mentions</p>
                <p className="text-3xl font-bold text-purple-900">{stats.total_stock_mentions}</p>
              </div>
            </div>

            {stats.articles_by_source && stats.articles_by_source.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Articles by Source</h4>
                <div className="space-y-2">
                  {stats.articles_by_source.map((source: any, index: number) => (
                    <div key={index} className="flex items-center justify-between bg-gray-50 rounded px-3 py-2">
                      <span className="text-sm text-gray-700">{source.source_name}</span>
                      <span className="text-sm font-semibold text-gray-900">{source.count} articles</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Top 10 Most Mentioned Stocks</h3>

            {stats.top_stocks && stats.top_stocks.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Rank</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Ticker</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Company</th>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">Mentions</th>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">Avg Sentiment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.top_stocks.map((stock: any, index: number) => (
                      <tr key={stock.ticker_symbol} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4 text-sm text-gray-600">{index + 1}</td>
                        <td className="py-3 px-4">
                          <span className="text-sm font-semibold text-gray-900">{stock.ticker_symbol}</span>
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-700">{stock.company_name}</td>
                        <td className="py-3 px-4 text-right">
                          <span className="inline-flex items-center px-2 py-1 bg-gray-100 text-gray-800 text-xs font-medium rounded">
                            {stock.mention_count}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {getSentimentIcon(stock.avg_sentiment)}
                            <span className={`text-sm font-medium ${getSentimentColor(stock.avg_sentiment)}`}>
                              {stock.avg_sentiment > 0 ? '+' : ''}{stock.avg_sentiment.toFixed(3)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">No stock data available</p>
            )}
          </div>

          <div className="bg-white border border-red-200 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Trash2 className="w-6 h-6 text-red-600" />
              <h3 className="text-lg font-semibold text-red-900">Danger Zone</h3>
            </div>

            <p className="text-sm text-gray-600 mb-4">
              Delete all articles and stock mentions from the database. This action cannot be undone.
            </p>

            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Delete All Articles
              </button>
            ) : (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm text-red-800 font-semibold mb-3">
                  Are you sure? This will permanently delete {stats.total_articles} articles and {stats.total_stock_mentions} stock mentions.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleDeleteAll}
                    disabled={deleteArticlesMutation.isPending}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleteArticlesMutation.isPending ? 'Deleting...' : 'Yes, Delete Everything'}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleteArticlesMutation.isPending}
                    className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Cancel
                  </button>
                </div>
                {deleteArticlesMutation.isError && (
                  <p className="text-sm text-red-600 mt-2">
                    Error: {(deleteArticlesMutation.error as Error)?.message || 'Failed to delete articles'}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
