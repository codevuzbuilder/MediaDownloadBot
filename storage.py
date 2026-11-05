import copy
import json
import os

PATH = "data/config.json"

EMOJI_DEFAULTS = {
    "wave": "👋", "star": "⭐", "video": "🎬", "music": "🎵", "circle": "⭕",
    "effect": "🎛", "wait": "⏳", "ok": "✅", "err": "❌", "help": "ℹ️",
    "stats": "📊", "admin": "🛠", "send": "📤", "search": "🔍", "fire": "🔥", "trash": "🗑",
}

DEFAULT = {
    "offset": 0,
    "users": [],
    "emojis": {k: {"char": c, "id": ""} for k, c in EMOJI_DEFAULTS.items()},
    "buttons": [
        {"id": "dl", "text": "📥 Video yuklash", "type": "message", "color": "primary", "icon": "",
         "admin_only": False,
         "value": "{e:video} Instagram, TikTok, YouTube, Facebook, Pinterest va boshqa platformalardan havolani yuboring."},
        {"id": "music", "text": "🎵 Qo'shiq yuklash", "type": "feature", "value": "music",
         "color": "success", "icon": "", "admin_only": False},
        {"id": "circle", "text": "⭕ Dumaloq video", "type": "message", "color": "primary", "icon": "",
         "admin_only": False,
         "value": "{e:circle} Video yuboring, uni dumaloq videoga aylantiraman."},
        {"id": "fx", "text": "🎛 Effektlar", "type": "message", "color": "danger", "icon": "",
         "admin_only": False,
         "value": "{e:effect} Audio yoki video yuboring: slowed, remix, concert hall, bass effektlarini qo'shaman."},
        {"id": "help", "text": "ℹ️ Yordam", "type": "message", "color": "", "icon": "",
         "admin_only": False,
         "value": "{e:help} Havola yuboring, qo'shiq nomini yozing yoki tugmalardan foydalaning."},
        {"id": "admin", "text": "🛠 Admin panel", "type": "feature", "value": "admin",
         "color": "danger", "icon": "", "admin_only": True},
    ],
}


class Store:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.data = copy.deepcopy(DEFAULT)
        if os.path.exists(PATH):
            with open(PATH, encoding="utf-8") as f:
                self.data.update(json.load(f))
            for k, v in EMOJI_DEFAULTS.items():
                self.data["emojis"].setdefault(k, {"char": v, "id": ""})
        self.save()

    def save(self):
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def find(self, bid):
        return next((b for b in self.data["buttons"] if b["id"] == bid), None)

    def add_user(self, uid):
        if uid not in self.data["users"]:
            self.data["users"].append(uid)