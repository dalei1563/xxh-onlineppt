"""
WebSocket protocol - 所有 WebSocket 消息的 Pydantic 模型。
统一入站/出站消息 schema，避免手写 dict 导致字段不一致。
"""
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ========== 入站消息 ==========

class InboundMessage(BaseModel):
    """入站消息基类"""
    type: str


class NextSlideMsg(InboundMessage):
    type: Literal["next"] = "next"


class PrevSlideMsg(InboundMessage):
    type: Literal["prev"] = "prev"


class FirstSlideMsg(InboundMessage):
    type: Literal["first"] = "first"


class LastSlideMsg(InboundMessage):
    type: Literal["last"] = "last"


class GotoSlideMsg(InboundMessage):
    type: Literal["goto"] = "goto"
    slide: str


class SyncSlideMsg(InboundMessage):
    type: Literal["sync"] = "sync"
    slide: str


class FullscreenMsg(InboundMessage):
    type: Literal["fullscreen"] = "fullscreen"


class ReplayVideoMsg(InboundMessage):
    type: Literal["replay_video"] = "replay_video"


class ScoreUpdateMsg(InboundMessage):
    type: Literal["score_update"] = "score_update"
    team_name: str
    delta: int
    auto_tts: bool = False


class ScoreSetMsg(InboundMessage):
    type: Literal["score_set"] = "score_set"
    team_name: str
    score: int


class ScoreGetMsg(InboundMessage):
    type: Literal["score_get"] = "score_get"


class ScoreLeaderboardMsg(InboundMessage):
    type: Literal["score_leaderboard"] = "score_leaderboard"


class ScoreResetMsg(InboundMessage):
    type: Literal["score_reset"] = "score_reset"


class GameControlMsg(InboundMessage):
    type: Literal["game_control"] = "game_control"
    action: Literal["start", "end", "reset"]
    round_name: str = ""


class TtsSpeakMsg(InboundMessage):
    type: Literal["tts_speak"] = "tts_speak"
    text: str
    voice: str = ""


class TtsStopMsg(InboundMessage):
    type: Literal["tts_stop"] = "tts_stop"


class AiQuestionMsg(InboundMessage):
    type: Literal["ai_question"] = "ai_question"
    text: str


class AiVoiceClearMsg(InboundMessage):
    type: Literal["ai_voice_clear"] = "ai_voice_clear"


class AiVoiceStartMsg(InboundMessage):
    type: Literal["ai_voice_start"] = "ai_voice_start"


# ========== 出站消息 ==========

class OutboundMessage(BaseModel):
    """出站消息基类"""
    type: str


class PresentationStateMsg(OutboundMessage):
    type: Literal["presentation_state"] = "presentation_state"
    current_slide_id: str
    slide_order: List[str]
    total: int
    current_position: int
    is_game_active: bool = False
    current_round: str = ""


class GotoSlideMsgOut(OutboundMessage):
    type: Literal["goto"] = "goto"
    slide: str
    source: Optional[int] = None


class FullscreenMsgOut(OutboundMessage):
    type: Literal["fullscreen"] = "fullscreen"
    source: Optional[int] = None


class ReplayVideoMsgOut(OutboundMessage):
    type: Literal["replay_video"] = "replay_video"
    source: Optional[int] = None


class SlideCreatedMsg(OutboundMessage):
    type: Literal["slide_created"] = "slide_created"
    slide: Dict[str, Any]


class SlideUpdatedMsg(OutboundMessage):
    type: Literal["slide_updated"] = "slide_updated"
    slide: Dict[str, Any]


class SlideDeletedMsg(OutboundMessage):
    type: Literal["slide_deleted"] = "slide_deleted"
    slide_id: str


class SlidesReorderedMsg(OutboundMessage):
    type: Literal["slides_reordered"] = "slides_reordered"
    order: List[str]


class ScoreUpdateMsgOut(OutboundMessage):
    type: Literal["score_update"] = "score_update"
    team_name: str
    score: int
    delta: int


class ScoreSetMsgOut(OutboundMessage):
    type: Literal["score_set"] = "score_set"
    team_name: str
    score: int


class ScoreBoardMsg(OutboundMessage):
    type: Literal["score_board"] = "score_board"
    teams: List[Dict[str, Any]]
    leaderboard: bool = False


class ScoreResetMsgOut(OutboundMessage):
    type: Literal["score_reset"] = "score_reset"
    teams: List[Dict[str, Any]]


class GameControlMsgOut(OutboundMessage):
    type: Literal["game_control"] = "game_control"
    action: Literal["started", "ended", "reset"]
    round_name: str = ""


class TtsFileMsg(OutboundMessage):
    type: Literal["tts_file"] = "tts_file"
    url: str
    text: str


class TtsBrowserMsg(OutboundMessage):
    type: Literal["tts_browser"] = "tts_browser"
    text: str


class TtsStopMsgOut(OutboundMessage):
    type: Literal["tts_stop"] = "tts_stop"


class AiVoiceStatusMsg(OutboundMessage):
    type: Literal["ai_voice_status"] = "ai_voice_status"
    status: str
    message: str = ""


class AiAnswerMsg(OutboundMessage):
    type: Literal["ai_answer"] = "ai_answer"
    text: str
    client_id: Optional[int] = None


class ClientsCountMsg(OutboundMessage):
    type: Literal["clients_count"] = "clients_count"
    count: int


class ErrorMsg(OutboundMessage):
    type: Literal["error"] = "error"
    message: str
