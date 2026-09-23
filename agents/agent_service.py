"""Agent invocation, serialized approval resumption, and execution telemetry."""
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import text, create_engine
from sqlalchemy.pool import NullPool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
from agents.graph.graph import agent_graph
from backend.app.db.database import SessionLocal, engine
from backend.app.db.models.agent_run import AgentRun
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.approval_request import ApprovalRequest
from backend.app.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)
_lock_engine = create_engine(engine.url, poolclass=NullPool, pool_pre_ping=True)


@contextmanager
def _thread_lock(thread_id):
    # Transaction-scoped advisory lock is released even if invocation raises.
    # It serializes only this checkpoint thread, not unrelated agent requests.
    key = int.from_bytes(sha256(thread_id.encode()).digest()[:8], 'big', signed=True)
    # A dedicated connection cannot exhaust the normal tool-session pool while
    # waiting on an LLM. NullPool closes it as soon as this invocation ends.
    with _lock_engine.begin() as conn:
        if not conn.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': key}):
            raise ValueError('This conversation is already being processed; retry shortly.')
        yield


def _result(state, thread_id, request_id=None):
    interruptions = state.get('__interrupt__') or []
    pending = interruptions[0].value if interruptions else {}
    approval_id = pending.get('approval_id') or state.get('approval_id')
    required = bool(pending) or state.get('approval_required', False)
    return {'request_id': state.get('request_id', request_id), 'thread_id': thread_id,
            'response': state.get('response') or ('Manager approval required; the operation is paused.' if pending else 'No response generated.'),
            'workflow': state.get('workflow'), 'intent': state.get('intent'),
            'entities': state.get('entities', {}), 'action_results': state.get('action_results', []),
            'approval_required': required, 'approval_id': approval_id,
            'approval_decision': state.get('approval_decision'), 'error': state.get('error')}


def _record_run(result, user_input=''):
    try:
        request_id = result['request_id']
        run_id = uuid5(NAMESPACE_URL, 'officehub:run:' + request_id)
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run is None:
                run = AgentRun(id=run_id, request_id=request_id, started_at=datetime.now(timezone.utc))
                db.add(run)
            run.intent = result.get('intent')
            run.error = result.get('error')
            run.status = ('failed' if run.error else 'waiting_approval' if result.get('approval_required') and not result.get('approval_decision') else 'completed')
            run.completed_at = None if run.status == 'waiting_approval' else datetime.now(timezone.utc)
            db.flush()
            for action in result.get('action_results') or [{'tool': None, 'result': result['response']}]:
                db.add(AuditLog(id=uuid4(), run_id=run_id, node=result.get('workflow') or 'agent',
                                tool=action.get('tool'), input={'user_input': user_input, 'args': action.get('args', {})},
                                output={'result': str(action.get('result', ''))}, error=run.error,
                                approval_status=result.get('approval_decision'), timestamp=datetime.now(timezone.utc)))
            if result.get('approval_id'):
                approval = db.get(ApprovalRequest, UUID(result['approval_id']))
                if approval:
                    approval.run_id = run_id
            db.commit()
    except Exception:
        logger.exception('Failed to persist agent telemetry')


def _begin_run(request_id):
    try:
        with SessionLocal() as db:
            run_id = uuid5(NAMESPACE_URL, 'officehub:run:' + request_id)
            if db.get(AgentRun, run_id) is None:
                db.add(AgentRun(id=run_id, request_id=request_id, status='running', started_at=datetime.now(timezone.utc)))
                db.commit()
    except Exception:
        logger.exception('Failed to record agent start')


def run_agent(user_input: str, conversation_id=None, request_id=None, conversation_history=None, thread_id=None) -> dict:
    request_id = request_id or str(uuid4())
    thread_id = thread_id or conversation_id or request_id
    config = {'configurable': {'thread_id': thread_id}}
    initial = {'request_id': request_id, 'user_input': user_input, 'conversation_id': conversation_id,
               'intent': None, 'workflow': None, 'entities': {}, 'action_plan': [], 'action_results': [],
               'approval_required': False, 'approval_id': None, 'approval_decision': None,
               'response': None, 'error': None, 'messages': (conversation_history or [])[-20:]}
    with _thread_lock(thread_id):
        snapshot = agent_graph.get_state(config)
        if snapshot.next or any(task.error or task.interrupts for task in snapshot.tasks):
            raise ValueError('This conversation has a pending operation; resolve it before sending another request.')
        state = initial
        _begin_run(request_id)
        try:
            state = agent_graph.invoke(initial, config=config)
            result = _result(state, thread_id, request_id)
        except Exception as exc:
            logger.exception('Agent invocation failed')
            result = _result({**initial, 'error': str(exc), 'response': 'The request failed; check the error and retry.'}, thread_id)
        _record_run(result, user_input)
        if not state.get('__interrupt__') and not result.get('error'):
            agent_graph.update_state(config, {'messages': [HumanMessage(content=user_input, id=request_id + ':user'),
                                                          AIMessage(content=result['response'], id=request_id + ':assistant')]})
        return result


def resume_agent(approval_id: str, approved: bool, thread_id=None, comment='', reviewer_id=None) -> dict:
    with SessionLocal() as db:
        record = ApprovalService(db).get_approval(approval_id)
        if record is None:
            raise ValueError('Approval not found.')
        saved_thread = record.action_payload.get('thread_id')
        if not saved_thread or (thread_id and thread_id != saved_thread):
            raise ValueError('Approval has no matching checkpoint thread.')
    with _thread_lock(saved_thread):
        with SessionLocal() as db:
            service = ApprovalService(db)
            record = service.approve(approval_id, reviewer_id) if approved else service.reject(approval_id, reviewer_id)
            payload = dict(record.action_payload)
            if payload.get('final_result'):
                return payload['final_result']
            payload['review_comment'] = comment
            record.action_payload = payload
            db.commit()
        config = {'configurable': {'thread_id': saved_thread}}
        snapshot = agent_graph.get_state(config)
        if not snapshot.next and not any(task.error or task.interrupts for task in snapshot.tasks):
            # Recover a crash between graph completion and response persistence.
            if snapshot.values.get('approval_id') != approval_id or not snapshot.values.get('approval_decision'):
                raise ValueError('No resumable checkpoint matches this approval.')
            state = snapshot.values
        else:
            pending_ids = {i.value.get('approval_id') for task in snapshot.tasks for i in task.interrupts if isinstance(i.value, dict)}
            if pending_ids and approval_id not in pending_ids:
                raise ValueError('Checkpoint is waiting for a different approval.')
            if snapshot.values.get('request_id') != payload['request_id']:
                raise ValueError('Checkpoint belongs to another request.')
            command = Command(resume={'approved': approved, 'approval_id': approval_id,
                                      'reviewer_id': reviewer_id, 'comment': comment}) if pending_ids else None
            try:
                state = agent_graph.invoke(command, config=config)
            except Exception as exc:
                logger.exception('Approval execution failed; the same decision can be retried')
                _record_run(_result({**snapshot.values, 'error': str(exc),
                                     'approval_id': approval_id, 'approval_required': True,
                                     'approval_decision': 'approved' if approved else 'rejected',
                                     'response': 'Execution failed; retry the same approval decision.'}, saved_thread))
                raise
        result = _result(state, saved_thread)
        if result.get('error'):
            # Preserve the decision and surface failure; never claim execution.
            logger.error('Approved workflow failed: %s', result['error'])
        with SessionLocal() as db:
            record = db.get(ApprovalRequest, UUID(approval_id))
            record.action_payload = {**record.action_payload, 'final_result': result}
            db.commit()
        _record_run(result)
        return result
