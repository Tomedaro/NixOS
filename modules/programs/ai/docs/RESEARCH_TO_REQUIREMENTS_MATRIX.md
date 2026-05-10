# Research to requirements matrix
This matrix turns research anchors into concrete project requirements. It prevents research names from becoming decorative citations and keeps future work tied to testable behavior.

| Anchor | Relevant idea | Project requirement | Current status | Proposed artifact/eval |
|---|---|---|---|---|
| Personal informatics | Prepare, collect, integrate, reflect, act | The AI vault must support not just collection but reflection and action review | Partial | learning loop doc; daily review eval |
| Personal informatics | Barriers cascade across stages | Stale/unclear data should block confident action | Partial | stale context eval |
| Microsoft HAI | Set expectations and adapt over time | Interactions should expose capability, uncertainty, and correction paths | Partial | interaction controls doc |
| Google PAIR | Feedback and controls steer AI | Controls must include wrong inference, less/more like this, helped, felt pressuring | Missing | feedback event schema |
| Self-Determination Theory | Autonomy, competence, relatedness | Tone must preserve agency, avoid shame, offer choices, and support competence | Partial in prompts/docs | voice model; tone eval |
| COM-B | Capability, opportunity, motivation | Friction hypotheses should classify obstacles without moralizing | Partial | planner vNext metadata |
| Implementation intentions | If-then plans with when/where/how | Proposed next actions should include trigger, action, fallback, stop condition | Partial | planner eval |
| JITAI | Decision point, tailoring variables, options, rule, outcomes | Each adaptive nudge should record why now, tailoring variables, alternative, expected outcome | Missing/partial | attention policy; evals |
| Micro-randomized trials | Compare intervention options at decision points | Future adaptation should start as bounded experiments, not permanent hidden policy | Missing | experiment schema |
| Calm technology | Inform without overwhelming | Silence/defer and burden budget are first-class intervention choices | Missing/partial | attention policy; silence eval |
| OpenAI eval guidance | Evals test style/content criteria despite LLM variability | Planner and proposal changes need product scenario evals | Missing | product eval runner |

## Key gap

The README already names many of these anchors, but the current audit did not yet require every anchor to map to a schema, control, invariant, or eval. That should be added before implementation.
