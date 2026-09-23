from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import Mock
import importlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.app.db.models import User, Customer, ApprovalRequest, Quote
from backend.app.api.dependencies import get_db
from backend.app.api.router import api_router
from agents.graph.state import AgentState
from test_regressions import seed_quote


@pytest.fixture
def client(database):
    app = FastAPI()
    app.include_router(api_router)
    def sessions():
        with database() as db:
            yield db
    app.dependency_overrides[get_db] = sessions
    with TestClient(app) as client:
        yield client


def test_demo_identity_uses_database_role_and_ignores_reviewer_body(database, client, monkeypatch):
    _, _, manager_id = seed_quote(database)
    staff_id, approval_id = uuid4(), uuid4()
    with database() as db:
        db.add(User(id=staff_id, email='staff@test.local', hashed_password='unused', full_name='Staff', role='staff', is_active=True))
        db.add(ApprovalRequest(id=approval_id, action_type='refund_approval', action_payload={}, reason='test', status='pending'))
        db.commit()
    assert client.get('/api/v1/customers').status_code == 401
    assert client.get('/api/v1/customers', headers={'X-User-Id': 'not-a-uuid'}).status_code == 401
    assert client.post(f'/api/v1/approvals/{approval_id}/approve', headers={'X-User-Id': str(staff_id), 'X-User-Role': 'admin'}).status_code == 403
    routes = importlib.import_module('backend.app.api.routes.approvals')
    resume = Mock(return_value={'response': 'Decision recorded', 'approval_decision': 'approved'})
    monkeypatch.setattr(routes, 'resume_agent', resume)
    response = client.post(f'/api/v1/approvals/{approval_id}/approve', headers={'X-User-Id': str(manager_id), 'X-User-Role': 'staff'}, json={'approved_by': str(staff_id)})
    assert response.status_code == 200
    assert resume.call_args.kwargs['reviewer_id'] == str(manager_id)


def test_customer_limit_tier_quote_shapes_and_status_filters(database, client):
    _, quote_id, manager_id = seed_quote(database, 'Preferred customer tier - approved for up to 15% discount.')
    with database() as db:
        db.add(Customer(id=uuid4(), name='Ahmed Second')); db.commit()
    headers = {'X-User-Id': str(manager_id)}
    response = client.get('/api/v1/customers?query=Ahmed&limit=1', headers=headers)
    assert len(response.json()) == 1
    assert response.json()[0]['tier'] == 'preferred'
    assert client.get('/api/v1/customers?limit=-1', headers=headers).status_code == 422
    quote = client.get(f'/api/v1/quotes/{quote_id}', headers=headers).json()
    listed = client.get('/api/v1/quotes?status=approved', headers=headers).json()[0]
    assert quote == listed
    for path in ['quotes', 'orders', 'invoices']:
        assert client.get(f'/api/v1/{path}?status=invalid', headers=headers).status_code == 422


def test_task_api_rejects_invalid_identity_and_timezone(database, client):
    customer_id, _, manager_id = seed_quote(database)
    headers = {'X-User-Id': str(manager_id)}
    body = {'task_type': 'manual_reminder', 'scheduled_at': '2099-01-01T09:00:00+05:00', 'customer_id': 'Ahmed'}
    assert client.post('/api/v1/tasks', json=body, headers=headers).status_code == 422
    body['customer_id'] = str(customer_id)
    body['scheduled_at'] = '2099-01-01T09:00:00'
    assert client.post('/api/v1/tasks', json=body, headers=headers).status_code == 422
    body['scheduled_at'] += '+05:00'
    response = client.post('/api/v1/tasks', json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()['customer_id'] == str(customer_id)


def test_facade_resume_can_retry_execution_failure_without_replaying_llm(database, monkeypatch):
    from agents import agent_service
    from agents.tools import quote_tools
    from backend.app.services.quote_service import QuoteService
    module = importlib.import_module('agents.graph.nodes.create_quote_node')
    _, quote_id, manager_id = seed_quote(database)
    monkeypatch.setattr(quote_tools, 'SessionLocal', database)
    monkeypatch.setattr(agent_service, 'SessionLocal', database)
    monkeypatch.setattr(agent_service, '_thread_lock', lambda key: nullcontext())
    llm = Mock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content='', tool_calls=[{'name': 'apply_discount_to_quote', 'args': {'quote_id': str(quote_id), 'discount_percent': 20}, 'id': 'd'}])
    monkeypatch.setattr(module, 'get_llm', lambda: llm)
    builder = StateGraph(AgentState)
    builder.add_node('quote', module.create_quote_node)
    builder.set_entry_point('quote'); builder.add_edge('quote', END)
    graph = builder.compile(checkpointer=MemorySaver())
    monkeypatch.setattr(agent_service, 'agent_graph', graph)
    config = {'configurable': {'thread_id': 'retry-test'}}
    result = graph.invoke({'request_id': str(uuid4()), 'user_input': 'apply 20% discount', 'entities': {}, 'messages': []}, config)
    approval_id = result['__interrupt__'][0].value['approval_id']
    apply = QuoteService.apply_discount
    monkeypatch.setattr(QuoteService, 'apply_discount', Mock(side_effect=RuntimeError('temporary failure')))
    with pytest.raises(RuntimeError, match='temporary'):
        agent_service.resume_agent(approval_id, True, reviewer_id=str(manager_id))
    monkeypatch.setattr(QuoteService, 'apply_discount', apply)
    resumed = agent_service.resume_agent(approval_id, True, reviewer_id=str(manager_id))
    assert resumed['approval_decision'] == 'approved'
    assert agent_service.resume_agent(approval_id, True, reviewer_id=str(manager_id)) == resumed
    assert llm.invoke.call_count == 1
    with database() as db:
        assert db.get(Quote, quote_id).total == Decimal('80')


