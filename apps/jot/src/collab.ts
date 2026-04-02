import crypto from "node:crypto";
import { IdList, type ElementId, type SavedIdList } from "articulated";

export type ClientInsertMutation = {
  name: "insert";
  args: {
    before: ElementId | null;
    id: ElementId;
    content: string;
    isInWord: boolean;
  };
  clientCounter: number;
};

export type ClientDeleteMutation = {
  name: "delete";
  args: {
    startId: ElementId;
    endId?: ElementId;
    contentLength?: number;
  };
  clientCounter: number;
};

export type ClientMutation = ClientInsertMutation | ClientDeleteMutation;

export type ClientMutationMessage = {
  type: "mutation";
  clientId: string;
  mutations: ClientMutation[];
};

export type IdListUpdate =
  | {
      type: "insertAfter";
      before: ElementId | null;
      id: ElementId;
      count: number;
    }
  | {
      type: "deleteRange";
      startIndex: number;
      endIndex: number;
    };

export type ServerHelloMessage = {
  type: "hello";
  clientId?: string;
  noteId: string;
  title: string;
  shareId: string;
  markdown: string;
  idListState: SavedIdList;
  serverCounter: number;
};

export type ServerMutationMessage = {
  type: "mutation";
  senderId: string;
  senderCounter: number;
  serverCounter: number;
  markdown: string;
  idListUpdates: IdListUpdate[];
};

export type PresenceSelection =
  | { type: "cursor"; cursor: { bunchId: string; counter: number } | null }
  | { type: "range"; start: { bunchId: string; counter: number } | null; end: { bunchId: string; counter: number } | null; direction: "forward" | "backward" };

export type ClientPresenceMessage = {
  type: "presence";
  clientId: string;
  selection: PresenceSelection;
};

export type ServerPresenceMessage = {
  type: "presence";
  clientId: string;
  name: string;
  color: string;
  selection: PresenceSelection;
};

export type ServerPresenceLeaveMessage = {
  type: "presence-leave";
  clientId: string;
};

export type SavedCharBunch = {
  bunchId: string;
  startCounter: number;
  chars: string;
};

export type SavedCollabState = {
  idListState: SavedIdList;
  chars: SavedCharBunch[];
  serverCounter: number;
};

export type CollabState = {
  idList: IdList;
  chars: Map<string, string>;
  serverCounter: number;
};

export class TrackedIdList {
  private _idList: IdList;
  private updates: IdListUpdate[] = [];

  constructor(idList: IdList, readonly trackChanges: boolean) {
    this._idList = idList;
  }

  get idList(): IdList {
    return this._idList;
  }

  getAndResetUpdates(): IdListUpdate[] {
    if (!this.trackChanges) {
      throw new Error("trackChanges not enabled");
    }
    const updates = this.updates;
    this.updates = [];
    return updates;
  }

  insertAfter(before: ElementId | null, newId: ElementId, count = 1) {
    this._idList = this._idList.insertAfter(before, newId, count);
    if (this.trackChanges) {
      this.updates.push({ type: "insertAfter", before, id: newId, count });
    }
  }

  deleteRange(startIndex: number, endIndex: number) {
    const ids: ElementId[] = [];
    for (let index = startIndex; index <= endIndex; index++) {
      ids.push(this._idList.at(index));
    }
    for (const id of ids) {
      this._idList = this._idList.delete(id);
    }
    if (this.trackChanges) {
      this.updates.push({ type: "deleteRange", startIndex, endIndex });
    }
  }

  apply(update: IdListUpdate) {
    switch (update.type) {
      case "insertAfter":
        this._idList = this._idList.insertAfter(update.before, update.id, update.count);
        return;
      case "deleteRange":
        this.deleteRange(update.startIndex, update.endIndex);
        if (!this.trackChanges) {
          return;
        }
        this.updates.pop();
        return;
    }
  }
}

function charKey(id: ElementId) {
  return `${id.bunchId}:${id.counter}`;
}

export function newCollabState(): CollabState {
  return {
    idList: IdList.new(),
    chars: new Map(),
    serverCounter: 0,
  };
}

export function collabFromMarkdown(markdown: string, serverCounter = 0): CollabState {
  if (!markdown) {
    return {
      idList: IdList.new(),
      chars: new Map(),
      serverCounter,
    };
  }

  const bunchId = crypto.randomUUID();
  const startId: ElementId = { bunchId, counter: 0 };
  const idList = IdList.new().insertAfter(null, startId, markdown.length);
  const chars = new Map<string, string>();
  for (let index = 0; index < markdown.length; index++) {
    chars.set(charKey({ bunchId, counter: index }), markdown[index]);
  }

  return { idList, chars, serverCounter };
}

