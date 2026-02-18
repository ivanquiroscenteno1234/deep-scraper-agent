/**
 * DataTable.tsx — Extracted results preview table + JSON download.
 */

import React from "react";
import { Table, Download } from "lucide-react";

interface DataTableProps {
  data: Record<string, string>[];
}

const DataTable: React.FC<DataTableProps> = ({ data }) => {
  if (data.length === 0) return null;

  const columns = Object.keys(data[0]);

  const downloadData = () => {
    const dataStr =
      "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
    const a = document.createElement("a");
    a.setAttribute("href", dataStr);
    a.setAttribute("download", "extracted_data.json");
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
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
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                {columns.map((col, j) => (
                  <td key={j} title={String(row[col])}>
                    {String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DataTable;
