import os
import re
import shutil
import tempfile
import time
import traceback
import uuid

import media
from storage import Store
from tg import TG, TGError, ent_text

TOKEN = os.environ["BOT_TOKEN"]
ADMIN = int(os.environ["ADMIN_ID"])
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "20700"))  # ~5h45m, GitHub limiti 6 soat
MAX_BUTTONS = 100
PAGE = 8
URL_RE = re.compile(r"https?://\S+")
COLORS = ["primary", "success", "danger", ""]
FX_COLORS = ["primary", "success", "danger"]

tg = TG(TOKEN)
db = Store()
FILES = {}   # token -> lokal fayl yo'li
STATE = {}   # admin uid -> kutilayotgan amal


# ---------- yordamchilar ----------
def E():
    return db.data["emojis"]


def say(chat, text, markup=None):
    return tg.say(chat, text, E(), markup)


def err(chat, text):
    say(chat, "{e:err} " + text)


def cb(text, data, style=None):
    d = {"text": text, "callback_data": data}
    if style:
        d["style"] = style
    return d


def ikb(rows):
    return {"inline_keyboard": rows}


def btn(b):
    if b["type"] == "url":
        d = {"text": b["text"], "url": b["value"]}
    else:
        d = {"text": b["text"], "callback_data": "btn:" + b["id"]}
    if b.get("color") in ("primary", "success", "danger"):
        d["style"] = b["color"]
    if b.get("icon"):
        d["icon_custom_emoji_id"] = b["icon"]
    return d


def check_size(path):
    if os.path.getsize(path) > 49 * 1024 * 1024:
        raise RuntimeError("fayl 50 MB dan katta")


def keep(path):
    if len(FILES) >= 40:
        old = FILES.pop(next(iter(FILES)))
        shutil.rmtree(os.path.dirname(old), ignore_errors=True)
    tok = uuid.uuid4().hex[:8]
    FILES[tok] = path
    return tok


def fx_markup(tok, video):
    rows = []
    if video:
        rows.append([cb("🎵 Qo'shiqni ajratish", f"fx:extract:{tok}", "primary"),
                     cb("⭕ Dumaloq video", f"fx:circle:{tok}", "success")])
    keys = list(media.EFFECTS)
    for i in range(0, len(keys), 2):
        rows.append([cb(media.EFFECTS[k][0], f"fx:{k}:{tok}", FX_COLORS[(i + j) % 3])
                     for j, k in enumerate(keys[i:i + 2])])
    return ikb(rows)


def job(chat, status, fn, *args):
    """Holat xabarini ko'rsatadi, ishni bajaradi, xatoni chiqaradi, holat xabarini o'chiradi."""
    w = say(chat, status)
    try:
        fn(chat, *args)
    except Exception as e:
        traceback.print_exc()
        err(chat, f"Xatolik: {str(e)[:150]}")
    finally:
        try:
            tg.call("deleteMessage", chat_id=chat, message_id=w["message_id"])
        except TGError:
            pass


# ---------- asosiy menyu ----------
def menu(chat, uid):
    rows = [[btn(b)] for b in db.data["buttons"] if not (b.get("admin_only") and uid != ADMIN)]
    say(chat, "{e:wave} Assalomu alaykum! Tugmalardan birini tanlang yoki havola / qo'shiq nomini yuboring.",
        ikb(rows))


# ---------- yuklash / musiqa / effektlar ----------
def do_link(chat, url):
    d = tempfile.mkdtemp(prefix="dl_")
    path, title = media.download_video(url, d)
    if not path:
        raise RuntimeError("video topilmadi")
    check_size(path)
    tok = keep(path)
    tg.send_file("sendVideo", "video", chat, path, E(), caption=f"{{e:video}} {title[:200]}",
                 markup=fx_markup(tok, True))


def do_music(chat, q):
    d = tempfile.mkdtemp(prefix="mu_")
    path, title = media.download_audio(q, d)
    if not path:
        raise RuntimeError("qo'shiq topilmadi")
    check_size(path)
    tok = keep(path)
    tg.send_file("sendAudio", "audio", chat, path, E(), caption=f"{{e:music}} {title[:200]}",
                 markup=fx_markup(tok, False), title=title[:64])


