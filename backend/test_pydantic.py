from pydantic import BaseModel, Field

class SummaryRequest(BaseModel):
    pdf_text: str
    summary_type: str = Field(default='medium')

