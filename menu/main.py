from fasthtml.common import *

# Initialize the database
db = database('menu.db')
menu_items = db.t.menu_items
if menu_items not in db.t:
    menu_items.create(id=int, content=str, created_at=str, pk='id')
MenuItem = menu_items.dataclass()

# Create the FastHTML app
app, rt = fast_app()

@rt('/')
def get():
    # Get all menu items
    all_items = menu_items(order_by='id DESC')

    # Create the form for new menu items
    form = Form(
        Textarea(name='content', placeholder='Enter menu item...', rows=4,
                style='width: 100%; padding: 8px; margin-bottom: 10px;'),
        Button('Add Item', type='submit',
               style='padding: 8px 16px; background-color: #007bff; color: white; border: none; cursor: pointer;'),
        method='post',
        action='/menu/add',
        style='width: 100%;'
    )

    # Two column layout with form and lantern image
    top_section = Div(
        Div(form, style='flex: 1; padding-right: 20px;'),
        style='display: flex; gap: 20px; margin-bottom: 20px; align-items: flex-start;'
    )

    # Display existing menu items
    items_list = Div(
        *[Div(
            P(Strong(f"Item #{item.id}"), style='margin: 0; color: #666; font-size: 0.9em;'),
            P(item.content, style='margin: 10px 0;'),
            Div(
                Form(
                    Button('Edit', type='submit',
                           style='padding: 4px 12px; background-color: #28a745; color: white; border: none; cursor: pointer; margin-right: 8px;'),
                    method='get',
                    action=f'/menu/edit/{item.id}',
                    style='display: inline;'
                ),
                Form(
                    Button('Delete', type='submit',
                           style='padding: 4px 12px; background-color: #dc3545; color: white; border: none; cursor: pointer;'),
                    method='post',
                    action=f'/menu/delete/{item.id}',
                    style='display: inline;'
                ),
                style='display: flex; gap: 8px;'
            ),
            style='border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9;'
        ) for item in all_items],
        style='margin-top: 20px;'
    )

    return Titled('Lal-Zhao Family Menu',
        top_section,
        items_list,
        style='max-width: 1000px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
    )

@rt('/add', methods=['post'])
def post(content: str):
    from datetime import datetime
    if content.strip():
        menu_items.insert(content=content, created_at=datetime.now().isoformat())
    return RedirectResponse('/menu', status_code=303)

@rt('/edit/{item_id}')
def edit(item_id: int):
    item = menu_items[item_id]

    # Edit form
    edit_form = Form(
        Textarea(name='content', rows=4, style='width: 100%; padding: 8px; margin-bottom: 10px;')(item.content),
        Div(
            Button('Save', type='submit',
                   style='padding: 8px 16px; background-color: #007bff; color: white; border: none; cursor: pointer; margin-right: 8px;'),
            A(Button('Cancel', type='button',
                     style='padding: 8px 16px; background-color: #6c757d; color: white; border: none; cursor: pointer;'),
              href='/menu'),
            style='display: flex; gap: 8px;'
        ),
        method='post',
        action=f'/menu/update/{item_id}',
        style='width: 100%;'
    )

    return Titled(f'Edit Item #{item_id}',
        edit_form,
        style='max-width: 600px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
    )

@rt('/update/{item_id}', methods=['post'])
def update(item_id: int, content: str):
    if content.strip():
        menu_items.update(id=item_id, content=content)
    return RedirectResponse('/menu', status_code=303)

@rt('/delete/{item_id}', methods=['post'])
def delete(item_id: int):
    menu_items.delete(item_id)
    return RedirectResponse('/menu', status_code=303)

serve(host='0.0.0.0', port=8742)
