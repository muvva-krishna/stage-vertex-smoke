"""PLUMBING-FIXTURE oracle. Lives in evaluator/ (never agent-visible).

Protocol: argv[1] = workspace dir. Print `GROUP <name> PASS|FAIL <detail>`
lines; exit 0 iff all groups pass. Groups prefixed `compat:` feed the rubric's
compatibility/regression component; others feed functional correctness.
"""
import importlib.util
import sys
from pathlib import Path


def load(workspace: Path):
    spec = importlib.util.spec_from_file_location("counter", workspace / "counter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    workspace = Path(sys.argv[1])
    mod = load(workspace)
    results = []
    results.append(("addition", mod.add(1, 2) == 3, "add(1,2)==3"))
    results.append(("addition_neg", mod.add(-1, 1) == 0, "add(-1,1)==0"))
    results.append(
        ("compat:format", mod.format_total(1, 2) == "1+2=3", "format_total stable")
    )
    ok = True
    for name, passed, detail in results:
        group = name if name.startswith("compat:") else (
            f"compat:{name.split(':')[1]}" if name.startswith("compat") else name
        )
        # map the format check into the compat namespace for the rubric
        if name == "compat:format":
            group = "compat:format"
        print(f"GROUP {group} {'PASS' if passed else 'FAIL'} {detail}")
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
