"""APK Builder desktop entry point."""
from dotenv import load_dotenv
from utils.app_paths import SETTINGS_FILE

load_dotenv(SETTINGS_FILE)

if __name__ == '__main__':
    from bin.gui import App
    app = App()
    app.mainloop()
