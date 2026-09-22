import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ShieldAlert, BarChart3, TrendingUp, CheckCircle, Clock, Zap } from 'lucide-react';

const MetricCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode; color: string }> = ({ title, value, icon, color }) => (
  <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex items-center space-x-4">
    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${color}`}>
      {icon}
    </div>
    <div>
      <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider">{title}</h3>
      <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
    </div>
  </div>
);

const MetricsPage: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const data = await api.getMetrics();
        setMetrics(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load metrics');
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="text-slate-500 animate-pulse text-sm font-medium">Running Evaluation Pipeline & Fetching Metrics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[calc(100vh-64px)] p-6">
        <ShieldAlert className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-900">Evaluation Failed</h2>
        <p className="text-sm text-slate-500 mt-2">{error}</p>
      </div>
    );
  }

  if (!metrics) return null;

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-10 min-h-[calc(100vh-64px)]">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
          <BarChart3 className="w-6 h-6 text-slate-700" />
          <span>System Evaluation & Metrics</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">Controlled synthetic fixtures, not independently reviewed research results. Precision, recall and F1 use macro averaging.</p>
      </div>

      {/* Extraction Metrics */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 border-b border-slate-200 pb-2">Extraction Integrity</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard title="Citation Recall" value={`${(metrics.citation_recall * 100).toFixed(1)}%`} icon={<CheckCircle className="w-5 h-5 text-indigo-700" />} color="bg-indigo-50 border border-indigo-100" />
          <MetricCard title="Claim Precision" value={`${(metrics.claim_precision * 100).toFixed(1)}%`} icon={<TrendingUp className="w-5 h-5 text-indigo-700" />} color="bg-indigo-50 border border-indigo-100" />
        </div>
      </section>

      {/* Retrieval Metrics */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 border-b border-slate-200 pb-2">Evidence Retrieval Quality</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard title="Recall@1" value={`${(metrics.recall_at_1 * 100).toFixed(1)}%`} icon={<Zap className="w-5 h-5 text-sky-700" />} color="bg-sky-50 border border-sky-100" />
          <MetricCard title="Recall@3" value={`${(metrics.recall_at_3 * 100).toFixed(1)}%`} icon={<TrendingUp className="w-5 h-5 text-sky-700" />} color="bg-sky-50 border border-sky-100" />
          <MetricCard title="Precision@3" value={`${(metrics.precision_at_3 * 100).toFixed(1)}%`} icon={<CheckCircle className="w-5 h-5 text-sky-700" />} color="bg-sky-50 border border-sky-100" />
          <MetricCard title="MRR Score" value={metrics.mrr_score.toFixed(3)} icon={<BarChart3 className="w-5 h-5 text-sky-700" />} color="bg-sky-50 border border-sky-100" />
        </div>
      </section>

      {/* Verification Metrics */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 border-b border-slate-200 pb-2">NLI & Alignment Accuracy</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard title="Accuracy" value={`${(metrics.accuracy * 100).toFixed(1)}%`} icon={<CheckCircle className="w-5 h-5 text-emerald-700" />} color="bg-emerald-50 border border-emerald-100" />
          <MetricCard title="Precision" value={`${(metrics.precision * 100).toFixed(1)}%`} icon={<TrendingUp className="w-5 h-5 text-emerald-700" />} color="bg-emerald-50 border border-emerald-100" />
          <MetricCard title="Recall" value={`${(metrics.recall * 100).toFixed(1)}%`} icon={<TrendingUp className="w-5 h-5 text-emerald-700" />} color="bg-emerald-50 border border-emerald-100" />
          <MetricCard title="F1-Score" value={(metrics.f1_score).toFixed(3)} icon={<BarChart3 className="w-5 h-5 text-emerald-700" />} color="bg-emerald-50 border border-emerald-100" />
        </div>
      </section>

      {/* System Metrics */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 border-b border-slate-200 pb-2">System Performance</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <MetricCard title="Avg Processing Time" value={`${metrics.avg_processing_time.toFixed(2)}s`} icon={<Clock className="w-5 h-5 text-amber-700" />} color="bg-amber-50 border border-amber-100" />
          <MetricCard title="Avg Latency / Claim" value={`${metrics.avg_latency.toFixed(2)}s`} icon={<Zap className="w-5 h-5 text-amber-700" />} color="bg-amber-50 border border-amber-100" />
          <MetricCard title="Failure Rate" value={`${(metrics.failure_rate * 100).toFixed(1)}%`} icon={<ShieldAlert className="w-5 h-5 text-red-700" />} color="bg-red-50 border border-red-100" />
        </div>
      </section>
      
      {/* Optimization Scripts Notice */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-6 mt-12 text-sm text-slate-600">
        <h3 className="font-semibold text-slate-900 mb-2">Parameter Optimization</h3>
        <p>Run <code className="bg-slate-200 px-1.5 py-0.5 rounded text-xs font-mono">python app/evaluation/optimize_retrieval.py</code> and <code className="bg-slate-200 px-1.5 py-0.5 rounded text-xs font-mono">python app/evaluation/optimize_nli.py</code> in the backend environment to view grid search optimization matrices.</p>
      </div>
    </div>
  );
};

export default MetricsPage;
