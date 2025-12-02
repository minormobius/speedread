import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from tkinter import ttk
import urllib.request
import re


class RSVPApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RSVP Speed Reader")

        # Core state
        self.words = []
        self.index = 0
        self.running = False

        # Keep raw text so we can slice out chapters later
        self.raw_text = ""

        # Frame coloring state (for alternating text colors)
        self.frame_index = 0
        # White and light pink
        self.text_colors = ("#ffffff", "#ff9aca")

        self._build_ui()
        self._bind_hotkeys()

    # ---------- UI SETUP ----------

    def _build_ui(self):
        control_frame = tk.Frame(self.root)
        control_frame.pack(padx=10, pady=10, fill="x")

        # Row 0: file + Gutenberg
        open_btn = tk.Button(
            control_frame,
            text="Open Text File…",
            command=self.open_file
        )
        open_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        tk.Label(control_frame, text="Gutenberg ID:").grid(
            row=0, column=1, padx=5, sticky="e"
        )
        self.gutenberg_entry = tk.Entry(control_frame, width=8)
        self.gutenberg_entry.grid(row=0, column=2, padx=2, sticky="w")

        fetch_btn = tk.Button(
            control_frame,
            text="Fetch",
            command=self.fetch_gutenberg
        )
        fetch_btn.grid(row=0, column=3, padx=5, sticky="w")

        # Row 1: speed slider
        tk.Label(control_frame, text="Speed (words/min):").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.speed_scale = tk.Scale(
            control_frame,
            from_=100,
            to=1200,
            orient="horizontal"
        )
        self.speed_scale.set(400)  # default WPM
        self.speed_scale.grid(row=1, column=1, columnspan=3,
                              padx=5, pady=5, sticky="we")

        # Row 2: window length slider
        tk.Label(control_frame, text="Window length (chars):").grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        self.window_scale = tk.Scale(
            control_frame,
            from_=5,
            to=80,
            orient="horizontal"
        )
        self.window_scale.set(20)  # default window size
        self.window_scale.grid(row=2, column=1, columnspan=3,
                               padx=5, pady=5, sticky="we")

        # Row 3: chapter selector (Gutenberg-style)
        tk.Label(control_frame, text="Chapter #:").grid(
            row=3, column=0, padx=5, pady=5, sticky="w"
        )
        self.chapter_entry = tk.Entry(control_frame, width=6)
        self.chapter_entry.grid(row=3, column=1, padx=2, sticky="w")

        chapter_btn = tk.Button(
            control_frame,
            text="Load Chapter",
            command=self.load_chapter
        )
        chapter_btn.grid(row=3, column=2, padx=5, pady=5, sticky="w")

        # Buttons: Start / Pause / Reset
        buttons_frame = tk.Frame(self.root)
        buttons_frame.pack(padx=10, pady=(0, 5))

        tk.Button(buttons_frame, text="Start",
                  command=self.start).pack(side="left", padx=5)
        tk.Button(buttons_frame, text="Pause",
                  command=self.pause).pack(side="left", padx=5)
        tk.Button(buttons_frame, text="Reset",
                  command=self.reset).pack(side="left", padx=5)

        # Progress bar
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(padx=10, pady=(0, 10), fill="x")

        tk.Label(progress_frame, text="Progress:").pack(side="left")
        self.progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate"
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Display area (Text with bold + normal tags)
        self.display = tk.Text(
            self.root,
            height=3,
            width=40,
            state="disabled",
            wrap="word",
        )
        self.display.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        # Dark-mode colors: black background, white text initial
        self.display.configure(
            bg="#000000",
            fg="#ffffff",
            insertbackground="#ffffff"
        )

        # Fonts for cybernetic reading
        self.base_font = tkfont.Font(family="Helvetica", size=32)
        self.bold_font = self.base_font.copy()
        self.bold_font.configure(weight="bold")

        self.display.configure(font=self.base_font)
        self.display.tag_configure("bold", font=self.bold_font, foreground="#ffffff")
        self.display.tag_configure("normal", font=self.base_font, foreground="#ffffff")

    def _bind_hotkeys(self):
        # Bind to the whole app so keys work regardless of focus
        self.root.bind_all("<space>", self._toggle_play)
        self.root.bind_all("<Up>", self._faster)
        self.root.bind_all("<Down>", self._slower)
        self.root.bind_all("<Right>", self._longer_window)
        self.root.bind_all("<Left>", self._shorter_window)

    # ---------- TEXT LOADING ----------

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open text file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return

        self.raw_text = text
        self.load_text(text)

    def fetch_gutenberg(self):
        """
        Very simple Project Gutenberg hook:
        Enter numeric ID (e.g. 1342 for Pride and Prejudice)
        and we'll try https://www.gutenberg.org/cache/epub/ID/pgID.txt
        """
        book_id = self.gutenberg_entry.get().strip()
        if not book_id.isdigit():
            messagebox.showerror(
                "Error",
                "Please enter a numeric Gutenberg ID (e.g. 84, 1342)."
            )
            return

        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

        try:
            with urllib.request.urlopen(url) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="ignore")
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Could not fetch book {book_id}:\n{e}"
            )
            return

        # Store full raw text so we can slice chapters
        self.raw_text = text
        self.load_text(text)

    def load_text(self, text: str, store_raw: bool = False):
        """
        Load text into the RSVP engine.
        If store_raw=True, also remember this exact text as raw_text.
        (We usually set raw_text on file/Gutenberg fetch instead.)
        """
        if store_raw:
            self.raw_text = text

        # Simple cleanup: flatten newlines to spaces
        cleaned = text.replace("\r\n", " ").replace("\n", " ")
        self.words = cleaned.split()
        self.index = 0
        self.frame_index = 0
        self.pause()
        self._update_display("")

        # Reset progress bar
        total = max(1, len(self.words))
        self.progress["maximum"] = total
        self.progress["value"] = 0

        if not self.words:
            messagebox.showinfo(
                "No words",
                "The loaded text appears to be empty."
            )

    def load_chapter(self):
        """
        Heuristic Gutenberg-style chapter loader.

        Instead of trusting the numeric in the heading, we:
        - Find all lines starting with 'CHAPTER' (case-insensitive).
        - Treat Chapter #1 as the FIRST such heading, Chapter #2 as the SECOND, etc.
        - Slice from that heading up to the next heading (or end-of-book).
        """
        if not self.raw_text:
            messagebox.showinfo(
                "No book loaded",
                "Load a text or Gutenberg book first."
            )
            return

        ch_str = self.chapter_entry.get().strip()
        if not ch_str.isdigit():
            messagebox.showerror(
                "Error",
                "Chapter must be a number (e.g. 1, 2, 3)."
            )
            return

        ch_idx = int(ch_str) - 1  # zero-based index into chapter list
        if ch_idx < 0:
            messagebox.showerror(
                "Error",
                "Chapter number must be >= 1."
            )
            return

        lines = self.raw_text.splitlines()

        # Find all candidate chapter headings
        chapter_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Simple heuristic: line starts with 'CHAPTER'
            if stripped.upper().startswith("CHAPTER "):
                chapter_lines.append(i)

        if not chapter_lines:
            messagebox.showerror(
                "Not found",
                "No 'CHAPTER ...' headings found in this text."
            )
            return

        if ch_idx >= len(chapter_lines):
            messagebox.showerror(
                "Not found",
                f"This text only has {len(chapter_lines)} chapters "
                f"by our heuristic; you requested chapter {ch_idx + 1}."
            )
            return

        start_line = chapter_lines[ch_idx]
        if ch_idx + 1 < len(chapter_lines):
            end_line = chapter_lines[ch_idx + 1]
        else:
            end_line = len(lines)

        chapter_text = "\n".join(lines[start_line:end_line])
        self.load_text(chapter_text, store_raw=False)

    # ---------- PLAYBACK CONTROL ----------

    def start(self):
        if not self.words:
            messagebox.showinfo(
                "No text",
                "Load a text file or fetch a Gutenberg book first."
            )
            return
        if not self.running:
            self.running = True
            self._schedule_next()

    def pause(self):
        self.running = False

    def reset(self):
        self.pause()
        self.index = 0
        self.frame_index = 0
        self._update_display("")
        self.progress["value"] = 0

    def _schedule_next(self):
        if not self.running:
            return

        # speed slider is in words per minute
        wpm = max(1, int(self.speed_scale.get()))
        interval_ms = int(60000 / wpm)

        self._show_next_chunk()
        self.root.after(interval_ms, self._schedule_next)

    # ---------- RENDERING ----------

    def _show_next_chunk(self):
        if self.index >= len(self.words):
            self.pause()
            return

        max_chars = int(self.window_scale.get())
        total_len = 0
        chunk_words = []

        while self.index < len(self.words):
            w = self.words[self.index]
            # +1 for space between words (but not before first)
            added = len(w) if not chunk_words else len(w) + 1

            if total_len + added > max_chars and chunk_words:
                break

            chunk_words.append(w)
            total_len += added
            self.index += 1

        self._render_chunk(chunk_words)

        # Update progress bar (based on word index)
        if self.words:
            self.progress["value"] = min(self.index, len(self.words))

    def _render_chunk(self, chunk_words):
        # Alternate text colors each frame
        color = self.text_colors[self.frame_index % len(self.text_colors)]
        self.frame_index += 1

        # Update tag colors for this frame
        self.display.tag_configure("bold", font=self.bold_font, foreground=color)
        self.display.tag_configure("normal", font=self.base_font, foreground=color)

        # Black background, always
        self.display.config(state="normal", bg="#000000")

        self.display.delete("1.0", "end")

        first_word = True
        for w in chunk_words:
            if not first_word:
                # Insert the space as normal text
                self.display.insert("end", " ", ("normal",))
            first_word = False

            # Cybernetic reading: bold first half, normal second half
            split_point = (len(w) + 1) // 2  # round up for odd lengths
            bold_part = w[:split_point]
            plain_part = w[split_point:]

            if bold_part:
                self.display.insert("end", bold_part, ("bold",))
            if plain_part:
                self.display.insert("end", plain_part, ("normal",))

        self.display.config(state="disabled")

    def _update_display(self, text: str):
        self.display.config(state="normal", bg="#000000")
        self.display.delete("1.0", "end")
        if text:
            self.display.insert("end", text, ("normal",))
        self.display.config(state="disabled")

    # ---------- HOTKEY HANDLERS ----------

    def _toggle_play(self, event=None):
        if self.running:
            self.pause()
        else:
            self.start()
        return "break"

    def _faster(self, event=None):
        step = 50
        current = self.speed_scale.get()
        new_val = min(self.speed_scale["to"], current + step)
        self.speed_scale.set(new_val)
        return "break"

    def _slower(self, event=None):
        step = 50
        current = self.speed_scale.get()
        new_val = max(self.speed_scale["from"], current - step)
        self.speed_scale.set(new_val)
        return "break"

    def _longer_window(self, event=None):
        step = 5
        current = self.window_scale.get()
        new_val = min(self.window_scale["to"], current + step)
        self.window_scale.set(new_val)
        return "break"

    def _shorter_window(self, event=None):
        step = 5
        current = self.window_scale.get()
        new_val = max(self.window_scale["from"], current - step)
        self.window_scale.set(new_val)
        return "break"


def main():
    root = tk.Tk()
    app = RSVPApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
