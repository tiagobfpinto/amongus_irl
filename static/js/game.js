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
const reportBtn = document.getElementById("report-btn");
const progressBarEl = document.getElementById("task-progress-bar");
const progressLabelEl = document.getElementById("task-progress-label");
const leaderBadgeEl = document.getElementById("leader-badge");
const meetingOverlay = document.getElementById("meeting-overlay");
const meetingOptionsEl = document.getElementById("meeting-options");
const meetingTimerEl = document.getElementById("meeting-timer");
const meetingFeedbackEl = document.getElementById("meeting-feedback");
const meetingSummaryEl = document.getElementById("meeting-summary");
const meetingSummaryTextEl = document.getElementById("meeting-summary-text");
const meetingSummaryVotesEl = document.getElementById("meeting-summary-votes");
const meetingSummaryCloseBtn = document.getElementById("meeting-summary-close");
const gameOverOverlay = document.getElementById("game-over-overlay");
const gameOverTitleEl = document.getElementById("game-over-title");
const gameOverTextEl = document.getElementById("game-over-text");
const gameOverResetBtn = document.getElementById("game-over-reset");
const impostorRevealEl = document.getElementById("impostor-reveal");
const impostorRevealContent = impostorRevealEl ? impostorRevealEl.querySelector(".reveal-content") : null;

const POLL_INTERVAL = 4000;
const SKIP_VOTE = "skip";
const PROGRESS_FLASH_CLASS = "progress-flash";

let pollTimer = null;
let killCountdownTimer = null;
let meetingCountdownTimer = null;
let killRemaining = 0;
let isImpostor = false;
let isAlive = true;
let currentStatus = "lobby";
let impostorRevealShown = false;
let lastMeetingId = null;
let lastSummaryId = null;
let lastRevealedRatio = 0;
let isFetching = false;
let fetchPending = false;
let isLeader = false;

function translateRole(role) {
    if (role === "impostor") {
        return "Impostor";
    }
    if (role === "crewmate") {
        return "Tripulante";
    }
    return "...";
}

function roleHint(role) {
    if (role === "impostor") {
        return "Finge fazer tarefas e evita ser apanhado.";
    }
    if (role === "crewmate") {
        return "Completa as tuas tarefas e desconfia dos impostores.";
    }
    return "A aguardar inicio do jogo.";
}

function createTaskElement(task) {
    const li = document.createElement("li");
    li.classList.toggle("done", !!task.done);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!task.done;
    checkbox.dataset.taskId = task.id || "";
    checkbox.addEventListener("change", handleTaskToggle);

    const span = document.createElement("span");
    span.classList.add("task-name");
    span.textContent = task.name || "Tarefa";

    li.appendChild(checkbox);
    li.appendChild(span);
    return li;
}

function renderTaskGroup(element, items) {
    if (!element) {
        return;
    }
    element.innerHTML = "";
    if (!items || items.length === 0) {
        const li = document.createElement("li");
        li.classList.add("muted");
        li.textContent = "Sem tarefas atribuidas.";
        element.appendChild(li);
        return;
    }
    for (let i = 0; i < items.length; i += 1) {
        element.appendChild(createTaskElement(items[i]));
    }
}

function renderTasks(tasks) {
    renderTaskGroup(tasksCommonEl, tasks && tasks.common);
    renderTaskGroup(tasksLongEl, tasks && tasks.long);
    renderTaskGroup(tasksFastEl, tasks && tasks.fast);
}

function parseJsonSafe(response) {
    return response.json().catch(function () {
        return {};
    });
}

