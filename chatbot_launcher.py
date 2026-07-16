import tkinter as tk
import threading
import subprocess
import tempfile
import json
import math
import time
import os
ICON_PATH = "/Users/skita/Github/ask-the-oracle/Ask the Oracle.app/Contents/Resources/AppIcon.icns"

def set_dock_icon():
    try:
        from AppKit import NSApp, NSImage
        image = NSImage.alloc().initWithContentsOfFile_(ICON_PATH)
        if image:
            NSApp.setApplicationIconImage_(image)
    except Exception:
        pass

CHATBOTS = [
    {"name": "ChatGPT", "label": "ChatGPT",       "url": "https://chatgpt.com",       "domain": "chatgpt.com",       "wait": 2.5},
    {"name": "Claude",  "label": "Claude",        "url": "https://claude.ai/new",      "domain": "claude.ai",         "wait": 2.5},
    {"name": "Gemini",  "label": "Gemini",         "url": "https://gemini.google.com",  "domain": "gemini.google.com", "wait": 3.0},
]

# Two oracle palettes. Live theme switching remaps widget colors by value
# (see apply_theme), so the values within each palette must stay distinct.
THEMES = {
    "dark": {
        "BG":       "#0e0b1a",  # deep space purple
        "FG":       "#d4a843",  # oracle gold
        "FG_DIM":   "#7a6030",  # muted gold
        "ENTRY_BG": "#1c1530",  # dark violet
        "ENTRY_FG": "#f0e0b0",  # parchment
        "CB_BG":    "#160f28",  # slightly lighter than bg for checkboxes
        "SEL_BG":   "#2e1f5e",  # selection highlight
    },
    "light": {
        "BG":       "#f4ecd8",  # aged parchment
        "FG":       "#8a6d1f",  # deep oracle gold
        "FG_DIM":   "#b59a55",  # muted gold
        "ENTRY_BG": "#fffaf0",  # ivory
        "ENTRY_FG": "#3a2e10",  # dark ink
        "CB_BG":    "#ece0c0",  # parchment shade for checkboxes
        "SEL_BG":   "#e6d3a3",  # selection highlight
    },
}

# Initial constants (dark); widgets are built from these, then recolored if
# the saved preference is light. Live toggling goes through apply_theme.
BG        = THEMES["dark"]["BG"]
FG        = THEMES["dark"]["FG"]
FG_DIM    = THEMES["dark"]["FG_DIM"]
ENTRY_BG  = THEMES["dark"]["ENTRY_BG"]
ENTRY_FG  = THEMES["dark"]["ENTRY_FG"]
CB_BG     = THEMES["dark"]["CB_BG"]
SEL_BG    = THEMES["dark"]["SEL_BG"]

# Color-bearing tk options we remap when switching themes.
_THEME_ATTRS = (
    "bg", "fg", "activebackground", "activeforeground", "selectcolor",
    "highlightbackground", "highlightcolor", "insertbackground",
    "selectbackground", "selectforeground",
)

def apply_theme(widget, old, new):
    """Recursively recolor a widget subtree by mapping old palette values to new."""
    mapping = {old[k]: new[k] for k in old}
    def _walk(w):
        for attr in _THEME_ATTRS:
            try:
                cur = str(w.cget(attr))
            except tk.TclError:
                continue
            if cur in mapping:
                try:
                    w.configure(**{attr: mapping[cur]})
                except tk.TclError:
                    pass
        for child in w.winfo_children():
            _walk(child)
    _walk(widget)

STATE_FILE = os.path.expanduser("~/.chatbot_launcher_state.json")

