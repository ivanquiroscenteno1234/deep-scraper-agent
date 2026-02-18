/**
 * SearchForm.tsx — URL, query, and date inputs + "Start Extraction" button.
 */

import React from "react";
import { Play, Search, Loader2 } from "lucide-react";

interface SearchFormProps {
  url: string;
  query: string;
  startDate: string;
  endDate: string;
  isRunning: boolean;
  onUrlChange: (v: string) => void;
  onQueryChange: (v: string) => void;
  onStartDateChange: (v: string) => void;
  onEndDateChange: (v: string) => void;
  onSubmit: () => void;
}

const SearchForm: React.FC<SearchFormProps> = ({
  url,
  query,
  startDate,
  endDate,
  isRunning,
  onUrlChange,
  onQueryChange,
  onStartDateChange,
  onEndDateChange,
  onSubmit,
}) => (
  <>
    <h2 className="flex items-center gap-2 mb-4">
      <Search size={20} color="#58a6ff" /> Search Parameters
    </h2>

    <div className="input-group">
      <label>Target URL</label>
      <input value={url} onChange={(e) => onUrlChange(e.target.value)} placeholder="https://..." />
    </div>

    <div className="input-group">
      <label>Party Name / Search Term</label>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="e.g. John Doe"
      />
    </div>

    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "1rem",
        marginBottom: "1.5rem",
      }}
    >
      <div className="input-group" style={{ marginBottom: 0 }}>
        <label>Start Date (MM/DD/YYYY)</label>
        <input
          value={startDate}
          onChange={(e) => onStartDateChange(e.target.value)}
          placeholder="01/01/1980"
        />
      </div>
      <div className="input-group" style={{ marginBottom: 0 }}>
        <label>End Date (MM/DD/YYYY)</label>
        <input
          value={endDate}
          onChange={(e) => onEndDateChange(e.target.value)}
          placeholder="MM/DD/YYYY"
        />
      </div>
    </div>

    <button
      onClick={onSubmit}
      disabled={isRunning}
      style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}
    >
      {isRunning ? (
        <>
          <Loader2 size={18} className="animate-spin" /> Agent Working...
        </>
      ) : (
        <>
          <Play size={18} /> Start Extraction
        </>
      )}
    </button>
  </>
);

export default SearchForm;
