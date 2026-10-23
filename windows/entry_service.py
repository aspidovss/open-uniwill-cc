"""PyInstaller entry point: uwccd.exe (Windows service host / console daemon)."""
from uwccd.win.winservice import main

if __name__ == "__main__":
    main()
