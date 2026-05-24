"""List all models available on the NVIDIA NIM account."""
import os
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

load_dotenv(find_dotenv())

api_key = os.getenv("NVIDIA_API_KEY")
if not api_key:
    raise RuntimeError("NVIDIA_API_KEY not set in .env")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
)

models = client.models.list()
for m in sorted(models.data, key=lambda x: x.id):
    print(m.id)
