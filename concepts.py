"""Catalogue des 30 concepts validés. Un concept par jour, tous différents sur 30 jours consécutifs.

Chaque concept : engine (moteur), params, et textes (titres, couverture, description, hashtags).
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

T_SAT = ["#satisfying", "#oddlysatisfying", "#satisfyingvideo", "#asmr", "#physics", "#simulation"]
T_MATH = ["#math", "#maths", "#experiment", "#exponential", "#didyouknow", "#science"]


def C(engine, params, titles, cover, desc_en, desc_fr, tags):
    return dict(engine=engine, params=params, titles=titles, cover=cover, desc=f"{desc_en}\n{desc_fr}", tags=tags)


CONCEPTS = {
    # ------------------------------------------------------------ Multiplication
    "01_wheel_blackhole": C("wheel", {},
        ["1 ball enters the black hole… then THIS happens 🕳️", "Can 1 ball fill the entire wheel? 🤯"],
        ["WILL IT FILL\nTHE WHEEL?", "1 BALL →\n350 BALLS?"],
        "Each ball that falls into the black hole comes out as TWO. 🕳️",
        "Chaque bille qui tombe dans le trou noir ressort en deux.", T_SAT + ["#blackhole"]),
    "02_hexagon_x3": C("arena", dict(shape=6, size=470, spin=0.4, gravity=800, cap=400,
                                     holes=[dict(orbit=210, r=62, effect="x3", w=0.5)], subtitle="EVERY BALL BECOMES 3"),
        ["Every ball becomes THREE inside this hexagon", "×3 black hole in a spinning hexagon 🔷"],
        ["EVERY BALL\nBECOMES 3", "×3 BLACK\nHOLE"],
        "Touch the black hole = turn into 3 balls. How fast does the hexagon fill up?",
        "Chaque bille qui touche le trou noir se transforme en 3.", T_SAT + ["#hexagon"]),
    "03_good_bad_holes": C("arena", dict(shape=3, size=540, spin=0.35, gravity=800, cap=300, start=3,
                                         holes=[dict(orbit=150, r=66, effect="x2", w=0.55, pull=1.3), dict(orbit=150, r=50, effect="kill", w=0.55, pull=0.5)],
                                         subtitle="×2 HOLE vs ☠ HOLE"),
        ["One hole doubles, one hole kills… will they survive?", "×2 hole vs ☠ hole — who wins?"],
        ["×2 OR ☠ ?", "WILL THEY\nSURVIVE?"],
        "One black hole doubles the balls, the red one destroys them. Will they survive until the end?",
        "Un trou double les billes, l'autre les détruit. Vont-elles survivre ?", T_SAT + ["#survival"]),
    "04_three_holes": C("arena", dict(shape=8, size=470, spin=0.3, gravity=700, cap=420,
                                      holes=[dict(orbit=230, r=50, effect="x2", w=0.4), dict(orbit=230, r=50, effect="x2", w=0.4),
                                             dict(orbit=230, r=50, effect="x2", w=0.4)], subtitle="3 BLACK HOLES · 1 BALL"),
        ["3 black holes, 1 ball… wait for it 🕳️🕳️🕳️", "Three orbiting black holes double every ball"],
        ["3 BLACK HOLES\n1 BALL", "WAIT FOR\nTHE END"],
        "Three orbiting black holes, each one doubles every ball it swallows.",
        "Trois trous noirs en orbite, chacun double les billes qu'il avale.", T_SAT + ["#blackhole"]),
    "05_bounce_clone": C("arena", dict(shape=5, size=470, spin=0.3, gravity=700, cap=350, wall="double", subtitle="EVERY BOUNCE = +1 BALL"),
        ["Every bounce creates a new ball 😳", "Bounce = clone. How many in 60 seconds?"],
        ["EVERY BOUNCE\n= +1 BALL", "HOW MANY\nIN 60s?"],
        "Each time a ball hits the wall, it clones itself. Guess the final number!",
        "Chaque rebond sur un mur crée une nouvelle bille. Devine le nombre final !", T_SAT + ["#pentagon"]),
    "06_crusher_4": C("walls", dict(walls=4),
        ["Every ball crushed by the walls DOUBLES 😳", "The walls are closing in… and the balls multiply"],
        ["CRUSHED\n= DOUBLED", "THE WALLS\nARE CLOSING"],
        "Every ball squeezed by a moving wall turns into two.", "Chaque bille écrasée par un mur se dédouble.", T_SAT + ["#chaos"]),
    "07_crusher_2": C("walls", dict(walls=2),
        ["The hydraulic press of balls 🧱", "Squeezed = doubled. How many by the end?"],
        ["THE BALL\nPRESS", "SQUEEZED\n= DOUBLED"],
        "Two walls squeeze the arena like a press. Every crushed ball doubles.",
        "Deux murs se resserrent comme une presse. Bille écrasée = doublée.", T_SAT + ["#press"]),
    "08_survival": C("arena", dict(shape="circle", size=460, spin=0.3, gravity=700, cap=300, start=2, wall="double",
                                   holes=[dict(orbit=220, r=78, effect="kill", w=0.55, pull=1.8)], subtitle="CLONES vs BLACK HOLE"),
        ["Can they multiply faster than the black hole eats them?", "Clone on bounce vs black hole — who wins?"],
        ["CAN THEY\nOUTGROW IT?", "CLONES vs\nBLACK HOLE"],
        "Bounces clone the balls, the red black hole eats them. Which force wins?",
        "Les rebonds clonent les billes, le trou rouge les mange. Qui l'emporte ?", T_SAT + ["#survival"]),
    # ------------------------------------------------------------ Évasion
    "09_escape_circle": C("arena", dict(shape="circle", size=380, spin=0.6, gap=0.5, gravity=600, cap=350, escape="spawn2",
                                        subtitle="EVERY ESCAPE = 2 MORE"),
        ["Every ball that escapes spawns 2 more 😱", "Escape the spinning circle… then it gets crazy"],
        ["EVERY ESCAPE\n= 2 MORE", "ESCAPE THE\nCIRCLE"],
        "Each time a ball escapes the spinning circle, 2 new balls appear in the middle.",
        "Chaque bille qui s'échappe du cercle fait apparaître 2 nouvelles billes.", T_SAT + ["#escape"]),
    "10_escape_square": C("arena", dict(shape=4, size=430, spin=0.5, gap=0.45, gravity=600, cap=350, escape="spawn2",
                                        subtitle="ESCAPE THE SQUARE"),
        ["Can they escape the spinning square?", "Escape = 2 new balls. The square goes crazy"],
        ["ESCAPE THE\nSQUARE", "ESCAPE\n= ×2"], "Escape the spinning square: every escapee is replaced by two.",
        "Chaque bille qui sort du carré est remplacée par deux.", T_SAT + ["#escape"]),
    "11_escape_triangle": C("arena", dict(shape=3, size=470, spin=1.0, gap=0.55, gravity=600, cap=350, escape="spawn2",
                                          subtitle="ESCAPE THE TRIANGLE"),
        ["This fast spinning triangle is chaos 🔺", "Escape the triangle = 2 more balls"],
        ["ESCAPE THE\nTRIANGLE", "PURE\nCHAOS"], "A small, fast spinning triangle. Every escape spawns 2 more balls.",
        "Un triangle rapide : chaque évasion fait apparaître 2 billes.", T_SAT + ["#escape"]),
    "12_rings": C("arena", dict(shape="circle", rings=30, ring_in=70, ring_out=480, ring_gap=0.7, gravity=700, vmin=600,
                                hud="rings", subtitle="BREAK ALL 30 RINGS"),
        ["Can 1 ball break 30 rings? 🎵", "Every ring she breaks plays a note"],
        ["30 RINGS\n1 BALL", "CAN IT\nESCAPE?"], "One ball, 30 spinning rings. Each ring breaks when the ball escapes through its gap.",
        "Une bille, 30 anneaux qui tournent. Chaque anneau franchi se brise.", T_SAT + ["#escape", "#rings"]),
    "13_hex_rings": C("arena", dict(shape=6, rings=25, ring_in=80, ring_out=500, ring_gap=0.55, gravity=700, vmin=600,
                                    hud="rings", subtitle="25 HEXAGONS · 1 BALL"),
        ["25 hexagons, 1 ball. Can it escape?", "Breaking out of 25 spinning hexagons 🔷"],
        ["25 HEXAGONS\n1 BALL", "BREAK\nOUT"], "One ball trapped in 25 nested spinning hexagons.",
        "Une bille enfermée dans 25 hexagones emboîtés.", T_SAT + ["#escape", "#hexagon"]),
    "14_rings_clone": C("arena", dict(shape="circle", rings=25, ring_in=80, ring_out=480, ring_gap=0.5, gravity=700, vmin=600,
                                      hud="rings", ring_double=True, cap=60, subtitle="EVERY RING = +1 BALL"),
        ["Every ring broken = +1 ball", "The more rings break, the more balls escape"],
        ["EVERY RING\n= +1 BALL", "25 RINGS\nTO BREAK"], "Each broken ring adds a new ball. The escape speeds up!",
        "Chaque anneau brisé ajoute une bille : l'évasion accélère !", T_SAT + ["#rings"]),
    # ------------------------------------------------------------ Une seule bille
    "15_grow_circle": C("arena", dict(shape="circle", size=450, spin=0.2, gravity=900, vmin=700, wall="grow", grow_max=0.95,
                                      note_on_bounce=True, hud="size", subtitle="IT GROWS EVERY BOUNCE"),
        ["This ball grows every time it bounces 🎵", "Will it fill the whole circle?"],
        ["IT GROWS\nEVERY BOUNCE", "WILL IT\nFILL IT?"], "Every bounce makes the ball a little bigger, and plays a note.",
        "À chaque rebond la bille grossit, et joue une note.", T_SAT + ["#music"]),
    "16_grow_hexagon": C("arena", dict(shape=6, size=480, spin=0.45, gravity=900, vmin=700, wall="grow", grow_max=0.92,
                                       note_on_bounce=True, hud="size", subtitle="FILL THE HEXAGON"),
        ["Will it fill the spinning hexagon?", "Growing ball vs spinning hexagon 🔷"],
        ["FILL THE\nHEXAGON", "GROWS EVERY\nBOUNCE"], "A ball that grows on every bounce inside a spinning hexagon.",
        "Une bille qui grossit à chaque rebond dans un hexagone qui tourne.", T_SAT + ["#hexagon"]),
    "17_grow_split": C("arena", dict(shape="circle", size=460, spin=0.25, gravity=800, vmin=650, wall="grow", grow_max=0.95,
                                     split_at=55, grow_step=2.5, cap=70, note_on_bounce=True, hud="count", subtitle="GROW · SPLIT · REPEAT"),
        ["Grow, split, repeat… until the screen is full", "Every big ball splits in two 🫧"],
        ["GROW\nSPLIT\nREPEAT", "SPLIT\nIN TWO"], "Balls grow on every bounce; when too big, they split in two.",
        "Les billes grossissent à chaque rebond puis se divisent en deux.", T_SAT + ["#bubbles"]),
    "18_strings_circle": C("arena", dict(shape="circle", size=450, spin=0.0, gravity=150, vmin=2800, vmax=3000, sub=6, wall="trail",
                                         note_on_bounce=True, hud="bounces", subtitle="EVERY BOUNCE ADDS A STRING"),
        ["Every bounce adds a string… wait for the pattern 🎨", "Bounce art: watch the pattern appear"],
        ["WAIT FOR\nTHE PATTERN", "BOUNCE\nART"], "Every bounce ties a new string to the ball. Watch the art appear.",
        "Chaque rebond ajoute un fil relié à la bille. Regarde le dessin apparaître.", T_SAT + ["#art", "#stringart"]),
    "19_strings_triangle": C("arena", dict(shape=3, size=520, spin=0.4, gravity=150, vmin=2800, vmax=3000, sub=6, wall="trail",
                                           note_on_bounce=True, hud="bounces", subtitle="SPINNING STRING ART"),
        ["String art inside a spinning triangle 🔺🎨", "The final pattern is unreal"],
        ["THE FINAL\nPATTERN", "STRING\nART"], "A spinning triangle, one ball, and a string for every bounce.",
        "Un triangle qui tourne, une bille, et un fil à chaque rebond.", T_SAT + ["#art", "#stringart"]),
    "20_speed": C("arena", dict(shape=4, size=440, spin=0.25, gravity=300, vmin=400, vmax=9000, sub=8, ball_r=18, wall="speed", speed_mul=1.03,
                                note_on_bounce=True, hud="speed", subtitle="+3% SPEED EVERY BOUNCE"),
        ["+3% speed on every bounce… it gets insane ⚡", "How fast can it go?"],
        ["+3% SPEED\nEVERY BOUNCE", "HOW FAST?"], "The ball gets 3% faster on every bounce. Watch the speedometer!",
        "La bille accélère de 3 % à chaque rebond. Regarde le compteur !", T_SAT + ["#speed"]),
    # ------------------------------------------------------------ Expériences mathématiques
    "21_x2_vs_half": C("race", dict(exp="x2_vs_half"),
        ["×2 vs ÷2 — who reaches the bottom first? 🤔", "1 ball ×2 vs 10 million ÷2"],
        ["×2 vs ÷2\nWHO WINS?", "GUESS THE\nWINNER"], "1 ball that doubles vs 10 million that halve. Comment your guess BEFORE the end! 👇",
        "Expérience : qui atteint le bas en premier ? Donne ton pronostic !", T_MATH + ["#satisfying"]),
    "22_plus1_vs_x2": C("race", dict(exp="plus1_vs_x2"),
        ["Can +1 beat ×2 with a head start?", "Linear vs exponential growth, explained with balls"],
        ["+1 vs ×2", "CAN +1\nWIN?"], "50 balls that add +1 vs 1 ball that doubles. Who wins?",
        "Croissance linéaire contre exponentielle : qui gagne ?", T_MATH + ["#satisfying"]),
    "23_risky_vs_safe": C("race", dict(exp="x3_fragile_vs_x2"),
        ["Risky ×3 or safe ×2? 🎲", "Would you take the risk?"],
        ["RISKY ×3\nOR SAFE ×2?", "TAKE THE\nRISK?"], "×3 but half of them die, vs a safe ×2. Which strategy wins?",
        "×3 mais la moitié meurt, contre ×2 sans risque. Quelle stratégie gagne ?", T_MATH + ["#strategy"]),
    "24_battle_royale": C("race", dict(exp="battle_royale"),
        ["4 rules, 1 winner — battle royale 👑", "+1, ×2, ×3 risky or ÷2… pick your champion"],
        ["4 RULES\n1 WINNER", "PICK YOUR\nCHAMPION"], "Four lanes, four rules. Pick your champion in the comments! 👇",
        "Quatre couloirs, quatre règles. Choisis ton champion en commentaire !", T_MATH + ["#battle"]),
    "25_risk_ladder": C("race", dict(exp="risk_ladder"),
        ["How much risk is worth it? ×2, ×3 or ×4", "The more it multiplies, the more it dies 🎲"],
        ["HOW MUCH\nRISK?", "×2  ×3  ×4"], "Safe ×2, ×3 with 50% deaths, ×4 with 75% deaths. Which one wins?",
        "×2 sûr, ×3 avec 50 % de morts, ×4 avec 75 %. Lequel gagne ?", T_MATH + ["#probability"]),
    "26_plus10_vs_x15": C("race", dict(exp="plus10_vs_x15"),
        ["+10 vs ×1.5 — slow and steady or exponential?", "Can a head start beat exponential growth?"],
        ["+10 vs ×1.5", "SLOW OR\nEXPONENTIAL?"], "100 balls adding +10 vs 1 ball growing ×1.5. Who reaches the bottom first?",
        "100 billes +10 contre 1 bille ×1,5. Qui arrive en bas en premier ?", T_MATH + ["#satisfying"]),
    # ------------------------------------------------------------ Autres
    "27_plinko": C("plinko", dict(mode="multi", start=1, subtitle="1 BALL → HOW MANY?"),
        ["Plinko where every bin multiplies your balls 🎰", "1 ball → how many after 60 seconds?"],
        ["1 BALL →\nHOW MANY?", "PLINKO\nMULTIPLIER"], "Every ball multiplies by the bin it lands in. Guess the final count!",
        "Chaque bille se multiplie selon la case où elle tombe. Devine le total !", T_SAT + ["#plinko"]),
    "28_plinko_deadly": C("plinko", dict(mode="deadly", start=5, subtitle="AVOID THE ☠ BINS"),
        ["Deadly plinko: will the balls survive? ☠️", "The middle kills, the edges multiply"],
        ["WILL THEY\nSURVIVE?", "DEADLY\nPLINKO"], "The middle bins kill, the edges multiply ×20. Will they survive?",
        "Les cases du milieu tuent, les bords multiplient. Vont-elles survivre ?", T_SAT + ["#plinko"]),
    "29_color_war": C("arena", dict(shape="circle", size=470, spin=0.2, gravity=0, vmin=450, start=80, cap=80, teams=True,
                                    hud="teams", subtitle="SLOWER BALL SWITCHES SIDE"),
        ["Red vs Blue — who takes over? 🔴🔵", "Color war: pick a side before the end!"],
        ["RED vs BLUE", "PICK A\nSIDE"], "When two colors collide, the slower ball switches sides. Who takes over?",
        "Quand deux couleurs se touchent, la plus lente change de camp. Qui gagne ?", T_SAT + ["#colorwar"]),
    "30_color_war_clones": C("arena", dict(shape=6, size=480, spin=0.3, gravity=300, vmin=450, start=6, cap=300, teams=True,
                                           wall="double", hud="teams", subtitle="BOUNCE = CLONE · TOUCH = CONVERT"),
        ["Red vs Blue: the multiplying war 🔴🔵", "Clones on every bounce, converts on every touch"],
        ["RED vs BLUE\nMULTIPLYING", "PICK A\nSIDE"], "Bounces clone, collisions convert. Which color takes the hexagon?",
        "Les rebonds clonent, les contacts convertissent. Quelle couleur gagne ?", T_SAT + ["#colorwar"]),
}

# Ordre de passage : les familles alternent (jamais deux concepts de la même famille deux jours de suite)
ORDER = ["01_wheel_blackhole", "21_x2_vs_half", "09_escape_circle", "15_grow_circle", "27_plinko",
         "02_hexagon_x3", "12_rings", "22_plus1_vs_x2", "18_strings_circle", "06_crusher_4",
         "29_color_war", "10_escape_square", "23_risky_vs_safe", "16_grow_hexagon", "03_good_bad_holes",
         "13_hex_rings", "24_battle_royale", "20_speed", "08_survival", "28_plinko_deadly",
         "04_three_holes", "11_escape_triangle", "25_risk_ladder", "17_grow_split", "07_crusher_2",
         "14_rings_clone", "30_color_war_clones", "05_bounce_clone", "26_plus10_vs_x15", "19_strings_triangle"]
assert sorted(ORDER) == sorted(CONCEPTS) and len(ORDER) == 30
START = 739931   # 11/11/2026 = premier jour du cycle (concept 01)


def concept_for_day(ordinal):
    """30 jours consécutifs = 30 concepts différents."""
    return ORDER[(ordinal - START) % 30]


def render(cid, seed, duration, scale, out):
    c = CONCEPTS[cid]
    eng, p = c["engine"], c["params"]
    sys.path.insert(0, HERE)
    if eng == "arena":
        import arena
        arena.run(dict(p, palette=seed), seed, duration, scale, out)
    elif eng == "plinko":
        import plinko
        plinko.run(p, seed, duration, scale, out)
    elif eng == "walls":
        import crusher_walls
        crusher_walls.run(seed, duration, scale, out, walls=p["walls"])
    elif eng == "wheel":
        pal = ["neon", "sunset", "toxic"][seed % 3]
        subprocess.run([sys.executable, "-W", "ignore", os.path.join(HERE, "wheel_blackhole.py"), "--palette", pal, "--seed", str(seed),
                        "--duration", str(duration), "--scale", str(scale), "--out", out], check=True, cwd=HERE)
    elif eng == "race":
        subprocess.run([sys.executable, "-W", "ignore", os.path.join(HERE, "race_towers.py"), "--exp", p["exp"], "--seed", str(seed),
                        "--duration", str(duration), "--scale", str(scale), "--out", out], check=True, cwd=HERE)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--concept", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=70)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default="out/concept.mp4")
    a = ap.parse_args()
    render(a.concept, a.seed, a.duration, a.scale, a.out)
