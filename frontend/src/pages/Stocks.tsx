import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stocksApi } from '@/api/client';
import type { NewsArticle } from '@/types';
import { TrendingUp, TrendingDown, Minus, X, Loader2, ExternalLink } from 'lucide-react';

function getSentimentIcon(score: number) {
  if (score > 0.3) return <TrendingUp className="w-5 h-5 text-green-600" />;
  if (score < -0.3) return <TrendingDown className="w-5 h-5 text-red-600" />;
  return <Minus className="w-5 h-5 text-gray-400" />;
}

function getSentimentColor(score: number) {
  if (score > 0.3) return 'text-green-600 bg-green-50';
  if (score < -0.3) return 'text-red-600 bg-red-50';
  return 'text-gray-600 bg-gray-50';
}

function MentionsModal({
  ticker,
  companyName,
  onClose,
}: {
  ticker: string;
  companyName: string;
  onClose: () => void;
}) {
  const { data: articles, isLoading } = useQuery({
    queryKey: ['stock-articles', ticker],
    queryFn: () => stocksApi.articles(ticker),
  });

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div>
            <h3 className="text-xl font-bold text-gray-900">
              {ticker} — Articles
            </h3>
            <p className="text-sm text-gray-600 mt-1">{companyName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-auto flex-1">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
            </div>
          )}

          {articles && articles.length === 0 && (
            <p className="text-gray-500 text-center py-8">No articles found.</p>
          )}

          {articles && articles.length > 0 && (
            <div className="space-y-4">
              {articles.map((article: NewsArticle) => {
                const mention = article.stock_mentions?.find(
                  (m) => m.ticker_symbol === ticker
                );
                return (
                  <div
                    key={article.id}
                    className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-gray-900 truncate">
                          {article.title || 'Untitled'}
                        </h4>
                        {article.summary && (
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                            {article.summary}
                          </p>
                        )}
                        {mention?.context_snippet && (
                          <p className="text-xs text-gray-500 mt-2 italic border-l-2 border-gray-300 pl-2">
                            "{mention.context_snippet}"
                          </p>
                        )}
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                          <span>
                            {new Date(article.fetched_at).toLocaleDateString()}
                          </span>
                          {mention && (
                            <span
                              className={`px-2 py-0.5 rounded font-medium ${getSentimentColor(
                                mention.sentiment_score
                              )}`}
                            >
                              Sentiment: {mention.sentiment_score > 0 ? '+' : ''}
                              {mention.sentiment_score.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-primary flex-shrink-0"
                        title="Open article"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-200 flex justify-end flex-shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export function Stocks() {
  const [mentionsModal, setMentionsModal] = useState<{
    ticker: string;
    companyName: string;
  } | null>(null);

  const { data: stocks, isLoading } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => stocksApi.list(),
    refetchInterval: 30000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Stock Analysis</h2>
        <p className="text-gray-600 mt-1">
          Sentiment analysis for mentioned stocks
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {stocks && stocks.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">
            No stock mentions yet. Add news sources to start tracking!
          </p>
        </div>
      )}

      {stocks && stocks.length > 0 && (
        <div className="grid gap-4">
          {stocks.map((stock) => (
            <div
              key={stock.ticker_symbol}
              className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-xl font-bold text-gray-900">
                      {stock.ticker_symbol}
                    </h3>
                    {getSentimentIcon(stock.avg_sentiment)}
                  </div>
                  <p className="text-gray-600 mb-4">{stock.company_name}</p>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Mentions:</span>
                      <button
                        onClick={() =>
                          setMentionsModal({
                            ticker: stock.ticker_symbol,
                            companyName: stock.company_name,
                          })
                        }
                        className="ml-2 font-medium text-primary hover:text-primary/80 underline underline-offset-2 cursor-pointer"
                      >
                        {stock.mention_count}
                      </button>
                    </div>
                    <div>
                      <span className="text-gray-600">Avg Sentiment:</span>
                      <span
                        className={`ml-2 font-medium px-2 py-1 rounded ${getSentimentColor(
                          stock.avg_sentiment
                        )}`}
                      >
                        {stock.avg_sentiment > 0 ? '+' : ''}
                        {stock.avg_sentiment.toFixed(3)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Latest:</span>
                      <span className="ml-2 font-medium">
                        {new Date(stock.latest_mention).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {mentionsModal && (
        <MentionsModal
          ticker={mentionsModal.ticker}
          companyName={mentionsModal.companyName}
          onClose={() => setMentionsModal(null)}
        />
      )}
    </div>
  );
}
