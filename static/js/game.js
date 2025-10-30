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
const deathNoteEl = document.getElementById("death-note");
const meetingLockEl = document.getElementById("meeting-lock");
const meetingReporterEl = document.getElementById("meeting-reporter");
const meetingDeceasedEl = document.getElementById("meeting-deceased");
const killOverlay = document.getElementById("kill-overlay");
const killOptionsEl = document.getElementById("kill-options");
const killCancelBtn = document.getElementById("kill-cancel");
const reportOverlay = document.getElementById("report-overlay");
const reportOptionsEl = document.getElementById("report-options");
const reportFeedbackEl = document.getElementById("report-feedback");
const reportCancelBtn = document.getElementById("report-cancel");
const sabotageBtn = document.getElementById("sabotage-btn");
const sabotageStatusEl = document.getElementById("sabotage-status");
const emergencyBtn = document.getElementById("emergency-btn");
const commsOverlay = document.getElementById("comms-overlay");
const commsCountdownEl = document.getElementById("comms-countdown");
const medicPanel = document.getElementById("medic-panel");
const medicVitalsEl = document.getElementById("medic-vitals");

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
let killTargets = [];
let deadPlayersList = [];
let reportableBodies = [];
let votingLocked = false;
let votingRemaining = 0;
let meetingVoteCountdownTimer = null;
let currentMeetingData = null;
let specialRole = null;
let isMedic = false;
let commsCountdownTimer = null;
let currentCommsRemaining = 0;
let commsActive = false;

function translateRole(role, special) {
    if (role === "impostor") {
        return "Impostor";
    }
    if (special === "medic") {
        return "Tripulante (Medico)";
    }
    if (role === "crewmate") {
        return "Tripulante";
    }
    return "...";
}

function roleHint(role, special) {
    if (role === "impostor") {
        return "Finge fazer tarefas e evita ser apanhado.";
    }
    if (special === "medic") {
        return "Consegue ver as vitals para verificar quem continua vivo.";
    }
    if (role === "crewmate") {
        return "Completa as tuas tarefas e desconfia dos impostores.";
    }
    return "A aguardar inicio do jogo.";
}

