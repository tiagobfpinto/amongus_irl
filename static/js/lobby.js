const playersList = document.getElementById("players");
const readyBtn = document.getElementById("ready-btn");
const startBtn = document.getElementById("start-btn");
const messageBox = document.getElementById("lobby-message");
const playerCountLabel = document.getElementById("player-count");
const readyCountLabel = document.getElementById("ready-count");
const statusLabel = document.getElementById("game-status");
const leaderNameLabel = document.getElementById("leader-name");
const lobbyCodeLabel = document.getElementById("lobby-code");
const configSection = document.getElementById("config-section");
const requiredPlayersInput = document.getElementById("required-players-input");
const killCooldownInput = document.getElementById("kill-cooldown-input");
const saveConfigBtn = document.getElementById("save-config-btn");
const configFeedback = document.getElementById("config-feedback");

let isReady = false;
let pollingTimer = null;
let leaderId = "";
let myPlayerId = "";
let amLeader = false;
let canManageLobby = false;
let currentLimits = {
    requiredPlayers: { min: 2, max: 15 },
    killCooldown: { min: 10, max: 600 },
};

function setMessage(text, variant = "info") {
    if (!messageBox) {
        return;
    }
    if (!text) {
        messageBox.classList.add("hidden");
        messageBox.textContent = "";
        return;
    }
    messageBox.textContent = text;
    messageBox.classList.remove("hidden", "error", "info");
    messageBox.classList.add(variant);
}

function setConfigStatus(text, variant = "info") {
    if (!configFeedback) {
        return;
    }
    if (!text) {
        configFeedback.textContent = "";
        configFeedback.classList.add("hidden");
        configFeedback.classList.remove("error", "info");
        return;
    }
    configFeedback.textContent = text;
    configFeedback.classList.remove("hidden", "error", "info");
    configFeedback.classList.add(variant);
}

function renderPlayers(players) {
    if (!playersList) {
        return;
    }
    playersList.innerHTML = "";
    let readyCount = 0;

    players.forEach((player) => {
        const li = document.createElement("li");
        li.classList.add("player-entry");

        if (player.is_me) {
            li.classList.add("me");
            isReady = player.ready;
            myPlayerId = player.id || "";
        }

        if (player.avatar) {
            const avatar = document.createElement("img");
            avatar.src = player.avatar;
            avatar.alt = player.name || "Jogador";
            avatar.classList.add("player-avatar");
            li.appendChild(avatar);
        }

        const info = document.createElement("div");
        info.classList.add("player-info");

        const nameSpan = document.createElement("span");
        nameSpan.classList.add("player-name");
        nameSpan.textContent = player.name;

        const header = document.createElement("div");
        header.classList.add("player-label");
        header.appendChild(nameSpan);

        if (player.leader) {
            const badge = document.createElement("span");
            badge.classList.add("badge", "leader");
            badge.textContent = "Lider";
            header.appendChild(badge);
        }

        const statusSpan = document.createElement("span");
        statusSpan.textContent = player.ready ? "Pronto" : "A espera";
        statusSpan.classList.add("player-status", player.ready ? "ready" : "muted");

        info.appendChild(header);
        info.appendChild(statusSpan);

        li.appendChild(info);

        if (canManageLobby && !player.is_me) {
            const kickBtn = document.createElement("button");
            kickBtn.type = "button";
            kickBtn.textContent = "Expulsar";
            kickBtn.classList.add("ghost", "danger", "kick-btn");
            kickBtn.addEventListener("click", function () {
                kickPlayer(player.id);
            });
            li.appendChild(kickBtn);
        }

        playersList.appendChild(li);

        if (player.ready) {
            readyCount += 1;
        }
    });

    readyCountLabel.textContent = readyCount.toString();
    readyBtn.textContent = isReady ? "Cancelar pronto" : "Estou pronto";
    readyBtn.classList.toggle("ghost", isReady);
    readyBtn.classList.toggle("primary", !isReady);
}

function applyConfigControls(config = {}, limits = {}, locked = false) {
    if (!requiredPlayersInput || !killCooldownInput) {
        return;
    }
    const requiredValue = typeof config.requiredPlayers === "number" ? config.requiredPlayers : parseInt(requiredPlayersInput.value || "0", 10);
    const cooldownValue = typeof config.killCooldown === "number" ? config.killCooldown : parseInt(killCooldownInput.value || "0", 10);
    requiredPlayersInput.value = Number.isFinite(requiredValue) ? requiredValue : "";
    killCooldownInput.value = Number.isFinite(cooldownValue) ? cooldownValue : "";

    if (limits.requiredPlayers) {
        currentLimits.requiredPlayers = limits.requiredPlayers;
        requiredPlayersInput.min = limits.requiredPlayers.min;
        requiredPlayersInput.max = limits.requiredPlayers.max;
    }
    if (limits.killCooldown) {
        currentLimits.killCooldown = limits.killCooldown;
        killCooldownInput.min = limits.killCooldown.min;
        killCooldownInput.max = limits.killCooldown.max;
    }

    const disabled = !canManageLobby || locked;
    requiredPlayersInput.disabled = disabled;
    killCooldownInput.disabled = disabled;
    if (saveConfigBtn) {
        saveConfigBtn.disabled = disabled;
        saveConfigBtn.classList.toggle("ghost", disabled);
    }
    if (configSection) {
        configSection.classList.toggle("locked", locked);
    }
}

