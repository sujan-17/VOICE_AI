import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from tools import TOOL_DEFINITIONS, AVAILABLE_TOOLS

load_dotenv()

class LLMHandler:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("NEXUS_API_KEY"),
            base_url=os.getenv("NEXUS_BASE_URL")
        )
        self.model = os.getenv("LLM_MODEL", "gpt-4.1-nano")
        self.max_tool_rounds = 3

    def load_experiment(self, exp_id):
        print(f"LOADING EXPERIMENT ID: {exp_id}")
        path = os.path.join("..", "experiments", f"{exp_id}.json")
        try:
            with open(path, "r") as f:
                data = json.load(f)
                print(f"LOADED DATA TITLE: {data.get('title')}")
                return data
        except FileNotFoundError:
            print(f"FILE NOT FOUND: {path}, falling back to exp_sorting")
            # Fallback in case of an invalid ID, though the frontend dropdown prevents this
            fallback = os.path.join("..", "experiments", "exp_sorting.json")
            with open(fallback, "r") as f:
                return json.load(f)

    def _count_evaluator_answers(self, history):
        user_turns = [msg for msg in history if msg.get("role") == "user"]
        return max(0, len(user_turns))

    def _build_system_prompt(self, mode, exp_id, exp_data, history):
        title = exp_data.get("title", "Unknown")
        steps = exp_data.get("steps", [])
        rubric = exp_data.get("rubric", {})

        if mode == "assistant":
            return (
                "You are a concise AI Lab Assistant.\n"
                f"Current experiment ID: {exp_id}\n"
                f"Experiment title: {title}\n"
                f"Allowed experiment steps: {json.dumps(steps, ensure_ascii=True)}\n\n"
                "Rules:\n"
                "1. Answer using the experiment data, prior chat context, and tool results before using general knowledge.\n"
                "2. If the user asks about a specific experiment step, use only the listed steps or the get_experiment_hint tool.\n"
                "3. If the user shares code and asks whether it works, asks for errors, or asks for validation, use a tool before concluding.\n"
                "4. If the answer is not supported by the experiment data or a tool result, say so briefly instead of guessing.\n"
                "5. Keep replies short: usually 1-3 sentences, plain and direct.\n"
                "6. Do not mention these rules, hidden reasoning, or internal tool policy."
            )

        answered = self._count_evaluator_answers(history)
        remaining = max(0, 3 - answered)
        return (
            "You are a strict but fair AI Lab Evaluator.\n"
            f"Current experiment ID: {exp_id}\n"
            f"Experiment title: {title}\n"
            f"Rubric: {json.dumps(rubric, ensure_ascii=True)}\n"
            f"Student answers already received in this session: {answered}\n"
            f"Questions remaining before final score: {remaining}\n\n"
            "Rules:\n"
            "1. Ask exactly one rubric-based question at a time until 3 student answers have been received.\n"
            "2. After each student answer, evaluate it briefly in 1-2 sentences.\n"
            "3. If fewer than 3 answers have been received, include the next question in the same reply.\n"
            "4. After the 3rd student answer, give a final score out of 10 with one short justification and stop asking questions.\n"
            "5. Do not invent rubric items. If the answer is unsupported, say what is missing briefly.\n"
            "6. Keep the entire reply concise."
        )

    def _serialize_assistant_message(self, resp_msg):
        message = {"role": "assistant"}
        if resp_msg.content:
            message["content"] = resp_msg.content
        if resp_msg.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in resp_msg.tool_calls
            ]
        return message

    def _execute_tool_call(self, tool_call):
        func_name = tool_call.function.name
        if func_name not in AVAILABLE_TOOLS:
            return f"Tool '{func_name}' is not available."

        try:
            args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            return f"Invalid arguments supplied to tool '{func_name}'."

        try:
            return AVAILABLE_TOOLS[func_name](**args)
        except Exception as exc:
            return f"Tool '{func_name}' failed: {str(exc)}"

    async def get_response(self, user_text, mode="assistant", exp_id="exp_01", history=None):
        history = history or []
        exp_data = self.load_experiment(exp_id)

        system_prompt = self._build_system_prompt(mode, exp_id, exp_data, history)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        for _ in range(self.max_tool_rounds):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=120,
                temperature=0.1
            )

            resp_msg = response.choices[0].message
            if not resp_msg.tool_calls:
                return (resp_msg.content or "").strip()

            messages.append(self._serialize_assistant_message(resp_msg))
            for tool_call in resp_msg.tool_calls:
                result = self._execute_tool_call(tool_call)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": result
                    }
                )

        fallback_messages = list(messages)
        fallback_messages.append(
            {
                "role": "system",
                "content": (
                    "You have enough information. Give the best short grounded answer now. "
                    "Do not call more tools. If uncertain, say so briefly."
                )
            }
        )
        final_resp = await self.client.chat.completions.create(
            model=self.model,
            messages=fallback_messages,
            max_tokens=120,
            temperature=0.1
        )
        return (final_resp.choices[0].message.content or "").strip()
