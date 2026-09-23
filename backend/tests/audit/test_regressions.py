from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import importlib
import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.app.db.models import Customer, Quote, QuoteItem, Product, User, ApprovalRequest, Invoice, Payment, FollowupTask, Communication
from backend.app.services.exceptions import ValidationError, NotFoundError
from backend.app.services.followup_service import create_followup
from backend.app.services.quote_service import calculate_discount_amount, calculate_quote_total
from backend.app.services.invoice_service import outstanding_balance, InvoiceService
from backend.app.db.repositories.approval_repository import ApprovalRepository
from backend.app.db.repositories.invoice_repository import InvoiceRepository
from backend.app.db.repositories.payment_repository import PaymentRepository
from backend.app.db.repositories.followup_repository import FollowupRepository
from backend.app.services.execution_service import require_logged_communication


def seed_quote(sessions, notes='Regular customer tier.'):
    with sessions() as db:
        customer = Customer(id=uuid4(), name='Ahmed', notes=notes)
        product = Product(id=uuid4(), name='Paper', sku='P-1', category='Office', unit_price=Decimal('100'), stock_quantity=10, reorder_threshold=2)
        quote = Quote(id=uuid4(), quote_number='Q-1', customer_id=customer.id, status='approved', subtotal=Decimal('100'), total=Decimal('100'), discount_percent=0, discount_amount=0)
        db.add_all([customer, product, quote]); db.flush()
        db.add(QuoteItem(quote_id=quote.id, product_id=product.id, quantity=1, unit_price=100, line_total=100))
        manager = User(id=uuid4(), email='manager@test.local', hashed_password='unused', full_name='Manager', role='manager', is_active=True)
        db.add(manager); db.commit()
        return customer.id, quote.id, manager.id


def test_currency_rounding_is_consistent():
    assert calculate_discount_amount(Decimal('.05'), Decimal('10')) == Decimal('.01')
    assert calculate_quote_total(Decimal('.05'), Decimal('10')) == Decimal('.04')


def test_discount_tool_commits_and_preferred_policy_is_server_owned(database, monkeypatch):
    from agents.tools import quote_tools
    _, quote_id, _ = seed_quote(database, 'Preferred customer tier - approved for up to 15% discount.')
    monkeypatch.setattr(quote_tools, 'SessionLocal', database)
    assert 'Error' not in quote_tools.apply_discount_to_quote.invoke({'quote_id': str(quote_id), 'discount_percent': 15})
    with database() as db:
        quote = db.get(Quote, quote_id)
        assert quote.total == Decimal('85')
        assert quote.status == 'approved'
    assert 'approval_threshold' not in quote_tools.apply_discount_to_quote.args
    assert 'Error' in quote_tools.apply_discount_to_quote.invoke({'quote_id': str(quote_id), 'discount_percent': 26})


@pytest.mark.parametrize('approved', [True, False])
def test_real_interrupt_resume_preserves_identity_and_does_not_replay(database, monkeypatch, approved):
    from agents.tools import quote_tools
    from agents.graph.state import AgentState
    node_module = importlib.import_module('agents.graph.nodes.create_quote_node')
    _, quote_id, manager_id = seed_quote(database)
    monkeypatch.setattr(quote_tools, 'SessionLocal', database)
    llm = Mock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content='', tool_calls=[{'name': 'apply_discount_to_quote', 'args': {'quote_id': str(quote_id), 'discount_percent': 20}, 'id': 'discount'}])
    monkeypatch.setattr(node_module, 'get_llm', lambda: llm)
    builder = StateGraph(AgentState)
    builder.add_node('quote', node_module.create_quote_node)
    builder.set_entry_point('quote'); builder.add_edge('quote', END)
    graph = builder.compile(checkpointer=MemorySaver())
    config = {'configurable': {'thread_id': 'actual-thread-not-request-id'}}
    initial = {'request_id': str(uuid4()), 'user_input': 'apply a 20% discount', 'entities': {}, 'messages': []}
    paused = graph.invoke(initial, config)
    approval_id = paused['__interrupt__'][0].value['approval_id']
    assert graph.get_state(config).next == ('quote',)
    from uuid import UUID
    with database() as db:
        record = db.get(ApprovalRequest, UUID(approval_id))
        assert record.action_payload['thread_id'] == config['configurable']['thread_id']
        quote = db.get(Quote, quote_id)
        assert quote.total == Decimal('100')
        assert quote.approval_id == record.id
        ApprovalRepository(db).resolve(record.id, 'approved' if approved else 'rejected', manager_id)
    result = graph.invoke(Command(resume={'approved': approved, 'approval_id': approval_id}), config)
    assert result['approval_decision'] == ('approved' if approved else 'rejected')
    assert not graph.get_state(config).next
    assert llm.invoke.call_count == 1
    with database() as db:
        assert db.query(ApprovalRequest).count() == 1
        quote = db.get(Quote, quote_id)
        assert quote.total == (Decimal('80') if approved else Decimal('100'))
        assert quote.status == 'approved'


