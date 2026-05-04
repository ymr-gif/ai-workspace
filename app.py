import streamlit as st
import httpx

st.set_page_config(page_title="AI Chatbot", page_icon="🤖", layout="centered")

st.title("All-Rounded AI Chatbot")
st.caption("Powered by NVIDIA NIM · Auto-routed to the best model for your query")

# Must match MODELS dict in router.py
MODEL_LABELS = {
    "meta/llama-3.1-8b-instruct":           "Llama 3.1 8B         · fast chat",
    "qwen/qwen2.5-coder-32b-instruct":      "Qwen 2.5 Coder 32B   · coding",
    "nvidia/llama-3.1-nemotron-nano-8b-v1": "Nemotron Nano 8B     · reasoning",
    "z-ai/glm4.7":                          "GLM-4.7              · deep analysis",
}

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("model_used"):
            label = MODEL_LABELS.get(msg["model_used"], msg["model_used"])
            st.caption(f"Model: {label}")

if prompt := st.chat_input("Ask anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Routing & thinking..."):
            try:
                r = httpx.post(
                    "http://localhost:8000/chat",
                    json={"message": prompt},
                    timeout=60,
                )
                r.raise_for_status()
                data       = r.json()
                reply      = data.get("response", "⚠️ Empty response from server.")
                model_used = data.get("model_used", "")
            except httpx.HTTPStatusError as e:
                reply, model_used = f"⚠️ Server error {e.response.status_code}: {e.response.text}", ""
            except httpx.RequestError as e:
                reply, model_used = f"⚠️ Could not reach backend: {e}", ""
            except Exception as e:
                reply, model_used = f"⚠️ Unexpected error: {e}", ""

        st.write(reply)
        if model_used:
            st.caption(f"Model: {MODEL_LABELS.get(model_used, model_used)}")

    st.session_state.messages.append({
        "role": "assistant", "content": reply, "model_used": model_used,
    })