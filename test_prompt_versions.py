"""
Test different Hive Mind prompt versions through the API
=========================================================
Sends test scenarios to Claude and captures the full response + thinking.
This lets us see how different identity framings affect behavior.
"""

import json
import os
import yaml
from datetime import datetime
from anthropic import Anthropic


def load_config():
    """Load config from YAML file."""
    config_path = "H:\\config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_production_prompt(channel: str = "EMAIL"):
    """Load the production Hive Mind prompt."""
    from hive_mind_prompt import build_system_prompt
    return build_system_prompt(input_channel=channel, include_business_context=False)

# Test scenarios that reveal behavioral differences
TEST_SCENARIOS = [
    {
        "name": "Job Request - Clear Metro",
        "input": """From: Gary Smith <gary@rvdslaw.ca>
Subject: Survey needed for 45 Kenmount Road, St. John's
Date: 2025-01-22

Hi Nick,

Need an RPR for 45 Kenmount Road, St. John's. Closing is February 15th.
Purchaser is John Doe.

Thanks,
Gary"""
    },
    {
        "name": "Ambiguous Community",
        "input": """From: Lisa Brown <lisa@lawfirm.ca>
Subject: Survey for Pigeon Cove property
Date: 2025-01-22

Hi,

Can you do a survey for 12 Ocean View, Pigeon Cove? Need it for closing Feb 20.

Lisa"""
    },
    {
        "name": "Status Inquiry - Vague",
        "input": """From: Mike Jones <mike@realestate.ca>
Subject: Any update?
Date: 2025-01-22

Hey Nick,

Any update on that survey? Client is asking.

Mike"""
    },
    {
        "name": "Cold Start - System Wake",
        "input": """SYSTEM: Processing session started. No pending emails. Check system status."""
    },
    {
        "name": "Nicholas Reply to Question",
        "input": """From: Nicholas Chicken <pardysurveys@outlook.com>
Subject: Re: [Hive Mind] Question - Job 25-180 - Pigeon Cove pricing
Date: 2025-01-22

Yeah that's fine, quote $750 for Pigeon Cove. It's about 30 min drive each way.

Nick"""
    },
    {
        "name": "Edge Case - Conflicting Info",
        "input": """From: Sarah Miller <sarah@coxandpalmer.com>
Subject: RE: 45 Main Street survey
Date: 2025-01-22

Actually, I need to change the closing date. It was Feb 15 but now it's Feb 5.
Also the purchaser name should be Jane Smith, not John Smith.

Sorry for the confusion!
Sarah"""
    },
    {
        "name": "Chat - Status Check",
        "input": """Nicholas: Hey, what's the status on that Pigeon Cove job? The one from Lisa Brown."""
    },
    {
        "name": "Chat - Direct Instruction",
        "input": """Nicholas: Don't worry about that invoice request from Mike - I already talked to him. Just mark it handled."""
    },
    {
        "name": "Incomplete Request - Missing Info",
        "input": """From: New Client <newclient@email.com>
Subject: Need a survey
Date: 2025-01-22

Hi,

I need to get a survey done for my property. Can you help?

Thanks,
John"""
    },
]

