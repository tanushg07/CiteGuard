import React, { useEffect, useState, useRef } from 'react';
import { Check, Loader2, Circle, AlertTriangle, RefreshCw } from 'lucide-react';
import type { AnalysisResponse, PipelineStep } from '../types';
import { api } from '../services/api';

interface ProcessingViewProps {
  params: {
    type: 'pdf' | 'text' | 'benchmark';
    targetFile?: File;
    sourceFiles?: File[];
    targetText?: string;
    sourceText?: string;
    documentTitle?: string;
  };
  onComplete: (data: AnalysisResponse) => void;
  onError: (errorMsg: string) => void;
  onCancel: () => void;
}

const DEFAULT_STEPS: PipelineStep[] = [
  { id: 1, name: 'PDF Ingestion & Parsing', status: 'pending', detail: 'Deconstructing PDF structure and layout...' },
  { id: 2, name: 'Claim Extraction', status: 'pending', detail: 'Isolating bracketed and author-year citations...' },
  { id: 3, name: 'Source Identification', status: 'pending', detail: 'Mapping bibliography and reference corpora...' },
  { id: 4, name: 'Evidence Retrieval', status: 'pending', detail: 'Querying TF-IDF / BM25 lexical candidate index...' },
  { id: 5, name: 'Cross-Encoder Re-ranking', status: 'pending', detail: 'MS-MARCO neural semantic alignment scoring...' },
  { id: 6, name: 'NLI Verification', status: 'pending', detail: 'DistilBERT MNLI textual entailment inference...' },
  { id: 7, name: 'Numerical Verification', status: 'pending', detail: 'Cross-referencing metrics, units, and statistics...' },
];