def test_invalid_task_target_does_not_choose_first_customer(database):
    customer_id, quote_id, _ = seed_quote(database)
    future = datetime.now(timezone.utc) + timedelta(days=2)
    with database() as db:
        with pytest.raises(ValidationError):
            create_followup(db, 'manual_reminder', future, 'Ahmed')
        with pytest.raises(NotFoundError):
            create_followup(db, 'manual_reminder', future, uuid4())
        with pytest.raises(ValidationError):
            create_followup(db, 'manual_reminder', 'next Tuesday', customer_id)
        with pytest.raises(ValidationError):
            create_followup(db, 'manual_reminder', future.replace(tzinfo=None), customer_id)
        assert db.query(FollowupTask).count() == 0
        task = create_followup(db, 'quote_followup', future, customer_id, quote_id)
        assert task.customer_id == customer_id


def test_task_claim_is_conditional_and_stale_work_is_not_requeued(database):
    customer_id, _, _ = seed_quote(database)
    with database() as db:
        repo = FollowupRepository(db)
        task = repo.create('manual_reminder', datetime.now(timezone.utc), customer_id)
        task_id = task.id
        assert repo.mark_in_progress(task_id) is not None
    with database() as db:
        repo = FollowupRepository(db)
        assert repo.mark_in_progress(task_id) is None
        task = db.get(FollowupTask, task_id)
        assert task.attempt_count == 1
        task.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        assert repo.get_due_tasks() == []
        db.refresh(task)
        assert task.status == 'failed'


def test_duplicate_product_demand_and_ambiguous_mutation(database, monkeypatch):
    from agents.tools import inventory_tools
    seed_quote(database)
    monkeypatch.setattr(inventory_tools, 'SessionLocal', database)
    result = inventory_tools.check_fulfillment_feasibility.invoke({'items': '[{"product_id":"P-1","quantity":6},{"product_id":"Paper","quantity":6}]'})
    assert 'NOT FEASIBLE' in result
    assert 'Error' in inventory_tools.check_fulfillment_feasibility.invoke({'items': '[{"product_id":"P-1","quantity":1.9}]'})
    with database() as db:
        db.add(Product(id=uuid4(), sku='P-2', name='Paper Premium', category='Office', unit_price=200, stock_quantity=20, reorder_threshold=2)); db.commit()
    assert 'Ambiguous' in inventory_tools.update_inventory.invoke({'product_id': 'Paper', 'change_quantity': 5})
    with database() as db:
        assert db.query(Product).filter_by(sku='P-1').one().stock_quantity == 10


def test_invoice_balance_api_and_tool_agree(database, monkeypatch):
    customer_id, _, _ = seed_quote(database)
    with database() as db:
        invoice = Invoice(id=uuid4(), invoice_id='INV-1', customer_id=customer_id, amount=100, issue_date=date.today(), due_date=date.today()-timedelta(days=3), status='partially_paid')
        db.add(invoice); db.flush()
        db.add(Payment(invoice_id=invoice.id, amount=40, method='cash')); db.commit()
        invoice_id = invoice.id
    from backend.app.api.routes.invoices import _format_invoice, list_overdue_invoices
    from agents.tools import invoice_tools
    monkeypatch.setattr(invoice_tools, 'SessionLocal', database)
    with database() as db:
        invoice = InvoiceRepository(db).get_with_payments('INV-1')
        assert outstanding_balance(invoice) == Decimal('60')
        assert _format_invoice(invoice)['amount_due'] == 60
        assert len(list_overdue_invoices(None, db, {})) == 1
        invoice.status = 'cancelled'; db.commit()
        service = InvoiceService(InvoiceRepository(db), PaymentRepository(db))
        with pytest.raises(ValidationError):
            service.record_payment(invoice_id, Decimal('1'), 'cash')
    assert 'not overdue' in invoice_tools.get_days_overdue.invoke({'invoice_id': 'INV-1'})


def test_success_prose_is_not_evidence_of_communication(database):
    customer_id, _, _ = seed_quote(database)
    with database() as db:
        with pytest.raises(ValueError):
            require_logged_communication({'response': 'Email sent!', 'action_results': []}, db, customer_id)
        with pytest.raises(ValueError):
            require_logged_communication({'error': 'tool failed'}, db, customer_id)


def test_every_registered_tool_has_a_workflow_binding():
    from agents.tools import ALL_TOOLS
    getters = [('check_inventory_node','_get_tools_for_inventory'), ('check_invoice_node','_get_tools_for_invoice'),
               ('customer_mgmt_node','_get_tools_for_customer'), ('followup_node','_get_tools_for_followup'),
               ('create_quote_node','_get_tools_for_quote'), ('resolve_issue_node','_get_tools_for_issue')]
    bound = {tool.name for module, getter in getters for tool in getattr(importlib.import_module('agents.graph.nodes.'+module), getter)()}
    assert {tool.name for tool in ALL_TOOLS} == bound
