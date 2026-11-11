#!/usr/bin/env python3
"""Minimal terminal assistant. Every important line is annotated for learning."""

# Reuse exactly the same offline memory and model engine as the browser app.

from server import (initialize, add_memory, get_memories, make_messages,
                    ollama_chat, remember_chat, MODEL)

# If the SQLite file does not exist, create its three tables.
initialize()

# Show the selected local model so the user can troubleshoot setup.
print(f"\nEinstein (offline terminal) — model: {MODEL}")

# A command help banner; no special packages are needed for the terminal UI.
print("Commands: /memories  /quit  or: remember that ...")

# The while loop keeps chatting until the user exits the program.
while True:
    try:
        # input waits for a human message from the keyboard.
        question = input("\nYou > ").strip()
    except (EOFError, KeyboardInterrupt):
        # Ctrl+D / Ctrl+C should exit cleanly instead of showing an error.
        print("\nGoodbye, Trailblazer!")
        break

    # Blank messages shouldn't be sent to the model.
    if not question:
        continue

    # A slash command closes the program without using the language model.
    if question.lower() == "/quit":
        print("Einstein > Goodbye, Trailblazer!")
        break

    # This command reads actual notes saved in SQLite across sessions.
    if question.lower() == "/memories":
        notes = get_memories()
        for row in notes:
            print(f"  [{row['id']}] {row['note']}")
        if not notes:
            print("Einstein > I don't have saved memories yet.")
        continue

    # Only explicitly requested details enter persistent long-term memory.
    if question.lower().startswith("remember that "):
        saved = add_memory(question[len("remember that "):])
        print(f"Einstein > I saved locally: {saved}")
        continue

    # Find relevant saved notes and imported document passages for this query.
    messages, sources = make_messages(question)
    try:
        # This calls http://127.0.0.1:11434/api/chat, NOT a cloud service.
        answer = ollama_chat(messages)
    except RuntimeError as error:
        # Show a helpful setup error if Ollama/model isn't ready on this Mac.
        print(f"Einstein > Local AI unavailable: {error}")
        continue

    # Store the question and answer for continuity after app restart.
    remember_chat(question, answer)

    # Display the answer and the names of user files used as context.
    print(f"Einstein > {answer}")
    if sources:
        print("Sources:", ", ".join(sorted({r['source'] for r in sources})))
