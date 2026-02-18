/**
 * LogViewer.tsx — Real-time agent execution log panel.
 */

import React, { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";

export interface LogEntry {
  text: string;
  type: "info" | "step" | "success" | "error";
}

interface LogViewerProps {
  logs: LogEntry[];
}

const LogViewer: React.FC<LogViewerProps> = ({ logs }) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column" }}>
      <h2 className="flex items-center gap-2 mb-4">
        <Terminal size={20} color="#8b949e" /> Agent Execution Logs
      </h2>
      <div className="logs-container">
        {logs.length === 0 && (
          <div style={{ color: "#333", textAlign: "center", marginTop: "auto", marginBottom: "auto" }}>
            Ready to start...
          </div>
        )}
        {logs.map((entry, i) => (
          <div key={i} className={`log-line ${entry.type}`}>
            {entry.text}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
};

export default LogViewer;
