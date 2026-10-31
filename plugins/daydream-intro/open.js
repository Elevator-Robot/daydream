// Explicit UI action: create an empty primary session, never submit a prompt.
// Uses the public OpenCode V2 Promise client (returns SessionInfo directly).
export function createOpenDaydream(context, onBusy = () => {}, onOpened = () => {}) {
  let opening = false;
  let pending;

  return async function openDaydream() {
    if (opening) return;
    opening = true;
    onBusy(true);
    try {
      if (!pending) {
        const location = context.location ?? context.data.location.default();
        await context.data.location.agent.sync(location);
        const agent = context.data.location.agent.list(location)?.find((agent) => agent.id === "daydream");
        if (!agent || agent.hidden || !["primary", "all"].includes(agent.mode)) {
          throw new Error("Install or enable the primary Daydream agent first.");
        }
        const selected = context.ui.model.current();
        pending = await context.client.session.create({
          title: "Daydream",
          agent: "daydream",
          location: { directory: location.directory },
          ...(selected ? {
            model: { providerID: selected.providerID, id: selected.modelID, variant: selected.variant },
          } : {}),
        });
      }
      // Populate reactive session data before mounting the composer so that the
      // intro sees agent=daydream immediately, before any model turn exists.
      await context.data.session.sync(pending.id);
      context.ui.router.navigate({ type: "session", sessionID: pending.id });
      const sessionID = pending.id;
      onOpened(sessionID);
      pending = undefined;
      return sessionID;
    } catch (error) {
      // If sync/navigation failed after creation, retain the empty session for a
      // retry instead of deleting it or creating duplicate sessions.
      context.ui.toast.show({
        title: "Open Daydream",
        message: error instanceof Error ? error.message : "Unable to open the Daydream session.",
        variant: "error",
      });
    } finally {
      opening = false;
      onBusy(false);
    }
  };
}