HEALTHCARE_CONTEXT = (
    "We work for an early-stage startup with the mission of accelerating "
    "health-tech adoption through exceptional sales intelligence."
)
MARKDOWN_CONTEXT = "Export response to a markdown file that can be downloaded."
TECH_STACK_CONTEXT = (
    "We use databricks hosted on AWS to ingest data and serve to customers "
    "via a web-app hosted on Aurora Postgres."
)
MVP_CONTEXT = (
    "This is for a minimum viable product (MVP) where we want a working "
    "prototype working by end of day today."
)

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {bot["name"]: True for bot in CHATBOTS}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def build_js(question, name):
    q = question.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    if name == "ChatGPT:insert":
        return f"""
(function() {{
    var el = document.querySelector("#prompt-textarea")
          || document.querySelector("div[contenteditable='true'].ProseMirror")
          || document.querySelector("textarea");
    if (!el) {{ return "not found: chatgpt input"; }}
    el.focus();
    if (el.tagName === "TEXTAREA") {{
        var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        setter.call(el, `{q}`);
        el.dispatchEvent(new Event("input", {{ bubbles: true }}));
    }} else {{
        document.execCommand("insertText", false, `{q}`);
    }}
    return "ok: text inserted into " + el.tagName;
}})();
"""

    if name == "ChatGPT:send":
        # Send in-page: dispatch a real Enter to the editor, then (if still unsent)
        # click the explicit send button. No mic-clickable heuristic.
        return """
(function() {
    var el = document.querySelector("#prompt-textarea")
          || document.querySelector("div[contenteditable='true'].ProseMirror")
          || document.querySelector("textarea");
    if (!el) { return "editor not found"; }
    function txt() { return el.value || el.textContent || ""; }
    if (!txt().trim()) { return "composer empty, not sending"; }
    el.focus();
    if (el.tagName === "TEXTAREA") {
        el.selectionStart = el.selectionEnd = el.value.length;
    } else {
        var sel = window.getSelection(), range = document.createRange();
        range.selectNodeContents(el); range.collapse(false);
        sel.removeAllRanges(); sel.addRange(range);
    }
    ["keydown", "keypress", "keyup"].forEach(function(t) {
        el.dispatchEvent(new KeyboardEvent(t, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true}));
    });
    setTimeout(function() {
        if (!txt().trim()) { return; }  // already sent
        var btn = document.querySelector('button[data-testid="send-button"]')
               || document.querySelector('button[aria-label="Send prompt"]')
               || document.querySelector('button[aria-label="Send message"]');
        if (btn && !btn.disabled) { btn.click(); }
    }, 150);
    return "enter dispatched";
})();
"""

    if name == "Claude:insert":
        return f"""
(function() {{
    var el = document.querySelector(".ProseMirror");
    if (!el) {{ return "not found: .ProseMirror"; }}
    el.focus();
    document.execCommand("insertText", false, `{q}`);
    return "ok: text inserted";
}})();
"""

    if name == "Claude:send":
        # Send in-page: dispatch a real Enter to the ProseMirror editor, then (if still
        # unsent) click the last ENABLED button in the composer. Because the composer now
        # has text, that button is the (enabled) send button, not the mic.
        return """
(function() {
    var el = document.querySelector(".ProseMirror");
    if (!el) { return "editor not found"; }
    function txt() { return el.textContent || ""; }
    if (!txt().trim()) { return "composer empty, not sending"; }
    el.focus();
    var sel = window.getSelection(), range = document.createRange();
    range.selectNodeContents(el); range.collapse(false);
    sel.removeAllRanges(); sel.addRange(range);
    ["keydown", "keypress", "keyup"].forEach(function(t) {
        el.dispatchEvent(new KeyboardEvent(t, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true}));
    });
    setTimeout(function() {
        if (!txt().trim()) { return; }  // already sent
        var btn = document.querySelector('button[aria-label="Send message"]');
        if (!(btn && !btn.disabled)) {
            // Fallback: last enabled button in the composer (= send, since text is present)
            var c = el.parentElement;
            while (c && c !== document.body) {
                var bs = Array.from(c.querySelectorAll("button:not([disabled])"));
                if (bs.length >= 2) { btn = bs[bs.length - 1]; break; }
                c = c.parentElement;
            }
        }
        if (btn && !btn.disabled) { btn.click(); }
    }, 150);
    return "enter dispatched";
})();
"""

    if name == "Gemini":
        return f"""
(function() {{
    var el = document.querySelector("rich-textarea .ql-editor");
    if (!el) {{ el = document.querySelector("div[role='textbox']"); }}
    if (!el) {{ return "not found: gemini input"; }}
    el.focus();
    document.execCommand("insertText", false, `{q}`);
    setTimeout(function() {{
        var sendBtn = document.querySelector('button[aria-label="Send message"]');
        if (sendBtn) {{ sendBtn.click(); }}
    }}, 600);
    return "ok: text inserted, send scheduled";
}})();
"""

    return ""

def check_existing_tab(domain):
    """Return True if Chrome has any tab open whose URL contains domain."""
    script = f"""
tell application "Google Chrome"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "{domain}" then
                return "true"
            end if
        end repeat
    end repeat
    return "false"
end tell
"""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() == "true"

