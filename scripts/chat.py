#!/usr/bin/env python3
"""Interactive chat with the DeepAgent."""

import argparse

import modal


def main(user_id: str = "test", project_id: str = "test"):
    print("DevLabo Agent Chat")
    print("=" * 40)
    print(f"User: {user_id} | Project: {project_id}")
    print("Type 'quit' to exit, 'files' to list changed files")
    print()

    # Get reference to deployed agent
    AgentCls = modal.Cls.from_name("devlabo-agent", "DeepAgent")
    agent = AgentCls(user_id=user_id, project_id=project_id)

    chat_history = []

    while True:
        try:
            message = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not message:
            continue
        if message.lower() == "quit":
            print("Goodbye!")
            break

        print("\nAgent: ", end="", flush=True)

        result = agent.chat.remote(message=message, chat_history=chat_history)

        print(result["response"])

        if result.get("files_changed"):
            print(f"\n[Files in project: {', '.join(result['files_changed'][:5])}...]")

        # Update chat history
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": result["response"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat with DevLabo Agent")
    parser.add_argument("--user", default="test", help="User ID (default: test)")
    parser.add_argument("--project", default="test", help="Project ID (default: test)")
    args = parser.parse_args()
    main(user_id=args.user, project_id=args.project)
