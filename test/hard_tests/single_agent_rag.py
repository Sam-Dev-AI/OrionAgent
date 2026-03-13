import os
import shutil
from dotenv import load_dotenv
from orionagent import Agent, Gemini, KnowledgeBase, MemoryConfig

load_dotenv()

def test_rag_researcher():
    print("\n=== Single Agent Hard Test 2: RAG Researcher ===")
    
    # Clean up old knowledge base if exists (mocking fresh start)
    if os.path.exists("orion_data/knowledge/test_kb"):
        shutil.rmtree("orion_data/knowledge/test_kb", ignore_errors=True)

    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.2)
    kb = KnowledgeBase(collection_name="test_kb")
    
    researcher = Agent(
        name="Librarian",
        role="Information Retrieval Specialist",
        description="Ingests data and retrieves precise answers from a knowledge base.",
        knowledge=kb,
        memory=MemoryConfig(mode="persistent"),
        model=llm,
        verbose=True
    )
    
    # 1. Ingest information
    ingest_task = "Ingest the information that the secret password for the vault is 'Orion-Infinity-2026'."
    print(f"Action: {ingest_task}")
    researcher.ask(ingest_task, stream=False)
    
    # 2. Query after session break (mocked by using same agent but new context)
    query_task = "What is the secret password for the vault? Search your knowledge base."
    print(f"Action: {query_task}")
    response = researcher.ask(query_task, stream=False)
    
    print(f"\nResponse: {response}")
    
    # Verification
    assert "Orion-Infinity-2026" in response, "Should retrieve the secret password from RAG"
    print("Test Passed: RAG ingestion and retrieval verified with persistent memory.")

if __name__ == "__main__":
    test_rag_researcher()
