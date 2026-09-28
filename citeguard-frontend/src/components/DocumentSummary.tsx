import type { AnalysisResponse } from '../types';

export default function DocumentSummary({ data }: { data: AnalysisResponse }) {
  const md = data.document?.metadata;
  return <section className="border-b border-slate-200 bg-white px-6 py-5" aria-label="Paper overview">
    <h1 className="text-xl font-semibold">{md?.title || data.summary.document_name}</h1>
    {md?.authors?.length ? <p className="text-sm text-slate-600 mt-1">{md.authors.join(', ')}</p> : <p className="text-xs text-slate-500 mt-1">Authors not reliably extracted; consult the original paper.</p>}
    <p className="text-xs text-slate-500 mt-2">{data.summary.total_pages} pages · {data.summary.total_references} references · {data.summary.unique_claims} distinct cited sentences · {data.summary.total_claims} claim–citation pairs · {data.summary.processing_time_seconds}s</p>
    <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4 text-xs" aria-label="Verdict totals">
      {Object.entries(data.summary.verdict_counts || {}).map(([label, count]) => <span key={label}><strong>{count}</strong> {label.toLowerCase().replaceAll('_',' ')}</span>)}
    </div>
    <details className="mt-4 text-xs text-slate-600"><summary className="cursor-pointer">Whole-paper structure and extraction</summary>
      <p className="mt-2">{data.document?.sentences?.length || 0} sentences extracted. Reference and heading fields use document-layout heuristics.</p>
      <div className="flex flex-wrap gap-3 mt-2">{data.document?.sections?.map((section, i) => <span key={i}>p. {section.page} · {section.title}</span>)}</div>
      {md?.abstract && <p className="mt-3 leading-relaxed">{md.abstract}</p>}
    </details>
  </section>;
}
