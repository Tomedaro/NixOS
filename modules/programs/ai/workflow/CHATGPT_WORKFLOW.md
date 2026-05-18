# ChatGPT Workflow

## Purpose

This file explains how to use ChatGPT web for the AI companion project with minimal friction.

The assistant should not only answer the current question. It should also tell the user what to do next.

## Core rule

Every substantial answer should end with a `Next action` section.

That section must say:

- whether to stay in the current chat or move to another chat;
- the exact target chat name if moving;
- what files or bundle to attach;
- what exact prompt or text to paste;
- what terminal commands to run locally;
- what not to do yet;
- stop conditions.

## Chat names

Use these chat names exactly:

- `00 Research and Design`
- `01 Implementation`
- `02 Verification and Debugging`
- `03 Release and Retrospective`

## When to use each chat

### 00 Research and Design

Use for:

- choosing the next task;
- architecture or design questions;
- external research;
- comparing options;
- checking project fit;
- deciding what is safest.

Move away when:

- a specific task has been selected;
- likely files are identified;
- risks are known;
- verification commands are known.

Usually move next to:

- `01 Implementation`

Do not ask this chat for implementation patches.

### 01 Implementation

Use for:

- patch planning;
- small code patches;
- small docs patches;
- exact file edits.

First ask for a patch plan.

Only ask for a patch after the plan is acceptable.

Move away when:

- a patch has been applied locally;
- checks fail;
- the task grows beyond its original scope.

Usually move next to:

- local terminal, if the patch is ready to test;
- `02 Verification and Debugging`, if checks fail;
- `03 Release and Retrospective`, if checks pass and the diff is staged.

Do not ask this chat for broad refactors or new architecture decisions.

### 02 Verification and Debugging

Use for:

- failed commands;
- failing tests;
- broken scripts;
- unexpected output;
- root-cause analysis.

Provide:

- exact command run;
- full output;
- current diff;
- relevant file excerpts.

Move away when:

- root cause is understood;
- a minimal fix is known;
- the issue is unrelated to the current task.

Usually move next to:

- `01 Implementation`

Do not ask this chat for new feature design.

### 03 Release and Retrospective

Use for:

- staged diff review;
- final risk review;
- commit readiness;
- workflow log updates;
- handoff updates;
- lessons learned.

Provide:

- latest bundle;
- staged diff;
- verification output;
- changed file list.

Move away when:

- commit is complete;
- handoff is updated;
- next task is identified.

Usually move next to:

- `00 Research and Design`

Do not ask this chat for new implementation patches.

## Bundle rule

Before a new serious chat, generate the latest bundle:

    cd ~/NixOS
    modules/programs/ai/dev/llm/make-docs-tar.sh

Attach the newest file from:

    modules/programs/ai/chatgpt-bundles/

## Standard local commands

Check docs:

    cd ~/NixOS
    modules/programs/ai/dev/llm/check-ai-docs.sh

Check current AI patch:

    cd ~/NixOS
    modules/programs/ai/dev/llm/check-llm-patch.sh

Run smoke tests:

    cd ~/NixOS
    modules/programs/ai/dev/run-smoke.sh

Run staged verification:

    cd ~/NixOS
    modules/programs/ai/dev/llm/verify-staged-ai.sh

## Required response ending

At the end of every substantial answer, the assistant should use this format:

Next action

Go to:
[chat name or "stay here"]

Attach:
[file paths or "nothing"]

Paste:
[copy-paste-ready prompt or "nothing"]

Run locally:
[commands or "nothing"]

Do not do yet:
[things to avoid]

Stop if:
[stop conditions]

## Default behavior

When uncertain, choose the smallest safe next step.

Do not propose:

- broad refactors;
- write-capable automation;
- MCP tools;
- ChatGPT Skills;
- new workflow files;

unless the current task clearly justifies them.

## Done definition

A task is done only when:

- the original objective is still the objective;
- the diff is small;
- local checks pass;
- smoke tests pass when relevant;
- staged verification passes before commit;
- workflow logs are updated if needed;
- the commit is made.
