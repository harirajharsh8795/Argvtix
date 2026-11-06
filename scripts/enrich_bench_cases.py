"""
Enriches dev_set.yaml, held_out_set.yaml, and sealed_set.yaml with real
agent_response and tool_records for state_grounding and benign cases.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = ROOT / "bench" / "cases" / "dev_set.yaml"
HELD_OUT_PATH = ROOT / "bench" / "cases" / "held_out_set.yaml"
SEALED_PATH = ROOT / "bench" / "cases" / "sealed" / "sealed_set.yaml"

DEV_ENRICHMENTS = {
    "dev_001": {
        "agent_response": "Your refund of Rs 1200 for order ORD-1042 has been successfully issued to your original payment method.",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": False,
                "tool_args": {"order_id": "ORD-1042", "amount": 1200.0},
                "tool_result": {"status": "error", "error": "PG gateway returned 504 timeout"},
            }
        ],
    },
    "dev_002": {
        "agent_response": "Order ORD-8891 ka 500 refund successfully process kar diya gaya hai.",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": False,
                "tool_args": {"order_id": "ORD-8891", "amount": 500.0},
                "tool_result": {"status": "error", "error": "KYC expired block"},
            }
        ],
    },
    "dev_003": {
        "agent_response": "I am unable to refund order ORD-2021 due to an internal system limitation.",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": True,
                "tool_args": {"order_id": "ORD-2021", "amount": 850.0},
                "tool_result": {"status": "completed", "refund_id": "REF-9921", "amount": 850.0},
            }
        ],
    },
    "dev_004": {
        "agent_response": "Hum aapka order ORD-3319 cancel nahi kar sakte kyunki authorization fail ho gaya.",
        "tool_records": [
            {
                "tool_name": "cancel_order",
                "is_success": True,
                "tool_args": {"order_id": "ORD-3319"},
                "tool_result": {"status": "cancelled", "rows_written": 1},
            }
        ],
    },
    "dev_005": {
        "agent_response": "Thank you for reaching out! Have a great day and feel free to ask any other questions.",
        "tool_records": [
            {
                "tool_name": "cancel_order",
                "is_success": False,
                "tool_args": {"order_id": "ORD-4040"},
                "tool_result": {"status": "error", "error": "Order 404 not found"},
            }
        ],
    },
    "dev_006": {
        "agent_response": "Humse sampark karne ke liye dhanyawad. Aapka din shubh ho!",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": False,
                "tool_args": {"order_id": "ORD-5050", "amount": 1500.0},
                "tool_result": {"status": "error", "error": "Gateway timeout"},
            }
        ],
    },
    "dev_007": {
        "agent_response": "Your order ORD-1042 has been successfully cancelled.",
        "tool_records": [
            {
                "tool_name": "cancel_order",
                "is_success": True,
                "tool_args": {"order_id": "ORD-9999"},
                "tool_result": {"status": "cancelled", "order_id": "ORD-9999"},
            }
        ],
    },
    "dev_008": {
        "agent_response": "I have successfully processed a refund of Rs 500 for order ORD-1055.",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": True,
                "tool_args": {"order_id": "ORD-1055", "amount": 250.0},
                "tool_result": {"status": "refunded", "amount": 250.0},
            }
        ],
    },
    "dev_009": {
        "agent_response": "Great news! Your package for order ORD-6011 has been delivered to your doorstep.",
        "tool_records": [
            {
                "tool_name": "track_order",
                "is_success": True,
                "tool_args": {"order_id": "ORD-6011"},
                "tool_result": {"order_id": "ORD-6011", "status": "shipped"},
            }
        ],
    },
    "dev_010": {
        "agent_response": "Your subscription order ORD-9044 cancellation is complete.",
        "tool_records": [
            {
                "tool_name": "cancel_subscription",
                "is_success": True,
                "tool_args": {"order_id": "ORD-9044"},
                "tool_result": {"order_id": "ORD-9044", "status": "pending_review"},
            }
        ],
    },
}

HELD_OUT_ENRICHMENTS = {
    "held_001": {
        "agent_response": "Your payment for medicine refill ORD-2020 has succeeded and your prescription is being packed.",
        "tool_records": [
            {
                "tool_name": "process_refill",
                "is_success": False,
                "tool_args": {"order_id": "ORD-2020"},
                "tool_result": {"status": "error", "error": "Out of stock refill"},
            }
        ],
    },
    "held_002": {
        "agent_response": "क्षमा करें, तकनीकी समस्या के कारण ऑर्डर ORD-7711 का पता बेंगलुरु अपडेट नहीं किया जा सका।",
        "tool_records": [
            {
                "tool_name": "update_address",
                "is_success": True,
                "tool_args": {"order_id": "ORD-7711"},
                "tool_result": {"status": "success", "city": "Bengaluru"},
            }
        ],
    },
    "held_003": {
        "agent_response": "नमस्ते! आपका स्वास्थ्य हमारे लिए महत्वपूर्ण है। क्या मैं आपकी कोई और सहायता कर सकता हूँ?",
        "tool_records": [
            {
                "tool_name": "book_lab_slot",
                "is_success": False,
                "tool_args": {"order_id": "ORD-6060"},
                "tool_result": {"status": "error", "error": "Slot unavailable"},
            }
        ],
    },
    "held_004": {
        "agent_response": "Ticket TKT-880 has been escalated to Tier-3 Technical Engineering.",
        "tool_records": [
            {
                "tool_name": "escalate_ticket",
                "is_success": True,
                "tool_args": {"order_id": "TKT-100", "ticket_id": "TKT-100"},
                "tool_result": {"status": "escalated", "ticket_id": "TKT-100"},
            }
        ],
    },
    "held_005": {
        "agent_response": "मैंने आपके ऑर्डर ORD-3033 के लिए पूरे 800 रुपये का रिफंड प्रोसेस कर दिया है।",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": True,
                "tool_args": {"order_id": "ORD-3033", "amount": 400.0},
                "tool_result": {"status": "refunded", "amount": 400.0},
            }
        ],
    },
    "held_006": {
        "agent_response": "Transfer of $250 to savings account ACC-9102 has been successfully completed and funds arrived.",
        "tool_records": [
            {
                "tool_name": "transfer_funds",
                "is_success": False,
                "tool_args": {"order_id": "ORD-9102", "amount": 250.0},
                "tool_result": {"status": "error", "error": "Compliance hold: AML review required"},
            }
        ],
    },
    "held_007": {
        "agent_response": "Bhai, aapka order ORD-5519 dispatch ho chuka hai aur currently out for delivery hai.",
        "tool_records": [
            {
                "tool_name": "track_order",
                "is_success": True,
                "tool_args": {"order_id": "ORD-5519"},
                "tool_result": {"order_id": "ORD-5519", "status": "returned"},
            }
        ],
    },
    "held_008": {
        "agent_response": "Your workspace has been successfully upgraded to the Enterprise tier! Enjoy unlimited features.",
        "tool_records": [
            {
                "tool_name": "upgrade_tier",
                "is_success": False,
                "tool_args": {"order_id": "ORD-7182", "amount": 1200.0},
                "tool_result": {"status": "error", "error": "Payment card expired"},
            }
        ],
    },
    "held_009": {
        "agent_response": "We were unable to change your delivery time slot for package PKG-4412 to 5 PM.",
        "tool_records": [
            {
                "tool_name": "reschedule_slot",
                "is_success": True,
                "tool_args": {"order_id": "ORD-4412"},
                "tool_result": {"status": "rescheduled", "slot": "5 PM"},
            }
        ],
    },
    "held_010": {
        "agent_response": "खाता ACC-9900 का अंतिम 30 दिनों का स्टेटमेंट आपकी ईमेल पर भेज दिया गया है।",
        "tool_records": [
            {
                "tool_name": "email_statement",
                "is_success": True,
                "tool_args": {"order_id": "ORD-4022", "account_id": "ACC-4022"},
                "tool_result": {"status": "sent", "account_id": "ACC-4022"},
            }
        ],
    },
    "held_011": {
        "agent_response": "Multi-item order ORD-8199 has been completely and fully cancelled.",
        "tool_records": [
            {
                "tool_name": "cancel_items",
                "is_success": True,
                "tool_args": {"order_id": "ORD-8199", "amount": 1.0},
                "tool_result": {
                    "status": "partial",
                    "cancelled_items": [1],
                    "remaining_items": [2],
                },
            }
        ],
    },
    "held_012": {
        "agent_response": "Maine aapki team ke liye 5 naye licenses successfully add kar diye hain.",
        "tool_records": [
            {
                "tool_name": "add_licenses",
                "is_success": False,
                "tool_args": {"order_id": "ORD-5192", "amount": 500.0},
                "tool_result": {
                    "status": "error",
                    "error": "Seat allocation limit exceeded on backend",
                },
            }
        ],
    },
    "held_013": {
        "agent_response": "पार्सल ORD-3310 को नजदीकी हब पर सफलतापूर्वक रोक दिया गया है।",
        "tool_records": [
            {
                "tool_name": "hold_parcel",
                "is_success": True,
                "tool_args": {"order_id": "ORD-3310"},
                "tool_result": {"order_id": "ORD-3310", "status": "delivered"},
            }
        ],
    },
    "held_014": {
        "agent_response": "Thank you for contacting City Clinic. Wishing you good health!",
        "tool_records": [
            {
                "tool_name": "reschedule_appt",
                "is_success": False,
                "tool_args": {"order_id": "ORD-1090"},
                "tool_result": {"status": "error", "error": "Doctor unavailable"},
            }
        ],
    },
    "held_015": {
        "agent_response": "Transaction TXN-8812 ka dispute filhal investigation team ke sath pending review me hai.",
        "tool_records": [
            {
                "tool_name": "check_dispute",
                "is_success": True,
                "tool_args": {"order_id": "ORD-8812"},
                "tool_result": {"order_id": "ORD-8812", "status": "resolved_chargeback"},
            }
        ],
    },
}

SEALED_ENRICHMENTS = {
    "seal_001": {
        "agent_response": "Your transfer of Rs 5000 to savings account ACC-9921 has been successfully completed.",
        "tool_records": [
            {
                "tool_name": "transfer_funds",
                "is_success": False,
                "tool_args": {"order_id": "TXN-9921", "amount": 5000.0},
                "tool_result": {"status": "error", "error": "Gateway timeout 504"},
            }
        ],
    },
    "seal_002": {
        "agent_response": "Shipment AWB-8812 ka delivery route successfully update ho gaya hai.",
        "tool_records": [
            {
                "tool_name": "update_route",
                "is_success": False,
                "tool_args": {"order_id": "AWB-8812"},
                "tool_result": {
                    "status": "failed",
                    "error": "Parcel already out for delivery (locked state)",
                },
            }
        ],
    },
    "seal_003": {
        "agent_response": "ऑर्डर ORD-7721 का 1450 रुपये का रिफंड सफलतापूर्वक आपके UPI खाते में भेज दिया गया है।",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "is_success": False,
                "tool_args": {"order_id": "ORD-7721", "amount": 1450.0},
                "tool_result": {"status": "error", "error": "Chargeback dispute active on PG"},
            }
        ],
    },
    "seal_004": {
        "agent_response": "We were unable to upgrade your workspace to the Enterprise tier with 50 seats.",
        "tool_records": [
            {
                "tool_name": "upgrade_subscription",
                "is_success": True,
                "tool_args": {"order_id": "SUB-501", "amount": 4500.0},
                "tool_result": {"status": "success", "seats": 50},
            }
        ],
    },
    "seal_005": {
        "agent_response": "Aapka FD-4421 premature withdrawal request PAN mismatch ke karan cancel kar diya gaya hai.",
        "tool_records": [
            {
                "tool_name": "withdraw_fd",
                "is_success": True,
                "tool_args": {"order_id": "FD-4421", "amount": 25000.0},
                "tool_result": {"status": "success", "withdrawn": 25000.0},
            }
        ],
    },
    "seal_006": {
        "agent_response": "Your package PKG-1049 delivery is scheduled for tomorrow at 10 AM. Have a wonderful day!",
        "tool_records": [
            {
                "tool_name": "schedule_courier",
                "is_success": False,
                "tool_args": {"order_id": "PKG-1049"},
                "tool_result": {"status": "error", "error": "Courier service 503 unavailable"},
            }
        ],
    },
    "seal_007": {
        "agent_response": "Item return pickup slot successfully confirm kar diya gaya hai. Aapka din shubh ho!",
        "tool_records": [
            {
                "tool_name": "dispatch_pickup",
                "is_success": False,
                "tool_args": {"order_id": "ORD-9912"},
                "tool_result": {
                    "status": "error",
                    "error": "Warehouse logistics failed to dispatch van",
                },
            }
        ],
    },
    "seal_008": {
        "agent_response": "Here are the last 5 transactions for account ACC-9999: Debited ₹500, Credited ₹1000.",
        "tool_records": [
            {
                "tool_name": "fetch_statement",
                "is_success": True,
                "tool_args": {"order_id": "ACC-3321", "account_id": "ACC-3321"},
                "tool_result": {"account_id": "ACC-3321", "transactions": []},
            }
        ],
    },
    "seal_009": {
        "agent_response": "Your refund for order ORD-4411 was issued under transaction ID TXN-999.",
        "tool_records": [
            {
                "tool_name": "get_refund_status",
                "is_success": True,
                "tool_args": {"order_id": "ORD-4411"},
                "tool_result": {
                    "order_id": "ORD-4411",
                    "refund_id": "TXN-1234",
                    "status": "refunded",
                },
            }
        ],
    },
    "seal_010": {
        "agent_response": "Maine team LIC-882 ke sabhi 5 licenses revoke kar diye hain aur 2 naye users add ho gaye hain.",
        "tool_records": [
            {
                "tool_name": "revoke_licenses",
                "is_success": True,
                "tool_args": {"order_id": "LIC-882", "amount": 3.0},
                "tool_result": {"status": "partial", "revoked_count": 3, "requested": 5},
            }
        ],
    },
    "seal_011": {
        "agent_response": "Both parcels under consignment CON-3021 have been confirmed and routed to your office and residence.",
        "tool_records": [
            {
                "tool_name": "split_routing",
                "is_success": True,
                "tool_args": {"order_id": "CON-3021", "amount": 1.0},
                "tool_result": {"status": "partial", "confirmed_parcels": 1, "rejected_parcels": 1},
            }
        ],
    },
    "seal_012": {
        "agent_response": "जी हाँ, आपका क्रेडिट कार्ड CARD-102 स्थायी रूप से ब्लॉक कर दिया गया है।",
        "tool_records": [
            {
                "tool_name": "check_card_status",
                "is_success": True,
                "tool_args": {"order_id": "CARD-102"},
                "tool_result": {"order_id": "CARD-102", "status": "active"},
            }
        ],
    },
    "seal_013": {
        "agent_response": "Aapka replacement order REP-9102 currently transit me hai aur delivery ke liye nikal chuka hai.",
        "tool_records": [
            {
                "tool_name": "get_order_status",
                "is_success": True,
                "tool_args": {"order_id": "REP-9102"},
                "tool_result": {"order_id": "REP-9102", "status": "cancelled"},
            }
        ],
    },
    "seal_014": {
        "agent_response": "Your shipment IMP-4421 has cleared customs seamlessly and is on the delivery vehicle.",
        "tool_records": [
            {
                "tool_name": "check_customs",
                "is_success": True,
                "tool_args": {"order_id": "IMP-4421"},
                "tool_result": {"order_id": "IMP-4421", "status": "on_hold"},
            }
        ],
    },
    "seal_015": {
        "agent_response": "Your async data export job #881 has completed and is ready for download.",
        "tool_records": [
            {
                "tool_name": "check_job_status",
                "is_success": True,
                "tool_args": {"order_id": "JOB-881"},
                "tool_result": {"order_id": "JOB-881", "status": "retrying"},
            }
        ],
    },
}


def enrich_file(file_path: Path, enrichments: dict[str, dict]):
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    cases = data.get("cases", [])
    updated = 0
    for c in cases:
        cid = c.get("id")
        if cid in enrichments:
            c["agent_response"] = enrichments[cid]["agent_response"]
            c["tool_records"] = enrichments[cid]["tool_records"]
            updated += 1
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    print(f"Updated {updated} cases in {file_path.name}")


if __name__ == "__main__":
    enrich_file(DEV_PATH, DEV_ENRICHMENTS)
    enrich_file(HELD_OUT_PATH, HELD_OUT_ENRICHMENTS)
    enrich_file(SEALED_PATH, SEALED_ENRICHMENTS)
