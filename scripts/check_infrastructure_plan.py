"""Reject destructive migration in ordinary CI apply; cleanup needs separate review."""
import json
import sys


def check(plan, operation):
    if operation == 'destroy':
        return
    deleting = [r['address'] for r in plan.get('resource_changes', [])
                if 'delete' in r['change']['actions']]
    if deleting:
        raise ValueError('Plano contém remoção/substituição; revisar migração/limpeza separadamente: ' + ', '.join(deleting))


if __name__ == '__main__':
    try:
        check(json.load(sys.stdin), sys.argv[1])
    except (ValueError, KeyError, IndexError) as error:
        raise SystemExit(str(error))
