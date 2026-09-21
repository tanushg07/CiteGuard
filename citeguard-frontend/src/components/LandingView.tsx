import React from 'react';
import { UploadCloud, FileText, Database, ShieldCheck } from 'lucide-react';

interface LandingViewProps {
  onUpload: () => void;
}

const LandingView: React.FC<LandingViewProps> = ({ onUpload }) => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 space-y-16">
      {/* Hero Section */}
      <div className="text-center space-y-6 max-w-3xl">
        <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-slate-900">
          Verify the Substance, Not Just the Source.
        </h1>
        <p className="text-lg text-slate-600 font-serif">
          An AI-powered Citation Verification and Evidence Alignment System built for rigorous academic research.
        </p>
      </div>

      {/* Upload Zone */}
      <div 
        className="w-full max-w-2xl border-2 border-dashed border-slate-300 rounded-lg bg-white p-16 flex flex-col items-center justify-center cursor-pointer hover:border-slate-400 hover:bg-slate-50 transition-colors shadow-sm"
        onClick={onUpload}
      >
        <div className="bg-slate-100 p-4 rounded-full mb-6">
          <UploadCloud className="w-8 h-8 text-slate-600" />
        </div>
        <h3 className="text-xl font-medium text-slate-900 mb-2">Upload Academic PDF</h3>
        <p className="text-slate-500 text-sm mb-6 text-center">Drag and drop your manuscript or click to browse.</p>
        <button className="bg-slate-900 text-white px-6 py-2.5 rounded text-sm font-medium hover:bg-slate-800 transition-colors">
          Select Document
        </button>
      </div>

      {/* 3-Step Pipeline Graphic */}
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-8 pt-8 border-t border-slate-200">
        <div className="flex flex-col items-center text-center space-y-4">
          <div className="w-12 h-12 bg-white border border-slate-200 rounded shadow-sm flex items-center justify-center text-slate-700 font-medium">
            1
          </div>
          <FileText className="w-6 h-6 text-slate-400" />
          <h4 className="font-medium text-slate-900">Upload PDF</h4>
          <p className="text-sm text-slate-500 leading-relaxed">Securely ingest your document into our private processing pipeline.</p>
        </div>
        <div className="flex flex-col items-center text-center space-y-4">
          <div className="w-12 h-12 bg-white border border-slate-200 rounded shadow-sm flex items-center justify-center text-slate-700 font-medium">
            2
          </div>
          <Database className="w-6 h-6 text-slate-400" />
          <h4 className="font-medium text-slate-900">AI Extraction & Retrieval</h4>
          <p className="text-sm text-slate-500 leading-relaxed">Isolate claims and retrieve cited evidence using cross-encoder reranking.</p>
        </div>
        <div className="flex flex-col items-center text-center space-y-4">
          <div className="w-12 h-12 bg-white border border-slate-200 rounded shadow-sm flex items-center justify-center text-slate-700 font-medium">
            3
          </div>
          <ShieldCheck className="w-6 h-6 text-slate-400" />
          <h4 className="font-medium text-slate-900">Traceable Verification Results</h4>
          <p className="text-sm text-slate-500 leading-relaxed">Review alignment scores and verify evidence in a structured interface.</p>
        </div>
      </div>
    </div>
  );
};

export default LandingView;
