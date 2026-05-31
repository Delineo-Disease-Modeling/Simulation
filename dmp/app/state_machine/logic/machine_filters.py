"""Pure filtering of saved state-machine rows for the manager UI.

Extracted from manage_state_machines so the (fiddly, index-coupled) filter logic
is unit-testable. ``model_categories`` is now an explicit parameter: the manager
only computes it for a specific disease, and passing it in removes the latent
NameError when a category is selected without a disease (it never happens through
the UI today, but the coupling was fragile).
"""


def filter_machines(saved_machines, selected_disease, selected_category,
                    selected_variant, selected_vaccination, model_categories):
    """Filter DB rows by the manager's selections, most-recently-updated first.

    Rows are the tuples from ``StateMachineDB.list_state_machines()``:
    index 2 = disease_name, 5 = model_path, 7 = updated_at.
    """
    machines = list(saved_machines)

    # Filter by selected disease
    if selected_disease != "All Diseases":
        machines = [m for m in machines if m[2] == selected_disease]

    # Filter by category (resolve the category name to its id, match model_path prefix)
    if selected_category != "All Categories":
        selected_category_id = None
        for category in model_categories:
            if category["name"] == selected_category:
                selected_category_id = category["id"]
                break
        if selected_category_id:
            machines = [m for m in machines if m[5].startswith(selected_category_id)]

    # Filter by variant (model_path contains the variant)
    if selected_variant and selected_variant != "All Variants":
        machines = [m for m in machines if selected_variant in m[5]]

    # Filter by vaccination status (Measles only)
    if selected_disease == "Measles" and selected_vaccination and selected_vaccination != "All Vaccination Statuses":
        machines = [m for m in machines if selected_vaccination in m[5]]

    # Sort by update time descending
    machines.sort(key=lambda x: x[7], reverse=True)
    return machines
