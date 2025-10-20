from fasthtml.common import *

# Initialize the database
db = database('notes.db')
notes = db.t.notes
if notes not in db.t:
    notes.create(id=int, content=str, created_at=str, status=str, pk='id')
Note = notes.dataclass()

# Add status column if it doesn't exist (migration)
try:
    db.execute("ALTER TABLE notes ADD COLUMN status TEXT DEFAULT 'active'")
except:
    pass

# Create the FastHTML app
app, rt = fast_app()

@rt('/')
def get():
    # Get all notes, separated by status
    active_notes = notes(where='status = "active" OR status IS NULL', order_by='id DESC')
    archived_notes = notes(where='status = "archived"', order_by='id DESC')

    # Create the form for new notes
    form = Form(
        Textarea(name='content', placeholder='Enter your note...', rows=4,
                style='width: 100%; padding: 8px; margin-bottom: 10px;'),
        Button('Add Item', type='submit',
               style='padding: 8px 16px; background-color: #007bff; color: white; border: none; cursor: pointer;'),
        method='post',
        action='/notes/add',
        style='width: 100%;'
    )

    # Two column layout with form and lantern image
    top_section = Div(
        Div(form, style='flex: 1; padding-right: 20px;'),
        style='display: flex; gap: 20px; margin-bottom: 20px; align-items: flex-start;'
    )

    # Display active notes
    active_list = Div(
        H3('Active Items', style='margin-bottom: 15px;'),
        *[Div(
            P(Strong(f"Item #{note.id}"), style='margin: 0; color: #666; font-size: 0.9em;'),
            P(note.content, style='margin: 10px 0;'),
            Div(
                Form(
                    Button('Archive', type='submit',
                           style='padding: 4px 12px; background-color: #6c757d; color: white; border: none; cursor: pointer;'),
                    method='post',
                    action=f'/notes/archive/{note.id}',
                    style='display: inline;'
                ),
                Form(
                    Button('Delete', type='submit',
                           style='padding: 4px 12px; background-color: #dc3545; color: white; border: none; cursor: pointer;'),
                    method='post',
                    action=f'/notes/delete/{note.id}',
                    style='display: inline; margin-left: 8px;'
                ),
                style='display: flex; gap: 8px;'
            ),
            style='border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9;'
        ) for note in active_notes],
        style='margin-top: 20px;'
    )

    # Display archived notes
    archived_list = Div(
        H3('Archived Items', style='margin-bottom: 15px; margin-top: 30px;'),
        *[Div(
            P(Strong(f"Item #{note.id}"), style='margin: 0; color: #666; font-size: 0.9em;'),
            P(note.content, style='margin: 10px 0;'),
            Div(
                Form(
                    Button('Reactivate', type='submit',
                           style='padding: 4px 12px; background-color: #28a745; color: white; border: none; cursor: pointer;'),
                    method='post',
                    action=f'/notes/activate/{note.id}',
                    style='display: inline;'
                ),
                Form(
                    Button('Delete', type='submit',
                           style='padding: 4px 12px; background-color: #dc3545; color: white; border: none; cursor: pointer;'),
                    method='post',
                    action=f'/notes/delete/{note.id}',
                    style='display: inline; margin-left: 8px;'
                ),
                style='display: flex; gap: 8px;'
            ),
            style='border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #e9ecef; opacity: 0.8;'
        ) for note in archived_notes],
        style='margin-top: 20px;'
    ) if len(archived_notes) > 0 else Div()

    return Titled('Lal-Zhao Family Shopping List',
        top_section,
        active_list,
        archived_list,
        style='max-width: 1000px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
    )

@rt('/add', methods=['post'])
def post(content: str):
    from datetime import datetime
    if content.strip():
        notes.insert(content=content, created_at=datetime.now().isoformat(), status='active')
    return RedirectResponse('/notes', status_code=303)

@rt('/archive/{note_id}', methods=['post'])
def archive(note_id: int):
    notes.update(id=note_id, status='archived')
    return RedirectResponse('/notes', status_code=303)

@rt('/activate/{note_id}', methods=['post'])
def activate(note_id: int):
    notes.update(id=note_id, status='active')
    return RedirectResponse('/notes', status_code=303)

@rt('/delete/{note_id}', methods=['post'])
def delete(note_id: int):
    notes.delete(note_id)
    return RedirectResponse('/notes', status_code=303)

serve(host='0.0.0.0', port=8765)
