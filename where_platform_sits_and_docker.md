# 🏗️ Hamara Platform KAHAN Lagega? Aur Docker Kya Hai?

---

## ❓ Pehle Ye Sawaal Solve Karte Hain

### "Hamara platform client ki website me lagega ya extension hoga?"

**Dono nahi.** 🙅

Ek example se samjho:

---

## 🏢 CCTV Camera Analogy (Sabse Simple)

Socho tum ek **mall** ke owner ho. Mall me shops hain, customers aate hain, employees kaam karte hain.

Ab tum **security system** lagana chahte ho.

```
SAWAAL: CCTV camera KAHAN lagega?

❌ Kya CCTV camera dukaan ki deewar me ghus jayega?     → NAHI
❌ Kya CCTV ek browser extension hai?                    → NAHI
❌ Kya CCTV dukaan ki website me add hoga?               → NAHI

✅ CCTV ek ALAG SYSTEM hai
   → Apna camera hai
   → Apna recording box (DVR) hai
   → Apna monitor hai (jahan guard baithke dekhta hai)
   → Bas WIRE se connect hai dukaan ke andar
```

### **Hamara platform = CCTV system for AI**

```
❌ Client ki website me nahi ghusega
❌ Browser extension nahi hai
❌ Client ka code change nahi hoga (bahut kam)

✅ Ek ALAG SYSTEM hai jo:
   → Client ke AI agent se WIRE (API) se connect hai
   → Apna database hai (traces store karta hai)
   → Apna dashboard hai (monitor pe dikhata hai)
   → Apna alert system hai (galti mili toh notification)
```

---

## 📐 Diagram: Platform KAHAN Baithta Hai

### PEHLE (Bina Hamara Platform):

```
Customer ──→ Client ki Website ──→ AI Agent ──→ Database
                                      │
                                   (koi dekh   
                                    nahi raha)  
                                      │
                                   Galat refund?
                                   Kisi ko pata nahi ☠️
```

### BAAD ME (Hamara Platform Lagne Ke Baad):

```
Customer ──→ Client ki Website ──→ AI Agent ──→ Database
                                      │
                                      │ ← API wire (connection)
                                      │
                              ┌───────▼────────┐
                              │                │
                              │  HAMARA EARP   │  ← YE ALAG SERVER PE
                              │  PLATFORM      │     CHAL RAHA HAI
                              │                │
                              │  ┌──────────┐  │
                              │  │ Trace    │  │ ← Har step record
                              │  │ Guard    │  │ ← Galat kaam roko
                              │  │ Watchdog │  │ ← Data check karo
                              │  │ Eval     │  │ ← Version compare
                              │  │ Dashboard│  │ ← Sab dikhao
                              │  └──────────┘  │
                              │                │
                              └────────────────┘
                                    │
                               Galti mili?
                               🚨 ALERT! 
```

### Key Point:
> **Hamara platform ek ALAG computer/server pe chalta hai. Client ki website se sirf WIRE (API) se connect hota hai. Client ki website me kuch nahi badalte.**

---

## 🔌 Connection Kaise Hota Hai? (3 Tarike)

### Tarika 1: SDK / Library (Sabse Common)

Client apne AI agent ke code me hamari **choti si library** add karta hai (2-3 lines):

```python
# CLIENT KA EXISTING CODE (pehle se hai):
def handle_ticket(ticket):
    response = ai_agent.process(ticket)
    return response

# HAMARI LIBRARY ADD KARNE KE BAAD (sirf 3 lines extra):
from earp import trace, guard

def handle_ticket(ticket):
    with trace.record():                    # ← Line 1: Recording shuru
        decision = guard.check(ticket)       # ← Line 2: Guard check
        response = ai_agent.process(ticket)
    return response                          # Bas! Baaki sab automatic
```

**Client ke code me sirf 3 lines add hui.** Baaki sab hamara platform khud handle karta hai.

### Tarika 2: Middleware / Proxy (Zero Code Change)

Hamara platform AI agent ke AAGE baith jaata hai, jaise ek **tollbooth** road pe:

```
PEHLE:
Customer Request ──→ AI Agent ──→ Response

BAAD ME:
Customer Request ──→ EARP Proxy ──→ AI Agent ──→ EARP Proxy ──→ Response
                        │                            │
                     Record                       Check
                     Guard                        Watchdog
```

**Client ke code me KUCH NAHI badalte.** Bas request hammare through jaati hai.

### Tarika 3: Database Watcher (Sirf Watchdog ke liye)

