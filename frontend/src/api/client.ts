/**
 * api/client.ts — All HTTP and WebSocket API calls.
 *
 * Extracted from App.tsx so components contain zero fetch() calls.
 */

const BASE = "http://localhost:8006";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Script {
  name: string;
  path: string;
  modified: string;
}

export interface ScrapeParams {
  url: string;
  search_query: string;
  start_date: string;
  end_date: string;
}

export interface ExecuteParams {
  script_path: string;
  search_query: string;
  start_date: string;
  end_date: string;
}

export interface ExecuteResult {
  success: boolean;
  row_count?: number;
  data?: Record<string, string>[];
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// REST helpers
// ---------------------------------------------------------------------------

/** Return the list of available generated scripts, sorted newest-first. */
export async function fetchScripts(): Promise<Script[]> {
  const res = await fetch(`${BASE}/api/scripts`);
  const data = await res.json();
  return data.scripts ?? [];
}

/** Start a scraping run and return the new run_id. */
export async function startRun(params: ScrapeParams): Promise<string> {
  const res = await fetch(`${BASE}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  const data = await res.json();
  return data.run_id as string;
}

/** Execute a previously generated script and return structured results. */
export async function executeScript(params: ExecuteParams): Promise<ExecuteResult> {
  const res = await fetch(`${BASE}/api/execute-script`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
}

/** Open the agent WebSocket for a given run_id. */
export function openAgentSocket(runId: string): WebSocket {
  return new WebSocket(`ws://localhost:8006/ws/agent/${runId}`);
}
