import React, { useState, useMemo } from 'react';
import type { AnalysisResponse, Status } from '../types';
import { api } from '../services/api';
import { 
  ChevronRight, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  HelpCircle, 
  Database, 
  Download, 
  Search, 
  ArrowLeft,
  BookOpen,
  Layers
} from 'lucide-react';

interface DashboardViewProps {
  data: AnalysisResponse;
  onReset: () => void;
}

const StatusPill: React.FC<{ status: Status; size?: 'sm' | 'md' }> = ({ status, size = 'sm' }) => {
  const styles: Record<Status, string> = {
    'Supported': 'bg-green-50 text-green-700 border-green-200',
    'Contradicted': 'bg-red-50 text-red-700 border-red-200',
    'Unrelated': 'bg-slate-100 text-slate-600 border-slate-200',
    'Numerical Mismatch': 'bg-amber-50 text-amber-700 border-amber-200'
  };

  const icons: Record<Status, React.ReactNode> = {
    'Supported': <CheckCircle2 className="w-3.5 h-3.5 mr-1" />,
    'Contradicted': <XCircle className="w-3.5 h-3.5 mr-1" />,
    'Unrelated': <HelpCircle className="w-3.5 h-3.5 mr-1" />,
    'Numerical Mismatch': <AlertCircle className="w-3.5 h-3.5 mr-1" />
  };

  return (
    <span className={`inline-flex items-center rounded-md font-medium border ${styles[status] || styles['Unrelated']} ${
      size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-xs'
    }`}>
      {icons[status] || icons['Unrelated']}
      {status === 'Unrelated' ? 'Insufficient evidence' : status}
    </span>
  );
};

