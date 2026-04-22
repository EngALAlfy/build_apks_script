import asyncio
import sys

# Monkey-patch asyncio for compatibility with older libraries (like mega.py/tenacity) on Python 3.11+
if not hasattr(asyncio, "coroutine"):
    import inspect
    asyncio.coroutine = lambda x: x  # Dummy or minimal fix
    # Some older tenacity versions might need a bit more, but often this is enough to bypass the import error

from dotenv import load_dotenv
from bin.gui import App

load_dotenv()


if __name__ == "__main__":
    app = App()
    app.mainloop()
