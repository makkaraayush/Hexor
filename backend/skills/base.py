from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseSkill(ABC):
    """Base interface for all Hexor built-in and dynamic skills."""
    name: str = "base_skill"
    description: str = "Base skill description"
    parameters: Dict[str, Any] = {}
    category: str = "general" # "pc_control", "bambu_3d", "spotify", "web", "system", "custom"

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute skill logic.
        Returns:
            {
                "success": bool,
                "message": str,
                "data": Any,
                "ui_action": Optional[str], # e.g. "show_3d_approval", "spotify_update", "render_intel"
                "requires_approval": bool
            }
        """
        pass

