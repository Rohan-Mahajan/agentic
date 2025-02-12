# test_case_manager.py
import pandas as pd
import re

def get_csv_test_cases(test_cases_df, module: str):
    test_cases = []
    if test_cases_df.empty:
        return test_cases
    df_filtered = test_cases_df[test_cases_df["Module"] == module]
    for _, row in df_filtered.iterrows():
        tc_text = " ".join([
            str(row.get("Test_Scenario", "")),
            str(row.get("Test_Steps", "")),
            str(row.get("Pre_Requisite", "")),
            str(row.get("Expected_Result", "")),
            str(row.get("Pass_Fail_Criteria", ""))
        ])
        if tc_text.strip() == "":
            continue
        tc_dict = {
            "Module": row["Module"],
            "Test_Scenario": row["Test_Scenario"],
            "Test_Steps": row["Test_Steps"],
            "Pre_Requisite": row["Pre_Requisite"],
            "Pass_Fail_Criteria": row["Pass_Fail_Criteria"],
            "Expected_Result": row["Expected_Result"]
        }
        test_cases.append(tc_dict)
    return test_cases

def parse_test_case(tc_text: str) -> dict:
    fields = {
        "Test_Scenario": "",
        "Test_Steps": "",
        "Pre_Requisite": "",
        "Expected_Result": "",
        "Pass_Fail_Criteria": ""
    }
    for field in fields.keys():
        pattern = field + r":\s*(.*?)\s*(?=(Test_Steps:|Pre_Requisite:|Expected_Result:|Pass_Fail_Criteria:|$))"
        match = re.search(pattern, tc_text, re.DOTALL)
        if match:
            fields[field] = match.group(1).strip()
    return fields

def save_new_test_cases(test_cases_df, new_cases: list, file_path="test_cases.csv"):
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
        test_cases_df.to_csv(file_path, index=False)
    return test_cases_df
