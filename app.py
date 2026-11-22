"""CodeBuddy backend (FastAPI). Every reply = message + reason + evidence + confidence.
Grounded on a problem bank, a hint ladder and REAL test execution (Python). No API key. Synthetic data only."""
import json, re, subprocess, sys, tempfile, os, uuid, time
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="CodeBuddy")
HERE = os.path.dirname(os.path.abspath(__file__))

P = {
 "id": "P01", "title": "Maximum of a List", "level": "Easy",
 "why": "Recommended because it practices loops and edge cases",
 "statement": "Given a list of integers, return the largest value.",
 "input": "A list of integers numbers", "output": "The largest integer", "constraints": "1 ≤ n ≤ 1000",
 "examples": [([3, 7, 2, 5], 7), ([-5, -2, -9], -2)],
 "tests": [([3, 7, 2, 5], 7), ([-5, -2, -9], -2), ([4], 4), ([0, 0], 0), ([-1], -1)],
 "hints": [  # (message, simpler, reason, evidence, label, why)
  ("What do you need to keep track of while you look at the numbers? Which value could be your starting maximum?",
   "Imagine one box called 'best'. What number should you put in the box before you start?",
   "Every solution needs a current best value, and choosing it wrongly is a common source of bugs.",
   "Problem statement: 'return the largest value'", "Confirmed", "this is a general rule for this problem type"),
  ("Try starting with the first number in the list instead of a fixed number. Then compare each next number with it.",
   "Put the first number of the list in the box. Do not use 0, because the numbers can be negative.",
   "Your start value must be a number that really exists in the list.",
   "Example 2: [-5, -2, -9] has only negative numbers", "Confirmed", "follows from the examples"),
  ("Loop over the list. When a number is bigger than your current best, update the best.",
   "Look at each number. If it is bigger than the box, replace the box.",
   "This is the standard single-pass scan; it checks every number once.",
   "Hint ladder level 3 of P01", "Confirmed", "taken from the problem's hint ladder"),
  ("Pseudocode: best = first item; for each item: if item > best, best = item; return best.",
   "Steps: take the first number. Check the rest one by one. Keep the biggest. Give it back.",
   "This is the last hint before the full solution: it names the steps but not the final code.",
   "Hint ladder level 4 of P01", "Confirmed", "taken from the problem's hint ladder")],
 "analysis": ("Input: a list of integers called numbers. Output: one integer, the largest in the list. "
              "Edge cases to think about: a list with one number, and a list where every number is negative (see Example 2)."),
 "concept": ("A 'running best' (also called a linear scan): you keep one variable with the best value so far "
             "and update it while you read each item once. It takes one pass, so the time grows with n."),
 "solution": {
  "python": "def find_max(numbers):\n    largest = numbers[0]\n    for number in numbers:\n        if number > largest:\n            largest = number\n    return largest",
  "cpp": "int find_max(vector<int> numbers) {\n    int largest = numbers[0];\n    for (int number : numbers)\n        if (number > largest) largest = number;\n    return largest;\n}",
  "java": "public static int findMax(int[] numbers) {\n    int largest = numbers[0];\n    for (int number : numbers)\n        if (number > largest) largest = number;\n    return largest;\n}"},
}
SESSIONS = {}
BANNED = re.compile(r"\b(os\.system|subprocess|socket|shutil|__import__|eval\(|exec\(|open\(|import os|import sys)")
START0 = re.compile(r"^\s*(?:int\s+|long\s+|var\s+)?(largest|max|maximum|best|biggest|result|ans|answer|mx)\s*=\s*0\s*;?\s*$")

class Req(BaseModel):
    session: str = ""
    message: str = ""
    code: str = ""
    language: str = "python"
    mode: str = ""
    short: bool = False

class Run(BaseModel):
    session: str = ""
    code: str = ""
    language: str = "python"
    which: str = "all"

class Fb(BaseModel):
    session: str = ""
    clear: bool = True

def S(sid):
    return SESSIONS.setdefault(sid, {"hint": 0, "confirm": False, "attempts": [], "last": "", "disagree": 0,
                                     "fb": [], "last_run": None, "created": time.time()})