function formatTimeHM(seconds) {
    if (!seconds) {
        return "--:--";
    }
    const date = new Date(seconds * 1000);
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return hours + ":" + minutes;
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
    const availableTargets = Array.isArray(killTargets) ? killTargets.length : 0;
    if (killBtn) {
        killBtn.disabled = remaining > 0 || availableTargets === 0;
    }
    if (sabotageBtn) {
        const canSabotage = !commsActive && canUse;
        sabotageBtn.disabled = !canSabotage;
    }
    if (killTimerEl) {
        if (availableTargets === 0) {
            killTimerEl.textContent = "Sem alvos disponiveis.";
        } else {
            killTimerEl.textContent = "Cooldown: " + remaining + "s";
        }
    }
    updateSabotageStatus();
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

function stopVotingDelay() {
    votingLocked = false;
    votingRemaining = 0;
    if (meetingVoteCountdownTimer) {
        clearInterval(meetingVoteCountdownTimer);
        meetingVoteCountdownTimer = null;
    }
    if (meetingOverlay) {
        meetingOverlay.classList.remove("intro-phase");
    }
}

function startVotingDelay(seconds) {
    stopVotingDelay();
    if (!seconds || seconds <= 0) {
        return;
    }
    votingLocked = true;
    votingRemaining = seconds;
    if (meetingOverlay) {
        meetingOverlay.classList.add("intro-phase");
    }
    if (meetingLockEl) {
        meetingLockEl.textContent = "Votacoes iniciam em " + votingRemaining + "s";
    }
    meetingVoteCountdownTimer = setInterval(function () {
        if (votingRemaining > 0) {
            votingRemaining -= 1;
            if (meetingLockEl) {
                meetingLockEl.textContent = "Votacoes iniciam em " + votingRemaining + "s";
            }
        } else {
            stopVotingDelay();
            if (currentMeetingData) {
                renderMeetingOptions(currentMeetingData);
                renderMeetingStatus(currentMeetingData);
            }
        }
    }, 1000);
}

function renderMeetingDeceased(meeting) {
    if (!meetingDeceasedEl) {
        return;
    }
    const deceased = meeting && Array.isArray(meeting.deceased) ? meeting.deceased : [];
    meetingDeceasedEl.innerHTML = "";
    if (deceased.length === 0) {
        meetingDeceasedEl.classList.add("hidden");
        return;
    }
    meetingDeceasedEl.classList.remove("hidden");
    deceased.forEach(function (entry) {
        const card = document.createElement("div");
        card.classList.add("deceased-card", "with-cross");
        if (entry.reported || (meeting.reportedBody && meeting.reportedBody.id === entry.id)) {
            card.classList.add("reported");
        }
        if (entry.avatar) {
            const avatar = document.createElement("img");
            avatar.src = entry.avatar;
            avatar.alt = entry.name || "Jogador";
            avatar.classList.add("avatar");
            card.appendChild(avatar);
        }
        const cross = document.createElement("span");
        cross.classList.add("cross-mark");
        cross.textContent = "X";
        card.appendChild(cross);
        const infoWrap = document.createElement("div");
        infoWrap.classList.add("info");
        const nameSpan = document.createElement("span");
        nameSpan.classList.add("name");
        nameSpan.textContent = entry.name || "Jogador";
        infoWrap.appendChild(nameSpan);
        if (entry.killedAt && !entry.leftGame) {
            const timeSpan = document.createElement("span");
            timeSpan.textContent = "Morto as " + formatTimeHM(entry.killedAt);
            infoWrap.appendChild(timeSpan);
        }
        if (entry.leftGame) {
            const leftSpan = document.createElement("span");
            leftSpan.textContent = "Saiu do jogo.";
            infoWrap.appendChild(leftSpan);
        }
        if (entry.killedByName) {
            const killerSpan = document.createElement("span");
            killerSpan.textContent = "Por " + entry.killedByName;
            infoWrap.appendChild(killerSpan);
        }
        if (meeting && meeting.reportedBody && meeting.reportedBody.id === entry.id) {
            const tag = document.createElement("span");
            tag.classList.add("status-tag");
            tag.textContent = "Corpo reportado";
            infoWrap.appendChild(tag);
        } else if (entry.reported) {
            const tag = document.createElement("span");
            tag.classList.add("status-tag");
            tag.textContent = "Ja reportado";
            infoWrap.appendChild(tag);
        }
        card.appendChild(infoWrap);
        meetingDeceasedEl.appendChild(card);
    });
}

function renderMeetingStatus(meeting) {
    if (meetingReporterEl) {
        if (meeting && meeting.reporter) {
            const prefix =
                meeting && meeting.type === "emergency"
                    ? "Reuniao de emergencia chamada por "
                    : "Reportado por ";
            meetingReporterEl.textContent = prefix + (meeting.reporter.name || "Jogador");
            meetingReporterEl.classList.remove("hidden");
        } else {
            meetingReporterEl.textContent = "";
            meetingReporterEl.classList.add("hidden");
        }
    }
    if (meetingLockEl) {
        if (votingLocked && votingRemaining > 0) {
            meetingLockEl.textContent = "Votacoes iniciam em " + votingRemaining + "s";
        } else {
            meetingLockEl.textContent = "";
        }
    }
    if (!meetingFeedbackEl) {
        return;
    }
    if (!meeting || !meeting.alivePlayers) {
        meetingFeedbackEl.textContent = "";
        return;
    }
    if (votingLocked && votingRemaining > 0) {
        meetingFeedbackEl.textContent = "Aguardem antes de votar.";
        return;
    }
    const pending = meeting.alivePlayers.filter(function (player) {
        return !player.hasVoted;
    });
    if (pending.length === 0) {
        meetingFeedbackEl.textContent = "Todos ja votaram.";
    } else {
        const names = pending.map(function (player) {
            return player.name;
        });
        meetingFeedbackEl.textContent = "Faltam votar: " + names.join(", ");
    }
}

function renderMeetingOptions(meeting) {
    if (!meetingOptionsEl) {
        return;
    }
    meetingOptionsEl.innerHTML = "";
    const myVote = meeting ? meeting.myVote : null;
    const disabled = !isAlive || votingLocked;
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
        if (player.hasVoted) {
            btn.classList.add("has-voted");
        }
        btn.disabled = disabled;
        btn.addEventListener("click", function () {
            const targetName = player.name || "este jogador";
            const confirmed = window.confirm("Tens a certeza que queres expulsar " + targetName + "?");
            if (!confirmed) {
                return;
            }
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

function closeKillModal() {
    if (killOverlay) {
        killOverlay.classList.add("hidden");
    }
}

function renderKillOptions() {
    if (!killOptionsEl) {
        return;
    }
    killOptionsEl.innerHTML = "";
    if (!Array.isArray(killTargets) || killTargets.length === 0) {
        const p = document.createElement("p");
        p.classList.add("muted");
        p.textContent = "Sem alvos disponiveis.";
        killOptionsEl.appendChild(p);
        return;
    }
    killTargets.forEach(function (target) {
        const btn = document.createElement("button");
        btn.type = "button";
        const option = document.createElement("div");
        option.classList.add("vote-option");
        if (target.avatar) {
            const avatar = document.createElement("img");
            avatar.src = target.avatar;
            avatar.alt = target.name || "Jogador";
            avatar.classList.add("vote-avatar");
            option.appendChild(avatar);
        }
        const label = document.createElement("span");
        label.classList.add("vote-name");
        label.textContent = target.name || "Jogador";
        option.appendChild(label);
        btn.appendChild(option);
        btn.addEventListener("click", function () {
            performKill(target.id);
        });
        killOptionsEl.appendChild(btn);
    });
}

function openKillModal() {
    if (!killOverlay) {
        return;
    }
    if (!Array.isArray(killTargets) || killTargets.length === 0) {
        alert("Sem alvos vivos para eliminar.");
        return;
    }
    renderKillOptions();
    killOverlay.classList.remove("hidden");
}

function performKill(targetId) {
    if (!targetId) {
        return;
    }
    const buttons = killOptionsEl ? killOptionsEl.querySelectorAll("button") : [];
    buttons.forEach(function (btn) {
        btn.disabled = true;
    });
    if (killBtn) {
        killBtn.disabled = true;
    }
    fetch("/api/impostor/kill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targetId: targetId })
    })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data || !data.ok) {
                const msg = data && data.error ? data.error : "Nao podes matar neste momento.";
                throw new Error(msg);
            }
            killRemaining = typeof data.cooldown === "number" ? data.cooldown : killRemaining;
            closeKillModal();
            updateKillUI();
            if (killRemaining > 0) {
                startKillCountdown();
            }
            if (data.gameOver) {
                showGameOver(data.gameOver);
            } else {
                fetchPlayer();
            }
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
            if (killOverlay && !killOverlay.classList.contains("hidden")) {
                renderKillOptions();
            }
        })
        .finally(function () {
            buttons.forEach(function (btn) {
                btn.disabled = false;
            });
            updateKillUI();
        });
}