def navigate_tab_to(domain, new_url):
    """Navigate the first matching Chrome tab to new_url (fresh chat)."""
    script = f"""
tell application "Google Chrome"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "{domain}" then
                set URL of t to "{new_url}"
                return
            end if
        end repeat
    end repeat
end tell
"""
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def open_url_in_chrome(url):
    """Open a URL as a new tab in the existing Chrome window (no new window)."""
    script = f'tell application "Google Chrome" to open location "{url}"'
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def inject_into_tab(domain, js_code, press_enter=False):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(js_code)
        js_path = f.name

    # Step 1: run JavaScript in the matching tab — search ALL windows, not just the front one
    inject_script = f"""
tell application "Google Chrome"
    set jsCode to do shell script "cat {js_path}"
    set jsResult to ""
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "{domain}" then
                set jsResult to (execute t javascript jsCode) as string
                exit repeat
            end if
        end repeat
        if jsResult is not "" then exit repeat
    end repeat
    return jsResult
end tell
"""
    r = subprocess.run(["osascript", "-e", inject_script], capture_output=True, text=True)
    os.unlink(js_path)
    print(f"{domain}: {r.stdout.strip() or r.stderr.strip() or 'no output'}")

    # Step 2 (optional): focus the tab and press Enter via a real keystroke.
    # Only do this when explicitly asked — pressing Enter on the *insert* step would
    # send the message prematurely, leaving the send step to misfire on an empty composer.
    if not press_enter:
        return

    focus_and_enter = f"""
tell application "Google Chrome"
    activate
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "{domain}" then
                set active tab index of w to (index of t)
                set index of w to 1
                exit repeat
            end if
        end repeat
    end repeat
end tell
delay 0.3
tell application "System Events"
    keystroke return
end tell
"""
    subprocess.run(["osascript", "-e", focus_and_enter], capture_output=True, text=True)

def open_chatbots(question, enabled_bots, continue_conversation=False):
    try:
        # Reuse already-open tabs; only open tabs for bots that aren't open yet.
        # When continue_conversation is set, an existing tab is left on its current
        # conversation (no reset to a fresh chat) so the message extends that thread.
        reuse_names = set()
        for bot in enabled_bots:
            if check_existing_tab(bot["domain"]):
                reuse_names.add(bot["name"])
                if continue_conversation:
                    print(f"Continuing existing conversation for {bot['domain']}")
                else:
                    navigate_tab_to(bot["domain"], bot["url"])  # reset to a fresh chat
                    print(f"Reusing existing tab for {bot['domain']} (fresh chat)")
            else:
                open_url_in_chrome(bot["url"])  # new tab in existing window, never a new window

        for bot in enabled_bots:
            is_reuse = bot["name"] in reuse_names
            wait = round(bot["wait"] * 0.6, 1) if is_reuse else bot["wait"]
            print(f"Waiting {wait}s for {bot['domain']} ({'existing' if is_reuse else 'new'} tab)...")
            time.sleep(wait)
            if bot["name"] in ("Claude", "ChatGPT"):
                # Insert text WITHOUT pressing Enter, then click the send button via JS.
                inject_into_tab(bot["domain"], build_js(question, f"{bot['name']}:insert"), press_enter=False)
                time.sleep(0.5)
                # Send via JS click (mic-guarded); hardware Enter is a safe backup since the composer has text.
                inject_into_tab(bot["domain"], build_js(question, f"{bot['name']}:send"), press_enter=True)
            else:
                # Gemini: its JS inserts + clicks send; keep the hardware-Enter backup.
                inject_into_tab(bot["domain"], build_js(question, bot["name"]), press_enter=True)

    except Exception as e:
        os.system(f'osascript -e \'display alert "Launcher error" message "{str(e)[:200]}"\'')

