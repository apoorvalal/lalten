function cloneId(id) {
  return id ? { bunchId: id.bunchId, counter: id.counter } : null;
}

function idsEqual(a, b) {
  return !!a && !!b && a.bunchId === b.bunchId && a.counter === b.counter;
}

export class SimpleIdList {
  constructor(entries = []) {
    this.entries = entries;
    this.length = 0;
    for (const entry of entries) {
      if (!entry.isDeleted) {
        this.length++;
      }
    }
  }

  static load(savedState) {
    const entries = [];
    for (const item of savedState || []) {
      for (let offset = 0; offset < item.count; offset++) {
        entries.push({
          id: { bunchId: item.bunchId, counter: item.startCounter + offset },
          isDeleted: Boolean(item.isDeleted),
        });
      }
    }
    return new SimpleIdList(entries);
  }

  clone() {
    return new SimpleIdList(this.entries.map((entry) => ({ id: cloneId(entry.id), isDeleted: entry.isDeleted })));
  }

  findKnownIndex(id) {
    for (let index = 0; index < this.entries.length; index++) {
      const entry = this.entries[index];
      if (idsEqual(entry.id, id)) {
        return index;
      }
    }
    return -1;
  }

  has(id) {
    const knownIndex = this.findKnownIndex(id);
    return knownIndex !== -1 && !this.entries[knownIndex].isDeleted;
  }

  isKnown(id) {
    return this.findKnownIndex(id) !== -1;
  }

  at(index) {
    if (!Number.isInteger(index) || index < 0 || index >= this.length) {
      throw new Error(`Index out of bounds: ${index}`);
    }
    let visibleIndex = 0;
    for (const entry of this.entries) {
      if (entry.isDeleted) {
        continue;
      }
      if (visibleIndex === index) {
        return cloneId(entry.id);
      }
      visibleIndex++;
    }
    throw new Error(`Index out of bounds: ${index}`);
  }

  indexOf(id, bias = "none") {
    const knownIndex = this.findKnownIndex(id);
    if (knownIndex === -1) {
      throw new Error("id is not known");
    }

    let visibleBefore = 0;
    for (let index = 0; index < knownIndex; index++) {
      if (!this.entries[index].isDeleted) {
        visibleBefore++;
      }
    }

    if (!this.entries[knownIndex].isDeleted) {
      return visibleBefore;
    }

    if (bias === "left") {
      return visibleBefore - 1;
    }
    if (bias === "right") {
      return visibleBefore;
    }
    return -1;
  }

  cursorAt(index, bind = "left") {
    if (!Number.isInteger(index) || index < 0 || index > this.length) {
      throw new Error(`Cursor index out of bounds: ${index}`);
    }
    if (bind === "left") {
      return index === 0 ? null : this.at(index - 1);
    }
    return index === this.length ? null : this.at(index);
  }

  cursorIndex(cursor, bind = "left") {
    if (bind === "left") {
      return cursor === null ? 0 : this.indexOf(cursor, "left") + 1;
    }
    return cursor === null ? this.length : this.indexOf(cursor, "right");
  }

  maxCounter(bunchId) {
    let max;
    for (const entry of this.entries) {
      if (entry.id.bunchId === bunchId) {
        if (max === undefined || entry.id.counter > max) {
          max = entry.id.counter;
        }
      }
    }
    return max;
  }

  insertAfter(before, startId, count = 1) {
    if (!Number.isInteger(count) || count < 0) {
      throw new Error(`Invalid count: ${count}`);
    }
    if (count === 0) {
      return;
    }

    let insertAt = 0;
    if (before !== null) {
      const knownIndex = this.findKnownIndex(before);
      if (knownIndex === -1) {
        throw new Error("before is not known");
      }
      insertAt = knownIndex + 1;
    }

    const inserted = [];
    for (let offset = 0; offset < count; offset++) {
      inserted.push({
        id: { bunchId: startId.bunchId, counter: startId.counter + offset },
        isDeleted: false,
      });
    }
    this.entries.splice(insertAt, 0, ...inserted);
    this.length += count;
  }

  deleteRange(startIndex, endIndex) {
    if (endIndex < startIndex) {
      return;
    }
    const knownIndexes = [];
    let visibleIndex = 0;
    for (let index = 0; index < this.entries.length; index++) {
      const entry = this.entries[index];
      if (entry.isDeleted) {
        continue;
      }
      if (visibleIndex >= startIndex && visibleIndex <= endIndex) {
        knownIndexes.push(index);
      }
      visibleIndex++;
      if (visibleIndex > endIndex) {
        break;
      }
    }

    for (const knownIndex of knownIndexes) {
      if (!this.entries[knownIndex].isDeleted) {
        this.entries[knownIndex] = { ...this.entries[knownIndex], isDeleted: true };
        this.length--;
      }
    }
  }
}