function closeReportModal() {
    if (reportOverlay) {
        reportOverlay.classList.add("hidden");
    }
    if (reportFeedbackEl) {
        reportFeedbackEl.classList.add("hidden");
        reportFeedbackEl.textContent = "";
    }
}

function renderReportOptions() {
    if (!reportOptionsEl) {
        return;
    }
    reportOptionsEl.innerHTML = "";
    const bodies = Array.isArray(deadPlayersList) ? deadPlayersList : [];
    if (bodies.length === 0) {
        const p = document.createElement("p");
        p.classList.add("muted");
        p.textContent = "Nao existem jogadores eliminados.";
        reportOptionsEl.appendChild(p);
        return;
    }
    const hasReportable =
        Array.isArray(reportableBodies) && reportableBodies.some(function (body) {
            return body && !body.reported;
        });
    bodies.forEach(function (body) {
        const btn = document.createElement("button");
        btn.type = "button";
        const option = document.createElement("div");
        option.classList.add("vote-option", "with-cross");
        if (body.avatar) {
            const avatar = document.createElement("img");
            avatar.src = body.avatar;
            avatar.alt = body.name || "Jogador";
            avatar.classList.add("vote-avatar");
            option.appendChild(avatar);
        }
        const cross = document.createElement("span");
        cross.classList.add("cross-mark");
        cross.textContent = "X";
        option.appendChild(cross);
        const label = document.createElement("span");
        label.classList.add("vote-name");
        label.textContent = body.name || "Jogador";
        option.appendChild(label);
        const info = document.createElement("span");
        info.classList.add("muted");
        if (body.leftGame) {
            info.textContent = "Saiu do jogo";
        } else if (body.killedAt) {
            info.textContent = "Encontrado as " + formatTimeHM(body.killedAt);
        } else {
            info.textContent = "Eliminado";
        }
        option.appendChild(info);
        if (body.reported) {
            const tag = document.createElement("span");
            tag.classList.add("status-tag");
            tag.textContent = "Ja reportado";
            option.appendChild(tag);
            btn.disabled = true;
            btn.classList.add("disabled");
        }
        btn.appendChild(option);
        if (!btn.disabled) {
            btn.addEventListener("click", function () {
                submitReport(body.id);
            });
        }
        reportOptionsEl.appendChild(btn);
    });
    if (reportFeedbackEl) {
        if (!hasReportable) {
            reportFeedbackEl.textContent = "Todos os corpos ja foram reportados.";
            reportFeedbackEl.classList.remove("hidden");
        } else {
            reportFeedbackEl.textContent = "";
            reportFeedbackEl.classList.add("hidden");
        }
    }
}

