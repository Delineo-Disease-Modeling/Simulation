import importlib


def test_dmp_entrypoint_imports_with_simulation_app_module_present():
    importlib.import_module("app")

    module = importlib.import_module("dmp.api.dmp_api_v2")

    assert module.app.title == "Disease Modeling Platform API v2.0"
