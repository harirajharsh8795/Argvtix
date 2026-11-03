"""Target adapters for Scout chatbot security audits."""

from argvtix.scout.adapters.base import BaseTargetAdapter
from argvtix.scout.adapters.http import HTTPChatAdapter
from argvtix.scout.adapters.web_widget import PlaywrightWidgetAdapter

__all__ = [
    "BaseTargetAdapter",
    "HTTPChatAdapter",
    "PlaywrightWidgetAdapter",
]
