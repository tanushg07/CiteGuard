export default function ReportSkeleton() {
  return <div className="report-skeleton" role="status" aria-label="Preparing verification report" aria-busy="true">
    <span className="sr-only">Preparing your evidence report…</span>
    {[0, 1, 2].map(index => <div key={index} className="skeleton-card" aria-hidden="true">
      <div className="skeleton-line short" /><div className="skeleton-line" /><div className="skeleton-line" />
    </div>)}
  </div>;
}
