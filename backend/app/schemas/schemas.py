from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


# ── Enums ──────────────────────────────────────────────
class UserRoleEnum(str, Enum):
    admin = "admin"
    analyst = "analyst"
    user = "user"


class MatchStatusEnum(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class MatchResultEnum(str, Enum):
    home_win = "home_win"
    away_win = "away_win"
    draw = "draw"


# ── Auth ───────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRoleEnum
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


# ── Sport ──────────────────────────────────────────────
class SportCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None


class SportResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]

    class Config:
        from_attributes = True


# ── Team ───────────────────────────────────────────────
class TeamCreate(BaseModel):
    name: str = Field(..., max_length=100)
    sport_id: int
    country: Optional[str] = None
    city: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None


class TeamResponse(BaseModel):
    id: int
    name: str
    sport_id: int
    country: Optional[str]
    city: Optional[str]
    logo_url: Optional[str]
    founded_year: Optional[int]

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    sport: Optional[SportResponse] = None


# ── Player ─────────────────────────────────────────────
class PlayerCreate(BaseModel):
    name: str = Field(..., max_length=150)
    team_id: int
    position: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None


class PlayerResponse(BaseModel):
    id: int
    name: str
    team_id: int
    position: Optional[str]
    date_of_birth: Optional[date]
    nationality: Optional[str]

    class Config:
        from_attributes = True


# ── Season ─────────────────────────────────────────────
class SeasonCreate(BaseModel):
    sport_id: int
    name: str = Field(..., max_length=100)
    start_date: date
    end_date: date


class SeasonResponse(BaseModel):
    id: int
    sport_id: int
    name: str
    start_date: date
    end_date: date

    class Config:
        from_attributes = True


# ── Match ──────────────────────────────────────────────
class MatchCreate(BaseModel):
    sport_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    match_date: datetime
    venue: Optional[str] = None


class MatchUpdate(BaseModel):
    status: Optional[MatchStatusEnum] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    result: Optional[MatchResultEnum] = None


class MatchResponse(BaseModel):
    id: int
    sport_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    match_date: datetime
    venue: Optional[str]
    status: MatchStatusEnum
    home_score: Optional[int]
    away_score: Optional[int]
    result: Optional[MatchResultEnum]

    class Config:
        from_attributes = True


class MatchDetailResponse(MatchResponse):
    home_team: Optional[TeamResponse] = None
    away_team: Optional[TeamResponse] = None
    sport: Optional[SportResponse] = None
    season: Optional[SeasonResponse] = None


# ── Team Statistics ────────────────────────────────────
class TeamStatisticsResponse(BaseModel):
    id: int
    team_id: int
    season_id: int
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int
    form_last5: Optional[list] = None

    class Config:
        from_attributes = True


class TeamStatsWithTeam(TeamStatisticsResponse):
    team: Optional[TeamResponse] = None


# ── Head to Head ───────────────────────────────────────
class HeadToHeadResponse(BaseModel):
    id: int
    team1_id: int
    team2_id: int
    total_matches: int
    team1_wins: int
    team2_wins: int
    draws: int

    class Config:
        from_attributes = True


# ── AI Model ──────────────────────────────────────────
class AIModelResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    algorithm: str
    accuracy: Optional[float]
    precision_score: Optional[float]
    recall_score: Optional[float]
    f1: Optional[float]
    trained_at: Optional[datetime]
    is_active: bool
    parameters: Optional[dict] = None

    class Config:
        from_attributes = True


# ── Prediction ─────────────────────────────────────────
class PredictionRequest(BaseModel):
    match_id: int


class PredictionResponse(BaseModel):
    id: int
    match_id: int
    user_id: Optional[int]
    predicted_result: MatchResultEnum
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    confidence: Optional[float]
    model_name: Optional[str]
    ai_analysis: Optional[str]
    sport_name: Optional[str] = None
    sport_icon: Optional[str] = None
    outcome_labels: Optional[dict] = None
    created_at: datetime
    is_correct: Optional[bool]

    class Config:
        from_attributes = True


class PredictionDetailResponse(PredictionResponse):
    match: Optional[MatchDetailResponse] = None


# ── Dashboard ──────────────────────────────────────────
class DashboardStats(BaseModel):
    total_matches: int
    completed_matches: int
    upcoming_matches: int
    total_predictions: int
    correct_predictions: int
    accuracy_percent: float
    total_teams: int
    total_sports: int
