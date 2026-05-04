# AI API Backend (FastAPI)

A lightweight, modular FastAPI backend template designed to grow into a production-ready API service with authentication, database integration, and AI-facing service layers.

---

## Table of Contents
- [Overview](#overview)
- [Current Status](#current-status)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Environment Variables](#environment-variables)
- [API Usage Examples](#api-usage-examples)
- [Development](#development)
- [Roadmap](#roadmap)

---

## Overview
This project provides a clean FastAPI foundation with separated routers, core config, and service modules so it can scale as requirements grow.

It is intended as a starter backend for applications that will eventually include:
- persistent storage (PostgreSQL)
- stronger authentication/authorization (JWT + role policies)
- external API and AI service integrations

---

## Current Status
This repository is currently in **starter-template phase**:
- Core API scaffolding is in place
- Basic auth flow structure exists
- Architecture is organized for future expansion

Some features listed in the roadmap are **planned** and not fully implemented yet.

---

## Features
- FastAPI-based REST API foundation
- Modular routing structure (`routers/`)
- Separated service logic (`services/`)
- Environment-based configuration via `.env`
- Integration-ready layout for external APIs/AI services

---

## Tech Stack
- Python
- FastAPI
- Uvicorn
- python-dotenv
- HTTPX

---

## Project Structure
```text
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

---

## Prerequisites
- Python 3.10+
- pip
- Git

---

## Quickstart

### 1) Clone the repository
```bash
git clone https://github.com/ymr-gif/ai-workspace.git
cd ai-workspace
```

### 2) Create and activate a virtual environment
```bash
python -m venv .venv
```

**Linux/macOS**
```bash
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Run the development server
```bash
uvicorn app.main:app --reload
```

Open: `http://127.0.0.1:8000`

Interactive API docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Environment Variables
Copy the example file and set your values:

```bash
cp .env.example .env
```

At minimum, configure values required by your auth/config modules before running the server.

---

## API Usage Examples
> Replace endpoints below with your actual route paths if they differ.

### Health check
```bash
curl -X GET http://127.0.0.1:8000/health
```

### Login (example)
```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Protected endpoint (example with bearer token)
```bash
curl -X GET http://127.0.0.1:8000/api/me \
  -H "Authorization: Bearer <your_token_here>"
```

---

## Development

### Run server
```bash
uvicorn app.main:app --reload
```

### Recommended next additions
- Add test suite (`pytest`)
- Add linting/formatting (`ruff`, `black`)
- Add pre-commit hooks

---

## Roadmap
- Add PostgreSQL integration (SQLAlchemy + Alembic)
- Implement JWT-based authentication
- Add user registration and account lifecycle flows
- Add role/permission checks
- Improve API security (rate limiting, CORS hardening, secrets management)
- Add observability (structured logs, metrics, health probes)
