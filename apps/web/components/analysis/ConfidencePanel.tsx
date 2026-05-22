"use client";

interface ConfidencePanelProps {
  score: number;
  label: string;
}

export default function ConfidencePanel({ score, label }: ConfidencePanelProps): React.ReactElement {
  return (
    <div>
      <p className="text-sm text-white/70 tabular-nums mb-2">
        {score}% · {label}
      </p>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}