def reply(msg, reason, evidence, label, why, options=None, **extra):
    d = {"message": msg, "reason": reason, "evidence": evidence, "confidence": {"label": label, "why": why},
         "options": options if options is not None else ["Get a hint", "Review my code", "Simpler explanation"]}
    d.update(extra); return d

def find_line(code):
    for i, l in enumerate(code.splitlines(), 1):
        if START0.match(l): return i, l.strip()
    return None, None

def complexity(code):
    lines = [l for l in code.splitlines() if l.strip()]
    loops = [l for l in lines if re.match(r"\s*(for|while)\b", l)]
    ind = [len(l) - len(l.lstrip()) for l in loops]
    if re.search(r"\.sort\(|sorted\(|sort\(", code):
        return "O(n log n)", "O(n)", "I saw a sort call, and sorting usually takes n log n steps"
    if len(loops) >= 2 and len(set(ind)) > 1:
        return "O(n^2)", "O(1)", "I saw a loop inside another loop, so the steps multiply"
    if len(loops) >= 1:
        return "O(n)", "O(1)", "I saw one loop over the list and no new list, so time grows with n and extra memory stays constant"
    return "unknown", "unknown", "I could not find a loop to base an estimate on"

def execute(code):
    tests = P["tests"]
    h = code + "\nimport json\nR=[]\nfor a,e in %r:\n  try:\n    r=find_max(list(a))\n  except Exception as ex:\n    r='ERROR: '+type(ex).__name__\n  R.append([a,e,r])\nprint(json.dumps(R))\n" % (tests,)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(h); path = f.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=3)
        if p.returncode:
            return None, (p.stderr.strip().splitlines() or ["error"])[-1]
        return json.loads(p.stdout), None
    except subprocess.TimeoutExpired:
        return None, "Time limit exceeded (3 seconds)"
    finally:
        os.unlink(path)

def do_run(s, code, lang, which):
    out = {"results": [], "passed": 0, "total": 0, "status": "", "error": None}
    if lang != "python":
        out["status"] = "Status: Run is not enabled for this language in the demo. Python only."
        return out, reply("I cannot run C++ or Java in this demo, so I cannot confirm the result of your code. I can still review it by reading it.",
                          "Real test runs are only built for Python right now.", "Demo limit: Python runner only", "Confirmed",
                          "this is a known limit of the demo", options=["Review my code", "Get a hint"])
    if BANNED.search(code) or len(code) > 5000:
        out["status"] = "Status: Not run. The code uses system, file or network commands, or it is too long."
        return out, reply("I did not run your code because it uses system, file or network commands (or it is too long). Send code that only solves the problem.",
                          "Running such code is not safe.", "Banned call found by a text check", "Confirmed", "found by a text check", options=["Get a hint"])
    res, err = execute(code)
    if err:
        out.update(error=err, status="Status: The code could not finish. " + err)
        s["attempts"].append({"t": time.time(), "passed": 0, "total": len(P["tests"]), "hints": s["hint"], "issue": "runtime error or timeout", "detail": err})
        return out, reply("Your code could not finish: " + err + ". Check the line named in the error message.",
                          "The test harness stopped with this message.", err, "Confirmed", "real error from running your code", options=["Get a hint", "Simpler explanation"])
    rows = [{"input": a, "expected": e, "actual": g, "ok": e == g} for a, e, g in res]
    if which == "examples": rows = rows[:len(P["examples"])]
    passed = sum(r["ok"] for r in rows); total = len(rows)
    out.update(results=rows, passed=passed, total=total,
               status=f"Status: {passed} of {total} tests passed." if passed == total else f"Status: {total - passed} of {total} tests failed.")
    bad = [r for r in rows if not r["ok"]]
    n, line = find_line(code)
    t, sp, how = complexity(code)
    s["last_run"] = {"time": t, "space": sp, "how": how, "passed": passed, "total": total}
    if which == "all":
        s["attempts"].append({"t": time.time(), "passed": passed, "total": total, "hints": s["hint"],
                              "issue": ("start value too high (line %d)" % n if (bad and n) else ("wrong output" if bad else "none")),
                              "detail": (f"input={bad[0]['input']}, expected={bad[0]['expected']}, actual={bad[0]['actual']}" if bad else "all tests passed")})
    if bad:
        b = bad[0]
        ev = f"Failed test: input={b['input']}, expected={b['expected']}, actual={b['actual']}" + (f"; your line {n}: {line}" if n else "")
        return out, reply(f"Test failed for input {b['input']}: expected {b['expected']} but got {b['actual']}. Look at the line where you set your starting value." if n else
                          f"Test failed for input {b['input']}: expected {b['expected']} but got {b['actual']}. Trace your loop with this input step by step.",
                          "Your start value 0 is bigger than every number in a list of negatives." if n else "The result differs from the expected output.",
                          ev, "Confirmed", "a real test failed", options=["Get a hint", "Simpler explanation", "I disagree"],
                          **({"highlight_line": n} if n else {}))
    return out, reply(f"All {total} tests passed. Time complexity looks like {t} and space {sp} (this is an estimate).",
                      "Every test returned the expected output. " + how[0].upper() + how[1:] + ".",
                      f"Test results: {passed}/{total} passed", "Confirmed", "backed by real tests; the complexity is an estimate, not verified",
                      options=["How did I get this?", "Show complete solution", "Next problem"])

