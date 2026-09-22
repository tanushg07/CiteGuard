import type { AnalysisResponse } from '../types';

export default function DocumentSummary({ data }: { data: AnalysisResponse }) {
  const score = Math.min(100, Math.max(0, data.summary.supported_percentage));
  const references = [...new Map(data.claims.filter(c => c.reference_metadata?.status === 'enriched')
    .map(c => [c.reference_metadata!.doi || c.reference_metadata!.raw_reference, c.reference_metadata!])).values()];
  return <section className="report-overview" aria-label="Document support summary">
    <div className="score-gauge" role="img" aria-label={`${score}% of claims supported`}
      style={{ background: `conic-gradient(#15803d ${score * 3.6}deg, #e2e8f0 0deg)` }}>
      <div><strong>{score}%</strong><span>supported</span></div>
    </div>
    <div className="min-w-0 flex-1">
      <p className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Evidence at a glance</p>
      <h2 className="text-lg font-semibold mt-1">{data.summary.supported_count} of {data.summary.total_claims} claims supported</h2>
      <p className="text-xs text-slate-500 mt-1">Completed in {data.summary.processing_time_seconds}s · Inspect each source before drawing conclusions.</p>
      {references.length > 0 && <div className="flex flex-wrap gap-2 mt-3" aria-label="Cited reference metadata">
        {references.map(reference => <span key={reference.doi || reference.raw_reference} className="reference-badge">
          {reference.venue && <span>{reference.venue}</span>}
          {reference.doi && <a href={`https://doi.org/${encodeURIComponent(reference.doi)}`} target="_blank" rel="noreferrer">DOI ↗ {reference.doi}</a>}
        </span>)}
      </div>}
    </div>
  </section>;
}
