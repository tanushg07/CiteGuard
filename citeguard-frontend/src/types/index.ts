export type Status = 'Supported' | 'Contradicted' | 'Unrelated' | 'Numerical Mismatch';

export interface RetrievedEvidenceItem {
  evidence_id?: string; source_id?: string; source_url?: string; page_number?: number;
  section?: string; paragraph?: number; retrieval_score?: number; rerank_score?: number | null;
  claim_id: string;
  source_document: string;
  evidence_text: string;
  relevance_score: number;
  source_citation?: string;
}

export interface NumericalComparison {
  status?: string; calculation?: string | null;
  has_numerical_data: boolean;
  claim_entities: string[];
  evidence_entities: string[];
  is_match: boolean | null;
  details: string | null;
}

export interface Claim {
  final_verdict?: string; claim_group_id?: string; citation_id?: string; section?: string;
  association_confidence?: string; decision_reason?: string;
  source_identification?: {status: string; reason: string; url?: string; [key: string]: unknown};
  nli?: {status: string; label?: string; score?: number; components?: unknown[]};
  reasoning?: string;
  reasoning_provider?: 'template' | 'groq';
  reference_metadata?: {
    raw_reference: string;
    provider: string;
    status: string;
    title?: string | null;
    doi?: string | null;
    abstract?: string | null;
    venue?: string | null;
    authors: string[];
    year?: number | null;
  } | null;
  id: string;
  text: string;
  context: string;
  citation_marker: string;
  source_document: string;
  evidence: string;
  evidence_list?: RetrievedEvidenceItem[];
  status: Status;
  confidence: number;
  numerical_check: string | null;
  numerical_comparison?: NumericalComparison;
  page_number: number;
}

export interface DocumentSummary {
  total_pages?: number; total_references?: number; unique_claims?: number;
  verdict_counts?: Record<string, number>;
  document_name: string;
  total_claims: number;
  supported_count: number;
  contradicted_count: number;
  unrelated_count: number;
  numerical_mismatch_count: number;
  supported_percentage: number;
  average_confidence: number;
  processing_time_seconds: number;
}

export interface AnalysisResponse {
  document?: { metadata?: {title?: string; authors?: string[]; abstract?: string};
    sentences?: unknown[]; sections?: {title: string; page: number}[] };
  warnings?: string[];
  engines?: Record<string, string>;
  job_id: string;
  summary: DocumentSummary;
  claims: Claim[];
  status: string;
}

export interface PipelineStep {
  id: number;
  name: string;
  status: 'pending' | 'loading' | 'complete' | 'error';
  detail?: string;
  claims_found?: number;
}
