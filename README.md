## Environment Setup
Copy `.env.example` to `.env` and fill in your values.


# terminal 1
```
uvicorn main:app --reload --port 8000 //uvicorn main:app --reload --port 8000 --log-level debug
```

# terminal 2
```
streamlit run app.py
```