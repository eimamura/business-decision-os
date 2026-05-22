"use client";

interface DataUsedPanelProps {
  dataUsed: string[];
}

function DatabaseIcon(): React.ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-indigo-400"
      aria-hidden="true"
    >
      <ellipse cx="7" cy="3" rx="5" ry="2" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M2 3v4c0 1.105 2.239 2 5 2s5-.895 5-2V3"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <path
        d="M2 7v3c0 1.105 2.239 2 5 2s5-.895 5-2V7"
        stroke="currentColor"
        strokeWidth="1.2"
      />
    </svg>
  );
}

export default function DataUsedPanel({ dataUsed }: DataUsedPanelProps): React.ReactElement {
  return (
    <div className="flex flex-wrap gap-2">
      {dataUsed.map((item, i) => (
        <span
          key={i}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/8 border border-white/12 text-xs text-white/55"
        >
          <DatabaseIcon />
          {item}
        </span>
      ))}
    </div>
  );
}
