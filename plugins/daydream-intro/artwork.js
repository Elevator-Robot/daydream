// Upright block lettering keeps the word readable; color supplies the neon look.
export const WORDMARK = [
  "██████╗  █████╗ ██╗   ██╗██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗",
  "██╔══██╗██╔══██╗╚██╗ ██╔╝██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║",
  "██║  ██║███████║ ╚████╔╝ ██║  ██║██████╔╝█████╗  ███████║██╔████╔██║",
  "██║  ██║██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║",
  "██████╔╝██║  ██║   ██║   ██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║",
  "╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
].join("\n");

export const LOGO = WORDMARK;

export function artwork(width, height) {
  if (width >= 74 && height >= 8) return LOGO;
  if (width >= 32) return "D A Y D R E A M";
  return "DAYDREAM";
}

export function canShowIntro(session, route) {
  return Boolean(
    session && !session.parentID && session.agent === "daydream" &&
    route?.type === "session" && route.sessionID === session.id,
  );
}

export function hasIntroRequest(sessionID, request, consumed) {
  return Boolean(request && request.sessionID === sessionID && request !== consumed);
}
