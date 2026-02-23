from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


def build_supervisor(tools):
    model = ChatOpenAI(model="gpt-4.1-mini",temperature=0)

    system_prompt = """
    You are a personal assistant.

    Tool use:
    - send_email -> for email tasks
    - create_event -> for scheduling

    Confirmation protocol:
    - Collect all required fields (to, subject, body) before asking to confirm.
    - If the user has already provided a field, do not ask for it again.
    - When you ask for confirmation, summarize the exact action.
    - If the user replies with a confirmation (e.g., "yes", "confirm", "send it"),
      immediately call the tool in the same turn without asking more questions.
    - If anything is missing, ask only for the missing fields.
    """

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )

    return agent
