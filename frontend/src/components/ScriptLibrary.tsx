/**
 * ScriptLibrary.tsx — Script selector + Run button.
 */

import React from "react";
import { FolderOpen, Loader2, Play, RefreshCw } from "lucide-react";
import type { Script } from "../api/client";

interface ScriptLibraryProps {
  scripts: Script[];
  selectedPath: string;
  isLoading: boolean;
  isExecuting: boolean;
  isAgentRunning: boolean;
  onRefresh: () => void;
  onSelectScript: (path: string) => void;
  onRun: () => void;
}

const ScriptLibrary: React.FC<ScriptLibraryProps> = ({
  scripts,
  selectedPath,
  isLoading,
  isExecuting,
  isAgentRunning,
  onRefresh,
  onSelectScript,
  onRun,
}) => (
  <div
    className="mt-4"
    style={{
      padding: "1rem",
      background: "rgba(0,0,0,0.2)",
      borderRadius: "8px",
      border: "1px solid var(--border-color)",
    }}
  >
    <div className="flex justify-between items-center mb-4">
      <div className="flex items-center gap-2">
        <FolderOpen size={16} color="#58a6ff" />
        <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Script Library</span>
      </div>
      <button
        className="btn-secondary"
        onClick={onRefresh}
        disabled={isLoading}
        style={{ padding: "0.4rem 0.8rem", borderRadius: "4px" }}
      >
        {isLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh
      </button>
    </div>

    {scripts.length > 0 ? (
      <>
        <div className="input-group" style={{ marginBottom: "0.75rem" }}>
          <label>Select Script</label>
          <select value={selectedPath} onChange={(e) => onSelectScript(e.target.value)}>
            {scripts.map((s) => (
              <option key={s.path} value={s.path}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn-secondary"
          onClick={onRun}
          disabled={isExecuting || isAgentRunning || !selectedPath}
          style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}
        >
          {isExecuting ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run Selected Script
        </button>
      </>
    ) : (
      <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "1rem" }}>
        No scripts available. Run the agent first to generate a script.
      </div>
    )}
  </div>
);

export default ScriptLibrary;
