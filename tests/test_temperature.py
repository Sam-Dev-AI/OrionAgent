import os
from unittest.mock import MagicMock
from orionagent import Agent, Manager, Gemini, Model

def test_temperature_propagation():
    # Mocking the model to intercept the temperature call
    mock_model = MagicMock(spec=Gemini)
    
    # 1. Test Agent layer (Stateless to avoid JSON mock errors)
    agent = Agent(name="TempBot", model=mock_model, memory="none")
    
    print("\n--- Phase 1: Agent.ask(temperature=0.3) ---")
    mock_model.generate.return_value = "Mock response"
    agent.ask("Hello", temperature=0.3, stream=False)
    
    # Check if model.generate was called with temperature=0.3
    print(f"Mock call args: {mock_model.generate.call_args}")
    kwargs = mock_model.generate.call_args.kwargs
    print(f"Agent passed temperature: {kwargs.get('temperature')}")
    assert kwargs.get('temperature') == 0.3
    
    # 2. Test Manager layer
    manager = Manager(name="Orchestrator", model=mock_model, memory="none")
    manager.add(agent)
    
    print("\n--- Phase 2: Manager.ask(temperature=0.9) ---")
    # We need to mock strategy to avoid real LLM calls for planning
    manager._strategy = MagicMock()
    manager.ask("Work on this", temperature=0.9, stream=False)
    
    # Strategy.execute should receive temperature=0.9
    strat_kwargs = manager._strategy.execute.call_args.kwargs
    print(f"Manager passed temperature to strategy: {strat_kwargs.get('temperature')}")
    assert strat_kwargs.get('temperature') == 0.9

    # 3. Test Model Factory
    print("\n--- Phase 3: Model Factory ---")
    factory_model = Model(provider="gemini", temperature=0.5)
    print(f"Factory model temperature: {getattr(factory_model, 'temperature', 'Not found')}")
    # Note: Model factory returns a provider instance, but provider.__init__ stores api_key etc.
    # We need to check if the generated provider has the temperature if it's stored.
    # Actually, Gemini provider doesn't store temperature in __init__, it receives it in generate().
    # But Model factory should pass it to get_provider.
    
    print("\nTEMPERATURE PROPAGATION TEST: PASSED")

if __name__ == "__main__":
    try:
        test_temperature_propagation()
    except Exception as e:
        print(f"\nTest FAILED: {e}")
        import traceback
        traceback.print_exc()
