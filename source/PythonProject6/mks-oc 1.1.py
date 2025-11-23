import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import subprocess
from pathlib import Path
import datetime
import json  # Для сохранения/восстановления состояния
import logging  # Для регистрации ошибок и отладки

# Настройка журнала (logging)
logging.basicConfig(
    level=logging.INFO,  # Или logging.DEBUG для более подробной информации
    format="%(asctime)s [%(levelname)s] %(module)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        logging.FileHandler("mks-os.log", encoding="utf-8"),  # Сохранение в файл
    ],
)

# === КОНФИГУРАЦИЯ ===
DEFAULT_GEOMETRY = "1024x640"
MIN_WIDTH = 800
MIN_HEIGHT = 520
BACKGROUND_COLOR = "#1e1e1e"
TASKBAR_COLOR = "#171717"
START_MENU_COLOR = "#111111"
DEFAULT_THEME = "Dark"
CONFIG_FILE = "mks-os_config.json"  # Файл для сохранения конфигурации.


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning("Config file not found. Using default settings.")
        return {}  # Вернуть пустой словарь, если файл не найден
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding config file: {e}.  Using default settings.")
        return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===


def run_command(command):
    """
    Запускает команду оболочки с обработкой ошибок.
    """
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {command}\n{e.stderr}")
        messagebox.showerror("Error", f"Command failed: {e.stderr}")
    except FileNotFoundError:
        logging.error(f"Command not found: {command}")
        messagebox.showerror("Error", f"Command not found: {command}")
    except Exception as e:
        logging.exception(f"Unexpected error running command: {command}")
        messagebox.showerror("Error", str(e))


# === КЛАССЫ ПРИЛОЖЕНИЙ ===


class BaseWindow:
    """
    Базовый класс для окон приложений, содержащий общую логику.
    """

    def __init__(self, master, title, geometry):
        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.geometry(geometry)
        self.win.protocol("WM_DELETE_WINDOW", self.close)  # Перехват закрытия окна

    def close(self):
        """Действия при закрытии окна (например, сохранение)."""
        self.win.destroy()  # Уничтожение окна


class NotepadWindow(BaseWindow):
    def __init__(self, master):
        super().__init__(master, "Notepad", "560x420")
        self.text = tk.Text(self.win, wrap="word")
        self.text.pack(fill="both", expand=True)

        menubar = tk.Menu(self.win)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Save", command=self.save)
        filem.add_command(label="Exit", command=self.close)
        menubar.add_cascade(label="File", menu=filem)
        self.win.config(menu=menubar)

    def save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.text.get("1.0", "end-1c"))
            except Exception as e:
                logging.exception("Error saving file")  # Логирование ошибки
                messagebox.showerror("Save error", str(e))


