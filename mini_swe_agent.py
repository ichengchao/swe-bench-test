#!/usr/bin/env python3
"""
Mini SWE Agent - A minimal SWE-bench evaluation agent.

Workflow:
1. Read task JSON
2. Checkout to base_commit (the buggy version)
3. Send problem_statement to LLM, ask it to generate a patch
4. Apply the patch
5. Run FAIL_TO_PASS tests to verify the fix
6. Run PASS_TO_PASS tests to ensure no regressions
"""

import json
import os
import subprocess
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Please install openai SDK: pip3 install openai")
    sys.exit(1)


def run_cmd(cmd, cwd=None):
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, result.stdout, result.stderr


def load_task(task_file):
    """Load and return the first task from the JSON file."""
    with open(task_file) as f:
        tasks = json.load(f)
    return tasks[0]


def checkout_base(repo_dir, base_commit):
    """Checkout the base (buggy) commit."""
    code, out, err = run_cmd(f"git checkout {base_commit}", cwd=repo_dir)
    if code != 0:
        print(f"Failed to checkout {base_commit}: {err}")
        sys.exit(1)
    print(f"[+] Checked out base commit: {base_commit[:10]}...")


def read_repo_context(repo_dir):
    """Read relevant source files for LLM context."""
    context = {}
    for root, dirs, files in os.walk(repo_dir):
        # Skip hidden dirs and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                filepath = os.path.join(root, f)
                relpath = os.path.relpath(filepath, repo_dir)
                with open(filepath) as fh:
                    context[relpath] = fh.read()
    return context


def generate_patch(problem_statement, repo_context):
    """Call DashScope API (OpenAI-compatible) to generate a fix patch."""
    client = OpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    files_text = ""
    for path, content in sorted(repo_context.items()):
        files_text += f"\n--- {path} ---\n{content}\n"

    prompt = f"""You are a software engineer fixing a bug. Given the problem statement and
the repository source code, generate a unified diff patch that fixes the bug.

IMPORTANT: Output ONLY the unified diff patch, nothing else. No explanation, no markdown
fences, just the raw diff starting with "diff --git".

## Problem Statement
{problem_statement}

## Repository Files
{files_text}

Generate the patch now:"""

    response = client.chat.completions.create(
        model="qwen-plus",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    patch_text = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    if patch_text.startswith("```"):
        lines = patch_text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # remove closing fence
        patch_text = "\n".join(lines)
    return patch_text


def apply_patch(repo_dir, patch_text):
    """Apply a unified diff patch to the repo. Tries multiple strategies."""
    # Ensure patch ends with newline
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    patch_file = os.path.join(repo_dir, "_agent_patch.diff")

    strategies = [
        "git apply _agent_patch.diff",
        "git apply --ignore-whitespace _agent_patch.diff",
        "git apply --3way _agent_patch.diff",
        "patch -p1 < _agent_patch.diff",
    ]

    for cmd in strategies:
        with open(patch_file, "w") as f:
            f.write(patch_text)
        code, out, err = run_cmd(cmd, cwd=repo_dir)
        if os.path.exists(patch_file):
            os.remove(patch_file)
        if code == 0:
            print(f"[+] Patch applied successfully (via: {cmd.split()[0:2]})")
            return True
        print(f"[!] {cmd} failed: {err.strip()}")

    # Last resort: try to parse and apply manually via search-replace
    print("[!] All patch strategies failed, trying manual apply...")
    return manual_apply_patch(repo_dir, patch_text)


def manual_apply_patch(repo_dir, patch_text):
    """Manually apply patch by parsing diff hunks and doing string replacement."""
    import re
    current_file = None
    old_lines = []
    new_lines = []
    in_hunk = False
    applied = False

    for line in patch_text.split("\n"):
        if line.startswith("diff --git"):
            # Apply previous hunk if any
            if current_file and old_lines:
                applied = _apply_hunk(repo_dir, current_file, old_lines, new_lines) or applied
                old_lines, new_lines = [], []
            # Parse file path: diff --git a/path b/path
            match = re.search(r"b/(.+)$", line)
            if match:
                current_file = match.group(1)
            in_hunk = False
        elif line.startswith("@@"):
            if old_lines:
                applied = _apply_hunk(repo_dir, current_file, old_lines, new_lines) or applied
                old_lines, new_lines = [], []
            in_hunk = True
        elif in_hunk:
            if line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            elif line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])

    # Apply last hunk
    if current_file and old_lines:
        applied = _apply_hunk(repo_dir, current_file, old_lines, new_lines) or applied

    if applied:
        print("[+] Patch applied via manual search-replace")
    return applied


