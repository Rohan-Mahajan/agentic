# data_loader.py
import pandas as pd
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import DEFECTS_CSV

def load_defects():
    try:
        defects_df = pd.read_csv(DEFECTS_CSV)
    except Exception:
        defects_df = pd.DataFrame()
    return defects_df

def load_test_cases():
    try:
        test_cases_df = pd.read_csv("test_cases.csv")
    except Exception:
        test_cases_df = pd.DataFrame(columns=[
            "Module", "Test_Scenario", "Test_Steps", 
            "Pre_Requisite", "Pass_Fail_Criteria", "Expected_Result"
        ])
    return test_cases_df

def build_defect_documents(defects_df):
    docs = []
    for _, row in defects_df.iterrows():
        if pd.notna(row.get("Description")) and pd.notna(row.get("Solution")):
            docs.append(Document(
                page_content=row["Description"],
                metadata={
                    "solution": row["Solution"],
                    "module": row["Module"]
                }
            ))
    return docs

def create_vector_store(docs):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(docs, embeddings)
    return vector_store
