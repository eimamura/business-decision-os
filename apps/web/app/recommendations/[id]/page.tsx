import RecommendationDetailClient from "./RecommendationDetailClient";

export default async function RecommendationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecommendationDetailClient id={id} />;
}