export class TrackedIdList {
  constructor(idList, trackChanges) {
    this._idList = idList;
    this.trackChanges = trackChanges;
    this.updates = [];
  }

  get idList() {
    return this._idList;
  }

  getAndResetUpdates() {
    if (!this.trackChanges) {
      throw new Error("trackChanges not enabled");
    }
    const updates = this.updates;
    this.updates = [];
    return updates;
  }

  insertAfter(before, id, count = 1) {
    this._idList.insertAfter(before, id, count);
    if (this.trackChanges) {
      this.updates.push({ type: "insertAfter", before: cloneId(before), id: cloneId(id), count });
    }
  }

  deleteRange(startIndex, endIndex) {
    this._idList.deleteRange(startIndex, endIndex);
    if (this.trackChanges) {
      this.updates.push({ type: "deleteRange", startIndex, endIndex });
    }
  }

  apply(update) {
    switch (update.type) {
      case "insertAfter":
        this._idList.insertAfter(update.before, update.id, update.count);
        return;
      case "deleteRange":
        this._idList.deleteRange(update.startIndex, update.endIndex);
        return;
    }
  }
}

export class ElementIdGenerator {
  constructor(newBunchId) {
    this.newBunchId = newBunchId;
    this.nextCounterMap = new Map();
  }

  generateAfter(beforeId, count = 1) {
    if (!Number.isInteger(count) || count < 1) {
      throw new Error(`Invalid count: ${count}`);
    }

    if (beforeId) {
      const nextCounter = this.nextCounterMap.get(beforeId.bunchId) || 0;
      if (beforeId.counter + 1 >= nextCounter) {
        const counter = beforeId.counter + 1;
        this.nextCounterMap.set(beforeId.bunchId, counter + count);
        return { bunchId: beforeId.bunchId, counter };
      }
    }

    const bunchId = this.newBunchId();
    this.nextCounterMap.set(bunchId, count);
    return { bunchId, counter: 0 };
  }
}

export function applyClientMutation(state, mutation) {
  const trackedIds = new TrackedIdList(state.idList.clone(), false);

  if (mutation.name === "insert") {
    const { before, id, content, isInWord } = mutation.args;
    if (!content) {
      return state;
    }
    if (before !== null && !trackedIds.idList.isKnown(before)) {
      return state;
    }
    if (trackedIds.idList.isKnown(id)) {
      return state;
    }
    if (isInWord && before !== null && !trackedIds.idList.has(before)) {
      return state;
    }

    trackedIds.insertAfter(before, id, content.length);
    const insertIndex = before === null ? 0 : trackedIds.idList.indexOf(id);
    return {
      text: state.text.slice(0, insertIndex) + content + state.text.slice(insertIndex),
      idList: trackedIds.idList,
    };
  }

  const { startId, endId, contentLength } = mutation.args;
  if (!trackedIds.idList.isKnown(startId)) {
    return state;
  }

  const startIndex = trackedIds.idList.indexOf(startId, "right");
  const endIndex = endId === undefined
    ? startIndex
    : trackedIds.idList.isKnown(endId)
      ? trackedIds.idList.indexOf(endId, "left")
      : startIndex - 1;

  if (endIndex < startIndex) {
    return state;
  }

  const currentLength = endIndex - startIndex + 1;
  if (contentLength !== undefined && currentLength > contentLength + 10) {
    return state;
  }

  trackedIds.deleteRange(startIndex, endIndex);
  return {
    text: state.text.slice(0, startIndex) + state.text.slice(endIndex + 1),
    idList: trackedIds.idList,
  };
}

export function applyIdListUpdates(idList, updates) {
  const trackedIds = new TrackedIdList(idList.clone(), false);
  for (const update of updates) {
    trackedIds.apply(update);
  }
  return trackedIds.idList;
}

export function selectionToIds(idList, start, end, direction = "forward") {
  if (start === end) {
    return {
      type: "cursor",
      cursor: idList.cursorAt(start, "left"),
    };
  }

  return {
    type: "range",
    start: idList.cursorAt(start, "right"),
    end: idList.cursorAt(end, "left"),
    direction: direction === "backward" ? "backward" : "forward",
  };
}

export function selectionFromIds(selection, idList) {
  try {
    if (selection.type === "cursor") {
      const index = idList.cursorIndex(selection.cursor, "left");
      return { start: index, end: index, direction: "none" };
    }

    const start = idList.cursorIndex(selection.start, "right");
    const end = idList.cursorIndex(selection.end, "left");
    if (selection.direction === "backward") {
      return { start, end, direction: "backward" };
    }
    return { start, end, direction: "forward" };
  } catch {
    return { start: 0, end: 0, direction: "none" };
  }
}
