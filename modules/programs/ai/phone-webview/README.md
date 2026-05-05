# phone-webview

Versioned source snapshot for the phone-side AI interaction UI and Tasker import.

Runtime vault paths:

- `AI/state/phone/ai-pi-gruvbox-card-v1.html`
- `AI/tasker/import/PerseveranceAI-v3.prj.xml`
- `AI/tasker/README.md`

The WebView card is responsible for writing phone actions into:

- `AI/inbox/actions/*.json`

Important action payload fields:

- `action`
- `nudge_id`
- `interaction_id`
- `intervention_id`
- `intervention_kind`
- `target_id`
- `target_name`
- `goal_text`
- `stop_condition`
- `android_package`
- `launch_task`

Authority boundary:

- WebView may write action request files.
- WebView may ask Tasker to launch the target app.
- WebView must not mutate desktop recovery state directly.
- `action-bridge` owns action validation and recovery state mutation.
- `recovery-manager` owns lifecycle classification.
- `intervention-outcomes` owns derived outcome summaries.

Operational note:

`DEBUG_WRITES` may be temporarily enabled in the runtime vault HTML while testing,
but should normally be disabled after the WebView/action path is stable.
