# swe-bench-test

一个用于学习和测试 SWE-bench 流程的 mock 仓库。包含一个简单的 Python 数学工具库，故意引入 bug，然后使用 SWE agent 自动修复。

## 项目结构

```
.
├── mathutils/
│   ├── __init__.py
│   └── core.py              # 数学工具函数 (add, subtract, multiply, divide, factorial, fibonacci)
├── tests/
│   └── test_core.py          # pytest 测试用例 (19个)
├── swe_task.json              # SWE-bench 格式的 task 定义
├── mini_swe_agent.py          # 自定义的 mini SWE agent (使用 DashScope)
├── dashscope_config.yaml      # 官方 mini-swe-agent 的 DashScope 配置
└── pyproject.toml
```

## Bug 说明

在 `mathutils/core.py` 的 `fibonacci` 函数中，将 `n==0` 和 `n==1` 两个 base case 合并为 `n <= 1: return 1`，导致 `fibonacci(0)` 返回 `1` 而不是 `0`。

对应 Issue: [#1 fibonacci(0) returns 1 instead of 0](https://github.com/ichengchao/swe-bench-test/issues/1)

## SWE-bench Task 格式

`swe_task.json` 包含一个标准的 SWE-bench task 实例：

```json
{
  "instance_id": "ichengchao__swe-bench-test-1",
  "repo": "ichengchao/swe-bench-test",
  "base_commit": "932468602d3778403ec173ca7a1151d329c9e027",
  "problem_statement": "...",
  "patch": "...",
  "FAIL_TO_PASS": ["tests/test_core.py::TestFibonacci::test_zero"],
  "PASS_TO_PASS": ["tests/test_core.py::TestAdd::test_positive", "..."]
}
```

- `base_commit`: 包含 bug 的 commit
- `patch`: 正确修复的 gold patch
- `FAIL_TO_PASS`: 修复前失败、修复后应通过的测试
- `PASS_TO_PASS`: 修复前后都应通过的测试

## 手动验证：用 gold patch 跑 FAIL_TO_PASS

不依赖任何 agent，直接用 `swe_task.json` 中的 gold patch 验证整个评估流程。

### 1. Checkout 到 buggy commit

```bash
git checkout 932468602d3778403ec173ca7a1151d329c9e027
```

### 2. 确认 FAIL_TO_PASS 测试失败

```bash
python3 -m pytest tests/test_core.py::TestFibonacci::test_zero -v
# 预期输出: FAILED - assert 1 == 0
```

### 3. 从 swe_task.json 中提取 patch 并保存为文件

```bash
python3 -c "
import json
with open('swe_task.json') as f:
    task = json.load(f)[0]
with open('gold_patch.diff', 'w') as f:
    f.write(task['patch'])
"
```

### 4. 应用 gold patch

```bash
git apply gold_patch.diff
```

此时 `mathutils/core.py` 已被修改，但不会产生 commit。

### 5. 验证 FAIL_TO_PASS 测试通过

```bash
python3 -m pytest tests/test_core.py::TestFibonacci::test_zero -v
# 预期输出: PASSED
```

### 6. 验证 PASS_TO_PASS 无回归

```bash
python3 -m pytest tests/test_core.py -v
# 预期输出: 19 passed
```

### 7. 恢复仓库

```bash
rm -f gold_patch.diff
git checkout . && git checkout master
```

## 使用方式

### 方式一：官方 mini-swe-agent (推荐)

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 是 SWE-agent 团队的官方极简 agent，约 100 行代码，SWE-bench verified 得分超 74%。

#### 1. 安装

```bash
pip install uv   # 如果还没有 uv
```

#### 2. 配置 DashScope

编辑 `dashscope_config.yaml`，填入你的 API key：

```yaml
model:
  model_name: "openai/qwen-plus"
  model_class: "litellm"
  model_kwargs:
    api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: "sk-your-dashscope-key"
  cost_tracking: "ignore_errors"

agent:
  step_limit: 30
```

#### 3. Checkout 到 buggy commit

```bash
git checkout 932468602d3778403ec173ca7a1151d329c9e027
```

#### 4. 运行 agent

```bash
export MSWEA_CONFIGURED=1

uvx mini-swe-agent \
  -m "openai/qwen-plus" \
  -c mini.yaml \
  -c dashscope_config.yaml \
  -t "fibonacci(0) returns 1 instead of 0. The bug is in mathutils/core.py. Fix it so that tests/test_core.py::TestFibonacci::test_zero passes." \
  -y \
  --exit-immediately \
  --agent-class default \
  -o agent_output.json
```

参数说明：
- `-m`: 模型名称 (需要带 `openai/` 前缀)
- `-c mini.yaml`: 加载默认配置
- `-c dashscope_config.yaml`: 覆盖模型配置为 DashScope
- `-t`: 问题描述 (即 problem_statement)
- `-y`: 跳过确认提示
- `--agent-class default`: 使用非交互 agent (适合脚本/CI 环境)
- `--exit-immediately`: agent 完成后自动退出
- `-o`: 输出 trajectory 文件路径

#### 5. 验证修复

```bash
python3 -m pytest tests/test_core.py -v
```

#### 6. 恢复仓库

```bash
git checkout . && git checkout master
```

### 方式二：自定义 mini SWE agent

`mini_swe_agent.py` 是一个自定义的简易 agent，直接读取 `swe_task.json` 并自动完成整个流程。

#### 1. 安装依赖

```bash
pip3 install openai pytest
```

#### 2. 运行

```bash
export DASHSCOPE_API_KEY="sk-your-dashscope-key"
python3 mini_swe_agent.py swe_task.json
```

执行流程：
1. 读取 task JSON
2. Checkout 到 buggy commit
3. 验证 FAIL_TO_PASS 测试确实失败
4. 将代码和问题描述发给 LLM，生成修复 patch
5. Apply patch (支持多种 fallback 策略)
6. 运行 FAIL_TO_PASS 测试 (应通过)
7. 运行 PASS_TO_PASS 测试 (无回归)
8. 输出结果：RESOLVED 或 FAILED

## 如何创建新的 task

1. 在代码中引入新 bug 并 commit
2. 记录 buggy commit SHA
3. 创建 GitHub Issue 描述问题
4. 修复 bug 并 commit，记录 patch diff
5. 在 `swe_task.json` 中添加新的 task 实例
6. 用 agent 跑一遍验证
