import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stocksApi } from '@/api/client';
import type { NewsArticle, StockInfo } from '@/types';
import {
  TrendingUp, TrendingDown, Minus, X, Loader2, ExternalLink,
  BarChart3, Bitcoin, Landmark, Globe2, Users, Fuel, DollarSign, Layers, LayoutGrid,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDate, formatShortDateTime } from '@/utils/date';

// ---------------------------------------------------------------------------
// Category definitions
// ---------------------------------------------------------------------------

interface CategoryDef {
  key: string;
  label: string;
  icon: React.ElementType;
  color: string;          // Tailwind ring / accent colour
  description: string;
}

const CATEGORIES: CategoryDef[] = [
  { key: 'all',           label: 'All',             icon: LayoutGrid,  color: 'blue',    description: 'All market entities' },
  { key: 'stocks',        label: 'Stocks',          icon: TrendingUp,  color: 'emerald', description: 'Publicly traded companies' },
  { key: 'indices',       label: 'Indices',         icon: BarChart3,   color: 'violet',  description: 'Market indices (DAX, DOW, etc.)' },
  { key: 'crypto',        label: 'Crypto',          icon: Bitcoin,     color: 'amber',   description: 'Cryptocurrencies' },
  { key: 'commodities',   label: 'Commodities',     icon: Fuel,        color: 'orange',  description: 'Oil, Gas, Gold, etc.' },
  { key: 'central_banks', label: 'Central Banks',   icon: Landmark,    color: 'sky',     description: 'FED, ECB, BOJ, etc.' },
  { key: 'countries',     label: 'Countries',       icon: Globe2,      color: 'teal',    description: 'Countries & unions' },
  { key: 'organisations', label: 'Organisations',   icon: Layers,      color: 'indigo',  description: 'NATO, OPEC, IMF, etc.' },
  { key: 'people',        label: 'People',          icon: Users,       color: 'pink',    description: 'Public figures' },
  { key: 'currencies',    label: 'Currencies',      icon: DollarSign,  color: 'lime',    description: 'USD, EUR, GBP, etc.' },
  { key: 'other',         label: 'Other',           icon: Minus,       color: 'gray',    description: 'Uncategorised mentions' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function categoryBadgeClasses(color: string) {
  const map: Record<string, string> = {
    blue:    'bg-blue-50 text-blue-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    violet:  'bg-violet-50 text-violet-700',
    amber:   'bg-amber-50 text-amber-700',
    orange:  'bg-orange-50 text-orange-700',
    sky:     'bg-sky-50 text-sky-700',
    teal:    'bg-teal-50 text-teal-700',
    indigo:  'bg-indigo-50 text-indigo-700',
    pink:    'bg-pink-50 text-pink-700',
    lime:    'bg-lime-50 text-lime-700',
    gray:    'bg-gray-50 text-gray-600',
  };
  return map[color] ?? map.gray;
}

// ---------------------------------------------------------------------------
// Mentions modal (reused from old Stocks page)
// ---------------------------------------------------------------------------

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
            <h3 className="text-xl font-bold text-gray-900">{ticker} — Articles</h3>
            <p className="text-sm text-gray-600 mt-1">{companyName}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
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
                  (m) => m.ticker_symbol === ticker,
                );
                return (
                  <div key={article.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-gray-900 truncate">
                          {article.title || 'Untitled'}
                        </h4>
                        {article.summary && (
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">{article.summary}</p>
                        )}
                        {mention?.context_snippet && (
                          <p className="text-xs text-gray-500 mt-2 italic border-l-2 border-gray-300 pl-2">
                            "{mention.context_snippet}"
                          </p>
                        )}
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                          <span>{formatShortDateTime(article.fetched_at)}</span>
                          {mention && (
                            <span className={`px-2 py-0.5 rounded font-medium ${getSentimentColor(mention.sentiment_score)}`}>
                              Sentiment: {mention.sentiment_score > 0 ? '+' : ''}
                              {mention.sentiment_score.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>
                      <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-primary flex-shrink-0" title="Open article">
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
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity card
// ---------------------------------------------------------------------------

function EntityCard({ entity, onMentionsClick }: { entity: StockInfo; onMentionsClick: () => void }) {
  const catDef = CATEGORIES.find((c) => c.key === entity.category) ?? CATEGORIES[CATEGORIES.length - 1];

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-xl font-bold text-gray-900">{entity.ticker_symbol}</h3>
            {getSentimentIcon(entity.avg_sentiment)}
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryBadgeClasses(catDef.color)}`}>
              {catDef.label}
            </span>
          </div>
          <p className="text-gray-600 mb-4">{entity.company_name}</p>

          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Mentions:</span>
              <button
                onClick={onMentionsClick}
                className="ml-2 font-medium text-primary hover:text-primary/80 underline underline-offset-2 cursor-pointer"
              >
                {entity.mention_count}
              </button>
            </div>
            <div>
              <span className="text-gray-600">Avg Sentiment:</span>
              <span className={`ml-2 font-medium px-2 py-1 rounded ${getSentimentColor(entity.avg_sentiment)}`}>
                {entity.avg_sentiment > 0 ? '+' : ''}
                {entity.avg_sentiment.toFixed(3)}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Latest:</span>
              <span className="ml-2 font-medium">
                {formatDate(entity.latest_mention)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function Market() {
  const [activeCategory, setActiveCategory] = useState('all');
  const [mentionsModal, setMentionsModal] = useState<{ ticker: string; companyName: string } | null>(null);

  const { data: entities, isLoading } = useQuery({
    queryKey: ['market-entities', activeCategory],
    queryFn: () => stocksApi.list(200, activeCategory === 'all' ? undefined : activeCategory),
    refetchInterval: 30000,
  });

  // Count per category for the badges (use the "all" query for counts)
  const { data: allEntities } = useQuery({
    queryKey: ['market-entities', 'all'],
    queryFn: () => stocksApi.list(500),
    refetchInterval: 30000,
  });

  const categoryCounts: Record<string, number> = {};
  if (allEntities) {
    let total = 0;
    for (const e of allEntities) {
      const cat = e.category ?? 'other';
      categoryCounts[cat] = (categoryCounts[cat] ?? 0) + 1;
      total++;
    }
    categoryCounts['all'] = total;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Market</h2>
        <p className="text-gray-600 mt-1">
          Entities mentioned in news — stocks, indices, crypto, commodities, and more
        </p>
      </div>

      {/* Category tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => {
          const count = categoryCounts[cat.key] ?? 0;
          const isActive = activeCategory === cat.key;
          const Icon = cat.icon;
          // Hide tabs with 0 items (except "all" and the currently active one)
          if (count === 0 && cat.key !== 'all' && !isActive) return null;
          return (
            <button
              key={cat.key}
              onClick={() => setActiveCategory(cat.key)}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50',
              )}
            >
              <Icon className="w-4 h-4" />
              {cat.label}
              {count > 0 && (
                <span
                  className={cn(
                    'ml-1 text-xs px-1.5 py-0.5 rounded-full',
                    isActive ? 'bg-white/20 text-primary-foreground' : 'bg-gray-100 text-gray-500',
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Empty state */}
      {entities && entities.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">
            {activeCategory === 'all'
              ? 'No market entities yet. Add news sources to start tracking!'
              : `No ${CATEGORIES.find((c) => c.key === activeCategory)?.label.toLowerCase() ?? 'entities'} found.`}
          </p>
        </div>
      )}

      {/* Entity grid */}
      {entities && entities.length > 0 && (
        <div className="grid gap-4">
          {entities.map((entity) => (
            <EntityCard
              key={`${entity.ticker_symbol}-${entity.company_name}`}
              entity={entity}
              onMentionsClick={() =>
                setMentionsModal({ ticker: entity.ticker_symbol, companyName: entity.company_name })
              }
            />
          ))}
        </div>
      )}

      {/* Modal */}
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
