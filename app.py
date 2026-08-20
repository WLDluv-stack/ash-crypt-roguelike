"""Ashen Crypt (Cripta de Ceniza): un roguelike ASCII para la terminal."""

import argparse
from contextlib import contextmanager
import os
import random
import select
import sys
import termios
import tty
from dataclasses import dataclass


BASE_WIDTH, BASE_HEIGHT = 64, 26
TOTAL_LEVELS = 10
BLOCKED_TERRAIN = {"#", "~", "O"}
MAX_ENEMIES = 12
MOVES = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}
ARROW_KEYS = {"[A": "w", "[B": "s", "[C": "d", "[D": "a"}
COLORS = {
    "wall": "\033[38;5;238m",
    "floor": "\033[38;5;252m",
    "hero": "\033[1;97;44m",
    "enemy": "\033[31m",
    "orc": "\033[33m",
    "boss": "\033[1;35m",
    "exit": "\033[36m",
    "potion": "\033[1;31m",
    "bomb": "\033[1;33m",
    "elixir": "\033[1;36m",
    "water": "\033[1;34m",
    "rubble": "\033[33m",
    "column": "\033[1;37m",
    "bones": "\033[37m",
    "moss": "\033[32m",
    "crystal": "\033[1;35m",
    "good": "\033[1;32m",
    "warning": "\033[1;33m",
    "danger": "\033[1;31m",
    "muted": "\033[90m",
}
RESET = "\033[0m"
TEXT = {
    "es": {
        "title": "CRIPTA DE CENIZA",
        "subtitle": "Un roguelike ASCII de exploracion y combate",
        "choose": "Elige idioma: [S] Espanol  [E] English",
        "start": "Pulsa ENTER para comenzar",
        "level": "NIVEL",
        "map": "MAPA",
        "health": "VIDA",
        "items": "OBJETOS",
        "kills": "BAJAS",
        "total_kills": "Bajas totales",
        "xp_total": "XP acumulada",
        "legend": "LEYENDA",
        "controls": "CONTROLES",
        "player": "JUGADOR",
        "enemy": "ENEMIGO",
        "boss": "JEFE",
        "water": "AGUA",
        "column": "COLUMNA",
        "exit": "SALIDA",
        "potion": "Pocion",
        "bomb": "Bomba",
        "elixir": "Elixir",
        "move": "mover",
        "potion_key": "pocion",
        "bomb_key": "bomba",
        "elixir_key": "elixir",
        "inventory": "inventario",
        "quit": "salir",
        "arrows": "Flechas",
        "status": "ESTADO",
        "message": "MENSAJE",
        "level_complete": "NIVEL COMPLETADO",
        "defeated": "Has derrotado a todos los enemigos del nivel",
        "press_enter_next": "Pulsa ENTER para descender al nivel",
    },
    "en": {
        "title": "ASHEN CRYPT",
        "subtitle": "An ASCII roguelike of exploration and combat",
        "choose": "Choose language: [S] Espanol  [E] English",
        "start": "Press ENTER to begin",
        "level": "LEVEL",
        "map": "MAP",
        "health": "HEALTH",
        "items": "ITEMS",
        "kills": "KILLS",
        "total_kills": "Total kills",
        "xp_total": "Total XP",
        "legend": "LEGEND",
        "controls": "CONTROLS",
        "player": "PLAYER",
        "enemy": "ENEMY",
        "boss": "BOSS",
        "water": "WATER",
        "column": "COLUMN",
        "exit": "EXIT",
        "potion": "Potion",
        "bomb": "Bomb",
        "elixir": "Elixir",
        "move": "move",
        "potion_key": "potion",
        "bomb_key": "bomb",
        "elixir_key": "elixir",
        "inventory": "inventory",
        "quit": "quit",
        "arrows": "Arrows",
        "status": "STATUS",
        "message": "MESSAGE",
        "level_complete": "LEVEL COMPLETED",
        "defeated": "You defeated every enemy on level",
        "press_enter_next": "Press ENTER to descend to level",
    },
}
MESSAGES = {
    "es": {
        "potion_use": "Bebes una pocion y recuperas {healed} HP.",
        "potion_empty": "No puedes usar una pocion ahora.",
        "bomb_empty": "No tienes bombas.",
        "bomb_hit": "La bomba alcanza a {count} enemigo(s) por {damage}.",
        "elixir_use": "El elixir te fortalece: golpeas mas fuerte y recibes menos dano durante 8 turnos.",
        "elixir_empty": "No tienes elixires.",
        "blocked": "Las piedras bloquean el paso.",
        "attack": "Golpeas a {name} por {damage}.",
        "defeated": " Ha caido!",
        "invalid": "Usa flechas/WASD, P pocion, B bomba, E elixir, I inventario o Q salir.",
        "collect": "Recoges {name}.",
        "hurt": " {name} te hiere por {damage}.",
        "descend": "Desciendes al nivel {level}.",
        "victory": "Has derrotado al Rey de la Cripta. La ceniza se aquieta. VICTORIA",
        "abandon": "Abandonas la cripta.",
        "defeat_end": "Tu antorcha se apaga. DERROTA",
    },
    "en": {
        "potion_use": "You drink a potion and recover {healed} HP.",
        "potion_empty": "You cannot use a potion right now.",
        "bomb_empty": "You have no bombs.",
        "bomb_hit": "The bomb hits {count} enemy/enemies for {damage}.",
        "elixir_use": "The elixir empowers you: stronger attacks and half damage taken for 8 turns.",
        "elixir_empty": "You have no elixirs.",
        "blocked": "The stones block your path.",
        "attack": "You hit {name} for {damage}.",
        "defeated": " Defeated!",
        "invalid": "Use arrows/WASD, P potion, B bomb, E elixir, I inventory or Q quit.",
        "collect": "You pick up {name}.",
        "hurt": " {name} hits you for {damage}.",
        "descend": "You descend to level {level}.",
        "victory": "You defeated the Crypt King. The ash grows still. VICTORY",
        "abandon": "You leave the crypt.",
        "defeat_end": "Your torch goes out. DEFEAT",
    },
}


