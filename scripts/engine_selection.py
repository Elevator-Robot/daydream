"""Read-only Godot discovery; never executes a candidate to discover it."""

import json
import os
from pathlib import Path
import re
import shutil

from sprite_core import read_regular


def version_pin(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"4\.\d+(?:\.\d+(?:\.[A-Za-z0-9_.-]+)?)?", value) or int(value.split('.')[1]) < 3:
        raise ValueError("Project engine settings must specify Godot 4.3 or newer")
    return value


def project_engine(context, data):
    """Called only after read grants cover the project/configuration files."""
    try:
        settings = json.loads(read_regular(context.path('.daydream/preview.json'), 16384))
    except FileNotFoundError:
        settings = {}
    if not isinstance(settings, dict) or set(settings) - {'godot', 'version'}:
        raise ValueError("Fix the project's .daydream/preview.json; only godot and version are supported")
    if 'godot' in settings and (not isinstance(settings['godot'], str) or not settings['godot'].strip()):
        raise ValueError("Fix the project's Godot setting: use an executable name or path")
    if 'version' in settings and not isinstance(settings['version'], str):
        raise ValueError("Fix the project's Godot version setting")
    configured_pin = version_pin(settings.get('version'))
    requested_pin = version_pin(data.get('godot_version'))
    if configured_pin and requested_pin and not (configured_pin == requested_pin or configured_pin.startswith(requested_pin + '.') or requested_pin.startswith(configured_pin + '.')):
        raise ValueError("Requested Godot version conflicts with the project's engine settings; no engine was run")
    try:
        project = read_regular(context.path('project.godot'), 1024 * 1024).decode('utf-8')
    except FileNotFoundError:
        project = ''
    features = re.search(r'^\s*config/features\s*=\s*PackedStringArray\(([^)]*)\)', project, re.MULTILINE)
    match = re.search(r'"(4\.\d+(?:\.\d+)?)"', features[1]) if features else None
    target = version_pin(match[1]) if match else None
    expected = (requested_pin if requested_pin and (not configured_pin or requested_pin.startswith(configured_pin + '.'))
                else configured_pin or requested_pin or target)
    if target and expected and expected.split('.')[:2] != target.split('.')[:2]:
        raise ValueError(f"Engine settings conflict with this project's Godot {target} target; no engine was run")
    if data.get('godot'):
        choice, origin = data['godot'], 'explicit override'
    elif settings.get('godot'):
        choice, origin = settings['godot'], 'project settings'
    elif os.environ.get('GODOT_BIN'):
        choice, origin = os.environ['GODOT_BIN'], 'GODOT_BIN'
    else:
        choice, origin = shutil.which('godot') or shutil.which('godot4'), 'PATH'
    if not isinstance(choice, str) or not choice or any(ord(ch) < 32 for ch in choice):
        raise ValueError("Godot wasn't found. Install your project's Godot editor or configure it once in .daydream/preview.json; nothing was installed automatically")
    if not Path(choice).is_absolute():
        if '/' in choice:
            choice = str(context.root / choice)
        else:
            choice = shutil.which(choice)
    if not choice:
        raise ValueError("The configured Godot editor wasn't found; check the project's engine setup")
    from editor_layout import executable
    binary = executable(choice)
    if not os.access(binary, os.X_OK):
        raise ValueError("The detected Godot editor isn't executable; check the project's engine setup")
    return {'godot': binary, 'expected_version': expected, 'project_target': target, 'selection': origin}
