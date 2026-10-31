// Only the explicit terminal launcher supplies this one-shot client-local marker.
// Merely selecting/restoring an agent never requests an intro.
export const LAUNCH_MARKER = "DAYDREAM_LAUNCH_SESSION";

export function launcherRequest(sessionID, session, route, consumed) {
  if (!sessionID || consumed.includes(sessionID) || !session || session.parentID ||
      session.agent !== "daydream" || session.id !== sessionID ||
      route.type !== "session" || route.sessionID !== sessionID) return undefined;
  return { sessionID };
}
