"""DeepAgent Modal service for AI-powered code generation."""

import logging
import os
from typing import Any

import modal

from agent.prompts import SYSTEM_PROMPT
from agent.tools import create_tools

logger = logging.getLogger(__name__)

# Modal image for agent service
agent_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "langchain-core>=0.3.0",
        "langchain-openai>=0.3.0",
        "langgraph>=0.2.0",
        "openai>=1.0.0",
    )
    .add_local_python_source("common", "gateway", "sandbox", "security", "agent")
)

app = modal.App("devlabo-agent")


@app.cls(
    image=agent_image,
    secrets=[modal.Secret.from_name("openrouter-secret")],
    timeout=300,  # 5 minute timeout for chat
)
class DeepAgent:
    """
    AI Agent that orchestrates code generation via LangChain and Sandbox RPC.

    Uses OpenRouter API for model access (OpenAI-compatible).
    """

    user_id: str = modal.parameter(default="default")
    project_id: str = modal.parameter(default="default")

    @modal.enter()
    def startup(self):
        """Initialize agent with Sandbox reference and LangChain components."""
        logger.info(f"Starting agent for {self.user_id}/{self.project_id}")

        # Get reference to the running Sandbox
        self._init_sandbox()

        # Initialize LangChain agent
        self._init_agent()

        logger.info("Agent startup complete")

    def _init_sandbox(self) -> None:
        """Get reference to the project's Sandbox instance."""
        try:
            # Use modal.Cls.from_name to get reference to deployed class
            SandboxCls = modal.Cls.from_name("devlabo-sandbox", "ProjectSandbox")
            self.sandbox = SandboxCls(
                user_id=self.user_id,
                project_id=self.project_id,
            )
            logger.info("Sandbox reference acquired")
        except Exception as e:
            logger.error(f"Failed to connect to Sandbox: {e}")
            self.sandbox = None

    def _init_agent(self) -> None:
        """Initialize the LangChain agent with tools."""
        from langchain_core.messages import SystemMessage
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        # OpenRouter uses OpenAI-compatible API
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("OPENROUTER_API_KEY not found in environment")
            self.agent = None
            return

        # Initialize OpenRouter-compatible LLM
        self.llm = ChatOpenAI(
            model="anthropic/claude-sonnet-4",  # Can be configured
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=4096,
        )

        # Create tools with sandbox reference
        self.tools = create_tools(self.sandbox) if self.sandbox else []

        # Create the agent using langgraph's create_react_agent
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

        logger.info(f"Agent initialized with {len(self.tools)} tools")

    def _get_changed_files(self) -> list[str]:
        """Get list of files that may have been changed during this interaction."""
        if not self.sandbox:
            return []
        try:
            # List files in writable scopes
            changed = []
            for scope in ["frontend", "dbml", "test-case"]:
                files = self.sandbox.list_files.remote(scope=scope)
                changed.extend([f"{scope}/{f}" for f in files])
            return changed
        except Exception as e:
            logger.warning(f"Could not list changed files: {e}")
            return []

    @modal.method()
    def chat(self, message: str, chat_history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """
        Process a user message and return response with any file changes.

        Args:
            message: The user's message/prompt.
            chat_history: Optional list of previous messages for context.

        Returns:
            Dict with 'response' and 'files_changed' keys.
        """
        if not self.agent:
            return {
                "response": "Error: Agent not initialized. Check API key configuration.",
                "files_changed": [],
                "error": True,
            }

        try:
            from langchain_core.messages import AIMessage, HumanMessage

            # Build messages list
            messages = []

            # Add chat history if provided
            if chat_history:
                for msg in chat_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            # Add current message
            messages.append(HumanMessage(content=message))

            # Invoke the agent
            result = self.agent.invoke({"messages": messages})

            # Extract the final response from the agent
            final_messages = result.get("messages", [])
            response_text = ""
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    response_text = msg.content
                    break

            return {
                "response": response_text or "No response generated",
                "files_changed": self._get_changed_files(),
                "error": False,
            }
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {
                "response": f"Error processing request: {e}",
                "files_changed": [],
                "error": True,
            }

    @modal.method()
    def get_status(self) -> dict[str, Any]:
        """Get the agent's status."""
        return {
            "user_id": self.user_id,
            "project_id": self.project_id,
            "sandbox_connected": self.sandbox is not None,
            "agent_initialized": self.agent is not None,
            "tools_count": len(self.tools) if hasattr(self, "tools") else 0,
        }


# CLI entrypoint for testing
@app.local_entrypoint()
def test_agent(
    message: str = "List all files in the prototype scope",
    user_id: str = "test",
    project_id: str = "test",
):
    """Test the agent with a simple message."""
    print(f"Testing agent for {user_id}/{project_id}")
    print(f"Message: {message}")

    agent = DeepAgent(user_id=user_id, project_id=project_id)

    print("\nGetting status...")
    status = agent.get_status.remote()
    print(f"Status: {status}")

    print("\nSending message...")
    result = agent.chat.remote(message=message)
    print(f"\nResponse: {result['response']}")
    print(f"Files changed: {result['files_changed']}")
