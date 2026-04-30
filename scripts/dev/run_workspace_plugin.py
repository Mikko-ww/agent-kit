from __future__ import annotations

import importlib
import sys


PLUGIN_MODULES = {
    "skills-link": "skills_link.plugin_cli",
    "opencode-env-switch": "opencode_env_switch.plugin_cli",
    "planning-files-skill": "planning_files_skill.plugin_cli",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("missing plugin id", file=sys.stderr)
        return 1

    plugin_id = sys.argv[1]
    plugin_args = sys.argv[2:]

    module_name = PLUGIN_MODULES.get(plugin_id)
    if module_name is None:
        print(f"unsupported workspace plugin: {plugin_id}", file=sys.stderr)
        return 1

    sys.argv = ["agent-kit-plugin", *plugin_args]

    plugin_cli = importlib.import_module(module_name)
    plugin_cli.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