def do_fx(chat, action, tok):
    src = FILES.get(tok)
    if not src or not os.path.exists(src):
        raise RuntimeError("fayl eskirgan, qaytadan yuboring")
    d = tempfile.mkdtemp(prefix="fx_")
    if action == "circle":
        out = media.circle(src, d)
        tg.send_file("sendVideoNote", "video_note", chat, out, E())
        return
    if action == "extract":
        out, cap = media.extract_audio(src, d), "Qo'shiq ajratildi"
    else:
        out, cap = media.audio_effect(src, action, d), media.EFFECTS[action][0]
    check_size(out)
    tg.send_file("sendAudio", "audio", chat, out, E(), caption=f"{{e:music}} {cap}")


def _fetch_media(chat, obj, video):
    d = tempfile.mkdtemp(prefix="up_")
    src = tg.download(obj["file_id"], os.path.join(d, "in.mp4" if video else "in.mp3"))
    tok = keep(src)
    say(chat, "{e:effect} Nima qilamiz?", fx_markup(tok, video))


def on_media(chat, m):
    obj = m.get("video") or m.get("video_note") or m.get("audio") or m.get("document")
    if not obj:
        return False
    mime = obj.get("mime_type", "")
    video = "video" in m or "video_note" in m or mime.startswith("video")
    audio = "audio" in m or mime.startswith("audio")
    if not (video or audio):
        return False
    job(chat, "{e:wait} Fayl yuklanmoqda...", _fetch_media, obj, video)
    return True


# ---------- xabarlar ----------
def on_message(m):
    chat = m["chat"]["id"]
    uid = m["from"]["id"]
    db.add_user(uid)
    text = (m.get("text") or m.get("caption") or "").strip()

    if uid == ADMIN and uid in STATE:
        return admin_input(chat, uid, m)
    if text.startswith("/start") or text.startswith("/menu"):
        return menu(chat, uid)
    if text.startswith("/admin"):
        if uid == ADMIN:
            admin_menu(chat)
        return
    if text.startswith("/music"):
        q = text[6:].strip()
        if q:
            return job(chat, "{e:search} Qidirilmoqda...", do_music, q)
        return say(chat, "{e:search} Qo'shiq nomini yozing.")
    if on_media(chat, m):
        return
    url = URL_RE.search(text)
    if url:
        return job(chat, "{e:wait} Yuklanmoqda...", do_link, url.group(0))
    if text and not text.startswith("/"):
        job(chat, "{e:search} Qidirilmoqda...", do_music, text)


def on_callback(q):
    tg.answer(q["id"])
    chat = q["message"]["chat"]["id"]
    uid = q["from"]["id"]
    data = q.get("data", "")

    if data.startswith("fx:"):
        _, action, tok = data.split(":", 2)
        return job(chat, "{e:wait} Tayyorlanmoqda...", do_fx, action, tok)

    if data.startswith("btn:"):
        b = db.find(data[4:])
        if not b:
            return
        if b["type"] == "message":
            return say(chat, b["value"])
        if b["type"] == "feature":
            if b["value"] == "music":
                return say(chat, "{e:search} Qo'shiq nomini yozing.")
            if b["value"] == "admin" and uid == ADMIN:
                return admin_menu(chat)
        return

    if data.startswith("adm:") and uid == ADMIN:
        return admin_cb(chat, uid, data.split(":"))


# ---------- admin panel ----------
def admin_menu(chat):
    say(chat, "{e:admin} Admin panel", ikb([
        [cb("➕ Tugma qo'shish", "adm:add", "success"), cb("✏️ Tugmalar", "adm:list:0", "primary")],
        [cb("😀 Premium emojilar", "adm:emojis", "primary"), cb("📊 Statistika", "adm:stats", "success")],
        [cb("📢 Xabar yuborish", "adm:bcast", "danger"), cb("❌ Yopish", "adm:close")],
    ]))


