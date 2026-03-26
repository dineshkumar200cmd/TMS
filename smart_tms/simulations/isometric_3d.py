"""
AI Smart Traffic Management System — 3D Isometric Edition
==========================================================
Redesigned with:
  • Rich isometric city (buildings, trees, road markings)
  • Smooth 60-FPS animated vehicles with headlights + shadows
  • Professional dark HUD with live bar chart
  • Glowing traffic lights + animated signal state
  • Emergency ambulance override with siren flash
  • Explanation overlay so viewers instantly understand the algorithm
"""

import pygame
import sys, random, math, time, threading, io, requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pygame.init()

# ── Screen ────────────────────────────────────────────────────────────────────
W, H      = 1440, 900
PANEL_W   = 340
GAME_W    = W - PANEL_W
FPS       = 60
CYCLE_T   = 120

# ── Isometric grid ────────────────────────────────────────────────────────────
TW, TH    = 130, 65         # massive zoom into the intersection
GRID      = 16
ROAD_C    = {7, 8}          # which cols are road
ROAD_R    = {7, 8}          # which rows are road
OX        = GAME_W // 2     # isometric origin x
OY        = -120            # push camera up to keep center intercept in view

def iso(tx, ty, tz=0):
    sx = OX + (tx - ty) * (TW // 2)
    sy = OY + (tx + ty) * (TH // 2) - tz * 22
    return int(sx), int(sy)

def tile_top(tx, ty, h=0):
    return [iso(tx,   ty,   h), iso(tx+1, ty,   h),
            iso(tx+1, ty+1, h), iso(tx,   ty+1, h)]

def box_faces(tx, ty, h):
    top   = tile_top(tx, ty, h)
    left  = [iso(tx,   ty+1, h), iso(tx+1, ty+1, h),
             iso(tx+1, ty+1, 0), iso(tx,   ty+1, 0)]
    right = [iso(tx+1, ty,   h), iso(tx+1, ty+1, h),
             iso(tx+1, ty+1, 0), iso(tx+1, ty,   0)]
    return top, left, right

# ── Colour palette ────────────────────────────────────────────────────────────
P = dict(
    bg        = (  5,   7,  15),
    sky_top   = (  6,   9,  30),
    sky_bot   = ( 15,  25,  60),
    grass_a   = ( 35,  85,  35), # brighter grass
    grass_b   = ( 40,  95,  40),
    road      = ( 58,  62,  72), # lighter asphalt
    road_dark = ( 46,  50,  60),
    inter     = ( 50,  54,  66),
    lane      = (255, 230,  80), # brighter yellow
    stop      = (255, 255, 255),
    marking   = (200, 200, 200),
    panel     = ( 14,  18,  40),
    card      = ( 20,  26,  56),
    border    = ( 40,  54, 110),
    text      = (220, 230, 255),
    muted     = (100, 120, 170),
    accent    = ( 80, 150, 255),
    green_h   = ( 50, 230, 100),
    green_d   = ( 20, 140,  55),
    yellow_h  = (255, 220,  40),
    yellow_d  = (160, 120,   0),
    red_h     = (255,  60,  60),
    red_d     = (140,  20,  20),
    blue_h    = (100, 180, 255),
    shadow    = (  0,   0,   0),
)

V_COLORS = [
    (100,160,255),(100,220,130),(255,180, 80),(200,100,220),
    (80, 200,200),(255,120,120),(130,180,255),(255,200,100),
]

# ── Smart Traffic AI ─────────────────────────────────────────────────────────
class TrafficAI:
    ROADS = ["North","South","East","West"]

    def __init__(self):
        self.waiting    = {r: 0  for r in self.ROADS}
        self.emergency  = {r: False for r in self.ROADS}
        self.green_times= {r: 30 for r in self.ROADS}
        self.active     = "North"
        self.state      = "RED"
        self.time_left  = 0
        self.cycle      = 0
        self.served     = 0
        self.api_url    = "http://127.0.0.1:5000/api"

    def recalculate(self):
        """Fetch live state from API and detect new emergency triggers."""
        new_emergencies = []
        try:
            resp = requests.get(f"{self.api_url}/status", timeout=0.15).json()
            latest_emg = resp['controller']['emergency']
            
            # Detect transitions from False -> True
            for r in self.ROADS:
                if latest_emg[r] and not self.emergency[r]:
                    new_emergencies.append(r)

            self.green_times = resp['controller']['calculated_green_times']
            self.emergency = latest_emg
            self.active    = resp['engine']['active_road']
            self.state     = resp['engine']['state']
            self.time_left = resp['engine']['time_left']
        except:
            pass
        return new_emergencies
            
    def push_waiting(self, road, count):
        try:
            requests.post(f"{self.api_url}/mock_traffic", json={"road": road, "count": count}, timeout=0.05)
        except:
            pass

    def is_green(self, road):
        return self.active == road and self.state == "GREEN"

# ── Vehicle ───────────────────────────────────────────────────────────────────
STOP_TILE = {"North":6.8, "South":9.2, "East":6.8, "West":9.2}

class Vehicle:
    _uid = 0
    def __init__(self, road, ai, emg=False):
        Vehicle._uid += 1
        self.uid  = Vehicle._uid
        self.road = road
        self.ai   = ai
        self.emg  = emg
        self.alive     = True
        self.crossed   = False
        self.served_f  = False
        self.speed     = 0.0
        self.max_speed = 0.055 if not emg else 0.09
        self.accel     = 0.0025
        self.brake     = 0.006
        self.color     = (220,50,50) if emg else random.choice(V_COLORS)
        self.flash_t   = 0
        self.trail     = []   # exhaust particles

        # Spawn outside grid
        if   road == "North": self.tx, self.ty, self.dx, self.dy = 7.6, -1.0,  0,  1
        elif road == "South": self.tx, self.ty, self.dx, self.dy = 8.3, 17.0,  0, -1
        elif road == "East":  self.tx, self.ty, self.dx, self.dy = 17.0, 7.6, -1,  0
        else:                 self.tx, self.ty, self.dx, self.dy = -1.0, 8.3,  1,  0

    # ─ physics helpers ────────────────────────────────────────────────────────
    def lead_coord(self):
        if self.road in ("North","South"): return self.ty
        return self.tx

    def dist_stop(self):
        st = STOP_TILE[self.road]
        if self.road == "North": return st - self.ty
        if self.road == "South": return self.ty - st
        if self.road == "East":  return self.tx - st
        return st - self.tx   # West

    def dist_ahead(self, other):
        if self.road == "North": return other.ty - self.ty - 0.55
        if self.road == "South": return self.ty - other.ty - 0.55
        if self.road == "East":  return self.tx - other.tx - 0.55
        return other.tx - self.tx - 0.55

    # ─ update ─────────────────────────────────────────────────────────────────
    def update(self, ahead):
        tgt = self.max_speed

        if not self.crossed:
            d = self.dist_stop()
            if 0 < d < 3.5 and not self.ai.is_green(self.road):
                tgt = max(0.0, d * 0.035)
            if d < -0.3:
                self.crossed = True
                if not self.served_f:
                    self.served_f = True
                    self.ai.served += 1

        if ahead:
            gap = self.dist_ahead(ahead)
            if 0 < gap < 2.2:
                tgt = min(tgt, max(0.0, (gap - 0.4) * 0.06))

        self.speed += (self.accel if self.speed < tgt else -self.brake)
        self.speed  = max(0.0, min(self.speed, tgt))

        self.tx += self.dx * self.speed
        self.ty += self.dy * self.speed

        self.flash_t += 1

        # Off-screen
        if not (-2 < self.tx < GRID+2 and -2 < self.ty < GRID+2):
            self.alive = False
            if self.emg: 
                self.ai.emergency[self.road] = False
                # Notify backend that emergency is over
                try:
                    requests.post(f"http://127.0.0.1:5000/api/override", 
                                  json={"road": self.road, "status": False}, timeout=0.1)
                except: pass

    # ─ draw ───────────────────────────────────────────────────────────────────
    def draw(self, surf, tick):
        tx, ty = self.tx, self.ty
        W_CAR, D_CAR, H_CAR = 0.58, 0.32, 0.22 # Bigger proportions

        # Shadow
        cx, cy = iso(tx + W_CAR/2, ty + D_CAR/2, 0)
        shadow_surf = pygame.Surface((70, 35), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0,0,0,120), shadow_surf.get_rect())
        surf.blit(shadow_surf, (cx-35, cy-17))

        # Body
        pts_top = [iso(tx,        ty,        H_CAR),
                   iso(tx+W_CAR,  ty,        H_CAR),
                   iso(tx+W_CAR,  ty+D_CAR,  H_CAR),
                   iso(tx,        ty+D_CAR,  H_CAR)]
        pts_lft = [iso(tx,        ty+D_CAR,  H_CAR),
                   iso(tx+W_CAR,  ty+D_CAR,  H_CAR),
                   iso(tx+W_CAR,  ty+D_CAR,  0),
                   iso(tx,        ty+D_CAR,  0)]
        pts_rgt = [iso(tx+W_CAR,  ty,        H_CAR),
                   iso(tx+W_CAR,  ty+D_CAR,  H_CAR),
                   iso(tx+W_CAR,  ty+D_CAR,  0),
                   iso(tx+W_CAR,  ty,        0)]

        col   = self.color
        dark  = tuple(max(0,c-70) for c in col)
        mid   = tuple(max(0,c-40) for c in col)

        pygame.draw.polygon(surf, col,  pts_top)
        pygame.draw.polygon(surf, dark, pts_lft)
        pygame.draw.polygon(surf, mid,  pts_rgt)
        pygame.draw.polygon(surf, (0,0,0), pts_top, 1)

        # Roof window
        wm = 0.10
        win = [iso(tx+wm,       ty+wm,       H_CAR+0.001),
               iso(tx+W_CAR-wm, ty+wm,       H_CAR+0.001),
               iso(tx+W_CAR-wm, ty+D_CAR-wm, H_CAR+0.001),
               iso(tx+wm,       ty+D_CAR-wm, H_CAR+0.001)]
        pygame.draw.polygon(surf, (140,200,230), win)

        # Headlights
        hl_col = (255,255,180)
        for hx in (tx+0.08, tx+W_CAR-0.08):
            hpos = iso(hx, ty if self.dy>=0 else ty+D_CAR, 0.05)
            pygame.draw.circle(surf, hl_col, hpos, 3)

        # Emergency siren
        if self.emg:
            on = (self.flash_t // 8) % 2
            sc = (255,80,80) if on else (80,80,255)
            sp = iso(tx + W_CAR/2, ty + D_CAR/2, H_CAR + 0.05)
            pygame.draw.circle(surf, sc, sp, 5)
            # Glow ring
            gs = pygame.Surface((26,26), pygame.SRCALPHA)
            gc = sc + (60,)
            pygame.draw.circle(gs, gc, (13,13), 12)
            surf.blit(gs, (sp[0]-13, sp[1]-13))

    def is_waiting(self):
        return not self.crossed and self.speed < 0.008


# ── Buildings ─────────────────────────────────────────────────────────────────
def draw_building(surf, tx, ty, floors, col):
    h = floors * 0.55
    top, left, right = box_faces(tx, ty, h)
    dark  = tuple(max(0,c-60) for c in col)
    shade = tuple(max(0,c-30) for c in col)
    pygame.draw.polygon(surf, col,   top)
    pygame.draw.polygon(surf, dark,  left)
    pygame.draw.polygon(surf, shade, right)
    for poly in (top, left, right):
        pygame.draw.polygon(surf, (0,0,0), poly, 1)
    # Windows per floor
    for fl in range(1, floors+1):
        fh = fl * 0.55 - 0.15
        for wx in (0.2, 0.6):
            wpos = iso(tx + wx, ty + 0.75, fh)
            wc = (220,230,100) if random.random() > 0.35 else (30,35,70)
            pygame.draw.rect(surf, wc, (*wpos, 5, 7))
        for wy in (0.2, 0.6):
            wpos = iso(tx + 0.85, ty + wy, fh)
            wc = (220,230,100) if random.random() > 0.35 else (30,35,70)
            pygame.draw.rect(surf, wc, (*wpos, 5, 7))

# ── Trees ─────────────────────────────────────────────────────────────────────
def draw_tree(surf, tx, ty):
    base = iso(tx+0.5, ty+0.5, 0)
    top  = iso(tx+0.5, ty+0.5, 0.8)
    pygame.draw.line(surf, (100,65,30), base, top, 3)
    for layer, rad in [(0.75,10),(0.55,14),(0.38,11)]:
        lp = iso(tx+0.5, ty+0.5, layer)
        pygame.draw.circle(surf, (30,100,30), lp, rad)
        pygame.draw.circle(surf, (40,130,40), lp, rad-3)

# ── Traffic light post ────────────────────────────────────────────────────────
def draw_signal_post(surf, tx, ty, state, road_active, sim_on, tick):
    base = iso(tx+0.5, ty+0.5, 0)
    top  = iso(tx+0.5, ty+0.5, 1.3)
    pygame.draw.line(surf, (70,70,80), base, top, 4)

    # Housing box
    bx, by = top[0]-10, top[1]-28
    pygame.draw.rect(surf, (20,20,25), (bx, by, 20, 52), border_radius=4)
    pygame.draw.rect(surf, (60,60,70), (bx, by, 20, 52), 1, border_radius=4)

    # Lights: red, yellow, green (top to bottom)
    for i, (lstate, bright, dark_c) in enumerate([
        ("RED",    P["red_h"],    P["red_d"]),
        ("YELLOW", P["yellow_h"], P["yellow_d"]),
        ("GREEN",  P["green_h"],  P["green_d"]),
    ]):
        active_light = (
            not sim_on and lstate == "RED"
        ) or (
            sim_on and road_active and state == lstate
        ) or (
            sim_on and not road_active and lstate == "RED"
        )

        lpos = (top[0], top[1] - 18 + i*16)
        col  = bright if active_light else dark_c

        # Glow
        if active_light:
            gs = pygame.Surface((28,28), pygame.SRCALPHA)
            gc = bright + (50,)
            pygame.draw.circle(gs, gc, (14,14), 13)
            surf.blit(gs, (lpos[0]-14, lpos[1]-14))

        pygame.draw.circle(surf, col, lpos, 7)
        pygame.draw.circle(surf, (0,0,0), lpos, 7, 1)


# ── Bar chart (matplotlib → pygame surface) ───────────────────────────────────
def make_chart(ai):
    fig, ax = plt.subplots(figsize=(2.9, 2.3), facecolor="#0E1228")
    ax.set_facecolor("#141830")

    roads = ai.ROADS
    smart = [ai.green_times[r] for r in roads]
    fixed = [30] * 4
    x = range(4)

    bars_fixed = ax.bar([i-0.21 for i in x], fixed, 0.38,
                        color="#334466", label="Fixed 30s", zorder=3)
    bars_smart = ax.bar([i+0.21 for i in x], smart, 0.38,
                        color="#3a8aff", label="AI Smart", zorder=3)

    # Highlight active road
    for i, road in enumerate(roads):
        if road == ai.active:
            col = ("#50e882" if ai.state=="GREEN"
                   else "#ffe040" if ai.state=="YELLOW"
                   else "#ff5555")
            bars_smart[i].set_color(col)

    for bar, val in zip(bars_smart, smart):
        if val > 0:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                    f"{val}s", color="white", fontsize=7,
                    ha="center", va="bottom", fontfamily="monospace")

    ax.set_xticks(list(x))
    ax.set_xticklabels([r[0] for r in roads], color="#aabbdd", fontsize=9)
    ax.tick_params(colors="#aabbdd", labelsize=7)
    ax.set_ylim(0, CYCLE_T + 15)
    ax.set_yticks([0, 30, 60, 90, 120])
    ax.yaxis.set_tick_params(labelsize=7, labelcolor="#aabbdd")
    ax.set_title("Green Time: Fixed vs AI", color="#aabbdd", fontsize=9, pad=4)
    ax.legend(facecolor="#141830", labelcolor="#aabbdd", fontsize=7,
              framealpha=0.8, loc="upper right")
    ax.spines["bottom"].set_color("#334466")
    ax.spines["left"].set_color("#334466")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#1e2a4a", linewidth=0.5, zorder=0)

    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=95, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return pygame.image.load(buf)


# ── Main Game ─────────────────────────────────────────────────────────────────
class TrafficGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("AI Smart Traffic Management System — 3D City")
        self.clock  = pygame.time.Clock()
        self.ai     = TrafficAI()
        self.vehicles = []
        self.running  = False
        self.tick     = 0
        self.chart_surf = None
        self.chart_age  = 999
        self.show_help  = True   # algorithm explanation overlay
        self.buttons    = []

        # Fonts
        self.fnt_xl  = pygame.font.SysFont("Consolas", 28, bold=True)
        self.fnt_lg  = pygame.font.SysFont("Consolas", 20, bold=True)
        self.fnt_md  = pygame.font.SysFont("Consolas", 15)
        self.fnt_sm  = pygame.font.SysFont("Consolas", 12)
        self.fnt_xsm = pygame.font.SysFont("Consolas", 11)

        # Seed buildings + trees
        rng = random.Random(7)
        self.buildings, self.trees = [], []
        zones = [(0,0,6,6),(10,0,6,6),(0,10,6,6),(10,10,6,6)]
        for bx,by,bw,bd in zones:
            for _ in range(5):
                btx = rng.randint(bx, bx+bw-2)
                bty = rng.randint(by, by+bd-2)
                if (btx in ROAD_C) or (bty in ROAD_R): continue
                bh  = rng.randint(2, 5)
                bc  = (rng.randint(45,100), rng.randint(50,100), rng.randint(70,150))
                self.buildings.append((btx, bty, bh, bc))
            for _ in range(4):
                ttx = rng.randint(bx, bx+bw-2)
                tty = rng.randint(by, by+bd-2)
                if (ttx in ROAD_C) or (tty in ROAD_R): continue
                self.trees.append((ttx+0.2, tty+0.2))

        # Pre-bake static ground into surface
        self.ground = pygame.Surface((GAME_W, H))
        self._bake_ground()

        # Start background threads
        threading.Thread(target=self._signal_loop,  daemon=True).start()
        threading.Thread(target=self._auto_spawn,   daemon=True).start()

    # ── Ground pre-bake ───────────────────────────────────────────────────────
    def _bake_ground(self):
        s = self.ground
        s.fill(P["bg"])

        # Sky gradient
        for gy in range(OY+10):
            t = gy / (OY+10)
            c = tuple(int(P["sky_top"][i] + t*(P["sky_bot"][i]-P["sky_top"][i])) for i in range(3))
            pygame.draw.line(s, c, (0, gy), (GAME_W, gy))

        # Ground tiles
        for ty in range(GRID):
            for tx in range(GRID):
                is_road = (tx in ROAD_C) or (ty in ROAD_R)
                is_inter= (tx in ROAD_C) and (ty in ROAD_R)
                if is_inter:
                    col = P["inter"]
                elif is_road:
                    col = P["road"] if (tx+ty)%2==0 else P["road_dark"]
                else:
                    col = P["grass_a"] if (tx+ty)%2==0 else P["grass_b"]
                pygame.draw.polygon(s, col, tile_top(tx, ty, 0))
                pygame.draw.polygon(s, (0,0,0), tile_top(tx, ty, 0), 1)

        # Lane centre lines (dashed yellow)
        for ty_c in range(GRID):
            if ty_c in ROAD_R: continue
            for seg in range(2):
                p1 = iso(7.48, ty_c + seg*0.55 + 0.05, 0.01)
                p2 = iso(7.48, ty_c + seg*0.55 + 0.35, 0.01)
                pygame.draw.line(s, P["lane"], p1, p2, 2)

        for tx_c in range(GRID):
            if tx_c in ROAD_C: continue
            for seg in range(2):
                p1 = iso(tx_c + seg*0.55 + 0.05, 7.48, 0.01)
                p2 = iso(tx_c + seg*0.55 + 0.35, 7.48, 0.01)
                pygame.draw.line(s, P["lane"], p1, p2, 2)

        # Stop lines (thick white)
        lines = [
            (iso(7.0, 6.78, 0.02), iso(8.0, 6.78, 0.02)),
            (iso(7.0, 9.22, 0.02), iso(8.0, 9.22, 0.02)),
            (iso(6.78, 7.0, 0.02), iso(6.78, 8.0, 0.02)),
            (iso(9.22, 7.0, 0.02), iso(9.22, 8.0, 0.02)),
        ]
        for p1, p2 in lines:
            pygame.draw.line(s, P["stop"], p1, p2, 4)

        # Zebra crossings
        for i in range(6):
            ox = 7.0 + i * (1.0/6)
            # North approach
            p1 = iso(ox,       6.62, 0.01)
            p2 = iso(ox+0.11,  6.62, 0.01)
            p3 = iso(ox+0.11,  6.72, 0.01)
            p4 = iso(ox,       6.72, 0.01)
            pygame.draw.polygon(s, P["marking"], [p1,p2,p3,p4])
            # South approach
            p1 = iso(ox,       9.28, 0.01)
            p2 = iso(ox+0.11,  9.28, 0.01)
            p3 = iso(ox+0.11,  9.38, 0.01)
            p4 = iso(ox,       9.38, 0.01)
            pygame.draw.polygon(s, P["marking"], [p1,p2,p3,p4])

        for i in range(6):
            oy = 7.0 + i * (1.0/6)
            p1 = iso(6.62, oy,      0.01); p2 = iso(6.72, oy,      0.01)
            p3 = iso(6.72, oy+0.11, 0.01); p4 = iso(6.62, oy+0.11, 0.01)
            pygame.draw.polygon(s, P["marking"], [p1,p2,p3,p4])
            p1 = iso(9.28, oy,      0.01); p2 = iso(9.38, oy,      0.01)
            p3 = iso(9.38, oy+0.11, 0.01); p4 = iso(9.28, oy+0.11, 0.01)
            pygame.draw.polygon(s, P["marking"], [p1,p2,p3,p4])

    def _signal_loop(self):
        """Continuously pulls from the backend and reacts to state changes."""
        while True:
            # Always check for emergency triggers, even if simulation is paused
            new_emgs = self.ai.recalculate()
            for road in new_emgs:
                self.spawn(road, emg=True, push_api=False)
                
            if not self.running:
                self.ai.state = "RED"
                time.sleep(0.4)
                continue
                
            time.sleep(0.5)

    def _auto_spawn(self):
        while True:
            if len(self.vehicles) < 28:
                road = random.choice(TrafficAI.ROADS)
                self.vehicles.append(Vehicle(road, self.ai))
            time.sleep(2.8)

    def spawn(self, road, emg=False, push_api=True):
        self.vehicles.append(Vehicle(road, self.ai, emg))
        if emg: 
            self.ai.emergency[road] = True
            if push_api:
                try:
                    requests.post(f"http://127.0.0.1:5000/api/override", 
                                  json={"road": road, "status": True}, timeout=0.1)
                except: pass

    def _road_state(self, road):
        if not self.running: return "RED"
        if self.ai.active == road: return self.ai.state
        return "RED"

    # ── Draw scene ────────────────────────────────────────────────────────────
    def _draw_scene(self):
        self.screen.blit(self.ground, (0, 0))

        # Depth-sort: buildings + trees by tx+ty
        objects = []
        for btx,bty,bh,bc in self.buildings:
            objects.append(("bld", btx+bty, btx, bty, bh, bc))
        for ttx,tty in self.trees:
            objects.append(("tree", ttx+tty, ttx, tty))
        objects.sort(key=lambda o: o[1])

        for obj in objects:
            if obj[0] == "bld":
                draw_building(self.screen, obj[2], obj[3], obj[4], obj[5])
            else:
                draw_tree(self.screen, obj[2], obj[3])

        # Traffic light posts
        sig_posts = {
            "North": (6.3,  6.3),
            "South": (8.7,  8.7),
            "East":  (6.3,  8.7),
            "West":  (8.7,  6.3),
        }
        for road, (tx, ty) in sig_posts.items():
            is_active = self.running and self.ai.active == road
            draw_signal_post(self.screen, tx, ty,
                             self._road_state(road),
                             is_active, self.running, self.tick)

        # Vehicles depth-sorted
        road_lanes = {r: [] for r in TrafficAI.ROADS}
        for v in self.vehicles:
            road_lanes[v.road].append(v)

        road_lanes["North"].sort(key=lambda v: v.ty, reverse=True)
        road_lanes["South"].sort(key=lambda v: v.ty)
        road_lanes["East" ].sort(key=lambda v: v.tx)
        road_lanes["West" ].sort(key=lambda v: v.tx, reverse=True)

        for v in sorted(self.vehicles, key=lambda v: v.tx + v.ty):
            lane = road_lanes[v.road]
            idx  = lane.index(v)
            v.update(lane[idx-1] if idx > 0 else None)
            v.draw(self.screen, self.tick)

        for road in TrafficAI.ROADS:
            c = sum(1 for v in road_lanes[road] if v.is_waiting())
            self.ai.waiting[road] = c
            if self.running and (self.tick % 30 == 0):
                self.ai.push_waiting(road, c)

        self.vehicles = [v for v in self.vehicles if v.alive]

        # Queue count badges near stop lines
        badge_pos = {
            "North": iso(6.2,  6.5,  0.3),
            "South": iso(8.8,  9.5,  0.3),
            "East":  iso(6.2,  9.0,  0.3),
            "West":  iso(9.5,  6.2,  0.3),
        }
        for road, bp in badge_pos.items():
            count = self.ai.waiting[road]
            bg_col = (P["red_d"] if count > 8
                      else P["yellow_d"] if count > 4
                      else P["card"])
            pygame.draw.rect(self.screen, bg_col,
                             (bp[0]-18, bp[1]-10, 36, 20), border_radius=10)
            pygame.draw.rect(self.screen, P["border"],
                             (bp[0]-18, bp[1]-10, 36, 20), 1, border_radius=10)
            lbl = self.fnt_sm.render(f"{count} 🚗", True, P["text"])
            self.screen.blit(lbl, (bp[0] - lbl.get_width()//2,
                                   bp[1] - lbl.get_height()//2))

        # Road name labels
        labels = {
            "NORTH": iso(7.5, 2.5, 0.1),
            "SOUTH": iso(7.5, 13.5, 0.1),
            "EAST":  iso(13.5, 7.5, 0.1),
            "WEST":  iso(2.5, 7.5, 0.1),
        }
        for name, pos in labels.items():
            lbl = self.fnt_sm.render(name, True, P["muted"])
            self.screen.blit(lbl, (pos[0]-lbl.get_width()//2, pos[1]))

        # Active road HUD
        if self.running:
            state = self.ai.state
            col = (P["green_h"] if state=="GREEN"
                   else P["yellow_h"] if state=="YELLOW"
                   else P["red_h"])
            hud = self.fnt_lg.render(
                f"▶  {self.ai.active.upper()} — {state}  {self.ai.time_left}s",
                True, col)
            pygame.draw.rect(self.screen, (*P["panel"], 200),
                             (8, 8, hud.get_width()+20, hud.get_height()+10),
                             border_radius=6)
            self.screen.blit(hud, (18, 13))

        # Emergency banner
        emg_road = next((r for r in TrafficAI.ROADS if self.ai.emergency[r]), None)
        if emg_road:
            flash = (self.tick // 15) % 2
            if flash:
                banner = self.fnt_lg.render(
                    f"🚨  EMERGENCY OVERRIDE — {emg_road.upper()} ROAD  🚨",
                    True, P["red_h"])
                bx = GAME_W//2 - banner.get_width()//2
                pygame.draw.rect(self.screen, (80,0,0),
                                 (bx-10, H-48, banner.get_width()+20, 36),
                                 border_radius=8)
                self.screen.blit(banner, (bx, H-44))

    # ── Draw HUD panel ────────────────────────────────────────────────────────
    def _draw_panel(self):
        px = GAME_W
        # Background
        pygame.draw.rect(self.screen, P["panel"], (px, 0, PANEL_W, H))
        pygame.draw.line(self.screen, P["border"], (px, 0), (px, H), 2)

        y = 16
        # Title
        t = self.fnt_xl.render("AI TRAFFIC TMS", True, P["accent"])
        self.screen.blit(t, (px + (PANEL_W-t.get_width())//2, y))
        y += 36
        sub = self.fnt_sm.render("Smart Signal Control System", True, P["muted"])
        self.screen.blit(sub, (px + (PANEL_W-sub.get_width())//2, y))
        y += 26

        pygame.draw.line(self.screen, P["border"], (px+10, y), (px+PANEL_W-10, y), 1)
        y += 12

        # Signal cards per road
        road_icons = {"North":"↓","South":"↑","East":"←","West":"→"}
        for road in TrafficAI.ROADS:
            state  = self._road_state(road)
            is_act = self.running and self.ai.active == road
            waiting= self.ai.waiting[road]
            gt     = self.ai.green_times[road]

            # Card background
            card_col = (25,55,30) if (is_act and state=="GREEN") else P["card"]
            pygame.draw.rect(self.screen, card_col,
                             (px+8, y, PANEL_W-16, 50), border_radius=8)
            pygame.draw.rect(self.screen, P["border"],
                             (px+8, y, PANEL_W-16, 50), 1, border_radius=8)

            # Signal dot
            sig_col = (P["green_h"] if state=="GREEN"
                       else P["yellow_h"] if state=="YELLOW"
                       else P["red_h"])
            pygame.draw.circle(self.screen, sig_col, (px+26, y+25), 10)
            if is_act and state in ("GREEN","YELLOW"):
                gs = pygame.Surface((30,30), pygame.SRCALPHA)
                pygame.draw.circle(gs, sig_col+(50,), (15,15), 14)
                self.screen.blit(gs, (px+11, y+10))

            # Road name + direction
            name_t = self.fnt_md.render(f"{road_icons[road]}  {road}", True, P["text"])
            self.screen.blit(name_t, (px+44, y+6))

            # Stats
            stats = f"Queue: {waiting}  |  Green: {gt}s"
            st_t = self.fnt_sm.render(stats, True, P["muted"])
            self.screen.blit(st_t, (px+44, y+26))

            # Timer countdown
            if is_act and self.running:
                tl_t = self.fnt_md.render(f"{self.ai.time_left}s", True, sig_col)
                self.screen.blit(tl_t, (px+PANEL_W-50, y+14))

            # Emergency tag
            if self.ai.emergency[road]:
                et = self.fnt_sm.render("🚑 OVERRIDE", True, P["red_h"])
                self.screen.blit(et, (px+PANEL_W-100, y+28))

            y += 58

        pygame.draw.line(self.screen, P["border"], (px+10, y), (px+PANEL_W-10, y), 1)
        y += 10

        # Stats row
        total_q = sum(self.ai.waiting.values())
        eff_label = self._efficiency_label()
        for label, val, col in [
            ("Total Queue", str(total_q),           P["accent"]),
            ("Served",      str(self.ai.served),    P["green_h"]),
            ("Cycles",      str(self.ai.cycle),     P["yellow_h"]),
            ("Efficiency",  eff_label,               P["green_h"]),
        ]:
            lbl_t = self.fnt_sm.render(label, True, P["muted"])
            val_t = self.fnt_md.render(val,   True, col)
            self.screen.blit(lbl_t, (px+14, y))
            self.screen.blit(val_t, (px+14, y+14))
            if label in ("Total Queue","Served"):
                # Second column
                pass
            y += 34 if label in ("Served","Efficiency") else 0

        y = H - 310   # anchor chart from bottom

        # Chart
        self.chart_age += 1
        if self.chart_age > 60 or self.chart_surf is None:
            self.chart_surf = make_chart(self.ai)
            self.chart_age  = 0
        if self.chart_surf:
            cx = px + (PANEL_W - self.chart_surf.get_width()) // 2
            self.screen.blit(self.chart_surf, (cx, y))
            y += self.chart_surf.get_height() + 8

        # Formula box
        pygame.draw.rect(self.screen, P["card"],
                         (px+8, y, PANEL_W-16, 44), border_radius=6)
        pygame.draw.rect(self.screen, P["border"],
                         (px+8, y, PANEL_W-16, 44), 1, border_radius=6)
        f1 = self.fnt_sm.render("Green = (queue / total) × 120s", True, P["accent"])
        f2 = self.fnt_xsm.render("More vehicles → longer green time", True, P["muted"])
        self.screen.blit(f1, (px + (PANEL_W-f1.get_width())//2, y+6))
        self.screen.blit(f2, (px + (PANEL_W-f2.get_width())//2, y+24))
        y += 52

        # Buttons
        self.buttons = []
        btn_defs = [
            ("▶  START CYCLE",  (px+10, y),      (150,32), P["green_d"],  "start"),
            ("■  STOP",         (px+168,y),      (150,32), P["red_d"],    "stop"),
        ]
        y += 38
        spawn_row = [
            (f"↓ N",  (px+10,  y), (70,28), (40,70,160), "sN"),
            (f"↑ S",  (px+87,  y), (70,28), (40,70,160), "sS"),
            (f"← E",  (px+164, y), (70,28), (40,70,160), "sE"),
            (f"→ W",  (px+241, y), (70,28), (40,70,160), "sW"),
        ]
        y += 34
        amb_row = [
            ("🚑 N", (px+10,  y), (70,28), (120,20,20), "aN"),
            ("🚑 S", (px+87,  y), (70,28), (120,20,20), "aS"),
            ("🚑 E", (px+164, y), (70,28), (120,20,20), "aE"),
            ("🚑 W", (px+241, y), (70,28), (120,20,20), "aW"),
        ]
        help_btn = [("? EXPLAIN",  (px+10, y+34), (308,28), P["card"], "help")]

        for group in (btn_defs, spawn_row, amb_row, help_btn):
            for label, pos, size, col, tag in group:
                r = pygame.Rect(pos, size)
                pygame.draw.rect(self.screen, col, r, border_radius=6)
                pygame.draw.rect(self.screen, P["border"], r, 1, border_radius=6)
                t = self.fnt_sm.render(label, True, P["text"])
                self.screen.blit(t, (r.x+(r.w-t.get_width())//2,
                                     r.y+(r.h-t.get_height())//2))
                self.buttons.append((r, tag))

        # ESC hint
        esc = self.fnt_xsm.render("ESC to quit", True, P["muted"])
        self.screen.blit(esc, (px+PANEL_W-esc.get_width()-8, H-16))

    # ── Algorithm explain overlay ─────────────────────────────────────────────
    def _draw_help(self):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))

        bw, bh = 700, 420
        bx, by = (W-bw)//2, (H-bh)//2
        pygame.draw.rect(self.screen, P["card"],
                         (bx, by, bw, bh), border_radius=16)
        pygame.draw.rect(self.screen, P["accent"],
                         (bx, by, bw, bh), 2, border_radius=16)

        lines = [
            (self.fnt_lg,  "🧠  How the AI Algorithm Works",     P["accent"]),
            (self.fnt_md,  "",                                   P["text"]),
            (self.fnt_md,  "STEP 1:  Count vehicles waiting at each road",  P["text"]),
            (self.fnt_sm,  "         North=40  South=10  East=70  West=30   Total=150", P["muted"]),
            (self.fnt_md,  "",                                   P["text"]),
            (self.fnt_md,  "STEP 2:  Apply the formula for each road:",      P["text"]),
            (self.fnt_sm,  "         Green Time = (vehicles / total) × 120s",P["accent"]),
            (self.fnt_md,  "",                                   P["text"]),
            (self.fnt_md,  "STEP 3:  Results:",                  P["text"]),
            (self.fnt_sm,  "         North →  (40/150) × 120  =  32 seconds", P["green_h"]),
            (self.fnt_sm,  "         South →  (10/150) × 120  =   8 seconds", P["yellow_h"]),
            (self.fnt_sm,  "         East  →  (70/150) × 120  =  56 seconds ← busiest", P["green_h"]),
            (self.fnt_sm,  "         West  →  (30/150) × 120  =  24 seconds", P["yellow_h"]),
            (self.fnt_md,  "",                                   P["text"]),
            (self.fnt_md,  "STEP 4:  Emergency vehicle detected?",P["text"]),
            (self.fnt_sm,  "         → Override all signals → Immediate GREEN for that road", P["red_h"]),
            (self.fnt_md,  "",                                   P["text"]),
            (self.fnt_sm,  "              Press any key to close this panel", P["muted"]),
        ]
        y = by + 24
        for fnt, text, col in lines:
            t = fnt.render(text, True, col)
            self.screen.blit(t, (bx + 30, y))
            y += t.get_height() + 5

    def _efficiency_label(self):
        total = sum(self.ai.waiting.values())
        if total == 0: return "—"
        smart = sum(self.ai.green_times[r] * max(self.ai.waiting[r],1)
                    for r in TrafficAI.ROADS)
        fixed = 30 * total
        pct   = max(0, (fixed - smart) / fixed * 100)
        return f"+{min(pct,65):.0f}%"

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            self.tick += 1

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                    self.show_help = False

                if event.type == pygame.MOUSEBUTTONDOWN:
                    for rect, tag in self.buttons:
                        if rect.collidepoint(event.pos):
                            if   tag == "start": self.running = True
                            elif tag == "stop":  self.running = False
                            elif tag == "sN":    self.spawn("North")
                            elif tag == "sS":    self.spawn("South")
                            elif tag == "sE":    self.spawn("East")
                            elif tag == "sW":    self.spawn("West")
                            elif tag == "aN":    self.spawn("North", emg=True)
                            elif tag == "aS":    self.spawn("South", emg=True)
                            elif tag == "aE":    self.spawn("East",  emg=True)
                            elif tag == "aW":    self.spawn("West",  emg=True)
                            elif tag == "help":  self.show_help = True

            self.screen.fill(P["bg"])
            self._draw_scene()
            self._draw_panel()
            if self.show_help:
                self._draw_help()

            pygame.display.flip()


if __name__ == "__main__":
    game = TrafficGame()
    game.run()