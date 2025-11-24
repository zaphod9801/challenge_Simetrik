import os
import sys
from google.adk.agents.llm_agent import Agent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

def test_adk():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set")
        return

    print("Initializing Agent...")
    agent = Agent(
        model='gemini-flash-latest',
        name='test_agent',
        description="A test agent",
        instruction="You are a helpful assistant. Reply with 'Hello ADK'."
    )
    
    print("Initializing Runner...")
    session_service = InMemorySessionService()
    session_service.create_session_sync(session_id="test_session", app_name="agents", user_id="test_user")
    runner = Runner(agent=agent, session_service=session_service, app_name="agents")
    
    print("Running Agent...")
    
    content = types.Content(role="user", parts=[types.Part(text="Say hello")])
    
    try:
        events = runner.run(
            user_id="test_user",
            session_id="test_session",
            new_message=content
        )
        
        for event in events:
            print(f"Event: {type(event)}")
            # Inspect event content
            if hasattr(event, 'text'):
                print(f"Text: {event.text}")
            elif hasattr(event, 'content'):
                print(f"Content: {event.content}")
            else:
                print(f"Event vars: {vars(event)}")
                
    except Exception as e:
        print(f"Error running agent: {e}")

if __name__ == "__main__":
    test_adk()
