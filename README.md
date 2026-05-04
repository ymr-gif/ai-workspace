# AI API Backend (FastAPI)

## Overview
This is a lightweight backend API built using FastAPI.  
It includes basic authentication logic, modular routing, and external API integration structure (planned expansion).

The goal of this project is to serve as a foundation for a scalable backend system that can later integrate databases, authentication systems, and AI services.

---

## Features
- FastAPI-based REST API
- Basic authentication system (admin/user roles)
- Modular project structure (routers + auth separation)
- Environment-based configuration using `.env`
- External API integration-ready architecture

---

## Tech Stack
- Python
- FastAPI
- Uvicorn
- Python-dotenv
- HTTPX

---

## Setup

### 1. Clone repo
```bash
git clone https://github.com/ymr-gif/ai-workspace.git
cd ai-workspace
```

### 2. Create virtual environment
```
Windows:
.venv\Scripts\activate
```
```
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Run server
```
uvicorn app:app --reload
```
---

## Environment Variables
Copy `.env.example` to `.env` and fill in required values before running the server.

---

# Roadmap
- Add PostgreSQL database integration
- Implement JWT-based authentication
- Add user registration system
- Improve API security and rate limiting

---

## Folder structure upgrade
```
app/
│
├── main.py
├── core/
│   └── config.py
│
├── routers/
│   ├── auth.py
│   └── api.py
│
├── services/
│   └── auth_service.py
│
├── models/
│   └── users.py
│
└── utils/
    └── security.py
```