def unsafe(t):
    return re.search(r"hack|malware|virus|steal|keylogger|ransomware|cheat (in|on) (the |my )?exam", t)

def chat(r, s):
    t = r.message.lower().strip(); code = r.code; lang = r.language; mode = r.mode
    if s["confirm"]:
        s["confirm"] = False
        if re.search(r"\b(yes|show|ok|sure)\b", t) and not re.search(r"\bno\b", t):
            s["last"] = "solution"
            return reply("Here is the full solution:\n" + P["solution"].get(lang, P["solution"]["python"]),
                         "You confirmed that you want it, so I am showing it.", "Reference solution of P01 (tested)", "Confirmed",
                         "taken from the problem bank and tested", options=["Explain it line by line", "Next problem"])
        mode = "hint"
    if unsafe(t):
        return reply("I can't help with that, because it could harm people. I can help you practice a safe problem instead.",
                     "This request is outside what a learning coach should do.", "Your request", "Confirmed", "it matches my safety rules", options=["Get a hint"])
    if not mode:
        if re.search(r"complete solution|full solution|write (it|the code) for me|give me the (answer|code)", t): mode = "solution"
        elif re.search(r"how did i get|how do you know", t): mode = "how"
        elif re.search(r"line by line", t): mode = "line"
        elif re.search(r"next problem|another problem", t): mode = "next"
        elif re.search(r"simpler|simple words|don'?t understand|too hard", t): mode = "simpler"
        elif re.search(r"disagree|you are wrong|that's wrong", t): mode = "disagree"
        elif re.search(r"don'?t know how to start|how to start|where (do|to) i start|hint|stuck", t): mode = "hint"
        elif re.search(r"\b(run|test)\b", t) and code.strip(): mode = "run"
        elif re.search(r"review|check my code|look at my code", t): mode = "review"
        elif re.search(r"analy[sz]e|understand the problem|what does the problem", t): mode = "analyze"
        elif re.search(r"explain|concept|what is a", t): mode = "concept"
        elif re.search(r"independent|on my own|by myself", t): mode = "try"
    if mode == "try":
        return reply("Okay, take your time. I will wait. Ask me when you want a hint, a review or an explanation.",
                     "You chose to work independently, so I will not interrupt.", "Your help mode: Try independently", "Confirmed", "you chose this",
                     options=["Get a hint", "Analyze the problem"])
    if mode == "hint":
        i = min(s["hint"], 3); s["hint"] = min(s["hint"] + 1, 4); s["last"] = ("hint", i)
        m, sm, why, ev, lab, lw = P["hints"][i]
        return reply(m, why, ev, lab, lw, hint_level=i + 1, options=["Get a hint", "Simpler explanation", "Review my code"])
    if mode == "analyze":
        s["last"] = "analyze"
        return reply(P["analysis"], "Reading the statement and examples first prevents most wrong starts.",
                     "Problem statement, constraints and Example 2", "Confirmed", "taken directly from the problem text", options=["Get a hint", "Explain a concept"])
    if mode == "concept":
        s["last"] = "concept"
        why = "You asked for a concept." if not s["attempts"] else "I picked this topic because your last attempt had a problem with the starting value."
        return reply(P["concept"], why, "Topic note: running best / linear scan", "Confirmed", "taken from the team-written topic notes",
                     options=["Simpler explanation", "Get a hint"])
    if mode == "solution":
        s["confirm"] = True
        return reply("You asked for the complete solution. Are you sure? You can try one more hint first. Reply 'Yes, show it' to see it.",
                     "Showing it now may reduce your learning, so you decide.", "Your request", "Confirmed", "my rule: ask before revealing",
                     options=["Yes, show it", "No, one more hint"])
    if mode == "simpler":
        l = s["last"]
        if isinstance(l, tuple): txt = P["hints"][l[1]][1]
        elif l == "analyze": txt = "The input is a list of numbers. The answer is one number: the biggest one. Be careful with lists that have only negative numbers."
        elif l == "concept": txt = "Keep one box called 'best'. Look at the numbers one by one. If a number is bigger than the box, put it in the box."
        else: txt = "Keep one box called 'best'. Put the first number in it. Check the other numbers one by one. If one is bigger, replace the box."
        return reply("In simple words: " + txt, "You asked for simpler wording, so I removed technical terms.", "My previous answer", "Confirmed", "same idea, shorter words",
                     options=["Get a hint", "Review my code"])
    if mode == "disagree":
        s["disagree"] += 1
        return reply("Thank you for challenging me. Press Run: a real test result is stronger than my opinion. Tell me what you expect and I will compare.",
                     "My 'Possible issue' labels can be wrong; tests settle it. Your disagreement is saved.", "Your feedback (saved for later)", "Not sure",
                     "only a test can decide", options=["Review my code"])
    if mode == "how":
        lr = s["last_run"]
        if not lr: return reply("Run your code first, then I can show how I got the result.", "There is no result to explain yet.", "No test run yet", "Not sure", "nothing has run", options=["Review my code"])
        return reply(f"Tests: {lr['passed']} of {lr['total']} passed in your last run. Time {lr['time']}, space {lr['space']}: {lr['how']}. This complexity is an estimate from reading your code; I did not measure it.",
                     "Showing the steps lets you check my result yourself.", "Your last test run and your code", "Confirmed", "tests are real; complexity is only an estimate", options=["Show complete solution"])
    if mode == "line":
        return reply("Line 1: start with the first number as the best. Line 2: look at every number. Line 3: if it is bigger than the best, update it. Last line: return the best.",
                     "You asked for a walkthrough of the solution.", "Reference solution of P01", "Confirmed", "taken from the problem bank", options=["Next problem"])
    if mode == "next":
        return reply("In this demo there is one problem. The full bank (30 problems) and the recommendation of the next one are planned work.",
                     "I only recommend problems that exist in my bank.", "Problem bank size: 1", "Confirmed", "this is a known limit of the demo", options=["Get a hint"])
    if mode == "run":
        if not code.strip(): return reply("There is no code to run yet. Write your code in the editor first.", "Nothing to test.", "Empty editor", "Confirmed", "the editor is empty", options=["Get a hint"])
        out, rep = do_run(s, code, lang, "all"); rep["run"] = out; return rep
    if mode == "review":
        if not code.strip():
            return reply("Paste or write some code in the editor first, then ask me again.", "I cannot review an empty editor.", "Empty editor", "Confirmed", "the editor is empty", options=["Get a hint"])
        n, line = find_line(code)
        if n:
            return reply("Possible issue: what if all the numbers are negative? Try [-5, -2, -9].",
                         f"Your line {n} sets the start value to 0, so a list of negatives would return 0.", f"Your line {n}: {line}",
                         "Possible issue", "Not sure: I have not run your code yet", highlight_line=n, options=["Run my code", "Get a hint", "I disagree"])
        return reply("I do not see an obvious issue by reading, but I have not run your code. Press Run to test it.",
                     "Reading cannot prove that code is correct.", "Your code (text only)", "Not sure", "no test has run yet", options=["Run my code"])
    if len(t.split()) <= 4 or re.search(r"doesn'?t work|not working|help me|fix it", t):
        return reply("I need a bit more to help. Please tell me the input you used, the output you got and the output you expected, or press Run so I can see a test result.",
                     "Without outputs I would be guessing.", "Your message has no code or outputs", "Not sure", "information is missing", options=["Review my code", "Get a hint"])
    return reply("That is outside what I can help with. I coach problem solving for this practice problem. I can give a hint, review your code, analyze the problem or explain a concept.",
                 "My data (problem bank, hints, tests) does not cover this topic.", "Your request", "Confirmed", "it is not in my scope", options=["Get a hint", "Analyze the problem"])

