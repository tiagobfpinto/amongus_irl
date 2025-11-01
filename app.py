import random
import string
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

def random_drawing():
    drawings = [
        "cuzgabs todo teso","kika a mamar mariana", "miguel a dar o cu",
        "lara a mamar irmao de parra","bapt a dancar","keil a fumar um kaya"
    ]
    return random.choice(drawings)

def random_location():
    locations = [
        "porta do carro do parra", "frigorifico", "cadeira na sala de estar","tronco, na parte de fora da casa"
    ]
    return random.choice(locations)



def _default_task_pool() -> Dict[str, List[Union[str, Dict[str, object]]]]:
    """Provide starter tasks so the app works out of the box.

    Each entry can be a plain string or a mapping with ``max_occurrences`` to
    control how many players may receive that task.
    """
    return {
        "common": [
            "Assinar a folha de presencas (mesa inicial)"
        ],
        "long": [
            {
                "name": "Pegar saco do lixo na sala e meter na rampa dos carros",
                "max_occurrences": 1,
            },
            {
                "name": "Montar castelo de cartas na casa de banho de criancas",
                "max_occurrences": 1,
            },
            {
                "name": "Montar castelo de cartas na dispensa",
                "max_occurrences": 1,
            },
            
        ],
        "fast": [
            {
                "name": "Ordenar garrafas de bebida pela primeira letra da marca por ordem alfabetica (cozinha)",
                "max_occurrences": 1,
            },
            {
                "name": "Empilhar 5 tampas umas em cima das outras na mesa principal",
                "max_occurrences": 1,
            },
            {
                "name": "Fazer uma bebida qualquer na cozinha",
                "max_occurrences": 2,
            },
            {
                "name": "Beber conteudo dum copo na sala",
                "max_occurrences": 2,
            },
            {
                "name": "Ligar TV da sala",
                "max_occurrences": 1,
            },
            {
                "name": "Ligar TV do quarto de criancas",
                "max_occurrences": 1,
            },
            {
                "name": "Ligar TV do quarto principal",
                "max_occurrences": 1,
            },
            {
                "name": "Meter toalha de maos no chuveiro da casa de banho das criancas",
                "max_occurrences": 1,
            },
            {
                "name": "Ordenar latas de cerveja numeradas",
                "max_occurrences": 1,
            },
            {
                "name": "Cortar uma rodela de limao na cozinha",
                "max_occurrences": 2,
            },
            
            {
                "name": "Fazer uma pila com os O do jogo do galo",
                "max_occurrences": 1,
            },
            {
                "name": "Acender vela na cozinha",
                "max_occurrences": 1,
            },
            {
                "name": "Acender vela restante na sala",
                "max_occurrences": 1,
            },
            {
                "name": f"Desenhar {random_drawing()} na cozinha",
                "max_occurrences": 2,
            },
            {
                "name": f"Pegar morcego na localização {random_location()} e dar um grito",
                "max_occurrences": 4,
            },
            {
                "name": "Pegar a pizza de brincar no quarto de crianças e levar para o frigorifico verdadeiro",
                "max_occurrences": 1,
            },
            {
                "name": "Meter as bolas da mesa de snooker dentro do triangulo (quarto crianças)",
                "max_occurrences": 1,
            },
        ],
    }


AVATAR_POOL: List[str] = [
    "/static/img/avatars/avatar-red.svg",
    "/static/img/avatars/avatar-blue.svg",
    "/static/img/avatars/avatar-green.svg",
    "/static/img/avatars/avatar-yellow.svg",
    "/static/img/avatars/avatar-pink.svg",
    "/static/img/avatars/avatar-orange.svg",
    "/static/img/avatars/avatar-cyan.svg",
    "/static/img/avatars/avatar-purple.svg",
]


@dataclass
class TaskItem:
    task_id: str
    name: str
    done: bool = False

    def to_payload(self) -> Dict[str, object]:
        return {"id": self.task_id, "name": self.name, "done": self.done}


@dataclass(frozen=True)
class TaskTemplate:
    name: str
    max_occurrences: Optional[int] = None


