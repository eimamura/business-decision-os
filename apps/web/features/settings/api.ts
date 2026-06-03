import { apiFetch } from "@/lib/api";

export interface GroundTruthDataset {
  columns: string[];
  rows: string[][];
}

export interface GroundTruthResponse {
  sku_parameters: GroundTruthDataset;
  location_parameters: GroundTruthDataset;
  supplier_parameters: GroundTruthDataset;
  customer_parameters: GroundTruthDataset;
}

export interface SampleDataTable {
  table_name: string;
  row_count: number;
  top_rows: Record<string, unknown>[];
}

const ADMIN_HEADERS = { "X-Dev-User": "dev-admin" };

export async function getGroundTruth(): Promise<GroundTruthResponse> {
  return apiFetch<GroundTruthResponse>("/api/v1/admin/ground-truth", {
    headers: ADMIN_HEADERS,
  });
}

export async function saveGroundTruth(data: GroundTruthResponse): Promise<void> {
  await apiFetch<unknown>("/api/v1/admin/ground-truth", {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...ADMIN_HEADERS },
    body: JSON.stringify(data),
  });
}

export async function generateSampleData(params: {
  seed: number;
  sku_count: number;
  horizon_days: number;
  warehouse_count: number;
  missing_rate: number;
}): Promise<{ tables: SampleDataTable[] }> {
  return apiFetch<{ tables: SampleDataTable[] }>("/api/v1/admin/sample-data/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ADMIN_HEADERS },
    body: JSON.stringify(params),
  });
}
