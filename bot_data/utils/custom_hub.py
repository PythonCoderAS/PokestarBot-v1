import datetime
from typing import Any, Dict, Optional, overload

import sentry_sdk._types


class CustomHub(sentry_sdk.Hub):

    @overload
    def add_breadcrumb(self, crumb: Dict[str, Any], hint: Optional[Dict[str, Any]] = None, **kwargs: Any):
        pass

    @overload
    def add_breadcrumb(self, *, crumb_type: str = "default", category: Optional[str] = None, message: str, level: str = "info",
                       timestamp: Optional[datetime.datetime] = None, data: Optional[Dict[str, Any]] = None):
        pass

    def add_breadcrumb(self, crumb: Optional[Dict[str, Any]] = None, hint: Optional[Dict[str, Any]] = None,
                       **kwargs: Any) -> None:
        super().add_breadcrumb(crumb, hint, **kwargs)
