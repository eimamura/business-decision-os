"use client";

import { TrendingUp, Package, BarChart3, Truck, CheckSquare } from "lucide-react";
import type { QuickAction } from "@/types/workspace";
import QuickActionCard from "./QuickActionCard";

interface ActionConfig {
  action: QuickAction;
  icon: React.ReactElement;
  iconBgClass: string;
}

const ACTION_CONFIGS: ActionConfig[] = [
  {
    action: {
      id: "forecast",
      title: "Analyze Forecast Risk",
      description: "Identify forecast risk by item, location, or time horizon.",
      prompt: "Analyze forecast risk for the next 4 weeks for DC West.",
    },
    icon: <TrendingUp size={18} />,
    iconBgClass: "bg-purple-500/15 text-purple-400",
  },
  {
    action: {
      id: "inventory",
      title: "Check Inventory Shortage",
      description: "Find at-risk SKUs and locations with potential stockouts.",
      prompt: "Show inventory shortage risk for the next 4 weeks.",
    },
    icon: <Package size={18} />,
    iconBgClass: "bg-cyan-500/15 text-cyan-400",
  },
  {
    action: {
      id: "kpi",
      title: "Explain KPI Anomaly",
      description: "Diagnose anomalies in KPIs and uncover root causes.",
      prompt: "Explain the latest KPI anomaly and its root cause.",
    },
    icon: <BarChart3 size={18} />,
    iconBgClass: "bg-amber-500/15 text-amber-400",
  },
  {
    action: {
      id: "otif",
      title: "Review OTIF Issues",
      description: "Analyze on-time, in-full performance and exceptions.",
      prompt: "Review OTIF issues for the last 30 days.",
    },
    icon: <Truck size={18} />,
    iconBgClass: "bg-blue-500/15 text-blue-400",
  },
  {
    action: {
      id: "action",
      title: "Create Action Plan",
      description: "Generate recommended actions and next steps for your team.",
      prompt: "Create an action plan for current supply chain risks.",
    },
    icon: <CheckSquare size={18} />,
    iconBgClass: "bg-green-500/15 text-green-400",
  },
];

interface QuickActionGridProps {
  onSelect: (prompt: string) => void;
}

export default function QuickActionGrid({ onSelect }: QuickActionGridProps): React.ReactElement {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 w-full">
      {ACTION_CONFIGS.map(({ action, icon, iconBgClass }) => (
        <QuickActionCard
          key={action.id}
          action={action}
          onSelect={onSelect}
          icon={icon}
          iconBgClass={iconBgClass}
        />
      ))}
    </div>
  );
}
