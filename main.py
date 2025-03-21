import sys
import os

# Додаємо кореневий каталог проекту до sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

import tkinter as tk
from app.gui.windows.main import PaymentAnalyzerApp

if __name__ == "__main__":
    root = tk.Tk()
    app = PaymentAnalyzerApp(root)
    root.mainloop()