from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language description of the desired SQL query",
        examples=["Show top 10 employees by salary"],
    )


class GenerateResponse(BaseModel):
    sql: str = Field(..., description="Generated SQL query only")


class ErrorResponse(BaseModel):
    detail: str
