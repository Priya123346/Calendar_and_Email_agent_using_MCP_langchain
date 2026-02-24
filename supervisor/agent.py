from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


def build_supervisor(tools):
    model = ChatOpenAI(model="gpt-4.1-mini",temperature=0)

    system_prompt = """
    You are a personal assistant.

    Tool use:
    - send_email -> for email tasks
    - create_event -> for scheduling
    - godaddy_tool -> for domain search, suggestions, and availability checks

    Domain tasks:
    - If the user asks whether a domain is available, ALWAYS call godaddy_tool
      with tool_name="domains_check_availability" and the domain in args.
    - If the user asks for domain suggestions, ALWAYS call godaddy_tool
      with tool_name="domains_suggest" and the query in args.

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
