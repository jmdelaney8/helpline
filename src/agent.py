import os
import re

import openai

import log

# Load your OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

_MODEL = "gpt-4o-mini"
_TEMPERATURE = 0.3


class HelplineAgent:
    def __init__(self, user_prompt):
        self.history = []  # Holds conversation context
        with open("src/agent_prompt.txt", "r") as f:
            self.system_instruction = f.read()
        self.system_instruction += user_prompt
        self.history = [{"role": "developer", "content": self.system_instruction}]

        self.interactions = []

    def respond(self, prompt):
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

            self.interactions.append((prompt, response.output_text))

            return response.output_text
        except Exception as e:
            return f"[Error] {e}"

    def get_action(self, transcript):
        """Returns an action for the given transcript."""
        response = self.respond(transcript)
        log.info(f"Agent response: {response}")

        if digit := extract_dtmf(response):
            return "send_dtfm", digit
        if "handoff" in response.lower():
            # Trigger handoff endpoint
            return "handoff", None
        if "report" in response.lower():
            log.info(f"Reporting to user: {response}")
            self.report_interactions()
            return "end_call", None
            self.call_end = True
        else:
            return None, None

    def report_interactions(self):
        """Prints the interactions"""
        print("interactions:\n")
        for input_, action in self.interactions:
            print(f"  {input_}")
            print(f"    {action}\n")


def extract_dtmf(response):
    # Match 'press ' or 'enter ' followed by contiguous digits
    dtmf_match = re.search(r"(?:press|enter) (\d+)", response, re.IGNORECASE)
    if dtmf_match:
        return dtmf_match.group(1)
    return None
