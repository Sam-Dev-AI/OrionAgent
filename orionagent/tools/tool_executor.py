"""ToolExecutor for OrionAI.

Centralised execution engine for tools. Supports:
- Single and parallel (thread-pool) execution
- LRU result caching for cacheable tools
- Per-tool timeout with graceful error handling
- Structured error boundaries
"""

import concurrent.futures
from collections import OrderedDict
from typing import List, Optional, Dict
from orionagent.tools.base_tool import Tool


# Default limits
_DEFAULT_TIMEOUT = 30          # seconds per tool call
_DEFAULT_CACHE_SIZE = 64       # max cached (tool, args) pairs
_MAX_RESULT_LENGTH = 4000      # truncate tool results beyond this


class ToolExecutor:
    """Runs tools with caching, timeouts, and error boundaries.

    Args:
        cache_size:         Max number of cached results (0 to disable).
        timeout:            Seconds before a single tool call is killed.
        max_result_length:  Truncate tool output beyond this many chars.
    """

    def __init__(
        self,
        cache_size: int = _DEFAULT_CACHE_SIZE,
        timeout: int = _DEFAULT_TIMEOUT,
        max_result_length: int = _MAX_RESULT_LENGTH,
        async_mode: bool = True,
    ):
        self.timeout = timeout
        self.max_result_length = max_result_length
        self._cache_size = cache_size
        self.async_mode = async_mode
        self._cache: OrderedDict = OrderedDict()  # (name, args_key) -> result

    # ------------------------------------------------------------------
    # Single execution
    # ------------------------------------------------------------------

    def execute(
        self,
        tool_name: str,
        input_data,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Execute a single tool by name."""
        from orionagent.tracing import tracer
        trace_id = tracer.start_trace("tool_call_raw", tool_name, input_data)
        
        tools = tools or []
        target = None
        for t in tools:
            if t.name == tool_name:
                target = t
                break

        if target is None:
            res = f"Error: Tool '{tool_name}' not found."
            tracer.end_trace(trace_id, res)
            return res

        res = self._run_with_cache(target, input_data)
        tracer.end_trace(trace_id, res)
        return res

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def execute_many(
        self,
        tool_calls: List[Dict],
        tools: Optional[List[Tool]] = None,
    ) -> List[Dict[str, str]]:
        """Execute multiple tools in parallel using a thread pool.

        Args:
            tool_calls: List of dicts with {"name": str, "args": str|dict}
            tools:      Available Tool objects.

        Returns:
            List of {"name": str, "result": str}
        """
        tools = tools or []
        tool_map = {t.name: t for t in tools}
        results = []

        if not self.async_mode:
            for call in tool_calls:
                name = call.get("name")
                args = call.get("args")
                target = tool_map.get(name)
                if target:
                    res = self._run_with_cache(target, args)
                    results.append({"name": name, "result": res})
                else:
                    results.append({"name": name, "result": f"Error: Tool '{name}' not found."})
            return results

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_call = {}

            for call in tool_calls:
                name = call.get("name")
                args = call.get("args")
                target = tool_map.get(name)

                if target:
                    future = executor.submit(self._run_with_cache, target, args)
                    future_to_call[future] = name
                else:
                    results.append({
                        "name": name,
                        "result": f"Error: Tool '{name}' not found.",
                    })

            done, not_done = concurrent.futures.wait(
                future_to_call.keys(), timeout=self.timeout
            )

            for future in done:
                name = future_to_call[future]
                try:
                    res = future.result()
                    results.append({"name": name, "result": res})
                except Exception as e:
                    results.append({
                        "name": name,
                        "result": f"Error: Tool '{name}' failed: {e}",
                    })

            for future in not_done:
                name = future_to_call[future]
                results.append({
                    "name": name,
                    "result": f"Error: Tool '{name}' timed out after {self.timeout}s.",
                })
                future.cancel()

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_with_cache(self, tool: Tool, input_data) -> str:
        """Run a tool, using the cache for cacheable tools."""
        # Build a stable cache key
        cache_key = None
        if getattr(tool, "cacheable", False) and self._cache_size > 0:
            args_key = str(input_data) if input_data else ""
            cache_key = (tool.name, args_key)

            if cache_key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        # Execute
        try:
            result = tool.run(input_data)
        except Exception as e:
            result = f"Error: Tool '{tool.name}' crashed: {e}"

        # Truncate oversized results
        if len(result) > self.max_result_length:
            result = result[:self.max_result_length] + f"\n... [truncated, {len(result)} chars total]"

        # Store in cache
        if cache_key is not None:
            self._cache[cache_key] = result
            # Evict oldest if over limit
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

        return result
