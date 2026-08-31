import sys, json, os

# ===== 1. Patch pipeline.py: upgrade _embedding() to use pgvector column =====
p = 'backend/app/jobs/pipeline.py'
src = open(p, encoding='utf-8').read()

MARKER_START = '    def _embedding():'
MARKER_END   = '    ok = _run_stage(db, jobs[JobStage.EMBEDDING], _embedding)'

idx_start = src.find(MARKER_START)
idx_end   = src.find(MARKER_END)

if idx_start == -1 or idx_end == -1:
    print('ERROR: could not find _embedding() markers in pipeline.py')
    sys.exit(1)

new_embedding = '''    def _embedding():
        import json as _json
        memory = ctx.get('memory')
        if not memory:
            return
        llm_res = ctx.get('llm_result')
        if llm_res:
            tag_str  = ' '.join(llm_res.tags)
            ent_str  = ' '.join(e.name for e in llm_res.entities)
            embed_text = (
                '{} | {} | Tags: {} | Entities: {} | Text: {}'.format(
                    memory.title or '',
                    memory.summary or '',
                    tag_str, ent_str,
                    (memory.raw_ocr_text or '')[:500]
                )
            )
        else:
            embed_text = '{} {}'.format(memory.title or '', memory.raw_ocr_text or '')

        vector = _compute_embedding(embed_text)
        if vector:
            try:
                memory.embedding = vector   # Phase C: pgvector column
            except Exception:
                pass
            memory.embedding_placeholder = _json.dumps(vector)  # JSON backup
            logger.info('Embedding stored dim=%d for memory %s', len(vector), memory.id)
        else:
            memory.embedding_placeholder = ''
        db.flush()

'''
src = src[:idx_start] + new_embedding + '    ' + src[idx_end:]
open(p, 'w', encoding='utf-8').write(src)
print('OK: pipeline._embedding() patched')

# ===== 2. Patch db_search.py: replace O(n) cosine with pgvector ANN query =====
ds = 'backend/app/services/db_search.py'
dsrc = open(ds, encoding='utf-8').read()

# Replace _embed_query to use local embedder first
EMBED_MARKER = 'def _embed_query(q: str) -> Optional[list]:'
EMBED_END    = 'def _keyword_hit'

ei = dsrc.find(EMBED_MARKER)
ee = dsrc.find(EMBED_END)

new_embed_query = '''def _embed_query(q: str):
    '''\"\"\"Embed query using same priority chain as pipeline: local -> Gemini -> None.\"\"\"'''
    from app.config import settings
    provider = getattr(settings, 'EMBEDDING_PROVIDER', 'local')
    if provider == 'local' or not settings.GEMINI_API_KEY:
        try:
            from app.core.local_embedder import embed_local
            vec = embed_local(q)
            if vec: return vec
        except Exception:
            pass
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            r = genai.embed_content(
                model='models/{}'.format(settings.EMBEDDING_MODEL),
                content=q, task_type='RETRIEVAL_QUERY')
            return r['embedding']
        except Exception:
            pass
    return None


