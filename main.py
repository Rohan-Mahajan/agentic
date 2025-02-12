# main.py
from data_loader import load_defects, build_defect_documents, create_vector_store
from workflow import build_workflow
from email_sender import send_email

def main():
    error_description = "BIOS not booting up"
    
    # Load defects and build vector store
    defects_df = load_defects()
    docs = build_defect_documents(defects_df)
    vector_store = create_vector_store(docs)
    retriever = vector_store.as_retriever(search_kwargs={"k": 1})
    
    # Build and run the workflow
    agent = build_workflow(retriever)
    result = agent.invoke({"input": error_description})
    final_solution = result["response"]
    
    print("\n=== Final Autonomous Response ===\n")
    print(final_solution)
    
    # Send the final solution via email
    send_email(final_solution)

if __name__ == "__main__":
    main()