def buttons_page(chat, page):
    bs = db.data["buttons"]
    pages = max(1, -(-len(bs) // PAGE))
    page = max(0, min(page, pages - 1))
    rows = [[cb(b["text"], f"adm:b:{b['id']}", b.get("color") or None)]
            for b in bs[page * PAGE:(page + 1) * PAGE]]
    nav = []
    if page > 0:
        nav.append(cb("⬅️", f"adm:list:{page - 1}"))
    nav.append(cb(f"{page + 1}/{pages}", f"adm:list:{page}"))
    if page < pages - 1:
        nav.append(cb("➡️", f"adm:list:{page + 1}"))
    rows.append(nav)
    rows.append([cb("➕ Qo'shish", "adm:add", "success"), cb("⬅️ Admin", "adm:menu")])
    say(chat, f"{{e:admin}} Tugmalar ({len(bs)}/{MAX_BUTTONS}). Tanlang:", ikb(rows))


def button_menu(chat, bid):
    b = db.find(bid)
    if not b:
        return err(chat, "Tugma topilmadi.")
    adm = "ha" if b.get("admin_only") else "yo'q"
    info = (f"Tugma: {b['text']}\nTur: {b['type']}\nMazmun: {b['value'][:120]}\n"
            f"Rang: {b.get('color') or 'kulrang'}\nFaqat admin: {adm}")
    rows = [
        [cb("✏️ Matn", f"adm:t:{bid}", "primary"), cb("🔗 Mazmun", f"adm:v:{bid}", "primary")],
        [cb("🎨 Rang", f"adm:c:{bid}", "success"), cb("😀 Premium ikonka", f"adm:i:{bid}", "success")],
        [cb("👁 Faqat admin", f"adm:m:{bid}", "danger"), cb("🗑 O'chirish", f"adm:x:{bid}", "danger")],
        [cb("⬅️ Orqaga", "adm:list:0")],
    ]
    say(chat, "{e:admin} " + info, ikb(rows))


def emojis_menu(chat):
    keys = list(E())
    rows = []
    for i in range(0, len(keys), 2):
        rows.append([cb(f"{E()[k]['char']} {k} {'✅' if E()[k].get('id') else '⚠️'}",
                        f"adm:e:{k}", "primary") for k in keys[i:i + 2]])
    rows.append([cb("⬅️ Admin", "adm:menu")])
    say(chat, "{e:admin} Premium emojilar. Kalitni tanlang, so'ng premium emoji yuboring. "
              "✅ = premium ID bor, ⚠️ = yo'q.", ikb(rows))


def admin_cb(chat, uid, p):
    act = p[1]
    arg = p[2] if len(p) > 2 else ""

    if act == "close":
        return
    if act == "menu":
        return admin_menu(chat)
    if act == "add":
        if len(db.data["buttons"]) >= MAX_BUTTONS:
            return err(chat, f"Tugmalar soni {MAX_BUTTONS} tadan oshmasin.")
        STATE[uid] = {"mode": "add_name"}
        return say(chat, "{e:send} Yangi tugma nomini yozing (emoji bilan bo'lishi mumkin). Bekor: /cancel")
    if act == "list":
        return buttons_page(chat, int(arg or 0))
    if act == "b":
        return button_menu(chat, arg)
    if act == "c":
        b = db.find(arg)
        if b:
            cur = b.get("color") or ""
            b["color"] = COLORS[(COLORS.index(cur) + 1) % 4] if cur in COLORS else COLORS[0]
            db.save()
        return button_menu(chat, arg)
    if act == "m":
        b = db.find(arg)
        if b:
            b["admin_only"] = not b.get("admin_only")
            db.save()
        return button_menu(chat, arg)
    if act == "x":
        b = db.find(arg)
        if b:
            db.data["buttons"].remove(b)
            db.save()
        return buttons_page(chat, 0)
    if act in ("t", "v", "i"):
        STATE[uid] = {"mode": {"t": "text", "v": "value", "i": "icon"}[act], "arg": arg}
        prompts = {
            "t": "Yangi matnni yuboring:",
            "v": "Yangi mazmunni yuboring (matn yoki https:// havola):",
            "i": "Tugma uchun premium emojini yuboring:",
        }
        return say(chat, "{e:send} " + prompts[act] + " (/cancel bekor qiladi)")
    if act == "emojis":
        return emojis_menu(chat)
    if act == "e":
        STATE[uid] = {"mode": "emoji", "arg": arg}
        return say(chat, f"{{e:send}} '{arg}' uchun premium emojini yuboring:")
    if act == "stats":
        return say(chat, f"{{e:stats}} Foydalanuvchilar: {len(db.data['users'])}\n"
                         f"Tugmalar: {len(db.data['buttons'])}/{MAX_BUTTONS}")
    if act == "bcast":
        STATE[uid] = {"mode": "bcast"}
        return say(chat, "{e:send} Yuboriladigan xabarni yuboring (matn, rasm, premium emoji...). Bekor: /cancel")


def admin_input(chat, uid, m):
    st = STATE[uid]
    mode = st["mode"]
    text = (m.get("text") or m.get("caption") or "").strip()

    if text == "/cancel":
        STATE.pop(uid, None)
        return say(chat, "{e:ok} Bekor qilindi.")

    ents = m.get("entities") or m.get("caption_entities") or []
    cust = [e for e in ents if e.get("type") == "custom_emoji"]

    if mode not in ("icon", "emoji", "bcast") and not text:
        return err(chat, "Matn yuboring.")

    if mode == "add_name":
        STATE[uid] = {"mode": "add_value", "name": text[:64]}
        return say(chat, "{e:send} Endi mazmunni yuboring: oddiy matn yoki https:// havola")

    if mode == "add_value":
        STATE.pop(uid, None)
        if len(db.data["buttons"]) >= MAX_BUTTONS:
            return err(chat, f"Tugmalar soni {MAX_BUTTONS} tadan oshmasin.")
        db.data["buttons"].append({
            "id": uuid.uuid4().hex[:6], "text": st["name"],
            "type": "url" if URL_RE.fullmatch(text) else "message",
            "value": text, "color": "primary", "icon": "", "admin_only": False,
        })
        db.save()
        say(chat, "{e:ok} Tugma qo'shildi.")
        return buttons_page(chat, 0)

    if mode in ("text", "value"):
        STATE.pop(uid, None)
        b = db.find(st["arg"])
        if not b:
            return err(chat, "Tugma topilmadi.")
        if mode == "text":
            b["text"] = text[:64]
        else:
            if b["type"] == "feature":
                return err(chat, "Bu tugma mazmunini o'zgartirib bo'lmaydi.")
            b["value"] = text
            b["type"] = "url" if URL_RE.fullmatch(text) else "message"
        db.save()
        say(chat, "{e:ok} Saqlandi.")
        return button_menu(chat, b["id"])

    if mode == "icon":
        if not cust:
            return err(chat, "Premium emoji yuboring.")
        STATE.pop(uid, None)
        b = db.find(st["arg"])
        if b:
            b["icon"] = cust[0]["custom_emoji_id"]
            db.save()
        say(chat, "{e:ok} Ikonka saqlandi.")
        return button_menu(chat, st["arg"])

    if mode == "emoji":
        STATE.pop(uid, None)
        key = st["arg"]
        if cust:
            E()[key] = {"char": ent_text(text, cust[0]), "id": cust[0]["custom_emoji_id"]}
        elif text:
            E()[key] = {"char": text[:4], "id": ""}
        else:
            return err(chat, "Emoji yuboring.")
        db.save()
        say(chat, f"{{e:ok}} '{key}' yangilandi.")
        return emojis_menu(chat)

    if mode == "bcast":
        STATE.pop(uid, None)
        sent = 0
        users = list(db.data["users"])
        for u in users:
            try:
                tg.call("copyMessage", chat_id=u, from_chat_id=chat, message_id=m["message_id"])
                sent += 1
            except Exception:
                pass
        return say(chat, f"{{e:ok}} Yuborildi: {sent}/{len(users)}")


# ---------- dispatch / asosiy sikl ----------
def handle(u):
    if "callback_query" in u:
        return on_callback(u["callback_query"])
    m = u.get("message")
    if m and not m.get("from", {}).get("is_bot"):
        on_message(m)


def main():
    print("Bot ishga tushdi")
    start = time.time()
    while time.time() - start < RUN_SECONDS:
        try:
            ups = tg.call("getUpdates", http_timeout=70, offset=db.data["offset"], timeout=50,
                          allowed_updates=["message", "callback_query"])
        except Exception as e:
            print("getUpdates:", e)
            time.sleep(5)
            continue
        for u in ups:
            db.data["offset"] = u["update_id"] + 1
            try:
                handle(u)
            except Exception:
                traceback.print_exc()
            db.save()
    db.save()
    print("Vaqt tugadi, bot to'xtatildi")


if __name__ == "__main__":
    main()