import os

import openai

import log

# Load your OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

_MODEL = "gpt-4o-mini"
_TEMPERATURE = 0.3


class HelplineAgent:
    def __init__(self):
        self.history = []  # Holds conversation context
        with open("src/agent_prompt.txt", "r") as f:
            self.system_instruction = f.read()

    def handle_user_prompt(self, user_prompt):
        self.system_instruction += user_prompt
        self.history = [{"role": "developer", "content": self.system_instruction}]

    def get_action(self, prompt):
        self.history.append({"role": "user", "content": prompt})

        log.info(f"agent history: {self.history}")

        try:
            response = openai.responses.create(
                model=_MODEL,
                input=self.history,
            )

            # Save history
            new_history = [
                {"role": el.role, "content": el.content} for el in response.output
            ]
            self.history += new_history

            return response.output_text
        except Exception as e:
            return f"[Error] {e}"


def run_cli():
    agent = HelplineAgent()
    print("Helpline Agent")

    goal = input("What do you want help with today: ")
    agent.handle_user_prompt(goal)

    print("Enter simulated phone prompts. Type 'exit' to quit.\n")
    while True:
        prompt = input("Phone prompt > ").strip()
        if prompt.lower() in {"exit", "quit"}:
            break

        action = agent.get_action(prompt)
        log.info(f"Agent: {action}\n")


def cli():
    agent = HelplineAgent()

    agent.handle_user_prompt("I need to reset my password")

    prompt = (
        "Press 1 for registration, press 2 for billing, press 3 for account management,"
        " press 4 for utility service requests"
    )

    action = agent.get_action(prompt)
    log.info(f"Agent: {action}\n")
