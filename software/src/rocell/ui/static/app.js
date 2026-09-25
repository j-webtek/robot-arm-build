/* Presentation only: all eligibility, identities and measurements come from
   ArrivalWizardService. Refresh/poll/image GETs can never dispatch an action. */
"use strict";
(() => {
  const $ = (selector) => document.querySelector(selector);
  const pages = {
    overview: "Overview", commissioning: "Guided rehearsal", camera: "Camera", arm: "Arm",
    board: "Board & tests", tasks: "Task rehearsal", diagnostics: "Diagnostics & exports", controls: "Control Center", activity: "Activity & results",
  };
  const state = {view: null, page: "overview", ticket: null, pending: false, refreshing: false,
    imageId: null, imageURL: null, operationId: null, lastError: null, results: new Map(), renderFailed: false,
    cameraSections: Object.create(null), controlDirectory: {query: "", section: "all", availability: "all", page: 0},
    activityDirectory: {query: "", section: "all", status: "all", page: 0},
    drafts: new Map(), formBindings: new Map(), renderedContext: null, connectionLost: false, previewGeneration: 0, previewBinding: null};
  const cameraSectionIds = ["camera-unavailable-actions", "camera-detailed-records"];
  const fragment = new URLSearchParams(location.hash.slice(1));
  let session = fragment.get("session"), csrf = fragment.get("csrf");
  try {
    if (session && csrf) {
      sessionStorage.setItem("rocell-session", session);
      sessionStorage.setItem("rocell-csrf", csrf);
      history.replaceState(null, "", location.pathname);
    } else {
      session = sessionStorage.getItem("rocell-session");
      csrf = sessionStorage.getItem("rocell-csrf");
    }
  } catch (_) { /* The private launch URL still works with storage disabled. */ }

  const text = (value) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const human = (value) => String(value === null || value === undefined || value === "" ? "Not recorded" : value).replaceAll("_", " ");
  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = text(content);
    return node;
  }
  function heading(title, description) {
    const box = element("div", "section-heading"); box.append(element("h2", "", title));
    if (description) box.append(element("span", "caption", description));
    return box;
  }
  function card(title, description) {
    const box = element("section", "card");
    if (title) box.append(element("h2", "", title));
    if (description) box.append(element("p", "", description));
    return box;
  }
  function badge(value) {
    const label = human(value);
    const style = /fail|error|uncertain|timed.out/i.test(label) ? "failed" : /hold|block|pending|unverified|not.verified|not.run/i.test(label) ? "hold" : "";
    return element("span", "badge " + style, label);
  }
  function detail(value, title = "Inspect structured record") {
    const box = element("details"); box.append(element("summary", "", title), element("pre", "", value)); return box;
  }
  function cameraDisclosure(id, title, ...contents) {
    // Presentation preference only. Native details retains all controls and
    // explanations in the DOM; expanding never prepares or runs an action.
    const box = element("details", "camera-disclosure"); box.id = id;
    const summary = element("summary", "", title); summary.id = id + "-summary";
    box.open = state.cameraSections[id] === true;
    box.append(summary, ...contents);
    box.addEventListener("toggle", () => {
      // A queued event from a replaced page must not overwrite a newer choice.
      if (document.getElementById?.(id) === box) state.cameraSections[id] = box.open;
    });
    return box;
  }
  function facts(value, omit = []) {
    const table = element("table", "detail-table"), body = element("tbody");
    if (value && typeof value === "object") Object.entries(value).forEach(([key, item]) => {
      if (omit.includes(key) || item === null || item === undefined) return;
      const row = element("tr"), name = element("th", "", human(key)); name.scope = "row";
      const data = element("td");
      if (typeof item === "object") data.append(detail(item, Array.isArray(item) ? `${item.length} records` : "View record"));
      else data.textContent = human(item);
      row.append(name, data); body.append(row);
    });
    table.append(body); return table;
  }
  function showError(error, target = $("#error-banner")) {
    target.hidden = false; target.textContent = error.message || String(error);
    $("#announcement").textContent = target.textContent;
  }
  async function request(path, body) {
    const headers = {"X-RoCell-Token": session || ""};
    const options = {headers, cache: "no-store", credentials: "omit"};
    if (body !== undefined) {
      options.method = "POST"; headers["Content-Type"] = "application/json";
      headers["X-RoCell-CSRF"] = csrf || ""; options.body = JSON.stringify(body);
    }
    // A transport timeout does not mean the upstream attempt did not execute.
    const controller = new AbortController(); options.signal = controller.signal;
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, options);
      if (!response.ok) {
        const document = await response.json().catch(() => ({}));
        const message = document.error?.message || `Local request failed (${response.status}).`;
        throw new Error(document.error?.code ? `${document.error.code}: ${message}` : message);
      }
      return path.startsWith("/api/images/") ? response.blob() : response.json();
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The request timed out. Inspect operation status before preparing another action; nothing was automatically retried.");
      throw error;
    } finally { clearTimeout(timer); }
  }

  // Explicitly reviewed ordinary fields only. IDs, paths, evidence selections,
  // reviewer/operator labels, camera control intents and confirmations are not
  // drafts. Adding a backend action does not silently opt its inputs into reuse.
  const ordinaryDraftFields = {
    record_note: ["note"], plan_task: ["text"], simulate_task: ["text"],
    movement_campaign_preview: ["plan_json", "board_transform_json", "clearance_mm"],
    movement_endpoint_rehearse: ["plan_json", "trial_id"],
    movement_campaign_simulate: ["plan_json", "board_transform_json", "clearance_mm"],
    rehearsal_camera_settings: ["brightness_offset"],
    rehearsal_camera_campaign: ["frame_count"], rehearsal_owned_camera_campaign: ["frame_count"],
    physical_camera_operating_proposal: ["rationale", "variance_rationale"],
    physical_intake_record: ["observed_value", "method", "evidence_note"],
    physical_received_camera_draft_record: ["observed_value", "method", "evidence_note"],
  };
  function previewContext(view = state.view) {
    return JSON.stringify([view?.session_id, view?.cell_id, view?.mode, view?.source_binding_sha256, view?.state_epoch]);
  }
  function draftContext(view = state.view) {
    return view && [view.session_id, view.cell_id, view.mode].every(value => typeof value === "string" && value.length > 0 && value.length <= 128)
      && typeof view.source_binding_sha256 === "string" && /^[a-f0-9]{64}$/.test(view.source_binding_sha256)
      && Number.isSafeInteger(view.state_epoch) && view.state_epoch >= 0 ? previewContext(view) : null;
  }
  function formContract(action) {
    if (!action || !Array.isArray(action.fields) || action.fields.length > 128) return null;
    if (!action.fields.every(spec => spec && typeof spec === "object" && !Array.isArray(spec)
      && typeof spec.name === "string" && /^[a-z][a-z0-9_]{0,127}$/.test(spec.name)
      && [undefined, "text", "textarea", "number", "select", "checkbox"].includes(spec.type)
      && (spec.type !== "select" || Array.isArray(spec.options) && spec.options.length <= 512))
      || new Set(action.fields.map(spec => spec.name)).size !== action.fields.length) return null;
    const encoded = JSON.stringify(action);
    return encoded.length <= 65536 ? encoded : null;
  }
  function currentFormAction(id) {
    const matches = Array.isArray(state.view?.actions) ? state.view.actions.filter(action => action?.action_id === id) : [];
    return matches.length === 1 ? matches[0] : null;
  }
  function draftNotice(message) {
    const node = $("#draft-notice"); node.hidden = !message; node.textContent = message;
  }
  function clearDrafts(message) {
    const hadDrafts = state.drafts.size > 0; state.drafts.clear();
    if (hadDrafts && message) draftNotice(message);
  }
  function pruneDrafts() {
    let pruned = false;
    for (const [id, draft] of state.drafts) {
      const action = currentFormAction(id);
      if (state.connectionLost || draft.context !== draftContext() || !action || action.enabled !== true || draft.contract !== formContract(action)) {
        state.drafts.delete(id); pruned = true;
      }
    }
    if (pruned) draftNotice("Ordinary drafts cleared because setup, eligibility or field requirements changed. Re-enter values against the current requirements.");
  }
  function invalidatePreview() {
    state.previewGeneration++; state.ticket = null; state.previewBinding = null;
    $("#execute-action").disabled = true; $("#action-dialog").close();
  }
  function draftBindingCurrent(binding) {
    const action = currentFormAction(binding.id);
    return !state.connectionLost && !state.pending && !state.renderFailed && binding.available && binding.context !== null
      && binding.context === draftContext() && binding.contract !== null && binding.contract === formContract(action)
      && action?.enabled === true;
  }
  function ordinaryControls(binding) {
    const names = Object.hasOwn(ordinaryDraftFields, binding.id) ? ordinaryDraftFields[binding.id] : [];
    return binding.controls.filter(([spec]) => names.includes(spec.name) && ["text", "textarea", "number"].includes(spec.type || "text"));
  }
  function draftDependencies(binding) {
    return JSON.stringify(binding.controls.filter(([spec]) => spec.type === "select").map(([spec, input]) => [spec.name, input.value]));
  }
  function attachedForm(binding) {
    return document.getElementById?.(binding.box.id) === binding.box;
  }
  function retainOrdinaryDraft(binding) {
    if (!attachedForm(binding) || !draftBindingCurrent(binding)) return;
    const values = ordinaryControls(binding).map(([spec, input]) => [spec.name, input.value]);
    if (!values.length || values.some(([name, value]) => {
      const limit = binding.controls.find(([spec]) => spec.name === name)?.[0].max_length;
      return typeof value !== "string" || value.length > (Number.isSafeInteger(limit) && limit > 0 ? Math.min(limit, 8192) : 8192);
    })) {
      state.drafts.delete(binding.id); binding.message.textContent = "Draft exceeds the in-tab limit and was not kept. Current form values are unchanged."; return;
    }
    state.drafts.delete(binding.id);
    state.drafts.set(binding.id, {context: binding.context, contract: binding.contract, dependencies: draftDependencies(binding), values});
    // Bounded and browser-memory only. Never write user text into web storage.
    while (state.drafts.size > 24 || [...state.drafts.values()].reduce((sum, draft) => sum + draft.values.reduce((n, [, value]) => n + value.length, 0), 0) > 65536) {
      state.drafts.delete(state.drafts.keys().next().value);
      draftNotice("An older ordinary draft was discarded to keep browser memory bounded. No form was submitted.");
    }
    binding.message.textContent = "Ordinary draft kept in this tab. Nothing submitted; identity labels, selections and confirmations are not saved.";
    binding.restore.disabled = true;
  }
  function restoreOrdinaryDraft(binding, explicit = false) {
    const draft = state.drafts.get(binding.id);
    if (!draft || !draftBindingCurrent(binding)) return false;
    if (draft.context !== binding.context || draft.contract !== binding.contract) { state.drafts.delete(binding.id); return false; }
    if (draft.dependencies !== draftDependencies(binding)) {
      binding.message.textContent = "Ordinary draft held for previous options. Reselect the exact options, then choose Restore ordinary draft. No values or selections were restored.";
      binding.restore.disabled = true; return false;
    }
    for (const [spec, input] of ordinaryControls(binding)) {
      const saved = draft.values.find(([name]) => name === spec.name);
      if (saved) input.value = saved[1];
    }
    binding.message.textContent = explicit ? "Ordinary draft restored for these options. Review every value before previewing. Nothing submitted."
      : "Ordinary draft restored. Review every value; identity labels, selections and confirmations use current service defaults.";
    binding.restore.disabled = true; return true;
  }
  function bindFormDraft(action, box, form, controls, available, questionUpdates) {
    const binding = {id: action.action_id, context: draftContext(), contract: formContract(action), page: state.page, box, controls, available};
    state.formBindings.set(box.id, binding);
    const ordinary = ordinaryControls(binding);
    if (ordinary.length) {
      if (!available || !draftBindingCurrent(binding)) state.drafts.delete(binding.id);
      binding.message = element("p", "caption form-draft-message", draftBindingCurrent(binding)
        ? "Ordinary drafts stay in this tab only while setup and field requirements match. Identity labels, options and confirmations are never saved."
        : "Draft retention is unavailable until this form has a complete, current and eligible setup context. No values, selections or confirmations are saved.");
      binding.message.setAttribute("role", "status");
      binding.restore = element("button", "button secondary", "Restore ordinary draft"); binding.restore.type = "button"; binding.restore.disabled = true;
      binding.restore.addEventListener("click", () => { if (attachedForm(binding)) restoreOrdinaryDraft(binding, true); });
      const reset = element("button", "button secondary", "Reset form to service defaults"); reset.type = "button"; reset.disabled = !available || state.pending || state.connectionLost;
      reset.addEventListener("click", () => {
        if (!attachedForm(binding)) return;
        state.drafts.delete(binding.id); render(); document.getElementById?.(box.id)?.focus({preventScroll: true}); draftNotice("Form reset to current service defaults. No values were submitted.");
      });
      const tools = element("div", "button-row form-draft-tools"); tools.append(binding.restore, reset); form.append(binding.message, tools);
      binding.restored = restoreOrdinaryDraft(binding);
      for (const [, input] of ordinary) input.addEventListener("input", () => retainOrdinaryDraft(binding));
    }
    for (const [spec, input] of controls) if (spec.type === "select") {
      input.addEventListener("change", () => {
        if (document.getElementById && !attachedForm(binding)) return;
        if (ordinary.length && state.drafts.has(binding.id)) {
          // A value describing question A must never migrate to question B.
          // Keep it held in memory, not in B's fields, for explicit restoration.
          for (const [field, control] of ordinary) control.value = field.default == null ? "" : String(field.default);
          const draft = state.drafts.get(binding.id);
          binding.restore.disabled = !draftBindingCurrent(binding) || draft.dependencies !== draftDependencies(binding);
          binding.message.textContent = binding.restore.disabled ? "Options changed. The earlier ordinary draft is held for its exact previous options; current fields use service defaults."
            : "The options match the held draft. Choose Restore ordinary draft to review its values; nothing was restored automatically.";
        }
        questionUpdates.get(spec.name)?.();
      });
    }
    return binding;
  }

  function actionForm(action) {
    const displayedRevision = state.view.revision;
    const receivedRecord = action.action_id === "physical_received_camera_draft_record";
    const received = receivedRecord ? receivedCameraProjection(state.view.received_camera_onboarding,state.view) : null;
    const intake = receivedRecord ? (received?.publication.status === "CURRENT" && received.status === "DRAFT" ? {status:"CURRENT_DRAFT",notebook:received.draft} : null) : action.action_id === "physical_intake_record" ? physicalIntakeProjection(state.view.physical_intake, state.view.physical_camera_setup) : null;
    const intakeHeld = (receivedRecord || action.action_id === "physical_intake_record") && (!intake || intake.status !== "CURRENT_DRAFT");
    const observational = action.action_id === "run_observational_movement";
    const wristPreview = action.observational_preview;
    const absoluteWrist = observational && wristPreview && Object.hasOwn(wristPreview, "absolute_target_degrees");
    const wristSelectionValid = absoluteWrist
      ? ([-4, 0, 4].includes(wristPreview.absolute_target_degrees)
        && wristPreview.reviewed_draft?.target_deg === wristPreview.absolute_target_degrees
        && [-1, 1].includes(wristPreview.reviewed_draft?.direction)
        && wristPreview.fresh_baseline_required === true && wristPreview.retry_allowed === false
        && !Object.hasOwn(wristPreview, "delta_degrees"))
      : wristPreview && [-5, -1, 1, 5].includes(wristPreview.delta_degrees);
    const wristPreviewValid = !observational || (wristPreview && wristSelectionValid
      && wristPreview.spd === 20 && wristPreview.acc === 1 && wristPreview.return_motion === false);
    const correction = action.action_id === "run_wrist_correction";
    const correctionPreview = action.correction_preview;
    const correctionPreviewValid = !correction || (correctionPreview
      && correctionPreview.schema === "rocell.wizard_wrist_correction_runtime.v1"
      && Number.isFinite(correctionPreview.nominal_target_deg)
      && Number.isFinite(correctionPreview.experimental_motor_target_deg)
      && Math.abs(correctionPreview.nominal_target_deg) <= 10
      && Math.abs(correctionPreview.experimental_motor_target_deg) <= 10
      && /^[a-f0-9]{64}$/.test(correctionPreview.binding_sha256)
      && /^[a-f0-9]{64}$/.test(correctionPreview.runtime_sha256)
      && correctionPreview.spd === 20 && correctionPreview.acc === 1
      && correctionPreview.fresh_baseline_required === true
      && correctionPreview.return_motion === false && correctionPreview.retry_allowed === false);
    const available = action.enabled === true && !intakeHeld && !state.connectionLost && wristPreviewValid && correctionPreviewValid;
    const box = card(null); box.classList.add("action-card");
    if (Object.hasOwn(pages, action.section) && !["controls", "activity"].includes(action.section)) { box.id = `${action.section}-action-${action.action_id}`; box.tabIndex = -1; }
    const form = element("form"); form.append(element("h3", "", action.label || human(action.action_id)));
    form.setAttribute("aria-label", action.label || human(action.action_id));
    if (action.description) form.append(element("p", "", action.description));
    if (action.action_id === "run_held_pair") {
      const preview = action.pair_preview;
      form.append(element("h4", "", "Host-bound elbow pair — servo counts, not millimeters"));
      if (preview && Number.isInteger(preview.forward_target_count) && Number.isInteger(preview.return_target_count)) {
        form.append(facts({"forward target": preview.forward_target_count, "return target": preview.return_target_count,
          "tolerance (counts)": preview.tolerance_counts, "controller": preview.address, "boot": preview.boot_id}));
      } else form.append(element("p", "", "No valid host-bound preparation is attached."));
      form.append(element("p", "", "Return requires verified forward arrival and successful export. No retry or recovery motion. The acknowledgement does not replace separate host approval."));
    }
    if (action.action_id === "run_positional_campaign") {
      form.append(element("h4", "", "Attended bounded movement test"));
      const preview = action.campaign_preview;
      if (preview && Array.isArray(preview.legs) && preview.legs.length > 0) {
        const jointLabel = ({ b: "base", r: "wrist roll", t: "wrist pitch" })[preview.selected_joint] || "wrist pitch";
        if (preview.roll_case_id) {
          form.append(element("p", "", `Target-variation case: ${preview.roll_case_id}. One command only; no automatic return or compensation.`));
          form.append(element("pre", "campaign-start-pose", JSON.stringify(preview.start_joints_rad)));
        }
        const route = element("ol");
        for (const leg of preview.legs) {
          route.append(element("li", "", `${leg.leg_id}: ${(leg.expected_start_rad * 180 / Math.PI).toFixed(3)}° → ${(leg.target_rad * 180 / Math.PI).toFixed(3)}° absolute ${jointLabel} target.`));
        }
        form.append(route);
        if (preview.limits) form.append(element("p", "", `Observation per command: ${preview.limits.observation_s} seconds on the same connection. Maximum writes: ${preview.limits.maximum_writes}. Speed setting: ${preview.limits.spd}; acceleration: ${preview.limits.acc}.`));
        form.append(element("pre", "campaign-selection", JSON.stringify(preview.usb_identity, null, 2)));
      } else {
        form.append(element("p", "", "No host-staged campaign. Reviewed originals and explicit targets must be attached first."));
      }
      form.append(element("p", "", "Each endpoint must verify before the next command. No retry after a fault. Cancellation does not guarantee that an accepted servo goal stops."));
    }
    if (correction) {
      form.append(element("h4", "", "Experimental correction — not a validated calibration"));
      if (correctionPreviewValid) {
        form.append(element("p", "", `Desired endpoint: ${correctionPreview.nominal_target_deg} degrees. Experimental motor command: ${correctionPreview.experimental_motor_target_deg} degrees. Speed setting: 20; acceleration setting: 1.`));
        form.append(element("p", "", "A fresh baseline must match the retained starting pose and approach. One command only, no return or retry. Process/export success does not mean endpoint success."));
        form.append(element("pre", "correction-selection", JSON.stringify(correctionPreview, null, 2)));
      } else {
        form.append(element("p", "", "No valid prepared correction preview. Prepare and review the matched assessment first."));
      }
      form.append(element("p", "", "Stay beside the secured arm with shutdown reachable. Opening serial can cause startup movement; software cancellation is not an emergency stop."));
    }
    if (observational) {
      form.append(element("h4", "", absoluteWrist ? "Absolute endpoint test: fixed target with fresh baseline verification" : "Observational test: no precision measurements needed"));
      if (wristPreviewValid) {
        if (absoluteWrist) {
          form.append(element("p", "", `Absolute wrist-pitch target: ${wristPreview.absolute_target_degrees} degrees. Speed: 20 servo steps/s; acceleration setting: 1. This is not a relative increment.`));
          form.append(element("p", "", "The fresh six-joint baseline must match the reviewed start and approach direction. Endpoint status is reconstructed from telemetry. No return or retry."));
          form.append(element("pre", "observational-selection", JSON.stringify(wristPreview.reviewed_draft, null, 2)));
        } else {
        form.append(element("p", "", `One wrist-pitch increment: ${wristPreview.delta_degrees > 0 ? "+" : ""}${wristPreview.delta_degrees} degree from the captured baseline. Speed: 20 servo steps/s; acceleration setting: 1.`));
        form.append(element("p", "", "The software derives an absolute target from the owned baseline immediately before sending. This is an increment, not a fixed +1-degree target. No return or retry."));
        }
        form.append(element("pre", "observational-selection", JSON.stringify(wristPreview.usb_identity, null, 2)));
      } else {
        form.append(element("p", "", "No valid staged observational preview. Complete intake and setup before running."));
      }
      const steps = element("ol", "observational-prerequisites");
      for (const text of [
        "Use connected arm for observational testing: reuse correlated USB metadata and confirm the model/firmware history.",
        absoluteWrist ? "Review the host-attached absolute target, expected start and approach direction shown above." : "Prepare observational wrist test: choose the retained records and relative wrist direction.",
        "Check the private bench review key. Missing key storage is a software setup issue; provisioning is a separate explicit action.",
        "With supplied power on, remain beside the secured arm, keep the movement area clear, and confirm only this bounded test.",
        "After the attempt, choose Record what the arm did. Notes and photos are optional; the software compares your observation with telemetry.",
        "Export logs before troubleshooting. A held result is not permission to repeat the command."
      ]) steps.append(element("li", "", text));
      form.append(steps);
      form.append(element("p", "", "Opening the controller may cause startup movement. Cancellation is not a physical emergency stop. Keep the power shutdown reachable."));
    }
    if (action.action_id === "run_endpoint_trial" && action.endpoint_draft) {
      form.append(element("p", "", "Bound draft: " + action.endpoint_draft_sha256));
      form.append(element("pre", "", JSON.stringify(action.endpoint_draft, null, 2)));
    }
    if (action.action_id === "run_first_motion" && !action.commissioning_preview) {
      form.append(element("p", "", "Advanced measured-profile workflow. Its measurement requirements do not apply to the separate observational wrist test above."));
      form.append(element("h4", "", "Prepare this commissioning test"));
      const prerequisites = element("ol", "commissioning-prerequisites");
      for (const text of [
        "Use Set up private bench review key: CHECK first, then explicitly PROVISION only when needed. Missing key storage is not an arm or USB fault.",
        "Record actual independent wrist measurements, including angle and radius uncertainty. Wrist angle is relative to the forearm, not world horizontal. Do not touch or reposition powered joints.",
        "Record all five engineering decisions for one exact selection. UNKNOWN and DENIED are retained but cannot authorize a run.",
        "Have the trusted host integration attach the exact draft, evidence originals and successful same-session measurement/review receipts. This page cannot infer them from a photo or manufacture missing measurements.",
        "After attachment, inspect the displayed command and limits. Confirm current powered setup and clearance only while present at the secured arm."
      ]) prerequisites.append(element("li", "", text));
      form.append(prerequisites);
      form.append(element("p", "", "Until these prerequisites are satisfied, keep this run blocked. There is no automatic home, return, retry or contact action."));
    }
    if (action.action_id === "run_first_motion" && action.commissioning_preview) {
      const preview = action.commissioning_preview;
      form.append(element("p", "", "Commissioning selection: " + preview.selection_sha256));
      form.append(element("p", "", "One absolute wrist-pitch target: +1 degree relative to the forearm (not a +1 degree increment). Speed: 20 servo steps/s; acceleration setting: 1. No return or retry."));
      form.append(element("p", "", "The selected starting interval, distal radius, USB identity, evidence hashes and limits are shown below. These declarations do not independently prove clearance or fresh telemetry. Opening the controller can cause startup movement; cancellation is not a physical emergency stop."));
      // Text content, never HTML: retained reference material is untrusted data.
      form.append(element("pre", "commissioning-selection", JSON.stringify(preview.selection, null, 2)));
    }
    const fields = element("div", "fields"), controls = [], questionUpdates = new Map();
    for (const spec of action.fields || []) {
      const row = element("div", spec.type === "checkbox" ? "field check" : "field");
      const id = `field-${action.action_id}-${spec.name}`;
      const label = element("label", "", spec.label || human(spec.name)); label.htmlFor = id;
      let input;
      if (spec.type === "select") {
        input = element("select");
        // Do not silently preselect the first discovered device. A reviewed
        // server default may be displayed; otherwise the user chooses.
        if (spec.default === undefined || spec.default === null) {
          const placeholder = element("option", "", spec.placeholder || "Choose an option");
          placeholder.value = ""; placeholder.disabled = true; placeholder.selected = true;
          input.append(placeholder);
        }
        for (const option of spec.options || []) {
          const item = typeof option === "object" ? option : {value: option, label: option};
          const opt = element("option", "", item.label || human(item.value));
          opt.value = String(item.value); input.append(opt);
        }
      } else if (spec.type === "textarea") input = element("textarea");
      else {
        input = element("input"); input.type = ["number", "checkbox"].includes(spec.type) ? spec.type : "text";
      }
      input.id = id; input.name = spec.name; input.required = Boolean(spec.required);
      input.disabled = !available || state.pending;
      if (spec.type === "checkbox") input.checked = Boolean(spec.default);
      else if (spec.default !== undefined && spec.default !== null) input.value = String(spec.default);
      if (spec.min !== undefined) input.min = spec.min;
      if (spec.max !== undefined) input.max = spec.max;
      if (spec.step !== undefined) input.step = spec.step;
      if (spec.type === "number" && spec.step === undefined) input.step = "any";
      if (spec.placeholder) input.placeholder = spec.placeholder;
      if (Number.isSafeInteger(spec.max_length) && spec.max_length > 0 && ["text", "textarea"].includes(spec.type || "text")) input.maxLength = spec.max_length;
      if (spec.type === "checkbox") row.append(input, label); else row.append(label, input);
      if (spec.help) {
        const help = element("small", "", spec.help); help.id = id + "-help";
        input.setAttribute("aria-describedby", help.id); row.append(help);
      }
      fields.append(row); controls.push([spec, input]);
      if (action.action_id === "review_first_motion_qualification" && spec.name === "assessment_operation_id") {
        const context = element("div", "notice warning"); context.setAttribute("aria-live", "polite");
        const updateAssessment = () => {
          const preview = action.qualification_previews?.[input.value];
          context.replaceChildren(element("p", "", "Review the selected assessment and its limitations. This cached display is not a fresh physical observation. Evidence is revalidated when the decision is recorded; acceptance cannot override a hold or authorize another move."));
          if (preview) context.append(element("pre", "qualification-assessment", JSON.stringify(preview, null, 2)));
          else context.append(element("p", "", "Choose an assessment to inspect its holds and reported observation."));
        };
        questionUpdates.set(spec.name, updateAssessment); updateAssessment(); fields.append(context);
      }
      if (["review_retained_first_motion_draft", "attach_retained_first_motion"].includes(action.action_id) && spec.name === "draft_operation_id") {
        const context = element("div", "notice warning"); context.setAttribute("aria-live", "polite");
        const updatePreview = () => {
          const preview = action.retained_draft_previews?.[input.value];
          context.replaceChildren(element("p", "", "Review is explicit and self-reported. This cached preview is not current physical verification or motion approval; execution re-checks the retained original."));
          if (preview && preview.motion_authorized === false && preview.selection) {
            context.append(element("p", "", "Selected commissioning digest: " + preview.selection_sha256));
            context.append(element("pre", "commissioning-selection", JSON.stringify(preview.selection, null, 2)));
          } else context.append(element("p", "", "Choose a retained draft to inspect its identity, geometry, command and limits."));
        };
        questionUpdates.set(spec.name, updatePreview); updatePreview(); fields.append(context);
      }
      if ((receivedRecord || action.action_id === "physical_intake_record") && spec.name === "record_id") {
        const context = element("div", "notice warning"); context.setAttribute("aria-live", "polite");
        const updateQuestion = () => {
          const selected = intake?.notebook?.rows.find(item => item.record_id === input.value);
          context.replaceChildren(selected ? intakeQuestion(selected) : element("p", "", "Choose one original question to see its units and requirement. No observed value or method is inferred."));
        };
        questionUpdates.set(spec.name, updateQuestion); updateQuestion(); fields.append(context);
      }
    }
    if (controls.length) form.append(fields);
    const draftBinding = bindFormDraft(action, box, form, controls, available, questionUpdates);
    if (action.blocked_reasons?.length) {
      const reasons = element("ul", "action-blockers");
      for (const reason of action.blocked_reasons) reasons.append(element("li", "", typeof reason === "object" ? reason.message || reason.code || text(reason) : reason));
      form.append(reasons);
    }
    const submit = element("button", "button " + (action.action_id === "stop_operation" ? "danger" : "primary"), "Preview action");
    submit.type = "submit"; submit.disabled = !available || state.pending;
    if (intakeHeld) form.append(element("p", "notice warning", "Current source-bound intake questions are unavailable. Recording is held; review setup and diagnostics."));
    form.append(submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); if (!available || state.pending || state.connectionLost || state.renderFailed || !form.reportValidity()) return;
      if (document.getElementById && !attachedForm(draftBinding)) return;
      const input = {};
      for (const [spec, control] of controls) {
        if (spec.type === "checkbox") input[spec.name] = control.checked;
        else if (spec.type === "number") {
          if (control.value !== "") input[spec.name] = Number(control.value);
        } else input[spec.name] = control.value;
      }
      submit.disabled = true;
      try { await prepare(action.action_id, input, displayedRevision); }
      catch (error) { showError(error); }
      finally { submit.disabled = !available || state.pending; }
    });
    // Group from the same eligibility calculation as the controls. In
    // particular, a missing current intake cannot look available in the list.
    box.append(form); return {node: box, available: available && !state.pending};
  }

  function actions(section, omittedActionId = null) {
    const result = element("div", "grid two");
    const items = (state.view.actions || []).filter((action) => action.section === section && action.action_id !== omittedActionId);
    for (const action of items) result.append(actionForm(action).node);
    if (!items.length) result.append(element("div", "empty-state", "No actions are offered for the current state. See Overview for prerequisites."));
    return result;
  }

  function cameraActions() {
    const fragment = element("section"); fragment.id = "camera-actions"; fragment.tabIndex = -1;
    const available = element("div", "grid two"), unavailable = element("div", "grid two");
    let offeredCount = 0, heldCount = 0;
    for (const action of (state.view.actions || []).filter(item => item.section === "camera")) {
      const form = actionForm(action);
      if (form.available) { available.append(form.node); offeredCount++; }
      else { unavailable.append(form.node); heldCount++; }
    }
    if (!offeredCount) available.append(element("p", "empty-state", "No camera action is currently available. Expand the unavailable actions to inspect their prerequisites; nothing is retried automatically."));
    fragment.append(heading("Camera actions", `${offeredCount} available · preview and confirmation still required`), available,
      cameraDisclosure(cameraSectionIds[0], `Unavailable camera actions (${heldCount})`,
        element("p", "caption", "All unavailable forms and their exact holds are retained here. Expanding this section changes only the page; it grants no connection, consent or stage acceptance."), unavailable));
    return fragment;
  }

  function reopening(view) {
    const box = card("Open an existing rehearsal", "Discover reads only the assigned store registry. Opening is a separate, explicitly confirmed action: it requalifies storage and acquires/releases leases on the original session.");
    box.append(element("p", "caption", "Nothing is discovered or opened by visiting this page. No session is copied, no prior operation is replayed, and no camera preview is loaded by reopening."));
    const discovery = view.discovery;
    if (!discovery || typeof discovery !== "object") {
      box.append(element("p", "empty-state", "Existing stores have not been discovered. Use the explicit Discover action below."));
    } else {
      const choices = Array.isArray(discovery.choices) ? discovery.choices : [];
      if (!choices.length) box.append(element("p", "empty-state", discovery.status === "NOT_DISCOVERED" ? "Discovery has not run in this launch." : "No eligible store choices were returned. Review discovery issues; do not enter a filesystem path."));
      if (choices.length > 128) box.append(element("p", "notice warning", "Discovery exceeds the display limit. Inspect diagnostics; the list is not silently truncated."));
      else for (const choice of choices) {
        if (!choice || typeof choice.choice_id !== "string") {
          box.append(element("p", "notice warning", "An invalid discovery record was returned. Do not infer a store selection.")); continue;
        }
        const row = element("details");
        row.append(element("summary", "", choice.session_id || choice.choice_id), badge(choice.status || "DISCOVERED_NOT_OPENED"));
        if (choice.source_matches === false) row.append(element("p", "notice warning", "Source mismatch: this store cannot be converted or silently rebased."));
        // Opaque choices/identity hashes must remain verbatim data, never paths
        // to serve or parameters for an automatically dispatched action.
        for (const key of ["choice_id", "directory", "cell_id", "session_id", "session_header_sha256", "discovery_sha256"]) {
          if (typeof choice[key] !== "string") continue;
          const line = element("p", "caption"); line.append(element("span", "", human(key) + ": "), element("code", "", choice[key])); row.append(line);
        }
        box.append(row);
      }
      if (Array.isArray(discovery.issues)) for (const issue of discovery.issues.slice(0, 128)) {
        if (!issue || typeof issue !== "object") continue;
        const notice = element("div", "notice warning");
        notice.append(element("strong", "", issue.code || "DISCOVERY_HOLD"), element("p", "", issue.message || "Discovery requires inspection."));
        if (issue.remediation) notice.append(element("p", "caption", issue.remediation)); box.append(notice);
      }
    }
    const result = view.reopen_result;
    if (result && typeof result === "object") {
      box.append(heading("Last explicit open result"), badge(result.status || "NOT_RECORDED"));
      if (result.status === "OPENED") {
        box.append(element("p", "", "Original rehearsal reopened. The active directory, cell and session above belong to that retained store; this is not a new session."));
        if (view.stage_state === "REVIEW_PENDING") box.append(element("p", "notice warning", "Retained assessment awaits a fresh, distinct reviewer. Reopening restores evidence, not acceptance or a previous approval."));
        if (result.disposition === "WAITING_NO_RECEIPT") box.append(element("p", "notice warning", "At reopening, this stage was waiting without an assessable receipt. That historical result does not prove current collection or authorize replay. An unrecorded operator must be supplied explicitly."));
      } else if (result.status === "READ_ONLY_HOLD") box.append(element("p", "notice warning", "Existing store held read-only. No restored approval or operational adapter was admitted. Inspect/export the retained evidence; do not repair, reset or replay it."));
      if (Array.isArray(result.reasons)) for (const reason of result.reasons.slice(0, 128)) {
        if (!reason || typeof reason !== "object") continue;
        box.append(element("p", "notice warning", `${reason.code || "OPEN_HOLD"}: ${reason.message || "Inspect retained state."}`));
        if (reason.remediation) box.append(element("p", "caption", reason.remediation));
      }
    }
    return box;
  }

  function compactCheckData(value) {
    // These are presentation bounds, not evidence acceptance. Never expand a
    // full report/protocol log merely because a cached projection contains it.
    let visited = 0;
    function bounded(item, depth) {
      if (++visited > 128 || depth > 6) return false;
      if (item === null || typeof item === "boolean") return true;
      if (typeof item === "string") return item.length <= 2048;
      if (typeof item === "number") return Number.isFinite(item) && Math.abs(item) <= Number.MAX_SAFE_INTEGER;
      if (Array.isArray(item)) return item.length <= 32 && item.every(child => bounded(child, depth + 1));
      if (!item || typeof item !== "object") return false;
      const entries = Object.entries(item);
      return entries.length <= 32 && entries.every(([key, child]) => key.length <= 128 && bounded(child, depth + 1));
    }
    if (!bounded(value, 0)) return null;
    const rendered = text(value);
    return typeof rendered === "string" && rendered.length <= 4096 ? rendered : null;
  }

  function retainedArmChecks(projection, title, stages, physicalLimitations, showObserved = true) {
    const box = element("div", "retained-evaluation");
    box.append(heading(title), element("p", "notice warning", physicalLimitations));
    const record = projection && typeof projection === "object" && !Array.isArray(projection);
    const digest = value => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
    const shortText = value => typeof value === "string" && value.length > 0 && value.length <= 512;
    const provenance = record && projection.provenance && typeof projection.provenance === "object" && !Array.isArray(projection.provenance)
      ? compactCheckData(projection.provenance) : null;
    const valid = record && stages.includes(projection.stage)
      && ["REHEARSAL_CHECKS_PASSED", "BLOCKED"].includes(projection.outcome)
      && projection.physical_authority === false && shortText(projection.meaning)
      && digest(projection.evaluation_sha256) && digest(projection.selected_inputs_sha256)
      && provenance !== null && Array.isArray(projection.checks)
      && projection.checks.length > 0 && projection.checks.length <= 16;
    if (!valid) {
      box.append(badge("NOT_VERIFIED"), element("p", "notice warning", "The retained check projection is missing, inconsistent or exceeds display bounds. Inspect diagnostics; no passing result is inferred and no report is silently truncated."));
      return box;
    }
    box.append(facts({evaluated_stage: projection.stage, reported_outcome: projection.outcome,
      evaluation_sha256: projection.evaluation_sha256, selected_inputs_sha256: projection.selected_inputs_sha256,
      physical_authority: false}), element("p", "caption", projection.meaning));
    if (showObserved) box.append(detail(provenance, "Synthetic input provenance"));
    const list = element("ul", "stage-list");
    for (const check of projection.checks) {
      const item = element("li"), row = check && typeof check === "object" && !Array.isArray(check);
      const kind = row && ["NOMINAL", "EXPECTED_FAULT", "INVARIANT"].includes(check.check_kind) ? check.check_kind : "UNKNOWN_CHECK_KIND";
      const observed = row ? compactCheckData(check.observed) : null;
      const validRow = row && typeof check.check_id === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(check.check_id)
        && kind !== "UNKNOWN_CHECK_KIND" && typeof check.passed === "boolean" && shortText(check.meaning) && observed !== null;
      // Expected-fault success remains its own category. It is never relabeled
      // as nominal readiness, an observed power state, or a physical stage PASS.
      const status = !validRow ? "NOT_VERIFIED" : !check.passed ? "BLOCKED"
        : kind === "NOMINAL" ? "NOMINAL_CHECK_PASSED_REHEARSAL"
          : kind === "EXPECTED_FAULT" ? "EXPECTED_FAULT_CHECK_PASSED_REHEARSAL" : "INVARIANT_CHECK_PASSED_REHEARSAL";
      item.append(element("span", "", validRow ? human(check.check_id) : "Invalid retained check"), badge(kind), badge(status));
      if (validRow) {
        item.append(element("p", "caption", check.meaning));
        if (showObserved) item.append(detail(observed, "Observed check data"));
      }
      else item.append(element("p", "notice warning", "Check data is not verified for display. Inspect its retained report; do not infer a passing result."));
      list.append(item);
    }
    box.append(list, element("p", "caption", "Expected-fault checks verify expected handling only; they cannot replace passing nominal checks. This view does not assess, review, replay, or advance a stage. The separate rehearsal journal and exact review remain authoritative."));
    return box;
  }

  function retainedFeedback(projection) {
    const box = retainedArmChecks(projection, "Retained synthetic feedback campaign", ["feedback_only_connection"],
      "Simulation only: no physical serial port, arm connection, firmware qualification or energy observation. A valid response does not establish pose, stationarity or safe power-off.", false);
    const object = value => value && typeof value === "object" && !Array.isArray(value);
    const digest = value => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
    const count = value => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
    const identifier = value => typeof value === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
    const error = value => value === null || (object(value) && Object.keys(value).length === 3
      && ["code", "phase", "error_type"].every(key => identifier(value[key])));
    const summary = object(projection) ? projection.safe_summary : null;
    const countKeys = ["object_creations", "identity_checks", "open_attempts", "opens_confirmed", "unexpected_open_objects", "write_attempts", "writes_confirmed", "write_bytes_confirmed", "read_attempts", "read_bytes_retained", "close_attempts", "closes_confirmed"];
    const valid = object(summary) && summary.schema === "rocell.rehearsal_arm_feedback_summary.v1"
      && ["binding_sha256", "source_sha256", "request_sha256", "controller_binding_sha256"].every(key => digest(summary[key]))
      && ["SUCCEEDED_DIAGNOSTIC", "BLOCKED_PRE_OPEN", "CANCELLED_PRE_OPEN", "FAILED_UNCERTAIN"].includes(summary.worker_outcome)
      && ["technical_response_valid", "feedback_receipt_valid", "serial_cleanup_confirmed", "effect_uncertain"].every(key => typeof summary[key] === "boolean")
      && summary.final_power_state === "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
      && summary.physical_authority === false && summary.arm_connected === false && summary.installed_firmware_proven_by_packet === false
      && object(summary.api_counts) && countKeys.every(key => count(summary.api_counts[key]))
      && error(summary.primary_error) && Array.isArray(summary.cleanup_errors) && summary.cleanup_errors.length <= 8 && summary.cleanup_errors.every(item => item !== null && error(item))
      && object(summary.wire) && ["response", "unexpected"].every(key => object(summary.wire[key]) && digest(summary.wire[key].sha256) && count(summary.wire[key].retained_bytes))
      && typeof summary.wire.unexpected.unretained_bytes === "number" && Number.isInteger(summary.wire.unexpected.unretained_bytes) && summary.wire.unexpected.unretained_bytes >= 0
      && object(summary.timing) && summary.timing.basis === "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP"
      && typeof summary.timing.transaction_timing_available === "boolean" && count(summary.timing.elapsed_ns);
    if (!valid) box.append(badge("NOT_VERIFIED"), element("p", "notice warning", "Safe serial summary is missing or invalid. No response validity, serial cleanup, or worker power result is inferred. Raw evidence is never expanded here."));
    else {
      box.append(heading("Technical response — separate from cleanup"),
        badge(summary.technical_response_valid ? "VALID_SYNTHETIC_RESPONSE" : "RESPONSE_NOT_VALIDATED"),
        facts({worker_outcome: summary.worker_outcome, complete_feedback_receipt_valid: summary.feedback_receipt_valid,
          request_sha256: summary.request_sha256, controller_binding_sha256: summary.controller_binding_sha256}),
        element("p", "caption", "Packet validity can be true even when close/cleanup failed. It proves neither installed firmware nor calibrated position."));
      box.append(heading("Serial cleanup — separate from power"),
        badge(summary.serial_cleanup_confirmed ? "SERIAL_API_CLEANUP_CONFIRMED" : "SERIAL_CLEANUP_NOT_CONFIRMED"),
        facts({effect_uncertain: summary.effect_uncertain}),
        element("p", "caption", "Closing a simulated serial handle is not a DC disconnect, an emergency stop, or evidence that actuator power is off."));
      if (summary.primary_error) box.append(heading("Primary error codes"), facts(summary.primary_error));
      for (const item of summary.cleanup_errors) box.append(heading("Cleanup error codes"), facts(item));
      const counters = {}; for (const key of countKeys) counters[key] = summary.api_counts[key];
      box.append(heading("Simulated serial API counters"), facts(counters),
        element("p", "caption", "These are incapable-backend API calls, not physical device operations. No raw request, response, boot bytes or arbitrary endpoint is displayed."));
      box.append(heading("Retained wire hashes and counts"), facts({
        response_sha256: summary.wire.response.sha256, response_bytes_retained: summary.wire.response.retained_bytes,
        unexpected_sha256: summary.wire.unexpected.sha256, unexpected_bytes_retained: summary.wire.unexpected.retained_bytes,
        unexpected_bytes_unretained: count(summary.wire.unexpected.unretained_bytes) ? summary.wire.unexpected.unretained_bytes : "NOT_EXACT_IN_BROWSER",
        binding_sha256: summary.binding_sha256, source_sha256: summary.source_sha256,
        host_elapsed_ns: summary.timing.elapsed_ns, timing_basis: summary.timing.basis,
        transaction_timing_available: summary.timing.transaction_timing_available,
      }), element("p", "caption", "Absolute monotonic timestamps stay in retained evidence and are not rendered as device timestamps. Unsafe numeric values are never rounded into an exact-looking count."));
    }
    // This remains visible even with an independent observer. Never replace
    // the worker's honest UNKNOWN state with a successful API-close result.
    box.append(heading("Worker final-power knowledge"), badge("UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"),
      element("p", "notice warning", "The serial worker cannot observe final actuator power. Response validity and serial cleanup do not change this UNKNOWN state."));
    const observation = object(projection) ? projection.final_power_observation : null;
    box.append(heading("Independent synthetic final-power observation"));
    const ownedObservation = object(observation) && observation.schema === "rocell.owned_arm_synthetic_final_power_observation.v1";
    const observationValid = object(observation) && (observation.schema === "rocell.synthetic_final_power_observation.v1" || ownedObservation)
      && observation.origin === "SYNTHETIC_REHEARSAL" && observation.observation_kind === "INDEPENDENT_POST_CAMPAIGN_FIXTURE"
      && identifier(observation.observer_id) && ["DEENERGIZED", "ENERGIZED", "UNKNOWN"].includes(observation.observed_power_state)
      && observation.observed_after_worker === true && observation.physical_observation === false && observation.serial_close_used_to_infer_power === false
      && ["permit_sha256", "observation_sha256"].every(key => digest(observation[key]))
      && (digest(observation.feedback_evidence_sha256) || (ownedObservation && observation.feedback_evidence_sha256 === null))
      && (!ownedObservation || (digest(observation.owned_evidence_sha256) && observation.process_cleanup_used_to_infer_power === false));
    if (!observationValid) box.append(badge(observation === null || observation === undefined ? "FINAL_POWER_OBSERVATION_MISSING" : "FINAL_POWER_OBSERVATION_NOT_VERIFIED"),
      element("p", "notice warning", "A separate retained synthetic post-campaign observation is missing or invalid. No known final power state or replay permission is inferred."));
    else {
      box.append(badge(observation.observed_power_state === "DEENERGIZED" ? "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY" : "FINAL_POWER_OBSERVATION_HOLD"),
        facts({recorded_synthetic_state: observation.observed_power_state, observer_id: observation.observer_id,
          observed_after_worker: true, permit_sha256: observation.permit_sha256,
          feedback_evidence_sha256: observation.feedback_evidence_sha256, observation_sha256: observation.observation_sha256,
          physical_observation: false, serial_close_used_to_infer_power: false}));
      if (ownedObservation) box.append(facts({owned_evidence_sha256: observation.owned_evidence_sha256, process_cleanup_used_to_infer_power: false}),
        element("p", "caption", "This separate synthetic observer follows the owned campaign. Its IPC evidence hash and actual inner feedback hash are distinct; no absolute host timestamp is rendered."));
    }
    box.append(element("p", "caption", "This independent fixture observation is rehearsal evidence only, not a measurement of real power. It does not rewrite the worker's UNKNOWN state. Missing, UNKNOWN or ENERGIZED results require the backend's explicit hold; the view cannot clear it or authorize another attempt."));
    return box;
  }

  function retainedReference(projection) {
    const box = retainedArmChecks(projection, "Retained synthetic reference-frame checks", ["reference_frame_calibration"],
      "Nominal software rehearsal only: no installed calibration, physical bootstrap/reference receipt importer, energy change, robot motion or contact. T105 feedback is not a calibrated joint state.");
    const object = value => value && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const count = value => Number.isSafeInteger(value) && value >= 0;
    const metric = value => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= Number.MAX_SAFE_INTEGER);
    const pending = ["bootstrap_phase_receipt", "reference_characterization_phase_receipt", "arm_to_board_transform", "controller_model_correlation", "free_state_tool_tcp", "keyboard_target_map", "phone_target_map", "outcome_observer_candidates"];
    const summary = object(projection) ? projection.reference_summary : null;
    const coverage = value => exact(value, ["selected", "catalog_total"]) && count(value.catalog_total)
      && Array.isArray(value.selected) && value.selected.length === 1 && value.catalog_total > value.selected.length
      && value.selected.every(item => typeof item === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(item));
    const valid = exact(summary, ["schema", "graph", "numeric", "target_coverage", "claim", "physical_components_pending", "camera_role", "controller_feedback_role"])
      && summary.schema === "rocell.rehearsal_reference_summary.v1"
      && exact(summary.graph, ["nominal_artifacts", "parent_edges", "context_edges", "detected_edges"])
      && ["nominal_artifacts", "parent_edges", "context_edges", "detected_edges"].every(key => count(summary.graph[key]))
      && summary.graph.nominal_artifacts === 15 && summary.graph.parent_edges === 27 && summary.graph.context_edges === 41
      && summary.graph.detected_edges <= summary.graph.parent_edges + summary.graph.context_edges
      && exact(summary.numeric, ["training_points", "heldout_points", "training_rms_mm", "heldout_rms_mm", "max_roundtrip_error_mm"])
      && summary.numeric.training_points === 4 && summary.numeric.heldout_points === 2
      && ["training_rms_mm", "heldout_rms_mm", "max_roundtrip_error_mm"].every(key => metric(summary.numeric[key]))
      && exact(summary.target_coverage, ["keyboard", "phone"])
      && coverage(summary.target_coverage.keyboard) && coverage(summary.target_coverage.phone)
      && summary.target_coverage.keyboard.catalog_total === 46 && summary.target_coverage.phone.catalog_total === 29
      && summary.claim === "TWO_TARGET_COORDINATE_ROUNDTRIPS_NOT_REACHABILITY_OR_COMPLETE_COVERAGE"
      && Array.isArray(summary.physical_components_pending) && summary.physical_components_pending.length === pending.length
      && new Set(summary.physical_components_pending).size === pending.length && pending.every(key => summary.physical_components_pending.includes(key))
      && summary.camera_role === "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
      && summary.controller_feedback_role === "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT";
    if (!valid) box.append(badge("NOT_VERIFIED"), element("p", "notice warning", "Reference summary is missing, inconsistent or exceeds display bounds. No zero residual, complete coverage or installed calibration is inferred; inspect the retained report."));
    else {
      box.append(heading("Nominal graph and injected-staleness coverage"), facts(summary.graph),
        element("p", "caption", "The 15 nominal artifacts are dependency fixtures. Detected stale edges describe deliberately injected failures, not measured calibration quality or physical closure."));
      const numeric = Object.fromEntries(Object.entries(summary.numeric).map(([key, value]) => [key, value === null ? "NOT_AVAILABLE" : value]));
      box.append(heading("Synthetic point fit and coordinate roundtrips"), facts(numeric),
        element("p", "caption", "Residuals use synthetic points and nominal FK/frame inputs. Small errors do not measure installed geometry, controller correlation, TCP or real targeting accuracy."));
      box.append(heading("Explicit target subset"));
      for (const device of ["keyboard", "phone"]) {
        const entry = summary.target_coverage[device];
        box.append(facts({device, selected_targets: entry.selected.join(", "), selected_count: entry.selected.length, catalog_total: entry.catalog_total}));
      }
      box.append(element("p", "notice warning", "Only two target coordinate roundtrips are represented: not all 75 keyboard/phone targets, no IK reachability, no route or collision qualification, and no physical typing/tapping acceptance."));
    }
    // These physical holds are intrinsic to this incapable presentation, not
    // derived from a passing synthetic report or from supplied status strings.
    box.append(heading("Eight physical reference components remain pending"));
    const components = element("ul", "stage-list");
    for (const name of pending) {
      const row = element("li"); row.append(element("span", "", human(name)), badge("PENDING")); components.append(row);
    }
    box.append(components, element("p", "notice warning", "Camera stages 6, 7 and 8 are DEPENDENCY_ONLY_NOT_NUMERIC_INPUT. Controller feedback is TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT: transport validity does not turn T105 fields into calibrated joints."),
      element("p", "caption", "Use the existing explicit collect, assess and exact review steps. No bootstrap importer or physical calibration control is provided here. Noncontact acceptance requires its own exact assessment; this reference rehearsal cannot accept it. Contact-dependent graph nodes are future requirements, not a physical closure granted by this rehearsal."));
    return box;
  }

  function validatedNoncontact(value) {
    // Pure presentation checks over retained data: no geometry loader, solver,
    // evidence reads or provider activation. Invalid summaries are withheld whole.
    const object = item => item !== null && typeof item === "object" && !Array.isArray(item);
    const exact = (item, keys) => object(item) && Object.keys(item).length === keys.length && keys.every(key => Object.hasOwn(item, key));
    const digest = item => typeof item === "string" && /^[0-9a-f]{64}$/.test(item);
    const id = item => typeof item === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(item);
    const ids = (item, max = 32) => Array.isArray(item) && item.length <= max && item.every(id) && new Set(item).size === item.length;
    const integer = item => Number.isSafeInteger(item);
    const count = (item, max) => integer(item) && item >= 0 && item <= max;
    const shortText = item => typeof item === "string" && item.length > 0 && !/[\u0000-\u001f\u007f]/u.test(item) && new TextEncoder().encode(item).length <= 512;
    if (!exact(value, ["stage", "evaluation_sha256", "selected_inputs_sha256", "outcome", "checks", "provenance", "physical_authority", "meaning", "safe_summary"])
      || value.stage !== "noncontact_acceptance" || value.outcome !== "BLOCKED" || value.physical_authority !== false
      || !digest(value.evaluation_sha256) || !digest(value.selected_inputs_sha256) || !shortText(value.meaning)
      || !object(value.provenance) || compactCheckData(value.provenance) === null
      || !Array.isArray(value.checks) || value.checks.length < 1 || value.checks.length > 16
      || !value.checks.every(row => exact(row, ["check_id", "check_kind", "passed", "observed", "meaning"])
        && id(row.check_id) && ["NOMINAL", "EXPECTED_FAULT", "INVARIANT"].includes(row.check_kind)
        && typeof row.passed === "boolean" && shortText(row.meaning) && compactCheckData(row.observed) !== null)
      || new Set(value.checks.map(row => row.check_id)).size !== value.checks.length
      || !value.checks.some(row => row.check_kind === "NOMINAL" && row.passed === false)) return null;
    const s = value.safe_summary;
    if (!exact(s, ["schema", "nominal_readiness", "collision_historical", "static_geometry", "accuracy", "selection", "dependencies", "not_evaluated", "physical_authority"])
      || s.schema !== "rocell.rehearsal_noncontact_summary.v1" || s.nominal_readiness !== "BLOCKED" || s.physical_authority !== false) return null;
    const h = s.collision_historical, g = s.static_geometry, a = s.accuracy, selected = s.selection, d = s.dependencies;
    if (!exact(h, ["scope", "status", "required_body_count", "proxy_body_count", "urdf_collision_element_count", "missing_body_ids", "unknown_body_ids"])
      || h.scope !== "HISTORICAL_EYE_ON_ARM" || h.status !== "COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE"
      || h.required_body_count !== 19 || !count(h.proxy_body_count, 19) || !count(h.urdf_collision_element_count, 100000)
      || !ids(h.missing_body_ids, 19) || !ids(h.unknown_body_ids, 19)
      || !exact(g, ["status", "required_body_count", "required_source_count", "missing_geometry_body_ids", "missing_source_keys"])
      || g.status !== "NOT_EVALUATED" || g.required_body_count !== 26 || g.required_source_count !== 9
      || !ids(g.missing_geometry_body_ids, 26) || g.missing_geometry_body_ids.length !== 26
      || !ids(g.missing_source_keys, 9)
      || !exact(a, ["status", "unit", "unmeasured_term_ids", "conservative_error_micrometers", "remaining_margin_micrometers", "controls"])
      || a.status !== "BLOCKED_UNBOUNDED" || a.unit !== "micrometers" || !ids(a.unmeasured_term_ids, 10) || a.unmeasured_term_ids.length !== 10
      || a.conservative_error_micrometers !== null || a.remaining_margin_micrometers !== null
      || !Array.isArray(a.controls) || a.controls.length !== 6) return null;
    const control = row => {
      if (!exact(row, ["case_id", "disposition", "blocking_term_ids", "conservative_error_micrometers", "eroded_target_radius_micrometers", "remaining_margin_micrometers"])
        || !id(row.case_id) || !ids(row.blocking_term_ids, 10) || !integer(row.eroded_target_radius_micrometers)) return false;
      if (row.disposition === "BLOCKED_UNBOUNDED") return row.conservative_error_micrometers === null && row.remaining_margin_micrometers === null && row.blocking_term_ids.length > 0;
      if (!["BLOCKED_TARGET_MARGIN", "DIAGNOSTIC_FITS_ZERO_AUTHORITY"].includes(row.disposition)
        || !count(row.conservative_error_micrometers, Number.MAX_SAFE_INTEGER) || !integer(row.remaining_margin_micrometers) || row.blocking_term_ids.length !== 0) return false;
      return row.disposition !== "DIAGNOSTIC_FITS_ZERO_AUTHORITY" || (row.eroded_target_radius_micrometers > 0 && row.remaining_margin_micrometers >= 0);
    };
    if (!a.controls.every(control) || JSON.stringify(a.controls.map(row => row.case_id)) !== JSON.stringify(["real_unmeasured", "missing_term", "stale_term", "domain_term", "target_margin", "finite_control"])
      || a.controls[0].disposition !== "BLOCKED_UNBOUNDED" || a.controls[0].blocking_term_ids.length !== 10
      || !exact(selected, ["domain", "tool_case_id", "target_scope", "keyboard_targets_evaluated", "keyboard_catalog_total", "phone_targets_evaluated", "phone_catalog_total"])
      || selected.domain !== "NOMINAL_SOURCE_GEOMETRY" || !id(selected.tool_case_id) || selected.target_scope !== "NO_TARGET_REACHABILITY_EVALUATED"
      || selected.keyboard_targets_evaluated !== 0 || selected.phone_targets_evaluated !== 0 || selected.keyboard_catalog_total !== 46 || selected.phone_catalog_total !== 29
      || !exact(d, ["reference_binding_sha256", "reference_evidence_sha256", "predecessor_receipt_sha256", "predecessor_assessment_sha256", "predecessor_review_sha256", "camera_role", "feedback_role"])
      || !["reference_binding_sha256", "reference_evidence_sha256", "predecessor_receipt_sha256", "predecessor_assessment_sha256", "predecessor_review_sha256"].every(key => digest(d[key]))
      || d.camera_role !== "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT" || d.feedback_role !== "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT"
      || JSON.stringify(s.not_evaluated) !== JSON.stringify(["POSE", "ROUTE", "SENSITIVITY", "VISIBILITY", "DYNAMICS", "PHYSICAL_MOTION"])) return null;
    return value;
  }

  function retainedNoncontact(projection) {
    const title = "Retained noncontact readiness gaps";
    const limitations = "No power, movement or contact is authorized. This is a no-device readiness report, not a move button, physical acceptance or stage-15 handoff.";
    const value = validatedNoncontact(projection);
    if (value === null) {
      const box = element("div", "retained-evaluation");
      box.append(heading(title), element("p", "notice warning", limitations), badge("NOT_VERIFIED"),
        element("p", "notice warning", "Noncontact projection is missing, inconsistent or exceeds display bounds. Readiness remains held; no partial passing checks or raw technical reports are displayed."));
      return box;
    }
    const box = retainedArmChecks(value, title, ["noncontact_acceptance"], limitations);
    const s = value.safe_summary, h = s.collision_historical, g = s.static_geometry, a = s.accuracy;
    // Literal identities/narratives are never humanized: underscores, signs
    // and original dependency hashes must survive presentation unchanged.
    const literal = values => { const list = element("dl", "facts"); for (const [key, item] of Object.entries(values)) list.append(element("dt", "", human(key)), element("dd", "", item === null ? "NOT_AVAILABLE" : String(item))); return list; };
    const inventory = (label, values) => { const section = element("details"); section.append(element("summary", "", `${label} (${values.length})`)); const list = element("ul"); for (const item of values) list.append(element("li", "", item)); section.append(list); return section; };
    box.append(heading("Nominal build readiness"), badge("BLOCKED"), element("p", "notice warning", "Successful synthetic fault/control checks cannot close missing installed geometry or unmeasured accuracy. A review records the blockage; it cannot advance to handoff."));
    box.append(heading("Historical collision audit — eye-on-arm only"), literal({scope: h.scope, status: h.status, required_body_count: h.required_body_count, proxy_body_count: h.proxy_body_count, urdf_collision_element_count: h.urdf_collision_element_count}),
      inventory("Missing historical bodies", h.missing_body_ids), inventory("Unknown historical bodies", h.unknown_body_ids),
      element("p", "caption", "The historical 19-body audit and nominal AABB proxies are not the updated static B0477 geometry or installed clearance."));
    box.append(heading("Separate static-camera geometry requirements"), literal({status: g.status, required_body_count: g.required_body_count, required_source_count: g.required_source_count}),
      inventory("Missing static geometry bodies", g.missing_geometry_body_ids), inventory("Missing static geometry source bindings", g.missing_source_keys),
      element("p", "caption", "All 26 static body requirements and nine source identities need their own complete geometry contract. Retained source-design hashes are not installed geometry; the missing-source list is separate from the required-source count. Names do not create measured shapes; pose and sweep clearance were not evaluated."));
    box.append(heading("Real-build accuracy — UNBOUNDED"), literal({status: a.status, unit: a.unit, conservative_error_micrometers: null, remaining_margin_micrometers: null}), inventory("Unmeasured real-build terms", a.unmeasured_term_ids),
      literal({...a.controls[0], blocking_term_ids: a.controls[0].blocking_term_ids.join(", ")}),
      element("p", "notice warning", "Missing bounds are NOT_AVAILABLE, never zero. The real_unmeasured calculation uses a synthetic target boundary to expose missing measurements; no target-specific safe geometry or measured accuracy is qualified."));
    box.append(heading("Separate synthetic accuracy controls"), element("p", "caption", "These fixed typed calculator cases use synthetic inputs, not the installed keyboard or phone. Finite sums and signed margins belong only to those controls; a finite control does not bound the real build."));
    for (const row of a.controls.slice(1)) box.append(literal({...row, blocking_term_ids: row.blocking_term_ids.join(", ") || "NONE"}));
    box.append(heading("Actual selected nominal domain and tool"), literal(s.selection),
      element("p", "caption", "No target reachability was evaluated: 0 of 46 keyboard targets and 0 of 29 phone targets. No passing UNMEASURED_SENSITIVITY_OVERLAY was substituted for this nominal selection."));
    box.append(heading("Original reviewed stage-13 dependencies"), literal(s.dependencies),
      element("p", "caption", "Exact reviewed dependency identities are retained, not new measurements. Camera evidence is DEPENDENCY_ONLY_NOT_NUMERIC_INPUT; controller feedback is TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT. No T105 fields become calibrated joints."));
    box.append(heading("Not evaluated by this report"));
    for (const axis of s.not_evaluated) box.append(literal({axis, status: "NOT_EVALUATED"}));
    box.append(element("p", "notice warning", "Zero actual device opens, acquired camera frames, serial writes, robot motions and contacts. No virtual route or plant ran in this slice. NC-02/NC-03 and all physical release gates remain open requirements."),
      element("p", "caption", "Use the existing explicit collect, assess and exact review steps. Export the original retained evidence for development review. Rendering, polling and export never rerun a diagnostic or accept stage 14."));
    return box;
  }

  function validatedCameraProcess(value) {
    // Validate only a bounded cached projection. Rendering cannot acquire a
    // frame, reverify files, resume a child or turn a fixture into authority.
    const object = item => item !== null && typeof item === "object" && !Array.isArray(item);
    const exact = (item, keys) => object(item) && Object.keys(item).length === keys.length && keys.every(key => Object.hasOwn(item, key));
    const digest = item => typeof item === "string" && /^[a-f0-9]{64}$/.test(item);
    const identifier = item => typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$/.test(item);
    const count = item => Number.isSafeInteger(item) && item >= 0;
    const boundedText = (item, maximum) => typeof item === "string" && item.length > 0
      && !/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(item) && new TextEncoder().encode(item).length <= maximum;
    const codes = item => Array.isArray(item) && item.length <= 16
      && item.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,127}$/.test(code));
    if (!exact(value, ["schema", "status", "evidence_sha256", "binding", "process", "native", "capture", "blockers", "device_cleanup_proven", "physical_authority", "qualified", "meaning"])
      || value.schema !== "rocell.rehearsal_owned_camera_summary.v1"
      || !["RETAINED_COMPLETE_REHEARSAL", "RETAINED_INCOMPLETE_REHEARSAL"].includes(value.status)
      || !digest(value.evidence_sha256) || !boundedText(value.meaning, 512) || !codes(value.blockers)
      || value.device_cleanup_proven !== false || value.physical_authority !== false || value.qualified !== false
      || !exact(value.binding, ["session_id", "attempt_id", "source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256", "settings_epoch"])
      || !["session_id", "attempt_id"].every(key => identifier(value.binding[key]))
      || !["source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256", "settings_epoch"].every(key => digest(value.binding[key]))) return null;
    const process = value.process, native = value.native, capture = value.capture;
    if (process !== null && (!exact(process, ["status", "created", "resumed", "tree_exit_confirmed", "cleanup_errors", "cleanup_error_count", "cleanup_errors_omitted", "primary_error", "returncode", "stdout_bytes", "stderr_bytes", "request_sha256"])
      || !["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(process.status)
      || !["created", "resumed", "tree_exit_confirmed"].every(key => typeof process[key] === "boolean")
      || !Array.isArray(process.cleanup_errors) || process.cleanup_errors.length > 16 || !process.cleanup_errors.every(code => boundedText(code, 128))
      || !count(process.cleanup_error_count) || !count(process.cleanup_errors_omitted)
      || process.cleanup_error_count !== process.cleanup_errors.length + process.cleanup_errors_omitted
      || !(process.primary_error === null || boundedText(process.primary_error, 128))
      || !(process.returncode === null || (Number.isSafeInteger(process.returncode) && process.returncode >= -(2 ** 31) && process.returncode <= 2 ** 32 - 1))
      || !count(process.stdout_bytes) || process.stdout_bytes > 32768 || !count(process.stderr_bytes) || process.stderr_bytes > 8192
      || !digest(process.request_sha256) || (process.resumed && !process.created))) return null;
    const nativeBounds = {source_activation_attempts: 1, source_opened: 1, source_shutdown_attempts: 1, control_set_attempts: 6, samples_received: 100000, frames_written: 32};
    const nativeKeys = Object.keys(nativeBounds);
    if (native !== null && (!exact(native, ["receipt_valid", "status", "cleanup_confirmed", "counts", "frame_count"])
      || !["receipt_valid", "cleanup_confirmed"].every(key => typeof native[key] === "boolean")
      || !["OK", "FAILED"].includes(native.status) || !exact(native.counts, nativeKeys)
      || !nativeKeys.every(key => count(native.counts[key]) && native.counts[key] <= nativeBounds[key]) || !count(native.frame_count) || native.frame_count > 32)) return null;
    if (capture !== null && (!exact(capture, ["metadata_binding_valid", "manifest_sha256", "plan_sha256", "envelope_sha256", "source_contract_sha256", "frames", "logical_bytes"])
      || typeof capture.metadata_binding_valid !== "boolean"
      || !["manifest_sha256", "plan_sha256", "envelope_sha256", "source_contract_sha256"].every(key => digest(capture[key]))
      || !count(capture.frames) || capture.frames > 32 || !count(capture.logical_bytes))) return null;
    if (value.status === "RETAINED_COMPLETE_REHEARSAL" && (!process || process.status !== "SUCCEEDED" || !process.created || !process.resumed
      || !process.tree_exit_confirmed || process.primary_error !== null || process.cleanup_error_count !== 0 || process.returncode !== 0
      || !native || !native.receipt_valid || native.status !== "OK" || !native.cleanup_confirmed || native.frame_count < 1
      || !capture || !capture.metadata_binding_valid || capture.frames !== native.frame_count || capture.logical_bytes < 1 || value.blockers.length !== 0)) return null;
    return value;
  }

  function retainedCameraProcess(projection) {
    const box = element("section", "retained-camera-process");
    box.append(heading("Contained camera-process rehearsal"), element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED"),
      element("p", "notice warning", "All pixels are source-derived incapable fixtures, not physical camera frames. Process exit is not physical device cleanup. No received camera, driver, USB3 link or capture backend is qualified."));
    const value = validatedCameraProcess(projection);
    if (!value) {
      box.append(badge("CAMERA_PROCESS_NOT_VERIFIED"), element("p", "notice warning", "The cached process summary is missing, inconsistent or exceeds display bounds. Inspect diagnostics; do not infer completion or replay the campaign."));
      return box;
    }
    box.append(element("span", "badge hold", human(value.status)), facts({evidence_sha256: value.evidence_sha256, ...value.binding}), element("p", "caption", value.meaning));
    box.append(heading("Actual child-process containment and cleanup"));
    if (!value.process) box.append(badge("PROCESS_EVIDENCE_MISSING"));
    else box.append(facts(value.process), element("p", "caption", "Created, resumed and tree-exit-confirmed describe the owned OS process only. Byte counters are retained output lengths; no child output, commands or raw paths are shown."));
    box.append(heading("Synthetic native receipt and cleanup"));
    if (!value.native) box.append(badge("SYNTHETIC_NATIVE_RECEIPT_MISSING"));
    else box.append(element("span", "badge hold", "SYNTHETIC_ONLY_NOT_DEVICE_CLEANUP"), facts(value.native),
      element("p", "caption", "Native counters and cleanup describe the incapable fixture contract only. An OK receipt cannot override a failed, cancelled or timed-out process."));
    box.append(heading("Retained frame metadata references"));
    if (!value.capture) box.append(badge("CAPTURE_METADATA_MISSING"));
    else box.append(facts(value.capture));
    box.append(element("p", "caption", "Metadata binding is not file-content verification. Reopening requires the backend's separate retained-content verification. This card does not load a preview; use the Camera page's current image provenance separately."));
    if (value.blockers.length) box.append(heading("Retained campaign holds"), facts({blockers: value.blockers}));
    box.append(facts({device_cleanup_proven: false, physical_authority: false, qualified: false}),
      element("p", "notice warning", "No automatic discovery, replay, process restart or new camera action follows from this display. Use an eligible explicit action preview and exact confirmation only."));
    return box;
  }

  function validatedArmResolution(value, owner) {
    // Only the producer's compact summary is accepted. Never parse raw trace
    // records, acquire metadata, or recompute a controller match in the UI.
    const v = cameraConfigurationValidators();
    const errors = ["REVIEWED_CONTROLLER_CHANGED", "CONTROLLER_RESOLUTION_CANCELLED", "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK", "CONTROLLER_METADATA_NOT_FRESH", "CONTROLLER_METADATA_HELD", "INVALID_CONTROLLER_METADATA", "CONTROLLER_METADATA_BYTE_LIMIT", "CONTROLLER_METADATA_ACQUISITION_FAILED", "CONTROLLER_RESOLUTION_INTERRUPTED", "CM_PROPERTY_STRING_INVALID", "CM_PROPERTY_TYPE_OR_SIZE_INVALID", "CM_LIST_INVALID", "CM_LIST_AMBIGUOUS_OR_OVER_LIMIT", "CM_LIST_CHANGED"];
    const limitations = ["METADATA_SNAPSHOT_NOT_ATOMIC_COM_TO_HANDLE_BINDING", "GENERIC_UNIT_SERIAL_NOT_USB_DESCRIPTOR_VERIFICATION", "ARM_MODEL_FIRMWARE_BOOT_AND_POWER_NOT_OBSERVED", "PHYSICAL_BACKEND_AND_RELEASE_REMAIN_HELD"];
    if (!v.exact(value, ["schema", "trace_sha256", "reviewed_binding_sha256", "origin", "attempt_count", "attempts", "status", "physical_authority", "arm_connected", "qualified", "limitations"])
      || value.schema !== "rocell.arm_controller_resolution_trace_summary.v1" || !v.digest(value.trace_sha256) || !v.digest(value.reviewed_binding_sha256)
      || value.origin !== (owner.provenance === "INCAPABLE_NONPURGING_ARM_WORKER" ? "SYNTHETIC_REHEARSAL" : "PHYSICAL_OBSERVATION")
      || !["physical_authority", "arm_connected", "qualified"].every(key => value[key] === false)
      || !v.integer(value.attempt_count, 0, 2) || !Array.isArray(value.attempts) || value.attempts.length !== value.attempt_count
      || JSON.stringify(value.limitations) !== JSON.stringify(limitations)
      || (owner.native && value.reviewed_binding_sha256 !== owner.native.controller_binding_sha256)) return null;
    for (let index = 0; index < value.attempts.length; index++) {
      const row = value.attempts[index];
      if (!v.exact(row, ["phase", "status", "snapshot_sha256", "resolution_sha256", "error_code"])
        || row.phase !== ["PRE_OPEN", "PRE_WRITE"][index] || !["MATCHED_METADATA_ONLY", "HELD"].includes(row.status)
        || !["snapshot_sha256", "resolution_sha256"].every(key => row[key] === null || v.digest(row[key]))
        || (row.resolution_sha256 !== null && row.snapshot_sha256 === null)
        || (row.status === "MATCHED_METADATA_ONLY" ? !row.snapshot_sha256 || !row.resolution_sha256 || row.error_code !== null : !errors.includes(row.error_code))
        || (index === 1 && value.attempts[0].status !== "MATCHED_METADATA_ONLY")) return null;
    }
    const expected = !value.attempts.length ? "NOT_ATTEMPTED" : value.attempts.some(row => row.status === "HELD") ? "HELD" : value.attempts.length === 1 ? "PRE_OPEN_MATCHED" : "PRE_WRITE_MATCHED";
    return value.status === expected ? value : null;
  }

  function retainedArmResolution(owner) {
    const box = element("section", "retained-arm-resolution");
    box.append(heading("Controller metadata checks before open and before write"));
    if (owner.schema === "rocell.arm_owned_evidence_summary.v1") {
      box.append(element("p", "notice warning", "NOT_RETAINED — historical record format contains no two-boundary resolution trace. Do not infer these checks ran or replay the attempt to fill the gap."));
      return box;
    }
    const value = owner.resolution;
    if (value === null) {
      box.append(element("p", "notice warning", "NOT_RETAINED — current-format result has no verified resolution trace. Missing trace is not a metadata match; inspect retained diagnostics without replay."));
      return box;
    }
    box.append(element("p", "notice warning", value.origin === "SYNTHETIC_REHEARSAL" ? "SYNTHETIC ONLY: fresh fixture acquisitions test the resolver, not a received controller or Windows device identity." : "PHYSICAL BACKEND HELD: retained metadata context does not qualify a controller or authorize connection."),
      element("p", "", `Trace status: ${value.status}`), element("p", "", `trace_sha256: ${value.trace_sha256}`), element("p", "", `reviewed_binding_sha256: ${value.reviewed_binding_sha256}`));
    for (const phase of ["PRE_OPEN", "PRE_WRITE"]) {
      const row = value.attempts.find(item => item.phase === phase);
      box.append(heading(phase === "PRE_OPEN" ? "PRE_OPEN — before serial open" : "PRE_WRITE — before the one feedback request"));
      if (!row) { box.append(element("p", "caption", "NOT_ATTEMPTED: no boundary attempt is retained.")); continue; }
      box.append(element("p", "", `Acquisition snapshot: ${row.snapshot_sha256 ? "RETAINED" : "NOT_RETAINED"}`),
        element("p", "", `Metadata comparison report: ${row.resolution_sha256 ? "RETAINED" : "NOT_RETAINED"}`), element("p", "", `Boundary result: ${row.status}`));
      if (row.snapshot_sha256) box.append(element("p", "", `snapshot_sha256: ${row.snapshot_sha256}`));
      if (row.resolution_sha256) box.append(element("p", "", `resolution_sha256: ${row.resolution_sha256}`));
      if (row.error_code) box.append(element("p", "notice warning", `Retained refusal: ${row.error_code}`));
    }
    box.append(element("p", "caption", "A retained hash identifies evidence, not an independent successful acquisition or match. Separate checks do not establish atomic COM-to-handle identity, USB serial-descriptor identity, model, firmware, boot or power. Physical backend and release remain held."));
    return box;
  }

  function validatedArmProcess(value) {
    // Display only: completeness of retained records is not transaction success
    // and cannot grant native device, process, or physical-power authority.
    const exact = (v, keys) => v !== null && typeof v === "object" && !Array.isArray(v)
      && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
    const text = (v, max = 128) => typeof v === "string" && v.length > 0 && !/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(v) && new TextEncoder().encode(v).length <= max;
    const hash = v => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
    const count = (v, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(v) && v >= 0 && v <= max;
    const codes = (v, max = 16) => Array.isArray(v) && v.length <= max && v.every(item => text(item));
    const states = ["SUCCEEDED_DIAGNOSTIC", "BLOCKED_PRE_OPEN", "CANCELLED_PRE_OPEN", "FAILED_UNCERTAIN"];
    const held = v => v.physical_authority === false && v.arm_connected === false && v.device_cleanup_proven === false && v.final_power_state === "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION";
    const versionTwo = value?.schema === "rocell.arm_owned_evidence_summary.v2";
    if (!exact(value, ["schema", "status", "provenance", "session_id", "attempt_id", "source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256", "worker_registration_sha256", "request_sha256", "inner_request_sha256", "evidence_sha256", "process", "handshake", "feedback", "native", "blockers", "physical_authority", "arm_connected", "device_cleanup_proven", "final_power_state", "meaning", ...(versionTwo ? ["resolution"] : [])])
      || !["rocell.arm_owned_evidence_summary.v1", "rocell.arm_owned_evidence_summary.v2"].includes(value.schema) || !["COMPLETE_INCAPABLE_EVIDENCE", "INCOMPLETE", "PHYSICAL_HELD"].includes(value.status)
      || !["INCAPABLE_NONPURGING_ARM_WORKER", "PHYSICAL_NONPURGING_ARM_HELD"].includes(value.provenance) || !held(value) || !text(value.meaning, 512)
      || !["session_id", "attempt_id"].every(k => typeof value[k] === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/.test(value[k]))
      || !["source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256", "worker_registration_sha256", "request_sha256", "inner_request_sha256", "evidence_sha256"].every(k => hash(value[k]))
      || !codes(value.blockers)) return null;
    const p = value.process, h = value.handshake, f = value.feedback, n = value.native;
    if (!exact(p, ["status", "process_created", "initial_thread_resumed", "tree_exit_confirmed", "returncode", "primary_error", "cleanup_errors", "cleanup_error_count", "cleanup_errors_omitted", "stdin_bytes_written", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"])
      || !["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(p.status) || !["process_created", "initial_thread_resumed", "tree_exit_confirmed"].every(k => typeof p[k] === "boolean")
      || (p.initial_thread_resumed && !p.process_created) || !(p.returncode === null || count(p.returncode, 2 ** 32 - 1))
      || !(p.primary_error === null || text(p.primary_error)) || !codes(p.cleanup_errors)
      || !["cleanup_error_count", "cleanup_errors_omitted", "stdin_bytes_written", "stdout_bytes", "stderr_bytes"].every(k => count(p[k]))
      || p.cleanup_error_count !== p.cleanup_errors.length + p.cleanup_errors_omitted || !hash(p.stdout_sha256) || !hash(p.stderr_sha256)
      || !exact(h, ["ready_retained", "release_retained", "child_pid"]) || typeof h.ready_retained !== "boolean" || typeof h.release_retained !== "boolean"
      || !(h.child_pid === null || (count(h.child_pid, 2 ** 32 - 1) && h.child_pid > 0)) || (h.release_retained && !h.ready_retained)) return null;
    if (f !== null && (!exact(f, ["status", "technical_response_valid", "connection_closed", "response_bytes", "response_sha256", "unexpected_bytes", "unexpected_sha256", "unexpected_bytes_unretained"])
      || !states.includes(f.status) || typeof f.technical_response_valid !== "boolean" || typeof f.connection_closed !== "boolean"
      || !["response_bytes", "unexpected_bytes", "unexpected_bytes_unretained"].every(k => count(f[k])) || !hash(f.response_sha256) || !hash(f.unexpected_sha256))) return null;
    if (n !== null) {
      const issue = v => exact(v, ["code", "operation", "winerror"]) && typeof v.code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(v.code)
        && typeof v.operation === "string" && /^[a-z][a-z0-9_:]{0,63}$/.test(v.operation) && count(v.winerror, 2 ** 32 - 1);
      if (!exact(n, ["schema", "evidence_sha256", "request_sha256", "controller_binding_sha256", "worker_result_sha256", "worker_status", "native_cleanup_confirmed", "resource_counts", "pending_io_unresolved", "startup_input_observed", "native_primary_error", "native_cleanup_errors", "late_read_bytes", "late_read_sha256", "physical_authority", "arm_connected", "device_cleanup_proven", "final_power_state", "physical_hold", "meaning"])
        || n.schema !== "rocell.arm_native_lifecycle_summary.v1" || !held(n) || !states.includes(n.worker_status)
        || !["evidence_sha256", "request_sha256", "controller_binding_sha256", "worker_result_sha256", "late_read_sha256"].every(k => hash(n[k]))
        || !["native_cleanup_confirmed", "pending_io_unresolved", "startup_input_observed"].every(k => n[k] === null || typeof n[k] === "boolean")
        || !(n.native_primary_error === null || issue(n.native_primary_error)) || !Array.isArray(n.native_cleanup_errors) || n.native_cleanup_errors.length > 8 || !n.native_cleanup_errors.every(issue)
        || !count(n.late_read_bytes, 1024) || !text(n.physical_hold, 512) || !text(n.meaning, 512)) return null;
      const r = n.resource_counts;
      if (r !== null && (!exact(r, ["acquired", "close_attempted", "close_confirmed", "unresolved"]) || !Object.values(r).every(v => count(v, 3))
        || r.acquired !== r.close_confirmed + r.unresolved || r.close_confirmed > r.close_attempted || r.close_attempted > r.acquired)) return null;
    }
    if (versionTwo && value.resolution !== null && !validatedArmResolution(value.resolution, value)) return null;
    if (value.status === "COMPLETE_INCAPABLE_EVIDENCE" && (!f || !n || !h.ready_retained || !h.release_retained || (versionTwo && value.resolution === null)
      || value.provenance !== "INCAPABLE_NONPURGING_ARM_WORKER")) return null;
    return value;
  }

  function retainedArmProcess(projection) {
    const box = element("section", "retained-arm-process");
    box.append(heading("Contained arm-feedback rehearsal"), element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED"),
      element("p", "notice warning", "The child is an actual owned process; serial behavior uses a sealed incapable Win32 model, not a physical controller. Received identity, firmware and power remain unverified."));
    const value = validatedArmProcess(projection);
    if (!value) {
      box.append(badge("ARM_PROCESS_NOT_VERIFIED"), element("p", "notice warning", "The cached summary is missing, inconsistent or exceeds display bounds. Inspect diagnostics; do not infer completion or replay."));
      return box;
    }
    box.append(element("span", "badge hold", human(value.status)), facts(value, ["process", "handshake", "feedback", "native", "resolution", "meaning"]), element("p", "caption", value.meaning),
      element("p", "notice warning", "Complete evidence means records were retained, not that feedback, cleanup or a physical power state passed."),
      heading("Actual child-process containment and cleanup"), facts(value.process),
      heading("Retained admission records — not proof RELEASE was sent"), facts(value.handshake),
      element("p", "caption", "Release retained means planned/retained bytes. A final authorization denial can prevent sending them; inspect stdin byte counts and the verified child result separately."),
      retainedArmResolution(value),
      heading("Modeled serial feedback validity"), value.feedback ? facts(value.feedback) : badge("FEEDBACK_EVIDENCE_MISSING"),
      heading("Modeled non-purging native-owner cleanup"), value.native ? facts(value.native) : badge("NATIVE_OWNER_EVIDENCE_MISSING"),
      element("p", "notice warning", "Process tree exit, native handle cleanup and serial close are separate. None proves physical de-energization. The worker final power remains UNKNOWN_REQUIRES_SEPARATE_OBSERVATION; inspect the independent synthetic observer in the stage assessment."),
      element("p", "caption", "Only counts and hashes are displayed. Raw serial and child bytes stay in private retained evidence. No automatic restart, replay, fallback, discovery or command follows from this card."));
    return box;
  }

  function cameraConfigurationValidators() {
    // Cached display contracts only. Hashes identify retained reports; these
    // structural checks neither replace evidence verification nor apply a knob.
    const ids = ["exposure", "gain", "white_balance", "brightness", "contrast", "saturation"];
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    const identifier = value => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$/.test(value);
    const string = (value, limit) => typeof value === "string" && value.length > 0
      && !/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(value) && new TextEncoder().encode(value).length <= limit;
    const integer = (value, low = -(2 ** 31), high = 2 ** 31 - 1) => Number.isSafeInteger(value) && low <= value && value <= high;
    const mode = value => exact(value, ["width", "height", "fps_numerator", "fps_denominator", "subtype", "stride_bytes"])
      && ["width", "height"].every(key => integer(value[key], 1, 16384))
      && ["fps_numerator", "fps_denominator"].every(key => integer(value[key], 1, 1000000))
      && string(value.subtype, 64) && (value.stride_bytes === null || (integer(value.stride_bytes, -1048576, 1048576) && value.stride_bytes !== 0));
    const sameMode = (left, right) => mode(left) && mode(right) && Object.keys(left).every(key => left[key] === right[key]);
    const observation = value => exact(value, ["control_id", "minimum", "maximum", "step", "default", "capability_flags", "value", "flags", "unit"])
      && ids.includes(value.control_id) && ["minimum", "maximum", "default", "value"].every(key => integer(value[key]))
      && integer(value.step, 1) && integer(value.capability_flags, 1, 3) && integer(value.flags, 1, 3)
      && value.minimum <= value.default && value.default <= value.maximum && value.minimum <= value.value && value.value <= value.maximum && string(value.unit, 64);
    const requested = value => exact(value, ["control_id", "value", "mode"]) && ids.includes(value.control_id)
      && integer(value.value) && ["auto", "manual"].includes(value.mode);
    const noAuthority = value => value.physical_authority === false && value.qualified === false;
    const binding = value => exact(value, ["session_id", "attempt_id", "source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256"])
      && identifier(value.session_id) && identifier(value.attempt_id)
      && ["source_sha256", "permit_sha256", "operation_sha256", "selected_identity_sha256"].every(key => digest(value[key]));
    const choice = value => typeof value === "string" && /^mode-[a-f0-9]{24}$/.test(value);
    function capabilities(value) {
      if (!exact(value, ["schema", "status", "capabilities_sha256", "probe_evidence_sha256", "binding", "endpoint_sha256", "modes", "controls", "unavailable_controls", "physical_authority", "qualified", "meaning"])
        || value.schema !== "rocell.camera_capabilities.v1" || value.status !== "REPORTED_REHEARSAL_ONLY" || !noAuthority(value)
        || !["capabilities_sha256", "probe_evidence_sha256", "endpoint_sha256"].every(key => digest(value[key])) || !binding(value.binding) || !string(value.meaning, 512)
        || !Array.isArray(value.modes) || value.modes.length > 128 || !Array.isArray(value.controls) || value.controls.length > 6
        || !value.controls.every(observation) || !Array.isArray(value.unavailable_controls) || value.unavailable_controls.length > 6 || !value.unavailable_controls.every(id => ids.includes(id))) return null;
      const partition = [...value.controls.map(item => item.control_id), ...value.unavailable_controls];
      if (partition.length !== 6 || new Set(partition).size !== 6 || new Set(value.modes.map(item => item?.choice_id)).size !== value.modes.length) return null;
      const modeHolds = ["UNSUPPORTED_PIXEL_FORMAT", "ODD_YUY2_WIDTH", "FRAME_BUDGET_EXCEEDED", "INVALID_REPORTED_STRIDE"];
      for (const item of value.modes) {
        if (!exact(item, ["choice_id", "mode", "selectable", "blockers"]) || !choice(item.choice_id) || !mode(item.mode)
          || typeof item.selectable !== "boolean" || !Array.isArray(item.blockers) || item.blockers.length > 4
          || !item.blockers.every(code => modeHolds.includes(code)) || new Set(item.blockers).size !== item.blockers.length
          || item.selectable !== (item.blockers.length === 0)
          || (item.selectable && (item.mode.subtype !== "YUY2" || item.mode.width % 2 !== 0))) return null;
        const expected = [];
        if (item.mode.subtype !== "YUY2") expected.push("UNSUPPORTED_PIXEL_FORMAT");
        if (item.mode.width % 2) expected.push("ODD_YUY2_WIDTH");
        if (item.mode.width * item.mode.height * 2 > 64 * 1024 * 1024) expected.push("FRAME_BUDGET_EXCEEDED");
        if (item.mode.stride_bytes !== null) {
          if (Math.abs(item.mode.stride_bytes) < item.mode.width * 2) expected.push("INVALID_REPORTED_STRIDE");
          else if (Math.abs(item.mode.stride_bytes) * item.mode.height > 64 * 1024 * 1024 && !expected.includes("FRAME_BUDGET_EXCEEDED")) expected.push("FRAME_BUDGET_EXCEEDED");
        }
        if (expected.length !== item.blockers.length || !expected.every(code => item.blockers.includes(code))) return null;
      }
      return value;
    }
    function candidate(value, caps) {
      if (!caps || !exact(value, ["schema", "status", "settings_epoch", "capabilities_sha256", "probe_evidence_sha256", "session_id", "source_sha256", "selected_identity_sha256", "endpoint_sha256", "mode_choice_id", "mode", "controls", "applied", "physical_authority", "qualified", "meaning"])
        || value.schema !== "rocell.camera_configuration.v1" || value.status !== "STAGED_NOT_APPLIED_REHEARSAL" || value.applied !== false || !noAuthority(value)
        || !digest(value.settings_epoch) || !string(value.meaning, 512) || !choice(value.mode_choice_id)
        || !["capabilities_sha256", "probe_evidence_sha256", "endpoint_sha256"].every(key => value[key] === caps[key])
        || !["session_id", "source_sha256", "selected_identity_sha256"].every(key => value[key] === caps.binding[key])
        || !Array.isArray(value.controls) || value.controls.length > 6 || !value.controls.every(requested)
        || new Set(value.controls.map(item => item.control_id)).size !== value.controls.length) return null;
      const selected = caps.modes.find(item => item.choice_id === value.mode_choice_id);
      if (!selected || !selected.selectable || !sameMode(value.mode, selected.mode)) return null;
      for (const item of value.controls) {
        const reported = caps.controls.find(row => row.control_id === item.control_id), flag = item.mode === "auto" ? 1 : 2;
        if (!reported || !(reported.capability_flags & flag) || item.value < reported.minimum || item.value > reported.maximum
          || (item.value - reported.minimum) % reported.step !== 0) return null;
      }
      return value;
    }
    const reasons = (value, allowed) => Array.isArray(value) && value.length <= allowed.length && value.every(code => allowed.includes(code)) && new Set(value).size === value.length;
    function probe(value) {
      if (!exact(value, ["schema", "status", "evidence_sha256", "binding", "process", "native", "blockers", "device_cleanup_proven", "physical_authority", "qualified", "meaning"])
        || value.schema !== "rocell.rehearsal_camera_probe_summary.v1" || !["COMPLETE_PROBE_REHEARSAL", "INCOMPLETE_PROBE_REHEARSAL"].includes(value.status)
        || !digest(value.evidence_sha256) || !binding(value.binding) || !noAuthority(value) || value.device_cleanup_proven !== false || !string(value.meaning, 512)
        || !Array.isArray(value.blockers) || value.blockers.length > 16 || !value.blockers.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,127}$/.test(code))) return null;
      const p = value.process, n = value.native;
      if (p !== null && (!exact(p, ["status", "created", "resumed", "tree_exit_confirmed", "cleanup_errors", "cleanup_error_count", "cleanup_errors_omitted", "primary_error", "returncode", "stdout_bytes", "stderr_bytes", "request_sha256"])
        || !["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(p.status) || !["created", "resumed", "tree_exit_confirmed"].every(key => typeof p[key] === "boolean")
        || (p.resumed && !p.created) || !Array.isArray(p.cleanup_errors) || p.cleanup_errors.length > 16 || !p.cleanup_errors.every(item => string(item, 128))
        || !integer(p.cleanup_error_count, 0, Number.MAX_SAFE_INTEGER) || !integer(p.cleanup_errors_omitted, 0, Number.MAX_SAFE_INTEGER)
        || p.cleanup_error_count !== p.cleanup_errors.length + p.cleanup_errors_omitted || !(p.primary_error === null || string(p.primary_error, 128))
        || !(p.returncode === null || integer(p.returncode, -(2 ** 31), 2 ** 32 - 1)) || !integer(p.stdout_bytes, 0, 32768) || !integer(p.stderr_bytes, 0, 8192) || !digest(p.request_sha256))) return null;
      const counts = ["source_activation_attempts", "source_opened", "source_shutdown_attempts", "control_set_attempts", "samples_received", "frames_written"];
      if (n !== null && (!exact(n, ["receipt_valid", "status", "cleanup_confirmed", "counts", "mode_count", "control_count"])
        || typeof n.receipt_valid !== "boolean" || typeof n.cleanup_confirmed !== "boolean" || !["OK", "FAILED"].includes(n.status)
        || !exact(n.counts, counts) || !counts.every(key => integer(n.counts[key], 0, key.startsWith("source_") ? 1 : 0))
        || !integer(n.mode_count, 0, 128) || !integer(n.control_count, 0, 6))) return null;
      if (value.status === "COMPLETE_PROBE_REHEARSAL" && (!p || p.status !== "SUCCEEDED" || !p.created || !p.resumed || !p.tree_exit_confirmed
        || p.cleanup_error_count !== 0 || p.primary_error !== null || p.returncode !== 0 || !n || !n.receipt_valid || n.status !== "OK" || !n.cleanup_confirmed
        || ["source_activation_attempts", "source_opened", "source_shutdown_attempts"].some(key => n.counts[key] !== 1) || value.blockers.length)) return null;
      return value;
    }
    function readback(value, config, caps) {
      const topReasons = ["CAPTURE_NOT_SUCCESSFULLY_CLOSED", "ENDPOINT_MISMATCH", "MODE_READBACK_MISMATCH", "CONTROL_READBACK_MISMATCH"];
      const rowReasons = ["CONTROL_READBACK_MISSING", "CONTROL_MODE_READBACK_MISMATCH", "MANUAL_VALUE_READBACK_MISMATCH", "CONTROL_CAPABILITY_DRIFT"];
      if (!config || !caps || !exact(value, ["schema", "status", "settings_epoch", "probe_evidence_sha256", "source_sha256", "selected_identity_sha256", "native_receipt_sha256", "requested_mode", "observed_mode", "mode_matched", "controls", "reasons", "physical_authority", "qualified", "meaning"])
        || value.schema !== "rocell.camera_readback.v1" || !["REQUESTED_SETTINGS_OBSERVED_REHEARSAL", "READBACK_MISMATCH_REHEARSAL"].includes(value.status)
        || !["settings_epoch", "probe_evidence_sha256", "source_sha256", "selected_identity_sha256"].every(key => value[key] === config[key])
        || !digest(value.native_receipt_sha256) || !sameMode(value.requested_mode, config.mode) || !(value.observed_mode === null || mode(value.observed_mode))
        || typeof value.mode_matched !== "boolean" || !reasons(value.reasons, topReasons) || !noAuthority(value) || !string(value.meaning, 512)
        || !Array.isArray(value.controls) || value.controls.length !== config.controls.length
        || value.mode_matched === value.reasons.includes("MODE_READBACK_MISMATCH")) return null;
      const actual = value.observed_mode, wanted = config.mode;
      if (value.mode_matched && (!actual || actual.width !== wanted.width || actual.height !== wanted.height || actual.subtype !== wanted.subtype
        || actual.fps_numerator * wanted.fps_denominator !== wanted.fps_numerator * actual.fps_denominator)) return null;
      for (let index = 0; index < value.controls.length; index++) {
        const row = value.controls[index], request = config.controls[index];
        if (!exact(row, ["control_id", "requested", "observed", "matched", "reasons"]) || row.control_id !== request.control_id
          || !exact(row.requested, ["value", "mode"]) || row.requested.value !== request.value || row.requested.mode !== request.mode
          || typeof row.matched !== "boolean" || !reasons(row.reasons, rowReasons) || row.matched !== (row.reasons.length === 0)) return null;
        const observed = row.observed;
        if (observed === null) { if (!row.reasons.includes("CONTROL_READBACK_MISSING")) return null; }
        else {
          const reported = caps.controls.find(item => item.control_id === row.control_id);
          if (!exact(observed, ["value", "flags", "unit"]) || !integer(observed.value) || !integer(observed.flags, 1, 3) || !string(observed.unit, 64)
            || row.reasons.includes("CONTROL_READBACK_MISSING")
            || (observed.flags !== (request.mode === "auto" ? 1 : 2)) !== row.reasons.includes("CONTROL_MODE_READBACK_MISMATCH")
            || (request.mode === "manual" && observed.value !== request.value) !== row.reasons.includes("MANUAL_VALUE_READBACK_MISMATCH")
            || (!row.reasons.includes("CONTROL_CAPABILITY_DRIFT") && (!reported || observed.unit !== reported.unit || observed.value < reported.minimum || observed.value > reported.maximum))) return null;
        }
      }
      if (value.controls.some(row => !row.matched) !== value.reasons.includes("CONTROL_READBACK_MISMATCH")
        || (value.status === "REQUESTED_SETTINGS_OBSERVED_REHEARSAL") !== (value.reasons.length === 0)) return null;
      return value;
    }
    function configuration(value) {
      if (!exact(value, ["schema", "status", "probe", "capabilities", "candidate", "readback", "physical_authority", "qualified", "meaning"])
        || value.schema !== "rocell.wizard_camera_configuration.v1" || !["PROBE_COMPLETE", "CONFIGURATION_STAGED", "READBACK_COMPLETE", "HELD"].includes(value.status)
        || !noAuthority(value) || !string(value.meaning, 512)) return null;
      const p = probe(value.probe), caps = value.capabilities === null ? null : capabilities(value.capabilities);
      if (!p || (value.capabilities !== null && !caps)) return null;
      if (caps && (p.status !== "COMPLETE_PROBE_REHEARSAL" || p.evidence_sha256 !== caps.probe_evidence_sha256
        || !Object.keys(p.binding).every(key => p.binding[key] === caps.binding[key]) || p.native.mode_count !== caps.modes.length || p.native.control_count !== caps.controls.length)) return null;
      const config = value.candidate === null ? null : candidate(value.candidate, caps), observed = value.readback === null ? null : readback(value.readback, config, caps);
      if ((value.candidate !== null && !config) || (value.readback !== null && !observed)) return null;
      if ((value.status === "PROBE_COMPLETE" && (!caps || config || observed))
        || (value.status === "CONFIGURATION_STAGED" && (!config || observed))
        || (value.status === "READBACK_COMPLETE" && (!observed || observed.status !== "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"))) return null;
      return value;
    }
    return {configuration, exact, digest, identifier, string, integer, mode, sameMode, observation, requested, choice};
  }

  function validatedCameraFault(value) {
    const v = cameraConfigurationValidators();
    const categories = {
      NONE: [null, "NONE"], CONTROL_READBACK_MISMATCH_REPORTED: ["INVALID_CAMERA_CONTRACT", "RETAINED_CALLER_ERROR_EXACT_MATCH"],
      PROCESS_CLEANUP_UNCONFIRMED: [null, "RETAINED_PROCESS_STATUS"], OPERATION_CANCELLED: ["CANCELLED", "RETAINED_PROCESS_STATUS"],
      OPERATION_TIMED_OUT: ["TIMED_OUT", "RETAINED_PROCESS_STATUS"], UNCLASSIFIED_CALLER_ERROR: ["UNCLASSIFIED", "RETAINED_VALIDATION_HOLD"],
      PROCESS_EXECUTION_UNCONFIRMED: [null, "RETAINED_PROCESS_STATUS"], REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE: [null, "RETAINED_VALIDATION_HOLD"],
      NATIVE_EVIDENCE_UNVERIFIED: [null, "RETAINED_VALIDATION_HOLD"], CAPTURE_RETENTION_UNVERIFIED: [null, "RETAINED_VALIDATION_HOLD"]
    };
    if (!v.exact(value, ["schema", "status", "evidence_sha256", "reason_category", "reported_code", "basis", "reason", "next_investigation", "retry_this_attempt_allowed", "automatic_retry_allowed", "clear_quarantine_allowed", "physical_authority", "qualified", "meaning"])
      || value.schema !== "rocell.camera_fault_diagnostic.v1" || !v.digest(value.evidence_sha256)
      || !Object.hasOwn(categories, value.reason_category) || !["reason", "next_investigation", "meaning"].every(key => v.string(value[key], 512))
      || !["retry_this_attempt_allowed", "automatic_retry_allowed", "clear_quarantine_allowed", "physical_authority", "qualified"].every(key => value[key] === false)) return null;
    const expected = categories[value.reason_category];
    return value.reported_code === expected[0] && value.basis === expected[1]
      && value.status === (value.reason_category === "NONE" ? "NO_REPORTED_FAULT" : "FAULT_REPORTED") ? value : null;
  }

  function retainedCameraFault(projection) {
    const box = element("section", "retained-camera-fault");
    box.append(heading("Retained camera fault explanation"));
    const value = validatedCameraFault(projection);
    if (!value) { box.append(element("p", "notice warning", "CAMERA_FAULT_NOT_VERIFIED: Malformed diagnostic projection withheld. Inspect retained diagnostics; no retry is inferred.")); return box; }
    box.append(element("span", "badge hold", human(value.status)), facts({reason_category: value.reason_category, reported_code: value.reported_code,
      basis: value.basis, evidence_sha256: value.evidence_sha256}), element("p", "", value.reason), heading("Next investigation"), element("p", "", value.next_investigation),
      element("p", "caption", value.meaning), element("p", "notice warning", "Historical retained explanation, not a current observation or authorization. No automatic retry, same-attempt replay or quarantine clearing. A reported settings rejection does not establish observed control values."));
    return box;
  }

  function cameraRuntimeReviewProjection(value, source, launch = null) {
    // Display a closed cached summary only. Never inspect files or validate a
    // runtime by executing it; the retained verifier and admission own that.
    const v = cameraConfigurationValidators(), flags = ["dispatch_enabled", "driver_qualified", "hardware_qualified", "connected", "physical_authority"];
    const held = item => flags.every(key => item[key] === false);
    const label = item => typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(item);
    const paths = new Set([
      "CMakeLists.txt", "camera_worker.cpp", "identity_metadata.cpp", "identity_metadata.h", "admission_entry.cpp", "admission_entry.h", "admission_entry_tests.cpp",
      "admission_protocol.cpp", "admission_protocol.h", "admission_protocol_tests.cpp", "capture_admission_entry.cpp", "capture_admission_entry.h", "capture_admission_entry_tests.cpp",
      "capture_admission_protocol.cpp", "capture_admission_protocol.h", "capture_admission_protocol_tests.cpp", "capture/CMakeLists.txt", "capture/admission_entry_wire_test.py",
      "owned_build_manifest.json", "owned_capture_build_manifest.json", "build-owned/Release/rocell_windows_camera.exe", "build-owned/Release/rocell_camera_admission_tests.exe",
      "build-owned/Release/rocell_camera_admission_entry_tests.exe", "build-owned-capture/Release/rocell_windows_camera.exe", "build-owned-capture/Release/rocell_windows_camera_probe_compile_check.exe",
      "build-owned-capture/Release/rocell_camera_capture_admission_tests.exe", "build-owned-capture/Release/rocell_camera_capture_admission_entry_tests.exe"
    ].map(path => "software/native/windows_camera/" + path));
    const reasons = ["MISSING", "UNREADABLE", "UNSAFE_PATH", "SIZE_LIMIT", "CHANGED_DURING_READ", "NOT_INSPECTED", "HASH_MISMATCH", "LENGTH_MISMATCH", "MANIFEST_INVALID", "MANIFEST_UNVERIFIED"];
    if (!v.exact(value, ["schema", "status", "inspection", "review", "publication", ...flags, "meaning"])
      || value.schema !== "rocell.wizard_physical_camera_runtime_review.v1" || !held(value) || !v.string(value.meaning, 512)
      || !["NOT_INSPECTED", "INSPECTION_RETAINED", "REVIEW_RECORDED", "HISTORICAL_HELD"].includes(value.status)
      || !v.exact(value.publication, ["status", "operation_id"]) || !["NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"].includes(value.publication.status)
      || !(value.publication.operation_id === null || v.identifier(value.publication.operation_id))) return null;
    const observed = value.inspection, review = value.review, publication = value.publication.status;
    if ((value.status === "HISTORICAL_HELD") !== (publication === "HISTORICAL_HELD")
      || (publication === "CURRENT" && value.publication.operation_id === null)
      || (publication === "PENDING" && review !== null)
      || (value.status === "NOT_INSPECTED" && (observed !== null || review !== null || !["NOT_PUBLISHED", "PENDING"].includes(publication)))
      || (value.status === "INSPECTION_RETAINED" && (observed === null || review !== null || !["PENDING", "CURRENT"].includes(publication)))
      || (value.status === "REVIEW_RECORDED" && (observed === null || review === null || publication !== "CURRENT"))) return null;
    if (observed !== null) {
      if (!v.exact(observed, ["schema", "operator_id", "source_sha256", "launch_session_id", "report_sha256", "status", "purposes", "coverage", ...flags])
        || observed.schema !== "rocell.physical_camera_runtime_inspection_summary.v1" || !held(observed) || !label(observed.operator_id)
        || !v.digest(observed.source_sha256) || !v.digest(observed.report_sha256) || typeof observed.launch_session_id !== "string" || !/^wizard-[0-9a-f]{32}$/.test(observed.launch_session_id)
        || !["FILES_MATCHED", "HELD"].includes(observed.status) || !v.exact(observed.purposes, ["probe", "capture"])
        || !v.exact(observed.coverage, ["planned_paths", "observed_paths", "unobserved_paths"])
        || !Object.values(observed.coverage).every(n => v.integer(n, 0, 40))
        || observed.coverage.planned_paths !== observed.coverage.observed_paths + observed.coverage.unobserved_paths
        || (publication === "CURRENT" && (observed.source_sha256 !== source || (launch !== null && observed.launch_session_id !== launch)))) return null;
      for (const purpose of ["probe", "capture"]) {
        const row = observed.purposes[purpose], pin = ["MATCHED", "HASH_MISMATCH", "LENGTH_MISMATCH", "NOT_OBSERVED"];
        if (!v.exact(row, ["purpose", "binary_status", "build_status", "source_status", "artifact_status", "source_counts", "artifact_counts", "gaps"])
          || row.purpose !== purpose || !pin.includes(row.binary_status) || ![...pin, "MANIFEST_INVALID"].includes(row.build_status)
          || !Array.isArray(row.gaps) || row.gaps.length > 40) return null;
        for (const kind of ["source", "artifact"]) {
          const counts = row[kind + "_counts"], status = row[kind + "_status"];
          if (!v.exact(counts, ["total", "matched", "gaps", "unverified"]) || !Object.values(counts).every(n => v.integer(n, 0, 40))
            || counts.total !== counts.matched + counts.gaps + counts.unverified || !["MATCHED", "GAPS", "NOT_VERIFIED"].includes(status)
            || (status === "MATCHED" && counts.matched !== counts.total)
            || (status === "GAPS" && (counts.gaps === 0 || counts.unverified !== 0))
            || (status === "NOT_VERIFIED" && counts.unverified !== counts.total)) return null;
        }
        const pairs = new Set();
        for (const gap of row.gaps) {
          if (!v.exact(gap, ["relative_path", "reason"]) || !paths.has(gap.relative_path) || !reasons.includes(gap.reason)) return null;
          const key = gap.relative_path + "|" + gap.reason;
          if (pairs.has(key)) return null;
          pairs.add(key);
        }
        if (observed.status === "FILES_MATCHED" && (["binary_status", "build_status", "source_status", "artifact_status"].some(key => row[key] !== "MATCHED") || row.gaps.length)) return null;
      }
      if (observed.status === "FILES_MATCHED" && observed.coverage.unobserved_paths !== 0) return null;
    }
    if (review !== null && (!observed || !v.exact(review, ["reviewer_id", "review_operation_id", "inspection_sha256", "status", "distinct_operator_labels"])
      || !label(review.reviewer_id) || review.reviewer_id.toLowerCase() === observed.operator_id.toLowerCase() || !v.identifier(review.review_operation_id)
      || review.inspection_sha256 !== observed.report_sha256 || review.distinct_operator_labels !== true
      || (publication === "CURRENT" && review.review_operation_id !== value.publication.operation_id)
      || review.status !== (observed.status === "FILES_MATCHED" ? "ACKNOWLEDGED_FILE_MATCH" : "ACKNOWLEDGED_HELD_REPORT"))) return null;
    return value;
  }

  function cameraRuntimeReview(projection, source) {
    const box = element("section", "runtime-file-review");
    box.append(heading("Runtime pair file inspection and review"), element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED / DISPATCH_DISABLED"),
      element("p", "notice warning", "File agreement is not runtime admission. No executable was launched and no camera or driver was qualified by this inspection. Probe/capture, power and motion remain held."));
    if (projection === undefined || projection === null) { box.append(element("p", "caption", "No runtime-pair inspection retained. Use the explicit file-inspection action; viewing never reads or rechecks runtime files.")); return box; }
    const value = cameraRuntimeReviewProjection(projection, source, state.view.session_id);
    if (!value) { box.append(element("p", "notice warning", "RUNTIME_INSPECTION_NOT_VERIFIED: Inconsistent cached inspection/review withheld. Inspect diagnostics; no file agreement or review is inferred.")); return box; }
    box.append(element("p", "", `Status: ${value.status}; publication: ${value.publication.status}`), element("p", "caption", value.meaning));
    if (value.publication.status === "PENDING") { box.append(element("p", "notice warning", "Inspection/review publication pending. Details are withheld until successful result retention and completion logging.")); return box; }
    if (value.publication.status === "HISTORICAL_HELD") box.append(element("p", "notice warning", "Historical file observations and review only; not current installed-file agreement. Original source and launch remain attached. No automatic reinspection or restoration of authority."));
    const observed = value.inspection;
    if (!observed) { box.append(element("p", "caption", "No runtime-pair inspection retained.")); return box; }
    box.append(element("p", "", `Inspector: ${observed.operator_id}`), element("p", "", `Report: ${observed.report_sha256}`),
      element("p", "", `Observed source: ${observed.source_sha256}; original launch: ${observed.launch_session_id}`),
      element("p", "", `File result: ${observed.status}; fixed paths planned ${observed.coverage.planned_paths}, observed ${observed.coverage.observed_paths}, unobserved ${observed.coverage.unobserved_paths}`));
    for (const purpose of ["probe", "capture"]) {
      const row = observed.purposes[purpose];
      box.append(heading(purpose + " file observations"), element("p", "", `${purpose}: executable pin ${row.binary_status}; build-record pin ${row.build_status}`),
        element("p", "", `${purpose}: source closure ${row.source_status}; declared artifacts ${row.artifact_status}`));
      for (const kind of ["source", "artifact"]) { const c = row[kind + "_counts"]; box.append(element("p", "", `${kind} rows: total ${c.total}, matched ${c.matched}, gaps ${c.gaps}, unverified ${c.unverified}`)); }
      for (const gap of row.gaps) box.append(element("p", "", `${gap.relative_path}: ${gap.reason}`));
      if (!row.gaps.length) box.append(element("p", "caption", "No per-file gaps reported; a global inspection hold may still apply."));
    }
    if (value.review) box.append(heading("Review of exact retained file report"), element("p", "", `Reviewer: ${value.review.reviewer_id}; ${value.review.status}`),
      element("p", "", `Reviewed report: ${value.review.inspection_sha256}; review operation: ${value.review.review_operation_id}`));
    else box.append(element("p", "caption", "No review recorded. Inspection never acknowledges itself."));
    box.append(element("p", "caption", "Labels record procedure, not authenticated independent people. Review cannot upgrade a held report. Full evidence belongs in the assigned export; this page never rebuilds, learns pins or re-inspects files."));
    return box;
  }

  function physicalCameraValidators() {
    // Structural presentation checks only: no provider imports, file reads,
    // endpoint resolution, evidence admission or physical release occurs here.
    const v = cameraConfigurationValidators(), ids = ["brightness", "contrast", "exposure", "gain", "saturation", "white_balance"];
    const bindingKeys = ["session_id", "attempt_id", "source_sha256", "operation_sha256", "permit_sha256", "selected_identity_sha256", "endpoint_sha256", "helper_sha256", "runtime_registration_sha256", "probe_preparation_sha256", "probe_evidence_sha256"];
    const codes = (items, max = 16) => Array.isArray(items) && items.length <= max && new Set(items).size === items.length && items.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(code));
    const binding = (item, capture = false) => v.exact(item, capture ? bindingKeys.slice(0, 9) : bindingKeys)
      && Object.entries(item).every(([key, value]) => ["session_id", "attempt_id"].includes(key) ? v.identifier(value) : v.digest(value));
    const same = (a, b) => Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => a[key] === b[key]);
    const held = value => value.provenance === "PHYSICAL_UNQUALIFIED" && value.physical_authority === false && value.hardware_qualified === false && v.string(value.meaning, 512);
    function capabilities(value) {
      if (!v.exact(value, ["schema", "provenance", "status", "binding", "modes", "controls", "physical_authority", "hardware_qualified", "capabilities_sha256", "unavailable_controls", "meaning"])
        || value.schema !== "rocell.physical_camera_capabilities.v1" || value.status !== "OBSERVED_NATIVE_UNQUALIFIED" || !held(value) || !binding(value.binding) || !v.digest(value.capabilities_sha256)
        || !Array.isArray(value.modes) || value.modes.length > 128 || !Array.isArray(value.controls) || value.controls.length > 6 || !value.controls.every(v.observation)
        || !Array.isArray(value.unavailable_controls) || !value.unavailable_controls.every(id => ids.includes(id))) return null;
      const partition = [...value.controls.map(item => item.control_id), ...value.unavailable_controls];
      if (partition.length !== 6 || new Set(partition).size !== 6 || new Set(value.modes.map(item => item?.choice_id)).size !== value.modes.length) return null;
      for (const item of value.modes) {
        if (!v.exact(item, ["choice_id", "mode", "selectable", "blockers"]) || !v.choice(item.choice_id) || !v.mode(item.mode) || !codes(item.blockers, 4) || typeof item.selectable !== "boolean") return null;
        const m = item.mode, expected = [];
        if (m.subtype !== "YUY2") expected.push("UNSUPPORTED_PIXEL_FORMAT");
        if (m.width < 2 || m.width % 2) expected.push("UNSUPPORTED_YUY2_WIDTH");
        let span = m.width * m.height * 2;
        if (m.stride_bytes !== null) { if (Math.abs(m.stride_bytes) < m.width * 2) expected.push("INVALID_REPORTED_STRIDE"); span = Math.max(span, (m.height - 1) * Math.abs(m.stride_bytes) + m.width * 2); }
        if (span > 64 * 1024 * 1024) expected.push("FRAME_BUDGET_EXCEEDED");
        if (JSON.stringify(item.blockers) !== JSON.stringify(expected) || item.selectable !== (expected.length === 0)) return null;
      }
      return value;
    }
    function candidate(value, caps) {
      if (!caps || !v.exact(value, ["schema", "provenance", "status", "capabilities_sha256", "binding", "mode_choice_id", "mode", "controls", "applied", "physical_authority", "hardware_qualified", "settings_epoch", "meaning"])
        || value.schema !== "rocell.physical_camera_configuration.v1" || value.status !== "STAGED_NOT_APPLIED_NATIVE" || !held(value) || value.applied !== false
        || !v.digest(value.settings_epoch) || value.capabilities_sha256 !== caps.capabilities_sha256 || !binding(value.binding) || !same(value.binding, caps.binding)
        || !Array.isArray(value.controls) || value.controls.length > 6 || !value.controls.every(v.requested) || new Set(value.controls.map(item => item.control_id)).size !== value.controls.length) return null;
      const mode = caps.modes.find(item => item.choice_id === value.mode_choice_id);
      if (!mode?.selectable || !v.sameMode(mode.mode, value.mode)) return null;
      for (const item of value.controls) {
        const observed = caps.controls.find(row => row.control_id === item.control_id), flag = item.mode === "auto" ? 1 : 2;
        if (!observed || !(observed.capability_flags & flag) || item.value < observed.minimum || item.value > observed.maximum || (item.value - observed.minimum) % observed.step !== 0) return null;
      }
      return value;
    }
    function readback(value, config, caps) {
      const keys = ["schema", "provenance", "status", "settings_epoch", "capabilities_sha256", "probe_binding", "capture_binding", "capture_preparation_sha256", "capture_evidence_sha256", "capture_request_sha256", "native_receipt_valid", "native_status", "native_requested_mode", "requested_mode", "observed_mode", "mode_matched", "controls", "reasons", "process_status", "process_cleanup_confirmed", "native_cleanup_confirmed", "frame_content_verified", "physical_authority", "hardware_qualified", "final_power_state", "readback_sha256", "meaning"];
      if (!config || !v.exact(value, keys) || value.schema !== "rocell.physical_camera_readback.v1" || !held(value)
        || !["capture_preparation_sha256", "capture_evidence_sha256", "capture_request_sha256", "readback_sha256"].every(key => v.digest(value[key]))
        || value.settings_epoch !== config.settings_epoch || value.capabilities_sha256 !== caps.capabilities_sha256 || !binding(value.probe_binding) || !same(value.probe_binding, caps.binding) || !binding(value.capture_binding, true)
        || !["session_id", "source_sha256", "selected_identity_sha256", "endpoint_sha256"].every(key => value.capture_binding[key] === caps.binding[key])
        || !["native_receipt_valid", "mode_matched", "process_cleanup_confirmed", "native_cleanup_confirmed"].every(key => typeof value[key] === "boolean")
        || ![null, "OK", "FAILED"].includes(value.native_status) || value.native_receipt_valid !== (value.native_status !== null)
        || !["HELD", "CANCELLED", "TIMED_OUT", "FAILED", "SUCCEEDED_NATIVE_DIAGNOSTIC"].includes(value.process_status)
        || value.frame_content_verified !== false || value.final_power_state !== "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
        || !v.sameMode(value.requested_mode, config.mode) || !["native_requested_mode", "observed_mode"].every(key => value[key] === null || v.mode(value[key]))
        || !codes(value.reasons) || !Array.isArray(value.controls) || value.controls.length !== config.controls.length) return null;
      const expected = [];
      if (value.process_status !== "SUCCEEDED_NATIVE_DIAGNOSTIC") expected.push("CAPTURE_CAMPAIGN_NOT_SUCCESSFUL");
      if (!value.process_cleanup_confirmed) expected.push("PROCESS_CLEANUP_UNCONFIRMED");
      if (!value.native_receipt_valid) expected.push("NATIVE_RECEIPT_UNAVAILABLE"); else if (value.native_status !== "OK") expected.push("NATIVE_CAPTURE_FAILED");
      if (!value.native_cleanup_confirmed) expected.push("NATIVE_CLEANUP_UNCONFIRMED");
      if (!value.mode_matched) expected.push("MODE_READBACK_MISMATCH");
      if (value.mode_matched && (!v.sameMode(value.native_requested_mode, config.mode) || !v.mode(value.observed_mode)
        || !["width", "height", "subtype"].every(key => value.observed_mode[key] === config.mode[key])
        // Match native rational equality without rounding or changing the report.
        || BigInt(value.observed_mode.fps_numerator) * BigInt(config.mode.fps_denominator) !== BigInt(config.mode.fps_numerator) * BigInt(value.observed_mode.fps_denominator)
        || (config.mode.stride_bytes !== null && value.observed_mode.stride_bytes !== config.mode.stride_bytes))) return null;
      for (let index = 0; index < value.controls.length; index++) {
        const row = value.controls[index], request = config.controls[index];
        if (!v.exact(row, ["control_id", "requested", "observed", "matched", "reasons"]) || row.control_id !== request.control_id || !v.exact(row.requested, ["value", "mode"])
          || row.requested.value !== request.value || row.requested.mode !== request.mode || typeof row.matched !== "boolean" || !codes(row.reasons, 4)) return null;
        const failures = [], observed = row.observed, pinned = caps.controls.find(item => item.control_id === row.control_id);
        if (observed === null) failures.push("CONTROL_READBACK_MISSING");
        else {
          if (!v.observation(observed) || observed.control_id !== row.control_id) return null;
          if (observed.flags !== (request.mode === "auto" ? 1 : 2)) failures.push("CONTROL_MODE_READBACK_MISMATCH");
          if (request.mode === "manual" && observed.value !== request.value) failures.push("MANUAL_VALUE_READBACK_MISMATCH");
          if (["minimum", "maximum", "step", "default", "capability_flags", "unit"].some(key => observed[key] !== pinned[key])) failures.push("CONTROL_CAPABILITY_DRIFT");
        }
        if (JSON.stringify(failures) !== JSON.stringify(row.reasons) || row.matched !== !failures.length) return null;
      }
      if (value.controls.some(row => !row.matched)) expected.push("CONTROL_READBACK_MISMATCH");
      if (JSON.stringify(expected) !== JSON.stringify(value.reasons) || value.status !== (expected.length ? "READBACK_MISMATCH_UNQUALIFIED" : "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED")) return null;
      return value;
    }
    function physical(value) {
      const keys = ["schema", "status", "source_sha256", "session_id", "reviewed_endpoint", "runtimes", "configuration", "plan", "last_frame", "fault", "publication", "blockers", "physical_authority", "hardware_qualified", "connected", "meaning"];
      if (value && Object.hasOwn(value, "runtime_inspection")) keys.push("runtime_inspection");
      if (!v.exact(value, keys)
        || value.schema !== "rocell.wizard_physical_camera.v1" || !["NOT_STARTED", "HELD", "OBSERVATION_RETAINED", "CONFIGURATION_STAGED", "CONTENT_VERIFIED"].includes(value.status)
        || !v.digest(value.source_sha256) || !v.identifier(value.session_id) || !v.string(value.meaning, 512) || !codes(value.blockers)
        || !["physical_authority", "hardware_qualified", "connected"].every(key => value[key] === false)
        || !v.exact(value.runtimes, ["probe", "capture"]) || !v.exact(value.configuration, ["capabilities", "candidate", "readback"])
        || !v.exact(value.publication, ["status", "operation_id"]) || !["NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"].includes(value.publication.status)
        || !(value.publication.operation_id === null || v.identifier(value.publication.operation_id))) return null;
      const endpoint = value.reviewed_endpoint;
      if (endpoint !== null && (!v.exact(endpoint, ["endpoint_sha256", "identity_sha256", "metadata_review_binding_sha256", "generic_candidate_sha256"]) || !Object.values(endpoint).every(v.digest))) return null;
      for (const purpose of ["probe", "capture"]) {
        const runtime = value.runtimes[purpose];
        if (runtime !== null && (!v.exact(runtime, ["purpose", "registration_sha256", "helper_sha256", "build_record_sha256", "status", "dispatch_enabled", "driver_qualified"])
          || runtime.purpose !== "FINITE_NATIVE_CAMERA_" + purpose.toUpperCase() || runtime.status !== "DORMANT_REVIEW_REQUIRED" || runtime.dispatch_enabled !== false || runtime.driver_qualified !== false
          || !["registration_sha256", "helper_sha256", "build_record_sha256"].every(key => v.digest(runtime[key])))) return null;
      }
      const plan = value.plan;
      if (plan !== null && (!v.exact(plan, ["plan_sha256", "operation", "stage", "status"]) || !v.digest(plan.plan_sha256) || !["probe", "capture"].includes(plan.operation)
        || typeof plan.stage !== "string" || !/^[a-z][a-z_]{0,63}$/.test(plan.stage) || plan.status !== "PREPARED_NOT_ADMITTED")) return null;
      const raw = value.configuration, caps = raw.capabilities === null ? null : capabilities(raw.capabilities), config = raw.candidate === null ? null : candidate(raw.candidate, caps), observed = raw.readback === null ? null : readback(raw.readback, config, caps);
      if ((raw.capabilities !== null && !caps) || (raw.candidate !== null && !config) || (raw.readback !== null && !observed)
        || (caps && (!endpoint || caps.binding.source_sha256 !== value.source_sha256 || caps.binding.session_id !== value.session_id || caps.binding.endpoint_sha256 !== endpoint.endpoint_sha256))) return null;
      const frame = value.last_frame;
      if (frame !== null && (!v.exact(frame, ["image_id", "attempt_id", "frame_index", "preview_sha256", "native_frame_sha256", "manifest_sha256", "settings_epoch", "endpoint_sha256", "capture_evidence_sha256", "provenance", "frame_content_verified", "live"])
        || !(frame.image_id === null || v.identifier(frame.image_id)) || !v.identifier(frame.attempt_id) || !v.integer(frame.frame_index, 0, 31)
        || !["preview_sha256", "native_frame_sha256", "manifest_sha256", "settings_epoch", "endpoint_sha256", "capture_evidence_sha256"].every(key => v.digest(frame[key]))
        || frame.provenance !== "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2" || frame.frame_content_verified !== true || frame.live !== false
        || !endpoint || frame.endpoint_sha256 !== endpoint.endpoint_sha256 || !config || frame.settings_epoch !== config.settings_epoch
        || !observed || frame.capture_evidence_sha256 !== observed.capture_evidence_sha256 || frame.attempt_id !== observed.capture_binding.attempt_id
        || (frame.image_id !== null && (value.publication.status !== "CURRENT" || value.status === "HELD" || value.publication.operation_id === null)))) return null;
      if (value.fault !== null && !validatedCameraFault(value.fault)) return null;
      if (value.status === "CONTENT_VERIFIED" && (!frame || !observed || observed.status !== "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
        || observed.process_status !== "SUCCEEDED_NATIVE_DIAGNOSTIC" || observed.native_status !== "OK" || observed.native_receipt_valid !== true
        || observed.process_cleanup_confirmed !== true || observed.native_cleanup_confirmed !== true || observed.mode_matched !== true
        || observed.reasons.length || observed.controls.some(row => !row.matched))) return null;
      if ((value.status === "NOT_STARTED" && (plan || caps || config || observed || frame || value.publication.status !== "NOT_PUBLISHED")) || (value.status === "CONFIGURATION_STAGED" && !config)) return null;
      return value;
    }
    return {physical};
  }

  function physicalCamera() {
    const box = card("Physical camera acquisition", "Purpose-specific runtime planning · finite captures · no automatic activation");
    box.append(element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED"), element("p", "notice warning", "Metadata review is not runtime admission. Probe and capture need separate qualified runtimes and explicit server-side approval. Storage qualification is not physical authority; this panel cannot release a camera or energize the arm."));
    const input = state.view.physical_camera, value = physicalCameraValidators().physical(input);
    if (!value) { box.append(element("p", "notice warning", input === undefined || input === null ? "No physical camera plan retained. Viewing this page performs no device query or activation." : "PHYSICAL_CAMERA_NOT_VERIFIED: Inconsistent or unsupported projection withheld. Inspect diagnostics; no connection or settings are inferred.")); return box; }
    box.append(facts({status: value.status, source_sha256: value.source_sha256, session_id: value.session_id, publication: value.publication.status}), element("p", "caption", value.meaning), element("p", "caption", "CURRENT publication describes the retained plan/report. A captured-frame claim additionally requires the separately verified last-frame record below; neither means connected or qualified. Runtime candidate hashes are fixed development references, not current-file inspection or runtime approval."));
    if (value.reviewed_endpoint) box.append(heading("Reviewed endpoint metadata — not a received-model qualification"), facts(value.reviewed_endpoint));
    else box.append(element("p", "caption", "No exact reviewed endpoint retained. Never select by friendly name, camera index or raw endpoint path."));
    for (const purpose of ["probe", "capture"]) { box.append(heading(human(purpose) + " runtime")); box.append(value.runtimes[purpose] ? facts(value.runtimes[purpose]) : element("p", "notice warning", "Purpose-specific runtime not registered. The metadata helper does not supply this qualification.")); }
    box.append(cameraRuntimeReview(value.runtime_inspection, value.source_sha256));
    if (value.plan) box.append(heading("Prepared plan — NOT ADMITTED"), facts(value.plan));
    if (value.blockers.length) { box.append(heading("Current physical gate holds")); const list = element("ul", "action-blockers"); for (const code of value.blockers) list.append(element("li", "", code)); box.append(list); }
    const {capabilities: caps, candidate: config, readback: observed} = value.configuration;
    box.append(heading("Reported support, intent and readback"), element("p", "caption", "Native reported support remains unqualified. No mode or electronic setting is selected automatically. Manual lens focus and aperture require physical adjustment and verification."));
    if (caps) {
      box.append(element("p", "notice warning", caps.meaning));
      box.append(facts({capabilities_sha256: caps.capabilities_sha256, probe_evidence_sha256: caps.binding.probe_evidence_sha256, reported_modes: caps.modes.length}));
      for (const row of caps.modes) box.append(element("p", "", `${row.choice_id}: ${row.mode.width} × ${row.mode.height}, ${row.mode.fps_numerator}/${row.mode.fps_denominator} fps, ${row.mode.subtype}, stride ${row.mode.stride_bytes ?? "NOT_REPORTED"} · ${row.selectable ? "SUPPORTED LAYOUT ONLY — NOT SELECTED" : "HELD: " + row.blockers.join(", ")}`));
      for (const control of caps.controls) box.append(element("p", "", `${control.control_id}: reported ${control.minimum}…${control.maximum}, step ${control.step}, default ${control.default}, current ${control.value} ${control.unit}, supported flags ${control.capability_flags}, current flags ${control.flags}${control.flags === 3 ? " (AMBIGUOUS — no mode inferred)" : ""}`));
      box.append(facts({unavailable_controls: caps.unavailable_controls}));
    } else box.append(element("p", "caption", "No retained native capability observation."));
    if (config) box.append(heading("Immutable settings intent — NOT APPLIED"), element("p", "notice warning", config.meaning), facts({settings_epoch: config.settings_epoch, mode_choice_id: config.mode_choice_id, applied: false}), facts(config.mode), facts({requested_controls: config.controls}));
    if (observed) {
      box.append(element("p", "notice warning", observed.meaning));
      box.append(heading("Retained settings readback — not pixel or power proof"), facts({status: observed.status, readback_sha256: observed.readback_sha256, mode_matched: observed.mode_matched, process_status: observed.process_status,
        process_cleanup_confirmed: observed.process_cleanup_confirmed, native_cleanup_confirmed: observed.native_cleanup_confirmed, frame_content_verified: false, final_power_state: observed.final_power_state}), facts({requested_mode: observed.requested_mode, observed_mode: observed.observed_mode}));
      for (const row of observed.controls) box.append(element("p", "", `${row.control_id}: requested ${row.requested.value} (${row.requested.mode}); observed ${row.observed ? row.observed.value + " " + row.observed.unit + " / flags " + row.observed.flags : "NOT_AVAILABLE"}; ${row.matched ? "MATCHED, STILL UNQUALIFIED" : "HELD: " + row.reasons.join(", ")}`));
      if (observed.reasons.length) box.append(facts({readback_holds: observed.reasons}));
    }
    box.append(heading("Last captured frame — NOT LIVE"));
    if (value.status === "CONTENT_VERIFIED") box.append(element("p", "caption", "CONTENT_VERIFIED: retained pixel bytes and the derived still preview were verified separately from settings readback. This is not a live feed, received-model qualification or canonical stage acceptance."));
    if (value.last_frame) box.append(facts(value.last_frame, ["image_id"]), element("p", "caption", value.last_frame.image_id ? "Published cached preview from separately verified retained native pixels. A still frame is not a live connection or calibration acceptance." : "Historical frame references only; current image publication is withheld. No automatic recapture."));
    else box.append(element("p", "caption", "No separately verified physical frame has been published. Readback alone never creates an image."));
    if (value.fault) box.append(retainedCameraFault(value.fault));
    box.append(element("p", "caption", "Viewing is device-inert. Explicit preparation may read current source files, but cannot open a device. Use only eligible preview/execute actions below; no automatic retries, reconnects or arm power actions."));
    return box;
  }

  function physicalSetupValidators() {
    const v = cameraConfigurationValidators();
    const stages = ["workspace_sources", "static_camera_contract", "camera_receipt", "camera_identity", "camera_mode_controls", "camera_frame_freshness", "optics_intrinsics", "static_registration", "arm_identity", "power_safety", "power_on_observation", "feedback_only_connection", "reference_frame_calibration", "noncontact_acceptance", "physical_handoff"];
    const states = ["PENDING", "WAITING_OPERATOR", "REVIEW_PENDING", "PASS", "BLOCKED", "INVALIDATED", "INCIDENT_HOLD", "SIDE_EFFECT_UNCERTAIN", "COMPLETE_DIAGNOSTIC"];
    const ids = (items, max = 256) => Array.isArray(items) && items.length <= max && items.every(v.identifier) && new Set(items).size === items.length;
    // V2 stage snapshots append references from each committed event. A review
    // can cite the same receipt again; this is not a unique evidence inventory.
    const evidenceOccurrences = items => Array.isArray(items) && items.length <= 256 && items.every(v.identifier);
    const codes = (items, max = 32) => Array.isArray(items) && items.length <= max && items.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(code)) && new Set(items).size === items.length;
    const falseFlags = (value, keys) => keys.every(key => value[key] === false);
    function verification(value, binding) {
      if (!v.exact(value, ["schema", "status", "runtime_activation", "cell", "qualification", "attempt_ledger", "quarantine", "session", "leases", "challenge_sha256", "effects_allowed_by_m1_storage", "effect_methods_exposed", "operation_effect", "authority"])
        || value.schema !== "rocell.physical_onboarding_m1_runtime.v1" || value.runtime_activation !== false || value.effect_methods_exposed !== false
        || !v.digest(value.challenge_sha256) || typeof value.effects_allowed_by_m1_storage !== "boolean") return null;
      const c = value.cell, q = value.qualification, a = value.attempt_ledger, quarantine = value.quarantine, s = value.session, leases = value.leases;
      const cellFalse = ["runtime_activation", "device_io_authorized", "robot_power_authorized", "motion_authorized", "contact_authorized", "automatic_effect_replay_allowed"];
      if (!v.exact(c, ["schema", "cell_id", "cell_key_sha256", "source_binding_sha256", "stage_plan_sha256", "durability_qualification_sha256", "attempt_ledger_id", "quarantine_ledger_id", "created_at_ns", ...cellFalse, "physical_release_effect", "cell_sha256"])
        || c.schema !== "rocell.physical_onboarding_m1_cell.v1" || c.cell_id !== binding.cell_id || !falseFlags(c, cellFalse) || c.physical_release_effect !== "NONE"
        || !["cell_key_sha256", "source_binding_sha256", "stage_plan_sha256", "durability_qualification_sha256", "cell_sha256"].every(key => v.digest(c[key]))
        || !v.identifier(c.attempt_ledger_id) || !v.identifier(c.quarantine_ledger_id)
        // Absolute ns arrive as JSON numbers above JS's exact range. Never use
        // or display them as exact identity/freshness evidence.
        || typeof c.created_at_ns !== "number" || !Number.isInteger(c.created_at_ns) || c.created_at_ns < 0 || c.created_at_ns >= 2 ** 63
        || !v.exact(q, ["anchor_sha256", "startup_report_sha256", "qualified_windows_ntfs"]) || !v.digest(q.anchor_sha256) || !v.digest(q.startup_report_sha256) || q.qualified_windows_ntfs !== true
        || !v.exact(a, ["head_sha256", "event_count", "unresolved_attempt_ids", "uncertain_attempt_ids"]) || !v.digest(a.head_sha256) || !v.integer(a.event_count, 0, Number.MAX_SAFE_INTEGER) || !ids(a.unresolved_attempt_ids) || !ids(a.uncertain_attempt_ids)
        || !v.exact(quarantine, ["head_sha256", "event_count", "latched", "clearing_supported"]) || !v.digest(quarantine.head_sha256) || !v.integer(quarantine.event_count, 0, Number.MAX_SAFE_INTEGER) || typeof quarantine.latched !== "boolean" || quarantine.clearing_supported !== false
        || !v.exact(s, ["session_id", "header_sha256", "head_sha256", "evidence_inventory_sha256", "reconciliation_required"]) || s.session_id !== binding.session_id || !["header_sha256", "head_sha256", "evidence_inventory_sha256"].every(key => v.digest(s[key])) || typeof s.reconciliation_required !== "boolean"
        || !v.exact(leases, ["active_or_stale_owners", "reconciliation_required"]) || !ids(leases.active_or_stale_owners) || leases.reconciliation_required !== (leases.active_or_stale_owners.length > 0)) return null;
      const effectKeys = ["os_device_metadata_reads", "device_opens", "camera_frames_captured", "serial_transactions", "robot_power_operations", "robot_commands_sent"];
      const authorityFalse = ["device_io_authorized", "robot_power_authorized", "motion_authorized", "descent_authorized", "contact_authorized"];
      if (!v.exact(value.operation_effect, effectKeys) || !effectKeys.every(key => value.operation_effect[key] === 0)
        || !v.exact(value.authority, ["diagnostic_only", ...authorityFalse, "physical_release_effect"]) || value.authority.diagnostic_only !== true || !falseFlags(value.authority, authorityFalse) || value.authority.physical_release_effect !== "NONE") return null;
      const ready = !quarantine.latched && !a.unresolved_attempt_ids.length && !a.uncertain_attempt_ids.length && !s.reconciliation_required && !leases.active_or_stale_owners.length;
      if (value.effects_allowed_by_m1_storage !== ready || value.status !== (ready ? "M1_STORAGE_READY_ZERO_HARDWARE_AUTHORITY" : quarantine.latched ? "M1_INTEGRITY_VALID_CELL_QUARANTINED" : "M1_INTEGRITY_VALID_RECONCILIATION_REQUIRED")) return null;
      return value;
    }
    function session(value) {
      if (!v.exact(value, ["schema", "binding", "status", "operation", "verification", "stages", "error", "partial_store_possible", "initialize_attempted", "physical_authority", "device_io_performed", "hardware_qualified", "replay_allowed"])
        || value.schema !== "rocell.physical_camera_session_view.v1" || !["NOT_INITIALIZED", "RUNNING", "STORAGE_READY_PENDING", "REFRESHED_STORAGE_ONLY", "HELD"].includes(value.status)
        || ![null, "INITIALIZE", "REFRESH"].includes(value.operation) || !["partial_store_possible", "initialize_attempted"].every(key => typeof value[key] === "boolean")
        || !falseFlags(value, ["physical_authority", "device_io_performed", "hardware_qualified", "replay_allowed"])) return null;
      const b = value.binding;
      if (!v.exact(b, ["workspace", "directory", "launch_id", "source_sha256", "cell_id", "session_id"]) || !v.string(b.workspace, 4096) || !v.string(b.directory, 4096) || !v.digest(b.source_sha256)
        || !/^wizard-[0-9a-f]{32}$/.test(b.launch_id) || !/^wizard-physical-camera-[0-9a-f]{16}$/.test(b.cell_id) || !/^physical-camera-[0-9a-f]{32}$/.test(b.session_id)) return null;
      if (value.error !== null && (!v.exact(value.error, ["code", "type"]) || !codes([value.error.code], 1) || !["PhysicalCameraSessionError", "OSError", "ValueError", "RuntimeError", "KeyboardInterrupt", "SystemExit", "Exception"].includes(value.error.type))) return null;
      const checked = value.verification === null ? null : verification(value.verification, b);
      if ((value.verification !== null && !checked) || (value.stages === null) !== (checked === null)) return null;
      if (value.stages !== null && (!Array.isArray(value.stages) || value.stages.length !== 15 || !value.stages.every((row, index) => v.exact(row, ["stage", "state", "last_event_sequence", "evidence_ids"])
        && row.stage === stages[index] && states.includes(row.state) && (row.last_event_sequence === null || v.integer(row.last_event_sequence, 0, Number.MAX_SAFE_INTEGER)) && evidenceOccurrences(row.evidence_ids)))) return null;
      if ((value.status === "NOT_INITIALIZED" && (value.operation !== null || checked || value.error || value.initialize_attempted || value.partial_store_possible))
        || (value.status === "RUNNING" && (value.operation === null || checked || value.error))
        || (value.status === "HELD" && checked)
        || (["STORAGE_READY_PENDING", "REFRESHED_STORAGE_ONLY"].includes(value.status) && (!checked || value.error || value.operation !== (value.status === "STORAGE_READY_PENDING" ? "INITIALIZE" : "REFRESH")))) return null;
      if (value.status === "STORAGE_READY_PENDING" && (!value.initialize_attempted || !checked.effects_allowed_by_m1_storage || checked.attempt_ledger.event_count !== 0 || checked.quarantine.event_count !== 0
        || value.stages.some(row => row.state !== "PENDING" || row.last_event_sequence !== null || row.evidence_ids.length))) return null;
      return value;
    }
    function reopening(value, launch, source) {
      const reasonCodes = ["NO_STORE_ROOT", "UNRECOGNIZED_ENTRY", "UNSAFE_PATH", "METADATA_LIMIT", "AMBIGUOUS_STORE", "INVALID_METADATA", "DOMAIN_MISMATCH", "LINEAGE_MISMATCH", "METADATA_CHANGED", "SOURCE_CHANGED", "CANCELLED", "DEADLINE_EXPIRED", "DISCOVERY_LIMIT", "REGISTRY_INVALIDATED", "INVALID_REQUEST", "REGISTRY_BUSY", "STALE_CHOICE"];
      const launchId = item => typeof item === "string" && /^wizard-[0-9a-f]{32}$/.test(item);
      if (!v.exact(value, ["schema", "status", "current_launch_id", "source_sha256", "discovery_sha256", "stores", "issues", "invalidation_reason", "physical_authority", "device_io_performed", "meaning"])
        || value.schema !== "rocell.physical_camera_reopen_registry.v1" || value.current_launch_id !== launch || value.source_sha256 !== source
        || !["NOT_DISCOVERED", "DISCOVERED", "HELD", "INVALIDATED"].includes(value.status) || !falseFlags(value, ["physical_authority", "device_io_performed"]) || !v.string(value.meaning, 512)
        || !Array.isArray(value.stores) || value.stores.length > 32 || !Array.isArray(value.issues) || value.issues.length > 33
        || !(value.discovery_sha256 === null || v.digest(value.discovery_sha256))) return null;
      for (const row of value.stores) {
        if (!v.exact(row, ["choice_id", "origin_launch_id", "cell_id", "session_id", "source_binding_sha256", "header_sha256", "descriptor_sha256", "source_matches", "selectable", "status", "physical_authority"])
          || !launchId(row.origin_launch_id) || typeof row.cell_id !== "string" || !/^wizard-physical-camera-[0-9a-f]{16}$/.test(row.cell_id)
          || typeof row.session_id !== "string" || !/^physical-camera-[0-9a-f]{32}$/.test(row.session_id)
          || !["source_binding_sha256", "header_sha256", "descriptor_sha256"].every(key => v.digest(row[key])) || row.physical_authority !== false
          || typeof row.source_matches !== "boolean" || row.selectable !== row.source_matches
          || row.status !== (row.selectable ? "METADATA_DISCOVERED_NOT_OPENED" : "SOURCE_DRIFT_HELD")
          || (row.selectable ? typeof row.choice_id !== "string" || !/^reopen-[0-9a-f]{32}$/.test(row.choice_id) : row.choice_id !== null)) return null;
      }
      if (new Set(value.stores.map(row => row.origin_launch_id)).size !== value.stores.length
        || new Set(value.stores.filter(row => row.selectable).map(row => row.choice_id)).size !== value.stores.filter(row => row.selectable).length
        || !value.issues.every(row => v.exact(row, ["store_label", "code", "meaning"]) && (row.store_label === null || launchId(row.store_label)) && reasonCodes.includes(row.code) && v.string(row.meaning, 512))) return null;
      if (value.status === "DISCOVERED") { if (!v.digest(value.discovery_sha256) || value.invalidation_reason !== null) return null; }
      else if (value.discovery_sha256 !== null || value.stores.length || (value.status !== "HELD" && value.issues.length)) return null;
      if (value.status === "INVALIDATED" ? !reasonCodes.includes(value.invalidation_reason) : value.invalidation_reason !== null) return null;
      return value;
    }
    function setup(value) {
      const v2 = ["rocell.wizard_physical_camera_setup.v2", "rocell.wizard_physical_camera_setup.v3"].includes(value?.schema);
      const extraKeys = v2 ? ["origin_launch_id", "requirements_provenance", "reopening"] : [];
      if (value?.schema === "rocell.wizard_physical_camera_setup.v3") extraKeys.push("configuration_records");
      if (value && Object.hasOwn(value, "source_workflow")) extraKeys.push("source_workflow");
      if (!v.exact(value, ["schema", "source_sha256", "launch_session_id", "session", "prerequisites", "publication", "physical_authority", "hardware_qualified", "meaning", ...extraKeys])
        || !["rocell.wizard_physical_camera_setup.v1", "rocell.wizard_physical_camera_setup.v2", "rocell.wizard_physical_camera_setup.v3"].includes(value.schema) || !v.digest(value.source_sha256) || !/^wizard-[0-9a-f]{32}$/.test(value.launch_session_id)
        || !falseFlags(value, ["physical_authority", "hardware_qualified"]) || !v.string(value.meaning, 512)
        || !v.exact(value.publication, ["status", "operation_id"]) || !["NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"].includes(value.publication.status)
        || !(value.publication.operation_id === null || v.identifier(value.publication.operation_id))) return null;
      const current = session(value.session);
      if (!current || current.binding.source_sha256 !== value.source_sha256 || current.binding.launch_id !== (v2 ? value.origin_launch_id : value.launch_session_id)) return null;
      if (value.prerequisites !== null && !physicalPrerequisites(value.prerequisites, current.binding)) return null;
      if (v2) {
        const expected = value.prerequisites === null ? "NONE" : value.origin_launch_id === value.launch_session_id ? "CURRENT_LAUNCH_ORIGINAL" : "REOPENED_ORIGINAL_CONTEXT";
        if (value.requirements_provenance !== expected || !reopening(value.reopening, value.launch_session_id, value.source_sha256)
          || (["PENDING", "HISTORICAL_HELD"].includes(value.publication.status) && value.prerequisites !== null)) return null;
      }
      return value;
    }
    return {setup, session, verification, stages, codes, reopening};
  }

  function physicalPrerequisites(value, binding) {
    const v = cameraConfigurationValidators(), p = physicalSetupValidators();
    const files = [["stage_catalog", "software/config/physical_onboarding_stage_catalog.json"], ["hazard_register", "software/config/physical_onboarding_hazards.json"], ["epoch_policy", "software/config/configuration_epochs.json"], ["intake_template", "hardware/static_overhead_camera/hardware_intake_template.csv"]];
    const epochNames = ["software_build", "camera_support_optics", "board_tags_bench", "arm_controller_tool", "power_system", "keyboard_station", "phone_station", "empty_cell_safety"];
    const epochStarts = ["workspace_sources", "camera_receipt", "camera_receipt", "arm_identity", "power_safety", "reference_frame_calibration", "reference_frame_calibration", "power_safety"];
    const intakeIds = [[], [], [1,2,3,4,5,6,7,8,9,17,19,20,21,22,23,24].map(n => "INT-" + String(n).padStart(3, "0")), ["INT-018"]];
    const hazardIds = [["HZ-012"], ["HZ-007", "HZ-010"], ["HZ-007", "HZ-008", "HZ-009"], ["HZ-009"]];
    const observationFields = ["observed_value", "instrument_or_method", "observed_at_ns", "operator_id", "evidence_references", "uncertainty_or_limitations"];
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    const text = (item, max = 4096) => item === "" || v.string(item, max);
    const texts = (items, max = 16, limit = 2048) => Array.isArray(items) && items.length > 0 && items.length <= max && items.every(item => v.string(item, limit));
    const keys = ["schema", "status", "binding", "evidence_sha256", "source_files", "stages", "hazards", "epochs", "metadata_selection", "source_preflight", "missing_requirements", "power_state", "canonical_stage_pass", "physical_authority", "qualified", "device_io_performed", "meaning"];
    if (!v.exact(value, keys) || value.schema !== "rocell.physical_camera_prerequisites_summary.v1" || value.status !== "REQUIREMENTS_RETAINED_NOT_ASSESSED" || !v.digest(value.evidence_sha256)
      || !v.exact(value.binding, ["source_sha256", "session_id", "launch_session_id"]) || value.binding.source_sha256 !== binding.source_sha256 || value.binding.session_id !== binding.session_id || value.binding.launch_session_id !== binding.launch_id
      || value.power_state !== "UNKNOWN" || !["canonical_stage_pass", "physical_authority", "qualified", "device_io_performed"].every(key => value[key] === false) || !v.string(value.meaning, 512)
      || !Array.isArray(value.source_files) || value.source_files.length !== 4 || !value.source_files.every((row, i) => v.exact(row, ["role", "relative_path", "sha256", "bytes"]) && row.role === files[i][0] && row.relative_path === files[i][1] && v.digest(row.sha256) && v.integer(row.bytes, 1, 65536))
      || !Array.isArray(value.stages) || value.stages.length !== 4 || !Array.isArray(value.hazards) || value.hazards.length !== 5 || !Array.isArray(value.epochs) || value.epochs.length !== 8) return null;
    for (let index = 0; index < 4; index++) {
      const row = value.stages[index];
      if (!v.exact(row, ["stage", "status", "required_effect_classes", "actuator_power_requirement", "owned_artifacts", "hazard_ids", "intake_rows", "required_records"])
        || row.stage !== p.stages[index] || row.status !== "REQUIREMENTS_ONLY" || !same(row.required_effect_classes, [index === 3 ? "READ_ONLY_OS_INVENTORY" : "NO_DEVICE_IO"])
        || row.actuator_power_requirement !== "DISCONNECTED_REQUIRED" || !texts(row.owned_artifacts, 8, 96) || !same(row.hazard_ids, hazardIds[index]) || !p.codes(row.required_records, 8)
        || !Array.isArray(row.intake_rows) || row.intake_rows.length !== intakeIds[index].length) return null;
      for (let offset = 0; offset < row.intake_rows.length; offset++) {
        const item = row.intake_rows[offset], acceptance = item?.acceptance;
        if (!v.exact(item, ["record_id", "assembly", "measurement", "unit", "candidate_or_requirement", "template_phase", "template_status", "template_notes", "required_observation_fields", "observation", "acceptance"])
          || item.record_id !== intakeIds[index][offset] || !["assembly", "measurement", "unit", "candidate_or_requirement", "template_phase", "template_notes"].every(key => text(item[key]))
          || !["NOT_CAPTURED", "NOT_CREATED", "NOT_MEASURED", "NOT_RECORDED", "NOT_TESTED", "OPEN_LIMIT"].includes(item.template_status) || !same(item.required_observation_fields, observationFields) || item.observation !== null
          || !v.exact(acceptance, ["status", "owner_stage", "prerequisites", "measurement_required"]) || acceptance.measurement_required !== true) return null;
        const deferred = item.record_id === "INT-005";
        if (acceptance.status !== (deferred ? "DEFERRED_LIMIT" : "NOT_ASSESSED") || acceptance.owner_stage !== (deferred ? "noncontact_acceptance" : row.stage)
          || !same(acceptance.prerequisites, deferred ? ["TARGET_ACCURACY_BUDGET_CLOSED"] : [])) return null;
      }
    }
    for (let index = 0; index < value.hazards.length; index++) {
      const row = value.hazards[index];
      if (!v.exact(row, ["id", "title", "severity", "status", "evidence_stages", "invalidation_epochs", "controls", "required_evidence", "fail_safe", "residual_status"])
        || row.id !== ["HZ-007", "HZ-008", "HZ-009", "HZ-010", "HZ-012"][index] || !v.string(row.title, 512) || row.severity !== "HIGH" || row.status !== "OPEN_BLOCKING"
        || !Array.isArray(row.evidence_stages) || !row.evidence_stages.length || row.evidence_stages.length > 15 || !row.evidence_stages.every(stage => p.stages.includes(stage))
        || !Array.isArray(row.invalidation_epochs) || !row.invalidation_epochs.length || row.invalidation_epochs.length > 8 || !row.invalidation_epochs.every(epoch => epochNames.includes(epoch))
        || !texts(row.controls) || !texts(row.required_evidence) || !p.codes([row.fail_safe], 1) || row.residual_status !== "UNASSESSED_REQUIRES_RECEIVED_HARDWARE_EVIDENCE") return null;
    }
    for (let index = 0; index < value.epochs.length; index++) {
      const row = value.epochs[index];
      if (!v.exact(row, ["epoch_id", "status", "value", "description", "change_triggers", "invalidates_from_stage", "required_bindings"])
        || row.epoch_id !== epochNames[index] || row.status !== "UNMEASURED" || row.value !== null || !v.string(row.description, 512) || row.invalidates_from_stage !== epochStarts[index]
        || !texts(row.change_triggers, 16, 96) || !texts(row.required_bindings, 16, 96)) return null;
    }
    const selection = value.metadata_selection, preflight = value.source_preflight;
    if (selection !== null && (!v.exact(selection, ["endpoint_sha256", "identity_sha256", "metadata_review_binding_sha256", "generic_candidate_sha256"]) || !Object.values(selection).every(v.digest))) return null;
    if (preflight !== null && (!v.exact(preflight, ["report_sha256", "outcome", "origin_session_id", "canonical_stage_pass", "power_state"]) || !v.digest(preflight.report_sha256) || !v.identifier(preflight.origin_session_id)
      || !["FILE_CHECKS_COHERENT", "HELD"].includes(preflight.outcome) || preflight.canonical_stage_pass !== false || preflight.power_state !== "UNKNOWN")) return null;
    const missing = ["REQUIREMENTS_ARE_NOT_OBSERVATIONS_OR_ACCEPTANCE", "DISCONNECTED_REQUIRED_NOT_OBSERVED", "HZ_012_QUALIFICATION_EVIDENCE_NOT_ASSESSED", "STATIC_CAMERA_CONTRACT_NOT_ASSESSED_BY_THIS_COLLECTION", "RECEIVED_CAMERA_AND_PASSIVE_WORKCELL_NOT_MEASURED", "RECEIVED_LABEL_TO_USB_CORRELATION_NOT_ASSESSED", "PERSISTENT_IDENTITY_STABILITY_NOT_QUALIFIED", "ALL_EIGHT_EPOCH_DEPENDENCIES_UNMEASURED", "NATIVE_ACTIVATION_AND_PHYSICAL_STAGE_GATES_REMAIN_HELD"];
    missing.push(preflight ? "SOURCE_PREFLIGHT_ONLY_NOT_CANONICAL_ACCEPTANCE" : "SOURCE_PREFLIGHT_NOT_SUPPLIED");
    if (preflight && preflight.outcome !== "FILE_CHECKS_COHERENT") missing.push("SOURCE_PREFLIGHT_HELD");
    missing.push(selection ? "METADATA_SELECTION_ONLY_NOT_RECEIVED_UNIT_QUALIFICATION" : "CURRENT_CAMERA_SELECTION_NOT_SUPPLIED");
    return same(value.missing_requirements, missing) ? value : null;
  }

  function physicalRequirementsCard(value) {
    const section = element("section", "physical-prerequisites");
    section.append(heading("Stage 1–4 requirements — NOT ASSESSED"), facts({evidence_sha256: value.evidence_sha256, power_state: "UNKNOWN", epoch_observations: "8 UNMEASURED", intake_observations: "17 NOT OBSERVED"}), element("p", "caption", value.meaning),
      element("p", "notice warning", "DISCONNECTED_REQUIRED is a requirement, not an observed power state. Retaining these questions can move stage 1 to WAITING_OPERATOR but cannot assess, review or pass it. A stage's evidence-reference count is not the full retained inventory and does not prove checklist review."));
    for (const source of value.source_files) section.append(element("p", "caption", `${source.role}: ${source.relative_path} · ${source.bytes} bytes · ${source.sha256}`));
    for (const stage of value.stages) {
      const group = element("details"); group.append(element("summary", "", `${human(stage.stage)} · REQUIREMENTS ONLY · ${stage.intake_rows.length} required intake records`), facts({required_effect_classes: stage.required_effect_classes, actuator_power_requirement: stage.actuator_power_requirement, owned_artifacts: stage.owned_artifacts, required_records: stage.required_records, hazard_ids: stage.hazard_ids}));
      for (const item of stage.intake_rows) {
        const row = element("details"); row.append(element("summary", "", `${item.record_id}: ${item.measurement} · ${item.unit || "unit not specified"} · OBSERVATION UNKNOWN`), facts({assembly: item.assembly, candidate_or_requirement_NOT_OBSERVED: item.candidate_or_requirement, template_phase: item.template_phase, template_status: item.template_status, template_notes: item.template_notes, required_observation_fields: item.required_observation_fields}),
          element("p", "notice warning", item.record_id === "INT-005" ? "INT-005: measurement and evidence are required now. Acceptance is DEFERRED to noncontact_acceptance until TARGET_ACCURACY_BUDGET_CLOSED; collecting or measuring flatness does not accept its limit." : "NOT ASSESSED: observed value, method, time, operator, evidence references and uncertainty are still required."), facts(item.acceptance));
        group.append(row);
      }
      section.append(group);
    }
    const hazards = element("details"); hazards.append(element("summary", "", "Five open blocking hazards — required controls and evidence"));
    for (const hazard of value.hazards) {
      hazards.append(heading(hazard.id + ": " + hazard.title), element("p", "notice warning", "OPEN BLOCKING · received-hardware evidence unassessed"));
      for (const control of hazard.controls) hazards.append(element("p", "", "Required control: " + control));
      for (const evidence of hazard.required_evidence) hazards.append(element("p", "", "Required evidence: " + evidence));
      hazards.append(facts({fail_safe: hazard.fail_safe, evidence_stages: hazard.evidence_stages, invalidation_epochs: hazard.invalidation_epochs}));
    }
    section.append(hazards);
    const epochs = element("details"); epochs.append(element("summary", "", "Eight configuration dependencies — all UNMEASURED"));
    for (const epoch of value.epochs) epochs.append(heading(human(epoch.epoch_id)), element("p", "", epoch.description), facts({status: epoch.status, invalidates_from_stage: epoch.invalidates_from_stage, change_triggers: epoch.change_triggers, required_bindings: epoch.required_bindings}));
    section.append(epochs);
    if (value.metadata_selection) section.append(heading("Retained metadata context — not a received-unit measurement"), facts(value.metadata_selection));
    if (value.source_preflight) section.append(heading("Separate source-only report — not stage acceptance"), facts(value.source_preflight));
    section.append(heading("Remaining requirements")); const missing = element("ul", "action-blockers"); for (const code of value.missing_requirements) missing.append(element("li", "", code)); section.append(missing);
    return section;
  }

  function physicalCameraReopening(value) {
    const box = element("section", "physical-camera-reopening");
    box.append(heading("Discover and reopen original camera storage"), element("p", "notice warning", "Discovery reads bounded store metadata only; it does not qualify or open storage. Reopen explicitly rechecks one selected original store and audits M1 storage. Neither operation connects devices, retries a campaign, repairs a store or clears quarantine. No choice is selected automatically."),
      facts({status: value.status, discovery_sha256: value.discovery_sha256, current_launch_id: value.current_launch_id, source_sha256: value.source_sha256}), element("p", "caption", value.meaning));
    if (value.invalidation_reason) box.append(element("p", "notice warning", value.invalidation_reason));
    if (!value.stores.length) box.append(element("p", "caption", "No current selectable store metadata. Use an eligible explicit discovery action; the page does not search for stores."));
    for (const row of value.stores) {
      const store = element("details"); store.append(element("summary", "", `${row.origin_launch_id} / ${row.session_id} - ${row.status}`),
        element("span", "badge hold", row.selectable ? "METADATA ONLY / NOT OPENED" : "SOURCE DRIFT / REOPEN HELD"),
        element("p", "caption", row.selectable ? "Source match permits only an explicit selected-store recheck. It is not storage acceptance or hardware qualification." : "This original source differs. It has no selectable token and cannot be relabeled as the current build."), facts(row));
      box.append(store);
    }
    if (value.issues.length) { box.append(heading("Store metadata issues")); for (const issue of value.issues) box.append(element("p", "notice warning", `${issue.store_label || "Assigned store registry"}: ${issue.code} - ${issue.meaning}`)); }
    return box;
  }

  function workspaceSourceWorkflowProjection(value, setup) {
    // These are cached summaries, not a source collector or M1 reader. The
    // backend verifies full subject hashes; presentation cannot grant PASS.
    const v = cameraConfigurationValidators(), flags = ["physical_authority", "canonical_stage_pass", "device_io_performed"];
    const checks = ["controlled_build_sources", "foundation_semantics", "unchanged_file_snapshot", "runtime_fail_closed", "launcher_and_bootstrap_present", "base_software_ready", "static_camera_plan_selected"];
    const missing = ["DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED", "HZ_012_QUALIFICATION_EVIDENCE_MISSING", "STATIC_CAMERA_RELEASE_NOT_QUALIFIED"];
    const same = (a, b) => a !== null && b !== null && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => a[key] === b[key]);
    const label = item => v.string(item, 128) && item.trim() === item && !/\p{C}/u.test(item);
    const identifier = item => typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(item);
    const bound = item => v.exact(item, ["source_sha256", "session_id", "origin_launch_id", "collection_launch_id", "header_sha256", "prerequisites_sha256", "operator_id"])
      && ["source_sha256", "header_sha256", "prerequisites_sha256"].every(key => v.digest(item[key]))
      && ["session_id", "origin_launch_id", "collection_launch_id"].every(key => identifier(item[key])) && label(item.operator_id);
    const noAuthority = item => flags.every(key => item[key] === false) && item.power_state === "UNKNOWN";
    const software = items => Array.isArray(items) && items.length === checks.length && items.every((row, index) => v.exact(row, ["check_id", "passed"])
      && row.check_id === checks[index] && typeof row.passed === "boolean" && (index >= 3 || row.passed === true));
    const supplemental = value?.schema === "rocell.wizard_workspace_source_workflow.v2";
    if (!v.exact(value, ["schema", "status", "receipt", "assessment", "review", ...flags, "power_state", ...(supplemental ? ["original_source_state", "supplementary"] : [])])
      || !["rocell.wizard_workspace_source_workflow.v1", "rocell.wizard_workspace_source_workflow.v2"].includes(value.schema) || !noAuthority(value)
      || !["NOT_STARTED", "REVIEW_PENDING", "REVIEWED_BLOCKED", "HISTORICAL_HELD"].includes(value.status)) return null;
    const r = value.receipt, a = value.assessment, review = value.review;
    if (supplemental && value.status === "NOT_STARTED") return value.original_source_state === "BLOCKED" && value.supplementary === null && r === null && a === null && review === null && setup.publication.status === "PENDING" ? value : null;
    if (supplemental && (value.original_source_state !== "BLOCKED" || !["REVIEWED_BLOCKED", "HISTORICAL_HELD"].includes(value.status) || !r || !a || !review
      || !v.exact(value.supplementary, ["collection_id", "state"]) || typeof value.supplementary.collection_id !== "string" || !/^intake-[0-9a-f]{32}$/.test(value.supplementary.collection_id)
      || !["WAITING_OPERATOR", "REVIEW_PENDING", "BLOCKED"].includes(value.supplementary.state))) return null;
    if (value.status === "NOT_STARTED") return r === null && a === null && review === null ? value : null;
    if (r !== null && (!v.exact(r, ["schema", "status", "binding", "receipt_sha256", "software_checks", "source_file_count", "foundation_contract_count", "host_blocker_count", ...flags, "power_state"])
      || r.schema !== "rocell.workspace_source_receipt_summary.v1" || r.status !== "FILE_FACTS_COLLECTED" || !bound(r.binding) || !v.digest(r.receipt_sha256) || !software(r.software_checks) || !noAuthority(r)
      || !v.integer(r.source_file_count, 0, 128) || !v.integer(r.foundation_contract_count, 0, 32) || !v.integer(r.host_blocker_count, 0, 64))) return null;
    if (a !== null && (!r || !v.exact(a, ["schema", "status", "verdict", "binding", "receipt_sha256", "assessment_sha256", "software_checks", "missing_requirements", ...flags, "power_state"])
      || a.schema !== "rocell.workspace_source_assessment_summary.v1" || a.status !== "ASSESSED" || a.verdict !== "BLOCKED" || !bound(a.binding) || !same(a.binding, r.binding)
      || a.receipt_sha256 !== r.receipt_sha256 || !v.digest(a.assessment_sha256) || !software(a.software_checks) || !noAuthority(a)
      || !a.software_checks.every((row, index) => row.passed === r.software_checks[index].passed)
      || !Array.isArray(a.missing_requirements) || JSON.stringify(a.missing_requirements) !== JSON.stringify([...missing, ...(a.software_checks.some(row => !row.passed) ? ["SOFTWARE_PREREQUISITES_NOT_READY"] : [])]))) return null;
    if (review !== null && (!a || !v.exact(review, ["schema", "status", "verdict", "binding", "receipt_sha256", "assessment_sha256", "review_sha256", "reviewer_id", "review_launch_id", "distinct_operator_labels", "authenticated_independent_people", ...flags, "power_state"])
      || review.schema !== "rocell.workspace_source_review_summary.v1" || review.status !== "ACKNOWLEDGED_BLOCKED" || review.verdict !== "BLOCKED" || !bound(review.binding) || !same(review.binding, r.binding)
      || review.receipt_sha256 !== r.receipt_sha256 || review.assessment_sha256 !== a.assessment_sha256 || !v.digest(review.review_sha256)
      || !label(review.reviewer_id) || review.reviewer_id === r.binding.operator_id || !identifier(review.review_launch_id)
      || review.distinct_operator_labels !== true || review.authenticated_independent_people !== false || !noAuthority(review))) return null;
    if (value.status === "REVIEW_PENDING" && (!r || !a || review !== null)) return null;
    if (value.status === "REVIEWED_BLOCKED" && (!r || !a || !review)) return null;
    if (["REVIEW_PENDING", "REVIEWED_BLOCKED"].includes(value.status)) {
      const original = setup.session.binding, verified = setup.session.verification, prerequisites = setup.prerequisites;
      if (setup.publication.status !== "CURRENT" || !verified || !prerequisites
        || r.binding.source_sha256 !== setup.source_sha256 || r.binding.session_id !== original.session_id || r.binding.origin_launch_id !== original.launch_id
        || r.binding.header_sha256 !== verified.session.header_sha256 || r.binding.prerequisites_sha256 !== prerequisites.evidence_sha256
        || setup.session.stages[0].stage !== "workspace_sources" || setup.session.stages[0].state !== (supplemental ? value.supplementary.state : value.status === "REVIEW_PENDING" ? "REVIEW_PENDING" : "BLOCKED")) return null;
    }
    return value;
  }

  function workspaceSourceWorkflow(setup) {
    const box = element("section", "workspace-source-workflow");
    box.append(heading("Saved workspace-source assessment and review"), element("span", "badge hold", "PHYSICAL ACCEPTANCE BLOCKED"), element("p", "notice warning", "Successful file collection and saved review are not a physical PASS. Disconnected actuator power and HZ-012 qualification are not established by file hashes or consent boxes. No power, device opening, motion or contact is authorized."));
    const input = setup.source_workflow;
    if (input === undefined || input === null) { box.append(element("p", "caption", "No source-stage workflow summary is available in this snapshot. Legacy exports remain read-only; no receipt or review is inferred.")); return box; }
    if (setup.publication.status === "PENDING") { box.append(element("p", "notice warning", "Source-stage publication pending. Receipt and review details are withheld until original-store audit and completion logging succeed.")); return box; }
    const value = workspaceSourceWorkflowProjection(input, setup);
    if (!value) { box.append(element("p", "notice warning", "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED: Inconsistent cached subject chain or publication withheld. Inspect original diagnostics; no assessment, review or stage acceptance is inferred.")); return box; }
    box.append(element("p", "", `Workflow: ${value.status}; power observation: UNKNOWN`));
    if (value.status === "NOT_STARTED") box.append(element("p", "caption", "No saved source receipt, assessment or review. Assessment and independent review are separate explicit file-only actions."));
    if (value.status === "HISTORICAL_HELD" || setup.publication.status === "HISTORICAL_HELD") box.append(element("p", "notice warning", "Historical original source evidence only; not a current audited stage result. Preserve the original subject chain. Do not recollect, replay or relabel a receipt to clear this hold."));
    const r = value.receipt, a = value.assessment, review = value.review;
    if (r) {
      box.append(heading("Actual retained software facts — separate from missing physical prerequisites"));
      for (const [key, item] of Object.entries({...r.binding, receipt_sha256: r.receipt_sha256, source_file_count: r.source_file_count, foundation_contract_count: r.foundation_contract_count, host_blocker_count: r.host_blocker_count})) box.append(element("p", "", `${key}: ${item}`));
      box.append(element("p", "caption", `Current application launch: ${setup.launch_session_id}. Collection launch: ${r.binding.collection_launch_id}. Original storage launch: ${r.binding.origin_launch_id}. Stored authorship is not rewritten on reopen.`));
      for (const row of r.software_checks) box.append(element("p", "", `${row.check_id}: ${row.passed ? "SOFTWARE_CHECK_PASSED" : "SOFTWARE_CHECK_BLOCKED"}`));
    }
    if (a) { box.append(heading("Saved assessment verdict: BLOCKED"), element("p", "", `Assessment: ${a.assessment_sha256}`), heading("Missing prerequisite evidence")); for (const reason of a.missing_requirements) box.append(element("p", "notice warning", reason)); }
    if (value.status === "REVIEW_PENDING") box.append(element("p", "notice warning", "Original stage is REVIEW_PENDING. A different reviewer must review this exact BLOCKED assessment; no control can change it to PASS."));
    if (review) {
      box.append(heading("Exact-subject independent review — ACKNOWLEDGED_BLOCKED"), element("p", "", `Reviewer: ${review.reviewer_id}; review launch: ${review.review_launch_id}`), element("p", "", `Review: ${review.review_sha256}`), element("p", "caption", "Distinct labels record procedure, not authenticated independent people. The review acknowledges BLOCKED and cannot upgrade missing physical evidence."));
      if (value.status === "REVIEWED_BLOCKED") box.append(element("p", "notice warning", value.schema === "rocell.wizard_workspace_source_workflow.v2"
        ? `Original source assessment/review remains BLOCKED. Current supplementary intake stage: ${value.supplementary.state}. This is a different subject, not a replacement source verdict or a physical PASS.`
        : "Original workspace_sources stage: BLOCKED. Later physical stages remain held; a saved review does not clear isolation or HZ-012 obligations."));
    }
    box.append(element("p", "caption", "Export the complete original workflow to the assigned folder. This panel uses cached summaries only: no file collection, M1 readback, assessment, review or device access occurs on render."));
    return box;
  }

  function physicalConfigurationRecordsProjection(value, setup) {
    const v = cameraConfigurationValidators(), stages = physicalSetupValidators().stages;
    if (!v.exact(value, ["schema", "status", "summary", "physical_authority", "hardware_qualified"])
      || value.schema !== "rocell.wizard_physical_configuration_records.v1" || !["NOT_RETAINED", "CURRENT", "HISTORICAL_HELD"].includes(value.status)
      || value.physical_authority !== false || value.hardware_qualified !== false) return null;
    if (setup.publication.status === "PENDING" && (value.status !== "NOT_RETAINED" || value.summary !== null)) return null;
    if (value.status === "NOT_RETAINED") return value.summary === null ? value : null;
    if (value.summary === null) return value.status === "HISTORICAL_HELD" ? value : null;
    const s = value.summary, b = s.binding, snapshot = s.original_snapshot, boundary = s.boundary;
    const current = value.status === "CURRENT", verified = setup.session.verification, prerequisites = setup.prerequisites;
    if (current && (setup.publication.status !== "CURRENT" || !verified || !prerequisites)) return null;
    if (!v.exact(s, ["schema", "record_sha256", "binding", "original_snapshot", "boundary", "entries", "coverage", "physical_authority", "qualified", "canonical_stage_pass", "admission_allowed", "device_io_performed", "meaning"])
      || s.schema !== "rocell.physical_configuration_epochs_summary.v1" || !v.digest(s.record_sha256) || !v.string(s.meaning, 512)
      || !["physical_authority", "qualified", "canonical_stage_pass", "admission_allowed", "device_io_performed"].every(key => s[key] === false)
      || !v.exact(b, ["source_sha256", "source_binding_sha256", "session_id", "cell_id", "origin_launch_id", "session_header_sha256", "prerequisites_sha256", "epoch_policy_sha256", "stage_catalog_sha256"])
      || !["source_sha256", "source_binding_sha256", "session_header_sha256", "prerequisites_sha256", "epoch_policy_sha256", "stage_catalog_sha256"].every(key => v.digest(b[key]))
      || b.source_sha256 !== setup.source_sha256 || b.session_id !== setup.session.binding.session_id || b.cell_id !== setup.session.binding.cell_id || b.origin_launch_id !== setup.session.binding.launch_id
      || (verified && (b.session_header_sha256 !== verified.session.header_sha256 || b.source_binding_sha256 !== verified.cell.source_binding_sha256))
      || (prerequisites && (b.prerequisites_sha256 !== prerequisites.evidence_sha256 || b.epoch_policy_sha256 !== prerequisites.source_files.find(row => row.role === "epoch_policy").sha256 || b.stage_catalog_sha256 !== prerequisites.source_files.find(row => row.role === "stage_catalog").sha256))
      || !v.exact(snapshot, ["head_sha256", "event_count", "evidence_inventory_sha256", "reference_count"]) || !v.digest(snapshot.head_sha256) || !v.digest(snapshot.evidence_inventory_sha256)
      || !v.integer(snapshot.event_count, 0, 512) || !v.integer(snapshot.reference_count, 0, 32)
      || !v.exact(boundary, ["stage", "phase"]) || !stages.includes(boundary.stage) || !["BEFORE_STAGE", "AFTER_STAGE"].includes(boundary.phase)
      || !Array.isArray(s.entries) || s.entries.length !== 8) return null;
    const domains = ["software_build", "camera_support_optics", "board_tags_bench", "arm_controller_tool", "power_system", "keyboard_station", "phone_station", "empty_cell_safety"];
    const starts = [0, 2, 2, 8, 9, 12, 12, 9];
    const bindings = [
      [["build_snapshot",0],["source_binding",0],["dependency_receipt",0],["provider_hashes",0]],
      [["camera_receipt",2],["camera_identity",3],["camera_mode_controls",4],["support_witnesses",7]],
      [["board_measurement",2],["tag_map",7],["bench_identity",2],["board_reseat_test",7]],
      [["arm_identity",8],["controller_identity",11],["firmware_identity",11],["tool_identity",12]],
      [["power_topology",9],["cutoff_test",9],["containment_review",9],["discharge_test",9]],
      [["keyboard_identity",12],["keyboard_pose",12],["keyboard_target_map",12]],
      [["phone_identity",12],["phone_pose",12],["screen_homography",12],["phone_target_map",12],["ui_state",12]],
      [["installed_object_inventory",9],["collision_geometry",13],["startup_sweep",10],["empty_cell_witness",9]]
    ];
    const statusKeys = {RETAINED_REFERENCE_UNASSESSED:"retained", MISSING_PREDECESSOR:"missing_predecessors", MISSING_CURRENT_OUTPUT:"missing_current_outputs", PENDING_CURRENT_OUTPUT:"pending_current_outputs", PENDING_FUTURE_OUTPUT:"pending_future_outputs"};
    const counts = Object.fromEntries(Object.values(statusKeys).map(key => [key, 0])), index = stages.indexOf(boundary.stage);
    for (let domain = 0; domain < s.entries.length; domain++) {
      const entry = s.entries[domain];
      if (!v.exact(entry, ["epoch_id", "invalidates_from_stage", "status", "bindings"]) || entry.epoch_id !== domains[domain] || entry.invalidates_from_stage !== stages[starts[domain]]
        || !Array.isArray(entry.bindings) || entry.bindings.length !== bindings[domain].length) return null;
      let retained = 0;
      for (let item = 0; item < entry.bindings.length; item++) {
        const row = entry.bindings[item], [id, owner] = bindings[domain][item];
        const relation = owner < index ? "PREDECESSOR" : owner === index ? "CURRENT_STAGE" : "FUTURE_STAGE";
        if (!v.exact(row, ["binding_id", "owner_stage", "relative_position", "status", "evidence_count", "payload_sha256s"]) || row.binding_id !== id || row.owner_stage !== stages[owner] || row.relative_position !== relation
          || !v.integer(row.evidence_count, 0, 4) || row.evidence_count > snapshot.reference_count || !Array.isArray(row.payload_sha256s) || row.payload_sha256s.length !== row.evidence_count || !row.payload_sha256s.every(v.digest)) return null;
        const expected = row.evidence_count ? "RETAINED_REFERENCE_UNASSESSED" : owner < index ? "MISSING_PREDECESSOR" : owner > index ? "PENDING_FUTURE_OUTPUT" : boundary.phase === "BEFORE_STAGE" ? "PENDING_CURRENT_OUTPUT" : "MISSING_CURRENT_OUTPUT";
        if (row.status !== expected) return null;
        counts[statusKeys[expected]]++; if (row.evidence_count) retained++;
      }
      if (entry.status !== (!retained ? "UNOBSERVED" : retained === entry.bindings.length ? "REFERENCES_RETAINED_UNASSESSED" : "PARTIALLY_REFERENCED")) return null;
    }
    if (!v.exact(s.coverage, ["total_bindings", ...Object.keys(counts)]) || s.coverage.total_bindings !== 32 || !Object.keys(counts).every(key => v.integer(s.coverage[key], 0, 32) && s.coverage[key] === counts[key])) return null;
    return value;
  }

  function physicalConfigurationRecords(setup) {
    const box = element("section", "physical-configuration-records");
    box.append(heading("Eight-domain configuration records — unqualified dependencies"), element("span", "badge hold", "NO ADMISSION / NO QUALIFICATION"));
    if (setup.schema !== "rocell.wizard_physical_camera_setup.v3") {
      box.append(element("p", "caption", "NOT_RETAINED: this legacy snapshot has no progressive configuration record. No record was inferred or created.")); return box;
    }
    const value = physicalConfigurationRecordsProjection(setup.configuration_records, setup);
    if (!value) { box.append(element("p", "notice warning", "CONFIGURATION_RECORDS_NOT_VERIFIED: inconsistent, unsupported or oversized projection withheld. Original evidence is not replaced or automatically recollected.")); return box; }
    box.append(element("p", "", `Record publication: ${value.status}`));
    if (value.status === "HISTORICAL_HELD") box.append(element("p", "notice warning", "Historical original configuration context only — not a current observation or acquisition permission."));
    if (!value.summary) { box.append(element("p", "caption", setup.publication.status === "PENDING" ? "Configuration details withheld until explicit operation publication completes. No retained record is inferred from pending work." : "No progressive record is available in this snapshot. Refresh does not create missing records or upgrade legacy evidence.")); return box; }
    const s = value.summary;
    box.append(element("p", "notice warning", "Retained references are UNASSESSED, not accepted observations. Pending outputs are not missing predecessors and waive no earlier hazard, isolation, firmware or runtime prerequisite."),
      facts({record_sha256:s.record_sha256, boundary_stage:s.boundary.stage, boundary_phase:s.boundary.phase}), facts(s.binding),
      heading("Original recorded boundary — not the latest session head"), facts(s.original_snapshot), facts(s.coverage), element("p", "caption", s.meaning));
    for (const entry of s.entries) {
      const group = element("details"); group.append(element("summary", "", `${entry.epoch_id}: ${entry.status}`), element("p", "", `Invalidates from: ${entry.invalidates_from_stage}`));
      for (const row of entry.bindings) {
        group.append(element("p", "", `${row.binding_id}: ${row.status} · ${row.relative_position} · producer ${row.owner_stage} · ${row.evidence_count} retained references`));
        for (const digest of row.payload_sha256s) group.append(element("p", "", `payload_sha256: ${digest}`));
      }
      box.append(group);
    }
    box.append(element("p", "caption", "The original prerequisite epoch requirements remain UNMEASURED. This immutable record describes its original boundary; later review does not recalculate it. No device control, canonical stage PASS, successor record or automatic retry is provided."));
    return box;
  }

  const cameraModeEntryFlags = ["arm_access_authorized", "authenticated_operator_identity", "camera_capture_authorized", "device_io_performed", "hardware_qualified", "native_release_allowed", "physical_authority"];
  const cameraModeEntryMeaning = "Setup entry only, not a camera connection. Probe, settings, images, arm startup and movement require separate later steps. Partial entries are diagnostic-only and are not automatically retried.";
  function cameraModeEntryValid(value, setup) {
    try {
      const v = cameraConfigurationValidators(), e = value?.entry, a = value?.attempt;
      const match = (x, pattern) => typeof x === "string" && pattern.test(x);
      if (!v.exact(value, ["schema", "source_sha256", "launch_session_id", "publication", "status", "entry", "attempt", "attempted", "next_action", "meaning", ...cameraModeEntryFlags])
        || value.schema !== "rocell.wizard_camera_mode_entry.v1" || !v.digest(value.source_sha256) || !match(value.launch_session_id, /^wizard-[0-9a-f]{32}$/)
        || value.source_sha256 !== setup.source_sha256 || value.launch_session_id !== setup.launch_session_id
        || !v.exact(value.publication, ["status", "operation_id"]) || value.publication.status !== setup.publication.status || value.publication.operation_id !== setup.publication.operation_id
        || !["CURRENT", "PENDING", "NOT_PUBLISHED", "HISTORICAL_HELD"].includes(value.publication.status)
        || typeof value.attempted !== "boolean" || value.meaning !== cameraModeEntryMeaning || !cameraModeEntryFlags.every(k => value[k] === false)) return false;
      const current = value.publication.status === "CURRENT", status = value.status;
      if (e !== null) {
        if (!v.exact(e, ["entry_id", "entry_sha256", "state", "session_id", "cell_id", "origin_launch_id", "entry_launch_id", "header_sha256", "selected_identity_sha256", "complete_review_sha256", "operator_id"])
          || !["INCOMPLETE", "ENTERED"].includes(e.state) || !match(e.entry_id, /^cameramode-[0-9a-f]{32}$/) || !match(e.session_id, /^physical-camera-[0-9a-f]{32}$/) || !match(e.cell_id, /^wizard-physical-camera-[0-9a-f]{16}$/)
          || !["origin_launch_id", "entry_launch_id"].every(k => match(e[k], /^wizard-[0-9a-f]{32}$/))
          || !["entry_sha256", "header_sha256", "selected_identity_sha256", "complete_review_sha256"].every(k => v.digest(e[k]))
          || typeof e.operator_id !== "string" || e.operator_id.trim() !== e.operator_id || !e.operator_id.length || new TextEncoder().encode(e.operator_id).length > 64 || /[\x00-\x1f\x7f\ud800-\udfff]/u.test(e.operator_id)) return false;
        if (current && (e.session_id !== setup.session.binding.session_id || e.cell_id !== setup.session.binding.cell_id || e.origin_launch_id !== setup.session.binding.launch_id || e.header_sha256 !== setup.session.verification.session.header_sha256)) return false;
      }
      if (a !== null && (!v.exact(a, ["entry_id", "entry_sha256", "retention", "event_count"]) || value.attempted !== true
        || !match(a.entry_id, /^cameramode-[0-9a-f]{32}$/) || !v.digest(a.entry_sha256)
        || !["COLLECTED_NOT_M1_RETAINED", "M1_PUBLICATION_UNCONFIRMED", "M1_PUBLISHED_READBACK_PENDING", "M1_FULL_BYTES_READ_BACK"].includes(a.retention)
        || !Number.isInteger(a.event_count) || a.event_count < 0 || a.event_count > 1 || (a.event_count !== 0 && a.retention !== "M1_FULL_BYTES_READ_BACK")
        || (e !== null && (a.entry_id !== e.entry_id || a.entry_sha256 !== e.entry_sha256)))) return false;
      if (value.next_action !== (status === "READY_TO_ENTER" ? "physical_camera_mode_enter" : null)) return false;
      if (status === "PENDING_PUBLICATION") return value.publication.status === "PENDING" && e === null && a === null;
      if (value.publication.status === "PENDING") return false;
      if (status === "HISTORICAL_HELD") return (e !== null || value.attempted) && (!current || e === null);
      if (status === "NOT_STARTED") return e === null && a === null && !value.attempted;
      if (!["READY_TO_ENTER", "ENTERED", "ENTERED_PREPARATION_PENDING_REVIEW", "INCOMPLETE_HELD"].includes(status) || !current) return false;
      if (status === "READY_TO_ENTER") { if (e !== null || a !== null || value.attempted) return false; }
      else if (e === null || e.state !== (["ENTERED", "ENTERED_PREPARATION_PENDING_REVIEW"].includes(status) ? "ENTERED" : "INCOMPLETE")) return false;
      const stages = setup.session.stages;
      return Array.isArray(stages) && stages.length === 15 && stages.slice(0, 4).every(r => r.state === "PASS")
        && stages[4].state === (status === "ENTERED_PREPARATION_PENDING_REVIEW" ? "BLOCKED" : status === "ENTERED" ? "WAITING_OPERATOR" : "PENDING") && stages.slice(5).every(r => r.state === "PENDING");
    } catch (_) { return false; }
  }

  function cameraModeEntry() {
    const box = card("Camera setup entry", "From reviewed identity to mode/control commissioning"), value = state.view.camera_mode_entry;
    const setup = physicalSetupValidators().setup(state.view.physical_camera_setup);
    if (value === undefined || value === null) { box.append(element("p", "caption", "No camera setup entry has been published.")); return box; }
    if (!setup || !cameraModeEntryValid(value, setup)) { box.append(element("p", "notice warning", "CAMERA_MODE_ENTRY_NOT_VERIFIED: Inconsistent camera-entry display withheld. Inspect/export diagnostics; no automatic retry.")); return box; }
    box.append(element("span", "badge hold", "NO CAMERA OR ARM ACCESS"), facts({status:value.status, publication:value.publication.status, attempted:value.attempted}), element("p", "caption", value.meaning));
    if (value.entry) box.append(heading("Original setup entry"), facts(value.entry));
    if (value.attempt) box.append(heading("Retained attempt"), facts(value.attempt));
    if (value.next_action && state.view.actions.some(a => a.action_id === value.next_action && a.enabled)) {
      const button = element("button", "secondary", "Continue to camera setup");
      button.addEventListener("click", () => {
        const target = document.getElementById("camera-action-" + value.next_action);
        if (target) { target.scrollIntoView({block:"start"}); target.focus({preventScroll:true}); }
      });
      box.append(button, element("p", "caption", "Opens the explicit action form only. Review its preview before execution."));
    }
    return box;
  }

  // A deliberately small projection: compound originals/attempts belong in
  // the separate bounded export, not repeated in every poll or result card.
  function cameraProbeSetupValid(value, setup) {
    try {
      const v = cameraConfigurationValidators();
      const fields = ["schema", "source_sha256", "launch_session_id", "publication", "state", "preparation_sha256", "review_sha256", "attempts", "export_available", "export_action", "original_documents_included", "physical_authority", "hardware_qualified", "connected", "meaning"];
      if (!v.exact(value, fields) || value.schema !== "rocell.wizard_camera_probe_setup.v1"
        || value.source_sha256 !== setup.source_sha256 || value.launch_session_id !== setup.launch_session_id
        || !v.exact(value.publication, ["status", "operation_id"]) || value.publication.status !== setup.publication.status || value.publication.operation_id !== setup.publication.operation_id
        || !["CURRENT", "PENDING", "NOT_PUBLISHED", "HISTORICAL_HELD"].includes(value.publication.status)
        || !["NOT_PREPARED", "PENDING_PUBLICATION", "INCOMPLETE", "PREPARED_REVIEW_REQUIRED", "REVIEWED_FOR_ADMISSION"].includes(value.state)
        || !["preparation_sha256", "review_sha256"].every(k => value[k] === null || v.digest(value[k]))
        || !["physical_authority", "hardware_qualified", "connected", "original_documents_included"].every(k => value[k] === false)
        || typeof value.export_available !== "boolean" || value.export_action !== "physical_camera_probe_export"
        || value.meaning !== "File-only preparation/review. CURRENT describes logged records, not camera admission. Inspect incomplete attempts; no automatic retry. Camera access and arm movement remain held."
        || !value.attempts || Array.isArray(value.attempts) || typeof value.attempts !== "object") return false;
      const states = ["QUEUED_NOT_DISPATCHED", "ORIGINAL_READ_PENDING", "RECORD_COLLECTED", "COMMIT_UNCONFIRMED", "COMMITTED_READBACK_PENDING", "ORIGINAL_READ_BACK"];
      for (const [key, attempt] of Object.entries(value.attempts)) {
        if (!["physical_camera_probe_prepare", "physical_camera_probe_review"].includes(key)
          || !v.exact(attempt, ["claimed", "status"]) || typeof attempt.claimed !== "boolean" || !states.includes(attempt.status)) return false;
      }
      if (value.state === "PENDING_PUBLICATION") return value.publication.status === "PENDING" && value.preparation_sha256 === null && value.review_sha256 === null;
      if (value.publication.status === "PENDING") return false;
      if (value.state === "NOT_PREPARED" && (value.preparation_sha256 !== null || value.review_sha256 !== null)) return false;
      if (["PREPARED_REVIEW_REQUIRED", "REVIEWED_FOR_ADMISSION"].includes(value.state)) {
        if (!v.digest(value.preparation_sha256) || !value.export_available || (value.state === "PREPARED_REVIEW_REQUIRED" ? value.review_sha256 !== null : !v.digest(value.review_sha256))) return false;
        if (value.publication.status === "CURRENT") {
          const stages = setup.session.stages;
          if (!Array.isArray(stages) || stages.length !== 15 || !stages.slice(0, 4).every(r => r.state === "PASS") || !stages.slice(5).every(r => r.state === "PENDING") || stages[4].state !== (value.state === "PREPARED_REVIEW_REQUIRED" ? "BLOCKED" : "WAITING_OPERATOR")) return false;
        }
      }
      return true;
    } catch (_) { return false; }
  }

  function cameraProbeSetup() {
    const box = card("Bounded camera probe preparation", "Prepare → review → separate admission; no automatic connection");
    const value = state.view.camera_probe_setup, setup = physicalSetupValidators().setup(state.view.physical_camera_setup);
    if (value === undefined) { box.append(element("p", "caption", "No probe preparation was included in this older snapshot.")); return box; }
    if (!setup || !cameraProbeSetupValid(value, setup)) { box.append(element("p", "notice warning", "CAMERA_PROBE_SETUP_NOT_VERIFIED: Inconsistent preparation display withheld. Inspect/export diagnostics.")); return box; }
    box.append(element("span", "badge hold", "NO CAMERA OR ARM ACCESS"), facts({state:value.state, publication:value.publication.status, preparation_sha256:value.preparation_sha256, review_sha256:value.review_sha256}), element("p", "caption", value.meaning));
    for (const [action, attempt] of Object.entries(value.attempts)) box.append(heading(human(action)), facts(attempt));
    box.append(element("p", "caption", "Use the explicit camera action forms below. Review the exact preview before confirming. A preparation review does not run the probe."));
    if (value.export_available) {
      const button = element("button", "secondary", "Open preparation export form");
      button.addEventListener("click", () => navigate("diagnostics"));
      box.append(button, element("p", "caption", "Diagnostics & exports contains the separate full preparation bundle. Opening that tab does not export or replay anything."));
    }
    return box;
  }

  function cameraProbeAttemptValid(value, view) {
    const v = cameraConfigurationValidators();
    const phases = ["NOT_ATTEMPTED", "AUTHENTICATING_ORIGINALS", "ORIGINALS_AUTHENTICATED", "ADMISSION_DERIVED", "RESULT_STAGED_NOT_PUBLISHED", "FAILED_HELD"];
    const keys = ["schema", "source_sha256", "launch_session_id", "status", "failed_phase", "queued", "claimed", "operation_id", "outcome", "export_available", "export_action", "physical_authority", "hardware_qualified", "connected", "meaning"];
    if (!v.exact(value, keys) || value.schema !== "rocell.wizard_camera_probe_attempt.v1"
      || !v.digest(value.source_sha256) || value.source_sha256 !== view.source_binding_sha256
      || value.launch_session_id !== view.session_id || !/^wizard-[0-9a-f]{32}$/.test(value.launch_session_id)
      || !phases.includes(value.status) || (value.failed_phase !== null && (!phases.includes(value.failed_phase) || value.status !== "FAILED_HELD"))
      || ["physical_authority", "hardware_qualified", "connected"].some(k => value[k] !== false)
      || ["queued", "claimed", "export_available"].some(k => typeof value[k] !== "boolean")
      || (value.claimed && !value.queued) || (value.queued ? !/^operation-[0-9a-f]{32}$/.test(value.operation_id) : value.operation_id !== null)
      || (value.queued || value.status !== "NOT_ATTEMPTED") !== value.export_available
      || (value.outcome !== null && !["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(value.outcome))
      || value.export_action !== "physical_camera_probe_attempt_export"
      || typeof value.meaning !== "string" || value.meaning.length > 512) return false;
    return true;
  }

  function cameraProbeAttempt() {
    const box = card("Selected-camera capability probe", "One explicit attempt → original readback → logged result");
    const value = state.view.camera_probe_attempt;
    if (value === undefined) { box.append(element("p", "caption", "This older snapshot does not include probe-attempt status.")); return box; }
    if (!cameraProbeAttemptValid(value, state.view)) { box.append(element("p", "notice warning", "CAMERA_PROBE_ATTEMPT_NOT_VERIFIED: Inconsistent status withheld. Inspect diagnostics; do not retry.")); return box; }
    box.append(element("span", "badge hold", "NO ARM ACCESS OR AUTOMATIC CAPTURE"), facts({last_retained_phase:value.status, queued:value.queued, claimed:value.claimed, operation_id:value.operation_id, logged_outcome:value.outcome, failed_phase:value.failed_phase}), element("p", "caption", value.meaning));
    box.append(element("p", "caption", "The last retained admission phase precedes completion logging. Check the logged outcome and the current capability panel together; neither grants arm access."));
    box.append(element("p", "caption", "Use the explicit probe form only after setup preparation and review. It may open the selected camera for capability reporting, without changing controls or capturing images. A disconnected actuator supply is an operator report, not a measured power state."));
    if (value.export_available) {
      const button = element("button", "secondary", "Open probe-attempt export form");
      button.addEventListener("click", () => navigate("diagnostics"));
      box.append(button, element("p", "caption", "The separate attempt bundle includes retained admission, native run/supervision and completion diagnostics. General logs contain only its pointer. Opening the form does not export or reconnect."));
    }
    return box;
  }

  function cameraOperatingProposalValid(value, view) {
    const exact=(x,k)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===k.length&&k.every(n=>Object.hasOwn(x,n));
    const sha=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)&&x!=='0'.repeat(64);
    const flags=['physical_authority','hardware_qualified','approved_operating_policy','original_stage_record_retained','connected'];
    const keys=['schema','source_sha256','launch_session_id','current_operation_id','proposal','attempted','maximum_attempts','action_id','state','meaning',...flags];
    const meaning='Logged proposal draft from cached subjects, not original-stage storage or operating-policy approval. No settings are applied and no device is opened. Export before closing; a fresh launch restores no current proposal.';
    if(!exact(value,keys)||value.schema!=='rocell.wizard_camera_operating_proposal.v1'||value.action_id!=='physical_camera_operating_proposal'
      ||!sha(value.source_sha256)||value.source_sha256!==view.source_binding_sha256||value.launch_session_id!==view.session_id
      ||typeof value.launch_session_id!=='string'||!/^wizard-[0-9a-f]{32}$/.test(value.launch_session_id)
      ||flags.some(k=>value[k]!==false)||!Number.isInteger(value.attempted)||value.attempted<0||value.attempted>8
      ||value.maximum_attempts!==8||value.meaning!==meaning
      ||!['NOT_STARTED','PENDING_PUBLICATION','HISTORICAL_HELD','LOGGED_DRAFT_NOT_APPROVED'].includes(value.state)
      ||((value.state==='NOT_STARTED')!==(value.attempted===0)))return false;
    if(value.state!=='LOGGED_DRAFT_NOT_APPROVED')return value.proposal===null&&value.current_operation_id===null;
    if(typeof value.current_operation_id!=='string'||!/^operation-[0-9a-f]{32}$/.test(value.current_operation_id))return false;
    const p=value.proposal;
    if(!exact(p,['proposal_sha256','policy_kind','target_mode','settings_epoch'])||!sha(p.proposal_sha256)||!sha(p.settings_epoch))return false;
    const m=p.target_mode;
    if(!exact(m,['width','height','fps_numerator','fps_denominator','subtype','stride_bytes'])||m.width!==5472||m.height!==3648||m.subtype!=='YUY2'
      ||![m.fps_numerator,m.fps_denominator].every(n=>Number.isInteger(n)&&n>0&&n<=1000000)
      ||!(m.stride_bytes===null||(Number.isInteger(m.stride_bytes)&&m.stride_bytes!==0&&Math.abs(m.stride_bytes)<=1048576)))return false;
    return (m.fps_numerator===9*m.fps_denominator&&p.policy_kind==='REFERENCE_9_FPS_PROPOSAL')
      ||(m.fps_numerator===8*m.fps_denominator&&p.policy_kind==='EXPLICIT_8_FPS_VARIANCE_PROPOSAL');
  }

  function cameraOperatingProposal() {
    const box=card('Camera operating-mode proposal','Explicit rationale → logged draft → separate original-stage review still required');
    const value=state.view.camera_operating_proposal;
    if(value===undefined){box.append(element('p','caption','This older snapshot has no operating-proposal status.'));return box;}
    if(!cameraOperatingProposalValid(value,state.view)){box.append(element('p','notice warning','CAMERA_OPERATING_PROPOSAL_NOT_VERIFIED: Inconsistent status withheld. Inspect diagnostic exports.'));return box;}
    box.append(element('span','badge hold','DRAFT ONLY — NOT APPROVED'),facts({state:value.state,attempted:value.attempted,maximum_attempts:value.maximum_attempts}),element('p','caption',value.meaning));
    if(value.proposal)box.append(facts(value.proposal));
    box.append(element('p','caption','After recording a draft, find Check proposal against saved original evidence in Camera actions or Control Center and explicitly select the retained captures. Assessment is a separate file-only action, not stage-5 approval. Export diagnostics to the assigned folder before closing.'));
    return box;
  }

  function cameraOperatingSubmissionValid(value, view) {
    const exact=(x,k)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===k.length&&k.every(n=>Object.hasOwn(x,n));
    const sha=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)&&x!=='0'.repeat(64);
    const flags=['stage_passed','approved_operating_policy','connected','physical_authority','hardware_qualified'];
    const keys=['schema','source_sha256','launch_session_id','action_id','state','publication','original_stage_authenticated','submission_id','submission_sha256','proposal_sha256','assessment_sha256','reference','retention','capture_requests','attempted','maximum_attempts','review_required','pixel_check_semantics','meaning',...flags];
    const meaning='A saved submission is unreviewed historical evidence. Original authentication does not restore a connection, prove current pixels, qualify calibration or enable the arm.';
    if(!exact(value,keys)||value.schema!=='rocell.wizard_camera_operating_submission.v1'||value.action_id!=='physical_camera_operating_submit'
      ||!sha(value.source_sha256)||value.source_sha256!==view.source_binding_sha256||value.launch_session_id!==view.session_id
      ||typeof value.launch_session_id!=='string'||!/^wizard-[0-9a-f]{32}$/.test(value.launch_session_id)
      ||flags.some(k=>value[k]!==false)||value.review_required!==true||typeof value.original_stage_authenticated!=='boolean'
      ||!Number.isInteger(value.attempted)||value.attempted<0||value.attempted>3||value.maximum_attempts!==3
      ||value.pixel_check_semantics!=='HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION'||value.meaning!==meaning)return false;
    const p=value.publication;
    if(!exact(p,['status','operation_id'])||!['NOT_PUBLISHED','PENDING','CURRENT','HISTORICAL_HELD'].includes(p.status)
      ||!(p.operation_id===null||(typeof p.operation_id==='string'&&/^operation-[0-9a-f]{32}$/.test(p.operation_id)))
      ||(p.status==='CURRENT'&&p.operation_id===null))return false;
    const original=['INCOMPLETE','SUBMITTED_REVIEW_REQUIRED'].includes(value.state);
    if(value.original_stage_authenticated!==original||!['NOT_STARTED','RUNNING','AWAITING_COMPLETION_LOG','HISTORICAL_HELD','RETAINED_UNREVIEWED','INCOMPLETE','SUBMITTED_REVIEW_REQUIRED'].includes(value.state)
      ||(!original&&value.attempted===0&&value.state!=='NOT_STARTED'))return false;
    if(value.submission_id===null)return !original&&['NOT_STARTED','RUNNING','HISTORICAL_HELD'].includes(value.state)
      &&(value.state!=='NOT_STARTED'||value.attempted===0)&&['submission_sha256','proposal_sha256','assessment_sha256','reference','retention'].every(k=>value[k]===null)
      &&Array.isArray(value.capture_requests)&&value.capture_requests.length===0;
    if(value.state==='NOT_STARTED'||typeof value.submission_id!=='string'||!/^cameraoperating-[0-9a-f]{32}$/.test(value.submission_id)
      ||!['submission_sha256','proposal_sha256','assessment_sha256'].every(k=>sha(value[k]))||!Array.isArray(value.capture_requests)||value.capture_requests.length!==2
      ||!value.capture_requests.every(k=>typeof k==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(k))||new Set(value.capture_requests).size!==2
      ||!['COLLECTED_NOT_M1_RETAINED','M1_PUBLICATION_UNCONFIRMED','M1_PUBLISHED_READBACK_PENDING','M1_FULL_BYTES_READ_BACK'].includes(value.retention))return false;
    if(value.reference===null)return !original&&['COLLECTED_NOT_M1_RETAINED','M1_PUBLICATION_UNCONFIRMED'].includes(value.retention);
    const r=value.reference;
    return exact(r,['evidence_id','stage','package_sha256','manifest_sha256','payload_sha256','payload_bytes'])
      &&['package_sha256','manifest_sha256','payload_sha256'].every(k=>sha(r[k]))&&r.evidence_id==='evidence-'+r.package_sha256
      &&r.stage==='camera_mode_controls'&&r.payload_sha256===value.submission_sha256&&Number.isInteger(r.payload_bytes)&&r.payload_bytes>0&&r.payload_bytes<=81920
      &&['M1_PUBLISHED_READBACK_PENDING','M1_FULL_BYTES_READ_BACK'].includes(value.retention)&&(!original||value.retention==='M1_FULL_BYTES_READ_BACK');
  }

  function cameraOperatingSubmission() {
    const box=card('Camera evidence saved for review','Proposal + two explicit captures → original submission → separate review');
    const value=state.view.camera_operating_submission;
    if(value===undefined){box.append(element('p','caption','This older snapshot has no original-submission status.'));return box;}
    if(!cameraOperatingSubmissionValid(value,state.view)){box.append(element('p','notice warning','CAMERA_OPERATING_SUBMISSION_NOT_VERIFIED: Inconsistent status withheld. Inspect diagnostic exports.'));return box;}
    box.append(element('span','badge hold','UNREVIEWED — NO CAMERA OR ARM AUTHORITY'),facts({state:value.state,publication:value.publication.status,original_stage_authenticated:value.original_stage_authenticated}),element('p','caption',value.meaning));
    if(value.submission_id)box.append(facts({submission_id:value.submission_id,submission_sha256:value.submission_sha256,proposal_sha256:value.proposal_sha256,assessment_sha256:value.assessment_sha256,retention:value.retention,capture_requests:value.capture_requests}));
    box.append(element('p','caption',value.state==='INCOMPLETE'?'The original package exists without its completed submission event. Export and inspect it; this action cannot be resumed automatically.':'Find Save camera originals for separate review in Camera actions or Control Center; select both captures explicitly. A historical checksum check is not current image verification. Continuity, separate review, freshness and installed calibration remain required.'));
    return box;
  }

  function cameraConfigurationAttemptValid(value, view) {
    const v = cameraConfigurationValidators();
    const keys = ["schema", "source_sha256", "launch_session_id", "settings_reference_retained", "attempts", "maximum_attempts", "capture_action", "export_action", "export_available", "physical_authority", "hardware_qualified", "connected", "meaning"];
    const phases = ["QUEUED_NOT_ADMITTED", "RUNNING_ORIGINAL_CAPTURE", "RESULT_STAGED_NOT_PUBLISHED", "CAPTURE_PUBLISHED_UNQUALIFIED", "FAILED_HELD"];
    const outcomes = [null, "SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"];
    if (!v.exact(value, keys) || value.schema !== "rocell.wizard_camera_configuration_attempt.v1"
      || !v.digest(value.source_sha256) || value.source_sha256 !== view.source_binding_sha256
      || value.launch_session_id !== view.session_id || !/^wizard-[0-9a-f]{32}$/.test(value.launch_session_id)
      || ["physical_authority", "hardware_qualified", "connected"].some(k => value[k] !== false)
      || typeof value.settings_reference_retained !== "boolean" || typeof value.export_available !== "boolean"
      || value.maximum_attempts !== 8 || !Array.isArray(value.attempts) || value.attempts.length > 8
      || value.export_available !== (value.attempts.length > 0)
      || value.capture_action !== "physical_camera_configuration_capture"
      || value.export_action !== "physical_camera_configuration_attempt_export"
      || typeof value.meaning !== "string" || value.meaning.length > 512) return false;
    const seen = new Set();
    return value.attempts.every(row => {
      if (!v.exact(row, ["operation_id", "claimed", "phase", "outcome"])
        || !/^operation-[0-9a-f]{32}$/.test(row.operation_id) || seen.has(row.operation_id)
        || typeof row.claimed !== "boolean" || !phases.includes(row.phase) || !outcomes.includes(row.outcome)
        || (row.phase !== "QUEUED_NOT_ADMITTED" && row.phase !== "FAILED_HELD" && !row.claimed)
        || (row.phase === "CAPTURE_PUBLISHED_UNQUALIFIED" && row.outcome !== "SUCCEEDED")
        || (row.phase === "FAILED_HELD" && row.outcome === "SUCCEEDED")) return false;
      seen.add(row.operation_id); return true;
    });
  }

  function cameraConfigurationAttempt() {
    const box = card("Camera settings and one-frame verification", "Logged settings → explicit bounded capture → inspect or export");
    const value = state.view.camera_configuration_attempt;
    if (value === undefined) { box.append(element("p", "caption", "This older snapshot has no settings-capture status.")); return box; }
    if (!cameraConfigurationAttemptValid(value, state.view)) { box.append(element("p", "notice warning", "CAMERA_CONFIGURATION_ATTEMPT_NOT_VERIFIED: Inconsistent status withheld. Inspect diagnostics without replay.")); return box; }
    box.append(element("span", "badge hold", "NO CALIBRATION OR ARM AUTHORITY"), facts({logged_settings_reference_retained:value.settings_reference_retained, retained_attempts:value.attempts.length, maximum_attempts:value.maximum_attempts}), element("p", "caption", value.meaning));
    for (const row of value.attempts) box.append(facts(row));
    box.append(element("p", "caption", "Use Stage reported native camera settings, then Verify settings with one camera frame below. A retained reference is historical until the action rechecks it. This is not a live stream; focus and aperture remain manual lens adjustments."));
    if (value.export_available) box.append(element("p", "caption", "Use Export camera settings-capture attempt below and select the exact attempt. It saves readback, cleanup and logs to the assigned export folder without reconnecting hardware."));
    return box;
  }

  function physicalCameraSetup() {
    const box = card("Physical camera setup", "Original camera-only diagnostic storage and required intake evidence");
    box.append(element("span", "badge hold", "NO PHYSICAL AUTHORITY"), element("p", "notice warning", "CURRENT means a published storage/report observation, not physical-stage PASS, a connected camera or native admission. Initialization does not measure hardware or pass any of the 15 physical stages. Refresh audits the original store without replay, repair or quarantine clearing."));
    box.append(sourceReassessment());
    box.append(staticCameraOnboarding());
    box.append(receivedCameraOnboarding());
    box.append(cameraIdentityOnboarding());
    const input = state.view.physical_camera_setup, value = physicalSetupValidators().setup(input);
    if (!value) { box.append(element("p", "notice warning", input === null || input === undefined ? "No physical setup state is available. Use an eligible explicit initialization action; this page never initializes storage." : "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED: Inconsistent, unsupported or oversized setup projection withheld. Inspect retained diagnostics; nothing is automatically reopened or retried.")); return box; }
    const s = value.session, verified = s.verification;
    box.append(facts({source_sha256: value.source_sha256, publication: value.publication.status, status: s.status, operation: s.operation,
      initialize_attempted: s.initialize_attempted, partial_store_possible: s.partial_store_possible}), element("p", "caption", value.meaning), heading("Assigned original storage binding"), facts(s.binding));
    if (["rocell.wizard_physical_camera_setup.v2", "rocell.wizard_physical_camera_setup.v3"].includes(value.schema)) {
      box.append(heading("Current application and original storage are distinct identities"), facts({current_application_launch: value.launch_session_id, original_storage_launch: value.origin_launch_id, requirements_provenance: value.requirements_provenance}),
        element("p", "caption", value.origin_launch_id === value.launch_session_id ? "This store belongs to the current launch. No existing store was inferred or selected." : "The original store was explicitly selected for reopening; storage audit and current publication are separate. Its cell, session, source and origin remain unchanged; the current application launch is not a replacement storage session."), physicalCameraReopening(value.reopening));
      if (value.requirements_provenance === "REOPENED_ORIGINAL_CONTEXT") box.append(element("p", "notice warning", "Historical original requirements: retained metadata and source-context hashes are not current-launch observations. CURRENT means this original report was audited and published, not current camera identity, configuration, image, connection or received-unit qualification."));
    } else box.append(element("p", "caption", "Legacy v1 read-only snapshot. Its recorded origin is preserved; a distinct current application launch or restart adoption is not established by this legacy record."));
    if (s.error) box.append(heading("Storage hold"), facts(s.error));
    if (verified) {
      box.append(heading("Retained storage verification — not hardware qualification"), facts({storage_status: verified.status, windows_ntfs_storage_qualified: verified.qualification.qualified_windows_ntfs,
        storage_prechecks_clear_only: verified.effects_allowed_by_m1_storage, challenge_sha256: verified.challenge_sha256,
        session_header_sha256: verified.session.header_sha256, session_head_sha256: verified.session.head_sha256, evidence_inventory_sha256: verified.session.evidence_inventory_sha256,
        absolute_creation_time: "RETAINED_NOT_INTERPRETED_AS_EXACT_IN_BROWSER"}), facts({attempt_ledger: verified.attempt_ledger, quarantine: verified.quarantine, leases: verified.leases}));
      box.append(heading("Original session recorded stage states — not the physical progress checklist"));
      box.append(element("p", "caption", "Repeated references are citations in separate committed events, not additional evidence files."));
      for (const row of s.stages) box.append(element("p", "", `${human(row.stage)}: ${row.state} · ${row.evidence_ids.length} retained reference occurrences (${new Set(row.evidence_ids).size} unique IDs)${row.last_event_sequence === null ? " · no event" : " · event " + row.last_event_sequence}`));
    } else box.append(element("p", "caption", "No current storage verification. A partial or held store must be inspected explicitly; a missing report is not an empty successful session."));
    box.append(workspaceSourceWorkflow(value), physicalConfigurationRecords(value));
    if (["PENDING", "HISTORICAL_HELD"].includes(value.publication.status)) box.append(element("p", "notice warning", "Current prerequisite details are withheld while publication is pending or historical. Original retained records remain diagnostic history; do not replay collection."));
    else if (!value.prerequisites) box.append(element("p", "caption", "No stage 1–4 prerequisite report has been collected. Required intake is not a completed measurement or accepted checkbox."));
    else box.append(physicalRequirementsCard(value.prerequisites));
    box.append(element("p", "caption", "Status uses cached projections only, without M1 reads. Initialize, refresh and collect requirements are separate explicit actions. Their storage/file effects never authorize device activation, arm power, motion or contact."));
    return box;
  }

  function sourceReassessmentProjection(value, view) {
    const v = cameraConfigurationValidators(), p = physicalSetupValidators();
    const flags = ["physical_authority", "hardware_qualified", "native_release_allowed", "device_io_performed"];
    const software = ["controlled_build_sources", "foundation_semantics", "unchanged_file_snapshot", "runtime_fail_closed", "launcher_and_bootstrap_present", "base_software_ready", "static_camera_plan_selected"];
    const ownership = ["DURABILITY_LOCKING", "ORDERED_CROSS_PROCESS_OWNERSHIP", "LIVE_CONTENDER_DENIED", "CLEAN_RELEASE_LINEAGE", "CRASH_STALE_OWNER_DENIED", "INJECTED_PROCESS_START_MISMATCH_DENIED", "ORIGINAL_M1_NO_REPLAY"];
    const states = ["PENDING", "WAITING_OPERATOR", "REVIEW_PENDING", "PASS", "BLOCKED", "INVALIDATED", "INCIDENT_HOLD", "SIDE_EFFECT_UNCERTAIN", "COMPLETE_DIAGNOSTIC"];
    const actions = ["physical_source_isolation_files_discover", "physical_source_qualify", "physical_source_qualification_review", "physical_static_contract_begin"];
    const actor = item => typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(item);
    const launch = item => typeof item === "string" && /^wizard-[0-9a-f]{32}$/.test(item);
    if (!v.exact(value, ["schema", "status", "source_sha256", "launch_session_id", "original_context", "publication", "stage_states", "qualification", "next_action", ...flags, "meaning"])
      || value.schema !== "rocell.wizard_source_reassessment.v1" || !["NOT_STARTED", "REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED", "INCOMPLETE_HELD", "HISTORICAL_HELD"].includes(value.status)
      || !v.digest(value.source_sha256) || !launch(value.launch_session_id) || !flags.every(key => value[key] === false) || !v.string(value.meaning, 512)
      || !v.exact(value.publication, ["status", "operation_id"]) || !["NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"].includes(value.publication.status)
      || !(value.publication.operation_id === null || v.identifier(value.publication.operation_id)) || !(value.next_action === null || actions.includes(value.next_action))) return null;
    const c = value.original_context, s = value.stage_states, q = value.qualification;
    if (c !== null && (!v.exact(c, ["source_sha256", "session_id", "cell_id", "origin_launch_id", "header_sha256", "prerequisites_sha256"])
      || !["source_sha256", "header_sha256", "prerequisites_sha256"].every(key => v.digest(c[key])) || !["session_id", "cell_id"].every(key => v.identifier(c[key])) || !launch(c.origin_launch_id))) return null;
    if (s !== null && (!c || !v.exact(s, ["workspace_sources", "static_camera_contract"]) || !Object.values(s).every(state => states.includes(state)))) return null;
    if (value.publication.status === "PENDING" && q !== null) return null;
    if (value.publication.status === "HISTORICAL_HELD" && value.status !== "HISTORICAL_HELD") return null;
    if (q !== null) {
      if (!c || !v.exact(q, ["qualification_id", "collection_launch_id", "operator_id", "original_subjects", "receipt_sha256", "assessment_sha256", "software_checks", "isolation", "ownership", "verdict", "missing_requirements", "review"])
        || typeof q.qualification_id !== "string" || !/^sourcequal-[0-9a-f]{32}$/.test(q.qualification_id) || !launch(q.collection_launch_id) || !actor(q.operator_id)
        || !v.exact(q.original_subjects, ["receipt_sha256", "assessment_sha256", "review_sha256"]) || !Object.values(q.original_subjects).every(v.digest)
        || !v.digest(q.receipt_sha256) || !v.digest(q.assessment_sha256) || !["PASS", "BLOCKED"].includes(q.verdict) || !p.codes(q.missing_requirements, 32)
        || !Array.isArray(q.software_checks) || q.software_checks.length !== software.length || !q.software_checks.every((row, i) => v.exact(row, ["check_id", "passed"]) && row.check_id === software[i] && typeof row.passed === "boolean")) return null;
      const isolation = q.isolation, owner = q.ownership, review = q.review;
      if (!v.exact(isolation, ["state", "statement", "attachment_sha256", "measurement_truth_verified"]) || !["UNKNOWN", "OBSERVED_DISCONNECTED"].includes(isolation.state)
        || !(v.string(isolation.statement, 512) || (isolation.state === "UNKNOWN" && isolation.statement === "")) || isolation.statement.trim() !== isolation.statement || /\p{C}/u.test(isolation.statement) || isolation.measurement_truth_verified !== false
        || !(isolation.attachment_sha256 === null || v.digest(isolation.attachment_sha256)) || (isolation.state === "OBSERVED_DISCONNECTED" && isolation.attachment_sha256 === null)
        || !v.exact(owner, ["status", "report_sha256", "checks"]) || !["SOFTWARE_MECHANISMS_PASSED", "HELD"].includes(owner.status) || !v.digest(owner.report_sha256)
        || !Array.isArray(owner.checks) || owner.checks.length !== ownership.length || !owner.checks.every((row, i) => v.exact(row, ["check_id", "passed", "provenance"]) && row.check_id === ownership[i] && typeof row.passed === "boolean" && row.provenance === (i === 5 ? "CONTROLLED_FAULT_INJECTION" : "ACTUAL_HOST_MECHANISM"))
        || (owner.status === "SOFTWARE_MECHANISMS_PASSED" && owner.checks.some(row => !row.passed))) return null;
      if ((q.verdict === "PASS" && (q.missing_requirements.length || q.software_checks.some(row => !row.passed) || owner.status !== "SOFTWARE_MECHANISMS_PASSED" || isolation.state !== "OBSERVED_DISCONNECTED"))
        || (q.verdict === "BLOCKED" && !q.missing_requirements.length)) return null;
      if (review !== null && (!v.exact(review, ["review_sha256", "reviewer_id", "review_launch_id", "verdict", "distinct_operator_labels", "authenticated_independent_people"])
        || !v.digest(review.review_sha256) || !actor(review.reviewer_id) || review.reviewer_id.toLowerCase() === q.operator_id.toLowerCase() || !launch(review.review_launch_id)
        || review.verdict !== q.verdict || review.distinct_operator_labels !== true || review.authenticated_independent_people !== false)) return null;
    }
    if ((value.status === "NOT_STARTED" && q !== null) || (value.status === "REVIEW_PENDING" && (!q || q.review !== null))
      || (value.status === "REVIEWED_PASS" && (!q?.review || q.verdict !== "PASS")) || (value.status === "REVIEWED_BLOCKED" && (!q?.review || q.verdict !== "BLOCKED"))) return null;
    if (["REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED"].includes(value.status) && value.publication.status !== "CURRENT") return null;
    if (value.publication.status === "CURRENT") {
      const setup = p.setup(view.physical_camera_setup), b = setup?.session.binding, verified = setup?.session.verification;
      if (!setup || setup.publication.status !== "CURRENT" || !verified || !setup.prerequisites || !c || !s || value.publication.operation_id === null
        || value.source_sha256 !== view.source_binding_sha256 || value.launch_session_id !== view.session_id || value.launch_session_id !== setup.launch_session_id
        || c.source_sha256 !== value.source_sha256 || c.source_sha256 !== setup.source_sha256 || c.session_id !== b.session_id || c.cell_id !== b.cell_id || c.origin_launch_id !== b.launch_id
        || c.header_sha256 !== verified.session.header_sha256 || c.prerequisites_sha256 !== setup.prerequisites.evidence_sha256
        || s.workspace_sources !== setup.session.stages[0].state || s.static_camera_contract !== setup.session.stages[1].state) return null;
      if (q) {
        const original = workspaceSourceWorkflowProjection(setup.source_workflow, setup);
        if (!original?.receipt || !original.assessment || !original.review || q.original_subjects.receipt_sha256 !== original.receipt.receipt_sha256
          || q.original_subjects.assessment_sha256 !== original.assessment.assessment_sha256 || q.original_subjects.review_sha256 !== original.review.review_sha256) return null;
      }
      if ((value.status === "REVIEW_PENDING" && s.workspace_sources !== "REVIEW_PENDING") || (value.status === "REVIEWED_PASS" && (s.workspace_sources !== "PASS" || !["PENDING", "WAITING_OPERATOR"].includes(s.static_camera_contract)))
        || (value.status === "REVIEWED_BLOCKED" && (s.workspace_sources !== "BLOCKED" || s.static_camera_contract !== "PENDING"))) return null;
    }
    return value;
  }

  function sourceReassessment() {
    const box = element("section", "source-reassessment");
    box.append(heading("Workspace-source reassessment — stage-only admission"), element("p", "notice warning", "Source-stage acceptance is not native camera release, received-hardware qualification or permission to connect, energize, move or contact. No device effect is performed by this workflow."));
    const input = state.view.source_reassessment;
    if (input === undefined || input === null) { box.append(element("p", "caption", "No source reassessment projection in this legacy snapshot. No successor assessment or accepted stage is inferred.")); return box; }
    const value = sourceReassessmentProjection(input, state.view);
    if (!value) { box.append(element("p", "notice warning", "SOURCE_REASSESSMENT_NOT_VERIFIED: Inconsistent cached subject, authority or publication withheld. Inspect original diagnostics; no stage acceptance is inferred.")); return box; }
    box.append(facts({status: value.status, publication: value.publication.status, source_sha256: value.source_sha256, current_application_launch: value.launch_session_id}), element("p", "caption", value.meaning));
    if (value.publication.status === "PENDING") { box.append(element("p", "notice warning", "Reassessment publication pending. New subject details remain withheld until original-store readback, source/Stop checks and completion logging succeed.")); return box; }
    const historical = value.status === "HISTORICAL_HELD" || value.publication.status === "HISTORICAL_HELD";
    if (historical) box.append(element("p", "notice warning", "Historical source qualification subject only — not current stage acceptance. Original observations and actors are not rebound to this launch. No automatic recollection, review or replay."));
    if (value.original_context) box.append(heading("Original source context"), facts(value.original_context));
    if (value.stage_states) box.append(heading(historical ? "Historical recorded stage states" : "Original session committed stage states"), facts(value.stage_states));
    const q = value.qualification;
    if (!q) box.append(element("p", "caption", value.status === "INCOMPLETE_HELD" ? "Incomplete qualification attempt: no complete receipt/assessment pair is projected. Preserve partial original evidence and inspect the full export; do not retry automatically." : "No complete source qualification is retained. UNKNOWN isolation remains blocked; discovery or a consent checkbox does not observe disconnected power."));
    else {
      box.append(facts({qualification_id: q.qualification_id, collection_launch_id: q.collection_launch_id, receipt_sha256: q.receipt_sha256, assessment_sha256: q.assessment_sha256}), element("p", "", `Operator label: ${q.operator_id}`), heading("Original BLOCKED source subjects — unchanged"), facts(q.original_subjects));
      box.append(heading("Actual retained software checks"));
      for (const row of q.software_checks) box.append(element("p", "", `${row.check_id}: ${row.passed ? "SOFTWARE_CHECK_PASSED" : "SOFTWARE_CHECK_BLOCKED"}`));
      box.append(heading("Retained isolation statement — not current electrical telemetry"), facts({state: q.isolation.state, attachment_sha256: q.isolation.attachment_sha256, measurement_truth_verified: false}), element("p", "", q.isolation.statement || "No isolation statement recorded."), element("p", "caption", "An operator statement and original attachment do not authenticate their contents or prove the present electrical state. UNKNOWN cannot satisfy isolation."));
      box.append(heading("Stage-relative software ownership coverage"), facts({status: q.ownership.status, report_sha256: q.ownership.report_sha256}));
      for (const row of q.ownership.checks) box.append(element("p", "", `${row.check_id}: ${row.passed ? "CHECK_PASSED" : "HELD"} · ${row.provenance}`));
      box.append(element("p", "caption", "Controlled process-start mismatch is fault injection, not observed operating-system PID reuse. Selected-device identity after effectful locking, received-hardware HZ-012 residuals and native runtime release remain separate obligations."), heading(`Retained source assessment verdict: ${q.verdict}`));
      for (const reason of q.missing_requirements) box.append(element("p", "notice warning", reason));
      if (q.review) box.append(heading("Exact-subject source qualification review"), element("p", "", `Reviewer label: ${q.review.reviewer_id}`), facts({review_sha256: q.review.review_sha256, review_launch_id: q.review.review_launch_id, verdict: q.review.verdict}), element("p", "caption", "Distinct labels record a procedure, not authenticated independent people. Review cannot upgrade a BLOCKED assessment."));
      else box.append(element("p", "notice warning", "Exact-subject review is still required. An assessed PASS is not a committed source-stage PASS."));
    }
    if (value.status === "REVIEWED_PASS" && !historical) box.append(element("p", "notice", "Stage 1 accepted only — no camera runtime release."), element("p", "caption", value.stage_states.static_camera_contract === "PENDING" ? "Stage 2 remains PENDING. Entering the static-camera contract is a separate explicit action; no stage advances on viewing or restart." : "Stage 2 was explicitly requested and remains WAITING_OPERATOR, not accepted. No camera is opened by that request."));
    if (value.next_action && !historical) box.append(element("p", "caption", `Next explicit action: ${value.next_action}. Use its eligible form below; this display never prepares or executes it.`));
    box.append(element("p", "caption", "Export the full original qualification metadata; original attachment export requires separate privacy consent. This panel reads cached projections only."));
    return box;
  }

  function staticCameraOnboardingProjection(value, view) {
    const v = cameraConfigurationValidators(), p = physicalSetupValidators();
    const flags = ["physical_authority", "hardware_qualified", "native_release_allowed", "device_io_performed"];
    const roleFlags = ["physical_authority", "hardware_qualified", "device_io_performed", "native_runtime_released"];
    const actions = ["physical_static_contract_collect", "physical_static_contract_review", "physical_camera_receipt_begin"];
    const checks = ["base_software_ready", "readiness_and_architecture_select_static_primary", "architecture_has_zero_physical_authority", "secondary_camera_unselected", "automatic_camera_fallback_disabled", "camera_profile_has_zero_live_authority", "profile_and_support_identity_match", "profile_and_support_native_mode_match", "architecture_and_support_board_match", "architecture_and_support_required_view_match", "architecture_file_matches_source_binding", "camera_profile_file_matches_source_binding", "support_design_file_matches_source_binding", "support_locks_architecture_bytes", "support_locks_camera_profile_bytes", "every_support_dependency_matches_source_binding", "physical_qualification_holds_retained"];
    const stages = ["PENDING", "WAITING_OPERATOR", "REVIEW_PENDING", "PASS", "BLOCKED", "INVALIDATED", "INCIDENT_HOLD", "SIDE_EFFECT_UNCERTAIN", "COMPLETE_DIAGNOSTIC"];
    const actor = x => typeof x === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(x);
    const launch = x => typeof x === "string" && /^wizard-[0-9a-f]{32}$/.test(x);
    const positive = x => typeof x === "number" && Number.isFinite(x) && x > 0 && x <= 1000000;
    const texts = x => Array.isArray(x) && x.length <= 32 && x.every(item => v.string(item, 4096));
    const checkRows = x => Array.isArray(x) && x.length === checks.length && x.every((row,i) => v.exact(row,["check_id","passed"]) && row.check_id === checks[i] && typeof row.passed === "boolean");
    const contextKeys = ["source_sha256","session_id","cell_id","origin_launch_id","header_sha256","prerequisites_sha256"];
    const bindingKeys = [...contextKeys,"contract_id","collection_launch_id","operator_id","source_qualification","static_request_event_sha256","store_directory"];
    const context = x => v.exact(x,contextKeys) && ["source_sha256","header_sha256","prerequisites_sha256"].every(key => v.digest(x[key])) && launch(x.origin_launch_id) && typeof x.session_id === "string" && /^physical-camera-[0-9a-f]{32}$/.test(x.session_id) && typeof x.cell_id === "string" && /^wizard-physical-camera-[0-9a-f]{16}$/.test(x.cell_id);
    const binding = x => v.exact(x,bindingKeys) && context(Object.fromEntries(contextKeys.map(key => [key,x[key]]))) && typeof x.contract_id === "string" && /^staticcontract-[0-9a-f]{32}$/.test(x.contract_id) && launch(x.collection_launch_id) && actor(x.operator_id) && v.digest(x.static_request_event_sha256) && v.string(x.store_directory,16384) && x.store_directory.length <= 4096 && v.exact(x.source_qualification,["receipt","assessment","review"]) && Object.values(x.source_qualification).every(v.digest);
    const sameBinding = (a,b) => bindingKeys.every(key => key === "source_qualification" ? ["receipt","assessment","review"].every(role => a[key][role] === b[key][role]) : a[key] === b[key]);
    if (!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","stage_states","contract","camera_receipt_entry","next_action","meaning",...flags]) || value.schema !== "rocell.wizard_static_camera_onboarding.v1" || !v.digest(value.source_sha256) || !launch(value.launch_session_id) || !flags.every(key => value[key] === false) || !v.string(value.meaning,512)
      || !["NOT_STARTED","REVIEW_PENDING","REVIEWED_PASS","REVIEWED_BLOCKED","INCOMPLETE_HELD","HISTORICAL_HELD"].includes(value.status) || !v.exact(value.publication,["status","operation_id"]) || !["NOT_PUBLISHED","PENDING","CURRENT","HISTORICAL_HELD"].includes(value.publication.status) || !(value.publication.operation_id === null || v.identifier(value.publication.operation_id)) || !(value.next_action === null || actions.includes(value.next_action)) || !(value.camera_receipt_entry === null || v.digest(value.camera_receipt_entry))) return null;
    const c=value.original_context,s=value.stage_states,t=value.contract,publication=value.publication.status;
    if ((c !== null && !context(c)) || (s !== null && (!v.exact(s,["workspace_sources","static_camera_contract","camera_receipt"]) || !Object.values(s).every(item => stages.includes(item)))) || (publication === "PENDING" && (t !== null || value.camera_receipt_entry !== null)) || (publication === "HISTORICAL_HELD" && value.status !== "HISTORICAL_HELD" && !(value.status === "NOT_STARTED" && t === null && value.camera_receipt_entry === null && value.next_action === null))) return null;
    if (t !== null) {
      if (!c || !v.exact(t,["contract_id","state","receipt","assessment","review"]) || typeof t.contract_id !== "string" || !/^staticcontract-[0-9a-f]{32}$/.test(t.contract_id) || !["INCOMPLETE","ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING","REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(t.state)) return null;
      const r=t.receipt,a=t.assessment,w=t.review;
      for (const item of [r,a,w]) if (item !== null && (!binding(item.binding) || item.binding.contract_id !== t.contract_id || !contextKeys.every(key => item.binding[key] === c[key]) || !roleFlags.every(key => item[key] === false) || JSON.stringify(item).replace(/[\u007f-\uffff]/g, character => "\\u" + character.charCodeAt(0).toString(16).padStart(4,"0")).length > 24576)) return null;
      if (r !== null) {
        if (!v.exact(r,["schema","binding","receipt_sha256","status","checks","design","blockers","source_file_count","source_bytes",...roleFlags]) || r.schema !== "rocell.static_camera_contract_receipt_summary.v1" || r.status !== "DESIGN_INPUTS_COLLECTED" || !v.digest(r.receipt_sha256) || !checkRows(r.checks) || r.source_file_count !== 5 || !v.integer(r.source_bytes,1,131072) || !v.exact(r.blockers,["architecture","profile","support"]) || !Object.values(r.blockers).every(texts)) return null;
        const d=r.design,m=d?.published_mode;
        if (!v.exact(d,["camera_model","sensor","lens_mount","focal_length_mm","board_size_mm","required_view_mm","nominal_entrance_pupil_z_mm","published_mode","value_provenance"]) || !["camera_model","sensor","lens_mount"].every(key => v.string(d[key],512)) || !positive(d.focal_length_mm) || !positive(d.nominal_entrance_pupil_z_mm) || d.value_provenance !== "DESIGN_NOT_MEASURED" || !Array.isArray(d.board_size_mm) || d.board_size_mm.length !== 3 || !d.board_size_mm.every(positive) || !Array.isArray(d.required_view_mm) || d.required_view_mm.length !== 2 || !d.required_view_mm.every(positive)) return null;
        if (m !== null && (!v.exact(m,["host_bus","width_px","height_px","maximum_fps","pixel_format","evidence_state"]) || !["host_bus","pixel_format","evidence_state"].every(key => v.string(m[key],128)) || !v.integer(m.width_px,1,100000) || !v.integer(m.height_px,1,100000) || !positive(m.maximum_fps))) return null;
      }
      if (a !== null && (!r || !v.exact(a,["schema","binding","receipt_sha256","assessment_sha256","status","verdict","checks","missing_requirements",...roleFlags]) || a.schema !== "rocell.static_camera_contract_assessment_summary.v1" || a.status !== "ASSESSED" || !v.digest(a.assessment_sha256) || a.receipt_sha256 !== r.receipt_sha256 || !sameBinding(a.binding,r.binding) || !checkRows(a.checks) || a.checks.some((row,i) => row.passed !== r.checks[i].passed) || !Array.isArray(a.missing_requirements) || a.missing_requirements.join("|") !== a.checks.filter(row => !row.passed).map(row => row.check_id).join("|") || a.verdict !== (a.missing_requirements.length ? "BLOCKED" : "PASS"))) return null;
      if (w !== null && (!a || !v.exact(w,["schema","binding","receipt_sha256","assessment_sha256","review_sha256","status","verdict","reviewer_id","review_launch_id","reviewed_at_ns","procedure_complete",...roleFlags]) || w.schema !== "rocell.static_camera_contract_review_summary.v1" || w.status !== "REVIEW_RECORDED" || !v.digest(w.review_sha256) || w.receipt_sha256 !== r.receipt_sha256 || w.assessment_sha256 !== a.assessment_sha256 || !sameBinding(w.binding,r.binding) || w.verdict !== a.verdict || !actor(w.reviewer_id) || w.reviewer_id.toLowerCase() === r.binding.operator_id.toLowerCase() || !launch(w.review_launch_id) || typeof w.reviewed_at_ns !== "number" || !Number.isInteger(w.reviewed_at_ns) || w.reviewed_at_ns <= 0 || w.reviewed_at_ns > 2**63 || w.procedure_complete !== true)) return null;
      if ((["REVIEW_PENDING","ASSESSMENT_RETAINED_NOT_COMMITTED"].includes(t.state) && (!a || w !== null)) || (["REVIEWED_PASS","REVIEWED_BLOCKED","REVIEW_RETAINED_NOT_COMMITTED"].includes(t.state) && !w) || (t.state === "REVIEWED_PASS" && w.verdict !== "PASS") || (t.state === "REVIEWED_BLOCKED" && w.verdict !== "BLOCKED")) return null;
    }
    if ((value.status === "NOT_STARTED" && t !== null) || (["REVIEW_PENDING","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(value.status) && (!t || t.state !== value.status || publication !== "CURRENT"))) return null;
    if (publication === "CURRENT") {
      const setup=p.setup(view.physical_camera_setup),b=setup?.session.binding,verification=setup?.session.verification;
      // A published storage refresh can precede every design prerequisite.
      // It is not a published design subject and cannot imply a stage PASS.
      if (value.status === "NOT_STARTED" && t === null && value.camera_receipt_entry === null && value.next_action === null) {
        if (!setup || setup.publication.status !== "CURRENT" || !verification || !s || value.publication.operation_id === null || value.source_sha256 !== view.source_binding_sha256 || value.source_sha256 !== setup.source_sha256 || value.launch_session_id !== view.session_id || value.launch_session_id !== setup.launch_session_id || ["workspace_sources","static_camera_contract","camera_receipt"].some((key,i) => s[key] !== setup.session.stages[i].state)) return null;
        if (c === null ? setup.prerequisites !== null : !setup.prerequisites || c.source_sha256 !== value.source_sha256 || c.session_id !== b.session_id || c.cell_id !== b.cell_id || c.origin_launch_id !== b.launch_id || c.header_sha256 !== verification.session.header_sha256 || c.prerequisites_sha256 !== setup.prerequisites.evidence_sha256) return null;
        return value;
      }
      if (!setup || setup.publication.status !== "CURRENT" || !verification || !setup.prerequisites || !c || !s || value.publication.operation_id === null || value.source_sha256 !== view.source_binding_sha256 || value.launch_session_id !== view.session_id || value.launch_session_id !== setup.launch_session_id || c.source_sha256 !== value.source_sha256 || c.source_sha256 !== setup.source_sha256 || c.session_id !== b.session_id || c.cell_id !== b.cell_id || c.origin_launch_id !== b.launch_id || c.header_sha256 !== verification.session.header_sha256 || c.prerequisites_sha256 !== setup.prerequisites.evidence_sha256 || ["workspace_sources","static_camera_contract","camera_receipt"].some((key,i) => s[key] !== setup.session.stages[i].state) || s.workspace_sources !== "PASS") return null;
      if (t?.receipt) {
        const q=sourceReassessmentProjection(view.source_reassessment,view)?.qualification,bound=t.receipt.binding;
        if (!q?.review || q.verdict !== "PASS" || bound.store_directory !== b.directory || ["receipt","assessment"].some(role => bound.source_qualification[role] !== q[role+"_sha256"]) || bound.source_qualification.review !== q.review.review_sha256) return null;
      }
      if ((value.status === "REVIEW_PENDING" && s.static_camera_contract !== "REVIEW_PENDING") || (value.status === "REVIEWED_PASS" && (s.static_camera_contract !== "PASS" || !["PENDING","WAITING_OPERATOR"].includes(s.camera_receipt))) || (value.status === "REVIEWED_BLOCKED" && (s.static_camera_contract !== "BLOCKED" || s.camera_receipt !== "PENDING")) || ((s.camera_receipt === "WAITING_OPERATOR") !== (value.camera_receipt_entry !== null))) return null;
    }
    return value;
  }

  function staticCameraOnboarding() {
    const box=element("section","static-camera-onboarding");
    box.append(heading("Static-camera design and received-unit onboarding"),element("p","notice warning","Design-only stage 2 is not received hardware, installation qualification or native camera release. No device, power, motion or contact effect is performed."));
    const input=state.view.static_camera_onboarding;
    if (input === undefined || input === null) { box.append(element("p","caption","No static-camera onboarding projection in this legacy snapshot. No design acceptance or received unit is inferred.")); return box; }
    const value=staticCameraOnboardingProjection(input,state.view);
    if (!value) { box.append(element("p","notice warning","STATIC_CAMERA_ONBOARDING_NOT_VERIFIED: Inconsistent cached design subject or publication withheld. Inspect original diagnostics; no acceptance is inferred.")); return box; }
    box.append(facts({status:value.status,publication:value.publication.status,source_sha256:value.source_sha256,current_launch:value.launch_session_id}),element("p","caption",value.meaning));
    if (value.publication.status === "PENDING") { box.append(element("p","notice warning","Design publication pending; new contract and entry details remain withheld until original readback and completion logging succeed.")); return box; }
    const historical=value.status === "HISTORICAL_HELD" || value.publication.status === "HISTORICAL_HELD";
    if (historical) box.append(element("p","notice warning","Historical design subject only — not current stage acceptance. Original context is not rebound; no replay or automatic next-stage entry."));
    if (value.original_context) box.append(heading("Original design context"),facts(value.original_context));
    if (value.stage_states) box.append(heading(historical ? "Historical recorded stage states" : "Original session committed stage states"),facts(value.stage_states));
    const t=value.contract;
    if (!t) box.append(element("p","caption","No complete static contract is published. Use only the eligible explicit file-only action; do not infer received measurements."));
    else {
      box.append(facts({contract_id:t.contract_id,retained_state:t.state}));
      const r=t.receipt,a=t.assessment,w=t.review;
      if (r) {
        box.append(element("p","",`Collection operator label: ${r.binding.operator_id}`),facts({receipt_sha256:r.receipt_sha256,source_file_count:r.source_file_count,source_bytes:r.source_bytes,collection_launch:r.binding.collection_launch_id,static_entry_event:r.binding.static_request_event_sha256}),heading("Reviewed source qualification dependencies"),facts(r.binding.source_qualification),heading("Published and nominal design values — NOT MEASURED"));
        for (const [key,item] of Object.entries(r.design)) if (key !== "published_mode") box.append(element("p","",`${key}: ${Array.isArray(item) ? item.join(" × ") : item}`));
        box.append(heading("Published catalog mode — not selected or observed device settings"));
        if (r.design.published_mode) box.append(facts(r.design.published_mode)); else box.append(element("p","notice warning","No unique matching published design mode retained."));
        box.append(heading("Actual file-derived design checks"));
        for (const row of r.checks) box.append(element("p","",`${row.check_id}: ${row.passed ? "DESIGN_CHECK_PASSED" : "BLOCKED"}`));
        box.append(heading("Preserved architecture, profile and support qualification holds"));
        for (const [family,items] of Object.entries(r.blockers)) for (const item of items) box.append(element("p","notice warning",`${family}: ${item}`));
      }
      if (a) box.append(heading(`Retained design assessment: ${a.verdict}`),facts({assessment_sha256:a.assessment_sha256,missing_requirements:a.missing_requirements}));
      if (w) box.append(heading("Exact-subject design review"),element("p","",`Reviewer label: ${w.reviewer_id}`),facts({review_sha256:w.review_sha256,verdict:w.verdict,review_launch:w.review_launch_id}),element("p","caption","Distinct labels record a procedure, not authenticated independent people. Review timestamp is retained, not interpreted as an exact JavaScript clock."));
      else box.append(element("p","notice warning","A retained assessment alone is not a committed stage PASS; exact-subject review is still required."));
    }
    if (value.status === "REVIEWED_PASS" && !historical) box.append(element("p","notice","Stage 2 design accepted only — no installation or native camera release."),element("p","caption",value.camera_receipt_entry ? "Stage 3 was explicitly requested and remains WAITING_OPERATOR; no received identity or measurement is supplied." : "Stage 3 remains PENDING. Requesting received-camera inspection is a separate explicit action."));
    if (value.camera_receipt_entry) box.append(facts({camera_receipt_entry_event:value.camera_receipt_entry}));
    if (value.next_action && !historical) box.append(element("p","caption",`Next explicit action: ${value.next_action}. This display never prepares or executes it.`));
    box.append(element("p","caption","Full original design records share the reserved source metadata export. Private isolation originals are not included; no automatic device activity or replay."));
    return box;
  }

  function receivedCameraValidators() {
    const v=cameraConfigurationValidators(),p=physicalSetupValidators();
    const flags=["physical_authority","hardware_qualified","native_release_allowed","device_io_performed"];
    const baseFlags=["physical_authority","hardware_qualified","canonical_stage_pass","device_io_performed","attachment_bytes_verified"];
    const roleFlags=[...baseFlags,"installation_qualified","native_runtime_released","measurement_truth_verified","authenticated_operator_identity"];
    const records=["001","002","003","004","005","006","007","008","009","017","019","020","021","022","023","024"].map(x=>"INT-"+x);
    const stages=["workspace_sources","static_camera_contract","camera_receipt","camera_identity"];
    const actions=["physical_received_camera_files_discover","physical_received_camera_draft_start","physical_received_camera_draft_record","physical_received_camera_submit","physical_received_camera_review","physical_camera_identity_begin","physical_received_camera_export"];
    const same=(a,b)=>a===b || (!!a && !!b && typeof a==="object" && typeof b==="object" && Array.isArray(a)===Array.isArray(b) && Object.keys(a).length===Object.keys(b).length && Object.keys(a).every(k=>Object.hasOwn(b,k)&&same(a[k],b[k])));
    const bounded=(x,max)=>{try{return JSON.stringify(x).replace(/[\u007f-\uffff]/g,c=>"\\u"+c.charCodeAt(0).toString(16).padStart(4,"0")).length<=max;}catch{return false;}};
    const launch=x=>typeof x==="string"&&/^wizard-[0-9a-f]{32}$/.test(x), actor=x=>typeof x==="string"&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(x);
    const contextKeys=["source_sha256","session_id","cell_id","origin_launch_id","header_sha256","prerequisites_sha256"];
    const context=x=>v.exact(x,contextKeys)&&contextKeys.every(k=>k.endsWith("sha256")?v.digest(x[k]):v.identifier(x[k]))&&launch(x.origin_launch_id);
    const triple=x=>v.exact(x,["receipt","assessment","review"])&&Object.values(x).every(v.digest);
    const binding=x=>v.exact(x,[...contextKeys,"receipt_id","collection_launch_id","operator_id","static_contract","camera_request_event_sha256"])&&context(Object.fromEntries(contextKeys.map(k=>[k,x[k]])))&&typeof x.receipt_id==="string"&&/^receivedcamera-[0-9a-f]{32}$/.test(x.receipt_id)&&launch(x.collection_launch_id)&&actor(x.operator_id)&&triple(x.static_contract)&&v.digest(x.camera_request_event_sha256);
    const coverage=x=>v.exact(x,["total","observed","unknown","unrecorded"])&&Object.values(x).every(n=>v.integer(n,0,16))&&x.total===16&&x.observed+x.unknown+x.unrecorded===16;
    const reference=x=>v.exact(x,["evidence_id","stage","package_sha256","manifest_sha256","payload_sha256","payload_bytes"])&&v.identifier(x.evidence_id)&&x.stage==="camera_receipt"&&["package_sha256","manifest_sha256","payload_sha256"].every(k=>v.digest(x[k]))&&v.integer(x.payload_bytes,1,2097152);
    const text=(x,max)=>v.string(x,max)&&x.trim()===x&&!/\p{C}/u.test(x);
    const ns=x=>typeof x==="number"&&Number.isInteger(x)&&x>0&&x<=2**63;
    const observationFields=["observed_value","instrument_or_method","observed_at_ns","operator_id","evidence_references","uncertainty_or_limitations"];
    function notebook(n,c,requirements,expectedLaunch=null,originalSha=null) {
      const keys=["schema","binding","revision","previous_sha256","rows","coverage",...baseFlags,"meaning"];
      if(!originalSha)keys.push("snapshot_sha256");
      if(!v.exact(n,keys)||n.schema!=="rocell.physical_intake_notebook.v1"||!v.integer(n.revision,0,128)||!v.digest(originalSha||n.snapshot_sha256)||!baseFlags.every(k=>n[k]===false)||!v.string(n.meaning,512)||(n.revision===0?n.previous_sha256!==null:!v.digest(n.previous_sha256))||!v.exact(n.binding,["source_sha256","session_id","origin_launch_id","launch_session_id","prerequisites_sha256"])||!launch(n.binding.launch_session_id)||!c||["source_sha256","session_id","origin_launch_id","prerequisites_sha256"].some(k=>n.binding[k]!==c[k])||(expectedLaunch&&n.binding.launch_session_id!==expectedLaunch)||!coverage(n.coverage)||!Array.isArray(n.rows)||n.rows.length!==16)return false;
      const questions=requirements?.stages.find(x=>x.stage==="camera_receipt")?.intake_rows;
      let observed=0,unknown=0;
      for(let i=0;i<16;i++){
        const r=n.rows[i],a=r?.acceptance,o=r?.observation,deferred=records[i]==="INT-005";
        if(!v.exact(r,["record_id","assembly","measurement","unit","candidate_or_requirement","template_phase","template_status","template_notes","required_observation_fields","observation","acceptance"])||r.record_id!==records[i]||!["assembly","measurement","unit","candidate_or_requirement","template_phase","template_notes"].every(k=>r[k]===""||v.string(r[k],4096))||!["NOT_CAPTURED","NOT_CREATED","NOT_MEASURED","NOT_RECORDED","NOT_TESTED","OPEN_LIMIT"].includes(r.template_status)||!same(r.required_observation_fields,observationFields)||!v.exact(a,["status","owner_stage","prerequisites","measurement_required"])||a.measurement_required!==true||a.status!==(deferred?"DEFERRED_LIMIT":"NOT_ASSESSED")||a.owner_stage!==(deferred?"noncontact_acceptance":"camera_receipt")||!same(a.prerequisites,deferred?["TARGET_ACCURACY_BUDGET_CLOSED"]:[]))return false;
        if(questions&&!same({...r,observation:null},questions[i]))return false;
        if(o===null)continue;
        if(!v.exact(o,["status","observed_value","method","evidence_note","operator_id","recorded_at_ns"])||!["OBSERVED","UNKNOWN"].includes(o.status)||![["observed_value",256],["method",512],["evidence_note",1024],["operator_id",64]].every(([k,max])=>text(o[k],max))||!ns(o.recorded_at_ns))return false;
        if(o.status==="OBSERVED") {if(["mm","g"].includes(r.unit)&&(!/^[0-9]+(?:\.[0-9]+)?$/.test(o.observed_value)||(!deferred&&!/[1-9]/.test(o.observed_value))))return false; observed++;} else unknown++;
      }
      const {snapshot_sha256,...payload}=n;
      return same(n.coverage,{total:16,observed,unknown,unrecorded:16-observed-unknown})&&observed+unknown<=n.revision&&(n.revision===0||observed+unknown>0)&&bounded(payload,65536);
    }
    const missingRoster=[...records.map(id=>id+"_OBSERVATION_REQUIRED"),"NOTEBOOK_CAMERA_STAGE_ORIGINAL_NOT_BOUND","BOARD_THICKNESS_OUTSIDE_ACCOMMODATION","STRUCTURED_CAMERA_INSPECTION_REQUIRED","INSPECTION_NOTEBOOK_REFERENCE_NOT_BOUND","CAMERA_RECEIPT_INSPECTION_UNCERTAIN","CAMERA_MANUFACTURER_MISMATCH","CAMERA_PRODUCT_ID_MISMATCH","CAMERA_LENS_FOCAL_LENGTH_MISMATCH","CAMERA_OR_LENS_DAMAGE_OBSERVED","CAMERA_IDENTITY_LABEL_NOT_LEGIBLE","CAMERA_PURCHASE_RECORD_MISMATCH","CAMERA_PACKAGE_CONTENTS_INCOMPLETE"];
    const missing=x=>Array.isArray(x)&&x.length<=32&&new Set(x).size===x.length&&x.every(k=>missingRoster.includes(k));
    function foundation(f,s){
      if(!v.exact(f,["schema","assessment_sha256","binding","notebook_sha256","inspection_sha256","status","coverage","row_checks","thickness","flatness_acceptance","missing_requirements","residuals","notebook_original_bound",...baseFlags])||f.schema!=="rocell.received_camera_record_assessment_summary.v1"||!v.digest(f.assessment_sha256)||!same(f.binding,s.binding)||f.notebook_sha256!==s.notebook_sha256||f.inspection_sha256!==s.inspection_sha256||!same(f.coverage,s.coverage)||!baseFlags.every(k=>f[k]===false)||typeof f.notebook_original_bound!=="boolean"||!missing(f.missing_requirements)||f.status!==(f.missing_requirements.length?"RECEIPT_INCOMPLETE":"RECEIPT_COMPLETE")||f.flatness_acceptance!=="DEFERRED_LIMIT"||!Array.isArray(f.row_checks)||f.row_checks.length!==16||!Array.isArray(f.residuals)||f.residuals.length!==6||!f.residuals.every(k=>typeof k==="string"&&/^[A-Z][A-Z0-9_]{0,127}$/.test(k)))return false;
      if(!f.row_checks.every((r,i)=>v.exact(r,["record_id","observation_status","acceptance"])&&r.record_id===records[i]&&["OBSERVED","UNKNOWN","UNRECORDED"].includes(r.observation_status)&&r.acceptance===(i===4?"DEFERRED_LIMIT":[2,3].includes(i)?"THICKNESS_ACCOMMODATION":"RECORDED_NOT_QUALIFIED")))return false;
      const t=f.thickness;
      return v.exact(t,["minimum_mm","maximum_mm","status","allowed_minimum_mm","allowed_maximum_mm"])&&["minimum_mm","maximum_mm"].every(k=>t[k]===null||(text(t[k],256)&&/^[0-9]+(?:\.[0-9]+)?$/.test(t[k])))&&["UNOBSERVED","WITHIN_ACCOMMODATION","OUTSIDE_ACCOMMODATION"].includes(t.status)&&t.allowed_minimum_mm==="17.5"&&t.allowed_maximum_mm==="18.5"&&(f.status!=="RECEIPT_COMPLETE"||(f.coverage.observed===16&&t.status==="WITHIN_ACCOMMODATION"&&f.notebook_original_bound));
    }
    function roles(t,c,requirements){
      if(!v.exact(t,["receipt_id","sequence","state","notebook","inspection","submission","assessment","review"])||typeof t.receipt_id!=="string"||!/^receivedcamera-[0-9a-f]{32}$/.test(t.receipt_id)||!v.integer(t.sequence,1,4)||!["INCOMPLETE","ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING","REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(t.state))return false;
      const n=t.notebook,s=t.submission,a=t.assessment,r=t.review;
      if(n!==null&&(!v.exact(n,["document","evidence_sha256","reference"])||!v.digest(n.evidence_sha256)||!reference(n.reference)||n.reference.payload_sha256!==n.evidence_sha256||n.reference.payload_bytes>65536||!notebook(n.document,c,requirements,null,n.evidence_sha256)))return false;
      for(const item of [s,a,r])if(item!==null&&(!binding(item.binding)||!contextKeys.every(k=>item.binding[k]===c[k])||item.binding.receipt_id!==t.receipt_id||item.sequence!==t.sequence||!roleFlags.every(k=>item[k]===false)||!bounded(item,24576)))return false;
      if(s!==null&&(!n||!v.exact(s,["schema","submission_sha256","status","binding","sequence","predecessor","coverage","notebook_sha256","inspection_sha256","draft_origin_notebook_sha256","carried_forward_record_ids","attachment_count","attachment_bytes","linked_row_count",...roleFlags])||s.schema!=="rocell.received_camera_submission_summary.v1"||s.status!=="SUBMISSION_COLLECTED"||!v.digest(s.submission_sha256)||s.notebook_sha256!==n.evidence_sha256||!same(s.coverage,n.document.coverage)||!(s.inspection_sha256===null||v.digest(s.inspection_sha256))||!(s.draft_origin_notebook_sha256===null||v.digest(s.draft_origin_notebook_sha256))||(s.sequence===1?s.predecessor!==null:!v.exact(s.predecessor,["submission","assessment","review"])||!Object.values(s.predecessor).every(v.digest))||!Array.isArray(s.carried_forward_record_ids)||!same(s.carried_forward_record_ids,records.filter(id=>s.carried_forward_record_ids.includes(id)))||!v.integer(s.attachment_count,0,16)||!v.integer(s.attachment_bytes,0,4194304)||!v.integer(s.linked_row_count,s.coverage.observed,16)))return false;
      if(a!==null&&(!s||!v.exact(a,["schema","assessment_sha256","status","binding","sequence","submission_sha256","foundation_sha256","verdict","missing_requirements","foundation",...roleFlags])||a.schema!=="rocell.received_camera_submission_assessment_summary.v1"||a.status!=="ASSESSED"||!v.digest(a.assessment_sha256)||!same(a.binding,s.binding)||a.submission_sha256!==s.submission_sha256||!foundation(a.foundation,s)||a.foundation_sha256!==a.foundation.assessment_sha256||!same(a.missing_requirements,a.foundation.missing_requirements)||a.verdict!==(a.foundation.status==="RECEIPT_COMPLETE"?"PASS":"BLOCKED")))return false;
      if(r!==null&&(!a||!v.exact(r,["schema","binding","sequence","meaning","submission_sha256","assessment_sha256","decision","verdict","reviewer_id","review_launch_id","reviewed_at_ns","distinct_operator_labels","review_sha256","status",...roleFlags])||r.schema!=="rocell.received_camera_submission_review_summary.v1"||r.status!=="REVIEW_RECORDED"||!same(r.binding,s.binding)||!v.digest(r.review_sha256)||r.submission_sha256!==s.submission_sha256||r.assessment_sha256!==a.assessment_sha256||!["ACKNOWLEDGE_EXACT","REJECT"].includes(r.decision)||r.verdict!==(r.decision==="REJECT"?"BLOCKED":a.verdict)||!actor(r.reviewer_id)||r.reviewer_id.toLowerCase()===s.binding.operator_id.toLowerCase()||!launch(r.review_launch_id)||!ns(r.reviewed_at_ns)||r.distinct_operator_labels!==true||!v.string(r.meaning,512)))return false;
      if(t.inspection!==null&&!inspection(t.inspection,s,n))return false;
      if(s&&(s.inspection_sha256===null)!==(t.inspection===null))return false;
      return !((["ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING"].includes(t.state)&&(!a||r!==null))||(["REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(t.state)&&!r)||(t.state==="REVIEWED_PASS"&&r.verdict!=="PASS")||(t.state==="REVIEWED_BLOCKED"&&r.verdict!=="BLOCKED"));
    }
    function inspection(i,s,n){
      const values=["observed_manufacturer","observed_product_id","observed_camera_serial"], conditions=["body_condition","lens_condition","connector_condition"], bools=["identity_label_legible","purchase_record_matches","package_contents_complete","inspection_uncertain"];
      const authority={scope:"DIAGNOSTIC_EVIDENCE_ONLY",hardware_commands_generated:0,power_commands_generated:0,motion_commands_generated:0,contact_commands_generated:0,power_authorized:false,motion_authorized:false,contact_authorized:false,build_promotion_authorized:false,session_mutation_effect:"NONE",physical_release_effect:"NONE"};
      if(!s||!n||!v.exact(i,["schema","binding","operator_id","observed_at_ns",...values,"observed_lens_focal_length_mm",...conditions,...bools,"purchase_record_evidence_id","inspection_image_evidence_ids","authority","receipt_sha256"])||i.schema!=="rocell.physical_onboarding.camera_receipt_inspection.v1"||i.receipt_sha256!==s.inspection_sha256||i.operator_id!==s.binding.operator_id||!ns(i.observed_at_ns)||!values.every(k=>v.string(i[k],2048)&&i[k].length<=512)||!(i.observed_lens_focal_length_mm===null||v.integer(i.observed_lens_focal_length_mm,1,500))||!conditions.every(k=>["ACCEPTABLE","DAMAGED","UNCERTAIN"].includes(i[k]))||!bools.every(k=>typeof i[k]==="boolean")||!same(i.authority,authority))return false;
      const b=i.binding;
      if(!v.exact(b,["source_binding_sha256","session_header_sha256","session_id","cell_id","stage_plan_sha256","stage","evidence","binding_sha256"])||!["source_binding_sha256","session_header_sha256","stage_plan_sha256","binding_sha256"].every(k=>v.digest(b[k]))||b.session_header_sha256!==s.binding.header_sha256||b.session_id!==s.binding.session_id||b.cell_id!==s.binding.cell_id||b.stage!=="camera_receipt"||!Array.isArray(b.evidence)||b.evidence.length<1||b.evidence.length>32||!b.evidence.every(reference)||new Set(b.evidence.map(x=>x.evidence_id)).size!==b.evidence.length)return false;
      return b.evidence.some(x=>same(x,n.reference))&&b.evidence.some(x=>x.evidence_id===i.purchase_record_evidence_id)&&Array.isArray(i.inspection_image_evidence_ids)&&i.inspection_image_evidence_ids.length>=1&&i.inspection_image_evidence_ids.length<=32&&new Set(i.inspection_image_evidence_ids).size===i.inspection_image_evidence_ids.length&&i.inspection_image_evidence_ids.every(id=>b.evidence.some(x=>x.evidence_id===id));
    }
    return {v,p,flags,baseFlags,roleFlags,records,stages,actions,same,bounded,context,contextKeys,binding,coverage,reference,notebook,roles,launch,actor};
  }

  function receivedCameraProjection(value,view) {
    const h=receivedCameraValidators(),{v,p,flags}=h;
    const pub=x=>v.exact(x,["status","operation_id"])&&["NOT_PUBLISHED","PENDING","CURRENT","HISTORICAL_HELD"].includes(x.status)&&(x.operation_id===null||v.identifier(x.operation_id));
    const exportPointer=x=>x===null||(v.exact(x,["path","export_id","manifest_sha256"])&&v.string(x.path,16384)&&v.identifier(x.export_id)&&v.digest(x.manifest_sha256));
    if(value?.schema==="rocell.wizard_received_camera_export_pointer.v1") {
      if(!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","latest_subjects","draft_sha256","metadata_export","separate_metadata_export_required","original_received_documents_included","private_original_media_included","physical_authority","hardware_qualified","meaning"])||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!pub(value.publication)||!(value.original_context===null||h.context(value.original_context))||!v.string(value.status,64)||!(value.draft_sha256===null||v.digest(value.draft_sha256))||!exportPointer(value.metadata_export)||value.separate_metadata_export_required!==true||["original_received_documents_included","private_original_media_included","physical_authority","hardware_qualified"].some(k=>value[k]!==false)||!v.string(value.meaning,512))return null;
      const t=value.latest_subjects;
      if(t!==null&&(!v.exact(t,["receipt_id","sequence","state","notebook_sha256","submission_sha256","assessment_sha256","review_sha256"])||typeof t.receipt_id!=="string"||!/^receivedcamera-[0-9a-f]{32}$/.test(t.receipt_id)||!v.integer(t.sequence,1,4)||!["INCOMPLETE","ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING","REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(t.state)||["notebook_sha256","submission_sha256","assessment_sha256","review_sha256"].some(k=>t[k]!==null&&!v.digest(t[k]))))return null;
      return value;
    }
    if(!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","stage_states","draft","draft_origin_notebook_sha256","collection","inbox","identity_entry","metadata_export","next_action","meaning",...flags])||value.schema!=="rocell.wizard_received_camera.v1"||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!flags.every(k=>value[k]===false)||!v.string(value.meaning,512)||!pub(value.publication)||!["NOT_STARTED","DRAFT","DISCOVERED","REVIEW_PENDING","REVIEWED_PASS","REVIEWED_BLOCKED","INCOMPLETE_HELD","HISTORICAL_HELD"].includes(value.status)||!(value.next_action===null||h.actions.includes(value.next_action))||!(value.identity_entry===null||v.digest(value.identity_entry))||!(value.draft_origin_notebook_sha256===null||v.digest(value.draft_origin_notebook_sha256)))return null;
    const c=value.original_context,t=value.collection,publication=value.publication.status,setup=p.setup(view.physical_camera_setup),requirements=setup?.prerequisites;
    const stageStates=["PENDING","WAITING_OPERATOR","REVIEW_PENDING","PASS","BLOCKED","INVALIDATED","INCIDENT_HOLD","SIDE_EFFECT_UNCERTAIN","COMPLETE_DIAGNOSTIC"];
    if((c!==null&&!h.context(c))||(value.stage_states!==null&&(!v.exact(value.stage_states,h.stages)||!Object.values(value.stage_states).every(x=>stageStates.includes(x))))||!v.exact(value.inbox,["discovery","choices"]))return null;
    const d=value.inbox.discovery,choices=value.inbox.choices;
    const mime={txt:"text/plain",json:"application/json",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg",pdf:"application/pdf"};
    const name=x=>typeof x==="string"&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,94}$/.test(x)&&!x.endsWith(".")&&!/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(x);
    const issueCodes=["BUSY","INVALID","LIMIT","UNSAFE_FILE","FILE_LIMIT","FILE_TYPE","CONTENT","CHANGED","STALE_CHOICE","SOURCE_CHANGED","CANCELLED","DEADLINE","READ_FAILED"].map(x=>"INTAKE_INBOX_"+x);
    if(!v.exact(d,["schema","status","directory","source_sha256","launch_session_id","discovery_sha256","files","issues","physical_authority","device_io_performed"])||d.schema!=="rocell.physical_intake_inbox.v1"||!["NOT_DISCOVERED","READY","HELD"].includes(d.status)||!v.string(d.directory,4096)||!/^(?:[A-Za-z]:[\\/]|\/)/.test(d.directory)||d.directory.replaceAll("\\","/").split("/").includes("..")||!d.directory.replaceAll("\\","/").endsWith("/software/runs/physical-intake-inbox")||d.source_sha256!==value.source_sha256||d.launch_session_id!==value.launch_session_id||d.physical_authority!==false||d.device_io_performed!==false||!Array.isArray(d.files)||d.files.length>32||!d.files.every(f=>v.exact(f,["choice_id","basename","media_type","payload_bytes","payload_sha256"])&&typeof f.choice_id==="string"&&/^intake-file-[0-9a-f]{32}$/.test(f.choice_id)&&name(f.basename)&&mime[f.basename.split(".").pop().toLowerCase()]===f.media_type&&v.integer(f.payload_bytes,1,2097152)&&v.digest(f.payload_sha256))||new Set(d.files.map(f=>f.choice_id)).size!==d.files.length||new Set(d.files.map(f=>f.basename)).size!==d.files.length||d.files.reduce((n,f)=>n+f.payload_bytes,0)>16777216||!Array.isArray(d.issues)||d.issues.length>33||!d.issues.every(i=>v.exact(i,["code","basename"])&&issueCodes.includes(i.code)&&(i.basename===null||name(i.basename)))||(d.status==="READY"?!v.digest(d.discovery_sha256):d.discovery_sha256!==null||d.files.length!==0)||(d.status==="NOT_DISCOVERED"&&d.issues.length!==0)||!Array.isArray(choices)||choices.length>32||!choices.every(i=>v.exact(i,["value","label"])&&d.files.some(f=>f.choice_id===i.value)&&v.string(i.label,256))||new Set(choices.map(i=>i.value)).size!==choices.length||(publication!=="CURRENT"&&choices.length!==0))return null;
    const e=value.metadata_export;
    const exportProvenance=x=>v.exact(x,["session_id","mode","source_binding_sha256","source_identity","software_version"])&&v.identifier(x.session_id)&&x.mode==="PHYSICAL_DIAGNOSTIC"&&v.digest(x.source_binding_sha256)&&v.exact(x.source_identity,["source_sha256"])&&x.source_identity.source_sha256===x.source_binding_sha256&&v.string(x.software_version,64);
    if(e!==null&&(!v.exact(e,["status","valid","path","export_root","export_id","files","total_bytes","manifest_sha256","physical_authority","provenance","limitations"])||e.status!=="EXPORTED_DIAGNOSTICS"||e.valid!==true||e.physical_authority!=="NONE"||!v.string(e.path,16384)||!v.string(e.export_root,16384)||!v.identifier(e.export_id)||!v.digest(e.manifest_sha256)||!v.integer(e.total_bytes,1,8388608)||!exportProvenance(e.provenance)||e.provenance.source_binding_sha256!==value.source_sha256||!Array.isArray(e.limitations)||e.limitations.length>16||!e.limitations.every(x=>v.string(x,1024))||!Array.isArray(e.files)||e.files.length<4||e.files.length>11||!e.files.every(f=>v.exact(f,["name","bytes","sha256"])&&typeof f.name==="string"&&/^(?:README\.md|report\.json|events\.jsonl|manifest\.json|attachment-received-camera-(?:cycle-0[1-4]|draft|attempt)\.json)$/.test(f.name)&&v.integer(f.bytes,f.name==="events.jsonl"?0:1,4194304)&&v.digest(f.sha256))||new Set(e.files.map(f=>f.name)).size!==e.files.length||["README.md","report.json","events.jsonl","manifest.json"].some(name=>!e.files.some(f=>f.name===name))||e.files.reduce((n,f)=>n+f.bytes,0)!==e.total_bytes))return null;
    if(publication==="PENDING")return value.draft===null&&t===null&&value.identity_entry===null&&value.draft_origin_notebook_sha256===null&&value.next_action===null&&d.status==="NOT_DISCOVERED"&&["NOT_STARTED","HISTORICAL_HELD"].includes(value.status)?value:null;
    if((value.draft!==null&&!h.notebook(value.draft,c,requirements,publication==="CURRENT"?value.launch_session_id:null))||(value.draft===null&&value.draft_origin_notebook_sha256!==null)||(t!==null&&(!c||!h.roles(t,c,requirements))))return null;
    if((value.status==="NOT_STARTED"&&(value.draft!==null||t!==null))||(value.status==="DRAFT"&&(value.draft===null||publication!=="CURRENT"))||(value.status==="DISCOVERED"&&(d.status!=="READY"||t!==null||value.draft!==null))||(["REVIEW_PENDING","REVIEWED_PASS","REVIEWED_BLOCKED"].includes(value.status)&&(!t||t.state!==value.status||publication!=="CURRENT"))||(publication==="HISTORICAL_HELD"&&!["NOT_STARTED","HISTORICAL_HELD"].includes(value.status))||(publication!=="CURRENT"&&value.next_action!==null))return null;
    if(publication==="CURRENT"){
      const b=setup?.session.binding,verification=setup?.session.verification,s=value.stage_states;
      if(!setup||setup.publication.status!=="CURRENT"||!verification||!s||value.publication.operation_id===null||value.source_sha256!==view.source_binding_sha256||value.source_sha256!==setup.source_sha256||value.launch_session_id!==view.session_id||value.launch_session_id!==setup.launch_session_id||h.stages.some((key,i)=>s[key]!==setup.session.stages[i].state))return null;
      if(c===null?requirements!==null:!requirements||c.source_sha256!==value.source_sha256||c.session_id!==b.session_id||c.cell_id!==b.cell_id||c.origin_launch_id!==b.launch_id||c.header_sha256!==verification.session.header_sha256||c.prerequisites_sha256!==requirements.evidence_sha256)return null;
      if((t||value.draft)&&(!c||s.workspace_sources!=="PASS"||s.static_camera_contract!=="PASS"))return null;
      if(t?.inspection&&t.inspection.binding.source_binding_sha256!==verification.cell.source_binding_sha256)return null;
      if((value.status==="REVIEW_PENDING"&&s.camera_receipt!=="REVIEW_PENDING")||(value.status==="REVIEWED_PASS"&&s.camera_receipt!=="PASS")||(value.status==="REVIEWED_BLOCKED"&&s.camera_receipt!=="BLOCKED")||((s.camera_identity==="WAITING_OPERATOR")!==(value.identity_entry!==null)))return null;
      if(t?.submission){const design=staticCameraOnboardingProjection(view.static_camera_onboarding,view)?.contract;if(!design?.review||design.review.verdict!=="PASS"||["receipt","assessment","review"].some(role=>t.submission.binding.static_contract[role]!==design[role][role+"_sha256"]))return null;}
    }
    return value;
  }

  function usbExportReceipt(receipt,source) {
    if(receipt===null)return true;
    const {v}=receivedCameraValidators(),q=receipt.provenance,fixed=["README.md","report.json","events.jsonl","manifest.json"];
    if(!v.exact(receipt,["status","valid","path","export_root","export_id","files","total_bytes","manifest_sha256","physical_authority","provenance","limitations"])||receipt.status!=="EXPORTED_DIAGNOSTICS"||receipt.valid!==true||receipt.physical_authority!=="NONE"||!["path","export_root"].every(k=>v.string(receipt[k],16384))||!v.identifier(receipt.export_id)||!v.digest(receipt.manifest_sha256)||!v.integer(receipt.total_bytes,1,8388608)||!v.exact(q,["session_id","mode","source_binding_sha256","source_identity","software_version"])||!v.identifier(q.session_id)||q.mode!=="PHYSICAL_DIAGNOSTIC"||q.source_binding_sha256!==source||!v.exact(q.source_identity,["source_sha256"])||q.source_identity.source_sha256!==source||!v.string(q.software_version,64)||!Array.isArray(receipt.limitations)||receipt.limitations.length>16||!receipt.limitations.every(x=>v.string(x,1024))||!Array.isArray(receipt.files)||receipt.files.length<5||receipt.files.length>12||!receipt.files.every(f=>v.exact(f,["name","bytes","sha256"])&&v.string(f.name,128)&&v.integer(f.bytes,f.name==="events.jsonl"?0:1,1048576)&&v.digest(f.sha256)))return false;
    const names=receipt.files.map(f=>f.name),parts=names.filter(n=>!fixed.includes(n)).sort();
    return new Set(names).size===names.length&&fixed.every(n=>names.includes(n))&&parts.length>=1&&parts.length<=8&&parts.every((n,j)=>n===`attachment-usb-identity-part-${String(j+1).padStart(2,"0")}.json`)&&receipt.files.reduce((n,f)=>n+f.bytes,0)===receipt.total_bytes;
  }

  function usbTrialBaselineValid(b,outer){
    if(b===null)return !["BASELINE_ACTIVE","BASELINE_RETAINED_BLOCKED"].includes(outer.status);
    const {v}=receivedCameraValidators(),flags=["physical_authority","hardware_qualified","camera_capture_authorized","arm_access_authorized"],nullable=(x,f)=>x===null||f(x),stamp=x=>typeof x==="number"&&Number.isInteger(x)&&x>0&&x<2**63,actor=x=>typeof x==="string"&&/^[\x20-\x7e]{1,64}$/.test(x)&&x.trim()===x;
    const states=["ENTERED","PREPARATION_REQUESTED","PREPARED","REVIEWED","BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","QUERY_REQUESTED","ORIGINAL_CAMPAIGN_HELD","RETAINED_BLOCKED","INCOMPLETE"],roles=["GENERIC_INVENTORY","NATIVE_INVENTORY","NATIVE_IDENTITY"],actions=["inventory_devices","native_camera_inventory","native_camera_identity"];
    if(!v.exact(b,["phase_id","state","phase_start_event_sha256","phase_started_at_utc_ns","acquisition_ledger","preparation","target","review","host_boot","execution","observation","phase_record",...flags])||typeof b.phase_id!=="string"||!/^usbphase-[0-9a-f]{32}$/.test(b.phase_id)||!states.includes(b.state)||!flags.every(k=>b[k]===false)||!nullable(b.phase_start_event_sha256,v.digest)||!nullable(b.phase_started_at_utc_ns,stamp)||!outer.plan)return false;
    const l=b.acquisition_ledger,p=b.preparation,r=b.review,t=b.target,h=b.host_boot,f=b.phase_record;
    if(l!==null){
      if(!v.exact(l,["schema","source_sha256","session_id","launch_session_id","trial_id","phase_id","phase_started_at_utc_ns","entries"])||l.schema!=="rocell.usb_phase_metadata_acquisition_ledger.v1"||l.source_sha256!==outer.source_sha256||l.session_id!==outer.original_context?.session_id||l.trial_id!==outer.plan.binding.trial_id||l.phase_id!==b.phase_id||!v.identifier(l.launch_session_id)||l.phase_started_at_utc_ns!==b.phase_started_at_utc_ns||!Array.isArray(l.entries)||l.entries.length>3)return false;
      let prior=l.phase_started_at_utc_ns;const ids=new Set();
      for(const [j,row] of l.entries.entries()){
        if(!v.exact(row,["role","action_id","operation_id","started_at_utc_ns","finished_at_utc_ns","published_at_utc_ns","document_sha256","result_sha256","completion_logged"])||row.role!==roles[j]||row.action_id!==actions[j]||!v.identifier(row.operation_id)||ids.has(row.operation_id)||!v.digest(row.document_sha256)||!v.digest(row.result_sha256)||row.completion_logged!==true||!["started_at_utc_ns","finished_at_utc_ns","published_at_utc_ns"].every(k=>stamp(row[k]))||!(prior<=row.started_at_utc_ns&&row.started_at_utc_ns<=row.finished_at_utc_ns&&row.finished_at_utc_ns<=row.published_at_utc_ns))return false;prior=row.published_at_utc_ns;ids.add(row.operation_id);
      }
    }
    if(p!==null&&(!v.exact(p,["schema","phase_id","plan_sha256","preparation_sha256","enrollment_sha256","operation_sha256","operator_id","phase_started_at_utc_ns","prepared_at_utc_ns","acquisition_count","meaning","stage_pass",...flags])||p.schema!=="rocell.usb_trial_baseline_preparation_summary.v1"||p.phase_id!==b.phase_id||p.plan_sha256!==outer.plan.plan_sha256||!["preparation_sha256","enrollment_sha256","operation_sha256"].every(k=>v.digest(p[k]))||!actor(p.operator_id)||p.acquisition_count!==3||!v.string(p.meaning,128)||p.stage_pass!==false||!flags.every(k=>p[k]===false)||!l||l.entries.length!==3||p.phase_started_at_utc_ns!==b.phase_started_at_utc_ns||!stamp(p.prepared_at_utc_ns)||p.prepared_at_utc_ns<l.entries[2].published_at_utc_ns))return false;
    if(t!==null&&(!p||!v.exact(t,["selection_sha256","native_identity_sha256","endpoint_sha256","symbolic_link","device_instance_id"])||!["selection_sha256","native_identity_sha256","endpoint_sha256"].every(k=>v.digest(t[k]))||!["symbolic_link","device_instance_id"].every(k=>v.string(t[k],4096))))return false;
    if(r!==null&&(!p||!t||!v.exact(r,["identity_sha256","policy_review_sha256","runtime_review_sha256","operator_id","reviewer_id","review_launch_id","boot_request_sha256"])||!["identity_sha256","policy_review_sha256","runtime_review_sha256","boot_request_sha256"].every(k=>v.digest(r[k]))||r.operator_id!==p.operator_id||!actor(r.reviewer_id)||r.reviewer_id.toLowerCase()===r.operator_id.toLowerCase()||r.review_launch_id!==l.launch_session_id))return false;
    if(h!==null&&(!r||!v.exact(h,["schema","original_state","observation_sha256","status","origin","host_key_sha256","boot_key_sha256","last_boot_up_time_utc","process_status","tree_exit_confirmed","blockers","physical_authority","hardware_qualified","device_io_performed"])||h.schema!=="rocell.wizard_usb_trial_boot_summary.v1"||!["BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","QUERY_REQUESTED","ORIGINAL_CAMPAIGN_HELD","RETAINED_BLOCKED","INCOMPLETE"].includes(h.original_state)||!v.digest(h.observation_sha256)||!["HELD","OBSERVED_HOST_BOOT"].includes(h.status)||!["WINDOWS_LOCAL_CIM","INJECTED_CIM_EXECUTOR","INCAPABLE_OWNED_CHILD"].includes(h.origin)||!["host_key_sha256","boot_key_sha256"].every(k=>nullable(h[k],v.digest))||!nullable(h.last_boot_up_time_utc,x=>typeof x==="string"&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$/.test(x))||!["SUCCEEDED","FAILED","CANCELLED","TIMED_OUT"].includes(h.process_status)||typeof h.tree_exit_confirmed!=="boolean"||!Array.isArray(h.blockers)||h.blockers.length>32||!h.blockers.every(x=>typeof x==="string"&&/^[A-Z0-9_]{1,128}$/.test(x))||["physical_authority","hardware_qualified","device_io_performed"].some(k=>h[k]!==false)||(h.status==="OBSERVED_HOST_BOOT"&&(!h.host_key_sha256||!h.boot_key_sha256||!h.last_boot_up_time_utc||!h.tree_exit_confirmed||h.process_status!=="SUCCEEDED"||h.blockers.length))))return false;
    if(!usbExecutionValid(b.execution,b.observation)||(b.execution!==null&&(!r||!h||h.status!=="OBSERVED_HOST_BOOT")))return false;
    const checkIds=["HOST_BOOT_OBSERVED","REVIEWED_NATIVE_SELECTION","OWNED_USB_RUN_SUCCEEDED","USB_OBSERVATION_COMPLETE","PROCESS_CLEANUP_CONFIRMED","NATIVE_CLEANUP_CONFIRMED","DRIVER_FIELDS_OBSERVED","DRIVER_SERVICE_MATCH","V2_OPERATING_USB3_OBSERVED"];
    if(f!==null&&(!b.execution||!v.exact(f,["phase_sha256","checks","provenance"])||!v.digest(f.phase_sha256)||!Array.isArray(f.checks)||f.checks.length!==9||!f.checks.every((r,j)=>v.exact(r,["check_id","passed"])&&r.check_id===checkIds[j]&&typeof r.passed==="boolean")||!v.exact(f.provenance,["usb","metadata","boot","metadata_helper_sha256"])||!["PHYSICAL_USB_QUERY","INCAPABLE_USB_QUERY"].includes(f.provenance.usb)||!["WINDOWS_NATIVE_METADATA","INCAPABLE_FIXTURE"].includes(f.provenance.metadata)||f.provenance.boot!==h.origin||!v.digest(f.provenance.metadata_helper_sha256)))return false;
    if(b.state==="RETAINED_BLOCKED"&&!f)return false;
    if(outer.status==="BASELINE_RETAINED_BLOCKED"&&b.state!=="RETAINED_BLOCKED")return false;
    if(outer.publication.status==="CURRENT"&&outer.status!=="HISTORICAL_HELD"&&p&&l.launch_session_id!==outer.launch_session_id&&b.state!=="RETAINED_BLOCKED")return false;
    return true;
  }

  const usbAbsenceActions=["physical_usb_absence_begin","physical_usb_absence_boot_review","physical_usb_absence_boot_collect","physical_usb_absence_runtime_review","physical_usb_absence_collect"];
  function usbAbsenceValid(a,outer,historical=false){
    const {v,h}= {v:cameraConfigurationValidators(),h:receivedCameraValidators()},flags=["physical_authority","hardware_qualified","camera_capture_authorized","arm_access_authorized"];
    const actor=x=>typeof x==="string"&&x.length>=1&&x.length<=64&&x.trim()===x&&/^[\x20-\x7e]+$/.test(x),stamp=x=>Number.isInteger(x)&&x>0&&x<2**63, nullable=(x,f)=>x===null||f(x),code=x=>typeof x==="string"&&/^[A-Za-z0-9_:-]{1,128}$/.test(x);
    if(a===null)return !["ABSENCE_ACTIVE","ABSENCE_RETAINED_BLOCKED"].includes(outer.status);
    const states=["PREPARATION_REQUESTED","PREPARED","BOOT_REVIEWED","BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","PRESENCE_REVIEW_REQUESTED","PRESENCE_REVIEW_PREPARED","RUNTIME_REVIEWED","QUERY_REQUESTED","RETAINED_BLOCKED","INCOMPLETE","ORIGINAL_CAMPAIGN_HELD"];
    if(!v.exact(a,["phase_id","phase","state","phase_start_event_sha256","phase_started_at_utc_ns","target","operator_event","preparation","boot_intent_sha256","boot_review","host_boot","runtime_review","execution","observation","phase_record",...flags])||!/^usbphase-[0-9a-f]{32}$/.test(a.phase_id)||a.phase!=="RECONNECT_ABSENCE"||!states.includes(a.state)||!flags.every(k=>a[k]===false)||!nullable(a.phase_start_event_sha256,v.digest)||!nullable(a.phase_started_at_utc_ns,stamp)||!outer.plan||!outer.baseline||outer.baseline.state!=="RETAINED_BLOCKED")return false;
    const t=a.target,p=a.preparation,r=a.operator_event,br=a.boot_review,b=a.host_boot,rr=a.runtime_review,e=a.execution,o=a.observation,f=a.phase_record;
    if(t!==null&&(!v.exact(t,["physical_usb_instance_id","physical_device_id","phase_binding_sha256","baseline_sha256","operation_sha256","runtime_registration_sha256","policy_sha256","launch_session_id"])||!v.string(t.physical_usb_instance_id,4096)||!/^USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}(?:&REV_[0-9A-F]{4})?\\[^\\\x00-\x20\x7f-\uffff]+$/i.test(t.physical_usb_instance_id)||t.physical_device_id!==t.physical_usb_instance_id.split("\\").slice(0,2).join("\\")||!["phase_binding_sha256","baseline_sha256","operation_sha256","runtime_registration_sha256","policy_sha256"].every(k=>v.digest(t[k]))||!h.launch(t.launch_session_id)))return false;
    if(r!==null&&(!t||!v.exact(r,["evidence_sha256","operator_id","event","reported_at_utc_ns"])||!v.digest(r.evidence_sha256)||!actor(r.operator_id)||r.event!=="OPERATOR_REPORTED_CAMERA_USB_UNPLUGGED"||!stamp(r.reported_at_utc_ns)||r.reported_at_utc_ns<a.phase_started_at_utc_ns))return false;
    if(p!==null&&(!r||!v.exact(p,["schema","preparation_sha256","phase_id","launch_session_id","operator_id","prepared_at_utc_ns","phase_started_at_utc_ns","phase_binding_sha256","operation_sha256","operator_event_sha256","runtime_registration_sha256","file_count","status","physical_authority","hardware_qualified","device_io_performed"])||p.schema!=="rocell.usb_absence_preparation_summary.v1"||!v.digest(p.preparation_sha256)||p.phase_id!==a.phase_id||p.launch_session_id!==t.launch_session_id||p.operator_id!==r.operator_id||p.phase_started_at_utc_ns!==a.phase_started_at_utc_ns||!stamp(p.prepared_at_utc_ns)||p.prepared_at_utc_ns<r.reported_at_utc_ns||!["phase_binding_sha256","operation_sha256","runtime_registration_sha256"].every(k=>p[k]===t[k])||p.operator_event_sha256!==r.evidence_sha256||!v.integer(p.file_count,1,32)||p.status!=="FILES_MATCHED"||!["physical_authority","hardware_qualified","device_io_performed"].every(k=>p[k]===false)))return false;
    if(!nullable(a.boot_intent_sha256,v.digest)||(a.boot_intent_sha256!==null&&!p))return false;
    if(br!==null&&(!a.boot_intent_sha256||!v.exact(br,["evidence_sha256","operator_id","reviewer_id","launch_session_id","intent_sha256"])||!v.digest(br.evidence_sha256)||br.operator_id!==r.operator_id||!actor(br.reviewer_id)||br.reviewer_id.toLowerCase()===br.operator_id.toLowerCase()||br.launch_session_id!==t.launch_session_id||br.intent_sha256!==a.boot_intent_sha256))return false;
    if(b!==null){
      if(!br||!v.exact(b,["schema","original_state","observation_sha256","status","origin","host_key_sha256","boot_key_sha256","last_boot_up_time_utc","process_status","tree_exit_confirmed","blockers","boot_relation","physical_authority","hardware_qualified","device_io_performed"])||b.schema!=="rocell.wizard_usb_absence_boot_summary.v1"||!["BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","INCOMPLETE"].includes(b.original_state)||!v.digest(b.observation_sha256)||!["HELD","OBSERVED_HOST_BOOT"].includes(b.status)||!["WINDOWS_LOCAL_CIM","INJECTED_CIM_EXECUTOR","INCAPABLE_OWNED_CHILD"].includes(b.origin)||!["host_key_sha256","boot_key_sha256"].every(k=>nullable(b[k],v.digest))||!nullable(b.last_boot_up_time_utc,x=>typeof x==="string"&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$/.test(x))||!["SUCCEEDED","FAILED","CANCELLED","TIMED_OUT"].includes(b.process_status)||typeof b.tree_exit_confirmed!=="boolean"||!Array.isArray(b.blockers)||b.blockers.length>32||!b.blockers.every(code)||!["HELD","SAME_HOST_SAME_BOOT","SAME_HOST_DIFFERENT_BOOT"].includes(b.boot_relation)||!["physical_authority","hardware_qualified","device_io_performed"].every(k=>b[k]===false))return false;
      if(b.status==="OBSERVED_HOST_BOOT"&&(!b.host_key_sha256||!b.boot_key_sha256||!b.last_boot_up_time_utc))return false;
      if(b.original_state==="BOOT_RETAINED"&&(b.status!=="OBSERVED_HOST_BOOT"||b.origin!=="WINDOWS_LOCAL_CIM"||!b.tree_exit_confirmed||b.process_status!=="SUCCEEDED"||b.blockers.length||b.boot_relation!=="SAME_HOST_SAME_BOOT"))return false;
    }
    if(rr!==null&&(!b||b.original_state!=="BOOT_RETAINED"||!v.exact(rr,["evidence_sha256","operator_id","reviewer_id","launch_session_id","operation_sha256","helper_sha256","usb_presence_policy_sha256"])||!v.digest(rr.evidence_sha256)||!v.digest(rr.helper_sha256)||rr.operator_id!==r.operator_id||!actor(rr.reviewer_id)||rr.reviewer_id.toLowerCase()===rr.operator_id.toLowerCase()||rr.launch_session_id!==t.launch_session_id||rr.operation_sha256!==t.operation_sha256||rr.usb_presence_policy_sha256!==t.policy_sha256))return false;
    if(e!==null){
      if(!rr||!v.exact(e,["schema","evidence_sha256","preparation_sha256","provenance","status","current_complete","native_outcome","actual_counts","no_attempt","released","process_cleanup_confirmed","native_cleanup_confirmed","counter_coverage","error","cleanup_errors","physical_authority","hardware_qualified","retries"])||e.schema!=="rocell.owned_usb_presence_run_summary.v1"||!v.digest(e.evidence_sha256)||!v.digest(e.preparation_sha256)||!["PHYSICAL_USB_PRESENCE","INCAPABLE_USB_PRESENCE"].includes(e.provenance)||!["PRESENT","ABSENT","HELD","FAILED","CANCELLED","TIMED_OUT","CLEANUP_UNCERTAIN"].includes(e.status)||!["current_complete","no_attempt","released","process_cleanup_confirmed","native_cleanup_confirmed"].every(k=>typeof e[k]==="boolean")||e.current_complete!==["PRESENT","ABSENT","HELD"].includes(e.status)||!nullable(e.native_outcome,x=>["PRESENT","ABSENT","HELD"].includes(x))||!nullable(e.error,code)||!Array.isArray(e.cleanup_errors)||e.cleanup_errors.length>16||!e.cleanup_errors.every(code)||e.physical_authority!==false||e.hardware_qualified!==false||e.retries!==0)return false;
      const c=e.actual_counts;
      if(e.counter_coverage==="NOT_REPORTED"){if(c!==null||e.no_attempt||e.native_cleanup_confirmed)return false;}
      else if(["NATIVE_RECEIPT","NO_PROCESS_CREATED"].includes(e.counter_coverage)){if(!v.exact(c,["api_calls","device_handle_opens","configuration_writes","frames"])||!v.integer(c.api_calls,0,4)||!["device_handle_opens","configuration_writes","frames"].every(k=>c[k]===0)|| (e.counter_coverage==="NO_PROCESS_CREATED"?(!e.no_attempt||e.released||c.api_calls!==0||e.native_cleanup_confirmed):e.no_attempt))return false;}else return false;
    }
    if(o!==null&&(!e||!v.exact(o,["schema","observation_sha256","request_sha256","provider","target_instance_id","outcome","error","api_calls","physical_authority","meaning"])||o.schema!=="rocell.usb_presence_summary.v1"||!v.digest(o.observation_sha256)||!v.digest(o.request_sha256)||!["WINDOWS_CONFIGURATION_MANAGER","INCAPABLE_FIXTURE"].includes(o.provider)||o.target_instance_id!==t.physical_usb_instance_id||o.outcome!==e.native_outcome||!nullable(o.error,code)||!v.integer(o.api_calls,0,4)||o.api_calls!==e.actual_counts?.api_calls||o.physical_authority!==false||!v.string(o.meaning,512)))return false;
    if(e&&((e.native_outcome!==null)!==(o!==null)))return false;
    const checks=["HOST_BOOT_PHYSICAL_OWNED_CLEAN","SAME_HOST_SAME_BOOT_AS_BASELINE","OPERATOR_REPORT_BOOT_REVIEW_QUERY_ORDER","PRESENCE_OBSERVATION_PHYSICAL_ORIGIN","PRESENCE_OWNED_RESULT_COMPLETE","PRESENCE_PROCESS_CLEANUP_CONFIRMED","PRESENCE_NATIVE_CLEANUP_CONFIRMED","EXACT_PHYSICAL_NODE_ABSENT"];
    if(f!==null){if(!e||!v.exact(f,["phase_sha256","status","presence_outcome","boot_relation","checks","missing_requirements","physical_node_absence_observed"])||!v.digest(f.phase_sha256)||f.presence_outcome!==e.native_outcome||f.boot_relation!==b.boot_relation||!Array.isArray(f.checks)||f.checks.length!==8||!f.checks.every((c,i)=>v.exact(c,["check_id","passed"])&&c.check_id===checks[i]&&typeof c.passed==="boolean")||JSON.stringify(f.missing_requirements)!==JSON.stringify(f.checks.filter(c=>!c.passed).map(c=>c.check_id))||f.status!==(f.missing_requirements.length?"HELD":"ABSENCE_OBSERVATIONS_RETAINED")||f.physical_node_absence_observed!==(f.missing_requirements.length===0))return false;}
    if(a.state==="RETAINED_BLOCKED"&&!f)return false;
    if(outer.status==="ABSENCE_RETAINED_BLOCKED"&&a.state!=="RETAINED_BLOCKED")return false;
    if(historical&&a&&(a.state!=="RETAINED_BLOCKED"||a.phase_record?.physical_node_absence_observed!==true))return false;
    if(!historical&&outer.publication.status==="CURRENT"&&outer.status!=="HISTORICAL_HELD"&&t&&t.launch_session_id!==outer.launch_session_id)return false;
    return true;
  }

  const usbReconnectActions=["begin","prepare","review","boot_collect","collect"].map(n=>"physical_usb_reconnect_"+n);
  const usbRebootActions=["begin","prepare","review","boot_collect","collect"].map(n=>"physical_usb_reboot_"+n);
  // One shared display grammar, with two closed phase contracts. No input is relabeled.
  function usbReconnectValid(a,outer,{reboot=false,historical=false}={}){
    const v=cameraConfigurationValidators(),h=receivedCameraValidators(),flags=["physical_authority","hardware_qualified","camera_capture_authorized","arm_access_authorized"],nullable=(x,f)=>x===null||f(x),stamp=x=>Number.isInteger(x)&&x>0&&x<2**63;
    const actor=x=>typeof x==="string"&&x.length>=1&&x.length<=64&&x.trim()===x&&/^[\x20-\x7e]+$/.test(x),code=x=>typeof x==="string"&&/^[A-Za-z0-9_:-]{1,128}$/.test(x);
    const phaseName=reboot?"REBOOT":"RECONNECT";
    if(a===null)return ![phaseName+"_ACTIVE",phaseName+"_RETAINED_BLOCKED"].includes(outer.status);
    if(!v.exact(a,["phase_id","state","phase_start_event_sha256","phase_started_at_utc_ns","operator_event","acquisition_ledger","preparation","target","review","host_boot","execution","observation","phase_record",...flags])||typeof a.phase_id!=="string"||!/^usbphase-[0-9a-f]{32}$/.test(a.phase_id)||!["PREPARATION_REQUESTED","PREPARED","REVIEWED","BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","QUERY_REQUESTED","RETAINED_BLOCKED","INCOMPLETE","ORIGINAL_CAMPAIGN_HELD"].includes(a.state)||!flags.every(k=>a[k]===false)||!nullable(a.phase_start_event_sha256,v.digest)||!nullable(a.phase_started_at_utc_ns,stamp)||!outer.plan||outer.absence?.state!=="RETAINED_BLOCKED"||outer.absence.phase_record?.physical_node_absence_observed!==true)return false;
    if(reboot&&(outer.reconnect?.state!=="RETAINED_BLOCKED"||outer.reconnect.phase_record?.status!=="RECONNECT_OBSERVATIONS_RETAINED"||a.phase_id===outer.reconnect.phase_id))return false;
    const r=a.operator_event,l=a.acquisition_ledger,p=a.preparation,t=a.target,review=a.review,b=a.host_boot,f=a.phase_record;
    if(r!==null&&(!v.exact(r,["evidence_sha256","operator_id","launch_session_id","reported_at_utc_ns","event"])||!v.digest(r.evidence_sha256)||!actor(r.operator_id)||!h.launch(r.launch_session_id)||!stamp(r.reported_at_utc_ns)||!stamp(a.phase_started_at_utc_ns)||r.reported_at_utc_ns<a.phase_started_at_utc_ns||r.event!==(reboot?"OPERATOR_REPORTED_HOST_RESTARTED":"OPERATOR_REPORTED_CAMERA_USB_RECONNECTED")))return false;
    if(l!==null){
      if(!r||!v.exact(l,["schema","source_sha256","session_id","launch_session_id","trial_id","phase_id","phase_started_at_utc_ns","entries"])||l.schema!=="rocell.usb_phase_metadata_acquisition_ledger.v1"||l.source_sha256!==outer.source_sha256||l.session_id!==outer.original_context?.session_id||l.launch_session_id!==r.launch_session_id||l.trial_id!==outer.plan.binding.trial_id||l.phase_id!==a.phase_id||l.phase_started_at_utc_ns!==a.phase_started_at_utc_ns||!Array.isArray(l.entries)||l.entries.length>3)return false;
      const roles=["GENERIC_INVENTORY","NATIVE_INVENTORY","NATIVE_IDENTITY"],actions=["inventory_devices","native_camera_inventory","native_camera_identity"],ids=new Set([a.phase_id]);let prior=r.reported_at_utc_ns;
      for(const [index,row] of l.entries.entries()){
        if(!v.exact(row,["role","action_id","operation_id","started_at_utc_ns","finished_at_utc_ns","published_at_utc_ns","document_sha256","result_sha256","completion_logged"])||row.role!==roles[index]||row.action_id!==actions[index]||!v.identifier(row.operation_id)||ids.has(row.operation_id)||!v.digest(row.document_sha256)||!v.digest(row.result_sha256)||row.completion_logged!==true||!["started_at_utc_ns","finished_at_utc_ns","published_at_utc_ns"].every(k=>stamp(row[k]))||!(prior<=row.started_at_utc_ns&&row.started_at_utc_ns<=row.finished_at_utc_ns&&row.finished_at_utc_ns<=row.published_at_utc_ns))return false;
        prior=row.published_at_utc_ns;ids.add(row.operation_id);
      }
    }
    if(p!==null&&(!r||!l||l.entries.length!==3||!v.exact(p,["preparation_sha256","operator_id","prepared_at_utc_ns","enrollment_sha256","operation_sha256","runtime_registration_sha256","file_count"])||!["preparation_sha256","enrollment_sha256","operation_sha256","runtime_registration_sha256"].every(k=>v.digest(p[k]))||p.operator_id!==r.operator_id||!stamp(p.prepared_at_utc_ns)||p.prepared_at_utc_ns<l.entries[2].published_at_utc_ns||!v.integer(p.file_count,1,32)))return false;
    if(t!==null&&(!p||!v.exact(t,["selection_sha256","native_identity_sha256","endpoint_sha256","symbolic_link","device_instance_id"])||!["selection_sha256","native_identity_sha256","endpoint_sha256"].every(k=>v.digest(t[k]))||!["symbolic_link","device_instance_id"].every(k=>v.string(t[k],4096))))return false;
    if(review!==null&&(!p||!t||!v.exact(review,["identity_sha256","policy_review_sha256","runtime_review_sha256","operator_id","reviewer_id","review_launch_id","boot_request_sha256"])||!["identity_sha256","policy_review_sha256","runtime_review_sha256","boot_request_sha256"].every(k=>v.digest(review[k]))||review.operator_id!==p.operator_id||!actor(review.reviewer_id)||review.reviewer_id.toLowerCase()===review.operator_id.toLowerCase()||review.review_launch_id!==r.launch_session_id))return false;
    if(b!==null){
      if(!review||!v.exact(b,["schema","original_state","observation_sha256","status","origin","host_key_sha256","boot_key_sha256","last_boot_up_time_utc","process_status","tree_exit_confirmed","blockers","boot_relation",...(reboot?["restart_status","reconnect_finished_at_utc_ns","phase_started_at_utc_ns"]:[]),"physical_authority","hardware_qualified","device_io_performed"])||b.schema!==(reboot?"rocell.wizard_usb_reboot_boot_summary.v1":"rocell.wizard_usb_reconnect_boot_summary.v1")||!["BOOT_REQUESTED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN","INCOMPLETE"].includes(b.original_state)||!v.digest(b.observation_sha256)||!["HELD","OBSERVED_HOST_BOOT"].includes(b.status)||!["WINDOWS_LOCAL_CIM","INJECTED_CIM_EXECUTOR","INCAPABLE_OWNED_CHILD"].includes(b.origin)||!["host_key_sha256","boot_key_sha256"].every(k=>nullable(b[k],v.digest))||!nullable(b.last_boot_up_time_utc,x=>typeof x==="string"&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$/.test(x))||!["SUCCEEDED","FAILED","CANCELLED","TIMED_OUT"].includes(b.process_status)||typeof b.tree_exit_confirmed!=="boolean"||!Array.isArray(b.blockers)||b.blockers.length>32||!b.blockers.every(code)||!["HELD","SAME_HOST_SAME_BOOT","SAME_HOST_DIFFERENT_BOOT"].includes(b.boot_relation)||!["physical_authority","hardware_qualified","device_io_performed"].every(k=>b[k]===false))return false;
      if(reboot&&(!["NOT_EVALUATED","BOOT_RETAINED","BOOT_HELD","BOOT_UNCERTAIN"].includes(b.restart_status)||!nullable(b.reconnect_finished_at_utc_ns,stamp)||!nullable(b.phase_started_at_utc_ns,stamp)||(b.phase_started_at_utc_ns!==null&&b.phase_started_at_utc_ns!==a.phase_started_at_utc_ns)))return false;
      if(reboot&&b.original_state==="BOOT_RETAINED"&&(b.restart_status!=="BOOT_RETAINED"||b.reconnect_finished_at_utc_ns===null||b.phase_started_at_utc_ns===null||b.reconnect_finished_at_utc_ns>=b.phase_started_at_utc_ns))return false;
      if(b.status==="OBSERVED_HOST_BOOT"&&(!b.host_key_sha256||!b.boot_key_sha256||!b.last_boot_up_time_utc))return false;
      if(b.original_state==="BOOT_RETAINED"&&(b.status!=="OBSERVED_HOST_BOOT"||b.origin!=="WINDOWS_LOCAL_CIM"||!b.tree_exit_confirmed||b.process_status!=="SUCCEEDED"||b.blockers.length||b.boot_relation!==(reboot?"SAME_HOST_DIFFERENT_BOOT":"SAME_HOST_SAME_BOOT")))return false;
    }
    if(!usbExecutionValid(a.execution,a.observation)||(a.execution!==null&&(!review||b?.original_state!=="BOOT_RETAINED")))return false;
    if(f!==null){
      if(!a.execution||!v.exact(f,["phase_sha256","status","boot_relation","values","comparisons","checks","missing_requirements"])||!v.digest(f.phase_sha256)||f.boot_relation!==b.boot_relation)return false;
      const fields="descriptor_serial vid pid endpoint endpoint_instance physical_usb_instance host_controller port_topology driver_provider driver_service driver_version driver_inf generic_driver_service generic_serial generic_vid generic_pid container_id machine_uuid boot_time_utc".split(" ");
      if(!v.exact(f.values,fields))return false;
      for(const item of Object.values(f.values)){
        if(!v.exact(item,["status","value","sha256"])||!["NOT_OBSERVED","VALUE_RETAINED","VALUE_IN_ORIGINAL"].includes(item.status))return false;
        if(item.status==="NOT_OBSERVED"){if(item.value!==null||item.sha256!==null)return false;}
        else if(!v.digest(item.sha256)||(item.status==="VALUE_IN_ORIGINAL"?item.value!==null:item.value===null||new TextEncoder().encode(JSON.stringify(item.value)).length>128))return false;
      }
      const names=fields.filter(k=>k!=="boot_time_utc").sort();
      const hashKeys=["baseline_sha256","reconnect_sha256",...(reboot?["reboot_sha256"]:[])],lastHash=reboot?"reboot_sha256":"reconnect_sha256";
      if(!Array.isArray(f.comparisons)||f.comparisons.length!==names.length||!f.comparisons.every((row,i)=>{const hashes=hashKeys.map(k=>row[k]);return v.exact(row,["field","status",...hashKeys])&&row.field===names[i]&&hashes.every(x=>nullable(x,v.digest))&&row[lastHash]===f.values[row.field].sha256&&row.status===(hashes.includes(null)?"NOT_OBSERVED":new Set(hashes).size===1?"MATCHED":"CHANGED");}))return false;
      const checks=("HOST_BOOT_PHYSICAL_OWNED_CLEAN "+(reboot?"SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN ":"SAME_HOST_SAME_BOOT_AS_ABSENCE ")+"OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER PHYSICAL_OBSERVATION_ORIGINS OWNED_RESULT_CURRENT_COMPLETE REVIEWED_NATIVE_SELECTION OWNED_USB_RUN_SUCCEEDED USB_OBSERVATION_COMPLETE PROCESS_CLEANUP_CONFIRMED NATIVE_CLEANUP_CONFIRMED DRIVER_FIELDS_OBSERVED DRIVER_SERVICE_MATCH V2_OPERATING_USB3_OBSERVED RECEIVED_SERIAL_MATCH GENERIC_VID_PID_MATCH EXACT_ABSENCE_PHYSICAL_NODE_RETURNED "+(reboot?"BASELINE_AND_RECONNECT_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY":"BASELINE_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY")).split(" ");
      if(!Array.isArray(f.checks)||f.checks.length!==checks.length||!f.checks.every((row,i)=>v.exact(row,["check_id","passed"])&&row.check_id===checks[i]&&typeof row.passed==="boolean")||JSON.stringify(f.missing_requirements)!==JSON.stringify(f.checks.filter(row=>!row.passed).map(row=>row.check_id))||f.status!==(f.missing_requirements.length?"HELD":phaseName+"_OBSERVATIONS_RETAINED"))return false;
    }
    if((a.state==="RETAINED_BLOCKED"&&!f)||(outer.status===phaseName+"_RETAINED_BLOCKED"&&a.state!=="RETAINED_BLOCKED"))return false;
    if(historical&&(a.state!=="RETAINED_BLOCKED"||(!reboot&&f?.status!=="RECONNECT_OBSERVATIONS_RETAINED")))return false;
    if(!historical&&outer.publication.status==="CURRENT"&&r&&r.launch_session_id!==outer.launch_session_id)return false;
    return true;
  }

  // Display consistency only: original authentication belongs to Setup, never
  // to these summaries. Preserve partial-review files without promoting them.
  const usbCompleteStates=["ASSESSMENT_REQUESTED","REVIEW_PENDING","REVIEWED_PASS","REVIEWED_BLOCKED","INCOMPLETE"];
  const usbCompleteActions=["physical_usb_complete_assess","physical_usb_complete_review"];
  function usbCompleteValid(outer,stages=null){
    const h=receivedCameraValidators(),{v}=h,c=outer.complete,pub=outer.publication.status;
    if(pub==="PENDING")return outer.status==="NOT_DECLARED"&&outer.next_action===null&&["plan","baseline","absence","reconnect","reboot","complete"].every(k=>outer[k]===null);
    const names=["BASELINE","RECONNECT_ABSENCE","AFTER_RECONNECT","AFTER_REBOOT"],statuses=["OBSERVATIONS_RETAINED","ABSENCE_OBSERVATIONS_RETAINED","RECONNECT_OBSERVATIONS_RETAINED","REBOOT_OBSERVATIONS_RETAINED"],rows=[outer.baseline,outer.absence,outer.reconnect,outer.reboot].map(x=>x?.phase_record);
    if(!outer.plan||rows.some(x=>!x)||outer.reboot.state!=="RETAINED_BLOCKED")return false;
    // Baseline's historical schema exposes checks, not a status field.
    rows[0]={...rows[0],status:rows[0].checks.every(c=>c.passed)?statuses[0]:"HELD"};
    const status=c===null?"COMPLETE_REVIEW_READY":c?.state,allowed=[null,"physical_usb_identity_export"];
    if(pub==="CURRENT"&&outer.status!==status)return false;
    if(pub!=="CURRENT"&&!allowed.includes(outer.next_action))return false;
    if(c===null)allowed.push(usbCompleteActions[0]);
    else {
      if(!v.exact(c,["series_id","state","series_sha256","assessment_sha256","review_sha256","assessment","review"])||typeof c.series_id!=="string"||!/^usbseries-[0-9a-f]{32}$/.test(c.series_id)||!usbCompleteStates.includes(status)||!["series_sha256","assessment_sha256","review_sha256"].every(k=>c[k]===null||v.digest(c[k])))return false;
      const a=c.assessment,r=c.review;
      if((a===null)!==(c.assessment_sha256===null)||(r===null)!==(c.review_sha256===null)||(a!==null&&c.series_sha256===null)||(r!==null&&a===null))return false;
      if(status==="ASSESSMENT_REQUESTED"&&c.series_sha256!==null)return false;
      if(status==="REVIEW_PENDING"){if(a===null||r!==null)return false;allowed.push(usbCompleteActions[1]);}
      if(["REVIEWED_PASS","REVIEWED_BLOCKED"].includes(status)&&r===null)return false;
      if(a!==null){
        const checks=[{check_id:"PHYSICAL_PLAN",passed:true},{check_id:"BASELINE_PHYSICAL_OWNED_BOOT",passed:outer.baseline.host_boot.original_state==="BOOT_RETAINED"},...rows.map((row,i)=>({check_id:names[i]+"_COMPLETE",passed:row.status===statuses[i]})),...rows.flatMap((row,i)=>row.checks.map(check=>({check_id:names[i]+"__"+check.check_id,passed:check.passed})))];
        const phases=rows.map((row,i)=>({phase:names[i],phase_sha256:row.phase_sha256,status:row.status,missing_checks:row.checks.filter(x=>!x.passed).map(x=>x.check_id)})),comparisons=rows[3].comparisons.map(row=>({field:row.field,status:row.status})),missing=checks.filter(x=>!x.passed).map(x=>x.check_id);
        const equalRows=(left,right)=>Array.isArray(left)&&left.length===right.length&&left.every((row,i)=>v.exact(row,Object.keys(right[i]))&&Object.keys(right[i]).every(k=>JSON.stringify(row[k])===JSON.stringify(right[i][k])));
        if(!v.exact(a,["verdict","phases","comparisons","checks","missing_requirements"])||!equalRows(a.checks,checks)||!equalRows(a.phases,phases)||!equalRows(a.comparisons,comparisons)||JSON.stringify(a.missing_requirements)!==JSON.stringify(missing)||a.verdict!==(missing.length?"BLOCKED":"ELIGIBLE_FOR_ORIGINAL_REVIEW"))return false;
      }
      if(r!==null){
        if(!v.exact(r,["verdict","decision","reviewer_id","review_launch_id","reviewed_at_utc_ns","assessment_sha256","series_sha256"])||!["REJECT","ACKNOWLEDGE_EXACT"].includes(r.decision)||typeof r.reviewer_id!=="string"||!/^[\x20-\x7e]{1,64}$/.test(r.reviewer_id)||r.reviewer_id.trim()!==r.reviewer_id||!h.launch(r.review_launch_id)||!Number.isInteger(r.reviewed_at_utc_ns)||r.reviewed_at_utc_ns<1)return false;
        const eligible=r.decision==="ACKNOWLEDGE_EXACT"&&a.verdict==="ELIGIBLE_FOR_ORIGINAL_REVIEW";
        if(r.series_sha256!==c.series_sha256||r.assessment_sha256!==c.assessment_sha256||r.verdict!==(eligible?"ELIGIBLE_FOR_ORIGINAL_STAGE_ACCEPTANCE":"BLOCKED")||(status.startsWith("REVIEWED_")&&status!==(eligible?"REVIEWED_PASS":"REVIEWED_BLOCKED")))return false;
      }
    }
    if(!allowed.includes(outer.next_action))return false;
    if(pub==="CURRENT"&&stages!==null){
      const expected={COMPLETE_REVIEW_READY:"BLOCKED",ASSESSMENT_REQUESTED:"WAITING_OPERATOR",REVIEW_PENDING:"REVIEW_PENDING",REVIEWED_PASS:"PASS",REVIEWED_BLOCKED:"BLOCKED",INCOMPLETE:null}[status];
      if((expected?stages[3].state!==expected:!["WAITING_OPERATOR","REVIEW_PENDING"].includes(stages[3].state))||stages.slice(4).some(row=>row.state!=="PENDING"))return false;
    }
    return true;
  }

  function usbQualificationProjection(value,view) {
    const h=receivedCameraValidators(),{v,p}=h,flags=["physical_authority","hardware_qualified","camera_capture_authorized","arm_access_authorized"];
    const phases=["BASELINE","RECONNECT_ABSENCE","AFTER_RECONNECT","AFTER_REBOOT"],action="physical_usb_qualification_declare";
    const actor=x=>typeof x==="string"&&x.length>=1&&x.length<=64&&x.trim()===x&&/^[\x20-\x7e]+$/.test(x);
    const label=(x,n)=>v.string(x,n)&&x.trim()===x&&!/[\x00-\x1f\x7f]/.test(x);
    const version6=value?.schema==="rocell.wizard_usb_qualification.v6",version5=version6||value?.schema==="rocell.wizard_usb_qualification.v5",version4=version5||value?.schema==="rocell.wizard_usb_qualification.v4",version3=version4||value?.schema==="rocell.wizard_usb_qualification.v3",version2=version3||value?.schema==="rocell.wizard_usb_qualification.v2",phaseActions=["physical_usb_qualification_begin","physical_usb_qualification_prepare","physical_usb_qualification_review","physical_usb_qualification_collect","physical_usb_identity_export",...(version3?usbAbsenceActions:[]),...(version4?[...usbReconnectActions,"physical_camera_refresh"]:[]),...(version5?usbRebootActions:[]),...(version6?usbCompleteActions:[])];
    if(!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","plan","next_action","export_receipt","meaning",...flags,...(version2?["baseline"]:[]),...(version3?["absence"]:[]),...(version4?["reconnect"]:[]),...(version5?["reboot"]:[]),...(version6?["complete"]:[])])||(!version2&&value.schema!=="rocell.wizard_usb_qualification.v1")||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!flags.every(k=>value[k]===false)||!v.string(value.meaning,1024)||!v.exact(value.publication,["status","operation_id"])||!["NOT_PUBLISHED","PENDING","CURRENT","HISTORICAL_HELD"].includes(value.publication.status)||!(value.publication.operation_id===null||v.identifier(value.publication.operation_id))||!["NOT_DECLARED","DECLARED","INCOMPLETE_HELD","HISTORICAL_HELD",...(version2?["BASELINE_ACTIVE","BASELINE_RETAINED_BLOCKED"]:[]),...(version3?["ABSENCE_ACTIVE","ABSENCE_RETAINED_BLOCKED"]:[]),...(version4?["RECONNECT_ACTIVE","RECONNECT_RETAINED_BLOCKED"]:[]),...(version5?["REBOOT_READY","REBOOT_ACTIVE","REBOOT_RETAINED_BLOCKED"]:[]),...(version6?["COMPLETE_REVIEW_READY",...usbCompleteStates]:[])].includes(value.status)||!(value.original_context===null||h.context(value.original_context))||!(value.next_action===null||value.next_action===action||(version2&&phaseActions.includes(value.next_action)))||!usbExportReceipt(value.export_receipt,value.source_sha256)||JSON.stringify(value).length>(version4?131072:65536))return null;
    const plan=value.plan,c=value.original_context;
    if(plan!==null){
      const hashes=["source_sha256","header_sha256","prerequisites_sha256","identity_entry_sha256","stage_policy_sha256","stage_catalog_sha256","stage_order_sha256"],b=plan.binding,r=plan.received_label;
      if(!v.exact(plan,["plan_sha256","binding","operator_id","launch_session_id","cable_label","port_label","received_label","phases"])||!v.digest(plan.plan_sha256)||!actor(plan.operator_id)||!h.launch(plan.launch_session_id)||!label(plan.cable_label,128)||!label(plan.port_label,128)||!v.exact(b,["trial_id","cell_id","session_id","origin_launch_id",...hashes])||typeof b.trial_id!=="string"||!/^usbtrial-[0-9a-f]{32}$/.test(b.trial_id)||!hashes.every(k=>v.digest(b[k]))||!v.identifier(b.cell_id)||!v.identifier(b.session_id)||!h.launch(b.origin_launch_id)||!v.exact(r,["manufacturer","product_id","serial","inspection_sha256"])||!v.digest(r.inspection_sha256)||!["manufacturer","product_id","serial"].every(k=>label(r[k],256))||!Array.isArray(plan.phases)||JSON.stringify(plan.phases)!==JSON.stringify(phases)||!c||Object.keys(c).some(k=>b[k]!==c[k]))return null;
    }
    if(version2&&!usbTrialBaselineValid(value.baseline,value))return null;
    if(version3&&!usbAbsenceValid(value.absence,value,version5))return null;
    if(version4&&!usbReconnectValid(value.reconnect,value,{historical:version5}))return null;
    if(version5&&!usbReconnectValid(value.reboot,value,{reboot:true,historical:version6}))return null;
    if(version6&&!usbCompleteValid(value))return null;
    if(version5&&value.publication.status!=="PENDING"&&(!value.plan||value.reconnect?.phase_record?.status!=="RECONNECT_OBSERVATIONS_RETAINED"))return null;
    if(value.next_action==="physical_camera_refresh"){
      const a=version5?value.reboot:value.reconnect;
      if(!version4||value.publication.status!=="HISTORICAL_HELD"||a?.state!=="PREPARATION_REQUESTED"||!a.operator_event||a.operator_event.launch_session_id!==value.launch_session_id||value.launch_session_id!==view.session_id||value.source_sha256!==view.source_binding_sha256||a.preparation!==null||a.acquisition_ledger?.entries.length!==3)return null;
    }
    if(value.publication.status==="PENDING")return plan===null&&value.next_action===null&&value.status==="NOT_DECLARED"&&(!version2||value.baseline===null)&&(!version3||value.absence===null)&&(!version4||value.reconnect===null)&&(!version5||value.reboot===null)&&(!version6||value.complete===null)?value:null;
    if(value.publication.status!=="CURRENT"&&value.next_action!==null&&!(version4&&value.publication.status==="HISTORICAL_HELD"&&["physical_usb_identity_export","physical_camera_refresh"].includes(value.next_action)))return null;
    if(value.publication.status==="HISTORICAL_HELD"&&value.status!=="HISTORICAL_HELD")return null;
    if((value.status==="DECLARED"&&plan===null)||(value.status==="NOT_DECLARED"&&plan!==null)||(!version2&&value.next_action!==null&&value.status!=="NOT_DECLARED"))return null;
    if(value.publication.status==="CURRENT"){
      const setup=p.setup(view.physical_camera_setup),b=setup?.session.binding,q=setup?.session.verification;
      if(!setup||setup.publication.status!=="CURRENT"||value.publication.operation_id===null||!q||value.source_sha256!==view.source_binding_sha256||value.source_sha256!==setup.source_sha256||value.launch_session_id!==view.session_id||value.launch_session_id!==setup.launch_session_id)return null;
      if(c===null?setup.prerequisites!==null:!setup.prerequisites||c.source_sha256!==value.source_sha256||c.session_id!==b.session_id||c.cell_id!==b.cell_id||c.origin_launch_id!==b.launch_id||c.header_sha256!==q.session.header_sha256||c.prerequisites_sha256!==setup.prerequisites.evidence_sha256)return null;
      if(plan&&(setup.session.stages.slice(0,3).some(row=>row.state!=="PASS")||(value.status==="DECLARED"&&setup.session.stages[3].state!=="REVIEW_PENDING")))return null;
      if(version6&&!usbCompleteValid(value,setup.session.stages))return null;
    }
    return value;
  }

  function usbQualification(){
    const box=element("section","usb-qualification");box.append(heading("USB reconnect / reboot trial — original phases"));
    const input=state.view.usb_qualification,value=usbQualificationProjection(input,state.view);
    if(!value){box.append(element("p","caption",input==null?"No trial declaration is included in this older snapshot.":"USB_QUALIFICATION_NOT_VERIFIED: Unsupported or inconsistent original declaration; no qualification is inferred."));return box;}
    box.append(facts({status:value.status,publication:value.publication.status,source_sha256:value.source_sha256,current_launch:value.launch_session_id}),element("p","notice warning",value.meaning));
    if(value.publication.status==="PENDING"){box.append(element("p","notice warning",["rocell.wizard_usb_qualification.v2","rocell.wizard_usb_qualification.v3","rocell.wizard_usb_qualification.v4","rocell.wizard_usb_qualification.v5","rocell.wizard_usb_qualification.v6"].includes(value.schema)?"Original phase publication pending; plan and observation details are withheld until original readback and the completion log.":"Declaration publication pending; plan details are withheld until original readback and the completion log."));return box;}
    if(value.publication.status!=="CURRENT")box.append(element("p","notice warning","HISTORICAL ONLY: This declaration does not restore a permit or trigger any acquisition."));
    const plan=value.plan;
    if(plan){box.append(facts({trial_id:plan.binding.trial_id,plan_sha256:plan.plan_sha256,original_launch:plan.binding.origin_launch_id,declaring_launch:plan.launch_session_id}),element("p","",`Operator label: ${plan.operator_id}`),element("p","",`Declared cable: ${plan.cable_label}`),element("p","",`Declared host port: ${plan.port_label}`));for(const k of ["manufacturer","product_id","serial"])box.append(element("p","",`Original received ${k}: ${plan.received_label[k]}`));for(const phase of plan.phases)box.append(element("p","",`${phase}: ${phase==="BASELINE"&&value.baseline?value.baseline.state:phase==="RECONNECT_ABSENCE"&&value.absence?value.absence.state:phase==="AFTER_RECONNECT"&&value.reconnect?value.reconnect.state:phase==="AFTER_REBOOT"&&value.reboot?value.reboot.state:"NOT ACQUIRED — required future phase, not evidence."}`));}
    if(value.baseline){const b=value.baseline;
      box.append(facts({phase_id:b.phase_id,state:b.state,original_phase_start:b.phase_start_event_sha256}),element("p","notice warning","Acquisition rows are published only after exact result retention and completion logging. Refresh the original session after fresh metadata review; timestamps are not device attestation."));
      for(const [role] of [["GENERIC_INVENTORY"],["NATIVE_INVENTORY"],["NATIVE_IDENTITY"]]){const row=b.acquisition_ledger?.entries.find(r=>r.role===role);box.append(element("p","",`${role}: ${row?"LOGGED IN THIS PHASE — "+row.operation_id:"NOT ACQUIRED IN THIS PHASE"}`));}
      if(b.target)box.append(facts(b.target));
      if(b.preparation)box.append(element("p","",`Prepared by ${b.preparation.operator_id}; original preparation ${b.preparation.preparation_sha256}`));
      if(b.review)box.append(element("p","",`Reviewed by ${b.review.reviewer_id}; boot request ${b.review.boot_request_sha256}. Labels are not authenticated independent people.`));
      if(b.host_boot)box.append(facts({host_boot_status:b.host_boot.status,original_state:b.host_boot.original_state,last_boot_up_time_utc:b.host_boot.last_boot_up_time_utc??"UNKNOWN",host_key_sha256:b.host_boot.host_key_sha256,boot_key_sha256:b.host_boot.boot_key_sha256,process_status:b.host_boot.process_status,tree_exit_confirmed:b.host_boot.tree_exit_confirmed}),element("p","",`Boot origin: ${b.host_boot.origin}`),element("p","caption","LastBootUpTime is provider-reported, not attestation. A new app launch is not a reboot."));
      if(b.host_boot&&(b.host_boot.blockers.length||["BOOT_HELD","BOOT_UNCERTAIN"].includes(b.host_boot.original_state))){for(const blocker of b.host_boot.blockers)box.append(element("p","notice warning",`Host-boot hold: ${blocker}`));box.append(element("p","notice warning","Export the retained host-boot request, process diagnostics and original events. USB collection did not follow an unconfirmed boot result; do not retry or infer a reboot from this launch."));}
      if(b.execution)box.append(facts({usb_status:b.execution.status,provenance:b.execution.provenance,counter_coverage:b.execution.counter_coverage,hub_open_attempts:b.execution.actual_counts?.hub_open_attempts??"UNKNOWN",process_cleanup_confirmed:b.execution.process_cleanup_confirmed,usb_cleanup_confirmed:b.execution.usb_cleanup_confirmed,error:b.execution.error??"NONE"}));
      if(b.observation)box.append(facts({...b.observation,serial_values:b.observation.serial_values.join(", ")||"NOT OBSERVED"}));
      for(const note of usbInvestigation(b.execution,b.observation))box.append(element("p","notice warning",note));
      if(b.phase_record)for(const row of b.phase_record.checks)box.append(element("p","",`${row.check_id}: ${row.passed?"OBSERVED CHECK ONLY":"NOT ESTABLISHED"}`));
    }
    if(value.absence){const a=value.absence;box.append(heading("RECONNECT_ABSENCE — exact physical USB node"),facts({phase_id:a.phase_id,state:a.state,phase_start:a.phase_start_event_sha256}),element("p","notice warning","The unplug report is not proof of mechanical cause or continuous absence. No live camera endpoint is selected after unplugging. Stop is software cancellation, not a robot emergency stop."));
      if(a.target)box.append(heading("Original literal target and device filter"),facts(a.target));
      if(a.operator_event)box.append(element("p","",`Unplug reported by ${a.operator_event.operator_id}; original ${a.operator_event.evidence_sha256}`));
      if(a.preparation)box.append(facts(a.preparation));
      if(a.boot_review)box.append(heading("Separate local host-boot review"),facts(a.boot_review));
      if(a.host_boot){box.append(heading("Original host-boot observation and baseline relation"),facts(a.host_boot),element("p","caption","LastBootUpTime is provider-reported, not attestation. A new application launch is not a reboot; changed boot during unplugging is a hold."));for(const issue of a.host_boot.blockers)box.append(element("p","notice warning",`Host-boot hold: ${issue}`));if(a.host_boot.original_state!=="BOOT_RETAINED")box.append(element("p","notice warning","Presence query did not follow this held/uncertain boot. Export the original intent, report and events; do not retry."));}
      if(a.runtime_review)box.append(heading("Final exact presence review — review does not itself query"),facts(a.runtime_review));
      if(a.execution){const e=a.execution;box.append(heading("Owned physical-node query — not USB hub opens"),facts({status:e.status,provenance:e.provenance,counter_coverage:e.counter_coverage,api_calls:e.actual_counts?.api_calls??"UNKNOWN",device_handle_opens:e.actual_counts?.device_handle_opens??"UNKNOWN",configuration_writes:e.actual_counts?.configuration_writes??"UNKNOWN",frames:e.actual_counts?.frames??"UNKNOWN",process_cleanup_confirmed:e.process_cleanup_confirmed,native_cleanup_confirmed:e.native_cleanup_confirmed,error:e.error??"NONE"}));if(!e.process_cleanup_confirmed||!e.native_cleanup_confirmed||e.counter_coverage==="NOT_REPORTED")box.append(element("p","notice warning","Unknown or unconfirmed effects remain held. Export the original campaign and process evidence; never replay this request."));}
      else if(["QUERY_REQUESTED","ORIGINAL_CAMPAIGN_HELD"].includes(a.state)||(a.state==="INCOMPLETE"&&a.runtime_review!==null)){box.append(heading("Physical-node query evidence unavailable"),facts({counter_coverage:"NOT_REPORTED",api_calls:"UNKNOWN",device_handle_opens:"UNKNOWN",configuration_writes:"UNKNOWN",frames:"UNKNOWN"}),element("p","notice warning","No owned execution evidence is available for this retained request or partial attempt. Do not infer that the query did not run or that effects were zero. Export the original campaign and terminal reasons; do not replay this request."));}
      if(a.observation)box.append(facts(a.observation));
      if(a.phase_record){box.append(facts({absence_phase_status:a.phase_record.status,physical_node_absence_observed:a.phase_record.physical_node_absence_observed,boot_relation:a.phase_record.boot_relation}));for(const check of a.phase_record.checks)box.append(element("p","",`${check.check_id}: ${check.passed?"OBSERVED CHECK ONLY":"NOT ESTABLISHED"}`));}
      box.append(element("p","notice warning","ABSENT means two complete request-bound physical-node samples only. An absence result does not replace AFTER_RECONNECT or AFTER_REBOOT; no qualification PASS or capture/arm release follows this phase."));
    }
    for(const [phase,a] of [["AFTER_RECONNECT",value.reconnect],["AFTER_REBOOT",value.reboot]]){if(!a)continue;const reboot=phase==="AFTER_REBOOT";box.append(heading(phase+" — retained original interval"),facts({phase_id:a.phase_id,state:a.state,phase_start:a.phase_start_event_sha256}),element("p","notice warning",reboot?"The restart report is an operator statement, not reboot proof. This interval requires its own three logged metadata acquisitions and one separately owned boot observation.":"The reconnect report is an operator statement, not mechanical proof. All three metadata acquisitions must be logged after this report; a new app launch cannot renew or rebind this interval."));
      for(const key of ["operator_event","target","preparation","review"])if(a[key])box.append(heading(key.replaceAll("_"," ")),facts(a[key]));
      const rows=a.acquisition_ledger?.entries||[];for(const role of ["GENERIC_INVENTORY","NATIVE_INVENTORY","NATIVE_IDENTITY"]){const row=rows.find(r=>r.role===role);box.append(element("p","",`${role}: ${row?"LOGGED AFTER "+(reboot?"RESTART":"RECONNECT")+" REPORT — "+row.operation_id:"NOT ACQUIRED AFTER THIS REPORT"}`));}
      if(a.host_boot){box.append(heading("Separately owned "+(reboot?"reboot":"reconnect")+" boot observation"),facts(a.host_boot),element("p","caption",reboot?"LastBootUpTime is provider-reported, not attestation. Reboot requires the same host, a different boot, and a reported boot epoch after reconnect completion and no later than Begin. No USB query runs automatically.":"LastBootUpTime is provider-reported, not attestation. Reconnect requires the same host and boot as absence; this boot action does not automatically query USB."));for(const issue of a.host_boot.blockers)box.append(element("p","notice warning",`Host-boot hold: ${issue}`));if(a.host_boot.original_state!=="BOOT_RETAINED")box.append(element("p","notice warning","No descriptor query follows this held or uncertain boot. Export the original intent, report and events; do not retry."));}
      if(a.execution){const e=a.execution;box.append(heading("Owned "+(reboot?"reboot":"reconnect")+" descriptor query"),facts({status:e.status,provenance:e.provenance,counter_coverage:e.counter_coverage,hub_open_attempts:e.actual_counts?.hub_open_attempts??"UNKNOWN",process_cleanup_confirmed:e.process_cleanup_confirmed,usb_cleanup_confirmed:e.usb_cleanup_confirmed,error:e.error??"NONE"}));}
      else if(["QUERY_REQUESTED","ORIGINAL_CAMPAIGN_HELD"].includes(a.state)||(a.state==="INCOMPLETE"&&a.review!==null))box.append(element("p","notice warning","Descriptor query evidence unavailable: counter_coverage NOT_REPORTED; hub opens UNKNOWN. Do not infer no query or zero effects. Export original campaign reasons; never replay this request."));
      if(a.observation)box.append(facts({...a.observation,serial_values:a.observation.serial_values.join(" | ")||"NOT OBSERVED"}));
      for(const note of usbInvestigation(a.execution,a.observation))box.append(element("p","notice warning",note));
      if(a.phase_record){const f=a.phase_record;box.append(heading(reboot?"Original baseline / reconnect / reboot comparison — not qualification":"Original unit / reconnect comparison — not qualification"),facts({phase_sha256:f.phase_sha256,status:f.status,boot_relation:f.boot_relation}));for(const row of f.comparisons){const item=f.values[row.field];box.append(element("p","",`${row.field}: ${item.status==="VALUE_RETAINED"?JSON.stringify(item.value):item.status} / ${row.status}`),element("p","caption",`Original value SHA: ${item.sha256??"NOT OBSERVED"}`));}for(const check of f.checks)box.append(element("p","",`${check.check_id}: ${check.passed?"OBSERVED CHECK ONLY":"NOT ESTABLISHED"}`));}
      box.append(element("p","notice warning",reboot?"Four phase records alone are not stage PASS or camera capture/arm release. See the separate final identity review below when present. Stop is software cancellation, not a robot E-stop.":"Reconnection alone does not complete AFTER_REBOOT or independent final qualification. No reconnect result is stage PASS or capture/arm release. Reopened or uncertain work is export-only. Stop is software cancellation, not a robot E-stop."));
    }
    if(value.schema==="rocell.wizard_usb_qualification.v6"){
      box.append(heading("Final camera-identity review — files only"));
      const c=value.complete;
      if(!c)box.append(element("p","","All four original phases are available for explicit assessment. No assessment or acceptance has been recorded."));
      else {
        box.append(facts({series_id:c.series_id,state:c.state,series_sha256:c.series_sha256,assessment_sha256:c.assessment_sha256,review_sha256:c.review_sha256}));
        if(c.assessment){box.append(element("p","","Assessment: "+c.assessment.verdict));for(const issue of c.assessment.missing_requirements)box.append(element("p","notice warning","NOT ESTABLISHED: "+issue));}
        if(c.review)box.append(facts(c.review));
        box.append(element("p","notice warning","A retained review file is not a committed PASS. Partial evidence is export-only; do not replay the action."));
      }
      box.append(element("p","notice warning","Identity acceptance does not authorize camera capture, arm access, power, motion or contact. Reviewer labels do not authenticate independent people."));
    }
    box.append(element("p","notice warning","A new app launch is not a reboot. The standalone legacy baseline cannot fill a declared trial phase. Manual disconnect/reconnect and Windows Restart are not performed automatically; declaration grants no phase or capture release."));
    if(value.export_receipt)box.append(element("p","",`Separate original USB export: ${value.export_receipt.path}`),element("p","",`Manifest SHA-256: ${value.export_receipt.manifest_sha256}`));return box;
  }

  function usbExecutionValid(e,o){
    const {v}=receivedCameraValidators(),nullable=(x,check)=>x===null||check(x),code=x=>typeof x==="string"&&/^[A-Za-z0-9_:-]{1,128}$/.test(x);
    if(e!==null){
      const names=["api_calls","hub_open_attempts","hub_open_successes","ioctl_attempts","ioctl_successes","descriptor_requests","close_attempts","close_successes","peak_open_handles","remaining_open_handles","returned_bytes"];
      if(!v.exact(e,["schema","evidence_sha256","preparation_sha256","status","provenance","released","no_attempt","counter_coverage","actual_counts","process_cleanup_confirmed","usb_cleanup_confirmed","error","cleanup_errors","physical_authority","hardware_qualified","retries"])||e.schema!=="rocell.owned_usb_identity_run_summary.v1"||!["evidence_sha256","preparation_sha256"].every(k=>v.digest(e[k]))||!["OBSERVED","HELD","FAILED","CANCELLED","TIMED_OUT","CLEANUP_UNCERTAIN"].includes(e.status)||!["PHYSICAL_USB_QUERY","INCAPABLE_USB_QUERY"].includes(e.provenance)||!["released","no_attempt","process_cleanup_confirmed","usb_cleanup_confirmed"].every(k=>typeof e[k]==="boolean")||!nullable(e.error,code)||!Array.isArray(e.cleanup_errors)||e.cleanup_errors.length>16||!e.cleanup_errors.every(code)||e.physical_authority!==false||e.hardware_qualified!==false||e.retries!==0)return false;
      const c=e.actual_counts;
      if(e.counter_coverage==="NOT_REPORTED"){if(c!==null||e.no_attempt||e.usb_cleanup_confirmed)return false;}
      else if(["NATIVE_RECEIPT","NO_PROCESS_CREATED"].includes(e.counter_coverage)){
        if(!v.exact(c,names)||!names.every(k=>v.integer(c[k],0,524288))||c.hub_open_attempts>32||c.close_attempts>32||c.hub_open_successes>c.hub_open_attempts||c.close_successes>c.close_attempts)return false;
        if(e.counter_coverage==="NO_PROCESS_CREATED"?(!e.no_attempt||e.released||Object.values(c).some(n=>n!==0)||e.usb_cleanup_confirmed):e.no_attempt)return false;
        if(e.counter_coverage==="NATIVE_RECEIPT"&&e.usb_cleanup_confirmed!==(c.remaining_open_handles===0&&c.hub_open_successes===c.close_successes&&c.close_successes===c.close_attempts))return false;
      }else return false;
      if(e.status==="OBSERVED"&&(!e.released||e.counter_coverage!=="NATIVE_RECEIPT"||!e.process_cleanup_confirmed||!e.usb_cleanup_confirmed||e.error!==null||e.cleanup_errors.length))return false;
    }
    if(o!==null&&(!e||e.counter_coverage!=="NATIVE_RECEIPT"||!v.exact(o,["outcome","serial_values","vid","pid","bcd_usb","i_serial_number","physical_usb_instance_id","host_controller_instance_id","hub_port","ex_speed","ex_v2_available","operating_at_superspeed","operating_at_superspeed_plus"])||!["OBSERVED","HELD"].includes(o.outcome)||!Array.isArray(o.serial_values)||o.serial_values.length>4||!o.serial_values.every(x=>v.string(x,508)&&x.length<=127)||!["vid","pid"].every(k=>nullable(o[k],x=>typeof x==="string"&&/^[0-9a-f]{4}$/.test(x)))||!nullable(o.bcd_usb,n=>v.integer(n,0,65535))||!nullable(o.i_serial_number,n=>v.integer(n,0,255))||!["physical_usb_instance_id","host_controller_instance_id"].every(k=>nullable(o[k],x=>v.string(x,4096)))||!nullable(o.hub_port,n=>v.integer(n,1,255))||!nullable(o.ex_speed,n=>v.integer(n,0,3))||typeof o.ex_v2_available!=="boolean"||!["operating_at_superspeed","operating_at_superspeed_plus"].every(k=>nullable(o[k],x=>typeof x==="boolean"))||(!o.ex_v2_available&&(o.operating_at_superspeed!==null||o.operating_at_superspeed_plus!==null))))return false;
    return true;
  }

  function usbIdentityProjection(value,view) {
    const h=receivedCameraValidators(),{v,p}=h;
    const flags=["physical_authority","hardware_qualified","camera_capture_authorized","arm_access_authorized"];
    const statuses=["NOT_STARTED","AWAITING_INSPECTION","AWAITING_REVIEW","READY_TO_QUERY","OBSERVED_UNQUALIFIED","HELD","INCOMPLETE_HELD","HISTORICAL_HELD"];
    const actions=["physical_usb_identity_inspect","physical_usb_identity_review","physical_usb_identity_collect","physical_usb_identity_export"];
    const summaries=["inspection","review","execution","observation"];
    const publication=x=>v.exact(x,["status","operation_id"])&&["NOT_PUBLISHED","PENDING","CURRENT","HISTORICAL_HELD"].includes(x.status)&&(x.operation_id===null||v.identifier(x.operation_id));
    const code=x=>typeof x==="string"&&/^[A-Za-z0-9_:-]{1,128}$/.test(x);
    const nullable=(x,check)=>x===null||check(x);
    const usbId=x=>typeof x==="string"&&/^usbidentity-[0-9a-f]{32}$/.test(x);
    const usbActor=x=>typeof x==="string"&&/^[\x20-\x7e]{1,64}$/.test(x)&&x.trim()===x;
    const pointer=value?.schema==="rocell.wizard_usb_identity_export_pointer.v1";
    const common=["schema","source_sha256","launch_session_id","original_context","publication","status","usb_id","export_receipt","meaning"];
    if(!v.exact(value,[...common,...(pointer?["coverage","separate_metadata_export_required","original_documents_included","physical_authority"]:["stage_states",...summaries,"next_action",...flags])])||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!nullable(value.original_context,h.context)||!publication(value.publication)||!statuses.includes(value.status)||!nullable(value.usb_id,usbId)||!v.string(value.meaning,512)||JSON.stringify(value).length>98304)return null;
    if(pointer?(value.separate_metadata_export_required!==true||value.original_documents_included!==false||value.physical_authority!==false||!v.exact(value.coverage,summaries)):(value.schema!=="rocell.wizard_usb_identity.v1"||!flags.every(k=>value[k]===false)||!nullable(value.next_action,x=>actions.includes(x))))return null;
    const data=pointer?value.coverage:value,i=data.inspection,r=data.review,e=data.execution,o=data.observation;
    if(i!==null&&(!v.exact(i,["evidence_sha256","operator_id","collection_launch_id","policy_sha256","operation_sha256","runtime_registration_sha256","helper_sha256","files_verified","target"])||!["evidence_sha256","policy_sha256","operation_sha256","runtime_registration_sha256","helper_sha256"].every(k=>v.digest(i[k]))||!usbActor(i.operator_id)||!h.launch(i.collection_launch_id)||i.files_verified!==20||!v.exact(i.target,["selection_sha256","native_identity_sha256","endpoint_sha256","symbolic_link","device_instance_id"])||!["selection_sha256","native_identity_sha256","endpoint_sha256"].every(k=>v.digest(i.target[k]))||!["symbolic_link","device_instance_id"].every(k=>v.string(i.target[k],4096))))return null;
    if(r!==null&&(!i||!v.exact(r,["policy_review_sha256","runtime_review_sha256","identity_sha256","reviewer_id","review_launch_id"])||!["policy_review_sha256","runtime_review_sha256","identity_sha256"].every(k=>v.digest(r[k]))||!usbActor(r.reviewer_id)||r.reviewer_id.toLowerCase()===i.operator_id.toLowerCase()||!h.launch(r.review_launch_id)))return null;
    if((e!==null&&r===null)||!usbExecutionValid(e,o))return null;
    const receipt=value.export_receipt;
    if(pointer){if(receipt!==null&&(!v.exact(receipt,["path","export_id","manifest_sha256"])||!v.string(receipt.path,16384)||!v.identifier(receipt.export_id)||!v.digest(receipt.manifest_sha256)))return null;return value;}
    if(receipt!==null){const q=receipt.provenance,fixed=["README.md","report.json","events.jsonl","manifest.json"];
      if(!v.exact(receipt,["status","valid","path","export_root","export_id","files","total_bytes","manifest_sha256","physical_authority","provenance","limitations"])||receipt.status!=="EXPORTED_DIAGNOSTICS"||receipt.valid!==true||receipt.physical_authority!=="NONE"||!["path","export_root"].every(k=>v.string(receipt[k],16384))||!v.identifier(receipt.export_id)||!v.digest(receipt.manifest_sha256)||!v.integer(receipt.total_bytes,1,8388608)||!v.exact(q,["session_id","mode","source_binding_sha256","source_identity","software_version"])||!v.identifier(q.session_id)||q.mode!=="PHYSICAL_DIAGNOSTIC"||q.source_binding_sha256!==value.source_sha256||!v.exact(q.source_identity,["source_sha256"])||q.source_identity.source_sha256!==value.source_sha256||!v.string(q.software_version,64)||!Array.isArray(receipt.limitations)||receipt.limitations.length>16||!receipt.limitations.every(x=>v.string(x,1024))||!Array.isArray(receipt.files)||receipt.files.length<5||receipt.files.length>12||!receipt.files.every(f=>v.exact(f,["name","bytes","sha256"])&&v.string(f.name,128)&&v.integer(f.bytes,f.name==="events.jsonl"?0:1,1048576)&&v.digest(f.sha256)))return null;
      const names=receipt.files.map(f=>f.name),parts=names.filter(n=>!fixed.includes(n)).sort();
      if(new Set(names).size!==names.length||fixed.some(n=>!names.includes(n))||parts.length<1||parts.length>8||parts.some((n,j)=>n!==`attachment-usb-identity-part-${String(j+1).padStart(2,"0")}.json`)||receipt.files.reduce((n,f)=>n+f.bytes,0)!==receipt.total_bytes)return null;
    }
    const stageNames=["workspace_sources","static_camera_contract","camera_receipt","camera_identity"],stageStates=["PENDING","WAITING_OPERATOR","REVIEW_PENDING","PASS","BLOCKED","INVALIDATED","INCIDENT_HOLD","SIDE_EFFECT_UNCERTAIN","COMPLETE_DIAGNOSTIC"],s=value.stage_states;
    if(s!==null&&(!v.exact(s,stageNames)||!Object.values(s).every(x=>stageStates.includes(x))))return null;
    if(value.publication.status==="PENDING")return summaries.every(k=>value[k]===null)&&value.next_action===null&&["NOT_STARTED","HISTORICAL_HELD"].includes(value.status)?value:null;
    if(value.publication.status!=="CURRENT"&&value.next_action!==null)return null;
    if(value.publication.status==="HISTORICAL_HELD"&&value.status!=="HISTORICAL_HELD")return null;
    if(value.publication.status==="CURRENT"){
      const setup=p.setup(view.physical_camera_setup),b=setup?.session.binding,q=setup?.session.verification,c=value.original_context;
      if(!setup||setup.publication.status!=="CURRENT"||!q||!s||value.publication.operation_id===null||value.source_sha256!==view.source_binding_sha256||value.source_sha256!==setup.source_sha256||value.launch_session_id!==view.session_id||value.launch_session_id!==setup.launch_session_id||stageNames.some((k,j)=>s[k]!==setup.session.stages[j].state))return null;
      if(c===null?setup.prerequisites!==null:!setup.prerequisites||c.source_sha256!==value.source_sha256||c.session_id!==b.session_id||c.cell_id!==b.cell_id||c.origin_launch_id!==b.launch_id||c.header_sha256!==q.session.header_sha256||c.prerequisites_sha256!==setup.prerequisites.evidence_sha256)return null;
      if((i||r||e||o)&&(!c||value.usb_id===null||stageNames.slice(0,3).some(k=>s[k]!=="PASS")||s.camera_identity==="PASS"))return null;
      if((value.status==="AWAITING_REVIEW"&&(!i||r))||(value.status==="READY_TO_QUERY"&&(!r||e))||(value.status==="OBSERVED_UNQUALIFIED"&&(e?.status!=="OBSERVED"||o?.outcome!=="OBSERVED")))return null;
    }
    return value;
  }

  function usbInvestigation(execution,observation){
    const notes=[];
    if(execution&&(!execution.process_cleanup_confirmed||execution.counter_coverage==="NOT_REPORTED"||(execution.counter_coverage==="NATIVE_RECEIPT"&&!execution.usb_cleanup_confirmed)))notes.push("Cleanup or effect accounting is uncertain. Do not retry or assume the device is closed. Export the retained original process/USB evidence and investigate both cleanup records before any new attempt.");
    if(execution&&/SOURCE|CONTEXT|TARGET|IDENTITY|PIN|FILE|RUNTIME/.test(execution.error||""))notes.push("Compare the retained source, runtime pins and exact target with the original reviewed subject. Changed files or selection require a new explicitly eligible inspection/review; never substitute a target or replay the consumed operation.");
    if(execution&&["CANCELLED","TIMED_OUT"].includes(execution.status))notes.push("The original Stop/deadline remains part of this attempt. Inspect and export its retained outcome; restarting the app does not renew its budget or authorize retry.");
    if(observation&&observation.operating_at_superspeed!==true&&observation.operating_at_superspeed_plus!==true)notes.push("USB3 operation is not established by these observations. Review the exact V2 operating flags and physical USB path; advertised capability or EX speed cannot fill this gap.");
    return notes;
  }

  function usbIdentity(){
    const box=element("section","usb-identity");box.append(heading("USB identity — one original baseline"),element("p","notice warning","Fixed-file inspection and review do not query USB. Collection is a separate, explicitly confirmed device query: no camera capture, arm access, power, motion or contact. Baseline evidence alone is not reconnect/reboot qualification."));
    const input=state.view.usb_identity,value=usbIdentityProjection(input,state.view);
    if(!value){box.append(element("p","caption",input==null?"No USB baseline workflow is available in this snapshot.":"USB_IDENTITY_NOT_VERIFIED: Unsupported or inconsistent cached context; no query or qualification is inferred."));return box;}
    box.append(facts({status:value.status,publication:value.publication.status,source_sha256:value.source_sha256,current_launch:value.launch_session_id}),element("p","caption",value.meaning));
    if(value.publication.status==="PENDING"){box.append(element("p","notice warning","USB publication pending: new target, review and query observations are withheld until original retention and completion logging."));return box;}
    const pointer=value.schema==="rocell.wizard_usb_identity_export_pointer.v1",data=pointer?value.coverage:value;
    if(pointer)box.append(element("p","notice warning","General export coverage only — full original USB evidence requires the separate metadata bundle."));
    if(value.publication.status!=="CURRENT")box.append(element("p","notice warning","HISTORICAL ONLY: Original target and USB observations are not a current connection. Reopen/refresh does not query, restore a consumed grant or replay this attempt."));
    if(value.original_context)box.append(heading("Original store context"),facts(value.original_context));
    if(data.inspection){const i=data.inspection;box.append(heading("Fixed files and exact target"),element("p","",`Operator label: ${i.operator_id}`),element("p","",`Endpoint symbolic link: ${i.target.symbolic_link}`),element("p","",`Device instance ID: ${i.target.device_instance_id}`),facts({files_verified:i.files_verified,inspection_sha256:i.evidence_sha256,policy_sha256:i.policy_sha256,operation_sha256:i.operation_sha256,runtime_registration_sha256:i.runtime_registration_sha256,helper_sha256:i.helper_sha256}));}
    if(data.review)box.append(heading("Exact policy/runtime review"),element("p","",`Reviewer label: ${data.review.reviewer_id}`),element("p","caption","Distinct procedural labels are not authenticated independent people; file review is not hardware qualification."));
    if(data.execution){const e=data.execution;box.append(heading("Owned query outcome and cleanup"),facts({status:e.status,provenance:e.provenance,counter_coverage:e.counter_coverage,released:e.released,no_attempt:e.no_attempt,process_cleanup_confirmed:e.process_cleanup_confirmed,usb_cleanup_confirmed:e.usb_cleanup_confirmed,error:e.error}));if(e.provenance==="INCAPABLE_USB_QUERY")box.append(element("p","notice warning","INCAPABLE / MODELED USB OBSERVATIONS — no received hardware was queried."));if(e.actual_counts===null)box.append(element("p","notice warning","Actual USB counts: NOT REPORTED / UNKNOWN. They are not zero; cleanup cannot be inferred from process exit."));else box.append(facts(e.actual_counts));for(const error of e.cleanup_errors)box.append(element("p","notice warning",error));}
    if(data.observation){const o=data.observation;box.append(heading("Literal retained USB values — not inferred identity"));for(const key of ["outcome","vid","pid","bcd_usb","i_serial_number","physical_usb_instance_id","host_controller_instance_id","hub_port","ex_speed","ex_v2_available","operating_at_superspeed","operating_at_superspeed_plus"])box.append(element("p","",`${key}: ${o[key]===null?"NOT OBSERVED":String(o[key])}`));box.append(element("p","",`Descriptor serial values: ${o.serial_values.length?o.serial_values.join(" | "):"NOT OBSERVED"}`),element("p","caption","Only the independent V2 operating flags describe SuperSpeed operation. EX speed and capability are not substituted; no nominal Mbps or serial number is inferred."));}
    for(const note of usbInvestigation(data.execution,data.observation))box.append(element("p","notice warning",note));
    if(value.export_receipt)box.append(element("p","",`Separate USB export: ${value.export_receipt.path}`),element("p","",`Manifest SHA-256: ${value.export_receipt.manifest_sha256}`));
    box.append(element("p","notice warning","One-shot attempt. Stop cannot undo completed device queries or committed evidence; await cleanup and export held evidence. No automatic retry. Physical absence, reconnect and actual same-host reboot qualification are still separate missing work; a new app launch is not a reboot."));return box;
  }

  function cameraIdentityProjection(value,view) {
    const h=receivedCameraValidators(),{v,p}=h;
    const flags=["physical_authority","hardware_qualified","native_release_allowed","device_io_performed"], roleFlags=[...flags,"measurement_truth_verified","authenticated_operator_identity"];
    const roles=["metadata","helper","receipt","assessment","review"], actions=["physical_camera_identity_submit","physical_camera_identity_review","physical_camera_identity_export"];
    const statuses=["NOT_STARTED","WAITING_METADATA","REVIEW_PENDING","REVIEWED_BLOCKED","INCOMPLETE_HELD","HISTORICAL_HELD"], cycleStates=["INCOMPLETE","ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING","REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_BLOCKED"];
    const publication=x=>v.exact(x,["status","operation_id"])&&["NOT_PUBLISHED","PENDING","CURRENT","HISTORICAL_HELD"].includes(x.status)&&(x.operation_id===null||v.identifier(x.operation_id));
    const id=x=>typeof x==="string"&&/^cameraidentity-[0-9a-f]{32}$/.test(x);
    const codes=(x,max)=>Array.isArray(x)&&x.length<=max&&x.every(k=>typeof k==="string"&&/^[A-Z][A-Z0-9_]{0,127}$/.test(k))&&new Set(x).size===x.length;
    const compactExport=x=>x===null||(v.exact(x,["path","export_id","manifest_sha256"])&&v.string(x.path,16384)&&v.identifier(x.export_id)&&v.digest(x.manifest_sha256));
    if(value?.schema==="rocell.wizard_camera_identity_export_pointer.v1") {
      if(!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","cycles","export_receipt","separate_metadata_export_required","original_documents_included","physical_authority","meaning"])||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!(value.original_context===null||h.context(value.original_context))||!publication(value.publication)||!statuses.includes(value.status)||!compactExport(value.export_receipt)||value.separate_metadata_export_required!==true||value.original_documents_included!==false||value.physical_authority!==false||!v.string(value.meaning,512)||!Array.isArray(value.cycles)||value.cycles.length>4)return null;
      return value.cycles.every((c,i)=>v.exact(c,["identity_id","sequence","state",...roles.map(r=>r+"_sha256")])&&id(c.identity_id)&&c.sequence===i+1&&cycleStates.includes(c.state)&&roles.every(r=>c[r+"_sha256"]===null||v.digest(c[r+"_sha256"])))?value:null;
    }
    if(!v.exact(value,["schema","source_sha256","launch_session_id","original_context","publication","status","stage_states","cycles","identity_entry","next_action","export_receipt","meaning",...flags])||value.schema!=="rocell.wizard_camera_identity_onboarding.v1"||!v.digest(value.source_sha256)||!h.launch(value.launch_session_id)||!flags.every(k=>value[k]===false)||!v.string(value.meaning,512)||!publication(value.publication)||!statuses.includes(value.status)||!(value.next_action===null||actions.includes(value.next_action))||!(value.identity_entry===null||v.digest(value.identity_entry))||!(value.original_context===null||h.context(value.original_context))||!Array.isArray(value.cycles)||value.cycles.length>4||JSON.stringify(value).length>131072)return null;
    const s=value.stage_states,stageNames=["workspace_sources","static_camera_contract","camera_receipt","camera_identity"],stageStates=["PENDING","WAITING_OPERATOR","REVIEW_PENDING","PASS","BLOCKED","INVALIDATED","INCIDENT_HOLD","SIDE_EFFECT_UNCERTAIN","COMPLETE_DIAGNOSTIC"];
    if(s!==null&&(!v.exact(s,stageNames)||!Object.values(s).every(x=>stageStates.includes(x))))return null;
    const minimumMissing=["USB_DESCRIPTOR_SERIAL_PROVENANCE_REQUIRED","USB_OPERATING_TOPOLOGY_AND_SPEED_REQUIRED","RECONNECT_AND_REBOOT_IDENTITY_EVIDENCE_REQUIRED","RECEIVED_LABEL_USB_CORRELATION_REQUIRED"];
    const missingRoster=[...minimumMissing,"ENDPOINT_METADATA_REVIEW_HELD","EXACT_DEVNODE_DRIVER_PROPERTIES_REQUIRED","GENERIC_NATIVE_DRIVER_SERVICE_CORRELATION_REQUIRED","INT018_OBSERVATION_NOT_RECORDED"];
    for(const [index,c] of value.cycles.entries()) {
      if(!v.exact(c,["identity_id","sequence","state",...roles])||!id(c.identity_id)||c.sequence!==index+1||!cycleStates.includes(c.state)||(index<value.cycles.length-1&&c.state!=="REVIEWED_BLOCKED"))return null;
      let gap=false;
      for(const role of roles){const r=c[role];if(r===null){gap=true;continue;}
        if(gap||!v.exact(r,["schema","sha256","identity_id","sequence","verdict","meaning",...roleFlags,...(role==="assessment"?["checks","missing_requirements"]:[])])||r.schema!==`rocell.camera_identity_${role}.v1`||!v.digest(r.sha256)||r.identity_id!==c.identity_id||r.sequence!==c.sequence||r.verdict!==(["assessment","review"].includes(role)?"BLOCKED":null)||!v.string(r.meaning,512)||!roleFlags.every(k=>r[k]===false))return null;
      }
      const a=c.assessment;
      if(a){const checks=a.checks,names=["provider","service","version","inf_path"];
        if(!v.exact(checks,["received_serial_reported_match","endpoint_selection_available","native_review_blockers","driver_protocol_schema","exact_devnode_driver_observed","driver_field_availability","generic_driver_service_matches","operator_observation_state"])||!["received_serial_reported_match","endpoint_selection_available","exact_devnode_driver_observed","generic_driver_service_matches"].every(k=>typeof checks[k]==="boolean")||!codes(checks.native_review_blockers,32)||!["rocell.windows_camera_identity.v1","rocell.windows_camera_identity.v2"].includes(checks.driver_protocol_schema)||!v.exact(checks.driver_field_availability,names)||!names.every(k=>["NOT_RETAINED","OBSERVED","UNAVAILABLE"].includes(checks.driver_field_availability[k]))||!["UNKNOWN","OBSERVED"].includes(checks.operator_observation_state)||!codes(a.missing_requirements,16)||!a.missing_requirements.every(k=>missingRoster.includes(k))||!minimumMissing.every(k=>a.missing_requirements.includes(k)))return null;
        if(checks.driver_protocol_schema.endsWith(".v1")&&(checks.exact_devnode_driver_observed||!names.every(k=>checks.driver_field_availability[k]==="NOT_RETAINED")))return null;
        if(checks.exact_devnode_driver_observed!==names.every(k=>checks.driver_field_availability[k]==="OBSERVED"))return null;
      }
      if((["ASSESSMENT_RETAINED_NOT_COMMITTED","REVIEW_PENDING"].includes(c.state)&&(!a||c.review!==null))||(["REVIEW_RETAINED_NOT_COMMITTED","REVIEWED_BLOCKED"].includes(c.state)&&!c.review))return null;
    }
    if(new Set(value.cycles.map(c=>c.identity_id)).size!==value.cycles.length)return null;
    const e=value.export_receipt;
    if(e!==null){const provenance=e.provenance;
      if(!v.exact(e,["status","valid","path","export_root","export_id","files","total_bytes","manifest_sha256","physical_authority","provenance","limitations"])||e.status!=="EXPORTED_DIAGNOSTICS"||e.valid!==true||e.physical_authority!=="NONE"||!v.string(e.path,16384)||!v.string(e.export_root,16384)||!v.identifier(e.export_id)||!v.digest(e.manifest_sha256)||!v.integer(e.total_bytes,1,8388608)||!v.exact(provenance,["session_id","mode","source_binding_sha256","source_identity","software_version"])||!v.identifier(provenance.session_id)||provenance.mode!=="PHYSICAL_DIAGNOSTIC"||provenance.source_binding_sha256!==value.source_sha256||!v.exact(provenance.source_identity,["source_sha256"])||provenance.source_identity.source_sha256!==value.source_sha256||!v.string(provenance.software_version,64)||!Array.isArray(e.limitations)||e.limitations.length>16||!e.limitations.every(x=>v.string(x,1024))||!Array.isArray(e.files)||e.files.length<4||e.files.length>12||!e.files.every(f=>v.exact(f,["name","bytes","sha256"])&&typeof f.name==="string"&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(f.name)&&v.integer(f.bytes,f.name==="events.jsonl"?0:1,1048576)&&v.digest(f.sha256))||new Set(e.files.map(f=>f.name)).size!==e.files.length||["README.md","report.json","events.jsonl","manifest.json"].some(name=>!e.files.some(f=>f.name===name))||e.files.reduce((n,f)=>n+f.bytes,0)!==e.total_bytes)return null;
      const fixed=["README.md","report.json","events.jsonl","manifest.json"],parts=e.files.filter(f=>!fixed.includes(f.name)).map(f=>f.name).sort();
      if(parts.length<1||parts.length>8||parts.some((name,i)=>name!==`attachment-camera-identity-part-${String(i+1).padStart(2,"0")}.json`))return null;
    }
    if(value.publication.status==="PENDING")return value.cycles.length===0&&value.identity_entry===null&&value.next_action===null&&["NOT_STARTED","HISTORICAL_HELD"].includes(value.status)?value:null;
    if((value.publication.status!=="CURRENT"&&value.next_action!==null)||(value.publication.status==="HISTORICAL_HELD"&&!["HISTORICAL_HELD","NOT_STARTED"].includes(value.status)))return null;
    if(value.publication.status==="CURRENT"){
      const setup=p.setup(view.physical_camera_setup),b=setup?.session.binding,verification=setup?.session.verification,c=value.original_context;
      if(!setup||setup.publication.status!=="CURRENT"||!verification||!s||value.publication.operation_id===null||value.source_sha256!==view.source_binding_sha256||value.source_sha256!==setup.source_sha256||value.launch_session_id!==view.session_id||value.launch_session_id!==setup.launch_session_id||stageNames.some((key,i)=>s[key]!==setup.session.stages[i].state))return null;
      if(c===null?setup.prerequisites!==null:!setup.prerequisites||c.source_sha256!==value.source_sha256||c.session_id!==b.session_id||c.cell_id!==b.cell_id||c.origin_launch_id!==b.launch_id||c.header_sha256!==verification.session.header_sha256||c.prerequisites_sha256!==setup.prerequisites.evidence_sha256)return null;
      if((value.cycles.length||value.identity_entry)&&(!c||["workspace_sources","static_camera_contract","camera_receipt"].some(k=>s[k]!=="PASS")||!value.identity_entry))return null;
      if((value.status==="REVIEW_PENDING"&&(s.camera_identity!=="REVIEW_PENDING"||value.cycles.at(-1)?.state!=="REVIEW_PENDING"))||(value.status==="REVIEWED_BLOCKED"&&(s.camera_identity!=="BLOCKED"||value.cycles.at(-1)?.state!=="REVIEWED_BLOCKED"))||(value.status==="WAITING_METADATA"&&s.camera_identity!=="WAITING_OPERATOR")||s.camera_identity==="PASS")return null;
    }
    return value;
  }

  function cameraIdentityOnboarding(){
    const box=element("section","camera-identity-onboarding");
    box.append(heading("Original camera identity — stage 4"),element("p","notice warning","Metadata-only assessment remains BLOCKED. No complete persistent-unit identity, USB operating-speed or reconnect/reboot qualification, stage-5 entry, native capture release or current connection is established."));
    const input=state.view.camera_identity_onboarding;
    if(input===undefined||input===null){box.append(element("p","caption","No original identity workflow is available in this snapshot."));return box;}
    const value=cameraIdentityProjection(input,state.view);
    if(!value){box.append(element("p","notice warning","CAMERA_IDENTITY_NOT_VERIFIED: Inconsistent cached identity context or publication withheld. Inspect original diagnostics; no acceptance is inferred."));return box;}
    box.append(facts({status:value.status,publication:value.publication.status,source_sha256:value.source_sha256,current_launch:value.launch_session_id}),element("p","caption",value.meaning));
    if(value.schema==="rocell.wizard_camera_identity_export_pointer.v1"){box.append(element("p","notice warning","General export coverage pointer only — full original identity subjects are in the separate metadata bundle."),detail(value,"Compact identity coverage"));return box;}
    if(value.publication.status==="PENDING"){box.append(element("p","notice warning","Identity publication pending: new subjects are withheld until exact original readback, source/Stop checks and completion logging."));return box;}
    const historical=value.status==="HISTORICAL_HELD"||value.publication.status==="HISTORICAL_HELD";
    if(historical)box.append(element("p","notice warning","HISTORICAL ONLY: Original metadata is not rebound to the current launch or currently connected device. Refresh/reopen does not run inventory, restore a live endpoint choice or replay a submission."));
    if(value.original_context)box.append(heading("Original identity context"),facts(value.original_context));
    if(value.stage_states)box.append(heading(historical?"Historical committed stage states":"Original committed stage states"),facts(value.stage_states));
    for(const cycle of value.cycles){box.append(heading(`Identity collection ${cycle.sequence}: ${cycle.state}`),element("p","",`identity_id: ${cycle.identity_id}`));
      for(const role of ["metadata","helper","receipt","assessment","review"])box.append(element("p","",`${role}: ${cycle[role]?.sha256||"NOT_RETAINED"}`));
      const a=cycle.assessment;
      if(a){box.append(heading("Metadata checks — not qualification"));for(const [key,item]of Object.entries(a.checks)){if(key==="native_review_blockers")continue;if(key==="driver_field_availability"){for(const [name,status]of Object.entries(item))box.append(element("p","",`Exact-devnode driver ${name}: ${status}`));}else box.append(element("p","",`${key}: ${item}`));}box.append(heading("Missing qualification evidence — BLOCKED"));for(const reason of a.missing_requirements)box.append(element("p","notice warning",reason));}
      if(cycle.review)box.append(element("p","caption","Exact-subject procedural review is retained; it cannot upgrade this BLOCKED metadata assessment. Operator/reviewer labels and the literal INT-018 statement remain in the full metadata bundle, not authenticated identities."));
    }
    if(!value.cycles.length)box.append(element("p","caption","No complete original identity collection retained. Use current generic discovery/review, fixed-helper inspection/review, exact native identity/review, then explicit original-store refresh. INT-018 needs an explicit observation or UNKNOWN reason; no serial value is inferred."));
    if(value.next_action&&!historical)box.append(element("p","caption",`Next explicit action: ${value.next_action}. Use the eligible form; nothing is prepared automatically.`));
    if(value.export_receipt)box.append(heading("Separate identity metadata export"),facts({path:value.export_receipt.path,export_id:value.export_receipt.export_id,manifest_sha256:value.export_receipt.manifest_sha256}));
    box.append(element("p","caption","General diagnostic export carries coverage only. Explicitly export the complete original identity metadata bundle; private raw media is not included."));
    return box;
  }

  function receivedCameraOnboarding(){
    const box=element("section","received-camera-onboarding");
    box.append(heading("Received camera and passive workcell — original stage 3"),element("p","notice warning","Receipt acceptance is not installation qualification, USB identity, native camera release or permission to connect, power, move or contact. No device effect is performed."));
    const input=state.view.received_camera_onboarding;
    if(input==null){box.append(element("p","caption","No received-camera projection in this legacy snapshot. Nothing is observed or submitted by viewing it."));return box;}
    const value=receivedCameraProjection(input,state.view);
    if(!value){box.append(element("p","notice warning","RECEIVED_CAMERA_NOT_VERIFIED: Inconsistent, unsupported or stale cached subject withheld. Inspect retained metadata; no acceptance or replay is inferred."));return box;}
    box.append(facts({status:value.status,publication:value.publication.status,source_sha256:value.source_sha256,current_launch:value.launch_session_id}),element("p","caption",value.meaning));
    if(value.schema==="rocell.wizard_received_camera_export_pointer.v1"){
      box.append(element("p","notice warning","RECEIVED METADATA POINTER ONLY: This general export does not contain the original received-camera documents or private media. Use the separate physical_received_camera_export bundle."));
      if(value.latest_subjects)box.append(facts(value.latest_subjects));if(value.metadata_export)box.append(facts(value.metadata_export));return box;
    }
    if(value.publication.status==="PENDING"){box.append(element("p","notice warning","Publication pending: draft, original collection and file choices withheld until original-store readback and completion logging succeed."));return box;}
    const historical=value.publication.status!=="CURRENT";
    if(historical)box.append(element("p","notice warning","HISTORICAL ONLY: original observations and reviewer labels are not current qualification. Context is not rebound; no automatic retry or identity entry."));
    if(value.original_context)box.append(heading("Original received-unit context"),facts(value.original_context));
    if(value.stage_states)box.append(heading(historical?"Historical recorded stages":"Original session committed stages"),facts(value.stage_states));
    const notebook=(n,label)=>{box.append(heading(label),facts({revision:n.revision,original_launch:n.binding.origin_launch_id,recording_launch:n.binding.launch_session_id,...n.coverage}));for(const row of n.rows){const item=element("details");item.append(element("summary","",`${row.record_id}: ${row.measurement} / ${row.unit||"no unit"} / ${row.observation?.status||"UNRECORDED"}`),intakeQuestion(row));if(row.observation)item.append(intakeObservation(row.observation));else item.append(element("p","caption","No observation recorded. No numeric value or identity is inferred."));box.append(item);}};
    if(value.draft){notebook(value.draft,"Editable draft — not a stored receipt");if(value.draft_origin_notebook_sha256)box.append(facts({carried_from_original_notebook:value.draft_origin_notebook_sha256}),element("p","notice warning","Carried-forward observations preserve their original labels and timestamps; they are not fresh measurements. Structured inspection must be explicitly observed again."));}
    const t=value.collection;
    if(t){box.append(heading("Latest original received collection"),facts({receipt_id:t.receipt_id,sequence:t.sequence,state:t.state}));if(t.notebook)notebook(t.notebook.document,"Original retained notebook — exact subject for review");
      const s=t.submission,a=t.assessment,r=t.review,i=t.inspection;
      if(s)box.append(facts({submission_sha256:s.submission_sha256,notebook_sha256:s.notebook_sha256,inspection_sha256:s.inspection_sha256,attachment_count:s.attachment_count,attachment_bytes:s.attachment_bytes,linked_row_count:s.linked_row_count,carried_forward_record_ids:s.carried_forward_record_ids}),element("p","",`Submission operator label: ${s.binding.operator_id}`));
      box.append(heading("Structured received-camera inspection — operator reported"));
      if(i){for(const key of ["observed_manufacturer","observed_product_id","observed_camera_serial","observed_lens_focal_length_mm","body_condition","lens_condition","connector_condition","identity_label_legible","purchase_record_matches","package_contents_complete","inspection_uncertain"])box.append(element("p","",`${key}: ${i[key]===null?"UNKNOWN":i[key]}`));box.append(facts({inspection_sha256:i.receipt_sha256,purchase_record_evidence_id:i.purchase_record_evidence_id,inspection_image_evidence_ids:i.inspection_image_evidence_ids}),element("p","caption","Original media is referenced, never previewed here. Narrative notes do not replace structured identity or prove measurement truth."));}else box.append(element("p","notice warning","Structured inspection UNKNOWN / not retained. Manufacturer, serial and lens identity are not inferred from notebook prose."));
      if(a){box.append(heading(`Receipt completeness assessment: ${a.verdict}`),facts({assessment_sha256:a.assessment_sha256,foundation_sha256:a.foundation_sha256,status:a.foundation.status,...a.foundation.coverage}),heading("Recorded thickness accommodation — exact decimal text"));for(const [key,item]of Object.entries(a.foundation.thickness))box.append(element("p","",`${key}: ${item===null?"UNKNOWN":item}`));for(const code of a.missing_requirements)box.append(element("p","notice warning",code));for(const code of a.foundation.residuals)box.append(element("p","caption",code));}
      if(r)box.append(heading("Exact-subject receipt review"),element("p","",`Reviewer label: ${r.reviewer_id}`),facts({review_sha256:r.review_sha256,submission_sha256:r.submission_sha256,assessment_sha256:r.assessment_sha256,decision:r.decision,verdict:r.verdict,review_launch:r.review_launch_id}),element("p","caption","Distinct labels are procedural, not authenticated independent people. Retained timestamps are not rendered as exact JavaScript clocks."));else box.append(element("p","notice warning","No committed exact-subject review; retained bytes or an assessment alone are not a stage PASS."));
    }
    if(value.status==="REVIEWED_PASS"&&!historical)box.append(element("p","notice","Stage 3 receipt accepted only — no installation qualification or native camera release."),element("p","caption",value.identity_entry?"Stage 4 identity was explicitly requested and remains WAITING_OPERATOR; no metadata enumeration has occurred.":"Stage 4 remains PENDING. Identity entry requires a separate explicit action."));
    const d=value.inbox.discovery;box.append(heading("Assigned inbox — explicit file discovery"),element("p","caption",d.directory),facts({status:d.status,discovery_sha256:d.discovery_sha256}));for(const f of d.files)box.append(element("p","",`${f.basename} · ${f.media_type} · ${f.payload_bytes} bytes · ${f.payload_sha256}`));for(const i of d.issues)box.append(element("p","notice warning",`${i.basename||"Assigned inbox"}: ${i.code}`));
    if(value.identity_entry)box.append(facts({identity_entry_event:value.identity_entry}));if(value.metadata_export)box.append(heading("Separate received metadata export"),facts({path:value.metadata_export.path,export_id:value.metadata_export.export_id,manifest_sha256:value.metadata_export.manifest_sha256}));
    if(value.next_action&&!historical)box.append(element("p","caption",`Next explicit action: ${value.next_action}. Viewing never prepares or executes it.`));
    box.append(element("p","notice warning","INT-005 acceptance remains deferred. Mount threads, C/CS interpretation, bench conditions and nominal dimensions or mass are not assigned invented acceptance tolerances. Export received-camera metadata separately: general diagnostics contain a pointer only. Private original media is not included or opened."));return box;
  }

  function physicalIntakeProjection(value, setupValue) {
    const v = cameraConfigurationValidators();
    if (!v.exact(value, ["schema", "status", "notebook", "physical_authority", "hardware_qualified", "meaning"])
      || value.schema !== "rocell.wizard_physical_intake.v1" || !["NOT_STARTED", "CURRENT_DRAFT", "HISTORICAL_HELD"].includes(value.status)
      || value.physical_authority !== false || value.hardware_qualified !== false || !v.string(value.meaning, 512)) return null;
    if (value.status !== "CURRENT_DRAFT") return value.notebook === null ? value : null;
    const setup = physicalSetupValidators().setup(setupValue), n = value.notebook;
    if (!setup || setup.publication.status !== "CURRENT" || !setup.prerequisites
      || !v.exact(n, ["schema", "binding", "revision", "previous_sha256", "rows", "coverage", "physical_authority", "hardware_qualified", "canonical_stage_pass", "device_io_performed", "attachment_bytes_verified", "meaning", "snapshot_sha256"])
      || n.schema !== "rocell.physical_intake_notebook.v1" || !v.integer(n.revision, 0, 128) || !v.digest(n.snapshot_sha256)
      || (n.revision === 0 ? n.previous_sha256 !== null : !v.digest(n.previous_sha256) || /^0{64}$/.test(n.previous_sha256))
      || !["physical_authority", "hardware_qualified", "canonical_stage_pass", "device_io_performed", "attachment_bytes_verified"].every(key => n[key] === false) || !v.string(n.meaning, 512)
      || !v.exact(n.binding, ["source_sha256", "session_id", "origin_launch_id", "launch_session_id", "prerequisites_sha256"])) return null;
    const b = n.binding, original = setup.session.binding;
    if (b.source_sha256 !== setup.source_sha256 || b.session_id !== original.session_id || b.origin_launch_id !== original.launch_id || b.launch_session_id !== setup.launch_session_id || b.prerequisites_sha256 !== setup.prerequisites.evidence_sha256) return null;
    const questions = setup.prerequisites.stages.find(stage => stage.stage === "camera_receipt").intake_rows;
    const same = (left, right) => {
      if (left === right) return true;
      if (left === null || right === null || typeof left !== "object" || typeof right !== "object" || Array.isArray(left) !== Array.isArray(right)) return false;
      const keys = Object.keys(left); return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && same(left[key], right[key]));
    };
    const entryText = (item, maximum) => v.string(item, maximum) && item.trim() === item && !/\p{C}/u.test(item);
    if (!Array.isArray(n.rows) || n.rows.length !== 16 || !v.exact(n.coverage, ["total", "observed", "unknown", "unrecorded"])) return null;
    let observed = 0, unknown = 0;
    for (let index = 0; index < n.rows.length; index++) {
      const row = n.rows[index], question = questions[index];
      if (!v.exact(row, Object.keys(question))) return null;
      const {observation, ...content} = row, {observation: ignored, ...expected} = question;
      if (!same(content, expected)) return null;
      if (observation === null) continue;
      if (!v.exact(observation, ["status", "observed_value", "method", "evidence_note", "operator_id", "recorded_at_ns"]) || !["OBSERVED", "UNKNOWN"].includes(observation.status)
        || !entryText(observation.observed_value, 256) || !entryText(observation.method, 512) || !entryText(observation.evidence_note, 1024) || !entryText(observation.operator_id, 64)
        || typeof observation.recorded_at_ns !== "number" || !Number.isInteger(observation.recorded_at_ns) || observation.recorded_at_ns <= 0 || observation.recorded_at_ns >= 2 ** 63) return null;
      if (observation.status === "OBSERVED") {
        if (["mm", "g"].includes(row.unit) && (!/^[0-9]+(?:\.[0-9]+)?$/.test(observation.observed_value) || (row.record_id !== "INT-005" && !/[1-9]/.test(observation.observed_value)))) return null;
        observed++;
      } else unknown++;
    }
    if (n.coverage.total !== 16 || n.coverage.observed !== observed || n.coverage.unknown !== unknown || n.coverage.unrecorded !== 16 - observed - unknown
      || observed + unknown > n.revision || (n.revision > 0 && observed + unknown === 0)) return null;
    // Match the model's entire canonical-ASCII payload budget, excluding its
    // externally supplied self hash. Key order does not affect encoded length.
    const {snapshot_sha256, ...payload} = n;
    if (JSON.stringify(payload).replace(/[\u007f-\uffff]/g, character => "\\u" + character.charCodeAt(0).toString(16).padStart(4, "0")).length > 65536) return null;
    return value;
  }

  function intakeQuestion(row) {
    const box = element("section", "intake-question");
    box.append(heading(`${row.record_id}: ${row.measurement}`), facts({assembly: row.assembly, source_unit: row.unit || "No unit specified", candidate_or_requirement_NOT_OBSERVED: row.candidate_or_requirement, source_notes: row.template_notes}),
      element("p", "notice warning", row.record_id === "INT-005" ? "INT-005 flatness: a draft value does not accept a flatness limit. Acceptance remains deferred to noncontact_acceptance until TARGET_ACCURACY_BUDGET_CLOSED." : "This source requirement is not an observed value. Recording a draft does not assess or accept this question."));
    return box;
  }

  function intakeObservation(observation) {
    // Narrative values are exact operator text, not enum identifiers. Never
    // pass them through human(), interpret markup, or alter punctuation.
    const table = element("table", "detail-table"), body = element("tbody");
    for (const key of ["status", "observed_value", "method", "evidence_note", "operator_id"]) {
      const row = element("tr"), label = element("th", "", human(key)); label.scope = "row";
      row.append(label, element("td", "", observation[key])); body.append(row);
    }
    table.append(body); return table;
  }

  function physicalIntake() {
    const box = card("Passive intake notebook", "Sixteen original camera, placemat and bench questions - operator drafts only");
    box.append(element("span", "badge hold", "DRAFT ONLY / NOT ACCEPTED"), element("p", "notice warning", "No stage PASS, power observation, epoch, permit or connection is created. Evidence notes are descriptions only; no attachment bytes are uploaded, read or verified. Export the notebook to the assigned diagnostics folder before closing: draft restoration on another launch is not supported."));
    const value = physicalIntakeProjection(state.view.physical_intake, state.view.physical_camera_setup);
    if (!value) { box.append(element("p", "notice warning", state.view.physical_intake == null ? "No intake notebook is available. Start explicitly after current setup requirements are published." : "PHYSICAL_INTAKE_NOT_VERIFIED: Inconsistent, stale or unsupported draft withheld. Nothing is inferred from old observations.")); return box; }
    box.append(facts({status: value.status}), element("p", "caption", value.meaning));
    if (!value.notebook) { box.append(element("p", "caption", value.status === "HISTORICAL_HELD" ? "Current draft is held. Retained exports are historical drafts, not current measurement or acceptance." : "No notebook started. Candidate dimensions never populate observation fields automatically.")); return box; }
    const n = value.notebook;
    box.append(facts({revision: n.revision, snapshot_sha256: n.snapshot_sha256, previous_sha256: n.previous_sha256}), facts(n.binding), heading("Draft coverage - not measurement acceptance"), facts(n.coverage),
      element("p", "caption", "OBSERVED means operator-reported, not verified. UNKNOWN is a reason, not measured coverage. Enter a value or reason, method, evidence description and operator explicitly; use your own 'not measured' or 'not supplied' description when appropriate. Narrative descriptions must be single-line, without line breaks. No nominal defaults or autosave."));
    for (const row of n.rows) {
      const section = element("details"); section.append(element("summary", "", `${row.record_id}: ${row.measurement} / ${row.unit || "no unit"} / ${row.observation?.status || "UNRECORDED"} / NOT ACCEPTED`), intakeQuestion(row));
      if (row.observation) section.append(intakeObservation(row.observation), element("p", "caption", "Record time retained; not interpreted as an exact browser timestamp or freshness proof."));
      else section.append(element("p", "caption", "No operator observation recorded."));
      box.append(section);
    }
    return box;
  }

  function physicalIntakeEvidenceProjection(value, view) {
    // Cached, bounded display only. Original bytes and subject hashes are
    // verified by the store, never by rendering or selecting an input here.
    const v = cameraConfigurationValidators(), equal = (a, b) => {
      if (a === b) return true;
      if (!a || !b || typeof a !== "object" || typeof b !== "object" || Array.isArray(a) !== Array.isArray(b)) return false;
      return Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => Object.hasOwn(b, k) && equal(a[k], b[k]));
    };
    const flags = ["physical_authority", "hardware_qualified", "canonical_stage_pass", "device_io_performed", "measurement_truth_verified", "authenticated_operator_identity"];
    const text = (x, max) => v.string(x, max) && x.trim() === x && !/\p{C}/u.test(x);
    const id = x => typeof x === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(x);
    const operator = x => typeof x === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(x);
    const collectionId = x => typeof x === "string" && /^intake-[0-9a-f]{32}$/.test(x);
    const basename = x => typeof x === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(x) && !x.endsWith(".");
    const media = {txt:"text/plain", json:"application/json", png:"image/png", jpg:"image/jpeg", jpeg:"image/jpeg", pdf:"application/pdf"};
    const attachment = (x, discovered) => v.exact(x, [discovered ? "choice_id" : "evidence_id", "basename", "media_type", "payload_bytes", "payload_sha256"])
      && (discovered ? typeof x.choice_id === "string" && /^intake-file-[0-9a-f]{32}$/.test(x.choice_id) : id(x.evidence_id))
      && basename(x.basename) && media[x.basename.split(".").pop().toLowerCase()] === x.media_type && v.digest(x.payload_sha256) && v.integer(x.payload_bytes, 1, (discovered ? 2 : 4) * 1024 * 1024);
    const contextKeys = ["source_sha256", "session_id", "cell_id", "origin_launch_id", "header_sha256", "prerequisites_sha256"];
    const bindingKeys = [...contextKeys, "source_binding_sha256", "submission_launch_id", "notebook_sha256"];
    const binding = x => v.exact(x, bindingKeys) && bindingKeys.every(k => k.endsWith("sha256") ? v.digest(x[k]) : id(x[k]));
    const noAuthority = x => flags.every(k => x[k] === false) && text(x.meaning, 512);
    const coverageKeys = ["total", "observed", "unknown", "attached_rows", "attachment_count", "attachment_bytes"];
    const records = ["001", "002", "003", "004", "005", "006", "007", "008", "009", "017", "019", "020", "021", "022", "023", "024"].map(x => "INT-" + x);
    const issueCodes = ["BUSY", "INVALID", "LIMIT", "UNSAFE_FILE", "FILE_LIMIT", "FILE_TYPE", "CONTENT", "CHANGED", "STALE_CHOICE", "SOURCE_CHANGED", "CANCELLED", "DEADLINE", "READ_FAILED"].map(x => "INTAKE_INBOX_" + x);
    if (!v.exact(value, ["schema", "source_sha256", "launch_session_id", "original_context", "publication", "status", "discovery", "collection", "collection_count", "physical_authority", "hardware_qualified", "meaning"])
      || value.schema !== "rocell.wizard_physical_intake_evidence.v1" || !v.digest(value.source_sha256) || !id(value.launch_session_id)
      || value.physical_authority !== false || value.hardware_qualified !== false || !text(value.meaning, 512)
      || !["NOT_STARTED", "DISCOVERED", "SUBMITTED_REVIEW_PENDING", "REVIEWED", "INCOMPLETE_HELD", "HISTORICAL_HELD"].includes(value.status)
      || !v.integer(value.collection_count, 0, 8) || !v.exact(value.publication, ["status", "operation_id"])
      || !["NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"].includes(value.publication.status) || !(value.publication.operation_id === null || id(value.publication.operation_id))) return null;
    const context = value.original_context, d = value.discovery, c = value.collection;
    if (context !== null && (!v.exact(context, contextKeys) || !contextKeys.every(k => k.endsWith("sha256") ? v.digest(context[k]) : id(context[k])))) return null;
    if (!v.exact(d, ["schema", "status", "directory", "source_sha256", "launch_session_id", "discovery_sha256", "files", "issues", "physical_authority", "device_io_performed"])
      || d.schema !== "rocell.physical_intake_inbox.v1" || !["NOT_DISCOVERED", "READY", "HELD"].includes(d.status)
      || !v.string(d.directory, 4096) || !/^(?:[A-Za-z]:[\\/]|\/)/.test(d.directory) || d.directory.replaceAll("\\", "/").split("/").includes("..")
      || !d.directory.replaceAll("\\", "/").endsWith("/software/runs/physical-intake-inbox")
      || d.source_sha256 !== value.source_sha256 || d.launch_session_id !== value.launch_session_id || d.physical_authority !== false || d.device_io_performed !== false
      || !Array.isArray(d.files) || d.files.length > 32 || !d.files.every(x => attachment(x, true)) || new Set(d.files.map(x => x.choice_id)).size !== d.files.length || new Set(d.files.map(x => x.basename)).size !== d.files.length
      || d.files.reduce((n, x) => n + x.payload_bytes, 0) > 16 * 1024 * 1024
      || !Array.isArray(d.issues) || d.issues.length > 33 || !d.issues.every(x => v.exact(x, ["code", "basename"]) && issueCodes.includes(x.code) && (x.basename === null || basename(x.basename)))
      || (d.status === "READY" ? !v.digest(d.discovery_sha256) : d.discovery_sha256 !== null || d.files.length !== 0)
      || (d.status === "NOT_DISCOVERED" && d.issues.length !== 0)) return null;
    if (value.publication.status === "PENDING") return c === null && d.status === "NOT_DISCOVERED" && ["NOT_STARTED", "HISTORICAL_HELD"].includes(value.status) ? value : null;
    if (c !== null) {
      if (!context || !v.exact(c, ["collection_id", "state", "submission", "assessment", "review"]) || !collectionId(c.collection_id)
        || !["INCOMPLETE", "REVIEW_PENDING", "REVIEW_RETAINED_NOT_COMMITTED", "REVIEWED_BLOCKED"].includes(c.state) || value.collection_count < 1) return null;
      const s = c.submission, a = c.assessment, r = c.review;
      if (s !== null) {
        if (!v.exact(s, ["schema", "submission_sha256", "binding", "collection_id", "sequence", "predecessor_submission_sha256", "operator_id", "notebook_revision", "stage", "observation_owner_stage", "rows", "attachments", "coverage", ...flags, "meaning"])
          || s.schema !== "rocell.physical_passive_intake_submission_summary.v1" || !v.digest(s.submission_sha256) || !binding(s.binding) || !contextKeys.every(k => s.binding[k] === context[k])
          || s.collection_id !== c.collection_id || !v.integer(s.sequence, 1, 8) || s.sequence !== value.collection_count || (s.sequence === 1 ? s.predecessor_submission_sha256 !== null : !v.digest(s.predecessor_submission_sha256))
          || !operator(s.operator_id) || !v.integer(s.notebook_revision, 1, 128) || s.stage !== "workspace_sources" || s.observation_owner_stage !== "camera_receipt" || !noAuthority(s)
          || !Array.isArray(s.rows) || s.rows.length !== 16 || !Array.isArray(s.attachments) || s.attachments.length > 16 || !s.attachments.every(x => attachment(x, false))
          || new Set(s.attachments.map(x => x.evidence_id)).size !== s.attachments.length || !v.exact(s.coverage, coverageKeys)) return null;
        const attached = new Set(), unknown = []; let observed = 0, linked = 0;
        for (let i = 0; i < 16; i++) {
          const row = s.rows[i], deferred = records[i] === "INT-005";
          if (!v.exact(row, ["record_id", "measurement", "unit", "status", "observed_value", "method", "attachment_evidence_id", "acceptance_status", "acceptance_owner_stage"])
            || row.record_id !== records[i] || !text(row.measurement, 4096) || !(row.unit === "" || text(row.unit, 4096)) || !["OBSERVED", "UNKNOWN"].includes(row.status) || !text(row.observed_value, 256) || !text(row.method, 512)
            || row.acceptance_status !== (deferred ? "DEFERRED_LIMIT" : "NOT_ASSESSED") || row.acceptance_owner_stage !== (deferred ? "noncontact_acceptance" : "camera_receipt")) return null;
          if (row.attachment_evidence_id !== null) { if (!s.attachments.some(x => x.evidence_id === row.attachment_evidence_id)) return null; attached.add(row.attachment_evidence_id); linked++; }
          if (row.status === "OBSERVED") { if (row.attachment_evidence_id === null || (["mm", "g"].includes(row.unit) && (!/^[0-9]+(?:\.[0-9]+)?$/.test(row.observed_value) || (!deferred && !/[1-9]/.test(row.observed_value))))) return null; observed++; } else unknown.push(row.record_id);
        }
        const expected = {total:16, observed, unknown:16-observed, attached_rows:linked, attachment_count:s.attachments.length, attachment_bytes:s.attachments.reduce((n, x) => n+x.payload_bytes, 0)};
        if (!equal(s.coverage, expected) || expected.attachment_bytes > 4*1024*1024 || attached.size !== s.attachments.length) return null;
        if (a !== null && (!v.exact(a, ["schema", "assessment_sha256", "submission_sha256", "binding", "collection_id", "status", "observation_completeness", "unknown_record_ids", "coverage", "physical_readiness", ...flags, "meaning"])
          || a.schema !== "rocell.physical_passive_intake_assessment_summary.v1" || !v.digest(a.assessment_sha256) || a.submission_sha256 !== s.submission_sha256 || !equal(a.binding, s.binding) || a.collection_id !== c.collection_id
          || a.status !== "STRUCTURE_AND_REFERENCES_VALID" || a.observation_completeness !== (unknown.length ? "UNKNOWN_ROWS_REMAIN" : "ALL_ROWS_OBSERVED") || !equal(a.unknown_record_ids, unknown) || !equal(a.coverage, expected) || a.physical_readiness !== false || !noAuthority(a))) return null;
        if (r !== null && (!a || !v.exact(r, ["schema", "review_sha256", "binding", "collection_id", "submission_sha256", "assessment_sha256", "reviewer_id", "review_launch_id", "decision", "status", "distinct_operator_labels", "authenticated_independent_people", ...flags, "meaning"])
          || r.schema !== "rocell.physical_passive_intake_review_summary.v1" || !v.digest(r.review_sha256) || !equal(r.binding, s.binding) || r.collection_id !== c.collection_id || r.submission_sha256 !== s.submission_sha256 || r.assessment_sha256 !== a.assessment_sha256
          || !operator(r.reviewer_id) || r.reviewer_id.toLowerCase() === s.operator_id.toLowerCase() || !id(r.review_launch_id) || !["ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW", "REJECT"].includes(r.decision)
          || r.status !== (r.decision === "REJECT" ? "REJECTED" : "ACKNOWLEDGED_FOR_LATER_STAGE_REVIEW") || r.distinct_operator_labels !== true || r.authenticated_independent_people !== false || !noAuthority(r))) return null;
      } else if (a !== null || r !== null) return null;
      if ((c.state !== "INCOMPLETE" && (!s || !a)) || (c.state === "REVIEW_PENDING" && r !== null) || (["REVIEW_RETAINED_NOT_COMMITTED", "REVIEWED_BLOCKED"].includes(c.state) && !r)) return null;
    }
    if (value.status === "NOT_STARTED" && (c !== null || value.collection_count !== 0 || (value.publication.status !== "HISTORICAL_HELD" && d.status !== "NOT_DISCOVERED"))) return null;
    if (value.status === "DISCOVERED" && d.status !== "READY") return null;
    if (value.status === "SUBMITTED_REVIEW_PENDING" && c?.state !== "REVIEW_PENDING") return null;
    if (value.status === "REVIEWED" && c?.state !== "REVIEWED_BLOCKED") return null;
    if (value.publication.status === "HISTORICAL_HELD" && !["HISTORICAL_HELD", "NOT_STARTED"].includes(value.status)) return null;
    if (value.publication.status === "CURRENT") {
      const setup = physicalSetupValidators().setup(view.physical_camera_setup);
      if (value.source_sha256 !== view.source_binding_sha256 || value.launch_session_id !== view.session_id || !setup || setup.publication.status !== "CURRENT" || !setup.prerequisites || !setup.session.verification || !context) return null;
      const b = setup.session.binding, verified = setup.session.verification;
      if (context.source_sha256 !== setup.source_sha256 || context.session_id !== b.session_id || context.cell_id !== b.cell_id || context.origin_launch_id !== b.launch_id || context.header_sha256 !== verified.session.header_sha256 || context.prerequisites_sha256 !== setup.prerequisites.evidence_sha256) return null;
      if (c?.submission) {
        if (c.submission.binding.source_binding_sha256 !== verified.cell.source_binding_sha256) return null;
        const questions = setup.prerequisites.stages.find(x => x.stage === "camera_receipt").intake_rows;
        if (!c.submission.rows.every((row, i) => row.measurement === questions[i].measurement && row.unit === questions[i].unit)) return null;
      }
      if (c && (!workspaceSourceWorkflowProjection(setup.source_workflow, setup) || setup.source_workflow.supplementary?.collection_id !== c.collection_id
        || setup.source_workflow.supplementary.state !== ({INCOMPLETE:"WAITING_OPERATOR",REVIEW_PENDING:"REVIEW_PENDING",REVIEW_RETAINED_NOT_COMMITTED:"REVIEW_PENDING",REVIEWED_BLOCKED:"BLOCKED"})[c.state])) return null;
    }
    return value;
  }

  function physicalIntakeEvidence() {
    const box = card("Retained passive intake evidence", "Original-store submissions and exact-subject review — not physical acceptance");
    box.append(element("span", "badge hold", "BYTES / PROCEDURAL REVIEW ONLY"), element("p", "notice warning", "The source verdict remains BLOCKED. OBSERVED means operator-reported, not measurement truth. File integrity and distinct labels do not qualify hardware or authenticate independent people. INT-005 acceptance stays deferred to noncontact_acceptance."));
    const value = physicalIntakeEvidenceProjection(state.view.physical_intake_evidence, state.view);
    if (!value) { box.append(element("p", "notice warning", state.view.physical_intake_evidence == null ? "No retained intake projection in this snapshot. Nothing is submitted or discovered by viewing it." : "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED: Inconsistent, unsupported or stale cached context withheld. Inspect original diagnostics; no retry or acceptance is inferred.")); return box; }
    box.append(element("p", "caption", `Intake publication: ${value.publication.status} / ${value.status}`), element("p", "caption", value.meaning));
    if (value.publication.status === "PENDING") { box.append(element("p", "notice warning", "Publication pending: discovery and collection details withheld until original-store retention and completion logging succeed.")); return box; }
    if (value.status === "HISTORICAL_HELD" || value.publication.status === "HISTORICAL_HELD") box.append(element("p", "notice warning", "HISTORICAL ONLY: original subject context is not current qualification or a usable file choice. No automatic discovery, submission, review or replay."));
    if (value.original_context) box.append(facts(value.original_context));
    const d = value.discovery;
    box.append(heading("Assigned inbox — explicit discovery only"), element("p", "caption", d.directory), facts({status:d.status, discovery_sha256:d.discovery_sha256}), element("p", "caption", "Place files in the assigned inbox, then explicitly discover. Complete all sixteen draft questions. OBSERVED requires an attachment; UNKNOWN may omit one. Batch selection does not read files or submit automatically."));
    for (const file of d.files) box.append(element("p", "", `${file.basename} · ${file.media_type} · ${file.payload_bytes} bytes · ${file.payload_sha256}`));
    for (const issue of d.issues) box.append(element("p", "notice warning", `${issue.basename || "Assigned inbox"}: ${issue.code}`));
    const c = value.collection;
    if (!c) box.append(element("p", "caption", "No published collection. Draft notes are not stored attachment evidence."));
    else {
      box.append(heading("Latest original collection"), facts({collection_id:c.collection_id, collection_state:c.state, retained_collection_count:value.collection_count}));
      if (["INCOMPLETE", "REVIEW_RETAINED_NOT_COMMITTED"].includes(c.state)) box.append(element("p", "notice warning", "Incomplete publication: stored bytes or review are not a committed review. Inspect the original collection; do not silently retry."));
      const s = c.submission;
      if (s) {
        box.append(element("p", "", `Operator label: ${s.operator_id}`), facts({submission_sha256:s.submission_sha256, sequence:s.sequence, predecessor_submission_sha256:s.predecessor_submission_sha256, notebook_revision:s.notebook_revision}), facts(s.binding), heading("Reported coverage — not measured acceptance"), facts(s.coverage));
        for (const row of s.rows) { const item = element("details"); item.append(element("summary", "", `${row.record_id}: ${row.measurement} / ${row.unit || "no unit"} / ${row.status} / ${row.acceptance_status}`));
          for (const key of ["observed_value", "method", "attachment_evidence_id", "acceptance_owner_stage"]) item.append(element("p", "", `${key}: ${row[key] === null ? "No attachment" : row[key]}`)); box.append(item); }
        for (const file of s.attachments) box.append(element("p", "", `Retained original: ${file.evidence_id} · ${file.basename} · ${file.media_type} · ${file.payload_bytes} bytes · ${file.payload_sha256}`));
      }
      if (c.assessment) box.append(heading("Structure/reference assessment — physical readiness false"), facts({assessment_sha256:c.assessment.assessment_sha256, status:c.assessment.status, observation_completeness:c.assessment.observation_completeness, unknown_record_ids:c.assessment.unknown_record_ids}));
      if (c.review) box.append(heading("Exact-subject procedural review — not authenticated people"), element("p", "", `Reviewer label: ${c.review.reviewer_id}`), facts({review_sha256:c.review.review_sha256, submission_sha256:c.review.submission_sha256, assessment_sha256:c.review.assessment_sha256, decision:c.review.decision, review_launch_id:c.review.review_launch_id}), element("p", "notice warning", c.review.decision === "REJECT" ? "Submission REJECTED; original evidence remains retained." : "Acknowledged for later-stage review only. No canonical physical stage is accepted."));
    }
    box.append(element("p", "notice warning", "Diagnostics export retains submission metadata, not original media. Export originals is a separate explicit action: byte-preserving files may contain private material and are not redacted. This page does not open or preview attachments."));
    return box;
  }

  function retainedCameraConfiguration(projection) {
    const box = element("section", "retained-camera-configuration");
    box.append(heading("Modeled camera capabilities and configuration"), element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED"),
      element("p", "notice warning", "These modes, ranges and readbacks are modeled incapable-fixture observations, not measured support from the purchased camera. Lens focus and aperture are manual physical adjustments; this interface cannot set or verify them."));
    const value = cameraConfigurationValidators().configuration(projection);
    if (!value) {
      box.append(badge("CAMERA_CONFIGURATION_NOT_VERIFIED"), element("p", "notice warning", "The cached configuration projection is missing, inconsistent or exceeds display bounds. Raw fields are withheld. Inspect retained diagnostics; do not guess support, apply defaults or replay a probe/capture."));
      return box;
    }
    box.append(element("span", "badge hold", human(value.status)), element("p", "caption", value.meaning), heading("Retained capability probe"),
      facts({status: value.probe.status, evidence_sha256: value.probe.evidence_sha256, ...value.probe.binding}));
    if (value.probe.process) box.append(heading("Probe: actual child process"), facts(value.probe.process));
    if (value.probe.native) box.append(heading("Probe: synthetic native observation"), facts(value.probe.native));
    if (value.probe.blockers.length) box.append(facts({probe_holds: value.probe.blockers}));
    box.append(element("p", "caption", "A complete probe is not a complete capture. Its source lifecycle has zero control writes, samples and frames. OS process cleanup does not prove physical camera cleanup."));
    const caps = value.capabilities;
    if (!caps) box.append(badge("CAPABILITIES_UNAVAILABLE"), element("p", "caption", "No reported modes or control limits are inferred from an incomplete probe."));
    else {
      box.append(facts({capabilities_sha256: caps.capabilities_sha256, probe_evidence_sha256: caps.probe_evidence_sha256, endpoint_sha256: caps.endpoint_sha256}), heading("Every reported mode; no automatic selection"));
      const modes = element("ul", "stage-list");
      for (const item of caps.modes) {
        const row = element("li"), body = element("div");
        body.append(element("strong", "", `${item.mode.width} × ${item.mode.height} · ${item.mode.fps_numerator}/${item.mode.fps_denominator} fps · ${item.mode.subtype}`),
          element("p", "caption", `Opaque choice: ${item.choice_id}; reported stride: ${item.mode.stride_bytes === null ? "NOT_REPORTED" : item.mode.stride_bytes} bytes`));
        if (item.blockers.length) body.append(element("p", "caption", item.blockers.join(", ")));
        row.append(body, element("span", "badge hold", item.selectable ? "REPORTED_FORMAT_CONTRACT_ONLY" : "REPORTED_MODE_CAPTURE_HELD")); modes.append(row);
      }
      box.append(modes, element("p", "caption", "The finite fixture action can further restrict eligible modes. Its explicit mode field is the available selection list; a reported format is not a promise of capture support or physical camera compatibility."));
      if (!caps.modes.length) box.append(badge("NO_REPORTED_MODES"));
      box.append(heading("Six electronic controls: modeled reports, not hardware limits"));
      for (const id of ["exposure", "gain", "white_balance", "brightness", "contrast", "saturation"]) {
        const item = caps.controls.find(row => row.control_id === id);
        const control = element("section"); control.append(element("h3", "", human(id)));
        if (!item) control.append(badge("UNAVAILABLE_NOT_REPORTED"));
        else control.append(facts({inclusive_range: `${item.minimum} to ${item.maximum}`, step: item.step, reported_default_not_applied: item.default, unit: item.unit,
          capability_flags: `${item.capability_flags} (${item.capability_flags === 1 ? "AUTO" : item.capability_flags === 2 ? "MANUAL" : "AUTO_AND_MANUAL_SUPPORTED"})`,
          current_modeled_readback: item.value, current_flags: `${item.flags} (${item.flags === 1 ? "AUTO" : item.flags === 2 ? "MANUAL" : "AMBIGUOUS_AUTO_AND_MANUAL"})`}));
        box.append(control);
      }
      box.append(element("p", "caption", "Reported defaults are informational and never automatically applied. Unreported controls have no inferred range. Current flags 3 are ambiguous, not a confirmed active mode."));
    }
    box.append(heading("Immutable candidate: staged, not applied"));
    if (!value.candidate) box.append(badge("NO_CONFIGURATION_CANDIDATE"));
    else box.append(facts({settings_epoch: value.candidate.settings_epoch, mode_choice_id: value.candidate.mode_choice_id, ...value.candidate.mode}),
      facts({requested_controls: value.candidate.controls, applied: false}), element("p", "caption", "Staging does no control write. A later explicit finite campaign uses this exact candidate; changing it is not an in-stream update."));
    box.append(heading("Requested versus observed modeled readback"));
    if (!value.readback) box.append(badge("READBACK_NOT_AVAILABLE"));
    else {
      const readback = value.readback;
      box.append(element("span", "badge hold", human(readback.status)), facts({settings_epoch: readback.settings_epoch, native_receipt_sha256: readback.native_receipt_sha256,
        requested_mode: readback.requested_mode, observed_mode: readback.observed_mode || "NOT_OBSERVED", mode_matched: readback.mode_matched}));
      for (const row of readback.controls) box.append(element("h3", "", human(row.control_id)), facts({requested_value: row.requested.value, requested_mode: row.requested.mode,
        observed_value: row.observed ? row.observed.value : "NOT_OBSERVED", observed_flags: row.observed ? row.observed.flags : "NOT_OBSERVED", observed_unit: row.observed ? row.observed.unit : "NOT_OBSERVED", matched: row.matched, reasons: row.reasons}));
      if (readback.reasons.length) box.append(facts({readback_holds: readback.reasons}));
    }
    box.append(element("p", "notice warning", "Manual readback must match the requested value exactly. Auto requires an observed auto flag, not a fixed-value promise. Readback comparison does not authenticate capture provenance or qualify a received camera. No provider call, path, endpoint command or control write originates from this display."));
    return box;
  }

  function commissioning() {
    const fragment = document.createDocumentFragment();
    const view = state.view.commissioning_rehearsal || {};
    const intro = card("Durable commissioning rehearsal", "Synthetic workflow only. This separate REHEARSAL session cannot qualify a physical camera, arm or board.");
    intro.append(badge(view.status), element("p", "", view.next_step || "Initialize explicitly."),
      facts(view, ["stages", "assessment", "selected_camera", "camera_settings", "capture_dataset", "camera_process", "camera_fault_diagnostic", "camera_configuration", "optics_evaluation", "arm_identity_evaluation", "power_evaluation", "arm_feedback_evaluation", "arm_feedback_process", "reference_evaluation", "noncontact_evaluation", "discovery", "reopen_result", "next_step", "limitations"]), element("p", "caption", view.limitations || ""));
    if (view.assessment) intro.append(heading("Exact assessment awaiting review"), facts(view.assessment));
    if (view.selected_camera) intro.append(heading("Reviewed synthetic candidate"), facts(view.selected_camera));
    if (view.camera_settings) intro.append(heading("Prepared synthetic settings"), facts({
      brightness_offset: view.camera_settings.settings?.brightness_offset,
      policy: view.camera_settings.settings?.exposure_policy,
      settings_epoch: view.camera_settings.settings_epoch,
    }));
    if (view.capture_dataset) {
      const capture = view.capture_dataset;
      intro.append(heading("Retained binary rehearsal"), facts({
        status: capture.status, domain: capture.domain,
        campaign_id: capture.verification?.plan?.binding?.campaign_id,
        frames: capture.dataset?.frames, logical_bytes: capture.dataset?.logical_bytes,
        manifest_sha256: capture.dataset?.manifest_sha256,
        physical_authority: false, m1_qualified: false,
      }), element("p", "caption", "This retained dataset is not a live image. Reopening does not load a preview; inspect the Camera page's current image provenance separately. Upsampling does not verify real optics."));
    }
    if (view.camera_process !== null && view.camera_process !== undefined) intro.append(retainedCameraProcess(view.camera_process));
    if (view.camera_fault_diagnostic !== null && view.camera_fault_diagnostic !== undefined) intro.append(retainedCameraFault(view.camera_fault_diagnostic));
    if (view.camera_configuration !== null && view.camera_configuration !== undefined) intro.append(retainedCameraConfiguration(view.camera_configuration));
    if (view.optics_evaluation && typeof view.optics_evaluation === "object") {
      const optics = view.optics_evaluation;
      intro.append(heading("Retained synthetic optics checks"), facts({
        evaluated_stage: optics.stage, outcome: optics.outcome,
        evaluation_sha256: optics.evaluation_sha256,
        selected_inputs_sha256: optics.selected_inputs_sha256,
        physical_authority: false,
      }), element("p", "caption", optics.meaning || "Synthetic reports only; no installed calibration."));
      const checks = element("ul", "stage-list");
      if (Array.isArray(optics.checks)) for (const check of optics.checks.slice(0, 16)) {
        if (!check || typeof check !== "object") continue;
        const item = element("li");
        item.append(element("span", "", human(check.check_id)), badge(check.passed === true ? "CHECK_PASSED_REHEARSAL" : "BLOCKED"));
        const detail = element("details"), summary = element("summary", "", "Observed check data");
        detail.append(summary, element("p", "caption", check.meaning || ""), element("pre", "json-view", text(check.observed)));
        item.append(detail); checks.append(item);
      }
      intro.append(checks, element("p", "caption", "These inputs are sealed synthetic intrinsics or nominal rendered JPEGs. The stage-6 camera dataset is a verified dependency only, not the evaluated pixels. Reopening verifies reports without rerunning probes."));
    }
    if (view.arm_identity_evaluation !== null && view.arm_identity_evaluation !== undefined) intro.append(retainedArmChecks(
      view.arm_identity_evaluation, "Retained synthetic arm-identity checks", ["arm_identity"],
      "Physical arm identity and firmware are unverified. Injected metadata and a synthetic chassis label are not USB/serial enumeration, a received-unit inspection, or an arm connection."));
    if (view.power_evaluation !== null && view.power_evaluation !== undefined) intro.append(retainedArmChecks(
      view.power_evaluation, "Retained synthetic power/startup checks", ["power_safety", "power_on_observation"],
      "Physical actuator energy, power-off state, startup motion and firmware are unverified. This report is not a power-state observation. No power-on, power-off, reset or firmware control is provided here."));
    if (view.arm_feedback_evaluation !== null && view.arm_feedback_evaluation !== undefined) intro.append(retainedFeedback(view.arm_feedback_evaluation));
    if (view.arm_feedback_process !== null && view.arm_feedback_process !== undefined) intro.append(retainedArmProcess(view.arm_feedback_process));
    if (view.reference_evaluation !== null && view.reference_evaluation !== undefined) intro.append(retainedReference(view.reference_evaluation));
    if (view.noncontact_evaluation !== null && view.noncontact_evaluation !== undefined) intro.append(retainedNoncontact(view.noncontact_evaluation));
    if (view.stages?.length) {
      const list = element("ol", "stage-list");
      view.stages.forEach((stage) => {
        const item = element("li"); item.append(element("span", "", human(stage.stage)), badge(stage.state)); list.append(item);
      });
      intro.append(heading("Separate rehearsal stage journal"), list);
    }
    fragment.append(intro, reopening(view), actions("commissioning"));
    return fragment;
  }
  function workspaceGuide(section) {
    // Workflow descriptions are navigation, not another action registry. Counts
    // and destinations come from the same current catalog used by Control Center.
    const guidance = {
      arm: {title: "Arm workspace", description: "Inspect controller identity and rehearse feedback before received-arm commissioning.", steps: [
        ["Inspect", "Read current readiness and exact controller metadata. A COM-port name is not an established connection."],
        ["Rehearse", "Use explicitly offered synthetic feedback or movement checks. They do not initialize or move the received arm."],
        ["Review", "Inspect the attempt, errors and cleanup. Separately gated physical diagnostics do not release general connection, motion or contact."]]},
      board: {title: "Board & test workspace", description: "Compare the software's nominal placemat layout and baseline results with the build.", steps: [
        ["Inspect layout", "Read source-bound dimensions and device positions below. This is a drawing, not a camera measurement."],
        ["Run software checks", "Browse the Board controls. Host/software baselines also live on Overview; each test needs its own preview."],
        ["Review limits", "Inspect detailed checks and failures. Nominal geometry does not verify assembled placement, reach or contact clearance."]]},
      tasks: {title: "Task workspace", description: "Compile individual keyboard targets or Android tap targets, then inspect a short nominal simulation.", steps: [
        ["Choose a target", "Select keyboard or phone and enter non-sensitive text. Compile produces a semantic plan, not a hardware command."],
        ["Simulate", "Run a separately previewed short task. Read path feasibility and failed checks, not just the worker's success status."],
        ["Keep the boundary", "The task model still uses legacy arm-mounted-camera calibration. Static-camera validation and physical typing/tapping are not released."]]},
      diagnostics: {title: "Evidence workspace", description: "Review retained results and preserve diagnostics in the assigned workspace folder.", steps: [
        ["Inspect the attempt", "Use Activity & results for exact errors, remediation and explicitly loaded full results. A timeout does not prove zero effects."],
        ["Choose the export", "General logs and dedicated original/attempt exports are separate controls. Inspect each description for what it preserves."],
        ["Verify the receipt", "After export, check its operation result and receipt below. History is bounded; export before closing. Never replay an action to repair its log."]]},
    };
    const value = guidance[section];
    const box = card(value.title, value.description); box.id = section + "-workspace-guide";
    const catalog = controlCatalog(), entries = catalog?.filter(row => row.section === section);
    const counts = catalog && catalog.every(row => row.valid)
      ? `${entries.length} registered forms · ${entries.filter(row => row.offered).length} offered by the current service. Offered is not hardware-ready.`
      : "Current form counts unavailable. Inspect Control Center and service holds; no readiness is inferred.";
    box.append(element("p", "caption", counts));
    const list = element("ol", "workspace-guide-steps");
    for (const [title, explanation] of value.steps) {
      const item = element("li"); item.append(element("strong", "", title), element("p", "", explanation)); list.append(item);
    }
    const buttons = element("div", "button-row");
    const browse = element("button", "button secondary", "Browse " + pages[section] + " controls"); browse.type = "button";
    browse.onclick = () => { state.controlDirectory = {query: "", section, availability: "all", page: 0}; navigate("controls"); };
    const results = element("button", "button secondary", "Review " + pages[section] + " results"); results.type = "button";
    results.onclick = () => { state.activityDirectory = {query: "", section, status: "all", page: 0}; navigate("activity"); };
    buttons.append(browse, results);
    if (section !== "diagnostics") {
      const exports = element("button", "button secondary", "Go to exports"); exports.type = "button"; exports.onclick = () => navigate("diagnostics"); buttons.append(exports);
    }
    box.append(list, buttons, element("p", "caption", "These shortcuts only navigate. They do not select a device, prepare a ticket or run an action."));
    return box;
  }
  function overview() {
    const fragment = document.createDocumentFragment(), stats = element("div", "grid three");
    for (const [title, value] of [["Camera", state.view.camera], ["Arm", state.view.arm], ["Session", state.view]]) {
      const box = card(null); box.append(element("div", "card-label", title));
      box.append(element("div", "stat", human(value?.status || value?.state || "Not connected")));
      box.append(element("p", "caption", value?.description || (title === "Session" ? state.view.session_id || "No session" : "Explicit reviewed actions only")));
      if (value?.verification) box.append(badge(value.verification)); stats.append(box);
    }
    fragment.append(stats);
    const next = card("Your next step", typeof state.view.next_step === "object" ? text(state.view.next_step) : state.view.next_step || "Choose a device page, inspect the prerequisites and preview the next eligible action.");
    const buttons = element("div", "button-row");
    for (const [name, label] of [["controls", "Find any control"], ["commissioning", "Guided rehearsal"], ["camera", "Set up camera"], ["arm", "Set up arm"], ["diagnostics", "Review & export logs"]]) {
      const button = element("button", "button secondary", label); button.onclick = () => navigate(name); buttons.append(button);
    }
    next.append(buttons);
    const procedure = element("details");
    procedure.append(element("summary", "", "How to operate this workbench"));
    const steps = element("ol", "guide");
    for (const line of ["Choose the component or search Control Center. Read current holds; opening a form performs no action.", "Enter required fields deliberately. Preview action asks the service for the exact effects and a short-lived ticket; it does not execute it.", "Review the ticket and explicitly confirm only the intended operation. Cancel discards an unexecuted preview, not a running hardware operation.", "Inspect Activity & results for the assessment, failures and cleanup. Export needed evidence before closing. Never automatically retry an uncertain operation."])
      steps.append(element("li", "", line));
    procedure.append(steps); next.append(procedure);
    fragment.append(heading("Guided setup"), next, actions("overview"));
    if (state.view.mode === "physical") {
      const value = state.view.physical_source_preflight;
      const box = card("Actual source preflight", "File observations and durable storage only. This is separate from the synthetic rehearsal; it never opens a camera or arm.");
      box.append(element("p", "notice warning", "No device connection is established by this file-only check. The actual physical connection and power state remain unverified; a coherent source report does not complete a physical stage."));
      if (value && value.schema === "rocell.physical_source_preflight_view.v1"
          && value.composition === "PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO" && value.replay_allowed === false
          && ["NOT_STARTED", "RUNNING", "HELD", "FILE_CHECKS_COHERENT", "PUBLICATION_PENDING", "PUBLICATION_HELD"].includes(value.status)
          && value.physical_authority === false && value.canonical_stage_pass === false
          && value.device_io_performed === false && value.power_state === "UNKNOWN") {
        box.append(badge(value.status), facts({session_id: value.session_id, directory: value.directory,
          canonical_stage_state: value.canonical_stage_state, power_state: value.power_state}),
          element("p", "caption", value.next_step));
        if (value.report) box.append(detail(value.report, "Inspect source checks and remaining physical holds"));
        if (value.attempt) box.append(detail(value.attempt, "Inspect durable file-only attempt"));
        if (value.error) box.append(detail(value.error, "Inspect source-preflight error"));
      } else box.append(badge("SOURCE_PREFLIGHT_SUMMARY_UNAVAILABLE"));
      box.append(element("p", "caption", "Nothing runs from viewing this card. Preview and confirm the explicit file-check action above, then use Diagnostics & exports."));
      fragment.append(box);
    }
    if (state.view.blockers?.length) {
      const box = card("Current holds", "A hold can be expected during rehearsal. Passing a simulation never qualifies physical operation.");
      const list = element("ul", "action-blockers");
      for (const hold of state.view.blockers) list.append(element("li", "", typeof hold === "object" ? hold.message || hold.reason || text(hold) : hold));
      box.append(list); fragment.append(box);
    }
    if (state.view.stages?.length) {
      const box = card("Onboarding progress"), list = element("ol", "stage-list");
      state.view.stages.forEach((stage, index) => {
        const row = element("li"), label = element("div");
        label.append(element("strong", "", stage.label || stage.title || stage.name || human(stage.stage_id)));
        if (stage.description || stage.next_step) label.append(element("p", "", stage.description || stage.next_step));
        row.append(element("span", "stage-number", index + 1), label, badge(stage.state || stage.status || "pending")); list.append(row);
      }); box.append(list); fragment.append(box);
    }
    return fragment;
  }

  function validatedDeviceMetadata(data) {
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const safeText = value => typeof value === "string" && value.length > 0 && new TextEncoder().encode(value).length <= 2048 && !/[\x00-\x1f\x7f\ud800-\udfff]/u.test(value);
    const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    const optionalText = value => value === null || safeText(value);
    const codes = value => Array.isArray(value) && value.length <= 32 && new Set(value).size === value.length && value.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(code));
    const followups = ["VERIFY_RECEIVED_MODEL_AND_UNIT", "RESOLVE_UNIQUE_IDENTITY_AND_NATIVE_PREOPEN_RECHECK", "QUALIFY_NATIVE_BACKEND_AND_CONNECTION_CONTRACT", "COMPLETE_CANONICAL_STAGE_AND_PHYSICAL_RELEASE_GATES"];
    const flags = value => value.physical_authority === false && value.connected === false && value.qualified === false && value.persistent_binding === false;
    let valid = exact(data, ["schema", "status", "provenance", "report_sha256", "operation_id", "devices", "physical_authority", "connected", "qualified", "persistent_binding", "invalidation_reason"])
      && data.schema === "rocell.wizard_device_selection.v1" && flags(data)
      && ["NO_INVENTORY", "METADATA_CANDIDATES_AVAILABLE", "METADATA_REVIEW_RECORDED", "INVALIDATED"].includes(data.status)
      && exact(data.provenance, ["mode", "session_id", "source_sha256", "platform_system", "captured_at_unix_ns", "scope"])
      && ["rehearsal", "physical"].includes(data.provenance.mode) && safeText(data.provenance.session_id) && digest(data.provenance.source_sha256)
      && optionalText(data.provenance.platform_system) && data.provenance.scope === "METADATA_SNAPSHOT_ONLY"
      // Nanoseconds are retained evidence, not an exactly representable JS clock.
      // They are never rendered as a number, freshness proof or device timestamp.
      && (data.provenance.captured_at_unix_ns === null || (Number.isInteger(data.provenance.captured_at_unix_ns) && data.provenance.captured_at_unix_ns >= 0 && data.provenance.captured_at_unix_ns <= 2 ** 63 - 1))
      && (data.report_sha256 === null || digest(data.report_sha256)) && optionalText(data.operation_id)
      && optionalText(data.invalidation_reason) && exact(data.devices, ["CAMERA", "SERIAL"]);
    if (valid) for (const deviceClass of ["CAMERA", "SERIAL"]) {
      const device = data.devices[deviceClass];
      valid = exact(device, ["candidates", "review"]) && Array.isArray(device.candidates) && device.candidates.length <= 128;
      if (!valid) break;
      const ids = new Set();
      for (const candidate of device.candidates) {
        valid = exact(candidate, ["choice_id", "display_name", "vid", "pid", "unit_serial", "source", "identity_blockers", "candidate_sha256"])
          && safeText(candidate.choice_id) && !ids.has(candidate.choice_id) && safeText(candidate.display_name)
          && [candidate.vid, candidate.pid].every(value => value === null || (typeof value === "string" && /^[a-f0-9]{4}$/.test(value)))
          && optionalText(candidate.unit_serial) && digest(candidate.candidate_sha256) && codes(candidate.identity_blockers)
          && (deviceClass === "CAMERA" ? ["WINDOWS_PNP", "LINUX_SYSFS"] : ["PYSERIAL_LIST_PORTS", "INJECTED_SERIAL_ENUMERATOR"]).includes(candidate.source);
        if (!valid) break;
        ids.add(candidate.choice_id);
      }
      if (!valid) break;
      if (device.review !== null) {
        const review = device.review;
        valid = exact(review, ["choice_id", "candidate_sha256", "reviewer_id", "report_sha256", "operation_id", "status", "connected", "qualified", "persistent_binding", "physical_authority", "followup_requirements"])
          && flags(review) && review.status === "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION"
          && safeText(review.reviewer_id) && review.report_sha256 === data.report_sha256 && review.operation_id === data.operation_id
          && device.candidates.some(candidate => candidate.choice_id === review.choice_id && candidate.candidate_sha256 === review.candidate_sha256)
          && Array.isArray(review.followup_requirements) && review.followup_requirements.length === followups.length
          && new Set(review.followup_requirements).size === followups.length && followups.every(code => review.followup_requirements.includes(code));
      }
      if (!valid) break;
    }
    if (valid && ["METADATA_CANDIDATES_AVAILABLE", "METADATA_REVIEW_RECORDED"].includes(data.status)) valid = digest(data.report_sha256) && safeText(data.operation_id)
      && data.invalidation_reason === null && (["CAMERA", "SERIAL"].some(key => data.devices[key].review !== null) === (data.status === "METADATA_REVIEW_RECORDED"));
    if (valid && ["NO_INVENTORY", "INVALIDATED"].includes(data.status)) valid = data.report_sha256 === null && data.operation_id === null
      && data.provenance.platform_system === null && data.provenance.captured_at_unix_ns === null
      && (data.status === "NO_INVENTORY" ? data.invalidation_reason === null : safeText(data.invalidation_reason))
      && ["CAMERA", "SERIAL"].every(key => data.devices[key].candidates.length === 0 && data.devices[key].review === null);
    return valid ? data : null;
  }

  function deviceMetadata(kind) {
    const title = kind === "CAMERA" ? "Camera metadata candidate review" : "Arm serial metadata candidate review";
    const box = card(title, "Read-only inventory snapshot — not a current connection or received-model verification.");
    box.append(element("span", "badge hold", "NOT CONNECTED"), element("span", "badge hold", "NOT QUALIFIED"),
      element("p", "notice warning", "Received model: UNKNOWN. A display name, USB VID/PID, unit serial or metadata acknowledgment cannot qualify the camera or arm. No persistent device binding is created."));
    const data = state.view.device_selection;
    const valid = validatedDeviceMetadata(data) !== null;
    if (!valid) {
      box.append(element("p", "notice warning", data === undefined || data === null ? "No metadata inventory snapshot is available. Run an eligible explicit inventory action; no candidate is selected." : "NOT VERIFIED: Device metadata is inconsistent or exceeds display bounds. Inspect diagnostics; no candidate or review is inferred."));
    } else {
      box.append(facts({snapshot_status: data.status, mode: data.provenance.mode, scope: data.provenance.scope,
        report_sha256: data.report_sha256 || "NOT_RECORDED", operation_id: data.operation_id || "NOT_RECORDED",
        source_sha256: data.provenance.source_sha256, platform_system: data.provenance.platform_system || "NOT_RECORDED",
        captured_timestamp: data.provenance.captured_at_unix_ns === null ? "NOT_RECORDED" : "RETAINED_NOT_INTERPRETED"}));
      if (data.invalidation_reason) box.append(element("p", "notice warning", data.invalidation_reason));
      if (data.status === "INVALIDATED") box.append(element("p", "notice warning", "This metadata snapshot was invalidated. No prior review is current; obtain a new explicit snapshot before reviewing a candidate."));
      else {
        const device = data.devices[kind];
        if (!device.candidates.length) box.append(element("p", "caption", "No candidates in this snapshot. This is not evidence that the device is absent or disconnected now."));
        for (const candidate of device.candidates) {
          const item = element("details"); item.append(element("summary", "", `${candidate.display_name} — ${candidate.identity_blockers.length} identity blockers`));
          item.append(facts({choice_id: candidate.choice_id, candidate_sha256: candidate.candidate_sha256, metadata_name: candidate.display_name,
            vid: candidate.vid || "NOT_RECORDED", pid: candidate.pid || "NOT_RECORDED", unit_serial: candidate.unit_serial || "NOT_RECORDED", source: candidate.source}));
          if (candidate.identity_blockers.length) { const list = element("ul", "action-blockers"); for (const code of candidate.identity_blockers) list.append(element("li", "", code)); item.append(heading("Identity blockers"), list); }
          else item.append(element("p", "caption", "No identity blocker was recorded in this snapshot. Received identity, connection and qualification remain unverified."));
          box.append(item);
        }
        if (device.review === null) box.append(element("p", "notice warning", "No metadata review recorded for this device. Nothing is automatically selected."));
        else { box.append(heading("Explicit metadata acknowledgment — not a connection"), facts(device.review, ["followup_requirements"])); const list = element("ul", "guide"); for (const code of device.review.followup_requirements) list.append(element("li", "", code)); box.append(list); }
      }
    }
    box.append(element("p", "caption", "Opening or refreshing this view does not discover, select, preview, connect or open a device. Use the separate inventory and review actions with an explicit choice and metadata-only acknowledgment. This review cannot authorize capture, serial access, power changes, motion or contact."));
    return box;
  }

  function validatedNativeArmMetadata(value, view) {
    // A cached correlation is not an identity-to-open permit. Only availability
    // labels and retained hashes reach this panel; no raw COM/interface paths.
    const v = cameraConfigurationValidators(), flags = ["connected", "qualified", "physical_authority"];
    const fields = ["persistent_port_path", "persistent_instance_id", "port_name", "vid", "pid", "driver_provider", "driver_service", "driver_version", "driver_inf"];
    const codes = new Set(["GENERIC_REVIEW_BLOCKED", "GENERIC_COLLECTION_INCOMPLETE", "NATIVE_COLLECTION_INCOMPLETE", "GENERIC_UNIT_NOT_PRESENT", "GENERIC_UNIT_AMBIGUOUS", "GENERIC_CANDIDATE_CHANGED", "GENERIC_PORT_AMBIGUOUS", "NATIVE_MAPPING_NOT_PRESENT", "NATIVE_MAPPING_AMBIGUOUS", "NATIVE_PROPERTIES_INCOMPLETE", "NATIVE_REQUIRED_FIELD_MISSING", "NATIVE_PORT_AMBIGUOUS", "NATIVE_PERSISTENT_PATH_AMBIGUOUS", "NATIVE_INSTANCE_AMBIGUOUS", "INVALID_COM_METADATA"]);
    const id = item => typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(item);
    if (!v.exact(value, ["schema", "status", "report", "invalidation_reason", ...flags])
      || value.schema !== "rocell.wizard_native_arm_metadata_view.v1" || !flags.every(key => value[key] === false)
      || !["NOT_INSPECTED", "CURRENT", "HISTORICAL_HELD"].includes(value.status)
      || !(value.invalidation_reason === null || ["ARM_METADATA_CONTEXT_CHANGED", "ARM_METADATA_NOT_PUBLISHED", "ARM_METADATA_ACTION_FAILED", "DIAGNOSTIC_LOG_FAILED", "SOURCE_CHANGED", "APPLICATION_CLOSED"].includes(value.invalidation_reason))
      || (value.status === "NOT_INSPECTED" && (value.report !== null || value.invalidation_reason !== null))
      || (value.status === "CURRENT" && (value.report === null || value.invalidation_reason !== null))) return null;
    const report = value.report;
    if (report === null) return value;
    if (!v.exact(report, ["schema", "status", "binding", "provenance", "report_sha256", "snapshot_sha256", "counts", "native_fields", "blockers", "persistent_binding", ...flags])
      || report.schema !== "rocell.wizard_native_arm_metadata_summary.v1" || !flags.every(key => report[key] === false) || report.persistent_binding !== false
      || !["METADATA_CORRELATED", "HELD"].includes(report.status) || !v.digest(report.report_sha256) || !v.digest(report.snapshot_sha256)
      || !v.exact(report.binding, ["mode", "session_id", "source_sha256", "operation_id", "generic_review_sha256", "generic_report_sha256", "generic_candidate_sha256", "generic_inventory_operation_id"])
      || !["physical", "rehearsal"].includes(report.binding.mode) || !["session_id", "operation_id", "generic_inventory_operation_id"].every(key => id(report.binding[key]))
      || !["source_sha256", "generic_review_sha256", "generic_report_sha256", "generic_candidate_sha256"].every(key => v.digest(report.binding[key]))
      || !v.exact(report.provenance, ["origin", "native_source", "unit_serial_origin"])
      || report.provenance.unit_serial_origin !== "GENERIC_SERIAL_INVENTORY_NOT_USB_DESCRIPTOR"
      || (report.binding.mode === "physical" ? report.provenance.origin !== "PHYSICAL_OBSERVATION" || report.provenance.native_source !== "WINDOWS_CM_METADATA" : report.provenance.origin !== "SYNTHETIC_REHEARSAL" || report.provenance.native_source !== "INJECTED_CM_METADATA")
      || !v.exact(report.counts, ["serial_candidates", "native_observations", "generic_matches", "native_matches"])
      || !Object.values(report.counts).every(count => v.integer(count, 0, 128))
      || report.counts.generic_matches > report.counts.serial_candidates || report.counts.native_matches > report.counts.native_observations
      || !v.exact(report.native_fields, fields) || !Object.values(report.native_fields).every(status => ["OBSERVED", "MISSING", "NOT_VERIFIED"].includes(status))
      || !Array.isArray(report.blockers) || report.blockers.length > 32 || new Set(report.blockers).size !== report.blockers.length || !report.blockers.every(code => codes.has(code))
      || ((report.status === "HELD") !== (report.blockers.length > 0))
      || (report.status === "METADATA_CORRELATED" && (report.counts.generic_matches !== 1 || report.counts.native_matches !== 1 || !Object.values(report.native_fields).every(status => status === "OBSERVED")))) return null;
    if (value.status === "CURRENT") {
      const generic = validatedDeviceMetadata(view.device_selection), binding = report.binding, review = generic?.devices.SERIAL.review;
      if (!generic || !review || binding.mode !== view.mode || binding.session_id !== view.session_id || binding.source_sha256 !== view.source_binding_sha256
        || generic.provenance.mode !== binding.mode || generic.provenance.session_id !== binding.session_id || generic.provenance.source_sha256 !== binding.source_sha256
        || binding.generic_candidate_sha256 !== review.candidate_sha256 || binding.generic_report_sha256 !== review.report_sha256
        || binding.generic_inventory_operation_id !== review.operation_id) return null;
    }
    return value;
  }

  function nativeArmMetadata() {
    const box = card("Native arm metadata correlation", "Present-interface and driver-field observations, not a serial connection.");
    box.append(element("span", "badge hold", "NOT_CONNECTED / NOT_QUALIFIED"), element("p", "notice warning", "Received arm model, firmware, boot behavior and actuator-power isolation remain unverified. Metadata correlation does not create a ReviewedControllerBinding, persistent open permission or motion authority."));
    const input = state.view.native_arm_metadata, value = validatedNativeArmMetadata(input, state.view);
    if (!value) {
      box.append(element("p", "notice warning", input === undefined || input === null ? "No native arm metadata report is available. Review a SERIAL candidate, then use an eligible explicit metadata action." : "NATIVE_ARM_METADATA_NOT_VERIFIED: Inconsistent or unbounded cached report withheld. Inspect diagnostics; no current correlation is inferred."));
    } else {
      box.append(element("p", "", `Publication: ${value.status}`));
      if (value.invalidation_reason) box.append(element("p", "notice warning", value.invalidation_reason));
      if (value.status === "HISTORICAL_HELD") box.append(element("p", "notice warning", "Historical metadata only. Original source, launch and candidate remain attached; these observations are not the current reviewed device. No automatic reinspection, reconnect or identity-to-open authorization."));
      if (!value.report) box.append(element("p", "caption", "No retained native report. No device absence, identity or driver state is inferred."));
      else {
        const report = value.report;
        box.append(element("p", "", `Correlation result: ${report.status}`), element("p", "notice warning", report.binding.mode === "rehearsal" ? "INCAPABLE REHEARSAL: Injected metadata only; no host device was observed." : "WINDOWS METADATA OBSERVATION ONLY: A retained observation is not proof of the currently connected unit or an atomically bound open handle."));
        for (const [key, item] of Object.entries({...report.binding, ...report.provenance, report_sha256: report.report_sha256, snapshot_sha256: report.snapshot_sha256})) box.append(element("p", "", `${key}: ${item}`));
        box.append(heading("Collection and matching counts"));
        for (const [key, count] of Object.entries(report.counts)) box.append(element("p", "", `${key}: ${count}`));
        box.append(heading("Native field availability — values are not exposed"));
        for (const [field, status] of Object.entries(report.native_fields)) box.append(element("p", "", `${field}: ${status}`));
        if (report.blockers.length) { const list = element("ul", "action-blockers"); for (const code of report.blockers) list.append(element("li", "", code)); box.append(heading("Correlation holds"), list); }
        else box.append(element("p", "caption", "Exactly one generic/native metadata match was retained. This is not connection, driver qualification, received-model verification or permission to open a port."));
      }
    }
    box.append(element("p", "caption", "Unit serial is generic inventory metadata, not a native USB-descriptor observation. Export original diagnostics to the assigned folder. Viewing never enumerates metadata, selects a port, prepares an action or sends serial bytes."));
    return box;
  }

  function validatedNativeEnrollment(data, generic) {
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const textValue = (value, limit = 1024) => typeof value === "string" && value.length > 0 && new TextEncoder().encode(value).length <= limit && !/[\x00-\x1f\x7f\ud800-\udfff]/u.test(value);
    const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    const codes = value => Array.isArray(value) && value.length <= 32 && value.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(code)) && new Set(value).size === value.length;
    const empty = ["PROVIDER_UNAVAILABLE", "NO_INVENTORY", "INVALIDATED"];
    if (!exact(data, ["schema", "status", "provenance", "inventory_sha256", "inventory_operation_id", "generic_candidate_sha256", "generic_report_sha256", "generic_operation_id", "candidates", "identity", "review", "blockers", "connected", "qualified", "persistent_binding", "physical_authority", "invalidation_reason"])
      || data.schema !== "rocell.wizard_native_camera_enrollment.v1"
      || ![...empty, "ENDPOINT_CHOICES_AVAILABLE", "IDENTITY_RETAINED", "ENDPOINT_METADATA_REVIEWED", "REVIEW_HELD"].includes(data.status)
      || ["connected", "qualified", "persistent_binding", "physical_authority"].some(key => data[key] !== false)
      || !exact(data.provenance, ["mode", "session_id", "source_sha256", "provider_provenance", "helper_sha256", "scope"])
      || !["rehearsal", "physical"].includes(data.provenance.mode) || !textValue(data.provenance.session_id, 2048) || !digest(data.provenance.source_sha256)
      || data.provenance.scope !== "NATIVE_ENDPOINT_METADATA_ONLY" || ![null, "INCAPABLE_FIXTURE", "WINDOWS_NATIVE_METADATA"].includes(data.provenance.provider_provenance)
      || !(data.provenance.helper_sha256 === null || digest(data.provenance.helper_sha256))
      || ((data.provenance.provider_provenance === null) !== (data.provenance.helper_sha256 === null))
      || !codes(data.blockers) || !(data.invalidation_reason === null || textValue(data.invalidation_reason, 512))
      || !Array.isArray(data.candidates) || data.candidates.length > 128) return null;
    const ids = new Set();
    for (const row of data.candidates) {
      if (!exact(row, ["choice_id", "friendly_name", "endpoint_sha256"]) || !textValue(row.choice_id, 128) || ids.has(row.choice_id)
        || !textValue(row.friendly_name) || !digest(row.endpoint_sha256)) return null;
      ids.add(row.choice_id);
    }
    if (empty.includes(data.status)) {
      if (data.candidates.length || data.identity !== null || data.review !== null || ["inventory_sha256", "inventory_operation_id", "generic_candidate_sha256", "generic_report_sha256", "generic_operation_id"].some(key => data[key] !== null)) return null;
      if (data.status === "PROVIDER_UNAVAILABLE" && data.provenance.provider_provenance !== null) return null;
      return data;
    }
    const current = validatedDeviceMetadata(generic);
    const cameraReview = current?.devices.CAMERA.review;
    // Exact references link the two cached views. A friendly name, matching
    // hash alone or an old generic review is never substituted for this link.
    if (!current || !cameraReview || data.provenance.provider_provenance === null
      || data.provenance.mode !== current.provenance.mode || data.provenance.session_id !== current.provenance.session_id || data.provenance.source_sha256 !== current.provenance.source_sha256
      || !digest(data.inventory_sha256) || !textValue(data.inventory_operation_id, 128)
      || data.generic_candidate_sha256 !== cameraReview.candidate_sha256 || data.generic_report_sha256 !== cameraReview.report_sha256 || data.generic_operation_id !== cameraReview.operation_id) return null;
    if (data.identity !== null) {
      const identity = data.identity;
      if (!exact(identity, ["choice_id", "endpoint_sha256", "identity_sha256", "operation_id", "exact_endpoint_observed", "generic_device_match", "container_match", "blockers"])
        || !data.candidates.some(row => row.choice_id === identity.choice_id && row.endpoint_sha256 === identity.endpoint_sha256)
        || !digest(identity.identity_sha256) || !textValue(identity.operation_id, 128) || !codes(identity.blockers)
        || ["exact_endpoint_observed", "generic_device_match", "container_match"].some(key => typeof identity[key] !== "boolean")) return null;
    }
    if (data.status === "ENDPOINT_CHOICES_AVAILABLE") return data.identity === null && data.review === null ? data : null;
    if (data.identity === null) return null;
    if (data.status === "IDENTITY_RETAINED") return data.review === null ? data : null;
    const review = data.review;
    if (!exact(review, ["choice_id", "reviewer_id", "binding_sha256", "status", "physical_authority"]) || review.physical_authority !== false
      || review.choice_id !== data.identity.choice_id || !textValue(review.reviewer_id, 2048)) return null;
    if (data.status === "ENDPOINT_METADATA_REVIEWED") return review.status === "REVIEWED_ENDPOINT_METADATA_ONLY" && digest(review.binding_sha256)
      && data.identity.exact_endpoint_observed && data.identity.generic_device_match && data.identity.container_match && data.identity.blockers.length === 0 ? data : null;
    return review.status === "METADATA_ACKNOWLEDGED_BUT_HELD" && review.binding_sha256 === null ? data : null;
  }

  function nativeCameraEnrollment() {
    const box = card("Native camera endpoint enrollment", "Metadata-only inventory, exact endpoint identity and explicit review. No camera activation.");
    box.append(element("span", "badge hold", "NOT CONNECTED"), element("span", "badge hold", "NOT QUALIFIED"),
      element("p", "notice warning", "No persistent-unit binding or physical authority. Exact endpoint mapping is not proof of received camera model, USB3 topology/link speed, camera readiness or permission to capture. Names never establish identity."));
    const input = state.view.native_camera_enrollment;
    const data = validatedNativeEnrollment(input, state.view.device_selection);
    if (!data) box.append(element("p", "notice warning", input === null || input === undefined ? "No native endpoint enrollment snapshot is available. Inspect the eligible actions and helper registration holds; no native endpoint is selected." : "NOT VERIFIED: Native enrollment metadata is inconsistent, stale or exceeds display bounds. Inspect diagnostics; no endpoint review or binding is inferred."));
    else {
      box.append(facts({snapshot_status: data.status, mode: data.provenance.mode, scope: data.provenance.scope,
        provider_provenance: data.provenance.provider_provenance || "NOT_REGISTERED", helper_sha256: data.provenance.helper_sha256 || "NOT_REGISTERED",
        source_sha256: data.provenance.source_sha256, inventory_sha256: data.inventory_sha256 || "NOT_RECORDED", inventory_operation_id: data.inventory_operation_id || "NOT_RECORDED",
        generic_candidate_sha256: data.generic_candidate_sha256 || "NOT_RECORDED", generic_report_sha256: data.generic_report_sha256 || "NOT_RECORDED", generic_operation_id: data.generic_operation_id || "NOT_RECORDED"}));
      if (data.status === "PROVIDER_UNAVAILABLE") box.append(element("p", "notice warning", "Native metadata helper registration is required. No provider is registered; this view does not search for, install or execute a helper."));
      if (data.invalidation_reason) box.append(heading("Latest reset or hold"), element("p", "notice warning", data.invalidation_reason));
      if (data.status === "INVALIDATED") box.append(element("p", "notice warning", "The native enrollment was invalidated. Old endpoint choices, identity and review are not current; no operation is replayed."));
      if (!data.candidates.length) box.append(element("p", "caption", "No native endpoint choices retained. This is not a live absence check."));
      for (const candidate of data.candidates) { const row = element("details"); row.append(element("summary", "", candidate.friendly_name), facts(candidate)); box.append(row); }
      box.append(element("p", "caption", "Identical names remain distinct opaque choices. Compare the exact endpoint hashes and identity evidence; no first-device or same-name fallback is used. Duplicate endpoint identity may remain ambiguous."));
      if (data.identity) { box.append(heading("Retained endpoint identity metadata"), facts(data.identity, ["blockers"])); const list = element("ul", "action-blockers"); for (const code of data.identity.blockers) list.append(element("li", "", code)); box.append(list, element("p", "caption", "Mapping observed, generic-device match and container match are separate metadata results. False may mean unavailable or inconsistent evidence; it is not a received-model or connectivity verdict.")); }
      else box.append(element("p", "caption", "No endpoint identity retained. Run an eligible explicit identity action; browsing never performs the lookup."));
      if (data.review) box.append(heading(data.status === "REVIEW_HELD" ? "Explicit native review remains held" : "Explicit native endpoint metadata review"), facts({...data.review, binding_meaning: "DIAGNOSTIC_METADATA_ONLY_NOT_PERSISTENT_UNIT_BINDING"}));
      else box.append(element("p", "caption", "No native review recorded. Nothing is automatically selected or acknowledged."));
      if (data.blockers.length) { box.append(heading("Remaining enrollment and qualification holds")); const list = element("ul", "action-blockers"); for (const code of data.blockers) list.append(element("li", "", code)); box.append(list); }
    }
    box.append(element("p", "caption", "This card performs no inventory, identity lookup, review, helper call or camera activation. Use the separate actions with explicit metadata-only consent, preview and execution. These operations do not grant capture, calibration, power, motion or contact authority."));
    return box;
  }

  function validatedCameraHelper(data) {
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const textValue = (value, limit = 128) => typeof value === "string" && value.length > 0 && new TextEncoder().encode(value).length <= limit && !/[\x00-\x1f\x7f\ud800-\udfff]/u.test(value);
    const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    const codes = value => Array.isArray(value) && value.length <= 32 && value.every(code => typeof code === "string" && /^[A-Z][A-Z0-9_]{0,95}$/.test(code)) && new Set(value).size === value.length;
    if (!exact(data, ["schema", "status", "provenance", "inspection", "review", "blockers", "allowed_operations", "probe_allowed", "capture_allowed", "connected", "qualified", "physical_authority", "invalidation_reason"])
      || data.schema !== "rocell.wizard_camera_helper_registration.v1"
      || !["NO_INSPECTION", "INSPECTION_RETAINED", "METADATA_HELPER_REGISTERED", "REVIEW_HELD", "INVALIDATED"].includes(data.status)
      || ["probe_allowed", "capture_allowed", "connected", "qualified", "physical_authority"].some(key => data[key] !== false)
      || !Array.isArray(data.allowed_operations) || data.allowed_operations.length !== 2 || !data.allowed_operations.includes("inventory") || !data.allowed_operations.includes("identity")
      || !codes(data.blockers) || !(data.invalidation_reason === null || textValue(data.invalidation_reason, 512))
      || !exact(data.provenance, ["mode", "session_id", "source_sha256", "scope"])
      || !["rehearsal", "physical"].includes(data.provenance.mode) || !textValue(data.provenance.session_id) || !digest(data.provenance.source_sha256)
      || data.provenance.scope !== "CAMERA_HELPER_METADATA_ONLY") return null;
    if (["NO_INSPECTION", "INVALIDATED"].includes(data.status)) return data.inspection === null && data.review === null ? data : null;
    const inspection = data.inspection;
    if (!exact(inspection, ["catalog_id", "display_name", "catalog_sha256", "inspection_sha256", "operation_id", "operator_id", "inspection_status", "inspection_provenance", "helper_sha256", "eligible_for_metadata_registration", "blockers"])
      || ["catalog_id", "display_name", "operation_id", "operator_id"].some(key => !textValue(inspection[key]))
      || !digest(inspection.catalog_sha256) || !digest(inspection.inspection_sha256) || !(inspection.helper_sha256 === null || digest(inspection.helper_sha256))
      || typeof inspection.eligible_for_metadata_registration !== "boolean" || !codes(inspection.blockers)
      || !["MATCHED_METADATA_CATALOG", "MISSING_FILES", "HASH_DRIFT", "UNSAFE_OR_UNREADABLE"].includes(inspection.inspection_status)
      || inspection.inspection_provenance !== (data.provenance.mode === "rehearsal" ? "INCAPABLE_FIXTURE" : "WORKSPACE_FILE_INSPECTION")
      || (inspection.eligible_for_metadata_registration ? (inspection.inspection_status !== "MATCHED_METADATA_CATALOG" || inspection.helper_sha256 === null) : inspection.helper_sha256 !== null)) return null;
    if (data.status === "INSPECTION_RETAINED") return data.review === null ? data : null;
    const review = data.review;
    if (!exact(review, ["reviewer_id", "review_operation_id", "status", "registration_sha256", "distinct_operator_labels", "physical_authority"])
      || !textValue(review.reviewer_id) || !textValue(review.review_operation_id) || review.reviewer_id === inspection.operator_id
      || review.distinct_operator_labels !== true || review.physical_authority !== false) return null;
    if (data.status === "METADATA_HELPER_REGISTERED") return inspection.eligible_for_metadata_registration && review.status === "METADATA_ONLY_REGISTERED" && digest(review.registration_sha256) ? data : null;
    return !inspection.eligible_for_metadata_registration && review.status === "ACKNOWLEDGED_BUT_HELD" && review.registration_sha256 === null ? data : null;
  }

  function cameraHelperRegistration() {
    const box = card("Camera metadata helper inspection & review", "One fixed catalogued helper; separate file inspection and exact-report review.");
    box.append(element("span", "badge hold", "CAMERA NOT CONNECTED"), element("span", "badge hold", "CAMERA NOT QUALIFIED"),
      element("p", "notice warning", "Metadata registration permits only eligible inventory and identity lookups after separate explicit actions. It does not permit probe or capture; separate purpose-specific runtime gates apply. It does not qualify a camera unit, driver, process containment or a trusted release."));
    const input = state.view.camera_helper_registration;
    const data = validatedCameraHelper(input);
    if (!data) box.append(element("p", "notice warning", input === null || input === undefined ? "No helper inspection snapshot is available. Inspect the fixed catalog through an eligible explicit action; no helper is registered by viewing this page." : "NOT VERIFIED: Helper registration metadata is inconsistent, stale or exceeds display bounds. Inspect diagnostics; no helper registration is inferred."));
    else {
      box.append(facts({status: data.status, mode: data.provenance.mode, scope: data.provenance.scope, source_sha256: data.provenance.source_sha256,
        metadata_operations: "inventory, identity", probe_allowed: false, capture_allowed: false, physical_authority: false}));
      if (data.provenance.mode === "rehearsal") box.append(element("p", "notice warning", "INCAPABLE FIXTURE: rehearsal inspection is synthetic and does not describe installed helper files or register a physical provider."));
      if (data.invalidation_reason) box.append(heading("Latest inspection/review reset or hold"), element("p", "notice warning", data.invalidation_reason));
      if (data.inspection) {
        box.append(heading("Retained fixed-catalog inspection"), facts(data.inspection, ["blockers"]));
        if (data.inspection.blockers.length) { const list = element("ul", "action-blockers"); for (const code of data.inspection.blockers) list.append(element("li", "", code)); box.append(list); }
        if (!data.inspection.eligible_for_metadata_registration) box.append(element("p", "notice warning", "This inspection cannot register the metadata helper. Missing, changed, unsafe or unreadable files remain held; acknowledgment does not repair or install them."));
      } else box.append(element("p", "caption", "No inspection retained. Default physical startup is unregistered. Visiting this page does not discover or hash helper files."));
      if (data.review) {
        box.append(heading(data.status === "REVIEW_HELD" ? "Helper review remains held" : "Exact helper report reviewed for metadata only"), facts(data.review));
        box.append(element("p", "caption", "Distinct operator/reviewer labels are diagnostic audit labels, not proof of authenticated independent people."));
      } else box.append(element("p", "caption", "No helper review recorded. A distinct reviewer label and metadata-only consent are required; no review or consent is automatic."));
      if (data.status === "INVALIDATED") box.append(element("p", "notice warning", "Inspection and review are no longer current. No prior registration is restored or operation replayed."));
      if (data.blockers.length) { box.append(heading("Remaining helper and physical-qualification holds")); const list = element("ul", "action-blockers"); for (const code of data.blockers) list.append(element("li", "", code)); box.append(list); }
    }
    box.append(element("p", "caption", "Matching catalogued files does not establish current full-build provenance, trusted-release status, runtime process containment or driver qualification. No unprojected qualification flag is inferred."),
      element("p", "caption", "This card performs no discovery, file hashing, helper installation or process launch. Use explicit inspect and review actions; any later native metadata lookup requires its own preview, consent and execution. No source activation, probe, capture, power, motion or contact authority is granted."));
    return box;
  }

  function cameraNextStep() {
    const box = card("Camera — next explicit step", "Navigation only. These links open existing forms on Camera or Arm; they do not preview, submit, initialize, reopen or operate a device.");
    box.id = "camera-next-step";
    const catalog = Array.isArray(state.view.actions) ? state.view.actions : [];
    const roster = ["physical_camera_prerequisites", "physical_camera_assess_sources", "physical_camera_review_sources", "physical_source_isolation_files_discover", "physical_source_qualify", "physical_source_qualification_review", "physical_static_contract_begin", "physical_static_contract_collect", "physical_static_contract_review", "physical_camera_receipt_begin",...receivedCameraValidators().actions,"physical_camera_identity_submit","physical_camera_identity_review","physical_camera_identity_export"];
    const eligible = id => {
      const matches = catalog.filter(item => item?.action_id === id);
      const section = id === "inventory_devices" ? "arm" : "camera";
      return matches.length === 1 && matches[0].section === section && matches[0].enabled === true && !state.pending ? matches[0] : null;
    };
    const goToAction = id => {
      const current = (state.view.actions || []).filter(item => item?.action_id === id);
      const section = id === "inventory_devices" ? "arm" : "camera";
      if (state.pending || current.length !== 1 || current[0].section !== section || current[0].enabled !== true) return;
      if (state.page !== section) navigate(section);
      const target = document.getElementById(`${section}-action-${id}`);
      if (target) { target.scrollIntoView({block:"start"}); target.focus({preventScroll:true}); }
    };
    const link = (id, description) => {
      const action=eligible(id); if (!action) return;
      const line=element("p"), anchor=element("a","",action.label || human(id));
      anchor.href=`#${action.section}-action-${id}`; anchor.setAttribute("data-action-target",id);
      anchor.addEventListener("click", event => { event.preventDefault(); goToAction(id); });
      line.append(anchor); if (description) line.append(element("span","caption",` — ${description}`)); box.append(line);
    };
    if(state.view.mode==="rehearsal"&&eligible("camera_rehearsal")){
      box.append(element("p","notice warning","Rehearse the camera workflow with synthetic data. This does not connect or qualify a physical camera."));
      link("camera_rehearsal","Open the existing rehearsal form only; no preview or execution occurs from this link.");return box;
    }
    const settingsAttempt = state.view.camera_configuration_attempt;
    if (cameraConfigurationAttemptValid(settingsAttempt, state.view)
      && (settingsAttempt.settings_reference_retained || settingsAttempt.export_available)) {
      box.append(element("p", "notice warning", "Inspect the logged settings and retained attempt outcome. A settings frame is not calibration or permission to operate the arm. No automatic capture or retry occurs."));
      link(settingsAttempt.capture_action, "Open the one-frame settings verification form; review camera effects and confirm current power isolation separately.");
      link(settingsAttempt.export_action, "Choose the exact retained capture to export without reconnecting or replaying it.");
      link("physical_camera_configuration", "Changing staged settings withdraws the previous settings reference and image.");
      link("physical_camera_operating_proposal", "Record an explicit rationale for the currently staged mode; draft only, no capture or approval.");
      link("physical_camera_operating_assessment", "Check a logged draft against saved originals and explicitly selected captures; file-only assessment, not approval.");
      link("physical_camera_operating_submit", "Explicitly select two original captures and save one unreviewed submission; no device access or automatic replay.");
      if (![settingsAttempt.capture_action, settingsAttempt.export_action, "physical_camera_configuration"].some(eligible)) box.append(element("p", "caption", "Current settings actions are held. Inspect the server's blocked reasons and diagnostic logs; do not initialize a replacement store to bypass the hold."));
      return box;
    }
    const initialize=eligible("physical_camera_initialize"), discover=eligible("physical_camera_discover"), reopen=eligible("physical_camera_reopen");
    if (initialize || discover || reopen) {
      box.append(element("p","notice warning","Choose deliberately: create a new original store OR discover and select an existing one. Neither option is selected automatically; discovery does not reopen a store."));
      link("physical_camera_initialize","Initialize a new assigned store, only if you intend to start a new session.");
      link("physical_camera_discover","Read the assigned registry; choose an original store separately.");
      link("physical_camera_reopen","Review the opaque original-store choice in its form. No choice is preselected here.");
      return box;
    }
    const source=sourceReassessmentProjection(state.view.source_reassessment,state.view);
    const design=staticCameraOnboardingProjection(state.view.static_camera_onboarding,state.view);
    const received=receivedCameraProjection(state.view.received_camera_onboarding,state.view);
    const identity=cameraIdentityProjection(state.view.camera_identity_onboarding,state.view);
    const usb=usbIdentityProjection(state.view.usb_identity,state.view);
    const trial=usbQualificationProjection(state.view.usb_qualification,state.view);
    if(["rocell.wizard_usb_qualification.v2","rocell.wizard_usb_qualification.v3","rocell.wizard_usb_qualification.v4","rocell.wizard_usb_qualification.v5","rocell.wizard_usb_qualification.v6"].includes(trial?.schema)&&trial.plan){
      box.append(element("p","notice warning",trial.schema.endsWith(".v6")?"Review the four retained original phases using the explicit file-only assessment and independent final review. Identity acceptance never authorizes capture or arm movement. Partial evidence is export-only. Navigation runs nothing.":trial.schema.endsWith(".v5")?"Continue the new AFTER_REBOOT interval with a restart report, three fresh metadata acquisitions, explicit original Refresh, review, one boot observation and one separately admitted USB query. A new launch is not reboot evidence. Navigation runs nothing.":trial.schema.endsWith(".v4")?"Continue AFTER_RECONNECT through explicit report, fresh metadata preparation, review, one boot observation and one separately admitted descriptor query. The report does not prove mechanical reconnection. Reopened or uncertain work is export-only; navigation runs nothing.":trial.schema.endsWith(".v3")?"Continue the original reported-unplug interval through five explicit steps: report/files, boot review, one boot observation, exact presence review, one presence query. The target is fixed by the original BASELINE. Stop is software cancellation, not an emergency stop; nothing is run by navigation.":"Continue only the original BASELINE interval. Fresh metadata, local boot observation and the separately admitted USB query are distinct steps. No automatic acquisition, disconnect/restart, permit renewal or retry."));
      let next=trial.next_action;
      if(next==="physical_camera_refresh")box.append(element("p","notice warning","Three current-launch metadata acquisitions are logged after this phase’s operator report. Explicitly refresh the original session before Prepare. Refresh performs no boot or USB query and does not renew or replay an attempted interval."));
      const activePhase=trial.reboot||trial.reconnect||trial.baseline,isReboot=!!trial.reboot,isReconnect=!!trial.reconnect,isReportPhase=isReboot||isReconnect;
      if(activePhase?.state==="PREPARATION_REQUESTED"&&trial.next_action!=="physical_camera_refresh"&&trial.source_sha256===state.view.source_binding_sha256&&(!isReportPhase||activePhase.operator_event?.launch_session_id===state.view.session_id)){
        const rows=activePhase.acquisition_ledger?.entries||[],generic=validatedDeviceMetadata(state.view.device_selection),helper=validatedCameraHelper(state.view.camera_helper_registration),native=validatedNativeEnrollment(state.view.native_camera_enrollment,state.view.device_selection);
        if(rows.length===0)next="inventory_devices";
        else if(!generic?.devices.CAMERA.review)next="review_camera_candidate";
        else if(!helper||["NO_INSPECTION","INVALIDATED"].includes(helper.status))next="camera_helper_inspect";
        else if(helper.status==="INSPECTION_RETAINED")next="camera_helper_review";
        else if(rows.length===1)next="native_camera_inventory";
        else if(rows.length===2)next="native_camera_identity";
        else if(native?.status==="IDENTITY_RETAINED")next="native_camera_review";
        else if(trial.publication.status!=="CURRENT")next=isReportPhase&&trial.next_action!=="physical_camera_refresh"?"physical_usb_identity_export":"physical_camera_refresh";
        else next=isReboot?"physical_usb_reboot_prepare":isReconnect?"physical_usb_reconnect_prepare":"physical_usb_qualification_prepare";
      }
      if(next&&eligible(next))link(next,"Navigate to the existing eligible form only. Read its consent and preview before explicit execution.");
      else box.append(element("p","caption","Inspect the server's action hold below; partial and earlier-launch prepared attempts are export-only."));
      if(next!=="physical_usb_identity_export")link("physical_usb_identity_export","Export retained original phase and attempt evidence without replay.");return box;
    }
    if(trial?.publication.status==="CURRENT"&&trial.next_action&&eligible(trial.next_action)){
      box.append(element("p","notice warning","Declare the trial before acquiring any phase. This saves only original received-unit and cable/port context; it does not run USB, boot, disconnect or restart operations."));
      link(trial.next_action,"Open the explicit file-only declaration form; no action is prepared or executed by this link.");return box;
    }
    if(trial?.plan||trial?.status==="INCOMPLETE_HELD"){
      box.append(element("p","notice warning","The original trial declaration is retained. No phase acquisition is available in this increment; do not disconnect or restart based on this declaration alone. Export the original plan/events for continuity; this does not qualify the camera or release capture."));
      link("physical_usb_identity_export","Open the existing explicit metadata export form only; no original record is replayed.");return box;
    }
    if(usb?.publication.status==="CURRENT"&&usb.next_action&&eligible(usb.next_action)){
      box.append(element("p","notice warning",usb.next_action==="physical_usb_identity_collect"?"The server offers one original-target USB baseline query. Read the explicit device-effect and Stop limits before confirming; there is no automatic query or retry.":"Continue the original USB baseline workflow. File inspection/review and the later effectful query remain separate actions."));
      link(usb.next_action,"Open the existing eligible form only; no preview or execution occurs from this link.");return box;
    }
    const identityWaiting = state.view.mode === "physical" && received
      && received.source_sha256 === state.view.source_binding_sha256
      && received.launch_session_id === state.view.session_id
      && received.stage_states?.camera_receipt === "PASS"
      && received.stage_states?.camera_identity === "WAITING_OPERATOR"
      && received.identity_entry !== null && received.publication.status !== "PENDING";
    if (identityWaiting) {
      box.append(element("p","notice warning","Original camera identity stage is waiting. Current-launch metadata collection and original-store publication are separate. Mapping review is not received-unit qualification or permission to capture."));
      const current = data => data && data.provenance?.mode === "physical"
        && data.provenance.session_id === state.view.session_id
        && data.provenance.source_sha256 === state.view.source_binding_sha256;
      const generic = validatedDeviceMetadata(state.view.device_selection);
      const helper = validatedCameraHelper(state.view.camera_helper_registration);
      const native = validatedNativeEnrollment(state.view.native_camera_enrollment, state.view.device_selection);
      let metadataNext = null;
      if (!current(generic) || !generic.devices.CAMERA.review) metadataNext = current(generic) && generic.devices.CAMERA.candidates.length ? "review_camera_candidate" : "inventory_devices";
      else if (!current(helper) || ["NO_INSPECTION","INVALIDATED"].includes(helper.status)) metadataNext = "camera_helper_inspect";
      else if (helper.status === "INSPECTION_RETAINED") metadataNext = "camera_helper_review";
      else if (helper.status === "METADATA_HELPER_REGISTERED") {
        if (!current(native) || ["PROVIDER_UNAVAILABLE","NO_INVENTORY","INVALIDATED"].includes(native.status)) metadataNext = "native_camera_inventory";
        else if (native.status === "ENDPOINT_CHOICES_AVAILABLE") metadataNext = "native_camera_identity";
        else if (native.status === "IDENTITY_RETAINED") metadataNext = "native_camera_review";
        else if (["ENDPOINT_METADATA_REVIEWED","REVIEW_HELD"].includes(native.status)) {
          box.append(element("p","caption","The retained endpoint review may still contain identity gaps. Refresh this already-owned original store after the final metadata review, then submit the exact server-owned evidence using the original identity workflow when offered. Do not initialize or reopen a replacement."));
          if (received.publication.status !== "CURRENT") metadataNext = "physical_camera_refresh";
          else if(identity?.publication.status === "CURRENT" && eligible("physical_camera_identity_submit")) metadataNext = "physical_camera_identity_submit";
        }
      }
      if (!metadataNext && identity?.publication.status === "CURRENT" && eligible(identity.next_action)) metadataNext = identity.next_action;
      if (metadataNext && eligible(metadataNext)) link(metadataNext, metadataNext === "inventory_devices" ? "Navigate to Arm's existing metadata form. Read and explicitly acknowledge its power-disconnected requirement; no inventory runs from this link." : "Open the existing form; no endpoint or reviewer is selected automatically.");
      else box.append(element("p","caption","Inspect the current metadata holds and original identity action eligibility below. No missing field is inferred and no operation is retried automatically."));
      box.append(element("p","caption","Order: generic discovery and camera review; fixed-helper inspection and review; native inventory, exact identity and review; one original-store refresh after the last metadata action. Intermediate refreshes are unnecessary. A new launch must explicitly discover/reopen the original store."));
      return box;
    }
    const cachedNext=[identity,received,design,source].find(item => item?.publication.status === "CURRENT" && roster.includes(item.next_action) && eligible(item.next_action))?.next_action;
    const next=cachedNext || roster.find(id => eligible(id));
    if (next) {
      box.append(element("p","caption",cachedNext ? "The published original workflow identifies this next step, and the server currently offers its form." : "The server currently offers this onboarding form. Eligibility is not stage acceptance or permission to connect."));
      link(next,"Review the fields and effects, then explicitly preview and confirm if appropriate.");
      if (next === "physical_source_qualify") link("physical_source_isolation_files_discover","Optional prior discovery for an operator-reported isolation original; no isolation is inferred.");
    } else box.append(element("p","notice warning","No next onboarding action is currently eligible. Inspect the retained stage requirements and blockers below; do not retry or infer a completed stage."));
    if (eligible("physical_camera_refresh")) link("physical_camera_refresh","Explicit readback of this original store, not replay or automatic recovery.");
    box.append(element("p","caption","Advanced diagnostics and all server action forms remain below. Design/source acceptance does not release native camera access or arm power."));
    return box;
  }

  function controlCatalog() {
    // The directory is a projection of the current service catalog, never a
    // parallel action registry. Bad/ambiguous entries stay visible but unroutable.
    const catalog = state.view.actions;
    if (!Array.isArray(catalog) || catalog.length > 512) return null;
    const counts = new Map();
    for (const action of catalog) if (typeof action?.action_id === "string") counts.set(action.action_id, (counts.get(action.action_id) || 0) + 1);
    return catalog.map((action, index) => {
      const string = (value, max) => typeof value === "string" && value.length > 0 && value.length <= max;
      const id = string(action?.action_id, 128) ? action.action_id : "unsupported-entry-" + index;
      const label = string(action?.label, 256) ? action.label : "Unsupported catalog entry";
      const section = string(action?.section, 64) ? action.section : "unmapped";
      const description = typeof action?.description === "string" && action.description.length <= 4096 ? action.description : "Description unavailable.";
      const reasons = Array.isArray(action?.blocked_reasons) && action.blocked_reasons.length <= 128
        ? action.blocked_reasons.map(reason => typeof reason === "string" ? reason : reason?.message || reason?.code).filter(reason => typeof reason === "string" && reason.length <= 4096) : [];
      const fieldsValid = Array.isArray(action?.fields) && action.fields.length <= 128
        && action.fields.every(field => field && !Array.isArray(field) && string(field.name, 128)
          && [undefined, "text", "textarea", "number", "select", "checkbox"].includes(field.type)
          && (field.type !== "select" || (Array.isArray(field.options) && field.options.length <= 512)))
        && new Set(action.fields.map(field => field.name)).size === action.fields.length;
      const valid = /^[a-z][a-z0-9_]{0,127}$/.test(id) && counts.get(id) === 1
        && string(action?.label, 256) && Object.hasOwn(pages, section) && !["controls", "activity"].includes(section)
        && typeof action.enabled === "boolean" && fieldsValid
        && Array.isArray(action.blocked_reasons) && action.blocked_reasons.length === reasons.length
        && (action.enabled === false || reasons.length === 0);
      const issue = counts.get(id) > 1 ? "Ambiguous action identifier; inspect Diagnostics."
        : !valid ? "Unsupported action contract or destination; inspect Diagnostics." : null;
      // Include labels/options such as the phone target, but never index entered
      // values or defaults. Search is navigation, not a device selection.
      const fieldText = fieldsValid ? action.fields.flatMap(field => [field.name, field.label,
        ...(field.type === "select" ? field.options.flatMap(option => typeof option === "object" && option !== null ? [option.label, option.value] : [option]) : [])])
        .filter(value => typeof value === "string" && value.length <= 4096).join(" ") : "";
      return {id, label, section, description, reasons, fieldText, valid, issue, offered: valid && action.enabled === true && !state.pending && !state.connectionLost};
    });
  }

  function openCatalogAction(id) {
    // Re-resolve against the latest service view. A directory link is only
    // navigation; the destination still owns its form, defaults and preview gate.
    const matches = (controlCatalog() || []).filter(row => row.id === id);
    if (matches.length !== 1 || !matches[0].valid) { showError(new Error("This control is no longer uniquely available in the catalog. Refresh status and inspect Diagnostics; no action ran.")); return; }
    const row = matches[0]; navigate(row.section);
    const target = document.getElementById?.(`${row.section}-action-${row.id}`);
    if (!target) { showError(new Error("The existing action form could not be located. Inspect Diagnostics; no action was prepared or executed.")); return; }
    // Disabled camera forms live inside a disclosure. Expanding it is not consent.
    let parent = target.parentElement;
    while (parent) {
      if (parent.tagName === "DETAILS") {
        parent.open = true;
        if (cameraSectionIds.includes(parent.id)) state.cameraSections[parent.id] = true;
      }
      parent = parent.parentElement;
    }
    target.scrollIntoView({block: "start"}); target.focus({preventScroll: true});
  }

  function controls() {
    const fragment = document.createDocumentFragment();
    const intro = card("Find the right control", "Browse every action registered by this application. Open its existing form to inspect prerequisites, review the exact effects, and explicitly confirm only when appropriate.");
    intro.append(element("p", "notice warning", "Offered by service is not hardware-ready. Received-unit verification, camera/arm qualification, and later movement/contact remain separate. Opening a form never connects a device or runs a test."));
    const catalog = controlCatalog();
    if (!catalog) { intro.append(element("p", "notice error", "The action catalog is missing or exceeds the supported display limit. No entries are silently omitted. Inspect Diagnostics and refresh status.")); fragment.append(intro); return fragment; }
    const preference = state.controlDirectory, filters = element("div", "control-filters");
    const field = (id, label, input) => { const row = element("div", "field"), name = element("label", "", label); name.htmlFor = id; input.id = id; row.append(name, input); filters.append(row); return input; };
    const search = field("control-search", "Search controls and hold reasons", element("input")); search.type = "search"; search.maxLength = 160; search.value = preference.query; search.placeholder = "e.g. capture, phone, export, identity";
    const select = (id, label, options, value) => {
      const input = element("select");
      for (const [key, text] of options) { const option = element("option", "", text); option.value = key; input.append(option); }
      input.value = value; return field(id, label, input);
    };
    const sections = select("control-section", "Component", [["all", "All components"], ...Object.entries(pages).filter(([key]) => !["controls", "activity"].includes(key)), ["unmapped", "Unmapped entries"]], preference.section);
    const availability = select("control-availability", "Availability", [["all", "All controls"], ["offered", "Offered by service"], ["held", "Held / unsupported"]], preference.availability);
    const results = element("div", "control-results"); results.id = "control-results";
    const status = element("p", "caption"); status.id = "control-results-status"; status.setAttribute("role", "status");
    const paint = () => {
      const query = preference.query.trim().toLocaleLowerCase();
      const filtered = catalog.filter(row => (preference.section === "all" || (preference.section === "unmapped" ? !Object.hasOwn(pages, row.section) || ["controls", "activity"].includes(row.section) : row.section === preference.section))
        && (preference.availability === "all" || (preference.availability === "offered" ? row.offered : !row.offered))
        && [row.id, row.label, row.description, row.fieldText, ...row.reasons, row.issue || ""].join(" ").toLocaleLowerCase().includes(query));
      const size = 12, totalPages = Math.max(1, Math.ceil(filtered.length / size));
      preference.page = Math.max(0, Math.min(preference.page, totalPages - 1));
      status.textContent = `${filtered.length} matching / ${catalog.length} registered controls · ${filtered.filter(row => row.offered).length} offered among these matches · page ${preference.page + 1} of ${totalPages}`;
      results.replaceChildren();
      for (const row of filtered.slice(preference.page * size, (preference.page + 1) * size)) {
        const item = element("article", "control-row"); item.setAttribute("data-catalog-action", row.id);
        const header = element("div", "control-row-heading");
        header.append(element("h3", "", row.label), element("span", "badge " + (row.offered ? "" : "hold"), row.offered ? "Offered · preview required" : "Held / unsupported"));
        item.append(header, element("p", "caption", `${Object.hasOwn(pages, row.section) ? pages[row.section] : "Unmapped"} · ${row.id}`), element("p", "", row.description));
        if (row.reasons.length || row.issue) {
          const reasons = element("ul", "action-blockers");
          for (const reason of [...row.reasons, ...(row.issue ? [row.issue] : [])]) reasons.append(element("li", "", reason));
          item.append(reasons);
        } else if (!row.offered) item.append(element("p", "caption", "The service is not offering this action now. Inspect its existing form and current diagnostics."));
        const open = element("button", "button secondary", row.offered ? "Open action form" : "Inspect held form"); open.type = "button"; open.disabled = !row.valid;
        open.setAttribute("data-open-control", row.id);
        open.addEventListener("click", () => { if (row.valid) openCatalogAction(row.id); });
        item.append(open); results.append(item);
      }
      if (!filtered.length) results.append(element("p", "empty-state", "No controls match these filters. Clear the search or choose All components / All controls. Nothing has run."));
      const pager = element("div", "button-row control-pagination");
      for (const [delta, label] of [[-1, "Previous controls"], [1, "Next controls"]]) {
        const button = element("button", "button secondary", label); button.type = "button";
        button.disabled = delta < 0 ? preference.page === 0 : preference.page >= totalPages - 1;
        button.addEventListener("click", () => { if (!button.disabled) { preference.page += delta; paint(); } }); pager.append(button);
      }
      results.append(pager);
    };
    const update = () => { preference.query = search.value.slice(0, 160); preference.section = sections.value; preference.availability = availability.value; preference.page = 0; paint(); };
    search.addEventListener("input", update); sections.addEventListener("change", update); availability.addEventListener("change", update);
    const clear = element("button", "button secondary", "Clear filters"); clear.type = "button";
    clear.addEventListener("click", () => { search.value = ""; sections.value = availability.value = "all"; update(); search.focus(); });
    const diagnostics = element("button", "button secondary", "Review results & exports"); diagnostics.type = "button"; diagnostics.addEventListener("click", () => navigate("diagnostics"));
    const links = element("div", "button-row"); links.append(clear, diagnostics);
    intro.append(filters, links, status); fragment.append(intro, results); paint(); return fragment;
  }

  function cameraWorkspace() {
    const box = card(null); box.classList.add("camera-workspace");
    box.append(element("div", "card-label", "STATIC OVERHEAD · CAMERA WORKSPACE"),
      element("h2", "", "Set up, inspect, then review"),
      element("p", "", "Work through the offered step, inspect the saved image and results, then export your diagnostics. Camera evidence does not release the arm for movement."));
    const nav = element("nav", "camera-shortcuts"); nav.setAttribute("aria-label", "Camera workspace shortcuts");
    for (const [id, label, note] of [
      ["camera-next-step", "1 · Next step", "Review the offered action"],
      ["camera-image", "2 · Saved image", "A retained frame, not live video"],
      ["camera-actions", "3 · All camera actions", "Preview before executing"],
      ["camera-detailed-records", "4 · Technical records", "Inspect evidence and holds"],
    ]) {
      const link = element("a", "camera-shortcut"); link.href = "#" + id;
      link.setAttribute("data-camera-section", id);
      link.append(element("strong", "", label), element("span", "", note));
      link.addEventListener("click", event => {
        event.preventDefault();
        // These fixed anchors change presentation only, never action eligibility.
        const target = document.getElementById?.(id); if (!target) return;
        if (id === "camera-detailed-records") {
          state.cameraSections[id] = true; target.open = true;
        }
        target.scrollIntoView({block: "start"});
        (id === "camera-detailed-records" ? document.getElementById(id + "-summary") : target)?.focus({preventScroll: true});
      });
      nav.append(link);
    }
    const exports = element("div", "camera-export-strip");
    const destination = element("div"); destination.append(element("strong", "", "Assigned diagnostic folder"),
      element("div", "camera-export-path", state.view.exports?.directory || "No export directory assigned"));
    const open = element("button", "button secondary", "Go to diagnostics & exports"); open.type = "button";
    open.id = "camera-open-diagnostics"; open.addEventListener("click", () => navigate("diagnostics"));
    exports.append(destination, open);
    box.append(nav, exports, element("p", "caption", "Shortcuts only navigate. Opening diagnostics does not create an export or access hardware."));
    return box;
  }

  function camera() {
    const fragment = document.createDocumentFragment(), grid = element("div", "grid two");
    const box = card("Retained camera image", "Static overhead · cached image, not a live connection");
    box.id = "camera-image"; box.tabIndex = -1;
    const preview = element("div", "camera-preview"); preview.id = "camera-preview";
    const provenance = state.view.camera?.provenance || state.view.camera?.image_provenance || state.view.camera?.status || "NO CAPTURE EVIDENCE";
    const schematic = /schematic|board.preview/i.test(provenance);
    const physicalImage = provenance === "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2";
    if (state.imageURL && (!physicalImage || (physicalImagePublished() && state.imageId === state.view.camera?.image_id))) {
      const img = element("img"); img.src = state.imageURL;
      img.alt = (state.view.camera?.description || "Latest service-provided image") + ". Provenance: " + human(provenance);
      preview.append(img);
    } else preview.append(element("p", "", "No image available. Use the eligible actions below; opening this page does not open the camera or perform a capture."));
    preview.append(element("span", "preview-label", schematic ? "SCHEMATIC · NOT CAMERA CAPTURE" : physicalImage ? (physicalImagePublished() ? "LAST CAPTURED · NOT LIVE" : "PHYSICAL IMAGE PUBLICATION HELD") : human(provenance)));
    box.append(preview, element("div", "caption", state.view.camera?.description || (schematic ? "Source-bound nominal board drawing. This is not an acquired camera frame and cannot validate lens, focus or installed calibration." : "This image is not calibration acceptance. Focus and aperture on the purchased lens are manual.")));
    const info = card("Service-reported camera state & settings", "Local service availability is separate from camera acquisition");
    info.append(element("p", "caption", "Local service connected means this page can reach the application, not that a camera is connected. Reviewed endpoint metadata, settings intent/readback and a finite last capture are separate records. None establishes the camera's current physical connection or the arm's power state."), facts(state.view.camera, ["image_id"]));
    grid.append(box, info);
    // Build and validate every diagnostic panel even while visually collapsed.
    // Historical failures remain inspectable; they cannot become current facts.
    const records = cameraDisclosure(cameraSectionIds[1], "Detailed camera records & prerequisites",
      element("p", "caption", "Inspect retained metadata, original setup, probe/settings attempts and historical failures. These are cached records, not a live connection or permission to move the arm."),
      deviceMetadata("CAMERA"), cameraHelperRegistration(), nativeCameraEnrollment(), physicalCameraSetup(), cameraModeEntry(), cameraProbeSetup(), cameraProbeAttempt(), cameraConfigurationAttempt(), cameraOperatingProposal(), cameraOperatingSubmission(), usbIdentity(), usbQualification(), physicalIntake(), physicalIntakeEvidence(), physicalCamera());
    const next = cameraNextStep(); next.tabIndex = -1;
    fragment.append(cameraWorkspace(), next, grid);
    const activity = renderOperations();
    if (activity) fragment.append(heading("Recent activity", "All components · saved results, never replayed"), activity);
    fragment.append(cameraActions(), records); return fragment;
  }
  function arm() {
    const fragment = document.createDocumentFragment(), grid = element("div", "grid two");
    let guidedActionId = null;
    const guide = card("Arm onboarding: next step", "Guidance only — no automatic connection or power change.");
    const readiness = state.view.arm_readiness;
    const readinessStates = ["WAIT_FOR_OPERATION", "REVIEW_SERVICE_HOLD", "INSPECT_METADATA", "REVIEW_CANDIDATE", "INSPECT_NATIVE_METADATA", "REVIEW_METADATA_HOLD", "PHYSICAL_BACKEND_PENDING", "REHEARSAL_ONLY"];
    if (readiness && readiness.schema === "rocell.arm_wizard_readiness.v1" && readinessStates.includes(readiness.state)
      && readiness.connected === false && readiness.physical_authority === false
      && typeof readiness.message === "string" && readiness.message.length <= 1024
      && typeof readiness.export_directory === "string" && readiness.export_directory.length <= 4096
      && (readiness.next_action_id === null || (state.view.actions || []).some(action => action.action_id === readiness.next_action_id))) {
      guide.append(element("span", "badge hold", readiness.state === "PHYSICAL_BACKEND_PENDING" ? "GENERAL_CONNECTION_HELD" : readiness.state), element("p", "", readiness.message),
        element("p", "caption", `Assigned export folder: ${readiness.export_directory}`));
      if (typeof readiness.startup_warning === "string" && readiness.startup_warning.length <= 1024) {
        guide.append(element("p", "notice warning", readiness.startup_warning));
      }
      const worklist = readiness.physical_connection_worklist;
      if (Array.isArray(worklist) && worklist.length === 6 && worklist.every(item => item
        && ["id", "owner", "milestone", "required"].every(key => typeof item[key] === "string" && item[key].length <= 1024))) {
        guide.append(element("h3", "", "General connection & later commissioning"),
          element("p", "caption", "Development/review guidance, not approval checkboxes or per-action eligibility. Separately gated diagnostics retain their own current prerequisites."));
        const list = element("ol", "");
        worklist.forEach(item => list.append(element("li", "", `${item.milestone} — ${item.owner}: ${item.required}`)));
        guide.append(list);
      }
      if (readiness.next_action_id) {
        const nextAction = state.view.actions.find(action => action.action_id === readiness.next_action_id);
        guidedActionId = nextAction.action_id;
        guide.append(element("p", "caption", `Next action: ${nextAction.label || nextAction.action_id}. Preview and explicit confirmation are required.`));
        guide.append(actionForm(nextAction).node);
      }
    } else guide.append(element("p", "notice warning", "Readiness guidance unavailable. Review the current action prerequisites; no connection is inferred."));
    const info = card("RoArm-M3 Pro", "Controller metadata, rehearsal and separately gated physical diagnostics");
    info.append(element("p", "caption", "Local service connected is not an arm connection. Metadata correlation does not open a serial port or verify installed firmware, boot behavior or power state."), facts(state.view.arm));
    const boundary = card("General Connect and motion remain held", "Rehearsal actions use incapable adapters. Separately registered passive observation, telemetry and one-shot feedback actions can access physical serial hardware only after their own current setup, identity and confirmation gates. They do not establish a persistent connection or motion permission.");
    boundary.append(element("p", "notice warning", "These are not instructions to power or connect the arm now. USB serial opening and manual power-on can reset or move the arm; each physical event needs its own reviewed prerequisites and explicit authorization. Even a zero-write read may reset the controller. Stop is not an emergency stop."));
    const steps = element("ol", "guide");
    for (const line of ["Retain exact controller metadata; never choose the first COM port. Metadata alone is not an identity-bound serial connection.", "Inspect each physical form's current startup, firmware, fixture and power prerequisites; a metadata match or rehearsal cannot supply them.", "A separately offered physical diagnostic requires its own bounded authorization and current setup. A captured packet is not installed calibration or permission to move.", "Inspect retained feedback and cleanup with their recorded provenance. No initialization, retry or reconnect is automatic."])
      steps.append(element("li", "", line));
    boundary.append(steps); grid.append(info, boundary);
    const passive = state.view.passive_arm_rehearsal;
    if (passive && passive.schema === "rocell.wizard_passive_arm_rehearsal_view.v1"
      && passive.provenance === "REHEARSAL_ONLY_NOT_RECEIVED_DEVICE_EVIDENCE"
      && passive.physical_authority === false && passive.connected === false) {
      const retained = card("Retained passive USB rehearsal", "Real process diagnostics; synthetic serial observations. Not a hardware connection or qualification.");
      retained.append(facts(passive, ["schema", "provenance", "export_attachment", "physical_authority", "connected"]),
        element("p", "caption", "Use Export logs to retain the request, raw output and cleanup details. A successful process exit does not prove device cleanup."));
      grid.append(retained);
    }
    const history = state.view.passive_arm_history;
    if (history && history.schema === "rocell.passive_arm_history_view.v1"
      && history.historical_only === true && history.connected === false
      && history.physical_authority === false && history.replay_allowed === false) {
      const saved = card("Saved passive arm attempt", "Historical diagnostics only. No connection or replay authority.");
      saved.append(facts(history, ["schema", "physical_authority", "connected", "replay_allowed"]));
      grid.append(saved);
    }
    fragment.append(workspaceGuide("arm"), guide, grid, deviceMetadata("SERIAL"), nativeArmMetadata(), heading("Arm actions"), actions("arm", guidedActionId)); return fragment;
  }
  function board() {
    const fragment = document.createDocumentFragment();
    const info = card("Placemat & baseline tests", "Geometry and test results come from the shared source-bound service, not a second browser configuration.");
    const drawing = boardDiagram(state.view.board?.geometry);
    if (drawing) {
      info.append(drawing, element("p", "caption", "Source-bound layout · origin at front-left · +X right, +Y toward the arm. This nominal drawing does not verify installed placement or reach."));
    }
    info.append(facts(state.view.board));
    if (state.view.baselines) info.append(detail(state.view.baselines, "Baseline results"));
    fragment.append(workspaceGuide("board"), info, heading("Board & test actions"), actions("board")); return fragment;
  }
  function boardDiagram(geometry) {
    if (!geometry || typeof geometry !== "object") return null;
    const width = geometry.width_mm, height = geometry.height_mm;
    if (![width, height].every((value) => typeof value === "number" && Number.isFinite(value) && value > 0 && value <= 10000)) return null;
    const ns = "http://www.w3.org/2000/svg";
    const node = (name, attributes = {}, content) => {
      const item = document.createElementNS(ns, name);
      Object.entries(attributes).forEach(([key, value]) => item.setAttribute(key, String(value)));
      if (content !== undefined) item.textContent = String(content);
      return item;
    };
    const svg = node("svg", {viewBox: `-28 -32 ${width + 56} ${height + 68}`, class: "diagram", role: "img", "aria-label": "Nominal source-bound placemat geometry"});
    svg.append(node("title", {}, "Nominal placemat — not measured hardware evidence"));
    svg.append(node("rect", {x: 0, y: 0, width, height, rx: 5, fill: "#e9f0ec", stroke: "#95b4a1", "stroke-width": 2}));
    svg.append(node("text", {x: width / 2, y: -12, "text-anchor": "middle"}, `${width} × ${height} mm`));
    svg.append(node("text", {x: 0, y: height + 23}, "(0, 0) · +X →"));
    const devices = Array.isArray(geometry.devices) ? geometry.devices.slice(0, 24) : [];
    for (const device of devices) {
      const values = [device.x_mm, device.y_mm, device.width_mm, device.height_mm];
      if (!values.every((value) => typeof value === "number" && Number.isFinite(value))) continue;
      const [x, y, w, h] = values;
      if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > width || y + h > height) continue;
      // SVG's downward Y is presentation only; source board Y remains upward.
      const top = height - y - h;
      const group = node("g");
      group.append(node("rect", {x, y: top, width: w, height: h, rx: 3, fill: "#cbe2d3", stroke: "#4b8970", "stroke-width": 1.5}));
      group.append(node("title", {}, `${device.name}: (${x}, ${y}) mm; ${w} × ${h} mm`));
      group.append(node("text", {x: x + w / 2, y: top + h / 2, "text-anchor": "middle", "dominant-baseline": "middle", class: w < 100 ? "phone-label" : ""}, String(device.name || "Device").slice(0, 24)));
      svg.append(group);
    }
    return svg;
  }
  function tasks() {
    const fragment = document.createDocumentFragment(), notice = element("div", "notice warning");
    notice.append(element("strong", "", "Simulation only — no physical keypresses or taps"));
    notice.append(element("span", "", "Rehearse individual keyboard strokes and Android targets against the configured placemat. Actual movement and contact require separately qualified execution and are not available here."));
    notice.append(element("p", "", "Legacy task simulations retain their locked arm-mounted-camera graph. The separate static task rehearsal uses the overhead-camera simulation bundle; neither qualifies installed camera calibration."));
    fragment.append(workspaceGuide("tasks"), notice);
    const observer = card("Observe keyboard input independently", "Record only a focused local test field. No arm movement; browser input does not establish who caused the press. Phone pairing is not implemented.");
    const testLink = element("a", "button secondary", "Open keyboard test pad"); testLink.href = "/input-test";
    observer.append(testLink); fragment.append(observer);
    if (state.view.tasks) { const box = card("Task results"); box.append(facts(state.view.tasks)); fragment.append(box); }
    fragment.append(heading("Rehearse a task"), actions("tasks")); return fragment;
  }
  function operationCatalog() {
    // Only the launch's cached summaries are indexed. Never search the disk,
    // load full results, infer components from action-name prefixes, or replay.
    const source = state.view.operations;
    if (!source || typeof source !== "object") return source === undefined ? [] : null;
    const values = Array.isArray(source) ? source : Object.values(source);
    if (values.length > 256) return null;
    const counts = new Map(), sections = new Map();
    for (const row of values) if (typeof row?.operation_id === "string") counts.set(row.operation_id, (counts.get(row.operation_id) || 0) + 1);
    for (const action of controlCatalog() || []) {
      if (action.valid) sections.set(action.id, action.section);
    }
    return values.map((operation, index) => {
      const valid = operation && typeof operation === "object" && !Array.isArray(operation)
        && typeof operation.operation_id === "string" && /^[A-Za-z0-9_-]{1,160}$/.test(operation.operation_id)
        && counts.get(operation.operation_id) === 1
        && typeof operation.action_id === "string" && /^[a-z][a-z0-9_]{0,127}$/.test(operation.action_id);
      return {operation, valid: !!valid, id: valid ? operation.operation_id : "unsupported-operation-" + index,
        section: sections.get(operation?.action_id) || "unmapped"};
    });
  }

  function operationGuidance(operation) {
    if (operation?.completion_log_persisted === false || operation?.result_retention === "FULL_JSON_RETAINED_COMPLETION_LOG_FAILED")
      return "Completion logging is unconfirmed. The action may already have taken effect. Inspect retained results and any export receipt, then review the diagnostic log hold. Do not replay the action to repair its log.";
    const messages = {
      QUEUED: "Queued by the service. Inspect progress; submitting another action is not a way to check it.",
      PENDING: "Pending; completion has not been reported. No readiness is inferred.",
      RUNNING: "Running according to the service. Read status before considering another action.",
      CANCEL_REQUESTED: "Cancellation requested, not confirmed. This is not a robot emergency stop or proof that hardware stopped.",
      CANCELLED: "The service reports cancellation. This is not proof of a robot stop or zero effects; inspect cleanup and retained evidence.",
      TIMED_OUT: "The diagnostic timed out. Hardware effects and cleanup may be uncertain. Inspect the attempt and export available evidence before considering any new action.",
      UNCERTAIN: "The outcome is uncertain. Preserve evidence and investigate the original attempt; do not replay it as a recovery shortcut.",
      FAILED: "The diagnostic failed. Read the exact error and remediation, inspect available results, and export evidence. Do not automatically retry.",
      SUCCEEDED: "The worker completed successfully. Review its assessment outcome and remaining holds; worker success is not hardware qualification or permission to move.",
    };
    return Object.hasOwn(messages, operation?.status) ? messages[operation.status]
      : "The operation status is unavailable or unsupported. Inspect the retained record and diagnostics; no successful completion is inferred.";
  }

  function operationNeedsAttention(entry) {
    const operation = entry.operation;
    return !entry.valid || !["QUEUED", "PENDING", "RUNNING", "SUCCEEDED"].includes(operation?.status)
      || operation?.completion_log_persisted === false || /^(OMITTED|FULL_JSON_RETAINED_COMPLETION_LOG_FAILED)/.test(operation?.result_retention || "");
  }

  function operationBinding(operation) {
    // A browser cache is presentation only, bound to the launch and summary's
    // retention/currentness fields. A rotated result cannot reappear from cache.
    return JSON.stringify([state.view.session_id, state.view.cell_id, state.view.mode, state.view.source_binding_sha256,
      operation?.operation_id, operation?.action_id, operation?.status, operation?.result_retention,
      operation?.result_sha256, operation?.completion_log_persisted]);
  }

  function activity() {
    const fragment = document.createDocumentFragment();
    const intro = card("Review what happened", "Search the operation summaries retained by this launch, newest first. Load a record only when you want to inspect it. Reading history never reruns an action or restores hardware access.");
    intro.append(element("p", "notice warning", "This is bounded launch history, not a permanent archive. Older full results may have rotated out. Export available evidence before closing the service; reopening the UI does not restore an earlier launch's results or approvals."));
    if (state.view.diagnostics?.retention_policy) intro.append(detail(state.view.diagnostics.retention_policy, "Service-reported retention & export policy"));
    const exports = element("div", "camera-export-strip"), destination = element("div");
    destination.append(element("strong", "", "Assigned diagnostic folder"), element("div", "camera-export-path", state.view.exports?.directory || "No export directory assigned"));
    const openExports = element("button", "button secondary", "Review diagnostics & exports"); openExports.type = "button";
    openExports.addEventListener("click", () => navigate("diagnostics")); exports.append(destination, openExports); intro.append(exports);
    const catalog = operationCatalog();
    if (!catalog) { intro.append(element("p", "notice error", "Operation history is missing, malformed or exceeds the supported display limit. No entries are silently omitted. Inspect Diagnostics; nothing was reloaded or retried.")); fragment.append(intro); return fragment; }
    const preference = state.activityDirectory, filters = element("div", "control-filters");
    const field = (id, label, input) => { const row = element("div", "field"), name = element("label", "", label); name.htmlFor = id; input.id = id; row.append(name, input); filters.append(row); return input; };
    const search = field("activity-search", "Search activity and errors", element("input")); search.type = "search"; search.maxLength = 160; search.value = preference.query; search.placeholder = "Operation, task, error or remediation";
    const select = (id, label, options, value) => {
      const input = element("select");
      for (const [key, label] of options) { const option = element("option", "", label); option.value = key; input.append(option); }
      input.value = value; return field(id, label, input);
    };
    const sections = select("activity-section", "Activity component", [["all", "All components"], ...Object.entries(pages).filter(([key]) => !["controls", "activity"].includes(key)), ["unmapped", "Unmapped / unavailable action"]], preference.section);
    const statuses = select("activity-status", "Operation status", [["all", "All statuses"], ["attention", "Needs review"], ["active", "Queued / running / pending"], ...["SUCCEEDED", "FAILED", "TIMED_OUT", "CANCEL_REQUESTED", "CANCELLED", "UNCERTAIN"].map(key => [key, human(key)]), ["unknown", "Unsupported / unknown"]], preference.status);
    const status = element("p", "caption"); status.id = "activity-results-status"; status.setAttribute("role", "status");
    const results = element("div", "activity-results"); results.id = "activity-results";
    const paint = () => {
      const query = preference.query.trim().toLocaleLowerCase();
      const filtered = catalog.filter(entry => {
        const operation = entry.operation, opStatus = operation?.status;
        const statusMatch = preference.status === "all" || (preference.status === "attention" ? operationNeedsAttention(entry)
          : preference.status === "active" ? ["QUEUED", "RUNNING", "PENDING"].includes(opStatus)
          : preference.status === "unknown" ? !["QUEUED", "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "CANCEL_REQUESTED", "CANCELLED", "UNCERTAIN"].includes(opStatus) : preference.status === opStatus);
        const searchable = [operation?.operation_id, operation?.action_id, operation?.label, opStatus, operation?.message, typeof operation?.error === "string" ? operation.error : "",
          operation?.error?.code, operation?.error?.message, operation?.error?.remediation, operation?.result_retention, operationGuidance(operation)]
          .filter(value => typeof value === "string").join(" ").toLocaleLowerCase();
        return statusMatch && (preference.section === "all" || preference.section === entry.section) && searchable.includes(query);
      }).reverse();
      const size = 8, totalPages = Math.max(1, Math.ceil(filtered.length / size));
      preference.page = Math.max(0, Math.min(preference.page, totalPages - 1));
      status.textContent = `${filtered.length} matching / ${catalog.length} retained operations · ${catalog.filter(operationNeedsAttention).length} need review · page ${preference.page + 1} of ${totalPages}`;
      results.replaceChildren();
      const pager = () => {
        const bar = element("div", "button-row control-pagination");
        for (const [delta, label] of [[-1, "Newer results"], [1, "Older results"]]) {
          const button = element("button", "button secondary", label); button.type = "button";
          button.disabled = delta < 0 ? preference.page === 0 : preference.page >= totalPages - 1;
          button.addEventListener("click", () => { if (!button.disabled) { preference.page += delta; paint(); status.focus(); } }); bar.append(button);
        }
        return bar;
      };
      const selected = filtered.slice(preference.page * size, (preference.page + 1) * size);
      // Page controls at both ends avoid scrolling through eight long reports
      // just to reach older summaries; focus announces and reveals the new page.
      results.append(pager());
      if (selected.length) results.append(renderOperations(selected));
      else results.append(element("p", "empty-state", catalog.length ? "No operations match these filters. Clear the filters to see this launch's retained history." : "No operations are retained in this launch. Use Control Center to find an appropriate action; browsing this page runs nothing."));
      results.append(pager());
    };
    const update = () => { preference.query = search.value.slice(0, 160); preference.section = sections.value; preference.status = statuses.value; preference.page = 0; paint(); };
    search.addEventListener("input", update); sections.addEventListener("change", update); statuses.addEventListener("change", update);
    const clear = element("button", "button secondary", "Clear activity filters"); clear.type = "button";
    clear.addEventListener("click", () => { search.value = ""; sections.value = statuses.value = "all"; update(); search.focus(); });
    status.tabIndex = -1; intro.append(filters, clear, status); fragment.append(intro, results); paint(); return fragment;
  }

  function diagnostics() {
    const fragment = document.createDocumentFragment(), grid = element("div", "grid two");
    const exports = card("Diagnostic exports", "The destination is assigned when this local service is launched. Browser requests cannot choose filesystem paths.");
    exports.append(element("div", "export-path", state.view.exports?.directory || "No export directory assigned"));
    for (const receipt of state.view.exports?.items || []) exports.append(detail(receipt, receipt.filename || receipt.name || receipt.export_id || "Export receipt"));
    if (!(state.view.exports?.items || []).length) exports.append(element("p", "caption", "No bundle exported yet. Run an export action below to preserve logs and results."));
    const info = card("Diagnostics & remediation"); info.append(facts(state.view.diagnostics)); grid.append(exports, info);
    fragment.append(workspaceGuide("diagnostics"), grid, heading("Diagnostics actions"), actions("diagnostics"));
    if (state.view.events?.length) {
      const events = card("Recent event log"), list = element("ol", "event-list");
      for (const event of state.view.events) {
        const row = element("li");
        if (typeof event === "object") {
          row.append(element("span", "", `${event.timestamp || event.at || ""} ${event.kind || event.message || event.event || event.type || "Event"}`.trim()));
          row.append(detail(event.details || event, "Event details"));
        } else row.textContent = event;
        list.append(row);
      }
      events.append(list); fragment.append(events);
    }
    const raw = card("Session record", "Readable browser JSON, not original evidence bytes. Large numeric timestamps may be rounded by the browser. Use original diagnostic exports for exact values and verification; this display cannot establish evidence identity."); raw.append(detail(state.view, "Read-only service snapshot")); fragment.append(raw); return fragment;
  }

  function renderOperations(selected = null) {
    const catalog = operationCatalog();
    if (!catalog) return card("Operation history unavailable", "The retained history is malformed or exceeds the display limit. Inspect Diagnostics; no result was loaded or action retried.");
    const operations = selected || catalog.slice(-6).reverse();
    if (!operations.length) return null;
    const box = card("Operation results", "Read-only progress. Reopening the page never replays an operation.");
    if (!selected) {
      const all = element("button", "button secondary", `Review all ${catalog.length} retained operations`); all.type = "button";
      all.addEventListener("click", () => navigate("activity")); box.append(all);
    }
    for (const entry of operations) {
      const operation = entry.operation;
      if (!operation || typeof operation !== "object" || Array.isArray(operation)) { box.append(card("Unsupported operation summary", "Inspect the service snapshot in Diagnostics. No result destination is inferred.")); continue; }
      const status = typeof operation.status === "string" ? operation.status : "UNKNOWN";
      const row = element("div", "operation " + (/FAILED|TIMED_OUT/.test(status) ? "failed" : ""));
      row.setAttribute("data-history-operation", entry.id);
      const statusBadge = element("span", "badge " + (/FAILED|TIMED_OUT|UNCERTAIN/.test(status) ? "failed" : status === "SUCCEEDED" ? "" : "hold"), human(status));
      row.append(statusBadge, element("h3", "", operation.label || human(operation.action_id || operation.operation_id)));
      row.append(element("p", "caption", `${pages[entry.section] || "Unmapped action"} · ${human(operation.operation_id)} · started ${operation.started_at || "not recorded"} · finished ${operation.finished_at || "not recorded"}`));
      row.append(element("p", "operation-guidance", operationGuidance(operation)));
      const omitted = typeof operation.result_retention === "string" && operation.result_retention.startsWith("OMITTED");
      if (omitted) row.append(element("p", "notice warning", "Full result is no longer retained in this launch. The summary remains available. Inspect earlier verified exports if you saved them; a new export cannot recreate omitted data."));
      row.append(element("p", "caption", `Retention: ${human(operation.result_retention)} · completion log: ${operation.completion_log_persisted === true ? "recorded" : operation.completion_log_persisted === false ? "unconfirmed" : "not recorded"}`));
      if (operation.action_id === "simulate_task") {
        row.append(element("p", "caption", "Worker status: " + status), taskSimulationFeedback(operation));
      }
      if (operation.action_id === "physical_camera_operating_assessment") {
        row.append(element("p", "notice warning", status === "SUCCEEDED"
          ? "Assessment completed. Operating approval is still on hold; load the checklist to see what was and was not checked."
          : "Assessment is incomplete or held. No operating approval is inferred; inspect the result before considering another attempt."));
      }
      if (operation.message || operation.error) row.append(element("p", "", operation.error && typeof operation.error === "object" ? operation.error.message || text(operation.error) : operation.message || operation.error));
      if (operation.error?.remediation) row.append(element("p", "", operation.error.remediation));
      row.append(detail(operation, "Operation summary & evidence references"));
      const resultBox = element("div");
      const cached = state.results.get(operation.operation_id);
      if (entry.valid && !omitted && cached && cached.binding === operationBinding(operation)) { appendOperationCameraFaults(resultBox, cached.value); appendMovementCampaignResult(resultBox, cached.value); if (operation.action_id === "physical_camera_operating_assessment") appendCameraAssessmentResult(resultBox, cached.value); resultBox.append(detail(operationCameraDisplay(cached.value), "Retained structured result")); }
      else if (cached) state.results.delete(operation.operation_id);
      const load = element("button", "button secondary", omitted ? "Load retained operation record" : operation.action_id === "physical_camera_operating_assessment" ? "Load assessment checklist" : "Load latest full result");
      load.type = "button"; load.disabled = !entry.valid; load.setAttribute("data-load-operation", entry.id);
      if (!entry.valid) row.append(element("p", "notice warning", "Operation identity is missing, ambiguous or unsupported. Inspect Diagnostics; no result link is inferred."));
      const displayedBinding = operationBinding(operation);
      load.addEventListener("click", async () => {
        load.disabled = true;
        try {
          const current = (operationCatalog() || []).find(item => item.id === entry.id && item.valid);
          if (!current || operationBinding(current.operation) !== displayedBinding) throw new Error("This operation's launch, status or retention changed. Refresh status and inspect the current record; nothing was retried.");
          const full = await request(`/api/operations/${encodeURIComponent(operation.operation_id)}`);
          if (full?.operation_id !== operation.operation_id || full.action_id !== operation.action_id) throw new Error("The returned result does not match this operation. Inspect diagnostics; nothing was retried.");
          const latest = (operationCatalog() || []).find(item => item.id === entry.id && item.valid);
          if (!latest || operationBinding(latest.operation) !== displayedBinding) throw new Error("The launch or retained summary changed while loading. Refresh status before inspecting this result; nothing was replayed.");
          state.results.delete(operation.operation_id);
          if (!(typeof full.result_retention === "string" && full.result_retention.startsWith("OMITTED"))) state.results.set(operation.operation_id, {binding: operationBinding(full), value: full});
          while (state.results.size > 8) state.results.delete(state.results.keys().next().value);
          const document = detail(operationCameraDisplay(full), full.result == null ? "Retained operation record — full result unavailable" : "Retained structured result"); document.open = full.action_id !== "physical_camera_operating_assessment" && !full.action_id.startsWith("movement_campaign_");
          resultBox.replaceChildren(); resultBox.append(element("p", "caption", "Loaded record: " + human(full.status) + ". " + operationGuidance(full))); appendOperationCameraFaults(resultBox, full); appendMovementCampaignResult(resultBox, full); if (operation.action_id === "physical_camera_operating_assessment") appendCameraAssessmentResult(resultBox, full); resultBox.append(document);
        } catch (error) { resultBox.replaceChildren(element("p", "notice error", error.message || String(error))); showError(error); }
        finally { load.disabled = !entry.valid; }
      });
      row.append(resultBox, load); box.append(row);
    }
    return box;
  }
  function appendMovementCampaignResult(box, operation) {
    if (operation.action_id === "run_held_pair") {
      const panel = card("Bounded elbow pair", "Controller-count evidence only. Physical stylus-tip accuracy is NOT QUALIFIED.");
      const report = operation.result?.steps?.[0]?.report;
      if (report?.schema === "rocell.held_pair_trial.v1" && report.retry_allowed === false
          && report.physical_tip_accuracy_verified === false && Array.isArray(report.steps)) {
        panel.append(facts({"phase": report.phase, "stop reason": report.reason || "none reported",
          "trial export": operation.result.export_path || "unavailable",
          "admission export": operation.result.admission_export_id || "unavailable"}));
        const rows = element("ol");
        for (const step of report.steps) rows.append(element("li", "", `${step.stage}: ${step.export_id}`));
        panel.append(rows);
      } else panel.append(element("p", "", "Trial evidence unavailable; no completion claim."));
      box.append(panel);
      return;
    }
    if (operation.action_id === "review_observed_pair") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Forward / return endpoints — saved observation", "Offline replay; no commands or retries.");
      box.append(panel);
      const review = report?.review;
      const legsConsistent = [review?.forward, review?.reverse].every(leg => leg
        && leg.origin === "HOST_HTTP_OBSERVATION" && leg.progression_authority === false
        && leg.provenance_verified === false && leg.physical_tip_accuracy_verified === false);
      const arrivalConsistent = review?.category !== "CONTROLLER_REPORTED_PAIR_ARRIVAL" || (
        review.endpoint_continuity_verified === true && review.forward?.category === "CONTROLLER_REPORTED_ARRIVAL"
        && review.reverse?.category === "CONTROLLER_REPORTED_ARRIVAL" && review.reverse?.controller_state === "COMPLETE");
      if (report?.schema !== "rocell.wizard_pair_review.v1" || report.replay_verified !== true
          || report.origin !== "HOST_HTTP_OBSERVATION" || report.hardware_access !== false
          || report.progression_authority !== false || report.retry_allowed !== false
          || review?.schema !== "rocell.observed_pair_review.v1" || review.origin !== "HOST_HTTP_OBSERVATION"
          || review.progression_authority !== false || review.provenance_verified !== false
          || review.physical_tip_accuracy_verified !== false || !legsConsistent || !arrivalConsistent) {
        panel.append(element("p", "notice warning", "Pair review unavailable or inconsistent.")); return;
      }
      panel.append(facts({"export": report.export_id, "offline replay": "Verified",
        "outcome": review.category, "units": "Elbow servo counts, not millimeters",
        "between-leg delta": review.between_leg_delta_counts ?? "Unavailable",
        "endpoint continuity": review.endpoint_continuity_verified === true ? "Verified in counts" : "Not established",
        "hardware qualification": "NOT QUALIFIED", "automatic resend": "Disabled"}));
      panel.append(element("p", "notice", "Controller-reported evidence; HTTP does not authenticate device provenance. Stylus-tip accuracy is not measured."));
      for (const [name, leg] of [["Forward", review.forward], ["Return", review.reverse]]) {
        if (!leg || leg.origin !== "HOST_HTTP_OBSERVATION" || leg.progression_authority !== false) {
          panel.append(element("p", "notice warning", `${name}: evidence unavailable.`)); continue;
        }
        panel.append(facts({"leg": name, "outcome": leg.category,
          "controller state": leg.controller_state || "Unavailable",
          "requested target": leg.requested_target ?? "Unavailable", "encoded target": leg.encoded_target ?? "Unavailable",
          "first goal readback": leg.first_goal_readback ?? "Unavailable", "settled goal readback": leg.settled_goal_readback ?? "Unavailable",
          "start position": leg.start_position ?? "Unavailable", "final position": leg.final_position ?? "Unavailable",
          "position change": leg.position_change_counts ?? "Unavailable", "signed endpoint error": leg.signed_error_counts ?? "Unavailable",
          "observation interval (us)": leg.observed_after_command_us ?? "Unavailable"}));
      }
      return;
    }
    if (["review_collected_hold", "review_observed_hold"].includes(operation.action_id)) {
      const observed = operation.action_id === "review_observed_hold";
      const origin = observed ? "HOST_HTTP_OBSERVATION" : "SIMULATION";
      const success = observed ? "CONTROLLER_REPORTED_HOLD_VERIFIED" : "SIMULATED_HOLD_VERIFIED";
      const report = operation.result?.steps?.[0]?.report;
      const panel = card(observed ? "Hold endpoints — saved controller observation" : "Hold endpoints — offline simulation review", "Saved evidence only; no commands or retries.");
      box.append(panel);
      const assessment = report?.assessment;
      const detail = report?.endpoint_review;
      if (report?.schema !== "rocell.wizard_hold_review.v1" || report.origin !== origin
          || report.replay_verified !== true || report.hardware_access !== false
          || report.progression_authority !== false || report.retry_allowed !== false
          || assessment?.origin !== origin || assessment.progression_authority !== false
          || detail?.origin !== origin || detail.progression_authority !== false
          || (observed && (assessment.provenance_verified !== false || assessment.physical_tip_accuracy_verified !== false))
          || detail.category !== assessment.category) {
        panel.append(element("p", "notice warning", "Hold review unavailable or inconsistent.")); return;
      }
      panel.append(facts({"export": report.export_id, "offline replay": "Verified",
        "origin": origin, "outcome": assessment.category,
        "host delivery": report.delivery?.result || "Unavailable",
        "hardware qualification": "NOT QUALIFIED", "automatic resend": "Disabled"}));
      const endpoint = detail.endpoint;
      if (observed) panel.append(element("p", "notice", "Controller-reported counts; HTTP does not authenticate device provenance. Physical tip accuracy is not measured."));
      if (observed && report.controller_status) panel.append(facts({
        "controller state (reported)": report.controller_status.state,
        "controller reason (reported)": report.controller_status.reason,
        "status stable across collection": report.stable_status_observed === true ? "Yes" : "Not established",
        "retained record count": report.controller_status.records}));
      if (assessment.category !== success || !endpoint) {
        panel.append(element("p", "notice warning", "Inconclusive — endpoint not verified.")); return;
      }
      panel.append(facts({"servo": endpoint.servo_id, "units": "Servo counts, not millimeters",
        "requested hold target": endpoint.requested_hold_target,
        "encoded command target": endpoint.encoded_command_target,
        "previous goal": endpoint.previous_goal, "first goal readback": endpoint.first_goal_readback,
        "settled goal readback": endpoint.settled_goal_readback,
        "start position": endpoint.start_position, "settled position": endpoint.settled_position,
        "signed endpoint error": endpoint.settled_error_counts,
        "position change": endpoint.position_change_counts,
        "torque before / settled": `${endpoint.torque_before} / ${endpoint.torque_settled}`,
        "explicit enable": endpoint.explicit_enable_used ? "Yes" : "No",
        "wire observation": "Not independently measured", "stylus-tip accuracy": "Not measured"}));
      for (const joint of endpoint.other_joint_changes || []) panel.append(facts({
        "neighbor servo": joint.servo_id, "position change (counts)": joint.position_change_counts,
        "goal changed": joint.goal_changed, "torque changed": joint.torque_changed}));
      return;
    }
    if (["review_planned_servo_run", "review_started_servo_run", "review_startup_servo_run", "review_started_startup_run"].includes(operation.action_id)) {
      const started = ["review_started_servo_run", "review_started_startup_run"].includes(operation.action_id);
      const startup = ["review_startup_servo_run", "review_started_startup_run"].includes(operation.action_id);
      const report = operation.result?.steps?.[0]?.report;
      const panel = card(startup ? "Startup command and endpoint — offline review" : started ? "Command delivery and telemetry — offline review" : "Planned servo run — offline review", "Saved evidence only. No arm connection or movement authority.");
      box.append(panel);
      const outcome = report?.outcome, assessment = outcome?.assessment;
      const valid = report?.schema === (startup && started ? "rocell.started_startup_review.v1" : startup ? "rocell.startup_run_review.v1" : started ? "rocell.started_run_review.v1" : "rocell.planned_run_review.v1")
        && (!started || (report.retry_allowed === false && report.delivery?.retry_allowed === false
          && report.delivery?.progression_authority === false && report.delivery?.endpoint_verified === false))
        && report.hardware_access === false && report.progression_authority === false
        && report.replay_verified === true
        && ((outcome?.status === "EVIDENCE_REJECTED" || (startup && outcome?.status === "INCONCLUSIVE")) ? assessment === null
          : ((outcome?.status === "ASSESSED" && assessment?.schema === (startup ? "rocell.startup_session_assessment.v1" : "rocell.session_assessment.v1"))
            || (!startup && outcome?.status === "PARTIAL_FAILURE_ASSESSED" && assessment?.schema === "rocell.partial_session_assessment.v1"))
            && (!startup || assessment.startup_evidence_verified === true)
            && assessment.progression_authority === false && assessment.provenance_verified === false
            && assessment.physical_accuracy_verified === false);
      if (!valid) { panel.append(element("p", "notice warning", "Planned-run review unavailable or inconsistent.")); return; }
      panel.append(facts({"export": report.export_id, "offline replay": "Verified",
        "evidence validation": outcome.status, "overall outcome": assessment?.category || (startup ? "Inconclusive — endpoint not verified" : "Evidence rejected"),
        "hardware qualification": "NOT QUALIFIED"}));
      if (started) panel.append(facts({
        "host delivery outcome": report.delivery.result,
        "transmission attempted": report.delivery.transmission_attempted === true ? "Yes — not proof of motion" : "Not recorded",
        "pre-send export": report.prepared_export_id,
        "automatic resend": "Disabled — challenge claim remains consumed",
        "delivery versus endpoint": "Controller acceptance does not verify arrival"}));
      if (assessment) panel.append(facts({
        "exact controller receipt": assessment.receipt?.exact_payload_match === true ? "Matched" : "Not verified",
        "bus acknowledgment": assessment.write?.acknowledgment_verified === true ? "Verified" : "Not verified",
        "endpoint evidence": assessment.endpoint?.category || "Unavailable",
        "frozen plan hash": assessment.startup_plan_sha256 || assessment.session_plan_sha256 || "Unavailable"}));
      if (startup && assessment) panel.append(facts({
        "startup scans and control state": assessment.startup_evidence_verified === true ? "Independently checked" : "Not verified",
        "initial elbow position (counts)": assessment.initial_elbow_position,
        "commanded delta (counts)": assessment.command_delta_counts,
        "automatic retry": "Disabled",
        "stylus-tip accuracy": "Not measured"}));
      if (assessment?.baseline) panel.append(facts({
        "pre-write baseline": assessment.baseline.recomputed_accepted === true ? "Independently checked" : "Not verified",
        "baseline position (counts)": assessment.baseline.position_count,
        "baseline goal (counts)": assessment.baseline.goal_count,
        "baseline age at write (microseconds)": assessment.baseline.age_at_write_us,
        "physical clearance": "Not established by servo feedback"}));
      if (assessment?.start_record) panel.append(facts({
        "controller-reported authorization": "Plan identity matched",
        "authorization phase": assessment.start_record.phase,
        "authenticated telemetry provenance": "Not verified"}));
      if (assessment?.whole_arm_baseline) panel.append(facts({
        "whole-arm baseline": "Seven servo reads independently checked",
        "oldest read age at write (microseconds)": assessment.whole_arm_baseline.oldest_read_age_at_write_us,
        "whole-arm physical clearance": "Not established by servo feedback"}));
      if (outcome.status === "PARTIAL_FAILURE_ASSESSED") panel.append(facts({
        "supported admission failure": assessment.supported_reason,
        "dispatch evidence": "Absent — does not prove no physical motion",
        "automatic retry": "Disabled"}));
      return;
    }
    if (operation.action_id === "simulate_servo_diagnostics") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Servo diagnostics — simulation only", "No arm commands. Software rehearsal completion does not establish hardware target acceptance, encoder freshness or physical accuracy.");
      box.append(panel);
      const outcome = report?.outcome, assessment = outcome?.assessment;
      const valid = report?.schema === "rocell.servo_diagnostic_rehearsal.v1"
        && report.origin === "SIMULATION" && report.motion_commands === 0
        && report.progression_authority === false && report.physical_accuracy_verified === false
        && ["TRACE_ASSESSED", "TRACE_REJECTED"].includes(outcome?.status)
        && (outcome.status === "TRACE_REJECTED" ? assessment === null
          : assessment?.schema === "rocell.servo_diagnostic_assessment.v1"
            && assessment.origin === "SIMULATION" && assessment.progression_authority === false
            && assessment.physical_accuracy_verified === false && assessment.provenance_verified === false);
      if (!valid) {
        panel.append(element("p", "notice warning", "Diagnostic summary unavailable or inconsistent. No result is inferred.")); return;
      }
      panel.append(facts({scenario: report.scenario, "trace validation": outcome.status,
        "diagnostic outcome": assessment?.category || "Rejected trace — no endpoint verdict",
        "export integrity": report.export?.verified === true ? "Verified" : "Not verified",
        "offline replay": report.replay_verified === true ? "Verified" : "Not verified",
        "hardware qualification": "NOT QUALIFIED"}));
      if (assessment) {
        panel.append(facts({"synthetic matching target readback": assessment.matching_target_readback_observed === true ? "Observed" : "Not observed",
          "synthetic fresh position samples": Number.isSafeInteger(assessment.fresh_position_samples) && assessment.fresh_position_samples >= 0 ? assessment.fresh_position_samples : "Unavailable",
          "synthetic final desired error (counts)": Number.isSafeInteger(assessment.final_desired_error_counts) ? assessment.final_desired_error_counts : "Unavailable"}));
        const evidence = report.evidence_summary;
        if (evidence?.schema === "rocell.servo_diagnostic_summary.v1"
            && evidence.origin === "SIMULATION" && evidence.source_sha256 === report.raw_sha256
            && evidence.progression_authority === false && evidence.physical_accuracy_verified === false) {
          const count = value => Number.isSafeInteger(value) ? value : "Unavailable";
          panel.append(facts({"synthetic controller receipt": evidence.stages?.controller_receipt,
            "synthetic bus dispatch": evidence.stages?.bus_dispatch,
            "final target read status": evidence.stages?.target_readback,
            "final position read status": evidence.stages?.position_acquisition,
            "desired target (counts)": count(evidence.desired_count),
            "transmitted target (counts)": count(evidence.wire_count),
            "final register target (raw counts)": count(evidence.final_target_count),
            "final measured position (counts)": count(evidence.final_position_count),
            "position minus transmitted target": count(evidence.position_minus_wire),
            "position minus register target": count(evidence.position_minus_readback),
            "torque enable": evidence.torque_enable, "operating mode": evidence.operating_mode}));
          panel.append(element("p", "caption", "All values above are synthetic. Raw speed/load/voltage/temperature/current fields, where acquired, are retained in the export without physical-unit scaling. Unavailable does not mean zero or disabled."));
        } else if (evidence !== undefined && evidence !== null) {
          panel.append(element("p", "notice warning", "Detailed evidence summary unavailable or inconsistent."));
        }
      }
      panel.append(element("p", "caption", "Inspect retained structured results for source hashes and the export folder. No automatic retry or hardware command is offered here."));
      return;
    }
    if (operation.action_id === "review_product_ghost_case") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Full-size keyboard simulation review", "Saved synthetic endpoints only. No replay or physical accuracy claim.");
      box.append(panel);
      if (report?.schema !== "rocell.product_ghost_export_review.v1" || report.motion_authorized !== false || report.hardware_access !== false) {
        panel.append(element("p", "notice warning", "Product review unavailable or inconsistent.")); return;
      }
      panel.append(facts({status: report.status, fault: report.fault, planned: report.planned,
        attempted: report.attempted, skipped: report.skipped, "plan hash": report.plan_sha256}));
      for (const row of (report.legs || []).slice(0, 128)) {
        panel.append(facts({key: row.key, phase: row.phase, status: row.status, "simulated writes": row.simulated_writes}));
      }
      return;
    }
    if (operation.action_id === "rehearse_ghost_endpoints") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Ghost endpoint simulation", "Synthetic feedback and transport only. No arm or camera access.");
      box.append(panel);
      if (report?.schema !== "rocell.ghost_endpoint_rehearsal.v1" || report.physical_authority !== false) {
        panel.append(element("p", "notice warning", "Endpoint simulation unavailable.")); return;
      }
      panel.append(facts({status: report.status, fault: report.fault, "attempted trials": report.trial_results?.length,
        "skipped after fault": report.skipped_trial_ids?.length, "zero-motion legs": report.no_motion_leg_sequences?.join(", "),
        "physical motion commands": report.physical_motion_commands}));
      for (const row of (report.trial_results || []).slice(0, 32)) {
        panel.append(facts({status: row.trial?.status, fault: row.fault, "simulated writes": row.simulated_wire_writes?.length}));
      }
      return;
    }
    if (operation.action_id === "rehearse_ghost_keyboard") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Ghost keyboard route", "Nominal free-space preview. No camera or motion; not physical key accuracy.");
      box.append(panel);
      if (report?.schema !== "rocell.ghost_keyboard_rehearsal.v1" || report.motion_authorized !== false) {
        panel.append(element("p", "notice warning", "Ghost preview unavailable.")); return;
      }
      panel.append(facts({status: report.status, keys: report.requested_keys?.join(" → "),
        legs: report.legs?.length, "layout hash": report.layout_sha256,
        "physical clearance": "NOT VERIFIED", "endpoint dynamics": "NOT SIMULATED"}));
      for (const leg of (report.legs || []).slice(0, 32)) {
        panel.append(facts({key: leg.key, phase: leg.phase, "target XYZ/pitch": leg.target?.join(", "), samples: leg.samples?.length}));
      }
      return;
    }
    if (operation.action_id === "review_tap_capture") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Phone tap observation", "Supplied browser events; CSS pixels are not physical coordinates or proof of a robot tap.");
      box.append(panel);
      if (report?.schema !== "rocell.tap_capture_review.v1" || report.motion_authorized !== false || report.robot_tap_confirmed !== false) {
        panel.append(element("p", "notice warning", "Tap review unavailable or inconsistent.")); return;
      }
      panel.append(facts({status: report.status, expected: report.expected_taps, clicks: report.observed_clicks,
        issues: report.issues?.join(", ") || "none", "robot caused input": "NOT ESTABLISHED"}));
      return;
    }
    if (operation.action_id === "review_input_capture") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Keyboard input observation", "Browser transcript only—not robot attribution, contact qualification or arm telemetry.");
      box.append(panel);
      if (report?.schema !== "rocell.input_capture_review.v1" || report.motion_authorized !== false || report.robot_press_confirmed !== false) {
        panel.append(element("p", "notice warning", "Input review unavailable or inconsistent.")); return;
      }
      panel.append(facts({status: report.status, expected: report.expected, observed: report.observed_text,
        "key presses": report.press_count, events: report.event_count, "stop reason": report.stop_reason,
        issues: report.issues?.join(", ") || "none", "robot caused input": "NOT ESTABLISHED"}));
      return;
    }
    if (operation.action_id === "review_cartesian_export") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Saved joint-response review", "Historical controller telemetry only. No movement or replay; not independent tool-tip accuracy.");
      box.append(panel);
      if (report?.schema !== "rocell.cartesian_export_review.v1" || report.motion_authorized !== false || report.hardware_access !== false) {
        panel.append(element("p", "notice warning", "Review unavailable or inconsistent."));
        return;
      }
      panel.append(facts({"source export": report.source_export_id, "recorded outcome": report.source_status,
        "reported samples": report.reported_sample_count, "XYZ target error (mm)": report.position_error_mm ?? "unknown",
        "next step": report.next_step, "physical readiness": "NOT QUALIFIED"}));
      for (const row of (report.joint_comparison || []).slice(0, 6)) {
        panel.append(facts({joint: row.joint, commanded: row.commanded ? "yes" : "no",
          "predicted count change": row.predicted_count_change ?? "not commanded",
          "reported count change": row.reported_count_change, response: row.response}));
      }
      panel.append(element("p", "caption", "Counts are reconstructed using reference firmware equations, not captured bus writes. Missing or opposite response needs investigation; this review never applies compensation."));
      return;
    }
    if (operation.action_id === "rehearse_static_task") {
      const report = operation.result?.steps?.[0]?.report;
      const route = report?.dense_route;
      const batch = route?.round;
      const task = report?.task_summary;
      const panel = card("Static-camera task rehearsal — simulation only", "Nominal board/tool geometry. No camera capture, arm commands or physical contact. Passing does not enable hardware.");
      panel.append(facts({
        "route outcome": report?.status || "unavailable",
        "camera architecture": report?.architecture || "unavailable",
        "device": report?.device || "unavailable",
        "requested targets (including repeats)": task?.requested_target_count ?? "unavailable",
        "target order": task?.requested_targets?.join(" → ") || "unavailable",
        "simulation park (board mm)": report?.park_selection?.xy_board_mm?.join(", ") || "unavailable",
        "waypoints evaluated": batch?.evaluated_waypoint_count ?? "unavailable",
        "waypoints planned": batch?.waypoint_count ?? "unavailable",
        "first failure": batch?.failure_reason || (batch?.all_waypoints_accepted === true ? "none in sampled checks" : "unavailable"),
        "failed target / phase": task?.first_failure ? `${task.first_failure.target || "no target"} / ${task.first_failure.phase}` : "none reported",
        "physical motion authorized": "no"
      }));
      panel.append(element("p", "", "Use Export logs to retain the complete numerical route and its source hashes. Full-arm clearance and installed accuracy remain unverified."));
      panel.append(detail(report || {}, "Inspect full static route evidence"));
      box.append(panel);
    }
    if (["run_wifi_roll_sweep_low_trial", "run_wifi_roll_sweep_center_trial", "run_wifi_roll_sweep_high_trial", "run_wifi_roll_trial", "run_wifi_roll_negative_trial", "run_wifi_roll_low_trial", "run_wifi_roll_high_trial", "run_wifi_roll_zero_trial", "run_wifi_roll_center_up_trial", "run_wifi_roll_center_down_trial", "run_wifi_roll_corrected_up_trial", "run_wifi_roll_corrected_down_trial", "run_wifi_roll_probe_low_trial", "run_wifi_roll_probe_high_trial", "run_wifi_roll_lookup_trial", "run_wifi_roll_adjacent_trial", "run_wifi_roll_adjacent_low_trial", "run_wifi_roll_adjacent_high_trial", "run_wifi_roll_adjacent_lookup_trial"].includes(operation.action_id)) {
      const panel = card("Single Wi-Fi roll trial", "Live command; no automatic return or retry. Controller endpoint verification is not external tool-tip accuracy.");
      const move = operation.result?.move_result;
      if (move) {
        const degrees = value => Number.isFinite(value) ? `${value.toFixed(5)}°` : "unavailable";
        panel.append(facts({
          "request": move.request_id,
          "native request": move.native_request_id || "unavailable",
          "configuration": move.configuration_id || "unavailable",
          "movement outcome": move.status,
          "native state": move.native_state || "unavailable",
          "desired endpoint": degrees(move.desired_deg),
          "commanded angle": degrees(move.commanded_deg),
          "last reported angle (not independently measured)": degrees(move.last_reported_deg),
          "reported minus desired": degrees(move.reported_minus_desired_deg),
          "endpoint verified by controller telemetry": move.endpoint_verified ? "yes" : "no",
          "command attempts": move.command_attempts ?? "unavailable"
        }));
      }
      panel.append(detail(operation.result?.steps?.[0]?.report || {}, "Inspect full movement evidence"));
      box.append(panel);
    }
    if (operation.action_id === "run_micro_commissioning") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Single micro-command commissioning", "Live experiment: one predecessor and at most one micro-command. No automatic retry or return. Reported settling is not physical accuracy.");
      panel.append(facts({status: report?.status || "unavailable", reason: report?.reason || "", "final export": report?.final_export_succeeded ? "saved" : "not confirmed"}));
      for (const leg of report?.summary?.legs || []) {
        const degrees = value => Number.isFinite(value) ? `${value.toFixed(5)}°` : "unavailable";
        panel.append(element("h4", "", leg.leg));
        panel.append(facts({
          "leg status": leg.status,
          "commanded angle": degrees(leg.command_deg),
          "desired endpoint": degrees(leg.desired_deg),
          "reported endpoint": degrees(leg.observed_deg),
          "reported minus command": degrees(leg.command_error_deg),
          "reported minus desired": degrees(leg.desired_error_deg),
          "hold status": leg.hold_status,
          "hold readings": leg.hold_samples ?? "unavailable",
          "maximum hold gap (ms)": Number.isFinite(leg.hold_max_gap_ms) ? leg.hold_max_gap_ms.toFixed(3) : "unavailable"
        }));
      }
      panel.append(element("p", "", "Display summary from retained controller telemetry, not an independent accuracy measurement. Missing values are unavailable, not zero. Inspect the full report for failures."));
      panel.append(detail(report || {}, "Inspect full commissioning report"));
      box.append(panel);
    }
    if (operation.action_id === "simulate_micro_correction") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Micro-correction diagnostics — simulation only", "No arm commands. Passing these checks does not enable live micro-movement or establish physical accuracy.");
      panel.append(facts({status: report?.status || "unavailable", "checks passed": report?.checks?.filter(item => item.passed).length || 0, "live authority from simulation": "none"}));
      panel.append(element("pre", "", JSON.stringify(report || {}, null, 2)));
      box.append(panel);
    }
    if (operation.action_id === "simulate_discrete_transaction") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Discrete transaction simulation", "In-memory tests only. No hardware commands or physical endpoint qualification.");
      panel.append(element("pre", "", JSON.stringify(report || {}, null, 2)));
      box.append(panel);
    }
    if (["observe_arm_wifi_feedback", "observe_arm_wifi_feedback_fast", "observe_arm_wifi_feedback_spaced", "observe_arm_wifi_feedback_intermediate", "observe_arm_wifi_bounded"].includes(operation.action_id)) {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("35-second Wi-Fi observation", "Feedback only. Original numeric responses retained; no movement qualification or freshness claim.");
      if (["rocell.arm_wifi_observation.v1", "rocell.arm_wifi_observation.v2", "rocell.arm_wifi_observation.v3", "rocell.arm_wifi_observation.v4"].includes(report?.schema)) {
        panel.append(facts({status: report.status, "stop reason": report.stop_reason,
          "requests attempted": report.request_attempts, "elapsed seconds": report.elapsed_s}));
        if (report.schema === "rocell.arm_wifi_observation.v3") {
          panel.append(element("p", "notice warning", "500 ms cooldown diagnostic. Discrete testing uses a provisional 1-second feedback-gap allowance; historical 250 ms counts are retained for comparison."));
        }
        if (report.schema === "rocell.arm_wifi_observation.v4") {
          panel.append(element("p", "notice warning", "150 ms cooldown: selected for discrete testing with a provisional 1-second feedback-gap allowance. Stationary timing alone does not verify a movement endpoint."));
        }
        panel.append(element("pre", "", JSON.stringify(report.reconstruction || {}, null, 2)));
        if (report.discrete_timing_assessment) panel.append(element("pre", "", JSON.stringify(report.discrete_timing_assessment, null, 2)));
      } else panel.append(element("p", "notice warning", "No retained observation available."));
      box.append(panel);
    }
    if (operation.action_id === "sample_arm_wifi_feedback") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Wi-Fi feedback timing", "Finite sequential observations with identity checks—not streaming or movement qualification.");
      if (report?.schema === "rocell.arm_wifi_sampling.v1") {
        panel.append(facts({status: report.status, "stop reason": report.stop_reason,
          successful: report.successful_samples, failed: report.failed_samples,
          "requests attempted": report.request_attempts}));
        panel.append(element("pre", "", JSON.stringify({http_ms: report.http_timing_ms,
          response_gaps_ms: report.response_completion_gaps_ms,
          reported_joint_spans_rad: report.reported_joint_span_rad}, null, 2)));
      } else panel.append(element("p", "notice warning", "No retained sampling result."));
      box.append(panel);
    }
    if (operation.action_id === "read_arm_wifi_feedback") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Wi-Fi joint feedback", "Read-only diagnostic. Not a motion baseline or independent tool-tip measurement.");
      if (report?.schema === "rocell.arm_wifi_feedback.v1") {
        panel.append(facts({status: report.status, address: report.address,
          "request attempts": report.request_attempts, "elapsed ms": report.elapsed_ms,
          "movement commands": report.motion_commands, reason: report.reason || "none"}));
        if (report.joints_rad) panel.append(element("pre", "", JSON.stringify(report.joints_rad, null, 2)));
        if (report.servo_status) {
          const servo = report.servo_status;
          const elbow = servo.torque_switches?.elbow;
          panel.append(facts({"reported elbow torque switch": elbow === true ? "ON" : elbow === false ? "OFF" : "NOT REPORTED",
            "reported elbow load (raw)": servo.loads_raw?.elbow ?? "NOT REPORTED",
            "reported supply voltage (V)": servo.voltage_v ?? "NOT REPORTED",
            "missing torque states": servo.missing_torque_switches?.join(", ") || "none"}));
          panel.append(element("p", "caption", "Raw load is not calibrated contact force. Missing torque or voltage fields do not establish actuator health."));
        }
        if (report.controller_cartesian) {
          const cart = report.controller_cartesian;
          panel.append(facts({"controller Cartesian feedback": cart.status,
            "missing Cartesian fields": cart.missing_fields?.join(", ") || "none",
            "controller X (mm)": cart.values?.x ?? "unavailable",
            "controller Y (mm)": cart.values?.y ?? "unavailable",
            "controller Z (mm)": cart.values?.z ?? "unavailable",
            "controller pitch (rad)": cart.values?.tit ?? "unavailable",
            "model/board correlation": "not verified"}));
          panel.append(element("p", "", "Joint readings alone do not establish a board or stylus-tip position. Missing Cartesian fields are not zero coordinates."));
        }
      } else panel.append(element("p", "notice warning", "No retained Wi-Fi feedback result."));
      box.append(panel);
    }
    if (operation.action_id === "run_positional_campaign") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Reported endpoint quality", "Delivery and settling do not prove precision. Controller reports are not external tool-tip measurements.");
      const endpoints = report?.endpoint_diagnostics;
      if (!Array.isArray(endpoints) || !endpoints.length) {
        panel.append(element("p", "notice warning", "No reconstructed endpoint quality available; inspect retained diagnostics."));
      } else for (const endpoint of endpoints) {
        const q = endpoint.quality_assessment;
        if (q?.schema !== "rocell.endpoint_quality.v1" || q.motion_authorized !== false) {
          panel.append(element("p", "caption", "Quality assessment unavailable in this retained result. No precision pass is inferred."));
          continue;
        }
        panel.append(facts({leg: endpoint.leg_id, arrival: q.arrival_status,
          persistence: q.persistence_status, "precision screen": q.precision_status,
          "absolute error (degrees)": q.absolute_error_deg, "diagnostic threshold (degrees)": q.precision_screen_deg,
          repeatability: q.repeatability_status, "next starting position": q.next_start_status}));
        panel.append(element("p", "caption", "The 0.1-degree screen is diagnostic only; historical verdicts and motion permissions are unchanged. Fresh feedback is required before another command."));
      }
      box.append(panel);
    }
    if (operation.action_id === "positional_campaign_boundary_tests") {
      const step = operation.result?.steps?.[0];
      const panel = card("Owned movement pipeline — software tests", "Synthetic I/O only. Passing tests do not release native movement or verify a physical stop.");
      if (step?.name === "registered_positional_suite" && typeof step.report?.output === "string") {
        panel.append(element("p", step.exit_code === 0 ? "notice" : "notice warning", step.exit_code === 0 ? "Registered software suite passed" : "Software suite failed — inspect retained output"));
        panel.append(element("pre", "", step.report.output.slice(0, 16000)));
        panel.append(element("p", "caption", "Use Export diagnostic report to retain this output in the workspace export folder."));
      } else panel.append(element("p", "notice warning", "Test report unavailable. No pass is inferred."));
      box.append(panel);
    }
    if (operation.action_id === "positional_campaign_rehearse") {
      const report = operation.result?.steps?.[0]?.report;
      const panel = card("Automatic positional testing — simulation", "No hardware commands or unattended release. Every target is synthetic.");
      if (report?.schema === "rocell.positional_campaign_rehearsal.v1") {
        panel.append(element("p", "notice", human(report.status)));
        panel.append(element("p", "caption", `Simulated writes: ${report.simulated_write_count}; physical writes: ${report.physical_write_count}`));
        for (const leg of report.legs || []) panel.append(element("p", "caption", `${leg.leg_id}: ${human(leg.status)} — ${human(leg.reason || leg.endpoint?.status)}`));
        panel.append(element("p", "caption", `Skipped legs: ${(report.skipped_leg_ids || []).join(", ") || "none"}`));
      } else panel.append(element("p", "notice warning", "Retained campaign report unavailable."));
      box.append(panel);
    }
    if (["run_observational_movement", "record_observational_movement"].includes(operation.action_id)) {
      const report = operation.result?.steps?.[0]?.report;
      const endpoint = (report?.summary?.rebuilt_trial?.analysis || report?.assessment?.analysis)?.endpoint_verification;
      const panel = card("Software endpoint verification", "Controller-reported evidence; not calibrated physical accuracy or permission for another move.");
      if (endpoint?.schema !== "rocell.reported_wrist_endpoint.v1") {
        panel.append(element("p", "notice warning", "Endpoint verification unavailable in this retained result. No success or automatic progression is inferred."));
      } else {
        panel.append(element("p", endpoint.endpoint_verified === true ? "notice" : "notice warning", human(endpoint.status)));
        for (const [label, value] of [["Movement detected", endpoint.movement_detected], ["Target band entered", endpoint.target_band_entered], ["Final position in target band", endpoint.final_in_target_band], ["Reported endpoint settled", endpoint.endpoint_verified]]) {
          panel.append(element("p", "caption", `${label}: ${value === true ? "yes" : value === false ? "no" : "unavailable"}`));
        }
        if (Number.isFinite(endpoint.final_error_rad)) panel.append(element("p", "caption", `Reported final target error: ${(endpoint.final_error_rad * 180 / Math.PI).toFixed(3)} degrees`));
        panel.append(element("p", "caption", "Automatic next command remains disabled. A separate current admission is required."));
      }
      box.append(panel);
    }
    if (operation.action_id === "movement_saved_capture_review") {
      const steps = operation.result?.steps;
      const saved = Array.isArray(steps) && steps.length === 1 ? steps[0]?.report : null;
      const panel = card("Saved arm telemetry review", "Historical data only; no device was opened.");
      box.append(panel);
      if (saved?.schema !== "rocell.wizard_saved_capture_analysis.v1" || saved.physical_authority !== false || saved.sample_freshness_verified !== false) {
        panel.append(element("p", "notice warning", "Saved capture summary unavailable or inconsistent."));
        return;
      }
      panel.append(facts({"capture hash":saved.coverage?.raw_sha256,
        "complete poses":saved.coverage?.counts?.POSE_TELEMETRY,
        "rejected lines":saved.coverage?.counts?.REJECTED_LINE,
        "retained bytes":saved.coverage?.retained_bytes,
        "processed complete-line bytes":saved.coverage?.processed_complete_line_bytes,
        "coverage":saved.coverage?.status,
        "unprocessed byte range":JSON.stringify(saved.coverage?.unprocessed_range),
        "current connection / freshness":"NOT ESTABLISHED"}));
      panel.append(element("p", "notice warning", "Parsing coverage is not movement qualification. Export logs retains the reanalysis, original capture bytes and read windows."));
      return;
    }
    if (operation.action_id === "review_endpoint_campaign") {
      const report = operation.result?.steps?.length === 1 ? operation.result.steps[0]?.report : null;
      const panel = card("Saved endpoint campaign", "Historical observations only; no hardware action or settings change.");
      box.append(panel);
      if (report?.schema !== "rocell.endpoint_campaign_analysis.v1" || report.motion_authorized !== false ||
          report.physical_ready !== false || report.recommended_settings !== null || !Array.isArray(report.groups)) {
        panel.append(element("p", "notice warning", "Campaign summary unavailable or inconsistent. Inspect the error and original exports."));
        return;
      }
      panel.append(facts({"plan hash":report.plan_sha256,"selected attempts":report.selected_attempt_ids?.length,
        "settings recommendation":report.recommendation_status,"continuous motion":"NOT OBSERVED"}));
      for (const group of report.groups.slice(0, 128)) {
        panel.append(element("p", "caption", `${Array.isArray(group.trial_ids) ? group.trial_ids.join(", ") : "Unknown trials"}: ${group.eligible_count} eligible; ${group.status}; reported endpoint spread (mm): ${group.reported_endpoint_spread_mm ?? "unavailable"}.`));
      }
      for (const limitation of report.limitations || []) panel.append(element("p", "caption", limitation));
      return;
    }
    if (operation.action_id === "movement_endpoint_review") {
      const report = operation.result?.steps?.length === 1 ? operation.result.steps[0]?.report : null;
      const panel = card("Exact endpoint request", "Inspection only—this does not approve or run the arm.");
      box.append(panel);
      if (report?.schema !== "rocell.endpoint_request_review.v1" || report.physical_authority !== false ||
          report.motion_approved !== false || report.device_open_count !== 0 || report.serial_write_count !== 0) {
        panel.append(element("p", "notice warning", "Review summary is unavailable or inconsistent. No approval inferred."));
        return;
      }
      panel.append(facts({"trial":report.trial_id,"request hash":report.request_sha256,"frame":report.frame,
        "speed coefficient":report.spd,"dwell (s)":report.dwell_s,"observation timeout (s)":report.timeout_s}));
      for (const row of report.axes || []) panel.append(element("p", "caption",
        `${row.axis}: ${row.start} → ${row.target} ${row.unit} (change ${row.delta})`));
      panel.append(element("p", "notice warning", report.speed_meaning));
      panel.append(element("p", "caption", "Operator checks required: " + (report.operator_checks || []).map(human).join(", ")));
      panel.append(element("p", "caption", "Engineering checks required: " + (report.engineering_checks || []).map(human).join(", ")));
      for (const note of report.limitations || []) panel.append(element("p", "caption", note));
      return;
    }
    if (operation.action_id === "movement_endpoint_rehearse") {
      const report = operation.result?.steps?.length === 1 ? operation.result.steps[0]?.report : null;
      const panel = card("Single endpoint rehearsal", "Synthetic byte streams only—no arm movement.");
      box.append(panel);
      if (report?.schema !== "rocell.wizard_endpoint_rehearsal.v1" || report.basis !== "SYNTHETIC_REHEARSAL" ||
          report.physical_authority !== false || report.native_device_opens !== 0 || report.physical_motion_commands !== 0) {
        panel.append(element("p", "notice warning", "Rehearsal summary unavailable or inconsistent. No readiness inferred."));
        return;
      }
      const trial = report.trial;
      panel.append(facts({"selected trial":report.request?.trial_id, "fault":report.fault,
        "trial outcome":trial?.status, "baseline":trial?.baseline?.status || "NOT CAPTURED",
        "simulated write":trial?.write?.status || "NOT SENT", "endpoint evidence":trial?.analysis?.status || "NOT ESTABLISHED",
        "cleanup":trial?.cleanup?.status || "UNKNOWN", "physical readiness":"NOT QUALIFIED"}));
      panel.append(element("p", "notice warning", "No automatic return or retry. An observed synthetic endpoint does not establish hardware movement, clearance, stopping, or speed settings."));
      panel.append(element("p", "caption", "Export logs retains the request, original baseline/post bytes, read timing, write result and cleanup status."));
      return;
    }
    if (!["movement_campaign_preview", "movement_campaign_simulate"].includes(operation.action_id)) return;
    const steps = operation.result?.steps;
    const report = Array.isArray(steps) && steps.length === 1 ? steps[0]?.report : null;
    const panel = card("Movement campaign summary", "Synthetic evidence only. A completed diagnostic is not a successful physical movement.");
    box.append(panel);
    if (report?.schema !== "rocell.wizard_movement_campaign.v1" || report.basis !== "SYNTHETIC_REHEARSAL" || report.physical_authority !== false) {
      panel.append(element("p", "notice warning", "Campaign summary unavailable or inconsistent. Inspect the retained record; no readiness is inferred."));
      return;
    }
    const controller = report.controller_model;
    const controllerConsistent = controller?.schema === "rocell.characterization_controller.v1" &&
      controller.plan_sha256 === report.preview?.plan_sha256 && controller.timing_available === false &&
      controller.motion_authorized === false && controller.physical_ready === false;
    panel.append(facts({"plan hash": report.preview?.plan_sha256,
      "coordinate frame": report.preview?.frame, "geometry": report.geometry?.status || "UNKNOWN",
      "controller path model": controllerConsistent ? controller.status : "UNAVAILABLE OR INCONSISTENT",
      "reference inverse kinematics": controllerConsistent ? (controller.reference_ik_status || "NOT EVALUATED") : "UNAVAILABLE OR INCONSISTENT",
      "campaign outcome": report.simulation?.status || "PREVIEW ONLY",
      "physical readiness": "NOT QUALIFIED", "speed units": "FIRMWARE COEFFICIENT (not mm/s)"}));
    if (controllerConsistent && Array.isArray(controller.trials)) {
      for (const trial of controller.trials.slice(0, 4)) {
        const ik = trial.reference_ik;
        if (!ik) continue;
        panel.append(element("p", "caption", `${trial.trial_id}: ${ik.status}; ${ik.evaluated_samples}/${trial.sample_count} reference samples checked.`));
        if (ik.first_failure) panel.append(element("p", "notice warning", `Reference IK unresolved at sample ${ik.first_failure.sample_index}: ${ik.first_failure.reason}. This branch is not qualified for this path.`));
      }
    }
    panel.append(element("p", "notice warning", "Reference IK is numerical screening only. Installed joint limits, roll/gripper, full-link and cable clearance remain unqualified. Synthetic travel timing is not a speed recommendation."));
    panel.append(element("p", "caption", "Controller interpolation samples have no elapsed timing. The separate linear rehearsal tests analysis and failure handling; neither verifies installed firmware or predicts actual movement duration."));
    panel.append(element("p", "notice warning", "Pinned reference T104 blocks normal pose-feedback refresh. Its stop flag exits interpolation but is not a verified servo hold. Continuous in-motion monitoring and stopping remain unqualified on the received arm."));
    panel.append(element("p", "caption", "Selected commissioning sequence: supervised endpoint measurements first, continuous motion measurements later. This choice does not arm a trial or approve any target."));
    const comparison = report.campaign_analysis;
    if (comparison?.schema === "rocell.movement_campaign_analysis.v1" &&
        comparison.plan_sha256 === report.preview?.plan_sha256 && comparison.motion_authorized === false &&
        comparison.physical_ready === false && comparison.recommended_settings === null && Array.isArray(comparison.groups)) {
      panel.append(element("p", "caption", "Repeatability comparison: reported endpoints only; hardware settings NOT QUALIFIED. Three eligible repetitions per identical route and coefficient are required by this rehearsal."));
      for (const group of comparison.groups.slice(0, 4)) {
        panel.append(element("p", "caption", `${Array.isArray(group.trial_ids) ? group.trial_ids.join(", ") : "Unknown trials"}: ${group.eligible_count} eligible; ${group.status}.`));
      }
    }
    const endpointComparison = report.endpoint_campaign_analysis;
    if (endpointComparison?.schema === "rocell.endpoint_campaign_analysis.v1" &&
        endpointComparison.plan_sha256 === report.preview?.plan_sha256 &&
        endpointComparison.observation_contract === "SUPERVISED_ENDPOINT_ONLY" &&
        endpointComparison.motion_authorized === false && endpointComparison.physical_ready === false &&
        endpointComparison.recommended_settings === null && Array.isArray(endpointComparison.groups)) {
      panel.append(element("h3", "", "Endpoint-only comparison · synthetic evidence"));
      panel.append(element("p", "caption", "Initial travel is unobserved under this contract. Endpoint spread and host dwell-entry timing do not establish travel speed, path clearance or physical stopping."));
      for (const group of endpointComparison.groups.slice(0, 4)) {
        panel.append(element("p", "caption", `${Array.isArray(group.trial_ids) ? group.trial_ids.join(", ") : "Unknown trials"}: ${group.eligible_count} eligible; ${group.status}.`));
      }
    }
    const trials = report.simulation?.trial_results;
    if (!Array.isArray(trials)) return;
    const table = element("table", "facts");
    table.append(element("caption", "", "Per-trial synthetic results"));
    const header = element("tr");
    for (const label of ["Trial", "Outcome", "Endpoint error (mm)", "Observed overshoot (mm)", "Settling evidence", "Issues"]) header.append(element("th", "", label));
    const head = element("thead"); head.append(header); table.append(head);
    const body = element("tbody");
    const number = value => typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "Unavailable";
    for (const trial of trials.slice(0, 4)) {
      const a = trial.wire_evidence?.analysis, row = element("tr");
      const values = [trial.trial_id, trial.status, number(a?.latest_reported_endpoint?.position_error_mm),
        number(a?.peak_observed_directional_overshoot_mm),
        a?.status === "OBSERVED_SETTLING" ? "Observed in synthetic data only" : "Not established",
        Array.isArray(a?.issues) ? a.issues.join(", ") || "None reported" : "No analysis"];
      for (const value of values) row.append(element("td", "", String(value ?? "Unavailable")));
      body.append(row);
    }
    table.append(body); panel.append(table);
    if (Array.isArray(report.simulation?.skipped_trial_ids) && report.simulation.skipped_trial_ids.length) panel.append(element("p", "notice warning", "Skipped: " + report.simulation.skipped_trial_ids.join(", ")));
    panel.append(element("p", "caption", "Export diagnostics preserves original synthetic bytes, read windows and full analysis. Expand the retained record for detail."));
  }

  function taskSimulationFeedback(operation) {
    // The service already exposes the one named CLI report status. Interpret
    // only that summary, not arbitrary nested evidence or a cached full result.
    // Successful process exit and sampled IK convergence are distinct claims.
    let meaning = "Simulation outcome is unavailable or inconsistent.";
    const status = operation.status;
    if (["QUEUED", "RUNNING", "CANCELLED", "TIMED_OUT"].includes(status)) {
      meaning = "Simulation has not completed; no feasibility result is inferred.";
    } else if (["SUCCEEDED", "FAILED"].includes(status) && Array.isArray(operation.steps) && operation.steps.length === 1) {
      const step = operation.steps[0];
      if (step && !Array.isArray(step) && step.name === "simulate_task" && Number.isInteger(step.exit_code)) {
        if (status === "SUCCEEDED" && step.exit_code === 0) {
          if (step.report_status === "PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS")
            meaning = "Simulation completed with unresolved reachability checks.";
          else if (step.report_status === "PASS_SIMULATION_ONLY_WITH_PHYSICAL_HOLDS")
            meaning = "Sampled nominal IK checks converged; the complete path is not qualified.";
        } else if (status === "FAILED" && step.exit_code !== 0 && step.report_status === "FAIL_SIMULATION_ONLY") {
          meaning = "Required simulation checks failed.";
        }
      }
    }
    return element("p", "notice warning task-simulation-feedback", meaning + " Worker success is not permission to move. Load the full retained result and export diagnostics for review. No camera, arm, motion or contact authorization is granted.");
  }
  function appendOperationCameraFaults(box, operation) {
    // Only this named server-owned report step carries this sidecar. Do not
    // recursively interpret arbitrary operation data as a current fault.
    const steps = operation?.result?.steps;
    if (!Array.isArray(steps) || steps.length > 32) return;
    for (const step of steps) if (step?.name === "retained-incapable-owned-camera-diagnostics" && step.report?.camera_fault_diagnostic !== undefined && step.report.camera_fault_diagnostic !== null)
      box.append(retainedCameraFault(step.report.camera_fault_diagnostic));
  }
  function appendCameraAssessmentResult(box, operation) {
    if (operation?.action_id !== "physical_camera_operating_assessment") return;
    const panel = element("section", "camera-assessment");
    panel.append(element("h3", "", "Saved assessment checklist"), element("span", "badge hold", "OPERATING APPROVAL HELD"));
    const labels = {
      REQUIRED_CONTROLS_SELECTED_MANUAL: "Required controls selected in manual mode",
      TWO_CAPTURE_REPORTS_PRESENT: "Two saved capture reports supplied",
      DISTINCT_PROBE_AND_CAPTURE_ATTEMPTS: "Probe and captures have distinct attempt references",
      BOTH_READBACKS_MATCH_AND_CLEANUP_CONFIRMED: "Both settings readbacks match and cleanup is confirmed",
      REPEATED_OBSERVED_FORMAT_AND_LAYOUT: "Captured format and image layout agree",
      SAME_CAPTURE_RUNTIME: "Both captures use the same recorded runtime",
    };
    const holds = {
      USB_SPEED_AND_IDENTITY_CONTINUITY_NOT_ASSESSED: "USB speed and device identity continuity still need assessment.",
      ORDERED_CLOSE_REOPEN_NOT_AUTHENTICATED: "The ordered close-and-reopen sequence is not authenticated.",
      PIXEL_FILES_NOT_VERIFIED: "Saved pixel files have not been verified by this assessment.",
      FRAME_FRESHNESS_NOT_ASSESSED: "Frame freshness has not been assessed.",
      SEPARATE_OPERATOR_REVIEW_NOT_RECORDED: "A separate operator review has not been recorded.",
      INSTALLED_OPTICS_AND_CALIBRATION_DEFERRED: "Installed focus, optics and placemat calibration are deferred until the build is ready.",
      PROPOSAL_AND_ASSESSMENT_ORIGINAL_STAGE_RETENTION_NOT_IMPLEMENTED: "Canonical stage storage for the proposal and assessment is not implemented yet.",
    };
    const worker = operation.result, steps = worker?.steps;
    const step = Array.isArray(steps) && steps.length === 1 ? steps[0] : null;
    const report = step?.report, preflight = report?.preflight;
    const checks = preflight?.checks, ids = Object.keys(labels), outstanding = Object.keys(holds);
    const falseFields = ["approved_operating_policy", "original_store_authenticated", "authenticated_operator_identity", "stage_passed", "physical_authority", "hardware_qualified", "camera_capture_authorized", "arm_access_authorized", "device_io_performed", "automatic_fallback"];
    const exactList = (actual, expected) => Array.isArray(actual) && actual.length === expected.length && actual.every((value, i) => value === expected[i]);
    const sealedV4 = report?.schema === "rocell.camera_original_operating_assessment.v4";
    const stagesV3 = sealedV4 || report?.schema === "rocell.camera_original_operating_assessment.v3";
    const pixelsV2 = stagesV3 || report?.schema === "rocell.camera_original_operating_assessment.v2";
    const pixels = pixelsV2 ? report.pixel_checks : [];
    const pixelLabels = {
      VERIFIED_AT_READ: "Saved pixels match the retained capture checksum",
      LOGGED_REFERENCE_UNAVAILABLE: "No usable logged pixel reference — not verified",
      REFERENCE_MISMATCH: "Capture reference does not match the original subject",
      PIXEL_FILE_UNAVAILABLE_OR_CHANGED: "Saved file is missing, changed or could not be safely read",
    };
    const pixelScope = "RETAINED_LAUNCH_COMPLETION_JOINED_TO_M1_NATIVE_CAPTURE";
    const sealedPixelScope = "M1_SEALED_CAPTURE_CHECKSUM";
    const sha = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value) && value !== "0".repeat(64);
    const validPixels = !pixelsV2 || (
      report.pixel_reference_scope === (sealedV4 ? "PER_CAPTURE_ORIGINAL_OR_LEGACY_REFERENCE" : pixelScope)
      && Array.isArray(pixels) && pixels.length <= 2
      && (!sealedV4 || pixels.some(p => p?.schema === "rocell.camera_operating_pixel_check.v2"))
      && Array.isArray(report.captures) && report.captures.length === pixels.length
      && new Set(pixels.map(p => p?.request_key)).size === pixels.length
      && new Set(pixels.map(p => p?.attempt_id)).size === pixels.length
      && pixels.every((p, i) => {
        const verified = p?.status === "VERIFIED_AT_READ";
        const hasReference = verified || p?.status === "PIXEL_FILE_UNAVAILABLE_OR_CHANGED";
        const sealed = sealedV4 && p?.schema === "rocell.camera_operating_pixel_check.v2";
        return p && Object.keys(p).length === (sealed ? 13 : 12)
          && p.schema === (sealed ? "rocell.camera_operating_pixel_check.v2" : "rocell.camera_operating_pixel_check.v1")
          && Object.hasOwn(pixelLabels, p.status) && p.reference_scope === (sealed ? sealedPixelScope : pixelScope)
          && (!sealed || (sha(p.capture_checksum_sha256)
            && p.capture_checksum_sha256 === report.captures[i]?.capture_checksum_sha256
            && sha(report.captures[i]?.permit_sha256) && p.result_sha256 === null))
          && typeof p.request_key === "string" && p.request_key.length > 0 && p.request_key.length <= 96
          && typeof p.attempt_id === "string" && p.attempt_id.length > 0 && p.attempt_id.length <= 96
          && p.request_key === report.captures[i]?.request_key && p.attempt_id === report.captures[i]?.attempt_id
          && p.content_verified_at_read === verified && p.frame_freshness_assessed === false
          && p.original_stage_record_retained === false && p.physical_authority === false
          && Number.isSafeInteger(p.verified_bytes) && (verified ? p.verified_bytes > 0 && p.verified_bytes <= 67108864 : p.verified_bytes === 0)
          && (hasReference ? (sealed || sha(p.result_sha256)) && sha(p.native_frame_sha256) : p.result_sha256 === null && p.native_frame_sha256 === null);
      })
    );
    const pixelsComplete = pixelsV2 && validPixels && pixels.length === 2
      && pixels.every(p => p.content_verified_at_read && (!sealedV4 || p.schema === "rocell.camera_operating_pixel_check.v2"));
    const expectedOutstanding = outstanding.filter(id => id !== "PIXEL_FILES_NOT_VERIFIED" || !pixelsComplete);
    const laterOwners = {
      FRAME_FRESHNESS_NOT_ASSESSED: ["camera_frame_freshness"],
      INSTALLED_OPTICS_AND_CALIBRATION_DEFERRED: ["optics_intrinsics", "static_registration"],
    };
    const ownership = report?.stage_requirements;
    const validOwnership = !stagesV3 || (
      ownership && !Array.isArray(ownership) && Object.keys(ownership).length === 9
      && ownership.schema === "rocell.camera_operating_stage_requirements.v1"
      && ownership.scope === "OWNERSHIP_PROJECTION_NOT_STAGE_ACCEPTANCE"
      && ownership.metadata_check_owner === "camera_mode_controls"
      && exactList(ownership.failed_metadata_checks, Array.isArray(preflight?.failed_checks) ? preflight.failed_checks : [])
      && ["stage_passed", "original_store_authenticated", "physical_authority", "hardware_qualified"].every(key => ownership[key] === false)
      && Array.isArray(ownership.requirements) && ownership.requirements.length === expectedOutstanding.length
      && ownership.requirements.every((row, i) => row && Object.keys(row).length === 3
        && row.id === expectedOutstanding[i]
        && row.scope === (Object.hasOwn(laterOwners, row.id) ? "LATER_STAGE" : "MODE_CONTROL_STAGE")
        && exactList(row.owner_stages, laterOwners[row.id] || ["camera_mode_controls"]))
    );
    // This is a closed display contract, NOT evidence authentication. Never
    // promote a successful worker, malformed report, or old result to readiness.
    const valid = operation.status === "SUCCEEDED" && operation.completion_log_persisted === true
      && operation.result_retention === "FULL_JSON_RETAINED"
      && worker?.schema === "rocell.wizard_worker_result.v1" && worker.action_id === operation.action_id && worker.status === "SUCCEEDED"
      && worker.physical_authority === false && worker.metadata_inventory_performed === false
      && ["device_open_count", "serial_write_count", "power_event_count", "motion_command_count", "contact_command_count"].every(key => worker[key] === 0)
      && step?.name === "original_operating_assessment" && step.exit_code === 0
      && (report?.schema === "rocell.camera_original_operating_assessment.v1" || pixelsV2) && report.status === "ORIGINAL_INPUTS_CHECKED_APPROVAL_HELD"
      && report.original_inputs_authenticated_at_read === true && report.currentness_requires_revalidation === true
      && ["original_stage_record_retained", "approved_operating_policy", "physical_authority", "hardware_qualified", "connected"].every(key => report[key] === false)
      && typeof report.proposal_sha256 === "string" && /^[a-f0-9]{64}$/.test(report.proposal_sha256)
      && preflight?.schema === "rocell.camera_operating_evidence_preflight.v1" && preflight.proposal_sha256 === report.proposal_sha256
      && falseFields.every(key => preflight[key] === false)
      && Array.isArray(checks) && checks.length === ids.length
      && checks.every((check, i) => check?.id === ids[i] && typeof check.satisfied === "boolean")
      && exactList(preflight.failed_checks, checks.filter(check => !check.satisfied).map(check => check.id))
      && preflight.status === (checks.every(check => check.satisfied) ? "CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW" : "BLOCKED_METADATA")
      && validPixels && validOwnership && exactList(report.unresolved_checks, expectedOutstanding);
    if (!valid) {
      panel.append(element("p", "notice warning", "Checklist unavailable: the retained result is incomplete, inconsistent, unlogged or not supported by this interface. Inspect the structured result and export diagnostics. No check is treated as passed."));
      box.append(panel); return;
    }
    panel.append(element("p", "", `${checks.filter(check => check.satisfied).length} of ${ids.length} metadata checks satisfied in this saved report. This is not a hardware-readiness score.`),
      element("p", "caption", "Historical result only: original inputs were checked when the assessment ran. Loading this report does not revalidate its source, settings, camera connection or calibration."));
    const list = element("ul", "camera-checklist");
    for (const check of checks) {
      const row = element("li", check.satisfied ? "check-recorded" : "check-held");
      row.append(element("span", "camera-check-state", check.satisfied ? "Satisfied" : "Not satisfied"), element("span", "", labels[check.id])); list.append(row);
    }
    panel.append(list);
    if (pixelsV2) {
      panel.append(element("h3", "", "Saved-pixel verification"), element("p", "caption", sealedV4
        ? "Each capture identifies an original receipt-bound checksum or an older launch-only reference. Legacy references are not promoted to originals. Saved-file integrity does not prove image freshness, optical quality or stage acceptance."
        : "Checksums come from retained launch completions joined to original native capture records. This checks saved file integrity, not image freshness, optical quality or canonical stage acceptance."));
      if (!pixels.length) panel.append(element("p", "notice warning", "No captures selected; saved pixels have not been checked."));
      for (const pixel of pixels) panel.append(element("p", pixel.content_verified_at_read ? "notice" : "notice warning", `${pixel.request_key}: ${pixelLabels[pixel.status]}${pixel.content_verified_at_read ? ` (${pixel.verified_bytes.toLocaleString()} bytes)` : ""}.${sealedV4 ? (pixel.schema === "rocell.camera_operating_pixel_check.v2" ? " Original receipt-bound checksum." : " Launch-only reference; not an original checksum record.") : ""}`));
    }
    const remaining = element("details", "camera-remaining");
    remaining.append(element("summary", "", `${expectedOutstanding.length} remaining requirements — approval stays on hold`));
    if (stagesV3) {
      remaining.append(element("p", "caption", "Requirements are grouped by their owning stage, not removed or approved. A mode/control review cannot qualify freshness, installed optics, placemat registration or arm motion."));
      for (const [scope, title] of [["MODE_CONTROL_STAGE", "Mode/control stage — original evidence and separate review"], ["LATER_STAGE", "Later camera stages — freshness and installed calibration"]]) {
        remaining.append(element("h3", "", title));
        if (scope === "MODE_CONTROL_STAGE" && ownership.failed_metadata_checks.length) remaining.append(element("p", "notice warning", `${ownership.failed_metadata_checks.length} metadata checks above also remain unsatisfied in this stage.`));
        const requirements = element("ul", "guide");
        for (const row of ownership.requirements.filter(row => row.scope === scope)) requirements.append(element("li", "", holds[row.id]));
        remaining.append(requirements);
      }
    } else {
      const requirements = element("ul", "guide");
      for (const id of expectedOutstanding) requirements.append(element("li", "", holds[id]));
      remaining.append(requirements);
    }
    panel.append(remaining, element("p", "caption", "Export diagnostics to preserve this assessment. A new application launch restores no operating approval."));
    box.append(panel);
  }
  function operationCameraDisplay(operation) {
    const steps = operation?.result?.steps;
    if (!Array.isArray(steps) || steps.length > 32) return operation;
    return {...operation, result: {...operation.result, steps: steps.map(step => {
      if (step?.name !== "retained-incapable-owned-camera-diagnostics" || !step.report || typeof step.report !== "object" || Array.isArray(step.report)) return step;
      const report = {...step.report}; delete report.camera_fault_diagnostic;
      return {...step, report};
    })}};
  }
  function reportRenderError(error) {
    state.renderFailed = true;
    clearDrafts("Ordinary drafts cleared after an interface error. Inspect status before re-entering values."); invalidatePreview();
    $("#connection-status").textContent = "Interface error · service may still be running";
    const message = "Interface rendering failed; backend action may still be running. Check diagnostics before retrying. Automatic status refresh is paused; use Refresh status after review. " + (error.message || String(error));
    state.lastError = message; showError(new Error(message));
  }
  function render() {
    try { renderView(); }
    catch (error) { reportRenderError(error); }
  }
  function renderView() {
    if (!state.view) return;
    const oldFocus = document.activeElement;
    const focusedBinding = [...state.formBindings.values()].find(binding => ordinaryControls(binding).some(([, input]) => input === oldFocus));
    const focus = focusedBinding ? {binding: focusedBinding, name: oldFocus.name,
      start: oldFocus.selectionStart, end: oldFocus.selectionEnd, direction: oldFocus.selectionDirection} : null;
    // Prune against the new view before any controls are created. Never bind an
    // event from an old DOM tree to a newly observed source or action contract.
    pruneDrafts();
    state.formBindings = new Map();
    // Snapshot native open state before replacing the tree, including a toggle
    // whose event is still queued. Only a focused disclosure summary is restored.
    const activeSummary = state.page === "camera" && cameraSectionIds.some(id => document.activeElement?.id === id + "-summary") ? document.activeElement.id : null;
    for (const id of cameraSectionIds) {
      const prior = document.getElementById?.(id);
      if (prior) state.cameraSections[id] = prior.open === true;
    }
    const view = state.view;
    $("#mode-badge").textContent = human(view.mode || "Unknown mode");
    $("#page-title").textContent = pages[state.page];
    const identity = $("#identity-bar"); identity.replaceChildren();
    for (const [name, value] of [["Cell", view.cell_id], ["Session", view.session_id], ["Status", view.status], ["Verification", view.verification], ["Source binding", view.source_binding_sha256?.slice(0, 16)]]) {
      if (value) { const span = element("span"); span.append(element("strong", "", name + " "), document.createTextNode(human(value))); identity.append(span); }
    }
    const banner = $("#authority-banner"); banner.replaceChildren();
    const rehearsal = /rehearsal|sim/i.test(view.mode || "");
    banner.append(element("strong", "", rehearsal ? "Rehearsal workspace · zero physical authority" : "Physical inspection workspace · activation is independently gated"));
    banner.append(element("span", "", rehearsal ? "Synthetic camera and arm observations exercise the real application flow. Nothing on this screen confirms the received hardware." : "Metadata, package readiness and a visible camera image are not permission to energize or move the arm. Follow current server-side holds."));
    $("#revision-label").textContent = `State revision ${view.revision} · ${human(view.authority || "No physical authority")}`;
    const content = $("#page-content");
    content.replaceChildren(({overview, commissioning, camera, arm, board, tasks, diagnostics, controls, activity}[state.page])());
    state.renderedContext = draftContext();
    if (focus && focus.binding.page === state.page && !$("#action-dialog").open) {
      const next = state.formBindings.get(focus.binding.box.id);
      if (next?.restored && next.context === focus.binding.context && next.contract === focus.binding.contract) {
        const control = ordinaryControls(next).find(([spec]) => spec.name === focus.name)?.[1];
        if (control && !control.disabled) {
          control.focus({preventScroll: true});
          // Number inputs reject setSelectionRange, even when a browser exposes
          // selection properties. Preserve their focus without fabricating a caret.
          if (control.type !== "number" && Number.isInteger(focus.start) && Number.isInteger(focus.end))
            control.setSelectionRange?.(focus.start, focus.end, focus.direction || "none");
        }
      }
    }
    if (activeSummary) document.getElementById?.(activeSummary)?.focus({preventScroll: true});
    const operations = ["camera", "activity"].includes(state.page) ? null : renderOperations(); if (operations) content.append(heading("Activity"), operations);
  }
  function navigate(page) {
    state.page = page;
    for (const button of document.querySelectorAll("[data-page]")) {
      const selected = button.dataset.page === page; button.classList.toggle("selected", selected);
      if (selected) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    }
    render(); $("#main").focus({preventScroll: true});
    // Explicit page navigation starts at the workspace, not the previous page's
    // scroll offset. Refresh/image renders do not move the operator's viewport.
    $("#main").scrollIntoView?.({block: "start"});
  }
  async function updateImage() {
    const provenance = state.view.camera?.provenance || state.view.camera?.image_provenance;
    const id = provenance === "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2" && !physicalImagePublished() ? null : state.view.camera?.image_id;
    if (!id) {
      if (state.imageURL) {
        URL.revokeObjectURL(state.imageURL); state.imageURL = null; state.imageId = null;
        if (state.page === "camera") render();
      }
      return;
    }
    if (id === state.imageId) return;
    const blob = await request(`/api/images/${encodeURIComponent(id)}`);
    const prior = state.imageURL; state.imageURL = URL.createObjectURL(blob); state.imageId = id;
    if (state.page === "camera") render(); if (prior) URL.revokeObjectURL(prior);
  }
  function physicalImagePublished() {
    const value = physicalCameraValidators().physical(state.view.physical_camera);
    return !!value && value.publication.status === "CURRENT" && value.last_frame?.image_id !== null
      && value.last_frame?.image_id === state.view.camera?.image_id;
  }
  async function refresh(force = false) {
    if (state.refreshing || (state.renderFailed && !force)) return;
    if (force) state.renderFailed = false;
    state.refreshing = true;
    let serviceReached = false;
    try {
      const view = await request("/api/view");
      serviceReached = true;
      const changed = !state.view || view.revision !== state.view.revision;
      const contextChanged = previewContext(view) !== previewContext(state.view);
      const reconnected = state.connectionLost;
      const activeBinding = [...state.formBindings.values()].find(binding => binding.controls.some(([, control]) => control === document.activeElement));
      state.view = view;
      state.connectionLost = false;
      pruneDrafts();
      if (contextChanged) { clearDrafts("Ordinary drafts cleared because the setup context changed. No prior selection or confirmation was restored."); invalidatePreview(); }
      if (state.previewBinding && state.previewBinding.contract !== formContract(currentFormAction(state.previewBinding.actionId))) invalidatePreview();
      const contractChanged = activeBinding && activeBinding.contract !== formContract(currentFormAction(activeBinding.id));
      $("#connection-status").textContent = "Local service connected";
      if (changed || force || contextChanged || reconnected || contractChanged) {
        // Preserve partially entered forms on read-only polling. Navigation or
        // an explicit refresh renders the latest state immediately.
        const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
        if (force || contextChanged || reconnected || contractChanged || !editing) render();
      }
      if (state.renderFailed) return;
      if (state.lastError) { $("#error-banner").hidden = true; state.lastError = null; }
      await updateImage();
    } catch (error) {
      if (serviceReached) reportRenderError(error);
      else {
        state.connectionLost = true; clearDrafts("Ordinary drafts cleared because the service became unavailable. Reconnect and review current requirements before entering values again."); invalidatePreview();
        if (state.view) render();
        $("#connection-status").textContent = "Service unavailable"; state.lastError = error.message; showError(error);
      }
    } finally { state.refreshing = false; }
  }
  async function prepare(actionId, input, revision) {
    if (!state.view || state.connectionLost || state.renderFailed) return;
    const generation = ++state.previewGeneration, context = previewContext(), contract = formContract(currentFormAction(actionId));
    state.ticket = null; $("#execute-action").disabled = true;
    state.previewBinding = {actionId, context, contract};
    $("#error-banner").hidden = true;
    const ticket = await request("/api/prepare", {action_id: actionId, input, expected_revision: revision});
    if (generation !== state.previewGeneration || context !== previewContext() || contract !== formContract(currentFormAction(actionId)) || state.connectionLost)
      throw new Error("Setup changed or the preview was cancelled while preparing. Inspect current status and prepare again explicitly; nothing was executed.");
    state.ticket = ticket;
    $("#action-title").textContent = state.ticket.label || human(actionId);
    $("#action-error").hidden = true;
    const preview = $("#action-preview"); preview.replaceChildren();
    preview.append(element("p", "", "Only the exact server-issued ticket below can be executed. Canceling this preview performs no device action."));
    if (state.ticket.effects?.length) {
      const list = element("ul", "guide"); for (const effect of state.ticket.effects) list.append(element("li", "", effect)); preview.append(list);
    }
    for (const warning of state.ticket.warnings || []) preview.append(element("div", "notice warning", warning));
    if (state.ticket.expires_in_s !== undefined) preview.append(element("p", "caption", `Ticket expires after ${state.ticket.expires_in_s} seconds. Any conflicting state change requires a new preview.`));
    preview.append(detail(state.ticket, "Exact action record"));
    $("#execute-action").disabled = false; $("#action-dialog").showModal();
  }
  async function execute() {
    if (!state.ticket || state.pending || state.connectionLost || state.renderFailed) return;
    const ticket = state.ticket; state.ticket = null; state.pending = true; state.previewGeneration++; state.previewBinding = null;
    clearDrafts("Ordinary drafts cleared when the reviewed action was submitted. Inspect its result before entering another action.");
    $("#execute-action").disabled = true; $("#action-error").hidden = true;
    try {
      const operation = await request("/api/execute", {ticket_id: ticket.ticket_id});
      state.operationId = operation.operation_id;
      $("#announcement").textContent = "Action submitted. Inspect operation progress below.";
      $("#action-dialog").close(); await refresh(true);
    } catch (error) {
      showError(error, $("#action-error"));
      $("#action-preview").append(element("p", "caption", "This ticket will not be resubmitted. Close this dialog and inspect current operations before considering another action."));
      await refresh(true);
    } finally { state.pending = false; render(); }
  }
  $("#navigation").addEventListener("click", (event) => { const button = event.target.closest("[data-page]"); if (button) navigate(button.dataset.page); });
  $("#refresh-button").onclick = () => refresh(true);
  $("#execute-action").onclick = execute;
  $("#cancel-action").onclick = $("#close-dialog").onclick = invalidatePreview;
  $("#action-dialog").addEventListener("cancel", invalidatePreview);
  $("#action-dialog-form").addEventListener("submit", (event) => event.preventDefault());
  if (!session || !csrf) showError(new Error("Open the private launch URL printed by the RoCell launcher. This page has no session credentials; hardware has not been accessed."));
  else { refresh(true); setInterval(() => { if (!document.hidden) refresh(); }, 1800); }
})();
