import os

from dotenv import load_dotenv

load_dotenv()

value = os.getenv('MY_VARIABLE')

if __name__ == "__main__":
