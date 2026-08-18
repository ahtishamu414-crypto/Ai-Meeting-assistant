from dotenv import load_dotenv
import os

load_dotenv()

print("TOKEN =", repr(os.getenv("HF_TOKEN")))