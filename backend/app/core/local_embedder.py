from __future__ import annotations
import logging, threading

logger = logging.getLogger(__name__)
MODEL_NAME = str('all-mpnet-base-v2')
EMBEDDING_DIM = 768
_model = None
_lock = threading.Lock()

def _load():
    global _model
    if _model: return _model
    with _lock:
        if _model: return _model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(str('Loading %s'), MODEL_NAME)
            _model = SentenceTransformer(MODEL_NAME)
            logger.info(str('Local embedder ready dim=%d'), EMBEDDING_DIM)
        except ImportError:
            logger.warning(str('pip install sentence-transformers>=2.7.0'))
        except Exception as e:
            logger.error(str('Embedder load failed: %s'), e)
    return _model

def embed_local(text):
    m = _load()
    if m is None: return None
    try:
        return m.encode(text, normalize_embeddings=True).tolist()
    except Exception as e:
        logger.warning(str('embed_local error: %s'), e)
        return None