function applyProgress(progress) {
    if (!progressBarEl || !progressLabelEl) {
        return;
    }
    const total = progress && typeof progress.total === "number" ? progress.total : 0;
    const rawRevealed = progress && typeof progress.revealed === "number" ? progress.revealed : 0;
    const revealedRatio = Math.max(0, Math.min(1, rawRevealed));
    const percentage = (revealedRatio * 100).toFixed(1);
    progressBarEl.style.width = percentage + "%";
    const revealedCount = total ? Math.round(revealedRatio * total) : 0;
    progressLabelEl.textContent = total ? revealedCount + " de " + total + " tarefas reveladas." : "Nenhuma tarefa revelada ainda.";

    if (revealedRatio > lastRevealedRatio) {
        progressBarEl.classList.remove(PROGRESS_FLASH_CLASS);
        void progressBarEl.offsetWidth;
        progressBarEl.classList.add(PROGRESS_FLASH_CLASS);
    }
    lastRevealedRatio = revealedRatio;
}

function handleTaskToggle(event) {
    const checkbox = event.target;
    if (!checkbox || checkbox.tagName !== "INPUT") {
        return;
    }
    const taskId = checkbox.dataset.taskId;
    if (!taskId) {
        return;
    }
    const listItem = checkbox.closest("li");
    const done = checkbox.checked;
    checkbox.disabled = true;
    updateTaskStatus(taskId, done)
        .then(function () {
            if (listItem) {
                listItem.classList.toggle("done", done);
            }
        })
        .catch(function () {
            checkbox.checked = !done;
        })
        .finally(function () {
            checkbox.disabled = false;
        });
}

function updateKillUI() {
    if (!impostorToolsEl) {
        return;
    }
    const canUse = isImpostor && isAlive && currentStatus === "in_game";
    if (!canUse) {
        impostorToolsEl.classList.add("hidden");
        return;
    }
    impostorToolsEl.classList.remove("hidden");
    const remaining = Math.max(0, killRemaining);
    if (killBtn) {
        killBtn.disabled = remaining > 0;
    }
    if (killTimerEl) {
        killTimerEl.textContent = "Cooldown: " + remaining + "s";
    }
}

function startKillCountdown() {
    stopKillCountdown();
    if (killRemaining <= 0) {
        return;
    }
    killCountdownTimer = setInterval(function () {
        if (killRemaining > 0) {
            killRemaining -= 1;
            updateKillUI();
        } else {
            stopKillCountdown();
        }
    }, 1000);
}

function stopKillCountdown() {
    if (killCountdownTimer) {
        clearInterval(killCountdownTimer);
        killCountdownTimer = null;
    }
}

function playImpostorReveal() {
    if (!impostorRevealEl || !impostorRevealContent) {
        return;
    }
    impostorRevealContent.classList.remove("play");
    void impostorRevealContent.offsetWidth;
    impostorRevealEl.classList.remove("hidden");
    impostorRevealContent.classList.add("play");
    setTimeout(function () {
        impostorRevealEl.classList.add("hidden");
    }, 2800);
}

function renderMeetingOptions(meeting) {
    if (!meetingOptionsEl) {
        return;
    }
    meetingOptionsEl.innerHTML = "";
    const myVote = meeting ? meeting.myVote : null;
    const disabled = !isAlive;
    const alivePlayers = meeting && meeting.alivePlayers ? meeting.alivePlayers : [];

    for (let i = 0; i < alivePlayers.length; i += 1) {
        const player = alivePlayers[i];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.dataset.target = player.id;
        btn.title = player.name || "";
        if (player.id === myVote) {
            btn.classList.add("selected");
        }
        btn.disabled = disabled;
        btn.addEventListener("click", function () {
            sendVote(player.id);
        });

        const option = document.createElement("div");
        option.classList.add("vote-option");

        if (player.avatar) {
            const avatar = document.createElement("img");
            avatar.src = player.avatar;
            avatar.alt = player.name || "Jogador";
            avatar.classList.add("vote-avatar");
            option.appendChild(avatar);
        }

        const label = document.createElement("span");
        label.classList.add("vote-name");
        label.textContent = player.name;
        option.appendChild(label);

        btn.appendChild(option);
        meetingOptionsEl.appendChild(btn);
    }

    const skipBtn = document.createElement("button");
    skipBtn.type = "button";
    skipBtn.textContent = "Skip";
    skipBtn.classList.add("skip");
    skipBtn.disabled = disabled;
    if (myVote === SKIP_VOTE) {
        skipBtn.classList.add("selected");
    }
    skipBtn.addEventListener("click", function () {
        sendVote(SKIP_VOTE);
    });
    meetingOptionsEl.appendChild(skipBtn);
}

