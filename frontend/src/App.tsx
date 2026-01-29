import React, { useState, useEffect, useRef } from 'react';
import { Play, Terminal, Database, FileCode, Loader2, Search, Download, Table, ChevronRight, FolderOpen, RefreshCw } from 'lucide-react';

interface LogEntry {
  text: string;
  type: 'info' | 'step' | 'success' | 'error';
}

function App() {
  const [url, setUrl] = useState('https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName');
  const [query, setQuery] = useState('Lauren Homes');
  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [startDate, setStartDate] = useState('01/01/1980');
  const [endDate, setEndDate] = useState(new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' }));
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [metrics, setMetrics] = useState({ scriptPath: '', extractedCount: 0 });
  const [extractedData, setExtractedData] = useState<any[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);

  // Script Library state
  const [availableScripts, setAvailableScripts] = useState<{ name: string, path: string, modified: string }[]>([]);
  const [selectedScriptPath, setSelectedScriptPath] = useState('');
  const [isLoadingScripts, setIsLoadingScripts] = useState(false);

  // Parallel execution state
  const [selectedScripts, setSelectedScripts] = useState<Set<string>>(new Set());
  const [isParallelRunning, setIsParallelRunning] = useState(false);
  const [runningScripts, setRunningScripts] = useState<Set<string>>(new Set()); // Track currently running scripts
  const [completedScripts, setCompletedScripts] = useState<Map<string, 'success' | 'error'>>(new Map()); // Track completion status
  const [parallelProgress, setParallelProgress] = useState<{
    total: number;
    completed: number;
    successful: number;
    failed: number;
    totalRows: number;
    results: Array<{ script: string; success: boolean; row_count: number; error?: string }>;
  }>({ total: 0, completed: 0, successful: 0, failed: 0, totalRows: 0, results: [] });

  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const addLog = (text: string, type: LogEntry['type'] = 'info') => {
    setLogs(prev => [...prev, { text, type }]);
  };

  const loadScripts = async () => {
    setIsLoadingScripts(true);
    try {
      const response = await fetch('http://localhost:8006/api/scripts');
      const data = await response.json();
      const scripts = data.scripts || [];
      setAvailableScripts(scripts);
      if (scripts.length > 0 && !selectedScriptPath) {
        setSelectedScriptPath(scripts[0].path);
      }
    } catch (err) {
      console.error('Failed to load scripts:', err);
      setAvailableScripts([]);
    } finally {
      setIsLoadingScripts(false);
    }
  };

  // Auto-load scripts on mount
  useEffect(() => {
    loadScripts();
  }, []);

  const startScraping = async () => {
    setLogs([]);
    setExtractedData([]);
    setMetrics({ scriptPath: '', extractedCount: 0 });
    setStatus('running');
    addLog(`🚀 Starting agent for ${url}`, 'info');

    try {
      const response = await fetch('http://localhost:8006/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          search_query: query,
          start_date: startDate,
          end_date: endDate
        }),
      });

      const { run_id } = await response.json();
      const ws = new WebSocket(`ws://localhost:8006/ws/agent/${run_id}`);
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
          setMetrics(prev => ({ ...prev, scriptPath: message.data.script_path }));
        }

        if (message.data?.extracted_count) {
          setMetrics(prev => ({ ...prev, extractedCount: message.data.extracted_count }));
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

  const runGeneratedScript = async () => {
    const scriptToRun = selectedScriptPath || metrics.scriptPath;
    if (!scriptToRun) return;

    setIsExecuting(true);
    addLog(`🔄 Executing script: ${scriptToRun.split(/[\\/]/).pop()}`, 'info');
    addLog(`📝 Parameters: query="${query}", range=${startDate} - ${endDate}`, 'info');

    try {
      const response = await fetch('http://localhost:8006/api/execute-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_path: scriptToRun,
          search_query: query,
          start_date: startDate,
          end_date: endDate
        }),
      });

      const result = await response.json();

      if (result.success) {
        setExtractedData(result.data);
        addLog(`✅ Script executed successfully! Extracted ${result.row_count} rows.`, 'success');
        // Add step logs from stdout if available
        if (result.stdout) {
          const stepLogs = result.stdout.split('\n').filter((l: string) => l.includes('[STEP'));
          stepLogs.forEach((l: string) => addLog(l, 'step'));
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

  // Toggle single script selection
  const toggleScriptSelection = (path: string) => {
    setSelectedScripts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  // Select/deselect all scripts
  const selectAllScripts = (selectAll: boolean) => {
    if (selectAll) {
      setSelectedScripts(new Set(availableScripts.map(s => s.path)));
    } else {
      setSelectedScripts(new Set());
    }
  };

  // Run selected scripts in parallel
  const runSelectedScriptsParallel = async () => {
    if (selectedScripts.size === 0) return;

    setIsParallelRunning(true);
    setRunningScripts(new Set()); // Reset running scripts
    setCompletedScripts(new Map()); // Reset completed scripts
    setParallelProgress({ total: selectedScripts.size, completed: 0, successful: 0, failed: 0, totalRows: 0, results: [] });
    addLog(`🚀 Starting parallel execution of ${selectedScripts.size} scripts...`, 'info');
    addLog(`📝 Parameters: query="${query}", range=${startDate} - ${endDate}`, 'info');

    try {
      // Start parallel execution
      const response = await fetch('http://localhost:8006/api/execute-parallel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_paths: Array.from(selectedScripts),
          search_query: query,
          start_date: startDate,
          end_date: endDate,
          max_concurrent: 0  // 0 = no limit, run all selected scripts at once
        }),
      });

      const { run_id } = await response.json();

      // Connect WebSocket for progress
      const ws = new WebSocket(`ws://localhost:8006/ws/parallel/${run_id}`);

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'parallel_start') {
          addLog(`⚡ Running up to ${message.max_concurrent} scripts concurrently`, 'info');
        }

        if (message.type === 'script_start') {
          addLog(`▶️ Starting: ${message.script}`, 'step');
          // Add to running scripts for animation
          setRunningScripts(prev => new Set([...prev, message.path]));
        }

        if (message.type === 'script_complete') {
          if (message.success) {
            addLog(`✅ ${message.script}: ${message.row_count} rows extracted`, 'success');
          } else {
            addLog(`❌ ${message.script}: ${message.error || 'Failed'}`, 'error');
          }
          // Remove from running, add to completed
          setRunningScripts(prev => {
            const newSet = new Set(prev);
            newSet.delete(message.path);
            return newSet;
          });
          setCompletedScripts(prev => new Map(prev).set(message.path, message.success ? 'success' : 'error'));

          setParallelProgress(prev => ({
            ...prev,
            completed: prev.completed + 1,
            successful: prev.successful + (message.success ? 1 : 0),
            failed: prev.failed + (message.success ? 0 : 1),
            totalRows: prev.totalRows + (message.row_count || 0),
            results: [...prev.results, message]
          }));
        }

        if (message.type === 'parallel_complete') {
          addLog(`✨ Parallel execution complete: ${message.successful}/${message.total_scripts} succeeded, ${message.total_rows} total rows`, 'success');
          setRunningScripts(new Set()); // Clear running scripts
          setParallelProgress(prev => ({
            ...prev,
            completed: message.total_scripts,
            successful: message.successful,
            failed: message.failed,
            totalRows: message.total_rows,
            results: message.results
          }));
          setIsParallelRunning(false);
        }

        if (message.type === 'error') {
          addLog(`❌ Error: ${message.error}`, 'error');
          setRunningScripts(new Set());
          setIsParallelRunning(false);
        }
      };

      ws.onerror = () => {
        addLog('❌ WebSocket connection error', 'error');
        setRunningScripts(new Set());
        setIsParallelRunning(false);
      };

      ws.onclose = () => {
        setIsParallelRunning(false);
      };

    } catch (err) {
      addLog(`❌ Failed to start parallel execution: ${err}`, 'error');
      setRunningScripts(new Set());
      setIsParallelRunning(false);
    }
  };

  const downloadData = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(extractedData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "extracted_data.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

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
          {(status === 'running' || isExecuting) && <Loader2 size={14} className="animate-spin" style={{ marginRight: '6px' }} />}
          {isExecuting ? 'executing script' : status}
        </div>
      </header>

      <div className="grid-layout">
        <div className="card">
          <h2 className="flex items-center gap-2 mb-4">
            <Search size={20} color="#58a6ff" /> Search Parameters
          </h2>

          <div className="input-group">
            <label>Target URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
            />
          </div>

          <div className="input-group">
            <label>Party Name / Search Term</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. John Doe"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label>Start Date (MM/DD/YYYY)</label>
              <input
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="01/01/1980"
              />
            </div>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label>End Date (MM/DD/YYYY)</label>
              <input
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="MM/DD/YYYY"
              />
            </div>
          </div>

          <button
            onClick={startScraping}
            disabled={status === 'running' || isExecuting}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
          >
            {status === 'running' ? 'Agent Working...' : <><Play size={18} /> Start Extraction</>}
          </button>

          {/* Script Library Section */}
          <div className="mt-4" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <FolderOpen size={16} color="#58a6ff" />
                <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>Script Library</span>
                {selectedScripts.size > 0 && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-color)', background: 'rgba(88, 166, 255, 0.15)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                    {selectedScripts.size} selected
                  </span>
                )}
              </div>
              <button
                className="btn-secondary"
                onClick={loadScripts}
                disabled={isLoadingScripts}
                style={{ padding: '0.4rem 0.8rem', borderRadius: '4px' }}
              >
                {isLoadingScripts ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh
              </button>
            </div>

            {availableScripts.length > 0 ? (
              <>
                {/* Select All / None buttons */}
                <div className="flex gap-2 mb-3">
                  <button
                    className="btn-secondary"
                    onClick={() => selectAllScripts(true)}
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderRadius: '4px' }}
                  >
                    Select All
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => selectAllScripts(false)}
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderRadius: '4px' }}
                  >
                    Select None
                  </button>
                </div>

                {/* Script checkboxes */}
                <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '0.75rem', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.5rem' }}>
                  {availableScripts.map((script, index) => {
                    const isRunning = runningScripts.has(script.path);
                    const completionStatus = completedScripts.get(script.path);

                    return (
                      <label
                        key={script.path}
                        className={`flex items-center gap-2 script-item ${isRunning ? 'script-running' : ''} ${completionStatus === 'success' ? 'script-success' : ''} ${completionStatus === 'error' ? 'script-error' : ''}`}
                        style={{
                          padding: '0.5rem',
                          cursor: 'pointer',
                          borderRadius: '4px',
                          background: selectedScripts.has(script.path) ? 'rgba(88, 166, 255, 0.1)' : 'transparent',
                          marginBottom: '0.25rem',
                          border: isRunning ? '1px solid rgba(88, 166, 255, 0.5)' : '1px solid transparent',
                          animationDelay: `${index * 0.05}s`
                        }}
                      >
                        {isRunning && <span className="running-dot" />}
                        <input
                          type="checkbox"
                          checked={selectedScripts.has(script.path)}
                          onChange={() => toggleScriptSelection(script.path)}
                          style={{ accentColor: 'var(--accent-color)' }}
                          className="checkbox-animate"
                        />
                        <span style={{
                          fontSize: '0.85rem',
                          flex: 1,
                          color: completionStatus === 'success' ? 'var(--success-color)' :
                            completionStatus === 'error' ? 'var(--error-color)' : 'inherit'
                        }}>
                          {script.name}
                          {completionStatus === 'success' && ' ✓'}
                          {completionStatus === 'error' && ' ✗'}
                        </span>
                      </label>
                    );
                  })}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2">
                  {/* Run Single */}
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      if (selectedScripts.size === 1) {
                        setSelectedScriptPath(Array.from(selectedScripts)[0]);
                        runGeneratedScript();
                      }
                    }}
                    disabled={selectedScripts.size !== 1 || isExecuting || isParallelRunning}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                  >
                    <Play size={14} /> Run Single
                  </button>

                  {/* Run Parallel */}
                  <button
                    onClick={runSelectedScriptsParallel}
                    disabled={selectedScripts.size < 1 || isExecuting || isParallelRunning || status === 'running'}
                    className={isParallelRunning ? 'btn-running' : ''}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: selectedScripts.size > 0 && !isParallelRunning ? 'var(--accent-color)' : undefined }}
                  >
                    {isParallelRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Run {selectedScripts.size > 1 ? `${selectedScripts.size} Parallel` : 'Selected'}
                  </button>
                </div>

                {/* Parallel Progress */}
                {(isParallelRunning || parallelProgress.completed > 0) && parallelProgress.total > 0 && (
                  <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                    <div className="flex justify-between items-center mb-2">
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {isParallelRunning && <span className="running-dot" />}
                        Parallel Progress
                      </span>
                      <span className="count-animate" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {parallelProgress.completed}/{parallelProgress.total}
                      </span>
                    </div>
                    <div style={{ height: '8px', background: 'var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div
                        className={isParallelRunning ? 'progress-bar-active' : ''}
                        style={{
                          height: '100%',
                          width: `${(parallelProgress.completed / parallelProgress.total) * 100}%`,
                          background: parallelProgress.failed > 0
                            ? 'linear-gradient(90deg, var(--success-color), var(--error-color))'
                            : 'linear-gradient(90deg, var(--success-color), #58d68d)',
                          transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                    <div className="flex justify-between mt-2" style={{ fontSize: '0.75rem' }}>
                      <span className="count-animate" style={{ color: 'var(--success-color)' }}>✓ {parallelProgress.successful} success</span>
                      <span className="count-animate" style={{ color: 'var(--error-color)' }}>✗ {parallelProgress.failed} failed</span>
                      <span className="count-animate" style={{ color: 'var(--accent-color)' }}>{parallelProgress.totalRows} rows</span>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '1rem' }}>
                No scripts available. Run the agent first to generate a script.
              </div>
            )}
          </div>

          {metrics.scriptPath && (
            <div className="mt-4" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                  <FileCode size={16} color="#58a6ff" />
                  <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>Generated Script</span>
                </div>
                <button
                  className="btn-secondary"
                  onClick={runGeneratedScript}
                  disabled={isExecuting || status === 'running'}
                  style={{ padding: '0.4rem 0.8rem', borderRadius: '4px' }}
                >
                  {isExecuting ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run Now
                </button>
              </div>
              <code style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', wordBreak: 'break-all', display: 'block', marginBottom: '0.5rem' }}>
                {metrics.scriptPath}
              </code>
            </div>
          )}

          {metrics.extractedCount > 0 && (
            <div className="mt-4" style={{ padding: '1rem', background: 'rgba(63, 185, 80, 0.1)', borderLeft: '3px solid var(--success-color)', borderRadius: '4px' }}>
              <div className="flex items-center gap-2">
                <Database size={16} color="var(--success-color)" />
                <span style={{ color: 'var(--success-color)', fontWeight: 600 }}>
                  Agent verified extraction: {metrics.extractedCount} rows
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="flex items-center gap-2 mb-4">
            <Terminal size={20} color="#8b949e" /> Agent Execution Logs
          </h2>
          <div className="logs-container">
            {logs.length === 0 && (
              <div style={{ color: '#333', textAlign: 'center', marginTop: 'auto', marginBottom: 'auto' }}>
                Ready to start...
              </div>
            )}
            {logs.map((log, i) => (
              <div key={i} className={`log-line ${log.type}`}>
                {log.text}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>

      {extractedData.length > 0 && (
        <div className="card mt-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="flex items-center gap-2">
              <Table size={20} color="#58a6ff" /> Data Preview
            </h2>
            <button className="btn-secondary flex items-center gap-2" onClick={downloadData}>
              <Download size={16} /> Export JSON
            </button>
          </div>
          <div className="results-table-container">
            <table className="results-table">
              <thead>
                <tr>
                  {Object.keys(extractedData[0]).map(key => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {extractedData.map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((val: any, j) => (
                      <td key={j} title={String(val)}>{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
