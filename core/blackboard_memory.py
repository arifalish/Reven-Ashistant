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
    conversation_memory: Dict[str, Any] = Field(default_factory=dict)

    retries: int = Field(default=0)

    # Encrypted Vault Data (Key-Value map of service -> encrypted string)
    vault_data: Dict[str, str] = Field(default_factory=dict)

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

        # Initialize Firestore
        if settings.FIREBASE_CREDS:
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDS)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                self.db = firestore.client()
            except Exception as e:
                print(f"Warning: Failed to initialize Firebase: {e}")

        # Initialize Redis
        if settings.UPSTASH_REDIS_URL and "mock-url" not in settings.UPSTASH_REDIS_URL:
            try:
                self.redis = Redis.from_url(settings.UPSTASH_REDIS_URL)
            except Exception as e:
                print(f"Warning: Failed to initialize Redis: {e}")

        # Simple local memory for fallback
        self._local_storage: Dict[str, str] = {}

    async def save_state(self, state: BlackboardState):
        """Save to Firestore/Redis/Local"""
        state_dict = state.model_dump()
        state_json = json.dumps(state_dict)

        if state.chat_id:
            self._local_storage[f"chat:{state.chat_id}"] = state_json

        # Try Redis
        if self.redis:
            try:
                await self.redis.set(f"mission:{state.mission_id}", state_json)
                if state.chat_id:
                    await self.redis.set(f"chat:{state.chat_id}:latest", state_json)
            except Exception:
                pass

        # Try Firestore
        if self.db:
            try:
                self.db.collection('missions').document(state.mission_id).set(state_dict)
                if state.chat_id:
                    self.db.collection('chat_memory').document(str(state.chat_id)).set({
                        "chat_id": state.chat_id,
                        "mission_id": state.mission_id,
                        "state": state_dict,
                        "updated_at": __import__("datetime").datetime.utcnow().isoformat()
                    })
            except Exception:
                pass

        # Fallback local storage
        self._local_storage[state.mission_id] = state_json

    async def load_state(self, mission_id: str) -> BlackboardState:
        """Load from Redis/Firestore/Local"""
        # Try Redis
        if self.redis:
            try:
                data = await self.redis.get(f"mission:{mission_id}")
                if data:
                    return BlackboardState.model_validate_json(data)
            except Exception:
                pass

        # Try Firestore
        if self.db:
            try:
                doc = self.db.collection('missions').document(mission_id).get()
                if doc.exists:
                    return BlackboardState.model_validate(doc.to_dict())
            except Exception:
                pass

        # Fallback local
        if mission_id in self._local_storage:
            return BlackboardState.model_validate_json(self._local_storage[mission_id])

        return BlackboardState(mission_id=mission_id)

    async def load_latest_chat_state(self, chat_id: int) -> Optional[BlackboardState]:
        """Load the latest known state for a Telegram chat thread."""
        if self.redis:
            try:
                data = await self.redis.get(f"chat:{chat_id}:latest")
                if data:
                    return BlackboardState.model_validate_json(data)
            except Exception:
                pass

        if self.db:
            try:
                doc = self.db.collection('chat_memory').document(str(chat_id)).get()
                if doc.exists:
                    state_dict = doc.to_dict().get('state')
                    if state_dict:
                        return BlackboardState.model_validate(state_dict)
            except Exception:
                pass

        if f"chat:{chat_id}" in self._local_storage:
            return BlackboardState.model_validate_json(self._local_storage[f"chat:{chat_id}"])

        return None

    async def add_to_vector_rag(self, content: str, metadata: dict):
        """
        Store context in Vector DB (simulated with Redis / mock logic).
        In a full implementation, we'd use nvidia/nv-embedqa-e5-v5 and a Pinecone/Qdrant instance.
        """
        if self.redis:
            try:
                # Mocking a vector insertion by just caching raw text
                # Real implementation would call embedding model, then store vector
                key = f"rag:{metadata.get('type', 'doc')}:{hash(content)}"
                await self.redis.set(key, content, ex=86400)  # 24h expiry
            except Exception:
                pass


memory_manager = BlackboardMemoryManager()
