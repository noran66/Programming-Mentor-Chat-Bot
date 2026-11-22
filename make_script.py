import warnings; warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient
from app import app
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
c=TestClient(app); sid=""
bad="def find_max(numbers):\n    largest = 0\n    for number in numbers:\n        if number > largest: largest = number\n    return largest"
good=bad.replace("largest = 0","largest = numbers[0]")
def chat(m,code=bad,mode=""):
    global sid; r=c.post("/api/chat",json={"session":sid,"message":m,"code":code,"mode":mode}).json(); sid=r["session"]; return r
def run(code,which="all"):
    global sid; r=c.post("/api/run",json={"session":sid,"code":code,"which":which}).json(); sid=r["session"]; return r["coach"]
g=c.get("/api/greeting").json(); h1=chat("I don't know how to start."); rv=chat("Review my code"); f=run(bad); h2=chat("Get a hint",mode="hint"); ok=run(good)
vague=chat("it doesn't work"); oos=chat("What is the weather in Cairo?"); sol=chat("Show complete solution",good,"solution")
why=lambda r:"What I looked at: %s\nWhy I said this: %s\nWhat I am not sure about: Nothing about the evidence above. %s"%(r["evidence"],r["reason"],r["confidence"]["why"])
conf=lambda r:"  [%s – %s]"%(r["confidence"]["label"],r["confidence"]["why"])
S=ParagraphStyle("s",fontName="Helvetica",fontSize=6.6,leading=7.8);B=ParagraphStyle("b",parent=S,fontName="Helvetica-Bold");H=ParagraphStyle("h",fontName="Helvetica-Bold",fontSize=11,leading=13)
p=lambda t,st=S:Paragraph(t.replace("&","&amp;").replace("<","&lt;").replace("\n","<br/>"),st)
rows=[("0:00","Intro (voice-over, landing page on screen): team CodeBuddy, project CodeBuddy – AI coding coach, target users: programming learners (novice AI users, screen-reader users, contest practice), HAI principle: Explainability.","(none)","(none)"),
("0:20","Greeting: click 'Start with a recommended problem', then click the floating chat icon on the right edge. The chat opens with the first message (what it can and cannot do).","(click chat icon)",g["message"]+conf(g)),
("0:50","Main task 1: stuck at the start. Hint 1 appears with its label.","I don't know how to start.",h1["message"]+conf(h1)),
("1:10","Main task 2: code with 'largest = 0' is in the editor. Press mode button 'Review my code'.","Review my code",rv["message"]+conf(rv)),
("1:30","Main task 3: press Run. Line 2 is highlighted and the output area lists each test.","Run my code (Run button)",f["message"]+conf(f)),
("1:50","Main task 4: press 'Get a hint', then change line 2 to 'largest = numbers[0]'.","Get a hint",h2["message"]+conf(h2)),
("2:15","Main task 5: press Run on the fixed code. Task finished.","Run my code (Run button)",ok["message"]+conf(ok)),
("2:35","PRINCIPLE (Explainability): scroll to the failed-test message and press 'Why this?'. Say: 'This is Explainability: what it looked at, why, how sure.' Point at the label change Possible issue -> Confirmed.","(press 'Why this?' on the failed-test message)",why(f)),
("3:15","Problem case 1: unclear request. Chatbot asks a clarifying question.","it doesn't work",vague["message"]+conf(vague)),
("3:35","Problem case 2: out-of-scope request. Chatbot gives the fallback.","What is the weather in Cairo?",oos["message"]+conf(oos)),
("3:55","User control: complete solution is gated (then press 'No, one more hint').","Show complete solution",sol["message"]+conf(sol)),
("4:15","Closing (voice-over): works now = one problem, hints with reasons, real Python test runs, confidence labels, 'Why this?', Progress page, safe fallbacks. Planned = LLM model, Judge0 for C++/Java, 30-problem bank, saved history, Arabic mode.","(none)","(none)")]
data=[[p("Time",B),p("What is shown",B),p("Exact user message",B),p("Exact chatbot reply",B)]]+[[p(a),p(b),p(x),p(d)] for a,b,x,d in rows]
t=Table(data,colWidths=[28,250,100,430],repeatRows=1)
t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.4,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dbe5f7")),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
SimpleDocTemplate("CodeBuddy_W6-7_Demo_Script.pdf",pagesize=landscape(A4),leftMargin=22,rightMargin=22,topMargin=20,bottomMargin=18,title="CodeBuddy W6-7 Demo Script").build(
 [Paragraph("CodeBuddy – Demo Script (Weeks 6-7) – about 4:30 – Principle: Explainability",H),Spacer(1,4),t,Spacer(1,3),
  p("Replies are the real outputs of the backend (python make_script.py rebuilds this file). Synthetic data only; no keys or personal data on screen. Browser zoom 125% so text is readable.")])
