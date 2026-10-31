import { Plugin } from "@opencode/plugin/tui";
import { jsx } from "@opentui/solid/jsx-runtime";
import { useTerminalDimensions } from "@opentui/solid";
import { createEffect, createMemo, createSignal, on, onCleanup, Show, untrack } from "solid-js";
import { createPlayback, frame, shouldStart } from "./animation.js";

export default Plugin.define({
  id: "daydream.intro",
  setup(context) {
    if (context.options.enabled === false) return;
    const reducedMotion = context.options.reducedMotion === true;
    const [memory, updateMemory] = context.storage.memory("intro", { initial: { seen: [] } });
    const [replay, setReplay] = createSignal(undefined);
    const [dismissal, setDismissal] = createSignal(0);
    let consumedReplay;

    context.keymap.layer(() => ({
      commands: [
        {
          id: "daydream.intro.replay",
          title: "Replay Daydream intro",
          group: "Daydream",
          palette: true,
          slash: { name: "daydream-intro" },
          enabled: () => {
            const route = context.ui.router.current();
            return route.type === "session" && shouldStart(
              context.data.session.get(route.sessionID), route, [],
            );
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
    }));

    function Intro(props) {
      const dimensions = useTerminalDimensions();
      const [visible, setVisible] = createSignal(false);
      const [progress, setProgress] = createSignal(0);
      const playback = createPlayback({
        onFrame: (value) => { setProgress(value); setVisible(true); },
        onHide: () => setVisible(false),
      });
      const active = createMemo(() => shouldStart(
        context.data.session.get(props.sessionID), context.ui.router.current(), [],
      ));
      createEffect(on([active, replay], ([selected, request]) => {
        playback.stop();
        if (!selected) return;
        const repeated = request?.sessionID === props.sessionID && request !== consumedReplay;
        if (repeated) consumedReplay = request;
        untrack(() => {
          if (!repeated && memory.seen.includes(props.sessionID)) return;
          updateMemory((draft) => {
            if (!draft.seen.includes(props.sessionID)) draft.seen.push(props.sessionID);
          });
          playback.start({ reducedMotion });
        });
      }));
      createEffect(on(dismissal, () => playback.stop(), { defer: true }));
      onCleanup(playback.stop);
      return jsx(Show, {
        get when() { return visible() && dimensions().width >= 16 && dimensions().height >= 8; },
        get children() {
          return jsx("box", {
            width: "100%",
            flexDirection: "column",
            alignItems: "center",
            paddingTop: 1,
            paddingBottom: 1,
            children: jsx("text", {
              fg: context.themeMode === "light" ? "#6941A5" : "#B9A1F5",
              wrapMode: "none",
              get children() {
                // Allow for sidebar/composer padding; compact before art can wrap.
                const art = frame(progress(), Math.max(0, dimensions().width - 36), dimensions().height - 6);
                return art.split(/([┃╋])/u).map((part) => jsx("span", {
                  fg: /^[┃╋]$/u.test(part)
                    ? (context.themeMode === "light" ? "#007F8B" : "#67E8F9")
                    : (context.themeMode === "light" ? "#6941A5" : "#B9A1F5"),
                  children: part,
                }));
              },
            }),
          });
        },
      });
    }

    // Non-modal: no dialog replacement, cursor control, input grab, or chat writes.
    return context.ui.slot({
      append: "session.composer.top",
      render: (props) => jsx(Intro, props),
    });
  },
});
