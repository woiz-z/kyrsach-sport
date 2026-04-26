import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, Boolean,
    ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    user = "user"


class MatchStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class MatchResult(str, enum.Enum):
    home_win = "home_win"
    away_win = "away_win"
    draw = "draw"


# ── Users ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="user")


# ── Password Reset Tokens ───────────────────────────────
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# ── Sports ─────────────────────────────────────────────
class Sport(Base):
    __tablename__ = "sports"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)

    teams = relationship("Team", back_populates="sport")
    seasons = relationship("Season", back_populates="sport")
    matches = relationship("Match", back_populates="sport")


# ── Teams ──────────────────────────────────────────────
class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    logo_url = Column(String(500), nullable=True)
    founded_year = Column(Integer, nullable=True)

    sport = relationship("Sport", back_populates="teams")
    players = relationship("Player", back_populates="team")
    statistics = relationship("TeamStatistics", back_populates="team")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


# ── Players ────────────────────────────────────────────
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    position = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String(100), nullable=True)

    team = relationship("Team", back_populates="players")


# ── Seasons ────────────────────────────────────────────
class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    sport = relationship("Sport", back_populates="seasons")
    matches = relationship("Match", back_populates="season")
    team_statistics = relationship("TeamStatistics", back_populates="season")


# ── Matches ────────────────────────────────────────────
class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    match_date = Column(DateTime, nullable=False)
    venue = Column(String(200), nullable=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.scheduled, nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    result = Column(Enum(MatchResult), nullable=True)

    sport = relationship("Sport", back_populates="matches")
    season = relationship("Season", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    predictions = relationship("Prediction", back_populates="match")


# ── Team Statistics ────────────────────────────────────
class TeamStatistics(Base):
    __tablename__ = "team_statistics"
    __table_args__ = (UniqueConstraint("team_id", "season_id", name="uq_team_season"),)

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    points = Column(Integer, default=0)
    form_last5 = Column(JSON, nullable=True)

    team = relationship("Team", back_populates="statistics")
    season = relationship("Season", back_populates="team_statistics")


# ── Head to Head ───────────────────────────────────────
class HeadToHead(Base):
    __tablename__ = "head_to_head"

    id = Column(Integer, primary_key=True, index=True)
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    total_matches = Column(Integer, default=0)
    team1_wins = Column(Integer, default=0)
    team2_wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)


# ── AI Models ──────────────────────────────────────────
class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    algorithm = Column(String(100), nullable=False)
    accuracy = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    f1 = Column(Float, nullable=True)
    trained_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)
    parameters = Column(JSON, nullable=True)


# ── Predictions ────────────────────────────────────────
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    predicted_result = Column(Enum(MatchResult), nullable=False)
    home_win_prob = Column(Float, nullable=False)
    draw_prob = Column(Float, nullable=False)
    away_win_prob = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    model_name = Column(String(100), nullable=True)
    ai_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_correct = Column(Boolean, nullable=True)

    match = relationship("Match", back_populates="predictions")
    user = relationship("User", back_populates="predictions")
