export function Help() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Help & Documentation</h2>
      <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-6">
        <section>
          <h3 className="text-lg font-semibold mb-2">Getting Started</h3>
          <p className="text-gray-600 mb-4">
            Stock News API automatically fetches and analyzes news from your configured sources.
          </p>
          <ol className="list-decimal list-inside space-y-2 text-gray-700">
            <li>Add data sources (websites or YouTube channels)</li>
            <li>Configure fetch frequency</li>
            <li>Monitor the dashboard for new articles</li>
            <li>Analyze stock sentiment trends</li>
          </ol>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-2">API Integration</h3>
          <p className="text-gray-600 mb-2">
            Access the REST API at <code className="bg-gray-100 px-2 py-1 rounded">http://localhost:8000/api/v1</code>
          </p>
          <p className="text-gray-600">
            View full API documentation at <code className="bg-gray-100 px-2 py-1 rounded">/docs</code>
          </p>
        </section>
      </div>
    </div>
  );
}
