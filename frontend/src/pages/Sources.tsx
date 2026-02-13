import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dataSourcesApi } from '@/api/client';
import type { DataSource, DataSourceCreate } from '@/types';
import { format } from 'date-fns';
import {
  CheckCircle,
  AlertCircle,
  Clock,
  X,
  Loader2,
  AlertTriangle,
  Play,
  Pause,
  Trash2,
  Edit,
  Plus,
} from 'lucide-react';

function getHealthIcon(status: string) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="w-4 h-4 text-green-600" />;
    case 'error':
      return <AlertCircle className="w-4 h-4 text-red-600" />;
    default:
      return <Clock className="w-4 h-4 text-orange-600" />;
  }
}

interface TestResult {
  message: string;
  source_id: number;
  url: string;
  status: string;
  stage: string;
  title: string;
  stock_count: number;
  errors: string[];
  total_articles?: number;
}

interface ProgressUpdate {
  type: 'init' | 'progress' | 'complete' | 'error';
  message: string;
  stage?: string;
  total_articles?: number;
  current_article?: number;
  progress?: number;
  status?: string;
  source_id?: number;
  url?: string;
  title?: string;
  stock_count?: number;
  errors?: string[];
}

function TestStatusModal({
  isOpen,
  onClose,
  result,
  isLoading,
  error,
  currentMessage,
  totalArticles,
  currentArticle,
  progress,
  completedStages,
}: {
  isOpen: boolean;
  onClose: () => void;
  result?: TestResult;
  isLoading: boolean;
  error?: Error | null;
  currentMessage: string;
  totalArticles: number;
  currentArticle: number;
  progress: number;
  completedStages: string[];
}) {
  const stagesList = [
    { key: 'init', label: 'Initializing browser...' },
    { key: 'scraped', label: 'Loading page...' },
    { key: 'link_extraction_complete', label: 'Extracting article links...' },
    { key: 'article_fetched', label: 'Scraping content...' },
    { key: 'analyzed', label: 'Analyzing content with AI...' },
    { key: 'ner_complete', label: 'Extracting stock mentions...' },
    { key: 'finalized', label: 'Saving to database...' },
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold text-gray-900">Test Source</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
              disabled={isLoading}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {isLoading && (
            <div className="flex flex-col items-center justify-center py-8">
              <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
              <p className="text-gray-600 text-lg font-medium mb-2">{currentMessage}</p>

              {/* Progress info */}
              {totalArticles > 0 && (
                <p className="text-gray-500 text-sm mb-4">
                  Processing article {currentArticle} of {totalArticles}
                </p>
              )}

              {/* Progress Bar */}
              {totalArticles > 0 && (
                <div className="w-full max-w-md mb-4">
                  <div className="bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div
                      className="bg-primary h-full transition-all duration-300 ease-out"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 text-center mt-1">{progress}% complete</p>
                </div>
              )}

              {/* Stage indicators */}
              <div className="w-full max-w-md space-y-2 mb-4">
                {stagesList.map((stage, index) => {
                  const isCompleted = completedStages.includes(stage.key);
                  const isCurrent = currentMessage.includes(stage.label.split('...')[0]);

                  return (
                    <div
                      key={index}
                      className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-all duration-300 ${
                        isCurrent
                          ? 'bg-primary/10 border-2 border-primary'
                          : isCompleted
                          ? 'bg-green-50 border border-green-200'
                          : 'bg-gray-50 border border-gray-200'
                      }`}
                    >
                      {isCompleted ? (
                        <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
                      ) : isCurrent ? (
                        <Loader2 className="w-5 h-5 text-primary animate-spin flex-shrink-0" />
                      ) : (
                        <Clock className="w-5 h-5 text-gray-400 flex-shrink-0" />
                      )}
                      <span
                        className={`text-sm ${
                          isCurrent
                            ? 'text-primary font-semibold'
                            : isCompleted
                            ? 'text-green-700'
                            : 'text-gray-500'
                        }`}
                      >
                        {stage.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              <p className="text-gray-500 text-sm mt-2 text-center">
                This may take a few minutes for listing pages with multiple articles
              </p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-semibold text-red-900 mb-2">Test Failed</h4>
                  <p className="text-red-800 text-sm">{error.message}</p>
                </div>
              </div>
            </div>
          )}

          {result && !isLoading && (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex items-center gap-3">
                {result.status === 'success' || result.status === 'skipped' ? (
                  <CheckCircle className="w-8 h-8 text-green-600" />
                ) : (
                  <AlertCircle className="w-8 h-8 text-red-600" />
                )}
                <div>
                  <h4 className="font-semibold text-lg">
                    {result.status === 'success' ? 'Test Successful' :
                     result.status === 'skipped' ? 'Test Completed (Duplicate)' :
                     'Test Failed'}
                  </h4>
                  <p className="text-sm text-gray-600">Stage: {result.stage}</p>
                </div>
              </div>

              {/* Results */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Title:</span>
                    <p className="font-medium mt-1">{result.title || 'N/A'}</p>
                  </div>
                  <div>
                    <span className="text-gray-600">Stocks Found:</span>
                    <p className="font-medium mt-1">{result.stock_count}</p>
                  </div>
                </div>

                <div>
                  <span className="text-gray-600 text-sm">URL:</span>
                  <p className="text-sm font-medium mt-1 break-all">{result.url}</p>
                </div>
              </div>

              {/* Errors */}
              {result.errors && result.errors.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h5 className="font-semibold text-yellow-900 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Warnings/Errors
                  </h5>
                  <ul className="text-sm text-yellow-800 space-y-1">
                    {result.errors.map((err, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-yellow-600">•</span>
                        <span>{err}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Success Message */}
              {(result.status === 'success' || result.status === 'skipped') && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-green-800 text-sm">
                    {result.status === 'skipped'
                      ? 'This article was already processed (duplicate detected)'
                      : 'Source test completed successfully. The article was processed and saved to the database.'}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Close Button */}
          {!isLoading && (
            <div className="mt-6 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceForm({
  source,
  onClose
}: {
  source?: DataSource;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const isEdit = !!source;

  const [formData, setFormData] = useState<DataSourceCreate & { id?: number }>({
    id: source?.id,
    name: source?.name || '',
    url: source?.url || '',
    source_type: source?.source_type || 'website',
    fetch_frequency_minutes: source?.fetch_frequency_minutes || 60,
    cron_expression: source?.cron_expression || null,
    extraction_instructions: source?.extraction_instructions || null,
  });

  const mutation = useMutation({
    mutationFn: (data: typeof formData) =>
      isEdit
        ? dataSourcesApi.update(data.id!, data)
        : dataSourcesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          {isEdit ? 'Edit Source' : 'Add New Source'}
        </h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Name
          </label>
          <input
            type="text"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="e.g., Yahoo Finance"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            URL
          </label>
          <input
            type="url"
            required
            value={formData.url}
            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="https://finance.yahoo.com/news or https://youtube.com/watch?v=..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Source Type
          </label>
          <select
            value={formData.source_type}
            onChange={(e) => setFormData({ ...formData, source_type: e.target.value as 'website' | 'youtube' })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="website">Website</option>
            <option value="youtube">YouTube</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Fetch Frequency (minutes)
          </label>
          <input
            type="number"
            min="1"
            value={formData.fetch_frequency_minutes}
            onChange={(e) => setFormData({ ...formData, fetch_frequency_minutes: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Cron Expression (optional)
          </label>
          <input
            type="text"
            value={formData.cron_expression || ''}
            onChange={(e) => setFormData({ ...formData, cron_expression: e.target.value || null })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="e.g., 0 */4 * * * (every 4 hours)"
          />
          <p className="text-xs text-gray-500 mt-1">
            Leave empty to use frequency above. Cron takes precedence if set.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Extraction Instructions (optional)
          </label>
          <textarea
            value={formData.extraction_instructions || ''}
            onChange={(e) => setFormData({ ...formData, extraction_instructions: e.target.value || null })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            rows={4}
            placeholder="e.g., Articles are in the 'Latest News' section with class 'news-item'. Focus on links with 'Read more' text."
          />
          <p className="text-xs text-gray-500 mt-1">
            Provide specific instructions to help the agent extract articles from this source.
            Include CSS classes, section names, link patterns, or other details about the page structure.
          </p>
        </div>

        {mutation.isError && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800">
            Error {isEdit ? 'updating' : 'creating'} source: {(mutation.error as Error).message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? (isEdit ? 'Updating...' : 'Creating...') : (isEdit ? 'Update Source' : 'Create Source')}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function SourceCard({ source }: { source: DataSource }) {
  const queryClient = useQueryClient();
  const [showEditForm, setShowEditForm] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | undefined>();
  const [testError, setTestError] = useState<Error | null>(null);
  const [isTestingState, setIsTestingState] = useState(false);
  const [currentMessage, setCurrentMessage] = useState('Initializing...');
  const [totalArticles, setTotalArticles] = useState(0);
  const [currentArticle, setCurrentArticle] = useState(0);
  const [progress, setProgress] = useState(0);
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const eventSourceRef = useState<EventSource | null>(null)[0];

  const statusMutation = useMutation({
    mutationFn: (status: 'active' | 'paused') =>
      dataSourcesApi.updateStatus(source.id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => dataSourcesApi.delete(source.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  const handleTest = () => {
    setShowTestModal(true);
    setIsTestingState(true);
    setTestError(null);
    setTestResult(undefined);
    setCurrentMessage('Initializing...');
    setTotalArticles(0);
    setCurrentArticle(0);
    setProgress(0);
    setCompletedStages([]);

    // Use EventSource for SSE
    const eventSource = new EventSource(`/api/v1/sources/${source.id}/test`);

    eventSource.onmessage = (event) => {
      const data: ProgressUpdate = JSON.parse(event.data);

      if (data.type === 'init') {
        setCurrentMessage(data.message);
      } else if (data.type === 'progress') {
        setCurrentMessage(data.message);
        if (data.total_articles) setTotalArticles(data.total_articles);
        if (data.current_article !== undefined) setCurrentArticle(data.current_article);
        if (data.progress !== undefined) setProgress(data.progress);
        if (data.stage) {
          setCompletedStages(prev => {
            if (!prev.includes(data.stage!)) {
              return [...prev, data.stage!];
            }
            return prev;
          });
        }
      } else if (data.type === 'complete') {
        setIsTestingState(false);
        setTestResult({
          message: data.message,
          source_id: data.source_id!,
          url: data.url!,
          status: data.status!,
          stage: data.stage!,
          title: data.title || 'N/A',
          stock_count: data.stock_count || 0,
          errors: data.errors || [],
          total_articles: data.total_articles
        });
        eventSource.close();
        queryClient.invalidateQueries({ queryKey: ['sources'] });
      } else if (data.type === 'error') {
        setIsTestingState(false);
        setTestError(new Error(data.message));
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      setIsTestingState(false);
      setTestError(new Error('Connection error. The server may have stopped responding.'));
      eventSource.close();
    };
  };

  const handleCloseTestModal = () => {
    setShowTestModal(false);
    if (eventSourceRef) {
      eventSourceRef.close();
    }
    setTestResult(undefined);
    setTestError(null);
    setIsTestingState(false);
  };

  if (showEditForm) {
    return <SourceForm source={source} onClose={() => setShowEditForm(false)} />;
  }

  return (
    <>
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-lg font-semibold text-gray-900">{source.name}</h3>
              {getHealthIcon(source.health_status)}
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                source.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {source.status}
              </span>
            </div>
            <p className="text-sm text-gray-600 break-all">{source.url}</p>
            {source.extraction_instructions && (
              <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs">
                <strong className="text-blue-900">Extraction Instructions:</strong>
                <p className="text-blue-800 mt-1">{source.extraction_instructions}</p>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <div>
            <span className="text-gray-600">Type:</span>
            <span className="ml-2 font-medium capitalize">{source.source_type}</span>
          </div>
          <div>
            <span className="text-gray-600">Frequency:</span>
            <span className="ml-2 font-medium">
              {source.cron_expression || `${source.fetch_frequency_minutes}min`}
            </span>
          </div>
          <div>
            <span className="text-gray-600">Last Fetch:</span>
            <span className="ml-2 font-medium">
              {source.last_fetch_timestamp
                ? format(new Date(source.last_fetch_timestamp), 'MMM d, h:mm a')
                : 'Never'}
            </span>
          </div>
          <div>
            <span className="text-gray-600">Errors:</span>
            <span className={`ml-2 font-medium ${source.error_count > 0 ? 'text-red-600' : ''}`}>
              {source.error_count}
            </span>
          </div>
        </div>

        {source.error_message && (
          <div className="bg-red-50 border border-red-200 rounded p-2 text-sm text-red-800 mb-4">
            {source.error_message}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={() => setShowEditForm(true)}
            className="flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium transition-colors"
          >
            <Edit className="w-4 h-4" />
            Edit
          </button>
          <button
            onClick={() => statusMutation.mutate(source.status === 'active' ? 'paused' : 'active')}
            disabled={statusMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium transition-colors"
          >
            {source.status === 'active' ? (
              <>
                <Pause className="w-4 h-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Resume
              </>
            )}
          </button>
          <button
            onClick={handleTest}
            disabled={isTestingState}
            className="px-3 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded text-sm font-medium transition-colors disabled:opacity-50"
          >
            {isTestingState ? 'Testing...' : 'Test Now'}
          </button>
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded text-sm font-medium transition-colors ml-auto"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      </div>

      <TestStatusModal
        isOpen={showTestModal}
        onClose={handleCloseTestModal}
        result={testResult}
        isLoading={isTestingState}
        error={testError}
        currentMessage={currentMessage}
        totalArticles={totalArticles}
        currentArticle={currentArticle}
        progress={progress}
        completedStages={completedStages}
      />
    </>
  );
}

export function Sources() {
  const [showAddForm, setShowAddForm] = useState(false);

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => dataSourcesApi.list(),
    refetchInterval: 10000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Data Sources</h2>
          <p className="text-gray-600 mt-1">
            Manage your news sources and schedules
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-lg font-medium transition-colors"
        >
          <Plus className="w-5 h-5" />
          Add Source
        </button>
      </div>

      {showAddForm && <SourceForm onClose={() => setShowAddForm(false)} />}

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {sources && sources.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">
            No data sources yet. Click "Add Source" to get started!
          </p>
        </div>
      )}

      {sources && sources.length > 0 && (
        <div className="grid gap-4">
          {sources.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </div>
      )}
    </div>
  );
}
