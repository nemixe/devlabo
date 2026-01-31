#!/usr/bin/env python3
"""Interactive chat with the DeepAgent."""

import modal


def main():
    print("DevLabo Agent Chat")
    print("=" * 40)
    print("Type 'quit' to exit, 'files' to list changed files")
    print()

    # Get reference to deployed agent
    AgentCls = modal.Cls.from_name("devlabo-agent", "DeepAgent")
    agent = AgentCls(user_id="default", project_id="default")

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
    main()
