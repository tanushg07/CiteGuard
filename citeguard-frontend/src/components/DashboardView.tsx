import { useMemo, useState } from 'react';
import type { AnalysisResponse } from '../types';
import ClaimCard, { OverlapText } from './ClaimCard';
import DocumentSummary from './DocumentSummary';
import { api } from '../services/api';

export default function DashboardView({data, onReset}: {data: AnalysisResponse; onReset: () => void}) {
  const [selected, setSelected] = useState(data.claims[0]?.id || '');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const claims = useMemo(() => data.claims.filter(c => (filter === 'ALL' || c.final_verdict === filter) &&
    `${c.text} ${c.citation_marker} ${c.reference_metadata?.title || ''}`.toLowerCase().includes(query.toLowerCase())), [data.claims, query, filter]);
  const claim = claims.find(c => c.id === selected) || claims[0];
  const source = claim?.source_identification;
  return <div className="max-w-screen-2xl mx-auto">
    <div className="flex justify-between px-6 py-3 border-b text-xs border-slate-200">
      <button onClick={onReset} className="cursor-pointer">Upload another paper</button>
      <div className="flex gap-4"><button onClick={() => api.exportResults(data.job_id,'json')}>Export full JSON report</button><button onClick={() => api.exportResults(data.job_id,'csv')}>Export CSV</button></div>
    </div>
    <DocumentSummary data={data} />
    {data.warnings?.map((warning,i) => <p key={i} role="status" className="mx-6 mt-3 p-3 border border-amber-200 bg-amber-50 text-xs text-amber-950">{warning}</p>)}
    <div className="grid lg:grid-cols-[320px_1fr] gap-6 p-6">
      <aside className="border border-slate-200 bg-white self-start">
        <div className="p-3 space-y-3 border-b border-slate-200">
          <input aria-label="Search claims and sources" placeholder="Search claims or sources" value={query} onChange={e => setQuery(e.target.value)} className="w-full border border-slate-300 p-2 text-sm" />
          <select aria-label="Filter verdict" value={filter} onChange={e => setFilter(e.target.value)} className="w-full border border-slate-300 p-2 text-xs">
            <option value="ALL">All verdicts ({data.claims.length})</option>
            {Object.keys(data.summary.verdict_counts || {}).map(v => <option key={v} value={v}>{v.replaceAll('_',' ')}</option>)}
          </select>
        </div>
        <div className="max-h-[75vh] overflow-y-auto divide-y divide-slate-200">
          {claims.map(c => <ClaimCard key={c.id} claim={c} selected={claim?.id === c.id} onSelect={() => setSelected(c.id)} />)}
          {!claims.length && <p className="p-4 text-sm text-slate-500">{data.claims.length ? 'No claims match these filters.' : 'No supported citation patterns were detected.'}</p>}
        </div>
      </aside>
      {claim && <article className="min-w-0 space-y-5">
        <section className="border border-slate-200 bg-white p-5 space-y-3">
          <div className="flex flex-wrap justify-between gap-3 text-xs text-slate-500"><span>{claim.claim_group_id} · {claim.citation_marker} · Manuscript page {claim.page_number} · {claim.section}</span><strong className="text-slate-900">{claim.final_verdict?.replaceAll('_',' ')}</strong></div>
          <blockquote className="font-serif text-lg leading-relaxed"><OverlapText text={claim.text} other={claim.evidence} /></blockquote>
          <p className="text-xs text-slate-500">Citation association: {claim.association_confidence?.replaceAll('_',' ')}. Shared terms are highlighted; overlap does not establish support.</p>
          <p className="border-t border-slate-200 pt-3 text-sm">{claim.decision_reason}</p>
          <details className="text-xs text-slate-500"><summary>Original paragraph</summary><p className="mt-2 leading-relaxed">{claim.context}</p></details>
        </section>
        <section className="border border-slate-200 bg-white p-5 space-y-3">
          <h2 className="font-semibold text-sm">Reference → identified source</h2>
          <p className="text-sm">{claim.reference_metadata?.raw_reference || 'No unambiguous reference-list entry could be associated with this marker.'}</p>
          <p className="text-xs text-slate-600">{source?.status} · {source?.reason}</p>
          <p className="font-medium text-sm">{claim.reference_metadata?.title}</p>
          <p className="text-xs text-slate-600">{claim.reference_metadata?.authors?.join(', ')} {claim.reference_metadata?.year} · {claim.reference_metadata?.venue}</p>
          <div className="flex flex-wrap gap-4 text-xs text-teal-800 underline">
            {claim.reference_metadata?.doi && <a href={`https://doi.org/${encodeURIComponent(claim.reference_metadata.doi)}`} target="_blank" rel="noreferrer">DOI: {claim.reference_metadata.doi}</a>}
            {source?.url && /^https?:\/\//.test(source.url) && <a href={source.url} target="_blank" rel="noreferrer">Open retrieved source PDF</a>}
          </div>
          <details className="text-xs"><summary className="cursor-pointer">Identification and retrieval audit</summary><pre className="whitespace-pre-wrap break-all mt-2 bg-slate-50 p-3">{JSON.stringify(source, null, 2)}</pre></details>
        </section>
        <section className="border border-slate-200 bg-white p-5 space-y-4">
          <h2 className="font-semibold text-sm">Source evidence</h2>
          {!claim.evidence_list?.length && <p className="text-sm text-slate-600">No source passage available. Bibliographic metadata and generated explanations are not evidence.</p>}
          {claim.evidence_list?.map((e,i) => <div key={`${e.source_id}-${e.evidence_id}-${i}`} className="border-l-2 border-teal-700 pl-4 space-y-2">
            <p className="text-xs font-medium">{e.source_document} · Source page {e.page_number} · {e.section || 'Section undetected'} · Paragraph {e.paragraph ?? 'unknown'}</p>
            <blockquote className="font-serif text-sm leading-relaxed"><OverlapText text={e.evidence_text} other={claim.text} /></blockquote>
            <p className="text-xs text-slate-500">{e.evidence_id} · Lexical score {e.retrieval_score?.toFixed(3)} · Rerank score {e.rerank_score == null ? 'unavailable' : e.rerank_score.toFixed(3)} · Scores measure relevance, not support.</p>
          </div>)}
        </section>
        <section className="grid md:grid-cols-2 gap-4 text-sm">
          <div className="border border-slate-200 bg-white p-5 space-y-2"><h2 className="font-semibold">NLI result</h2><p>{claim.nli?.status}: {claim.nli?.label || 'Unavailable'} {claim.nli?.score != null ? `(${(claim.nli.score*100).toFixed(1)}% model score)` : ''}</p><p className="text-xs text-slate-500">Model score is not a probability that the citation is correct.</p>{claim.nli?.components && <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(claim.nli.components,null,2)}</pre>}</div>
          <div className="border border-slate-200 bg-white p-5 space-y-2"><h2 className="font-semibold">Numerical verification</h2><p>{claim.numerical_comparison?.status || 'NOT_APPLICABLE'}</p><p className="text-xs text-slate-600">{claim.numerical_comparison?.details}</p>{claim.numerical_comparison?.calculation && <p className="font-mono text-xs">{claim.numerical_comparison.calculation}</p>}</div>
        </section>
        {claim.reasoning && <section className="border-t border-slate-200 pt-4 text-sm text-slate-600"><h2 className="text-xs font-semibold mb-2">Explanation · {claim.reasoning_provider === 'groq' ? 'Groq-generated, not evidence' : 'Rule-based'}</h2><p>{claim.reasoning}</p></section>}
      </article>}
    </div>
  </div>;
}
