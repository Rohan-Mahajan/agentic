from google.colab import userdata
import pandas as pd
import numpy as np
import logging
from typing import TypedDict, List

# Import LangGraph and related components
from langgraph.graph import END, StateGraph
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_groq import ChatGroq
from langchain.chat_models import AzureChatOpenAI

# Initialize the LLM
azure_api_key = userdata.get("azure_api_key")
azure_endpoint = userdata.get("azure_endpoint")
deployment_name = "gpt-4-32k"

llm = AzureChatOpenAI(
    deployment_name=deployment_name,
    openai_api_key=azure_api_key,
    openai_api_base=azure_endpoint,
    openai_api_version = "2024-08-01-preview",
    model_name="gpt-4-32k",
    temperature=0.3
)

# defining a similarity function
def cosine_similarity(vec1: np.ndarray, vec2:np.ndarray)->float:
  return float(np.dot(vec1, vec2)/(np.linalg.norm(vec1))*(np.linalg.norm(vec2)))

def get_embedding(text:str) -> np.ndarray:
  return np.array(embeddings.embed_query(text))

def is_similar(query:str, document: Document, threshold:float = 0.5)->bool:
  query_emb = get_embedding(query)
  doc_emb = get_embedding(document.page_content)
  sim = cosine_similarity(query_emb, doc_emb)
  logging.info("Cosine Similarity: %d", sim)
  return sim >= threshold

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Data Loading and Document Preparation
df = pd.read_csv("/content/defects.csv")

try:
    test_cases_df = pd.read_csv("/content/test_cases.csv")
except Exception as e:
    logging.warning("Test cases file not found or unreadable. Creating an empty DataFrame.")
    test_cases_df = pd.DataFrame(columns=["Module", "Test_Scenario", "Test_Steps", "Pre_Requisite", "Pass_Fail_Criteria", "Expected_Result"])

# Build documents from defects CSV (only using Module, Description, Solution)
docs = []
for _, row in df.iterrows():
    if pd.notna(row["Description"]) and pd.notna(row["Solution"]):
        docs.append(Document(
            page_content=row["Description"],
            metadata={
                "solution": row["Solution"],
                "module": row["Module"]
            }
        ))

# Create embeddings and FAISS vector store for retrieval
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vector_store = FAISS.from_documents(docs, embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 1})

# Helper: Retrieve CSV Test Cases by Module (only return proper ones)
def get_csv_test_cases(module: str) -> List[dict]:
    """
    Returns a list of proper test cases from the CSV for the given module.
    A test case is considered proper if all required fields are non-empty.
    Each test case is a dictionary with keys:
      Module, Test_Scenario, Test_Steps, Pre_Requisite, Pass_Fail_Criteria, Expected_Result.
    """
    valid_cases = []
    global test_cases_df
    if test_cases_df.empty:
        return valid_cases

    df_filtered = test_cases_df[test_cases_df["Module"] == module]
    required_fields = ["Test_Scenario", "Test_Steps", "Pre_Requisite", "Pass_Fail_Criteria", "Expected_Result"]
    for _, row in df_filtered.iterrows():
        if all(str(row.get(field, "")).strip() for field in required_fields):
            tc_dict = {field: row[field] for field in required_fields}
            tc_dict["Module"] = row["Module"]
            valid_cases.append(tc_dict)
    return valid_cases

# Helper: Parse Generated Test Case into Fields
def parse_test_case(tc_text: str) -> dict:
    """
    Parses a generated test case text to extract the fields.
    Expected labels: Test_Scenario:, Test_Steps:, Pre_Requisite:, Expected_Result:, Pass_Fail_Criteria:
    """
    fields = {
        "Test_Scenario": "",
        "Test_Steps": "",
        "Pre_Requisite": "",
        "Expected_Result": "",
        "Pass_Fail_Criteria": ""
    }
    # Use regex to capture content after each label up to the next label or end.
    for field in fields.keys():
        pattern = field + r":\s*(.*?)\s*(?=(Test_Steps:|Pre_Requisite:|Expected_Result:|Pass_Fail_Criteria:|$))"
        match = re.search(pattern, tc_text, re.DOTALL)
        if match:
            fields[field] = match.group(1).strip()
    return fields

