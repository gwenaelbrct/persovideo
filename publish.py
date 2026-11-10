"""Publie la vidéo du jour. Chaque plateforme est ignorée si ses secrets ne sont pas configurés.

Usage: python3 publish.py out/<date>
Secrets (variables d'environnement, fournis par GitHub Actions) :
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
  IG_USER_ID, IG_ACCESS_TOKEN                          (Instagram, API « Instagram Login »)
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN     (YouTube)
"""
import json, os, sys, time, uuid, urllib.parse, urllib.request

env = os.environ.get


def http(method, url, data=None, headers=None, timeout=300):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def multipart(fields, files):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (name, data, ctype) in files.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
                     + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


# ------------------------------------------------------------------ Telegram
def telegram(d, meta):
    tok, chat = env("TELEGRAM_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("Telegram : non configuré, ignoré"); return
    api = f"https://api.telegram.org/bot{tok}"
    with open(os.path.join(d, "video.mp4"), "rb") as f:
        body, ct = multipart({"chat_id": chat, "caption": meta["title"][:1000], "supports_streaming": "true"},
                             {"video": ("video.mp4", f.read(), "video/mp4")})
    s, _, r = http("POST", api + "/sendVideo", body, {"Content-Type": ct})
    print("Telegram vidéo :", s, r[:200])
    with open(os.path.join(d, "cover.jpg"), "rb") as f:
        body, ct = multipart({"chat_id": chat, "caption": "Couverture"}, {"photo": ("cover.jpg", f.read(), "image/jpeg")})
    http("POST", api + "/sendPhoto", body, {"Content-Type": ct})
    for txt in (meta["caption"], meta["youtube_title"]):
        data = urllib.parse.urlencode({"chat_id": chat, "text": txt}).encode()
        http("POST", api + "/sendMessage", data)


# ------------------------------------------------------------------ Instagram (Reels)
def instagram(d, meta):
    uid, tok = env("IG_USER_ID"), env("IG_ACCESS_TOKEN")
    if not (uid and tok):
        print("Instagram : non configuré, ignoré"); return
    host = env("IG_API_HOST", "graph.instagram.com")
    ver = "v21.0"
    q = urllib.parse.urlencode({"media_type": "REELS", "upload_type": "resumable", "caption": meta["caption"][:2100],
                                "share_to_feed": "true", "thumb_offset": "55000", "access_token": tok}).encode()
    s, _, r = http("POST", f"https://{host}/{ver}/{uid}/media", q)
    if s != 200:
        raise SystemExit(f"Instagram création conteneur : {s} {r[:300]}")
    cid = json.loads(r)["id"]
    path = os.path.join(d, "video.mp4")
    with open(path, "rb") as f:
        data = f.read()
    s, _, r = http("POST", f"https://rupload.facebook.com/ig-api-upload/{ver}/{cid}", data,
                   {"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(data))}, timeout=900)
    print("Instagram upload :", s, r[:200])
    for _ in range(60):
        s, _, r = http("GET", f"https://{host}/{ver}/{cid}?fields=status_code&access_token={tok}")
        st = json.loads(r).get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise SystemExit(f"Instagram traitement en erreur : {r[:300]}")
        time.sleep(10)
    s, _, r = http("POST", f"https://{host}/{ver}/{uid}/media_publish",
                   urllib.parse.urlencode({"creation_id": cid, "access_token": tok}).encode())
    print("Instagram publication :", s, r[:200])


# ------------------------------------------------------------------ YouTube Shorts
def youtube(d, meta):
    cid, sec, rt = env("YT_CLIENT_ID"), env("YT_CLIENT_SECRET"), env("YT_REFRESH_TOKEN")
    if not (cid and sec and rt):
        print("YouTube : non configuré, ignoré"); return
    s, _, r = http("POST", "https://oauth2.googleapis.com/token", urllib.parse.urlencode(
        {"client_id": cid, "client_secret": sec, "refresh_token": rt, "grant_type": "refresh_token"}).encode())
    if s != 200:
        raise SystemExit(f"YouTube token : {s} {r[:300]}")
    at = json.loads(r)["access_token"]
    body = {"snippet": {"title": meta["youtube_title"][:100], "description": meta["caption"][:4900],
                        "tags": [t.lstrip("#") for t in meta["hashtags"]], "categoryId": "28"},
            "status": {"privacyStatus": env("YT_PRIVACY", "public"), "selfDeclaredMadeForKids": False}}
    path = os.path.join(d, "video.mp4")
    size = os.path.getsize(path)
    s, h, r = http("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                   json.dumps(body).encode(), {"Authorization": f"Bearer {at}", "Content-Type": "application/json; charset=UTF-8",
                                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    loc = h.get("Location") or h.get("location")
    if not loc:
        raise SystemExit(f"YouTube init : {s} {r[:300]}")
    with open(path, "rb") as f:
        s, _, r = http("PUT", loc, f.read(), {"Content-Type": "video/mp4"}, timeout=900)
    print("YouTube :", s, r[:300])


if __name__ == "__main__":
    d = sys.argv[1]
    only = sys.argv[2:] or ["telegram", "instagram", "youtube"]
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    errors = []
    for name in only:
        try:
            globals()[name](d, meta)
        except BaseException as e:   # une plateforme en échec ne bloque pas les autres
            print(f"ERREUR {name} :", e); errors.append(name)
    if errors:
        sys.exit(1)
