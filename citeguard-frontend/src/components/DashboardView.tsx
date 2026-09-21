import React, { useState } from 'react';
import { mockClaims, type Claim, type Status } from '../data/mockData';
import { ChevronRight, FileText, CheckCircle2, XCircle, AlertCircle, HelpCircle, Database } from 'lucide-react';

const StatusPill: React.FC<{ status: Status }> = ({ status }) => {
  const styles = {
    'Supported': 'bg-green-50 text-green-700 border-green-200',
    'Contradicted': 'bg-red-50 text-red-700 border-red-200',
    'Unrelated': 'bg-slate-100 text-slate-600 border-slate-200',
    'Numerical Mismatch': 'bg-amber-50 text-amber-700 border-amber-200'
  };

  const icons = {
    'Supported': <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />,
    'Contradicted': <XCircle className="w-3.5 h-3.5 mr-1.5" />,
    'Unrelated': <HelpCircle className="w-3.5 h-3.5 mr-1.5" />,
    'Numerical Mismatch': <AlertCircle className="w-3.5 h-3.5 mr-1.5" />
  };

  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${styles[status]}`}>
      {icons[status]}
      {status}
    </span>
  );
};

const DashboardView: React.FC = () => {
  const [selectedClaim, setSelectedClaim] = useState<Claim>(mockClaims[0]);

  return (
    <div className="h-screen flex bg-[#F9FAFB] overflow-hidden">
      {/* Left Sidebar */}
      <div className="w-96 border-r border-slate-200 bg-white flex flex-col shadow-sm z-10">
        <div className="p-5 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Extracted Claims</h2>
          <p className="text-sm text-slate-500 mt-1">Verification pipeline results</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {mockClaims.map((claim) => (
            <div 
              key={claim.id}
              onClick={() => setSelectedClaim(claim)}
              className={`p-4 border-b border-slate-100 cursor-pointer transition-colors ${selectedClaim.id === claim.id ? 'bg-slate-50 border-l-4 border-l-slate-800' : 'hover:bg-slate-50 border-l-4 border-l-transparent'}`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                  {claim.citationNumber}
                </span>
                <StatusPill status={claim.status} />
              </div>
              <p className="text-sm text-slate-800 font-serif line-clamp-2 leading-relaxed">
                "{claim.text}"
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-4xl mx-auto space-y-8">
          
          {/* Top Section: Context & Claim */}
          <div className="bg-white border border-slate-200 rounded-lg p-8 shadow-sm">
            <div className="flex items-center space-x-2 text-sm text-slate-500 font-medium mb-4 uppercase tracking-wider">
              <FileText className="w-4 h-4" />
              <span>Original Manuscript Context</span>
            </div>
            <p className="font-serif text-lg leading-loose text-slate-600">
              {selectedClaim.context.split(selectedClaim.text).map((part, i, arr) => (
                <React.Fragment key={i}>
                  {part}
                  {i < arr.length - 1 && (
                    <span className="bg-yellow-100 text-slate-900 px-1 rounded-sm py-0.5 font-medium">
                      {selectedClaim.text}
                    </span>
                  )}
                </React.Fragment>
              ))}
            </p>
          </div>

          {/* Verification Verdict & Numerical Check */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* NLI Verdict Card */}
            <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg p-6 shadow-sm">
              <h3 className="text-sm text-slate-500 font-medium mb-4 uppercase tracking-wider">NLI Verdict</h3>
              <div className="flex items-center space-x-4 mb-6">
                <StatusPill status={selectedClaim.status} />
                <span className="text-xl font-semibold text-slate-900">
                  {selectedClaim.status === 'Supported' ? 'Evidence aligns with claim' :
                   selectedClaim.status === 'Contradicted' ? 'Evidence contradicts claim' :
                   selectedClaim.status === 'Unrelated' ? 'Evidence does not address claim' : 
                   'Numerical divergence detected'}
                </span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm font-medium">
                  <span className="text-slate-600">Model Confidence</span>
                  <span className="text-slate-900">{selectedClaim.confidence}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5">
                  <div 
                    className={`h-2.5 rounded-full ${selectedClaim.status === 'Supported' ? 'bg-green-600' : selectedClaim.status === 'Contradicted' ? 'bg-red-600' : selectedClaim.status === 'Unrelated' ? 'bg-slate-400' : 'bg-amber-500'}`} 
                    style={{ width: `${selectedClaim.confidence}%` }}
                  ></div>
                </div>
              </div>
            </div>

            {/* Numerical Check */}
            <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm">
              <h3 className="text-sm text-slate-500 font-medium mb-4 uppercase tracking-wider">Entity Verification</h3>
              {selectedClaim.numericalCheck ? (
                <div className="space-y-3">
                  <div className="text-sm p-3 bg-slate-50 border border-slate-200 rounded text-slate-700 font-mono">
                    {selectedClaim.numericalCheck.split('|').map((part, i) => (
                      <div key={i} className="mb-1 last:mb-0">{part.trim()}</div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-24 text-sm text-slate-400 bg-slate-50 rounded border border-slate-100 border-dashed">
                  No statistical entities detected
                </div>
              )}
            </div>
          </div>

          {/* Middle Section: Retrieved Evidence */}
          <div className="bg-slate-900 rounded-lg p-8 shadow-md text-slate-200">
            <div className="flex items-center space-x-2 text-sm text-slate-400 font-medium mb-4 uppercase tracking-wider">
              <Database className="w-4 h-4" />
              <span>Retrieved Source Evidence</span>
            </div>
            <div className="mb-4 pb-4 border-b border-slate-800">
              <span className="text-sm font-mono bg-slate-800 text-slate-300 px-2 py-1 rounded mr-3">
                {selectedClaim.citationNumber}
              </span>
              <span className="text-sm text-slate-300">{selectedClaim.sourceDocument}</span>
            </div>
            <p className="font-serif text-lg leading-relaxed text-slate-100">
              "{selectedClaim.evidence}"
            </p>
          </div>

          {/* Traceability Footer */}
          <div className="flex items-center space-x-2 text-xs font-medium text-slate-500 pt-4 px-2">
            <span>Claim {selectedClaim.id}</span>
            <ChevronRight className="w-3 h-3" />
            <span>Citation {selectedClaim.citationNumber}</span>
            <ChevronRight className="w-3 h-3" />
            <span className="truncate max-w-[200px]">{selectedClaim.sourceDocument}</span>
            <ChevronRight className="w-3 h-3" />
            <span>Evidence Passage</span>
          </div>

        </div>
      </div>
    </div>
  );
};

export default DashboardView;
