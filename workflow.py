# workflow.py
import re
import pandas as pd
from langgraph.graph import END, StateGraph
from llm_client import (
    generate_concise_solution, generate_explanation,
    analyze_test_cases, generate_comprehensive_test_cases
)
from test_case_manager import get_csv_test_cases, parse_test_case, save_new_test_cases
from utils import similarity
from config import TEST_CASES_CSV

def validate_or_generate_test_cases(state: dict) -> dict:
    try:
        error_message = state["input"]
        solution = None
        module = None

        # Retrieve defect context if available.
        if state.get("context") and len(state["context"]) > 0:
            context = state["context"][0]
            if similarity(error_message.lower(), context.page_content.lower()) >= 0.6:
                solution = context.metadata["solution"]
                module = context.metadata["module"]

        # Load CSV test cases.
        try:
            test_cases_df = pd.read_csv(TEST_CASES_CSV)
        except Exception:
            test_cases_df = pd.DataFrame(columns=[
                "Module", "Test_Scenario", "Test_Steps", 
                "Pre_Requisite", "Pass_Fail_Criteria", "Expected_Result"
            ])
        csv_test_cases = get_csv_test_cases(test_cases_df, module) if module else []

        # Generate a concise solution if none is found.
        if not solution:
            solution = generate_concise_solution(error_message)
            explanation = generate_explanation(error_message, solution)
        else:
            explanation = generate_explanation(error_message, solution)

        if csv_test_cases:
            # Format CSV test cases for LLM analysis.
            def format_tc_plain(tc: dict) -> str:
                return (f"Test_Scenario: {tc['Test_Scenario']}\n"
                        f"Test_Steps: {tc['Test_Steps']}\n"
                        f"Pre_Requisite: {tc['Pre_Requisite']}\n"
                        f"Expected_Result: {tc['Expected_Result']}\n"
                        f"Pass_Fail_Criteria: {tc['Pass_Fail_Criteria']}")
            csv_tc_text = "\n\n".join(format_tc_plain(tc) for tc in csv_test_cases)

            # Analyze and generate additional test cases if needed.
            analysis_response = analyze_test_cases(solution, csv_tc_text)
            delimiter = "\n### END TEST CASE ###\n"
            additional_tc_raw = [tc.strip() for tc in re.split(delimiter, analysis_response) if tc.strip()]
            extra_generated_cases = []
            for tc_raw in additional_tc_raw:
                parsed = parse_test_case(tc_raw)
                if parsed["Test_Scenario"]:
                    extra_generated_cases.append({
                        "Module": module if module else "Generated",
                        "Test_Scenario": parsed["Test_Scenario"],
                        "Test_Steps": parsed["Test_Steps"],
                        "Pre_Requisite": parsed["Pre_Requisite"],
                        "Pass_Fail_Criteria": parsed["Pass_Fail_Criteria"],
                        "Expected_Result": parsed["Expected_Result"]
                    })
            # Combine CSV and additional test cases.
            all_test_cases = csv_test_cases + extra_generated_cases
            if extra_generated_cases:
                test_cases_df = save_new_test_cases(test_cases_df, extra_generated_cases, TEST_CASES_CSV)
            def format_tc(tc: dict) -> str:
                return (f"<p><strong>Test_Scenario:</strong> {tc['Test_Scenario']}<br>"
                        f"<strong>Test_Steps:</strong> {tc['Test_Steps']}<br>"
                        f"<strong>Pre_Requisite:</strong> {tc['Pre_Requisite']}<br>"
                        f"<strong>Expected_Result:</strong> {tc['Expected_Result']}<br>"
                        f"<strong>Pass_Fail_Criteria:</strong> {tc['Pass_Fail_Criteria']}</p>")
            test_cases_html = "\n".join(format_tc(tc) for tc in all_test_cases)
            response_template = (
                "<h2>Error:</h2><p>{Error}</p>"
                "<h2>Solution:</h2><p>{Solution}</p>"
                "<h2>Explanation:</h2><p>{Explanation}</p>"
                "<h2>Test Cases (CSV + Generated):</h2>{TestCases}"
            )
            final_response = response_template.format(
                Error=error_message,
                Solution=solution,
                Explanation=explanation,
                TestCases=test_cases_html
            )
        else:
            # Generate comprehensive test cases when no CSV cases exist.
            test_cases_response = generate_comprehensive_test_cases(error_message, solution, explanation)
            delimiter = "\n### END TEST CASE ###\n"
            test_cases_raw = [tc.strip() for tc in re.split(delimiter, test_cases_response) if tc.strip()]
            generated_cases = []
            for tc_raw in test_cases_raw:
                parsed = parse_test_case(tc_raw)
                if parsed["Test_Scenario"]:
                    generated_cases.append({
                        "Module": module if module else "Generated",
                        "Test_Scenario": parsed["Test_Scenario"],
                        "Test_Steps": parsed["Test_Steps"],
                        "Pre_Requisite": parsed["Pre_Requisite"],
                        "Pass_Fail_Criteria": parsed["Pass_Fail_Criteria"],
                        "Expected_Result": parsed["Expected_Result"]
                    })
            if generated_cases:
                test_cases_df = save_new_test_cases(test_cases_df, generated_cases, TEST_CASES_CSV)
            def format_tc(tc: dict) -> str:
                return (f"<p><strong>Test_Scenario:</strong> {tc['Test_Scenario']}<br>"
                        f"<strong>Test_Steps:</strong> {tc['Test_Steps']}<br>"
                        f"<strong>Pre_Requisite:</strong> {tc['Pre_Requisite']}<br>"
                        f"<strong>Expected_Result:</strong> {tc['Expected_Result']}<br>"
                        f"<strong>Pass_Fail_Criteria:</strong> {tc['Pass_Fail_Criteria']}</p>")
            test_cases_html = "\n".join(format_tc(tc) for tc in generated_cases)
            response_template = (
                "<h2>Error:</h2><p>{Error}</p>"
                "<h2>Solution:</h2><p>{Solution}</p>"
                "<h2>Explanation:</h2><p>{Explanation}</p>"
                "<h2>Test Cases (Generated):</h2>{TestCases}"
            )
            final_response = response_template.format(
                Error=error_message,
                Solution=solution,
                Explanation=explanation,
                TestCases=test_cases_html
            )
        state["response"] = final_response
        return {"response": final_response}
    except Exception as e:
        state["response"] = f"Error processing request: {e}"
        return {"response": state["response"]}

def build_workflow(retriever):
    workflow = StateGraph(dict)
    workflow.add_node("retrieve", lambda state: {"context": retriever.invoke(state["input"])})
    workflow.add_node("validate_or_generate_test_cases", validate_or_generate_test_cases)
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "validate_or_generate_test_cases")
    workflow.add_edge("validate_or_generate_test_cases", END)
    return workflow.compile()
