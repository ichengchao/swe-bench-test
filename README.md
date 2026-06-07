# swe-bench-test

一个用于 SWE-bench 评估的 mock Python 项目。包含一个简单的数学工具库，故意引入了 bug，供 SWE agent 自动修复。

评估任务定义和工具集见 [swe-bench-task](https://github.com/ichengchao/swe-bench-task)。

## 项目结构

```
.
├── mathutils/
│   ├── __init__.py
│   └── core.py          # 数学工具函数 (add, subtract, multiply, divide, factorial, fibonacci)
├── tests/
│   └── test_core.py      # pytest 测试用例 (19个)
└── pyproject.toml
```

## Bug 说明

在 `mathutils/core.py` 的 `fibonacci` 函数中，将 `n==0` 和 `n==1` 两个 base case 合并为 `n <= 1: return 1`，导致 `fibonacci(0)` 返回 `1` 而不是 `0`。

对应 Issue: [#1 fibonacci(0) returns 1 instead of 0](https://github.com/ichengchao/swe-bench-test/issues/1)

## Commit 说明

| Commit | 说明 |
|--------|------|
| `1620de8` | 正确版本（所有测试通过） |
| `9324686` | 引入 bug（fibonacci base case 合并） |
| `5000a92` | 修复 bug（恢复独立的 base case） |
