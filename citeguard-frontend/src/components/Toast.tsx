import { useEffect, useState } from 'react';

export default function Toast() {
  const [toast, setToast] = useState<{ message: string; kind: string } | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const receive = (event: Event) => {
      setToast((event as CustomEvent).detail);
      clearTimeout(timer);
      timer = setTimeout(() => setToast(null), 7000);
    };
    window.addEventListener('citeguard:toast', receive);
    return () => { clearTimeout(timer); window.removeEventListener('citeguard:toast', receive); };
  }, []);
  return <div className="toast-region" aria-live="polite" aria-atomic="true">
    {toast && <div className={`toast ${toast.kind}`} role={toast.kind === 'error' ? 'alert' : 'status'}>
      <span>{toast.message}</span><button aria-label="Dismiss notification" onClick={() => setToast(null)}>×</button>
    </div>}
  </div>;
}
