import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings, Plus, Trash2, Save } from 'lucide-react';

interface LLMConfig {
  available_models: string[];
  model_assignments: Record<string, string>;
}

// API calls (will be added to client.ts later)
const configApi = {
  get: async () => {
    const response = await fetch('/api/v1/config/llm');
    if (!response.ok) throw new Error('Failed to fetch config');
    return response.json();
  },

  update: async (config: any) => {
    const response = await fetch('/api/v1/config/llm', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error('Failed to update config');
    return response.json();
  },

  deleteModel: async (modelName: string) => {
    const response = await fetch(`/api/v1/config/llm/models/${modelName}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete model');
    return response.json();
  },
};

const workflowSteps = [
  { key: 'scraper', label: 'Scraper', description: 'Extracts article links from listing pages' },
  { key: 'link_extractor', label: 'Link Extractor', description: 'Identifies article URLs on pages' },
  { key: 'analyzer', label: 'Content Analyzer', description: 'Analyzes article content and extracts metadata' },
  { key: 'ner', label: 'Stock Extraction (NER)', description: 'Identifies stock tickers and company names' },
];

export function Config() {
  const queryClient = useQueryClient();
  const [newModelName, setNewModelName] = useState('');
  const [modelAssignments, setModelAssignments] = useState<Record<string, string>>({});
  const [isPulling, setIsPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<string>('');

  const { data: config, isLoading, error } = useQuery<LLMConfig>({
    queryKey: ['llm-config'],
    queryFn: () => configApi.get(),
  });

  // Update model assignments when config loads
  useEffect(() => {
    if (config) {
      setModelAssignments(config.model_assignments || {});
    }
  }, [config]);

  const updateConfigMutation = useMutation({
    mutationFn: (config: any) => configApi.update(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-config'] });
    },
  });

  const pullModel = async (modelName: string) => {
    setIsPulling(true);
    setPullProgress('Starting download...');

    try {
      const response = await fetch('/api/v1/config/llm/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName }),
      });

      if (!response.ok) {
        throw new Error('Failed to start model pull');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.error) {
                setPullProgress(`Error: ${data.error}`);
                throw new Error(data.error);
              }

              if (data.status) {
                let progress = data.status;
                if (data.completed && data.total) {
                  const percent = Math.round((data.completed / data.total) * 100);
                  progress += ` (${percent}%)`;
                }
                setPullProgress(progress);
              }
            } catch (e) {
              console.warn('Failed to parse progress:', line);
            }
          }
        }
      }

      setPullProgress('Download complete!');
      setTimeout(() => {
        setIsPulling(false);
        setPullProgress('');
        setNewModelName('');
        queryClient.invalidateQueries({ queryKey: ['llm-config'] });
      }, 2000);
    } catch (error) {
      setPullProgress(`Error: ${(error as Error).message}`);
      setTimeout(() => {
        setIsPulling(false);
        setPullProgress('');
      }, 3000);
    }
  };

  const deleteModelMutation = useMutation({
    mutationFn: (modelName: string) => configApi.deleteModel(modelName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-config'] });
    },
  });

  const handleSaveConfig = () => {
    updateConfigMutation.mutate({
      model_assignments: modelAssignments,
    });
  };

  const handleAddModel = (e: React.FormEvent) => {
    e.preventDefault();
    if (newModelName.trim() && !isPulling) {
      pullModel(newModelName.trim());
    }
  };

  const handleModelChange = (step: string, model: string) => {
    setModelAssignments(prev => ({
      ...prev,
      [step]: model,
    }));
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">LLM Configuration</h2>
        <p className="text-gray-600 mt-1">
          Configure which LLM models are used for each step of the workflow
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600">Loading configuration...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 mb-6">
          Error loading configuration: {(error as Error).message}
        </div>
      )}

      {config && (
        <div className="space-y-6">
          {/* Model Assignments */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-6">
              <Settings className="w-6 h-6 text-primary" />
              <h3 className="text-lg font-semibold text-gray-900">Workflow Model Assignments</h3>
            </div>

            <div className="space-y-4">
              {workflowSteps.map((step) => (
                <div key={step.key} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-900">{step.label}</h4>
                      <p className="text-sm text-gray-600 mt-1">{step.description}</p>
                    </div>
                    <div className="w-64">
                      <select
                        value={modelAssignments[step.key] || config.available_models?.[0] || ''}
                        onChange={(e) => handleModelChange(step.key, e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                      >
                        {config.available_models?.map((model: string) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={handleSaveConfig}
                disabled={updateConfigMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {updateConfigMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>

            {updateConfigMutation.isSuccess && (
              <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-3 text-green-800 text-sm">
                Configuration saved successfully!
              </div>
            )}

            {updateConfigMutation.isError && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm">
                Error saving configuration: {(updateConfigMutation.error as Error)?.message}
              </div>
            )}
          </div>

          {/* Available Models */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Plus className="w-6 h-6 text-primary" />
              <h3 className="text-lg font-semibold text-gray-900">Available Models</h3>
            </div>

            <p className="text-sm text-gray-600 mb-4">
              Add or remove LLM models available for workflow steps. Models must be installed in Ollama.
            </p>

            {/* Add Model Form */}
            <form onSubmit={handleAddModel} className="flex gap-3 mb-6">
              <input
                type="text"
                value={newModelName}
                onChange={(e) => setNewModelName(e.target.value)}
                placeholder="e.g., llama3.1, mistral, gemma2"
                disabled={isPulling}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!newModelName.trim() || isPulling}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                {isPulling ? 'Downloading...' : 'Add Model'}
              </button>
            </form>

            {isPulling && pullProgress && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-800 text-sm mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  <span className="font-medium">Downloading model...</span>
                </div>
                <div className="text-xs">{pullProgress}</div>
              </div>
            )}

            {/* Model List */}
            <div className="space-y-2">
              {config.available_models?.map((model: string) => (
                <div key={model} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
                  <span className="font-medium text-gray-900">{model}</span>
                  <button
                    onClick={() => deleteModelMutation.mutate(model)}
                    disabled={deleteModelMutation.isPending || config.available_models.length === 1}
                    className="flex items-center gap-2 px-3 py-1 text-red-600 hover:bg-red-50 rounded text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title={config.available_models.length === 1 ? 'Cannot delete the last model' : 'Delete model'}
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
