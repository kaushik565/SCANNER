# layout.py

import tkinter as tk
from datetime import datetime

from config import (
    APP_TITLE,
    BACKGROUND_COLOR,
    CARD_BORDER,
    CLOCK_FORMAT,
    FOOTER_TEXT,
    FULLSCREEN,
    HEADER_TEXT,
    INFO_TEXT_COLOR,
    SUBHEADER_TEXT,
    TEXT_MUTED,
    TITLE_FONT,
    SMALL_FONT,
    WINDOW_SIZE,
)


def create_main_window(setup_frame_builder):
    """Create the root window with shared header/footer sections."""
    window = tk.Tk()
    window.title(APP_TITLE)
    window.configure(bg=BACKGROUND_COLOR)
    if FULLSCREEN:
        window.attributes("-fullscreen", True)
    else:
        window.geometry(WINDOW_SIZE)

    header_frame = tk.Frame(
        window,
        bg=BACKGROUND_COLOR,
        padx=4,
        pady=2,
        highlightbackground=CARD_BORDER,
        highlightthickness=1,
    )
    header_frame.pack(fill="x", padx=4, pady=(2, 4))

    # Combine header text in single line for compact display
    combined_text = f"{HEADER_TEXT} | {SUBHEADER_TEXT}"
    tk.Label(
        header_frame,
        text=combined_text,
        font=SMALL_FONT,
        fg=INFO_TEXT_COLOR,
        bg=BACKGROUND_COLOR,
        wraplength=750,
    ).pack(anchor="w")

    footer_frame = tk.Frame(window, bg=BACKGROUND_COLOR, padx=2, pady=1)
    footer_frame.pack(side="bottom", fill="x")

    # Combine footer text and clock in single compact line
    footer_label = tk.Label(
        footer_frame,
        text=FOOTER_TEXT,
        font=SMALL_FONT,
        fg=TEXT_MUTED,
        bg=BACKGROUND_COLOR,
    )
    footer_label.pack(side="left", padx=2)

    clock_label = tk.Label(footer_frame, font=SMALL_FONT, fg=TEXT_MUTED, bg=BACKGROUND_COLOR)
    clock_label.pack(side="right", padx=2)

    def update_clock():
        clock_label.config(text=datetime.now().strftime(CLOCK_FORMAT))
        window.after(1000, update_clock)

    update_clock()
    setup_frame_builder(window)
    return window
