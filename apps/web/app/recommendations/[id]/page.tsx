"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { useRecommendation } from "@/features/recommendations/hooks";
import type { Recommendation } from "@/features/recommendations/api";

interface RecommendationPageProps {
  params: { id: string };
}

const RISK_STYLES = {
  low: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-red-100 text-red-700",
};

export default function RecommendationPage({ params }: RecommendationPageProps): React.ReactElement {
  const { id } = params;
  const { data: recommendation, isLoading: loading } = useRecommendation(id);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (recommendation === undefined && !loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Recommendation not found.</div>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <Link href={`/chat/${recommendation.session_id}`} className="text-sm text-blue-600 hover:underline">
          ← Back to Chat
        </Link>
        <h1 className="text-lg font-semibold text-gray-900">Recommendation Detail</h1>
        <span
          className={`ml-auto text-xs px-2.5 py-1 rounded-full font-medium capitalize ${RISK_STYLES[recommendation.risk_level]}`}
        >
          {recommendation.risk_level} risk
        </span>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Primary Recommendation</h2>
              <p className="text-sm text-gray-600 mt-0.5">{recommendation.primary_label}</p>
            </div>
            {recommendation.requires_approval && (
              <span className="bg-orange-100 text-orange-700 text-xs px-2.5 py-1 rounded-full font-medium">
                Requires Approval
              </span>
            )}
          </div>
          <KpiScoreGrid scores={recommendation.primary_kpi_scores} />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-3">Rationale</h2>
          <div className="prose prose-sm max-w-none text-gray-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
              {recommendation.rationale}
            </ReactMarkdown>
          </div>
        </div>

        {recommendation.alternatives.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Alternatives</h2>
            {recommendation.alternatives.map((alt) => (
              <div key={alt.id} className="bg-white rounded-xl border border-gray-200 p-6">
                <h3 className="text-sm font-semibold text-gray-800 mb-2">{alt.label}</h3>
                <KpiScoreGrid scores={alt.kpi_scores} />
                {alt.tradeoff && (
                  <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
                    <div>
                      <span className="text-xs font-semibold text-amber-800">What you give up:</span>
                      <p className="text-xs text-amber-700 mt-0.5">{alt.tradeoff.what_you_give_up}</p>
                    </div>
                    <div>
                      <span className="text-xs font-semibold text-green-800">Benefit:</span>
                      <p className="text-xs text-green-700 mt-0.5">{alt.tradeoff.benefit}</p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-800 mb-3">Weight Vector Used</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(recommendation.weight_vector).map(([kpi, w]) => (
              <span key={kpi} className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full">
                {kpi}: {(w * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

function KpiScoreGrid({ scores }: { scores: Recommendation["primary_kpi_scores"] }): React.ReactElement {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {scores.map((s) => (
        <div key={s.kpi} className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-500 capitalize">{s.kpi.replace(/_/g, " ")}</p>
          <p className="text-sm font-semibold text-gray-900 mt-0.5">{(s.score * 100).toFixed(1)}%</p>
          <div className="mt-1.5 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${s.score * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
