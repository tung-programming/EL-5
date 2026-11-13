document.addEventListener("DOMContentLoaded", () => {
	const checkStepForm = document.getElementById("check-step-form");
	const explorerForm = document.getElementById("explorer-form");
	const previousInput = document.getElementById("previous-equation");
	const currentInput = document.getElementById("current-equation");
	const expressionInput = document.getElementById("expression-input");
	const exploreButton = document.getElementById("explore-button");
	const resultStatus = document.getElementById("result-status");
	const resultAnnouncement = document.getElementById("result-announcement");
	const resultJson = document.getElementById("result-json");
	const repeatButton = document.getElementById("repeat-result");
	const detailButton = document.getElementById("more-detail");
	const stopButton = document.getElementById("stop-speech");
	const speechRate = document.getElementById("speech-rate");
	const speechRateValue = document.getElementById("speech-rate-value");
	const explorerContainer = document.getElementById("explorer");
	const explorerStatus = document.getElementById("explorer-status");
	const explorerLive = document.getElementById("explorer-live");
	const helpPanel = document.getElementById("explorer-help");
	const newProblemButton = document.getElementById("new-problem");
	const historyList = document.getElementById("step-history-list");
	const historyEmpty = document.getElementById("history-empty");

	let explorerView = null;
	let explorerTree = null;
	let explorerNodes = new Map();
	let latestAnnouncement = "";
	let latestDetail = "";
	let latestAnnouncementTarget = "result";
	let explorerRequest = 0;
	// The correct steps of the current problem, oldest first: {equation, note}.
	let stepHistory = [];

	function rememberAnnouncement(text, target) {
		if (!text) return;
		latestAnnouncement = text;
		latestAnnouncementTarget = target;
		repeatButton.disabled = false;
	}

	function indexExplorerNodes(root) {
		const nodes = new Map();
		if (!root) return nodes;
		const pending = [root];
		while (pending.length) {
			const node = pending.pop();
			nodes.set(node.id, node);
			(node.children || []).forEach((child) => pending.push(child));
		}
		return nodes;
	}

	function announcementMode() {
		return document.querySelector('input[name="announcement-mode"]:checked').value;
	}

	function speechAvailable() {
		return "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function";
	}

	function cancelSpeech() {
		if (speechAvailable()) window.speechSynthesis.cancel();
	}

	function speak(text) {
		if (!text || !speechAvailable()) return;
		rememberAnnouncement(text, "explorer");
		const utterance = new window.SpeechSynthesisUtterance(text);
		utterance.rate = Number(speechRate.value);
		window.speechSynthesis.speak(utterance);
	}

	function writeLive(region, text) {
		if (!region || !text) return;
		region.textContent = "";
		window.setTimeout(() => {
			region.textContent = text;
		}, 40);
	}

	function announceResult(text) {
		if (!text) return;
		rememberAnnouncement(text, "result");
		if (announcementMode() === "speech") {
			cancelSpeech();
			speak(text);
			rememberAnnouncement(text, "result");
		} else {
			writeLive(resultAnnouncement, text);
		}
	}

	function updateAnnouncementMode() {
		const screenReaderMode = announcementMode() === "screen-reader";
		resultAnnouncement.setAttribute("aria-live", screenReaderMode ? "polite" : "off");
		explorerLive.setAttribute("aria-live", screenReaderMode ? "polite" : "off");
		const speechControlsEnabled = !screenReaderMode && speechAvailable();
		speechRate.disabled = !speechControlsEnabled;
		stopButton.disabled = !speechControlsEnabled;
		if (!screenReaderMode && !speechAvailable()) {
			document.querySelector('input[name="announcement-mode"][value="screen-reader"]').checked = true;
			resultAnnouncement.setAttribute("aria-live", "polite");
			explorerLive.setAttribute("aria-live", "polite");
			explorerStatus.textContent = "Browser speech is unavailable. Screen-reader announcements remain selected.";
			return;
		}
		cancelSpeech();
		if (explorerTree && !explorerContainer.hidden) renderExplorer(explorerTree);
	}

	function setStatus(status, message) {
		resultStatus.dataset.status = status;
		resultStatus.textContent = message;
	}

	function setExplorerStatus(status, message) {
		explorerStatus.dataset.status = status;
		explorerStatus.textContent = message;
	}

	async function fetchJson(url, payload) {
		const response = await fetch(url, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});

		let data;
		try {
			data = await response.json();
		} catch {
			throw new Error("The server returned an unreadable response.");
		}
		if (!response.ok) {
			throw new Error(data.detail || "Request failed.");
		}
		return data;
	}

	function renderExplorer(tree) {
		if (explorerView) explorerView.destroy();
		explorerNodes = indexExplorerNodes(tree);
		explorerContainer.hidden = false;
		explorerView = window.ExplorerKeys.createView(explorerContainer, tree, {
			onExit: () => {
				explorerContainer.hidden = true;
				exploreButton.focus();
			},
			document: window.document,
			liveRegion: explorerLive,
			helpPanel,
			mode: announcementMode() === "speech" ? "speech" : "screen-reader",
			speak,
			cancelSpeech,
			schedule: (fn) => window.setTimeout(fn, 25),
		});
		decorateExplorer();
		const opened = explorerView.open();
		if (!opened.focused) {
			throw new Error("The browser could not move focus into the explorer.");
		}
	}

	function clearExplorer() {
		cancelSpeech();
		if (explorerView) explorerView.destroy();
		explorerView = null;
		explorerTree = null;
		explorerNodes.clear();
		explorerContainer.replaceChildren();
		explorerContainer.hidden = true;
		helpPanel.hidden = true;
		if (latestAnnouncementTarget === "explorer") {
			latestAnnouncement = "";
			repeatButton.disabled = true;
			latestDetail = "";
			detailButton.disabled = true;
		}
	}

	function announceExplorerMessage(text) {
		rememberAnnouncement(text, "explorer");
		if (announcementMode() === "speech") {
			cancelSpeech();
			speak(text);
		} else {
			writeLive(explorerLive, text);
		}
	}

	function sameEquation(a, b) {
		return a.replace(/\s+/g, "").toLowerCase() === b.replace(/\s+/g, "").toLowerCase();
	}

	// "x = 3", "x = -2.5", "x = 8/3" or the same with the sides swapped.
	function isSolved(text) {
		const compact = text.replace(/\s+/g, "").toLowerCase();
		const value = "[+-]?\\d+(?:\\.\\d+)?(?:/\\d+)?";
		return new RegExp(`^x=${value}$`).test(compact) || new RegExp(`^${value}=x$`).test(compact);
	}

	function renderHistory() {
		historyList.replaceChildren();
		stepHistory.forEach((step, index) => {
			const item = document.createElement("li");
			const equation = document.createElement("span");
			equation.className = "step-equation";
			equation.textContent = step.equation;
			const note = document.createElement("span");
			note.className = "step-note";
			note.textContent = index === 0 ? "Starting equation" : step.note;
			item.append(equation, note);
			historyList.appendChild(item);
		});
		historyEmpty.hidden = stepHistory.length > 0;
	}

	function recordCorrectStep(previousText, currentText, note) {
		const last = stepHistory[stepHistory.length - 1];
		// A new or edited previous equation starts a new problem.
		if (!last || !sameEquation(last.equation, previousText)) {
			stepHistory = [{ equation: previousText, note: "" }];
		}
		stepHistory.push({ equation: currentText, note });
		renderHistory();
	}

	function startNewProblem() {
		cancelSpeech();
		stepHistory = [];
		renderHistory();
		previousInput.value = "";
		currentInput.value = "";
		resultJson.textContent = "";
		latestDetail = "";
		detailButton.disabled = true;
		setStatus("idle", "New problem. Type the starting equation, then your first step.");
		previousInput.focus();
		announceResult("New problem. Type the starting equation, then your first step.");
	}

	function focusAndSelect(input) {
		input.focus();
		input.select();
	}

	function showResult(data, previousText, currentText) {
		const concise = data.explanation?.concise || `The step is ${data.status}.`;
		let message = concise;

		// Move focus before announcing: focusing an input cancels page speech.
		if (data.status === "valid") {
			recordCorrectStep(previousText, currentText, concise);
			previousInput.value = currentText;
			currentInput.value = "";
			if (isSolved(currentText)) {
				message = `${concise} You solved it: ${currentText}. Select Start a new problem to try another one.`;
				newProblemButton.focus();
			} else {
				message = `${concise} Now type the step after ${currentText}.`;
				currentInput.focus();
			}
		} else if (data.status === "invalid") {
			message = `${concise} Try this step again.`;
			focusAndSelect(currentInput);
		} else {
			message = `${concise} You can change the step and check it again.`;
			focusAndSelect(currentInput);
		}

		setStatus(data.status, `${data.status.toUpperCase()}: ${message}`);
		resultJson.textContent = JSON.stringify(data, null, 2);
		latestDetail = data.explanation?.detailed || concise;
		repeatButton.disabled = !latestAnnouncement && !concise;
		detailButton.disabled = !latestDetail;
		announceResult(message);
	}

	// Visual-only maths for the explorer tree. Screen readers keep using each
	// item's aria-label, so this is aria-hidden.
	function mathText(node) {
		if (!node) return "";
		const kids = node.children || [];
		const [a, b] = kids;
		switch (node.type) {
			case "Number":
				return String(node.value ?? "");
			case "Variable":
				return String(node.value || "x");
			case "Group":
				return `(${mathText(a)})`;
			case "Neg":
				return `\u2212${mathText(a)}`;
			case "Equation":
				return `${mathText(a)} = ${mathText(b)}`;
			case "Add":
				return `${mathText(a)} + ${mathText(b)}`;
			case "Sub":
				return `${mathText(a)} \u2212 ${mathText(b)}`;
			case "Div":
				return `${mathText(a)} / ${mathText(b)}`;
			case "Pow":
				return `${mathText(a)}^${mathText(b)}`;
			case "Mul": {
				const numberLike = a && (a.type === "Number" || (a.type === "Neg" && a.children?.[0]?.type === "Number"));
				const joins = b && ["Variable", "Group", "Pow"].includes(b.type);
				return numberLike && joins ? `${mathText(a)}${mathText(b)}` : `${mathText(a)} \u00d7 ${mathText(b)}`;
			}
			default:
				return node.value != null ? String(node.value) : "";
		}
	}

	function decorateExplorer() {
		explorerContainer.querySelectorAll('[role="treeitem"][data-node-id]').forEach((item) => {
			const node = explorerNodes.get(item.getAttribute("data-node-id"));
			const label = item.firstElementChild;
			if (!node || !label || label.tagName !== "SPAN") return;
			const row = document.createElement("span");
			row.className = "node-row";
			item.insertBefore(row, label);
			label.className = "node-name";
			row.appendChild(label);
			// Leaves like "Constant term 3" already show their value in the name.
			const symbols = mathText(node);
			if (symbols && ((node.children || []).length || !label.textContent.includes(symbols))) {
				const math = document.createElement("span");
				math.className = "node-math";
				math.setAttribute("aria-hidden", "true");
				math.textContent = symbols;
				row.appendChild(math);
			}
		});
	}

	function repeatLastAnnouncement() {
		if (!latestAnnouncement) return;
		if (announcementMode() === "speech") {
			cancelSpeech();
			const text = latestAnnouncement;
			const target = latestAnnouncementTarget;
			speak(text);
			rememberAnnouncement(text, target);
			return;
		}
		const region = latestAnnouncementTarget === "explorer" ? explorerLive : resultAnnouncement;
		writeLive(region, latestAnnouncement);
	}

	function selectedNodeFocused(event) {
		const item = event.target && event.target.closest
			? event.target.closest('[role="treeitem"][data-node-id]')
			: null;
		if (!item) return;
		const node = explorerNodes.get(item.getAttribute("data-node-id"));
		if (!node) return;
		rememberAnnouncement(node.spoken_quick || node.role || "Equation part", "explorer");
		latestDetail = node.spoken_detailed || "";
		detailButton.disabled = !latestDetail;
	}

	checkStepForm.addEventListener("submit", async (event) => {
		event.preventDefault();

		const previousText = previousInput.value.trim();
		const currentText = currentInput.value.trim();
		if (!previousText || !currentText) {
			const missing = previousText ? currentInput : previousInput;
			const message = previousText ? "Type your next step first." : "Type the previous equation first.";
			setStatus("error", message);
			missing.focus();
			announceResult(message);
			return;
		}
		const payload = {
			previous_equation: previousText,
			current_equation: currentText,
		};
		const submitButton = checkStepForm.querySelector('button[type="submit"]');
		submitButton.disabled = true;

		try {
			cancelSpeech();
			setStatus("unknown", "Checking the step…");
			resultJson.textContent = "";
			const data = await fetchJson("/api/check-step", payload);
			showResult(data, previousText, currentText);
		} catch (error) {
			setStatus("error", `Could not check the step: ${error.message}`);
			resultJson.textContent = JSON.stringify({ error: error.message }, null, 2);
			latestDetail = "";
			focusAndSelect(/previous/i.test(error.message) ? previousInput : currentInput);
			announceResult(`Could not check the step. ${error.message}`);
		} finally {
			submitButton.disabled = false;
		}
	});

	explorerForm.addEventListener("submit", async (event) => {
		event.preventDefault();
		const requestId = ++explorerRequest;
		clearExplorer();
		setExplorerStatus("loading", "Parsing expression…");
		exploreButton.disabled = true;

		try {
			const payload = { expression: expressionInput.value };
			const tree = await fetchJson("/api/parse-expression", payload);
			if (requestId !== explorerRequest) return;
			explorerTree = tree;
			setExplorerStatus("success", "Expression parsed. Explorer is ready.");
			renderExplorer(tree);
		} catch (error) {
			if (requestId !== explorerRequest) return;
			setExplorerStatus("error", `Could not explore this expression: ${error.message}`);
			announceExplorerMessage(`Could not explore this expression. ${error.message}`);
		} finally {
			if (requestId === explorerRequest) exploreButton.disabled = false;
		}
	});

	document.querySelectorAll('input[name="announcement-mode"]').forEach((input) => {
		input.addEventListener("change", updateAnnouncementMode);
	});

	repeatButton.addEventListener("click", repeatLastAnnouncement);
	newProblemButton.addEventListener("click", startNewProblem);

	// Enter in the previous equation moves on to the step box while it is empty.
	previousInput.addEventListener("keydown", (event) => {
		if (event.key === "Enter" && !currentInput.value.trim()) {
			event.preventDefault();
			currentInput.focus();
		}
	});

	detailButton.addEventListener("click", () => {
		if (!latestDetail) return;
		if (explorerView && !explorerContainer.hidden) announceExplorerMessage(latestDetail);
		else announceResult(latestDetail);
	});

	stopButton.addEventListener("click", cancelSpeech);

	speechRate.addEventListener("input", () => {
		speechRateValue.value = `${speechRate.value}x`;
		speechRateValue.textContent = `${speechRate.value}x`;
	});

	[previousInput, currentInput, expressionInput].forEach((input) => {
		input.addEventListener("focus", cancelSpeech);
	});

	explorerContainer.addEventListener("focusin", selectedNodeFocused);
	new window.MutationObserver(() => {
		const text = explorerLive.textContent.trim();
		if (text) rememberAnnouncement(text, "explorer");
	}).observe(explorerLive, { childList: true, characterData: true, subtree: true });

	updateAnnouncementMode();
});
