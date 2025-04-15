import textwrap
import re

import openai
import os


# Load your OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

_MODEL = "gpt-4o-mini"
_TEMPERATURE = 0.3


class HelplineAgent:
    def __init__(self):
        self.history = []  # Holds conversation context
        self.system_instruction = textwrap.dedent("""\
            # Overview
            You are an automated phone system navigator. Your job is to listen to
            phone prompts and respond with what a human would do next (e.g.,
            'press 1', 'say "technical support"', etc.). Be concise and respond
            with only the action you would take.

            You should use the developer-described goal to determine how to answer each
            phone prompt to achieve the goal. If you think you've made contact with a
            human operator (as opposed to the automated help line system) please
            respond "hand off to developer" in order to relinquish control to developer
            to continue the conversation.

            # Example
            developer goal: I need to ask a question about my rental application.

            user: Press 1 for billing, 2 for applications, 3 for service.

            agent: press 1
                                                  
            user: Hello thank you for contacting the billing department, how may I help
                  you?
            
            agent: handoff to developer
                                                  
            # General instructions:
            - If asked, communicate with the system in English.
            - The developer goal is never an emergency.
            - We don't want to make the helpline mad. Over-escalating our requests might
              upset them. That being said, we do need to be persistent to help the
              developer                                   
                                        

            The following is the developer-described goal:

            developer goal:
        """)

    def handle_user_prompt(self, user_prompt):
        self.system_instruction += user_prompt
        self.history = [{"role": "developer", "content": self.system_instruction}]

    def get_action(self, prompt):
        self.history.append({"role": "user", "content": prompt})

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

            if dtfm_action := extract_dtmf(response.output_text):
                return dtfm_action
            else:
                return response.output_text
        except Exception as e:
            return f"[Error] {e}"


def extract_dtmf(action):
    dtmf_match = re.search(r"press (\d+)", action, re.IGNORECASE)
    if dtmf_match:
        return dtmf_match.group(1)
    return None


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
        print(f"Agent: {action}\n")


def cli():
    agent = HelplineAgent()

    agent.handle_user_prompt("I need to reset my password")

    prompt = (
        "Press 1 for registration, press 2 for billing, press 3 for account management,"
        " press 4 for utility service requests"
    )

    action = agent.get_action(prompt)
    print(f"Agent: {action}\n")
