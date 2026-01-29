"""
Diagnostics - Comprehensive logging for API usage and token tracking
=====================================================================
Tracks every API call, tool usage, token counts, and costs.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from config_loader import get_config


class APICallLogger:
    """Logs detailed information about every API call."""

    def __init__(self):
        self.logger = logging.getLogger("diagnostics")
        self.cfg = get_config()

        log_folder = os.path.dirname(self.cfg.log_file)
        self.diagnostics_file = os.path.join(log_folder, f"api_diagnostics_{datetime.now().strftime('%Y-%m-%d')}.jsonl")

        self.session_stats = {
            "session_start": datetime.now().isoformat(),
            "total_api_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cached_tokens": 0,
            "emails_processed": 0,
            "tool_calls": {},
            "tool_result_sizes": {},
            "estimated_cost": 0.0
        }

    def log_api_call(
        self,
        email_subject: str,
        email_sender: str,
        iteration: int,
        response: Any,
        system_prompt_chars: int,
        tools_chars: int,
        messages_chars: int,
        tool_calls_this_iteration: List[str] = None,
        tool_results_chars: int = 0
    ):
        """Log detailed information about an API call."""

        usage = getattr(response, 'usage', None)
        # Note: Anthropic API returns input_tokens as non-cached tokens only
        # cache_creation_input_tokens and cache_read_input_tokens are additional
        base_input_tokens = getattr(usage, 'input_tokens', 0) if usage else 0
        output_tokens = getattr(usage, 'output_tokens', 0) if usage else 0
        cache_creation_tokens = getattr(usage, 'cache_creation_input_tokens', 0) if usage else 0
        cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0) if usage else 0

        # Total input tokens = base + cache_creation + cache_read
        input_tokens = base_input_tokens + cache_creation_tokens + cache_read_tokens

        # Sonnet pricing: $3/M input, $15/M output, $0.30/M cached read, $3.75/M cached write
        # Base tokens charged at full rate, cache reads at discount, cache writes at premium
        input_cost = base_input_tokens * 3.0 / 1_000_000
        cache_write_cost = cache_creation_tokens * 3.75 / 1_000_000
        cached_read_cost = cache_read_tokens * 0.30 / 1_000_000
        output_cost = output_tokens * 15.0 / 1_000_000
        total_cost = input_cost + cache_write_cost + cached_read_cost + output_cost

        entry = {
            "timestamp": datetime.now().isoformat(),
            "email": {
                "subject": email_subject[:100] if email_subject else "N/A",
                "sender": email_sender[:50] if email_sender else "N/A"
            },
            "iteration": iteration,
            "tokens": {
                "input_total": input_tokens,
                "input_base": base_input_tokens,
                "output_total": output_tokens,
                "cache_creation": cache_creation_tokens,
                "cache_read": cache_read_tokens
            },
            "breakdown_chars": {
                "system_prompt": system_prompt_chars,
                "tools": tools_chars,
                "messages": messages_chars,
                "tool_results_this_iter": tool_results_chars
            },
            "tool_calls": tool_calls_this_iteration or [],
            "cost_estimate_usd": round(total_cost, 6),
            "stop_reason": response.stop_reason if response else "unknown"
        }

        self.session_stats["total_api_calls"] += 1
        self.session_stats["total_input_tokens"] += input_tokens
        self.session_stats["total_output_tokens"] += output_tokens
        self.session_stats["total_cached_tokens"] += cache_read_tokens
        self.session_stats["estimated_cost"] += total_cost

        for tool in (tool_calls_this_iteration or []):
            self.session_stats["tool_calls"][tool] = self.session_stats["tool_calls"].get(tool, 0) + 1

        try:
            with open(self.diagnostics_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write diagnostics: {e}")

        # Show cache breakdown in log
        cache_info = ""
        if cache_creation_tokens > 0:
            cache_info = f" (cache_write: {cache_creation_tokens:,})"
        elif cache_read_tokens > 0:
            cache_info = f" (cache_read: {cache_read_tokens:,})"

        self.logger.info(
            f"    [API] iter={iteration} | in={input_tokens:,} out={output_tokens:,}{cache_info} | "
            f"${total_cost:.4f} | tools: {tool_calls_this_iteration or 'none'}"
        )

        return entry

    def log_tool_result_size(self, tool_name: str, result: str):
        """Log the size of a tool result for analysis."""
        result_chars = len(result) if isinstance(result, str) else len(json.dumps(result))
        estimated_tokens = result_chars // 4

        # Track in session stats
        if tool_name not in self.session_stats["tool_result_sizes"]:
            self.session_stats["tool_result_sizes"][tool_name] = {"total_chars": 0, "count": 0, "max": 0}

        stats = self.session_stats["tool_result_sizes"][tool_name]
        stats["total_chars"] += result_chars
        stats["count"] += 1
        stats["max"] = max(stats["max"], result_chars)

        if estimated_tokens > 2000:
            self.logger.warning(
                f"    [LARGE RESULT] {tool_name}: {result_chars:,} chars (~{estimated_tokens:,} tokens)"
            )

        return result_chars

    def log_email_complete(self, email_subject: str, total_iterations: int, actions: List[str]):
        """Log when an email is fully processed."""
        self.session_stats["emails_processed"] += 1
        self.logger.info(
            f"  [COMPLETE] {email_subject[:50]} | iters: {total_iterations} | actions: {actions}"
        )

    def get_session_summary(self) -> dict:
        """Get summary of this session's API usage."""
        stats = self.session_stats.copy()

        if stats["total_api_calls"] > 0:
            stats["avg_input_tokens_per_call"] = stats["total_input_tokens"] // stats["total_api_calls"]
            stats["cache_hit_rate"] = round(
                stats["total_cached_tokens"] / max(stats["total_input_tokens"], 1) * 100, 1
            )

        # Calculate avg tool result sizes
        for tool, data in stats.get("tool_result_sizes", {}).items():
            if data["count"] > 0:
                data["avg_chars"] = data["total_chars"] // data["count"]

        return stats

    def print_session_summary(self):
        """Print a formatted session summary."""
        stats = self.get_session_summary()

        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Emails processed: {stats['emails_processed']}")
        print(f"Total API calls: {stats['total_api_calls']}")
        print(f"Total input tokens: {stats['total_input_tokens']:,}")
        print(f"Total output tokens: {stats['total_output_tokens']:,}")
        print(f"Cached tokens: {stats['total_cached_tokens']:,} ({stats.get('cache_hit_rate', 0)}% hit rate)")
        print(f"Estimated cost: ${stats['estimated_cost']:.4f}")

        if stats.get("tool_calls"):
            print(f"\nTool calls (top 10):")
            for tool, count in sorted(stats['tool_calls'].items(), key=lambda x: -x[1])[:10]:
                print(f"  {tool}: {count}")

        if stats.get("tool_result_sizes"):
            print(f"\nLargest tool results (by max size):")
            sorted_tools = sorted(stats['tool_result_sizes'].items(), key=lambda x: -x[1]['max'])[:5]
            for tool, data in sorted_tools:
                print(f"  {tool}: max={data['max']:,} chars, avg={data.get('avg_chars', 0):,} chars")

        print("=" * 60 + "\n")


_diagnostics = None

def get_diagnostics() -> APICallLogger:
    """Get the global diagnostics instance."""
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = APICallLogger()
    return _diagnostics
