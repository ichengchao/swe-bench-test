# SWE-bench Task 字段说明

本文档说明 `swe_task.json` 中每个字段的含义、来源以及在评估流程中的作用。

## 整体结构

`swe_task.json` 是一个 JSON 数组，每个元素代表一个 SWE-bench task 实例。一个 task 描述了一个完整的"bug → 修复 → 验证"流程。

## 字段详解

### instance_id

```json
"instance_id": "ichengchao__swe-bench-test-1"
```

- **含义**: task 实例的唯一标识符
- **命名规则**: `{owner}__{repo}-{issue_number}`，双下划线分隔 owner 和 repo
- **来源**: 根据 GitHub 仓库和 Issue 编号手动构造
- **用途**: 在批量评估时用于区分不同 task，也用于结果报告的 key

### repo

```json
"repo": "ichengchao/swe-bench-test"
```

- **含义**: GitHub 仓库的路径（`owner/repo` 格式）
- **来源**: 仓库的 GitHub 地址，即 `github.com/ichengchao/swe-bench-test`
- **用途**: agent 可以据此 clone 仓库或定位远程地址

### base_commit

```json
"base_commit": "932468602d3778403ec173ca7a1151d329c9e027"
```

- **含义**: 包含 bug 的 commit SHA（即 buggy 版本）
- **来源**: 引入 bug 后执行 `git rev-parse HEAD` 获得
- **用途**: 评估时 agent 会被 checkout 到这个 commit，在此基础上进行修复。这是 agent 的"起点"
- **获取方式**:
  ```bash
  # 引入 bug 并 commit 后
  git rev-parse HEAD
  # 输出: 932468602d3778403ec173ca7a1151d329c9e027
  ```

### problem_statement

- **含义**: 问题描述，即 GitHub Issue 的内容
- **来源**: 从 GitHub Issue 的 title + body 拼接而来
- **用途**: 这是提供给 agent 的唯一输入。agent 需要理解问题描述，定位 bug，并生成修复代码
- **注意**: 这里不应包含修复方案或具体的代码修改指导，只描述"现象"和"期望行为"

完整内容（渲染后）:

> fibonacci(0) returns 1 instead of 0
>
> ## Bug Description
>
> The `fibonacci(0)` function returns `1` instead of the expected `0`.
>
> ## Steps to Reproduce
>
> ```python
> from mathutils import fibonacci
>
> print(fibonacci(0))  # Expected: 0, Actual: 1
> ```
>
> ## Expected Behavior
>
> `fibonacci(0)` should return `0`, since the Fibonacci sequence is defined as:
> - F(0) = 0
> - F(1) = 1
> - F(n) = F(n-1) + F(n-2)
>
> ## Actual Behavior
>
> `fibonacci(0)` returns `1`.
>
> ## Test Failure
>
> ```
> FAILED tests/test_core.py::TestFibonacci::test_zero - assert 1 == 0
> ```

### patch

- **含义**: 正确修复的 unified diff（即 gold patch / 参考答案）
- **来源**: 修复 bug 后通过 `git diff` 获得
- **用途**:
  - 不会提供给 agent（agent 不知道正确答案）
  - 用于参考对比：评估时可以对比 agent 生成的 patch 与 gold patch
  - 在某些评估框架中也可以用来验证测试的正确性
- **获取方式**:
  ```bash
  # 修复 bug 后，commit 之前
  git diff mathutils/core.py
  ```

完整内容:

```diff
diff --git a/mathutils/core.py b/mathutils/core.py
index 713fd8c..a54e80d 100644
--- a/mathutils/core.py
+++ b/mathutils/core.py
@@ -43,7 +43,9 @@ def fibonacci(n):
     """
     if n < 0:
         raise ValueError("Fibonacci is not defined for negative numbers")
-    if n <= 1:
+    if n == 0:
+        return 0
+    if n == 1:
         return 1
     a, b = 0, 1
     for _ in range(2, n + 1):
```

解读：将 `if n <= 1: return 1`（对 n=0 和 n=1 都返回 1）拆分为两个独立的 base case，使 `fibonacci(0)` 正确返回 `0`。

### test_patch

```json
"test_patch": ""
```

