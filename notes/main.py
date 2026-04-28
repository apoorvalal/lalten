from datetime import datetime
import re

from fasthtml.common import *


DB_PATH = 'notes.db'
db = database(DB_PATH)
notes = db.t.notes
if notes not in db.t:
    notes.create(id=int, content=str, created_at=str, status=str, pk='id')
Note = notes.dataclass()

try:
    db.execute("ALTER TABLE notes ADD COLUMN status TEXT DEFAULT 'active'")
except Exception:
    pass

app, rt = fast_app()


def normalize_item(content: str) -> str:
    return re.sub(r'\s+', ' ', content.strip().lower())


def dedupe_archived(note_list):
    seen = set()
    deduped = []
    for note in note_list:
        key = normalize_item(note.content)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(note)
    return deduped


def note_card(note, *, archived: bool, search: str = ''):
    button_specs = [
        (
            'Reactivate' if archived else 'Archive',
            f'/notes/activate/{note.id}' if archived else f'/notes/archive/{note.id}',
            '#198754' if archived else '#6c757d',
        ),
        ('Delete', f'/notes/delete/{note.id}', '#dc3545'),
    ]

    action_forms = [
        Form(
            Input(type='hidden', name='q', value=search) if search else None,
            Button(
                label,
                type='submit',
                cls='note-btn',
                style=f'background-color: {color};',
            ),
            method='post',
            action=action,
            cls='note-form',
        )
        for (label, action, color) in button_specs
    ]

    card_class = 'note-card archived' if archived else 'note-card active'
    return Div(
        Div(
            Div(
                Span(f'#{note.id}', cls='note-id'),
                Span(note.content, cls='note-content'),
                cls='note-text-wrap',
            ),
            Div(*action_forms, cls='note-actions'),
            cls='note-row',
        ),
        cls=card_class,
    )


@rt('/')
def get(q: str = ''):
    search = q.strip()
    active_notes = list(notes(where='status = "active" OR status IS NULL', order_by='id DESC'))
    archived_notes = list(notes(where='status = "archived"', order_by='id DESC'))
    archived_notes = dedupe_archived(archived_notes)
    if search:
        needle = normalize_item(search)
        archived_notes = [n for n in archived_notes if needle in normalize_item(n.content)]

    form = Form(
        Textarea(
            name='content',
            placeholder='Enter item(s), separated by newlines, commas, or semicolons...',
            rows=3,
            style='width: 100%; padding: 8px; margin-bottom: 8px; resize: vertical;',
        ),
        Button(
            'Add Item',
            type='submit',
            style='padding: 8px 14px; background-color: #0d6efd; color: white; border: none; border-radius: 8px; cursor: pointer;',
        ),
        method='post',
        action='/notes/add',
        style='width: 100%;',
    )

    search_form = Form(
        Input(
            type='text',
            name='q',
            value=search,
            placeholder='Search archived items...',
            style='flex: 1; min-width: 220px; padding: 8px 10px; border: 1px solid #d0d7de; border-radius: 8px;',
        ),
        Button(
            'Search',
            type='submit',
            style='padding: 8px 12px; background-color: #f1f3f5; border: 1px solid #d0d7de; border-radius: 8px; cursor: pointer;',
        ),
        A(
            'Clear',
            href='/notes',
            style='padding: 8px 12px; color: #555; text-decoration: none;',
        ),
        method='get',
        action='/notes',
        style='display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0 16px 0;',
    )

    top_section = Div(
        Div(form, style='flex: 1;'),
        style='display: flex; gap: 20px; margin-bottom: 16px; align-items: flex-start;'
    )

    active_list = Div(
        H3(f'Active Items ({len(active_notes)})', style='margin-bottom: 10px;'),
        *[note_card(note, archived=False, search=search) for note in active_notes],
        style='margin-top: 12px;'
    )

    archived_heading = f'Archived Items ({len(archived_notes)})'
    if search:
        archived_heading += f' for “{search}”'

    archived_children = [H3(archived_heading, style='margin: 22px 0 8px 0;'), search_form]
    archived_children.extend(note_card(note, archived=True, search=search) for note in archived_notes)
    if search and len(archived_notes) == 0:
        archived_children.append(P('No archived items match that search.', style='color: #666; margin-top: 8px;'))
    archived_list = Div(*archived_children, style='margin-top: 8px;')

    styles = Style('''
        .note-card {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px 10px;
            margin-bottom: 8px;
            background: #fafafa;
        }
        .note-card.archived {
            background: #f2f4f6;
            opacity: 0.92;
        }
        .note-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px 12px;
            flex-wrap: wrap;
        }
        .note-text-wrap {
            min-width: 0;
            flex: 1 1 320px;
        }
        .note-id {
            color: #777;
            font-size: 0.78rem;
            margin-right: 8px;
        }
        .note-content {
            font-size: 0.95rem;
            line-height: 1.3;
            word-break: break-word;
        }
        .note-actions {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: flex-end;
            flex: 0 1 auto;
        }
        .note-form { display: inline-flex; }
        .note-btn {
            padding: 3px 8px;
            color: white;
            border: none;
            border-radius: 7px;
            cursor: pointer;
            font-size: 0.82rem;
            line-height: 1.2;
            white-space: nowrap;
        }
    ''')

    return Titled(
        'Lal-Zhao Family Shopping List',
        styles,
        top_section,
        active_list,
        archived_list,
        style='max-width: 920px; margin: 0 auto; padding: 18px; font-family: Arial, sans-serif;'
    )


@rt('/add', methods=['post'])
def post(content: str):
    if content.strip():
        items = re.split(r'[\n,;]+', content)
        items = [item.strip() for item in items if item.strip()]

        existing = list(notes(order_by='id DESC'))
        by_norm = {}
        for note in existing:
            key = normalize_item(note.content)
            if key and key not in by_norm:
                by_norm[key] = note

        for item in items:
            key = normalize_item(item)
            if not key:
                continue
            existing_note = by_norm.get(key)
            if existing_note is not None:
                if existing_note.status == 'archived':
                    notes.update(id=existing_note.id, status='active')
                continue
            notes.insert(content=item, created_at=datetime.now().isoformat(), status='active')
            latest = list(notes(order_by='id DESC', limit=1))
            if latest:
                by_norm[key] = latest[0]

    return RedirectResponse('/notes', status_code=303)


@rt('/archive/{note_id}', methods=['post'])
def archive(note_id: int, q: str = ''):
    notes.update(id=note_id, status='archived')
    target = f'/notes?q={q}' if q else '/notes'
    return RedirectResponse(target, status_code=303)


@rt('/activate/{note_id}', methods=['post'])
def activate(note_id: int, q: str = ''):
    notes.update(id=note_id, status='active')
    target = f'/notes?q={q}' if q else '/notes'
    return RedirectResponse(target, status_code=303)


@rt('/delete/{note_id}', methods=['post'])
def delete(note_id: int, q: str = ''):
    notes.delete(note_id)
    target = f'/notes?q={q}' if q else '/notes'
    return RedirectResponse(target, status_code=303)


serve(host='0.0.0.0', port=8765)
