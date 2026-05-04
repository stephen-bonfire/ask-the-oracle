import tkinter as tk
import threading
import subprocess
import tempfile
import json
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
    {"name": "ChatGPT", "label": "ChatGPT",       "url": "https://chatgpt.com",       "domain": "chatgpt.com",       "wait": 5.0},
    {"name": "Claude",  "label": "Claude",        "url": "https://claude.ai/new",      "domain": "claude.ai",         "wait": 5.0},
    {"name": "Gemini",  "label": "Gemini",         "url": "https://gemini.google.com",  "domain": "gemini.google.com", "wait": 6.0},
]

BG        = "#0e0b1a"   # deep space purple
FG        = "#d4a843"   # oracle gold
FG_DIM    = "#7a6030"   # muted gold
ENTRY_BG  = "#1c1530"   # dark violet
ENTRY_FG  = "#f0e0b0"   # parchment
CB_BG     = "#160f28"   # slightly lighter than bg for checkboxes
SEL_BG    = "#2e1f5e"   # selection highlight

STATE_FILE = os.path.expanduser("~/.chatbot_launcher_state.json")

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

    if name == "ChatGPT":
        return f"""
(function() {{
    var el = document.querySelector("#prompt-textarea");
    if (!el) {{ return "not found: #prompt-textarea"; }}
    el.focus();
    if (el.tagName === "TEXTAREA") {{
        var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        setter.call(el, `{q}`);
        el.dispatchEvent(new Event("input", {{ bubbles: true }}));
    }} else {{
        document.execCommand("insertText", false, `{q}`);
    }}
    setTimeout(function() {{
        el.dispatchEvent(new KeyboardEvent("keydown", {{
            key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true
        }}));
    }}, 600);
    return "ok: text inserted, enter scheduled";
}})();
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
        return """
(function() {
    // Walk up from the editor to find its form/composer container, then get the last button
    var editor = document.querySelector(".ProseMirror");
    if (!editor) { return "editor not found"; }
    var container = editor.parentElement;
    while (container && container !== document.body) {
        var btns = Array.from(container.querySelectorAll("button:not([disabled])"));
        if (btns.length >= 2) {
            // The send button is the last enabled button in the composer
            var sendBtn = btns[btns.length - 1];
            sendBtn.click();
            return "clicked: aria=" + (sendBtn.getAttribute("aria-label") || "none") + " class=" + sendBtn.className.substring(0, 50);
        }
        container = container.parentElement;
    }
    return "send button not found";
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

def inject_into_tab(domain, js_code):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(js_code)
        js_path = f.name

    # Step 1: inject text via JavaScript
    inject_script = f"""
tell application "Google Chrome"
    set jsCode to do shell script "cat {js_path}"
    set jsResult to ""
    repeat with t in tabs of front window
        if URL of t contains "{domain}" then
            set jsResult to (execute t javascript jsCode) as string
            exit repeat
        end if
    end repeat
    return jsResult
end tell
"""
    r = subprocess.run(["osascript", "-e", inject_script], capture_output=True, text=True)
    os.unlink(js_path)
    print(f"{domain}: {r.stdout.strip() or r.stderr.strip() or 'no output'}")

    # Step 2: bring that tab into focus and press Enter via real keystroke
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

def open_chatbots(question, enabled_bots):
    try:
        urls = [bot["url"] for bot in enabled_bots]
        subprocess.Popen([
            "open", "-na", "Google Chrome", "--args", "--new-window"
        ] + urls)

        for bot in enabled_bots:
            print(f"Waiting {bot['wait']}s for {bot['domain']}...")
            time.sleep(bot["wait"])
            if bot["name"] == "Claude":
                js = build_js(question, "Claude:insert")
                inject_into_tab(bot["domain"], js)
                time.sleep(1.0)
                js2 = build_js(question, "Claude:send")
                inject_into_tab(bot["domain"], js2)
            else:
                js = build_js(question, bot["name"])
                inject_into_tab(bot["domain"], js)

    except Exception as e:
        os.system(f'osascript -e \'display alert "Launcher error" message "{str(e)[:200]}"\'')

def launch(question, checks, word_limit_var, root):
    q = question.strip()
    if not q:
        return

    if word_limit_var.get():
        if not q.endswith("."):
            q += "."
        q += " Limit to 100 words."

    enabled_bots = [bot for bot, var in zip(CHATBOTS, checks) if var.get()]
    if not enabled_bots:
        return

    state = {bot["name"]: var.get() for bot, var in zip(CHATBOTS, checks)}
    state["word_limit"] = word_limit_var.get()
    save_state(state)

    root.withdraw()
    t = threading.Thread(target=open_chatbots, args=(q, enabled_bots))
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

    w, h = 500, 230
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
    )
    entry.pack(padx=18, fill=tk.BOTH, expand=True)
    entry.focus_set()

    # Oracle checkboxes
    check_frame = tk.Frame(root, bg=BG)
    check_frame.pack(anchor="w", padx=14, pady=(8, 0))

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

    # Word limit checkbox
    word_limit_var = tk.BooleanVar(value=state.get("word_limit", False))
    tk.Checkbutton(
        root, text="Limit to 100 words", variable=word_limit_var,
        font=("Georgia", 10, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(anchor="w", padx=20, pady=(4, 0))

    entry.bind("<Command-Return>", lambda e: (launch(entry.get("1.0", "end-1c"), checks, word_limit_var, root), "break")[1])
    entry.bind("<Escape>", lambda e: root.destroy())

    tk.Label(
        root, text="⟡  ⌘↩ to consult  ·  Esc to withdraw  ⟡",
        font=("Georgia", 9, "italic"), bg=BG, fg=FG_DIM,
    ).pack(pady=(6, 10))

    root.mainloop()

if __name__ == "__main__":
    main()