function startMeetingCountdown(seconds) {
    stopMeetingCountdown();
    let remaining = Math.max(0, seconds);
    const update = function () {
        if (meetingTimerEl) {
            meetingTimerEl.textContent = remaining + "s";
        }
        if (remaining <= 0) {
            stopMeetingCountdown();
        }
        remaining -= 1;
    };
    update();
    meetingCountdownTimer = setInterval(update, 1000);
}

function stopMeetingCountdown() {
    if (meetingCountdownTimer) {
        clearInterval(meetingCountdownTimer);
        meetingCountdownTimer = null;
    }
}

function showMeeting(meeting) {
    if (!meetingOverlay) {
        return;
    }
    if (meeting && meeting.id !== lastMeetingId && meetingFeedbackEl) {
        meetingFeedbackEl.textContent = "";
        lastMeetingId = meeting.id;
    }
    meetingOverlay.classList.remove("hidden");
    renderMeetingOptions(meeting);
    startMeetingCountdown(meeting ? meeting.endsIn || 0 : 0);
}

function hideMeeting() {
    if (!meetingOverlay) {
        return;
    }
    meetingOverlay.classList.add("hidden");
    stopMeetingCountdown();
    lastMeetingId = null;
}

function describeSummary(summary) {
    if (!summary) {
        return "Reuniao concluida.";
    }
    if (summary.gameOver) {
        if (summary.gameOver.message) {
            return summary.gameOver.message;
        }
        if (summary.gameOver.winner === "crewmates") {
            return "O impostor foi expulso. Tripulacao vence!";
        }
        if (summary.gameOver.winner === "impostor") {
            return "Impostor venceu.";
        }
    }
    if (summary.outcome === "ejected" && summary.ejected) {
        return summary.ejected.name + " foi expulso.";
    }
    if (summary.outcome === "skipped") {
        return "A votacao terminou em skip.";
    }
    if (summary.outcome === "no_votes") {
        return "Ninguem votou nesta reuniao.";
    }
    return "Reuniao terminada sem expulsao.";
}

function renderSummaryVotes(votes) {
    if (!meetingSummaryVotesEl) {
        return;
    }
    meetingSummaryVotesEl.innerHTML = "";
    if (!votes || votes.length === 0) {
        const li = document.createElement("li");
        li.textContent = "Sem votos registados.";
        meetingSummaryVotesEl.appendChild(li);
        return;
    }
    for (let i = 0; i < votes.length; i += 1) {
        const vote = votes[i];
        const li = document.createElement("li");
        const nameSpan = document.createElement("span");
        nameSpan.textContent = vote.label;
        const countSpan = document.createElement("span");
        countSpan.classList.add("count");
        countSpan.textContent = vote.count;
        li.appendChild(nameSpan);
        li.appendChild(countSpan);
        meetingSummaryVotesEl.appendChild(li);
    }
}

function showMeetingSummary(summary) {
    hideMeeting();
    if (!meetingSummaryEl) {
        return;
    }
    meetingSummaryTextEl.textContent = describeSummary(summary);
    renderSummaryVotes(summary ? summary.votes : []);
    meetingSummaryEl.classList.remove("hidden");
    if (summary && summary.progress) {
        applyProgress(summary.progress);
    }
}

function hideMeetingSummary() {
    if (!meetingSummaryEl) {
        return;
    }
    meetingSummaryEl.classList.add("hidden");
}

