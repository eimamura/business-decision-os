import ScenarioComparisonClient from "./ScenarioComparisonClient";

export default async function ScenarioPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ScenarioComparisonClient sessionId={sessionId} />;
}
