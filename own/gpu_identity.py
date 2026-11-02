"""Read only the provider workspace identity; never echo credentials or SDK errors."""
import json
import sys


def main():
    try:
        import modal
        workspace = modal.Workspace.from_context().hydrate()
        print(json.dumps({'workspace_name': workspace.name}))
    except Exception:
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