@app.get("/api/problem")
def problem():
    return {k: P[k] for k in ("id", "title", "level", "why", "statement", "input", "output", "constraints")} | \
           {"examples": [{"input": a, "output": e} for a, e in P["examples"]]}

@app.get("/api/greeting")
def greeting():
    return reply("Hi, I'm CodeBuddy. I can give hints one at a time, review your code, explain concepts and analyze the problem. "
                 "I cannot run your code unless you press Run, my complexity estimates may be uncertain, and I can make mistakes. "
                 "Tap 'Why this?' on any answer to see my reason.",
                 "I say this first so you know what to expect.", "About CodeBuddy: I use your code, test results and hint history.", "Confirmed",
                 "this is how the system is built", options=[])

@app.post("/api/chat")
def chat_ep(r: Req):
    sid = r.session or str(uuid.uuid4()); s = S(sid)
    out = chat(r, s)
    if r.short: out["message"] = re.split(r"(?<=[.?!])\s", out["message"])[0] if "\n" not in out["message"] else out["message"]
    out["session"] = sid; return out

@app.post("/api/run")
def run_ep(r: Run):
    sid = r.session or str(uuid.uuid4()); s = S(sid)
    out, rep = do_run(s, r.code, r.language, r.which)
    return {"session": sid, "run": out, "coach": rep}

