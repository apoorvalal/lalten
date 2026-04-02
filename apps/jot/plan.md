# jot collaborative rewrite plan

This file is for the next session. Read it first, then execute it. Do not keep patching the current collaborative editor. Replace it cleanly.

## Immediate instruction to future self

The current collab path is half-old, half-new, and broken. Stop trying to salvage it piecemeal.

Immediately do a full semantic rewrite of collaborative editing based on the `articulated` semantic-rebasing demo architecture.

No backward compatibility is required.

It is acceptable to break old local test data and require fresh notes.

Keep comments, auth, API keys, CLI, themes, mobile preview, and share flows working, but rebuild the document editing core from first principles.

## Current repo

Repo root:
- `/Users/badlogic/workspaces/jot`

Important current files in this repo:
- `src/server.ts`
- `src/collab.ts`
- `public/app.js`
- `public/collab-editor.js`
- `public/styles.css`
- `public/theme.js`
- `public/login.js`
- `cli/jot.mjs`
- `README.md`
- `Dockerfile`
- `docker/docker-compose.base.yml`
- `docker/docker-compose.prod.yml`
- `docker/docker-compose.dev.yml`
- `docker/control.sh`

## External references to read fully before coding

### 1. Matt Weidner article
Read fully:
- `https://mattweidner.com/2025/05/21/text-without-crdts.html`

Core concepts to use:
- stable character ids
- semantic client mutations
- server applies mutations literally
- server reconciliation on clients
- no CRDT ordering logic needed for centralized server

### 2. articulated library docs
Read:
- `node_modules/articulated/README.md`
- `node_modules/articulated/build/commonjs/index.d.ts`
- `node_modules/articulated/build/commonjs/id_list.d.ts`
- `node_modules/articulated/build/commonjs/element_id.d.ts`
- `node_modules/articulated/build/commonjs/element_id_generator.d.ts`
- `node_modules/articulated/build/commonjs/saved_id_list.d.ts`

### 3. semantic-rebasing demo
Local clone already exists at:
- `/tmp/articulated-demos/semantic-rebasing`

Read these files fully:
- `/tmp/articulated-demos/semantic-rebasing/README.md`
- `/tmp/articulated-demos/semantic-rebasing/src/common/tracked_id_list.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/common/client_mutations.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/common/client_messages.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/common/server_messages.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/site/web_socket_client.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/site/prosemirror_wrapper.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/server/rich_text_server.ts`
- `/tmp/articulated-demos/semantic-rebasing/src/server/server.ts`

Do not cargo-cult ProseMirror. We use a textarea. But copy the architecture exactly:
- client sends mutations
- server applies mutations
- server broadcasts canonical updates
- client maintains confirmed state + pending mutations
- client restores selection by ids

## What is currently broken

Current state is not a real rewrite.

Problems:
- editor path mixes REST refresh logic and WebSocket op logic
- generic `updated` broadcasts stomp local state
- ack / pending mutation handling is incomplete
- cursor and selection drift under normal typing speed
- current `public/collab-editor.js` is experimental and should be discarded
- some server routes still derive from markdown in ways that conflict with collab state ownership

## Non-goals for the rewrite

- no attempt to preserve old note metadata format exactly
- no migration tooling beyond best-effort fresh conversion from existing `.md` files
- no operation-level history slider in this rewrite
- no remote cursors yet
- no collaborative public edit mode yet

Those can come after stable collaborative editing.

## Goals for the rewrite

### Primary goal
Two or more browser tabs can edit the same markdown document at the same time at normal typing speed without corruption.

### Secondary goals
- owner editor uses collaborative core
- public shared preview remains read-only comment mode for now
- CLI still works for list/search/read/edit/update/delete
- API key flow still works
- comments still work on top of current markdown rendering model
- server still writes `.md` file as a derived artifact for convenience

## Final architecture to implement

## 1. Source of truth

The source of truth for a note must be:
- `IdList` from articulated
- char storage keyed by element id
- append-only mutation log or update log if useful

The plain markdown string is derived.

The `.md` file is a derived artifact written during persistence. It is not authoritative.

## 2. Note storage format

Keep one note per id:
- `data/notes/<id>.md`
- `data/notes/<id>.json`

The JSON should contain:
- title
- shareId
- timestamps
- comment threads
- saved collaborative state

Suggested JSON shape:

```json
{
  "id": "abc123",
  "title": "untitled",
  "shareId": "...",
  "createdAt": "...",
  "updatedAt": "...",
  "threads": [],
  "collab": {
    "idListState": [...],
    "chars": [
      { "bunchId": "...", "startCounter": 0, "chars": "hello" }
    ],
    "serverCounter": 42
  }
}
```

No backward compat needed. If old notes exist without collab state, convert markdown to collab state on load.

## 3. Client mutations

The browser must send semantic mutations, not raw low-level patches.

Start with only two mutation kinds:

```ts
type ClientMutation =
  | {
      name: "insert";
      args: {
        before: ElementId | null;
        id: ElementId;
        content: string;
        isInWord: boolean;
      };
      clientCounter: number;
    }
  | {
      name: "delete";
      args: {
        startId: ElementId;
        endId?: ElementId;
        contentLength?: number;
      };
      clientCounter: number;
    };
```

Notes:
- use `beforeinput`
- do not diff full strings as primary mechanism
- derive mutation directly from selection and input intent where possible
- fallback diffing is acceptable only for weird composition edge cases if needed

## 4. Server application model

The server must:
- receive mutations over WebSocket
- apply them to authoritative note state
- use a tracked IdList wrapper that records actual structural updates
- derive new markdown string
- persist note
- broadcast canonical server updates to all clients

