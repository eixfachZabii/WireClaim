from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print("KEY loaded:", bool(os.getenv("AZURE_OPENAI_API_KEY")))
print("ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))
print("MODEL:", os.getenv("AZURE_OPENAI_MODEL"))

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

response = client.responses.create(
    model=os.getenv("AZURE_OPENAI_MODEL"),
    input="Answer only with: API works"
)

print(response.output_text)