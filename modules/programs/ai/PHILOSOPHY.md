## Modularity and future instruments

Modularity is a core part of the philosophy.

The user will keep inventing new ways the companion could help: new goal workflows, new context sources, new phone controls, new Obsidian surfaces, new local models, new memory views, new evaluators, and new recovery instruments.

The system should welcome that.

New functionality should be added as explicit instruments around a small deterministic kernel, not by giving one giant agent more authority. Each instrument should declare:

- what goal it serves;
- what it reads;
- what it writes;
- what schema it uses;
- what authority it needs;
- whether an LLM can influence it;
- whether it can mutate TaskNotes;
- how the user reviews or corrects it;
- how it is tested;
- how it can be disabled.

This makes the project expandable without becoming chaotic.

A future instrument might be a goal reviewer, a blocker detector, a language-learning coach, a focus-session planner, a stale-task cleaner, a screenshot summarizer, a voice capture parser, a semantic memory retriever, or a weekly strategy reviewer. All of these should plug into the same basic architecture:

```text
context -> memory -> proposal -> review -> bounded action -> outcome -> learning
```

Modern LLMs and neural networks make many new instruments possible. The project should use them for better goal understanding, semantic memory, planning, multimodal capture, evaluation, and explanation. But stronger models should improve proposals and insight, not erase review boundaries.

The more capable the model becomes, the more important the extension model becomes.