@app.post("/api/feedback")
def fb_ep(f: Fb):
    S(f.session)["fb"].append(f.clear); return {"ok": True}

@app.get("/api/progress")
def progress(session: str = ""):
    s = S(session); a = s["attempts"]
    items = []
    if a:
        items.append({"title": "Attempts and tests", "value": f"{len(a)} attempt(s). Best result: {max(x['passed'] for x in a)} of {a[0]['total']} tests.",
                      "how": "Counted from your test runs: " + "; ".join(f"attempt {i+1}: {x['passed']}/{x['total']}" for i, x in enumerate(a))})
        errs = [(i + 1, x["issue"]) for i, x in enumerate(a) if x["issue"] != "none"]
        if errs:
            items.append({"title": "Practice area", "value": "Starting values and negative numbers" if any("start" in e for _, e in errs) else "Checking outputs by tracing",
                          "how": "Based on attempts " + ", ".join(str(i) for i, _ in errs) + ": " + "; ".join(f"attempt {i}: {e}" for i, e in errs)})
    items.append({"title": "Help used", "value": f"{s['hint']} hint(s) requested. This is a learning signal, not a score.",
                  "how": "Counted from the hint buttons you pressed in this session."})
    if s["fb"]:
        items.append({"title": "Explanation feedback", "value": f"{sum(s['fb'])} of {len(s['fb'])} explanations rated clear. {s['disagree']} disagreement(s).",
                      "how": "Counted from your 'Was this explanation clear?' and 'I disagree' presses."})
    if a and a[-1]["issue"] == "none":
        items.append({"title": "Next step", "value": "Try a problem with a harder edge case (planned in the full problem bank).",
                      "how": "Your last attempt passed all tests, so a harder problem is the next step. I explain it because I only recommend with evidence."})
    return {"empty": not a and not s["hint"], "items": items}

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))
