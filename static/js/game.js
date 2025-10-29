const roleNameEl = document.getElementById("role-name");
const roleHintEl = document.getElementById("role-hint");
const roleCardEl = document.getElementById("role-card");
const tasksCommonEl = document.getElementById("tasks-common");
const tasksLongEl = document.getElementById("tasks-long");
const tasksFastEl = document.getElementById("tasks-fast");
const impostorToolsEl = document.getElementById("impostor-tools");
const killBtn = document.getElementById("kill-btn");
const killTimerEl = document.getElementById("kill-timer");
const refreshBtn = document.getElementById("refresh-btn");
const resetBtn = document.getElementById("reset-btn");

let pollTimer = null;
let countdownTimer = null;
let killRemaining = 0;
let isImpostor = false;

function translateRole(role) {
    if (role === "impostor") {
        return "Impostor";
    }
    if (role === "crewmate") {
        return "Tripulante";
    }
    return "...";
}

function renderTasks(tasks) {
    const populate = (element, items) => {
        element.innerHTML = "";
        if (!items || items.length === 0) {
            const li = document.createElement("li");
            li.classList.add("muted");
            li.textContent = "Sem tarefas atribuídas.";
            element.appendChild(li);
            return;
        }
        items.forEach((task) => {
            const li = document.createElement("li");
            li.textContent = task;
            element.appendChild(li);
        });
    };

    populate(tasksCommonEl, tasks?.common);
    populate(tasksLongEl, tasks?.long);
    populate(tasksFastEl, tasks?.fast);
}

function updateKillUI() {
    if (!impostorToolsEl) {
        return;
    }
    if (!isImpostor) {
        impostorToolsEl.classList.add("hidden");
        return;
    }
    impostorToolsEl.classList.remove("hidden");
    const canKill = killRemaining <= 0;
    killBtn.disabled = !canKill;
    killTimerEl.textContent = `Cooldown: ${Math.max(0, killRemaining)}s`;
}

function startCountdown() {
    stopCountdown();
    countdownTimer = setInterval(() => {
        if (killRemaining > 0) {
            killRemaining -= 1;
            updateKillUI();
        }
    }, 1000);
}

function stopCountdown() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }
}

async function fetchPlayer() {
    try {
        const response = await fetch("/api/player");
        if (response.status === 404) {
            window.location.href = "/";
            return;
        }
        const data = await response.json();
        if (!data.ok) {
            throw new Error(data.error || "Erro ao carregar estado do jogador.");
        }

        if (data.status === "lobby") {
            window.location.href = "/lobby";
            return;
        }

        const role = data.role || "crewmate";
        isImpostor = role === "impostor";

        roleNameEl.textContent = translateRole(role);
        roleCardEl.classList.toggle("crewmate", role === "crewmate");
        roleCardEl.classList.toggle("impostor", role === "impostor");

        if (isImpostor) {
            roleHintEl.textContent = "Finge fazer tarefas e usa o botão assim que estiver disponível.";
        } else {
            roleHintEl.textContent = "Completa as tuas tarefas e desconfia dos impostores.";
        }

        renderTasks(data.tasks || {});

        killRemaining = parseInt(data.killRemaining ?? 0, 10);
        updateKillUI();
        startCountdown();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

async function triggerKill() {
    if (!isImpostor) {
        return;
    }
    try {
        killBtn.disabled = true;
        const response = await fetch("/api/impostor/kill", { method: "POST" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Não podes matar ainda.");
        }
        killRemaining = data.cooldown ?? 0;
        updateKillUI();
    } catch (error) {
        console.error(error);
        alert(error.message);
    } finally {
        killBtn.disabled = killRemaining > 0;
    }
}

async function resetGame() {
    if (!confirm("Tens a certeza que queres voltar ao lobby?")) {
        return;
    }
    try {
        const response = await fetch("/api/reset", { method: "POST" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Não foi possível reiniciar.");
        }
        window.location.href = data.redirect || "/lobby";
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

function setup() {
    fetchPlayer();
    pollTimer = setInterval(fetchPlayer, 5000);
    refreshBtn?.addEventListener("click", fetchPlayer);
    resetBtn?.addEventListener("click", resetGame);
    killBtn?.addEventListener("click", triggerKill);
}

window.addEventListener("DOMContentLoaded", setup);