@dataclass
class Player:
    player_id: str
    name: str
    ready: bool = False
    role: Optional[str] = None  # "crewmate" or "impostor"
    special_role: Optional[str] = None  # e.g. "medic"
    tasks: Dict[str, List[TaskItem]] = field(default_factory=dict)
    alive: bool = True
    kill_cooldown_end: float = 0.0
    joined_at: float = field(default_factory=time.time)
    avatar: str = ""
    death_time: Optional[float] = None
    killed_by: Optional[str] = None
    killed_by_name: Optional[str] = None
    death_reported: bool = False
    left_game: bool = False
    emergency_available: bool = True
    medic_vitals_active_until: float = 0.0
    medic_vitals_ready: bool = True
    medic_completed_tasks: Set[str] = field(default_factory=set)

    def lobby_payload(self, current_id: str, leader_id: Optional[str]) -> Dict[str, object]:
        return {
            "id": self.player_id,
            "name": self.name,
            "ready": self.ready,
            "is_me": self.player_id == current_id,
            "alive": self.alive,
            "leader": self.player_id == leader_id,
            "avatar": self.avatar,
        }

    def death_payload(self, viewer_id: Optional[str] = None) -> Optional[Dict[str, object]]:
        if self.alive or not self.death_time:
            return None
        payload = {
            "id": self.player_id,
            "name": self.name,
            "killedAt": int(self.death_time),
            "killedBy": self.killed_by,
            "killedByName": self.killed_by_name,
            "reported": self.death_reported,
            "avatar": self.avatar,
            "leftGame": self.left_game,
        }
        if viewer_id != self.player_id:
            payload.pop("killedAt", None)
            payload.pop("killedBy", None)
            payload.pop("killedByName", None)
        return payload

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
    MEETING_VOTE_DELAY = 10
    CONFIG_LIMITS = {
        "required_players": {"min": 2, "max": 15},
        "kill_cooldown": {"min": 10, "max": 600},
    }

    def __init__(self, code: str) -> None:
        self.code = code.upper()
        self.created_at = time.time()
        self._lock = threading.Lock()
        self.players: Dict[str, Player] = {}
        self.status: str = "lobby"  # lobby | in_game
        self.round_number: int = 0
        self.leader_id: Optional[str] = None
        self.config = {
            "required_players": 2,
            "impostors": 1,
            "task_counts": {"common": 1, "long": 1, "fast": 3},
            "kill_cooldown": 120,
            "meeting_duration": 150,
        }
        self.medic_vitals_duration: int = 5
        self.task_pool = _default_task_pool()
        self.task_templates: Dict[str, List[TaskTemplate]] = {}
        self._task_usage: Dict[str, int] = {}
        self._selected_common_tasks: List[TaskTemplate] = []
        self.meeting: Optional[Dict[str, object]] = None
        self.last_meeting_summary: Optional[Dict[str, object]] = None
        self.revealed_progress: float = 0.0
        self.end_info: Optional[Dict[str, object]] = None
        self._used_avatars: Set[str] = set()
        self.comms_sabotage_end: float = 0.0
        self.comms_sabotage_by: Optional[str] = None
        self.comms_sabotage_duration: int = 25  # seconds
        self._refresh_task_templates()
        self._reset_task_usage()

    def current_player(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def _assign_new_leader_locked(self) -> None:
        active_players = [player for player in self.players.values() if not player.left_game]
        if not active_players:
            self.leader_id = None
            return
        leader = min(active_players, key=lambda player: player.joined_at)
        self.leader_id = leader.player_id

    def _allocate_avatar_locked(self) -> str:
        for avatar in AVATAR_POOL:
            if avatar not in self._used_avatars:
                self._used_avatars.add(avatar)
                return avatar
        choice = random.choice(AVATAR_POOL)
        self._used_avatars.add(choice)
        return choice

    def _release_avatar_locked(self, avatar: str) -> None:
        if avatar:
            self._used_avatars.discard(avatar)

    def add_player(self, name: str) -> Player:
        with self._lock:
            player_id = str(uuid.uuid4())
            new_player = Player(
                player_id=player_id,
                name=name.strip(),
                avatar=self._allocate_avatar_locked(),
            )
            self.players[player_id] = new_player
            if not self.leader_id:
                self.leader_id = player_id
            return new_player

    def remove_player(self, player_id: str) -> bool:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return False

            if self.status in {"in_game", "meeting"}:
                self._handle_player_departure_locked(player)
                self._release_avatar_locked(player.avatar)
            else:
                removed = self.players.pop(player_id, None)
                if not removed:
                    return False
                self._release_avatar_locked(removed.avatar)
                if removed.player_id == self.leader_id:
                    self._assign_new_leader_locked()
            if player.player_id == self.leader_id and player.left_game:
                self._assign_new_leader_locked()
            return True

    def is_empty(self) -> bool:
        with self._lock:
            return not any(not player.left_game for player in self.players.values())

    def has_player_named(self, name: str) -> bool:
        name_key = name.strip().lower()
        with self._lock:
            return any(
                player.name.lower() == name_key and not player.left_game
                for player in self.players.values()
            )

    def is_leader(self, player_id: str) -> bool:
        with self._lock:
            return self.leader_id == player_id

    def toggle_ready(self, player_id: str, ready: bool) -> bool:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return False
            if player.left_game:
                return False
            player.ready = ready
            return True

    def everyone_ready(self) -> bool:
        with self._lock:
            return self._everyone_ready_unlocked()

    def _everyone_ready_unlocked(self) -> bool:
        active = [player for player in self.players.values() if not player.left_game]
        return bool(active) and all(p.ready for p in active)

    def can_start(self) -> bool:
        with self._lock:
            active = [player for player in self.players.values() if not player.left_game]
            has_required_count = len(active) >= self.config["required_players"]
            return self.status == "lobby" and has_required_count and self._everyone_ready_unlocked()

    def _config_payload_unlocked(self) -> Dict[str, object]:
        return {
            "requiredPlayers": self.config["required_players"],
            "killCooldown": self.config["kill_cooldown"],
            "impostors": self.config["impostors"],
            "meetingDuration": self.config["meeting_duration"],
        }

    def _config_limits_payload(self) -> Dict[str, Dict[str, int]]:
        return {
            "requiredPlayers": self.CONFIG_LIMITS["required_players"],
            "killCooldown": self.CONFIG_LIMITS["kill_cooldown"],
        }

    def update_config(self, requester_id: str, updates: Dict[str, int]) -> Dict[str, object]:
        with self._lock:
            if requester_id != self.leader_id:
                return {"ok": False, "error": "Apenas o lider pode alterar definicoes."}
            if self.status != "lobby":
                return {"ok": False, "error": "Nao podes alterar definicoes depois do jogo comecar."}

            errors = []
            required_players = updates.get("requiredPlayers")
            if required_players is not None:
                limits = self.CONFIG_LIMITS["required_players"]
                if not isinstance(required_players, int):
                    errors.append("Numero de jogadores invalido.")
                elif required_players < limits["min"] or required_players > limits["max"]:
                    errors.append(
                        f"O numero de jogadores deve estar entre {limits['min']} e {limits['max']}."
                    )
                else:
                    self.config["required_players"] = required_players

            kill_cooldown = updates.get("killCooldown")
            if kill_cooldown is not None:
                limits = self.CONFIG_LIMITS["kill_cooldown"]
                if not isinstance(kill_cooldown, int):
                    errors.append("Kill cooldown invalido.")
                elif kill_cooldown < limits["min"] or kill_cooldown > limits["max"]:
                    errors.append(
                        f"O kill cooldown deve estar entre {limits['min']} e {limits['max']} segundos."
                    )
                else:
                    self.config["kill_cooldown"] = kill_cooldown

            if errors:
                return {"ok": False, "error": " ".join(errors)}

            return {"ok": True, "config": self._config_payload_unlocked()}

    def kick_player(self, requester_id: str, target_id: str) -> Dict[str, object]:
        with self._lock:
            if requester_id != self.leader_id:
                return {"ok": False, "error": "Apenas o lider pode expulsar jogadores."}
            if self.status != "lobby":
                return {"ok": False, "error": "Nao podes expulsar jogadores depois do jogo comecar."}
            if requester_id == target_id:
                return {"ok": False, "error": "Nao te podes expulsar a ti proprio."}
            target = self.players.get(target_id)
            if not target:
                return {"ok": False, "error": "Jogador nao encontrado."}

            removed = self.players.pop(target_id, None)
            if not removed:
                return {"ok": False, "error": "Nao foi possivel expulsar o jogador."}

            self._release_avatar_locked(removed.avatar)
            removed.ready = False
            removed.alive = False

            if removed.player_id == self.leader_id:
                self._assign_new_leader_locked()

            return {
                "ok": True,
                "removed": {"id": removed.player_id, "name": removed.name},
                "leaderId": self.leader_id,
            }

    def _normalize_task_pool(self) -> Dict[str, List[TaskTemplate]]:
        normalized: Dict[str, List[TaskTemplate]] = {}
        for category, entries in self.task_pool.items():
            normalized_entries: List[TaskTemplate] = []
            for entry in entries:
                if isinstance(entry, TaskTemplate):
                    normalized_entries.append(entry)
                    continue
                if isinstance(entry, dict):
                    name = str(entry.get("name", "")).strip()
                    if not name:
                        continue
                    raw_limit = entry.get("max_occurrences", entry.get("max"))
                    if raw_limit is None:
                        normalized_entries.append(TaskTemplate(name=name, max_occurrences=None))
                        continue
                    try:
                        limit = int(raw_limit)
                    except (TypeError, ValueError):
                        normalized_entries.append(TaskTemplate(name=name, max_occurrences=None))
                        continue
                    if limit <= 0:
                        continue
                    normalized_entries.append(TaskTemplate(name=name, max_occurrences=limit))
                    continue
                name = str(entry).strip()
                if not name:
                    continue
                normalized_entries.append(TaskTemplate(name=name, max_occurrences=None))
            normalized[category] = normalized_entries
        return normalized

    def _refresh_task_templates(self) -> None:
        self.task_templates = self._normalize_task_pool()

    def _reset_task_usage(self) -> None:
        self._task_usage = {}

    def _task_key(self, category: str, template: TaskTemplate) -> str:
        return f"{category}:{template.name}"

    def _increment_task_usage(self, category: str, template: TaskTemplate) -> None:
        if template.max_occurrences is None:
            return
        key = self._task_key(category, template)
        self._task_usage[key] = self._task_usage.get(key, 0) + 1

    def _select_task_template(self, category: str, assigned_names: Set[str]) -> Optional[TaskTemplate]:
        templates = self.task_templates.get(category, [])
        if not templates:
            return None
        eligible: List[TaskTemplate] = []
        preferred: List[TaskTemplate] = []
        for template in templates:
            if template.max_occurrences is not None:
                usage = self._task_usage.get(self._task_key(category, template), 0)
                if usage >= template.max_occurrences:
                    continue
            eligible.append(template)
            if template.name not in assigned_names:
                preferred.append(template)
        if not eligible:
            return None
        pool = preferred or eligible
        return random.choice(pool)

    def _choose_common_tasks(self, player_count: int) -> List[TaskTemplate]:
        count = int(self.config.get("task_counts", {}).get("common", 0))
        templates = self.task_templates.get("common", [])
        if count <= 0 or not templates or player_count <= 0:
            return []
        if count >= len(templates):
            return [random.choice(templates) for _ in range(count)]
        return random.sample(templates, count)

    def _build_tasks(self) -> Dict[str, List[TaskItem]]:
        tasks: Dict[str, List[TaskItem]] = {}
        task_counts = self.config.get("task_counts", {})
        for category, count in task_counts.items():
            if count <= 0:
                tasks[category] = []
                continue
            if category == "common":
                selected_templates = self._selected_common_tasks[:count]
                tasks[category] = [
                    TaskItem(task_id=f"{category}:{uuid.uuid4().hex}", name=template.name)
                    for template in selected_templates
                ]
                continue
            assigned_templates: List[TaskTemplate] = []
            assigned_names: Set[str] = set()
            for _ in range(count):
                template = self._select_task_template(category, assigned_names)
                if not template:
                    break
                assigned_templates.append(template)
                assigned_names.add(template.name)
                self._increment_task_usage(category, template)
            tasks[category] = [
                TaskItem(task_id=f"{category}:{uuid.uuid4().hex}", name=template.name)
                for template in assigned_templates
            ]
        return tasks

    def start_game(self) -> Dict[str, str]:
        with self._lock:
            if self.status != "lobby":
                return {"ok": False, "error": "O jogo ja comecou."}
            active_players = [player for player in self.players.values() if not player.left_game]
            if len(active_players) < self.config["required_players"]:
                return {
                    "ok": False,
                    "error": f"Sao necessarios pelo menos {self.config['required_players']} jogadores.",
                }
            if not all(p.ready for p in active_players):
                return {"ok": False, "error": "Nem todos os jogadores estao prontos."}
            if self.config["impostors"] >= len(active_players):
                return {"ok": False, "error": "Configuracao invalida: impostores a mais."}

            self._clear_comms_sabotage_locked()
            self.round_number += 1
            self.status = "in_game"
            self.meeting = None
            self.last_meeting_summary = None
            self.revealed_progress = 0.0
            self.end_info = None
            all_ids = [player.player_id for player in active_players]
            impostor_ids = set(random.sample(all_ids, self.config["impostors"]))

            self._refresh_task_templates()
            self._reset_task_usage()
            self._selected_common_tasks = self._choose_common_tasks(len(active_players))

            for pid, player in self.players.items():
                if player.left_game:
                    continue
                player.role = "impostor" if pid in impostor_ids else "crewmate"
                player.tasks = {}
                player.alive = True
                if player.role == "impostor":
                    player.kill_cooldown_end = time.time()
                else:
                    player.kill_cooldown_end = 0.0
                player.death_time = None
                player.killed_by = None
                player.killed_by_name = None
                player.death_reported = False
                player.left_game = False
                player.special_role = None
                player.emergency_available = True
                player.medic_vitals_active_until = 0.0
                player.medic_vitals_ready = False
                player.medic_completed_tasks = set()

            assignment_players = active_players[:]
            random.shuffle(assignment_players)
            for player in assignment_players:
                player.tasks = self._build_tasks()

            medic_candidates = [p for p in self.players.values() if p.role == "crewmate" and not p.left_game]
            if medic_candidates:
                medic = random.choice(medic_candidates)
                medic.special_role = "medic"
                medic.medic_vitals_active_until = 0.0
                medic.medic_vitals_ready = True
                medic.medic_completed_tasks = set()

            return {"ok": True}

    def reset_to_lobby(self) -> None:
        with self._lock:
            self.status = "lobby"
            self.round_number = 0
            self.meeting = None
            self.last_meeting_summary = None
            self.revealed_progress = 0.0
            self.end_info = None
            self._reset_task_usage()
            self._selected_common_tasks = []
            for pid, player in list(self.players.items()):
                if player.left_game:
                    self._release_avatar_locked(player.avatar)
                    self.players.pop(pid, None)
                    continue
                player.ready = False
                player.role = None
                player.tasks = {}
                player.alive = True
                player.kill_cooldown_end = 0.0
                player.death_time = None
                player.killed_by = None
                player.killed_by_name = None
                player.death_reported = False
                player.left_game = False
                player.special_role = None
                player.emergency_available = True
                player.medic_vitals_active_until = 0.0
                player.medic_vitals_ready = True
                player.medic_completed_tasks = set()
            self._clear_comms_sabotage_locked()

    def impostor_sabotage(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if self.status != "in_game":
                return {"ok": False, "error": "O jogo ainda nao comecou."}
            if player.role != "impostor":
                return {"ok": False, "error": "Apenas o impostor pode usar este botao."}
            if player.left_game:
                return {"ok": False, "error": "Jogador nao esta ativo."}

            self._clear_expired_comms_locked()
            if time.time() < self.comms_sabotage_end:
                remaining = int(self.comms_sabotage_end - time.time())
                return {
                    "ok": False,
                    "error": "As comunicacoes ja estao sabotadas.",
                    "remaining": remaining,
                }

            now = time.time()
            self.comms_sabotage_end = now + self.comms_sabotage_duration
            self.comms_sabotage_by = player_id
            return {"ok": True, "duration": self.comms_sabotage_duration}

    def medic_activate_vitals(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if self.status != "in_game":
                return {"ok": False, "error": "As vitals so estao disponiveis durante a ronda."}
            if player.special_role != "medic":
                return {"ok": False, "error": "Apenas o medico pode usar este botao."}
            if player.left_game:
                return {"ok": False, "error": "Jogador nao esta ativo."}

            self._clear_expired_medic_window_locked(player)
            now = time.time()
            remaining = max(0, int(player.medic_vitals_active_until - now))
            if player.medic_vitals_active_until > now:
                vitals = self._collect_vitals_locked()
                return {
                    "ok": True,
                    "active": True,
                    "remaining": remaining,
                    "ready": player.medic_vitals_ready,
                    "duration": self.medic_vitals_duration,
                    "vitals": vitals,
                }

            if not player.medic_vitals_ready:
                return {
                    "ok": False,
                    "error": "Completa uma nova tarefa para desbloquear novamente as vitals.",
                    "active": False,
                    "remaining": 0,
                    "ready": False,
                    "duration": self.medic_vitals_duration,
                }

            player.medic_vitals_ready = False
            player.medic_vitals_active_until = now + self.medic_vitals_duration
            vitals = self._collect_vitals_locked()
            return {
                "ok": True,
                "active": True,
                "remaining": self.medic_vitals_duration,
                "ready": player.medic_vitals_ready,
                "duration": self.medic_vitals_duration,
                "vitals": vitals,
            }

    def impostor_kill(self, player_id: str, target_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if self.status != "in_game":
                return {"ok": False, "error": "O jogo ainda nao comecou."}
            if player.role != "impostor":
                return {"ok": False, "error": "Apenas o impostor pode usar este botao."}
            if not target_id:
                return {"ok": False, "error": "Seleciona a vitima."}

            target_player = self.players.get(target_id)
            if not target_player or not target_player.alive:
                return {"ok": False, "error": "Vitima invalida."}
            if target_player.player_id == player.player_id:
                return {"ok": False, "error": "Nao podes matar-te a ti proprio."}
            if target_player.role == "impostor":
                return {"ok": False, "error": "Nao podes matar outro impostor."}

            now = time.time()
            if now < player.kill_cooldown_end:
                remaining = int(player.kill_cooldown_end - now)
                return {
                    "ok": False,
                    "error": f"Ainda faltam {remaining} segundos para poder matar novamente.",
                    "remaining": remaining,
                }

            player.kill_cooldown_end = now + self.config["kill_cooldown"]
            self._mark_player_dead_locked(target_player, player)

            impostor_survivor = self._impostor_last_crewmate_locked()
            if impostor_survivor and self.status == "in_game":
                self.status = "ended"
                self.end_info = {
                    "winner": "impostor",
                    "reason": "last_crewmate",
                    "impostor": {
                        "id": impostor_survivor.player_id,
                        "name": impostor_survivor.name,
                    },
                    "message": f"O impostor {impostor_survivor.name} Venceu!",
                }

            if self.status == "ended":
                self._clear_comms_sabotage_locked()

            return {
                "ok": True,
                "cooldown": self.config["kill_cooldown"],
                "victim": target_player.death_payload(),
                "gameOver": self.end_info if self.status == "ended" else None,
            }

    def _task_totals_unlocked(self) -> Tuple[int, int]:
        total = 0
        completed = 0
        for player in self.players.values():
            if player.left_game or player.role != "crewmate":
                continue
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

        previous_done = target_task.done
        target_task.done = bool(done)
        if player.special_role == "medic":
            self._handle_medic_task_update_locked(player, target_task, previous_done)
        total, completed = self._task_totals_unlocked()
        current_progress = completed / total if total else 0.0
        if total and completed >= total and self.status in {"in_game", "meeting"}:
            self.status = "ended"
            self.end_info = {
                "winner": "crewmates",
                "reason": "tasks",
                "message": "Todas as tarefas foram concluidas. Tripulacao venceu!",
            }
            self.revealed_progress = max(self.revealed_progress, current_progress)
            self.meeting = None
            self._clear_comms_sabotage_locked()
        progress_payload = {
            "total": total,
            "completed": completed,
            "current": current_progress,
            "revealed": self.revealed_progress,
        }
        result: Dict[str, object] = {
            "ok": True,
            "task": target_task.to_payload(),
            "progress": progress_payload,
        }
        if self.status == "ended" and self.end_info:
            result["gameOver"] = self.end_info
        return result

    def _handle_medic_task_update_locked(
        self, player: Player, task: TaskItem, previous_done: bool
    ) -> None:
        if player.special_role != "medic":
            return
        if task.done and not previous_done and task.task_id not in player.medic_completed_tasks:
            player.medic_completed_tasks.add(task.task_id)
            player.medic_vitals_ready = True

    def _alive_players_unlocked(self) -> List[Player]:
        return [player for player in self.players.values() if player.alive and not player.left_game]

    def _dead_players_unlocked(self) -> List[Player]:
        return [player for player in self.players.values() if not player.alive and player.death_time]

    def _active_players_unlocked(self) -> List[Player]:
        return [player for player in self.players.values() if not player.left_game]

    def _clear_expired_comms_locked(self) -> None:
        if self.comms_sabotage_end and time.time() >= self.comms_sabotage_end:
            self.comms_sabotage_end = 0.0
            self.comms_sabotage_by = None

    def _clear_comms_sabotage_locked(self) -> None:
        self.comms_sabotage_end = 0.0
        self.comms_sabotage_by = None

    def _comms_remaining_locked(self) -> int:
        self._clear_expired_comms_locked()
        return max(0, int(self.comms_sabotage_end - time.time()))

    def _clear_expired_medic_window_locked(self, player: Player) -> None:
        if player.medic_vitals_active_until and time.time() >= player.medic_vitals_active_until:
            player.medic_vitals_active_until = 0.0

    def _collect_vitals_locked(self) -> List[Dict[str, object]]:
        vitals: List[Dict[str, object]] = []
        for other in self.players.values():
            vitals.append(
                {
                    "id": other.player_id,
                    "name": other.name,
                    "alive": other.alive and not other.left_game,
                    "leftGame": other.left_game,
                }
            )
        return vitals

    def _mark_player_dead_locked(self, victim: Player, killer: Optional[Player]) -> None:
        if not victim.alive:
            return
        victim.alive = False
        victim.death_time = time.time()
        if killer:
            victim.killed_by = killer.player_id
            victim.killed_by_name = killer.name
        else:
            victim.killed_by = None
            victim.killed_by_name = None
        victim.death_reported = False

    def _handle_player_departure_locked(self, player: Player) -> None:
        if player.left_game:
            return

        player.left_game = True
        player.ready = False
        player.special_role = None
        player.emergency_available = False
        player.medic_vitals_active_until = 0.0
        player.medic_vitals_ready = False
        player.medic_completed_tasks = set()

        if player.alive and player.role == "impostor":
            player.alive = False
            player.death_time = time.time()
            player.killed_by = None
            player.killed_by_name = None
            player.death_reported = True
            player.tasks = {}
            self.meeting = None
            self.last_meeting_summary = None
            self.status = "ended"
            self.end_info = {
                "winner": "crewmates",
                "reason": "impostor_left",
                "impostor": {"id": player.player_id, "name": player.name},
                "message": f"O impostor {player.name} abandonou o jogo. Tripulacao vence!",
            }
            self._clear_comms_sabotage_locked()
            return

        if player.alive:
            self._mark_player_dead_locked(player, None)
            player.death_reported = True
        player.tasks = {}

        if self.meeting:
            self.meeting["votes"].pop(player.player_id, None)
            if self.status == "meeting":
                self._maybe_finalize_meeting_locked()

        if self.status == "in_game":
            impostor_survivor = self._impostor_last_crewmate_locked()
            if impostor_survivor:
                self.status = "ended"
                self.end_info = {
                    "winner": "impostor",
                    "reason": "last_crewmate",
                    "impostor": {
                        "id": impostor_survivor.player_id,
                        "name": impostor_survivor.name,
                    },
                    "message": f"O impostor {impostor_survivor.name} Venceu!",
                }
                self.meeting = None
            elif not any(
                p.alive and p.role == "impostor" and not p.left_game for p in self.players.values()
            ):
                self.status = "ended"
                self.end_info = {
                    "winner": "crewmates",
                    "reason": "impostors_gone",
                    "message": "Todos os impostores foram eliminados. Tripulacao vence!",
                }
                self.meeting = None
        if self.status == "ended":
            self._clear_comms_sabotage_locked()
    def _impostor_last_crewmate_locked(self) -> Optional[Player]:
        alive_players = self._alive_players_unlocked()
        impostors = [player for player in alive_players if player.role == "impostor"]
        crewmates = [player for player in alive_players if player.role == "crewmate"]
        if len(impostors) == 1 and len(crewmates) <= 1:
            return impostors[0]
        return None

    def call_emergency_meeting(self, caller_id: str) -> Dict[str, object]:
        with self._lock:
            caller = self.players.get(caller_id)
            if not caller:
                return {"ok": False, "error": "Jogador nao encontrado."}
            if caller.left_game:
                return {"ok": False, "error": "Jogador nao esta ativo."}
            if not caller.alive:
                return {"ok": False, "error": "Jogadores mortos nao podem chamar reuniao."}
            if self.status != "in_game":
                return {"ok": False, "error": "Nao podes chamar reuniao agora."}
            if self.meeting:
                return {"ok": False, "error": "Ja existe uma reuniao a decorrer."}
            if not caller.emergency_available:
                return {"ok": False, "error": "Ja usaste a tua reuniao de emergencia."}

            caller.emergency_available = False
            now = time.time()
            meeting_id = str(uuid.uuid4())
            self.status = "meeting"
            self.meeting = {
                "id": meeting_id,
                "caller": caller_id,
                "started_at": now,
                "ends_at": now + self.config["meeting_duration"],
                "votes": {},
                "reported_body": None,
                "voting_starts_at": now + self.MEETING_VOTE_DELAY,
                "type": "emergency",
            }
            self._clear_comms_sabotage_locked()
            return {"ok": True, "meetingId": meeting_id}

    def start_meeting(self, caller_id: str, body_id: Optional[str]) -> Dict[str, object]:
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

            if not body_id:
                return {"ok": False, "error": "Indica o corpo reportado."}
            reported_body = self.players.get(body_id)
            if not reported_body or reported_body.alive or not reported_body.death_time:
                return {"ok": False, "error": "Esse corpo nao foi encontrado."}
            reported_body.death_reported = True

            now = time.time()
            meeting_id = str(uuid.uuid4())
            self.status = "meeting"
            self.meeting = {
                "id": meeting_id,
                "caller": caller_id,
                "started_at": now,
                "ends_at": now + self.config["meeting_duration"],
                "votes": {},
                "reported_body": reported_body.player_id,
                "voting_starts_at": now + self.MEETING_VOTE_DELAY,
                "type": "reported",
            }
            self._clear_comms_sabotage_locked()
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
            "type": meeting.get("type", "reported"),
            "votes": votes_breakdown,
            "outcome": outcome,
            "progress": {
                "total": total,
                "completed": completed,
                "revealed": self.revealed_progress,
            },
        }
        summary["deceased"] = [
            payload for payload in (p.death_payload() for p in self.players.values()) if payload
        ]

        if ejected_player:
            summary["ejected"] = {
                "id": ejected_player.player_id,
                "name": ejected_player.name,
                "role": ejected_player.role,
            }

        impostor_survivor = self._impostor_last_crewmate_locked()

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
        elif impostor_survivor:
            self.status = "ended"
            self.end_info = {
                "winner": "impostor",
                "reason": "last_crewmate",
                "impostor": {
                    "id": impostor_survivor.player_id,
                    "name": impostor_survivor.name,
                },
                "message": f"O impostor {impostor_survivor.name} Venceu!",
            }
            summary["gameOver"] = self.end_info
        else:
            self.status = "in_game"

        self.last_meeting_summary = summary
        self.meeting = None
        if self.status == "ended":
            self._clear_comms_sabotage_locked()

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

            vote_start = self.meeting.get("voting_starts_at", self.meeting.get("started_at", 0))
            now = time.time()
            if now < vote_start:
                remaining = int(vote_start - now)
                return {
                    "ok": False,
                    "error": "Ainda nao podes votar. Aguarda alguns segundos.",
                    "delay": remaining,
                }

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
        voting_starts_in = max(0, int(self.meeting["voting_starts_at"] - time.time()))
        votes = self.meeting["votes"]
        alive_players = []
        for p in self.players.values():
            if not p.alive or p.left_game:
                continue
            alive_players.append(
                {
                    "id": p.player_id,
                    "name": p.name,
                    "avatar": p.avatar,
                    "hasVoted": p.player_id in votes,
                }
            )

        deceased_players = []
        for player in self._dead_players_unlocked():
            payload = player.death_payload(current_player_id)
            if payload:
                deceased_players.append(payload)

        reported_body_id = self.meeting.get("reported_body")
        reported_body = self.players.get(reported_body_id) if reported_body_id else None
        reported_payload = None
        if reported_body:
            reported_payload = {
                "id": reported_body.player_id,
                "name": reported_body.name,
                "avatar": reported_body.avatar,
            }
            if reported_body.player_id == current_player_id and reported_body.killed_by_name:
                reported_payload["killedByName"] = reported_body.killed_by_name
            reported_payload["leftGame"] = reported_body.left_game

        reporter_payload = None
        caller = self.players.get(self.meeting["caller"])
        if caller:
            reporter_payload = {
                "id": caller.player_id,
                "name": caller.name,
                "avatar": caller.avatar,
            }

        votes = self.meeting["votes"]
        return {
            "id": self.meeting["id"],
            "caller": self.meeting["caller"],
            "type": self.meeting.get("type", "reported"),
            "endsIn": remaining,
            "alivePlayers": alive_players,
            "deceased": deceased_players,
            "reportedBody": reported_payload,
            "reporter": reporter_payload,
            "voted": list(votes.keys()),
            "votingStartsIn": voting_starts_in,
            "myVote": votes.get(current_player_id),
        }

    def _meeting_summary_for_player_unlocked(
        self, current_player_id: str
    ) -> Optional[Dict[str, object]]:
        summary = self.last_meeting_summary
        if not summary:
            return None
        filtered = summary.copy()
        raw_deceased = summary.get("deceased", [])
        deceased_entries: List[Dict[str, object]] = []
        for entry in raw_deceased:
            if not entry:
                continue
            entry_copy = dict(entry)
            if entry_copy.get("id") != current_player_id:
                entry_copy.pop("killedAt", None)
                entry_copy.pop("killedBy", None)
                entry_copy.pop("killedByName", None)
            deceased_entries.append(entry_copy)
        if "deceased" in filtered:
            filtered["deceased"] = deceased_entries
        return filtered

    def player_view(self, player_id: str) -> Dict[str, object]:
        with self._lock:
            player = self.players.get(player_id)
            if not player:
                return {"ok": False, "error": "Jogador nao encontrado."}

            if self.meeting:
                self._maybe_finalize_meeting_locked()
            self._clear_expired_comms_locked()

            total, completed = self._task_totals_unlocked()
            current_progress = completed / total if total else 0.0

            meeting_payload = self._meeting_payload_unlocked(player_id)
            summary = self._meeting_summary_for_player_unlocked(player_id)
            end_info = self.end_info if self.status == "ended" else None

            dead_payloads = []
            for target in self.players.values():
                payload = target.death_payload(player_id)
                if payload:
                    dead_payloads.append(payload)
            kill_targets = []
            if player.role == "impostor":
                for other in self.players.values():
                    if (
                        other.player_id == player_id
                        or not other.alive
                        or other.left_game
                    ):
                        continue
                    kill_targets.append(
                        {
                            "id": other.player_id,
                            "name": other.name,
                            "avatar": other.avatar,
                        }
                    )

            death_note = None
            if not player.alive and player.death_time and player.killed_by_name:
                killed_at = time.strftime("%H:%M", time.localtime(player.death_time))
                death_note = f"Foste morto as {killed_at} por {player.killed_by_name}."
            elif not player.alive and player.death_time:
                killed_at = time.strftime("%H:%M", time.localtime(player.death_time))
                death_note = f"Foste morto as {killed_at}."

            payload = {
                "ok": True,
                "name": player.name,
                "role": player.role,
                "status": self.status,
                "alive": player.alive,
                "isLeader": player.player_id == self.leader_id,
                "leaderId": self.leader_id,
                "avatar": player.avatar,
                "lobbyCode": self.code,
                "tasks": player.tasks_payload(),
                "killCooldown": self.config["kill_cooldown"],
                "killRemaining": player.kill_cooldown_remaining(),
                "deadPlayers": dead_payloads,
                "deathNote": death_note,
                "progress": {
                    "total": total,
                    "completed": completed,
                    "current": current_progress,
                    "revealed": self.revealed_progress,
                },
                "specialRole": player.special_role,
                "emergencyAvailable": player.emergency_available,
            }
            comms_remaining = self._comms_remaining_locked()
            comms_active = comms_remaining > 0
            payload["commsSabotage"] = {
                "active": comms_active,
                "remaining": comms_remaining,
                "affectsPlayer": comms_active and player.role != "impostor",
            }
            if kill_targets:
                payload["killTargets"] = kill_targets

            if player.special_role == "medic":
                self._clear_expired_medic_window_locked(player)
                now = time.time()
                remaining = max(0, int(player.medic_vitals_active_until - now))
                active = player.medic_vitals_active_until > now
                medic_payload: Dict[str, object] = {
                    "active": active,
                    "remaining": remaining,
                    "ready": player.medic_vitals_ready,
                    "duration": self.medic_vitals_duration,
                }
                if active:
                    medic_payload["vitals"] = self._collect_vitals_locked()
                payload["medicVitals"] = medic_payload

            if meeting_payload:
                payload["meeting"] = meeting_payload
            if summary:
                payload["meetingSummary"] = summary
            if end_info:
                payload["gameOver"] = end_info

            return payload

    def lobby_snapshot(self, current_id: str) -> Dict[str, object]:
        with self._lock:
            active_players = [p for p in self.players.values() if not p.left_game]
            players = [p.lobby_payload(current_id, self.leader_id) for p in active_players]
            player_count = len(active_players)
            required = self.config["required_players"]
            status = self.status
            everyone_ready = bool(active_players) and all(p.ready for p in active_players)
            can_start = status == "lobby" and player_count >= required and everyone_ready
            leader = self.players.get(self.leader_id) if self.leader_id else None
            payload = {
                "code": self.code,
                "status": status,
                "round": self.round_number,
                "playerCount": player_count,
                "requiredPlayers": required,
                "everyoneReady": everyone_ready,
                "canStart": can_start,
                "players": players,
                "leaderId": self.leader_id,
                "leaderName": leader.name if leader else None,
                "config": self._config_payload_unlocked(),
                "configLimits": self._config_limits_payload(),
            }
        return payload


class LobbyManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lobbies: Dict[str, GameState] = {}

    def _generate_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choices(alphabet, k=5))

    def create_lobby(self, host_name: str) -> Tuple[GameState, Player]:
        with self._lock:
            while True:
                code = self._generate_code()
                if code not in self._lobbies:
                    lobby = GameState(code=code)
                    self._lobbies[code] = lobby
                    break
        player = lobby.add_player(host_name)
        return lobby, player

    def get_lobby(self, code: str) -> Optional[GameState]:
        if not code:
            return None
        with self._lock:
            return self._lobbies.get(code.upper())

    def join_lobby(self, code: str, name: str) -> Tuple[Optional[GameState], Optional[Player], Optional[str]]:
        lobby = self.get_lobby(code)
        if not lobby:
            return None, None, "Lobby nao encontrado."
        if lobby.status != "lobby":
            return None, None, "O jogo ja comecou. Aguarda terminar para entrar."
        if lobby.has_player_named(name):
            return None, None, "Esse nome ja esta em uso neste lobby."
        player = lobby.add_player(name)
        return lobby, player, None

    def remove_player(self, code: str, player_id: str) -> bool:
        lobby = self.get_lobby(code)
        if not lobby:
            return False
        removed = lobby.remove_player(player_id)
        if removed:
            self._cleanup_if_empty(lobby)
        return removed

    def discard_lobby(self, code: str) -> None:
        if not code:
            return
        with self._lock:
            self._lobbies.pop(code.upper(), None)

    def _cleanup_if_empty(self, lobby: GameState) -> None:
        if lobby.is_empty():
            self.discard_lobby(lobby.code)


app = Flask(__name__)
app.secret_key = "among-us-irl-demo"  # replace with environment secret in production

lobby_manager = LobbyManager()


def _clear_session() -> None:
    session.pop("player_id", None)
    session.pop("lobby_code", None)


def _current_context(require_player: bool = True) -> Tuple[Optional[GameState], Optional[Player]]:
    lobby_code = session.get("lobby_code")
    player_id = session.get("player_id")
    if not lobby_code:
        return None, None
    lobby = lobby_manager.get_lobby(lobby_code)
    if not lobby:
        _clear_session()
        return None, None
    player = lobby.current_player(player_id) if player_id else None
    if require_player and not player:
        session.pop("player_id", None)
        return None, None
    return lobby, player


def _leave_current_lobby() -> None:
    lobby, player = _current_context(require_player=False)
    if lobby and player:
        lobby_manager.remove_player(lobby.code, player.player_id)
    _clear_session()


@app.route("/", methods=["GET"])
def index():
    lobby_obj, player = _current_context(require_player=False)
    if lobby_obj and player:
        return redirect(url_for("lobby"))
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create_lobby_route():
    name = (request.form.get("name") or "").strip()
    join_code = (request.form.get("code") or "").strip().upper()
    if not name:
        return render_template(
            "index.html",
            create_error="Escolhe um nome para criares o lobby.",
            join_error=None,
            join_code=join_code,
            create_name=name,
            join_name="",
        )

    previous_code = session.get("lobby_code")
    previous_player = session.get("player_id")
    lobby_obj, player = lobby_manager.create_lobby(name)
    if previous_code and previous_player:
        lobby_manager.remove_player(previous_code, previous_player)
    session["lobby_code"] = lobby_obj.code
    session["player_id"] = player.player_id
    return redirect(url_for("lobby"))


@app.route("/join", methods=["POST"])
def join():
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    if not code:
        return render_template(
            "index.html",
            join_error="Indica o codigo do lobby.",
            create_error=None,
            join_code=code,
            create_name="",
            join_name=name,
        )
    if not name:
        return render_template(
            "index.html",
            join_error="Escolhe um nome para entrares.",
            create_error=None,
            join_code=code,
            create_name="",
            join_name=name,
        )

    lobby_obj, player, error = lobby_manager.join_lobby(code, name)
    if error:
        return render_template(
            "index.html",
            join_error=error,
            create_error=None,
            join_code=code,
            create_name="",
            join_name=name,
        )

    previous_code = session.get("lobby_code")
    previous_player = session.get("player_id")
    if previous_code and previous_player:
        lobby_manager.remove_player(previous_code, previous_player)

    session["lobby_code"] = lobby_obj.code
    session["player_id"] = player.player_id
    return redirect(url_for("lobby"))


@app.route("/lobby", methods=["GET"])
def lobby():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return redirect(url_for("index"))
    return render_template("lobby.html", lobby_code=lobby_obj.code)


@app.route("/game", methods=["GET"])
def game():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return redirect(url_for("index"))
    if lobby_obj.status not in {"in_game", "meeting", "ended"}:
        return redirect(url_for("lobby"))
    return render_template("game.html")


@app.route("/leave", methods=["POST"])
def leave():
    _leave_current_lobby()
    return redirect(url_for("index"))


@app.route("/api/state", methods=["GET"])
def api_state():
    lobby_obj, player = _current_context(require_player=False)
    if not lobby_obj:
        return jsonify({"ok": False, "error": "Lobby nao encontrado."}), 404
    player_id = player.player_id if player else ""
    snapshot = lobby_obj.lobby_snapshot(player_id)
    return jsonify(snapshot)


@app.route("/api/player", methods=["GET"])
def api_player():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        _clear_session()
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    payload = lobby_obj.player_view(player.player_id)
    return jsonify(payload)


@app.route("/api/tasks/complete", methods=["POST"])
def api_tasks_complete():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    task_id = data.get("taskId", "")
    done = bool(data.get("done", True))
    result = lobby_obj.mark_task(player.player_id, task_id, done)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/medic/vitals", methods=["POST"])
def api_medic_vitals():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = lobby_obj.medic_activate_vitals(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/report", methods=["POST"])
def api_report():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    body_id = data.get("bodyId") or data.get("body_id")
    result = lobby_obj.start_meeting(player.player_id, body_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/meeting/emergency", methods=["POST"])
def api_meeting_emergency():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = lobby_obj.call_emergency_meeting(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/meeting/vote", methods=["POST"])
def api_meeting_vote():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    target = data.get("target")
    vote_target = GameState.SKIP_VOTE if target == GameState.SKIP_VOTE else target
    result = lobby_obj.cast_vote(player.player_id, vote_target)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/ready", methods=["POST"])
def api_ready():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404

    data = request.get_json(silent=True) or {}
    ready = bool(data.get("ready"))
    if not lobby_obj.toggle_ready(player.player_id, ready):
        return jsonify({"ok": False, "error": "Nao foi possivel actualizar o estado."}), 400
    return jsonify({"ok": True, "ready": ready})


@app.route("/api/start", methods=["POST"])
def api_start():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = lobby_obj.start_game()
    if result.get("ok"):
        return jsonify({"ok": True, "redirect": url_for("game")})
    return jsonify(result), 400


@app.route("/api/impostor/kill", methods=["POST"])
def api_impostor_kill():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    target_id = data.get("targetId") or data.get("target_id")
    result = lobby_obj.impostor_kill(player.player_id, target_id or "")
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/impostor/sabotage", methods=["POST"])
def api_impostor_sabotage():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    result = lobby_obj.impostor_sabotage(player.player_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/reset", methods=["POST"])
def api_reset():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    if not lobby_obj.is_leader(player.player_id):
        return jsonify({"ok": False, "error": "So o lider pode terminar o jogo."}), 403
    lobby_obj.reset_to_lobby()
    return jsonify({"ok": True, "redirect": url_for("lobby")})


@app.route("/api/lobby/config", methods=["POST"])
def api_lobby_config():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    updates: Dict[str, int] = {}
    if "requiredPlayers" in data:
        try:
            updates["requiredPlayers"] = int(data["requiredPlayers"])
        except (TypeError, ValueError):
            updates["requiredPlayers"] = data["requiredPlayers"]
    if "killCooldown" in data:
        try:
            updates["killCooldown"] = int(data["killCooldown"])
        except (TypeError, ValueError):
            updates["killCooldown"] = data["killCooldown"]
    result = lobby_obj.update_config(player.player_id, updates)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/lobby/kick", methods=["POST"])
def api_lobby_kick():
    lobby_obj, player = _current_context()
    if not lobby_obj or not player:
        return jsonify({"ok": False, "error": "Sessao expirada. Volta ao lobby."}), 404
    data = request.get_json(silent=True) or {}
    target_id = data.get("playerId") or data.get("player_id")
    if not target_id:
        return jsonify({"ok": False, "error": "Jogador invalido."}), 400
    result = lobby_obj.kick_player(player.player_id, target_id)
    status_code = 200 if result.get("ok") else 400
    if result.get("ok") and lobby_obj.is_empty():
        lobby_manager.discard_lobby(lobby_obj.code)
    return jsonify(result), status_code


if __name__ == "__main__":
    app.run(debug=True)
