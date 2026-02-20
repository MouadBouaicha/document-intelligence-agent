"""In-memory session manager for document and agent state."""
import threading
from typing import Any, Dict, List, Optional

from models import ProcessedDocument


class SessionManager:
    """Thread-safe in-memory store for documents and per-session agent state."""

    def __init__(self):
        self._lock = threading.Lock()
        # doc_id -> ProcessedDocument
        self._documents: Dict[str, ProcessedDocument] = {}
        # session_id -> agent instance
        self._agents: Dict[str, Any] = {}
        # session_id -> doc_id (which document is active for this session)
        self._session_docs: Dict[str, str] = {}

    # --- Document management ---

    def store_document(self, doc: ProcessedDocument) -> None:
        with self._lock:
            self._documents[doc.doc_id] = doc

    def get_document(self, doc_id: str) -> Optional[ProcessedDocument]:
        with self._lock:
            return self._documents.get(doc_id)

    def list_documents(self) -> List[ProcessedDocument]:
        with self._lock:
            return list(self._documents.values())

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._documents:
                return False
            del self._documents[doc_id]
            # Evict any sessions using this document
            stale = [sid for sid, did in self._session_docs.items() if did == doc_id]
            for sid in stale:
                self._agents.pop(sid, None)
                del self._session_docs[sid]
            return True

    # --- Agent management ---

    def store_agent(self, session_id: str, agent: Any, doc_id: str) -> None:
        with self._lock:
            self._agents[session_id] = agent
            self._session_docs[session_id] = doc_id

    def get_agent(self, session_id: str) -> Optional[Any]:
        with self._lock:
            return self._agents.get(session_id)

    def get_session_doc_id(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._session_docs.get(session_id)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._agents.pop(session_id, None)
            self._session_docs.pop(session_id, None)


# Singleton used across all routes
session_manager = SessionManager()