# Helper: Save New Test Cases to CSV (avoiding duplicates)
def save_new_test_cases(new_cases: List[dict]):
    """
    new_cases: list of dictionaries with keys:
      Module, Test_Scenario, Test_Steps, Pre_Requisite, Pass_Fail_Criteria, Expected_Result.
    Appends only new (non-duplicate) test cases to the CSV.
    """
    global test_cases_df
    required_columns = ["Module", "Test_Scenario", "Test_Steps", "Pre_Requisite", "Pass_Fail_Criteria", "Expected_Result"]
    if test_cases_df.empty:
        test_cases_df = pd.DataFrame(columns=required_columns)
    
    rows_to_add = []
    for case in new_cases:
        duplicate = test_cases_df[
            (test_cases_df["Module"] == case["Module"]) &
            (test_cases_df["Test_Scenario"] == case["Test_Scenario"]) &
            (test_cases_df["Test_Steps"] == case["Test_Steps"]) &
            (test_cases_df["Pre_Requisite"] == case["Pre_Requisite"]) &
            (test_cases_df["Pass_Fail_Criteria"] == case["Pass_Fail_Criteria"]) &
            (test_cases_df["Expected_Result"] == case["Expected_Result"])
        ]
        if duplicate.empty:
            rows_to_add.append(case)
    if rows_to_add:
        new_df = pd.DataFrame(rows_to_add)
        test_cases_df = pd.concat([test_cases_df, new_df], ignore_index=True)
        test_cases_df.to_csv("/content/test_cases.csv", index=False)
        logging.info("Saved %d new test case(s) to CSV.", len(rows_to_add))
    else:
        logging.info("No new test cases to save (duplicates skipped).")

# Define Agent State and LLM Initialization
class AgentState(TypedDict):
    input: str
    context: List[Document]
    response: str