def test_workflow_rejects_unbound_tool_and_preserves_clarification(monkeypatch):
    module = importlib.import_module('agents.graph.nodes.customer_mgmt_node')
    llm = Mock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [AIMessage(content='', tool_calls=[{'name': 'update_inventory', 'args': {}, 'id': 'x'}]), AIMessage(content='Which customer?')]
    monkeypatch.setattr(module, 'get_llm', lambda: llm)
    result = module.customer_mgmt_node({'user_input': 'update customer', 'messages': []})
    assert 'unavailable' in result['action_results'][0]['result']
    assert result['action_results'][-1]['result'] == 'Which customer?'


def test_inventory_runs_dependent_tool_rounds(monkeypatch):
    module = importlib.import_module('agents.graph.nodes.check_inventory_node')
    first, second = Mock(), Mock()
    first.name = 'get_low_stock_products'; first.invoke.return_value = 'P-1 has low stock'
    second.name = 'update_inventory'; second.invoke.return_value = 'Adjusted P-1'
    monkeypatch.setattr(module, '_get_tools_for_inventory', lambda: [first, second])
    llm = Mock(); llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [AIMessage(content='', tool_calls=[{'name': first.name, 'args': {}, 'id': '1'}]),
                              AIMessage(content='', tool_calls=[{'name': second.name, 'args': {'product_id': 'P-1', 'change_quantity': 10}, 'id': '2'}]), AIMessage(content='Done')]
    monkeypatch.setattr(module, 'get_llm', lambda: llm)
    result = module.check_inventory_node({'user_input': 'restock low items', 'messages': []})
    second.invoke.assert_called_once()
    assert len(result['action_results']) == 3


def test_llm_constructor_failure_uses_fallback(monkeypatch):
    module = importlib.import_module('agents.graph.nodes.classify_intent')
    monkeypatch.setattr(module, '_get_llm', Mock(side_effect=RuntimeError('missing key')))
    assert module.classify_intent({'user_input': 'Remind Ahmed about his overdue invoice'})['intent'] == 'follow_up'


def test_full_graph_records_runs_nodes_tools_and_conversation(database, monkeypatch):
    from agents import agent_service
    from agents.graph.graph import build_graph
    from agents.tools import inventory_tools
    from backend.app.core import audit
    from backend.app.db.models import AgentRun, AuditLog
    seed_quote(database)
    monkeypatch.setattr(agent_service, 'SessionLocal', database)
    monkeypatch.setattr(audit, 'SessionLocal', database)
    monkeypatch.setattr(inventory_tools, 'SessionLocal', database)
    monkeypatch.setattr(agent_service, '_thread_lock', lambda key: nullcontext())
    monkeypatch.setattr(agent_service, 'agent_graph', build_graph(MemorySaver()))
    for module_name, content in [('classify_intent', 'inventory_check'), ('identify_entities', '{}')]:
        module = importlib.import_module('agents.graph.nodes.' + module_name)
        llm = Mock(); llm.invoke.return_value = AIMessage(content=content)
        monkeypatch.setattr(module, '_get_llm', lambda llm=llm: llm)
    inventory = importlib.import_module('agents.graph.nodes.check_inventory_node')
    llm = Mock(); llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [AIMessage(content='', tool_calls=[{'name': 'get_all_products', 'args': {}, 'id': 'catalog'}]), AIMessage(content='Paper is available.')]
    monkeypatch.setattr(inventory, 'get_llm', lambda: llm)
    response_node = importlib.import_module('agents.graph.nodes.formulate_response')
    final_llm = Mock(); final_llm.invoke.return_value = AIMessage(content='Paper is available.')
    monkeypatch.setattr(response_node, 'get_llm', lambda **kwargs: final_llm)
    result = agent_service.run_agent('List products', thread_id='history-test')
    assert not result['error']
    with database() as db:
        run = db.query(AgentRun).one()
        assert run.status == 'completed'
        assert db.query(AuditLog).filter(AuditLog.run_id == run.id).count() >= 7
    state = agent_service.agent_graph.get_state({'configurable': {'thread_id': 'history-test'}})
    assert state.values['messages'][-2].content == 'List products'
    assert state.values['messages'][-1].content == 'Paper is available.'
