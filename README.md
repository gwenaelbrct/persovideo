# Vidéos satisfaisantes automatiques

Chaque jour à 10h30 (heure de Paris), GitHub Actions génère une vidéo de 1 min 10 (1080×1920, avec son),
puis la publie à 11h00 : un e-mail GitHub (Release) avec la vidéo, la couverture et le texte à copier ;
Instagram Reels et YouTube Shorts en automatique une fois leurs accès configurés.

## 30 concepts, un par jour
`concepts.py` contient les 30 concepts validés et leur ordre de passage : 30 jours consécutifs = 30 vidéos différentes,
et jamais deux concepts de la même famille deux jours de suite. Les couleurs et la physique changent à chaque passage.

| Moteur | Fichier | Concepts |
|---|---|---|
| Arène (formes, ouvertures, anneaux, trous noirs, effets au rebond) | `arena.py` | 02–05, 08–20, 29–30 |
| Roue + trou noir | `wheel_blackhole.py` | 01 |
| Murs qui écrasent | `crusher_walls.py` | 06–07 |
| Expériences / courses (2 à 4 couloirs) | `race_towers.py` | 21–26 |
| Plinko | `plinko.py` | 27–28 |

`daily.py` choisit le concept du jour, génère titre, description, hashtags et couverture.
`publish.py` publie (chaque plateforme est ignorée tant que ses secrets ne sont pas configurés).

Tester un concept précis : `python daily.py --concept 12_rings --scale 0.5`

## Secrets à ajouter (Settings → Secrets and variables → Actions)
| Secret | Plateforme |
|---|---|
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube |

## Tester à la main
Onglet **Actions** → « Vidéo du jour » → **Run workflow**.

En local : `pip install numpy pillow` (+ ffmpeg), puis `python daily.py --scale 0.5` pour un aperçu rapide.