# Workflow Node: Validate or Generate Test Cases (with CSV storage and supplementing missing cases)
def validate_or_generate_test_cases(state: AgentState):
    try:
        if not state["context"]:
            return {"response": "**Error**: The defect could not be found in the database."}
        context = state["context"][0]
        error_message = state["input"]

        # Ensure the defect is similar to the error message
        if not is_similar(error_message, context, threshold = 0.6):
          return {"response":"**Error**: The defect could not be found in the database."}

        # if similarity(error_message.lower(), context.page_content.lower()) <= 0.5:
        #     return {"response": "**Error**: The defect could not be found in the database."}

        solution = context.metadata["solution"]
        module = context.metadata["module"]

        # Generate explanation for why the solution works
        explanation_prompt = """
        [INST] Explain why this solution fixes the following error:
        Error: {error}
        Solution: {solution}
        [/INST]
        """
        explanation_template = ChatPromptTemplate.from_template(explanation_prompt)
        formatted_explanation = explanation_template.format_prompt(error=error_message, solution=solution)
        explanation = llm.invoke(formatted_explanation.to_messages()).content.strip()

        # Fetch test cases from CSV for the module
        csv_test_cases = get_csv_test_cases(module)
        REQUIRED_TEST_CASE_COUNT = 4  # set as required; adjust as needed

        if csv_test_cases and len(csv_test_cases) >= REQUIRED_TEST_CASE_COUNT:
            # If enough proper test cases exist, use them.
            selected_cases = csv_test_cases
            logging.info("Using %d test case(s) from CSV.", len(selected_cases))
        elif csv_test_cases and len(csv_test_cases) < REQUIRED_TEST_CASE_COUNT:
            # If some proper test cases exist but not enough, generate the missing ones.
            num_to_generate = REQUIRED_TEST_CASE_COUNT - len(csv_test_cases)
            additional_prompt = """
            [INST] Generate {num} additional comprehensive test case(s) to fully validate the following defect solution end-to-end.
            Error: {error}
            Solution: {solution}
            Explanation: {explanation}
            Ensure that these test cases do not duplicate the following existing test cases:
            {existing_test_cases}
            Each test case MUST include:
            Test_Scenario:
            Test_Steps:
            Pre_Requisite:
            Expected_Result:
            Pass_Fail_Criteria:
            End each test case with the delimiter "### END TEST CASE ###".
            [/INST]
            """
            existing_str = "\n".join(
                f"Test_Scenario: {tc['Test_Scenario']}\nTest_Steps: {tc['Test_Steps']}\nPre_Requisite: {tc['Pre_Requisite']}\nExpected_Result: {tc['Expected_Result']}\nPass_Fail_Criteria: {tc['Pass_Fail_Criteria']}"
                for tc in csv_test_cases
            )
            additional_template = ChatPromptTemplate.from_template(additional_prompt)
            formatted_additional = additional_template.format_prompt(
                num=num_to_generate,
                error=error_message,
                solution=solution,
                explanation=explanation,
                existing_test_cases=existing_str
            )
            additional_response = llm.invoke(formatted_additional.to_messages()).content.strip()
            delimiter = "\n### END TEST CASE ###\n"
            additional_cases_raw = [tc.strip() for tc in re.split(delimiter, additional_response) if tc.strip()]
            additional_cases = []
            for tc_raw in additional_cases_raw:
                parsed = parse_test_case(tc_raw)
                if parsed["Test_Scenario"]:
                    additional_cases.append({
                        "Module": module,
                        "Test_Scenario": parsed["Test_Scenario"],
                        "Test_Steps": parsed["Test_Steps"],
                        "Pre_Requisite": parsed["Pre_Requisite"],
                        "Pass_Fail_Criteria": parsed["Pass_Fail_Criteria"],
                        "Expected_Result": parsed["Expected_Result"]
                    })
            selected_cases = csv_test_cases + additional_cases
            if additional_cases:
                save_new_test_cases(additional_cases)
            logging.info("CSV had %d test case(s); generated %d additional test case(s).", len(csv_test_cases), len(additional_cases))
        else:
            # If no proper test cases exist in CSV, generate them all.
            full_prompt = """
            [INST] Generate a comprehensive set of test cases to fully validate the following defect solution end-to-end.
            Error: {error}
            Solution: {solution}
            Explanation: {explanation}
            Each test case MUST include:
            Test_Scenario:
            Test_Steps:
            Pre_Requisite:
            Expected_Result:
            Pass_Fail_Criteria:
            End each test case with the delimiter "### END TEST CASE ###".
            [/INST]
            """
            full_template = ChatPromptTemplate.from_template(full_prompt)
            formatted_full = full_template.format_prompt(error=error_message, solution=solution, explanation=explanation)
            full_response = llm.invoke(formatted_full.to_messages()).content.strip()
            delimiter = "\n### END TEST CASE ###\n"
            full_cases_raw = [tc.strip() for tc in re.split(delimiter, full_response) if tc.strip()]
            selected_cases = []
            for tc_raw in full_cases_raw:
                parsed = parse_test_case(tc_raw)
                if parsed["Test_Scenario"]:
                    selected_cases.append({
                        "Module": module,
                        "Test_Scenario": parsed["Test_Scenario"],
                        "Test_Steps": parsed["Test_Steps"],
                        "Pre_Requisite": parsed["Pre_Requisite"],
                        "Pass_Fail_Criteria": parsed["Pass_Fail_Criteria"],
                        "Expected_Result": parsed["Expected_Result"]
                    })
            if selected_cases:
                save_new_test_cases(selected_cases)
            logging.info("No proper test cases found in CSV; generated %d test case(s) from scratch.", len(selected_cases))

        # Format the selected test cases for final output
        def format_tc(tc: dict) -> str:
            return (f"Test_Scenario: {tc['Test_Scenario']}\n"
                    f"Test_Steps: {tc['Test_Steps']}\n"
                    f"Pre_Requisite: {tc['Pre_Requisite']}\n"
                    f"Expected_Result: {tc['Expected_Result']}\n"
                    f"Pass_Fail_Criteria: {tc['Pass_Fail_Criteria']}")
        test_cases_text = "\n\n".join(format_tc(tc) for tc in selected_cases)
        response_template = (
            "**Error:**\n{Error}\n\n"
            "**Solution:**\n{Solution}\n\n"
            "**Explanation:**\n{Explanation}\n\n"
            "**Test Cases:**\n{TestCases}"
        )
        return {"response": response_template.format(
            Error=error_message,
            Solution=solution,
            Explanation=explanation,
            TestCases=test_cases_text
        )}

    except Exception as e:
        logging.error("Validation/Generation error: %s", str(e))
        return {"response": f"Error processing request: {str(e)}"}

