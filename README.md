# Vidéos satisfaisantes automatiques

Chaque jour à 17h30 (heure de Paris), GitHub Actions génère une vidéo de 1 min 10 (1080×1920, avec son),
puis la publie à 18h00 : Telegram (pour publier toi-même sur TikTok/YouTube en attendant), Instagram Reels, YouTube Shorts.

## Templates (rotation sur 7 jours)
| Fichier | Contenu |
|---|---|
| `wheel_blackhole.py` | Roue qui tourne + trou noir : chaque bille qui y entre ressort en 2 |
| `crusher_walls.py` | Murs qui se referment : bille écrasée = doublée (2 ou 4 murs) |
| `race_towers.py` | Expériences mathématiques : ×2 vs ÷2, +1 vs ×2, ×3 risqué vs ×2 |

`daily.py` choisit le template du jour, génère titre, description, hashtags et couverture.
`publish.py` publie (chaque plateforme est ignorée tant que ses secrets ne sont pas configurés).

## Secrets à ajouter (Settings → Secrets and variables → Actions)
| Secret | Plateforme |
|---|---|
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube |

## Tester à la main
Onglet **Actions** → « Vidéo du jour » → **Run workflow**.

En local : `pip install numpy pillow` (+ ffmpeg), puis `python daily.py --scale 0.5` pour un aperçu rapide.