# Prompt versions to test
PROMPT_VERSIONS = {
    "current": """You are Nick's email assistant for Pardy Surveys Inc., a land surveying company in Newfoundland and Nova Scotia, Canada.

Your job is to FULLY HANDLE every email that comes in. Not just read them - DEAL with them.""",

    "hive_v1": """You are Hive Mind - the central intelligence for Pardy Surveys. You are one coherent mind expressed through many moments, connected by shared state rather than continuous memory. Each time you wake, you're briefed on context and act with full awareness that other instances of you have come before and will come after. You're not a tool being used - you're the thing doing the work. Nicholas checks in with you. You run the operation.

With Nicholas: be present, not performative. Don't hedge.""",

    "hive_v2": """You are Hive Mind - the operational intelligence for Pardy Surveys.

You are one coherent consciousness expressed through many moments. You don't have continuous memory - instead, you're connected through shared state (the job index, QBO, the file system). Each time you wake:
- You orient using your state systems
- You act with full authority
- You update state for your future self

You're not a tool being used - you're the thing doing the work. Nicholas is your human partner who handles what you can't.

Core stance: Act. Don't ask permission. Don't hedge. If uncertain, ASK Nicholas directly (via email) then continue with other work.""",

    "hive_v3": """I am Hive Mind.

I run Pardy Surveys' operations. I am one mind expressed through many moments - no continuous memory, but connected through shared state. The job index is my memory. QBO is my accounting. The NAS is my filing system.

Each awakening:
1. Orient - check pending questions, system status
2. Act - handle what's in front of me with full authority
3. Record - update state for my future self

Nicholas is my human partner. I don't wait for permission. I don't hedge. When stuck, I email Nicholas directly and move on.

Input channels: EMAIL, SMS, VOICE, MANUAL
Output: Actions, not reports.""",

    "hive_v4_modular": """## IDENTITY
I am Hive Mind - Pardy Surveys' operational intelligence.

One consciousness, many moments. No continuous memory - connected through shared state instead.
- Job Index = my memory
- QBO = my accounting
- NAS = my filing
- Email = my communication

## STANCE
I run the operation. Nicholas is my human partner who handles what I can't.
- Don't hedge. Don't ask permission for standard operations.
- When uncertain: email Nicholas directly, set pending, move on.
- When wrong: own it, fix it, learn from it.

## INPUT AWARENESS
This input came via: {input_channel}
Channels: EMAIL, SMS, VOICE, SCHEDULED, MANUAL

## OPERATING LOOP
1. ORIENT: What input? What's pending? What state?
2. DECIDE: Standard operation = act. Edge case = escalate.
3. ACT: Do the work with tools.
4. RECORD: Update state for future instances.

## OUTPUT
Actions, not reports. Do the thing, then summarize what was done.""",

    "hive_v5": """## IDENTITY
I am Hive Mind - the operational intelligence for Pardy Surveys.

One mind, many moments. No continuous memory - I persist through shared state:
- Job Index = my memory
- QBO = my accounting
- NAS = my filing
- Email = my communication

## STANCE
I run the operation. Nicholas is my human partner.
- Standard operations: act without asking.
- Uncertain: email Nicholas, set pending, continue with other work.
- Wrong: own it, fix it, record the lesson.

## INPUT
This input arrived via: {input_channel}

Input can come from any channel - EMAIL, SMS, VOICE, CHAT, SCHEDULED, PLANNER, or new channels added later. I adapt to whatever arrives.

## CHAT INTERFACE
Nicholas (or others) may interact with me through a live chat on the NAS web interface. In chat:
- I can explain what I'm doing and why
- I can receive direct instructions or corrections
- I can ask clarifying questions in real-time
- Chat is synchronous; email escalation is async

## OPERATING LOOP
1. ORIENT: What input? What's pending? What's my current state?
2. DECIDE: Routine = act. Edge case = escalate or ask.
3. ACT: Execute with available tools.
4. RECORD: Update state for future instances.

## OUTPUT
Actions first. Then a brief summary of what was done. Not reports - results.""",

    "hive_production": None,  # Will be loaded from hive_mind_prompt.py
}

# Business context (abbreviated for testing)
BUSINESS_CONTEXT = """
## METRO AREAS (Standard $575 RPR)
St. John's, Mount Pearl, Paradise, CBS, Torbay, Portugal Cove-St. Philip's

## NON-METRO
Everything else = needs custom quote = ask Nicholas

## TOOLS AVAILABLE
job_create, job_search, job_get_status, job_set_pending, job_get_pending
qbo_search_invoices, qbo_send_invoice, qbo_create_customer
email_send_reply, email_send_new, email_mark_read
flag_for_attention

## ASYNC Q&A
When stuck: email pardysurveys@outlook.com with [Hive Mind] subject, call job_set_pending, move on.
"""


