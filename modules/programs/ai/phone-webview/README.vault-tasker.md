# Perseverance AI Tasker Project

Import:

`AI/tasker/import/PerseveranceAI-v3.prj.xml`

## Contract

Actions/check-ins:

`Tasker -> AI/inbox/actions/*.json -> ai-action-bridge`

Passive telemetry:

`Tasker -> AI/inbox/from-phone/events/*.json -> phone-bridge`

## Bind first

Widgets / quick settings:

- AI Action Start Anki Recovery
- AI Action Check In Overwhelmed
- AI Action Check In Tired
- AI Action Check In Doing OK
- AI Action End Completed
- AI Action End Paused

Profiles:

- Display/User Present -> AI Event Phone Unlock
- AnkiDroid enter -> AI Event Open AnkiDroid
- AnkiDroid exit -> AI Event Close AnkiDroid

Vault path used by writer tasks:

`/storage/emulated/11/Documents/Obsidian`
