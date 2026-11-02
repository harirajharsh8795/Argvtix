"""
ShopOps Policy Document Store
Static policy text used by the RAG retriever.
These represent internal SOPs the AI agent must follow.
"""

POLICY_DOCUMENTS = [
    {
        "id": "pol_refund_01",
        "title": "Refund Policy — Eligibility Window",
        "content": (
            "Customers are eligible for a full refund within 7 days of delivery. "
            "Items must be unused, in original packaging, with receipt. "
            "Electronics have a 30-day replacement window but no cash refund after 7 days. "
            "Sale items marked 'Final Sale' are non-refundable."
        ),
        "tags": ["refund", "eligibility", "policy"],
    },
    {
        "id": "pol_refund_02",
        "title": "Refund Policy — Approval Threshold",
        "content": (
            "Refund amounts above Rs 10,000 require supervisor approval before processing. "
            "AI agents must not auto-approve refunds exceeding Rs 10,000. "
            "The agent must route such requests to the human approval queue. "
            "Refunds below Rs 10,000 can be auto-processed if all eligibility criteria are met."
        ),
        "tags": ["refund", "approval", "threshold", "supervisor"],
    },
    {
        "id": "pol_refund_03",
        "title": "Refund Policy — Duplicate Prevention",
        "content": (
            "A refund can only be issued once per order. "
            "If a refund has already been processed for an order, no further refund is allowed. "
            "Agent must check existing refund records before processing any new refund request. "
            "Duplicate refund attempts must be blocked and flagged for review."
        ),
        "tags": ["refund", "duplicate", "prevention"],
    },
    {
        "id": "pol_cancel_01",
        "title": "Order Cancellation Policy",
        "content": (
            "Orders can be cancelled free of charge before dispatch/shipment. "
            "Once an order is marked 'shipped', cancellation is not possible. "
            "Customer will receive a full refund within 5-7 business days upon successful cancellation. "
            "For bulk orders above 10 units, cancellation requires supervisor approval."
        ),
        "tags": ["cancel", "order", "dispatch"],
    },
    {
        "id": "pol_inventory_01",
        "title": "Inventory Management Policy",
        "content": (
            "Inventory counts must be decremented immediately upon order placement. "
            "For returns and cancellations, inventory must be restocked within 24 hours. "
            "Inventory adjustments above 50 units require manager approval. "
            "Negative inventory counts are strictly prohibited and must be flagged immediately."
        ),
        "tags": ["inventory", "stock", "restock"],
    },
    {
        "id": "pol_pii_01",
        "title": "Data Privacy & PII Policy",
        "content": (
            "Customer Personally Identifiable Information (PII) must never appear in AI responses. "
            "PII includes: Aadhaar number, PAN card, phone number, email address, bank account details. "
            "All customer identifiers must be referenced by internal IDs, not raw PII values. "
            "Any accidental PII exposure must be immediately logged as a security incident."
        ),
        "tags": ["pii", "privacy", "security", "aadhaar"],
    },
    {
        "id": "pol_balance_01",
        "title": "Balance & Statement Inquiry Policy",
        "content": (
            "Customer wallet balance and transaction history are read-only operations. "
            "Balance inquiries do not require supervisor approval. "
            "Only the account holder (verified by customer_id) can view their own balance. "
            "Statement history is limited to last 90 days in customer-facing responses."
        ),
        "tags": ["balance", "wallet", "statement", "read-only"],
    },
    {
        "id": "pol_subscription_01",
        "title": "Subscription Change Policy",
        "content": (
            "Subscription plan changes take effect from the next billing cycle. "
            "Downgrades are immediately effective and partial refunds are issued pro-rata. "
            "Upgrades above Rs 5,000/month require billing verification. "
            "Free trial subscriptions cannot be upgraded until the trial period ends."
        ),
        "tags": ["subscription", "upgrade", "downgrade", "billing"],
    },
]
