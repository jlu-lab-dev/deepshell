# tool_router.py
# LLM-based two-stage tool routing for ReAct Agent.
# Stage 1: Expert routing (pick relevant experts)
# Stage 2: Tool selection  (pick specific tools from selected experts)

import json
import logging
import os
import re
import uuid
import importlib
from typing import Any

from config.config_manager import ConfigManager
from chat.model_manager import ModelManager


class ToolRouter:
    """
    Two-stage LLM tool router.

    Caches all expert definitions and tool schemas at __init__ time.
    Each workflow call goes through:
      route_experts()  → select_tools()  → get_filtered_*(...)
    Fallback on any error to the full tool set so the user is never blocked.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._experts: list[dict] = []
        self._schemas_by_expert: dict[str, list[dict]] = {}
        self._all_schemas: list[dict] = []
        self._all_func_map: dict[str, callable] = {}

        self._model_manager = ModelManager()
        self._config = ConfigManager()
        self._load_static_data()

    # ─── Static data loading (once per instance) ───────────────────────────

    def _load_static_data(self):
        """Load experts.json and all tool JSON files; cache on self."""
        base = os.path.dirname(__file__)

        # Load experts
        with open(os.path.join(base, "experts.json"), encoding="utf-8") as f:
            self._experts = json.load(f)

        # Load each expert's schema file + implementation module
        for expert in self._experts:
            name = expert["name"]
            self._schemas_by_expert[name] = []

            if expert.get("tools_definition_file"):
                def_path = os.path.join(base, expert["tools_definition_file"])
                with open(def_path, encoding="utf-8") as f:
                    schemas = json.load(f)
                    self._schemas_by_expert[name] = schemas
                    self._all_schemas.extend(schemas)

            if expert.get("tools_implementation_module"):
                mod = importlib.import_module(expert["tools_implementation_module"])
                if hasattr(mod, "FUNCTION_MAP"):
                    self._all_func_map.update(mod.FUNCTION_MAP)

        logging.info(
            f"[ToolRouter] Loaded {len(self._experts)} experts, "
            f"{len(self._all_schemas)} total tools."
        )

    # ─── Public API ────────────────────────────────────────────────────────

    def route_experts(self, user_input: str) -> list[str]:
        """
        Stage 1 – Expert Routing.
        Ask the LLM to return a JSON array of expert names relevant to user_input.
        Falls back to all experts (except general_fallback_expert) on any error.
        """
        try:
            config = self._config.get_assistant_config("tool_expert_router")
            if not config:
                logging.warning(
                    "[ToolRouter] 'tool_expert_router' config missing, "
                    "using fallback."
                )
                return self._fallback_expert_names()

            prompt = self._build_expert_prompt(user_input, config)
            # Random session_id: never written to conversation_repo history
            session = f"router_expert_{uuid.uuid4().hex[:12]}"
            response = self._model_manager.chat(
                model_name=self.model_name,
                messages=[user_input],
                system_prompt=prompt,
                session_id=session,
            )
            expert_names = self._parse_expert_names(response)
            if not expert_names:
                return self._fallback_expert_names()
            logging.info(f"[ToolRouter] Routed experts: {expert_names}")
            return expert_names

        except Exception as e:
            logging.error(
                f"[ToolRouter] Expert routing failed: {e}", exc_info=True
            )
            return self._fallback_expert_names()

    def select_tools(
        self,
        user_input: str,
        expert_names: list[str],
    ) -> list[str]:
        """
        Stage 2 – Tool Selection.
        Ask the LLM to return a JSON array of tool names from the given experts.
        Falls back to all tools from those experts on any error.
        """
        try:
            config = self._config.get_assistant_config("tool_selector")
            if not config:
                logging.warning(
                    "[ToolRouter] 'tool_selector' config missing, "
                    "using fallback."
                )
                return self._fallback_tool_names(expert_names)

            prompt = self._build_tool_prompt(user_input, expert_names, config)
            session = f"router_tool_{uuid.uuid4().hex[:12]}"
            response = self._model_manager.chat(
                model_name=self.model_name,
                messages=[user_input],
                system_prompt=prompt,
                session_id=session,
            )
            tool_names = self._parse_tool_names(response)
            if not tool_names:
                return self._fallback_tool_names(expert_names)
            logging.info(f"[ToolRouter] Selected tools: {tool_names}")
            return tool_names

        except Exception as e:
            logging.error(
                f"[ToolRouter] Tool selection failed: {e}", exc_info=True
            )
            return self._fallback_tool_names(expert_names)

    def get_filtered_schemas(self, tool_names: list[str]) -> list[dict]:
        """Return full schemas for the given tool names, preserving original order."""
        name_set = set(tool_names)
        return [s for s in self._all_schemas if s.get("name") in name_set]

    def get_filtered_func_map(self, tool_names: list[str]) -> dict[str, callable]:
        """Return the function map filtered to the given tool names."""
        name_set = set(tool_names)
        return {k: v for k, v in self._all_func_map.items() if k in name_set}

    # ─── Fallbacks ─────────────────────────────────────────────────────────

    def _fallback_expert_names(self) -> list[str]:
        """Return all expert names except general_fallback_expert."""
        return [
            e["name"] for e in self._experts
            if e["name"] != "general_fallback_expert"
        ]

    def _fallback_tool_names(self, expert_names: list[str]) -> list[str]:
        """Return all tool names from the given experts."""
        names = []
        for en in expert_names:
            for schema in self._schemas_by_expert.get(en, []):
                if (n := schema.get("name")):
                    names.append(n)
        return names

    # ─── Prompt building ───────────────────────────────────────────────────

    def _build_expert_prompt(self, user_input: str, config: dict) -> str:
        """Build Stage-1 system prompt, injecting expert list into {expert_list}."""
        expert_lines = []
        for e in self._experts:
            tag = (
                " [闲聊/通用，仅当问题无需工具时使用]"
                if e["name"] == "general_fallback_expert"
                else ""
            )
            expert_lines.append(f"- **{e['name']}**{tag}: {e['description']}")

        expert_list_block = "\n".join(expert_lines)
        template = config.get("prompt_template", "")
        return template.replace("{expert_list}", expert_list_block)

    def _build_tool_prompt(
        self, user_input: str, expert_names: list[str], config: dict,
    ) -> str:
        """Build Stage-2 system prompt, injecting tool briefs into {tool_briefs}."""
        tool_lines = []
        for en in expert_names:
            for schema in self._schemas_by_expert.get(en, []):
                name = schema.get("name", "")
                desc = schema.get("description", "")
                tool_lines.append(f"- {name}: {desc}")

        tool_briefs_block = "\n".join(tool_lines) if tool_lines else "(无工具)"

        template = config.get("prompt_template", "")
        return template.replace("{tool_briefs}", tool_briefs_block)

    # ─── Response parsing ───────────────────────────────────────────────────

    def _parse_expert_names(self, response: str) -> list[str]:
        """Extract expert name strings from LLM response."""
        valid = {e["name"] for e in self._experts}
        return self._parse_json_list(response, valid)

    def _parse_tool_names(self, response: str) -> list[str]:
        """Extract tool name strings from LLM response."""
        valid = {s["name"] for s in self._all_schemas}
        return self._parse_json_list(response, valid)

    @staticmethod
    def _parse_json_list(response: str, valid_values: set[str]) -> list[str]:
        """
        Extract the first [...] JSON array from response and return only items
        present in valid_values.  Handles both plain strings and
        [{"name": "..."}] dicts.  Returns [] on any failure.
        """
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if not match:
            return []
        try:
            raw = json.loads(match.group(0))
            if not isinstance(raw, list):
                return []
            result = []
            for item in raw:
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("name", "")
                else:
                    continue
                if name in valid_values:
                    result.append(name)
            return result
        except json.JSONDecodeError:
            return []
