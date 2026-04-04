import subprocess
import sys
import ast
import json
import os

def run_python_code(code: str):
    """Executes python code and returns the output or error."""
    try:
        # We run the code in a separate process for basic safety
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return f"Success! Output:\n{result.stdout}"
        else:
            return f"Runtime Error:\n{result.stderr}"
    except Exception as e:
        return f"Failed to execute: {str(e)}"

def check_syntax(code: str):
    """Checks Python code for syntax errors without executing it."""
    try:
        ast.parse(code)
        return "Syntax is correct."
    except SyntaxError as e:
        return f"Syntax Error on line {e.lineno}: {e.msg}\n{e.text}"
    except Exception as e:
        return f"Error checking syntax: {str(e)}"

def analyze_time_complexity(algorithm_name: str):
    """Returns standard big O time complexity for a given algorithm."""
    complexities = {
        "bubble sort": "Time: O(n^2), Space: O(1)",
        "merge sort": "Time: O(n log n), Space: O(n)",
        "quick sort": "Time: O(n log n) avg / O(n^2) worst, Space: O(log n)",
        "binary search": "Time: O(log n), Space: O(1)",
        "linear search": "Time: O(n), Space: O(1)",
        "linked list append": "Time: O(n) without tail pointer, O(1) with tail pointer. Space: O(1)",
        "linked list traversal": "Time: O(n), Space: O(1)",
        "pandas mean": "Time: O(n), Space: O(1)",
        "pandas boolean indexing": "Time: O(n), Space: O(n) for the output mask",
        "api request": "Time: O(1) local + Network Latency, Space: O(1)"
    }
    alg = algorithm_name.lower().strip()
    return complexities.get(alg, f"Complexity information not available for '{algorithm_name}'. Please verify the name.")

def generate_test_cases(topic: str):
    """Returns deterministic standard test cases for a given topic."""
    test_cases = {
        "sorting": "[1, 5, 2, 8, 3] -> [1, 2, 3, 5, 8]\nNegative values: [9, -8, 7, -6] -> [-8, -6, 7, 9]\nEmpty: [] -> []\nSingle: [1] -> [1]",
        "binary search": "arr=[1, 3, 5, 7, 9], target=5 -> index 2\narr=[1, 3, 5, 7, 9], target=4 -> not found (-1)\narr=[], target=1 -> not found (-1)",
        "linked list": "Append(1), Append(2), Append(3) -> Lists prints: 1 -> 2 -> 3\nAppend to empty list -> Head becomes the new node.",
        "api integration": "Valid URL -> Status 200 OK, JSON Parsed Successfully\nInvalid URL (404) -> requests.exceptions.HTTPError\nTimeout Exceeded -> requests.exceptions.Timeout",
        "data analysis": "df['Score'].mean() where Score=[80, 90, 100] -> 90.0\nBoolean mask [True, False, True] -> Returns rows 0 and 2."
    }
    top = topic.lower().strip()
    return test_cases.get(top, f"No predefined test cases for '{topic}'. Valid options: sorting, binary search, linked list, api integration, data analysis.")

def get_experiment_hint(step_number: int, exp_id: str):
    """Pulls a specific hint based on the experiment ID and step number."""
    path = os.path.join("..", "experiments", f"{exp_id}.json")
    try:
        if not os.path.exists(path):
            return f"Experiment {exp_id} not found."
        with open(path, "r") as f:
            data = json.load(f)
            steps = data.get("steps", [])
            if 0 < step_number <= len(steps):
                return f"Hint for Step {step_number}: {steps[step_number-1]}"
            else:
                return f"Invalid step number: {step_number}. Total steps: {len(steps)}."
    except Exception as e:
        return f"Error loading hints: {str(e)}"

# A dictionary of tools available to the LLM
AVAILABLE_TOOLS = {
    "run_python_code": run_python_code,
    "check_syntax": check_syntax,
    "analyze_time_complexity": analyze_time_complexity,
    "generate_test_cases": generate_test_cases,
    "get_experiment_hint": get_experiment_hint
}

# This describes the tools to the LLM so it knows how to use them
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_python_code",
            "description": "Runs Python code and returns stdout or stderr. Use only when the user provides code or asks to verify actual runtime behavior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The full python code to execute."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_syntax",
            "description": "Checks Python code for syntax errors without running it. Prefer this when the user asks about syntax, formatting, or likely parse errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The python code to check."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_time_complexity",
            "description": "Returns deterministic Big O time and space complexity for a known algorithm. Use for complexity questions instead of answering from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "algorithm_name": {"type": "string", "description": "Name of the algorithm (e.g., 'merge sort')."}
                },
                "required": ["algorithm_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_test_cases",
            "description": "Returns deterministic standard test cases for a supported topic. Use when the user asks for examples, validations, or edge cases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to generate test cases for (e.g., 'sorting')."}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_experiment_hint",
            "description": "Returns the exact experiment hint for a specific step. Use this for step-specific lab questions instead of inventing instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer", "description": "The step number the student is on (1-indexed)."},
                    "exp_id": {"type": "string", "description": "The current experiment ID (e.g., 'exp_sorting')."}
                },
                "required": ["step_number", "exp_id"]
            }
        }
    }
]