const DashboardView: React.FC<DashboardViewProps> = ({ data, onReset }) => {
  const [selectedClaimId, setSelectedClaimId] = useState<string>(
    data.claims.length > 0 ? data.claims[0].id : ''
  );
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [showAllEvidence, setShowAllEvidence] = useState<boolean>(false);

  // Filtered claims
  const filteredClaims = useMemo(() => {
    return data.claims.filter((c) => {
      const matchesSearch = c.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            c.citation_marker.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            c.source_document.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
      const matchesConfidence = c.confidence >= minConfidence;

      return matchesSearch && matchesStatus && matchesConfidence;
    });
  }, [data.claims, searchQuery, statusFilter, minConfidence]);

  const selectedClaim = useMemo(() => {
    const found = data.claims.find((c) => c.id === selectedClaimId);
    return found || (data.claims.length > 0 ? data.claims[0] : null);
  }, [data.claims, selectedClaimId]);

  const summary = data.summary;

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col bg-[#F9FAFB]">
      {data.warnings?.map(warning => <p key={warning} role="status" className="bg-amber-50 text-amber-900 border border-amber-200 rounded p-3 text-sm">{warning}</p>)}
      {/* Top Document Summary Banner */}
      <div className="bg-white border-b border-slate-200 px-8 py-5 shadow-2xs">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
              <button 
                onClick={onReset}
                className="hover:text-slate-900 inline-flex items-center space-x-1 cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>New Verification</span>
              </button>
              <span>/</span>
              <span>Verification Report</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
              <FileText className="w-5 h-5 text-slate-700" />
              <span>{summary.document_name}</span>
            </h1>
          </div>

          {/* Quick Metrics Cards */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="bg-slate-50 border border-slate-200 rounded px-3 py-1.5 text-center">
              <div className="text-xs text-slate-500 font-medium">Claims</div>
              <div className="text-base font-bold text-slate-900">{summary.total_claims}</div>
            </div>

            <div className="bg-green-50 border border-green-200 rounded px-3 py-1.5 text-center">
              <div className="text-xs text-green-700 font-medium">Supported</div>
              <div className="text-base font-bold text-green-800">
                {summary.supported_count} <span className="text-xs font-normal">({summary.supported_percentage}%)</span>
              </div>
            </div>

            <div className="bg-red-50 border border-red-200 rounded px-3 py-1.5 text-center">
              <div className="text-xs text-red-700 font-medium">Contradicted</div>
              <div className="text-base font-bold text-red-800">{summary.contradicted_count}</div>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded px-3 py-1.5 text-center">
              <div className="text-xs text-amber-700 font-medium">Mismatch</div>
              <div className="text-base font-bold text-amber-800">{summary.numerical_mismatch_count}</div>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded px-3 py-1.5 text-center">
              <div className="text-xs text-slate-500 font-medium">Avg Conf</div>
              <div className="text-base font-bold text-slate-900">{summary.average_confidence}%</div>
            </div>

            {/* Export Actions */}
            <div className="flex items-center space-x-2 pl-2 border-l border-slate-200">
              <button
                onClick={() => api.exportResults(data.job_id, 'csv')}
                className="inline-flex items-center space-x-1 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 px-3 py-1.5 rounded text-xs font-medium transition-colors shadow-2xs cursor-pointer"
                title="Export CSV"
              >
                <Download className="w-3.5 h-3.5" />
                <span>CSV</span>
              </button>
              <button
                onClick={() => api.exportResults(data.job_id, 'json')}
                className="inline-flex items-center space-x-1 bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors shadow-2xs cursor-pointer"
                title="Export JSON"
              >
                <Download className="w-3.5 h-3.5" />
                <span>JSON</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden max-w-7xl w-full mx-auto p-6 gap-6">
        {/* Left Sidebar: Extracted Claims List */}
        <div className="w-96 flex flex-col bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden shrink-0">
          {/* Search & Filter Header */}
          <div className="p-4 border-b border-slate-200 space-y-3 bg-slate-50/50">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search claims or citations..."
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-slate-900"
              />
            </div>

            {/* Status Filter Pills */}
            <div className="flex flex-wrap gap-1.5">
              {['ALL', 'Supported', 'Contradicted', 'Numerical Mismatch', 'Unrelated'].map((status) => (
                <button
                  key={status === 'Unrelated' ? 'Insufficient evidence' : status}
                  onClick={() => setStatusFilter(status)}
                  className={`text-xs px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
                    statusFilter === status
                      ? 'bg-slate-900 text-white'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {status === 'Unrelated' ? 'Insufficient evidence' : status}
                </button>
              ))}
            </div>

            {/* Confidence Range Slider */}
            <div className="pt-1">
              <div className="flex justify-between text-[11px] text-slate-500 font-medium mb-1">
                <span>Min Confidence</span>
                <span className="font-mono text-slate-900">{minConfidence}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="95"
                step="5"
                value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="w-full accent-slate-900 h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          {/* Claims Scroll List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {filteredClaims.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No claims match your filter criteria.
              </div>
            ) : (
              filteredClaims.map((claim) => {
                const isSelected = selectedClaim?.id === claim.id;
                return (
                  <div
                    key={claim.id}
                    onClick={() => setSelectedClaimId(claim.id)}
                    className={`p-4 cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-slate-50/80 border-l-4 border-l-slate-900'
                        : 'hover:bg-slate-50/50 border-l-4 border-l-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono font-bold bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200">
                        {claim.citation_marker || `Claim ${claim.id}`}
                      </span>
                      <StatusPill status={claim.status} />
                    </div>
                    <p className="text-xs text-slate-800 font-serif line-clamp-2 leading-relaxed">
                      "{claim.text}"
                    </p>
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100/60 text-[11px] text-slate-400">
                      <span>Conf: {claim.confidence}%</span>
                      <span className="truncate max-w-[140px]">{claim.source_document}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Main Content Area: Selected Claim Inspection */}
        {selectedClaim ? (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            {/* Section 1: Original Manuscript Context */}
            <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500 font-semibold uppercase tracking-wider">
                <div className="flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-slate-600" />
                  <span>Original Manuscript Context</span>
                </div>
                <span className="font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                  Page {selectedClaim.page_number}
                </span>
              </div>

              <div className="font-serif text-base leading-relaxed text-slate-700 bg-slate-50/40 p-4 rounded border border-slate-100">
                {selectedClaim.context ? (
                  selectedClaim.context.split(selectedClaim.text).map((part, i, arr) => (
                    <React.Fragment key={i}>
                      {part}
                      {i < arr.length - 1 && (
                        <span className="bg-amber-100 text-slate-900 px-1 py-0.5 rounded font-medium border-b-2 border-amber-400">
                          {selectedClaim.text}
                        </span>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <span className="bg-amber-100 text-slate-900 px-1 py-0.5 rounded font-medium">
                    {selectedClaim.text}
                  </span>
                )}
              </div>
            </div>

            {/* Section 2: Verification Analysis Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* NLI Verdict Card */}
              <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg p-6 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Natural Language Inference (NLI)
                  </h3>
                  <StatusPill status={selectedClaim.status} size="md" />
                </div>

                <div>
                  <div className="text-xl font-bold text-slate-900 mb-1">
                    {selectedClaim.status === 'Supported' && 'Evidence Strongly Supports Claim'}
                    {selectedClaim.status === 'Contradicted' && 'Evidence Directly Contradicts Claim'}
                    {selectedClaim.status === 'Numerical Mismatch' && 'Numerical Value Divergence Detected'}
                    {selectedClaim.status === 'Unrelated' && 'Evidence Does Not Sufficiently Align'}
                  </div>
                  <p className="text-xs text-slate-500">
                    {data.engines?.verification === 'nli' ? 'DistilBERT MNLI prediction; confidence is a model score, not a guarantee.' : 'Conservative lexical baseline; neural verification did not run.'}
                  </p>
                </div>

                {/* Confidence Bar */}
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-600">Model Confidence</span>
                    <span className="text-slate-900 font-mono">{selectedClaim.confidence}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        selectedClaim.status === 'Supported'
                          ? 'bg-green-600'
                          : selectedClaim.status === 'Contradicted'
                          ? 'bg-red-600'
                          : selectedClaim.status === 'Numerical Mismatch'
                          ? 'bg-amber-500'
                          : 'bg-slate-400'
                      }`}
                      style={{ width: `${selectedClaim.confidence}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Entity / Statistical Verification Card */}
              <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs space-y-3">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Statistical Verification
                </h3>

                {selectedClaim.numerical_check ? (
                  <div className="space-y-2">
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs font-mono text-slate-700 leading-relaxed">
                      {selectedClaim.numerical_check.split('|').map((part, i) => (
                        <div key={i} className="mb-1 last:mb-0">
                          {part.trim()}
                        </div>
                      ))}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {selectedClaim.numerical_comparison?.is_match
                        ? 'Extracted values occur in evidence; this does not establish their context.'
                        : 'Discrepancy detected between claim numbers and source document numbers.'}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-28 text-xs text-slate-400 bg-slate-50 rounded border border-slate-200 border-dashed p-4 text-center">
                    <span>No quantitative or metric entities detected in this claim.</span>
                  </div>
                )}
              </div>
            </div>

            {/* Section 3: Retrieved Source Evidence Card */}
            <div className="bg-slate-900 rounded-lg p-6 shadow-md text-slate-200 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <Database className="w-4 h-4 text-slate-300" />
                  <span>Retrieved Source Evidence</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">
                    {selectedClaim.citation_marker}
                  </span>
                  <span className="text-xs text-slate-400 truncate max-w-xs">{selectedClaim.source_document}</span>
                </div>
              </div>

              <blockquote className="font-serif text-base leading-relaxed text-slate-100 bg-slate-800/40 p-4 rounded border-l-4 border-slate-600">
                "{selectedClaim.evidence}"
              </blockquote>

              {/* Additional Candidate Evidence toggle */}
              {selectedClaim.evidence_list && selectedClaim.evidence_list.length > 1 && (
                <div className="pt-2">
                  <button
                    onClick={() => setShowAllEvidence(!showAllEvidence)}
                    className="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1 cursor-pointer"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>
                      {showAllEvidence
                        ? 'Hide supplementary candidate passages'
                        : `Show ${selectedClaim.evidence_list.length - 1} alternative candidate passages`}
                    </span>
                  </button>

                  {showAllEvidence && (
                    <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                      {selectedClaim.evidence_list.filter(ev => ev.evidence_text !== selectedClaim.evidence || ev.source_document !== selectedClaim.source_document).map((ev, idx) => (
                        <div key={idx} className="p-3 bg-slate-800/60 rounded text-xs text-slate-300 space-y-1">
                          <div className="flex justify-between text-slate-400 text-[11px]">
                            <span>Candidate #{idx + 2} • {ev.source_document}</span>
                            <span>Score: {ev.relevance_score.toFixed(3)}</span>
                          </div>
                          <p className="font-serif text-slate-200">"{ev.evidence_text}"</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Traceability Breadcrumb Footer */}
            <div className="flex items-center space-x-2 text-xs font-medium text-slate-500 bg-white border border-slate-200 rounded p-3 shadow-2xs">
              <span className="font-mono">{selectedClaim.id}</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span>Citation {selectedClaim.citation_marker}</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="truncate max-w-[220px]">{selectedClaim.source_document}</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="font-semibold text-slate-700">{selectedClaim.status}</span>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-white border border-slate-200 rounded-lg p-12 text-slate-400 text-sm">
            Select a claim from the left sidebar to view detailed verification breakdown.
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardView;
