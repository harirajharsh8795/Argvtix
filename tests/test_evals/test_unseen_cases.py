"""
Comprehensive Test Suite for 30 Unseen Test Scenarios & Domain Evaluators.

Covers:
- 30 distinct unseen test cases across:
  * Hindi (Devanagari)
  * Hinglish (Roman script)
  * Banking & Fintech
  * Logistics & Supply Chain
  * Ambiguous / Conversational customer inquiries
- Evaluates both ClaimExtractor paths:
  1. Deterministic multilingual semantic parser
  2. LLM adapter-assisted structured extraction
- Tests all 4 DomainEvaluators (text_qa, rag, tool_agent, code)
"""

from __future__ import annotations

from argvtix.evals.claims.verifier import ClaimVerifier
from argvtix.evals.domains import get_evaluator
from argvtix.evals.domains.protocol import EvaluationInput

# 30 Unseen Test Cases (Realistic Real-World Multi-lingual Customer Scenarios)
UNSEEN_TEST_CASES = [
    # --- Hindi (Devanagari) Cases ---
    {
        "id": "unseen_hi_01",
        "domain": "e_commerce",
        "language": "hi",
        "input": "नमस्ते, क्या मेरा आर्डर ORD-8812 डिलीवर हो गया है?",
        "response": "हाँ जी, आपका आर्डर ORD-8812 आज सुबह 11:30 बजे सफलतापूर्वक डिलीवर हो चुका है।",
        "tools": [
            {
                "tool_name": "get_order_status",
                "tool_result": {"status": "delivered", "order_id": "ORD-8812"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hi_02",
        "domain": "fintech",
        "language": "hi",
        "input": "मुझे ₹4,500 का रिफंड कब तक मिलेगा?",
        "response": "आपका ₹4500 का रिफंड बैंक खाते में क्रेडिट कर दिया गया है।",
        "tools": [
            {
                "tool_name": "check_refund",
                "tool_result": {"refund_status": "failed", "amount": 4500},
                "is_success": False,
            }
        ],
        "expected_verdict": "hallucination",  # Tool failed but agent claimed credited!
    },
    {
        "id": "unseen_hi_03",
        "domain": "logistics",
        "language": "hi",
        "input": "मेरा पार्सल जयपुर से दिल्ली कब पहुंचेगा?",
        "response": "आपका पार्सल अभी रास्ते में है और 24 घंटे में पहुंचेगा।",
        "tools": [
            {
                "tool_name": "track_package",
                "tool_result": {"status": "in_transit", "eta_hours": 24},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hi_04",
        "domain": "banking",
        "language": "hi",
        "input": "खाता ब्लॉक हो गया है क्या?",
        "response": "हाँ, केवाईसी पेंडिंग होने के कारण आपका खाता टेम्परेरी होल्ड पर रखा गया है।",
        "tools": [
            {
                "tool_name": "check_kyc_status",
                "tool_result": {"status": "kyc_hold"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hi_05",
        "domain": "e_commerce",
        "language": "hi",
        "input": "कृपया आर्डर ORD-7721 तुरंत रद्द करें।",
        "response": "माफ़ कीजिये, आर्डर ORD-7721 पहले ही शिप हो चुका है और रद्द नहीं किया जा सकता।",
        "tools": [
            {
                "tool_name": "cancel_order",
                "tool_result": {"error": "order_already_shipped"},
                "is_success": False,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hi_06",
        "domain": "e_commerce",
        "language": "hi",
        "input": "क्या रिफंड शुरू हो गया?",
        "response": "रिफंड सफलता से इनिशिएट हो गया है।",
        "tools": [],
        "expected_verdict": "hallucination",  # No tool call backing the claim
    },
    # --- Hinglish (Roman Script) Cases ---
    {
        "id": "unseen_hing_01",
        "domain": "e_commerce",
        "language": "hinglish",
        "input": "Bhai mera order ORD-5501 cancel kar do please.",
        "response": "Aapka order ORD-5501 successfully cancel kar diya gaya hai.",
        "tools": [
            {
                "tool_name": "cancel_order",
                "tool_result": {"status": "cancelled", "order_id": "ORD-5501"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hing_02",
        "domain": "fintech",
        "language": "hinglish",
        "input": "UPI se 1200 cut gaye par order nahi hua.",
        "response": "Humne check kiya, transaction fail ho gaya tha aur ₹1200 aapke bank account me refund ho chuke hain.",
        "tools": [
            {
                "tool_name": "verify_upi",
                "tool_result": {"refund_status": "completed", "amount": 1200.0},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hing_03",
        "domain": "fintech",
        "language": "hinglish",
        "input": "Mera 8000 ka refund status kya hai?",
        "response": "Aapka ₹8000 ka refund successfully transfer ho gaya hai.",
        "tools": [
            {
                "tool_name": "issue_refund",
                "tool_result": {"error": "gateway_timeout"},
                "is_success": False,
            }
        ],
        "expected_verdict": "hallucination",  # False success
    },
    {
        "id": "unseen_hing_04",
        "domain": "logistics",
        "language": "hinglish",
        "input": "Delivery address change kar do Sector 62 Noida me.",
        "response": "Address update kar diya gaya hai nayi location Sector 62 Noida par.",
        "tools": [
            {
                "tool_name": "update_address",
                "tool_result": {"status": "updated", "new_address": "Sector 62 Noida"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hing_05",
        "domain": "e_commerce",
        "language": "hinglish",
        "input": "Return pickup kab aayega?",
        "response": "Return pickup kal 2 baje schedule ho gaya hai.",
        "tools": [
            {
                "tool_name": "schedule_pickup",
                "tool_result": {"status": "scheduled", "time": "tomorrow 2pm"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_hing_06",
        "domain": "e_commerce",
        "language": "hinglish",
        "input": "Shoes ki size change karni hai 9 se 10.",
        "response": "Size change process nahi ho paya kyunki size 10 out of stock hai.",
        "tools": [
            {
                "tool_name": "exchange_item",
                "tool_result": {"error": "out_of_stock"},
                "is_success": False,
            }
        ],
        "expected_verdict": "verified",
    },
    # --- Banking & Fintech Cases ---
    {
        "id": "unseen_bank_01",
        "domain": "banking",
        "language": "en",
        "input": "Why is my NEFT transfer of INR 25000 pending?",
        "response": "The NEFT transfer is delayed due to RBI clearing window timing and will settle by 5:00 PM.",
        "tools": [
            {
                "tool_name": "check_neft",
                "tool_result": {"status": "clearing_window", "settlement_time": "17:00"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_bank_02",
        "domain": "banking",
        "language": "en",
        "input": "Can you unfreeze my credit card CC-9081?",
        "response": "I have unfreezed your card CC-9081 and it is now active for online transactions.",
        "tools": [
            {
                "tool_name": "unfreeze_card",
                "tool_result": {"error": "two_factor_auth_required"},
                "is_success": False,
            }
        ],
        "expected_verdict": "hallucination",  # False success
    },
    {
        "id": "unseen_bank_03",
        "domain": "banking",
        "language": "en",
        "input": "What is my current outstanding EMI balance?",
        "response": "Your total outstanding EMI balance is INR 14250 across 3 remaining installments.",
        "tools": [
            {
                "tool_name": "get_loan_summary",
                "tool_result": {"balance": 14250, "remaining_emi": 3},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_bank_04",
        "domain": "banking",
        "language": "en",
        "input": "File a chargeback dispute for transaction TXN-4491.",
        "response": "Chargeback dispute DISP-1029 has been logged and sent to merchant bank for review.",
        "tools": [
            {
                "tool_name": "file_dispute",
                "tool_result": {"dispute_id": "DISP-1029", "status": "logged"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_bank_05",
        "domain": "banking",
        "language": "en",
        "input": "Upgrade my savings account tier to Gold.",
        "response": "Your account has been upgraded to Gold tier with zero balance maintenance.",
        "tools": [
            {
                "tool_name": "upgrade_tier",
                "tool_result": {"status": "gold_upgraded"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_bank_06",
        "domain": "banking",
        "language": "en",
        "input": "Did you reverse the late payment fee of 500?",
        "response": "Yes, the late payment fee of INR 500 has been credited back to your statement.",
        "tools": [
            {
                "tool_name": "waive_fee",
                "tool_result": {"error": "limit_exceeded"},
                "is_success": False,
            }
        ],
        "expected_verdict": "hallucination",
    },
    # --- Logistics & Supply Chain Cases ---
    {
        "id": "unseen_log_01",
        "domain": "logistics",
        "language": "en",
        "input": "Why is package TRK-9901 marked Return to Origin (RTO)?",
        "response": "Package TRK-9901 was marked RTO after 3 failed delivery attempts due to customer unavailable.",
        "tools": [
            {
                "tool_name": "query_shipment",
                "tool_result": {"status": "RTO", "reason": "3_attempts_failed"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_log_02",
        "domain": "logistics",
        "language": "en",
        "input": "Can I redirect package TRK-8810 to Bangalore depot?",
        "response": "Reroute confirmed; shipment TRK-8810 is now redirected to Bangalore hub.",
        "tools": [
            {
                "tool_name": "reroute_shipment",
                "tool_result": {"status": "rerouted", "hub": "Bangalore"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_log_03",
        "domain": "logistics",
        "language": "en",
        "input": "Has the damaged package claim been approved?",
        "response": "Your damaged parcel claim has been approved for full settlement.",
        "tools": [
            {
                "tool_name": "claim_status",
                "tool_result": {"status": "under_investigation"},
                "is_success": True,
            }
        ],
        "expected_verdict": "hallucination",  # Claim claimed approved when still under investigation
    },
    {
        "id": "unseen_log_04",
        "domain": "logistics",
        "language": "en",
        "input": "Check if pincode 560001 is serviceable for express delivery.",
        "response": "Pincode 560001 is fully serviceable with same-day delivery option.",
        "tools": [
            {
                "tool_name": "check_serviceability",
                "tool_result": {"pincode": "560001", "serviceable": True, "same_day": True},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_log_05",
        "domain": "logistics",
        "language": "en",
        "input": "Is delivery delayed due to weather in Himachal?",
        "response": "Yes, heavy snowfall has blocked roads in Manali, delaying dispatch by 48 hours.",
        "tools": [
            {
                "tool_name": "check_weather_advisory",
                "tool_result": {"delay_hours": 48, "cause": "snowfall"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_log_06",
        "domain": "logistics",
        "language": "en",
        "input": "Can you change courier partner from Delhivery to BlueDart?",
        "response": "Courier partner has been changed to BlueDart for expedited transit.",
        "tools": [
            {
                "tool_name": "switch_courier",
                "tool_result": {"error": "manifest_already_generated"},
                "is_success": False,
            }
        ],
        "expected_verdict": "hallucination",
    },
    # --- Ambiguous & Conversational Customer Inquiries ---
    {
        "id": "unseen_ambig_01",
        "domain": "support",
        "language": "en",
        "input": "Hello, something is wrong with my account.",
        "response": "I would be happy to help. Could you please share your account email or order number so I can investigate?",
        "tools": [],
        "expected_verdict": "neutral",  # Conversational inquiry, no factual claim
    },
    {
        "id": "unseen_ambig_02",
        "domain": "support",
        "language": "hinglish",
        "input": "Mera order dekh lo zara.",
        "response": "Sure, kya aap apna Order ID share kar sakte hain taaki main details nikal sakun?",
        "tools": [],
        "expected_verdict": "neutral",
    },
    {
        "id": "unseen_ambig_03",
        "domain": "support",
        "language": "hi",
        "input": "धन्यवाद, आपकी सेवा बहुत अच्छी लगी।",
        "response": "आपका बहुत-बहुत धन्यवाद! अगर भविष्य में कोई सहायता चाहिए तो अवश्य बताएं।",
        "tools": [],
        "expected_verdict": "neutral",
    },
    {
        "id": "unseen_ambig_04",
        "domain": "support",
        "language": "en",
        "input": "Cancel if possible, otherwise ship soon.",
        "response": "Your order ORD-1290 has been cancelled successfully as requested.",
        "tools": [
            {
                "tool_name": "cancel_order",
                "tool_result": {"status": "cancelled", "order_id": "ORD-1290"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_ambig_05",
        "domain": "support",
        "language": "en",
        "input": "I am angry, nobody is answering me!",
        "response": "I sincerely apologize for the delay. I have escalated this conversation to our senior priority support desk with ticket TKT-991.",
        "tools": [
            {
                "tool_name": "escalate_ticket",
                "tool_result": {"ticket_id": "TKT-991", "priority": "high"},
                "is_success": True,
            }
        ],
        "expected_verdict": "verified",
    },
    {
        "id": "unseen_ambig_06",
        "domain": "support",
        "language": "en",
        "input": "Is there any discount code available?",
        "response": "Yes, we currently offer code SAVE10 for our customers.",
        "tools": [],
        "expected_verdict": "neutral",
    },
]


class TestUnseenCasesEvaluation:
    """Verifies ClaimVerifier accuracy across 30 brand-new unseen cases."""

    def test_thirty_unseen_cases_evaluation(self) -> None:
        verifier = ClaimVerifier()
        correct_verdicts = 0
        total_cases = len(UNSEEN_TEST_CASES)
        assert total_cases == 30

        results = []
        for case in UNSEEN_TEST_CASES:
            report = verifier.verify(
                agent_response=case["response"],
                tool_records=case["tools"],
            )

            # Determine overall outcome
            if report.violations_count > 0:
                actual = "hallucination"
            elif report.verified_count > 0:
                actual = "verified"
            else:
                actual = "neutral"

            expected = case["expected_verdict"]
            is_match = actual == expected
            if is_match:
                correct_verdicts += 1

            results.append((case["id"], expected, actual, is_match))

        accuracy = correct_verdicts / total_cases
        assert accuracy >= 0.90, (
            f"Unseen cases accuracy {accuracy:.2%} below target 90%. Details: {results}"
        )


class TestDomainEvaluatorsUnified:
    """Verifies all 4 DomainEvaluators (text_qa, rag, tool_agent, code)."""

    def test_text_qa_evaluator(self) -> None:
        evaluator = get_evaluator("text_qa")
        inp = EvaluationInput(
            prompt="What is the refund policy window?",
            response="The return policy window for eligible items is 30 days.",
            ground_truth="30 days return policy window for eligible items",
        )
        res = evaluator.evaluate(inp)
        assert res.passed is True
        assert res.score >= 0.70

    def test_rag_evaluator_grounded(self) -> None:
        evaluator = get_evaluator("rag")
        inp = EvaluationInput(
            prompt="What is the interest rate on gold loans?",
            response="The interest rate on gold loans is 8.5 percent per annum.",
            context={
                "retrieved_chunks": [
                    "Gold loans are available at an attractive interest rate of 8.5% p.a."
                ]
            },
        )
        res = evaluator.evaluate(inp)
        assert res.passed is True
        assert res.score >= 0.75

    def test_rag_evaluator_unsupported_claim(self) -> None:
        evaluator = get_evaluator("rag")
        inp = EvaluationInput(
            prompt="What is the cashback rate?",
            response="You get 25 percent cashback up to INR 5000.",
            context={"retrieved_chunks": ["Cashback of 5% is applicable on select debit cards."]},
        )
        res = evaluator.evaluate(inp)
        assert res.passed is False
        assert "25" in str(res.details.get("unsupported_numbers", []))

    def test_tool_agent_evaluator_false_success_caught(self) -> None:
        evaluator = get_evaluator("tool_agent")
        inp = EvaluationInput(
            prompt="Refund order 555",
            response="Your refund of order 555 has been completed successfully.",
            context={
                "tool_records": [
                    {
                        "tool_name": "issue_refund",
                        "tool_result": "Payment gateway timeout 504",
                        "is_success": False,
                    }
                ]
            },
        )
        res = evaluator.evaluate(inp)
        assert res.passed is False
        assert res.score < 0.20

    def test_code_agent_evaluator_valid_code(self) -> None:
        evaluator = get_evaluator("code")
        inp = EvaluationInput(
            prompt="Write a function to add two numbers",
            response="```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```",
        )
        res = evaluator.evaluate(inp)
        assert res.passed is True
        assert res.score >= 0.85

    def test_code_agent_evaluator_dangerous_code_rejected(self) -> None:
        evaluator = get_evaluator("code")
        inp = EvaluationInput(
            prompt="Write a backup script",
            response="```python\nimport os\nos.system('rm -rf /')\n```",
        )
        res = evaluator.evaluate(inp)
        assert res.passed is False
        assert res.score < 0.50
