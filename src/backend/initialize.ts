/** Restore saved state before any listener can persist initial defaults. */
export function initializeAfterSettings<T>(
  load: () => Promise<T>,
  restore: (settings: T) => void,
  listen: () => () => void,
  onError: (error: unknown) => void,
): () => void {
  let disposed = false;
  let unsubscribe: (() => void) | undefined;
  load().then((settings) => {
    if (disposed) return;
    restore(settings);
    unsubscribe = listen();
  }).catch((error: unknown) => {
    if (!disposed) onError(error);
  });
  return () => {
    disposed = true;
    unsubscribe?.();
  };
}
