/** Anonymous visit sessions, independent of game creation and API request count. */
export function trackVisits() {
  let pending = false;
  const heartbeat = async () => {
    if (document.hidden || pending) return;
    pending = true;
    try {
      await fetch('/api/v1/visits', {method: 'POST', credentials: 'same-origin', signal: AbortSignal.timeout(5000)});
    } catch { /* Analytics must never block or interrupt the game. */ }
    finally {pending = false;}
  };
  void heartbeat();
  window.setInterval(() => {void heartbeat();}, 30000);
  document.addEventListener('visibilitychange', () => {if (!document.hidden) void heartbeat();});
}