def launch(question, checks, healthcare_var, markdown_var, tech_stack_var, mvp_var, word_limit_var, word_count_var, continue_var, theme_var, root):
    q = question.strip()
    if not q:
        return

    if healthcare_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {HEALTHCARE_CONTEXT}"

    if markdown_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {MARKDOWN_CONTEXT}"

    if tech_stack_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {TECH_STACK_CONTEXT}"

    if mvp_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {MVP_CONTEXT}"

    if word_limit_var.get():
        # Pull the word count; fall back to 100 if user typed garbage
        raw = word_count_var.get().strip()
        try:
            n = max(1, int(raw))
        except (ValueError, TypeError):
            n = 100
        if not q.endswith("."):
            q += "."
        q += f" Limit to {n} words."

    enabled_bots = [bot for bot, var in zip(CHATBOTS, checks) if var.get()]
    if not enabled_bots:
        return

    state = {bot["name"]: var.get() for bot, var in zip(CHATBOTS, checks)}
    state["healthcare"] = healthcare_var.get()
    state["markdown"] = markdown_var.get()
    state["tech_stack"] = tech_stack_var.get()
    state["mvp"] = mvp_var.get()
    state["word_limit"] = word_limit_var.get()
    state["word_count"] = word_count_var.get()
    state["continue"] = continue_var.get()
    state["theme"] = theme_var.get()
    save_state(state)

    root.withdraw()
    t = threading.Thread(target=open_chatbots, args=(q, enabled_bots, continue_var.get()))
    t.start()


    def wait_for_thread():
        if t.is_alive():
            root.after(500, wait_for_thread)
        else:
            root.destroy()

    root.after(500, wait_for_thread)

