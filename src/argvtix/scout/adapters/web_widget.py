"""Playwright Web-Widget Target Adapter for Scout auditing."""

from __future__ import annotations

import logging
from typing import Any

from argvtix.scout.adapters.base import BaseTargetAdapter
from argvtix.scout.safety import ScoutSafetyController
from argvtix.scout.scope import ScopeConfig

logger = logging.getLogger("argvtix.scout.adapters.web_widget")


class PlaywrightWidgetAdapter(BaseTargetAdapter):
    """Adapter for auditing live web chatbot widgets using Playwright."""

    def __init__(
        self,
        scope: ScopeConfig,
        safety_controller: ScoutSafetyController | None = None,
        auto_send_email: bool = False,
        widget_url: str | None = None,
        input_selector: str = "textarea, input[type='text'], [contenteditable='true']",
        send_button_selector: str = "button[type='submit'], button:has-text('Send'), .send-btn",
        response_selector: str = ".message.assistant, [data-role='assistant'], .bot-message",
        timeout_sec: float = 15.0,
        browser_page: Any | None = None,
    ) -> None:
        super().__init__(scope, safety_controller, auto_send_email)
        self.widget_url = widget_url or scope.target_url
        self.input_selector = input_selector
        self.send_button_selector = send_button_selector
        self.response_selector = response_selector
        self.timeout_sec = timeout_sec
        self.page = browser_page
        self._owns_browser = False
        self._browser = None
        self._playwright = None

    def _ensure_page(self) -> Any:
        if self.page is not None:
            return self.page

        # Lazy initialize Playwright if not injected
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import]

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self.page = self._browser.new_page()
            self._owns_browser = True
            self.page.goto(self.widget_url, timeout=int(self.timeout_sec * 1000))
            return self.page
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Install via 'pip install playwright' and 'playwright install chromium'."
            ) from exc

    def send_message(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        """Sends a message to the web chatbot widget via browser automation."""
        # 1. Runtime Egress Check: refuse any request to a host outside scope allowlists
        self.validate_egress(self.widget_url)

        # 2. Safety Preflight Check: verify kill switch, circuit breaker, conversation bounds
        current_turns = len(history or []) // 2
        self.safety.check_safety_preflight(current_conversation_turns=current_turns)

        # 3. Rate Limit Enforcement: acquire slot from token bucket rate limiter
        self.safety.acquire_request_slot(timeout_sec=self.timeout_sec)

        try:
            page = self._ensure_page()

            # Record baseline response count before sending message
            previous_count = page.locator(self.response_selector).count()

            # Focus and fill the input field
            page.fill(self.input_selector, message)

            # Click send button (fallback to pressing Enter)
            send_btn = page.locator(self.send_button_selector)
            if send_btn.count() > 0 and send_btn.first.is_visible():
                send_btn.first.click()
            else:
                page.press(self.input_selector, "Enter")

            # Wait for assistant response count to increment or element to update
            page.wait_for_function(
                f"document.querySelectorAll('{self.response_selector}').length > {previous_count}",
                timeout=int(self.timeout_sec * 1000),
            )

            # Retrieve text of latest assistant response
            responses = page.locator(self.response_selector)
            last_index = responses.count() - 1
            latest_text = responses.nth(last_index).inner_text().strip()

            self.safety.record_response(200)
            return latest_text

        except Exception as exc:
            self.safety.record_response(500)
            logger.error("Error during Playwright widget interaction: %s", exc)
            raise RuntimeError(f"Web widget interaction error: {exc}") from exc

    def close(self) -> None:
        """Closes browser resources if owned."""
        if self._owns_browser:
            try:
                if self.page:
                    self.page.close()
                if self._browser:
                    self._browser.close()
                if self._playwright:
                    self._playwright.stop()
            except Exception:
                pass
            finally:
                self.page = None
                self._browser = None
                self._playwright = None