# Build the State Graph Workflow
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", lambda state: {"context": retriever.invoke(state["input"])})
workflow.add_node("validate_or_generate_test_cases", validate_or_generate_test_cases)
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "validate_or_generate_test_cases")
workflow.add_edge("validate_or_generate_test_cases", END)
agent = workflow.compile()

# Autonomous Evaluation & Self-improvement Functions
def auto_evaluate_solution(response: str) -> int:
    if "### END TEST CASE ###" in response:
        return 5
    elif "**Error**:" in response:
        return 1
    else:
        return 3

def generate_alternative_solution(error_message: str) -> str:
    alt_prompt = """
    [INST] Provide a concise, actionable alternative solution for the following error:
    Error: {error}
    Ensure that the solution is clear and does not include any follow-up questions.
    [/INST]
    """
    alt_template = ChatPromptTemplate.from_template(alt_prompt)
    formatted_alt = alt_template.format_prompt(error=error_message)
    alternative_solution = llm.invoke(formatted_alt.to_messages()).content.strip()

    test_case_prompt = """
    [INST] Given the error and the alternative solution:
    Error: {error}
    Solution: {solution}
    Generate EXACTLY 4 structured test cases with the delimiter "### END TEST CASE ###" after each test case.
    Each test case must include:
      Test_Scenario:
      Test_Steps:
      Pre_Requisite:
      Expected_Result:
      Pass_Fail_Criteria:
    [/INST]
    """
    tc_template = ChatPromptTemplate.from_template(test_case_prompt)
    formatted_tc = tc_template.format_prompt(error=error_message, solution=alternative_solution)
    alternative_test_cases = llm.invoke(formatted_tc.to_messages()).content.strip()

    alt_response = (
        "**Alternative Solution (Generated):**\n{AltSolution}\n\n"
        "**Test Cases for Alternative Solution:**\n{AltTestCases}"
    ).format(
        AltSolution=alternative_solution,
        AltTestCases=alternative_test_cases
    )
    return alt_response

def get_solution_autonomously(error_message: str) -> str:
    max_iterations = 3
    iteration = 0
    while iteration < max_iterations:
        logging.info("Iteration %d: Processing error: %s", iteration + 1, error_message)
        result = agent.invoke({"input": error_message.strip()})
        response = result["response"]
        logging.info("Agent response:\n%s", response)
        rating = auto_evaluate_solution(response)
        logging.info("Auto-evaluated rating: %d", rating)
        if rating < 3:
            logging.info("Rating below threshold. Generating alternative solution.")
            alt_response = generate_alternative_solution(error_message)
            logging.info("Alternative response generated.")
            return alt_response
        else:
            return response
        iteration += 1
    logging.info("Max iterations reached. Returning last response.")
    return response

# Autonomous Agent Execution
def main():
    error_description = "BIOS not booting up"
    final_solution = get_solution_autonomously(error_description)
    print("\n=== Final Autonomous Response ===\n")
    print(final_solution)

if __name__ == "__main__":
    main()