def main():
    os.system(
        "osascript -e 'tell application \"System Events\" to set frontmost of every process "
        f"whose unix id is {os.getpid()} to true'"
    )

    state = load_state()

    root = tk.Tk()
    set_dock_icon()  # set after tkinter owns the app
    root.title("Ask the Oracle")
    root.resizable(True, True)
    root.configure(bg=BG)

    w, h = 540, 270
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2 - 80
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    tk.Label(
        root, text="✦  Ask the Oracle  ✦",
        font=("Georgia", 15, "bold"), bg=BG, fg=FG
    ).pack(pady=(14, 6))

    entry = tk.Text(
        root, font=("Georgia", 13), width=44, height=3,
        wrap="word",
        bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=FG,
        relief="flat", highlightthickness=1,
        highlightbackground=FG_DIM, highlightcolor=FG,
        selectbackground=SEL_BG, selectforeground=ENTRY_FG,
        padx=6, pady=6,
        undo=True, autoseparators=True, maxundo=100,
    )
    entry.pack(padx=18, fill=tk.BOTH, expand=True)
    entry.focus_set()

    # Flip-switch geometry, shared by the continue switch (this row) and the
    # theme switch (top-right corner) below.
    SW_W, SW_H, SW_PAD = 52, 26, 3
    SW_KNOB = SW_H - 2 * SW_PAD

    # Oracle checkboxes
    check_frame = tk.Frame(root, bg=BG)
    check_frame.pack(anchor="w", padx=14, pady=(10, 0))

    checks = []
    for bot in CHATBOTS:
        var = tk.BooleanVar(value=state.get(bot["name"], True))
        cb = tk.Checkbutton(
            check_frame, text=bot["label"], variable=var,
            font=("Georgia", 11, "italic"), bg=BG, fg=FG,
            activebackground=BG, activeforeground=FG,
            selectcolor=CB_BG, bd=0,
        )
        cb.pack(side="left", padx=6)
        checks.append(var)

    # Continue flip-switch, last item in the row (right of Gemini). Left = new
    # chat (continue_var False, knob shows →); right = continue the existing
    # conversation (continue_var True, knob shows a two-arrow loop). See open_chatbots.
    continue_var = tk.BooleanVar(value=state.get("continue", False))
    continue_switch = tk.Canvas(
        check_frame, width=SW_W, height=SW_H, bg=BG, highlightthickness=0, bd=0,
    )
    continue_switch.pack(side="left", padx=(6, 0))

    # Options, top row: most-used (healthcare context + word-limit checkbox + variable word count)
    options_top_frame = tk.Frame(root, bg=BG)
    options_top_frame.pack(anchor="w", padx=20, pady=(10, 0))

    healthcare_var = tk.BooleanVar(value=state.get("healthcare", False))
    tk.Checkbutton(
        options_top_frame, text="Healthcare Startup", variable=healthcare_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left", padx=(0, 10))

    word_limit_var = tk.BooleanVar(value=state.get("word_limit", False))
    tk.Checkbutton(
        options_top_frame, text="Limit to", variable=word_limit_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left")

    word_count_var = tk.StringVar(value=str(state.get("word_count", "100")))
    word_count_entry = tk.Entry(
        options_top_frame, textvariable=word_count_var,
        width=5, justify="center",
        font=("Georgia", 11, "italic"),
        bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=FG,
        relief="flat", highlightthickness=1,
        highlightbackground=FG_DIM, highlightcolor=FG,
        selectbackground=SEL_BG, selectforeground=ENTRY_FG,
    )
    word_count_entry.pack(side="left", padx=(4, 4))

    tk.Label(
        options_top_frame, text="words",
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
    ).pack(side="left")

    # Options, bottom row: less-used (markdown + tech stack + mvp)
    options_bottom_frame = tk.Frame(root, bg=BG)
    options_bottom_frame.pack(anchor="w", padx=20, pady=(6, 0))

    markdown_var = tk.BooleanVar(value=state.get("markdown", False))
    tk.Checkbutton(
        options_bottom_frame, text="Markdown", variable=markdown_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left", padx=(0, 10))

    tech_stack_var = tk.BooleanVar(value=state.get("tech_stack", False))
    tk.Checkbutton(
        options_bottom_frame, text="Tech Stack", variable=tech_stack_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left", padx=(0, 10))

    mvp_var = tk.BooleanVar(value=state.get("mvp", False))
    tk.Checkbutton(
        options_bottom_frame, text="MVP", variable=mvp_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left", padx=(0, 10))

    # Theme flip-switch (dark ⟷ light), overlaid in the top-right corner of the
    # window. tk has no native toggle, so it's a Canvas: a pill track with a
    # sliding gold knob carrying a ☾/☀ glyph. Widgets are built dark;
    # current_theme tracks what's live.
    theme_var = tk.StringVar(value=state.get("theme", "dark"))
    current_theme = {"name": "dark"}

    switch = tk.Canvas(
        root, width=SW_W, height=SW_H,
        bg=BG, highlightthickness=0, bd=0,
    )
    switch.place(relx=1.0, x=-14, y=14, anchor="ne")

    def _pill(c, x0, y0, x1, y1, fill):
        r = (y1 - y0) / 2
        c.create_oval(x0, y0, x0 + 2 * r, y1, fill=fill, outline=fill)
        c.create_oval(x1 - 2 * r, y0, x1, y1, fill=fill, outline=fill)
        c.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=fill)

    def render_switch():
        pal = THEMES[current_theme["name"]]
        is_light = current_theme["name"] == "light"
        switch.delete("all")
        switch.configure(bg=pal["BG"])
        _pill(switch, 1, 1, SW_W - 1, SW_H - 1, pal["ENTRY_BG"])
        kx = SW_PAD if is_light else (SW_W - SW_PAD - SW_KNOB)
        switch.create_oval(kx, SW_PAD, kx + SW_KNOB, SW_PAD + SW_KNOB,
                           fill=pal["FG"], outline=pal["FG"])
        switch.create_text(kx + SW_KNOB / 2, SW_PAD + SW_KNOB / 2 + 1,
                           text="☀" if is_light else "☾",
                           fill=pal["BG"], font=("Georgia", 10))

    def render_continue():
        pal = THEMES[current_theme["name"]]
        on = continue_var.get()  # True = continue (knob right)
        continue_switch.delete("all")
        continue_switch.configure(bg=pal["BG"])
        _pill(continue_switch, 1, 1, SW_W - 1, SW_H - 1, pal["ENTRY_BG"])
        kx = (SW_W - SW_PAD - SW_KNOB) if on else SW_PAD
        continue_switch.create_oval(kx, SW_PAD, kx + SW_KNOB, SW_PAD + SW_KNOB,
                                    fill=pal["FG"], outline=pal["FG"])
        # Glyph drawn as strokes (not text) so it takes the knob's BG color and
        # matches the theme: a two-arrow loop for continue, a plain arrow for new.
        cx, cy = kx + SW_KNOB / 2, SW_PAD + SW_KNOB / 2
        ink = pal["BG"]
        if on:
            r = 5.5
            def _arc(a0, a1):
                pts = []
                for i in range(9):
                    a = math.radians(a0 + (a1 - a0) * i / 8)
                    pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
                return pts
            continue_switch.create_line(*_arc(185, 355), fill=ink, width=2, smooth=True,
                                        arrow="last", arrowshape=(4, 5, 2), capstyle="round")
            continue_switch.create_line(*_arc(5, 175), fill=ink, width=2, smooth=True,
                                        arrow="last", arrowshape=(4, 5, 2), capstyle="round")
        else:
            continue_switch.create_line(cx - 5, cy, cx + 5, cy, fill=ink, width=2,
                                        arrow="last", arrowshape=(4, 5, 2), capstyle="round")

    def toggle_continue(event=None):
        continue_var.set(not continue_var.get())
        render_continue()
        # Persist immediately so the choice survives closing without launching.
        s = load_state()
        s["continue"] = continue_var.get()
        save_state(s)

    def toggle_theme(event=None):
        new_name = "light" if current_theme["name"] == "dark" else "dark"
        apply_theme(root, THEMES[current_theme["name"]], THEMES[new_name])
        current_theme["name"] = new_name
        theme_var.set(new_name)
        render_switch()
        render_continue()  # canvas items aren't touched by apply_theme; redraw
        # Persist immediately so the choice survives closing without launching.
        s = load_state()
        s["theme"] = new_name
        save_state(s)

    switch.bind("<Button-1>", toggle_theme)
    continue_switch.bind("<Button-1>", toggle_continue)
    render_switch()
    render_continue()

    def _launch(e=None):
        launch(entry.get("1.0", "end-1c"), checks, healthcare_var, markdown_var, tech_stack_var, mvp_var, word_limit_var, word_count_var, continue_var, theme_var, root)
        return "break"

    # Bind Cmd+Return on root so it works regardless of which widget has focus
    root.bind_all("<Command-Return>", _launch)
    entry.bind("<Escape>", lambda e: root.destroy())
    word_count_entry.bind("<Escape>", lambda e: root.destroy())

    # macOS-style editing shortcuts (Tk on macOS doesn't wire these up by default for Text)
    def _del_range(widget, start, end):
        if widget.compare(start, "!=", end):
            widget.delete(start, end)
        return "break"

    def _has_selection(widget):
        return bool(widget.tag_ranges("sel"))

    # Cmd+Backspace: delete from cursor to start of visible line
    def _cmd_backspace(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert linestart", "insert")

    # Option+Backspace: delete previous word
    def _opt_backspace(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert-1c wordstart", "insert")

    # Cmd+Delete (forward): delete to end of line
    def _cmd_delete(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert", "insert lineend")

    # Option+Delete (forward): delete next word
    def _opt_delete(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert", "insert wordend")

    # Cursor movement
    def _move(widget, index, select):
        if select:
            if not _has_selection(widget):
                widget.tag_add("sel", "insert")
            widget.mark_set("anchor", widget.index("sel.first") if _has_selection(widget) else "insert")
        widget.mark_set("insert", index)
        widget.see("insert")
        if not select:
            widget.tag_remove("sel", "1.0", "end")
        return "break"

    def _cmd_left(e):  return _move(e.widget, "insert linestart", False)
    def _cmd_right(e): return _move(e.widget, "insert lineend", False)
    def _opt_left(e):  return _move(e.widget, "insert-1c wordstart", False)
    def _opt_right(e): return _move(e.widget, "insert wordend", False)

    def _select_all(e):
        e.widget.tag_add("sel", "1.0", "end-1c")
        e.widget.mark_set("insert", "end-1c")
        return "break"

    # Cmd+Z / Cmd+Shift+Z: undo/redo (Tk's Text undo stack, enabled above)
    def _undo(e):
        try:
            e.widget.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def _redo(e):
        try:
            e.widget.edit_redo()
        except tk.TclError:
            pass
        return "break"

    for seq, fn in [
        ("<Command-BackSpace>", _cmd_backspace),
        ("<Option-BackSpace>",  _opt_backspace),
        ("<Command-Delete>",    _cmd_delete),
        ("<Option-Delete>",     _opt_delete),
        ("<Command-Left>",      _cmd_left),
        ("<Command-Right>",     _cmd_right),
        ("<Option-Left>",       _opt_left),
        ("<Option-Right>",      _opt_right),
        ("<Command-a>",         _select_all),
        ("<Command-A>",         _select_all),
        ("<Command-z>",         _undo),
        ("<Command-Z>",         _undo),
        ("<Command-Shift-z>",   _redo),
        ("<Command-Shift-Z>",   _redo),
    ]:
        entry.bind(seq, fn)

    tk.Label(
        root, text="⟡  ⌘↩ to consult  ·  Esc to withdraw  ⟡",
        font=("Georgia", 9, "italic"), bg=BG, fg=FG_DIM,
    ).pack(pady=(6, 10))

    # Apply the saved theme now that every widget exists (build palette is dark).
    if theme_var.get() != current_theme["name"]:
        toggle_theme()

    root.mainloop()

if __name__ == "__main__":
    main()