Do not broadcast client intent as truth.

Server update payload should look something like:

```ts
type ServerMessage =
  | {
      type: "hello";
      noteId: string;
      title: string;
      shareId: string;
      markdown: string;
      idListState: SavedIdList;
      serverCounter: number;
    }
  | {
      type: "mutation";
      senderId: string;
      senderCounter: number;
      serverCounter: number;
      markdown: string;
      idListUpdates: IdListUpdate[];
    };
```

For the first working version, sending the full markdown with every server mutation is acceptable.

That makes reconciliation much easier. Optimize later.

## 5. Client reconciliation model

The client must maintain:
- `serverText`
- `serverIdList`
- `pendingMutations`
- current textarea state derived from `serverText + pendingMutations`

When a server mutation arrives:
1. apply server update to confirmed server state
2. drop confirmed local mutations if `senderId === clientId` and `senderCounter` reached
3. rebuild local state by replaying remaining pending mutations on top of confirmed state
4. restore selection using id-based selection mapping

This is the core thing to get right.

## 6. Selection preservation

Implement selection tracking in ID-space, like the demo.

At minimum support:
- cursor selection
- text range selection

Need helper conversions:
- `selectionToIds(state)`
- `selectionFromIds(selectionIds, state)`

Since we use textarea, the selection mapping is simpler than ProseMirror:
- map visible character indices to ids via `IdList.at`
- restore cursor/range using `IdList.indexOf`

## 7. Tracked IdList wrapper

Implement a small mutable wrapper around `IdList` similar to:
- `/tmp/articulated-demos/semantic-rebasing/src/common/tracked_id_list.ts`

For our use case it should record updates like:

```ts
type IdListUpdate =
  | { type: "insertAfter"; before: ElementId | null; id: ElementId; count: number }
  | { type: "deleteRange"; startIndex: number; endIndex: number };
```

The server uses this to produce canonical updates for clients.

## 8. Character storage

Use compressed bunch storage server-side for persistence, but in-memory you can use:
- `Map<string, string>` keyed by `bunchId:counter`

This is fine.

If easier for first pass, also keep an in-memory visible string cache.

## 9. REST API after rewrite

Keep these routes usable:
- `GET /api/notes`
- `GET /api/notes/:id`
- `GET /api/notes/:id?offset=...&limit=...`
- `POST /api/notes`
- `POST /api/notes/:id/edit`
- `PUT /api/notes/:id` for title updates and full markdown replacement
- `DELETE /api/notes/:id`
- `GET/POST/DELETE /api/keys`

But note:
- REST edit/update must internally convert requested text changes into mutations or rebuild authoritative collab state cleanly
- no direct markdown mutation bypassing collab source of truth

Acceptable shortcut for `PUT markdown`:
- rebuild note collab state from full markdown replacement

Acceptable shortcut for `POST /edit`:
- find text range in current markdown
- convert to delete mutation + insert mutation

## 10. Comments

Do not touch comments much in the rewrite.

Keep current comment system:
- text-quote anchors
- reply tree UI
- modal behavior
- shared/public comment flows

Only ensure comments continue to work against derived markdown text.

## 11. UI behavior after rewrite

### Editor mode
- collaborative textarea on left
- rendered preview on right
- same mobile preview overlay behavior
- comments unchanged for now

### Public mode
- read-only preview
- comments only
- no collaborative editing yet

## 12. WebSocket auth

For now, owner editor connections can stay cookie-authenticated.

Do not add public collaborative editing in this rewrite.

So WS server can remain simple for owner note editing.

## 13. Step-by-step execution order

### Step 1
Create a proper shared module for collaborative state and updates:
- `src/collab.ts`
- maybe `public/collab-shared.js` or inline equivalents for browser

### Step 2
Implement `TrackedIdList` wrapper in server and browser.

### Step 3
Refactor server note model to make collab state authoritative.

### Step 4
Replace current WS protocol:
- remove generic `updated`-for-text logic
- add mutation hello/ack/broadcast model

### Step 5
Replace `public/collab-editor.js` completely.
Do not patch the current file. Rewrite it cleanly.

### Step 6
Wire editor mode in `public/app.js` to use the new collab editor.

### Step 7
Keep preview rendering server-side through `/api/render` initially.
That is fine.

### Step 8
Test in two tabs:
- normal typing speed
- backspace
- paste
- newline
- word delete
- editing in the middle of a line
- both users typing in different places
- both users typing in same word

### Step 9
Then make CLI edits still work.

## 14. Acceptance criteria

The rewrite is only done when all of this holds:

1. Typing at normal speed does not drop/reorder characters.
2. Two tabs editing same note converge correctly.
3. No REST reload loop interferes with typing.
4. Cursor is stable during remote updates.
5. Backspace/delete/paste/newline work.
6. `.md` stays up to date on disk.
7. Existing comments still render and can be added.
8. Local CLI can still list/search/read/edit/update/delete.

## 15. Current commands / environment

Local dev server:
```bash
cd /Users/badlogic/workspaces/jot
npm run build
node dist/server.js
```

CLI:
```bash
node cli/jot.mjs instances
node cli/jot.mjs local list
node cli/jot.mjs local read <id>
```

Remote deploy target:
- host: `slayer.marioslab.io`
- app path: `~/jot`
- domain: `https://jot.mariozechner.at`

Deploy command on server:
```bash
ssh slayer "cd ~/jot && git pull && cd docker && bash control.sh start"
```

## 16. Important instruction

Do not waste time on polishing UI until the collaborative core is stable.

Do not do more cosmetic patches to the current broken editor.

Rewrite the collaborative editor and WS flow properly first.

Then test aggressively.

Then continue.