@dataclass
class Actor:
    x: int
    y: int
    char: str
    name: str
    hp: int
    attack: int
    xp: int = 0
    boss: bool = False


@dataclass
class Item:
    x: int
    y: int
    char: str
    name: str
    kind: str


@contextmanager
def direct_input():
    """Lee teclas individuales y restaura la terminal incluso al salir."""
    if os.name == "nt" or not sys.stdin.isatty():
        yield
        return
    file_descriptor = sys.stdin.fileno()
    old_settings = termios.tcgetattr(file_descriptor)
    try:
        tty.setcbreak(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)


def read_key():
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip().lower()[:1]
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            return {"H": "w", "P": "s", "M": "d", "K": "a"}.get(key, "")
        return key.lower()
    key = sys.stdin.read(1)
    if key != "\033":
        return key.lower()
    sequence = ""
    while len(sequence) < 2 and select.select([sys.stdin], [], [], 0.05)[0]:
        sequence += sys.stdin.read(1)
    return ARROW_KEYS.get(sequence, "")


def start_screen():
    os.system("clear" if os.name != "nt" else "cls")
    print("\n" + "=" * 64)
    print("                 ASHEN CRYPT")
    print("       Cripta de Ceniza | ASCII roguelike")
    print("=" * 64)
    print("\nElige idioma / Choose language: [S] Espanol  [E] English")
    choice = input("> ").strip().lower()[:1]
    language = "en" if choice == "e" else "es"
    print(f"\n{TEXT[language]['title']}")
    print(TEXT[language]["subtitle"])
    input(f"\n{TEXT[language]['start']}... ")
    return language


def wait_for_enter():
    if not sys.stdin.isatty():
        sys.stdin.readline()
        return
    while True:
        if read_key() in ("\r", "\n"):
            return


