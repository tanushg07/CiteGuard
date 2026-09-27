import { useState } from 'react';
import type { DragEvent } from 'react';
import { FileText, Upload } from 'lucide-react';
import { notify } from '../services/notifications';

interface Props {
  onStartAnalysis: (params: {type: 'pdf' | 'text' | 'benchmark'; targetFile?: File; documentTitle?: string}) => void;
}

export default function LandingView({ onStartAnalysis }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const select = (candidate?: File) => {
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith('.pdf')) { notify('Choose a research paper in PDF format.', 'error'); return; }
    if (candidate.size > 25 * 1024 * 1024) { notify('The PDF must be 25 MB or smaller.', 'error'); return; }
    setFile(candidate);
  };
  const drop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); select(event.dataTransfer.files[0]); };
  return <div className="max-w-3xl mx-auto px-6 py-16 space-y-8">
    <header className="space-y-3">
      <p className="text-xs uppercase tracking-widest text-slate-500">Citation verification workspace</p>
      <h1 className="text-3xl font-semibold tracking-tight">Review a paper against its sources</h1>
      <p className="text-slate-600 leading-relaxed">Upload one research PDF. CiteGuard reads the whole paper, identifies cited works, retrieves accessible source papers, and compares their passages with the original claims.</p>
    </header>
    <div onDrop={drop} onDragOver={event => event.preventDefault()} className="border border-dashed border-slate-400 bg-white p-10 text-center space-y-4">
      <FileText className="w-8 h-8 mx-auto text-slate-500" />
      <p className="font-medium">{file ? file.name : 'Choose or drop a research paper'}</p>
      <p className="text-sm text-slate-500">{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · Ready to verify` : 'Text-based PDF · Up to 25 MB'}</p>
      <label className="inline-flex items-center gap-2 border border-slate-300 px-4 py-2 cursor-pointer text-sm focus-within:outline-2">
        <Upload className="w-4 h-4" />{file ? 'Change paper' : 'Choose PDF'}
        <input aria-label="Research paper PDF" type="file" accept=".pdf" className="sr-only" onChange={event => select(event.target.files?.[0])} />
      </label>
    </div>
    <button disabled={!file} className="w-full bg-slate-900 text-white py-3 text-sm font-medium disabled:opacity-40 cursor-pointer"
      onClick={() => file && onStartAnalysis({type: 'pdf', targetFile: file, documentTitle: file.name})}>Verify citations</button>
    <div className="grid sm:grid-cols-3 gap-6 text-sm border-t border-slate-200 pt-6">
      <div><h2 className="font-semibold mb-2">1. Analyze the paper</h2><p className="text-slate-600">Read all pages and associate claims with nearby citations and references.</p></div>
      <div><h2 className="font-semibold mb-2">2. Find the evidence</h2><p className="text-slate-600">Identify sources and retrieve legitimate accessible full text automatically.</p></div>
      <div><h2 className="font-semibold mb-2">3. Review each decision</h2><p className="text-slate-600">Inspect source pages, model results, numerical checks, and unresolved cases.</p></div>
    </div>
    <p className="text-xs text-slate-500 leading-relaxed">Inaccessible papers and uncertain matches are reported explicitly. Metadata is never treated as evidence. Scanned PDFs require OCR before upload. Bibliographic queries are sent to enabled scholarly APIs; optional Groq explanations send selected claims and passages when configured.</p>
  </div>;
}
