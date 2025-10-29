import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


def _default_task_pool() -> Dict[str, List[str]]:
    """Provide starter tasks so the app works out of the box."""
    return {
        "common": [
            "Scan ID card",
            "Fix wiring in cafeteria",
            "Swipe admin badge",
        ],
        "long": [
            "Calibrate distributor",
            "Fuel engines",
            "Inspect sample",
            "Align engine output",
        ],
        "fast": [
            "Prime shields",
            "Chart course",
            "Empty garbage",
            "Stabilize steering",
            "Download data in weapons",
            "Submit asteroid report",
            "Divert power to navigation",
        ],
    }


@dataclass
class Player:
    player_id: str
    name: str
    ready: bool = False
    role: Optional[str] = None  # "crewmate" or "impostor"
    tasks: Dict[str, List[str]] = field(default_factory=dict)
    kill_cooldown_end: float = 0.0

    def lobby_payload(self, current_id: str) -> Dict[str, object]:
        return {
            "name": self.name,
            "ready": self.ready,
            "is_me": self.player_id == current_id,
        }

    def kill_cooldown_remaining(self) -> int:
        remaining = max(0.0, self.kill_cooldown_end - time.time())
        return int(remaining)


class GameState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.players: Dict[str, Player] = {}
        self.status: str = "lobby"  # lobby | in_game
        self.round_number: int = 0
        self.config = {
            "required_players": 2,
            "impostors": 1,
            "task_counts": {"common": 1, "long": 1, "fast": 3},
            "kill_cooldown": 120,
        }
        self.task_pool = _default_task_pool()

    def current_player(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def add_player(self, name: str) -> Player:
        with self._lock:
            player_id = str(uuid.uuid4())
            new_player = Player(player_id=player_id, name=name.strip())
            self.players[player_id] = new_player
            return new_player

    def remove_player(self, player_id: str) -> None:
        with self._lock:
            self.players.pop(player_id, None)

    def toggle_ready(self, player_id: str, ready: bool) -> bool:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return False
            player.ready = ready
            return True

    def everyone_ready(self) -> bool:
        with self._lock:
            return self._everyone_ready_unlocked()

    def _everyone_ready_unlocked(self) -> bool:
        return bool(self.players) and all(p.ready for p in self.players.values())

    def can_start(self) -> bool:
        with self._lock:
            has_required_count = len(self.players) >= self.config["required_players"]
            return self.status == "lobby" and has_required_count and self._everyone_ready_unlocked()

    def _pick_tasks(self) -> Dict[str, List[str]]:
        tasks: Dict[str, List[str]] = {}
        for category, count in self.config["task_counts"].items():
            pool = self.task_pool.get(category, [])
            if not pool:
                tasks[category] = []
                continue
            if count <= len(pool):
                tasks[category] = random.sample(pool, count)
            else:
                tasks[category] = pool.copy()
                remaining = count - len(pool)
                tasks[category].extend(random.choices(pool, k=remaining))
        return tasks

    def start_game(self) -> Dict[str, str]:
        with self._lock:
            if self.status != "lobby":
                return {"ok": False, "error": "O jogo já começou."}
            if len(self.players) < self.config["required_players"]:
                return {
                    "ok": False,
                    "error": f"São necessários pelo menos {self.config['required_players']} jogadores.",
                }
            if not all(p.ready for p in self.players.values()):
                return {"ok": False, "error": "Nem todos os jogadores estão prontos."}
            if self.config["impostors"] >= len(self.players):
                return {"ok": False, "error": "Configuração inválida: impostores a mais."}

            self.round_number += 1
            self.status = "in_game"

            all_ids = list(self.players.keys())
            impostor_ids = set(random.sample(all_ids, self.config["impostors"]))

            for pid, player in self.players.items():
                player.role = "impostor" if pid in impostor_ids else "crewmate"
                player.tasks = self._pick_tasks()
                if player.role == "impostor":
                    player.kill_cooldown_end = time.time()
                else:
                    player.kill_cooldown_end = 0.0

            return {"ok": True}

    def reset_to_lobby(self) -> None:
        with self._lock:
            self.status = "lobby"
            self.round_number = 0
            for player in self.players.values():
                player.ready = False
                player.role = None
                player.tasks = {}
                player.kill_cooldown_end = 0.0

    def impostor_kill(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador não encontrado."}
            if self.status != "in_game":
                return {"ok": False, "error": "O jogo ainda não começou."}
            if player.role != "impostor":
                return {"ok": False, "error": "Apenas o impostor pode usar este botão."}

            now = time.time()
            if now < player.kill_cooldown_end:
                remaining = int(player.kill_cooldown_end - now)
                return {
                    "ok": False,
                    "error": f"Ainda faltam {remaining} segundos para poder matar novamente.",
                    "remaining": remaining,
                }

            player.kill_cooldown_end = now + self.config["kill_cooldown"]
            return {"ok": True, "cooldown": self.config["kill_cooldown"]}

    def lobby_snapshot(self, current_id: str) -> Dict[str, object]:
        with self._lock:
            players = [p.lobby_payload(current_id) for p in self.players.values()]
            player_count = len(self.players)
            required = self.config["required_players"]
            status = self.status
            everyone_ready = bool(self.players) and all(p.ready for p in self.players.values())
            can_start = status == "lobby" and player_count >= required and everyone_ready
            payload = {
                "status": status,
                "round": self.round_number,
                "playerCount": player_count,
                "requiredPlayers": required,
                "everyoneReady": everyone_ready,
                "canStart": can_start,
                "players": players,
            }
        return payload


app = Flask(__name__)
app.secret_key = "among-us-irl-demo"  # replace with environment secret in production

state = GameState()


def _require_player():
    player_id = session.get("player_id")
    if not player_id:
        return None
    return state.current_player(player_id)


@app.route("/", methods=["GET"])
def index():
    if _require_player():
        return redirect(url_for("lobby"))
    return render_template("index.html")


@app.route("/join", methods=["POST"])
def join():
    name = (request.form.get("name") or "").strip()
    if not name:
        return render_template("index.html", error="Escolhe um nome para entrar.")

    if state.status != "lobby":
        return render_template("index.html", error="Espera terminar a ronda antes de entrares.")

    existing = [p for p in state.players.values() if p.name.lower() == name.lower()]
    if existing:
        return render_template("index.html", error="Esse nome já está ocupado.")

    player = state.add_player(name)
    session["player_id"] = player.player_id
    return redirect(url_for("lobby"))


@app.route("/lobby", methods=["GET"])
def lobby():
    player = _require_player()
    if not player:
        return redirect(url_for("index"))
    return render_template("lobby.html")


@app.route("/game", methods=["GET"])
def game():
    player = _require_player()
    if not player:
        return redirect(url_for("index"))
    if state.status != "in_game":
        return redirect(url_for("lobby"))
    return render_template("game.html")


@app.route("/leave", methods=["POST"])
def leave():
    player = _require_player()
    if player:
        state.remove_player(player.player_id)
        session.pop("player_id", None)
    return redirect(url_for("index"))


@app.route("/api/state", methods=["GET"])
def api_state():
    player = _require_player()
    player_id = player.player_id if player else ""
    return jsonify(state.lobby_snapshot(player_id))


@app.route("/api/player", methods=["GET"])
def api_player():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessão expirada. Volta ao lobby."}), 404
    payload = {
        "ok": True,
        "name": player.name,
        "role": player.role,
        "status": state.status,
        "tasks": player.tasks,
        "killCooldown": state.config["kill_cooldown"],
        "killRemaining": player.kill_cooldown_remaining(),
    }
    return jsonify(payload)


@app.route("/api/ready", methods=["POST"])
def api_ready():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessão expirada. Volta ao lobby."}), 404

    data = request.get_json(silent=True) or {}
    ready = bool(data.get("ready"))
    if not state.toggle_ready(player.player_id, ready):
        return jsonify({"ok": False, "error": "Não foi possível actualizar o estado."}), 400
    return jsonify({"ok": True, "ready": ready})


@app.route("/api/start", methods=["POST"])
def api_start():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessão expirada. Volta ao lobby."}), 404
    result = state.start_game()
    if result.get("ok"):
        return jsonify({"ok": True, "redirect": url_for("game")})
    return jsonify(result), 400


@app.route("/api/impostor/kill", methods=["POST"])
def api_impostor_kill():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessão expirada. Volta ao lobby."}), 404
    result = state.impostor_kill(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/reset", methods=["POST"])
def api_reset():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessão expirada. Volta ao lobby."}), 404
    state.reset_to_lobby()
    return jsonify({"ok": True, "redirect": url_for("lobby")})


if __name__ == "__main__":
    app.run(debug=True)
