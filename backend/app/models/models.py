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

    # ESPN team ID — populated during scraping, used for team-specific news API calls
    espn_id = Column(String(30), nullable=True, index=True)

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
    photo_url = Column(String(500), nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    jersey_number = Column(Integer, nullable=True)
    espn_id = Column(String(30), nullable=True, index=True)
    stats_json = Column(JSON, nullable=True)
    bio = Column(Text, nullable=True)

    team = relationship("Team", back_populates="players")
    lineups = relationship("MatchLineup", back_populates="player")
    events = relationship("MatchEvent", back_populates="player")


# ── Seasons ────────────────────────────────────────────
class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # ESPN sport/league codes for news fetching (e.g. "soccer" / "eng.1")
    espn_sport = Column(String(50), nullable=True)
    espn_league = Column(String(50), nullable=True)

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
    # External provider event ID (e.g. ESPN event id) for deduplication and re-fetching
    external_id = Column(String(80), nullable=True, index=True)
    # Enrichment flag: True once lineup/events/stats have been fetched
    enriched = Column(Boolean, default=False, nullable=False)

    sport = relationship("Sport", back_populates="matches")
    season = relationship("Season", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    predictions = relationship("Prediction", back_populates="match")
    lineups = relationship("MatchLineup", back_populates="match", cascade="all, delete-orphan")
    events = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan",
                          order_by="MatchEvent.minute")
    stat_lines = relationship("MatchStatLine", back_populates="match", cascade="all, delete-orphan")


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


# ── Match Lineups ─────────────────────────────────────
class MatchLineup(Base):
    """Starting XI + bench for each team in a match."""
    __tablename__ = "match_lineups"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    is_starter = Column(Boolean, default=True, nullable=False)
    position = Column(String(50), nullable=True)
    jersey_number = Column(Integer, nullable=True)
    minutes_played = Column(Integer, nullable=True)

    match = relationship("Match", back_populates="lineups")
    team = relationship("Team")
    player = relationship("Player")


# ── Match Events ───────────────────────────────────────
class MatchEvent(Base):
    """In-match events: goals, cards, substitutions, assists."""
    __tablename__ = "match_events"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # goal / yellow_card / red_card / substitution / assist
    minute = Column(Integer, nullable=True)
    detail = Column(String(300), nullable=True)  # human-readable description

    match = relationship("Match", back_populates="events")
    team = relationship("Team")
    player = relationship("Player")


# ── Match Stat Lines ───────────────────────────────────
class MatchStatLine(Base):
    """Per-team aggregated match statistics (possession, shots, etc.)."""
    __tablename__ = "match_stat_lines"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    is_home = Column(Boolean, nullable=False)
    # Flexible JSON bag — keys vary by sport:
    # soccer: possession, shots, shots_on_target, corners, fouls, yellow_cards, red_cards, offsides, pass_accuracy
    # basketball: points, rebounds, assists, steals, blocks, turnovers, fg_pct, three_pct, ft_pct
    # hockey: shots, saves, power_play_goals, power_play_attempts, faceoff_pct
    stats = Column(JSON, nullable=True, default=dict)

    match = relationship("Match", back_populates="stat_lines")


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


# ── News ───────────────────────────────────────────────
class NewsArticle(Base):
    """Stores news/gossip articles from ESPN, Google News, Reddit, etc."""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(String(2000), unique=True, nullable=False)
    image_url = Column(String(2000), nullable=True)
    source = Column(String(200), nullable=True)   # "ESPN", "Google News", "Reddit r/soccer"
    language = Column(String(10), nullable=True)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    match_links = relationship("MatchNews", back_populates="article", cascade="all, delete-orphan")
    team_links = relationship("TeamNews", back_populates="article", cascade="all, delete-orphan")
    season_links = relationship("SeasonNews", back_populates="article", cascade="all, delete-orphan")


class MatchNews(Base):
    """Junction: match ↔ news article."""
    __tablename__ = "match_news"
    __table_args__ = (UniqueConstraint("match_id", "article_id", name="uq_match_article"),)

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)

    match = relationship("Match")
    article = relationship("NewsArticle", back_populates="match_links")


class TeamNews(Base):
    """Junction: team ↔ news article."""
    __tablename__ = "team_news"
    __table_args__ = (UniqueConstraint("team_id", "article_id", name="uq_team_article"),)

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)

    team = relationship("Team")
    article = relationship("NewsArticle", back_populates="team_links")


class SeasonNews(Base):
    """Junction: season/league ↔ news article."""
    __tablename__ = "season_news"
    __table_args__ = (UniqueConstraint("season_id", "article_id", name="uq_season_article"),)

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)

    season = relationship("Season")
    article = relationship("NewsArticle", back_populates="season_links")
