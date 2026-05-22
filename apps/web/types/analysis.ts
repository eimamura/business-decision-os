export type RiskLevel = "Critical" | "High" | "Medium" | "Low";

export type AnalysisSummaryCard = {
  label: string;
  value: string;
  tone: "critical" | "high" | "warning" | "neutral" | "success";
};

export type RecommendedAction = {
  action: string;
  priority: RiskLevel;
  reason?: string;
  owner?: string;
  timing?: string;
};

export type RiskItem = {
  sku: string;
  location: string;
  daysOfSupply: string;
  driver: string;
};

export type RiskGroup = {
  level: RiskLevel;
  description: string;
  items: RiskItem[];
  actions: string;
};

export type InventoryShortageAnalysis = {
  title: string;
  status: string;
  duration: string;
  confidence: number;
  confidenceLabel: string;
  summary: string;
  summaryCards: AnalysisSummaryCard[];
  keyFindings: string[];
  recommendedActions: RecommendedAction[];
  riskGroups: RiskGroup[];
  dataUsed: string[];
};
