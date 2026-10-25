"""APK Builder desktop entry point."""
if __name__ == '__main__':
    from bin.gui import App
    app = App()
    app.mainloop()