function updateSabotageStatus() {
    if (!sabotageStatusEl) {
        return;
    }
    if (!isImpostor || currentStatus !== "in_game") {
        sabotageStatusEl.textContent = "";
        return;
    }
    if (commsActive) {
        sabotageStatusEl.textContent =
            "Comunicacoes voltam em " + Math.max(0, currentCommsRemaining) + "s";
    } else {
        sabotageStatusEl.textContent = "Comunicacoes disponiveis.";
    }
}

function stopCommsCountdown() {
    if (commsCountdownTimer) {
        clearInterval(commsCountdownTimer);
        commsCountdownTimer = null;
    }
}

function hideCommsOverlay() {
    stopCommsCountdown();
    commsActive = false;
    currentCommsRemaining = 0;
    if (commsOverlay) {
        commsOverlay.classList.add("hidden");
    }
    if (commsCountdownEl) {
        commsCountdownEl.textContent = "0";
    }
    updateSabotageStatus();
    updateKillUI();
}

function showCommsOverlay(remainingSeconds) {
    const seconds = Math.max(0, parseInt(remainingSeconds, 10) || 0);
    if (seconds <= 0) {
        hideCommsOverlay();
        return;
    }
    commsActive = true;
    currentCommsRemaining = seconds;
    if (commsCountdownEl) {
        commsCountdownEl.textContent = seconds;
    }
    if (commsOverlay) {
        commsOverlay.classList.remove("hidden");
    }
    stopCommsCountdown();
    commsCountdownTimer = setInterval(function () {
        currentCommsRemaining = Math.max(0, currentCommsRemaining - 1);
        if (commsCountdownEl) {
            commsCountdownEl.textContent = Math.max(0, currentCommsRemaining);
        }
        if (currentCommsRemaining <= 0) {
            hideCommsOverlay();
        }
    }, 1000);
    updateSabotageStatus();
    updateKillUI();
}

function renderMedicPanel(vitals) {
    if (!medicPanel || !medicVitalsEl) {
        return;
    }
    if (!isMedic || !Array.isArray(vitals) || vitals.length === 0) {
        medicPanel.classList.add("hidden");
        medicVitalsEl.innerHTML = "";
        return;
    }
    medicPanel.classList.remove("hidden");
    medicVitalsEl.innerHTML = "";
    vitals
        .slice()
        .sort(function (a, b) {
            const nameA = (a && a.name ? a.name : "").toLowerCase();
            const nameB = (b && b.name ? b.name : "").toLowerCase();
            return nameA.localeCompare(nameB);
        })
        .forEach(function (entry) {
            if (!entry) {
                return;
            }
            const li = document.createElement("li");
            li.classList.add("vital");
            if (entry.leftGame) {
                li.classList.add("left");
            } else if (entry.alive) {
                li.classList.add("alive");
            } else {
                li.classList.add("dead");
            }
            const nameSpan = document.createElement("span");
            nameSpan.classList.add("name");
            nameSpan.textContent = entry.name || "Jogador";
            li.appendChild(nameSpan);
            const stateSpan = document.createElement("span");
            stateSpan.classList.add("state");
            if (entry.leftGame) {
                stateSpan.textContent = "Saiu";
            } else if (entry.alive) {
                stateSpan.textContent = "Vivo";
            } else {
                stateSpan.textContent = "Morto";
            }
            li.appendChild(stateSpan);
            medicVitalsEl.appendChild(li);
        });
}

