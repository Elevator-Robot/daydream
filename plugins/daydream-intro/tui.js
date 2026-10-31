import { Plugin } from "@opencode/plugin/tui";
import { jsx } from "@opentui/solid/jsx-runtime";
import { useTerminalDimensions } from "@opentui/solid";
import { createEffect, createMemo, createSignal, on, onCleanup, Show } from "solid-js";
import { artwork, canShowIntro, hasIntroRequest } from "./artwork.js";
import { createPlayback } from "./ttfx.js";
import { createOpenDaydream } from "./open.js";
import { commandLayer } from "./commands.js";

export default Plugin.define({
  id: "daydream.intro",
  setup(context) {
    if (context.options.enabled === false) return;
    const reducedMotion = context.options.reducedMotion === true;
    const [replay, setReplay] = createSignal(undefined);
    const [dismissal, setDismissal] = createSignal(0);
    const [opening, setOpening] = createSignal(false);
    const openDaydream = createOpenDaydream(context, setOpening, (sessionID) => setReplay({ sessionID }));
    let consumedReplay;

    context.keymap.layer(() => commandLayer(context, { opening, openDaydream, setReplay, setDismissal }));

    function Intro(props) {
      const dimensions = useTerminalDimensions();
      const [visible, setVisible] = createSignal(false);
      const [canvas, setCanvas] = createSignal([]);
      const playback = createPlayback({
        onFrame: (value) => { setCanvas(value); setVisible(true); },
        onHide: () => setVisible(false),
        onError: (error) => context.ui.toast.show({
          title: "Daydream intro", message: error.message, variant: "warning", duration: 6000,
        }),
      });
      const size = () => ({
        width: Math.max(8, Math.min(120, dimensions().width - 36)),
        height: Math.max(4, Math.min(24, dimensions().height - 8)),
      });
      const active = createMemo(() => canShowIntro(
        context.data.session.get(props.sessionID), context.ui.router.current(),
      ));
      createEffect(on([active, replay], ([selected, request]) => {
        playback.stop();
        // Agent selection, session restore, and /agent alone never request art.
        if (!selected || !hasIntroRequest(props.sessionID, request, consumedReplay)) return;
        consumedReplay = request;
        const { width, height } = size();
        playback.start({ text: artwork(width, height), width, height, reducedMotion });
      }));
      createEffect(on(dismissal, () => playback.stop(), { defer: true }));
      // Captured frames have fixed dimensions; cancel rather than stretch on resize.
      createEffect(on(dimensions, () => playback.stop(), { defer: true }));
      onCleanup(playback.stop);
      return jsx(Show, {
        get when() { return visible() && dimensions().width >= 16 && dimensions().height >= 8; },
        get children() {
          return jsx("box", {
            width: "100%",
            flexDirection: "column",
            alignItems: "center",
            backgroundColor: "#000000",
            paddingTop: 1,
            paddingBottom: 1,
            children: jsx("text", {
              fg: "#ffffff",
              wrapMode: "none",
              get children() {
                return canvas().map((part) => jsx("span", {
                  fg: part.color,
                  children: part.text,
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
