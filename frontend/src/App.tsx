import React, { useState, useEffect, useRef } from 'react';
import { Loader2, FileCode, Database } from 'lucide-react';

import { fetchScripts, startRun, executeScript, openAgentSocket } from './api/client';
import type { Script } from './api/client';

import SearchForm from './components/SearchForm';
import ScriptLibrary from './components/ScriptLibrary';
import LogViewer from './components/LogViewer';
import DataTable from './components/DataTable';
import type { LogEntry } from './components/LogViewer';

type AppStatus = 'idle' | 'running' | 'success' | 'error';

function App() {
  // Search params
  const [url, setUrl] = useState('https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName');
  const [query, setQuery] = useState('Lauren Homes');
  const [startDate, setStartDate] = useState('01/01/1980');
  const [endDate, setEndDate] = useState(
    new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' })
  );

  // Agent run state
  const [status, setStatus] = useState<AppStatus>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [metrics, setMetrics] = useState({ scriptPath: '', extractedCount: 0 });

  // Script library state
  const [scripts, setScripts] = useState<Script[]>([]);
  const [selectedScriptPath, setSelectedScriptPath] = useState('');
  const [isLoadingScripts, setIsLoadingScripts] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Extracted data
  const [extractedData, setExtractedData] = useState<Record<string, string>[]>([]);

  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (text: string, type: LogEntry['type'] = 'info') =>
    setLogs((prev) => [...prev, { text, type }]);

  // ---------------------------------------------------------------------------
  // Script library
  // ---------------------------------------------------------------------------

  const loadScripts = async () => {
    setIsLoadingScripts(true);
    try {
      const loaded = await fetchScripts();
      setScripts(loaded);
      if (loaded.length > 0 && !selectedScriptPath) {
        setSelectedScriptPath(loaded[0].path);
      }
    } catch (err) {
      console.error('Failed to load scripts:', err);
    } finally {
      setIsLoadingScripts(false);
    }
  };

  useEffect(() => { loadScripts(); }, []);

  // ---------------------------------------------------------------------------
  // Agent run
  // ---------------------------------------------------------------------------

  const startScraping = async () => {
    setLogs([]);
    setExtractedData([]);
    setMetrics({ scriptPath: '', extractedCount: 0 });
    setStatus('running');
    addLog(`🚀 Starting agent for ${url}`, 'info');

    try {
      const runId = await startRun({ url, search_query: query, start_date: startDate, end_date: endDate });
      const ws = openAgentSocket(runId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.error) {
          addLog(`❌ Error: ${message.error}`, 'error');
          setStatus('error');
          return;
        }

        if (message.logs) {
          message.logs.forEach((log: string) => {
            let type: LogEntry['type'] = 'info';
            if (log.includes('[STEP')) type = 'step';
            if (log.includes('✅') || log.includes('SUCCESS')) type = 'success';
            if (log.includes('❌') || log.includes('FAILED')) type = 'error';
            addLog(log, type);
          });
        }

        if (message.data?.script_path) {
          setMetrics((prev) => ({ ...prev, scriptPath: message.data.script_path }));
        }
        if (message.data?.extracted_count) {
          setMetrics((prev) => ({ ...prev, extractedCount: message.data.extracted_count }));
        }

        if (message.status === 'completed' || message.status === 'SCRIPT_TESTED') {
          setStatus('success');
          addLog('✨ Workflow completed successfully!', 'success');
        }
        if (message.status === 'NEEDS_HUMAN_REVIEW' || message.status === 'error') {
          setStatus('error');
        }
      };
    } catch (err) {
      addLog(`❌ Failed to connect to server: ${err}`, 'error');
      setStatus('error');
    }
  };

  // ---------------------------------------------------------------------------
  // Execute script
  // ---------------------------------------------------------------------------

  const runGeneratedScript = async () => {
    const scriptToRun = selectedScriptPath || metrics.scriptPath;
    if (!scriptToRun) return;

    setIsExecuting(true);
    addLog(`🔄 Executing script: ${scriptToRun.split(/[\\/]/).pop()}`, 'info');
    addLog(`📝 Parameters: query="${query}", range=${startDate} - ${endDate}`, 'info');

    try {
      const result = await executeScript({
        script_path: scriptToRun,
        search_query: query,
        start_date: startDate,
        end_date: endDate,
      });

      if (result.success) {
        setExtractedData(result.data ?? []);
        addLog(`✅ Script executed successfully! Extracted ${result.row_count} rows.`, 'success');
        if (result.stdout) {
          result.stdout.split('\n').filter((l) => l.includes('[STEP')).forEach((l) => addLog(l, 'step'));
        }
      } else {
        addLog(`❌ Execution failed: ${result.error}`, 'error');
        if (result.stderr) addLog(result.stderr, 'error');
      }
    } catch (err) {
      addLog(`❌ Error running script: ${err}`, 'error');
    } finally {
      setIsExecuting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="app-container">
      <header>
        <div>
          <h1>Deep Scraper Agent</h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Next-gen official records extraction engine
          </p>
        </div>
        <div className={`badge badge-${status}`}>
          {(status === 'running' || isExecuting) && (
            <Loader2 size={14} className="animate-spin" style={{ marginRight: '6px' }} />
          )}
          {isExecuting ? 'executing script' : status}
        </div>
      </header>

      <div className="grid-layout">
        <div className="card">
          <SearchForm
            url={url}
            query={query}
            startDate={startDate}
            endDate={endDate}
            isRunning={status === 'running' || isExecuting}
            onUrlChange={setUrl}
            onQueryChange={setQuery}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            onSubmit={startScraping}
          />

          <ScriptLibrary
            scripts={scripts}
            selectedPath={selectedScriptPath}
            isLoading={isLoadingScripts}
            isExecuting={isExecuting}
            isAgentRunning={status === 'running'}
            onRefresh={loadScripts}
            onSelectScript={setSelectedScriptPath}
            onRun={runGeneratedScript}
          />

          {metrics.scriptPath && (
            <div
              className="mt-4"
              style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}
            >
              <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
                <FileCode size={16} color="#58a6ff" />
                <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>Generated Script</span>
              </div>
              <code style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', wordBreak: 'break-all', display: 'block' }}>
                {metrics.scriptPath}
              </code>
            </div>
          )}

          {metrics.extractedCount > 0 && (
            <div
              className="mt-4"
              style={{ padding: '1rem', background: 'rgba(63, 185, 80, 0.1)', borderLeft: '3px solid var(--success-color)', borderRadius: '4px' }}
            >
              <div className="flex items-center gap-2">
                <Database size={16} color="var(--success-color)" />
                <span style={{ color: 'var(--success-color)', fontWeight: 600 }}>
                  Agent verified extraction: {metrics.extractedCount} rows
                </span>
              </div>
            </div>
          )}
        </div>

        <LogViewer logs={logs} />
      </div>

      <DataTable data={extractedData} />
    </div>
  );
}

export default App;