function openReportModal() {
    if (!reportOverlay) {
        return;
    }
    if (!Array.isArray(reportableBodies) || reportableBodies.length === 0) {
        alert("Nao ha corpos por reportar.");
        return;
    }
    renderReportOptions();
    reportOverlay.classList.remove("hidden");
}

function callEmergencyMeeting() {
    if (!emergencyBtn || emergencyBtn.disabled) {
        return;
    }
    if (!isAlive || currentStatus !== "in_game") {
        return;
    }
    emergencyBtn.disabled = true;
    fetch("/api/meeting/emergency", { method: "POST" })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data || !data.ok) {
                const msg = data && data.error ? data.error : "Nao foi possivel chamar reuniao.";
                throw new Error(msg);
            }
            fetchPlayer();
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
            emergencyBtn.disabled = false;
        });
}

function submitReport(bodyId) {
    if (!bodyId) {
        return;
    }
    const buttons = reportOptionsEl ? reportOptionsEl.querySelectorAll("button") : [];
    buttons.forEach(function (btn) {
        btn.disabled = true;
    });
    if (reportFeedbackEl) {
        reportFeedbackEl.classList.add("hidden");
        reportFeedbackEl.textContent = "";
    }
    fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bodyId: bodyId })
    })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data || !data.ok) {
                const msg = data && data.error ? data.error : "Nao foi possivel chamar reuniao.";
                throw new Error(msg);
            }
            closeReportModal();
            fetchPlayer();
        })
        .catch(function (error) {
            console.error(error);
            if (reportFeedbackEl) {
                reportFeedbackEl.textContent = error.message;
                reportFeedbackEl.classList.remove("hidden");
            } else {
                alert(error.message);
            }
        })
        .finally(function () {
            buttons.forEach(function (btn) {
                btn.disabled = false;
            });
        });
}

function showMeeting(meeting) {
    if (!meetingOverlay) {
        return;
    }
    if (meeting && meeting.id !== lastMeetingId) {
        lastMeetingId = meeting.id;
        if (meetingFeedbackEl) {
            meetingFeedbackEl.textContent = "";
        }
        stopVotingDelay();
    }
    currentMeetingData = meeting || null;
    meetingOverlay.classList.remove("hidden");
    renderMeetingOptions(meeting);
    renderMeetingDeceased(meeting);
    if (meeting && typeof meeting.votingStartsIn === "number") {
        startVotingDelay(meeting.votingStartsIn);
    } else {
        stopVotingDelay();
    }
    renderMeetingStatus(meeting);
    startMeetingCountdown(meeting ? meeting.endsIn || 0 : 0);
}

function hideMeeting() {
    if (!meetingOverlay) {
        return;
    }
    meetingOverlay.classList.add("hidden");
    if (meetingReporterEl) {
        meetingReporterEl.textContent = "";
        meetingReporterEl.classList.add("hidden");
    }
    stopMeetingCountdown();
    stopVotingDelay();
    lastMeetingId = null;
    currentMeetingData = null;
}

function describeSummary(summary) {
    if (!summary) {
        return "Reuniao concluida.";
    }
    const summaryType = summary.type;
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
        return summaryType === "emergency"
            ? "A reuniao de emergencia terminou em skip."
            : "A votacao terminou em skip.";
    }
    if (summary.outcome === "no_votes") {
        return summaryType === "emergency"
            ? "Reuniao de emergencia terminou sem votos."
            : "Ninguem votou nesta reuniao.";
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
                    if (data && typeof data.delay === "number") {
                        startVotingDelay(data.delay);
                        if (meetingFeedbackEl) {
                            meetingFeedbackEl.textContent =
                                (data.error || "Ainda nao podes votar.") + " (" + data.delay + "s)";
                        }
                        return;
                    }
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
    openReportModal();
}