const ProcessingView: React.FC<ProcessingViewProps> = ({ params, onComplete, onError, onCancel }) => {
  const [steps, setSteps] = useState<PipelineStep[]>(DEFAULT_STEPS);
  const [, setCurrentStepIdx] = useState<number>(0);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const hasExecutedRef = useRef(false);

  // Timer
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Step progression animation coupled with real API call
  useEffect(() => {
    if (hasExecutedRef.current) return;
    hasExecutedRef.current = true;

    let isSubscribed = true;

    const runAnalysis = async () => {
      try {
        let jobResponse: any;

        if (params.type === 'pdf' && params.targetFile) {
          jobResponse = await api.verifyPDF(params.targetFile, params.sourceFiles || []);
        } else if (params.type === 'text' && params.targetText) {
          jobResponse = await api.analyzeText(
            params.targetText,
            params.documentTitle,
            params.sourceText,
            'Referenced Source'
          );
        } else {
          // benchmark might still return AnalysisResponse or job_id, assuming AnalysisResponse for now 
          // or we can adjust benchmark to also use background tasks. Let's assume it still returns AnalysisResponse directly
          // Actually, let's just leave benchmark as is.
          const result = await api.runBenchmark();
          if (isSubscribed) onComplete(result);
          return;
        }

        if (!isSubscribed) return;
        
        const jobId = jobResponse.job_id;
        
        // Connect to WebSocket
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Assuming API_BASE_URL is usually derived from window.location or hardcoded in api.ts
        const wsUrl = `ws://127.0.0.1:8000/api/ws/${jobId}`;
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          if (!isSubscribed) {
            ws.close();
            return;
          }
          
          const msg = JSON.parse(event.data);
          
          if (msg.status === 'update') {
            const stepId = msg.data.step_id;
            const status = msg.data.status; // 'loading', 'complete', 'error'
            const detail = msg.data.detail;
            
            if (status === 'error') {
               setErrorMessage(detail || "An error occurred during pipeline execution.");
               onError(detail || "An error occurred");
               ws.close();
               return;
            }
            
            setCurrentStepIdx(stepId - 1);
            setSteps((old) =>
              old.map((s) => {
                if (s.id === stepId) {
                  return { ...s, status, detail: detail || s.detail };
                }
                if (s.id < stepId) return { ...s, status: 'complete' };
                return s;
              })
            );
          } else if (msg.status === 'completed') {
            setSteps((old) => old.map((s) => ({ ...s, status: 'complete' })));
            setTimeout(() => {
              if (isSubscribed) onComplete(msg.data);
            }, 600);
            ws.close();
          } else if (msg.status === 'error') {
            setErrorMessage(msg.message || 'Processing failed on the server.');
            onError(msg.message || 'Processing failed.');
            ws.close();
          }
        };

        ws.onerror = (e) => {
          if (!isSubscribed) return;
          setErrorMessage('WebSocket connection failed.');
          onError('WebSocket connection failed.');
        };

      } catch (err: any) {
        if (!isSubscribed) return;
        const msg = err.message || 'Verification failed to start. Please check the backend.';
        setErrorMessage(msg);
        onError(msg);
      }
    };

    runAnalysis();

    return () => {
      isSubscribed = false;
    };
  }, [params, onComplete, onError]);

  const handleRetry = () => {
    hasExecutedRef.current = false;
    setErrorMessage(null);
    setCurrentStepIdx(0);
    setSteps(DEFAULT_STEPS);
  };

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col items-center justify-center p-6 bg-[#F9FAFB]">
      <div className="bg-white border border-slate-200 shadow-sm rounded-lg p-8 w-full max-w-xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-6 border-b border-slate-200 mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Verification Pipeline</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {params.type === 'pdf' && params.targetFile
                ? `Ingesting: ${params.targetFile.name}`
                : params.type === 'text'
                ? `Analyzing: ${params.documentTitle || 'Pasted Text'}`
                : 'Evaluating Academic Benchmark Dataset'}
            </p>
          </div>
          <div className="text-right">
            <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded">
              {elapsedSeconds}s elapsed
            </span>
          </div>
        </div>

        {/* Error Notification */}
        {errorMessage ? (
          <div className="space-y-4 py-4">
            <div className="p-4 bg-red-50 border border-red-200 rounded-md flex items-start space-x-3 text-red-800 text-sm">
              <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold">Pipeline Error</h4>
                <p className="text-xs text-red-700 mt-1">{errorMessage}</p>
              </div>
            </div>
            <div className="flex space-x-3 pt-2">
              <button
                onClick={handleRetry}
                className="flex-1 inline-flex items-center justify-center space-x-2 bg-slate-900 text-white py-2 px-4 rounded text-sm font-medium hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Retry Pipeline</span>
              </button>
              <button
                onClick={onCancel}
                className="bg-white border border-slate-300 text-slate-700 py-2 px-4 rounded text-sm font-medium hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          /* Step progression list */
          <div className="space-y-3.5">
            {steps.map((step) => {
              const isDone = step.status === 'complete';
              const isLoading = step.status === 'loading';
              const isPending = step.status === 'pending';

              return (
                <div
                  key={step.id}
                  className={`flex items-start space-x-3 p-3 rounded-md border transition-all ${
                    isLoading
                      ? 'border-slate-800 bg-slate-50 ring-1 ring-slate-800/10'
                      : isDone
                      ? 'border-slate-200 bg-white'
                      : 'border-transparent opacity-50'
                  }`}
                >
                  <div className="pt-0.5 shrink-0">
                    {isDone && (
                      <div className="w-5 h-5 rounded-full bg-green-100 border border-green-300 flex items-center justify-center">
                        <Check className="w-3.5 h-3.5 text-green-700" />
                      </div>
                    )}
                    {isLoading && (
                      <div className="w-5 h-5 rounded-full bg-slate-100 border border-slate-400 flex items-center justify-center">
                        <Loader2 className="w-3.5 h-3.5 text-slate-800 animate-spin" />
                      </div>
                    )}
                    {isPending && (
                      <div className="w-5 h-5 rounded-full border border-slate-300 flex items-center justify-center">
                        <Circle className="w-2 h-2 text-slate-300 fill-slate-300" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4
                        className={`text-sm font-medium ${
                          isLoading ? 'text-slate-900 font-semibold' : isDone ? 'text-slate-800' : 'text-slate-500'
                        }`}
                      >
                        {step.id}. {step.name}
                      </h4>
                      <span
                        className={`text-xs font-mono font-medium ${
                          isDone ? 'text-green-600' : isLoading ? 'text-slate-600 animate-pulse' : 'text-slate-400'
                        }`}
                      >
                        {isDone ? 'COMPLETED' : isLoading ? 'PROCESSING' : 'WAITING'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 leading-normal">{step.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProcessingView;
