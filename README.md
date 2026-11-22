# CodeBuddy – working demo (HAI principle: Explainability)

Web app + FastAPI backend. Landing page, workspace (problem panel, code editor, Run / Test with examples, output),
Progress, About, Accessibility settings, and a floating chat icon on the right edge that opens the CodeBuddy chat.

Every reply has: message, reason ("Why this?": what I looked at / why / what I am not sure about), evidence and a
confidence label in words (Confirmed / Possible issue / Not sure). Hints come one at a time; the full solution needs confirmation.
Python code is run on real tests in a subprocess (3 s limit). C++/Java: review only (Run is not enabled, and the app says so).
No API key needed. Synthetic data only. Sessions are kept in memory.

## Run
    pip install -r requirements.txt
    uvicorn app:app --reload
Open http://127.0.0.1:8000

## Files
- app.py: problem bank (P01), hint ladder, modes, test runner, complexity estimate, progress, safety / out-of-scope handling
- static/index.html: the interface (keyboard use, ARIA labels, live regions, dark mode, high contrast, text size, short replies)
- make_script.py: rebuilds the demo script from real backend replies
- Planned: LLM model for free-text coaching, Judge0/Docker for C++/Java, 30-problem bank, saved history.