export function collabToMarkdown(state: CollabState): string {
  const parts: string[] = [];
  for (const id of state.idList.values()) {
    const char = state.chars.get(charKey(id));
    if (char !== undefined) {
      parts.push(char);
    }
  }
  return parts.join("");
}

export function saveCollabState(state: CollabState): SavedCollabState {
  const idListState = state.idList.save();
  const chars: SavedCharBunch[] = [];

  for (const item of idListState) {
    let text = "";
    for (let offset = 0; offset < item.count; offset++) {
      const id: ElementId = {
        bunchId: item.bunchId,
        counter: item.startCounter + offset,
      };
      text += state.chars.get(charKey(id)) || "\0";
    }
    chars.push({
      bunchId: item.bunchId,
      startCounter: item.startCounter,
      chars: text,
    });
  }

  return {
    idListState,
    chars,
    serverCounter: state.serverCounter,
  };
}

export function loadCollabState(saved: SavedCollabState): CollabState {
  const idList = IdList.load(saved.idListState || []);
  const chars = new Map<string, string>();

  for (const bunch of saved.chars || []) {
    for (let offset = 0; offset < bunch.chars.length; offset++) {
      const id: ElementId = {
        bunchId: bunch.bunchId,
        counter: bunch.startCounter + offset,
      };
      chars.set(charKey(id), bunch.chars[offset]);
    }
  }

  return {
    idList,
    chars,
    serverCounter: saved.serverCounter || 0,
  };
}

export function idAtIndex(state: CollabState, index: number): ElementId {
  return state.idList.at(index);
}

export function idBeforeIndex(state: CollabState, index: number): ElementId | null {
  if (index <= 0) {
    return null;
  }
  return state.idList.at(index - 1);
}

function applyInsertMutation(
  trackedIds: TrackedIdList,
  chars: Map<string, string>,
  mutation: ClientInsertMutation,
) {
  const { before, id, content, isInWord } = mutation.args;
  if (!content) {
    return;
  }
  if (before !== null && !trackedIds.idList.isKnown(before)) {
    return;
  }
  if (trackedIds.idList.isKnown(id)) {
    return;
  }
  if (isInWord && before !== null && !trackedIds.idList.has(before)) {
    return;
  }

  trackedIds.insertAfter(before, id, content.length);
  for (let offset = 0; offset < content.length; offset++) {
    chars.set(
      charKey({ bunchId: id.bunchId, counter: id.counter + offset }),
      content[offset],
    );
  }
}

function applyDeleteMutation(
  trackedIds: TrackedIdList,
  mutation: ClientDeleteMutation,
) {
  const { startId, endId, contentLength } = mutation.args;
  if (!trackedIds.idList.isKnown(startId)) {
    return;
  }

  const startIndex = trackedIds.idList.indexOf(startId, "right");
  const endIndex = endId === undefined
    ? startIndex
    : trackedIds.idList.isKnown(endId)
      ? trackedIds.idList.indexOf(endId, "left")
      : startIndex - 1;

  if (endIndex < startIndex) {
    return;
  }

  const currentLength = endIndex - startIndex + 1;
  if (contentLength !== undefined && currentLength > contentLength + 10) {
    return;
  }

  trackedIds.deleteRange(startIndex, endIndex);
}

export function applyClientMutations(state: CollabState, mutations: ClientMutation[]) {
  const trackedIds = new TrackedIdList(state.idList, true);
  const chars = new Map(state.chars);

  for (const mutation of mutations) {
    switch (mutation.name) {
      case "insert":
        applyInsertMutation(trackedIds, chars, mutation);
        break;
      case "delete":
        applyDeleteMutation(trackedIds, mutation);
        break;
    }
  }

  const idListUpdates = trackedIds.getAndResetUpdates();
  const nextState: CollabState = {
    idList: trackedIds.idList,
    chars,
    serverCounter: idListUpdates.length > 0 ? state.serverCounter + 1 : state.serverCounter,
  };

  return {
    state: nextState,
    markdown: collabToMarkdown(nextState),
    idListUpdates,
    changed: idListUpdates.length > 0,
  };
}
