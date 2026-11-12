document.addEventListener("DOMContentLoaded", () => {
	const checkStepForm = document.getElementById("check-step-form");
	const explorerForm = document.getElementById("explorer-form");
	const previousInput = document.getElementById("previous-equation");
	const currentInput = document.getElementById("current-equation");
	const expressionInput = document.getElementById("expression-input");
	const resultStatus = document.getElementById("result-status");
	const resultJson = document.getElementById("result-json");
	const explorerContainer = document.getElementById("explorer");
	const explorerLive = document.getElementById("explorer-live");
	const helpPanel = document.getElementById("explorer-help");

	let explorerView = null;

	function announce(text) {
		if (!text) return;
		if (explorerLive) {
			explorerLive.textContent = "";
			window.setTimeout(() => {
				explorerLive.textContent = text;
			}, 40);
		}
		if ("speechSynthesis" in window) {
			const utterance = new SpeechSynthesisUtterance(text);
			window.speechSynthesis.cancel();
			window.speechSynthesis.speak(utterance);
		}
	}

	function setStatus(status, message) {
		resultStatus.dataset.status = status;
		resultStatus.textContent = message;
	}

	async function fetchJson(url, payload) {
		const response = await fetch(url, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});

		const data = await response.json();
		if (!response.ok) {
			throw new Error(data.detail || "Request failed.");
		}
		return data;
	}

	checkStepForm.addEventListener("submit", async (event) => {
		event.preventDefault();

		const payload = {
			previous_equation: previousInput.value,
			current_equation: currentInput.value,
		};

		try {
			setStatus("unknown", "Checking the step…");
			const data = await fetchJson("/api/check-step", payload);
			setStatus(data.status, `${data.status.toUpperCase()}: ${data.explanation.concise}`);
			resultJson.textContent = JSON.stringify(data, null, 2);
			announce(data.explanation.concise);
		} catch (error) {
			setStatus("invalid", `Could not check the step: ${error.message}`);
			resultJson.textContent = JSON.stringify({ error: error.message }, null, 2);
			announce(error.message);
		}
	});

	explorerForm.addEventListener("submit", async (event) => {
		event.preventDefault();

		try {
			const payload = { expression: expressionInput.value };
			const tree = await fetchJson("/api/parse-expression", payload);

			if (window.ExplorerKeys && typeof window.ExplorerKeys.createView === "function") {
				if (explorerView) {
					explorerView.destroy();
				}

				explorerView = window.ExplorerKeys.createView(explorerContainer, tree, {
					onExit: () => {
						expressionInput.focus();
					},
					document: window.document,
					liveRegion: explorerLive,
					helpPanel: helpPanel,
					mode: "screen-reader",
					speak: (text) => announce(text),
					cancelSpeech: () => {
						if ("speechSynthesis" in window) {
							window.speechSynthesis.cancel();
						}
					},
					schedule: (fn) => window.setTimeout(fn, 25),
				});
				explorerView.open();
				announce(explorerView.controller.openAnnouncement());
			} else {
				explorerContainer.textContent = JSON.stringify(tree, null, 2);
			}
		} catch (error) {
			explorerContainer.textContent = `Could not build the explorer: ${error.message}`;
			announce(error.message);
		}
	});

	if (expressionInput && expressionInput.value) {
		explorerForm.requestSubmit();
	}
});
