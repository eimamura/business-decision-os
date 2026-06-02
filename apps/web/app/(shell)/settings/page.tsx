"use client";

import { useEffect, useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface GroundTruthDataset {
  columns: string[];
  rows: string[][];
}

interface GroundTruthResponse {
  sku_parameters: GroundTruthDataset;
  location_parameters: GroundTruthDataset;
  supplier_parameters: GroundTruthDataset;
  customer_parameters: GroundTruthDataset;
}

interface SampleDataTable {
  table_name: string;
  row_count: number;
  top_rows: Record<string, unknown>[];
}

interface SampleDataResponse {
  tables: SampleDataTable[];
}

type StatusMsg = { type: "success" | "error"; message: string };

type TabKey = keyof GroundTruthResponse;

const TABS: { key: TabKey; label: string }[] = [
  { key: "sku_parameters", label: "SKU Parameters" },
  { key: "location_parameters", label: "Locations" },
  { key: "supplier_parameters", label: "Suppliers" },
  { key: "customer_parameters", label: "Customers" },
];

function formatCell(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function SettingsPage(): React.ReactElement {
  const [groundTruth, setGroundTruth] = useState<GroundTruthResponse | null>(null);
  const [gtLoading, setGtLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("sku_parameters");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<StatusMsg | null>(null);

  const [sampleSeed, setSampleSeed] = useState("42");
  const [sampleSkuCount, setSampleSkuCount] = useState("30");
  const [sampleHorizonDays, setSampleHorizonDays] = useState("365");
  const [sampleWarehouseCount, setSampleWarehouseCount] = useState("2");
  const [sampleMissingRate, setSampleMissingRate] = useState("0.02");
  const [sampleGenerating, setSampleGenerating] = useState(false);
  const [sampleStatus, setSampleStatus] = useState<StatusMsg | null>(null);
  const [sampleTables, setSampleTables] = useState<SampleDataTable[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/admin/ground-truth`, {
      headers: { "X-Dev-User": "dev-admin" },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<GroundTruthResponse>;
      })
      .then(setGroundTruth)
      .catch(() => setSaveStatus({ type: "error", message: "Failed to load ground truth parameters." }))
      .finally(() => setGtLoading(false));
  }, []);

  const updateCell = useCallback((tab: TabKey, rowIdx: number, colIdx: number, value: string) => {
    setGroundTruth((prev) => {
      if (!prev) return prev;
      const dataset = prev[tab];
      const newRows = dataset.rows.map((r, ri) =>
        ri === rowIdx ? r.map((c, ci) => (ci === colIdx ? value : c)) : r
      );
      return { ...prev, [tab]: { ...dataset, rows: newRows } };
    });
  }, []);

  async function handleSave(): Promise<void> {
    if (!groundTruth) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/ground-truth`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Dev-User": "dev-admin" },
        body: JSON.stringify(groundTruth),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const updated = await res.json() as GroundTruthResponse;
      setGroundTruth(updated);
      setSaveStatus({ type: "success", message: "Ground truth parameters saved." });
    } catch (err: unknown) {
      setSaveStatus({ type: "error", message: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerate(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSampleGenerating(true);
    setSampleStatus(null);
    setSampleTables([]);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/sample-data/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-User": "dev-admin" },
        body: JSON.stringify({
          seed: Number(sampleSeed),
          sku_count: Number(sampleSkuCount),
          horizon_days: Number(sampleHorizonDays),
          warehouse_count: Number(sampleWarehouseCount),
          missing_rate: Number(sampleMissingRate),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: string | { msg?: string }[] }).detail;
        if (Array.isArray(detail) && detail.length > 0) {
          throw new Error(detail.map((item) => item.msg ?? "Invalid input").join("; "));
        }
        throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
      }
      const data = await res.json() as SampleDataResponse;
      setSampleTables(data.tables);
      setSampleStatus({ type: "success", message: "Sample data generated and loaded into database." });
    } catch (err: unknown) {
      setSampleStatus({ type: "error", message: err instanceof Error ? err.message : "Generation failed." });
    } finally {
      setSampleGenerating(false);
    }
  }

  const currentDataset = groundTruth?.[activeTab];

  return (
    <div className="min-h-screen bg-[#070B14] text-white">
      {/* Header */}
      <header className="border-b border-white/5 px-6 py-3 flex items-center gap-4">
        <h1 className="text-sm font-semibold text-white/80 tracking-tight">Data Generation Studio</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* Ground Truth Parameters */}
        <section className="bg-[#0F1629] border border-white/8 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">Ground Truth Parameters</h2>
              <p className="text-[11px] text-white/35 mt-0.5">
                Edit parameters → Save → Generate to reflect changes in sample data
              </p>
            </div>
            <div className="flex items-center gap-3">
              {saveStatus && (
                <span className={`text-xs ${saveStatus.type === "success" ? "text-emerald-400" : "text-red-400"}`}>
                  {saveStatus.message}
                </span>
              )}
              <button
                onClick={handleSave}
                disabled={saving || gtLoading || !groundTruth}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors"
              >
                {saving ? "Saving…" : "Save Ground Truth"}
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/5">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-5 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === key
                    ? "border-indigo-400 text-white bg-indigo-500/10"
                    : "border-transparent text-white/40 hover:text-white/70 hover:bg-white/3"
                }`}
              >
                {label}
                {groundTruth && (
                  <span className="ml-1.5 text-[10px] text-white/25">
                    {groundTruth[key].rows.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Editable Table */}
          <div className="overflow-x-auto">
            {gtLoading ? (
              <div className="px-5 py-8 space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-8 bg-white/5 rounded animate-pulse" />
                ))}
              </div>
            ) : !currentDataset ? (
              <p className="px-5 py-6 text-xs text-white/30">No data</p>
            ) : (
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b border-white/5">
                    {currentDataset.columns.map((col) => (
                      <th
                        key={col}
                        className="px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-white/30 whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {currentDataset.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="border-b border-white/3 hover:bg-white/2">
                      {row.map((cell, colIdx) => (
                        <td key={colIdx} className="px-2 py-1.5">
                          <input
                            type="text"
                            value={cell}
                            onChange={(e) => updateCell(activeTab, rowIdx, colIdx, e.target.value)}
                            className="w-full min-w-[80px] bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white placeholder-white/20 focus:border-indigo-500/50 focus:outline-none focus:bg-white/8 transition-colors"
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Generation Config */}
        <section className="bg-[#0F1629] border border-white/8 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Generation Config</h2>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {[
                { id: "seed", label: "Seed", value: sampleSeed, set: setSampleSeed, step: "1", min: undefined, max: undefined },
                { id: "sku-count", label: "SKU count", value: sampleSkuCount, set: setSampleSkuCount, step: "1", min: "1", max: "30" },
                { id: "horizon-days", label: "Horizon days", value: sampleHorizonDays, set: setSampleHorizonDays, step: "1", min: "1", max: "1095" },
                { id: "warehouse-count", label: "Warehouses", value: sampleWarehouseCount, set: setSampleWarehouseCount, step: "1", min: "1", max: "10" },
                { id: "missing-rate", label: "Missing rate", value: sampleMissingRate, set: setSampleMissingRate, step: "0.01", min: "0", max: "0.25" },
              ].map(({ id, label, value, set, step, min, max }) => (
                <div key={id}>
                  <label htmlFor={id} className="block text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-1.5">
                    {label}
                  </label>
                  <input
                    id={id}
                    type="number"
                    value={value}
                    onChange={(e) => set(e.target.value)}
                    step={step}
                    min={min}
                    max={max}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:border-indigo-500/50 focus:outline-none focus:bg-white/8 transition-colors"
                  />
                </div>
              ))}
            </div>

            {sampleStatus && (
              <div className={`text-xs px-3 py-2 rounded-lg ${
                sampleStatus.type === "success"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
              }`}>
                {sampleStatus.message}
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={sampleGenerating}
                className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white px-5 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2"
              >
                {sampleGenerating ? (
                  <>
                    <svg className="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    Generating…
                  </>
                ) : "Generate Sample Data"}
              </button>
            </div>
          </form>
        </section>

        {/* Preview Results */}
        {sampleTables.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-white/60 mb-3 px-1">
              Generated Tables
              <span className="ml-2 text-[10px] font-normal text-white/25">{sampleTables.length} tables</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sampleTables.map((table) => {
                const columns = table.top_rows[0] ? Object.keys(table.top_rows[0]) : [];
                return (
                  <div key={table.table_name} className="bg-[#0F1629] border border-white/8 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-white">{table.table_name}</h3>
                      <span className="text-[10px] font-medium text-white/35">
                        {table.row_count.toLocaleString()} rows
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-[11px]">
                        <thead>
                          <tr className="border-b border-white/5">
                            {columns.map((col) => (
                              <th key={col} className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-widest text-white/25 whitespace-nowrap">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {table.top_rows.map((row, rowIndex) => (
                            <tr key={`${table.table_name}-${rowIndex}`} className="border-b border-white/3 last:border-b-0">
                              {columns.map((col) => (
                                <td key={col} className="px-3 py-2 text-white/60 whitespace-nowrap max-w-[200px] truncate">
                                  {formatCell(row[col])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
