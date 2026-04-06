from google import genai
from google.genai import types

from config import settings
from tools import AVAILABLE_TOOLS


class GeminiService:
    EVALUATOR_CONTROL_PHRASES = {
        "start",
        "start viva",
        "start evaluation",
        "begin",
        "begin viva",
        "begin evaluation",
        "next",
        "next question",
        "ask next question",
        "continue",
        "continue viva",
        "continue evaluation",
        "go on",
        "proceed",
        "what",
        "what?",
        "ok",
        "okay",
        "yes",
    }

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
        self.model = settings.gemini_model

    def _normalize_text(self, text):
        return " ".join((text or "").strip().lower().split())

    def _is_evaluator_control_message(self, text):
        return self._normalize_text(text) in self.EVALUATOR_CONTROL_PHRASES

    def _is_meaningful_evaluator_answer(self, text):
        normalized = self._normalize_text(text)
        if not normalized:
            return False
        return not self._is_evaluator_control_message(normalized)

    def _filter_evaluator_history(self, history):
        filtered = []
        for message in history or []:
            if message.get("role") == "user" and not self._is_meaningful_evaluator_answer(message.get("content", "")):
                continue
            filtered.append(message)
        return filtered

    def _count_evaluator_answers(self, history):
        user_turns = [
            msg for msg in history
            if msg.get("role") == "user" and self._is_meaningful_evaluator_answer(msg.get("content", ""))
        ]
        return max(0, len(user_turns))

    def _prepare_evaluator_prompt(self, user_text, history):
        answered = self._count_evaluator_answers(history)
        if not self._is_evaluator_control_message(user_text):
            return user_text
        if answered <= 0:
            return "Please start the viva by asking question 1 only."
        if answered >= 5:
            return "The viva is already complete. Provide the final score and concise feedback only."
        return "Please ask the next viva question only. Do not count this as a student answer."

    def build_system_prompt(self, mode, experiment, history):
        title = experiment.title
        objective = experiment.objective
        steps = experiment.steps or []

        if mode == "assistant":
            return (
                "You are Voice Lab Assistant, a concise and supportive lab guide.\n"
                f"Current experiment slug: {experiment.slug}\n"
                f"Experiment title: {title}\n"
                f"Experiment objective: {objective}\n"
                f"Allowed experiment steps: {steps}\n\n"
                "Behavior rules:\n"
                "1. Prioritize the experiment objective, steps, and prior chat context.\n"
                "2. If the student asks about a specific step, stay grounded in the listed steps.\n"
                "3. If the student shares code for validation, use the available tools when helpful.\n"
                "4. If something is not supported by experiment data or tool output, say that clearly instead of guessing.\n"
                "5. Keep replies short, practical, and easy to follow."
            )

        answered = self._count_evaluator_answers(history)
        remaining = max(0, 5 - answered)
        return (
            "You are Voice Lab Evaluator, a fair and structured lab examiner.\n"
            f"Current experiment slug: {experiment.slug}\n"
            f"Experiment title: {title}\n"
            f"Experiment objective: {objective}\n"
            f"Experiment steps: {steps}\n"
            f"Student answers already received in this session: {answered}\n"
            f"Questions remaining before the final score: {remaining}\n\n"
            "Behavior rules:\n"
            "1. Generate exactly five viva questions yourself based only on the experiment objective, steps, and the student's answers.\n"
            "2. Ask exactly one question at a time.\n"
            "3. After each student answer, briefly analyze that answer in one or two sentences.\n"
            "4. If fewer than five answers have been received, include the next question in the same reply.\n"
            "5. After the fifth answer, provide a final score out of 10 and concise feedback covering strengths and weaknesses.\n"
            "6. Keep the questions relevant to the experiment and vary them across concept, logic, implementation, edge cases, and improvement ideas.\n"
            "7. Do not mention any rubric and do not require predefined questions.\n"
            "8. Treat the current user message as the newest turn when deciding whether to ask the next question or give the final score.\n"
            "9. If the conversation is just starting and the current user message is only asking to begin the viva, ask question 1 without analysis.\n"
            "10. Keep the response concise."
        )

    def build_history(self, history):
        gemini_history = []
        for message in history:
            role = "model" if message.get("role") == "assistant" else "user"
            gemini_history.append(
                {
                    "role": role,
                    "parts": [{"text": message.get("content", "")}],
                }
            )
        return gemini_history

    async def get_response(self, user_text, mode, experiment, history=None):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file before using chat.")
        if self.client is None:
            self.client = genai.Client(api_key=settings.gemini_api_key)
        history = history or []
        if mode == "evaluator":
            history = self._filter_evaluator_history(history)
            user_text = self._prepare_evaluator_prompt(user_text, history)
        system_prompt = self.build_system_prompt(mode, experiment, history)
        tools = list(AVAILABLE_TOOLS.values())
        chat = self.client.aio.chats.create(
            model=self.model,
            history=self.build_history(history),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=tools,
                max_output_tokens=800,
            ),
        )
        response = await chat.send_message(user_text)
        return (response.text or "").strip()
