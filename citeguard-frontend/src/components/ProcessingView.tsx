import React, { useEffect, useState, useRef } from 'react';
import { Check, Loader2, Circle, AlertTriangle, RefreshCw } from 'lucide-react';
import type { AnalysisResponse, PipelineStep } from '../types';
import { api, API_BASE_URL } from '../services/api';

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
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const callbacks = useRef({ onComplete, onError });
  callbacks.current = { onComplete, onError };
  const requestRef = useRef<{attempt: number; promise: Promise<any>} | null>(null);

  // Timer
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const fail = (message: string) => {
      if (!active) return;
      setErrorMessage(message);
      callbacks.current.onError(message);
    };
    // Reuse the submission during React StrictMode's effect replay.
    if (!requestRef.current || requestRef.current.attempt !== attempt) {
      const promise = params.type === 'pdf' && params.targetFile
        ? api.verifyPDF(params.targetFile, params.sourceFiles || [])
        : params.type === 'text' && params.targetText
        ? api.analyzeText(params.targetText, params.documentTitle, params.sourceText, 'Referenced Source')
        : api.runBenchmark();
      requestRef.current = { attempt, promise };
    }
    const started = Date.now();
    const poll = async (jobId: string) => {
      try {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
        if (!response.ok) throw new Error('Unable to read analysis status.');
        const message = await response.json();
        if (!active) return;
        if (message.status === 'completed') {
          callbacks.current.onComplete(message.data);
          return;
        }
        if (message.status === 'error') throw new Error(message.message);
        if (message.status === 'update') {
          const update = message.data;
          setSteps(old => old.map(step => step.id === update.step_id
            ? { ...step, status: update.status, detail: update.detail }
            : step.id < update.step_id ? { ...step, status: 'complete' } : step));
        }
        if (Date.now() - started > 15 * 60 * 1000) throw new Error('Analysis timed out. Please retry.');
        timer = setTimeout(() => { void poll(jobId); }, 750);
      } catch (error) {
        fail(error instanceof Error ? error.message : 'Analysis failed.');
      }
    };
    requestRef.current.promise.then(result => {
      if (!active) return;
      if (result.status === 'completed') callbacks.current.onComplete(result);
      else void poll(result.job_id);
    }).catch(error => fail(error.message || 'Could not connect to backend.'));
    return () => { active = false; clearTimeout(timer); };
  }, [params, attempt]);

  const handleRetry = () => {
    setErrorMessage(null);
    setElapsedSeconds(0);
    setSteps(DEFAULT_STEPS);
    setAttempt(value => value + 1);
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
