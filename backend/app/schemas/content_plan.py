from datetime import datetime
from pydantic import BaseModel, Field


class GeneratePlanRequest(BaseModel):
    sessionId: str


class SharedDescriptionSchema(BaseModel):
    outfitFamily: str = ""
    lightingMood: str = ""
    cameraStyle: str = ""
    backgroundLocation: str = ""


class ImageDescriptionSchema(BaseModel):
    pose: str = ""
    bodyAngle: str = ""
    handPlacement: str = ""
    framing: str = ""
    fullPrompt: str = ""


class ContentPlanResponse(BaseModel):
    id: str
    sessionId: str
    dayNo: int
    section: str
    contentType: str
    sectionIntent: str
    sharedDescription: dict
    hashtags: list[str]
    imageCount: int
    createdAt: datetime


class ImagePromptResponse(BaseModel):
    id: str
    sessionId: str
    contentPlanId: str
    dayNo: int
    section: str
    imageNo: int
    prompt: str
    status: str
    jobId: str
    attempts: int
    errorMessage: str
    createdAt: datetime
    updatedAt: datetime
