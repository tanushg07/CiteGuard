import { useState } from 'react';
import LandingView from './components/LandingView';
import ProcessingView from './components/ProcessingView';
import DashboardView from './components/DashboardView';

type ViewState = 'landing' | 'processing' | 'dashboard';

function App() {
  const [view, setView] = useState<ViewState>('landing');

  return (
    <div className="font-sans text-slate-900 bg-[#F9FAFB] min-h-screen">
      {/* Top Navigation Bar */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-50">
        <div 
          className="flex items-center space-x-2 cursor-pointer"
          onClick={() => setView('landing')}
        >
          <div className="w-8 h-8 bg-slate-900 rounded flex items-center justify-center">
            <span className="text-white font-serif font-bold text-lg leading-none">C</span>
          </div>
          <span className="font-semibold text-xl tracking-tight">CiteGuard</span>
        </div>
        <div className="text-sm font-medium text-slate-500">
          Academic Verification Platform
        </div>
      </nav>

      {/* Main Content Area */}
      <main>
        {view === 'landing' && (
          <LandingView onUpload={() => setView('processing')} />
        )}
        
        {view === 'processing' && (
          <ProcessingView onComplete={() => setView('dashboard')} />
        )}
        
        {view === 'dashboard' && (
          <DashboardView />
        )}
      </main>
    </div>
  );
}

export default App;
