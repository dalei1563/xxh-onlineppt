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


class DisplayModeMsg(InboundMessage):
    type: Literal["display_mode"] = "display_mode"
    mode: str  # "fill" 或 "16-9"


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


class AiAudioDataMsg(InboundMessage):
    """客户端上传的音频数据（base64 编码）"""
    type: Literal["ai_audio_data"] = "ai_audio_data"
    audio: str  # base64 编码的音频数据
    format: str = "wav"  # 音频格式
    done: bool = False  # 是否录音结束


class AiRealtimeStartMsg(InboundMessage):
    type: Literal["ai_realtime_start"] = "ai_realtime_start"
    audio: bool = True


class AiRealtimeAudioAppendMsg(InboundMessage):
    type: Literal["ai_realtime_audio_append"] = "ai_realtime_audio_append"
    audio: str


class AiRealtimeTextMsg(InboundMessage):
    type: Literal["ai_realtime_text"] = "ai_realtime_text"
    text: str


class AiRealtimeCancelMsg(InboundMessage):
    type: Literal["ai_realtime_cancel"] = "ai_realtime_cancel"


class AiRealtimeClearMsg(InboundMessage):
    type: Literal["ai_realtime_clear"] = "ai_realtime_clear"


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


class DisplayModeMsgOut(OutboundMessage):
    type: Literal["display_mode"] = "display_mode"
    mode: str


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


class AiAudioStatusMsg(OutboundMessage):
    """AI 音频处理状态"""
    type: Literal["ai_audio_status"] = "ai_audio_status"
    status: str  # recording/recording_stop/thinking/speaking/error
    message: str = ""


class AiAudioTranscriptMsg(OutboundMessage):
    """语音识别结果"""
    type: Literal["ai_audio_transcript"] = "ai_audio_transcript"
    text: str
    is_user: bool = True  # True=用户说的，False=AI说的


class AiRealtimeStatusMsg(OutboundMessage):
    type: Literal["ai_realtime_status"] = "ai_realtime_status"
    status: str
    message: str = ""


class AiRealtimeTextDeltaMsg(OutboundMessage):
    type: Literal["ai_realtime_text_delta"] = "ai_realtime_text_delta"
    delta: str


class AiRealtimeTextDoneMsg(OutboundMessage):
    type: Literal["ai_realtime_text_done"] = "ai_realtime_text_done"
    text: str


class AiRealtimeAudioDeltaMsg(OutboundMessage):
    type: Literal["ai_realtime_audio_delta"] = "ai_realtime_audio_delta"
    audio: str
    sample_rate: int = 24000


class AiRealtimeUserTranscriptMsg(OutboundMessage):
    type: Literal["ai_realtime_user_transcript"] = "ai_realtime_user_transcript"
    text: str


class ClientsCountMsg(OutboundMessage):
    type: Literal["clients_count"] = "clients_count"
    count: int


class ErrorMsg(OutboundMessage):
    type: Literal["error"] = "error"
    message: str
