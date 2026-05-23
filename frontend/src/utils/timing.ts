/**
 * Utility per timing preciso nei test cognitivi.
 * Uso performance.now() che ha precisione al millisecondo,
 * molto più affidabile di Date.now().
 */

export class PreciseTimer {
  private startTime: number = 0;

  start(): void {
    this.startTime = performance.now();
  }

  elapsed(): number {
    return performance.now() - this.startTime;
  }

  reset(): void {
    this.startTime = performance.now();
  }
}

/**
 * Sleep ad alta precisione. La setTimeout standard è inaffidabile
 * per delay < 20ms. Per questi casi usiamo requestAnimationFrame loop.
 */
export function preciseSleep(ms: number): Promise<void> {
  if (ms < 20) {
    return new Promise(resolve => {
      const start = performance.now();
      function check() {
        if (performance.now() - start >= ms) resolve();
        else requestAnimationFrame(check);
      }
      requestAnimationFrame(check);
    });
  }
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Attendi un evento (click o keypress) con timeout.
 * Ritorna il RT in ms o null se timeout.
 */
export function waitForResponse(
  timeoutMs: number,
  eventType: "click" | "keypress" = "keypress",
  validKey?: string
): Promise<number | null> {
  return new Promise(resolve => {
    const startTime = performance.now();
    let resolved = false;

    const cleanup = () => {
      document.removeEventListener(eventType, handler);
      clearTimeout(timer);
    };

    const handler = (ev: Event) => {
      if (validKey && eventType === "keypress") {
        const keyEvent = ev as KeyboardEvent;
        if (keyEvent.key !== validKey) return;
      }
      if (!resolved) {
        resolved = true;
        cleanup();
        resolve(performance.now() - startTime);
      }
    };

    document.addEventListener(eventType, handler);

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        cleanup();
        resolve(null);
      }
    }, timeoutMs);
  });
}
