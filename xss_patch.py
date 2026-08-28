import re, os

ROOT = r"E:\project\app"

HELPERS = """
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]);});}
function safeUrl(u){u=String(u==null?"":u);if(/^\\s*javascript:/i.test(u))return"#";return esc(u);}
"""

# (file, [(old_substring, new_substring), ...])  -- only user/API free-text fields
PATCHES = {
    "bookmark-manager": [
        ('href="${m.url}"', 'href="${safeUrl(m.url)}"'),
        ('>${m.url}<', '>${esc(m.url)}<'),
        ('${m.title}', '${esc(m.title)}'),
        ('${m.tag}', '${esc(m.tag)}'),
    ],
    "password-vault": [
        ('${it.site}', '${esc(it.site)}'),
        ('${it.user}', '${esc(it.user)}'),
        ('${it.pass}', '${esc(it.pass)}'),
    ],
    "expense-ledger": [
        ('${l.note||""}', '${esc(l.note||"")}'),
        ('${l.date}', '${esc(l.date)}'),
        ('${l.cat}', '${esc(l.cat)}'),
    ],
    "habit-tracker": [
        ('${h.name}', '${esc(h.name)}'),
    ],
    "workout-log": [
        ('${l.date}', '${esc(l.date)}'),
        ('${l.type}', '${esc(l.type)}'),
    ],
    "recipe-box": [
        ('${r.name}', '${esc(r.name)}'),
        ('${r.tag}', '${esc(r.tag)}'),
        ('${r.time}', '${esc(r.time)}'),
        ('${r.ing}', '${esc(r.ing)}'),
        ('<li>${s}</li>', '<li>${esc(s)}</li>'),
    ],
    "trip-planner": [
        ('${h1}', '${esc(h1)}'),
        ('${h2}', '${esc(h2)}'),
        ('${t.am}', '${esc(t.am)}'),
        ('${t.pm}', '${esc(t.pm)}'),
        ('${t.ev}', '${esc(t.ev)}'),
        ('${city}', '${esc(city)}'),
    ],
    "mood-meter": [
        ('${r.note||""}', '${esc(r.note||"")}'),
        ('${r.date}', '${esc(r.date)}'),
    ],
    "code-teacher": [
        ("'+txt;", "'+esc(txt);"),
    ],
}

def inject_helpers(html):
    if "function esc(" in html:
        return html
    # insert right after the first <script> (no src)
    m = re.search(r"<script>", html)
    if not m:
        return html
    i = m.end()
    return html[:i] + "\n" + HELPERS.strip() + "\n" + html[i:]

total = 0
for app, subs in PATCHES.items():
    p = os.path.join(ROOT, app, "index.html")
    if not os.path.exists(p):
        print("SKIP missing", p); continue
    with open(p, "r", encoding="utf-8") as f:
        html = f.read()
    before = html
    html = inject_helpers(html)
    applied = 0
    for old, new in subs:
        if old in html:
            html = html.replace(old, new)
            applied += 1
        else:
            print(f"  [warn] {app}: pattern not found -> {old!r}")
    if html != before:
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
        total += 1
        print(f"OK {app}: injected_helpers={('function esc(' in before)==False}, applied={applied}/{len(subs)}")
    else:
        print(f"NOCHANGE {app}")

print(f"\nPatched {total} files.")
