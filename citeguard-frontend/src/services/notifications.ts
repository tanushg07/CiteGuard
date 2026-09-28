export function notify(message: string, kind: 'success' | 'error' = 'success') {
  window.dispatchEvent(new CustomEvent('citeguard:toast', { detail: { message, kind } }));
}
