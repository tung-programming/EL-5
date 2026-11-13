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

	let explorerView = null;
	let explorerTree = null;
	let explorerNodes = new Map();
	let latestAnnouncement = "";
	let latestDetail = "";
	let latestAnnouncementTarget = "result";
	let explorerRequest = 0;

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

	function showResult(data) {
		const concise = data.explanation?.concise || `The step is ${data.status}.`;
		setStatus(data.status, `${data.status.toUpperCase()}: ${concise}`);
		resultJson.textContent = JSON.stringify(data, null, 2);
		latestDetail = data.explanation?.detailed || concise;
		repeatButton.disabled = !latestAnnouncement && !concise;
		detailButton.disabled = !latestDetail;
		announceResult(concise);
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

		const payload = {
			previous_equation: previousInput.value,
			current_equation: currentInput.value,
		};
		const submitButton = checkStepForm.querySelector('button[type="submit"]');
		submitButton.disabled = true;

		try {
			cancelSpeech();
			setStatus("unknown", "Checking the step…");
			resultJson.textContent = "";
			const data = await fetchJson("/api/check-step", payload);
			showResult(data);
		} catch (error) {
			setStatus("error", `Could not check the step: ${error.message}`);
			resultJson.textContent = JSON.stringify({ error: error.message }, null, 2);
			latestDetail = "";
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
