import json
import re
import requests


class TGError(Exception):
    pass


def u16(s):
    """Telegram entity offsetlari UTF-16 birliklarida hisoblanadi."""
    return len(s.encode("utf-16-le")) // 2


def ent_text(text, e):
    b = text.encode("utf-16-le")
    return b[e["offset"] * 2:(e["offset"] + e["length"]) * 2].decode("utf-16-le")


def render(text, emojis):
    """{e:key} belgisini premium (custom_emoji) entity ga aylantiradi."""
    out, ents, pos = "", [], 0
    for part in re.split(r"(\{e:\w+\})", text):
        m = re.fullmatch(r"\{e:(\w+)\}", part)
        if m:
            e = emojis.get(m.group(1))
            if not e:
                continue
            ch = e.get("char", "")
            if e.get("id"):
                ents.append({"type": "custom_emoji", "offset": pos,
                             "length": u16(ch), "custom_emoji_id": e["id"]})
            out += ch
            pos += u16(ch)
        else:
            out += part
            pos += u16(part)
    return out, ents


class TG:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.file_base = f"https://api.telegram.org/file/bot{token}/"
        self.s = requests.Session()

    def call(self, method, files=None, http_timeout=70, **kw):
        data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                for k, v in kw.items() if v is not None}
        r = self.s.post(self.base + method, data=data, files=files, timeout=http_timeout)
        j = r.json()
        if not j.get("ok"):
            raise TGError(f"{method}: {j.get('description')}")
        return j["result"]

    def say(self, chat, text, emojis, markup=None):
        t, ents = render(text, emojis)
        return self.call("sendMessage", chat_id=chat, text=t,
                         entities=ents or None, reply_markup=markup)

    def send_file(self, method, field, chat, path, emojis, caption="", markup=None, **kw):
        cap, ents = render(caption, emojis) if caption else ("", [])
        with open(path, "rb") as f:
            return self.call(method, files={field: f}, http_timeout=900, chat_id=chat,
                             caption=cap or None, caption_entities=ents or None,
                             reply_markup=markup, **kw)

    def download(self, file_id, dest):
        info = self.call("getFile", file_id=file_id)
        with requests.get(self.file_base + info["file_path"], stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        return dest

    def answer(self, cb_id):
        try:
            self.call("answerCallbackQuery", callback_query_id=cb_id)
        except TGError:
            pass