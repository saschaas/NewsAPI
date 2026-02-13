import { useQuery } from '@tanstack/react-query';
import { stocksApi } from '@/api/client';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

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

export function Stocks() {
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
                      <span className="ml-2 font-medium">
                        {stock.mention_count}
                      </span>
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
    </div>
  );
}