function triggerKill() {
    if (!isImpostor || !isAlive || currentStatus !== "in_game" || !killBtn) {
        return;
    }
    openKillModal();
}

function triggerSabotage() {
    if (!isImpostor || !isAlive || currentStatus !== "in_game" || !sabotageBtn) {
        return;
    }
    sabotageBtn.disabled = true;
    fetch("/api/impostor/sabotage", { method: "POST" })
        .then(parseJsonSafe)
        .then(function (data) {
            if (!data || !data.ok) {
                const msg = data && data.error ? data.error : "Nao podes sabotar agora.";
                throw new Error(msg);
            }
            fetchPlayer();
        })
        .catch(function (error) {
            console.error(error);
            alert(error.message);
        })
        .finally(function () {
            updateKillUI();
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
                hideCommsOverlay();
                window.location.href = "/lobby";
                return;
            }

            const role = data.role || "crewmate";
            specialRole = data.specialRole || null;
            isMedic = specialRole === "medic";
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
                roleNameEl.textContent = translateRole(role, specialRole);
            }
            if (roleCardEl) {
                roleCardEl.classList.toggle("crewmate", role === "crewmate");
                roleCardEl.classList.toggle("impostor", role === "impostor");
                roleCardEl.classList.toggle("leader", isLeader);
            }
            if (roleHintEl) {
                roleHintEl.textContent = roleHint(role, specialRole);
            }

            if (isImpostor && !impostorRevealShown && currentStatus !== "lobby") {
                impostorRevealShown = true;
                playImpostorReveal();
            }

            renderTasks(data.tasks || {});
            renderMedicPanel(isMedic ? data.vitals : null);

            killTargets = Array.isArray(data.killTargets) ? data.killTargets : [];
            if (!isImpostor) {
                killTargets = [];
            }
            deadPlayersList = Array.isArray(data.deadPlayers) ? data.deadPlayers : [];
            reportableBodies = deadPlayersList.filter(function (body) {
                return body && !body.reported;
            });

            if (deathNoteEl) {
                if (data.deathNote) {
                    deathNoteEl.textContent = data.deathNote;
                    deathNoteEl.classList.remove("hidden");
                } else {
                    deathNoteEl.textContent = "";
                    deathNoteEl.classList.add("hidden");
                }
            }
            if (roleCardEl) {
                roleCardEl.classList.toggle("dead", !isAlive);
            }

            const commsData = data.commsSabotage || {};
            if (
                commsData &&
                commsData.active &&
                typeof commsData.remaining === "number" &&
                commsData.remaining > 0
            ) {
                showCommsOverlay(commsData.remaining);
            } else {
                hideCommsOverlay();
            }

            const killValue =
                typeof data.killRemaining === "number"
                    ? data.killRemaining
                    : parseInt(data.killRemaining, 10);
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

            const cannotReport =
                !isAlive || data.status !== "in_game" || !!data.meeting || !!data.gameOver;
            if (reportBtn) {
                reportBtn.disabled = cannotReport || commsActive;
            }
            if (emergencyBtn) {
                const inGame = currentStatus === "in_game";
                emergencyBtn.classList.toggle("hidden", !inGame);
                const canEmergency =
                    inGame &&
                    data.emergencyAvailable &&
                    isAlive &&
                    !data.meeting &&
                    !data.gameOver &&
                    !commsActive;
                emergencyBtn.textContent = data.emergencyAvailable
                    ? "Chamar reuniao"
                    : "Reuniao usada";
                emergencyBtn.disabled = !canEmergency;
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
    if (sabotageBtn) {
        sabotageBtn.addEventListener("click", triggerSabotage);
    }
    if (reportBtn) {
        reportBtn.addEventListener("click", reportBody);
    }
    if (emergencyBtn) {
        emergencyBtn.addEventListener("click", callEmergencyMeeting);
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
