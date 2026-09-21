import type { AnalysisResponse } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

export const api = {
  /**
   * Upload target manuscript PDF and optional source reference PDFs for verification.
   */
  async verifyPDF(targetFile: File, sourceFiles: File[] = []): Promise<{job_id: string}> {
    const formData = new FormData();
    formData.append('target_file', targetFile);

    for (const file of sourceFiles) {
      formData.append('source_files', file);
    }

    const response = await fetch(`${API_BASE_URL}/verify`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Upload verification failed' }));
      throw new Error(errorData.detail || `Server error: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Direct text analysis for pasting manuscript snippet & referenced source text.
   */
  async analyzeText(
    targetText: string,
    documentTitle: string = 'Pasted Manuscript',
    sourceText?: string,
    sourceTitle?: string
  ): Promise<{job_id: string}> {
    const response = await fetch(`${API_BASE_URL}/analyze-text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        document_title: documentTitle,
        target_text: targetText,
        source_title: sourceTitle,
        source_text: sourceText,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Text analysis failed' }));
      throw new Error(errorData.detail || `Server error: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Runs the official 5-claim academic benchmark dataset through the full pipeline.
   */
  async runBenchmark(): Promise<AnalysisResponse> {
    const response = await fetch(`${API_BASE_URL}/benchmark`, {
      method: 'GET',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Benchmark execution failed' }));
      throw new Error(errorData.detail || `Server error: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Retrieves previous verification results by job ID.
   */
  async getResults(jobId: string): Promise<AnalysisResponse> {
    const response = await fetch(`${API_BASE_URL}/results/${jobId}`);
    if (!response.ok) {
      throw new Error(`Job ${jobId} not found`);
    }
    return response.json();
  },

  /**
   * Downloads verified claims report as JSON or CSV.
   */
  exportResults(jobId: string, format: 'json' | 'csv' = 'json'): void {
    const url = `${API_BASE_URL}/export/${jobId}?format=${format}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `citeguard_report_${jobId}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  },

  /**
   * Checks backend health status.
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch('http://127.0.0.1:8000/health');
      return response.ok;
    } catch {
      return false;
    }
  },

  /**
   * Fetches the quantitative evaluation metrics.
   */
  async getMetrics(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/metrics`);
    if (!response.ok) {
      throw new Error(`Failed to fetch metrics`);
    }
    return response.json();
  },
};