async function saveConfig(event) {
    if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
    }
    if (!canManageLobby) {
        return;
    }
    try {
        setConfigStatus("A guardar...");
        const payload = {};
        const requiredValue = parseInt(requiredPlayersInput.value, 10);
        const cooldownValue = parseInt(killCooldownInput.value, 10);
        if (Number.isFinite(requiredValue)) {
            payload.requiredPlayers = requiredValue;
        }
        if (Number.isFinite(cooldownValue)) {
            payload.killCooldown = cooldownValue;
        }
        const response = await fetch("/api/lobby/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Nao foi possivel actualizar as definicoes.");
        }
        setConfigStatus("Definicoes actualizadas.");
        await fetchState();
    } catch (error) {
        console.error(error);
        setConfigStatus(error.message, "error");
    }
}

async function kickPlayer(playerId) {
    if (!playerId || !canManageLobby) {
        return;
    }
    try {
        const response = await fetch("/api/lobby/kick", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ playerId }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Nao foi possivel expulsar o jogador.");
        }
        const removedName = data.removed && data.removed.name ? data.removed.name : "Jogador";
        setMessage(`${removedName} foi expulso.`);
        await fetchState();
    } catch (error) {
        console.error(error);
        setMessage(error.message, "error");
    }
}

async function fetchState() {
    try {
        const response = await fetch("/api/state");
        if (!response.ok) {
            throw new Error(`Erro ao carregar estado (${response.status})`);
        }
        const data = await response.json();
        const players = data.players || [];
        leaderId = data.leaderId || "";

        const statusMap = {
            lobby: "Lobby",
            in_game: "Jogo em curso",
            meeting: "Reuniao",
            ended: "Terminado",
        };
        statusLabel.textContent = statusMap[data.status] || data.status;

        playerCountLabel.textContent = (data.playerCount || 0).toString();
        if (lobbyCodeLabel) {
            lobbyCodeLabel.textContent = data.code || "----";
        }
        if (leaderNameLabel) {
            leaderNameLabel.textContent = data.leaderName || "Por definir";
        }

        const me = players.find((player) => player.is_me);
        myPlayerId = me && me.id ? me.id : "";
        amLeader = !!(me && me.leader);
        canManageLobby = amLeader && data.status === "lobby";

        renderPlayers(players);
        applyConfigControls(data.config || {}, data.configLimits || currentLimits, data.status !== "lobby");
        if (!canManageLobby) {
            setConfigStatus("");
        }

        if (["in_game", "meeting", "ended"].includes(data.status)) {
            window.location.href = "/game";
            return;
        }

        const requiredPlayers =
            (data.config && typeof data.config.requiredPlayers === "number"
                ? data.config.requiredPlayers
                : data.requiredPlayers) || 0;
        const remaining = Math.max(0, requiredPlayers - (data.playerCount || 0));

        if (data.playerCount < requiredPlayers) {
            setMessage(
                `Faltam ${remaining} jogador(es) para atingir o minimo de ${requiredPlayers}.`
            );
        } else if (!data.everyoneReady) {
            setMessage("Nem todos estao prontos ainda.");
        } else {
            setMessage(
                amLeader
                    ? "Tudo pronto! Podes comecar quando quiseres."
                    : "Tudo pronto! Qualquer pessoa pode comecar."
            );
        }

        readyBtn.disabled = data.status !== "lobby";
        startBtn.disabled = !data.canStart;
    } catch (error) {
        console.error(error);
        setMessage("Nao foi possivel obter o estado do lobby. A tentar de novo...", "error");
    }
}

async function toggleReady() {
    try {
        readyBtn.disabled = true;
        const response = await fetch("/api/ready", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ready: !isReady }),
        });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Erro ao actualizar estado.");
        }
        isReady = !isReady;
        await fetchState();
    } catch (error) {
        console.error(error);
        setMessage(error.message, "error");
    } finally {
        readyBtn.disabled = false;
    }
}

async function startGame() {
    try {
        startBtn.disabled = true;
        const response = await fetch("/api/start", { method: "POST" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Nao foi possivel iniciar o jogo.");
        }
        window.location.href = data.redirect || "/game";
    } catch (error) {
        console.error(error);
        setMessage(error.message, "error");
    } finally {
        startBtn.disabled = false;
    }
}

function setup() {
    fetchState();
    pollingTimer = setInterval(fetchState, 2500);
    if (readyBtn) {
        readyBtn.addEventListener("click", toggleReady);
    }
    if (startBtn) {
        startBtn.addEventListener("click", startGame);
    }
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener("click", saveConfig);
    }
    if (requiredPlayersInput) {
        requiredPlayersInput.addEventListener("input", function () {
            setConfigStatus("");
        });
    }
    if (killCooldownInput) {
        killCooldownInput.addEventListener("input", function () {
            setConfigStatus("");
        });
    }
}

window.addEventListener("DOMContentLoaded", setup);