Watchdog sirf client ke **database se read** karta hai — kuch likhta nahi:

```
Client ka Database ←─── READ ONLY connection ───→ Hamara Watchdog
                                                      │
                                                  "Duplicate refund mila!"
                                                  "Inventory mismatch!"
                                                      │
                                                  🚨 Alert
```

---

## 🏥 Real Example: Clinic Me Kaise Lagega?

### Step 1: Clinic ka existing system
```
Patient ──→ Clinic Website ──→ AI Chatbot ──→ Database
             (React/WordPress)   (GPT API)    (MySQL/Postgres)
             
AI Chatbot kaam:
- Appointment book karo
- Doctor suggest karo
- Patient ki history batao
```

### Step 2: Hamara platform ALAG server pe install
```bash
# Clinic ke IT team ko bolte hain:
# "Ek alag server do (ya cloud pe lagao), hum apna system wahan install karte hain"

# Server pe:
docker compose up
# Done. Platform chal raha hai.
```

### Step 3: Connection lagao (2-3 lines clinic ke code me)
```python
# Clinic ke AI chatbot ke code me sirf ye add:
import earp

@earp.trace()                          # ← Har call record hogi
@earp.guard(require_approval_above=1)  # ← 1+ appointment pe human approval
def book_appointment(patient, doctor, time):
    # ... clinic ka existing code ...
    pass
```

### Step 4: Watchdog connect karo (read-only)
```
Hamara Watchdog ──READ ONLY──→ Clinic ka Database

Watchdog check karta hai:
✅ Double booking toh nahi? (Same doctor, same time, 2 patients)
✅ Patient ka PII (Aadhaar) response me toh nahi gaya?
✅ Appointment galat department me toh nahi book hua?
```

### Step 5: Dashboard pe sab dikhta hai
```
Clinic ka manager browser me kholti hai: http://earp-server:8501

Dashboard dikhata hai:
- Aaj 45 appointments book hue
- 2 ko Guard ne roka (wrong doctor) 
- 1 double booking Watchdog ne pakdi
- AI ka Hindi accuracy 92%
- PII leak: 0 (Presidio mask kar raha hai)
```

---

## 🐳 DOCKER: Bilkul Zero Se Samjho

### Docker Kya Hai? (Sabse Simple Explanation)

**Problem imagine karo:**

```
Tumne apna platform apne laptop pe banaya. Sab kuch chal raha hai.

Ab client ko dena hai. Client ka laptop:
- Windows hai (tumhara Mac tha)
- Python 3.9 hai (tumhara 3.12 tha)
- Postgres installed nahi hai
- Alag libraries hain

Result: KUCH NAHI CHALTA 💀
```

**Docker solution:**

```
Docker = Ek DABBA (container) jisme POORA SYSTEM packed hai

Dabba ke andar:
├── Python 3.12 ✅
├── Postgres database ✅
├── Tumhara code ✅
├── Sab libraries ✅
└── Sab settings ✅

Ye dabba KISI BHI computer pe chalega — Windows, Mac, Linux, Cloud.
Bas Docker install karo, dabba kholo, DONE.
```

**Real life analogy:**

```
🍔 Bina Docker: "Burger banana hai? Toh pehle kitchen banao, 
   oven khaido, ingredients lao, recipe seekho..."

🍔 Docker ke saath: "Ye lo sealed dabba, microwave me 2 minute,
   burger ready. Kisi bhi kitchen me chalega."
```

---

### Docker Install Kaise Karo?

#### Step 1: Docker Desktop Download Karo

```
1. Browser me jao: https://www.docker.com/products/docker-desktop/
2. "Download for Windows" pe click karo
3. Installer download hoga (~500MB)
4. Installer run karo → Next Next Next → Install
5. Computer restart karo
```

#### Step 2: Check Karo Ki Docker Install Hua

```powershell
# PowerShell/Terminal kholo aur ye likho:
docker --version
# Output aana chahiye: Docker version 27.x.x

docker compose version  
# Output aana chahiye: Docker Compose version v2.x.x
```

#### Step 3: Test Karo

```powershell
# Ye command chala ke dekho:
docker run hello-world

# Agar ye message aaye toh Docker sahi install hai:
# "Hello from Docker! This message shows that your installation
#  appears to be working correctly."
```

---

### Docker Compose Kya Hai?

Docker = ek dabba run karta hai
Docker **Compose** = **bahut saare dabbe ek saath** run karta hai

Hamara platform me **4-5 dabbe** chahiye:

```
┌─────────────────────────────────────────────────┐
│  docker compose up  (ek command, sab shuru)      │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐      │
│  │ Dabba 1  │ │ Dabba 2  │ │ Dabba 3      │      │
│  │ POSTGRES │ │ FASTAPI  │ │ STREAMLIT    │      │
│  │ Database │ │ Backend  │ │ Dashboard    │      │
│  │ Port:5432│ │ Port:8000│ │ Port:8501    │      │
│  └──────────┘ └──────────┘ └──────────────┘      │
│                                                   │
│  ┌──────────┐ ┌──────────┐                        │
│  │ Dabba 4  │ │ Dabba 5  │                        │
│  │ LITELLM  │ │ ShopOps  │                        │
│  │ Gateway  │ │ AI Agent │                        │
│  │ Port:4000│ │ (worker) │                        │
│  └──────────┘ └──────────┘                        │
│                                                   │
│  Sab ek private network me connected hain         │
└─────────────────────────────────────────────────┘
```

---

### Docker Compose Full Process (Step by Step)

#### Step 1: Project me ye file hogi — `docker-compose.yml`

```yaml
# docker-compose.yml — YE FILE HUME BANANI HAI

version: "3.9"

services:

  # DABBA 1: Database
  postgres:
    image: pgvector/pgvector:pg16    # Postgres + Vector search
    environment:
      POSTGRES_USER: earp
      POSTGRES_PASSWORD: earp123
      POSTGRES_DB: earp_db
    ports:
      - "5432:5432"                  # Laptop ke port 5432 pe available
    volumes:
      - postgres_data:/var/lib/postgresql/data  # Data save rahega
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U earp"]
      interval: 5s
      retries: 5

  # DABBA 2: Backend API
  api:
    build: .                          # Hamara code se image banao
    command: uvicorn earp.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"                  # API: http://localhost:8000
    environment:
      DATABASE_URL: postgresql://earp:earp123@postgres:5432/earp_db
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy   # Pehle database ready ho
    
  # DABBA 3: Dashboard
  dashboard:
    build: .
    command: streamlit run earp/dashboard/app.py --server.port 8501
    ports:
      - "8501:8501"                  # Dashboard: http://localhost:8501
    environment:
      API_URL: http://api:8000
    depends_on:
      - api

  # DABBA 4: LLM Gateway  
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"                  # Gateway: http://localhost:4000
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: --config /app/config.yaml

volumes:
  postgres_data:                     # Database ka data yahan save hoga
```

#### Step 2: Ek `.env` file banao (secrets ke liye)

```bash
# .env file (ye git me NAHI jayegi)
GEMINI_API_KEY=AIzaSy...tumhara_key
GROQ_API_KEY=gsk_...tumhara_key
```

#### Step 3: EK COMMAND se sab start karo

```powershell
# Terminal me project folder me jao aur ye likho:
docker compose up

# Ye hoga:
# 1. Docker Postgres ka image download karega (pehli baar ~200MB)
# 2. Tumhara code ka image banega
# 3. Sab 4-5 dabbe (containers) ek saath start honge
# 4. Terminal me logs dikhenge:

# postgres_1  | database system is ready to accept connections
# api_1       | Uvicorn running on http://0.0.0.0:8000
# dashboard_1 | You can now view your Streamlit app in your browser
# litellm_1   | LiteLLM running on http://0.0.0.0:4000
```

#### Step 4: Browser me kholo

```
http://localhost:8000      → API (Swagger docs dikhega)
http://localhost:8000/docs → API documentation
http://localhost:8501      → Dashboard (ye main cheez hai!)
http://localhost:4000      → LLM Gateway
```

#### Step 5: Band karo

```powershell
# Terminal me Ctrl+C dabao
# Ya:
docker compose down        # Sab containers band

docker compose down -v     # Sab band + database ka data bhi delete
```

---

### Roz Kaam Kaise Karoge (Daily Commands)

```powershell
# Subah: Start karo
docker compose up -d          # -d = background me chale (terminal free)

# Kaam ke dauran:
docker compose logs -f api    # API ke logs dekho (live)
docker compose logs -f dashboard  # Dashboard ke logs dekho

# Code change kiya? Rebuild karo:
docker compose up -d --build  # Naya code ke saath restart

# Database me data dekho:
docker compose exec postgres psql -U earp -d earp_db
# Ab SQL likh sakte ho:
# SELECT * FROM orders LIMIT 10;

# Tests chalao:
docker compose exec api pytest tests/ -v

# Seed data dalo:
docker compose exec api python -m earp.seed

# Sham ko band karo:
docker compose down
```

