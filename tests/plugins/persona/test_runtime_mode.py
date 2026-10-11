from src.core.persona_runtime_mode import should_use_script_mode


def test_script_entrypoint_uses_lightweight_mode():
    assert should_use_script_mode(
        "/home/ubuntu/ATRI_PROJ/scripts/migrate_persona.py",
    )


def test_launcher_script_in_stack_does_not_hide_bot_plugin():
    assert not should_use_script_mode(
        "/home/ubuntu/ATRI_PROJ/scripts/manage_processes.py",
        ["/home/ubuntu/ATRI_PROJ/scripts/manage_processes.py"],
        ["/home/ubuntu/ATRI_PROJ/bot.py"],
    )


def test_adapter_import_keeps_legacy_lightweight_mode():
    assert should_use_script_mode(
        "/home/ubuntu/ATRI_PROJ/bot.py",
        ["/home/ubuntu/ATRI_PROJ/src/adapters/nonebot/persona_assembler.py"],
    )


def test_scripts_substring_in_other_path_component_does_not_enable_script_mode():
    assert not should_use_script_mode(
        "/home/ubuntu/ATRI_PROJ/scripts-helper/bot.py",
    )
