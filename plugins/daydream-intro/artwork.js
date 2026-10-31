// Original Daydream wordmark, with terminal-style outlined/shadowed lettering.
export const LOGO = [
  "██████╗  █████╗ ██╗   ██╗██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗",
  "██╔══██╗██╔══██╗╚██╗ ██╔╝██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║",
  "██║  ██║███████║ ╚████╔╝ ██║  ██║██████╔╝█████╗  ███████║██╔████╔██║",
  "██║  ██║██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║",
  "██████╔╝██║  ██║   ██║   ██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║",
  "╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
].join("\n");

export function artwork(width, height) {
  return width >= 70 && height >= 12 ? LOGO : "DAYDREAM";
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
