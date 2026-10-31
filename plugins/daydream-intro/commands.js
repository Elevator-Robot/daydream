import { canShowIntro } from "./artwork.js";

// The home prompt owns a non-base input mode. Commands must be global to be
// reachable from its palette, before a message/session has been submitted.
export function commandLayer(context, { opening, openDaydream, setReplay, setDismissal }) {
  return {
    mode: "global",
    commands: [
      {
        id: "daydream.open",
        title: "Open Daydream",
        description: "Open an empty Daydream session and play its intro without sending a message",
        group: "Daydream",
        palette: true,
        slash: { name: "daydream" },
        enabled: () => !opening(),
        run: async () => { await openDaydream(); },
      },
      {
        id: "daydream.intro.replay",
        title: "Replay Daydream intro",
        group: "Daydream",
        palette: true,
        slash: { name: "daydream-intro" },
        enabled: () => {
          const route = context.ui.router.current();
          return route.type === "session" && canShowIntro(context.data.session.get(route.sessionID), route);
        },
        run: () => {
          const route = context.ui.router.current();
          if (route.type === "session") setReplay({ sessionID: route.sessionID });
        },
      },
      {
        id: "daydream.intro.hide",
        title: "Hide Daydream intro",
        group: "Daydream",
        palette: true,
        slash: { name: "daydream-hide-intro" },
        run: () => setDismissal((value) => value + 1),
      },
    ],
  };
}
