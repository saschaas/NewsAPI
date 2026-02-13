import { Menu, Pause, Play } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { systemApi, schedulerApi } from '@/api/client';

export function Header() {
  const { toggleSidebar, wsConnected, globalPause, setGlobalPause } = useAppStore();
  const queryClient = useQueryClient();

  // Fetch system status
  const { data: status } = useQuery({
    queryKey: ['system-status'],
    queryFn: systemApi.status,
    refetchInterval: 10000, // 10 seconds
  });

  // Toggle global pause mutation
  const pauseMutation = useMutation({
    mutationFn: (paused: boolean) => schedulerApi.pause(paused),
    onSuccess: (_, paused) => {
      setGlobalPause(paused);
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] });
    },
  });

  const handleTogglePause = () => {
    pauseMutation.mutate(!globalPause);
  };

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900">
            Stock News API
          </h1>
        </div>

        <div className="flex items-center gap-6">
          {/* System Stats */}
          {status && (
            <div className="hidden md:flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-600">Sources:</span>
                <span className="font-medium text-green-600">
                  {status.active_sources}
                </span>
                /
                <span className="font-medium text-gray-400">
                  {status.paused_sources}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-600">Articles:</span>
                <span className="font-medium">{status.total_articles}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-600">Ollama:</span>
                <span
                  className={`w-2 h-2 rounded-full ${
                    status.ollama_status === 'healthy'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                  }`}
                />
              </div>
            </div>
          )}

          {/* WebSocket Status */}
          <div className="flex items-center gap-2 text-sm">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-green-500' : 'bg-gray-300'
              }`}
            />
            <span className="hidden sm:inline text-gray-600">
              {wsConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Global Pause Toggle */}
          <button
            onClick={handleTogglePause}
            disabled={pauseMutation.isPending}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              globalPause
                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                : 'bg-orange-100 text-orange-700 hover:bg-orange-200'
            }`}
          >
            {globalPause ? (
              <>
                <Play className="w-4 h-4" />
                <span className="hidden sm:inline">Resume</span>
              </>
            ) : (
              <>
                <Pause className="w-4 h-4" />
                <span className="hidden sm:inline">Pause</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
