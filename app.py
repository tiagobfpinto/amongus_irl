import random
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
class TaskItem:
    task_id: str
    name: str
    done: bool = False

    def to_payload(self) -> Dict[str, object]:
        return {"id": self.task_id, "name": self.name, "done": self.done}


@dataclass
class Player:
    player_id: str
    name: str
    ready: bool = False
    role: Optional[str] = None  # "crewmate" or "impostor"
    tasks: Dict[str, List[TaskItem]] = field(default_factory=dict)
    alive: bool = True
    kill_cooldown_end: float = 0.0
    joined_at: float = field(default_factory=time.time)

    def lobby_payload(self, current_id: str, leader_id: Optional[str]) -> Dict[str, object]:
        return {
            "name": self.name,
            "ready": self.ready,
            "is_me": self.player_id == current_id,
            "alive": self.alive,
            "leader": self.player_id == leader_id,
        }

    def kill_cooldown_remaining(self) -> int:
        remaining = max(0.0, self.kill_cooldown_end - time.time())
        return int(remaining)

    def tasks_payload(self) -> Dict[str, List[Dict[str, object]]]:
        payload: Dict[str, List[Dict[str, object]]] = {}
        for category, items in self.tasks.items():
            payload[category] = [task.to_payload() for task in items]
        return payload


