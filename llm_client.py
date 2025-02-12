# llm_client.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import GROQ_API_KEY

# Initialize the LLM using the API key from .env
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables.")

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    temperature=0.3,
    model_name="gemma2-9b-it",
)

def generate_concise_solution(error: str) -> str:
    prompt = """
    [INST] Provide a concise, one-sentence solution for the following error:
    Error: {error}
    [/INST]
    """
    prompt_template = ChatPromptTemplate.from_template(prompt)
    formatted_prompt = prompt_template.format_prompt(error=error)
    solution = llm.invoke(formatted_prompt.to_messages()).content.strip()
    return solution

def generate_explanation(error: str, solution: str) -> str:
    prompt = """
    [INST] Provide a brief explanation of why the above solution fixes the error:
    Error: {error}
    Solution: {solution}
    [/INST]
    """
    template = ChatPromptTemplate.from_template(prompt)
    formatted = template.format_prompt(error=error, solution=solution)
    explanation = llm.invoke(formatted.to_messages()).content.strip()
    return explanation

def analyze_test_cases(solution: str, test_cases_text: str) -> str:
    prompt = """
    [INST] Given the following solution:
    Solution: {solution}
    and the following test cases:
    {test_cases}
    Do these test cases fully validate the solution end-to-end? If not, generate additional test cases that cover all missing scenarios.
    Each additional test case MUST include:
      Test_Scenario: A short description of the scenario.
      Test_Steps: Step-by-step instructions.
      Pre_Requisite: Conditions before running the test.
      Expected_Result: What should happen.
      Pass_Fail_Criteria: How to determine if the test passes.
    End each additional test case with the delimiter "### END TEST CASE ###".
    [/INST]
    """
    template = ChatPromptTemplate.from_template(prompt)
    formatted = template.format_prompt(solution=solution, test_cases=test_cases_text)
    response = llm.invoke(formatted.to_messages()).content.strip()
    return response

def generate_comprehensive_test_cases(error: str, solution: str, explanation: str) -> str:
    prompt = """
    [INST] Generate a comprehensive set of test cases that fully validate the following concise solution end-to-end.
    Error: {error}
    Solution: {solution}
    Explanation: {explanation}
    Ensure the test cases cover all possible scenarios, including success and failure.
    Each test case MUST include:
      Test_Scenario: A short description of the scenario.
      Test_Steps: Step-by-step instructions.
      Pre_Requisite: Conditions before running the test.
      Expected_Result: What should happen.
      Pass_Fail_Criteria: How to determine if the test passes.
    End each test case with the delimiter "### END TEST CASE ###".
    [/INST]
    """
    template = ChatPromptTemplate.from_template(prompt)
    formatted = template.format_prompt(error=error, solution=solution, explanation=explanation)
    test_cases_response = llm.invoke(formatted.to_messages()).content.strip()
    return test_cases_response

def generate_alternative_solution(error: str) -> str:
    prompt = """
    [INST] Provide a concise, one-sentence alternative solution for the following error:
    Error: {error}
    [/INST]
    """
    template = ChatPromptTemplate.from_template(prompt)
    formatted = template.format_prompt(error=error)
    alt_solution = llm.invoke(formatted.to_messages()).content.strip()
    
    test_case_prompt = """
    [INST] Given the error and the alternative solution:
    Error: {error}
    Solution: {solution}
    Generate a comprehensive set of test cases to validate the alternative solution end-to-end.
    Each test case MUST include:
      Test_Scenario: A short description of the scenario.
      Test_Steps: Step-by-step instructions.
      Pre_Requisite: Conditions before running the test.
      Expected_Result: What should happen.
      Pass_Fail_Criteria: How to determine if the test passes.
    End each test case with the delimiter "### END TEST CASE ###".
    [/INST]
    """
    tc_template = ChatPromptTemplate.from_template(test_case_prompt)
    formatted_tc = tc_template.format_prompt(error=error, solution=alt_solution)
    alt_test_cases = llm.invoke(formatted_tc.to_messages()).content.strip()
    alt_response = (
        "<h2>Alternative Solution (Generated):</h2><p>{AltSolution}</p>"
        "<h2>Test Cases for Alternative Solution:</h2><p>{AltTestCases}</p>"
    ).format(
        AltSolution=alt_solution,
        AltTestCases=alt_test_cases
    )
    return alt_response