function showGameOver(info) {
    if (!gameOverOverlay) {
        return;
    }
    hideMeetingSummary();
    if (info.winner === "crewmates") {
        gameOverTitleEl.textContent = "Tripulacao venceu!";
        gameOverTextEl.textContent = info.message || "O impostor foi eliminado.";
    } else {
        const impostorName =
            info.impostor && info.impostor.name ? info.impostor.name : "Impostor";
        const headline = info.message || "Impostor venceu!";
        gameOverTitleEl.textContent = headline;
        const detail =
            info.reason === "last_crewmate"
                ? "Restava apenas um tripulante vivo."
                : "O impostor " + impostorName + " manteve o controlo da nave.";
        gameOverTextEl.textContent = detail;
    }
    gameOverOverlay.classList.remove("hidden");
}

function hideGameOver() {
    if (!gameOverOverlay) {
        return;
    }
    gameOverOverlay.classList.add("hidden");
}

function updateTaskStatus(taskId, done) {
    return fetch("/api/tasks/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ taskId: taskId, done: done })
    })
        .then(function (response) {
            return parseJsonSafe(response).then(function (data) {
                if (!response.ok || !data.ok) {
                    const msg = data && data.error ? data.error : "Nao foi possivel marcar a tarefa.";
                    throw new Error(msg);
                }
                if (data.progress) {
                    applyProgress(data.progress);
                }
                return data;
            });
        });
}

function sendVote(target) {
    if (!isAlive) {
        return Promise.resolve();
    }
    if (meetingFeedbackEl) {
        meetingFeedbackEl.textContent = "A enviar voto...";
    }
    return fetch("/api/meeting/vote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: target })
    })
        .then(function (response) {
            return parseJsonSafe(response).then(function (data) {
                if (!response.ok || !data.ok) {
                    const msg = data && data.error ? data.error : "Nao foi possivel votar.";
                    throw new Error(msg);
                }
                if (meetingFeedbackEl) {
                    meetingFeedbackEl.textContent = data.final ? "Reuniao encerrada." : "Voto registado.";
                }
                fetchPlayer();
            });
        })
        .catch(function (error) {
            console.error(error);
            if (meetingFeedbackEl) {
                meetingFeedbackEl.textContent = error.message;
            }
        });
}

function reportBody() {
    if (!reportBtn) {
        return;
    }
    reportBtn.disabled = true;
    fetch("/api/report", { method: "POST" })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data.ok) {
                throw new Error(data.error || "Nao foi possivel chamar reuniao.");
            }
            fetchPlayer();
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
        })
        .finally(function () {
            reportBtn.disabled = false;
        });
}

function triggerKill() {
    if (!isImpostor || !isAlive || currentStatus !== "in_game" || !killBtn) {
        return;
    }
    killBtn.disabled = true;
    fetch("/api/impostor/kill", { method: "POST" })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data.ok) {
                throw new Error(data.error || "Nao podes matar neste momento.");
            }
            killRemaining = typeof data.cooldown === "number" ? data.cooldown : 0;
            updateKillUI();
            startKillCountdown();
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
        })
        .finally(function () {
            killBtn.disabled = killRemaining > 0;
        });
}

function resetGame() {
    if (!isLeader) {
        alert("Apenas o lider pode terminar o jogo.");
        return;
    }
    if (!confirm("Terminar o jogo e voltar ao lobby?")) {
        return;
    }
    const buttons = [];
    if (resetBtn && !resetBtn.classList.contains("hidden")) {
        buttons.push(resetBtn);
    }
    if (gameOverResetBtn && !gameOverResetBtn.classList.contains("hidden")) {
        buttons.push(gameOverResetBtn);
    }
    buttons.forEach(function (btn) {
        btn.disabled = true;
    });
    fetch("/api/reset", { method: "POST" })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data.ok) {
                throw new Error(data.error || "Nao foi possivel reiniciar.");
            }
            window.location.href = data.redirect || "/lobby";
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
        })
        .finally(function () {
            buttons.forEach(function (btn) {
                btn.disabled = !isLeader;
            });
        });
}

