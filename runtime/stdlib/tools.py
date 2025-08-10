import os
import subprocess
import json
import urllib.request
import urllib.parse


def register(reg):
    def tool_call(a, ctx):
        """Call an external tool defined with @tool."""
        tool_id = a.get("tool")
        if not tool_id:
            raise RuntimeError("tool_call requires 'tool' parameter")

        tools = ctx.get("tools", {})
        if tool_id not in tools:
            raise RuntimeError(f"Unknown tool: {tool_id}")

        tool_def = tools[tool_id]
        args = a.get("args", {})

        # Validate input against tool's input schema if specified
        input_schema = tool_def.get("input_schema")
        if input_schema and input_schema in ctx.get("shapes", {}):
            try:
                # Import validation function dynamically to avoid circular imports
                import importlib
                vm_module = importlib.import_module("runtime.vm")
                validate_against_shape = vm_module.validate_against_shape
                validate_against_shape(args, input_schema, ctx.get("shapes", {}))
            except Exception as e:
                raise RuntimeError(f"Tool input validation failed: {e}")

        # Execute the tool based on its implementation type
        implementation = tool_def.get("implementation", {})
        impl_type = implementation.get("type")

        if impl_type == "command":
            return _execute_command_tool(tool_def, args, implementation)
        elif impl_type == "http":
            return _execute_http_tool(tool_def, args, implementation)
        elif impl_type == "python":
            return _execute_python_tool(tool_def, args, implementation)
        else:
            raise RuntimeError(f"Unsupported tool implementation type: {impl_type}")

    def _execute_command_tool(tool_def, args, implementation):
        """Execute a command-line tool."""
        command = implementation.get("command")
        if not command:
            raise RuntimeError("Command tool requires 'command' in implementation")

        # Replace placeholders in command with arguments
        try:
            formatted_command = command.format(**args)
        except KeyError as e:
            raise RuntimeError(f"Missing argument for command placeholder: {e}")

        # Execute command with security restrictions
        if not _is_command_allowed(formatted_command):
            raise RuntimeError("Command not allowed by security policy")

        try:
            result = subprocess.run(
                formatted_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=os.getenv("ALP_TOOL_CWD", os.getcwd())
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed with code {result.returncode}: {result.stderr}")

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            raise RuntimeError("Command timed out after 30 seconds")
        except Exception as e:
            raise RuntimeError(f"Command execution failed: {e}")

    def _execute_http_tool(tool_def, args, implementation):
        """Execute an HTTP API tool."""
        url = implementation.get("url")
        method = implementation.get("method", "GET").upper()

        if not url:
            raise RuntimeError("HTTP tool requires 'url' in implementation")

        # Replace placeholders in URL with arguments
        try:
            formatted_url = url.format(**args)
        except KeyError as e:
            raise RuntimeError(f"Missing argument for URL placeholder: {e}")

        # Check URL allowlist
        if not _is_http_url_allowed(formatted_url):
            raise RuntimeError("HTTP URL not allowed by security policy")

        # Prepare request
        headers = implementation.get("headers", {})
        if "json_body" in implementation:
            headers.setdefault("Content-Type", "application/json")
            data = json.dumps(args).encode("utf-8")
        else:
            data = None

        try:
            req = urllib.request.Request(url=formatted_url, method=method, headers=headers)
            with urllib.request.urlopen(req, data=data, timeout=30) as resp:
                response_text = resp.read().decode("utf-8")

            # Try to parse as JSON, fallback to text
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                response_data = response_text

            return {
                "status": resp.status,
                "data": response_data,
                "headers": dict(resp.headers)
            }
        except Exception as e:
            raise RuntimeError(f"HTTP request failed: {e}")

    def _execute_python_tool(tool_def, args, implementation):
        """Execute a Python function tool."""
        module_name = implementation.get("module")
        function_name = implementation.get("function")

        if not module_name or not function_name:
            raise RuntimeError("Python tool requires 'module' and 'function' in implementation")

        # Security: only allow whitelisted modules
        allowed_modules = os.getenv("ALP_TOOL_PYTHON_MODULES", "").split(",")
        if module_name not in allowed_modules:
            raise RuntimeError(f"Python module '{module_name}' not in allowlist")

        try:
            module = __import__(module_name, fromlist=[function_name])
            func = getattr(module, function_name)
            result = func(args)
            return result
        except Exception as e:
            raise RuntimeError(f"Python tool execution failed: {e}")

    def _is_command_allowed(command):
        """Check if command is allowed by security policy."""
        # Basic security: check against dangerous commands
        dangerous_patterns = ["rm ", "del ", "format", "sudo", "su ", "chmod +x"]
        command_lower = command.lower()

        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return False

        # Check allowlist if specified
        allowlist = os.getenv("ALP_TOOL_COMMAND_ALLOWLIST", "").strip()
        if allowlist:
            allowed_commands = [cmd.strip() for cmd in allowlist.split(",")]
            return any(command.startswith(allowed_cmd) for allowed_cmd in allowed_commands)

        # Default: allow if no explicit restrictions
        return os.getenv("ALP_TOOL_ALLOW_COMMANDS", "0") == "1"

    def _is_http_url_allowed(url):
        """Check if HTTP URL is allowed by security policy."""
        # Reuse existing HTTP allowlist logic
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if not host:
            return False

        allowlist = os.getenv("ALP_HTTP_ALLOWLIST", "").strip()
        if not allowlist:
            return False
        allowed_hosts = {h.strip().lower() for h in allowlist.split(",") if h.strip()}
        return host.lower() in allowed_hosts

    reg("tool_call", tool_call)
