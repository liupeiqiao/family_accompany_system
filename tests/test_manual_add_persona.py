"""RED -> GREEN: Persona section must have manual add-new-persona button."""


def test_source_has_add_new_persona_button():
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    section_start = source.find("show_new_persona_form")
    assert section_start > 0, "show_new_persona_form not found in app.py"
    assert "btn_add_new_persona" in source, "missing btn_add_new_persona"


def test_delete_persona_uses_proper_db_function():
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    delete_area = source.split("btn_del_persona")[1][:500] if "btn_del_persona" in source else ""
    assert "db_delete_persona" in delete_area or "remove_persona" in delete_area, (
        "delete should use db_delete_persona / remove_persona, not save empty dict"
    )