function fetchPlayer() {
    if (isFetching) {
        fetchPending = true;
        return;
    }
    isFetching = true;
    fetch("/api/player")
        .then(function (response) {
            if (response.status === 404) {
                window.location.href = "/";
                return null;
            }
            return response.json();
        })
        .then(function (data) {
            if (!data) {
                return;
            }
            if (!data.ok) {
                throw new Error(data.error || "Erro ao carregar estado do jogador.");
            }

            currentStatus = data.status;
            if (currentStatus === "lobby") {
                impostorRevealShown = false;
                lastSummaryId = null;
                lastRevealedRatio = 0;
                hideMeeting();
                hideMeetingSummary();
                hideGameOver();
                window.location.href = "/lobby";
                return;
            }

        const role = data.role || "crewmate";
        isImpostor = role === "impostor";
        isAlive = data.alive !== false;
        isLeader = data.isLeader === true;
        if (leaderBadgeEl) {
            leaderBadgeEl.classList.toggle("hidden", !isLeader);
        }
        if (resetBtn) {
            resetBtn.classList.toggle("hidden", !isLeader);
            resetBtn.disabled = !isLeader;
        }
        if (gameOverResetBtn) {
            if (isLeader) {
                gameOverResetBtn.textContent = "Terminar jogo";
                gameOverResetBtn.disabled = false;
            } else {
                gameOverResetBtn.textContent = "Aguardar lider";
                gameOverResetBtn.disabled = true;
            }
        }

            if (roleNameEl) {
                roleNameEl.textContent = translateRole(role);
            }
        if (roleCardEl) {
            roleCardEl.classList.toggle("crewmate", role === "crewmate");
            roleCardEl.classList.toggle("impostor", role === "impostor");
            roleCardEl.classList.toggle("leader", isLeader);
        }
            if (roleHintEl) {
                roleHintEl.textContent = roleHint(role);
            }

            if (isImpostor && !impostorRevealShown && currentStatus !== "lobby") {
                impostorRevealShown = true;
                playImpostorReveal();
            }

            renderTasks(data.tasks || {});

            const killValue = typeof data.killRemaining === "number" ? data.killRemaining : parseInt(data.killRemaining, 10);
            killRemaining = isNaN(killValue) ? 0 : killValue;
            updateKillUI();
            if (killRemaining > 0) {
                startKillCountdown();
            } else {
                stopKillCountdown();
            }

            if (data.progress) {
                applyProgress(data.progress);
            }

            if (data.meeting) {
                showMeeting(data.meeting);
            } else {
                hideMeeting();
            }

            if (data.meetingSummary && data.meetingSummary.id !== lastSummaryId) {
                lastSummaryId = data.meetingSummary.id;
                showMeetingSummary(data.meetingSummary);
            }

            if (data.gameOver) {
                showGameOver(data.gameOver);
            } else {
                hideGameOver();
            }

            const cannotReport = !isAlive || data.status !== "in_game" || !!data.meeting || !!data.gameOver;
            if (reportBtn) {
                reportBtn.disabled = cannotReport;
            }
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
        })
        .finally(function () {
            isFetching = false;
            if (fetchPending) {
                fetchPending = false;
                fetchPlayer();
            }
        });
}

function setup() {
    fetchPlayer();
    pollTimer = setInterval(fetchPlayer, POLL_INTERVAL);

    if (refreshBtn) {
        refreshBtn.addEventListener("click", fetchPlayer);
    }
    if (resetBtn) {
        resetBtn.addEventListener("click", resetGame);
    }
    if (killBtn) {
        killBtn.addEventListener("click", triggerKill);
    }
    if (reportBtn) {
        reportBtn.addEventListener("click", reportBody);
    }
    if (meetingSummaryCloseBtn) {
        meetingSummaryCloseBtn.addEventListener("click", function () {
            hideMeetingSummary();
        });
    }
    if (gameOverResetBtn) {
        gameOverResetBtn.addEventListener("click", resetGame);
    }
    if (progressBarEl) {
        progressBarEl.addEventListener("animationend", function () {
            progressBarEl.classList.remove(PROGRESS_FLASH_CLASS);
        });
    }
}

window.addEventListener("DOMContentLoaded", setup);