---

## 🌍 Client Ko Kaise Doge? (3 Options)

### Option 1: Client ke server pe Docker install (On-Premise)

```
Client ka IT team:
1. Server pe Docker install kare
2. Hamara code clone kare:  git clone https://github.com/you/earp.git
3. docker compose up
4. DONE. Platform chal raha hai unke server pe.
```

```
┌─ Client ka Office ──────────────────────┐
│                                          │
│  Client ka Server                        │
│  ┌────────────────────────────────────┐  │
│  │  Docker                           │  │
│  │  ┌─────────┐ ┌──────┐ ┌────────┐ │  │
│  │  │Postgres │ │ API  │ │Dashboard│ │  │
│  │  └─────────┘ └──────┘ └────────┘ │  │
│  └────────────────────────────────────┘  │
│         │                                │
│         │ API wire                       │
│         ▼                                │
│  Client ka AI System                     │
│                                          │
└──────────────────────────────────────────┘
```

### Option 2: Cloud pe deploy karo (SaaS-style)

```
Hamara platform cloud pe chal raha hai (Railway/Render/AWS).
Client ke AI system se API se connect.

Client ko sirf DASHBOARD ka URL dena hai:
"Ye lo: https://earp-dashboard.railway.app — login karo aur sab dekho"
```

```
┌─ Cloud (Railway/AWS) ──────────┐
│                                 │
│  Hamara EARP Platform           │
│  ┌────────┐ ┌──────┐ ┌──────┐ │
│  │Postgres│ │ API  │ │Dash- │ │
│  │        │ │      │ │board │ │
│  └────────┘ └──┬───┘ └──────┘ │
│                │               │
└────────────────┼───────────────┘
                 │ Internet (API)
                 │
┌────────────────▼───────────────┐
│  Client ka Office              │
│  Client ka AI System           │
│  (unke server pe, ya unka cloud)│
└────────────────────────────────┘
```

### Option 3: Client ke existing cloud me add karo

```
Client already AWS/GCP use karta hai?
Toh unke cloud account me hamara Docker image deploy kar do.

Client ka AWS:
├── Unka AI Agent (ECS/Lambda)
├── Unka Database (RDS)
└── Hamara EARP Platform (ECS)  ← Ye add karo
    ├── API wire se AI Agent se connect
    └── Read-only wire se Database se connect
```

---

## 🎯 Final Summary: Kahan Lagega?

```
Q: Website me lagega?
A: NAHI. Alag system hai. Sirf API WIRE se connect.

Q: Extension hai?
A: NAHI. Standalone platform hai.

Q: Client ke code me kya change hoga?
A: Sirf 2-3 lines (hamari library import + trace/guard decorator).
   Ya ZERO lines (agar proxy/middleware mode use karo).

Q: Docker kya karta hai?
A: Poora platform ek DABBE me pack karta hai.
   Kisi bhi computer pe "docker compose up" karo → sab chal jayega.

Q: Client ko kaise denge?
A: 3 tarike:
   1. Unke server pe Docker install → docker compose up
   2. Cloud pe deploy → URL de do
   3. Unke cloud account me add karo
```

---

## 🗺️ Visual Summary

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   CLIENT KI DUNIYA              HAMARI DUNIYA                ║
║   (unka existing system)        (alag system)                ║
║                                                              ║
║   ┌──────────────┐              ┌──────────────────┐         ║
║   │ Client ki    │              │ EARP Platform    │         ║
║   │ Website      │              │                  │         ║
║   │ (React/      │              │ 📹 Trace Store   │         ║
║   │  WordPress)  │              │ 🛡️ Action Guard  │         ║
║   └──────┬───────┘              │ 📊 Eval Engine   │         ║
║          │                      │ 🔍 Watchdog      │         ║
║          ▼                      │ 📺 Dashboard     │         ║
║   ┌──────────────┐    API       │ 🚨 Alerts        │         ║
║   │ Client ka    │◄────WIRE────►│                  │         ║
║   │ AI Agent     │              │                  │         ║
║   └──────┬───────┘              └──────────────────┘         ║
║          │                              │                    ║
║          ▼                         Browser me                ║
║   ┌──────────────┐              ┌──────────────────┐         ║
║   │ Client ka    │◄──READ ONLY──│ Watchdog         │         ║
║   │ Database     │              │ (sirf padhta hai, │         ║
║   └──────────────┘              │  kuch likhta nahi)│         ║
║                                 └──────────────────┘         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```