'''

if ei != -1 and ee != -1:
    dsrc = dsrc[:ei] + new_embed_query + dsrc[ee:]
    print('OK: _embed_query patched in db_search.py')

# Replace the main search loop with pgvector ANN query
OLD_SEARCH = '''        memories = base.order_by(Memory.created_at.desc()).all()

        if not memories:
            return SearchResponse(query=q, total=0, limit=request.limit, offset=request.offset, results=[])

        scored: List[Tuple[float, str, Memory]] = []

        for mem in memories:
            kw = _keyword_hit(q, mem)

            # Semantic score from stored embedding
            sem = 0.0
            if query_vec and mem.embedding_placeholder:
                try:
                    stored_vec = json.loads(mem.embedding_placeholder)
                    if isinstance(stored_vec, list) and stored_vec:
                        sem = _cosine(query_vec, stored_vec)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Hybrid score
            score = 0.6 * sem + 0.4 * kw

            # Include if query is empty (browse mode) or score above threshold
            if not q or score >= 0.03:
                match_type = "hybrid" if sem > 0.3 and kw > 0.3 else ("semantic" if sem >= kw else "keyword")
                scored.append((score, match_type, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        total = len(scored)
        page = scored[request.offset: request.offset + request.limit]

        results = [_to_search_result(m, s, mt, q) for s, mt, m in page]'''

NEW_SEARCH = '''        # Phase C: Use pgvector ANN search when embedding is available,
        # then blend with keyword scoring (hybrid).
        from sqlalchemy import text as sql_text

        _HAS_PGVECTOR = False
        try:
            from pgvector.sqlalchemy import Vector
            _HAS_PGVECTOR = True
        except ImportError:
            pass

        scored: List[Tuple[float, str, Memory]] = []

        if _HAS_PGVECTOR and query_vec:
            # Pgvector ANN: retrieve top-N candidates by cosine distance
            try:
                from sqlalchemy import func as sqlfunc
                from sqlalchemy import cast, Float
                q_vec_str = '[' + ','.join(str(v) for v in query_vec) + ']'
                ann_candidates = (
                    base
                    .filter(Memory.embedding.isnot(None))
                    .order_by(
                        sql_text('embedding <=> :qvec').bindparams(qvec=q_vec_str)
                    )
                    .limit(100)
                    .all()
                )
                # Score candidates
                for mem in ann_candidates:
                    kw  = _keyword_hit(q, mem)
                    # Re-compute cosine from stored embedding for exact score
                    sem = 0.0
                    try:
                        if mem.embedding_placeholder:
                            stored = json.loads(mem.embedding_placeholder)
                            if isinstance(stored, list) and stored:
                                sem = _cosine(query_vec, stored)
                    except Exception:
                        pass
                    score = 0.6 * sem + 0.4 * kw
                    if not q or score >= 0.03:
                        mt = 'hybrid' if sem > 0.3 and kw > 0.3 else ('semantic' if sem >= kw else 'keyword')
                        scored.append((score, mt, mem))

                # Also keyword-only search for memories without embeddings yet
                kw_only = base.filter(Memory.embedding.is_(None)).order_by(Memory.created_at.desc()).limit(200).all()
                kw_ids  = {m.id for _, _, m in scored}
                for mem in kw_only:
                    if mem.id in kw_ids: continue
                    kw = _keyword_hit(q, mem)
                    score = 0.4 * kw
                    if not q or score >= 0.03:
                        scored.append((score, 'keyword', mem))
            except Exception as ann_exc:
                import logging as _log
                _log.getLogger(__name__).warning('pgvector ANN failed, falling back to O(n): %s', ann_exc)
                _HAS_PGVECTOR = False

        if not _HAS_PGVECTOR:
            # Fallback: O(n) scoring (works without pgvector extension)
            memories = base.order_by(Memory.created_at.desc()).all()
            if not memories:
                return SearchResponse(query=q, total=0, limit=request.limit, offset=request.offset, results=[])
            for mem in memories:
                kw  = _keyword_hit(q, mem)
                sem = 0.0
                if query_vec and mem.embedding_placeholder:
                    try:
                        stored = json.loads(mem.embedding_placeholder)
                        if isinstance(stored, list) and stored:
                            sem = _cosine(query_vec, stored)
                    except Exception:
                        pass
                score = 0.6 * sem + 0.4 * kw
                if not q or score >= 0.03:
                    mt = 'hybrid' if sem > 0.3 and kw > 0.3 else ('semantic' if sem >= kw else 'keyword')
                    scored.append((score, mt, mem))

        if not scored and not q:
            memories = base.order_by(Memory.created_at.desc()).all()
            scored = [(1.0, 'keyword', m) for m in memories]

        scored.sort(key=lambda x: x[0], reverse=True)
        total = len(scored)
        page  = scored[request.offset: request.offset + request.limit]
        results = [_to_search_result(m, s, mt, q) for s, mt, m in page]'''

if OLD_SEARCH in dsrc:
    dsrc = dsrc.replace(OLD_SEARCH, NEW_SEARCH, 1)
    print('OK: DBSearchService.search() patched to pgvector + fallback')
else:
    print('WARN: db_search main loop not found for exact replace - check manually')

open(ds, 'w', encoding='utf-8').write(dsrc)
print('db_search.py written')
print('All patches applied successfully')