class FileExplorerWindow(BaseWindow):
    def __init__(self, master, path=None):
        super().__init__(master, "File Explorer", "600x420")
        self.current_path = Path(path or os.getcwd())

        self.path_label = tk.Label(self.win, text=str(self.current_path), anchor="w")
        self.path_label.pack(fill="x")

        self.listbox = tk.Listbox(self.win)
        self.listbox.pack(fill="both", expand=True, side="left")

        self.scroll = tk.Scrollbar(self.win, orient="vertical")
        self.scroll.config(command=self.listbox.yview)
        self.scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=self.scroll.set)

        self.populate()
        self.listbox.bind("<Double-1>", self.on_double)

        btn_frame = tk.Frame(self.win)
        btn_frame.pack(fill="x")
        up_btn = tk.Button(btn_frame, text="Up", command=self.go_up)
        up_btn.pack(side="left", padx=5, pady=5)
        open_btn = tk.Button(btn_frame, text="Open", command=self.open_selected)
        open_btn.pack(side="left", padx=5, pady=5)

    def populate(self):
        self.listbox.delete(0, tk.END)
        self.path_label.config(text=str(self.current_path))
        try:
            entries = sorted(
                self.current_path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError as e:
            logging.warning(f"Permission denied: {self.current_path}. {e}")
            messagebox.showerror("Permission Denied", str(e))
            entries = []
        self.listbox.insert(tk.END, ".. (Up)")
        self._entries = [".."]
        for p in entries:
            self.listbox.insert(tk.END, ("[D] " if p.is_dir() else "[F] ") + p.name)
            self._entries.append(str(p))

    def on_double(self, event):
        idx = self.listbox.curselection()
        if not idx:
            return
        i = idx[0]
        self.handle_selection(i)

    def go_up(self):
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.populate()

    def open_selected(self):
        idx = self.listbox.curselection()
        if not idx:
            return
        i = idx[0]
        self.handle_selection(i)

    def handle_selection(self, i):
        path = self._entries[i]
        if path == "..":
            self.go_up()
        else:
            p = Path(path)
            if p.is_dir():
                self.current_path = p
                self.populate()
            else:
                self.open_file(p)

    def open_file(self, p):
        try:
            if os.name == "nt":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.call(["open", p])
            else:
                subprocess.call(["xdg-open", p])
        except FileNotFoundError:
            logging.error(f"File not found: {p}")
            messagebox.showerror("File Not Found", "The specified file was not found.")
        except Exception as e:
            logging.exception(f"Error opening file: {p}")
            messagebox.showerror("Open file", str(e))


class SettingsWindow(BaseWindow):
    def __init__(self, master):
        super().__init__(master, "Settings", "420x260")
        frame = tk.Frame(self.win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.config = load_config()
        self.btn_fullscreen = tk.BooleanVar(value=self.config.get("fullscreen", False))
        cb = tk.Checkbutton(
            frame,
            text="Enable experimental fullscreen (not implemented)",
            variable=self.btn_fullscreen,
            state="disabled",
        )
        cb.pack(anchor="w")

        self.theme = tk.StringVar(value=self.config.get("theme", DEFAULT_THEME))
        tk.Label(frame, text="Theme:").pack(anchor="w", pady=(8, 0))
        theme_menu = tk.OptionMenu(frame, self.theme, "Dark", "Light", command=self.apply_theme)
        theme_menu.pack(anchor="w")

    def apply_theme(self, theme):
        """Применяет выбранную тему."""
        self.config["theme"] = theme
        save_config(self.config)
        # Здесь должна быть логика для изменения цветов элементов UI.
        print(f"Applying theme: {theme}")  # Заглушка, нужно реализовать смену темы


# === ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ ===


class WinOC:
    def __init__(self, root):
        self.root = root

        # Загрузка конфигурации
        self.config = load_config()
        self.root.title(self.config.get("title", "mks-os 1.1"))  # Пример загрузки title
        self.root.geometry(self.config.get("geometry", DEFAULT_GEOMETRY))
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(bg=BACKGROUND_COLOR)  # Применение из конфига

        self.desktop = tk.Canvas(self.root, bg=BACKGROUND_COLOR, highlightthickness=0)
        self.desktop.pack(fill="both", expand=True)

        self.draw_desktop_background()
        self.app_icons = []
        self.open_windows = []

        self.create_desktop_icons()
        self.create_taskbar()
        self.create_start_menu_button()

        self.start_menu = None  # будет создано в create_start_menu_button
        self.update_clock()

        self.root.bind("<Escape>", lambda e: self.close_start_menu())

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)  # Перехват закрытия окна

    def on_close(self):
        """Сохраняет состояние перед закрытием."""
        self.save_window_state()
        self.root.destroy()

    def save_window_state(self):
        """Сохраняет геометрию окна и другие параметры."""
        self.config["geometry"] = self.root.geometry()
        save_config(self.config)

    def draw_desktop_background(self):
        # простая фоновая текстура, чтобы визуально напоминать рабочий стол
        self.desktop.create_rectangle(0, 0, 2000, 2000, fill="#0b2545", outline="")
        for i in range(0, 2000, 20):
            self.desktop.create_line(0, i, 2000, i, fill="#0f2a6b", width=1, dash=(2, 8))

    def create_desktop_icons(self):
        icons = [
            ("Notepad", self.open_notepad),
            ("File Explorer", self.open_file_explorer),
            ("Settings", self.open_settings),
        ]
        x, y = 50, 50
        for name, command in icons:
            self.create_desktop_icon(name, command, x, y)
            y += 100

    def create_desktop_icon(self, name, command, x, y):
        icon_size = 50
        text_offset = 10

        # Создаем иконку (простой прямоугольник placeholder)
        icon = self.desktop.create_rectangle(
            x - icon_size // 2,
            y - icon_size // 2,
            x + icon_size // 2,
            y + icon_size // 2,
            fill="#336699",
            outline="#6699CC",
        )

        # Создаем текст под иконкой
        text = self.desktop.create_text(
            x,
            y + icon_size // 2 + text_offset,
            text=name,
            fill="white",
            anchor="n",
        )

        # Добавляем обработчик клика
        def on_icon_click(event, cmd=command):
            cmd()

        self.desktop.tag_bind(icon, "<Button-1>", on_icon_click)
        self.desktop.tag_bind(text, "<Button-1>", on_icon_click)

        # Сохраняем иконки чтобы держать на них ссылки
        self.app_icons.append((icon, text))

    def create_taskbar(self):
        """Создает панель задач внизу экрана."""
        self.taskbar = tk.Frame(
            self.root, bg=TASKBAR_COLOR, height=30
        )  # Устанавливаем высоту
        self.taskbar.pack(side="bottom", fill="x")

        # Добавляем часы на панель задач
        self.clock_label = tk.Label(
            self.taskbar, bg=TASKBAR_COLOR, fg="white", font=("Helvetica", 10)
        )
        self.clock_label.pack(side="right", padx=10)

       # Разделитель между часами и остальными элементами панели задач
        self.separator = ttk.Separator(self.taskbar, orient='vertical')
        self.separator.pack(side='right', fill='y', padx=5)

    def create_start_menu_button(self):
        """Создает кнопку "Пуск" и привязывает к ней вызов Start Menu."""
        self.start_button = tk.Button(
            self.taskbar,
            text="Start",
            command=self.toggle_start_menu,
            bg="#2a2a2a",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            width=6,
        )
        self.start_button.pack(side="left", padx=5)

    def create_start_menu(self):
        """Создает Start Menu."""
        if self.start_menu:
            self.start_menu.destroy()

        self.start_menu = tk.Frame(
            self.root, bg=START_MENU_COLOR, highlightthickness=1, highlightbackground="gray"
        )
        self.start_menu.place(
            x=0, y=self.root.winfo_height() - 200, anchor="sw"
        )  # 200 - высота меню

        buttons = [
            ("Notepad", self.open_notepad),
            ("File Explorer", self.open_file_explorer),
            ("Settings", self.open_settings),
            ("Close MKS OS", self.on_close)  # Добавляем кнопку "Выход"
        ]

        for i, (text, command) in enumerate(buttons):
            btn = tk.Button(
                self.start_menu,
                text=text,
                command=command,
                bg=START_MENU_COLOR,
                fg="white",
                width=15,
                anchor="w",
                relief=tk.FLAT,
            )
            btn.grid(row=i, column=0, sticky="ew", padx=5, pady=2)  # Используем grid
            # Добавляем hover effect
            btn.bind("<Enter>", lambda e, bg=START_MENU_COLOR: e.widget.config(bg="#444444"))
            btn.bind("<Leave>", lambda e, bg=START_MENU_COLOR: e.widget.config(bg=bg))


    def toggle_start_menu(self):
        """Показывает/скрывает Start Menu."""
        if self.start_menu:
            self.close_start_menu()
        else:
            self.create_start_menu()

    def close_start_menu(self):
        """Удаляет Start Menu."""
        if self.start_menu:
            self.start_menu.destroy()
            self.start_menu = None

    def update_clock(self):
        """Обновляет время на панели задач."""
        now = datetime.datetime.now()
        time_string = now.strftime("%H:%M:%S")  # Формат времени
        date_string = now.strftime("%Y-%m-%d")  # Формат даты
        self.clock_label.config(text=f"{time_string}  {date_string}")
        self.root.after(1000, self.update_clock)  # Обновлять каждую секунду

    def open_notepad(self):
        """Открывает окно Notepad."""
        NotepadWindow(self.root)

    def open_file_explorer(self):
        """Открывает окно File Explorer."""
        FileExplorerWindow(self.root)

    def open_settings(self):
        """Открывает окно Settings."""
        SettingsWindow(self.root)


if __name__ == "__main__":
    root = tk.Tk()
    app = WinOC(root)
    root.mainloop()