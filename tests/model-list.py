from openai import OpenAI
from config import NVIDIA_API_KEY

load dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="NVIDIA_API_KEY"
)

models = client.models.list()
print(models) #gets all model lists