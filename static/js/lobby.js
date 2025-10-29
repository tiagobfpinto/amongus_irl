const playersList = document.getElementById("players");
const readyBtn = document.getElementById("ready-btn");
const startBtn = document.getElementById("start-btn");
const messageBox = document.getElementById("lobby-message");
const playerCountLabel = document.getElementById("player-count");
const readyCountLabel = document.getElementById("ready-count");
const statusLabel = document.getElementById("game-status");

let isReady = false;
let pollingTimer = null;

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

function renderPlayers(players) {
    playersList.innerHTML = "";
    let readyCount = 0;

    players.forEach((player) => {
        const li = document.createElement("li");
        li.textContent = player.name;
        if (player.is_me) {
            li.classList.add("me");
            isReady = player.ready;
        }

        const status = document.createElement("span");
        status.textContent = player.ready ? "Ready" : "Waiting";
        status.classList.add(player.ready ? "ready" : "muted");
        li.appendChild(status);
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

async function fetchState() {
    try {
        const response = await fetch("/api/state");
        if (!response.ok) {
            throw new Error(`Erro ao carregar estado (${response.status})`);
        }
        const data = await response.json();
        playerCountLabel.textContent = data.playerCount.toString();
        statusLabel.textContent = data.status === "in_game" ? "Jogo em curso" : "Lobby";

        renderPlayers(data.players || []);

        if (data.status === "in_game") {
            window.location.href = "/game";
            return;
        }

        const remaining = Math.max(0, data.requiredPlayers - data.playerCount);
        if (data.playerCount < data.requiredPlayers) {
            setMessage(
                `Faltam ${remaining} jogador(es) para atingir o mínimo de ${data.requiredPlayers}.`
            );
        } else if (!data.everyoneReady) {
            setMessage("Nem todos estão prontos ainda.");
        } else {
            setMessage("Tudo pronto! Qualquer pessoa pode começar.");
        }

        startBtn.disabled = !data.canStart;
    } catch (error) {
        console.error(error);
        setMessage("Não foi possível obter o estado do lobby. A tentar de novo...", "error");
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
            throw new Error(data.error || "Não foi possível iniciar o jogo.");
        }
        window.location.href = data.redirect || "/game";
    } catch (error) {
        console.error(error);
        setMessage(error.message, "error");
    } finally {
        // enable again so someone else can try
        startBtn.disabled = false;
    }
}

function setup() {
    fetchState();
    pollingTimer = setInterval(fetchState, 2500);
    readyBtn?.addEventListener("click", toggleReady);
    startBtn?.addEventListener("click", startGame);
}

window.addEventListener("DOMContentLoaded", setup);
