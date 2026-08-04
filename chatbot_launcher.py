import tkinter as tk
import threading
import subprocess
import tempfile
import json
import math
import time
import os
import uuid
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

# Effort level -> the exact label each site's in-page model picker shows for that
# choice. ChatGPT now nests Light/Medium/High under an Effort submenu in the
# composer model picker; Claude needs "More models" for Opus/Sonnet; Gemini
# lists Flash/Thinking/Pro with no submenu.
EFFORT_MODELS = {
    "ChatGPT": {"high": "High",      "medium": "Medium",        "low": "Light"},
    "Claude":  {"high": "Opus 5",    "medium": "Sonnet 5",       "low": "Haiku 4.5"},
    "Gemini":  {"high": "Pro",       "medium": "Thinking",       "low": "Flash"},
}
EFFORT_LEVELS = ["low", "medium", "high"]

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
TECH_STACK_CONTEXT = (
    "We use databricks hosted on AWS to ingest data and serve to customers "
    "via a web-app hosted on Aurora Postgres. The developers all work from "
    "local environments on apple macbooks."
)
POC_CONTEXT = (
    "This is a throwaway proof-of-concept that needs to be running in under "
    "30 minutes — 1 hour absolute max. Do the simplest thing that works: "
    "single file if possible, hardcode where reasonable, minimal "
    "dependencies. Skip auth, tests, error handling, config, and abstractions "
    "unless they're essential to demonstrate the core idea. Getting a working "
    "version running now beats doing it \"right.\""
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


def save_launch_state(checks, healthcare_var, tech_stack_var, poc_var, word_limit_var,
                      word_count_var, continue_var, effort_var, theme_var):
    """Persist the current launch settings for either prompt action."""
    state = {bot["name"]: var.get() for bot, var in zip(CHATBOTS, checks)}
    state["healthcare"] = healthcare_var.get()
    state["tech_stack"] = tech_stack_var.get()
    state["poc"] = poc_var.get()
    state["word_limit"] = word_limit_var.get()
    state["word_count"] = word_count_var.get()
    state["continue"] = continue_var.get()
    state["effort"] = effort_var.get()
    state["theme"] = theme_var.get()
    save_state(state)

# Regex (as a JS literal) used to find each site's model-picker trigger button,
# independent of which model is currently selected (so it works no matter what
# was picked last time). Confirmed against the live DOM for each site.
_MODEL_BUTTON_RE = {
    "ChatGPT": "/Instant|Medium|High|Pro|GPT-5/",
    "Claude":  "/Haiku|Sonnet|Opus|Fable/",
    "Gemini":  "/Flash|Thinking|Pro/",
}

def build_js(question, name, extra=None):
    q = question.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    label = (extra or "").replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    if name.endswith(":openModel"):
        bot = name.split(":")[0]
        re_literal = _MODEL_BUTTON_RE.get(bot, "/(?!)/")  # never matches if bot unknown
        return f"""
(function() {{
    function fire(el) {{
        ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(function(t) {{
            el.dispatchEvent(new MouseEvent(t, {{bubbles: true, cancelable: true, view: window}}));
        }});
    }}
    if (`{bot}` === "ChatGPT") {{
        var editor = document.querySelector("#prompt-textarea")
                  || document.querySelector("div[contenteditable='true'].ProseMirror")
                  || document.querySelector("textarea");
        var form = editor && editor.closest("form");
        var scoped = form && Array.from(form.querySelectorAll('button[aria-haspopup="menu"]')).find(function(x) {{
            return x.textContent.trim().length > 0;
        }});
        if (scoped) {{ fire(scoped); return "opened"; }}
    }}
    if (`{bot}` === "Gemini") {{
        var existingGeminiMenu = Array.from(document.querySelectorAll('[role=menuitem],[role=option]')).find(function(x) {{
            return /Flash|Thinking|Pro/.test(x.textContent || "");
        }});
        if (existingGeminiMenu) {{ return "opened"; }}
        var geminiEditor = document.querySelector("rich-textarea .ql-editor")
                        || document.querySelector("div[role='textbox']");
        var c = geminiEditor && geminiEditor.parentElement;
        while (c && c !== document.body) {{
            var mode = Array.from(c.querySelectorAll("button")).find(function(x) {{
                return (x.getAttribute("aria-label") || "").includes("Open mode picker");
            }});
            if (mode) {{ mode.click(); return "opened"; }}
            c = c.parentElement;
        }}
    }}
    var re = {re_literal};
    var b = Array.from(document.querySelectorAll('button[aria-haspopup]')).find(function(x) {{
        return re.test(x.textContent) && x.textContent.trim().length < 40;
    }});
    if (!b) {{ return "notfound"; }}
    fire(b);
    return "opened";
}})();
"""

    if name.endswith(":pickModel"):
        # Generic across all three sites: click the menu item whose text contains
        # the target label. If not present at this level, Claude's models hide
        # behind a "More models" submenu — click that and let the caller retry.
        bot = name.split(":")[0]
        return f"""
(function() {{
    var items = Array.from(document.querySelectorAll('[role=menuitem],[role=menuitemradio],[role=menuitemcheckbox],[role=option]'));
    function fire(el) {{
        ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(function(t) {{
            el.dispatchEvent(new MouseEvent(t, {{bubbles: true, cancelable: true, view: window}}));
        }});
        // Gemini and Claude's nested pickers require a native click to commit
        // the selection or open a submenu.
        if (typeof el.click === "function") {{ el.click(); }}
    }}
    function text(el) {{ return el.textContent.trim().replace(/\\s+/g, " "); }}
    var target = items.find(function(i) {{
        var role = i.getAttribute("role");
        return (role === "menuitem" || role === "menuitemradio" || role === "option") && text(i) === `{label}`;
    }}) || items.find(function(i) {{
        var role = i.getAttribute("role");
        return (role === "menuitem" || role === "menuitemradio" || role === "option") && text(i).includes(`{label}`);
    }}) || items.find(function(i) {{
        return text(i) === `{label}`;
    }});
    if (target) {{ fire(target); return "selected"; }}
    var more = items.find(function(i) {{ return i.textContent.includes("More models"); }});
    if (more) {{ more.click(); return "submenu"; }}
    var effort = `{bot}` === "ChatGPT" && items.find(function(i) {{ return text(i).includes("Effort"); }});
    if (effort) {{ effort.click(); return "submenu"; }}
    return "notfound";
}})();
"""

    if name.endswith(":currentModel"):
        bot = name.split(":")[0]
        re_literal = _MODEL_BUTTON_RE.get(bot, "/(?!)/")  # never matches if bot unknown
        return f"""
(function() {{
    if (`{bot}` === "Gemini") {{
        var button = Array.from(document.querySelectorAll("button")).find(function(x) {{
            return (x.getAttribute("aria-label") || "").includes("Open mode picker");
        }});
        return button ? button.textContent.trim().replace(/\\s+/g, " ") : "";
    }}
    var re = {re_literal};
    var b = Array.from(document.querySelectorAll('button[aria-haspopup]')).find(function(x) {{
        return re.test(x.textContent) && x.textContent.trim().length < 40;
    }});
    return b ? b.textContent.trim().replace(/\\s+/g, " ") : "";
}})();
"""

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
        # Send in-page: click the real send button, polling while ChatGPT
        # finishes any model-switch UI transition.
        return """
(function() {
    var el = document.querySelector("#prompt-textarea")
          || document.querySelector("div[contenteditable='true'].ProseMirror")
          || document.querySelector("textarea");
    if (!el) { return "editor not found"; }
    function txt() { return el.value || el.textContent || ""; }
    if (!txt().trim()) { return "composer empty, not sending"; }
    function clickSend() {
        // A model switch can leave stale composer controls in the document.
        // Resolve the button from the active editor's form, not page-wide.
        var form = el.closest("form");
        var btn = form && (
            form.querySelector('button[data-testid="send-button"]')
            || form.querySelector('button[aria-label="Send prompt"]')
            || form.querySelector('button[aria-label="Send message"]')
        );
        if (!(btn && !btn.disabled)) { return false; }
        btn.click();
        return true;
    }
    el.focus();
    if (el.tagName === "TEXTAREA") {
        el.selectionStart = el.selectionEnd = el.value.length;
    } else {
        var sel = window.getSelection(), range = document.createRange();
        range.selectNodeContents(el); range.collapse(false);
        sel.removeAllRanges(); sel.addRange(range);
    }
    var attempts = 0;
    function attemptSend() {
        attempts += 1;
        if (!txt().trim() || attempts > 4) {
            clearInterval(timer);
            return;
        }
        clickSend();
    }
    // A fresh ChatGPT composer can rehydrate immediately after a model change.
    // Keep trying only while the prompt remains, so a successful send is never
    // duplicated.
    var timer = setInterval(attemptSend, 750);
    attemptSend();
    return "send polling";
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

    if name == "Gemini:insertOnly":
        return f"""
(function() {{
    var el = document.querySelector("rich-textarea .ql-editor");
    if (!el) {{ el = document.querySelector("div[role='textbox']"); }}
    if (!el) {{ return "not found: gemini input"; }}
    el.focus();
    document.execCommand("insertText", false, `{q}`);
    return "ok: text inserted, not sent";
}})();
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

    if name == "Gemini:send":
        return """
(function() {
    var el = document.querySelector("rich-textarea .ql-editor")
          || document.querySelector("div[role='textbox']");
    if (!el) { return "editor not found"; }
    function txt() { return el.textContent || el.value || ""; }
    if (!txt().trim()) { return "composer empty, not sending"; }
    function clickSend() {
        // Gemini renders the accessible label on the nested button only after
        // text input enables the send control.
        var btn = document.querySelector('div[data-test-id="send-button-container"] button')
               || document.querySelector('button[aria-label="Send message"]');
        if (!(btn && !btn.disabled)) { return false; }
        btn.click();
        return true;
    }
    if (clickSend()) { return "send clicked"; }
    var attempts = 0;
    var timer = setInterval(function() {
        attempts += 1;
        if (!txt().trim() || clickSend() || attempts >= 12) {
            clearInterval(timer);
        }
    }, 250);
    return "send polling";
})();
"""

    if name == "Claude:closeModel":
        return """
(function() {
    var openMenu = Array.from(document.querySelectorAll('[role="menu"]')).find(function(menu) {
        return !menu.hasAttribute("data-closed");
    });
    return openMenu ? "ready to close" : "already closed";
})();
"""

    if name.endswith(":locateCopyPreviousResponse"):
        # These are the response-level copy controls observed in the live sites.
        # Selecting the final matching control skips code-block copy buttons.
        bot = name.split(":")[0]
        if bot == "ChatGPT":
            selector = "Array.from(document.querySelectorAll('button[data-testid=copy-turn-action-button][aria-label=\\\"Copy response\\\"]'))"
        elif bot == "Claude":
            selector = "Array.from(document.querySelectorAll('button[data-testid=action-bar-copy][aria-label=Copy]'))"
        else:
            selector = "Array.from(document.querySelectorAll('button[aria-label=Copy]'))"
        return f"""
(function() {{
    var buttons = {selector};
    var button = buttons[buttons.length - 1];
    if (!button) {{ return "not found"; }}
    button.scrollIntoView({{block: "center", inline: "center"}});
    var rect = button.getBoundingClientRect();
    return [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
        Math.round(window.innerHeight),
    ].join(",");
}})();
"""

    if name.endswith(":extractPreviousResponse"):
        # Clipboard writes require a trusted browser click. If macOS blocks that
        # automation, use the same response-level control to locate the message
        # container and preserve the button's "latest assistant response" meaning.
        bot = name.split(":")[0]
        if bot == "ChatGPT":
            button_selector = "button[data-testid=copy-turn-action-button][aria-label=\\\"Copy response\\\"]"
            container_selector = "section"
        elif bot == "Claude":
            button_selector = "button[data-testid=action-bar-copy][aria-label=Copy]"
            container_selector = "[role=article]"
        else:
            button_selector = "button[aria-label=Copy]"
            container_selector = "response-container"
        return f"""
(function() {{
    var buttons = Array.from(document.querySelectorAll('{button_selector}'));
    var button = buttons[buttons.length - 1];
    var container = button && button.closest('{container_selector}');
    return container ? container.innerText.trim() : "";
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

def inject_into_tab(domain, js_code, press_enter=False, log_result=True, key_code=None):
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
    result = r.stdout.strip() or r.stderr.strip() or "no output"
    if log_result:
        print(f"{domain}: {result}")

    # Step 2 (optional): focus the tab and send a trusted macOS keypress.
    # Enter is explicitly opt-in so inserting text never sends prematurely.
    if press_enter:
        key_code = 36
    if key_code is None:
        return result

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
delay 0.5
tell application "System Events"
    key code {key_code}
end tell
"""
    subprocess.run(["osascript", "-e", focus_and_enter], capture_output=True, text=True)
    return result

def select_model(bot, effort):
    """Open the site's model picker and click the item mapped to `effort`.

    Returns True if the model is confirmed selected, False if the picker button
    or matching menu item couldn't be found (site UI changed) — the caller then
    leaves the prompt pasted but unsent so the user can pick a model manually.
    """
    label = EFFORT_MODELS.get(bot["name"], {}).get(effort)
    if not label:
        return True

    domain = bot["domain"]
    if bot["name"] == "Gemini":
        current = inject_into_tab(domain, build_js("", f"{bot['name']}:currentModel"), log_result=False)
        if label in current:
            return True

    opened = inject_into_tab(domain, build_js("", f"{bot['name']}:openModel"))
    if opened != "opened":
        print(f"{domain}: model picker button not found")
        return False

    time.sleep(0.5)
    result = inject_into_tab(domain, build_js("", f"{bot['name']}:pickModel", extra=label))
    if result == "submenu":
        time.sleep(0.5)
        result = inject_into_tab(domain, build_js("", f"{bot['name']}:pickModel", extra=label))

    if result != "selected":
        print(f"{domain}: could not select model \"{label}\"")
        return False

    if bot["name"] == "Claude":
        # Claude completes the selection after its click handler returns. A real
        # Escape after that transition dismisses the visual picker reliably.
        time.sleep(0.35)
        inject_into_tab(
            domain, build_js("", "Claude:closeModel"), log_result=False, key_code=53,
        )

    if bot["name"] == "Gemini":
        for _ in range(10):
            time.sleep(0.25)
            current = inject_into_tab(domain, build_js("", f"{bot['name']}:currentModel"), log_result=False)
            if label in current:
                return True
        print(f"{domain}: selected \"{label}\" but current mode is \"{current}\"")
        return False

    time.sleep(0.8 if bot["name"] == "ChatGPT" and effort == "high" else 0.3)
    return True


def clipboard_text():
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def set_clipboard_text(value):
    subprocess.run(["pbcopy"], input=value, text=True, check=True)


def click_tab_point(domain, x, y, viewport_height):
    """Focus the first matching Chrome tab and click a viewport-relative point."""
    click_script = f"""
tell application "Google Chrome"
    repeat with w in windows
        set tabIndex to 0
        repeat with t in tabs of w
            set tabIndex to tabIndex + 1
            if URL of t contains "{domain}" then
                set active tab index of w to tabIndex
                set index of w to 1
                activate
                set windowBounds to bounds of w
                set screenX to (item 1 of windowBounds) + {x}
                set screenY to (item 4 of windowBounds) - {viewport_height} + {y}
                delay 0.2
                tell application "System Events" to click at {{screenX, screenY}}
                return
            end if
        end repeat
    end repeat
end tell
"""
    result = subprocess.run(["osascript", "-e", click_script], capture_output=True, text=True)
    if result.returncode:
        print(f"{domain}: could not click copy control ({result.stderr.strip()})")
        return False
    return True


def copy_previous_response(bot):
    """Click the site's latest response copy control and return the copied text."""
    sentinel = f"ask-the-oracle-{uuid.uuid4()}"
    set_clipboard_text(sentinel)
    location = inject_into_tab(bot["domain"], build_js("", f"{bot['name']}:locateCopyPreviousResponse"))
    try:
        x, y, viewport_height = (int(value) for value in location.split(","))
    except ValueError:
        print(f"{bot['domain']}: response copy control not found ({location})")
        return ""
    if not click_tab_point(bot["domain"], x, y, viewport_height):
        return ""

    # The browser copy control writes to the macOS pasteboard after its click handler.
    for _ in range(10):
        time.sleep(0.15)
        copied = clipboard_text()
        if copied != sentinel:
            return copied.strip()

    print(f"{bot['domain']}: copy control did not update the clipboard; reading linked response")
    return inject_into_tab(
        bot["domain"], build_js("", f"{bot['name']}:extractPreviousResponse"), log_result=False,
    )


def combined_responses_prompt(instruction, responses):
    """Build the synthesis prompt, preserving the user's instruction first."""
    sections = "\n\n".join(
        f"## {bot_name}\n\n{response}" for bot_name, response in responses
    )
    instruction = instruction.strip()
    instruction_prefix = f"{instruction}\n\n" if instruction else ""
    return (
        f"{instruction_prefix}Here are the responses from three different chatbots:\n\n"
        f"{sections}"
    )


def apply_prompt_settings(question, healthcare_var, tech_stack_var, poc_var, word_limit_var, word_count_var):
    """Append the enabled prompt context options to a message."""
    q = question
    if healthcare_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {HEALTHCARE_CONTEXT}"

    if tech_stack_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {TECH_STACK_CONTEXT}"

    if poc_var.get():
        if not q.endswith("."):
            q += "."
        q += f" {POC_CONTEXT}"

    if word_limit_var.get():
        # Pull the word count; fall back to 100 if user typed garbage.
        raw = word_count_var.get().strip()
        try:
            n = max(1, int(raw))
        except (ValueError, TypeError):
            n = 100
        if not q.endswith("."):
            q += "."
        q += f" Limit to {n} words."

    return q


def open_chatbots(question, enabled_bots, effort="medium", continue_conversation=False):
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
            # A continued conversation can reuse its ready composer, but navigating
            # an existing tab to a fresh chat needs the full site load time.
            wait = round(bot["wait"] * 0.6, 1) if is_reuse and continue_conversation else bot["wait"]
            print(f"Waiting {wait}s for {bot['domain']} ({'existing' if is_reuse else 'new'} tab)...")
            time.sleep(wait)
            model_ok = select_model(bot, effort)
            if bot["name"] in ("Claude", "ChatGPT"):
                # Insert text WITHOUT pressing Enter, then click the send button via JS.
                inject_into_tab(bot["domain"], build_js(question, f"{bot['name']}:insert"), press_enter=False)
                if model_ok:
                    time.sleep(0.5)
                    # ChatGPT's send routine already clicks/polls the send button; a later hardware Enter can submit a duplicate.
                    inject_into_tab(
                        bot["domain"], build_js(question, f"{bot['name']}:send"),
                        press_enter=(bot["name"] == "Claude"),
                    )
                else:
                    print(f"{bot['domain']}: leaving prompt unsent (model selection failed)")
            else:
                # Gemini enables its send button asynchronously, so insert first and
                # let its in-page send routine poll and click the actual control.
                if model_ok:
                    inject_into_tab(bot["domain"], build_js(question, "Gemini:insertOnly"), press_enter=False)
                    time.sleep(0.5)
                    inject_into_tab(bot["domain"], build_js(question, "Gemini:send"), press_enter=False)
                else:
                    inject_into_tab(bot["domain"], build_js(question, "Gemini:insertOnly"), press_enter=False)
                    print(f"{bot['domain']}: leaving prompt unsent (model selection failed)")

    except Exception as e:
        os.system(f'osascript -e \'display alert "Launcher error" message "{str(e)[:200]}"\'')

def launch(question, checks, healthcare_var, tech_stack_var, poc_var, word_limit_var, word_count_var, continue_var, effort_var, theme_var, root):
    q = question.strip()
    if not q:
        return

    q = apply_prompt_settings(
        q, healthcare_var, tech_stack_var, poc_var, word_limit_var, word_count_var,
    )

    enabled_bots = [bot for bot, var in zip(CHATBOTS, checks) if var.get()]
    if not enabled_bots:
        return

    save_launch_state(
        checks, healthcare_var, tech_stack_var, poc_var, word_limit_var,
        word_count_var, continue_var, effort_var, theme_var,
    )

    root.withdraw()
    t = threading.Thread(target=open_chatbots, args=(q, enabled_bots, effort_var.get(), continue_var.get()))
    t.start()


    def wait_for_thread():
        if t.is_alive():
            root.after(500, wait_for_thread)
        else:
            root.destroy()

    root.after(500, wait_for_thread)


def launch_combined_responses(instruction, checks, healthcare_var, tech_stack_var, poc_var,
                              word_limit_var, word_count_var, continue_var, effort_var, theme_var, root):
    """Copy each open bot's latest response, then send the combined prompt onward."""
    enabled_bots = [bot for bot, var in zip(CHATBOTS, checks) if var.get()]
    if not enabled_bots:
        return

    save_launch_state(
        checks, healthcare_var, tech_stack_var, poc_var, word_limit_var,
        word_count_var, continue_var, effort_var, theme_var,
    )
    root.withdraw()
    keep_open = {"value": False}

    def copy_and_launch():
        original_clipboard = clipboard_text()
        try:
            responses = []
            for bot in CHATBOTS:
                if not check_existing_tab(bot["domain"]):
                    print(f"{bot['domain']}: no open chat to copy")
                    continue
                response = copy_previous_response(bot)
                if response:
                    responses.append((bot["name"], response))

            if not responses:
                keep_open["value"] = True

                def show_copy_error():
                    root.deiconify()
                    os.system(
                        "osascript -e 'display alert \"No responses copied\" "
                        "message \"Open a completed ChatGPT, Claude, or Gemini response and try again.\"'"
                    )

                root.after(0, show_copy_error)
                return

            prompt = apply_prompt_settings(
                combined_responses_prompt(instruction, responses), healthcare_var, tech_stack_var, poc_var,
                word_limit_var, word_count_var,
            )
            open_chatbots(prompt, enabled_bots, effort_var.get(), continue_var.get())
        finally:
            set_clipboard_text(original_clipboard)

    t = threading.Thread(target=copy_and_launch)
    t.start()

    def wait_for_thread():
        if t.is_alive():
            root.after(500, wait_for_thread)
        elif keep_open["value"]:
            return
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

    w, h = 540, 330
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2 - 80
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.lift()
    root.focus_force()

    tk.Label(
        root, text="✦  Ask the Oracle  ✦",
        font=("Georgia", 15, "bold"), bg=BG, fg=FG
    ).pack(pady=(14, 6))

    entry = tk.Text(
        root, font=("Georgia", 13), width=44, height=5,
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

    synthesize_button = tk.Canvas(
        check_frame, width=94, height=SW_H, bg=BG, highlightthickness=0, bd=0,
    )
    synthesize_button.pack(side="left", padx=(18, 0))

    # Effort selector: one global Low/Medium/High choice, translated per-site to a
    # model via EFFORT_MODELS before the prompt is sent (see select_model()).
    effort_frame = tk.Frame(root, bg=BG)
    effort_frame.pack(anchor="w", padx=14, pady=(6, 0))

    tk.Label(
        effort_frame, text="Effort:",
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
    ).pack(side="left", padx=(0, 6))

    effort_var = tk.StringVar(value=state.get("effort", "medium"))
    for level in EFFORT_LEVELS:
        tk.Radiobutton(
            effort_frame, text=level.capitalize(), value=level, variable=effort_var,
            font=("Georgia", 11, "italic"), bg=BG, fg=FG,
            activebackground=BG, activeforeground=FG,
            selectcolor=CB_BG, bd=0,
        ).pack(side="left", padx=(0, 8))

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

    # Options, bottom row: less-used context.
    options_bottom_frame = tk.Frame(root, bg=BG)
    options_bottom_frame.pack(anchor="w", padx=20, pady=(6, 0))

    tech_stack_var = tk.BooleanVar(value=state.get("tech_stack", False))
    tk.Checkbutton(
        options_bottom_frame, text="Tech Stack", variable=tech_stack_var,
        font=("Georgia", 11, "italic"), bg=BG, fg=FG_DIM,
        activebackground=BG, activeforeground=FG,
        selectcolor=CB_BG, bd=0,
    ).pack(side="left", padx=(0, 10))

    poc_var = tk.BooleanVar(value=state.get("poc", False))
    tk.Checkbutton(
        options_bottom_frame, text="POC", variable=poc_var,
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

    def render_synthesize():
        pal = THEMES[current_theme["name"]]
        synthesize_button.delete("all")
        synthesize_button.configure(bg=pal["BG"])
        _pill(synthesize_button, 0, 0, 94, SW_H, pal["FG_DIM"])
        _pill(synthesize_button, 1, 1, 93, SW_H - 1, pal["ENTRY_BG"])
        synthesize_button.create_text(
            47, SW_H / 2 + 1, text="Collect", fill=pal["FG"],
            font=("Georgia", 10, "italic"),
        )

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
        render_synthesize()
        # Persist immediately so the choice survives closing without launching.
        s = load_state()
        s["theme"] = new_name
        save_state(s)

    switch.bind("<Button-1>", toggle_theme)
    continue_switch.bind("<Button-1>", toggle_continue)
    render_switch()
    render_continue()
    render_synthesize()

    def _launch(e=None):
        launch(
            entry.get("1.0", "end-1c"), checks, healthcare_var, tech_stack_var, poc_var,
            word_limit_var, word_count_var, continue_var, effort_var, theme_var, root,
        )
        return "break"

    def _launch_combined_responses():
        launch_combined_responses(
            entry.get("1.0", "end-1c"), checks, healthcare_var, tech_stack_var, poc_var,
            word_limit_var, word_count_var, continue_var, effort_var, theme_var, root,
        )

    synthesize_button.bind("<Button-1>", lambda event: _launch_combined_responses())

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

    # Cmd+Backspace: delete from cursor to start of visible (wrapped) line.
    # "insert linestart" is the LOGICAL line (back to the last real \n), which
    # spans every wrapped line in a paragraph; "display linestart" is the
    # actual on-screen line, which is what Cmd+Backspace should respect.
    def _cmd_backspace(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert display linestart", "insert")

    # Tk's "wordstart"/"wordend" treat a run of whitespace as its own word, so
    # from a position right at a word boundary they only cross the whitespace
    # gap, not the next word too. Skip whitespace first so one stroke always
    # clears a full word, matching macOS's native word-jump behavior.
    def _word_start_index(widget, idx):
        while True:
            prev = widget.index(f"{idx}-1c")
            if widget.compare(prev, "==", idx) or not widget.get(prev).isspace():
                break
            idx = prev
        # wordstart looks at the character to the RIGHT of the index, so use
        # idx-1c (the char we just confirmed is non-whitespace) as the anchor.
        return widget.index(f"{idx}-1c wordstart")

    def _word_end_index(widget, idx):
        while True:
            ch = widget.get(idx)
            if not ch or not ch.isspace():
                break
            idx = widget.index(f"{idx}+1c")
        return widget.index(f"{idx} wordend")

    # Paragraph jump (Option+Up/Down): paragraphs here are delimited by real
    # newlines (Tk's "linestart"/"lineend", the logical rather than display
    # line). If already at the paragraph boundary, hop to the next one.
    def _para_start_index(widget, idx):
        ls = widget.index(f"{idx} linestart")
        if widget.compare(idx, "!=", ls):
            return ls
        prev = widget.index(f"{idx}-1c")
        return ls if widget.compare(prev, "==", idx) else widget.index(f"{prev} linestart")

    def _para_end_index(widget, idx):
        le = widget.index(f"{idx} lineend")
        if widget.compare(idx, "!=", le):
            return le
        nxt = widget.index(f"{idx}+1c")
        return le if widget.compare(nxt, "==", idx) else widget.index(f"{nxt} lineend")

    # Option+Backspace: delete previous word
    def _opt_backspace(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, _word_start_index(e.widget, "insert"), "insert")

    # Cmd+Delete (forward): delete to end of visible (wrapped) line
    def _cmd_delete(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert", "insert display lineend")

    # Option+Delete (forward): delete next word
    def _opt_delete(e):
        if _has_selection(e.widget):
            e.widget.delete("sel.first", "sel.last")
            return "break"
        return _del_range(e.widget, "insert", _word_end_index(e.widget, "insert"))

    # Cursor movement. With select=True, extends the "sel" tag between a
    # persistent "anchor" mark (set fresh only when no selection is active)
    # and the new insert position, so repeated shift-jumps grow/shrink the
    # same selection instead of resetting its start each time.
    def _move(widget, index, select):
        if select:
            if not _has_selection(widget):
                widget.mark_set("anchor", "insert")
            widget.mark_set("insert", index)
            anchor, ins = widget.index("anchor"), widget.index("insert")
            start, end = (anchor, ins) if widget.compare(anchor, "<=", ins) else (ins, anchor)
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", start, end)
        else:
            widget.mark_set("insert", index)
            widget.tag_remove("sel", "1.0", "end")
        widget.see("insert")
        return "break"

    def _cmd_left(e):  return _move(e.widget, "insert display linestart", False)
    def _cmd_right(e): return _move(e.widget, "insert display lineend", False)
    def _opt_left(e):  return _move(e.widget, _word_start_index(e.widget, "insert"), False)
    def _opt_right(e): return _move(e.widget, _word_end_index(e.widget, "insert"), False)

    # Cmd+Shift+Left/Right: extend selection to the wrapped display-line edge
    def _cmd_shift_left(e):  return _move(e.widget, "insert display linestart", True)
    def _cmd_shift_right(e): return _move(e.widget, "insert display lineend", True)

    # Control+Shift+Left/Right and Option+Shift+Left/Right: extend selection by word
    def _shift_word_left(e):  return _move(e.widget, _word_start_index(e.widget, "insert"), True)
    def _shift_word_right(e): return _move(e.widget, _word_end_index(e.widget, "insert"), True)

    # Shift+Up/Down: extend selection by wrapped display line
    def _shift_up(e):   return _move(e.widget, "insert -1 display lines", True)
    def _shift_down(e): return _move(e.widget, "insert +1 display lines", True)

    # Cmd+Shift+Up/Down: extend selection to the start/end of the whole text
    def _cmd_shift_up(e):   return _move(e.widget, "1.0", True)
    def _cmd_shift_down(e): return _move(e.widget, "end-1c", True)

    # Cmd+Up/Down: jump to the start/end of the whole text
    def _cmd_up(e):   return _move(e.widget, "1.0", False)
    def _cmd_down(e): return _move(e.widget, "end-1c", False)

    # Option+Up/Down: paragraph jump
    def _opt_up(e):   return _move(e.widget, _para_start_index(e.widget, "insert"), False)
    def _opt_down(e): return _move(e.widget, _para_end_index(e.widget, "insert"), False)

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
        ("<Command-Shift-Left>",  _cmd_shift_left),
        ("<Command-Shift-Right>", _cmd_shift_right),
        ("<Control-Shift-Left>",  _shift_word_left),
        ("<Control-Shift-Right>", _shift_word_right),
        ("<Option-Shift-Left>",   _shift_word_left),
        ("<Option-Shift-Right>",  _shift_word_right),
        ("<Shift-Up>",           _shift_up),
        ("<Shift-Down>",         _shift_down),
        ("<Command-Shift-Up>",   _cmd_shift_up),
        ("<Command-Shift-Down>", _cmd_shift_down),
        ("<Command-Up>",        _cmd_up),
        ("<Command-Down>",      _cmd_down),
        ("<Option-Up>",         _opt_up),
        ("<Option-Down>",       _opt_down),
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
