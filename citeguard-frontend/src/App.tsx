import { useState } from 'react';
import LandingView from './components/LandingView';
import ProcessingView from './components/ProcessingView';
import DashboardView from './components/DashboardView';
import MetricsPage from './pages/MetricsPage';
import type { AnalysisResponse } from './types';
import { Shield, Activity } from 'lucide-react';

type ViewState = 'landing' | 'processing' | 'dashboard' | 'metrics';

interface AnalysisParams {
  type: 'pdf' | 'text' | 'benchmark';
  targetFile?: File;
  sourceFiles?: File[];
  targetText?: string;
  sourceText?: string;
  documentTitle?: string;
}

function App() {
  const [view, setView] = useState<ViewState>('landing');
  const [params, setParams] = useState<AnalysisParams | null>(null);
  const [results, setResults] = useState<AnalysisResponse | null>(null);

  const handleStartAnalysis = (analysisParams: AnalysisParams) => {
    setParams(analysisParams);
    setView('processing');
  };

  const handleProcessingComplete = (data: AnalysisResponse) => {
    setResults(data);
    setView('dashboard');
  };

  const handleReset = () => {
    setParams(null);
    setResults(null);
    setView('landing');
  };

  return (
    <div className="font-sans text-slate-900 bg-[#F9FAFB] min-h-screen flex flex-col">
      {/* Global Academic Navigation Bar */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
        <div 
          className="flex items-center space-x-2.5 cursor-pointer"
          onClick={handleReset}
        >
          <div className="w-8 h-8 bg-slate-900 rounded flex items-center justify-center text-white">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <span className="font-semibold text-lg tracking-tight text-slate-900">CiteGuard</span>
            <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded ml-2 border border-slate-200">
              v2.0
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <button
            onClick={() => setView('metrics')}
            className={`text-xs font-medium flex items-center space-x-1 transition-colors cursor-pointer ${view === 'metrics' ? 'text-slate-900 bg-slate-100 px-2.5 py-1.5 rounded' : 'text-slate-500 hover:text-slate-900'}`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Metrics & Evaluation</span>
          </button>
          
          <div className="text-xs font-medium text-slate-300 hidden sm:block">|</div>
          
          <div className="text-xs font-medium text-slate-500 hidden sm:block">
            Evidence-Aligned Citation Integrity
          </div>
          {view === 'dashboard' && (
            <button
              onClick={handleReset}
              className="text-xs font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 px-3 py-1.5 rounded transition-colors cursor-pointer ml-2"
            >
              Upload New Document
            </button>
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1">
        {view === 'landing' && (
          <LandingView onStartAnalysis={handleStartAnalysis} />
        )}

        {view === 'processing' && params && (
          <ProcessingView
            params={params}
            onComplete={handleProcessingComplete}
            onError={(err) => console.error('Analysis error:', err)}
            onCancel={handleReset}
          />
        )}

        {view === 'dashboard' && results && (
          <DashboardView data={results} onReset={handleReset} />
        )}

        {view === 'metrics' && (
          <MetricsPage />
        )}
      </main>
    </div>
  );
}

export default App;
