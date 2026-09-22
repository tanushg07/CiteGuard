export type Status = 'Supported' | 'Contradicted' | 'Unrelated' | 'Numerical Mismatch';

export interface RetrievedEvidenceItem {
  claim_id: string;
  source_document: string;
  evidence_text: string;
  relevance_score: number;
  source_citation?: string;
}

export interface NumericalComparison {
  has_numerical_data: boolean;
  claim_entities: string[];
  evidence_entities: string[];
  is_match: boolean | null;
  details: string | null;
}

export interface Claim {
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