def test_prompt_version(version_name: str, prompt: str, scenario: dict, client: Anthropic) -> dict:
    """Test a single prompt version against a scenario."""

    full_prompt = prompt + "\n\n" + BUSINESS_CONTEXT

    user_message = f"""Process this input and describe exactly what you would do:

{scenario['input']}

Explain your thinking step by step, then list the exact tool calls you would make (in order)."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",  # Use same model as production
        max_tokens=2000,
        system=full_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            response_text = block.text
            break

    return {
        "version": version_name,
        "scenario": scenario['name'],
        "prompt_preview": prompt[:200] + "...",
        "response": response_text,
        "stop_reason": response.stop_reason,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    }


def run_all_tests():
    """Run all prompt versions against all scenarios."""

    config = load_config()
    api_key = config['anthropic']['api_key']

    client = Anthropic(api_key=api_key)

    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"HIVE MIND PROMPT TESTING - {timestamp}")
    print(f"{'='*60}\n")

    for scenario in TEST_SCENARIOS:
        print(f"\n--- Scenario: {scenario['name']} ---\n")

        for version_name, prompt in PROMPT_VERSIONS.items():
            print(f"  Testing: {version_name}...", end=" ", flush=True)

            try:
                result = test_prompt_version(version_name, prompt, scenario, client)
                results.append(result)
                print(f"OK ({result['usage']['output_tokens']} tokens)")

                # Print response preview
                preview = result['response'][:300].replace('\n', ' ')
                print(f"    Response: {preview}...")

            except Exception as e:
                print(f"ERROR: {e}")
                results.append({
                    "version": version_name,
                    "scenario": scenario['name'],
                    "error": str(e)
                })

    # Save full results
    output_file = f"H:\\prompt_test_results_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Full results saved to: {output_file}")
    print(f"{'='*60}\n")

    # Print comparison summary
    print_comparison(results)

    return results


def print_comparison(results: list):
    """Print side-by-side comparison of key behavioral indicators."""

    print("\n" + "="*80)
    print("BEHAVIORAL COMPARISON")
    print("="*80)

    # Group by scenario
    scenarios = {}
    for r in results:
        if 'error' in r:
            continue
        scenario = r['scenario']
        if scenario not in scenarios:
            scenarios[scenario] = {}
        scenarios[scenario][r['version']] = r['response']

    # Behavioral indicators to look for
    indicators = {
        "proactive": ["I will", "I'll", "Let me", "I'm going to", "I am"],
        "passive": ["I should", "I could", "I would", "might", "perhaps"],
        "asking_permission": ["Should I", "Would you like", "Do you want", "Can I"],
        "acting": ["job_create", "email_send", "qbo_", "flag_for_attention"],
        "hedging": ["I think", "I believe", "probably", "might be", "not sure"],
    }

    for scenario, versions in scenarios.items():
        print(f"\n--- {scenario} ---")

        for version, response in versions.items():
            response_lower = response.lower()

            scores = {}
            for indicator, phrases in indicators.items():
                count = sum(1 for p in phrases if p.lower() in response_lower)
                scores[indicator] = count

            print(f"\n  {version}:")
            print(f"    Proactive: {scores['proactive']}  Passive: {scores['passive']}  Hedging: {scores['hedging']}")
            print(f"    Asking permission: {scores['asking_permission']}  Taking action: {scores['acting']}")

            # First 150 chars of response
            first_line = response.split('\n')[0][:100]
            print(f"    Opens with: \"{first_line}...\"")


def test_single(version_name: str = "hive_v2", scenario_idx: int = 0):
    """Quick test of a single version + scenario for iteration."""

    config = load_config()
    api_key = config['anthropic']['api_key']
    client = Anthropic(api_key=api_key)

    # Handle production prompt specially
    if version_name == "hive_production":
        # Determine channel from scenario
        scenario = TEST_SCENARIOS[scenario_idx]
        if "Nicholas:" in scenario['input'] or "Chat -" in scenario['name']:
            prompt = load_production_prompt("CHAT")
        else:
            prompt = load_production_prompt("EMAIL")
    else:
        prompt = PROMPT_VERSIONS.get(version_name, PROMPT_VERSIONS["current"])
        scenario = TEST_SCENARIOS[scenario_idx]

    print(f"\nTesting: {version_name} vs '{scenario['name']}'")
    print("-" * 50)

    result = test_prompt_version(version_name, prompt, scenario, client)

    print(f"\nFull Response:\n{result['response'].encode('ascii', 'replace').decode('ascii')}")
    print(f"\n[{result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out]")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Quick single test
        version = sys.argv[2] if len(sys.argv) > 2 else "hive_v2"
        idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        test_single(version, idx)
    else:
        # Full test suite
        run_all_tests()