- **含义**: 为验证修复而新增/修改的测试代码的 diff
- **来源**: 如果修复时需要添加新测试，这里记录测试文件的 diff
- **用途**:
  - 评估时，先将 test_patch apply 到 base_commit 上，确保 FAIL_TO_PASS 的测试存在
  - 如果测试在 base_commit 中已经存在（如本例），则此字段为空
- **本例为空的原因**: `tests/test_core.py::TestFibonacci::test_zero` 在 base_commit 时已存在，无需额外添加测试

### FAIL_TO_PASS

```json
"FAIL_TO_PASS": [
  "tests/test_core.py::TestFibonacci::test_zero"
]
```

- **含义**: 在 base_commit（buggy 版本）上失败，修复后应该通过的测试列表
- **格式**: pytest 的 test node ID（`文件路径::类名::方法名`）
- **来源**: 在 base_commit 上运行 `pytest -v`，找出失败的测试
- **用途**: 评估 agent 是否成功修复了 bug 的核心指标
  - 修复前：这些测试必须 FAIL（验证 bug 确实存在）
  - 修复后：这些测试必须 PASS（验证 bug 已被修复）
- **获取方式**:
  ```bash
  # 在 buggy commit 上运行测试
  git checkout 932468602d
  python3 -m pytest tests/ -v
  # 找到 FAILED 的测试: tests/test_core.py::TestFibonacci::test_zero
  ```

### PASS_TO_PASS

```json
"PASS_TO_PASS": [
  "tests/test_core.py::TestAdd::test_positive",
  "tests/test_core.py::TestAdd::test_negative",
  "..."
]
```

- **含义**: 在 base_commit 上已经通过，修复后仍应通过的测试列表
- **格式**: 同上，pytest test node ID
- **来源**: 在 base_commit 上运行 `pytest -v`，找出所有通过的测试
- **用途**: 确保 agent 的修复没有引入回归（regression）
  - 修复前：这些测试 PASS
  - 修复后：这些测试仍然必须 PASS
- **获取方式**:
  ```bash
  # 在 buggy commit 上运行测试
  python3 -m pytest tests/ -v
  # 收集所有 PASSED 的测试
  ```

### environment_setup_commit

```json
"environment_setup_commit": "1620de8"
```

- **含义**: 环境初始化所需的 commit SHA（短格式）
- **来源**: 项目首次创建完整代码和测试的 commit
- **用途**:
  - 某些 SWE-bench 评估框架需要此字段来安装依赖或初始化环境
  - 通常是第一个"一切正常"的 commit
- **获取方式**:
  ```bash
  # 正确版本首次提交后
  git rev-parse --short HEAD
  # 输出: 1620de8
  ```

## 评估流程中各字段的使用时序

```
1. git checkout {base_commit}          # 切到 buggy 版本
2. git apply {test_patch}              # 应用测试补丁（如果有）
3. pytest {FAIL_TO_PASS}               # 验证 bug 确实存在 → 应 FAIL
4. pytest {PASS_TO_PASS}               # 验证其他测试正常 → 应 PASS
5. 将 {problem_statement} 给 agent     # agent 开始工作
6. agent 生成 patch 并 apply            # agent 修复 bug
7. pytest {FAIL_TO_PASS}               # 验证修复 → 应 PASS
8. pytest {PASS_TO_PASS}               # 验证无回归 → 应 PASS
9. 对比 agent patch 与 {patch}          # 可选：对比参考答案
```

## 如何构造新的 task

```bash
# 1. 写好正确代码和测试，commit
git add . && git commit -m "Add feature X"
SETUP_COMMIT=$(git rev-parse --short HEAD)

# 2. 引入 bug，commit
# ... 修改代码 ...
git add . && git commit -m "Refactor X"
BASE_COMMIT=$(git rev-parse HEAD)

# 3. 创建 GitHub Issue
gh issue create --title "Bug description" --body "..."

# 4. 修复 bug，记录 patch
# ... 修复代码 ...
GOLD_PATCH=$(git diff)
git add . && git commit -m "Fix bug"

# 5. 在 buggy commit 上收集测试结果
git checkout $BASE_COMMIT
python3 -m pytest tests/ -v    # 记录 FAIL 和 PASS 的测试

# 6. 填写 swe_task.json
```