def _apply_hunk(repo_dir, filepath, old_lines, new_lines):
    """Replace old_lines with new_lines in the given file."""
    full_path = os.path.join(repo_dir, filepath)
    if not os.path.exists(full_path):
        return False
    with open(full_path) as f:
        content = f.read()
    old_text = "\n".join(old_lines)
    new_text = "\n".join(new_lines)
    if old_text in content:
        content = content.replace(old_text, new_text, 1)
        with open(full_path, "w") as f:
            f.write(content)
        return True
    return False


def run_tests(repo_dir, test_list, label=""):
    """Run a list of pytest test IDs. Returns (passed, failed, results)."""
    if not test_list:
        return [], [], []

    test_args = " ".join(test_list)
    code, out, err = run_cmd(
        f"python3 -m pytest {test_args} -v", cwd=repo_dir
    )

    full_output = out + err
    passed = []
    failed = []

    for test_id in test_list:
        if f"{test_id} PASSED" in full_output:
            passed.append(test_id)
        else:
            failed.append(test_id)

    return passed, failed, full_output


def main():
    task_file = sys.argv[1] if len(sys.argv) > 1 else "swe_task.json"
    repo_dir = os.path.dirname(os.path.abspath(task_file))

    print("=" * 60)
    print("  Mini SWE Agent")
    print("=" * 60)

    # 1. Load task
    task = load_task(task_file)
    print(f"\n[*] Task: {task['instance_id']}")
    print(f"[*] Repo: {task['repo']}")
    print(f"[*] FAIL_TO_PASS: {task['FAIL_TO_PASS']}")
    print(f"[*] PASS_TO_PASS: {len(task['PASS_TO_PASS'])} tests")

    # 2. Checkout buggy commit
    print(f"\n--- Step 1: Checkout base commit ---")
    checkout_base(repo_dir, task["base_commit"])

    # 3. Verify tests fail as expected
    print(f"\n--- Step 2: Verify FAIL_TO_PASS tests fail ---")
    passed, failed, output = run_tests(repo_dir, task["FAIL_TO_PASS"])
    if failed:
        print(f"[+] Confirmed: {len(failed)} test(s) failing as expected")
    else:
        print("[!] Warning: FAIL_TO_PASS tests are not failing!")

    # 4. Get repo context and generate patch via LLM
    print(f"\n--- Step 3: Generate patch via LLM ---")
    repo_context = read_repo_context(repo_dir)
    patch_text = generate_patch(task["problem_statement"], repo_context)
    print(f"[+] Generated patch:\n{patch_text}\n")

    # 5. Apply patch
    print(f"--- Step 4: Apply patch ---")
    if not apply_patch(repo_dir, patch_text):
        print("[FAIL] Could not apply patch")
        run_cmd(f"git checkout .", cwd=repo_dir)  # restore
        run_cmd(f"git checkout master", cwd=repo_dir)
        sys.exit(1)

    # 6. Run FAIL_TO_PASS tests (should now pass)
    print(f"\n--- Step 5: Verify FAIL_TO_PASS tests now pass ---")
    passed_f2p, failed_f2p, _ = run_tests(repo_dir, task["FAIL_TO_PASS"])

    # 7. Run PASS_TO_PASS tests (should still pass)
    print(f"\n--- Step 6: Verify PASS_TO_PASS tests still pass ---")
    passed_p2p, failed_p2p, _ = run_tests(repo_dir, task["PASS_TO_PASS"])

    # 8. Report results
    print(f"\n{'=' * 60}")
    print(f"  Results for {task['instance_id']}")
    print(f"{'=' * 60}")
    print(f"  FAIL_TO_PASS: {len(passed_f2p)}/{len(task['FAIL_TO_PASS'])} now passing")
    print(f"  PASS_TO_PASS: {len(passed_p2p)}/{len(task['PASS_TO_PASS'])} still passing")

    all_f2p_pass = len(failed_f2p) == 0
    all_p2p_pass = len(failed_p2p) == 0
    resolved = all_f2p_pass and all_p2p_pass

    if resolved:
        print(f"\n  STATUS: RESOLVED ✓")
    else:
        print(f"\n  STATUS: FAILED ✗")
        if failed_f2p:
            print(f"  Still failing: {failed_f2p}")
        if failed_p2p:
            print(f"  Regressions: {failed_p2p}")

    # Cleanup: go back to master
    run_cmd("git checkout .", cwd=repo_dir)
    run_cmd("git checkout master", cwd=repo_dir)

    return 0 if resolved else 1


if __name__ == "__main__":
    sys.exit(main())
