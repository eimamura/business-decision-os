"use client";
// InlineChart renders a recharts chart from a ChartSpec object embedded in a chat message.

import React from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface SeriesSpec {
  dataKey: string;
  name: string;
  color: string;
}

interface ChartSpec {
  type: "bar" | "line";
  title: string;
  xKey: string;
  series: readonly SeriesSpec[];
  data: readonly Record<string, unknown>[];
}

interface InlineChartProps {
  spec: ChartSpec;
}

export function parseChartSpec(raw: string): ChartSpec | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "type" in parsed &&
      "data" in parsed &&
      "xKey" in parsed &&
      "series" in parsed &&
      ((parsed as Record<string, unknown>)["type"] === "bar" ||
        (parsed as Record<string, unknown>)["type"] === "line")
    ) {
      return parsed as ChartSpec;
    }
    return null;
  } catch {
    return null;
  }
}

export default function InlineChart({ spec }: InlineChartProps): React.JSX.Element {
  const commonProps = {
    data: spec.data as Record<string, unknown>[],
  };

  const cartesianGrid = (
    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff18" />
  );

  const xAxis = (
    <XAxis dataKey={spec.xKey} tick={{ fontSize: 10, fill: "#ffffff66" }} />
  );

  const yAxis = <YAxis tick={{ fontSize: 10, fill: "#ffffff66" }} />;

  const tooltip = (
    <Tooltip
      contentStyle={{
        background: "#1a1a2a",
        border: "1px solid #ffffff22",
        borderRadius: 6,
        fontSize: 11,
      }}
    />
  );

  return (
    <div className="mt-3 mb-1" data-testid="inline-chart">
      <p className="text-xs text-white/50 mb-1">{spec.title}</p>
      <ResponsiveContainer width="100%" height={220}>
        {spec.type === "bar" ? (
          <BarChart {...commonProps}>
            {cartesianGrid}
            {xAxis}
            {yAxis}
            {tooltip}
            {spec.series.map((s) => (
              <Bar key={s.dataKey} dataKey={s.dataKey} name={s.name} fill={s.color} />
            ))}
          </BarChart>
        ) : (
          <LineChart {...commonProps}>
            {cartesianGrid}
            {xAxis}
            {yAxis}
            {tooltip}
            {spec.series.map((s) => (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name}
                stroke={s.color}
                dot={false}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