class Game:
    def __init__(self, seed=None, language="es"):
        self.rng = random.Random(seed)
        self.language = language if language in TEXT else "es"
        self.text = TEXT[self.language]
        self.color_enabled = sys.stdout.isatty()
        self.level = 1
        self.width = BASE_WIDTH
        self.height = BASE_HEIGHT
        self.hero = Actor(0, 0, "@", "Aventurero", 28, 6)
        self.max_hp = 28
        self.inventory = {"pociones": 2, "bombas": 1, "elixires": 0}
        self.kills = 0
        self.xp = 0
        self.elixir_turns = 0
        self.message = "The crypt breathes in the darkness." if self.language == "en" else "La cripta respira en la oscuridad."
        self.make_level()

    def make_level(self):
        self.width = BASE_WIDTH + (self.level - 1) * 16
        self.height = BASE_HEIGHT
        self.map = [["#" for _ in range(self.width)] for _ in range(self.height)]
        rooms = []
        room_count = 8 + self.level
        for _ in range(room_count):
            room_w = self.rng.randint(5, 10)
            room_h = self.rng.randint(4, 7)
            x = self.rng.randint(1, self.width - room_w - 2)
            y = self.rng.randint(1, self.height - room_h - 2)
            for row in range(y, y + room_h):
                for col in range(x, x + room_w):
                    self.map[row][col] = "."
            if rooms:
                old_x, old_y = rooms[-1]
                for col in range(min(old_x, x), max(old_x, x) + 1):
                    self.map[old_y][col] = "."
                for row in range(min(old_y, y), max(old_y, y) + 1):
                    self.map[row][x] = "."
            rooms.append((x + room_w // 2, y + room_h // 2))

        self.decorate_map(rooms)
        self.ensure_room_connections(rooms)
        self.hero.x, self.hero.y = rooms[0]
        self.exit = rooms[-1]
        self.enemies = []
        self.items = []
        enemy_types = [
            ("g", "Ghoul", 7, 3, 8),
            ("o", "Orco", 12, 4, 14),
        ]
        if self.level >= 3:
            enemy_types.append(("v", "Vampiro", 16, 5, 20))
        if self.level >= 6:
            enemy_types.append(("c", "Cultista", 20, 6, 26))
        occupied = {self.hero_position()}
        enemy_count = min(MAX_ENEMIES, 3 + self.level // 2)
        for _ in range(enemy_count):
            x, y = self.random_floor(rooms, occupied)
            occupied.add((x, y))
            char, name, hp, attack, xp = self.rng.choice(enemy_types)
            self.enemies.append(Actor(x, y, char, self.localize_name(name), hp + self.level * 2, attack + self.level // 3, xp))
        if self.level in (5, TOTAL_LEVELS):
            x, y = self.exit
            boss_name = self.localize_name("Guardian del Abismo" if self.level == 5 else "Rey de la Cripta")
            boss_hp = 55 + self.level * 8
            if len(self.enemies) < MAX_ENEMIES:
                self.enemies.append(Actor(x, y, "B", boss_name, boss_hp, 8 + self.level // 2, 100, True))
        item_types = [("!", "Pocion", "pociones"), ("*", "Bomba", "bombas")]
        if self.level >= 3:
            item_types.append(("+", "Elixir de vigor", "elixires"))
        for _ in range(2 + self.level // 2):
            x, y = self.random_floor(rooms, occupied)
            occupied.add((x, y))
            char, name, kind = self.rng.choice(item_types)
            self.items.append(Item(x, y, char, self.localize_name(name), kind))
        self.map[self.exit[1]][self.exit[0]] = ">"

    def hero_position(self):
        return self.hero.x, self.hero.y

    def localize_name(self, name):
        if self.language == "en":
            return {
                "Ghoul": "Ghoul",
                "Orco": "Orc",
                "Vampiro": "Vampire",
                "Cultista": "Cultist",
                "Guardian del Abismo": "Abyss Guardian",
                "Rey de la Cripta": "Crypt King",
                "Pocion": "Potion",
                "Bomba": "Bomb",
                "Elixir de vigor": "Vigor Elixir",
            }.get(name, name)
        return name

    def decorate_map(self, rooms):
        """Viste las salas con agua, columnas y restos sin tocar entradas ni salida."""
        for room_x, room_y in rooms[1:-1]:
            if self.rng.random() < 0.8:
                water_cells = [(room_x, room_y)]
                if self.rng.random() < 0.65:
                    water_cells.append((room_x + 1, room_y))
                if self.rng.random() < 0.45:
                    water_cells.append((room_x, room_y + 1))
                for x, y in water_cells:
                    if self.map[y][x] == ".":
                        self.map[y][x] = "~"
            if self.rng.random() < 0.7:
                for dx, dy in ((-2, -1), (2, 1)):
                    x, y = room_x + dx, room_y + dy
                    if self.map[y][x] == ".":
                        self.map[y][x] = "O"
            for _ in range(self.rng.randint(1, 3)):
                x = room_x + self.rng.randint(-2, 2)
                y = room_y + self.rng.randint(-2, 2)
                if self.map[y][x] == ".":
                    self.map[y][x] = self.rng.choice([",", ":", ";", "^"])

    def ensure_room_connections(self, rooms):
        """Reabre los corredores despues de decorar para que nunca queden bloqueados."""
        for first, second in zip(rooms, rooms[1:]):
            first_x, first_y = first
            second_x, second_y = second
            for x in range(min(first_x, second_x), max(first_x, second_x) + 1):
                self.map[first_y][x] = "."
            for y in range(min(first_y, second_y), max(first_y, second_y) + 1):
                self.map[y][second_x] = "."

    def random_floor(self, rooms, occupied):
        while True:
            x, y = self.rng.choice(rooms)
            x += self.rng.randint(-2, 2)
            y += self.rng.randint(-2, 2)
            if self.map[y][x] == "." and (x, y) not in occupied:
                return x, y

    def render(self):
        if self.color_enabled:
            print("\033[2J\033[H", end="")
        else:
            os.system("clear" if os.name != "nt" else "cls")
        grid = [row[:] for row in self.map]
        for item in self.items:
            grid[item.y][item.x] = item.char
        for enemy in self.enemies:
            grid[enemy.y][enemy.x] = enemy.char
        grid[self.hero.y][self.hero.x] = self.hero.char
        print("+" + "-" * self.width + "+")
        for row in grid:
            print("|" + "".join(self.paint_cell(cell) for cell in row) + "|")
        print("+" + "-" * self.width + "+")
        filled = max(0, min(20, round(20 * self.hero.hp / self.max_hp)))
        hp_bar = "#" * filled + "." * (20 - filled)
        hp_color = "good" if self.hero.hp > self.max_hp // 2 else "warning" if self.hero.hp > 0 else "danger"
        inventory = self.inventory
        print(f" {self.text['level']} {self.level:02d}/{TOTAL_LEVELS}   {self.text['map']} {self.width}x{self.height}   {self.paint(self.text['health'], hp_color)} {self.paint('[' + hp_bar + ']', hp_color)} {self.hero.hp}/{self.max_hp}")
        print(f" {self.text['items']}   {self.paint('! ' + self.text['potion'], 'potion')} x{inventory['pociones']}   {self.paint('* ' + self.text['bomb'], 'bomb')} x{inventory['bombas']}   {self.paint('+ ' + self.text['elixir'], 'elixir')} x{inventory['elixires']}   XP {self.xp}   {self.text['kills']} {self.kills}")
        if self.elixir_turns:
            active = "ELIXIR ACTIVO" if self.language == "es" else "ELIXIR ACTIVE"
            effect = "dano aumentado y dano recibido reducido" if self.language == "es" else "increased damage and reduced damage taken"
            turns = "turnos" if self.language == "es" else "turns"
            print(f" {self.text['status']}    {self.paint(active, 'elixir')} - {effect} ({self.elixir_turns} {turns})")
        boss = next((enemy for enemy in self.enemies if enemy.boss), None)
        if boss:
            boss_max_hp = 55 + self.level * 8
            boss_bar = "#" * max(0, round(20 * boss.hp / boss_max_hp))
            print(f"{self.paint(self.text['boss'], 'boss')}: {boss.name} {self.paint('[' + boss_bar + ']', 'boss')} {boss.hp}/{boss_max_hp}")
        print(f" {self.text['legend']}  " + " | ".join((
            f"{self.paint('@', 'hero')} {self.text['player']}",
            f"{self.paint('g', 'enemy')} {self.text['enemy']}",
            f"{self.paint('B', 'boss')} {self.text['boss']}",
            f"{self.paint('~', 'water')} {self.text['water']}",
            f"{self.paint('O', 'column')} {self.text['column']}",
            f"{self.paint('>', 'exit')} {self.text['exit']}",
        )))
        print(f" {self.text['controls']}  {self.text['arrows']}/WASD {self.text['move']} | P {self.text['potion_key']} | B {self.text['bomb_key']} | E {self.text['elixir_key']} | I {self.text['inventory']} | Q {self.text['quit']}")
        print(self.format_message())

    def render_level_complete(self):
        if self.color_enabled:
            print("\033[2J\033[H", end="")
        else:
            os.system("clear" if os.name != "nt" else "cls")
        print("\n" + "=" * 64)
        print(self.paint(f"             {self.text['level_complete']}", "good"))
        print("=" * 64)
        print(f"{self.text['defeated']} {self.level}.")
        print(f"{self.text['total_kills']}: {self.kills}    {self.text['xp_total']}: {self.xp}")
        print(f"\n{self.text['press_enter_next']} {self.level + 1}: {self.paint('ENTER', 'warning')}")
        print("=" * 64)

    def paint(self, text, color):
        if not self.color_enabled:
            return text
        return f"{COLORS[color]}{text}{RESET}"

    def say(self, key, **values):
        return MESSAGES[self.language][key].format(**values)

    def format_message(self):
        if "bloquean" in self.message or "No tienes" in self.message or "block" in self.message or "no bombs" in self.message or "no elixirs" in self.message:
            icon, color = "!", "warning"
        elif "hiere" in self.message or "dano" in self.message or "caido" in self.message or "hits you" in self.message or "damage" in self.message or "Defeated" in self.message:
            icon, color = "*", "danger"
        elif "recoges" in self.message or "recuperas" in self.message or "fortalece" in self.message or "pick up" in self.message or "recover" in self.message or "empowers" in self.message:
            icon, color = "+", "good"
        else:
            icon, color = ">", "muted"
        banner = f" {icon} {self.message} "
        return self.paint(f" {self.text['message']} " + banner.center(58, "="), color)

    def paint_cell(self, cell):
        color = {"#": "wall", ".": "floor", "~": "water", "O": "column", ",": "rubble", ":": "bones", ";": "moss", "^": "crystal", "@": "hero", "g": "enemy", "o": "orc", "v": "enemy", "c": "enemy", "B": "boss", ">": "exit", "!": "potion", "*": "bomb", "+": "elixir"}[cell]
        return self.paint(cell, color)

    def enemy_at(self, x, y):
        return next((enemy for enemy in self.enemies if enemy.x == x and enemy.y == y), None)

    def take_turn(self, command):
        if command == "q":
            return False
        if command == "i":
            labels = {
                "pociones": self.text["potion"],
                "bombas": self.text["bomb"],
                "elixires": self.text["elixir"],
            }
            self.message = " | ".join(f"{labels[name]}: {amount}" for name, amount in self.inventory.items())
            return True
        if command == "p":
            if self.inventory["pociones"] and self.hero.hp < self.max_hp:
                self.inventory["pociones"] -= 1
                healed = min(8, self.max_hp - self.hero.hp)
                self.hero.hp += healed
                self.message = self.say("potion_use", healed=healed)
            else:
                self.message = self.say("potion_empty")
        elif command == "b":
            if not self.inventory["bombas"]:
                self.message = self.say("bomb_empty")
            else:
                targets = [enemy for enemy in self.enemies if abs(enemy.x - self.hero.x) + abs(enemy.y - self.hero.y) <= 2]
                self.inventory["bombas"] -= 1
                damage = 12 + self.level
                for enemy in targets:
                    enemy.hp -= damage
                defeated = [enemy for enemy in targets if enemy.hp <= 0]
                for enemy in defeated:
                    self.enemies.remove(enemy)
                    self.kills += 1
                    self.xp += enemy.xp
                self.message = self.say("bomb_hit", count=len(targets), damage=damage)
                if not self.enemies:
                    if self.level == TOTAL_LEVELS:
                        return "won"
                    return "level_complete"
        elif command == "e":
            if self.inventory["elixires"]:
                self.inventory["elixires"] -= 1
                self.max_hp += 5
                self.hero.hp = min(self.max_hp, self.hero.hp + 14)
                self.hero.attack += 1
                self.elixir_turns = 8
                self.message = self.say("elixir_use")
            else:
                self.message = self.say("elixir_empty")
        elif command in MOVES:
            dx, dy = MOVES[command]
            target_x, target_y = self.hero.x + dx, self.hero.y + dy
            if not (0 <= target_x < self.width and 0 <= target_y < self.height) or self.map[target_y][target_x] in BLOCKED_TERRAIN:
                self.message = self.say("blocked")
            else:
                enemy = self.enemy_at(target_x, target_y)
                if enemy:
                    damage = self.rng.randint(max(1, self.hero.attack - 2), self.hero.attack + 2)
                    if self.elixir_turns:
                        damage += 4
                    enemy.hp -= damage
                    self.message = self.say("attack", name=enemy.name, damage=damage)
                    if enemy.hp <= 0:
                        self.enemies.remove(enemy)
                        self.kills += 1
                        self.xp += enemy.xp
                        self.hero.attack += 1 if enemy.boss else 0
                        self.message += self.say("defeated")
                        if not self.enemies:
                            if self.level == TOTAL_LEVELS:
                                return "won"
                            return "level_complete"
                else:
                    self.hero.x, self.hero.y = target_x, target_y
                    self.collect_item()
                    if (target_x, target_y) == self.exit and not self.enemies:
                        if self.level == TOTAL_LEVELS:
                            return "won"
                        self.level += 1
                        self.max_hp += 2 + self.level
                        self.hero.hp = self.max_hp
                        self.make_level()
                        self.message = self.say("descend", level=self.level)
        else:
            self.message = self.say("invalid")
        self.enemies_act()
        return True

    def collect_item(self):
        item = next((item for item in self.items if (item.x, item.y) == self.hero_position()), None)
        if item:
            self.items.remove(item)
            self.inventory[item.kind] += 1
            self.message = self.say("collect", name=item.name)

    def enemies_act(self):
        for enemy in self.enemies:
            distance = abs(enemy.x - self.hero.x) + abs(enemy.y - self.hero.y)
            if distance == 1:
                damage = self.rng.randint(max(1, enemy.attack - 2), enemy.attack)
                if self.elixir_turns:
                    damage = max(1, damage // 2)
                self.hero.hp -= damage
                self.message += self.say("hurt", name=enemy.name, damage=damage)
            elif distance <= 8:
                dx = (self.hero.x > enemy.x) - (self.hero.x < enemy.x)
                dy = (self.hero.y > enemy.y) - (self.hero.y < enemy.y)
                next_x, next_y = enemy.x + dx, enemy.y + dy
                if self.map[next_y][next_x] not in BLOCKED_TERRAIN and not self.enemy_at(next_x, next_y):
                    enemy.x, enemy.y = next_x, next_y
        if self.elixir_turns:
            self.elixir_turns -= 1

    def run(self):
        with direct_input():
            while self.hero.hp > 0:
                self.render()
                result = self.take_turn(read_key())
                if result == "level_complete":
                    self.render_level_complete()
                    wait_for_enter()
                    self.level += 1
                    self.max_hp += 2 + self.level
                    self.hero.hp = self.max_hp
                    self.make_level()
                    self.message = self.say("descend", level=self.level)
                    continue
                if result == "won":
                    self.render()
                    print("\n" + self.say("victory"))
                    return
                if result is False:
                    print("\n" + self.say("abandon"))
                    return
            self.render()
            print("\n" + self.say("defeat_end"))


def main():
    parser = argparse.ArgumentParser(description="Roguelike ASCII por turnos")
    parser.add_argument("--seed", type=int, help="semilla para repetir un mapa")
    args = parser.parse_args()
    language = start_screen()
    Game(args.seed, language).run()


if __name__ == "__main__":
    main()