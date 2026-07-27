"use client";

import { Download } from "lucide-react";

function displayValue(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ResultTable({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  if (rows.length === 0) {
    return <div className="empty-result">조건과 일치하는 행이 없습니다.</div>;
  }

  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row))),
  );

  const download = () => {
    const quote = (value: unknown) =>
      `"${displayValue(value).replaceAll('"', '""')}"`;
    const csv = [
      columns.map(quote).join(","),
      ...rows.map((row) =>
        columns.map((column) => quote(row[column])).join(","),
      ),
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "factory-graph-result.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="result-table-wrap">
      <div className="result-table-toolbar">
        <span>{rows.length} rows</span>
        <button type="button" onClick={download} className="ghost-button">
          <Download size={14} /> CSV
        </button>
      </div>
      <div className="result-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td title={displayValue(row[column])} key={column}>
                    {displayValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
