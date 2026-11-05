"""CodeBuddy backend - Week 5: first model call from our own backend.

Run:  pip install -r requirements.txt
      export ANTHROPIC_API_KEY=your_key      (Windows: set ANTHROPIC_API_KEY=your_key)
      uvicorn main:app --reload
Test: open http://127.0.0.1:8000/docs and try POST /chat
"""
import json
import os
import re

import anthropic
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CodeBuddy")
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
MODEL = os.getenv("CODEBUDDY_MODEL", "claude-sonnet-5-5")

# ---- Knowledge source: team-written problem bank (one sample problem) ----
PROBLEMS = {
    "max-list": {
        "statement": "Given a list of integers, return the largest value.",
        "constraints": "1 <= n <= 10^5, values between -10^9 and 10^9",
        "hints": [  # 4-level hint ladder, gentle question -> near solution
            "What do you need to keep track of while you look at the numbers?",
            "Which value could be your starting maximum before you see any number?",
            "Think about a list where every number is negative. Does your starting value still work?",
            "Start with the first element, then update it whenever you see a bigger one.",
        ],
        # The reference solution is NEVER sent to the model in hint mode.
    }
}

SYSTEM_PROMPT = """You are CodeBuddy, a problem-solving coach for programming learners.
Rules:
- Give ONE hint or question at a time. Never write the full solution or full code.
- Use only the hint level provided; never go beyond it.
- Use short, plain language.
- Explain WHY you say it and name the evidence (a code line, a test result, or a constraint).
- Mark confidence: "Confirmed" only if backed by a test result or a rule;
  "Possible issue" if likely but unverified; "Not sure" otherwise, with a reason.
- If you have not seen test output, you cannot use "Confirmed".
Return ONLY JSON with keys: message, reason, evidence, confidence, confidence_reason."""

FALLBACK = {
    "message": "I could not prepare a reliable answer this time. Please try again, "
               "or choose another option: Get a hint / Review my code / Explain a concept.",
    "reason": "The AI service did not return a valid answer.",
    "evidence": "none",
    "confidence": "Not sure",
    "confidence_reason": "No verified response was produced.",
    "fallback": True,
}

HANDOVER = {
    "message": "This is best handled by a real person. Please contact your instructor or TA, "
               "or check the official language documentation. [TEAM: add real contact/link]",
    "reason": "You asked for a person, or the topic is outside what I can coach.",
    "evidence": "user request",
    "confidence": "Confirmed",
    "confidence_reason": "Handover rule matched.",
    "handover": True,
}

HANDOVER_PATTERN = re.compile(r"(human|real person|teacher|instructor|\bta\b|مدرس|دكتور|معيد)", re.I)
CONFIDENCE = {"Confirmed", "Possible issue", "Not sure"}


class ChatIn(BaseModel):
    problem_id: str = "max-list"
    message: str
    code: str = ""
    language: str = "python"
    hint_level: int = 1          # 1..4, controlled by the app, not by the model
    test_output: str = ""        # real output from the sandbox, if any


def build_user_content(body: ChatIn, problem: dict) -> str:
    level = max(1, min(body.hint_level, 4))
    allowed_hints = problem["hints"][:level]  # enforce the ladder in code
    return (
        f"Problem: {problem['statement']}\nConstraints: {problem['constraints']}\n"
        f"Allowed hint ladder up to level {level}: {json.dumps(allowed_hints)}\n"
        f"Language: {body.language}\nStudent code:\n{body.code or '(none)'}\n"
        f"Test output: {body.test_output or '(not run yet)'}\n"
        f"Student message: {body.message}"
    )


def valid(data: dict, body: ChatIn) -> bool:
    keys = {"message", "reason", "evidence", "confidence", "confidence_reason"}
    if not keys.issubset(data) or data["confidence"] not in CONFIDENCE:
        return False
    if "```" in str(data["message"]):                      # safeguard: no code dumps
        return False
    if data["confidence"] == "Confirmed" and not body.test_output:  # safeguard: honest labels
        data["confidence"] = "Possible issue"
        data["confidence_reason"] = "No test result yet, so I cannot confirm this."
    return True


@app.post("/chat")
def chat(body: ChatIn):
    if HANDOVER_PATTERN.search(body.message):
        return HANDOVER
    problem = PROBLEMS.get(body.problem_id)
    if not problem:
        return {**FALLBACK, "message": "I could not find this problem. Please pick one from the list."}
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_content(body, problem)}],
            timeout=30,
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```json|```$", "", text).strip()
        data = json.loads(text)
        return data if valid(data, body) else FALLBACK
    except Exception as e:  # network error, timeout, bad JSON, ...
        print("model error:", e)
        return FALLBACK
