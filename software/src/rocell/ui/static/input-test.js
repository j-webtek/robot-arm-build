/* Explicit, field-scoped test input only. Never a global keyboard listener. */
"use strict";
(() => {
  function createCapture(expected, id, start) {
    if (!/^[a-z]{1,8}$/.test(expected)) throw new Error("Use 1–8 lowercase letters.");
    const data = {schema: "rocell.input_capture.v1", capture_id: id, expected, stop_reason: null, events: []};
    return {
      stop(reason = "STOPPED") { if (data.stop_reason === null) data.stop_reason = reason; },
      add(kind, key, repeat, trusted, now) {
        if (data.stop_reason !== null) return;
        const elapsed = Math.max(0, Math.floor(now - start));
        if (elapsed > 60000) { this.stop("TIME_LIMIT"); return; }
        if (!/^[a-z]$/.test(key)) { this.stop("UNSUPPORTED_INPUT"); return; }
        if (data.events.length >= 64) { this.stop("EVENT_LIMIT"); return; }
        data.events.push({kind, key, repeat: !!repeat, trusted: !!trusted, at_ms: elapsed});
      },
      snapshot() { return JSON.parse(JSON.stringify(data)); }
    };
  }
  if (typeof module !== "undefined") module.exports = {createCapture};
  if (typeof document === "undefined") return;
  const get = id => document.getElementById(id);
  let capture = null, timer = null, ticket = null, pending = false, submitted = false;
  function finish(reason = "STOPPED") {
    if (!capture) return;
    capture.stop(reason); clearTimeout(timer);
    get("pad").disabled = true; get("stop").disabled = true;
    get("expected").disabled = false; get("start").disabled = false;
    get("prepare").disabled = submitted;
    get("status").textContent = `Stopped: ${capture.snapshot().stop_reason}`;
    get("result").textContent = JSON.stringify(capture.snapshot(), null, 2);
  }
  get("start").addEventListener("click", () => {
    if (pending) return;
    try {
      capture = createCapture(get("expected").value, crypto.randomUUID(), performance.now());
      submitted = false;
      ticket = null; get("save").disabled = true; get("prepare").disabled = true;
      get("expected").disabled = true; get("start").disabled = true;
      get("result").textContent = ""; get("saved").textContent = "";
      get("pad").value = ""; get("pad").disabled = false; get("stop").disabled = false;
      get("status").textContent = "Recording only the test field. Release the key, then click Stop.";
      timer = setTimeout(() => finish("TIME_LIMIT"), 60000); get("pad").focus();
    } catch (error) { get("status").textContent = error.message; }
  });
  // Stop before the button's focus change can interrupt the capture.
  get("stop").addEventListener("pointerdown", () => finish());
  get("stop").addEventListener("click", () => finish());
  get("pad").addEventListener("blur", () => finish("BLUR"));
  function record(kind, event, key) {
    if (!capture || capture.snapshot().stop_reason !== null) return;
    if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || event.isComposing) {
      event.preventDefault(); finish("UNSUPPORTED_INPUT"); return;
    }
    capture.add(kind, key, event.repeat, event.isTrusted, performance.now());
    if (capture.snapshot().stop_reason !== null) { event.preventDefault(); finish(); }
  }
  get("pad").addEventListener("keydown", event => record("down", event, event.key));
  get("pad").addEventListener("keyup", event => record("up", event, event.key));
  get("pad").addEventListener("beforeinput", event => {
    if (event.inputType !== "insertText" || !/^[a-z]$/.test(event.data || "")) {
      event.preventDefault(); finish("UNSUPPORTED_INPUT");
    }
  });
  get("pad").addEventListener("input", event => record("text", event, event.data || ""));
  async function request(path, body) {
    const headers = {"X-RoCell-Token": sessionStorage.getItem("rocell-session") || ""};
    if (body) Object.assign(headers, {"Content-Type": "application/json", "X-RoCell-CSRF": sessionStorage.getItem("rocell-csrf") || ""});
    const response = await fetch(path, {method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || "Capture could not be saved.");
    return result;
  }
  get("prepare").addEventListener("click", async () => {
    if (pending || submitted || !capture || capture.snapshot().stop_reason === null) return;
    pending = true; ticket = null; get("save").disabled = true;
    try {
      const view = await request("/api/view");
      const preview = await request("/api/prepare", {action_id: "review_input_capture",
        input: {capture_json: JSON.stringify(capture.snapshot())}, expected_revision: view.revision});
      ticket = preview.ticket_id; get("saved").textContent = JSON.stringify(preview, null, 2);
      get("save").disabled = !ticket;
    } catch (error) { get("saved").textContent = error.message; }
    finally { pending = false; }
  });
  get("save").addEventListener("click", async () => {
    if (pending || submitted || !ticket) return;
    // Latch before dispatch: a lost response must not allow a second ticket for
    // the same capture. Only explicitly starting a new capture clears this latch.
    submitted = true; get("prepare").disabled = true;
    pending = true; const selected = ticket; ticket = null; get("save").disabled = true;
    try {
      const result = await request("/api/execute", {ticket_id: selected});
      get("saved").textContent = `Capture submitted. Review Activity for completion, then export diagnostics. ${JSON.stringify(result)}`;
    } catch (error) { get("saved").textContent = `Save outcome uncertain; check Activity. This capture will not be resubmitted. ${error.message}`; }
    finally { pending = false; }
  });
})();
