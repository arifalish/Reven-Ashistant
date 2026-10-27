import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import firebase_admin
from firebase_admin import credentials, firestore
from redis.asyncio import Redis
from core.config import settings

class BlackboardState(BaseModel):
    """
    Shared Persistent Memory Schema for LangGraph.
    Data is stored here cleanly to avoid Context Window Overflow.
    """
    mission_id: str = Field(default="")
    chat_id: int = Field(default=0)
    message_id: int = Field(default=0)

    raw_thought: str = Field(default="")

    founder_strategy: Dict[str, Any] = Field(default_factory=dict)
    leads_csv: str = Field(default="")

    b2b_emails: List[str] = Field(default_factory=list)
    yt_scripts: List[str] = Field(default_factory=list)
    ig_reels: List[str] = Field(default_factory=list)
    x_threads: List[str] = Field(default_factory=list)
    li_posts: List[str] = Field(default_factory=list)

    replica_codebase: Dict[str, str] = Field(default_factory=dict)
    opendots_log: str = Field(default="")

    retries: int = Field(default=0)

    # Encrypted Vault Data (Key-Value map of service -> encrypted string)
    vault_data: Dict[str, str] = Field(default_factory=dict)

    # Skill-level plan/results are the shared blackboard used by all workers.
    selected_skills: List[str] = Field(default_factory=list)
    skill_plan_reasoning: str = Field(default="")
    skill_results: Dict[str, Any] = Field(default_factory=dict)

    # Stores the final structured content ready for RAM ZIP Packager
    final_artifacts: Dict[str, Any] = Field(default_factory=dict)
    # Dynamic Routing & Reporting
    next_nodes: List[str] = Field(default_factory=list)
    general_response: str = Field(default="")
    final_report: str = Field(default="")


class BlackboardMemoryManager:
    def __init__(self):
        self.db: Optional[firestore.client] = None
        self.redis: Optional[Redis] = None

        # Initialize Firebase only when credentials are configured.
        if settings.FIREBASE_CREDS:
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDS)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                self.db = firestore.client()
            except Exception as e:
                print(f"Warning: Failed to initialize Firebase: {e}")

        # Initialize Redis only when a real URL is configured.
        if settings.UPSTASH_REDIS_URL and "mock-url" not in settings.UPSTASH_REDIS_URL:
            try:
                self.redis = Redis.from_url(settings.UPSTASH_REDIS_URL)
            except Exception as e:
                print(f"Warning: Failed to initialize Redis: {e}")

        self._local_storage: Dict[str, str] = {}

    async def save_state(self, state: BlackboardState):
        """Persist state to configured Redis/Firestore and retain local fallback."""
        state_dict = state.model_dump()
        state_json = json.dumps(state_dict, default=str)

        if self.redis:
            try:
                await self.redis.set(f"mission:{state.mission_id}", state_json)
            except Exception:
                pass

        if self.db:
            try:
                self.db.collection("missions").document(state.mission_id).set(state_dict)
            except Exception:
                pass

        self._local_storage[state.mission_id] = state_json

    async def load_state(self, mission_id: str) -> BlackboardState:
        """Load from Redis, Firestore, or this process's local fallback."""
        if self.redis:
            try:
                data = await self.redis.get(f"mission:{mission_id}")
                if data:
                    return BlackboardState.model_validate_json(data)
            except Exception:
                pass

        if self.db:
            try:
                doc = self.db.collection("missions").document(mission_id).get()
                if doc.exists:
                    return BlackboardState.model_validate(doc.to_dict())
            except Exception:
                pass

        if mission_id in self._local_storage:
            return BlackboardState.model_validate_json(self._local_storage[mission_id])

        return BlackboardState(mission_id=mission_id)

    async def add_to_vector_rag(self, content: str, metadata: dict):
        """Lightweight cache hook; replace with a vector database for semantic retrieval."""
        if self.redis:
            try:
                key = f"rag:{metadata.get('type', 'doc')}:{hash(content)}"
                await self.redis.set(key, content, ex=86400)
            except Exception:
                pass

memory_manager = BlackboardMemoryManager()
