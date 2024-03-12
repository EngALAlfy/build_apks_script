from dotenv import load_dotenv
from bin.gui import App

load_dotenv()


if __name__ == "__main__":
    app = App()
    app.mainloop()
