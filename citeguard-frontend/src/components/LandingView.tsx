import React, { useState, useEffect } from 'react';
import { 
  UploadCloud, 
  FileText, 
  Database, 
  ShieldCheck, 
  Sparkles, 
  FileCode, 
  CheckCircle2, 
  Plus,
  Trash2
} from 'lucide-react';
import { api } from '../services/api';

interface LandingViewProps {
  onStartAnalysis: (params: {
    type: 'pdf' | 'text' | 'benchmark';
    targetFile?: File;
    sourceFiles?: File[];
    targetText?: string;
    sourceText?: string;
    documentTitle?: string;
  }) => void;
}

const LandingView: React.FC<LandingViewProps> = ({ onStartAnalysis }) => {
  const [mode, setMode] = useState<'pdf' | 'text'>('pdf');
  const [targetFile, setTargetFile] = useState<File | null>(null);
  const [sourceFiles, setSourceFiles] = useState<File[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

  // Text mode inputs
  const [targetText, setTargetText] = useState<string>('');
  const [sourceText, setSourceText] = useState<string>('');
  const [docTitle, setDocTitle] = useState<string>('');

  useEffect(() => {
    api.checkHealth().then(setIsBackendHealthy).catch(() => setIsBackendHealthy(false));
  }, []);

  const handleTargetFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        setTargetFile(file);
      }
    }
  };

  const handleSourceFilesAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files).filter(f => f.name.endsWith('.pdf'));
      setSourceFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeSourceFile = (index: number) => {
    setSourceFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleStartPDFAnalysis = () => {
    if (!targetFile) return;
    onStartAnalysis({
      type: 'pdf',
      targetFile,
      sourceFiles,
    });
  };

  const handleStartTextAnalysis = () => {
    if (!targetText.trim()) return;
    onStartAnalysis({
      type: 'text',
      targetText,
      sourceText,
      documentTitle: docTitle || 'Pasted Manuscript',
    });
  };

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col items-center justify-center p-6 py-12 max-w-5xl mx-auto space-y-12">
      {/* Backend Status Notification */}
      <div className="w-full flex items-center justify-between bg-slate-50 border border-slate-200 rounded-md px-4 py-2 text-xs text-slate-600">
        <div className="flex items-center space-x-2">
          <span className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-green-500' : isBackendHealthy === false ? 'bg-red-500' : 'bg-amber-500 animate-pulse'}`} />
          <span className="font-medium">
            Backend Engine: {isBackendHealthy ? 'Online (FastAPI + HuggingFace)' : isBackendHealthy === false ? 'Offline (Run server)' : 'Checking status...'}
          </span>
        </div>
        <button
          onClick={() => onStartAnalysis({ type: 'benchmark' })}
          className="inline-flex items-center space-x-1.5 text-slate-900 font-semibold hover:text-slate-700 bg-white border border-slate-300 hover:border-slate-400 px-3 py-1 rounded shadow-xs transition-colors cursor-pointer"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-600" />
          <span>Load Standard Academic Benchmark</span>
        </button>
      </div>

      {/* Hero Section */}
      <div className="text-center space-y-4 max-w-3xl">
        <div className="inline-flex items-center space-x-2 bg-slate-100 border border-slate-200 text-slate-700 px-3 py-1 rounded-full text-xs font-medium">
          <ShieldCheck className="w-3.5 h-3.5 text-slate-900" />
          <span>Automated Citation Verification & Evidence Alignment</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-slate-900 leading-tight">
          Verify the Substance, Not Just the Source.
        </h1>
        <p className="text-base md:text-lg text-slate-600 font-serif leading-relaxed">
          Extract in-text citation claims, retrieve cited source literature, and compute natural language inference & numerical alignment to safeguard scientific integrity.
        </p>
      </div>

      {/* Mode Switcher Tabs */}
      <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
        <button
          onClick={() => setMode('pdf')}
          className={`flex items-center space-x-2 px-5 py-2 rounded-md text-sm font-medium transition-all ${
            mode === 'pdf' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Academic PDF Ingestion</span>
        </button>
        <button
          onClick={() => setMode('text')}
          className={`flex items-center space-x-2 px-5 py-2 rounded-md text-sm font-medium transition-all ${
            mode === 'text' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <FileCode className="w-4 h-4" />
          <span>Direct Text / LaTeX Input</span>
        </button>
      </div>

      {/* Mode 1: PDF Upload Container */}
      {mode === 'pdf' && (
        <div className="w-full max-w-3xl space-y-6">
          {/* Main Manuscript Upload */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleTargetFileDrop}
            className={`border-2 border-dashed rounded-lg p-10 flex flex-col items-center justify-center transition-all bg-white ${
              targetFile ? 'border-green-500 bg-green-50/20' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50/50'
            }`}
          >
            <input
              type="file"
              id="target-pdf-input"
              accept=".pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setTargetFile(e.target.files[0])}
            />

            {targetFile ? (
              <div className="flex flex-col items-center space-y-3">
                <div className="w-12 h-12 bg-green-100 text-green-700 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div className="text-center">
                  <h3 className="font-semibold text-slate-900 text-base">{targetFile.name}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">{(targetFile.size / 1024 / 1024).toFixed(2)} MB • Ready for analysis</p>
                </div>
                <label
                  htmlFor="target-pdf-input"
                  className="text-xs text-slate-600 hover:text-slate-900 underline cursor-pointer pt-1"
                >
                  Change file
                </label>
              </div>
            ) : (
              <label htmlFor="target-pdf-input" className="flex flex-col items-center cursor-pointer text-center">
                <div className="bg-slate-100 p-4 rounded-full mb-4 text-slate-600">
                  <UploadCloud className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-medium text-slate-900 mb-1">Upload Manuscript PDF</h3>
                <p className="text-slate-500 text-sm mb-4">Drag and drop your academic paper here, or click to browse.</p>
                <span className="bg-slate-900 text-white px-5 py-2 rounded text-sm font-medium hover:bg-slate-800 transition-colors">
                  Select Document
                </span>
              </label>
            )}
          </div>

          {/* Supplementary Cited Papers (Optional) */}
          <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-slate-900">Supplementary Reference PDFs (Optional)</h4>
                <p className="text-xs text-slate-500">Attach cited source papers to verify claims against full external texts.</p>
              </div>
              <label
                htmlFor="source-pdfs-input"
                className="inline-flex items-center space-x-1.5 text-xs font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 px-3 py-1.5 rounded cursor-pointer transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Source Paper</span>
              </label>
              <input
                type="file"
                id="source-pdfs-input"
                accept=".pdf"
                multiple
                className="hidden"
                onChange={handleSourceFilesAdd}
              />
            </div>

            {sourceFiles.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-100">
                {sourceFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-slate-50 px-3 py-2 rounded border border-slate-200 text-xs">
                    <span className="truncate font-medium text-slate-800">{file.name}</span>
                    <button
                      onClick={() => removeSourceFile(idx)}
                      className="text-slate-400 hover:text-red-600 p-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Submit Action */}
          <div className="flex justify-end pt-2">
            <button
              onClick={handleStartPDFAnalysis}
              disabled={!targetFile}
              className={`px-8 py-3 rounded-md text-sm font-medium transition-all ${
                targetFile
                  ? 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm cursor-pointer'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              Verify Citations & Evidence
            </button>
          </div>
        </div>
      )}

      {/* Mode 2: Direct Text Input */}
      {mode === 'text' && (
        <div className="w-full max-w-3xl space-y-6">
          <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                Document Title
              </label>
              <input
                type="text"
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="e.g. Attention Mechanism Analysis (Draft v2)"
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                Manuscript Body / Claims (with [1] or (Author, Year) markers) *
              </label>
              <textarea
                rows={6}
                value={targetText}
                onChange={(e) => setTargetText(e.target.value)}
                placeholder="Paste paragraphs containing citation-backed statements, e.g. Specifically, training time was reduced by 40% when utilizing sparse attention [12]..."
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:outline-none focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                Referenced Source Document / Evidence Passages (Optional)
              </label>
              <textarea
                rows={4}
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Paste the cited external study passage or bibliography text for cross-referencing..."
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:outline-none focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={handleStartTextAnalysis}
                disabled={!targetText.trim()}
                className={`px-8 py-3 rounded-md text-sm font-medium transition-all ${
                  targetText.trim()
                    ? 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm cursor-pointer'
                    : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                }`}
              >
                Execute Analysis
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3-Step Pipeline Visual Overview */}
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-8 pt-6 border-t border-slate-200">
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="w-10 h-10 bg-white border border-slate-200 rounded shadow-xs flex items-center justify-center text-slate-700 font-medium">
            1
          </div>
          <FileText className="w-5 h-5 text-slate-400" />
          <h4 className="font-semibold text-slate-900 text-sm">Document Parsing & Ingestion</h4>
          <p className="text-xs text-slate-500 leading-relaxed">
            Extracts academic paragraphs, section hierarchy, and regex-isolated citation markers.
          </p>
        </div>

        <div className="flex flex-col items-center text-center space-y-3">
          <div className="w-10 h-10 bg-white border border-slate-200 rounded shadow-xs flex items-center justify-center text-slate-700 font-medium">
            2
          </div>
          <Database className="w-5 h-5 text-slate-400" />
          <h4 className="font-semibold text-slate-900 text-sm">Cross-Encoder Retrieval</h4>
          <p className="text-xs text-slate-500 leading-relaxed">
            BM25 candidate screening followed by MS-MARCO neural re-ranking for exact passage matching.
          </p>
        </div>

        <div className="flex flex-col items-center text-center space-y-3">
          <div className="w-10 h-10 bg-white border border-slate-200 rounded shadow-xs flex items-center justify-center text-slate-700 font-medium">
            3
          </div>
          <ShieldCheck className="w-5 h-5 text-slate-400" />
          <h4 className="font-semibold text-slate-900 text-sm">NLI & Numerical Alignment</h4>
          <p className="text-xs text-slate-500 leading-relaxed">
            Evaluates textual entailment/contradiction alongside exact statistical entity consistency.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LandingView;
