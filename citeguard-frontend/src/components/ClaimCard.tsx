import { useId, useState } from 'react';
import type { Claim } from '../types';

const stopWords = new Set('the a an and or of in on to for with was were is are this that by from as at it'.split(' '));
const tokens = (text: string) => text.match(/\d+(?:\.\d+)?%?|[\p{L}][\p{L}\p{N}-]*/gu) || [];

export function OverlapText({ text, other }: { text: string; other: string }) {
  const shared = new Set(tokens(other).map(word => word.toLowerCase()));
  return <>{text.split(/(\d+(?:\.\d+)?%?|[\p{L}][\p{L}\p{N}-]*)/gu).map((part, index) =>
    shared.has(part.toLowerCase()) && !stopWords.has(part.toLowerCase())
      ? <mark key={index} className="overlap-mark">{part}</mark> : part)}</>;
}

export default function ClaimCard({ claim, selected, onSelect }: {
  claim: Claim; selected: boolean; onSelect: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const tone = claim.status === 'Supported' ? 'supported' : claim.status === 'Contradicted' ? 'contradicted' : 'uncertain';
  return <article className={`claim-card ${tone} ${selected ? 'selected' : ''}`}>
    <button className="w-full text-left cursor-pointer" onClick={onSelect} aria-pressed={selected}>
      <div className="flex justify-between gap-2 text-xs mb-2">
        <span className="font-mono font-semibold">{claim.citation_marker}</span>
        <span>{claim.status === 'Unrelated' ? 'Insufficient evidence' : claim.status}</span>
      </div>
      <p className="text-sm leading-relaxed line-clamp-3">{claim.text}</p>
      <p className="mt-2 text-xs text-slate-500">Page {claim.page_number} · {claim.confidence}% confidence</p>
    </button>
    <button onClick={() => setExpanded(!expanded)} aria-expanded={expanded} aria-controls={panelId}
      className="text-xs font-semibold mt-3 text-slate-600 cursor-pointer">{expanded ? '− Hide explanation' : '+ Why this verdict?'}</button>
    <div id={panelId} className={`claim-expansion ${expanded ? 'expanded' : ''}`} inert={!expanded}>
      <div><p className="text-xs leading-relaxed text-slate-600 pt-3">{claim.reasoning || 'Select this claim to inspect the evidence and numerical checks.'}</p></div>
    </div>
  </article>;
}
