# ==================================================
# PROJECT OCTOPUS — UNIVERSAL CONNECTOR INTERFACE
# ==================================================

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """
    Common interface for all Project Octopus
    data connectors.

    Every connector must support:
        1. Connection
        2. Connection testing
        3. Data discovery
        4. Data extraction
        5. Closing the connection
    """

    def __init__(self, config: dict):
        self.config = config
        self.connected = False

    # --------------------------------------------------
    # CONNECT
    # --------------------------------------------------

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the source."""
        pass

    # --------------------------------------------------
    # TEST CONNECTION
    # --------------------------------------------------

    @abstractmethod
    def test_connection(self) -> bool:
        """Check whether the source is reachable."""
        pass

    # --------------------------------------------------
    # DISCOVER DATA
    # --------------------------------------------------

    @abstractmethod
    def discover(self) -> Any:
        """
        Discover available tables, files, sheets,
        endpoints, datasets, or other source objects.
        """
        pass

    # --------------------------------------------------
    # EXTRACT DATA
    # --------------------------------------------------

    @abstractmethod
    def extract(self, target: Any = None) -> Any:
        """Extract selected data from the source."""
        pass

    # --------------------------------------------------
    # SOURCE INFORMATION
    # --------------------------------------------------

    def get_source_info(self) -> dict:
        """Return basic connector information."""

        return {
            "connector": self.__class__.__name__,
            "connected": self.connected
        }

    # --------------------------------------------------
    # CLOSE CONNECTION
    # --------------------------------------------------

    def close(self) -> None:
        """Close the source connection."""

        self.connected = False