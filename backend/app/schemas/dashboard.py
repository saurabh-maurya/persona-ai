from pydantic import BaseModel


class CharacterStats(BaseModel):
    characterId: str
    name: str
    status: str
    totalSessions: int
    totalImages: int
    generatedImages: int


class SessionStats(BaseModel):
    sessionId: str
    sessionName: str
    characterName: str
    status: str
    completionPct: float
    totalImages: int
    generatedImages: int
    failedImages: int


class QueueStats(BaseModel):
    pending: int
    processing: int
    completed: int
    failed: int
    retrying: int
    total: int


class DashboardResponse(BaseModel):
    totalCharacters: int
    activeCharacters: int
    totalSessions: int
    totalImages: int
    generatedImages: int
    queue: QueueStats
    recentSessions: list[SessionStats]
