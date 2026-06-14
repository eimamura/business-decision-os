"use client";

import Link from "next/link";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useScenarios } from "@/features/scenarios/hooks";
import type { Candidate } from "@/features/scenarios/api";

interface ScenarioPageProps {
  params: { sessionId: string };
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export default function ScenarioPage({ params }: ScenarioPageProps): React.ReactElement {
  const { sessionId } = params;
  const { data: candidates = [], isLoading: loading } = useScenarios(sessionId);

  const radarData = buildRadarData(candidates);
  const kpis = radarData.length > 0 ? Object.keys(radarData[0]).filter((k) => k !== "kpi") : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <Link href={`/chat/${sessionId}`} className="text-sm text-blue-600 hover:underline">
          ← Back to Chat
        </Link>
        <h1 className="text-lg font-semibold text-gray-900">Scenario Comparison</h1>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {loading ? (
          <div className="h-96 bg-gray-200 rounded-xl animate-pulse" />
        ) : candidates.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p>No scenarios available yet.</p>
            <p className="text-sm mt-1">Run a decision session to generate candidates.</p>
          </div>
        ) : (
          <div className="space-y-8">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-base font-semibold text-gray-800 mb-4">KPI Radar</h2>
              <ResponsiveContainer width="100%" height={400}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="kpi" tick={{ fontSize: 12 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 1]} tick={{ fontSize: 10 }} />
                  {candidates.map((c: Candidate, i) => (
                    <Radar
                      key={c.id}
                      name={c.label ?? `Candidate ${i + 1}`}
                      dataKey={c.id}
                      stroke={COLORS[i % COLORS.length]}
                      fill={COLORS[i % COLORS.length]}
                      fillOpacity={c.is_primary ? 0.25 : 0.1}
                      strokeWidth={c.is_primary ? 2.5 : 1.5}
                    />
                  ))}
                  <Legend />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-base font-semibold text-gray-800">KPI Scores</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="text-left px-6 py-3 font-medium text-gray-600">Candidate</th>
                      {kpis.map((kpi) => (
                        <th key={kpi} className="text-right px-4 py-3 font-medium text-gray-600 capitalize">
                          {kpi.replace(/_/g, " ")}
                        </th>
                      ))}
                      <th className="text-center px-4 py-3 font-medium text-gray-600">Primary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {candidates.map((c: Candidate, i) => (
                      <tr key={c.id} className={c.is_primary ? "bg-blue-50" : ""}>
                        <td className="px-6 py-3 font-medium text-gray-900">
                          <span
                            className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                            style={{ backgroundColor: COLORS[i % COLORS.length] }}
                          />
                          {c.label ?? `Candidate ${i + 1}`}
                        </td>
                        {kpis.map((kpi) => {
                          const score = radarData.find((r) => r.kpi === kpi)?.[c.id] ?? 0;
                          return (
                            <td key={kpi} className="text-right px-4 py-3 text-gray-700 font-mono text-xs">
                              {(score as number).toFixed(3)}
                            </td>
                          );
                        })}
                        <td className="text-center px-4 py-3">
                          {c.is_primary && (
                            <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-medium">
                              Primary
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function buildRadarData(candidates: Candidate[]): Record<string, string | number>[] {
  if (candidates.length === 0) return [];

  const allKpis = Array.from(
    new Set(candidates.flatMap((c) => c.kpi_scores.map((s) => s.kpi)))
  );

  return allKpis.map((kpi) => {
    const row: Record<string, string | number> = { kpi };
    for (const c of candidates) {
      const score = c.kpi_scores.find((s) => s.kpi === kpi)?.score ?? 0;
      row[c.id] = score;
    }
    return row;
  });
}