class GameState:
    SKIP_VOTE = "skip"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.players: Dict[str, Player] = {}
        self.status: str = "lobby"  # lobby | in_game
        self.round_number: int = 0
        self.initial_alive_count: int = 0
        self.leader_id: Optional[str] = None
        self.config = {
            "required_players": 2,
            "impostors": 1,
            "task_counts": {"common": 1, "long": 1, "fast": 3},
            "kill_cooldown": 120,
            "meeting_duration": 150,
        }
        self.task_pool = _default_task_pool()
        self.meeting: Optional[Dict[str, object]] = None
        self.last_meeting_summary: Optional[Dict[str, object]] = None
        self.revealed_progress: float = 0.0
        self.end_info: Optional[Dict[str, object]] = None

    def current_player(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def _assign_new_leader_locked(self) -> None:
        if not self.players:
            self.leader_id = None
            return
        leader = min(self.players.values(), key=lambda player: player.joined_at)
        self.leader_id = leader.player_id

    def add_player(self, name: str) -> Player:
        with self._lock:
            player_id = str(uuid.uuid4())
            new_player = Player(player_id=player_id, name=name.strip())
            self.players[player_id] = new_player
            if not self.leader_id:
                self.leader_id = player_id
            return new_player

    def remove_player(self, player_id: str) -> None:
        with self._lock:
            removed = self.players.pop(player_id, None)
            if removed and removed.player_id == self.leader_id:
                self._assign_new_leader_locked()

    def is_leader(self, player_id: str) -> bool:
        with self._lock:
            return self.leader_id == player_id

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

    def _build_tasks(self) -> Dict[str, List[TaskItem]]:
        tasks: Dict[str, List[TaskItem]] = {}
        for category, count in self.config["task_counts"].items():
            pool = self.task_pool.get(category, [])
            if not pool:
                tasks[category] = []
                continue
            if count <= len(pool):
                selected = random.sample(pool, count)
            else:
                selected = pool.copy()
                remaining = count - len(pool)
                selected.extend(random.choices(pool, k=remaining))
            tasks[category] = [
                TaskItem(task_id=f"{category}:{uuid.uuid4().hex}", name=name) for name in selected
            ]
        return tasks

    def start_game(self) -> Dict[str, str]:
        with self._lock:
            if self.status != "lobby":
                return {"ok": False, "error": "O jogo ja comecou."}
            if len(self.players) < self.config["required_players"]:
                return {
                    "ok": False,
                    "error": f"Sao necessarios pelo menos {self.config['required_players']} jogadores.",
                }
            if not all(p.ready for p in self.players.values()):
                return {"ok": False, "error": "Nem todos os jogadores estao prontos."}
            if self.config["impostors"] >= len(self.players):
                return {"ok": False, "error": "Configuracao invalida: impostores a mais."}

            self.round_number += 1
            self.status = "in_game"
            self.meeting = None
            self.last_meeting_summary = None
            self.revealed_progress = 0.0
            self.end_info = None
            self.initial_alive_count = len(self.players)

            all_ids = list(self.players.keys())
            impostor_ids = set(random.sample(all_ids, self.config["impostors"]))

            for pid, player in self.players.items():
                player.role = "impostor" if pid in impostor_ids else "crewmate"
                player.tasks = self._build_tasks()
                player.alive = True
                if player.role == "impostor":
                    player.kill_cooldown_end = time.time()
                else:
                    player.kill_cooldown_end = 0.0

            return {"ok": True}

    def reset_to_lobby(self) -> None:
        with self._lock:
            self.status = "lobby"
            self.round_number = 0
            self.meeting = None
            self.last_meeting_summary = None
            self.revealed_progress = 0.0
            self.end_info = None
            self.initial_alive_count = 0
            for player in self.players.values():
                player.ready = False
                player.role = None
                player.tasks = {}
                player.alive = True
                player.kill_cooldown_end = 0.0

    def impostor_kill(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if self.status != "in_game":
                return {"ok": False, "error": "O jogo ainda nao comecou."}
            if player.role != "impostor":
                return {"ok": False, "error": "Apenas o impostor pode usar este botao."}

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

    def _task_totals_unlocked(self) -> Tuple[int, int]:
        total = 0
        completed = 0
        for player in self.players.values():
            for items in player.tasks.values():
                for task in items:
                    total += 1
                    if task.done:
                        completed += 1
        return total, completed

    def mark_task(self, player_id: str, task_id: str, done: bool) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if self.status not in {"in_game", "meeting"}:
                return {"ok": False, "error": "Ainda nao podes marcar tarefas."}
            if not task_id:
                return {"ok": False, "error": "Tarefa invalida."}

            target_task: Optional[TaskItem] = None
            for group in player.tasks.values():
                for task in group:
                    if task.task_id == task_id:
                        target_task = task
                        break
                if target_task:
                    break

            if not target_task:
                return {"ok": False, "error": "Tarefa nao encontrada."}

            target_task.done = bool(done)
            total, completed = self._task_totals_unlocked()
            current_progress = completed / total if total else 0.0
            progress_payload = {
                "total": total,
                "completed": completed,
                "current": current_progress,
                "revealed": self.revealed_progress,
            }
            return {"ok": True, "task": target_task.to_payload(), "progress": progress_payload}

    def _alive_players_unlocked(self) -> List[Player]:
        return [player for player in self.players.values() if player.alive]

    def start_meeting(self, caller_id: str) -> Dict[str, object]:
        with self._lock:
            caller = self.players.get(caller_id)
            if not caller:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if not caller.alive:
                return {"ok": False, "error": "Apenas jogadores vivos podem reportar."}
            if self.status not in {"in_game"}:
                return {"ok": False, "error": "Nao podes chamar reuniao agora."}
            if self.meeting:
                return {"ok": False, "error": "Ja existe uma reuniao a decorrer."}

            now = time.time()
            meeting_id = str(uuid.uuid4())
            self.status = "meeting"
            self.meeting = {
                "id": meeting_id,
                "caller": caller_id,
                "started_at": now,
                "ends_at": now + self.config["meeting_duration"],
                "votes": {},
            }
            return {"ok": True, "meetingId": meeting_id}

    def _maybe_finalize_meeting_locked(self) -> None:
        if not self.meeting:
            return
        if time.time() >= self.meeting["ends_at"]:
            self._resolve_meeting_locked()

    def _resolve_meeting_locked(self) -> None:
        if not self.meeting:
            return

        meeting = self.meeting
        votes: Dict[str, str] = meeting["votes"]
        vote_counter = Counter(votes.values())
        skip_key = self.SKIP_VOTE

        chosen_target: Optional[str] = None
        if vote_counter:
            highest = vote_counter.most_common()
            top_count = highest[0][1]
            top_targets = [target for target, count in highest if count == top_count]
            if len(top_targets) == 1 and top_targets[0] != skip_key:
                chosen_target = top_targets[0]

        ejected_player: Optional[Player] = None
        outcome = "no_votes"
        if chosen_target:
            ejected_player = self.players.get(chosen_target)
            if ejected_player and ejected_player.alive:
                ejected_player.alive = False
                outcome = "ejected"
            else:
                chosen_target = None
                ejected_player = None
                outcome = "no_elimination"
        elif vote_counter:
            outcome = "skipped" if vote_counter.get(skip_key) else "no_elimination"

        total, completed = self._task_totals_unlocked()
        current_progress = completed / total if total else 0.0
        self.revealed_progress = current_progress

        votes_breakdown = []
        for target, count in vote_counter.items():
            if target == skip_key:
                label = "Skip"
            else:
                player = self.players.get(target)
                label = player.name if player else "Desconhecido"
            votes_breakdown.append({"target": target, "label": label, "count": count})

        summary = {
            "id": meeting["id"],
            "caller": meeting["caller"],
            "votes": votes_breakdown,
            "outcome": outcome,
            "progress": {
                "total": total,
                "completed": completed,
                "revealed": self.revealed_progress,
            },
        }

        if ejected_player:
            summary["ejected"] = {
                "id": ejected_player.player_id,
                "name": ejected_player.name,
                "role": ejected_player.role,
            }

        alive_players = self._alive_players_unlocked()
        impostor_player = next((p for p in self.players.values() if p.role == "impostor"), None)

        if ejected_player and ejected_player.role == "impostor":
            self.status = "ended"
            self.end_info = {
                "winner": "crewmates",
                "reason": "impostor_ejected",
                "impostor": {
                    "id": ejected_player.player_id,
                    "name": ejected_player.name,
                },
            }
            summary["gameOver"] = self.end_info
        elif self.initial_alive_count > 3 and len(alive_players) <= 3:
            self.status = "ended"
            self.end_info = {
                "winner": "impostor",
                "reason": "few_survivors",
                "impostor": {
                    "id": impostor_player.player_id if impostor_player else "",
                    "name": impostor_player.name if impostor_player else "Impostor",
                },
            }
            summary["gameOver"] = self.end_info
        else:
            self.status = "in_game"

        self.last_meeting_summary = summary
        self.meeting = None

    def cast_vote(self, voter_id: str, target_id: Optional[str]) -> Dict[str, object]:
        with self._lock:
            voter = self.players.get(voter_id)
            if not voter:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if not voter.alive:
                return {"ok": False, "error": "Jogadores mortos nao votam."}
            if self.status != "meeting" or not self.meeting:
                return {"ok": False, "error": "Nao existe reuniao ativa."}

            self._maybe_finalize_meeting_locked()
            if self.status != "meeting" or not self.meeting:
                return {"ok": False, "error": "A reuniao ja terminou."}

            if target_id and target_id != self.SKIP_VOTE:
                target_player = self.players.get(target_id)
                if not target_player or not target_player.alive:
                    return {"ok": False, "error": "Destino invalido."}

            vote_value = target_id or self.SKIP_VOTE
            self.meeting["votes"][voter_id] = vote_value

            alive_ids = {p.player_id for p in self._alive_players_unlocked()}
            if alive_ids.issubset(set(self.meeting["votes"].keys())):
                self._resolve_meeting_locked()
                return {"ok": True, "final": True}

            return {"ok": True, "final": False}

    def _meeting_payload_unlocked(self, current_player_id: str) -> Optional[Dict[str, object]]:
        if not self.meeting:
            return None
        remaining = max(0, int(self.meeting["ends_at"] - time.time()))
        alive_players = [
            {"id": p.player_id, "name": p.name}
            for p in self.players.values()
            if p.alive
        ]
        votes = self.meeting["votes"]
        return {
            "id": self.meeting["id"],
            "caller": self.meeting["caller"],
            "endsIn": remaining,
            "alivePlayers": alive_players,
            "myVote": votes.get(current_player_id),
        }

    def player_view(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}

            if self.meeting:
                self._maybe_finalize_meeting_locked()

            total, completed = self._task_totals_unlocked()
            current_progress = completed / total if total else 0.0

            meeting_payload = self._meeting_payload_unlocked(player_id)
            summary = self.last_meeting_summary
            end_info = self.end_info if self.status == "ended" else None

            payload = {
                "ok": True,
                "name": player.name,
                "role": player.role,
                "status": self.status,
                "alive": player.alive,
                "isLeader": player.player_id == self.leader_id,
                "leaderId": self.leader_id,
                "tasks": player.tasks_payload(),
                "killCooldown": self.config["kill_cooldown"],
                "killRemaining": player.kill_cooldown_remaining(),
                "progress": {
                    "total": total,
                    "completed": completed,
                    "current": current_progress,
                    "revealed": self.revealed_progress,
                },
            }

            if meeting_payload:
                payload["meeting"] = meeting_payload
            if summary:
                payload["meetingSummary"] = summary
            if end_info:
                payload["gameOver"] = end_info

            return payload

    def lobby_snapshot(self, current_id: str) -> Dict[str, object]:
        with self._lock:
            players = [p.lobby_payload(current_id, self.leader_id) for p in self.players.values()]
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
                "leaderId": self.leader_id,
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
        return render_template("index.html", error="Esse nome ja esta ocupado.")

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
    if state.status not in {"in_game", "meeting", "ended"}:
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
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    payload = state.player_view(player.player_id)
    return jsonify(payload)


@app.route("/api/tasks/complete", methods=["POST"])
def api_tasks_complete():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    task_id = data.get("taskId", "")
    done = bool(data.get("done", True))
    result = state.mark_task(player.player_id, task_id, done)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/report", methods=["POST"])
def api_report():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = state.start_meeting(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/meeting/vote", methods=["POST"])
def api_meeting_vote():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    target = data.get("target")
    vote_target = GameState.SKIP_VOTE if target == GameState.SKIP_VOTE else target
    result = state.cast_vote(player.player_id, vote_target)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/ready", methods=["POST"])
def api_ready():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404

    data = request.get_json(silent=True) or {}
    ready = bool(data.get("ready"))
    if not state.toggle_ready(player.player_id, ready):
        return jsonify({"ok": False, "error": "Nao foi possivel actualizar o estado."}), 400
    return jsonify({"ok": True, "ready": ready})


@app.route("/api/start", methods=["POST"])
def api_start():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = state.start_game()
    if result.get("ok"):
        return jsonify({"ok": True, "redirect": url_for("game")})
    return jsonify(result), 400


@app.route("/api/impostor/kill", methods=["POST"])
def api_impostor_kill():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = state.impostor_kill(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/reset", methods=["POST"])
def api_reset():
    player = _require_player()
    if not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    if not state.is_leader(player.player_id):
        return jsonify({"ok": False, "error": "So o lider pode terminar o jogo."}), 403
    state.reset_to_lobby()
    return jsonify({"ok": True, "redirect": url_for("lobby")})


if __name__ == "__main__":
    app.run(debug=True)
